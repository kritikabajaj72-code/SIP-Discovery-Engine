"""Tests for the data loader, using the real files in data/raw.

Run from the project folder:

    python -m unittest src.test_data_loader

A few extra checks use tiny in-memory tables. Those cover missing optional
columns and exact-duplicate removal, which the current raw files do not
contain. No test writes to data/raw.
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

import pandas as pd

# Allow `python src/test_data_loader.py` as well as unittest discovery.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_loader import (  # noqa: E402
    APP_REVIEW,
    COMMON_COLUMNS,
    INVESTOR_DISCUSSION,
    RAW_DIR,
    assign_missing_record_ids,
    detect_source_type,
    load_master_dataset,
    map_frame,
    match_columns,
    read_raw_csv,
    remove_exact_duplicates,
)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DataLoaderTests(unittest.TestCase):
    """Check the loader against the Google Play and YouTube exports."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_files = sorted(RAW_DIR.glob("*.csv"))
        cls.raw_hashes = {path.name: _file_sha256(path) for path in cls.raw_files}
        cls.combined, cls.report = load_master_dataset()
        cls.reviews = read_raw_csv(RAW_DIR / "sip_relevant_reviews.csv")
        cls.youtube = read_raw_csv(RAW_DIR / "youtube_sip_keyword_filtered.csv")

    def test_raw_files_are_not_modified(self) -> None:
        for path in self.raw_files:
            self.assertEqual(
                _file_sha256(path),
                self.raw_hashes[path.name],
                f"{path.name} changed while loading. The loader must only read raw files.",
            )

    def test_actual_columns_drive_the_mapping(self) -> None:
        review_type = detect_source_type(self.reviews, "sip_relevant_reviews.csv")
        youtube_type = detect_source_type(self.youtube, "youtube_sip_keyword_filtered.csv")
        self.assertEqual(review_type, APP_REVIEW)
        self.assertEqual(youtube_type, INVESTOR_DISCUSSION)

        review_map = match_columns(self.reviews, review_type)
        youtube_map = match_columns(self.youtube, youtube_type)
        self.assertEqual(review_map["original_text"], "review_text")
        self.assertEqual(review_map["record_id"], "review_id")
        self.assertEqual(review_map["app"], "app")
        self.assertEqual(review_map["rating"], "rating")
        self.assertIsNone(review_map["source_url"])
        self.assertEqual(youtube_map["original_text"], "comment")
        self.assertEqual(youtube_map["source_url"], "video_url")
        self.assertEqual(youtube_map["date"], "published_at")
        self.assertEqual(youtube_map["video_title"], "video_title")
        self.assertEqual(youtube_map["channel"], "channel")
        # YouTube has likes, not a star rating. Likes must not be copied into rating.
        self.assertIsNone(youtube_map["rating"])
        self.assertIsNone(youtube_map["app"])

    def test_combined_schema_and_row_counts(self) -> None:
        self.assertEqual(list(self.combined.columns), COMMON_COLUMNS)
        self.assertEqual(len(self.reviews) + len(self.youtube), len(self.combined))
        self.assertEqual(self.report["combined_rows"], len(self.combined))
        self.assertEqual(self.report["duplicates_removed"], 0)
        self.assertEqual(
            self.report["rows_loaded_by_source_type"][APP_REVIEW],
            len(self.reviews),
        )
        self.assertEqual(
            self.report["rows_loaded_by_source_type"][INVESTOR_DISCUSSION],
            len(self.youtube),
        )
        self.assertEqual(self.report["rows_loaded_by_source"]["Google Play"], len(self.reviews))
        self.assertEqual(self.report["rows_loaded_by_source"]["YouTube"], len(self.youtube))

    def test_source_types_and_known_apps(self) -> None:
        review_rows = self.combined[self.combined["source_type"] == APP_REVIEW]
        discussion_rows = self.combined[self.combined["source_type"] == INVESTOR_DISCUSSION]
        self.assertEqual(set(self.combined["source_type"]), {APP_REVIEW, INVESTOR_DISCUSSION})
        self.assertEqual(set(review_rows["source"]), {"Google Play"})
        self.assertEqual(set(discussion_rows["source"]), {"YouTube"})
        self.assertEqual(set(review_rows["app"]), set(self.reviews["app"]))
        self.assertTrue((discussion_rows["app"] == "").all())
        self.assertNotIn("(not provided)", set(self.combined["app"]))
        for app_name in ("Groww", "Zerodha Coin", "INDmoney"):
            self.assertIn(app_name, set(review_rows["app"]))

        summary = {(row["source"], row["app"]): row for row in self.report["source_summary"]}
        self.assertEqual(summary[("YouTube", "")]["source_type"], INVESTOR_DISCUSSION)
        self.assertEqual(summary[("YouTube", "")]["records"], len(self.youtube))
        self.assertEqual(summary[("Google Play", "Groww")]["records"], int((self.reviews["app"] == "Groww").sum()))
        self.assertEqual(
            summary[("Google Play", "Zerodha Coin")]["records"],
            int((self.reviews["app"] == "Zerodha Coin").sum()),
        )
        self.assertEqual(
            summary[("Google Play", "INDmoney")]["records"],
            int((self.reviews["app"] == "INDmoney").sum()),
        )
        self.assertTrue(self.report["text_preservation"]["texts_preserved"])
        self.assertEqual(self.report["text_preservation"]["missing_source_texts"], 0)

    def test_original_text_links_and_metadata_are_preserved(self) -> None:
        review_rows = self.combined[self.combined["source_type"] == APP_REVIEW]
        discussion_rows = self.combined[self.combined["source_type"] == INVESTOR_DISCUSSION]

        self.assertEqual(
            set(review_rows["original_text"]),
            set(self.reviews["review_text"]),
        )
        self.assertEqual(set(review_rows["record_id"]), set(self.reviews["review_id"]))
        self.assertEqual(set(review_rows["rating"]), set(self.reviews["rating"]))
        self.assertEqual(set(review_rows["date"]), set(self.reviews["date"]))

        self.assertEqual(set(discussion_rows["original_text"]), set(self.youtube["comment"]))
        self.assertEqual(set(discussion_rows["source_url"]), set(self.youtube["video_url"]))
        self.assertEqual(set(discussion_rows["video_title"]), set(self.youtube["video_title"]))
        self.assertEqual(set(discussion_rows["channel"]), set(self.youtube["channel"]))
        self.assertEqual(set(discussion_rows["date"]), set(self.youtube["published_at"]))

        # Different comments on one video must all remain.
        comments_per_video = discussion_rows.groupby("source_url").size()
        self.assertGreater(int(comments_per_video.max()), 1)
        self.assertEqual(self.report["missing_text"], 0)

    def test_optional_fields_stay_blank_instead_of_being_invented(self) -> None:
        review_rows = self.combined[self.combined["source_type"] == APP_REVIEW]
        discussion_rows = self.combined[self.combined["source_type"] == INVESTOR_DISCUSSION]
        for column in ("video_title", "channel", "source_url"):
            self.assertTrue((review_rows[column] == "").all(), column)
        self.assertTrue((discussion_rows["rating"] == "").all())
        self.assertTrue(discussion_rows["record_id"].str.startswith("local-").all())
        self.assertEqual(discussion_rows["record_id"].nunique(), len(discussion_rows))

    def test_saved_csv_matches_the_combined_table(self) -> None:
        saved = pd.read_csv(
            PROJECT_ROOT / "data" / "processed" / "master_dataset.csv",
            dtype=str,
            keep_default_na=False,
        )
        self.assertEqual(list(saved.columns), COMMON_COLUMNS)
        self.assertEqual(len(saved), len(self.combined))
        self.assertEqual(saved["original_text"].tolist(), self.combined["original_text"].tolist())
        youtube_saved = saved[saved["source_type"] == INVESTOR_DISCUSSION]
        self.assertTrue((youtube_saved["app"] == "").all())
        self.assertNotIn("(not provided)", saved.astype(str).values.ravel().tolist())

    def test_missing_optional_columns_do_not_crash(self) -> None:
        sparse = pd.DataFrame(
            {
                "source": ["Google Play"],
                "review_text": ["good for sip"],
            }
        )
        mapped = map_frame(sparse, APP_REVIEW, "sparse_reviews.csv")
        self.assertEqual(list(mapped.columns), COMMON_COLUMNS)
        self.assertEqual(mapped.loc[0, "original_text"], "good for sip")
        self.assertEqual(mapped.loc[0, "source_type"], APP_REVIEW)
        for column in ("record_id", "app", "rating", "date", "video_title", "channel", "source_url"):
            self.assertEqual(mapped.loc[0, column], "")

    def test_exact_duplicates_are_removed_but_same_video_comments_stay(self) -> None:
        comments = pd.DataFrame(
            {
                "source": ["YouTube", "YouTube", "YouTube"],
                "video_id": ["abc", "abc", "abc"],
                "video_title": ["How to do SIP", "How to do SIP", "How to do SIP"],
                "channel": ["Coach", "Coach", "Coach"],
                "video_url": ["https://www.youtube.com/watch?v=abc"] * 3,
                "comment": ["Thanks for sip tips", "Thanks for sip tips", "I started a SIP"],
                "published_at": ["2025-07-20T14:44:08Z"] * 3,
                "likes": ["1", "1", "4"],
            }
        )
        mapped = map_frame(comments, INVESTOR_DISCUSSION, "sample_youtube.csv")
        deduped, removed = remove_exact_duplicates(mapped)
        self.assertEqual(removed, 1)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(
            set(deduped["original_text"]),
            {"Thanks for sip tips", "I started a SIP"},
        )
        self.assertEqual(set(deduped["source_url"]), {"https://www.youtube.com/watch?v=abc"})
        with_ids = assign_missing_record_ids(deduped)
        self.assertEqual(with_ids["record_id"].nunique(), 2)


if __name__ == "__main__":
    unittest.main()
