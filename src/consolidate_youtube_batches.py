"""Combine the nine YouTube comment batches into one master file.

The raw batch files are only read. This module does not call YouTube
or Gemini. Running it again replaces the master file and the quality
report, not the raw batches.

Run from the project folder:

    python -m src.consolidate_youtube_batches
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MASTER_PATH = PROCESSED_DIR / "youtube_targeted_comments_master.csv"
REPORT_PATH = PROCESSED_DIR / "youtube_targeted_comments_quality_report.md"

BATCH_COUNT = 9
ORIGINAL_COLUMNS = (
    "video_id",
    "video_title",
    "channel",
    "video_url",
    "comment_id",
    "comment_text",
    "comment_published_at",
    "like_count",
    "discovery_search_query",
)
BATCH_COLUMN = "collection_batch"
MASTER_COLUMNS = ORIGINAL_COLUMNS + (BATCH_COLUMN,)


@dataclass
class ConsolidationResult:
    """Rows kept for the master file, plus notes about what was skipped."""

    rows: list[dict[str, str]] = field(default_factory=list)
    rows_before_dedup: int = 0
    duplicate_comment_ids: list[str] = field(default_factory=list)
    empty_comment_rows: int = 0
    malformed_rows: int = 0
    errors: list[str] = field(default_factory=list)
    comments_per_batch_before_dedup: dict[int, int] = field(default_factory=dict)


def batch_path(batch_number: int, raw_dir: Path = RAW_DIR) -> Path:
    """Path of one raw batch. The file is not created here."""
    return raw_dir / f"youtube_targeted_comments_batch{batch_number}.csv"


def default_batch_paths(raw_dir: Path = RAW_DIR) -> list[tuple[int, Path]]:
    """The nine collected batches, in batch order."""
    return [(number, batch_path(number, raw_dir)) for number in range(1, BATCH_COUNT + 1)]


def read_batch(batch_number: int, path: Path) -> tuple[list[dict[str, str]], list[str], int]:
    """Read one batch. Missing or unreadable files become error strings.

    Returns rows, error messages, and a count of rows that had no comment id.
    """
    if not path.is_file():
        return [], [f"Missing batch file: {path}"], 0
    try:
        handle = path.open(encoding="utf-8", newline="")
    except OSError as exc:
        return [], [f"Could not read {path}: {exc}"], 0

    rows: list[dict[str, str]] = []
    malformed = 0
    with handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            return [], [f"Empty or headerless file: {path}"], 0
        missing = [column for column in ORIGINAL_COLUMNS if column not in fieldnames]
        if missing:
            return [], [f"{path} is missing columns: {', '.join(missing)}"], 0
        for raw in reader:
            if raw is None:
                malformed += 1
                continue
            comment_id = (raw.get("comment_id") or "").strip()
            if not comment_id:
                malformed += 1
                continue
            # Copy the collected text exactly. Only the new batch column is added.
            row = {column: raw.get(column) if raw.get(column) is not None else "" for column in ORIGINAL_COLUMNS}
            row[BATCH_COLUMN] = str(batch_number)
            rows.append(row)
    return rows, [], malformed


def consolidate(batch_files: list[tuple[int, Path]]) -> ConsolidationResult:
    """Join batches in order and keep the first row for each comment id."""
    result = ConsolidationResult()
    seen: set[str] = set()
    for batch_number, path in batch_files:
        rows, errors, malformed = read_batch(batch_number, path)
        result.errors.extend(errors)
        result.malformed_rows += malformed
        result.comments_per_batch_before_dedup[batch_number] = len(rows)
        result.rows_before_dedup += len(rows)
        for row in rows:
            comment_id = row["comment_id"].strip()
            if comment_id in seen:
                result.duplicate_comment_ids.append(comment_id)
                continue
            seen.add(comment_id)
            result.rows.append(row)
            if not row["comment_text"].strip():
                result.empty_comment_rows += 1
    return result


def write_master(rows: list[dict[str, str]], path: Path = MASTER_PATH) -> None:
    """Write the master CSV. This path is under data/processed, not data/raw."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MASTER_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in MASTER_COLUMNS})


def _duplicate_texts(rows: list[dict[str, str]]) -> list[tuple[str, int]]:
    """Exact comment strings that appear on more than one kept comment id.

    Blank text is not listed here. Empty comments are counted separately.
    """
    counts: Counter[str] = Counter()
    for row in rows:
        text = row["comment_text"]
        if text.strip():
            counts[text] += 1
    duplicates = [(text, count) for text, count in counts.items() if count > 1]
    duplicates.sort(key=lambda item: (-item[1], item[0][:80]))
    return duplicates


