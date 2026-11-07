"""Build a blank review sheet for the YouTube video candidates.

This module only reads ``data/processed/youtube_video_candidates.csv``
and writes a new CSV for a person to fill in. It does not call Gemini
or any other API, and it does not change the candidate file.

A title is not treated as approval. The new review columns are left
blank on purpose.

Run from the project folder:

    python -m src.review_youtube_candidates

How to fill the sheet is explained in
``data/processed/youtube_video_candidates_review_README.md``.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_PATH = PROJECT_ROOT / "data" / "processed" / "youtube_video_candidates.csv"
REVIEW_PATH = PROJECT_ROOT / "data" / "processed" / "youtube_video_candidates_for_review.csv"

# These are the fields a reviewer needs on screen. They already exist
# in the candidate file. This list does not add or approve anything.
DISPLAY_FIELDS = (
    "title",
    "channel_name",
    "video_url",
    "search_query",
    "preliminary_topic",
)

# A person fills these in. They stay empty when this module runs.
REVIEW_FIELDS = (
    "human_review_status",
    "human_review_reason",
    "evidence_type",
)

# Allowed values for evidence_type. They are documented for the reviewer.
# This module does not write any of them into the sheet.
EVIDENCE_TYPES = (
    "first_person_actual_discontinuation",
    "first_person_intention_to_stop",
    "first_person_financial_difficulty",
    "first_person_missed_payment",
    "first_person_pause_or_cancellation",
    "general_educational_discussion",
    "other",
    "unknown",
)

# The current discovery file has one row per video.
EXPECTED_CANDIDATES = 160


def load_candidates(path: Path = CANDIDATES_PATH) -> tuple[list[str], list[dict[str, str]]]:
    """Read every candidate row. Missing files are reported, not invented."""
    if not path.is_file():
        raise FileNotFoundError(f"Could not find the candidate file at {path}.")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    missing = [field for field in DISPLAY_FIELDS if field not in fieldnames]
    if missing:
        raise ValueError(
            "The candidate file is missing columns needed for review: "
            + ", ".join(missing)
        )
    if len(rows) != EXPECTED_CANDIDATES:
        raise ValueError(
            f"Expected {EXPECTED_CANDIDATES} candidate videos, found {len(rows)}."
        )
    return fieldnames, rows


def review_fieldnames(original_fields: list[str]) -> list[str]:
    """Keep every original column, then add the blank review columns.

    Review columns are placed just after the fields a person looks at,
    so they are easy to edit in a spreadsheet. No original column is dropped.
    """
    leading = [field for field in DISPLAY_FIELDS if field in original_fields]
    remaining = [field for field in original_fields if field not in leading]
    return leading + list(REVIEW_FIELDS) + remaining


def build_review_rows(fieldnames: list[str], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Copy each video and leave the human-review cells empty."""
    review_rows = []
    for row in rows:
        copied = {field: row.get(field, "") for field in fieldnames if field not in REVIEW_FIELDS}
        for field in REVIEW_FIELDS:
            copied[field] = ""
        review_rows.append(copied)
    return review_rows


def display_candidates(rows: list[dict[str, str]]) -> None:
    """Print the fields a reviewer uses. This does not judge the videos."""
    print(f"Candidate videos: {len(rows)}")
    print("Preliminary topics are not approvals. Human-review fields are blank.")
    print()
    for number, row in enumerate(rows, start=1):
        print(f"{number}. {row.get('title', '')}")
        print(f"   Channel: {row.get('channel_name', '')}")
        print(f"   URL: {row.get('video_url', '')}")
        print(f"   Search query: {row.get('search_query', '')}")
        print(f"   Preliminary topic: {row.get('preliminary_topic', '')}")
        print()


def write_review_sheet(fieldnames: list[str], rows: list[dict[str, str]], path: Path = REVIEW_PATH) -> None:
    """Write the review CSV. The original candidate file is not opened for writing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main() -> None:
    """Read the 160 candidates, show them, and save a blank review sheet."""
    try:
        original_fields, rows = load_candidates()
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    fieldnames = review_fieldnames(original_fields)
    review_rows = build_review_rows(fieldnames, rows)
    display_candidates(review_rows)
    write_review_sheet(fieldnames, review_rows)
    print(f"Wrote {len(review_rows)} rows to {REVIEW_PATH}")
    print("Fill human_review_status, human_review_reason, and evidence_type by hand.")
    print("Allowed evidence_type values:")
    for evidence_type in EVIDENCE_TYPES:
        print(f"  {evidence_type}")


if __name__ == "__main__":
    main()
