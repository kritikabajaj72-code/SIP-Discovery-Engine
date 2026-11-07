"""Load Google Play reviews and YouTube comments into one table.

This module does not classify text. It only:

1. Finds CSV files in ``data/raw``.
2. Reads each file and looks at the column names that are really there.
3. Copies those columns into one shared schema.
4. Drops exact duplicate rows (different comments on the same video stay).
5. Writes ``data/processed/master_dataset.csv``.
6. Prints a short quality report.

Rows are not invented. If a file has no rating, app, link, or similar
optional field, that cell is left blank.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


# Folder layout is fixed by the project: this file lives in src/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_PATH = PROCESSED_DIR / "master_dataset.csv"

# Every output row uses these columns, in this order.
COMMON_COLUMNS = [
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

# source_type values requested for the two kinds of evidence.
APP_REVIEW = "app_review"
INVESTOR_DISCUSSION = "investor_discussion"

# Column names that strongly suggest each kind of file.
# Detection uses whatever headers are present; it does not trust the file name.
REVIEW_HINTS = {
    "review_text",
    "review_id",
    "app",
    "rating",
    "developer_reply",
    "helpful_votes",
    "app_version",
}
DISCUSSION_HINTS = {
    "comment",
    "comment_text",
    "video_id",
    "video_title",
    "video_url",
    "channel",
    "published_at",
}

# For each output field, try these source headers in order.
# The first header that actually exists in the file is the one we copy.
# Names are compared after light cleaning (see clean_column_name).
COLUMN_CANDIDATES = {
    APP_REVIEW: {
        "record_id": ["review_id", "id", "record_id"],
        "source": ["source", "platform"],
        "app": ["app", "app_name", "application"],
        "original_text": ["review_text", "review", "content", "text"],
        "rating": ["rating", "score", "stars"],
        "date": ["date", "review_date"],
        "video_title": ["video_title"],
        "channel": ["channel", "channel_name"],
        "source_url": ["review_url", "source_url", "url"],
    },
    INVESTOR_DISCUSSION: {
        "record_id": ["comment_id", "id", "record_id"],
        # Likes are not ratings, so "likes" is intentionally not listed.
        "source": ["source", "platform"],
        "app": ["app", "app_name", "application"],
        "original_text": ["comment", "comment_text", "text", "content"],
        "rating": ["rating", "score", "stars"],
        "date": ["published_at", "date", "comment_date"],
        "video_title": ["video_title", "title"],
        "channel": ["channel", "channel_name"],
        "source_url": ["video_url", "url", "source_url", "link"],
    },
}


def clean_column_name(name: str) -> str:
    """Turn a header into a simple key we can compare.

    ``Review Text`` and ``review_text`` both become ``review_text``.
    A UTF-8 byte-order mark on the first header is removed so ``source``
    is not missed.
    """
    text = str(name).replace("\ufeff", "").strip().lower()
    for character in (" ", "-", "."):
        text = text.replace(character, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def find_raw_csv_files(raw_dir: Path | None = None) -> list[Path]:
    """Return the two intended curated CSV inputs in a stable order."""
    folder = Path(raw_dir) if raw_dir is not None else RAW_DIR

    if not folder.is_dir():
        raise FileNotFoundError(f"Could not find the raw data folder: {folder}")

    required_files = [
        "sip_relevant_reviews.csv",
        "youtube_sip_keyword_filtered.csv",
    ]

    missing = [name for name in required_files if not (folder / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Required input files are missing from {folder}: {', '.join(missing)}"
        )

    return [folder / name for name in required_files]

def read_raw_csv(path: Path) -> pd.DataFrame:
    """Read one CSV as text, without guessing types or filling values.

    Reading everything as text keeps reviews and comments unchanged.
    ``keep_default_na=False`` stops the word "NA" inside a comment from
    being turned into a missing value.
    """
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(
            f"'{path.name}' is empty. Expected a header row and at least the text column."
        ) from exc
    except Exception as exc:
        raise ValueError(
            f"Could not read '{path.name}' as a CSV. "
            "Check that the file is comma-separated and saved as UTF-8. "
            f"Details: {exc}"
        ) from exc

    frame.columns = [str(column).replace("\ufeff", "").strip() for column in frame.columns]
    if len(frame.columns) == 0:
        raise ValueError(f"'{path.name}' has no column names.")
    return frame


def column_lookup(frame: pd.DataFrame) -> dict[str, str]:
    """Map a cleaned header to the header exactly as it appears in the file."""
    lookup: dict[str, str] = {}
    for original in frame.columns:
        lookup[clean_column_name(original)] = original
    return lookup


def detect_source_type(frame: pd.DataFrame, filename: str) -> str:
    """Decide whether a table is app reviews or investor discussion.

    The decision uses the column names in this file. A file with
    ``review_text`` and ``app`` is Google Play evidence. A file with
    ``comment`` and ``video_url`` is YouTube evidence.
    """
    present = set(column_lookup(frame))
    review_score = len(REVIEW_HINTS & present)
    discussion_score = len(DISCUSSION_HINTS & present)

    if review_score == 0 and discussion_score == 0:
        raise ValueError(
            f"Could not recognise '{filename}'. "
            f"Columns found: {list(frame.columns)}. "
            "A Google Play file needs a review column such as review_text. "
            "A YouTube file needs a comment column such as comment, plus video fields."
        )
    if review_score == discussion_score:
        raise ValueError(
            f"Could not tell what '{filename}' contains, because review columns "
            f"and YouTube columns are tied. Columns found: {list(frame.columns)}."
        )
    if review_score > discussion_score:
        return APP_REVIEW
    return INVESTOR_DISCUSSION


def match_columns(frame: pd.DataFrame, source_type: str) -> dict[str, str | None]:
    """Choose the source column for each shared field, or None if it is absent."""
    lookup = column_lookup(frame)
    plan = COLUMN_CANDIDATES[source_type]
    mapping: dict[str, str | None] = {}
    for field in COMMON_COLUMNS:
        if field == "source_type":
            # source_type is a label we assign. It is not copied from a column.
            mapping[field] = None
            continue
        mapping[field] = None
        for candidate in plan[field]:
            original = lookup.get(clean_column_name(candidate))
            if original is not None:
                mapping[field] = original
                break
    return mapping


def _blank_series(frame: pd.DataFrame) -> pd.Series:
    """An empty text value for every row. Used when a column is not in the file."""
    return pd.Series([""] * len(frame), index=frame.index, dtype="object")


def map_frame(frame: pd.DataFrame, source_type: str, filename: str) -> pd.DataFrame:
    """Copy one raw table into the shared schema.

    Missing optional columns become blank cells. The original wording of
    the text, dates, ratings, and links is copied as stored.
    """
    if source_type not in COLUMN_CANDIDATES:
        raise ValueError(
            f"Unknown source_type '{source_type}' for '{filename}'. "
            f"Use '{APP_REVIEW}' or '{INVESTOR_DISCUSSION}'."
        )

    mapping = match_columns(frame, source_type)
    text_column = mapping["original_text"]
    if text_column is None:
        expected = COLUMN_CANDIDATES[source_type]["original_text"]
        raise ValueError(
            f"'{filename}' looks like {source_type}, but no text column was found. "
            f"Looked for {expected}. Columns found: {list(frame.columns)}."
        )

    mapped = pd.DataFrame(index=frame.index)
    for field in COMMON_COLUMNS:
        if field == "source_type":
            mapped[field] = source_type
            continue
        source_column = mapping[field]
        if source_column is None:
            if field == "source":
                mapped[field] = (
                    "Google Play" if source_type == APP_REVIEW else "YouTube"
                )
            else:
                mapped[field] = _blank_series(frame)
        else:
            mapped[field] = frame[source_column].fillna("").astype(str)
    return mapped


def assign_missing_record_ids(frame: pd.DataFrame) -> pd.DataFrame:
    """Fill record_id only when the source file had no id column.

    Google Play rows keep ``review_id``. YouTube exports in this project
    have a video id but no comment id, so each comment gets a local key
    built from fields that are already on the row. The key is not a
    YouTube id and it does not add any new facts about the comment.
    """
    result = frame.copy()
    missing = result["record_id"].str.strip() == ""
    if not missing.any():
        return result

    other_fields = [column for column in COMMON_COLUMNS if column != "record_id"]
    for index in result.index[missing]:
        parts = [str(result.at[index, column]) for column in other_fields]
        digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]
        result.at[index, "record_id"] = f"local-{digest}"
    return result


def remove_exact_duplicates(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop rows that are identical across every shared field.

    Comments that share a video but differ in text, date, or link are kept.
    The first copy of an exact duplicate is the one that remains.
    """
    before = len(frame)
    deduped = frame.drop_duplicates(keep="first").reset_index(drop=True)
    return deduped, before - len(deduped)


