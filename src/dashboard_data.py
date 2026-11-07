"""Load the secondary-research files for the local dashboard.

This module only reads files. It does not write datasets, call an API,
or turn a keyword match into a confirmed investor action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.audit_youtube_evidence import CATEGORY_PRIORITY
from src.google_play_analyze import DIRECT, INDIRECT, NOT_RELEVANT, rating_band


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED = "data/processed"

# Files the dashboard is allowed to read. Nothing here is written back.
RESEARCH_FILES = {
    "play_master": f"{PROCESSED}/google_play_reviews_master.csv",
    "play_evidence": f"{PROCESSED}/google_play_sip_evidence.csv",
    "play_categories": f"{PROCESSED}/google_play_problem_categories.csv",
    "play_comparative": f"{PROCESSED}/google_play_comparative_analysis.md",
    "play_quality": f"{PROCESSED}/google_play_quality_report.md",
    "youtube_master": f"{PROCESSED}/youtube_targeted_comments_master.csv",
    "youtube_audit": f"{PROCESSED}/youtube_evidence_audit.csv",
    "youtube_quality": f"{PROCESSED}/youtube_targeted_comments_quality_report.md",
    "youtube_audit_note": f"{PROCESSED}/youtube_evidence_audit.md",
    "findings": f"{PROCESSED}/sip_problem_discovery_groww.md",
}

APP_ORDER = ("Groww", "Zerodha Coin", "INDmoney")

# Friendly names for codes already stored in the files.
PLAY_CATEGORY_LABELS = {
    "sip_payment_failure": "SIP payment failure",
    "missed_instalment": "Missed instalment",
    "sip_pause_or_cancellation": "SIP pause or cancellation",
    "sip_amount_or_date_change": "SIP amount or date change",
    "sip_setup_and_registration": "SIP setup or registration",
    "redemption_or_withdrawal": "Redemption or withdrawal",
    "kyc_or_onboarding": "KYC or onboarding",
    "app_crash_or_technical": "Technical issue",
    "fund_selection_or_discovery": "Fund selection",
    "returns_losses_or_dissatisfaction": "Returns, losses, or dissatisfaction",
    "financial_constraints": "Financial constraints",
    "none": "No problem keyword",
}

YOUTUBE_CATEGORY_LABELS = {
    "missed_payment": "Missed payment",
    "general_educational_discussion": "General educational discussion",
    "first_person_actual_discontinuation": "First-person stopped/discontinued wording",
    "sip_cancellation": "First-person cancellation wording",
    "temporary_pause": "Temporary pause",
    "financial_difficulty": "Explicit financial difficulty",
    "intention_to_stop": "Intention to stop",
}

# A column may have been renamed. The first name that exists is used.
COLUMN_ALIASES = {
    "app_name": ("app_name", "app", "application"),
    "rating": ("rating", "score"),
    "review_text": ("review_text", "content", "review"),
    "sip_relevance": ("sip_relevance",),
    "possible_problem_category": ("possible_problem_category", "problem_category"),
    "review_count": ("review_count", "count"),
    "comment_text": ("comment_text", "text"),
    "video_id": ("video_id",),
    "video_title": ("video_title", "title"),
    "channel": ("channel", "channel_name"),
    "collection_batch": ("collection_batch", "batch"),
    "possible_evidence_category": ("possible_evidence_category", "evidence_category"),
    "manual_verification_required": ("manual_verification_required",),
    "comment_id": ("comment_id",),
}


@dataclass
class LoadedTable:
    """One CSV or markdown file, plus a plain-language load note."""

    key: str
    path: Path
    frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    text: str = ""
    message: str = ""


@dataclass
class ResearchBundle:
    """Every table and note the dashboard can show."""

    tables: dict[str, LoadedTable]

    def frame(self, key: str) -> pd.DataFrame:
        table = self.tables.get(key)
        if table is None:
            return pd.DataFrame()
        return table.frame

    def text(self, key: str) -> str:
        table = self.tables.get(key)
        if table is None:
            return ""
        return table.text

    def messages(self) -> list[str]:
        return [table.message for table in self.tables.values() if table.message]


@dataclass
class OverviewCounts:
    """Counts calculated from the loaded tables. Zero means no rows."""

    play_reviews: int = 0
    youtube_comments: int = 0
    apps: int = 0
    youtube_videos: int = 0
    youtube_channels: int = 0
    youtube_keyword_leads: int = 0
    play_sip_relevance_leads: int = 0
    play_direct: int = 0
    play_indirect: int = 0


def project_root() -> Path:
    """Folder that contains app.py and the data directory."""
    return PROJECT_ROOT


def resolve_column(frame: pd.DataFrame, key: str) -> str | None:
    """Return the actual column name for a logical field, if one exists."""
    if frame is None:
        return None
    columns = list(frame.columns)
    for candidate in COLUMN_ALIASES.get(key, (key,)):
        if candidate in columns:
            return candidate
    return None


def label_play_category(code: str) -> str:
    """Human label for a stored Play category code."""
    text = "" if code is None else str(code)
    return PLAY_CATEGORY_LABELS.get(text, text.replace("_", " ") or "Unlabelled")


def label_youtube_category(code: str) -> str:
    """Human label for a stored YouTube lead category."""
    text = "" if code is None else str(code)
    return YOUTUBE_CATEGORY_LABELS.get(text, text.replace("_", " ") or "Unlabelled")


def load_research(root: Path | None = None) -> ResearchBundle:
    """Read each research file. A missing file becomes an empty table."""
    base = project_root() if root is None else Path(root)
    tables: dict[str, LoadedTable] = {}
    for key, relative in RESEARCH_FILES.items():
        path = base / relative
        if relative.endswith(".csv"):
            tables[key] = _read_csv(key, path)
        else:
            tables[key] = _read_text(key, path)
    return ResearchBundle(tables=tables)


def _read_csv(key: str, path: Path) -> LoadedTable:
    if not path.exists():
        return LoadedTable(
            key=key,
            path=path,
            message=f"Missing file: {path.as_posix()}. Related charts show an empty state.",
        )
    try:
        # keep_default_na=False so the category word "none" and review text stay text.
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    except Exception as error:  # noqa: BLE001 - show the load problem, do not invent rows.
        return LoadedTable(
            key=key,
            path=path,
            message=f"Could not read {path.name}: {error}",
        )
    return LoadedTable(key=key, path=path, frame=frame)


def _read_text(key: str, path: Path) -> LoadedTable:
    if not path.exists():
        return LoadedTable(
            key=key,
            path=path,
            message=f"Missing file: {path.as_posix()}.",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as error:  # noqa: BLE001 - report the read problem.
        return LoadedTable(key=key, path=path, message=f"Could not read {path.name}: {error}")
    return LoadedTable(key=key, path=path, text=text)


def _nonempty(frame: pd.DataFrame, column: str | None) -> pd.Series:
    if column is None or column not in frame.columns:
        return pd.Series(dtype=str)
    values = frame[column].fillna("").astype(str)
    return values[values.str.strip() != ""]


def overview_counts(bundle: ResearchBundle) -> OverviewCounts:
    """KPI values. Each one is a row count or a unique-value count."""
    play = bundle.frame("play_master")
    youtube = bundle.frame("youtube_master")
    audit = bundle.frame("youtube_audit")
    counts = OverviewCounts(
        play_reviews=len(play.index),
        youtube_comments=len(youtube.index),
        youtube_keyword_leads=len(audit.index),
    )
    app_column = resolve_column(play, "app_name")
    counts.apps = int(_nonempty(play, app_column).nunique())
    video_column = resolve_column(youtube, "video_id")
    channel_column = resolve_column(youtube, "channel")
    counts.youtube_videos = int(_nonempty(youtube, video_column).nunique())
    counts.youtube_channels = int(_nonempty(youtube, channel_column).nunique())
    relevance_column = resolve_column(play, "sip_relevance")
    if relevance_column is not None:
        relevance = play[relevance_column].fillna("").astype(str)
        counts.play_direct = int((relevance == DIRECT).sum())
        counts.play_indirect = int((relevance == INDIRECT).sum())
        counts.play_sip_relevance_leads = counts.play_direct + counts.play_indirect
    return counts


def ordered_apps(frame: pd.DataFrame) -> list[str]:
    """Known apps first, then any other app name present in the file."""
    column = resolve_column(frame, "app_name")
    if column is None:
        return []
    found = list(_nonempty(frame, column).unique())
    ordered = [name for name in APP_ORDER if name in found]
    ordered.extend(sorted(name for name in found if name not in ordered))
    return ordered


def filter_apps(frame: pd.DataFrame, apps: list[str] | None) -> pd.DataFrame:
    """Keep the selected apps. None keeps every app. An empty list keeps none."""
    if frame is None or frame.empty:
        return pd.DataFrame(columns=[] if frame is None else frame.columns)
    column = resolve_column(frame, "app_name")
    if column is None or apps is None:
        return frame.copy()
    return frame[frame[column].isin(apps)].copy()


def filter_by_value(frame: pd.DataFrame, logical_column: str, value: str) -> pd.DataFrame:
    """Keep rows whose column equals value. 'All' and a missing column keep the rows."""
    if frame is None or frame.empty or not value or value == "All":
        return frame.copy() if frame is not None else pd.DataFrame()
    column = resolve_column(frame, logical_column)
    if column is None:
        return frame.copy()
    return frame[frame[column].astype(str) == value].copy()


def filter_search(frame: pd.DataFrame, logical_columns: tuple[str, ...], query: str) -> pd.DataFrame:
    """Case-insensitive search across the first text column that exists."""
    if frame is None or frame.empty or not query.strip():
        return frame.copy() if frame is not None else pd.DataFrame()
    mask = pd.Series(False, index=frame.index)
    used = False
    for logical in logical_columns:
        column = resolve_column(frame, logical)
        if column is None:
            continue
        used = True
        mask = mask | frame[column].astype(str).str.contains(query.strip(), case=False, na=False, regex=False)
    if not used:
        return frame.copy()
    return frame[mask].copy()


def app_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per app. Band and relevance cells are counts, and they sum to reviews."""
    columns = [
        "app_name",
        "reviews",
        "negative",
        "neutral",
        "positive",
        "unrated",
        "direct",
        "indirect",
        "not_relevant",
        "relevance_unlabelled",
    ]
    if frame is None or frame.empty:
        return pd.DataFrame(columns=columns)
    app_column = resolve_column(frame, "app_name")
    if app_column is None:
        return pd.DataFrame(columns=columns)
    rating_column = resolve_column(frame, "rating")
    relevance_column = resolve_column(frame, "sip_relevance")
    rows = []
    for app_name in ordered_apps(frame):
        group = frame[frame[app_column] == app_name]
        if rating_column is None:
            bands = {"negative": 0, "neutral": 0, "positive": 0, "unrated": len(group.index)}
        else:
            band_values = group[rating_column].map(rating_band)
            bands = {name: int((band_values == name).sum()) for name in ("negative", "neutral", "positive", "unrated")}
        if relevance_column is None:
            relevance = {"direct": 0, "indirect": 0, "not_relevant": 0, "relevance_unlabelled": len(group.index)}
        else:
            values = group[relevance_column].astype(str)
            known = values.isin([DIRECT, INDIRECT, NOT_RELEVANT])
            relevance = {
                "direct": int((values == DIRECT).sum()),
                "indirect": int((values == INDIRECT).sum()),
                "not_relevant": int((values == NOT_RELEVANT).sum()),
                "relevance_unlabelled": int((~known).sum()),
            }
        rows.append({"app_name": app_name, "reviews": len(group.index), **bands, **relevance})
    return pd.DataFrame(rows, columns=columns)