def build_quality_report(result: ConsolidationResult) -> str:
    """Describe the master file. This does not judge investor experience."""
    rows = result.rows
    videos = {row["video_id"] for row in rows if row["video_id"].strip()}
    channels = {row["channel"] for row in rows if row["channel"].strip()}
    per_video: Counter[str] = Counter(row["video_id"] for row in rows)
    missing_counts = {
        column: sum(1 for row in rows if not str(row.get(column, "")).strip())
        for column in MASTER_COLUMNS
    }
    duplicate_texts = _duplicate_texts(rows)
    lines = [
        "# YouTube targeted comments quality report",
        "",
        "This report describes the combined comment file. It does not infer who the commenters are, whether they are first-time investors, or why anyone stopped a SIP.",
        "",
        "Language detection has not been performed.",
        "",
        "## Size",
        "",
        f"- Total rows before deduplication: {result.rows_before_dedup}",
        f"- Unique comments after deduplication: {len(rows)}",
        f"- Duplicate comment IDs removed: {len(result.duplicate_comment_ids)}",
        f"- Rows skipped because the comment id was missing: {result.malformed_rows}",
        f"- Unique videos in the master file: {len(videos)}",
        f"- Unique channels in the master file: {len(channels)}",
        f"- Empty comments: {result.empty_comment_rows}",
        "",
        "The review sheet had 83 videos marked include. A video appears in this file only when at least one comment was saved. Videos with no saved comments are not counted above.",
        "",
        "## Comments per batch",
        "",
        "Counts below are rows read from each raw file before duplicate comment ids were removed.",
        "",
        "| Batch | Comments read |",
        "| ---: | ---: |",
    ]
    for batch_number in range(1, BATCH_COUNT + 1):
        lines.append(f"| {batch_number} | {result.comments_per_batch_before_dedup.get(batch_number, 0)} |")
    lines.extend(
        [
            "",
            "## Missing values by column",
            "",
            "A value is missing when the cell is empty after reading. Comment text is not rewritten.",
            "",
            "| Column | Empty cells |",
            "| --- | ---: |",
        ]
    )
    for column in MASTER_COLUMNS:
        lines.append(f"| `{column}` | {missing_counts[column]} |")
    lines.extend(["", "## Comments per video", "", "| Video id | Comments |", "| --- | ---: |"])
    for video_id, count in sorted(per_video.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{video_id}` | {count} |")
    lines.extend(
        [
            "",
            "## Duplicate comment IDs",
            "",
        ]
    )
    if result.duplicate_comment_ids:
        lines.append("These comment ids were already kept from an earlier batch or earlier row. The later copy was not added.")
        lines.append("")
        for comment_id in result.duplicate_comment_ids:
            lines.append(f"- `{comment_id}`")
    else:
        lines.append("No duplicate comment ids were found.")
    lines.extend(["", "## Exact duplicate comment text", ""])
    if duplicate_texts:
        extra = sum(count - 1 for _, count in duplicate_texts)
        lines.append(
            f"{len(duplicate_texts)} non-empty comment strings occur more than once "
            f"({extra} extra rows). The comment ids are different, so both rows are kept. "
            "Blank comments are not included in this list."
        )
        lines.append("")
        shown = duplicate_texts[:15]
        for text, count in shown:
            preview = " ".join(text.split())
            if len(preview) > 160:
                preview = preview[:160] + "..."
            lines.append(f"- {count} copies: {preview}")
        if len(duplicate_texts) > len(shown):
            lines.append(f"- {len(duplicate_texts) - len(shown)} further duplicate strings are not listed.")
    else:
        lines.append("No non-empty comment string is an exact copy of another kept comment.")
    lines.extend(["", "## File problems", ""])
    if result.errors:
        for error in result.errors:
            lines.append(f"- {error}")
    else:
        lines.append("All nine batch files were read and had the expected columns.")
    lines.extend(
        [
            "",
            "## Other notes",
            "",
            "- Deduplication keeps the first row for a comment id. Batch 1 is read before batch 2, and so on.",
            "- Like counts and dates are copied as text. They are not checked against YouTube.",
            "- The same comment text on two ids can be two people posting the same words, or one person posting twice. This report does not decide which.",
            "",
        ]
    )
    return "\n".join(lines)


def write_quality_report(result: ConsolidationResult, path: Path = REPORT_PATH) -> None:
    """Write the markdown quality report next to the master CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_quality_report(result), encoding="utf-8")


def main() -> None:
    """Read the nine raw batches and write the master file and quality report."""
    result = consolidate(default_batch_paths())
    write_master(result.rows)
    write_quality_report(result)
    print(f"Rows before deduplication: {result.rows_before_dedup}")
    print(f"Unique comments: {len(result.rows)}")
    print(f"Duplicate comment IDs removed: {len(result.duplicate_comment_ids)}")
    print(f"Wrote {MASTER_PATH}")
    print(f"Wrote {REPORT_PATH}")
    if result.errors:
        print("Some batch files could not be used:", file=sys.stderr)
        for error in result.errors:
            print(f"  {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
