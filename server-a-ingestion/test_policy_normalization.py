import unittest
from policy_normalization import apply_duplicates, normalize_rules, prepare_policy_for_ingest


class PolicyNormalizationTest(unittest.TestCase):
    def test_value_aware_enterprise_and_unit_migrations(self):
        rules, issues, _ = normalize_rules({"all": [
            {"field": "loai_doanh_nghiep", "operator": "==", "value": "DNNVV"},
            {"field": "company_age_years", "operator": "<=", "value": 5},
        ]})
        self.assertEqual(rules["all"][0]["field"], "is_sme")
        self.assertEqual(rules["all"][1]["field"], "company_age_months")
        self.assertEqual(rules["all"][1]["value"], 60)
        self.assertFalse(issues)

    def test_policy_parameter_is_not_company_fact(self):
        _, issues, parameters = normalize_rules({"all": [{"field": "chi_phi", "operator": "<=", "value": 10}]})
        self.assertEqual(issues[0]["code"], "policy_parameter")
        self.assertEqual(parameters[0]["raw_condition"]["field"], "chi_phi")

    def test_legacy_approval_is_invalidated_without_provenance(self):
        policy = prepare_policy_for_ingest({"policy_id": "p", "review_status": "approved", "rules": {"all": [{"field": "is_sme", "operator": "==", "value": True}]}})
        self.assertEqual(policy["review_status"], "candidate")
        self.assertIn("approval_invalidated", [x["code"] for x in policy["validation_issues_current"]])

    def test_duplicate_direction_points_secondary_to_primary(self):
        first = {"policy_id": "a", "canonical_policy_key": "same", "review_status": "candidate", "is_current": True}
        second = {"policy_id": "b", "canonical_policy_key": "same", "review_status": "candidate", "is_current": True}
        apply_duplicates([second, first])
        self.assertEqual(second["superseded_by_policy_id"], "a")
        self.assertNotIn("supersedes_policy_id", second)

    def test_startup_public_offering_rule_uses_any(self):
        rules, issues, _ = normalize_rules({"all": [
            {"field": "legal_form", "operator": "!=", "value": "joint_stock_company"},
            {"field": "has_public_offering", "operator": "==", "value": False},
        ]})
        self.assertFalse(issues)
        self.assertIn("any", rules["all"][0])


if __name__ == "__main__": unittest.main()