def category_counts_from_reviews(frame: pd.DataFrame) -> pd.DataFrame:
    """Primary category counts from the review rows, including 'none'."""
    empty = pd.DataFrame(columns=["app_name", "possible_problem_category", "review_count"])
    if frame is None or frame.empty:
        return empty
    app_column = resolve_column(frame, "app_name")
    category_column = resolve_column(frame, "possible_problem_category")
    if app_column is None or category_column is None:
        return empty
    counted = (
        frame.groupby([app_column, category_column], dropna=False)
        .size()
        .reset_index(name="review_count")
        .rename(columns={app_column: "app_name", category_column: "possible_problem_category"})
    )
    counted["review_count"] = counted["review_count"].astype(int)
    return counted.sort_values(["app_name", "possible_problem_category"]).reset_index(drop=True)


def category_file_matches_master(bundle: ResearchBundle) -> str:
    """Compare the saved category file with a fresh count of the master file."""
    master = category_counts_from_reviews(bundle.frame("play_master"))
    saved = bundle.frame("play_categories")
    if master.empty and saved.empty:
        return "No Google Play category counts are available."
    if saved.empty:
        return "The category count file is missing. Charts use the review master instead."
    count_column = resolve_column(saved, "review_count")
    app_column = resolve_column(saved, "app_name")
    category_column = resolve_column(saved, "possible_problem_category")
    if count_column is None or app_column is None or category_column is None:
        return "The category file is missing an expected column. Charts use the review master."
    saved_total = pd.to_numeric(saved[count_column], errors="coerce").fillna(0).sum()
    master_total = int(master["review_count"].sum()) if not master.empty else 0
    if int(saved_total) != master_total:
        return (
            f"Category file total ({int(saved_total)}) does not match the review master ({master_total}). "
            "Charts use the review master."
        )
    return f"Category file total matches the review master ({master_total} reviews)."


