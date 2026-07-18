import unittest
from datetime import date
import json
from pathlib import Path

from profile_features import DERIVATION_VERSIONS, derive_enterprise_size, derive_profile_facts


class ProfileFeaturesTest(unittest.TestCase):
    def test_derives_complete_innovative_startup_profile(self):
        facts, lineage = derive_profile_facts({
            "sector": "thuong_mai_dich_vu",
            "social_insurance_employees": 8,
            "annual_revenue_vnd": 2_000_000_000,
            "total_capital_vnd": 2_000_000_000,
            "first_business_registration_date": "2023-01-15",
            "legal_form": "limited_liability_company",
            "has_public_offering": False,
            "has_valid_invention_patent": True,
        }, as_of=date(2026, 7, 19))
        self.assertEqual(facts["company_age_months"], 42)
        self.assertEqual(facts["enterprise_size"], "micro")
        self.assertTrue(facts["is_sme"])
        self.assertTrue(facts["innovation_selection_criteria_met"])
        self.assertTrue(facts["is_innovative_startup"])
        self.assertEqual(lineage["is_innovative_startup"]["version"], "1.0.0")

    def test_missing_innovation_evidence_stays_unknown(self):
        facts, _ = derive_profile_facts({
            "sector": "thuong_mai_dich_vu",
            "social_insurance_employees": 8,
            "annual_revenue_vnd": 2_000_000_000,
            "first_business_registration_date": "2023-01-15",
            "legal_form": "limited_liability_company",
            "has_public_offering": False,
        }, as_of=date(2026, 7, 19))
        self.assertIsNone(facts["innovation_selection_criteria_met"])
        self.assertIsNone(facts["is_innovative_startup"])

    def test_any_verified_selection_method_is_sufficient(self):
        facts, _ = derive_profile_facts({
            "has_valid_invention_patent": False,
            "has_valid_innovation_award": False,
            "has_innovative_startup_council_approval": True,
        }, as_of=date(2026, 7, 19))
        self.assertTrue(facts["innovation_selection_criteria_met"])

    def test_all_selection_methods_false_is_false(self):
        selection_fields = {
            "has_valid_invention_patent": False,
            "has_valid_innovation_award": False,
            "has_valid_science_technology_certificate": False,
            "has_valid_high_tech_certificate": False,
            "has_qualifying_startup_fund_investment": False,
            "has_qualifying_startup_support_commitment": False,
            "has_innovative_startup_council_approval": False,
        }
        facts, _ = derive_profile_facts(selection_fields, as_of=date(2026, 7, 19))
        self.assertFalse(facts["innovation_selection_criteria_met"])
        self.assertFalse(facts["is_innovative_startup"])

    def test_missing_alternative_financial_measure_does_not_guess_large(self):
        self.assertIsNone(derive_enterprise_size({
            "sector": "thuong_mai_dich_vu",
            "social_insurance_employees": 80,
            "annual_revenue_vnd": 400_000_000_000,
            "total_capital_vnd": None,
        }))

    def test_employee_limit_can_prove_large_without_financial_guess(self):
        self.assertEqual(derive_enterprise_size({
            "sector": "thuong_mai_dich_vu",
            "social_insurance_employees": 101,
            "annual_revenue_vnd": 1_000_000_000,
        }), "large")

    def test_invalid_financial_value_does_not_get_ignored(self):
        self.assertIsNone(derive_enterprise_size({
            "sector": "thuong_mai_dich_vu",
            "social_insurance_employees": 8,
            "annual_revenue_vnd": -1,
            "total_capital_vnd": 2_000_000_000,
        }))

    def test_founded_year_is_not_used_as_registration_date(self):
        facts, _ = derive_profile_facts({"founded_year": 2023}, as_of=date(2026, 7, 19))
        self.assertIsNone(facts["company_age_months"])

    def test_derivation_versions_match_fact_catalog(self):
        path = Path(__file__).resolve().parents[1] / "server-a-ingestion" / "fact-catalog-v1.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        catalog_versions = {
            field: definition["derivation"]["version"]
            for field, definition in catalog["fields"].items()
            if definition.get("source") == "derived"
        }
        self.assertEqual(DERIVATION_VERSIONS, catalog_versions)


if __name__ == "__main__":
    unittest.main()
