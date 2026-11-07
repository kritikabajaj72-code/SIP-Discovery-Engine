"""Classify SIP feedback with Gemini and save the results in batches.

Reads ``data/processed/master_dataset.csv`` and writes
``data/processed/classified_records.csv``. Each finished record id is skipped
on the next run, so an interrupted classification can continue.

The model is asked to use Unknown when the text does not say something.
It must not turn a negative app review into SIP discontinuation, and it must
separate an actual stop from an intention, a pause, a missed instalment, or
general discussion.

Run a small sample first:

    python src/test_classifier.py

The API key is read from ``.env`` and is never written to the log.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTER_PATH = PROJECT_ROOT / "data" / "processed" / "master_dataset.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "classified_records.csv"
ENV_PATH = PROJECT_ROOT / ".env"

# Current free-tier model. Override with GEMINI_MODEL in the environment or .env.
DEFAULT_MODEL = "gemini-3.5-flash-lite"
BATCH_SIZE = 10
MAX_ATTEMPTS = 5
BASE_DELAY_SECONDS = 2.0
BATCH_PAUSE_SECONDS = 1.0
UNKNOWN = "Unknown"

PRESERVED_COLUMNS = [
    "record_id",
    "source",
    "source_type",
    "app",
    "original_text",
    "rating",
    "date",
    "video_title",
    "channel",
    "source_url",
]
CLASSIFICATION_FIELDS = [
    "relevance_to_sip",
    "investor_motivation",
    "journey_stage",
    "pain_point",
    "trigger",
    "behaviour",
    "emotion",
    "root_cause",
    "root_cause_detail",
    "root_cause_category",
    "unmet_need",
    "continuation_relevance",
    "evidence_quote",
    "evidence_strength",
    "confidence_score",
    "unsupported_inference",
    "uncertainty_reason",
]
OUTPUT_COLUMNS = PRESERVED_COLUMNS + CLASSIFICATION_FIELDS

RELEVANCE_VALUES = {"direct", "indirect", "not_relevant", UNKNOWN}
JOURNEY_VALUES = {
    "not_started",
    "considering",
    "active",
    "paused",
    "stopped",
    "not_applicable",
    UNKNOWN,
}
EMOTION_VALUES = {"positive", "negative", "mixed", "neutral", UNKNOWN}
CONTINUATION_VALUES = {
    "actual_discontinuation",
    "intention_to_discontinue",
    "temporary_pause",
    "missed_instalment",
    "general_discussion",
    "not_applicable",
    UNKNOWN,
}
# Mutually distinguishable descriptions of what the text supports.
# "unknown" is lowercase because that is the required label.
BEHAVIOUR_VALUES = {
    "actively_continuing",
    "considering_discontinuation",
    "explicitly_discontinued",
    "temporarily_paused",
    "missed_installment",
    "reducing_or_changing_amount",
    "asking_about_cancellation_or_pause",
    "general_advice_or_opinion",
    "unknown",
}
EVIDENCE_STRENGTH_VALUES = {"strong", "moderate", "weak", "none"}
ROOT_CAUSE_CATEGORIES = {
    "financial_constraints",
    "competing_financial_commitments",
    "low_or_disappointing_returns",
    "market_volatility",
    "payment_failure_or_technical_friction",
    "lack_of_sip_flexibility",
    "lack_of_investment_knowledge",
    "app_usability",
    "other",
    "unknown",
}
# Used only to reject a category the stated cause does not support.
# A category is never assigned from these patterns alone.
ROOT_CAUSE_CATEGORY_HINTS = {
    "financial_constraints": r"afford|money|paisa|peisa|salary|income|funds?",
    "competing_financial_commitments": r"expense|loan|emi|rent|fees|family",
    "low_or_disappointing_returns": r"return|returns|loss|losses|underperform",
    "market_volatility": r"market|volatile|volatility|crash|bear|nav",
    "payment_failure_or_technical_friction": r"payment|autopay|upi|mandate|glitch|fail|failed|deduct|technical|process",
    "lack_of_sip_flexibility": r"amount|pause|pausing|change|step[- ]?up|flexib",
    "lack_of_investment_knowledge": r"understand|confus|knowledge|don't know|do not know",
    "app_usability": r"\bapp\b|screen|button|slow|crash|option|interface",
}
ENUM_FIELDS = {
    "relevance_to_sip": RELEVANCE_VALUES,
    "journey_stage": JOURNEY_VALUES,
    "emotion": EMOTION_VALUES,
    "continuation_relevance": CONTINUATION_VALUES,
    "behaviour": BEHAVIOUR_VALUES,
    "evidence_strength": EVIDENCE_STRENGTH_VALUES,
    "root_cause_category": ROOT_CAUSE_CATEGORIES,
}
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RETRYABLE_STATUS_NAMES = {"RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED", "ABORTED"}

LOGGER = logging.getLogger("sip_classifier")

SYSTEM_INSTRUCTION = """
You classify public app reviews and investor comments for a study of
Systematic Investment Plans (SIPs) in India.

