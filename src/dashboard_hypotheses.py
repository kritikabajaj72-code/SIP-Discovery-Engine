"""Four research hypotheses and the keyword counts that relate to each one.

A hypothesis stays UNVALIDATED. Keyword totals are observations to read,
not a cause of SIP discontinuation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.dashboard_data import label_play_category, resolve_column, youtube_lead_counts


UNVALIDATED = "UNVALIDATED"


@dataclass
class HypothesisCard:
    """One hypothesis prepared for the dashboard."""

    title: str
    summary: str
    observations: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    lead_counts: list[tuple[str, int]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    status: str = UNVALIDATED


def _play_counts(frame: pd.DataFrame, codes: tuple[str, ...]) -> list[tuple[str, int, str]]:
    """Return (label, total, per-app sentence) for each requested category."""
    results = []
    app_column = None if frame is None else resolve_column(frame, "app_name")
    category_column = None if frame is None else resolve_column(frame, "possible_problem_category")
    for code in codes:
        label = label_play_category(code)
        if frame is None or category_column is None:
            results.append((label, 0, "The review file has no problem-category column."))
            continue
        matched = frame[frame[category_column].astype(str) == code]
        total = len(matched.index)
        if app_column is None or matched.empty:
            detail = "No app split is available." if app_column is None else "No reviews carry this primary label."
        else:
            parts = [
                f"{app_name} {int(count)}"
                for app_name, count in matched[app_column].value_counts().items()
            ]
            detail = ", ".join(parts)
        results.append((label, total, detail))
    return results


def _youtube_count(leads: pd.DataFrame, code: str) -> int:
    if leads is None or leads.empty or "category_code" not in leads.columns:
        return 0
    matched = leads.loc[leads["category_code"] == code, "comments"]
    if matched.empty:
        return 0
    return int(matched.iloc[0])


def build_hypotheses(play: pd.DataFrame, youtube_leads: pd.DataFrame) -> list[HypothesisCard]:
    """Build the four cards from the current Play reviews and YouTube lead rows."""
    lead_table = youtube_lead_counts(youtube_leads)
    payment = _play_counts(play, ("sip_payment_failure", "missed_instalment"))
    financial_play = _play_counts(play, ("financial_constraints",))
    returns = _play_counts(play, ("returns_losses_or_dissatisfaction",))
    management = _play_counts(
        play,
        ("sip_pause_or_cancellation", "sip_amount_or_date_change", "sip_setup_and_registration"),
    )
    missed_payment = _youtube_count(lead_table, "missed_payment")
    financial_comment = _youtube_count(lead_table, "financial_difficulty")
    intention = _youtube_count(lead_table, "intention_to_stop")
    cancellation = _youtube_count(lead_table, "sip_cancellation")
    pause = _youtube_count(lead_table, "temporary_pause")
    stopped_wording = _youtube_count(lead_table, "first_person_actual_discontinuation")

    return [
        HypothesisCard(
            title="1. Payment and operational friction",
            summary=(
                "Asks whether failed deductions, missed instalments, or mandate trouble "
                "appear in the collected feedback."
            ),
            observations=[
                f"Google Play primary label '{payment[0][0]}': {payment[0][1]} reviews ({payment[0][2]}).",
                f"Google Play primary label '{payment[1][0]}': {payment[1][1]} reviews ({payment[1][2]}).",
                f"YouTube keyword lead 'Missed payment': {missed_payment} comments.",
            ],
            sources=["Google Play review master", "YouTube keyword audit"],
            lead_counts=[
                (payment[0][0], payment[0][1]),
                (payment[1][0], payment[1][1]),
                ("YouTube missed-payment wording", missed_payment),
            ],
            limitations=[
                "A payment-failure phrase does not show that the person discontinued a SIP.",
                "A missed-payment phrase is not the same as a decision to stop.",
                "YouTube comments are not labelled with an app, so they are not Groww evidence by themselves.",
                "Google Play and YouTube are separate populations.",
            ],
        ),
        HypothesisCard(
            title="2. Financial affordability",
            summary=(
                "Asks whether people say a fixed monthly SIP became hard to afford. "
                "This sample has very little explicit wording of that kind."
            ),
            observations=[
                f"Google Play primary label '{financial_play[0][0]}': {financial_play[0][1]} reviews ({financial_play[0][2]}).",
                f"YouTube keyword lead 'Explicit financial difficulty': {financial_comment} comments.",
                f"YouTube keyword lead 'Intention to stop': {intention} comments.",
            ],
            sources=["Google Play review master", "YouTube keyword audit"],
            lead_counts=[
                (financial_play[0][0], financial_play[0][1]),
                ("YouTube explicit financial difficulty", financial_comment),
                ("YouTube intention-to-stop wording", intention),
            ],
            limitations=[
                "The rules do not infer income, expenses, or affordability from a general complaint.",
                "An intention phrase would still not prove that the person later stopped.",
                "These counts are too small to treat affordability as a demonstrated cause.",
            ],
        ),
        HypothesisCard(
            title="3. Investment disappointment",
            summary=(
                "Asks whether return, loss, or dissatisfaction wording shows an expectation gap. "
                "The YouTube audit has no separate returns category."
            ),
            observations=[
                f"Google Play primary label '{returns[0][0]}': {returns[0][1]} reviews ({returns[0][2]}).",
                "YouTube keyword audit: no returns or dissatisfaction category was defined, so none is counted here.",
            ],
            sources=["Google Play review master"],
            lead_counts=[(returns[0][0], returns[0][1])],
            limitations=[
                "The words return or loss do not show that the reviewer stopped a SIP.",
                "A low star rating is the reviewer's rating, not a measured fund return.",
                "Educational comments about markets are not personal disappointment.",
            ],
        ),
        HypothesisCard(
            title="4. SIP management friction",
            summary=(
                "Asks whether people describe trouble changing, pausing, cancelling, or setting up a SIP."
            ),
            observations=[
                f"Google Play primary label '{management[0][0]}': {management[0][1]} reviews ({management[0][2]}).",
                f"Google Play primary label '{management[1][0]}': {management[1][1]} reviews ({management[1][2]}).",
                f"Google Play primary label '{management[2][0]}': {management[2][1]} reviews ({management[2][2]}).",
                f"YouTube keyword lead 'First-person cancellation wording': {cancellation} comments.",
                f"YouTube keyword lead 'Temporary pause': {pause} comments.",
                (
                    "YouTube keyword lead 'First-person stopped/discontinued wording': "
                    f"{stopped_wording} comments. These are wording matches, not confirmed stops."
                ),
            ],
            sources=["Google Play review master", "YouTube keyword audit"],
            lead_counts=[
                (management[0][0], management[0][1]),
                (management[1][0], management[1][1]),
                (management[2][0], management[2][1]),
                ("YouTube cancellation wording", cancellation),
                ("YouTube temporary-pause wording", pause),
                ("YouTube stopped/discontinued wording", stopped_wording),
            ],
            limitations=[
                "A request to cancel or pause does not show that the action was completed.",
                "Stopped/discontinued wording still needs a person to read the comment.",
                "No row in these files is marked as manually verified.",
            ],
        ),
    ]
