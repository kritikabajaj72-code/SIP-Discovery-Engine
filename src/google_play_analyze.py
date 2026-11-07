"""Keyword labels and reports for the Google Play reviews.

A keyword hit is a research lead. It does not show that a person stopped
a SIP, and it does not show that one app is better than another.
"""

from __future__ import annotations

import re
from collections import Counter

from src.google_play_clean import CLEAN_COLUMNS


DIRECT = "direct"
INDIRECT = "indirect"
NOT_RELEVANT = "not_relevant"

SIP_PAYMENT = "sip_payment_failure"
MISSED = "missed_instalment"
PAUSE_OR_CANCEL = "sip_pause_or_cancellation"
AMOUNT_OR_DATE = "sip_amount_or_date_change"
SETUP = "sip_setup_and_registration"
REDEMPTION = "redemption_or_withdrawal"
CRASH = "app_crash_or_technical"
KYC = "kyc_or_onboarding"
FUND_CHOICE = "fund_selection_or_discovery"
RETURNS = "returns_losses_or_dissatisfaction"
FINANCIAL = "financial_constraints"
NO_PROBLEM = "none"

# Earlier items win the single category. matched_keywords still lists every hit.
PROBLEM_RULES = (
    (SIP_PAYMENT, re.compile(
        r"\b(?:payment|autopay|auto-pay|mandate|upi)\b.{0,40}\b(?:fail\w*|failed|not deducted|error)\b"
        r"|\b(?:fail\w*|failed) (?:the )?payment\b|\bunable to (?:do |make |pay )?sip payment\b"
        r"|\bnot deducted\b|\bpayment fails\b",
        re.IGNORECASE,
    )),
    (MISSED, re.compile(
        r"\bmiss(?:ed)?\b.{0,30}\b(?:sips?|payments?|instal\w*)\b"
        r"|\b(?:sips?|payments?|instal\w*)\b.{0,30}\bmiss(?:ed)?\b",
        re.IGNORECASE,
    )),
    (PAUSE_OR_CANCEL, re.compile(
        r"\b(?:paus\w*|cancell?|cancel|stop)\w*\b.{0,30}\bsips?\b"
        r"|\bsips?\b.{0,30}\b(?:paus\w*|cancell?|cancel|stop)\w*\b",
        re.IGNORECASE,
    )),
    (AMOUNT_OR_DATE, re.compile(
        r"\b(?:change|modify|edit|increase|decrease|reduc\w*|step[- ]?up)\b.{0,40}\bsips?\b.{0,20}\b(?:amount|date)?\b"
        r"|\bsip (?:amount|date)\b",
        re.IGNORECASE,
    )),
    (SETUP, re.compile(
        r"\b(?:start|create|set ?up|register|begin)\b.{0,30}\bsips?\b|\bsip (?:setup|registration|mandate)\b",
        re.IGNORECASE,
    )),
    (REDEMPTION, re.compile(r"\b(?:redeem\w*|withdraw\w*|withdrawal)\b", re.IGNORECASE)),
    (KYC, re.compile(r"\b(?:kyc|onboarding|pan card|account opening)\b", re.IGNORECASE)),
    (CRASH, re.compile(
        r"\b(?:crash\w*|not working|does not work|doesn't work|bug|glitch|unable to open|app (?:is )?down)\b",
        re.IGNORECASE,
    )),
    (FUND_CHOICE, re.compile(
        r"\b(?:which fund|find (?:a |the )?fund|search (?:for )?fund|fund (?:selection|discovery))\b",
        re.IGNORECASE,
    )),
    (RETURNS, re.compile(
        r"\b(?:returns?|losses|loss|xirr|disappoint\w*)\b",
        re.IGNORECASE,
    )),
    (FINANCIAL, re.compile(
        r"\bcan(?:not|'t) afford\b|\bno money\b|\bunable to continue\b|\bdon'?t have (?:the )?money\b",
        re.IGNORECASE,
    )),
)

SIP_WORD = re.compile(r"\bsips?\b|systematic investment plan", re.IGNORECASE)
INDIRECT_WORD = re.compile(
    r"\b(?:mutual funds?|nav|portfolio|kyc|redeem\w*|withdraw\w*|mandate|investment)\b",
    re.IGNORECASE,
)