Use only statements that are explicit in the text. If a field is not
supported by the text, return Unknown. Never guess.

Do not infer age, income, occupation, family situation, first-time investor
status, or any other personal financial circumstance unless the text states
that fact in words.

A negative app review is not evidence of SIP discontinuation. Crashes, login
problems, fees, customer support, slow pages, or a low opinion of an app are
app feedback unless the writer explicitly connects them to stopping, pausing,
or planning to stop a SIP.

continuation_relevance must be exactly one of:
- actual_discontinuation: the writer states they have already stopped, cancelled, or ended a SIP.
- intention_to_discontinue: the writer plans or wants to stop, but does not say they have already stopped.
- temporary_pause: the writer describes a pause, or a plan to pause and resume. A pause is not discontinuation.
- missed_instalment: an instalment failed, was skipped, or was not deducted, without a stated decision to end the SIP.
- general_discussion: SIP, mutual funds, investing, or the app is discussed, but none of the four situations above is stated.
- not_applicable: the text is not about investing or SIP continuation.
- Unknown: the wording is too unclear to choose.

relevance_to_sip must be exactly one of:
- direct: the text explicitly discusses a SIP or systematic investment plan.
- indirect: investing, mutual funds, or an investment app is discussed, but a SIP is not the subject.
- not_relevant: the text is not about investing.
- Unknown.

journey_stage must be exactly one of: not_started, considering, active, paused, stopped, not_applicable, Unknown.
Use active only when the writer says they currently invest or run a SIP. Use stopped only when behaviour is explicitly_discontinued. Praise such as "good for SIP" is not an active SIP.

behaviour must be exactly one of:
- actively_continuing: the writer says they personally are still running or continuing a SIP.
- considering_discontinuation: the writer says they are thinking about stopping their own SIP, but have not stopped.
- explicitly_discontinued: the writer clearly states that they personally have already stopped or cancelled their SIP. Advice, questions, missed payments, and amount changes do not qualify.
- temporarily_paused: the writer says they personally paused their SIP and have not ended it.
- missed_installment: a payment or instalment was missed, failed, or skipped. This is not discontinuation.
- reducing_or_changing_amount: the writer is changing the SIP amount, including stopping one amount only so they can start another. This is not discontinuation when they say the SIP itself is meant to continue.
- asking_about_cancellation_or_pause: the writer asks how cancellation, withdrawal, or a pause works. A question is not proof they did it.
- general_advice_or_opinion: advice or opinion about SIPs, including "don't stop your SIP", comments about other people, feature wishes, and short praise. This is not the writer's personal SIP action.
- unknown: the text does not clearly support one of the labels above.

Rules for behaviour:
- A missed instalment is not a discontinued SIP.
- Asking how to cancel or pause is not discontinuation.
- A comment about someone else's SIP is not the writer's behaviour.
- Changing the amount is not discontinuation by itself.
- "Don't stop your SIP" and similar advice are general_advice_or_opinion.
- Use explicitly_discontinued only when the writer states that they themselves stopped or cancelled.
- Do not invent a personal history, including how long someone has invested, unless the text states that history in clear language.
- If the comment is mainly Malayalam or another non-English language and the meaning is not clear, use behaviour unknown. Do not translate a guess into a personal history.

emotion must be exactly one of: positive, negative, mixed, neutral, Unknown.

investor_motivation, pain_point, trigger, root_cause, and unmet_need
must be short phrases copied from what the text says, or Unknown.
Use Unknown for root_cause when the text does not state a cause.
root_cause_detail must repeat that same root_cause text. Do not replace it with a category name.
root_cause_category must be exactly one of: financial_constraints, competing_financial_commitments, low_or_disappointing_returns, market_volatility, payment_failure_or_technical_friction, lack_of_sip_flexibility, lack_of_investment_knowledge, app_usability, other, unknown.
Use unknown when the text does not state a cause. Do not choose a category to fill the field.

evidence_quote must be a short exact excerpt copied from original_text, or Unknown.
It must support the behaviour label. Do not paraphrase.
evidence_strength must be exactly one of: strong, moderate, weak, none.
Use none when there is no supporting excerpt. Do not use strong for advice, questions, or ambiguous text.
confidence_score must be a number from 0 to 0.95. Never use 1. It is your estimated confidence, not a measured accuracy.
unsupported_inference must be true when a personal action, history, or cause would be a guess, and false when every label is directly supported.
uncertainty_reason must explain a real ambiguity, unclear language, or an unsupported guess. Use Unknown when the text is clear.

