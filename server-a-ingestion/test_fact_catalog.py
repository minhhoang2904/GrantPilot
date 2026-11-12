import json
import re
import unittest
import unicodedata
from pathlib import Path


CATALOG_PATH = Path(__file__).with_name("fact-catalog-v1.json")
ALLOWED_TYPES = {"boolean", "integer", "number", "enum", "string"}
ALLOWED_OPERATORS = {"==", "!=", ">", ">=", "<", "<=", "in", "not_in", "exists", "contains"}
AMBIGUOUS_LEGACY_FIELDS = {
    "loai_doanh_nghiep",
    "loai_hinh_doanh_nghiep",
    "nganh_hoat_dong",
    "has_patent",
}
POLICY_PARAMETER_FIELDS = {
    "chi_phi",
    "gia_tri_hop_dong",
    "noi_dung_ho_tro",
    "loai_ho_tro",
    "dieu_kien_ho_tro",
    "loai_khoa_dao_tao",
    "hinh_thuc_dao_tao",
    "ngan_sach_nha_nuoc",
}


def field_token(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


class FactCatalogContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.fields = cls.catalog["fields"]

    def test_catalog_identity_and_missing_semantics_are_locked(self):
        self.assertEqual(self.catalog["schema_version"], "fact-catalog-v1")
        self.assertEqual(self.catalog["catalog_version"], "1.0.0")
        self.assertEqual(self.catalog["status"], "approved")
        self.assertIsNone(self.catalog["semantics"]["missing_value"])
        self.assertEqual(self.catalog["semantics"]["missing_behavior"], "unknown")
        self.assertEqual(self.catalog["semantics"]["boolean_values"], [True, False, None])

    def test_every_field_has_a_valid_machine_contract(self):
        for name, definition in self.fields.items():
            with self.subTest(field=name):
                self.assertIn(definition["type"], ALLOWED_TYPES)
                self.assertIn(definition["source"], {"direct", "derived"})
                self.assertTrue(definition["nullable"])
                self.assertEqual(definition["missing_behavior"], "unknown")
                self.assertTrue(set(definition["operators"]) <= ALLOWED_OPERATORS)
                self.assertTrue(set(definition["source_kinds"]) <= set(self.catalog["source_kinds"]))
                if definition["type"] == "enum":
                    self.assertTrue(definition.get("enum"))
                for dependency in definition.get("depends_on", []):
                    self.assertIn(dependency, self.fields)
                if definition["source"] == "derived":
                    self.assertTrue(definition.get("depends_on"))
                    self.assertTrue(definition.get("derivation", {}).get("function"))
                    self.assertTrue(definition.get("derivation", {}).get("version"))

    def test_normalized_aliases_are_unambiguous(self):
        owners = {}
        for field, definition in self.fields.items():
            for alias in [field, *(definition.get("aliases") or [])]:
                token = field_token(alias)
                previous = owners.get(token)
                self.assertIn(previous, {None, field}, f"Alias '{alias}' maps to both {previous} and {field}")
                owners[token] = field

    def test_ambiguous_legacy_fields_are_not_spelling_aliases(self):
        aliases = {
            field_token(alias)
            for field, definition in self.fields.items()
            for alias in [field, *(definition.get("aliases") or [])]
        }
        self.assertFalse({field_token(value) for value in AMBIGUOUS_LEGACY_FIELDS} & aliases)

    def test_policy_parameters_are_not_company_facts(self):
        self.assertFalse(POLICY_PARAMETER_FIELDS & set(self.fields))

    def test_core_profile_and_derived_facts_are_present(self):
        expected = {
            "sector",
            "legal_form",
            "social_insurance_employees",
            "annual_revenue_vnd",
            "total_capital_vnd",
            "first_business_registration_date",
            "has_public_offering",
            "company_age_months",
            "enterprise_size",
            "is_sme",
            "innovation_selection_criteria_met",
            "is_innovative_startup",
        }
        self.assertTrue(expected <= set(self.fields))


if __name__ == "__main__":
    unittest.main()