def _quote_label(value: str) -> str:
    """Show a blank value as empty quotes so a report line stays readable.

    The dataset itself keeps the cell blank. This helper is only for printing.
    """
    return f'"{value}"'


def build_source_summary(combined: pd.DataFrame) -> list[dict]:
    """Count saved rows for each source, source type, and app.

    YouTube rows have no app in the source file, so their app value stays blank.
    Nothing in this summary fills in an app name.
    """
    if len(combined) == 0:
        return []

    grouped = (
        combined.groupby(["source", "source_type", "app"], dropna=False)
        .size()
        .reset_index(name="records")
        .sort_values(["source", "source_type", "app"], kind="mergesort")
    )
    return [
        {
            "source": "" if pd.isna(row.source) else str(row.source),
            "source_type": "" if pd.isna(row.source_type) else str(row.source_type),
            "app": "" if pd.isna(row.app) else str(row.app),
            "records": int(row.records),
        }
        for row in grouped.itertuples(index=False)
    ]


def confirm_text_preserved(loaded: pd.DataFrame, combined: pd.DataFrame) -> dict:
    """Check that every raw comment and review still appears in the saved table.

    Exact duplicate rows can be removed once. Their text still counts as
    preserved when one identical copy remains. No text is rewritten.
    """
    loaded_texts = loaded["original_text"] if len(loaded) else pd.Series(dtype="object")
    saved_texts = set(combined["original_text"]) if len(combined) else set()
    missing = [text for text in loaded_texts if text not in saved_texts]
    return {
        "texts_preserved": len(missing) == 0,
        "source_text_rows": int(len(loaded_texts)),
        "missing_source_texts": int(len(missing)),
    }


