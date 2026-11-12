import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from company_profile import (
    PROFILE_SCHEMA_VERSION,
    USER_INPUT_FACT_FIELDS,
    canonicalize_company,
    decision_facts,
    new_company_document,
)


class CompanyProfileContractTest(unittest.TestCase):
    def test_user_input_fields_match_fact_catalog(self):
        path = Path(__file__).resolve().parents[2] / "server-a-ingestion" / "fact-catalog-v1.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        expected = {
            field for field, definition in catalog["fields"].items()
            if definition.get("source") == "direct"
            and "user_input" in definition.get("source_kinds", [])
        }
        self.assertEqual(USER_INPUT_FACT_FIELDS, expected)

    def test_safe_legacy_names_are_exposed_without_unsafe_inference(self):
        company = canonicalize_company({
            "is_public_offering": False,
            "product_type": "SaaS",
            "province": "Hà Nội",
            "founded_year": 2023,
            "has_patent": True,
            "business_type": "startup",
        })
        self.assertFalse(company["has_public_offering"])
        self.assertEqual(company["business_description"], "SaaS")
        self.assertEqual(company["province_name"], "Hà Nội")
        self.assertNotIn("first_business_registration_date", company)
        self.assertNotIn("has_valid_invention_patent", company)
        self.assertNotIn("legal_form", company)

    def test_new_document_tracks_user_input_provenance(self):
        timestamp = datetime(2026, 7, 19, tzinfo=timezone.utc)
        document = new_company_document({
            "email": "owner@example.test",
            "company_name": "Công ty mẫu",
            "has_public_offering": False,
            "province_code": None,
        }, timestamp)
        self.assertEqual(document["profile_schema_version"], PROFILE_SCHEMA_VERSION)
        self.assertEqual(document["fact_provenance"]["has_public_offering"]["status"], "accepted")
        self.assertEqual(document["fact_provenance"]["province_code"]["status"], "missing")

    def test_decision_projection_excludes_identity_and_legacy_claims(self):
        facts = decision_facts({
            "company_name": "Công ty mẫu",
            "business_description": "SaaS",
            "has_patent": True,
            "sector": "thuong_mai_dich_vu",
        })
        self.assertEqual(facts["sector"], "thuong_mai_dich_vu")
        self.assertNotIn("company_name", facts)
        self.assertNotIn("business_description", facts)
        self.assertNotIn("has_patent", facts)


if __name__ == "__main__":
    unittest.main()
