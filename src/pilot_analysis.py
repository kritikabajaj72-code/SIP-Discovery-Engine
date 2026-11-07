"""Describe the 100-record pilot classification file.

This module only reads ``data/processed/classified_records_pilot.csv``.
It does not call Gemini and does not rewrite classification files.

Run from the project folder:

    python -m src.pilot_analysis
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PILOT_PATH = PROJECT_ROOT / "data" / "processed" / "classified_records_pilot.csv"
REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "pilot_analysis_report.md"
SUMMARY_PATH = PROJECT_ROOT / "data" / "processed" / "pilot_analysis_summary.csv"

PAYMENT_FRICTION = re.compile(r"\b(?:payment|instal+ments?|autopay|miss(?:ed|ing)?)\b", re.IGNORECASE)
GENERIC_STOP_ADVICE = re.compile(
    r"don'?t stop your sip|do not stop your sip|keep patience",
    re.IGNORECASE,
)
UNKNOWN_TEXT = {"", "unknown"}
REQUESTED_APPS = ("Groww", "Zerodha Coin", "INDmoney")
REQUESTED_SOURCES = ("Google Play", "YouTube")

# Existing labels only. These groups are not inferred from keywords.
FRICTION_GROUPS = (
    (
        "actual_discontinuation",
        "Actual discontinuation",
        lambda frame: (frame["behaviour"] == "explicitly_discontinued")
        | (frame["continuation_relevance"] == "actual_discontinuation"),
    ),
    (
        "intention_to_discontinue",
        "Intention to discontinue",
        lambda frame: (frame["behaviour"] == "considering_discontinuation")
        | (frame["continuation_relevance"] == "intention_to_discontinue"),
    ),
    (
        "missed_instalment",
        "Missed instalments",
        lambda frame: (frame["behaviour"] == "missed_installment")
        | (frame["continuation_relevance"] == "missed_instalment"),
    ),
    (
        "amount_reduction",
        "Amount reduction",
        lambda frame: frame["behaviour"] == "reducing_or_changing_amount",
    ),
)


def load_pilot(path: Path | None = None) -> pd.DataFrame:
    """Read the pilot classifications. Missing files are reported, not invented."""
    source = Path(path) if path is not None else PILOT_PATH
    if not source.is_file():
        raise FileNotFoundError(f"Could not find the pilot classifications at {source}.")
    frame = pd.read_csv(source, dtype=str, keep_default_na=False)
    required = [
        "record_id",
        "source",
        "app",
        "original_text",
        "source_url",
        "relevance_to_sip",
        "behaviour",
        "emotion",
        "root_cause",
        "root_cause_detail",
        "root_cause_category",
        "continuation_relevance",
        "evidence_quote",
        "evidence_strength",
        "confidence_score",
        "unsupported_inference",
    ]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{source.name} is missing columns: {', '.join(missing)}.")
    return frame


def _counts(frame: pd.DataFrame, column: str) -> list[tuple[str, int]]:
    """Return observed values and counts. Blank cells stay blank."""
    values = frame[column].fillna("").map(lambda value: str(value).strip())
    counts = values.value_counts(dropna=False)
    return [(str(name), int(count)) for name, count in counts.items()]


def _is_unknown(value: str) -> bool:
    return str(value).strip().lower() in UNKNOWN_TEXT


def average_confidence(frame: pd.DataFrame) -> tuple[float | None, int]:
    """Average the numeric confidence scores. Non-numeric scores are excluded."""
    scores = pd.to_numeric(frame["confidence_score"], errors="coerce")
    usable = scores.dropna()
    if usable.empty:
        return None, 0
    return float(usable.mean()), int(usable.shape[0])


def unknown_root_cause_count(frame: pd.DataFrame) -> int:
    """Count rows whose kept root-cause text is blank or Unknown."""
    detail = frame["root_cause_detail"] if "root_cause_detail" in frame.columns else frame["root_cause"]
    return int(detail.map(_is_unknown).sum())


def unsupported_inference_count(frame: pd.DataFrame) -> int | None:
    """Count true flags. Return None when the column has no usable values."""
    if "unsupported_inference" not in frame.columns:
        return None
    flags = frame["unsupported_inference"].str.strip().str.lower()
    if flags.eq("").all():
        return None
    return int(flags.isin({"true", "1", "yes"}).sum())


def source_url_text(value: str) -> str:
    """Show the stored URL. Do not create one when the cell is empty."""
    text = str(value).strip()
    if text:
        return text
    return "Not present in classified_records_pilot.csv"


def _comment_record(row: dict, group_id: str, group_label: str) -> dict:
    """Copy the fields the report is allowed to show."""
    return {
        "group_id": group_id,
        "group_label": group_label,
        "record_id": str(row["record_id"]),
        "source": row["source"],
        "app": row["app"],
        "behaviour": row["behaviour"],
        "continuation_relevance": row["continuation_relevance"],
        "evidence_strength": row["evidence_strength"],
        "evidence_quote": row["evidence_quote"],
        "original_text": row["original_text"],
        "source_url": source_url_text(row["source_url"]),
    }


def _by_evidence(frame: pd.DataFrame) -> pd.DataFrame:
    """Order stronger stored evidence before weaker evidence."""
    strength_order = {"strong": 0, "moderate": 1, "weak": 2, "none": 3}
    ordered = frame.copy()
    ordered["_strength_order"] = ordered["evidence_strength"].map(
        lambda value: strength_order.get(str(value).strip(), 9)
    )
    return ordered.sort_values(
        ["_strength_order", "confidence_score", "record_id"],
        ascending=[True, False, True],
    )


def friction_comments(frame: pd.DataFrame) -> list[dict]:
    """Collect up to 10 comments that speak to continuation friction.

    Discontinuation, intention, missed instalments, and amount changes come
    only from stored labels. Generic "don't stop your SIP" advice is not
    placed in those groups. Payment-operation comments that the classifier
    labelled as general advice can fill the remaining places, and they stay
    labelled as general advice.
    """
    selected: list[dict] = []
    seen: set[str] = set()
    for group_id, group_label, matcher in FRICTION_GROUPS:
        matches = _by_evidence(frame.loc[matcher(frame)])
        for row in matches.to_dict(orient="records"):
            record_id = str(row["record_id"])
            if record_id in seen:
                continue
            seen.add(record_id)
            selected.append(_comment_record(row, group_id, group_label))

    payment_rows = frame[
        frame["original_text"].str.contains(PAYMENT_FRICTION, na=False)
        & ~frame["original_text"].str.contains(GENERIC_STOP_ADVICE, na=False)
    ]
    payment_rows = _by_evidence(payment_rows)
    for row in payment_rows.to_dict(orient="records"):
        if len(selected) >= 10:
            break
        record_id = str(row["record_id"])
        if record_id in seen:
            continue
        seen.add(record_id)
        selected.append(
            _comment_record(
                row,
                "payment_operation_not_discontinuation",
                "Payment operations, not labelled as discontinuation",
            )
        )
    return selected[:10]


def build_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Build one row per reported count."""
    rows: list[dict[str, str]] = []

    def add(section: str, item: str, value: str) -> None:
        rows.append({"section": section, "item": item, "value": value})

    add("overview", "total_classified_records", str(len(frame)))
    source_counts = dict(_counts(frame, "source"))
    for source in REQUESTED_SOURCES:
        add("source", source, str(source_counts.get(source, 0)))
    for source, count in _counts(frame, "source"):
        if source not in REQUESTED_SOURCES:
            add("source", source if source else "(blank)", str(count))

    app_counts = dict(_counts(frame, "app"))
    for app in REQUESTED_APPS:
        add("app", app, str(app_counts.get(app, 0)))
    for app, count in _counts(frame, "app"):
        if app not in REQUESTED_APPS:
            add("app", app if app else "(blank)", str(count))

    for column, section in (
        ("relevance_to_sip", "sip_relevance"),
        ("behaviour", "behaviour"),
        ("root_cause_category", "root_cause_category"),
        ("emotion", "emotion"),
        ("continuation_relevance", "continuation_relevance"),
        ("evidence_strength", "evidence_strength"),
    ):
        for item, count in _counts(frame, column):
            add(section, item if item else "(blank)", str(count))

    mean_score, used = average_confidence(frame)
    add("confidence", "average", "" if mean_score is None else f"{mean_score:.3f}")
    add("confidence", "scores_used", str(used))
    add("root_cause", "unknown_root_cause_detail", str(unknown_root_cause_count(frame)))
    unsupported = unsupported_inference_count(frame)
    add(
        "unsupported_inference",
        "true",
        "" if unsupported is None else str(unsupported),
    )
    return pd.DataFrame(rows, columns=["section", "item", "value"])


