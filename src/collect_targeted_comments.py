"""Collect public top-level comments for reviewed YouTube videos.

Reads the human review sheet and keeps rows marked include. Comments
are stored as YouTube returns them. They are not classified, and this
module does not call Gemini.

Running it with no arguments collects the included videos that come
after the first 20. Those first 20 are already in batch 1 and batch 2.
The rest are written to batch 3, batch 4, and so on, 10 videos at a
time. The program prints the plan and waits until you type YES.

One batch can still be collected on its own:

    python -m src.collect_targeted_comments --batch-start 10 --batch-size 10 --output data/raw/youtube_targeted_comments_batch2.csv

The YouTube API key is read from YOUTUBE_API_KEY in .env. It is never
printed. Existing raw files are never overwritten.

Each commentThreads request costs about 1 quota unit. One video needs
one request when it has 100 comments or fewer.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
REVIEW_PATH = PROJECT_ROOT / "data" / "processed" / "youtube_video_candidates_reviewed_initial.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "youtube_targeted_comments_batch1.csv"

# These raw files already exist. This module must never write to them.
PROTECTED_RAW_FILES = (
    PROJECT_ROOT / "data" / "raw" / "sip_relevant_reviews.csv",
    PROJECT_ROOT / "data" / "raw" / "youtube_sip_keyword_filtered.csv",
)

COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
DEFAULT_BATCH_SIZE = 10
DEFAULT_BATCH_START = 0
# Batch 1 and batch 2 already cover the first 20 included videos.
REMAINING_START = 20
FIRST_REMAINING_BATCH_NUMBER = 3
MAX_COMMENTS_PER_VIDEO = 100
PAGE_SIZE = 100
PAUSE_SECONDS = 0.3
REQUEST_TIMEOUT_SECONDS = 30

# A video can be skipped. These reasons are not quota failures.
UNAVAILABLE_REASONS = {
    "commentsDisabled",
    "videoNotFound",
    "videoOwnerDisabledComments",
}

# Stop the batch. More calls would spend quota or repeat the same failure.
STOP_REASONS = {
    "quotaExceeded",
    "dailyLimitExceeded",
    "rateLimitExceeded",
    "keyInvalid",
}

OUTPUT_COLUMNS = (
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


class CommentCollectionError(Exception):
    """The run cannot continue. The message must not contain the API key."""


def redact_secret(message: str, secret: str) -> str:
    """Remove the API key from any text before it is shown."""
    if not message:
        return ""
    if secret and secret in message:
        return message.replace(secret, "[redacted]")
    return message


def load_api_key() -> str:
    """Read the YouTube key from .env or the process environment."""
    load_dotenv(ENV_PATH)
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise CommentCollectionError(
            "YOUTUBE_API_KEY is missing. Add it to the .env file in the "
            "project folder. The Gemini key is not used."
        )
    return api_key


def parse_args() -> argparse.Namespace:
    """Read either a full remaining run or one explicit batch.

    With no batch flags, the run starts after the first 20 included
    videos and writes batch 3 onward. Passing --batch-start or --output
    collects one batch only.
    """
    parser = argparse.ArgumentParser(
        description="Collect top-level public comments for included YouTube videos."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Videos per batch. Default: 10.",
    )
    parser.add_argument(
        "--batch-start",
        type=int,
        default=None,
        help="Included videos to skip. Set this to collect one batch only.",
    )
    parser.add_argument(
        "--max-comments",
        type=int,
        default=MAX_COMMENTS_PER_VIDEO,
        help="Maximum top-level comments per video. Default: 100.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV for a single batch. Refuses to overwrite an existing file.",
    )
    return parser.parse_args()


def load_included_videos(path: Path = REVIEW_PATH) -> list[dict[str, str]]:
    """Keep review rows whose human_review_status is include, in file order."""
    if not path.is_file():
        raise CommentCollectionError(f"Could not find the review file at {path}.")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        required = {"human_review_status", "video_id", "title", "channel_name", "video_url", "search_query"}
        missing = sorted(required - fieldnames)
        if missing:
            raise CommentCollectionError(
                "The review file is missing columns: " + ", ".join(missing)
            )
        return [
            dict(row)
            for row in reader
            if (row.get("human_review_status") or "").strip() == "include"
        ]


def select_batch(videos: list[dict[str, str]], start: int, size: int) -> list[dict[str, str]]:
    """Take one slice of the included list. Later runs pass a higher start."""
    if start < 0 or size < 1:
        raise CommentCollectionError("--batch-start must be 0 or more, and --batch-size must be at least 1.")
    return videos[start:start + size]


def output_is_protected(path: Path) -> bool:
    """True when the path is an existing raw dataset or already exists."""
    resolved = path.resolve()
    protected = {item.resolve() for item in PROTECTED_RAW_FILES}
    if resolved in protected:
        return True
    return path.exists()


def batch_output_path(batch_number: int) -> Path:
    """Path for one numbered comment batch. Batch 1 and 2 already exist."""
    return PROJECT_ROOT / "data" / "raw" / f"youtube_targeted_comments_batch{batch_number}.csv"


def plan_remaining_batches(videos: list[dict[str, str]], start: int, size: int) -> list[dict]:
    """Build batch 3, batch 4, and so on for the videos after ``start``."""
    plans = []
    index = start
    number = FIRST_REMAINING_BATCH_NUMBER
    while index < len(videos):
        plans.append(
            {
                "number": number,
                "start": index,
                "videos": videos[index:index + size],
                "output": batch_output_path(number),
            }
        )
        index += size
        number += 1
    return plans


def confirm_collection(lines: list[str]) -> bool:
    """Show the plan and wait for YES. Any other answer cancels."""
    print("Collection plan:")
    for line in lines:
        print(line)
    print("No files have been written and no YouTube comments have been requested yet.")
    if not sys.stdin.isatty():
        print("Cancelled. This command needs an interactive terminal so you can confirm.")
        return False
    answer = input("Type YES to start collection. Anything else cancels: ")
    if answer.strip() != "YES":
        print("Cancelled. No comments were collected.")
        return False
    return True


def _error_reason(payload: dict) -> str:
    """Read a short YouTube reason such as commentsDisabled or quotaExceeded."""
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return ""
    reasons = error.get("errors")
    if isinstance(reasons, list) and reasons and isinstance(reasons[0], dict):
        return str(reasons[0].get("reason") or "")
    return str(error.get("status") or "")


def request_comment_page(api_key: str, video_id: str, page_token: str, page_size: int) -> dict:
    """Call commentThreads.list once. The request URL is never printed."""
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": str(page_size),
        "textFormat": "plainText",
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token
    request = Request(
        f"{COMMENT_THREADS_URL}?{urlencode(params)}",
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
        # Do not attach the response body. It can contain the request URL.
        raise CommentCollectionError(
            f"HTTP {exc.code}" + (f" {reason}" if reason else "")
        ) from exc
    except URLError as exc:
        raise CommentCollectionError(f"network error ({exc.reason})") from exc
    except TimeoutError as exc:
        raise CommentCollectionError("the request timed out") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CommentCollectionError("YouTube returned a response that was not JSON") from exc
    if not isinstance(payload, dict):
        raise CommentCollectionError("YouTube returned an unexpected response")
    return payload


def comments_from_page(payload: dict, video: dict[str, str]) -> list[dict[str, str]]:
    """Copy top-level comments. Replies are not requested and are not stored."""
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
        comment = snippet.get("topLevelComment") if isinstance(snippet.get("topLevelComment"), dict) else {}
        comment_snippet = comment.get("snippet") if isinstance(comment.get("snippet"), dict) else {}
        comment_id = str(comment.get("id") or "").strip()
        if not comment_id:
            continue
        like_count = comment_snippet.get("likeCount")
        rows.append(
            {
                "video_id": video.get("video_id", ""),
                "video_title": video.get("title", ""),
                "channel": video.get("channel_name", ""),
                "video_url": video.get("video_url", ""),
                "comment_id": comment_id,
                "comment_text": str(comment_snippet.get("textOriginal") or comment_snippet.get("textDisplay") or ""),
                "comment_published_at": str(comment_snippet.get("publishedAt") or ""),
                "like_count": "" if like_count is None else str(like_count),
                "discovery_search_query": video.get("search_query", ""),
            }
        )
    return rows


def collect_video_comments(api_key: str, video: dict[str, str], max_comments: int) -> list[dict[str, str]]:
    """Page through comment threads until the cap or the last page."""
    collected: list[dict[str, str]] = []
    page_token = ""
    while len(collected) < max_comments:
        page_size = min(PAGE_SIZE, max_comments - len(collected))
        payload = request_comment_page(api_key, video.get("video_id", ""), page_token, page_size)
        collected.extend(comments_from_page(payload, video))
        page_token = str(payload.get("nextPageToken") or "")
        if not page_token:
            break
        time.sleep(PAUSE_SECONDS)
    return collected[:max_comments]


def drop_duplicate_comment_ids(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[str]]:
    """Drop a later row only when its comment_id was already kept.

    The returned ID list is the duplicates that were not written. The same
    comment text on two different IDs is kept.
    """
    seen: set[str] = set()
    unique = []
    duplicate_ids = []
    for row in rows:
        comment_id = row["comment_id"]
        if comment_id in seen:
            duplicate_ids.append(comment_id)
            continue
        seen.add(comment_id)
        unique.append(row)
    return unique, duplicate_ids


def write_comments(rows: list[dict[str, str]], path: Path) -> None:
    """Create the output CSV. The caller must already have refused an existing path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def reason_from_message(message: str) -> str:
    """Return the YouTube reason token at the end of a short error message."""
    parts = message.split()
    return parts[-1] if parts else ""


