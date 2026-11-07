"""Classify exactly 5 records and print each comment with its labels.

The sample is written to ``data/processed/classified_records_test.csv``.
Records after the first five are not sent to Gemini.

Run from the project folder:

    python src/test_classifier.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classifier import (  # noqa: E402
    CLASSIFICATION_FIELDS,
    MASTER_PATH,
    classify_records,
    load_master,
    redact_secret,
)

SAMPLE_SIZE = 5
TEST_OUTPUT = PROJECT_ROOT / "data" / "processed" / "classified_records_test.csv"


def display_results(rows: list[dict]) -> None:
    """Print each original comment followed by the fields Gemini returned."""
    for number, row in enumerate(rows, start=1):
        print("-" * 72)
        print(f"Record {number} of {len(rows)}")
        print(f"Original comment: {row['original_text']}")
        print("Classification:")
        for field in CLASSIFICATION_FIELDS:
            print(f"  {field}: {row[field]}")
    print("-" * 72)


def main() -> None:
    """Load the master file, classify the first five rows, and show them."""
    try:
        master = load_master(MASTER_PATH)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    if len(master) < SAMPLE_SIZE:
        print(
            f"Error: the master dataset has {len(master)} records. "
            f"This test needs {SAMPLE_SIZE}.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    sample = master.head(SAMPLE_SIZE).to_dict(orient="records")
    remaining = len(master) - len(sample)
    print(
        f"Selected {len(sample)} records from {MASTER_PATH.name}. "
        f"{remaining} records will not be processed.",
        flush=True,
    )

    try:
        classified = classify_records(sample, TEST_OUTPUT)
    except Exception as exc:
        # The message is already redacted. Do not print a traceback.
        secret = ""
        try:
            from dotenv import load_dotenv
            import os

            load_dotenv(PROJECT_ROOT / ".env")
            secret = os.getenv("GEMINI_API_KEY", "")
        except Exception:
            secret = ""
        print(f"Error: {redact_secret(str(exc), secret)}", file=sys.stderr)
        raise SystemExit(1) from None

    display_results(classified)
    print(f"Saved {len(classified)} records to {TEST_OUTPUT}")
    if len(classified) != SAMPLE_SIZE:
        print(
            f"Error: expected {SAMPLE_SIZE} classifications and received {len(classified)}.",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