def youtube_lead_counts(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per known lead category, including categories with zero matches."""
    rows = []
    column = None if frame is None else resolve_column(frame, "possible_evidence_category")
    values = pd.Series(dtype=str) if column is None else frame[column].fillna("").astype(str)
    seen = list(CATEGORY_PRIORITY)
    if column is not None:
        for extra in sorted(set(values) - set(seen)):
            if extra:
                seen.append(extra)
    for code in seen:
        rows.append(
            {
                "category_code": code,
                "category": label_youtube_category(code),
                "comments": int((values == code).sum()) if column is not None else 0,
            }
        )
    return pd.DataFrame(rows)


def batch_counts(frame: pd.DataFrame) -> pd.DataFrame:
    """Comments and videos in each collection batch."""
    empty = pd.DataFrame(columns=["collection_batch", "batch_label", "comments", "videos"])
    if frame is None or frame.empty:
        return empty
    batch_column = resolve_column(frame, "collection_batch")
    if batch_column is None:
        return empty
    video_column = resolve_column(frame, "video_id")
    working = frame.copy()
    working["_batch"] = working[batch_column].fillna("").astype(str)
    grouped_comments = working.groupby("_batch").size()
    if video_column is None:
        grouped_videos = pd.Series(0, index=grouped_comments.index)
    else:
        grouped_videos = working.groupby("_batch")[video_column].nunique()
    rows = []
    for batch in sorted(grouped_comments.index, key=_batch_sort_key):
        rows.append(
            {
                "collection_batch": batch,
                "batch_label": f"Batch {batch}" if batch else "Unlabelled batch",
                "comments": int(grouped_comments.loc[batch]),
                "videos": int(grouped_videos.loc[batch]) if batch in grouped_videos.index else 0,
            }
        )
    return pd.DataFrame(rows)


def _batch_sort_key(value: str) -> tuple[int, str]:
    digits = "".join(character for character in str(value) if character.isdigit())
    return (int(digits) if digits else 10**9, str(value))


def source_record_counts(counts: OverviewCounts) -> pd.DataFrame:
    """Two record counts. They are not one combined population."""
    return pd.DataFrame(
        [
            {"source": "Google Play reviews", "records": counts.play_reviews, "population": "App reviews"},
            {"source": "YouTube comments", "records": counts.youtube_comments, "population": "Video comments"},
        ]
    )


def play_category_options(frame: pd.DataFrame) -> list[str]:
    """Category codes present in the review file, with the known list as a fallback."""
    column = None if frame is None else resolve_column(frame, "possible_problem_category")
    if column is None:
        return list(PLAY_CATEGORY_LABELS)
    found = [value for value in frame[column].fillna("").astype(str).unique() if value]
    ordered = [code for code in PLAY_CATEGORY_LABELS if code in found]
    ordered.extend(sorted(code for code in found if code not in ordered))
    return ordered


def split_findings(markdown: str) -> list[tuple[str, str]]:
    """Group the written report into the six navigation sections."""
    if not markdown.strip():
        return []
    parts = [part.strip() for part in __import__("re").split(r"(?=^## )", markdown, flags=__import__("re").M) if part.strip()]
    intro = []
    sections: dict[str, str] = {}
    for part in parts:
        if not part.startswith("## "):
            intro.append(part)
            continue
        heading = part.splitlines()[0].replace("## ", "", 1).strip()
        sections[heading] = part
    groups = [
        ("Research objective", ("1.",)),
        ("Methodology", ("2.",)),
        ("Findings", ("3.", "4.", "5.")),
        ("Research gaps", ("6.",)),
        ("Interview questions", ("7.",)),
        ("Research limitations", ("8.", "9.")),
    ]
    blocks: list[tuple[str, str]] = []
    if intro:
        blocks.append(("About this write-up", "\n\n".join(intro)))
    used: set[str] = set()
    for title, prefixes in groups:
        chosen = [text for heading, text in sections.items() if heading.startswith(prefixes)]
        used.update(heading for heading in sections if heading.startswith(prefixes))
        if chosen:
            blocks.append((title, "\n\n".join(chosen)))
    leftover = [text for heading, text in sections.items() if heading not in used]
    if leftover:
        blocks.append(("Additional notes", "\n\n".join(leftover)))
    if not blocks:
        blocks.append(("Research findings", markdown))
    return blocks
