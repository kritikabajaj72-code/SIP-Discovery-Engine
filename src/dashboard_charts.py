"""Plotly charts for the research dashboard.

Charts show counts from the tables passed in. They do not rank apps
and they do not treat a keyword as a confirmed discontinuation.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.dashboard_data import label_play_category, resolve_column


APP_COLOURS = {
    "Groww": "#1F7A6A",
    "Zerodha Coin": "#1D4E89",
    "INDmoney": "#8A6A2F",
}
BAND_COLOURS = {
    "negative": "#8C4A4A",
    "neutral": "#C4A35A",
    "positive": "#1F7A6A",
    "unrated": "#7A8B99",
}
SOURCE_COLOURS = {
    "Google Play reviews": "#1D4E89",
    "YouTube comments": "#0F6E6E",
}
FALLBACK_COLOURS = ["#1D4E89", "#1F7A6A", "#8A6A2F", "#5C6B7A", "#8C4A4A"]


def empty_figure(message: str) -> go.Figure:
    """A blank chart with one sentence, used when a file or column is missing."""
    figure = go.Figure()
    figure.update_layout(
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": message,
                "showarrow": False,
                "x": 0.5,
                "y": 0.5,
                "xref": "paper",
                "yref": "paper",
                "font": {"size": 14, "color": "#5C6B7A"},
            }
        ],
        margin={"l": 24, "r": 24, "t": 24, "b": 24},
    )
    return figure


def _theme(figure: go.Figure, title: str, height: int = 420) -> go.Figure:
    figure.update_layout(
        title={"text": title, "font": {"size": 16, "color": "#122033"}},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font={"family": "Arial, sans-serif", "color": "#122033", "size": 13},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"l": 48, "r": 24, "t": 72, "b": 48},
        height=height,
        bargap=0.28,
    )
    figure.update_xaxes(showgrid=False, linecolor="#E3E8EE")
    figure.update_yaxes(gridcolor="#E6EBF0", zeroline=False)
    return figure


def _colour_for(name: str, index: int) -> str:
    return APP_COLOURS.get(name, FALLBACK_COLOURS[index % len(FALLBACK_COLOURS)])


def source_distribution_chart(counts: pd.DataFrame) -> go.Figure:
    """Side-by-side record counts for the two sources."""
    if counts is None or counts.empty:
        return empty_figure("No source counts are available.")
    figure = go.Figure()
    for index, row in counts.iterrows():
        figure.add_bar(
            x=[row["source"]],
            y=[row["records"]],
            name=row["population"],
            marker_color=SOURCE_COLOURS.get(row["source"], FALLBACK_COLOURS[index % len(FALLBACK_COLOURS)]),
            text=[int(row["records"])],
            textposition="outside",
            hovertemplate="%{x}<br>Records: %{y}<br>Population: " + str(row["population"]) + "<extra></extra>",
        )
    figure.update_layout(showlegend=False, yaxis_title="Records collected")
    return _theme(figure, "Records collected, shown separately by source")


def review_volume_chart(summary: pd.DataFrame) -> go.Figure:
    """How many reviews each selected app contributed."""
    if summary is None or summary.empty:
        return empty_figure("No app reviews match this selection.")
    figure = go.Figure()
    for index, row in summary.iterrows():
        figure.add_bar(
            x=[row["app_name"]],
            y=[row["reviews"]],
            name=row["app_name"],
            marker_color=_colour_for(row["app_name"], index),
            text=[int(row["reviews"])],
            textposition="outside",
            hovertemplate="%{x}<br>Reviews: %{y}<extra></extra>",
        )
    figure.update_layout(showlegend=False, yaxis_title="Reviews")
    return _theme(figure, "Review volume")


def rating_distribution_chart(frame: pd.DataFrame) -> go.Figure:
    """Star counts by app. Stars are reviewer ratings, not a quality score."""
    if frame is None or frame.empty:
        return empty_figure("No reviews are available for the rating chart.")
    app_column = resolve_column(frame, "app_name")
    rating_column = resolve_column(frame, "rating")
    if app_column is None or rating_column is None:
        return empty_figure("The review file has no app or rating column.")
    figure = go.Figure()
    apps = list(dict.fromkeys(frame[app_column].astype(str)))
    for index, app_name in enumerate(apps):
        group = frame[frame[app_column] == app_name]
        stars = []
        for star in range(1, 6):
            numeric = pd.to_numeric(group[rating_column], errors="coerce")
            stars.append(int((numeric == star).sum()))
        figure.add_bar(
            x=["1 star", "2 stars", "3 stars", "4 stars", "5 stars"],
            y=stars,
            name=app_name,
            marker_color=_colour_for(app_name, index),
        )
    figure.update_layout(barmode="group", yaxis_title="Reviews")
    return _theme(figure, "Rating distribution")


def rating_band_chart(summary: pd.DataFrame) -> go.Figure:
    """Negative, neutral, and positive bands stacked by app."""
    if summary is None or summary.empty:
        return empty_figure("No reviews are available for the rating bands.")
    figure = go.Figure()
    for band in ("negative", "neutral", "positive", "unrated"):
        if band not in summary.columns:
            continue
        if band == "unrated" and int(summary[band].sum()) == 0:
            continue
        figure.add_bar(
            x=summary["app_name"],
            y=summary[band],
            name=band.capitalize(),
            marker_color=BAND_COLOURS[band],
        )
    figure.update_layout(barmode="stack", yaxis_title="Reviews")
    return _theme(figure, "Negative, neutral, and positive rating bands")


def sip_relevance_chart(summary: pd.DataFrame) -> go.Figure:
    """Direct and indirect SIP wording, plus reviews with neither."""
    if summary is None or summary.empty:
        return empty_figure("No reviews are available for SIP relevance.")
    figure = go.Figure()
    series = [
        ("direct", "Direct SIP mention", "#1D4E89"),
        ("indirect", "Indirect relevance", "#1F7A6A"),
        ("not_relevant", "Not relevant by these rules", "#C5CED6"),
    ]
    for column, name, colour in series:
        figure.add_bar(x=summary["app_name"], y=summary[column], name=name, marker_color=colour)
    figure.update_layout(barmode="group", yaxis_title="Reviews")
    return _theme(figure, "SIP relevance labels")


def problem_category_chart(counts: pd.DataFrame, include_none: bool) -> go.Figure:
    """Primary keyword category by app. One review has one primary category."""
    if counts is None or counts.empty:
        return empty_figure("No problem-category counts are available.")
    working = counts.copy()
    if not include_none:
        working = working[working["possible_problem_category"].astype(str) != "none"]
    if working.empty:
        return empty_figure("No problem-keyword categories are present in this selection.")
    working["label"] = working["possible_problem_category"].map(label_play_category)
    totals = working.groupby("label")["review_count"].sum().sort_values(ascending=True)
    figure = go.Figure()
    for index, app_name in enumerate(working["app_name"].unique()):
        group = working[working["app_name"] == app_name].set_index("label")
        figure.add_bar(
            y=list(totals.index),
            x=[int(group["review_count"].get(label, 0)) for label in totals.index],
            name=str(app_name),
            orientation="h",
            marker_color=_colour_for(str(app_name), index),
        )
    figure.update_layout(barmode="group", xaxis_title="Reviews", height=max(420, 36 * len(totals.index) + 160))
    return _theme(figure, "Primary problem-category distribution", height=max(420, 36 * len(totals.index) + 160))


def youtube_lead_chart(counts: pd.DataFrame) -> go.Figure:
    """Keyword-lead counts, including a category whose count is zero."""
    if counts is None or counts.empty:
        return empty_figure("No YouTube lead table is available.")
    figure = go.Figure()
    figure.add_bar(
        y=counts["category"],
        x=counts["comments"],
        orientation="h",
        marker_color="#1D4E89",
        text=counts["comments"],
        textposition="outside",
        hovertemplate="%{y}<br>Keyword matches: %{x}<extra></extra>",
    )
    figure.update_layout(xaxis_title="Comments matched by keywords", showlegend=False)
    return _theme(figure, "YouTube keyword leads", height=480)


def batch_chart(counts: pd.DataFrame) -> go.Figure:
    """How the saved comments are spread across collection batches."""
    if counts is None or counts.empty:
        return empty_figure("No collection-batch column is available.")
    figure = go.Figure()
    figure.add_bar(
        x=counts["batch_label"],
        y=counts["comments"],
        name="Comments",
        marker_color="#0F6E6E",
        text=counts["comments"],
        textposition="outside",
        customdata=counts["videos"],
        hovertemplate="%{x}<br>Comments: %{y}<br>Videos: %{customdata}<extra></extra>",
    )
    figure.update_layout(yaxis_title="Comments", showlegend=False)
    return _theme(figure, "YouTube comments by collection batch")