def _distribution_lines(pairs: list[tuple[str, int]]) -> list[str]:
    if not pairs:
        return ["- No values recorded."]
    return [f"- {name if name else '(blank)'}: {count}" for name, count in pairs]


def render_report(frame: pd.DataFrame, comments: list[dict]) -> str:
    """Write the exploratory report from the summary counts and selected comments."""
    mean_score, used = average_confidence(frame)
    confidence_line = (
        "No numeric confidence scores are present."
        if mean_score is None
        else f"{mean_score:.3f} across {used} numeric scores."
    )
    unsupported = unsupported_inference_count(frame)
    unsupported_line = (
        "The unsupported_inference column is not available."
        if unsupported is None
        else str(unsupported)
    )
    lines = [
        "# SIP pilot analysis",
        "",
        "This is an exploratory analysis of a 100-record pilot. It is not the final research conclusion. The counts describe only the rows in `classified_records_pilot.csv`. They are not a statistically representative sample of SIP investors, and they do not show that one factor causes another.",
        "",
        "## Counts",
        "",
        f"- Total classified records: {len(frame)}",
        "",
        "### Source",
        *_distribution_lines(_counts(frame, "source")),
        "",
        "### App",
        "YouTube rows in this file have a blank app cell. Those rows are counted as blank rather than assigned to an app.",
        *_distribution_lines(_counts(frame, "app")),
        "",
        "### SIP relevance",
        *_distribution_lines(_counts(frame, "relevance_to_sip")),
        "",
        "### Behaviour",
        *_distribution_lines(_counts(frame, "behaviour")),
        "",
        "### Root cause category",
        *_distribution_lines(_counts(frame, "root_cause_category")),
        "",
        "### Emotion",
        *_distribution_lines(_counts(frame, "emotion")),
        "",
        "### Continuation relevance",
        *_distribution_lines(_counts(frame, "continuation_relevance")),
        "",
        "### Evidence strength",
        *_distribution_lines(_counts(frame, "evidence_strength")),
        "",
        f"- Average confidence score: {confidence_line}",
        f"- Records with unknown root cause detail: {unknown_root_cause_count(frame)}",
        f"- Records with unsupported inference flagged true: {unsupported_line}",
        "",
        "## Comments about SIP continuation friction",
        "",
        "The four continuation groups below use only the behaviour and continuation labels already stored in the pilot file. Advice such as \"don't stop your SIP\" is not listed as discontinuation. If a group has no rows, that label does not appear in this pilot. Source URLs are copied from the file. An empty Google Play source_url cell is reported as not present.",
        "",
        f"Comments shown: {len(comments)}. This pilot does not contain 10 comments that the stored labels separate into discontinuation, intention, missed instalments, or amount reduction.",
        "",
    ]
    grouped: dict[str, list[dict]] = {label: [] for _, label, _ in FRICTION_GROUPS}
    grouped["Payment operations, not labelled as discontinuation"] = []
    for comment in comments:
        grouped.setdefault(comment["group_label"], []).append(comment)
    section_labels = [label for _, label, _ in FRICTION_GROUPS]
    section_labels.append("Payment operations, not labelled as discontinuation")
    for label in section_labels:
        lines.append(f"### {label}")
        rows = grouped[label]
        if not rows:
            lines.append("No records in this pilot have this label.")
            lines.append("")
            continue
        for number, comment in enumerate(rows, start=1):
            lines.extend(
                [
                    f"{number}. Record `{comment['record_id']}`",
                    f"   - Source: {comment['source'] or '(blank)'}",
                    f"   - App: {comment['app'] or '(blank)'}",
                    f"   - Behaviour: {comment['behaviour']}",
                    f"   - Continuation relevance: {comment['continuation_relevance']}",
                    f"   - Evidence strength: {comment['evidence_strength']}",
                    f"   - Evidence quote: {comment['evidence_quote']}",
                    f"   - Source URL: {comment['source_url']}",
                    "   - Original text:",
                    "",
                    "```text",
                    comment["original_text"],
                    "```",
                    "",
                ]
            )
    lines.extend(
        [
            "A stored label with evidence strength `none` is not treated as proof that a SIP was stopped or missed. Payment-operation comments keep the behaviour label stored in the file.",
            "",
            "No generic SIP comments were added to reach 10.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(frame: pd.DataFrame, report_path: Path | None = None, summary_path: Path | None = None) -> None:
    """Write the markdown report and the summary table."""
    report_destination = Path(report_path) if report_path is not None else REPORT_PATH
    summary_destination = Path(summary_path) if summary_path is not None else SUMMARY_PATH
    summary = build_summary(frame)
    comments = friction_comments(frame)
    report_destination.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_destination, index=False, encoding="utf-8")
    report_destination.write_text(render_report(frame, comments), encoding="utf-8")


def main() -> None:
    """Read the pilot file and write the two analysis outputs."""
    frame = load_pilot(PILOT_PATH)
    write_outputs(frame)
    print(f"Read {len(frame)} records from {PILOT_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