Return one classification for every input record_id. Do not add, drop, or change ids.
""".strip()


def configure_logging() -> None:
    """Log to the console without adding request debugging."""
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # Keep HTTP client logs quiet so request URLs are not written out.
    for logger_name in ("httpx", "httpcore", "google.genai", "google.auth"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def redact_secret(message: str, secret: str) -> str:
    """Remove the API key from a message before it is logged."""
    if secret and secret in message:
        return message.replace(secret, "[redacted]")
    return message


def load_settings() -> tuple[str, str]:
    """Read the Gemini key and model name from the local environment."""
    load_dotenv(ENV_PATH)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to the .env file in the project folder."
        )
    model = os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL
    return api_key, model


def load_master(path: Path | None = None) -> pd.DataFrame:
    """Read the combined dataset and keep the columns this step needs."""
    source = Path(path) if path is not None else MASTER_PATH
    if not source.is_file():
        raise FileNotFoundError(
            f"Could not find the master dataset at {source}. "
            "Run the data loader before classification."
        )
    frame = pd.read_csv(source, dtype=str, keep_default_na=False)
    missing = [column for column in PRESERVED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{source.name} is missing required columns: {', '.join(missing)}."
        )
    return frame[PRESERVED_COLUMNS].copy()


def load_completed_ids(path: Path) -> set[str]:
    """Return record ids that already have a saved classification."""
    if not path.is_file():
        return set()
    saved = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "record_id" not in saved.columns:
        raise ValueError(
            f"{path.name} has no record_id column, so progress cannot be resumed."
        )
    return {record_id.strip() for record_id in saved["record_id"] if record_id.strip()}


def save_progress(path: Path, new_rows: list[dict]) -> None:
    """Add one finished batch to the output file.

    The file is replaced only after the new copy is written, so an interruption
    during the write does not wipe earlier batches.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    incoming = pd.DataFrame(new_rows, columns=OUTPUT_COLUMNS)
    if path.is_file():
        existing = pd.read_csv(path, dtype=str, keep_default_na=False)
        for column in OUTPUT_COLUMNS:
            if column not in existing.columns:
                existing[column] = ""
        combined = pd.concat([existing[OUTPUT_COLUMNS], incoming], ignore_index=True)
        combined = combined.drop_duplicates(subset=["record_id"], keep="first")
    else:
        combined = incoming

    temporary = path.with_suffix(".csv.tmp")
    combined.to_csv(temporary, index=False, encoding="utf-8")
    temporary.replace(path)


def classification_schema() -> dict:
    """JSON schema for one batch. Unknown is allowed on every category."""

    def enum_field(values: set[str], description: str) -> dict:
        return {
            "type": "string",
            "enum": sorted(values),
            "description": description,
        }

    item_properties = {
        "record_id": {"type": "string"},
        "relevance_to_sip": enum_field(
            RELEVANCE_VALUES,
            "direct, indirect, not_relevant, or Unknown.",
        ),
        "investor_motivation": {
            "type": "string",
            "description": "A short phrase stated in the text, or Unknown.",
        },
        "journey_stage": enum_field(
            JOURNEY_VALUES,
            "Stage explicitly supported by the text, or Unknown.",
        ),
        "pain_point": {"type": "string", "description": "Stated problem, or Unknown."},
        "trigger": {"type": "string", "description": "Stated prompt for the comment, or Unknown."},
        "behaviour": enum_field(
            BEHAVIOUR_VALUES,
            "One mutually exclusive behaviour label, or unknown.",
        ),
        "emotion": enum_field(EMOTION_VALUES, "Tone of the words, or Unknown."),
        "root_cause": {
            "type": "string",
            "description": "Cause explicitly stated in the text, or Unknown.",
        },
        "root_cause_detail": {
            "type": "string",
            "description": "The same words as root_cause, not a category name.",
        },
        "root_cause_category": enum_field(
            ROOT_CAUSE_CATEGORIES,
            "Normalised cause category, or unknown when the cause is not stated.",
        ),
        "unmet_need": {"type": "string", "description": "Need the writer asks for, or Unknown."},
        "continuation_relevance": enum_field(
            CONTINUATION_VALUES,
            "How the text relates to continuing a SIP. Must not contradict behaviour.",
        ),
        "evidence_quote": {
            "type": "string",
            "description": "Exact short excerpt from original_text that supports behaviour, or Unknown.",
        },
        "evidence_strength": enum_field(
            EVIDENCE_STRENGTH_VALUES,
            "How directly the excerpt supports the behaviour label.",
        ),
        "confidence_score": {
            "type": "number",
            "description": "Estimated confidence from 0 to 0.95. Do not use 1.",
        },
        "unsupported_inference": {
            "type": "boolean",
            "description": "True when a personal action, history, or cause would be a guess.",
        },
        "uncertainty_reason": {
            "type": "string",
            "description": "Real ambiguity or unclear language, or Unknown.",
        },
    }
    return {
        "type": "object",
        "properties": {
            "classifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": item_properties,
                    "required": ["record_id", *CLASSIFICATION_FIELDS],
                },
            }
        },
        "required": ["classifications"],
    }