def build_quality_report(
    file_reports: list[dict],
    combined: pd.DataFrame,
    duplicates_removed: int,
) -> dict:
    """Collect the counts the quality report needs to print."""
    rows_loaded_by_source_type: dict[str, int] = {}
    rows_loaded_by_source: dict[str, int] = {}
    for report in file_reports:
        source_type = report["source_type"]
        rows_loaded_by_source_type[source_type] = (
            rows_loaded_by_source_type.get(source_type, 0) + report["rows_loaded"]
        )
        for source_name, count in report["rows_by_source"].items():
            rows_loaded_by_source[source_name] = rows_loaded_by_source.get(source_name, 0) + count

    missing_text = int(combined["original_text"].str.strip().eq("").sum()) if len(combined) else 0

    rows_by_source = (
        combined["source"].value_counts(dropna=False).sort_index().to_dict()
        if len(combined)
        else {}
    )
    rows_by_app = (
        combined["app"].value_counts(dropna=False).sort_index().to_dict()
        if len(combined)
        else {}
    )
    if len(combined):
        cross = (
            combined.groupby(["app", "source"], dropna=False)
            .size()
            .reset_index(name="rows")
            .sort_values(["source", "app"], kind="mergesort")
        )
        rows_by_app_and_source = [
            {
                "app": "" if pd.isna(row.app) else str(row.app),
                "source": "" if pd.isna(row.source) else str(row.source),
                "rows": int(row.rows),
            }
            for row in cross.itertuples(index=False)
        ]
    else:
        rows_by_app_and_source = []

    return {
        "files": file_reports,
        "rows_loaded_by_source_type": rows_loaded_by_source_type,
        "rows_loaded_by_source": rows_loaded_by_source,
        "combined_rows": int(len(combined)),
        "duplicates_removed": int(duplicates_removed),
        "missing_text": missing_text,
        "rows_by_source": {"" if pd.isna(key) else str(key): int(value) for key, value in rows_by_source.items()},
        "rows_by_app": {"" if pd.isna(key) else str(key): int(value) for key, value in rows_by_app.items()},
        "rows_by_app_and_source": rows_by_app_and_source,
        "source_summary": build_source_summary(combined),
    }