def collect_batch(api_key: str, videos: list[dict[str, str]], max_comments: int) -> dict:
    """Collect comments video by video. Quota errors stop the rest of the batch."""
    comments: list[dict[str, str]] = []
    unavailable: list[tuple[str, str, str]] = []
    errors: list[tuple[str, str, str]] = []
    attempted = 0
    stopped = ""

    for index, video in enumerate(videos):
        video_id = (video.get("video_id") or "").strip()
        title = video.get("title", "")
        if index:
            time.sleep(PAUSE_SECONDS)
        attempted += 1
        if not video_id:
            errors.append(("", title, "missing video_id"))
            continue
        try:
            comments.extend(collect_video_comments(api_key, video, max_comments))
        except CommentCollectionError as exc:
            reason = reason_from_message(str(exc))
            if reason in UNAVAILABLE_REASONS:
                unavailable.append((video_id, title, reason))
                continue
            if reason in STOP_REASONS:
                stopped = reason
                errors.append((video_id, title, reason))
                break
            errors.append((video_id, title, reason or "request failed"))
    unique_comments, duplicate_ids = drop_duplicate_comment_ids(comments)
    return {
        "comments": unique_comments,
        "duplicate_ids": duplicate_ids,
        "attempted": attempted,
        "unavailable": unavailable,
        "errors": errors,
        "stopped": stopped,
    }


