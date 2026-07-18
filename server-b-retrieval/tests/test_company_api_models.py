import unittest

from pydantic import ValidationError

from main import CompanyIn, CompanyUpdate


VALID = {
    "email": "owner@example.test",
    "company_name": "Công ty mẫu",
    "sector": "thuong_mai_dich_vu",
    "primary_business_activity_group": "services",
    "legal_form": "limited_liability_company",
    "province_name": "Hà Nội",
    "business_description": "Phần mềm SaaS",
    "social_insurance_employees": 8,
    "annual_revenue_vnd": 2_000_000_000,
    "total_capital_vnd": 1_000_000_000,
    "first_business_registration_date": "2023-01-15",
    "has_public_offering": False,
    "has_business_registration": True,
    "has_coworking_contract": False,
}


class CompanyApiModelTest(unittest.TestCase):
    def test_valid_payload_serializes_canonical_date_and_names(self):
        payload = CompanyIn(**VALID).model_dump(mode="json")
        self.assertEqual(payload["first_business_registration_date"], "2023-01-15")
        self.assertFalse(payload["has_public_offering"])
        self.assertNotIn("founded_year", payload)
        self.assertNotIn("has_patent", payload)

    def test_rejects_negative_money_string_boolean_and_extra_fields(self):
        for update in (
            {"annual_revenue_vnd": -1},
            {"has_public_offering": "false"},
            {"has_patent": True},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                CompanyIn(**{**VALID, **update})

    def test_coworking_cost_must_match_contract_state(self):
        with self.assertRaises(ValidationError):
            CompanyIn(**{**VALID, "coworking_monthly_cost_vnd": 3_000_000})
        accepted = CompanyIn(**{
            **VALID,
            "has_coworking_contract": True,
            "coworking_monthly_cost_vnd": 3_000_000,
        })
        self.assertEqual(accepted.coworking_monthly_cost_vnd, 3_000_000)

    def test_activity_group_must_match_sector(self):
        with self.assertRaises(ValidationError):
            CompanyIn(**{**VALID, "primary_business_activity_group": "agriculture"})

    def test_future_registration_date_is_rejected(self):
        with self.assertRaises(ValidationError):
            CompanyIn(**{**VALID, "first_business_registration_date": "2999-01-01"})

    def test_patch_preserves_explicit_null(self):
        patch = CompanyUpdate(province_code=None).model_dump(mode="json", exclude_unset=True)
        self.assertEqual(patch, {"province_code": None})
        with self.assertRaises(ValidationError):
            CompanyUpdate(company_name=None)


if __name__ == "__main__":
    unittest.main()
