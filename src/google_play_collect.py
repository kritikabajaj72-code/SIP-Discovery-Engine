"""Collect newest Google Play reviews for three investment apps.

Reviews are not filtered by topic. This module does not call Gemini.
The original sip_relevant_reviews.csv file is never written.

The real download happens only when a reviews function is passed in,
or when the pipeline asks for it after confirmation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_OUTPUT = PROJECT_ROOT / "data" / "raw" / "google_play_reviews_unfiltered.csv"
PROTECTED_RAW = PROJECT_ROOT / "data" / "raw" / "sip_relevant_reviews.csv"

# Package ids are the Google Play ids. Names are labels for the report.
APPS = (
    ("Groww", "com.nextbillion.groww"),
    ("Zerodha Coin", "com.zerodha.coin"),
    ("INDmoney", "in.indwealth"),
)

MAX_REVIEWS = 500
PAGE_SIZE = 200
LANGUAGE = "en"
COUNTRY = "in"

RAW_COLUMNS = (
    "review_id",
    "review_text",
    "rating",
    "review_date",
    "app_version",
    "thumbs_up_count",
    "developer_response",
    "developer_response_date",
    "app_name",
    "package_id",
    "collection_timestamp",
)


class CollectionError(Exception):
    """The download cannot continue. No partial file should be written."""


def output_is_blocked(path: Path) -> bool:
    """True when writing would replace an existing file or the old SIP extract."""
    resolved = path.resolve()
    if resolved == PROTECTED_RAW.resolve():
        return True
    return path.exists()


def default_reviews_callable():
    """Import the scraper only when a real download is requested."""
    try:
        from google_play_scraper import Sort, reviews
    except ImportError as exc:
        raise CollectionError(
            "google-play-scraper is not installed. "
            "Install project dependencies with: pip install -r requirements.txt"
        ) from exc

    def _reviews(package_id: str, count: int, continuation_token):
        return reviews(
            package_id,
            lang=LANGUAGE,
            country=COUNTRY,
            sort=Sort.NEWEST,
            count=count,
            continuation_token=continuation_token,
        )

    return _reviews


def _text(value: object) -> str:
    """Store a missing scraper field as an empty string. Do not invent a value."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def normalise_review(raw: dict, app_name: str, package_id: str, collected_at: str) -> dict[str, str]:
    """Map one scraper review onto the project columns."""
    version = raw.get("reviewCreatedVersion")
    if version in (None, ""):
        version = raw.get("appVersion")
    return {
        "review_id": _text(raw.get("reviewId")).strip(),
        "review_text": _text(raw.get("content")),
        "rating": _text(raw.get("score")),
        "review_date": _text(raw.get("at")),
        "app_version": _text(version),
        "thumbs_up_count": _text(raw.get("thumbsUpCount")),
        "developer_response": _text(raw.get("replyContent")),
        "developer_response_date": _text(raw.get("repliedAt")),
        "app_name": app_name,
        "package_id": package_id,
        "collection_timestamp": collected_at,
    }


def fetch_pages(package_id: str, reviews_func, max_reviews: int = MAX_REVIEWS, page_size: int = PAGE_SIZE) -> list[dict]:
    """Follow continuation tokens until the cap or the last page."""
    collected: list[dict] = []
    token = None
    while len(collected) < max_reviews:
        batch, token = reviews_func(
            package_id,
            count=min(page_size, max_reviews - len(collected)),
            continuation_token=token,
        )
        if not batch:
            break
        collected.extend(batch)
        if not token:
            break
    return collected[:max_reviews]


def dedupe_app_reviews(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep the first copy of each review id inside one app."""
    seen: set[str] = set()
    unique = []
    for row in rows:
        review_id = row.get("review_id", "").strip()
        if not review_id or review_id in seen:
            continue
        seen.add(review_id)
        unique.append(row)
    return unique


def collect_apps(reviews_func=None, max_reviews: int = MAX_REVIEWS, collected_at: str | None = None) -> dict:
    """Download each app. A failed app does not discard the error list.

    The caller must not write a file unless every app succeeded.
    """
    if reviews_func is None:
        reviews_func = default_reviews_callable()
    timestamp = collected_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows: list[dict[str, str]] = []
    app_counts: dict[str, int] = {}
    failures: list[tuple[str, str]] = []

    for app_name, package_id in APPS:
        try:
            raw_reviews = fetch_pages(package_id, reviews_func, max_reviews=max_reviews)
        except Exception as exc:
            # Keep the message short. Do not include a page of HTML from the store.
            detail = str(exc).strip().splitlines()[0][:180] if str(exc).strip() else type(exc).__name__
            failures.append((app_name, detail or type(exc).__name__))
            continue
        normalised = [
            normalise_review(item, app_name, package_id, timestamp)
            for item in raw_reviews
            if isinstance(item, dict)
        ]
        unique = dedupe_app_reviews(normalised)
        app_counts[app_name] = len(unique)
        rows.extend(unique)

    return {
        "rows": rows,
        "app_counts": app_counts,
        "failures": failures,
        "complete": len(failures) == 0 and len(app_counts) == len(APPS),
        "collection_timestamp": timestamp,
    }
