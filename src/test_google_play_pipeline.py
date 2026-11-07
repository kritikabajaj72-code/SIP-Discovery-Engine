"""Tests for the Google Play pipeline.

The scraper is replaced with a fake function. These tests do not use
the network and do not read the project's raw review files.

Run from the project folder:

    python -m unittest src.test_google_play_pipeline -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.google_play_analyze import (  # noqa: E402
    DIRECT,
    INDIRECT,
    NOT_RELEVANT,
    annotate_reviews,
    build_comparative_report,
    classify_review,
)
from src.google_play_clean import clean_reviews  # noqa: E402
from src.google_play_collect import (  # noqa: E402
    APPS,
    collect_apps,
    dedupe_app_reviews,
    fetch_pages,
    normalise_review,
    output_is_blocked,
)
from src.google_play_pipeline import confirm_collection  # noqa: E402


def _raw_review(review_id: str, content: str, score=5, at="2026-01-01T00:00:00", version="1.0"):
    return {
        "reviewId": review_id,
        "content": content,
        "score": score,
        "thumbsUpCount": 2,
        "reviewCreatedVersion": version,
        "at": at,
        "replyContent": None,
        "repliedAt": None,
    }


class CollectionTests(unittest.TestCase):
    """Download behaviour with a stand-in scraper."""

    def test_pagination_stops_at_the_last_token(self) -> None:
        calls = []

        def fake_reviews(package_id, count, continuation_token):
            calls.append((package_id, count, continuation_token))
            if continuation_token is None:
                return ([_raw_review("a", "first"), _raw_review("b", "second")], "next")
            return ([_raw_review("c", "third")], None)

        rows = fetch_pages("com.nextbillion.groww", fake_reviews, max_reviews=500, page_size=2)
        self.assertEqual([row["reviewId"] for row in rows], ["a", "b", "c"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][2], "next")

    def test_deduplication_keeps_the_first_review_id(self) -> None:
        rows = [
            normalise_review(_raw_review("same", "first text"), "Groww", "com.nextbillion.groww", "t"),
            normalise_review(_raw_review("same", "second text"), "Groww", "com.nextbillion.groww", "t"),
        ]
        unique = dedupe_app_reviews(rows)
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0]["review_text"], "first text")

    def test_missing_fields_stay_blank(self) -> None:
        raw = {"reviewId": "r1", "content": None, "score": None, "at": None}
        row = normalise_review(raw, "INDmoney", "in.indwealth", "2026-01-02T00:00:00+00:00")
        self.assertEqual(row["review_text"], "")
        self.assertEqual(row["rating"], "")
        self.assertEqual(row["review_date"], "")
        self.assertEqual(row["app_name"], "INDmoney")
        self.assertEqual(row["package_id"], "in.indwealth")

    def test_failed_app_does_not_count_as_complete(self) -> None:
        def fake_reviews(package_id, count, continuation_token):
            if package_id == "com.zerodha.coin":
                raise RuntimeError("store page unavailable")
            return ([_raw_review(package_id, "ok")], None)

        result = collect_apps(fake_reviews, max_reviews=10, collected_at="2026-01-01T00:00:00+00:00")
        self.assertFalse(result["complete"])
        self.assertIn("Groww", result["app_counts"])
        self.assertTrue(any(name == "Zerodha Coin" for name, _detail in result["failures"]))

    def test_existing_output_is_blocked_without_reading_the_network(self) -> None:
        with tempfile.TemporaryDirectory() as folder_name:
            path = Path(folder_name) / "google_play_reviews_unfiltered.csv"
            path.write_text("already here", encoding="utf-8")
            self.assertTrue(output_is_blocked(path))


class CleaningAndKeywordTests(unittest.TestCase):
    """Cleaning flags and keyword leads."""

    def test_clean_flags_empty_text_and_missing_rating(self) -> None:
        cleaned = clean_reviews(
            [
                {
                    "review_id": "r1",
                    "review_text": "   ",
                    "rating": "",
                    "review_date": "",
                    "app_version": "",
                    "thumbs_up_count": "",
                    "developer_response": "",
                    "developer_response_date": "",
                    "app_name": "Groww",
                    "package_id": "com.nextbillion.groww",
                    "collection_timestamp": "t",
                }
            ]
        )
        row = cleaned["rows"][0]
        self.assertEqual(row["review_text"], "   ")
        self.assertEqual(row["empty_review"], "true")
        self.assertEqual(row["rating_missing"], "true")
        self.assertEqual(row["date_missing"], "true")
        self.assertEqual(row["source"], "Google Play")
        self.assertEqual(row["source_type"], "app_review")
        self.assertEqual(row["source_id"], "google_play:com.nextbillion.groww:r1")

    def test_direct_indirect_and_irrelevant_reviews(self) -> None:
        self.assertEqual(classify_review("I started a SIP yesterday.")["sip_relevance"], DIRECT)
        self.assertEqual(classify_review("The mutual fund portfolio screen is confusing.")["sip_relevance"], INDIRECT)
        self.assertEqual(classify_review("Nice colours.")["sip_relevance"], NOT_RELEVANT)

    def test_payment_failure_is_not_labelled_as_discontinuation(self) -> None:
        label = classify_review("Unable to do SIP payment. please check.")
        self.assertEqual(label["possible_problem_category"], "sip_payment_failure")
        self.assertNotIn("discontinu", label["possible_problem_category"])
        self.assertEqual(label["manual_verification_required"], "true")

    def test_cancellation_request_is_a_lead_not_a_completed_event(self) -> None:
        label = classify_review("How do I cancel SIP in the app?")
        self.assertEqual(label["possible_problem_category"], "sip_pause_or_cancellation")
        self.assertEqual(label["sip_relevance"], DIRECT)
        self.assertNotIn("confirmed", label["matched_keywords"])

    def test_financial_words_are_required_for_that_category(self) -> None:
        self.assertEqual(classify_review("I cannot afford the SIP.")["possible_problem_category"], "financial_constraints")
        self.assertNotEqual(classify_review("The app is slow.")["possible_problem_category"], "financial_constraints")

    def test_report_states_limits_and_uses_only_given_counts(self) -> None:
        rows = annotate_reviews(
            clean_reviews(
                [
                    {
                        "review_id": "1",
                        "review_text": "SIP payment failed",
                        "rating": "1",
                        "review_date": "2026-01-01",
                        "app_version": "",
                        "thumbs_up_count": "0",
                        "developer_response": "",
                        "developer_response_date": "",
                        "app_name": "Groww",
                        "package_id": "com.nextbillion.groww",
                        "collection_timestamp": "t",
                    },
                    {
                        "review_id": "2",
                        "review_text": "Good app",
                        "rating": "5",
                        "review_date": "2026-01-02",
                        "app_version": "",
                        "thumbs_up_count": "0",
                        "developer_response": "",
                        "developer_response_date": "",
                        "app_name": "Zerodha Coin",
                        "package_id": "com.zerodha.coin",
                        "collection_timestamp": "t",
                    },
                ]
            )["rows"]
        )
        report = build_comparative_report(rows)
        self.assertIn("| Groww | 1 |", report)
        self.assertIn("| Zerodha Coin | 1 |", report)
        self.assertIn("do not show which app is better", report)
        self.assertIn("does not prove the writer discontinued a SIP", report)

    def test_confirmation_rejects_anything_except_yes(self) -> None:
        answers = iter(["no"])

        def fake_input(_prompt: str) -> str:
            return next(answers)

        original_isatty = sys.stdin.isatty
        original_input = __import__("builtins").input
        sys.stdin.isatty = lambda: True  # type: ignore[method-assign]
        __import__("builtins").input = fake_input
        try:
            self.assertFalse(confirm_collection(["plan"]))
        finally:
            sys.stdin.isatty = original_isatty  # type: ignore[method-assign]
            __import__("builtins").input = original_input

    def test_three_app_ids_are_the_requested_packages(self) -> None:
        packages = {package_id for _name, package_id in APPS}
        self.assertEqual(
            packages,
            {"com.nextbillion.groww", "com.zerodha.coin", "in.indwealth"},
        )


if __name__ == "__main__":
    unittest.main()
