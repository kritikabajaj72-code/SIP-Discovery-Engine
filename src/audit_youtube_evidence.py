"""Keyword screen of the combined YouTube comments.

A match is a lead for a person to read. It is not confirmation that the
commenter stopped a SIP, missed a payment, or had a money problem.

This module does not call YouTube or Gemini. It reads the master CSV
written by ``src.consolidate_youtube_batches``.

Run from the project folder:

    python -m src.audit_youtube_evidence
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTER_PATH = PROJECT_ROOT / "data" / "processed" / "youtube_targeted_comments_master.csv"
AUDIT_CSV_PATH = PROJECT_ROOT / "data" / "processed" / "youtube_evidence_audit.csv"
AUDIT_MD_PATH = PROJECT_ROOT / "data" / "processed" / "youtube_evidence_audit.md"

SOURCE_COLUMNS = (
    "video_id",
    "video_title",
    "channel",
    "video_url",
    "comment_id",
    "comment_text",
    "comment_published_at",
    "like_count",
    "discovery_search_query",
    "collection_batch",
)
AUDIT_COLUMNS = SOURCE_COLUMNS + (
    "possible_evidence_category",
    "keyword_matches",
    "evidence_quote",
    "manual_verification_required",
)

# Category names are possible leads. They are not confirmed experiences.
ACTUAL = "first_person_actual_discontinuation"
INTENTION = "intention_to_stop"
FINANCIAL = "financial_difficulty"
MISSED = "missed_payment"
PAUSE = "temporary_pause"
CANCEL = "sip_cancellation"
EDUCATION = "general_educational_discussion"

# Earlier categories win only after question and advice have been applied
# in screen_comment. This order is the fallback when those do not apply.
CATEGORY_PRIORITY = (ACTUAL, INTENTION, PAUSE, CANCEL, MISSED, FINANCIAL, EDUCATION)


@dataclass(frozen=True)
class KeywordRule:
    """One transparent pattern. The quote is the original matched slice."""

    name: str
    category: str
    pattern: re.Pattern[str]


def _rule(name: str, category: str, expression: str) -> KeywordRule:
    return KeywordRule(name, category, re.compile(expression, re.IGNORECASE))


# Questions and advice are listed first so a later reader can see why a
# comment was not called a personal discontinuation.
RULES: tuple[KeywordRule, ...] = (
    _rule(
        "advice_not_personal_experience",
        EDUCATION,
        r"don'?t stop(?: your)? sips?|do not stop(?: your)? sips?|never stop(?: your)? sips?"
        r"|should not stop(?: your)? sips?|keep patience|those who stop|people who stop",
    ),
    _rule(
        "question_about_stopping",
        EDUCATION,
        r"\b(?:should|can|shall|could|would|do) i\b.{0,50}\b(?:stop|pause|cancel|discontinu\w*)\b"
        r"|\bhow (?:do|to|can) i\b.{0,50}\b(?:stop|pause|cancel|discontinu\w*)\b"
        r"|\b(?:is it|whether to)\b.{0,40}\b(?:stop|pause|cancel)\b",
    ),
    _rule(
        "first_person_stopped_or_discontinued",
        ACTUAL,
        r"\b(?:i've|i have|ive)(?: already)? stopped\b.{0,30}\bsips?\b"
        r"|\bi stopped (?:my |the )?(?:mutual fund )?sips?\b"
        r"|\b(?:i've|i have|ive)(?: already)? discontinued\b.{0,30}\bsips?\b"
        r"|\bdiscontinued my (?:mutual fund )?sips?\b",
    ),
    _rule(
        "first_person_intention",
        INTENTION,
        r"\b(?:i am|i'm|im)\b.{0,30}\b(?:thinking|planning|considering)\b.{0,40}\b(?:stop|discontinu\w*)\b"
        r"|\bi (?:want|wanna|wish) to (?:stop|discontinue)\b",
    ),
    _rule(
        "first_person_pause",
        PAUSE,
        r"\b(?:i|i've|i have)\b.{0,40}\bpaus(?:e|ed|ing)\b.{0,30}\bsips?\b"
        r"|\bpaused my sips?\b",
    ),
    _rule(
        "first_person_cancellation",
        CANCEL,
        r"\b(?:i|i've|i have)\b.{0,40}\bcancell?ed\b.{0,30}\bsips?\b"
        r"|\bcancell?ed my sips?\b",
    ),
    _rule(
        "missed_payment_or_failed_debit",
        MISSED,
        r"\bmiss(?:ed)?\b.{0,30}\b(?:sips?|payments?|instal\w*)\b"
        r"|\b(?:sips?|payments?|instal\w*)\b.{0,30}\bmiss(?:ed)?\b"
        r"|\bmissing\b(?! the\b).{0,25}\b(?:sips?|payments?|instal\w*)\b"
        r"|\b(?:payment|autopay|auto-pay)\b.{0,30}\b(?:fail\w*|failed|not deducted)\b"
        r"|\bnot deducted\b",
    ),
    _rule(
        "explicit_financial_constraint",
        FINANCIAL,
        r"\bcan(?:not|'t) afford\b|\bunable to continue\b|\bno money\b"
        r"|\bdon'?t have (?:the )?money\b|\bfinancial (?:problem|issue|difficult\w*)\b",
    ),
)


def exact_excerpt(text: str, pattern: re.Pattern[str]) -> str:
    """Return the original slice that matched. It is not a paraphrase."""
    match = pattern.search(text)
    if match is None:
        return ""
    start = text.rfind("\n", 0, match.start())
    end_newline = text.find("\n", match.end())
    left = start + 1
    right = end_newline if end_newline != -1 else len(text)
    excerpt = text[left:right].strip()
    if excerpt and excerpt in text:
        return excerpt
    return text[match.start():match.end()]


def screen_comment(text: str) -> dict[str, str] | None:
    """Find keyword leads in one comment.

    A question about stopping, or advice such as "never stop your SIP",
    is not labelled as first-person discontinuation. A missed payment is
    not labelled as discontinuation unless the comment also says the
    writer stopped or discontinued the SIP.
    """
    if not text or not text.strip():
        return None
    matches: list[tuple[str, str, str]] = []
    for rule in RULES:
        if rule.pattern.search(text):
            matches.append((rule.name, rule.category, exact_excerpt(text, rule.pattern)))
    if not matches:
        return None

    names = {name for name, _, _ in matches}
    categories = {category for _, category, _ in matches}
    question_or_advice = bool(
        names & {"advice_not_personal_experience", "question_about_stopping"}
    )
    if ACTUAL in categories:
        category = ACTUAL
    elif INTENTION in categories:
        category = INTENTION
    elif question_or_advice:
        category = EDUCATION
    else:
        category = next(item for item in CATEGORY_PRIORITY if item in categories)

    quote = ""
    for name, matched_category, excerpt in matches:
        if matched_category == category and excerpt:
            quote = excerpt
            break
    if not quote:
        quote = next(excerpt for _, _, excerpt in matches if excerpt)

    return {
        "possible_evidence_category": category,
        "keyword_matches": " | ".join(name for name, _, _ in matches),
        "evidence_quote": quote,
        "manual_verification_required": "true",
    }


def load_master(path: Path = MASTER_PATH) -> list[dict[str, str]]:
    """Read the combined comments. The master file is not changed."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Could not find {path}. Run python -m src.consolidate_youtube_batches first."
        )
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in SOURCE_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Master file is missing columns: {', '.join(missing)}")
        return [dict(row) for row in reader]


