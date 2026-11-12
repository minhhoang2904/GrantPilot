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

    def test_negated_dnnvv_is_not_migrated_to_positive_is_sme(self):
        rules, issues, _ = normalize_rules({"all": [{"field": "loai_doanh_nghiep", "operator": "!=", "value": "DNNVV"}]})
        self.assertEqual(rules["all"][0]["field"], "loai_doanh_nghiep")
        self.assertEqual(issues[0]["code"], "unknown_field")

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

    def test_nested_rules_count_as_mapped_in_dry_run(self):
        from policy_normalization import dry_run
        report = dry_run([{"policy_id":"p","pipeline":{"document_id":"d"},"rules":{"all":[{"field":"is_sme","operator":"==","value":True},{"any":[{"field":"has_collateral","operator":"==","value":True},{"field":"has_credit_rating","operator":"==","value":True}]}]}}], {"d":{"document_id":"d"}}, [])
        self.assertEqual(report["conditions_mapped"], 3)

    def test_recurring_issue_is_not_marked_resolved(self):
        raw={"policy_id":"p","rules":{"all":[{"field":"unknown","operator":"==","value":True}]}}
        first=prepare_policy_for_ingest(raw)
        second=prepare_policy_for_ingest({**raw,"validation_issues_current":first["validation_issues_current"],"validation_history":first["validation_history"]})
        self.assertFalse(any(x.get("resolved_at") for x in second["validation_history"] if x.get("code")=="unknown_field"))


if __name__ == "__main__": unittest.main()