def print_quality_report(report: dict) -> None:
    """Print a plain-language summary of what was loaded and saved."""
    print("SIP data loader — quality report")
    print("-" * 40)
    print("Columns inspected and rows loaded from each file:")
    for file_report in report["files"]:
        print(f"  {file_report['filename']}  ({file_report['source_type']})")
        print(f"    columns: {', '.join(file_report['columns'])}")
        print(f"    rows loaded: {file_report['rows_loaded']}")
        print("    field mapping:")
        for field, source_column in file_report["mapping"].items():
            if field == "source_type":
                origin = f"labelled as {file_report['source_type']}"
            elif field == "record_id" and source_column is None:
                origin = "(no id column; a local key is built from the other fields)"
            elif source_column is None:
                origin = "(column not in this file, left blank)"
            else:
                origin = source_column
            print(f"      {field} <- {origin}")

    print("Rows loaded by source:")
    for source_name, count in report["rows_loaded_by_source"].items():
        print(f"  {_quote_label(source_name)}: {count}")

    print(f"Rows in the combined dataset: {report['combined_rows']}")
    print(f"Duplicate rows removed: {report['duplicates_removed']}")
    print(f"Missing text records: {report['missing_text']}")
    preservation = report.get("text_preservation", {})
    if preservation:
        status = "yes" if preservation["texts_preserved"] else "no"
        print(
            "Original comments and review text preserved: "
            f"{status} ({preservation['missing_source_texts']} missing "
            f"of {preservation['source_text_rows']} source texts)"
        )

    print("Source-level summary:")
    print(f"  {'source':<16} {'source_type':<22} {'app':<16} records")
    for row in report["source_summary"]:
        print(
            f"  {row['source']:<16} {row['source_type']:<22} "
            f"{row['app']:<16} {row['records']}"
        )


def load_master_dataset(
    raw_dir: Path | None = None,
    output_path: Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Load both raw CSVs, save the combined table, and return it with a report.

    The raw CSV files are only read. This function never writes to ``data/raw``.
    """
    folder = Path(raw_dir) if raw_dir is not None else RAW_DIR
    destination = Path(output_path) if output_path is not None else OUTPUT_PATH
    csv_files = find_raw_csv_files(folder)

    mapped_frames: list[pd.DataFrame] = []
    file_reports: list[dict] = []
    seen_types: set[str] = set()

    for path in csv_files:
        raw_frame = read_raw_csv(path)
        source_type = detect_source_type(raw_frame, path.name)
        seen_types.add(source_type)
        mapping = match_columns(raw_frame, source_type)
        mapped = map_frame(raw_frame, source_type, path.name)

        source_counts = mapped["source"].value_counts(dropna=False).to_dict()
        file_reports.append(
            {
                "filename": path.name,
                "source_type": source_type,
                "rows_loaded": int(len(mapped)),
                "columns": [str(column) for column in raw_frame.columns],
                "mapping": mapping,
                "rows_by_source": {str(key): int(value) for key, value in source_counts.items()},
            }
        )
        mapped_frames.append(mapped)

    missing_types = {APP_REVIEW, INVESTOR_DISCUSSION} - seen_types
    if missing_types:
        found = ", ".join(path.name for path in csv_files)
        pretty_missing = ", ".join(sorted(missing_types))
        raise ValueError(
            "Both datasets are required: Google Play reviews (app_review) and "
            f"YouTube comments (investor_discussion). Missing: {pretty_missing}. "
            f"CSV files seen: {found}."
        )

    loaded = pd.concat(mapped_frames, ignore_index=True)
    loaded = loaded[COMMON_COLUMNS]
    combined, duplicates_removed = remove_exact_duplicates(loaded)
    combined = assign_missing_record_ids(combined)

    destination.parent.mkdir(parents=True, exist_ok=True)
    # Empty optional fields, including YouTube app, are written as blank cells.
    combined.to_csv(destination, index=False, encoding="utf-8")

    report = build_quality_report(file_reports, combined, duplicates_removed)
    report["text_preservation"] = confirm_text_preserved(loaded, combined)
    report["output_path"] = str(destination)
    print_quality_report(report)
    print(f"Saved combined dataset to: {destination}")
    return combined, report


def main() -> None:
    """Entry point for ``python -m src.data_loader``."""
    load_master_dataset()


if __name__ == "__main__":
    main()