def build_batch_prompt(batch: list[dict]) -> str:
    """Send only the text and source context needed to classify the batch."""
    payload = [
        {
            "record_id": row["record_id"],
            "source": row["source"],
            "source_type": row["source_type"],
            "app": row["app"],
            "original_text": row["original_text"],
        }
        for row in batch
    ]
    return (
        "Classify every record below. Return JSON with a classifications array "
        "containing one object per record_id.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _clean_text(value: object) -> str:
    if value is None:
        return UNKNOWN
    text = str(value).strip()
    return text or UNKNOWN


def _clean_score(value: object) -> tuple[str, bool]:
    """Keep an estimated 0-0.95 score. A value of 1 is not treated as certainty."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return UNKNOWN, False
    if score < 0 or score > 1:
        return UNKNOWN, False
    capped = score >= 1
    if capped:
        score = 0.95
    return f"{score:.2f}", capped


def _quote_is_present(quote: str, original_text: str) -> bool:
    if quote == UNKNOWN:
        return True
    collapsed_quote = " ".join(quote.split()).lower()
    collapsed_text = " ".join(original_text.split()).lower()
    return bool(collapsed_quote) and collapsed_quote in collapsed_text


def _flag(value: object) -> str:
    """Store the unsupported-inference flag as true or false."""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower()
    return "true" if text in {"true", "yes", "1"} else "false"


def _note(cleaned: dict, message: str) -> None:
    """Append a validation note without erasing a reason already present."""
    current = cleaned.get("uncertainty_reason", UNKNOWN)
    if current == UNKNOWN or not current:
        cleaned["uncertainty_reason"] = message
        return
    if message not in current:
        cleaned["uncertainty_reason"] = f"{current} {message}"


def _mark_unsupported(cleaned: dict, message: str) -> None:
    cleaned["unsupported_inference"] = "true"
    _note(cleaned, message)


def _is_unclear_language(text: str) -> bool:
    """True when most letters are not Latin, so a translation would be a guess."""
    letters = [character for character in text if character.isalpha()]
    if len(letters) < 12:
        return False
    non_latin = sum(1 for character in letters if ord(character) > 127)
    return non_latin / len(letters) >= 0.25


def _contains(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def apply_validation_rules(cleaned: dict, original_text: str) -> dict:
    """Reject behaviour labels the excerpt does not actually support.

    Keyword presence and model confidence are not treated as proof.
    """
    quote = cleaned["evidence_quote"]
    behaviour = cleaned["behaviour"]
    quote_ok = quote != UNKNOWN and _quote_is_present(quote, original_text)
    combined = f"{quote}\n{original_text}"

    if cleaned["confidence_score"] == "0.95" and _contains(r"\b1(?:\.0+)?\b", str(cleaned.get("_raw_confidence", ""))):
        _note(cleaned, "Confidence is an estimate and was kept below 1.")

    if not quote_ok:
        cleaned["evidence_quote"] = UNKNOWN
        cleaned["evidence_strength"] = "none"
        if behaviour != "unknown":
            cleaned["behaviour"] = "unknown"
            _mark_unsupported(
                cleaned,
                "The behaviour label had no exact supporting excerpt, so it was not kept.",
            )
        behaviour = cleaned["behaviour"]

    if _is_unclear_language(original_text):
        if behaviour != "unknown":
            _mark_unsupported(
                cleaned,
                "The comment is not in English, so a personal behaviour label was not accepted.",
            )
        cleaned["behaviour"] = "unknown"
        cleaned["evidence_strength"] = "none"
        cleaned["root_cause"] = UNKNOWN
        cleaned["investor_motivation"] = UNKNOWN
        cleaned["journey_stage"] = UNKNOWN
        _note(
            cleaned,
            "The comment is mainly in a non-English language, so its personal meaning was left unknown.",
        )
        behaviour = "unknown"

    advice = _contains(
        r"don'?t stop|do not stop|should not stop|keep patience|those who stop|people",
        quote if quote_ok else "",
    )
    someone_else = _contains(
        r"\b(someone|those who|people|many sips|fund houses)\b",
        quote if quote_ok else "",
    )
    self_stopped = _contains(
        r"\b(i|i've|i have|i had)\b.{0,50}\b(stopped|cancelled|canceled|discontinued)\b"
        r"|\b(stopped|cancelled|canceled|discontinued)\s+my\s+sips?\b",
        quote if quote_ok else "",
    )
    denies_stopping = _contains(
        r"not to stop|never stopped|have not stopped|did not stop|didn't stop|intention is not to stop",
        combined,
    )
    missed = _contains(r"\bmiss(?:ed|ing)?\b|\bpayment\b", quote if quote_ok else "")
    amount_change = _contains(
        r"\b(reduc\w*|amount|change the sip|changing)\b|\b\d{3,}\b",
        quote if quote_ok else "",
    )
    own_pause = _contains(
        r"\b(i|my)\b.{0,40}\bpaus(?:e|ed|ing)\b|\bpaused my sips?\b",
        quote if quote_ok else "",
    )
    general_pause = _contains(
        r"\b(someone|can pause|hope pausing|pausing sips)\b",
        quote if quote_ok else "",
    )
    question = "?" in original_text or _contains(
        r"\b(how|what|can i|should i|will it|is it)\b",
        quote if quote_ok else "",
    )
    own_continuing = _contains(
        r"\b(i|my)\b.{0,40}\b(continu\w*|doing|have been doing|still)\b.{0,20}\bsips?\b",
        quote if quote_ok else "",
    )
    considering = _contains(
        r"\b(thinking|considering|planning|want to stop|might stop)\b",
        quote if quote_ok else "",
    )

    if behaviour == "explicitly_discontinued" and (
        not self_stopped or denies_stopping or advice or someone_else or missed
    ):
        replacement = "unknown"
        if missed and not self_stopped:
            replacement = "missed_installment"
        elif amount_change and denies_stopping:
            replacement = "reducing_or_changing_amount"
        elif question and not self_stopped:
            replacement = "asking_about_cancellation_or_pause"
        elif advice or someone_else:
            replacement = "general_advice_or_opinion"
        cleaned["behaviour"] = replacement
        _mark_unsupported(
            cleaned,
            "explicitly_discontinued was removed because the text does not say the writer stopped their own SIP.",
        )
        behaviour = replacement

    if behaviour == "missed_installment" and not missed:
        cleaned["behaviour"] = "unknown"
        _mark_unsupported(cleaned, "missed_installment was removed because the excerpt does not describe a missed payment.")
        behaviour = "unknown"

    if behaviour == "temporarily_paused" and (not own_pause or general_pause):
        cleaned["behaviour"] = "general_advice_or_opinion" if general_pause or advice else "unknown"
        _mark_unsupported(
            cleaned,
            "temporarily_paused was removed because the text does not say the writer paused their own SIP.",
        )
        behaviour = cleaned["behaviour"]

    if behaviour == "actively_continuing" and not own_continuing:
        cleaned["behaviour"] = "general_advice_or_opinion" if advice or _contains(r"\b(good|best|nice)\b", quote) else "unknown"
        _mark_unsupported(cleaned, "actively_continuing was removed because the writer does not say they are continuing a SIP.")
        behaviour = cleaned["behaviour"]

    if behaviour == "considering_discontinuation" and (not considering or advice):
        cleaned["behaviour"] = "general_advice_or_opinion" if advice else "unknown"
        _mark_unsupported(cleaned, "considering_discontinuation was removed because the writer does not say they are thinking of stopping.")
        behaviour = cleaned["behaviour"]

    if behaviour == "reducing_or_changing_amount" and not amount_change:
        cleaned["behaviour"] = "unknown"
        _mark_unsupported(cleaned, "reducing_or_changing_amount was removed because the excerpt does not describe an amount change.")
        behaviour = "unknown"

    if behaviour == "asking_about_cancellation_or_pause" and not (
        question and _contains(r"\b(cancel\w*|paus\w*|withdraw\w*)\b", quote if quote_ok else "")
    ):
        cleaned["behaviour"] = (
            "general_advice_or_opinion"
            if _contains(r"\b(good|best|nice|how to|choose)\b", quote if quote_ok else "")
            else "unknown"
        )
        _mark_unsupported(
            cleaned,
            "A cancellation or pause question was not accepted because the excerpt does not ask about cancelling or pausing.",
        )
        behaviour = cleaned["behaviour"]

    if behaviour == "actively_continuing" and amount_change and denies_stopping:
        cleaned["behaviour"] = "reducing_or_changing_amount"
        behaviour = "reducing_or_changing_amount"
        _mark_unsupported(
            cleaned,
            "actively_continuing was not kept because the text is about changing the SIP amount, and the writer says they do not intend to stop.",
        )

    supported = {
        "explicitly_discontinued": self_stopped and not denies_stopping and not advice,
        "missed_installment": missed,
        "temporarily_paused": own_pause and not general_pause,
        "actively_continuing": own_continuing and not amount_change,
        "considering_discontinuation": considering and not advice,
        "reducing_or_changing_amount": amount_change,
        "asking_about_cancellation_or_pause": question and _contains(
            r"\b(cancel\w*|paus\w*|withdraw\w*)\b", quote if quote_ok else ""
        ),
        "general_advice_or_opinion": quote_ok,
    }
    if behaviour == "unknown" or not quote_ok:
        cleaned["evidence_strength"] = "none"
        cleaned["root_cause"] = UNKNOWN
    elif supported.get(behaviour):
        cleaned["evidence_strength"] = "strong" if behaviour != "general_advice_or_opinion" else "moderate"
    else:
        cleaned["evidence_strength"] = "weak"
        cleaned["root_cause"] = UNKNOWN

    if cleaned["evidence_strength"] in {"none", "weak"}:
        cleaned["root_cause"] = UNKNOWN
    elif not _quote_is_present(cleaned["root_cause"], original_text):
        cleaned["root_cause"] = UNKNOWN
        _mark_unsupported(cleaned, "The root cause was not an exact statement from the text, so it was left Unknown.")

    if cleaned["continuation_relevance"] == "actual_discontinuation" and behaviour != "explicitly_discontinued":
        cleaned["continuation_relevance"] = "missed_instalment" if behaviour == "missed_installment" else "general_discussion"
        _mark_unsupported(cleaned, "A discontinuation conclusion was removed because the behaviour label does not support it.")

    if cleaned["journey_stage"] == "stopped" and behaviour != "explicitly_discontinued":
        cleaned["journey_stage"] = UNKNOWN
        _mark_unsupported(cleaned, "A stopped journey stage was removed because discontinuation is not established.")
    if cleaned["journey_stage"] == "active" and behaviour != "actively_continuing":
        cleaned["journey_stage"] = UNKNOWN
        _mark_unsupported(cleaned, "An active journey stage was removed because the writer does not say they are continuing.")
    if cleaned["journey_stage"] == "paused" and behaviour != "temporarily_paused":
        cleaned["journey_stage"] = UNKNOWN
    cleaned["root_cause_detail"] = cleaned.get("root_cause", UNKNOWN)
    return assign_root_cause_category(cleaned)


def assign_root_cause_category(cleaned: dict) -> dict:
    """Keep a cause category only when the stated cause supports it.

    This does not change behaviour labels or evidence quotes.
    """
    detail = cleaned.get("root_cause", UNKNOWN) or UNKNOWN
    cleaned["root_cause_detail"] = detail
    proposed = _clean_text(cleaned.get("root_cause_category", "unknown")).lower()
    if proposed == "unknown":
        cleaned["root_cause_category"] = "unknown"
        return cleaned
    insufficient = detail == UNKNOWN or cleaned.get("evidence_strength") in {"none", "weak"}
    if insufficient or proposed not in ROOT_CAUSE_CATEGORIES:
        cleaned["root_cause_category"] = "unknown"
        return cleaned
    if proposed == "other":
        cleaned["root_cause_category"] = "other"
        return cleaned
    hint = ROOT_CAUSE_CATEGORY_HINTS.get(proposed)
    evidence_text = f"{detail}\n{cleaned.get('evidence_quote', '')}"
    if hint and not _contains(hint, evidence_text):
        cleaned["root_cause_category"] = "unknown"
        _mark_unsupported(
            cleaned,
            "The root-cause category was not kept because the stated cause did not support it.",
        )
        return cleaned
    cleaned["root_cause_category"] = proposed
    return cleaned


def normalise_classification(raw: dict, original_text: str) -> dict:
    """Force missing or unsupported labels to Unknown. Do not fill gaps."""
    cleaned: dict[str, str] = {}
    for field, allowed in ENUM_FIELDS.items():
        value = _clean_text(raw.get(field))
        if field in {"behaviour", "root_cause_category"} and value.lower() == "unknown":
            value = "unknown"
        if field == "evidence_strength" and value == UNKNOWN:
            value = "none"
        if field == "behaviour" and value not in allowed:
            cleaned[field] = "unknown"
        elif field == "root_cause_category" and value not in allowed:
            cleaned[field] = "unknown"
        elif field == "evidence_strength" and value not in allowed:
            cleaned[field] = "none"
        else:
            cleaned[field] = value if value in allowed else UNKNOWN

    for field in (
        "investor_motivation",
        "pain_point",
        "trigger",
        "root_cause",
        "unmet_need",
        "uncertainty_reason",
    ):
        cleaned[field] = _clean_text(raw.get(field))

    quote = _clean_text(raw.get("evidence_quote"))
    if not _quote_is_present(quote, original_text):
        quote = UNKNOWN
        if cleaned["uncertainty_reason"] == UNKNOWN:
            cleaned["uncertainty_reason"] = (
                "The returned evidence quote was not present in the original text."
            )
    cleaned["evidence_quote"] = quote
    score, capped = _clean_score(raw.get("confidence_score"))
    cleaned["confidence_score"] = score
    cleaned["_raw_confidence"] = str(raw.get("confidence_score", ""))
    if capped and cleaned["uncertainty_reason"] == UNKNOWN:
        cleaned["uncertainty_reason"] = "Confidence is an estimate and was kept below 1."
    cleaned["unsupported_inference"] = _flag(raw.get("unsupported_inference"))
    cleaned = apply_validation_rules(cleaned, original_text)
    cleaned.pop("_raw_confidence", None)
    return cleaned


def parse_batch_response(response_text: str) -> list[dict]:
    """Read the JSON array of classifications from a model response."""
    if not response_text or not response_text.strip():
        raise ValueError("Gemini returned an empty response.")
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini did not return valid JSON.") from exc

    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = payload.get("classifications")
    else:
        records = None
    if not isinstance(records, list):
        raise ValueError("Gemini JSON did not contain a classifications list.")
    parsed = [item for item in records if isinstance(item, dict) and item.get("record_id")]
    if not parsed:
        raise ValueError("Gemini JSON did not include any record_id values.")
    return parsed


def is_retryable(exc: Exception) -> bool:
    """Rate limits, temporary outages, and a bad JSON reply can be retried."""
    if isinstance(exc, errors.APIError):
        status = (exc.status or "").upper()
        return exc.code in RETRYABLE_STATUS_CODES or status in RETRYABLE_STATUS_NAMES
    if isinstance(exc, (ValueError, json.JSONDecodeError, TimeoutError, ConnectionError)):
        return True
    return exc.__class__.__name__ in {
        "ConnectError",
        "ReadTimeout",
        "RemoteProtocolError",
        "ConnectTimeout",
    }


def request_batch(client: genai.Client, model: str, batch: list[dict], api_key: str) -> list[dict]:
    """Call Gemini for one batch, waiting between retries."""
    prompt = build_batch_prompt(batch)
    config = types.GenerateContentConfig(
        temperature=0,
        max_output_tokens=8192,
        response_mime_type="application/json",
        response_json_schema=classification_schema(),
        system_instruction=SYSTEM_INSTRUCTION,
        thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
    )
    last_error = "the request failed"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            return parse_batch_response(getattr(response, "text", "") or "")
        except Exception as exc:
            last_error = redact_secret(str(getattr(exc, "message", "") or exc), api_key)
            status = getattr(exc, "code", None)
            if not is_retryable(exc) or attempt == MAX_ATTEMPTS:
                LOGGER.error(
                    "Batch failed after %s attempt(s). status=%s detail=%s",
                    attempt,
                    status if status is not None else type(exc).__name__,
                    last_error,
                )
                raise
            delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            LOGGER.warning(
                "Temporary API problem (status %s). Retry %s/%s in %.0f seconds.",
                status if status is not None else type(exc).__name__,
                attempt,
                MAX_ATTEMPTS,
                delay,
            )
            time.sleep(delay)
    raise RuntimeError(last_error)


def rows_from_response(batch: list[dict], classifications: list[dict]) -> tuple[list[dict], list[str]]:
    """Join model labels back to the original rows. Unmatched ids are failures."""
    by_id: dict[str, dict] = {}
    for item in classifications:
        record_id = str(item.get("record_id", "")).strip()
        if record_id and record_id not in by_id:
            by_id[record_id] = item

    ready: list[dict] = []
    failed: list[str] = []
    expected = {row["record_id"] for row in batch}
    for record_id in by_id:
        if record_id not in expected:
            LOGGER.warning("Ignored unexpected record_id returned by the model: %s", record_id)

    for row in batch:
        raw = by_id.get(row["record_id"])
        if raw is None:
            failed.append(row["record_id"])
            LOGGER.error("Failed record_id=%s reason=missing from model response", row["record_id"])
            continue
        labels = normalise_classification(raw, row["original_text"])
        saved = {column: row[column] for column in PRESERVED_COLUMNS}
        saved.update(labels)
        ready.append(saved)
        LOGGER.info("Processed record_id=%s", row["record_id"])
    return ready, failed


def classify_records(records: list[dict], output_path: Path) -> list[dict]:
    """Classify only the records given and write those rows to ``output_path``.

    The rest of the master dataset is not read or sent. The output file is
    replaced with this sample, so a repeat run does not move on to later records.
    """
    configure_logging()
    if not records:
        raise ValueError("No records were provided to classify.")

    prepared: list[dict] = []
    for row in records:
        missing = [column for column in PRESERVED_COLUMNS if column not in row]
        if missing:
            raise ValueError(
                "A selected record is missing required fields: " + ", ".join(missing)
            )
        prepared.append({column: str(row[column]).strip() if column == "record_id" else str(row[column]) for column in PRESERVED_COLUMNS})

    api_key, model = load_settings()
    LOGGER.info("Model: %s", model)
    LOGGER.info("Classifying the %s selected records only.", len(prepared))
    client = genai.Client(api_key=api_key)
    try:
        classifications = request_batch(client, model, prepared, api_key)
    except Exception as exc:
        detail = redact_secret(str(getattr(exc, "message", "") or exc), api_key)
        raise RuntimeError(f"The Gemini request failed. {detail}") from None

    ready, failed = rows_from_response(prepared, classifications)
    destination = Path(output_path)
    if ready:
        destination.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(ready, columns=OUTPUT_COLUMNS).to_csv(
            destination, index=False, encoding="utf-8"
        )
        LOGGER.info("Saved %s classified records to %s", len(ready), destination)
    if failed:
        LOGGER.error(
            "Failed to classify %s selected record(s): %s",
            len(failed),
            ", ".join(failed),
        )
    if not ready:
        raise RuntimeError(
            "Gemini did not return a usable classification for the selected records."
        )
    return ready


def classify_dataset(
    max_records: int | None = None,
    batch_size: int = BATCH_SIZE,
    master_path: Path | None = None,
    output_path: Path | None = None,
    record_ids: set[str] | None = None,
) -> dict:
    """Classify pending records and save after every batch.

    ``max_records`` limits how many not-yet-classified records are sent.
    Records already stored in the output file are skipped.
    """
    configure_logging()
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    if max_records is not None and max_records < 1:
        raise ValueError("max_records must be at least 1.")

    api_key, model = load_settings()
    source = Path(master_path) if master_path is not None else MASTER_PATH
    destination = Path(output_path) if output_path is not None else OUTPUT_PATH
    master = load_master(source)
    completed = load_completed_ids(destination)

    skipped_existing = 0
    skipped_blank = 0
    candidates: list[dict] = []
    for row in master.to_dict(orient="records"):
        record_id = str(row["record_id"]).strip()
        row["record_id"] = record_id
        if record_id in completed:
            skipped_existing += 1
            continue
        if not str(row["original_text"]).strip():
            skipped_blank += 1
            LOGGER.info("Skipped record_id=%s reason=blank original_text", record_id)
            continue
        candidates.append(row)

    if record_ids is not None:
        wanted = {str(record_id) for record_id in record_ids}
        candidates = [row for row in candidates if row["record_id"] in wanted]

    selected = candidates if max_records is None else candidates[:max_records]
    LOGGER.info("Model: %s", model)
    LOGGER.info("Master records: %s", len(master))
    LOGGER.info("Skipped already classified: %s", skipped_existing)
    LOGGER.info("Skipped blank text: %s", skipped_blank)
    LOGGER.info("Selected for this run: %s", len(selected))
    LOGGER.info("Left for a later run: %s", len(candidates) - len(selected))

    client = genai.Client(api_key=api_key)
    processed = 0
    failed_ids: list[str] = []
    batch_count = 0

    for start in range(0, len(selected), batch_size):
        batch = selected[start : start + batch_size]
        batch_count += 1
        ids = ", ".join(row["record_id"] for row in batch)
        LOGGER.info("Starting batch %s with %s records: %s", batch_count, len(batch), ids)
        try:
            classifications = request_batch(client, model, batch, api_key)
            ready, failed = rows_from_response(batch, classifications)
        except Exception as exc:
            detail = redact_secret(str(getattr(exc, "message", "") or exc), api_key)
            failed = [row["record_id"] for row in batch]
            ready = []
            for record_id in failed:
                LOGGER.error("Failed record_id=%s reason=%s", record_id, detail)

        failed_ids.extend(failed)
        if ready:
            save_progress(destination, ready)
            processed += len(ready)
            LOGGER.info(
                "Saved batch %s. Processed so far: %s. Failed so far: %s.",
                batch_count,
                processed,
                len(failed_ids),
            )
        else:
            LOGGER.error("Batch %s saved nothing.", batch_count)

        if start + batch_size < len(selected):
            time.sleep(BATCH_PAUSE_SECONDS)

    summary = {
        "processed": processed,
        "failed": len(failed_ids),
        "failed_record_ids": failed_ids,
        "skipped_already_classified": skipped_existing,
        "skipped_blank_text": skipped_blank,
        "selected": len(selected),
        "output_path": str(destination),
    }
    LOGGER.info(
        "Run complete. Processed: %s. Failed: %s. "
        "Skipped already classified: %s. Skipped blank text: %s.",
        summary["processed"],
        summary["failed"],
        summary["skipped_already_classified"],
        summary["skipped_blank_text"],
    )
    return summary


def main() -> None:
    """Classify a limited number of records.

    A maximum is required so a plain run does not classify the full dataset.
    """
    parser = argparse.ArgumentParser(
        description="Classify SIP feedback records with Gemini."
    )
    parser.add_argument(
        "--max-records",
        type=int,
        required=True,
        help="Maximum number of not-yet-classified records to send in this run.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help="Records per Gemini request. The default is 10.",
    )
    args = parser.parse_args()
    try:
        classify_dataset(max_records=args.max_records, batch_size=args.batch_size)
    except RuntimeError as exc:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        LOGGER.error("%s", redact_secret(str(exc), os.getenv("GEMINI_API_KEY", "")))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
