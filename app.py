"""SIP Discovery research dashboard.

Run from the project folder:

    streamlit run app.py

The app reads processed research files and does not collect new data.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard_charts import (
    batch_chart,
    problem_category_chart,
    rating_band_chart,
    rating_distribution_chart,
    review_volume_chart,
    sip_relevance_chart,
    source_distribution_chart,
    youtube_lead_chart,
)
from src.dashboard_data import (
    app_summary,
    batch_counts,
    category_counts_from_reviews,
    category_file_matches_master,
    filter_apps,
    filter_by_value,
    filter_search,
    label_play_category,
    label_youtube_category,
    load_research,
    ordered_apps,
    overview_counts,
    play_category_options,
    resolve_column,
    source_record_counts,
    split_findings,
    youtube_lead_counts,
)
from src.dashboard_hypotheses import build_hypotheses


TABLE_PREVIEW_ROWS = 200

st.set_page_config(
    page_title="SIP Discovery Engine",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    """Draw the dashboard from the local research files."""
    _style()
    bundle = load_research()
    counts = overview_counts(bundle)
    play = bundle.frame("play_master")
    youtube = bundle.frame("youtube_master")
    leads = bundle.frame("youtube_audit")

    _header()
    _integrity_banner()
    for message in bundle.messages():
        st.warning(message)

    apps = ordered_apps(play)
    with st.sidebar:
        st.header("Filters")
        st.caption("Filters change tables and the app charts. Hypothesis counts stay on the full files.")
        selected_apps = st.multiselect("Apps", options=apps, default=apps)
        play_categories = play_category_options(play)
        selected_play_category = st.selectbox(
            "Google Play problem category",
            options=["All"] + play_categories,
            format_func=lambda value: "All categories" if value == "All" else label_play_category(value),
        )
        lead_table = youtube_lead_counts(leads)
        selected_youtube_category = st.selectbox(
            "YouTube keyword-lead category",
            options=["All"] + lead_table["category_code"].tolist(),
            format_func=lambda value: "All lead categories" if value == "All" else label_youtube_category(value),
        )
        search = st.text_input("Search reviews and comments", placeholder="Type a word from the original text")
        source = st.radio(
            "Download source",
            options=["Google Play reviews", "YouTube comments", "YouTube keyword leads"],
        )
        st.divider()
        st.caption("Counts are calculated when the app loads. No external API is called.")

    filtered_play = filter_search(
        filter_by_value(filter_apps(play, selected_apps), "possible_problem_category", selected_play_category),
        ("review_text",),
        search,
    )
    app_scoped_play = filter_apps(play, selected_apps)
    filtered_comments = filter_search(youtube, ("comment_text", "video_title"), search)
    filtered_leads = filter_search(
        filter_by_value(leads, "possible_evidence_category", selected_youtube_category),
        ("comment_text", "video_title"),
        search,
    )

    overview_tab, apps_tab, youtube_tab, hypothesis_tab, findings_tab, explorer_tab = st.tabs(
        [
            "Research overview",
            "App comparison",
            "YouTube feedback",
            "Problem discovery",
            "Research findings",
            "Evidence explorer",
        ]
    )

    with overview_tab:
        _overview(counts, bundle)
    with apps_tab:
        _apps(app_scoped_play, selected_play_category, filtered_play)
    with youtube_tab:
        _youtube(youtube, leads, filtered_leads)
    with hypothesis_tab:
        _hypotheses(play, leads)
    with findings_tab:
        _findings(bundle)
    with explorer_tab:
        _explorer(source, filtered_play, filtered_comments, filtered_leads)


def _style() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1180px;}
        h1 {letter-spacing: 0.04em; font-weight: 700; margin-bottom: 0;}
        .subtitle {color: #5C6B7A; font-size: 1.05rem; margin-top: 0.15rem;}
        .banner {
            background: #F3F7F8;
            border-left: 4px solid #0F6E6E;
            padding: 12px 16px;
            border-radius: 8px;
            margin: 12px 0 18px 0;
            color: #122033;
        }
        .kpi {
            background: #FFFFFF;
            border: 1px solid #E3E8EE;
            border-radius: 12px;
            padding: 14px 16px 12px 16px;
            min-height: 132px;
        }
        .kpi .label {color: #5C6B7A; font-size: 0.82rem;}
        .kpi .value {color: #122033; font-size: 1.85rem; font-weight: 700; margin: 4px 0;}
        .kpi .note {color: #5C6B7A; font-size: 0.78rem; line-height: 1.35;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _header() -> None:
    st.markdown("# SIP DISCOVERY ENGINE")
    st.markdown("### AI-Powered Investor Feedback Research")
    st.markdown(
        "<p class='subtitle'>Secondary Research | Groww | India | November 2026</p>",
        unsafe_allow_html=True,
    )


def _integrity_banner() -> None:
    st.markdown(
        """
        <div class="banner">
        <strong>How to read the numbers.</strong>
        Observed counts are rows in the collected files.
        Keyword matches are rules applied to those words. They are leads for a person to read.
        Manually verified evidence is not recorded in these files.
        The four hypotheses are unvalidated. Nothing on this page is a confirmed cause,
        a confirmed discontinuation, or a sample of first-time investors.
        Google Play reviews and YouTube comments are two separate populations.
        </div>
        """,
        unsafe_allow_html=True,
    )


def _kpi(label: str, value: int, note: str) -> str:
    return (
        "<div class='kpi'>"
        f"<div class='label'>{label}</div>"
        f"<div class='value'>{value:,}</div>"
        f"<div class='note'>{note}</div>"
        "</div>"
    )


def _overview(counts, bundle) -> None:
    st.subheader("Research overview")
    st.caption("The product selected for this assignment is Groww. Zerodha Coin and INDmoney are comparison sources.")
    cards = [
        ("Google Play reviews", counts.play_reviews, "Observed rows in the review master. Not a representative sample."),
        ("YouTube comments", counts.youtube_comments, "Observed top-level comments. A separate population from Play reviews."),
        ("Apps analysed", counts.apps, "Distinct app names in the Play review master."),
        ("YouTube videos", counts.youtube_videos, "Distinct videos that have at least one saved comment."),
        ("YouTube keyword leads", counts.youtube_keyword_leads, "Keyword matches. Not confirmed discontinuations."),
        (
            "Play SIP-relevance leads",
            counts.play_sip_relevance_leads,
            f"Direct {counts.play_direct:,} plus indirect {counts.play_indirect:,}. Not confirmed discontinuations.",
        ),
    ]
    for start in (0, 3):
        columns = st.columns(3)
        for column, card in zip(columns, cards[start:start + 3]):
            column.markdown(_kpi(*card), unsafe_allow_html=True)
    st.plotly_chart(source_distribution_chart(source_record_counts(counts)), use_container_width=True)
    st.info(
        "Google Play reviews are comments on a named app. YouTube comments are discussion under videos. "
        "Do not add these records together and treat the sum as one investor population. "
        f"YouTube channels represented: {counts.youtube_channels:,}."
    )
    st.caption(category_file_matches_master(bundle))


def _apps(app_scoped_play: pd.DataFrame, selected_category: str, filtered_play: pd.DataFrame) -> None:
    st.subheader("App comparison")
    st.caption(
        "These charts use the selected apps and the full review text for those apps. "
        "They do not rank an app as better or worse. A larger complaint count is not a quality score."
    )
    summary = app_summary(app_scoped_play)
    if not summary.empty:
        band_total = int(summary[["negative", "neutral", "positive", "unrated"]].sum().sum())
        relevance_total = int(summary[["direct", "indirect", "not_relevant", "relevance_unlabelled"]].sum().sum())
        st.caption(
            f"Selected reviews: {int(summary['reviews'].sum()):,}. "
            f"Rating bands sum to {band_total:,}. SIP-relevance labels sum to {relevance_total:,}."
        )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(review_volume_chart(summary), use_container_width=True)
    with right:
        st.plotly_chart(rating_band_chart(summary), use_container_width=True)
    st.plotly_chart(rating_distribution_chart(app_scoped_play), use_container_width=True)
    st.plotly_chart(sip_relevance_chart(summary), use_container_width=True)
    include_none = st.checkbox("Include reviews with no problem keyword in the category chart", value=False)
    category_frame = category_counts_from_reviews(app_scoped_play)
    if selected_category != "All":
        category_frame = category_frame[category_frame["possible_problem_category"] == selected_category]
    st.plotly_chart(
        problem_category_chart(category_frame, include_none or selected_category == "none"),
        use_container_width=True,
    )
    st.markdown("**Reviews in the current Play filter**")
    st.caption("The table uses the app, problem-category, and search filters. The charts above use the app filter only.")
    _show_table(_play_preview(filtered_play), "No Play reviews match these filters.")
    _download(filtered_play, "google_play_reviews_filtered.csv", "play-download")


def _youtube(youtube: pd.DataFrame, leads: pd.DataFrame, filtered_leads: pd.DataFrame) -> None:
    st.subheader("YouTube investor feedback")
    video_column = resolve_column(youtube, "video_id")
    channel_column = resolve_column(youtube, "channel")
    videos = 0 if video_column is None else youtube[video_column].replace("", pd.NA).nunique(dropna=True)
    channels = 0 if channel_column is None else youtube[channel_column].replace("", pd.NA).nunique(dropna=True)
    metric_columns = st.columns(3)
    metric_columns[0].metric("Comments", f"{len(youtube.index):,}")
    metric_columns[1].metric("Videos represented", f"{int(videos):,}")
    metric_columns[2].metric("Channels represented", f"{int(channels):,}")
    st.caption(
        "Lead counts include a zero when a category has no keyword match. "
        "A stopped/discontinued match is wording, not a confirmed stop. "
        "Missed-payment matches are not counted again as discontinuation."
    )
    lead_table = youtube_lead_counts(leads)
    st.plotly_chart(youtube_lead_chart(lead_table), use_container_width=True)
    st.dataframe(lead_table[["category", "comments"]], use_container_width=True, hide_index=True)
    st.plotly_chart(batch_chart(batch_counts(youtube)), use_container_width=True)
    st.markdown("**Candidate comments**")
    st.caption("Every row below is a keyword lead. Verification status is the stored flag, which asks for a human reading.")
    _show_table(_lead_preview(filtered_leads), "No keyword leads match the YouTube category filter and search.")
    _download(filtered_leads, "youtube_keyword_leads_filtered.csv", "youtube-lead-download")


def _hypotheses(play: pd.DataFrame, leads: pd.DataFrame) -> None:
    st.subheader("SIP problem discovery")
    st.caption("Each card is a question for later research. The status stays UNVALIDATED.")
    for card in build_hypotheses(play, leads):
        with st.expander(f"{card.title} — {card.status}"):
            st.write(card.summary)
            st.markdown("**Supporting observations**")
            for observation in card.observations:
                st.markdown(f"- {observation}")
            st.markdown("**Relevant sources:** " + "; ".join(card.sources))
            st.markdown("**Keyword leads**")
            st.dataframe(
                pd.DataFrame(card.lead_counts, columns=["Lead", "Count"]),
                use_container_width=True,
                hide_index=True,
            )
            st.markdown("**Evidence limitations**")
            for limitation in card.limitations:
                st.markdown(f"- {limitation}")
            st.markdown(f"**Validation status:** {card.status}")


def _findings(bundle) -> None:
    st.subheader("Research findings")
    st.caption("This is the saved write-up. Interview questions are proposed. No interview answers are included.")
    blocks = split_findings(bundle.text("findings"))
    if not blocks:
        st.info("The findings file is missing or empty.")
        return
    for title, body in blocks:
        with st.expander(title, expanded=(title == "Research objective")):
            st.markdown(body)
    with st.expander("Google Play written notes"):
        comparative = bundle.text("play_comparative")
        quality = bundle.text("play_quality")
        st.markdown(comparative or "The comparative note is missing.")
        st.markdown(quality or "The Play quality note is missing.")
    with st.expander("YouTube written notes"):
        st.markdown(bundle.text("youtube_quality") or "The YouTube quality note is missing.")
        st.markdown(bundle.text("youtube_audit_note") or "The YouTube audit note is missing.")


def _explorer(source: str, play: pd.DataFrame, comments: pd.DataFrame, leads: pd.DataFrame) -> None:
    st.subheader("Evidence explorer")
    st.caption("Download contains every filtered row, not only the preview.")
    if source == "Google Play reviews":
        frame = play
        preview = _play_preview(play)
        filename = "google_play_reviews_filtered.csv"
        empty = "No Play reviews match the sidebar filters."
    elif source == "YouTube comments":
        frame = comments
        preview = _comment_preview(comments)
        filename = "youtube_comments_filtered.csv"
        empty = "No YouTube comments match the search."
    else:
        frame = leads
        preview = _lead_preview(leads)
        filename = "youtube_keyword_leads_filtered.csv"
        empty = "No YouTube keyword leads match the sidebar filters."
    st.caption(f"Filtered rows: {len(frame.index):,}.")
    _show_table(preview, empty)
    _download(frame, filename, "explorer-download")


def _play_preview(frame: pd.DataFrame) -> pd.DataFrame:
    return _select_columns(
        frame,
        [
            ("app_name", "App"),
            ("rating", "Rating"),
            ("sip_relevance", "SIP relevance"),
            ("possible_problem_category", "Problem category"),
            ("review_text", "Review text"),
            ("manual_verification_required", "Manual verification required"),
            ("source_id", "Source id"),
        ],
    )


def _comment_preview(frame: pd.DataFrame) -> pd.DataFrame:
    return _select_columns(
        frame,
        [
            ("video_title", "Video title"),
            ("channel", "Channel"),
            ("comment_text", "Comment text"),
            ("collection_batch", "Batch"),
            ("video_url", "Video URL"),
        ],
    )


def _lead_preview(frame: pd.DataFrame) -> pd.DataFrame:
    preview = _select_columns(
        frame,
        [
            ("video_title", "Video title"),
            ("comment_text", "Comment text"),
            ("possible_evidence_category", "Possible evidence category"),
            ("manual_verification_required", "Verification status"),
            ("video_url", "Video URL"),
        ],
    )
    if "Possible evidence category" in preview.columns:
        preview["Possible evidence category"] = preview["Possible evidence category"].map(label_youtube_category)
    if "Verification status" in preview.columns:
        preview["Verification status"] = preview["Verification status"].map(_verification_label)
    return preview


def _verification_label(value: str) -> str:
    text = str(value).strip().lower()
    if text == "true":
        return "Keyword lead — manual reading still required"
    if text == "false":
        return "Not flagged as a keyword lead"
    return "Verification not recorded"


def _select_columns(frame: pd.DataFrame, pairs: list[tuple[str, str]]) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=[label for _, label in pairs])
    data = {}
    for logical, label in pairs:
        if logical in frame.columns:
            data[label] = frame[logical]
        else:
            resolved = resolve_column(frame, logical)
            if resolved is not None:
                data[label] = frame[resolved]
    if not data:
        return frame.head(TABLE_PREVIEW_ROWS).copy()
    return pd.DataFrame(data).head(TABLE_PREVIEW_ROWS)


def _show_table(frame: pd.DataFrame, empty_message: str) -> None:
    if frame is None or frame.empty:
        st.info(empty_message)
        return
    st.dataframe(frame, use_container_width=True, hide_index=True, height=420)


def _download(frame: pd.DataFrame, filename: str, key: str) -> None:
    if frame is None or frame.empty:
        st.caption("Nothing to download for this filter.")
        return
    st.download_button(
        "Download filtered CSV",
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


if __name__ == "__main__":
    main()