def audit_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep only comments with at least one keyword lead."""
    leads = []
    for row in rows:
        screen = screen_comment(row.get("comment_text", ""))
        if screen is None:
            continue
        lead = {column: row.get(column, "") for column in SOURCE_COLUMNS}
        lead.update(screen)
        if lead["evidence_quote"] and lead["evidence_quote"] not in lead["comment_text"]:
            raise ValueError("Evidence quote is not an exact part of the original comment.")
        leads.append(lead)
    return leads


def write_audit_csv(leads: list[dict[str, str]], path: Path = AUDIT_CSV_PATH) -> None:
    """Write the candidate sheet. Every data row still needs a person to check it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_COLUMNS)
        writer.writeheader()
        for lead in leads:
            writer.writerow({column: lead.get(column, "") for column in AUDIT_COLUMNS})


def build_audit_report(screened_count: int, leads: list[dict[str, str]]) -> str:
    """Explain the screen. Counts are keyword hits, not confirmed behaviour."""
    counts = Counter(lead["possible_evidence_category"] for lead in leads)
    lines = [
        "# YouTube evidence audit",
        "",
        "Keyword matches are leads for human review. They are not confirmed investor experiences.",
        "",
        "A question about stopping a SIP is not evidence that the author stopped one. Advice such as \"never stop your SIP\" is not personal experience. A missed payment is not labelled as discontinuation unless the comment also says the writer stopped or discontinued the SIP. This screen does not decide that someone is a first-time investor, and it does not invent a reason that the words do not state.",
        "",
        f"- Comments screened: {screened_count}",
        f"- Comments with at least one keyword lead: {len(leads)}",
        f"- Comments with no keyword lead: {screened_count - len(leads)}",
        "",
        "Every lead has `manual_verification_required` set to `true`. `possible_evidence_category` is the keyword bucket, not a final label. `evidence_quote` is a slice of the original comment.",
        "",
        "## Leads by possible category",
        "",
        "| Possible category | Comments |",
        "| --- | ---: |",
    ]
    for category in CATEGORY_PRIORITY:
        lines.append(f"| `{category}` | {counts.get(category, 0)} |")
    lines.extend(
        [
            "",
            "## How a comment is bucketed",
            "",
            "- `first_person_actual_discontinuation`: the text matches a first-person \"I stopped\" or \"I discontinued\" SIP pattern.",
            "- `intention_to_stop`: the text matches wanting or planning to stop, and it does not match the stop-already pattern.",
            "- `temporary_pause`: the text matches a first-person pause.",
            "- `sip_cancellation`: the text matches a first-person cancellation.",
            "- `missed_payment`: the text matches a missed instalment, missed payment, or a failed debit, and it does not match a stronger pattern above.",
            "- `financial_difficulty`: the text contains an explicit money-problem phrase, and it does not match a stronger pattern above.",
            "- `general_educational_discussion`: the text is advice not to stop, or a question about stopping, pausing, or cancelling, and it does not also match a first-person \"I stopped\" or \"I discontinued\" pattern.",
            "",
            "If a comment matches more than one keyword, `keyword_matches` lists each hit. The category is only the first bucket that the rules above allow. A second keyword is not a finding that one thing caused another.",
            "",
            "## What this audit does not do",
            "",
            "- It does not call an AI model.",
            "- It does not treat the video title as proof about the commenter.",
            "- It does not count a comment as a personal discontinuation because the video was found with a search about stopping.",
            "- Comments with no keyword hit are left out of `youtube_evidence_audit.csv`. Absence from that file is not proof that the comment has no useful meaning.",
            "",
        ]
    )
    return "\n".join(lines)


def write_audit_report(screened_count: int, leads: list[dict[str, str]], path: Path = AUDIT_MD_PATH) -> None:
    """Write the short explanation that must be read with the CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_audit_report(screened_count, leads), encoding="utf-8")


def main() -> None:
    """Screen the master comments and write the audit files."""
    try:
        rows = load_master()
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    leads = audit_rows(rows)
    write_audit_csv(leads)
    write_audit_report(len(rows), leads)
    print(f"Comments screened: {len(rows)}")
    print(f"Keyword leads: {len(leads)}")
    print(f"Wrote {AUDIT_CSV_PATH}")
    print(f"Wrote {AUDIT_MD_PATH}")
    print("These leads are not confirmed experiences.")


if __name__ == "__main__":
    main()
