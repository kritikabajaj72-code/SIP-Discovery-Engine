"""Offline checks for root-cause categories.

These tests do not call Gemini and do not write validation or pilot files.

Run from the project folder:

    python -m unittest src.test_root_cause_category
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classifier import normalise_classification  # noqa: E402


def _raw(**overrides) -> dict:
    base = {
        "relevance_to_sip": "direct",
        "investor_motivation": "Unknown",
        "journey_stage": "Unknown",
        "pain_point": "Unknown",
        "trigger": "Unknown",
        "behaviour": "unknown",
        "emotion": "Unknown",
        "root_cause": "Unknown",
        "root_cause_detail": "Unknown",
        "root_cause_category": "unknown",
        "unmet_need": "Unknown",
        "continuation_relevance": "general_discussion",
        "evidence_quote": "Unknown",
        "evidence_strength": "none",
        "confidence_score": 0.7,
        "unsupported_inference": False,
        "uncertainty_reason": "Unknown",
    }
    base.update(overrides)
    return base


class RootCauseCategoryTests(unittest.TestCase):
    def test_unknown_cause_is_not_given_a_category(self) -> None:
        text = "I missed my payment this month becoz of this."
        result = normalise_classification(
            _raw(
                behaviour="missed_installment",
                root_cause="Unknown",
                root_cause_category="financial_constraints",
                evidence_quote="I missed my payment this month",
            ),
            text,
        )
        self.assertEqual(result["behaviour"], "missed_installment")
        self.assertEqual(result["root_cause_detail"], "Unknown")
        self.assertEqual(result["root_cause_category"], "unknown")
        self.assertEqual(result["evidence_quote"], "I missed my payment this month")

    def test_category_is_removed_when_the_stated_cause_does_not_support_it(self) -> None:
        text = "I missed my payment this month becoz of this."
        result = normalise_classification(
            _raw(
                behaviour="missed_installment",
                root_cause="I missed my payment this month",
                root_cause_category="low_or_disappointing_returns",
                evidence_quote="I missed my payment this month",
                evidence_strength="strong",
            ),
            text,
        )
        self.assertEqual(result["behaviour"], "missed_installment")
        self.assertEqual(result["root_cause_detail"], "I missed my payment this month")
        self.assertEqual(result["root_cause_category"], "unknown")
        self.assertEqual(result["evidence_quote"], "I missed my payment this month")

    def test_supported_category_is_kept_without_changing_behaviour(self) -> None:
        text = "2 time meda sip miss ho geya madam peisa nahi tha"
        result = normalise_classification(
            _raw(
                behaviour="missed_installment",
                root_cause="peisa nahi tha",
                root_cause_category="financial_constraints",
                evidence_quote="sip miss ho geya",
                evidence_strength="strong",
            ),
            text,
        )
        self.assertEqual(result["behaviour"], "missed_installment")
        self.assertEqual(result["root_cause_detail"], "peisa nahi tha")
        self.assertEqual(result["root_cause_category"], "financial_constraints")
        self.assertEqual(result["evidence_quote"], "sip miss ho geya")

    def test_advice_is_not_relabelled_as_discontinuation(self) -> None:
        text = "don't stop your sip just keep patience"
        result = normalise_classification(
            _raw(
                behaviour="explicitly_discontinued",
                root_cause="Unknown",
                root_cause_category="market_volatility",
                evidence_quote="don't stop your sip",
                evidence_strength="strong",
            ),
            text,
        )
        self.assertEqual(result["behaviour"], "general_advice_or_opinion")
        self.assertNotEqual(result["behaviour"], "explicitly_discontinued")
        self.assertEqual(result["root_cause_category"], "unknown")
        self.assertEqual(result["evidence_quote"], "don't stop your sip")


if __name__ == "__main__":
    unittest.main()
