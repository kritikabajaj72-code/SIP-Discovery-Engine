"""Find YouTube videos that may describe personal SIP experiences.

This module calls the YouTube Data API v3 search endpoint. It does not
download comments, and it does not call Gemini.

The API key is read from the local environment. Put it in the project
.env file as YOUTUBE_API_KEY. The key is never written into this file
and is never printed.

Each search request costs about 100 YouTube quota units. Ten queries
with one page each cost about 1,000 units. The default daily quota is
10,000 units.

Run from the project folder:

    python -m src.youtube_discovery

Optional settings in .env:

    YOUTUBE_MAX_RESULTS_PER_QUERY=25
    YOUTUBE_SEARCH_PAGES=1
    YOUTUBE_REGION_CODE=
"""

from __future__ import annotations

import csv
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "youtube_video_candidates.csv"

# Search only. Comments are a later step.
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# The research queries. They are stored with each video so a reviewer
# can see which search returned it.
SEARCH_QUERIES = (
    "I stopped my SIP why India",
    "why I discontinued my mutual fund SIP",
    "stopped SIP due to financial problems",
    "unable to continue monthly SIP India",
    "paused my SIP personal experience",
    "SIP missed payment personal experience",
    "first time investor stopped SIP India",
    "SIP investment regret India personal experience",
    "mutual fund SIP stopped after losses",
    "SIP cancellation experience India",
)

# One page of 25 videos per query is 10 API calls. Raise the page count
# only when you still have quota. YouTube allows at most 50 results per call.
DEFAULT_MAX_RESULTS = 25
DEFAULT_PAGES = 1
MAX_PAGES = 2
PAUSE_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 30

OUTPUT_COLUMNS = (
    "video_id",
    "title",
    "channel_name",
    "channel_id",
    "video_url",
    "publication_date",
    "search_query",
    "matched_queries",
    "preliminary_topic",
    "human_review_required",
    "classification_basis",
)

# Title patterns. The search query is not used here. A title that only
# contains the word SIP stays in "other" unless one of these patterns matches.
TOPIC_RULES = (
    (
        "actual discontinuation experience",
        re.compile(
            r"\b(?:i|i've|i have|i had)\b.{0,50}\b(?:stopped|discontinued|quit)\b"
            r"|\bwhy i (?:stopped|discontinued)\b"
            r"|\b(?:stopped|discontinued) my (?:mutual fund )?sips?\b",
            re.IGNORECASE,
        ),
        "The title uses first-person words about having stopped or discontinued.",
    ),
    (
        "intention to discontinue",
        re.compile(
            r"\b(?:thinking of stopping|want to stop|should i stop|might stop|"
            r"planning to (?:stop|discontinu\w*))\b",
            re.IGNORECASE,
        ),
        "The title talks about thinking of stopping, not about having stopped.",
    ),
    (
        "missed instalments",
        re.compile(
            r"\bmiss(?:ed|ing)?\b.{0,40}\b(?:payment|sip|instal\w*)\b"
            r"|\b(?:payment|instal\w*)\b.{0,40}\bmiss(?:ed|ing)?\b",
            re.IGNORECASE,
        ),
        "The title mentions a missed payment or instalment.",
    ),
    (
        "pausing or cancellation",
        re.compile(r"\bpaus\w*\b|\bcancel\w*\b", re.IGNORECASE),
        "The title mentions pausing or cancellation.",
    ),
    (
        "financial constraints",
        re.compile(
            r"financial problem|unable to continue|can(?:not|'t) afford|no money",
            re.IGNORECASE,
        ),
        "The title mentions money problems or being unable to continue.",
    ),
    (
        "market losses or disappointing returns",
        re.compile(
            r"\b(?:loss|losses|regret|disappoint\w*|negative returns?|"
            r"returns? (?:are )?fall\w*)\b",
            re.IGNORECASE,
        ),
        "The title mentions losses, regret, or weak returns.",
    ),
    (
        "general SIP education",
        re.compile(
            r"\b(?:how to|beginners?|explained|what is|what are|guide|tutorial|mistakes?)\b",
            re.IGNORECASE,
        ),
        "The title reads as a guide, explainer, or mistakes video.",
    ),
)


