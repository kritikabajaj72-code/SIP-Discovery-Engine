"""Classify a fixed 100-record pilot sample.

The sample mixes SIP wording with other comments and follows the source and
app mix in the master file. Progress is saved after each batch of 10.
Records already stored in the pilot file are skipped on the next run.

This does not write the validation files and does not classify the rest
of the master dataset.

Run from the project folder:

    python src/run_pilot.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classifier import (  # noqa: E402
    MASTER_PATH,
    classify_dataset,
    load_master,
    redact_secret,
)

PILOT_SIZE = 100
PILOT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "classified_records_pilot.csv"
PROTECTED_OUTPUTS = {
    PROJECT_ROOT / "data" / "processed" / "classified_records_validation.csv",
    PROJECT_ROOT / "data" / "processed" / "classified_records_validation_v2.csv",
}
SIP_WORD = re.compile(r"\bsips?\b", re.IGNORECASE)


def largest_remainder(counts: dict[tuple[str, str], int], total: int) -> dict[tuple[str, str], int]:
    """Split ``total`` across groups in proportion to their sizes."""
    population = sum(counts.values())
    if population == 0:
        return {key: 0 for key in counts}
    raw = {key: counts[key] / population * total for key in counts}
    allocated = {key: int(raw[key]) for key in counts}
    leftover = total - sum(allocated.values())
    order = sorted(counts, key=lambda key: (raw[key] - allocated[key], key[0], key[1]), reverse=True)
    for key in order[:leftover]:
        allocated[key] += 1
    return allocated


def _mix_group(rows: list[dict], count: int) -> list[dict]:
    """Take ``count`` rows, including both SIP wording and other wording when both exist."""
    if count <= 0:
        return []
    ordered = sorted(rows, key=lambda row: str(row["record_id"]))
    sip_rows = [row for row in ordered if SIP_WORD.search(str(row["original_text"]))]
    other_rows = [row for row in ordered if row not in sip_rows]
    if not sip_rows:
        return other_rows[:count]
    if not other_rows:
        return sip_rows[:count]
    if count == 1:
        pool = sip_rows if len(sip_rows) >= len(other_rows) else other_rows
        return pool[:1]
    sip_count = int(round(count * len(sip_rows) / len(ordered)))
    sip_count = min(max(sip_count, 1), count - 1)
    return sip_rows[:sip_count] + other_rows[: count - sip_count]


def select_pilot_records(frame, size: int = PILOT_SIZE) -> list[dict]:
    """Choose a stable pilot sample without using keyword matches alone."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in frame.to_dict(orient="records"):
        key = (str(row["source"]), str(row["app"]))
        groups.setdefault(key, []).append(row)
    targets = largest_remainder({key: len(rows) for key, rows in groups.items()}, size)
    selected: list[dict] = []
    for key in sorted(groups):
        selected.extend(_mix_group(groups[key], targets.get(key, 0)))
    if len(selected) != size:
        raise RuntimeError(
            f"The pilot sample has {len(selected)} records. Expected {size}."
        )
    return selected


def main() -> None:
    """Classify the 100-record pilot, resuming from the pilot file."""
    if PILOT_OUTPUT.resolve() in {path.resolve() for path in PROTECTED_OUTPUTS}:
        print("Error: the pilot output path would overwrite a validation file.", file=sys.stderr)
        raise SystemExit(1)

    try:
        master = load_master(MASTER_PATH)
        sample = select_pilot_records(master, PILOT_SIZE)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    print(
        f"Pilot sample contains {len(sample)} records. "
        f"The other {len(master) - len(sample)} master records are outside this run.",
        flush=True,
    )
    try:
        classify_dataset(
            max_records=None,
            output_path=PILOT_OUTPUT,
            record_ids={str(row["record_id"]) for row in sample},
        )
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
    print(f"Pilot file: {PILOT_OUTPUT}")


if __name__ == "__main__":
    main()
