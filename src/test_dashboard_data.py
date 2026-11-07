"""Checks for the research dashboard data layer.

These tests read the saved research files. They do not collect data or
write over those files.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

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
    category_counts_from_reviews,
    category_file_matches_master,
    load_research,
    overview_counts,
    project_root,
    source_record_counts,
    split_findings,
    youtube_lead_counts,
)
from src.dashboard_hypotheses import UNVALIDATED, build_hypotheses


EXPECTED_YOUTUBE_LEADS = {
    "missed_payment": 46,
    "general_educational_discussion": 17,
    "first_person_actual_discontinuation": 6,
    "sip_cancellation": 5,
    "temporary_pause": 1,
    "financial_difficulty": 1,
    "intention_to_stop": 0,
}


class DashboardDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_research(project_root())

    def test_required_files_load(self) -> None:
        messages = self.bundle.messages()
        self.assertEqual(messages, [], "\n".join(messages))
        self.assertGreater(len(self.bundle.frame("play_master").index), 0)
        self.assertGreater(len(self.bundle.frame("youtube_master").index), 0)
        self.assertGreater(len(self.bundle.frame("youtube_audit").index), 0)
        self.assertIn("Research objective", self.bundle.text("findings"))

    def test_overview_counts_match_tables(self) -> None:
        play = self.bundle.frame("play_master")
        youtube = self.bundle.frame("youtube_master")
        audit = self.bundle.frame("youtube_audit")
        counts = overview_counts(self.bundle)
        self.assertEqual(counts.play_reviews, len(play.index))
        self.assertEqual(counts.youtube_comments, len(youtube.index))
        self.assertEqual(counts.apps, play["app_name"].nunique())
        videos = youtube["video_id"].fillna("").astype(str)
        channels = youtube["channel"].fillna("").astype(str)
        self.assertEqual(counts.youtube_videos, videos[videos.str.strip() != ""].nunique())
        self.assertEqual(counts.youtube_channels, channels[channels.str.strip() != ""].nunique())
        self.assertEqual(counts.youtube_keyword_leads, len(audit.index))
        relevance = play["sip_relevance"]
        self.assertEqual(counts.play_sip_relevance_leads, int(relevance.isin(["direct", "indirect"]).sum()))
        self.assertEqual(counts.play_reviews, 1500)
        self.assertEqual(counts.youtube_comments, 2692)
        self.assertEqual(counts.apps, 3)
        self.assertEqual(counts.youtube_videos, 76)
        self.assertEqual(counts.youtube_keyword_leads, 76)
        self.assertEqual(counts.play_sip_relevance_leads, 303)

    def test_app_comparison_totals_match_reviews(self) -> None:
        play = self.bundle.frame("play_master")
        summary = app_summary(play)
        self.assertEqual(int(summary["reviews"].sum()), len(play.index))
        bands = summary[["negative", "neutral", "positive", "unrated"]].sum().sum()
        relevance = summary[["direct", "indirect", "not_relevant", "relevance_unlabelled"]].sum().sum()
        self.assertEqual(int(bands), len(play.index))
        self.assertEqual(int(relevance), len(play.index))
        counted = category_counts_from_reviews(play)
        self.assertEqual(int(counted["review_count"].sum()), len(play.index))
        for app_name, group in play.groupby("app_name"):
            app_rows = summary.loc[summary["app_name"] == app_name, "reviews"]
            self.assertEqual(int(app_rows.iloc[0]), len(group.index))
        self.assertIn("matches the review master", category_file_matches_master(self.bundle))

    def test_youtube_lead_counts_match_audit(self) -> None:
        audit = self.bundle.frame("youtube_audit")
        counted = youtube_lead_counts(audit).set_index("category_code")["comments"]
        for code, expected in EXPECTED_YOUTUBE_LEADS.items():
            self.assertEqual(int(counted.loc[code]), expected, code)
        self.assertEqual(int(counted.sum()), len(audit.index))
        self.assertEqual(int(audit["possible_evidence_category"].value_counts().sum()), len(audit.index))

    def test_findings_navigation_sections(self) -> None:
        titles = [title for title, _body in split_findings(self.bundle.text("findings"))]
        for expected in (
            "Research objective",
            "Methodology",
            "Findings",
            "Research gaps",
            "Interview questions",
            "Research limitations",
        ):
            self.assertIn(expected, titles)

    def test_hypotheses_stay_unvalidated(self) -> None:
        cards = build_hypotheses(self.bundle.frame("play_master"), self.bundle.frame("youtube_audit"))
        self.assertEqual(len(cards), 4)
        for card in cards:
            self.assertEqual(card.status, UNVALIDATED)
            combined = " ".join(card.observations).lower()
            self.assertNotIn("confirmed discontinuation", combined)
            self.assertNotIn("established cause", combined)

    def test_empty_frames_do_not_crash(self) -> None:
        empty = pd.DataFrame()
        summary = app_summary(empty)
        figures = [
            source_distribution_chart(source_record_counts(overview_counts(load_research(Path(tempfile.mkdtemp()))))),
            review_volume_chart(summary),
            rating_distribution_chart(empty),
            rating_band_chart(summary),
            sip_relevance_chart(summary),
            problem_category_chart(category_counts_from_reviews(empty), False),
            youtube_lead_chart(youtube_lead_counts(empty)),
            batch_chart(pd.DataFrame()),
        ]
        for figure in figures:
            self.assertIsNotNone(figure.to_dict())
        cards = build_hypotheses(empty, empty)
        self.assertTrue(all(card.status == UNVALIDATED for card in cards))
        narrow = pd.DataFrame({"review_id": ["abc"]})
        self.assertTrue(app_summary(narrow).empty)
        self.assertIsNotNone(rating_distribution_chart(narrow).to_dict())

    def test_missing_directory_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            bundle = load_research(Path(folder))
            self.assertGreater(len(bundle.messages()), 0)
            counts = overview_counts(bundle)
            self.assertEqual(counts.play_reviews, 0)
            self.assertEqual(counts.youtube_comments, 0)
            self.assertEqual(counts.youtube_keyword_leads, 0)


if __name__ == "__main__":
    unittest.main()
