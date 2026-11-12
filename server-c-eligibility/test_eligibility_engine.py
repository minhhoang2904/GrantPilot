from __future__ import annotations

import unittest
from unittest.mock import patch

import config
from eligibility_engine import evaluate, evaluate_rules


class RuleEngineTest(unittest.TestCase):
    def test_nested_all_any_passes(self):
        rules = {
            "all": [
                {"field": "is_sme", "operator": "==", "value": True},
                {
                    "any": [
                        {"field": "has_collateral", "operator": "==", "value": True},
                        {"field": "has_credit_rating", "operator": "==", "value": True},
                    ]
                },
            ]
        }
        result = evaluate_rules(rules, {"is_sme": True, "has_collateral": True})
        self.assertEqual(result["status"], "pass")

    def test_missing_field_is_unknown_not_false(self):
        policy = {
            "policy_id": "p1",
            "rules": {"all": [{"field": "is_innovative_startup", "operator": "==", "value": True}]},
        }
        result = evaluate({"is_innovative_startup": None}, policy)
        self.assertEqual(result["status"], "needs_more_information")
        self.assertIsNone(result["is_eligible"])
        self.assertEqual(result["missing_fields"], ["is_innovative_startup"])

    def test_false_fact_fails_instead_of_becoming_unknown(self):
        policy = {
            "policy_id": "p1",
            "rules": {"all": [{"field": "is_sme", "operator": "==", "value": True}]},
        }
        result = evaluate({"is_sme": False}, policy)
        self.assertEqual(result["status"], "not_eligible")
        self.assertFalse(result["is_eligible"])

    def test_invalid_operator_requires_manual_review(self):
        result = evaluate_rules(
            {"all": [{"field": "x", "operator": "approximately", "value": 1}]},
            {"x": 1},
        )
        self.assertEqual(result["status"], "error")

    def test_contains_operator_is_preserved(self):
        result = evaluate_rules(
            {"field": "description", "operator": "contains", "value": "công nghệ"},
            {"description": "Giải pháp công nghệ cao"},
        )
        self.assertEqual(result["status"], "pass")

    def test_unknown_legal_status_can_be_strict(self):
        policy = {
            "policy_id": "p1",
            "document_status": "unknown",
            "rules": {"all": [{"field": "x", "operator": "==", "value": 1}]},
        }
        with patch.object(config, "STRICT_LEGAL_STATUS", True):
            result = evaluate({"x": 1}, policy)
        self.assertEqual(result["status"], "manual_review")

    def test_application_requirement_is_preserved_without_affecting_decision(self):
        requirement = "Giải pháp chuyển đổi số phải được công bố trên cổng hoặc trang thông tin hợp lệ."
        policy = {
            "policy_id": "technology",
            "document_status": "effective",
            "rules": {"all": [{"field": "is_sme", "operator": "==", "value": True}]},
            "application_requirements": [requirement],
        }
        result = evaluate({"is_sme": True}, policy)
        self.assertEqual(result["status"], "eligible")
        self.assertEqual(result["application_requirements"], [requirement])
        self.assertEqual(result["missing_fields"], [])


if __name__ == "__main__":
    unittest.main()
