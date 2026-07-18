from __future__ import annotations

import unittest
from datetime import date

from eligibility_service import EligibilityService


class FakeRepository:
    def get_policies(self, policy_ids=None, require_evidence=True):
        policies = [
            {
                "policy_id": "p1",
                "policy_name": "Hỗ trợ DNNVV",
                "document_status": "effective",
                "evidence_unit_ids": ["law_art-1"],
                "rules": {"all": [{"field": "is_sme", "operator": "==", "value": True}]},
            },
            {
                "policy_id": "p2",
                "policy_name": "Hỗ trợ startup sáng tạo",
                "document_status": "effective",
                "evidence_unit_ids": ["law_art-2"],
                "rules": {
                    "all": [
                        {"field": "is_innovative_startup", "operator": "==", "value": True}
                    ]
                },
            },
        ]
        return [policy for policy in policies if not policy_ids or policy["policy_id"] in policy_ids]

    def get_evidence(self, unit_ids):
        return [
            {
                "unit_id": unit_id,
                "document_number": "01/2026/TEST",
                "article": "1",
                "source_url": "https://example.test",
            }
            for unit_id in unit_ids
        ]


class FakeExplainer:
    def explain(self, profile, results, evidence):
        return "Giải thích không thay đổi status."


class EligibilityServiceTest(unittest.TestCase):
    def test_service_derives_profile_and_attaches_sources(self):
        service = EligibilityService(FakeRepository(), FakeExplainer())
        response = service.evaluate(
            {
                "sector": "thuong_mai_dich_vu",
                "social_insurance_employees": 5,
                "annual_revenue_vnd": 1_000_000_000,
                "first_business_registration_date": "2023-01-15",
                "legal_form": "limited_liability_company",
                "has_public_offering": False,
            },
            candidate_policy_ids=["p1", "p2"],
            evaluation_date=date(2026, 7, 19),
        )
        by_id = {result["policy_id"]: result for result in response["eligibility_results"]}
        self.assertEqual(by_id["p1"]["status"], "eligible")
        self.assertEqual(by_id["p2"]["status"], "needs_more_information")
        self.assertEqual(by_id["p1"]["sources"][0]["unit_id"], "law_art-1")
        self.assertEqual(response["derived_facts"]["enterprise_size"], "micro")
        self.assertIsNone(response["derived_facts"]["is_innovative_startup"])
        self.assertEqual(response["explanation"], "Giải thích không thay đổi status.")

    def test_unknown_candidate_is_reported(self):
        service = EligibilityService(FakeRepository(), FakeExplainer())
        response = service.evaluate({}, candidate_policy_ids=["missing"])
        self.assertEqual(response["diagnostics"]["excluded_candidate_policy_ids"], ["missing"])


if __name__ == "__main__":
    unittest.main()
