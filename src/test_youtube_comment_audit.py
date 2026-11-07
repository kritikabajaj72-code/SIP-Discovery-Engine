"""Tests for combining YouTube batches and for keyword leads.

These tests use temporary files. They do not call YouTube or Gemini,
and they do not read or write the project's raw datasets.

Run from the project folder:

    python -m unittest src.test_youtube_comment_audit -v
"""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.audit_youtube_evidence import (  # noqa: E402
    ACTUAL,
    EDUCATION,
    INTENTION,
    MISSED,
    audit_rows,
    screen_comment,
)
from src.consolidate_youtube_batches import (  # noqa: E402
    ORIGINAL_COLUMNS,
    consolidate,
)


def _write_batch(folder: Path, number: int, rows: list[dict[str, str]]) -> Path:
    path = folder / f"youtube_targeted_comments_batch{number}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ORIGINAL_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _comment(comment_id: str, text: str, video_id: str = "vid1") -> dict[str, str]:
    return {
        "video_id": video_id,
        "video_title": "A title",
        "channel": "A channel",
        "video_url": "https://www.youtube.com/watch?v=vid1",
        "comment_id": comment_id,
        "comment_text": text,
        "comment_published_at": "2026-01-01T00:00:00Z",
        "like_count": "0",
        "discovery_search_query": "I stopped my SIP why India",
    }


class ConsolidateTests(unittest.TestCase):
    """Combining batch files, ids, text, and missing inputs."""

    def test_combines_nine_batches_and_marks_each_batch(self) -> None:
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            files = []
            for number in range(1, 10):
                path = _write_batch(
                    folder,
                    number,
                    [_comment(f"c{number}", f"comment from batch {number}", f"v{number}")],
                )
                files.append((number, path))
            result = consolidate(files)
        self.assertEqual(result.rows_before_dedup, 9)
        self.assertEqual(len(result.rows), 9)
        self.assertEqual([row["collection_batch"] for row in result.rows], [str(n) for n in range(1, 10)])
        self.assertEqual(result.errors, [])

    def test_deduplicates_by_comment_id_and_keeps_the_first_text(self) -> None:
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            first = _write_batch(folder, 1, [_comment("same", "original wording")])
            second = _write_batch(folder, 2, [_comment("same", "later wording")])
            result = consolidate([(1, first), (2, second)])
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0]["comment_text"], "original wording")
        self.assertEqual(result.rows[0]["collection_batch"], "1")
        self.assertEqual(result.duplicate_comment_ids, ["same"])

    def test_preserves_comment_text_exactly(self) -> None:
        original = "I stopped my SIP.\nLine two — don't change this."
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            path = _write_batch(folder, 1, [_comment("c1", original)])
            result = consolidate([(1, path)])
        self.assertEqual(result.rows[0]["comment_text"], original)

    def test_missing_file_is_reported_and_other_batches_are_kept(self) -> None:
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            path = _write_batch(folder, 1, [_comment("c1", "kept")])
            missing = folder / "youtube_targeted_comments_batch2.csv"
            result = consolidate([(1, path), (2, missing)])
        self.assertEqual(len(result.rows), 1)
        self.assertTrue(any("Missing batch file" in error for error in result.errors))
        self.assertFalse(missing.exists())

    def test_empty_comment_is_counted_and_kept(self) -> None:
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            path = _write_batch(folder, 1, [_comment("c1", "   ")])
            result = consolidate([(1, path)])
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.empty_comment_rows, 1)
        self.assertEqual(result.rows[0]["comment_text"], "   ")


class KeywordScreenTests(unittest.TestCase):
    """Keyword leads must not promote questions, advice, or missed payments."""

    def test_first_person_stop_is_only_a_possible_category(self) -> None:
        lead = screen_comment("I stopped my SIP last month.")
        self.assertIsNotNone(lead)
        assert lead is not None
        self.assertEqual(lead["possible_evidence_category"], ACTUAL)
        self.assertEqual(lead["manual_verification_required"], "true")
        self.assertIn(lead["evidence_quote"], "I stopped my SIP last month.")

    def test_question_about_stopping_is_not_actual_discontinuation(self) -> None:
        lead = screen_comment("Should I stop my SIP now?")
        self.assertIsNotNone(lead)
        assert lead is not None
        self.assertEqual(lead["possible_evidence_category"], EDUCATION)
        self.assertNotEqual(lead["possible_evidence_category"], ACTUAL)
        self.assertIn("question_about_stopping", lead["keyword_matches"])

    def test_advice_not_to_stop_is_not_personal_experience(self) -> None:
        lead = screen_comment("Never stop your SIP, just keep patience.")
        self.assertIsNotNone(lead)
        assert lead is not None
        self.assertEqual(lead["possible_evidence_category"], EDUCATION)
        self.assertNotEqual(lead["possible_evidence_category"], ACTUAL)

    def test_intention_is_not_labelled_as_already_stopped(self) -> None:
        lead = screen_comment("I want to stop my SIP but I have not done it.")
        self.assertIsNotNone(lead)
        assert lead is not None
        self.assertEqual(lead["possible_evidence_category"], INTENTION)
        self.assertNotEqual(lead["possible_evidence_category"], ACTUAL)

    def test_regret_about_not_stopping_is_not_actual_discontinuation(self) -> None:
        lead = screen_comment("I should have stopped the SIPs the moment it was promoted.")
        if lead is not None:
            self.assertNotEqual(lead["possible_evidence_category"], ACTUAL)

    def test_missing_the_point_is_not_a_missed_payment(self) -> None:
        lead = screen_comment("You are missing the biggest point. SIP is a discipline.")
        if lead is not None:
            self.assertNotEqual(lead["possible_evidence_category"], MISSED)

    def test_missed_payment_is_not_discontinuation(self) -> None:
        lead = screen_comment("I missed my SIP payment this month.")
        self.assertIsNotNone(lead)
        assert lead is not None
        self.assertEqual(lead["possible_evidence_category"], MISSED)
        self.assertNotEqual(lead["possible_evidence_category"], ACTUAL)

    def test_audit_rows_keep_original_text_and_require_review(self) -> None:
        rows = [
            {
                "video_id": "v",
                "video_title": "Title",
                "channel": "Channel",
                "video_url": "https://www.youtube.com/watch?v=v",
                "comment_id": "c",
                "comment_text": "I missed my SIP payment this month.",
                "comment_published_at": "2026-01-01T00:00:00Z",
                "like_count": "1",
                "discovery_search_query": "query",
                "collection_batch": "1",
            },
            {
                "video_id": "v",
                "video_title": "Title",
                "channel": "Channel",
                "video_url": "https://www.youtube.com/watch?v=v",
                "comment_id": "d",
                "comment_text": "Nice video",
                "comment_published_at": "",
                "like_count": "0",
                "discovery_search_query": "query",
                "collection_batch": "1",
            },
        ]
        leads = audit_rows(rows)
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["comment_text"], "I missed my SIP payment this month.")
        self.assertIn(leads[0]["evidence_quote"], leads[0]["comment_text"])
        self.assertEqual(leads[0]["manual_verification_required"], "true")


if __name__ == "__main__":
    unittest.main()