def empty_result() -> dict:
    """A batch result used when a file is skipped and no API call is made."""
    return {
        "comments": [],
        "duplicate_ids": [],
        "attempted": 0,
        "unavailable": [],
        "errors": [],
        "stopped": "",
    }


def run_one_batch(api_key: str, videos: list[dict[str, str]], max_comments: int, output: Path) -> dict:
    """Collect one batch and create its CSV. An existing path is not written."""
    if output_is_protected(output):
        print(f"Skipped {output}: the file already exists, so it was not overwritten.")
        result = empty_result()
        result["skipped_videos"] = len(videos)
        result["created"] = False
        return result
    result = collect_batch(api_key, videos, max_comments)
    result["skipped_videos"] = 0
    # A quota failure before any comment must not create an empty file.
    # An empty file would be skipped on the next run, and those videos
    # would never be collected.
    if result["stopped"] and not result["comments"]:
        result["created"] = False
        return result
    try:
        write_comments(result["comments"], output)
    except OSError as exc:
        raise CommentCollectionError(f"could not write the comment file ({exc})") from exc
    result["created"] = True
    return result


def print_execution_summary(included_count: int, totals: dict) -> None:
    """Print the combined result of every batch in this run."""
    print("Run summary:")
    print(f"Total included videos: {included_count}")
    print(f"Videos attempted in this execution: {totals['attempted']}")
    print(f"Videos skipped: {totals['skipped']}")
    print(f"Total comments collected in this execution: {totals['comments']}")
    print(f"Unavailable videos: {len(totals['unavailable'])}")
    for video_id, title, reason in totals["unavailable"]:
        print(f"  unavailable {video_id} ({reason}): {title}")
    print(f"API errors: {len(totals['errors'])}")
    for video_id, title, reason in totals["errors"]:
        print(f"  error {video_id} ({reason}): {title}")
    print(f"Duplicate comment IDs removed: {len(totals['duplicate_ids'])}")
    for comment_id in totals["duplicate_ids"]:
        print(f"  duplicate {comment_id}")
    created = totals["created"]
    print(f"Output filenames created: {len(created)}")
    for path in created:
        print(f"  {path}")
    if totals["stopped"]:
        print(f"Stopped because YouTube returned {totals['stopped']}. Later batches were not started.")