ANALYSIS_COLUMNS = CLEAN_COLUMNS + (
    "sip_relevance",
    "possible_problem_category",
    "matched_keywords",
    "manual_verification_required",
)


def classify_review(text: str) -> dict[str, str]:
    """Label one review from its own words. Titles and apps are not used."""
    hits = [name for name, pattern in PROBLEM_RULES if pattern.search(text or "")]
    if SIP_WORD.search(text or ""):
        relevance = DIRECT
    elif INDIRECT_WORD.search(text or "") or hits:
        relevance = INDIRECT
    else:
        relevance = NOT_RELEVANT
    category = hits[0] if hits else NO_PROBLEM
    needs_review = relevance != NOT_RELEVANT or category != NO_PROBLEM
    return {
        "sip_relevance": relevance,
        "possible_problem_category": category,
        "matched_keywords": " | ".join(hits),
        "manual_verification_required": "true" if needs_review else "false",
    }


def annotate_reviews(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Copy each cleaned review and add the keyword columns."""
    annotated = []
    for row in rows:
        labelled = dict(row)
        labelled.update(classify_review(row.get("review_text", "")))
        annotated.append(labelled)
    return annotated


def evidence_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Reviews a person should read. Irrelevant reviews with no keyword stay out."""
    return [row for row in rows if row.get("manual_verification_required") == "true"]


def category_counts(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Count primary problem categories by app. none is included so totals add up."""
    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        counts[(row.get("app_name", ""), row.get("possible_problem_category", NO_PROBLEM))] += 1
    table = []
    for (app_name, category), count in sorted(counts.items()):
        table.append(
            {
                "app_name": app_name,
                "possible_problem_category": category,
                "review_count": str(count),
            }
        )
    return table


def _rating_number(value: str) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    if number < 1 or number > 5:
        return None
    return number


def rating_band(value: str) -> str:
    """Use the star rating only. The words in the review do not set this band."""
    number = _rating_number(value)
    if number is None:
        return "unrated"
    if number <= 2:
        return "negative"
    if number == 3:
        return "neutral"
    return "positive"


def _count_rows(rows: list[dict[str, str]], predicate) -> int:
    return sum(1 for row in rows if predicate(row))


def build_quality_report(clean_result: dict, annotated: list[dict[str, str]]) -> str:
    """Describe completeness. This is not a finding about investors."""
    lines = [
        "# Google Play review quality report",
        "",
        "This file describes the unfiltered English-language sample collected from Google Play for India. It is not a representative sample of Indian investors.",
        "",
        f"- Rows read from the unfiltered file: {clean_result['rows_read']}",
        f"- Rows kept after review-id deduplication: {len(annotated)}",
        f"- Duplicate review ids removed: {len(clean_result['duplicate_ids'])}",
        f"- Rows skipped because the review id was missing: {clean_result['missing_ids']}",
        f"- Empty review text: {_count_rows(annotated, lambda row: row.get('empty_review') == 'true')}",
        f"- Missing rating: {_count_rows(annotated, lambda row: row.get('rating_missing') == 'true')}",
        f"- Missing date: {_count_rows(annotated, lambda row: row.get('date_missing') == 'true')}",
        "",
        "Original review text is unchanged. YouTube comments are not part of this file.",
        "",
        "A keyword label in the master file is a lead for manual reading. It does not establish that a SIP was discontinued.",
        "",
    ]
    return "\n".join(lines)


def build_comparative_report(rows: list[dict[str, str]]) -> str:
    """Compare the three apps with counts only."""
    app_names = [row.get("app_name", "") for row in rows]
    apps = []
    for name in ("Groww", "Zerodha Coin", "INDmoney"):
        if name in app_names or True:
            apps.append(name)
    lines = [
        "# Google Play comparative notes",
        "",
        "These counts describe this English-language, India-store sample of newest reviews. They do not show which app is better, and they do not show that a keyword caused a SIP to stop.",
        "",
        "Limits of the sample:",
        "",
        "- At most 500 newest reviews were requested for each app. An app can have fewer.",
        "- Only the English language and the India store listing were requested.",
        "- People who do not write a Play review are not in the file.",
        "- A different number of reviews per app means the samples are not the same size.",
        "",
        "## Reviews collected",
        "",
        "| App | Reviews |",
        "| --- | ---: |",
    ]
    by_app: dict[str, list[dict[str, str]]] = {name: [] for name in apps}
    for row in rows:
        by_app.setdefault(row.get("app_name", ""), []).append(row)
    for name in apps:
        lines.append(f"| {name} | {len(by_app.get(name, []))} |")

    lines.extend(["", "## Rating distribution", "", "Stars are stored as collected. A missing rating is unrated, not guessed.", ""])
    lines.append("| App | 1 | 2 | 3 | 4 | 5 | Unrated |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name in apps:
        group = by_app.get(name, [])
        stars = []
        for score in range(1, 6):
            stars.append(str(_count_rows(group, lambda row, score=score: _rating_number(row.get("rating", "")) == score)))
        unrated = _count_rows(group, lambda row: rating_band(row.get("rating", "")) == "unrated")
        lines.append(f"| {name} | " + " | ".join(stars) + f" | {unrated} |")

    lines.extend(["", "## Rating bands", "", "Negative means 1 or 2 stars. Neutral means 3. Positive means 4 or 5. This uses the rating only.", ""])
    lines.append("| App | Negative | Neutral | Positive | Unrated |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for name in apps:
        group = by_app.get(name, [])
        lines.append(
            "| {name} | {neg} | {neu} | {pos} | {unrated} |".format(
                name=name,
                neg=_count_rows(group, lambda row: rating_band(row.get("rating", "")) == "negative"),
                neu=_count_rows(group, lambda row: rating_band(row.get("rating", "")) == "neutral"),
                pos=_count_rows(group, lambda row: rating_band(row.get("rating", "")) == "positive"),
                unrated=_count_rows(group, lambda row: rating_band(row.get("rating", "")) == "unrated"),
            )
        )

    lines.extend(["", "## SIP relevance", "", "Direct means the review text contains SIP or “systematic investment plan”. Indirect means another investment word or a problem keyword, without that SIP phrase. This is not proof of a personal SIP.", ""])
    lines.append("| App | Direct | Indirect | Not relevant |")
    lines.append("| --- | ---: | ---: | ---: |")
    for name in apps:
        group = by_app.get(name, [])
        lines.append(
            f"| {name} | "
            f"{_count_rows(group, lambda row: row.get('sip_relevance') == DIRECT)} | "
            f"{_count_rows(group, lambda row: row.get('sip_relevance') == INDIRECT)} | "
            f"{_count_rows(group, lambda row: row.get('sip_relevance') == NOT_RELEVANT)} |"
        )

    lines.extend(
        [
            "",
            "## Problem-category leads",
            "",
            "Each review has one primary category, chosen by a fixed rule order. A payment-failure lead does not prove the writer discontinued a SIP. A cancellation word does not prove a cancellation happened. A feature complaint does not prove the writer is a first-time investor. Financial circumstances are counted only when the review states them.",
            "",
            "| App | Category | Reviews |",
            "| --- | --- | ---: |",
        ]
    )
    for item in category_counts(rows):
        if item["app_name"] in apps:
            lines.append(
                f"| {item['app_name']} | `{item['possible_problem_category']}` | {item['review_count']} |"
            )

    focus = (
        ("Payment-related leads", SIP_PAYMENT),
        ("Missed-instalment leads", MISSED),
        ("Pause or cancellation wording", PAUSE_OR_CANCEL),
        ("SIP amount or date wording", AMOUNT_OR_DATE),
        ("Usability or technical leads", CRASH),
        ("KYC or onboarding leads", KYC),
    )
    lines.extend(["", "## Selected lead groups", ""])
    lines.append("| Lead group | " + " | ".join(apps) + " |")
    lines.append("| --- | " + " | ".join("---:" for _ in apps) + " |")
    for label, category in focus:
        cells = []
        for name in apps:
            group = by_app.get(name, [])
            cells.append(str(_count_rows(group, lambda row, category=category: row.get("possible_problem_category") == category)))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "Different review counts are a sampling limit. A larger count is not by itself a worse app, and a smaller count is not by itself a better app.",
            "",
        ]
    )
    return "\n".join(lines)