class YouTubeSearchError(Exception):
    """A search failed. The message must not contain the API key."""

    def __init__(self, message: str, found: dict | None = None, summary: list | None = None) -> None:
        super().__init__(message)
        self.found = found or {}
        self.summary = summary or []


def redact_secret(message: str, secret: str) -> str:
    """Remove the API key from an error before it is shown."""
    if not message:
        return ""
    cleaned = message
    if secret:
        cleaned = cleaned.replace(secret, "[redacted]")
    return cleaned


def load_api_key() -> str:
    """Read YOUTUBE_API_KEY from .env or the process environment."""
    load_dotenv(ENV_PATH)
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise YouTubeSearchError(
            "YOUTUBE_API_KEY is missing. Add it to the .env file in the "
            "project folder. The Gemini key is not used for YouTube."
        )
    return api_key


def _bounded_int(name: str, default: int, low: int, high: int) -> int:
    """Read an optional integer setting and keep it inside a safe range."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(low, min(value, high))


def classify_title(title: str) -> tuple[str, str]:
    """Give a title a provisional topic. This is not a relevance decision.

    A video is not marked as a discontinuation experience just because
    the title contains SIP or because the search query was about stopping.
    """
    text = html.unescape(title or "")
    for topic, pattern, basis in TOPIC_RULES:
        if pattern.search(text):
            return topic, basis + " Human review is required."
    return (
        "other",
        "The title does not state a personal SIP experience. "
        "It is not treated as relevant only because it was returned for a SIP search. "
        "Human review is required.",
    )


def video_url(video_id: str) -> str:
    """Build the normal watch URL from a video id."""
    return f"https://www.youtube.com/watch?v={video_id}"


def _error_reason(payload: dict) -> str:
    """Read the YouTube error reason, such as quotaExceeded."""
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return ""
    reasons = error.get("errors")
    if isinstance(reasons, list) and reasons and isinstance(reasons[0], dict):
        return str(reasons[0].get("reason") or "")
    return str(error.get("status") or "")


def search_once(api_key: str, query: str, page_token: str = "") -> dict:
    """Call search.list once. The request URL is never printed."""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": str(_bounded_int("YOUTUBE_MAX_RESULTS_PER_QUERY", DEFAULT_MAX_RESULTS, 1, 50)),
        "key": api_key,
    }
    region = os.getenv("YOUTUBE_REGION_CODE", "").strip()
    if region:
        params["regionCode"] = region
    if page_token:
        params["pageToken"] = page_token

    request = Request(
        f"{SEARCH_URL}?{urlencode(params)}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        reason = ""
        try:
            reason = _error_reason(json.loads(body)) if body else ""
        except json.JSONDecodeError:
            reason = ""
        # Do not include the response body. It can repeat the request URL.
        raise YouTubeSearchError(
            f"YouTube search failed (HTTP {exc.code}"
            + (f", {reason}" if reason else "")
            + ")."
        ) from exc
    except URLError as exc:
        raise YouTubeSearchError(
            f"Could not reach the YouTube API ({exc.reason})."
        ) from exc
    except TimeoutError as exc:
        raise YouTubeSearchError("The YouTube API request timed out.") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise YouTubeSearchError("YouTube returned a response that was not JSON.") from exc
    if not isinstance(payload, dict):
        raise YouTubeSearchError("YouTube returned an unexpected response.")
    return payload


def rows_from_page(payload: dict, query: str) -> list[dict]:
    """Turn one search page into video rows. Channels and playlists are skipped."""
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        identifier = item.get("id") if isinstance(item.get("id"), dict) else {}
        if identifier.get("kind") not in (None, "youtube#video"):
            continue
        video_id = str(identifier.get("videoId") or "").strip()
        if not video_id:
            continue
        snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
        title = str(snippet.get("title") or "")
        topic, basis = classify_title(title)
        rows.append(
            {
                "video_id": video_id,
                "title": title,
                "channel_name": str(snippet.get("channelTitle") or ""),
                "channel_id": str(snippet.get("channelId") or ""),
                "video_url": video_url(video_id),
                "publication_date": str(snippet.get("publishedAt") or ""),
                "search_query": query,
                "matched_queries": query,
                "preliminary_topic": topic,
                "human_review_required": "true",
                "classification_basis": basis,
            }
        )
    return rows


def add_unique(found: dict[str, dict], rows: list[dict]) -> int:
    """Keep the first copy of a video and record any later query that found it.

    Returns the number of videos that were not already in ``found``.
    """
    added = 0
    for row in rows:
        video_id = row["video_id"]
        existing = found.get(video_id)
        if existing is None:
            found[video_id] = row
            added += 1
            continue
        queries = existing["matched_queries"].split(" | ")
        if row["search_query"] not in queries:
            queries.append(row["search_query"])
            existing["matched_queries"] = " | ".join(queries)
    return added


def search_all(api_key: str) -> tuple[dict[str, dict], list[tuple[str, int, int]]]:
    """Run every query. Stop when the quota is used up and keep earlier results."""
    pages = _bounded_int("YOUTUBE_SEARCH_PAGES", DEFAULT_PAGES, 1, MAX_PAGES)
    found: dict[str, dict] = {}
    summary: list[tuple[str, int, int]] = []

    for index, query in enumerate(SEARCH_QUERIES):
        if index:
            time.sleep(PAUSE_SECONDS)
        returned = 0
        page_token = ""
        try:
            for _ in range(pages):
                payload = search_once(api_key, query, page_token)
                page_rows = rows_from_page(payload, query)
                returned += len(page_rows)
                add_unique(found, page_rows)
                page_token = str(payload.get("nextPageToken") or "")
                if not page_token:
                    break
                time.sleep(PAUSE_SECONDS)
        except YouTubeSearchError as exc:
            # quotaExceeded and other request errors should not start more calls.
            new_count = sum(1 for row in found.values() if row["search_query"] == query)
            summary.append((query, returned, new_count))
            raise YouTubeSearchError(
                f"{exc} Stopped during query {index + 1} of {len(SEARCH_QUERIES)}: {query}",
                found,
                summary,
            ) from exc
        new_count = sum(1 for row in found.values() if row["search_query"] == query)
        summary.append((query, returned, new_count))
    return found, summary


def write_candidates(rows: list[dict], path: Path = OUTPUT_PATH) -> None:
    """Save the candidate table. This does not touch the raw datasets."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def print_summary(summary: list[tuple[str, int, int]], unique_count: int) -> None:
    """Show how many videos each query returned and how many were new."""
    print("Videos returned by each search query:")
    for query, returned, new_count in summary:
        print(f"  {returned} returned, {new_count} new: {query}")
    print(f"Total unique videos: {unique_count}")
    print("Every preliminary topic requires human review.")
    print("A title that only mentions SIP is not treated as a relevant experience.")


def main() -> None:
    """Search YouTube and write the candidate CSV."""
    try:
        api_key = load_api_key()
        found, summary = search_all(api_key)
    except YouTubeSearchError as exc:
        safe_message = redact_secret(str(exc), os.getenv("YOUTUBE_API_KEY", ""))
        print(f"Error: {safe_message}", file=sys.stderr)
        if exc.found:
            rows = list(exc.found.values())
            write_candidates(rows)
            print_summary(exc.summary, len(rows))
            print(f"Wrote the partial result to {OUTPUT_PATH}")
        sys.exit(1)

    rows = list(found.values())
    write_candidates(rows)
    print_summary(summary, len(rows))
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
