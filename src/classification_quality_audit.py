"""Audit unsupported inferences in the 100-record pilot.

This module only reads ``data/processed/classified_records_pilot.csv``.
It does not call Gemini and does not change any classification file.

Run from the project folder:

    python -m src.classification_quality_audit
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PILOT_PATH = PROJECT_ROOT / "data" / "processed" / "classified_records_pilot.csv"
AUDIT_PATH = PROJECT_ROOT / "data" / "processed" / "unsupported_inference_audit.csv"
REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "classification_quality_audit.md"

TYPE_HISTORY = "Invented personal investor history"
TYPE_GENERAL = "Confusing general discussion with personal behaviour"
TYPE_MISSED_AS_STOP = "Treating missed instalments as discontinuation"
TYPE_FINANCE = "Inferring financial circumstances without evidence"
TYPE_CAUSE = "Assigning root causes without supporting text"
TYPE_OTHER = "Other"
INFERENCE_TYPES = (
    TYPE_HISTORY,
    TYPE_GENERAL,
    TYPE_MISSED_AS_STOP,
    TYPE_FINANCE,
    TYPE_CAUSE,
    TYPE_OTHER,
)

AUDIT_COLUMNS = [
    "record_id",
    "source",
    "app",
    "original_text",
    "behaviour",
    "root_cause_category",
    "root_cause_detail",
    "evidence_quote",
    "evidence_strength",
    "confidence_score",
    "uncertainty_reason",
    "inference_type",
    "review_status",
    "audit_note",
]

# These comments may support a personal reading that the validator rejected.
# They are not confirmed errors, and this audit does not restore any label.
HUMAN_REVIEW_CASES = {
    "local-0a3006c170d71f2c": (
        "The stored reason says explicitly_discontinued was removed. The comment is a short Hindi sentence that contains the English word SIP. A reader who knows the language should decide whether the writer says they stopped three SIPs. This audit does not treat the removal as a confirmed error and does not restore the label."
    ),
    "local-080daab4b7fa4331": (
        "The comment says “I started my SIP journey almost 3 years ago” and “No going back now.” The file says actively_continuing was removed. A person should decide whether those sentences state personal continuation. This audit does not confirm or reject that reading."
    ),
    "local-0650b3b60dfebec1": (
        "The comment is Hindi in Latin script and mentions 2008 and a monthly amount. The file says actively_continuing was removed. A person should read it. This audit does not translate it into a behaviour."
    ),
    "local-02ef26799bf8cca3": (
        "The comment names two funds, says an SIP was done there, and asks whether it should be continued. The file says actively_continuing was removed. A person should decide whether that is a personal continuation statement."
    ),
    "local-06348d5abe992b11": (
        "The comment describes starting an SIP when the market falls and selling when it rises. The file says actively_continuing was removed. A person should decide what behaviour, if any, that describes."
    ),
    "local-1e45e5069d02d69f": (
        "The stored reason includes an English gloss of a Tamil or Manglish sentence and says actively_continuing was removed. This audit does not treat that gloss as confirmed evidence."
    ),
    "local-11925dbc5b6f48be": (
        "The comment says an SIP was started and that a loss occurred. The file says an active journey stage was removed and a root-cause category was not kept. The saved detail “loss ho gya” appears in the comment. The rejected category name is not stored. A person should decide whether the sentence states a personal active SIP."
    ),
    "local-19b4b15e04c4d306": (
        "The comment states an XIRR of 11% and asks whether to continue with mutual funds. The file says an active journey stage was removed. The return figure is in the comment. A person should decide whether the question states a personal active SIP."
    ),
    "local-1db6c358a0ccd51e": (
        "The comment says “I've been investing since 4 years” and gives invested and current amounts. The file says actively_continuing was removed. Those amounts are in the comment. A person should decide whether the sentence states continuation of a SIP rather than investing in general."
    ),
}


def load_pilot(path: Path | None = None) -> pd.DataFrame:
    """Read the pilot classifications without changing the file."""
    source = Path(path) if path is not None else PILOT_PATH
    if not source.is_file():
        raise FileNotFoundError(f"Could not find the pilot classifications at {source}.")
    frame = pd.read_csv(source, dtype=str, keep_default_na=False)
    required = [
        "record_id",
        "source",
        "app",
        "original_text",
        "behaviour",
        "root_cause_category",
        "root_cause_detail",
        "evidence_quote",
        "evidence_strength",
        "confidence_score",
        "uncertainty_reason",
        "unsupported_inference",
        "continuation_relevance",
    ]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Pilot file is missing columns: {', '.join(missing)}")
    return frame


def _named_types(reason: str) -> list[str]:
    """Types named by the stored validation text. Order is the display priority."""
    found: list[str] = []
    discontinuation = (
        "explicitly_discontinued was removed" in reason
        or "A discontinuation conclusion was removed" in reason
        or "considering_discontinuation was removed" in reason
    )
    history = (
        "actively_continuing was removed" in reason
        or "An active journey stage was removed" in reason
        or "A stopped journey stage was removed" in reason
    )
    if discontinuation:
        found.append(TYPE_GENERAL)
    if "missed_installment was removed" in reason:
        found.append(TYPE_OTHER)
    if history and not discontinuation:
        found.append(TYPE_HISTORY)
    if "The root-cause category was not kept" in reason:
        found.append(TYPE_CAUSE)
    quote_missing = (
        "no exact supporting excerpt" in reason or "evidence quote was not present" in reason
    )
    if quote_missing and not found:
        found.append(TYPE_OTHER)
    return found


def _model_only_type(reason: str) -> str | None:
    """A suggested type when the model wrote the reason and named no removed label."""
    lowered = reason.lower()
    if any(
        phrase in lowered
        for phrase in (
            "without explicit personal",
            "without stating personal",
            "without mentioning personal",
            "feature request",
            "feature question",
            "general educational",
            "general opinion",
            "general strategic",
            "app limitations",
        )
    ):
        return TYPE_GENERAL
    if reason.strip():
        return TYPE_OTHER
    return None


def audit_row(row: pd.Series) -> pd.Series:
    """Classify one flagged row. This does not change the stored labels."""
    reason = row["uncertainty_reason"]
    record_id = row["record_id"]
    behaviour = row["behaviour"]
    continuation = row["continuation_relevance"]
    notes: list[str] = []
    types: list[str] = []
    status = "confirmed_error"

    if record_id in HUMAN_REVIEW_CASES:
        status = "human_review"
        types = [TYPE_OTHER]
        if "The root-cause category was not kept" in reason:
            types.append(TYPE_CAUSE)
        notes.append(HUMAN_REVIEW_CASES[record_id])
    elif "not in English" in reason or "non-English" in reason:
        status = "human_review"
        types = [TYPE_OTHER]
        notes.append(
            "The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour."
        )
    else:
        if continuation == "intention_to_discontinue" and behaviour != "considering_discontinuation":
            types.append(TYPE_GENERAL)
            notes.append(
                "The continuation label is still intention_to_discontinue. The behaviour is not considering_discontinuation, and the evidence strength is not strong. The comment is not used as proof that a SIP will be stopped."
            )
        if continuation == "missed_instalment" and behaviour != "missed_installment":
            types.append(TYPE_OTHER)
            notes.append(
                "The continuation label is still missed_instalment after the missed-instalment behaviour was removed. The saved evidence strength is none. This is not counted as discontinuation."
            )
        for inference_type in _named_types(reason):
            if inference_type not in types:
                types.append(inference_type)
        if not types:
            suggested = _model_only_type(reason)
            status = "human_review"
            types = [suggested or TYPE_OTHER]
            notes.append(
                "The stored reason describes the comment, but it does not name a label that was removed. The saved behaviour is left as stored. A person should decide whether any unsupported inference remains."
            )
        else:
            if TYPE_HISTORY in types:
                notes.append(
                    "A personal continuation, active journey, or stopped journey label was removed because the text does not state it. The saved behaviour is the label left after that check."
                )
            if TYPE_GENERAL in types and continuation != "intention_to_discontinue":
                notes.append(
                    "A personal discontinuation or intention label was removed. The comment is not counted as the writer stopping a SIP."
                )
            if TYPE_CAUSE in types:
                notes.append(
                    "A root-cause category was not kept. The saved category is unknown. Where a detail remains, it is a phrase from the comment; the rejected category name is not in the file."
                )
            if types == [TYPE_OTHER]:
                notes.append(
                    "A behaviour label was not kept because it had no exact excerpt. The rejected behaviour name is not stored, so the inference type cannot be recovered."
                )

    if behaviour == "missed_installment" and continuation == "missed_instalment":
        notes.append(
            "The saved missed-instalment label is still present. This audit does not treat that label as discontinuation and does not mark the missed-instalment label itself as an error."
        )

    result = row.copy()
    result["inference_type"] = types[0]
    result["review_status"] = status
    result["audit_note"] = " ".join(notes)
    result["additional_types"] = "; ".join(types[1:])
    return result


def build_audit(frame: pd.DataFrame) -> pd.DataFrame:
    """Return only rows whose unsupported_inference flag is true."""
    flagged = frame[frame["unsupported_inference"].str.lower() == "true"].copy()
    if flagged.empty:
        return pd.DataFrame(columns=AUDIT_COLUMNS)
    audited = flagged.apply(audit_row, axis=1)
    missing_type = ~audited["inference_type"].isin(INFERENCE_TYPES)
    missing_status = ~audited["review_status"].isin({"confirmed_error", "human_review"})
    if missing_type.any() or missing_status.any():
        raise ValueError("Every flagged row needs a known inference type and review status.")
    return audited.sort_values(["review_status", "inference_type", "record_id"])


def _count_table(audit: pd.DataFrame) -> list[tuple[str, int, int]]:
    """Count primary types separately for confirmed errors and human review."""
    rows = []
    for inference_type in INFERENCE_TYPES:
        matched = audit[audit["inference_type"] == inference_type]
        confirmed = int((matched["review_status"] == "confirmed_error").sum())
        review = int((matched["review_status"] == "human_review").sum())
        rows.append((inference_type, confirmed, review))
    return rows


def _examples(audit: pd.DataFrame, inference_type: str, status: str, limit: int = 3) -> list[str]:
    """Short record ids for one type and status. Text stays in the CSV."""
    matched = audit[
        (audit["inference_type"] == inference_type) & (audit["review_status"] == status)
    ]
    return matched["record_id"].head(limit).tolist()


def render_report(pilot: pd.DataFrame, audit: pd.DataFrame) -> str:
    """Write the audit summary. Counts come only from the rows above."""
    total = len(pilot)
    flagged = len(audit)
    confirmed = audit[audit["review_status"] == "confirmed_error"]
    review = audit[audit["review_status"] == "human_review"]
    still_intention = confirmed[confirmed["continuation_relevance"] == "intention_to_discontinue"]
    still_missed = confirmed[
        (confirmed["continuation_relevance"] == "missed_instalment")
        & (confirmed["behaviour"] != "missed_installment")
    ]
    additional_cause = int(
        audit["additional_types"].str.contains(TYPE_CAUSE, regex=False).sum()
    )
    unnamed_review = int(review["audit_note"].str.contains("does not name a label").sum())
    lines = [
        "# Classification quality audit",
        "",
        "This is an audit of the existing 100-record pilot in `classified_records_pilot.csv`. It is not a correction of those labels, and it is not a finding about the full dataset. No classification was changed.",
        "",
        "A row is included only when `unsupported_inference` is true. The flag means the classifier or its validation rules recorded an unsupported conclusion. Many of those conclusions were already replaced with `unknown` or with a more general label before this file was saved. This audit reads that record. It does not decide that every flagged row still contains a wrong label.",
        "",
        "## Coverage",
        "",
        f"- Pilot records read: {total}",
        f"- `unsupported_inference` true: {flagged}",
        f"- `unsupported_inference` false: {total - flagged}",
        f"- Confirmed errors: {len(confirmed)}",
        f"- Cases requiring human review: {len(review)}",
        "",
        "Confirmed error means the stored reason names a conclusion, and the original text, read without translation, does not state that conclusion. Human review means the comment is not in English, the removed label may still be a fair reading, or the reason does not name the label that was rejected.",
        "",
        "## Inference types",
        "",
        "Each row has one primary type. A second type is counted only in the note below the table. No row was given a type unless the stored reason or a still-present label supported it.",
        "",
        "| Inference type | Confirmed errors | Human review |",
        "| --- | ---: | ---: |",
    ]
    for inference_type, confirmed_count, review_count in _count_table(audit):
        lines.append(f"| {inference_type} | {confirmed_count} | {review_count} |")
    lines.extend(
        [
            "",
            f"Rows whose primary type is something else, but which also record an unsupported root-cause category: {additional_cause}. One of those is in human review, because the comment may still describe a personal SIP.",
            "",
            f"The human-review column is not a count of confirmed errors. {unnamed_review} of those rows have a stored reason that describes the comment but does not name the label that was rejected.",
            "",
            "### Invented personal investor history",
            "",
            "These confirmed rows record that an active journey, a stopped journey, or `actively_continuing` was removed. The text does not say the writer is continuing or has stopped a SIP. Comments that do state a personal SIP history are in the human-review list instead of this group.",
            "",
            "Example record ids: " + ", ".join(f"`{record_id}`" for record_id in _examples(audit, TYPE_HISTORY, "confirmed_error")) + ".",
            "",
            "### Confusing general discussion with personal behaviour",
            "",
            "These confirmed rows record that a discontinuation or intention label was removed, or a continuation label is still stored after that behaviour was removed. Advice, app complaints, and a non-SIP portfolio comment are not treated as the writer stopping a SIP.",
            "",
            "Example record ids: " + ", ".join(f"`{record_id}`" for record_id in _examples(audit, TYPE_GENERAL, "confirmed_error")) + ".",
            "",
            "### Treating missed instalments as discontinuation",
            "",
            "Confirmed errors of this type: 0. No flagged row describes a missed instalment that was kept as discontinuation. Two rows still have behaviour `missed_installment` and continuation `missed_instalment`. Their flag comes from an active journey stage that was removed. Those missed-instalment labels were not reclassified.",
            "",
            "### Inferring financial circumstances without evidence",
            "",
            "Confirmed errors of this type: 0. Among the flagged rows, no saved root-cause detail states income, age, first-time status, or an unstated financial circumstance. Amounts and losses that appear in a comment are quotations from that comment, not inferred circumstances.",
            "",
            "### Assigning root causes without supporting text",
            "",
            "The confirmed rows of this type have a stored reason saying the root-cause category was not kept. The saved category is `unknown`. The rejected category name is not in the file, so this audit does not say which category was proposed. A saved detail that remains is a phrase present in the comment.",
            "",
            "Example record ids: " + ", ".join(f"`{record_id}`" for record_id in _examples(audit, TYPE_CAUSE, "confirmed_error")) + ".",
            "",
            "### Other",
            "",
            "Confirmed rows of this type either lost a behaviour label because the evidence quote was not in the text, or still have continuation `missed_instalment` after that behaviour was removed. The rejected behaviour name is not stored for the quote failures, so no more specific type is assigned.",
            "",
            "## Confirmed errors still stored",
            "",
            "These saved continuation labels still conflict with the behaviour left on the row. They were not corrected.",
            "",
        ]
    )
    if still_intention.empty and still_missed.empty:
        lines.append("None.")
        lines.append("")
    for _, row in pd.concat([still_intention, still_missed]).iterrows():
        lines.extend(
            [
                f"- `{row['record_id']}` ({row['source'] or 'blank source'}): behaviour `{row['behaviour']}`, continuation `{row['continuation_relevance']}`, evidence strength `{row['evidence_strength']}`.",
                f"  - Evidence quote: {row['evidence_quote']}",
                f"  - Note: {row['audit_note']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Confirmed errors already removed from the saved behaviour",
            "",
            f"{len(confirmed) - len(still_intention) - len(still_missed)} confirmed rows name a label in `uncertainty_reason` that is no longer the saved behaviour. The reason is the evidence that the unsupported inference occurred. This audit does not put the removed label back and does not replace it with a new one.",
            "",
            "## Cases requiring human review",
            "",
            f"{len(review)} flagged rows are not called errors here.",
            "",
        ]
    )
    for _, row in review.sort_values("record_id").iterrows():
        lines.append(
            f"- `{row['record_id']}` ({row['source'] or 'blank source'}): {row['audit_note']} Stored reason: {row['uncertainty_reason']}"
        )
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "This audit covers the 100 classified pilot rows only. It does not call the classification model, does not change `classified_records_pilot.csv`, and does not claim that the pilot is representative or that any root cause caused a behaviour.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(pilot: pd.DataFrame, audit_path: Path | None = None, report_path: Path | None = None) -> pd.DataFrame:
    """Write the audit table and the markdown summary."""
    audit = build_audit(pilot)
    table_path = Path(audit_path) if audit_path is not None else AUDIT_PATH
    summary_path = Path(report_path) if report_path is not None else REPORT_PATH
    table_path.parent.mkdir(parents=True, exist_ok=True)
    audit.loc[:, AUDIT_COLUMNS].to_csv(table_path, index=False, encoding="utf-8")
    summary_path.write_text(render_report(pilot, audit), encoding="utf-8")
    return audit


def main() -> None:
    """Read the pilot file and write the audit outputs."""
    pilot = load_pilot(PILOT_PATH)
    audit = write_outputs(pilot)
    print(f"Read {len(pilot)} records from {PILOT_PATH}")
    print(f"Flagged rows: {len(audit)}")
    print(audit.groupby(['review_status', 'inference_type']).size().to_string())
    print(f"Wrote {AUDIT_PATH}")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
