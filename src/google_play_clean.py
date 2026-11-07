"""Clean the unfiltered Google Play reviews.

Original review text is kept. YouTube comments are not read or written.
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.google_play_collect import RAW_COLUMNS


CLEAN_COLUMNS = RAW_COLUMNS + (
    "source_id",
    "source",
    "source_type",
    "empty_review",
    "rating_missing",
    "date_missing",
)


def read_raw_reviews(path: Path) -> list[dict[str, str]]:
    """Read the unfiltered CSV. A missing file is an error, not an empty study."""
    if not path.is_file():
        raise FileNotFoundError(f"Could not find the unfiltered reviews at {path}.")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in RAW_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Unfiltered file is missing columns: {', '.join(missing)}")
        return [dict(row) for row in reader]


def clean_reviews(rows: list[dict[str, str]]) -> dict:
    """Drop later copies of a review id and flag empty or incomplete fields."""
    kept: list[dict[str, str]] = []
    seen: set[str] = set()
    duplicate_ids: list[str] = []
    missing_id = 0
    for raw in rows:
        review_id = (raw.get("review_id") or "").strip()
        if not review_id:
            missing_id += 1
            continue
        if review_id in seen:
            duplicate_ids.append(review_id)
            continue
        seen.add(review_id)
        text = raw.get("review_text") if raw.get("review_text") is not None else ""
        rating = (raw.get("rating") or "").strip()
        review_date = (raw.get("review_date") or "").strip()
        package_id = (raw.get("package_id") or "").strip()
        row = {column: raw.get(column) if raw.get(column) is not None else "" for column in RAW_COLUMNS}
        row["review_text"] = text
        row["source_id"] = f"google_play:{package_id}:{review_id}"
        row["source"] = "Google Play"
        row["source_type"] = "app_review"
        row["empty_review"] = "true" if not str(text).strip() else "false"
        row["rating_missing"] = "true" if not rating else "false"
        row["date_missing"] = "true" if not review_date else "false"
        kept.append(row)
    return {
        "rows": kept,
        "rows_read": len(rows),
        "duplicate_ids": duplicate_ids,
        "missing_ids": missing_id,
    }


def write_csv(rows: list[dict[str, str]], path: Path, columns: tuple[str, ...]) -> None:
    """Write a derived CSV. Callers must not point this at a raw input file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
