"""Reclassify the same 10-record validation sample with the revised behaviour labels.

The record ids come from ``classified_records_validation.csv``. A phrase match
is still not treated as proof of discontinuation. The full dataset is not sent.

Run from the project folder:

    python src/validate_classifier.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classifier import (  # noqa: E402
    MASTER_PATH,
    classify_records,
    load_master,
    redact_secret,
)

PREVIOUS_VALIDATION = PROJECT_ROOT / "data" / "processed" / "classified_records_validation.csv"
VALIDATION_OUTPUT = PROJECT_ROOT / "data" / "processed" / "classified_records_validation_v2.csv"
MAX_SIGNAL_RECORDS = 10
MAX_PER_SIGNAL = 2
NEGATIVE_EXAMPLES = 3

# Loose text search only. These patterns do not assign a classification.
SIGNAL_PATTERNS = {
    "stopped SIP": r"\bstop(?:ped|ping)?\b.{0,24}\bsips?\b",
    "discontinued SIP": r"\bdiscontinu\w*\b.{0,24}\bsips?\b",
    "paused SIP": r"\bpaus(?:e|ed|ing)\b.{0,24}\bsips?\b",
    "cancelling SIP": r"\bcancel\w*\b.{0,24}\bsips?\b|\bsips?\b.{0,24}\bcancel\w*\b",
    "missed SIP instalments": (
        r"\bmiss(?:ed|ing)?\b.{0,40}\b(?:sips?|instal\w*|payments?)\b"
        r"|\bsips?\b.{0,40}\bmiss(?:ed|ing)?\b"
    ),
    "thinking of stopping SIP": (
        r"\b(?:thinking of|want to|planning to|plan to|considering)\b"
        r".{0,24}\bstop(?:ping)?\b.{0,16}\bsips?\b"
    ),
    "unable to continue SIP": (
        r"\b(?:unable to|cannot|can't|could not|couldn't)\b"
        r".{0,24}\bcontinue\b.{0,16}\bsips?\b"
    ),
    "financial difficulty affecting SIP": (
        r"\b(?:financial difficult\w*|can't afford|cannot afford|lost (?:my )?job)\b"
        r".{0,40}\bsips?\b|\bsips?\b.{0,40}\b(?:financial difficult\w*|can't afford|cannot afford)\b"
    ),
}


# Prefer a direct phrase such as "stop my SIP" over a looser nearby match.
DIRECT_PATTERNS = {
    "stopped SIP": r"\bstop(?:ped|ping)?\s+(?:my\s+|the\s+|our\s+|your\s+)?sips?\b",
    "paused SIP": r"\bpaus(?:e|ed|ing)\s+(?:my\s+|the\s+|a\s+)?sips?\b",
    "cancelling SIP": r"\bcancel\w*\s+(?:my\s+|the\s+|a\s+)?sips?\b|\bsips?\s+cancel\w*\b",
    "missed SIP instalments": r"\bmiss(?:ed|ing)\s+(?:my\s+|the\s+)?(?:sips?|payments?|instal\w*)\b",
}


def matching_rows(frame: pd.DataFrame, name: str, pattern: str) -> list[dict]:
    """Return master rows whose text matches one search pattern.

    Direct wording is listed before looser matches. The order is only used
    to choose a varied sample. It does not decide the model label.
    """
    mask = frame["original_text"].str.contains(pattern, case=False, regex=True, na=False)
    rows = frame.loc[mask].to_dict(orient="records")
    direct = DIRECT_PATTERNS.get(name)

    def sort_key(row: dict) -> tuple[int, str]:
        text = str(row["original_text"])
        is_direct = 0 if direct and re.search(direct, text, flags=re.I) else 1
        return (is_direct, str(row["record_id"]))

    return sorted(rows, key=sort_key)


def select_signal_records(frame: pd.DataFrame) -> tuple[list[tuple[str, dict]], dict[str, int]]:
    """Pick a diverse handful of phrase matches, at most two from each group."""
    counts: dict[str, int] = {}
    grouped: dict[str, list[dict]] = {}
    for name, pattern in SIGNAL_PATTERNS.items():
        rows = matching_rows(frame, name, pattern)
        counts[name] = len(rows)
        grouped[name] = rows

    selected: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for name, rows in grouped.items():
        taken = 0
        seen_shapes: set[str] = set()
        unused = list(rows)
        # First take different kinds of wording, then fill from what remains.
        for prefer_new_shape in (True, False):
            for row in unused:
                record_id = str(row["record_id"])
                if record_id in seen:
                    continue
                shape = comment_shape(str(row["original_text"]))
                if prefer_new_shape and shape in seen_shapes:
                    continue
                selected.append((name, row))
                seen.add(record_id)
                seen_shapes.add(shape)
                taken += 1
                if taken >= MAX_PER_SIGNAL or len(selected) >= MAX_SIGNAL_RECORDS:
                    break
            if taken >= MAX_PER_SIGNAL or len(selected) >= MAX_SIGNAL_RECORDS:
                break
        if len(selected) >= MAX_SIGNAL_RECORDS:
            break
    return selected, counts


def comment_shape(text: str) -> str:
    """Group similar wording so the sample is not ten versions of one sentence."""
    lowered = text.lower()
    if re.search(r"i made this mistake|i stopped|biggest regret|have been stopping", lowered):
        return "personal_past"
    if re.search(r"never stopped|have not stopped|didn't stop|did not stop", lowered):
        return "says_they_continued"
    if re.search(r"don't stop|do not stop|why should i stop|should i stop", lowered):
        return "advice_or_question"
    if re.search(r"miss(?:ed|ing)", lowered):
        return "missed_wording"
    if re.search(r"paus", lowered):
        return "pause_wording"
    return "other"


def select_negative_examples(frame: pd.DataFrame, used_ids: set[str]) -> list[dict]:
    """Ordinary SIP comments that did not match a stop, pause, or miss phrase."""
    signal = re.compile("|".join(f"(?:{pattern})" for pattern in SIGNAL_PATTERNS.values()), re.I)
    sip_word = re.compile(r"\bsips?\b", re.I)
    thin_comment = re.compile(
        r"^(?:next\s+)?sips?(?:\s+(?:part|right now|video)(?:\s+\w+){0,2})?(?:\s*[\W\d]*)?$",
        re.I,
    )
    candidates = []
    for row in frame.to_dict(orient="records"):
        if str(row["record_id"]) in used_ids:
            continue
        text = " ".join(str(row["original_text"]).split())
        words = re.findall(r"[A-Za-z']+", text)
        if len(words) < 3 or thin_comment.match(text):
            continue
        if sip_word.search(text) and not signal.search(text):
            candidates.append(row)
    candidates.sort(key=lambda row: (len(str(row["original_text"])), str(row["record_id"])))

    chosen: list[dict] = []
    seen_sources: set[str] = set()
    for row in candidates:
        if row["source_type"] in seen_sources and len(chosen) < NEGATIVE_EXAMPLES - 1:
            continue
        chosen.append(row)
        seen_sources.add(row["source_type"])
        if len(chosen) >= NEGATIVE_EXAMPLES:
            break
    if len(chosen) < NEGATIVE_EXAMPLES:
        for row in candidates:
            if row["record_id"] not in {item["record_id"] for item in chosen}:
                chosen.append(row)
            if len(chosen) >= NEGATIVE_EXAMPLES:
                break
    return chosen


def print_search_report(counts: dict[str, int], signal_rows: list[tuple[str, dict]]) -> None:
    """Show what the search found before any model label is trusted."""
    print("Phrase search in master_dataset.csv")
    print("A match only means the words appear. It does not prove discontinuation.")
    print("-" * 72)
    for name, count in counts.items():
        print(f"  {name}: {count}")
    empty = [name for name, count in counts.items() if count == 0]
    if empty:
        print("No records found for: " + "; ".join(empty) + ".")
    print(
        f"Selected {len(signal_rows)} signal records "
        f"(maximum {MAX_SIGNAL_RECORDS}, at most {MAX_PER_SIGNAL} per phrase)."
    )


def print_result(row: dict) -> None:
    """Show the comment and the labels that need human review."""
    print("-" * 72)
    print(f"Original comment: {row['original_text']}")
    print(f"Predicted behaviour: {row['behaviour']}")
    print(f"SIP relevance: {row['relevance_to_sip']}")
    print(f"Root cause detail: {row['root_cause_detail']}")
    print(f"Root cause category: {row['root_cause_category']}")
    print(f"Confidence: {row['confidence_score']}")
    print(f"Evidence quote: {row['evidence_quote']}")
    print(f"Evidence strength: {row['evidence_strength']}")
    print(f"Unsupported inference: {row['unsupported_inference']}")
    print(f"Uncertainty: {row['uncertainty_reason']}")


def load_same_validation_records(master: pd.DataFrame) -> list[dict]:
    """Reload the 10 records used in the first validation, in the same order."""
    if not PREVIOUS_VALIDATION.is_file():
        raise FileNotFoundError(
            f"Could not find the first validation file at {PREVIOUS_VALIDATION}."
        )
    previous = pd.read_csv(PREVIOUS_VALIDATION, dtype=str, keep_default_na=False)
    if "record_id" not in previous.columns:
        raise ValueError(f"{PREVIOUS_VALIDATION.name} has no record_id column.")
    by_id = {str(row["record_id"]): row for row in master.to_dict(orient="records")}
    sample = []
    missing = []
    for record_id in previous["record_id"].tolist():
        row = by_id.get(str(record_id))
        if row is None:
            missing.append(str(record_id))
        else:
            sample.append(row)
    if missing:
        raise ValueError("These validation record ids are not in the master dataset: " + ", ".join(missing))
    return sample


def main() -> None:
    """Classify the original 10 validation records again and save a new file."""
    try:
        master = load_master(MASTER_PATH)
        sample = load_same_validation_records(master)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    print(
        f"Reclassifying the same {len(sample)} validation records. "
        f"The other {len(master) - len(sample)} records will not be processed.",
        flush=True,
    )

    try:
        classified = classify_records(sample, VALIDATION_OUTPUT)
    except Exception as exc:
        secret = ""
        try:
            import os

            from dotenv import load_dotenv

            load_dotenv(PROJECT_ROOT / ".env")
            secret = os.getenv("GEMINI_API_KEY", "")
        except Exception:
            secret = ""
        print(f"Error: {redact_secret(str(exc), secret)}", file=sys.stderr)
        raise SystemExit(1) from None

    print("Validation results")
    for row in classified:
        print_result(row)
    print("-" * 72)
    print(f"Saved {len(classified)} records to {VALIDATION_OUTPUT}")
    if len(classified) != len(sample):
        print(
            f"Error: sent {len(sample)} records and received {len(classified)} classifications.",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