def collect_remaining(api_key: str, included: list[dict[str, str]], batch_size: int, max_comments: int) -> dict:
    """Collect every remaining batch. Existing batch files are skipped."""
    plans = plan_remaining_batches(included, REMAINING_START, batch_size)
    totals = {
        "attempted": 0,
        "skipped": 0,
        "comments": 0,
        "unavailable": [],
        "errors": [],
        "duplicate_ids": [],
        "created": [],
        "stopped": "",
    }
    for plan in plans:
        output = plan["output"]
        if output_is_protected(output):
            print(
                f"Skipped batch {plan['number']} ({len(plan['videos'])} videos): "
                f"{output} already exists."
            )
            totals["skipped"] += len(plan["videos"])
            continue
        print(f"Starting batch {plan['number']}: {len(plan['videos'])} videos.")
        result = run_one_batch(api_key, plan["videos"], max_comments, output)
        totals["attempted"] += result["attempted"]
        totals["comments"] += len(result["comments"])
        totals["unavailable"].extend(result["unavailable"])
        totals["errors"].extend(result["errors"])
        totals["duplicate_ids"].extend(result["duplicate_ids"])
        if result["created"]:
            totals["created"].append(output)
            print(f"Created {output} with {len(result['comments'])} comments.")
        if result["stopped"]:
            totals["stopped"] = result["stopped"]
            break
    return totals


def main() -> None:
    """Confirm, then collect the remaining batches or one requested batch."""
    args = parse_args()
    batch_size = DEFAULT_BATCH_SIZE if args.batch_size is None else args.batch_size
    max_comments = args.max_comments
    if batch_size < 1 or max_comments < 1 or max_comments > MAX_COMMENTS_PER_VIDEO:
        print(
            f"Error: --batch-size must be at least 1 and --max-comments must be from 1 to {MAX_COMMENTS_PER_VIDEO}.",
            file=sys.stderr,
        )
        sys.exit(1)

    single_batch = args.batch_start is not None or args.output is not None
    try:
        included = load_included_videos()
    except CommentCollectionError as exc:
        print(f"Error: {redact_secret(str(exc), os.getenv('YOUTUBE_API_KEY', ''))}", file=sys.stderr)
        sys.exit(1)

    if single_batch:
        start = DEFAULT_BATCH_START if args.batch_start is None else args.batch_start
        output = args.output if args.output is not None else DEFAULT_OUTPUT
        output = output if output.is_absolute() else PROJECT_ROOT / output
        try:
            selected = select_batch(included, start, batch_size)
        except CommentCollectionError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        if not selected:
            print(
                f"Error: no included videos in this batch. The review file has {len(included)} included videos.",
                file=sys.stderr,
            )
            sys.exit(1)
        plan_lines = [
            f"Total included videos: {len(included)}",
            f"Single batch: {len(selected)} videos starting at index {start}.",
            f"Output: {output}",
        ]
        if output_is_protected(output):
            print(f"Skipped {output}: the file already exists, so it was not overwritten.")
            print_execution_summary(
                len(included),
                {
                    "attempted": 0,
                    "skipped": len(selected),
                    "comments": 0,
                    "unavailable": [],
                    "errors": [],
                    "duplicate_ids": [],
                    "created": [],
                    "stopped": "",
                },
            )
            return
    else:
        plans = plan_remaining_batches(included, REMAINING_START, batch_size)
        plan_lines = [
            f"Total included videos: {len(included)}",
            f"Already collected elsewhere: the first {REMAINING_START} included videos (batch 1 and batch 2).",
            f"Remaining videos: {max(0, len(included) - REMAINING_START)}",
            f"Batch size: {batch_size}",
        ]
        if not plans:
            plan_lines.append("No remaining videos to collect.")
        for plan in plans:
            state = "already exists and will be skipped" if output_is_protected(plan["output"]) else "will be created"
            plan_lines.append(
                f"Batch {plan['number']}: {len(plan['videos'])} videos, index {plan['start']} -> {plan['output']} ({state})"
            )
        if not plans:
            print("\n".join(plan_lines))
            return

    if not confirm_collection(plan_lines):
        sys.exit(1)

    try:
        api_key = load_api_key()
        if single_batch:
            result = run_one_batch(api_key, selected, max_comments, output)
            print_execution_summary(
                len(included),
                {
                    "attempted": result["attempted"],
                    "skipped": result["skipped_videos"],
                    "comments": len(result["comments"]),
                    "unavailable": result["unavailable"],
                    "errors": result["errors"],
                    "duplicate_ids": result["duplicate_ids"],
                    "created": [output] if result["created"] else [],
                    "stopped": result["stopped"],
                },
            )
        else:
            totals = collect_remaining(api_key, included, batch_size, max_comments)
            print_execution_summary(len(included), totals)
    except CommentCollectionError as exc:
        print(f"Error: {redact_secret(str(exc), os.getenv('YOUTUBE_API_KEY', ''))}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
