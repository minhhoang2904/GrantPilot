import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import golden_policy_mvp
from golden_policy_mvp import StaleGoldenApprovalError, apply_golden_overlay
from pipeline import LEGAL_UNITS_PATH, POLICIES_PATH, load_sources, normalize_policy_artifact, persist_policies, read_jsonl
from policy_normalization import approval_valid, load_catalog

POLICIES = json.loads((Path(__file__).resolve().parent / "data" / "golden_policies_mvp.json").read_text(encoding="utf-8"))


def evaluate(node, profile):
    if "all" in node:
        results = [evaluate(child, profile) for child in node["all"]]
        return False if False in results else (None if None in results else True)
    if "any" in node:
        results = [evaluate(child, profile) for child in node["any"]]
        return True if True in results else (None if None in results else False)
    value = profile.get(node["field"])
    if value is None:
        return None
    if node["operator"] == "==":
        return value == node["value"]
    if node["operator"] == "in":
        return value in node["value"]
    raise AssertionError(f"Unsupported test operator: {node['operator']}")


class GoldenPolicyMvpTest(unittest.TestCase):
    def matches(self, profile):
        return {policy["policy_id"] for policy in POLICIES if evaluate(policy["rules"], profile) is True}

    def test_sme_services_gets_general_information_online_and_digital_support(self):
        expected = {POLICIES[0]["policy_id"], POLICIES[1]["policy_id"], POLICIES[3]["policy_id"]}
        self.assertEqual(self.matches({"is_sme": True, "primary_business_activity_group": "services"}), expected)

    def test_sme_manufacturing_gets_all_four_policies(self):
        self.assertEqual(self.matches({"is_sme": True, "primary_business_activity_group": "manufacturing"}), {p["policy_id"] for p in POLICIES})

    def test_large_enterprise_gets_no_mvp_policy(self):
        self.assertEqual(self.matches({"is_sme": False, "primary_business_activity_group": "manufacturing"}), set())

    def test_missing_facts_do_not_become_eligible(self):
        self.assertEqual(self.matches({}), set())

    def test_full_ingest_overlay_keeps_only_four_reviewed_policies_approved(self):
        base = json.loads(POLICIES_PATH.read_text(encoding="utf-8"))
        units = read_jsonl(LEGAL_UNITS_PATH)
        sources = load_sources()
        rows = normalize_policy_artifact(apply_golden_overlay(base, sources=sources, units=units), units, sources)
        approved = [row for row in rows if row["review_status"] == "approved"]
        eligible = [row for row in rows if row["eligible_for_decision"]]
        self.assertEqual(len(rows), 100)
        self.assertEqual({row["policy_id"] for row in approved}, {policy["policy_id"] for policy in POLICIES})
        self.assertEqual({row["policy_id"] for row in eligible}, {policy["policy_id"] for policy in POLICIES})
        self.assertTrue(all(approval_valid(row, load_catalog()) for row in approved))
        technology = next(row for row in rows if row["policy_id"] == "circular_06_2022_tt_bkhdt_ho_tro_cong_nghe_48284a5c")
        self.assertIn("application_requirements", technology)
        self.assertNotIn("publication_requirement", technology["rules"])

    def test_stale_rule_rejects_manifest_without_generating_a_new_hash(self):
        base = json.loads(POLICIES_PATH.read_text(encoding="utf-8"))
        units = read_jsonl(LEGAL_UNITS_PATH)
        sources = load_sources()
        golden = golden_policy_mvp.golden_policies()
        manifest_before = copy.deepcopy(golden_policy_mvp.approval_manifest())
        golden[0]["rules"]["all"][0]["value"] = False
        with patch("golden_policy_mvp.golden_policies", return_value=golden):
            with self.assertRaises(StaleGoldenApprovalError):
                apply_golden_overlay(base, sources=sources, units=units)
        self.assertEqual(golden_policy_mvp.approval_manifest(), manifest_before)

    def test_reviewed_at_is_stable_across_repeated_full_ingest(self):
        base = json.loads(POLICIES_PATH.read_text(encoding="utf-8"))
        units = read_jsonl(LEGAL_UNITS_PATH)
        sources = load_sources()
        first = apply_golden_overlay(base, sources=sources, units=units)
        second = apply_golden_overlay(base, sources=sources, units=units)
        golden_ids = {policy["policy_id"] for policy in POLICIES}
        first_times = {row["policy_id"]: row["approval"]["reviewed_at"] for row in first if row["policy_id"] in golden_ids}
        second_times = {row["policy_id"]: row["approval"]["reviewed_at"] for row in second if row["policy_id"] in golden_ids}
        self.assertEqual(first_times, second_times)

    def test_policy_mongo_persistence_always_applies_golden_overlay(self):
        client, db = Mock(), Mock()
        with patch("mongo_store.database", return_value=(client, db)), patch("mongo_store.ensure_indexes"), \
             patch("mongo_store.ingest_policies", return_value={"total": 100}) as ingest, \
             patch("golden_policy_mvp.apply_golden_overlay", return_value=[{"policy_id": "golden"}]) as overlay:
            persist_policies([{"policy_id": "raw"}])
        overlay.assert_called_once_with([{"policy_id": "raw"}], db=db)
        ingest.assert_called_once_with(db, [{"policy_id": "golden"}])
        client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
