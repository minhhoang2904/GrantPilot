import copy
import json
import unittest
from pathlib import Path

from golden_policy_mvp import apply_golden_overlay, golden_policies, normalize_golden_candidate
from mongo_store import _policy_row, utcnow
from pipeline import LEGAL_UNITS_PATH, POLICIES_PATH, load_sources, normalize_policy_artifact, read_jsonl
from policy_discovery import (
    CANONICAL_TOPIC_BY_POLICY,
    SCHEMA_VERSION,
    validate_discovery,
    validate_discovery_collection,
)
from policy_normalization import load_catalog, policy_hash, prepare_policy_for_ingest


class PolicyDiscoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = load_sources()
        cls.units = read_jsonl(LEGAL_UNITS_PATH)
        cls.base = json.loads(POLICIES_PATH.read_text(encoding="utf-8"))

    def test_four_golden_policies_have_canonical_discovery_metadata(self):
        policies = golden_policies()
        self.assertEqual(len(policies), 4)
        validate_discovery_collection(policies, load_catalog())
        self.assertEqual(
            {policy["policy_id"]: policy["discovery"]["topic_id"] for policy in policies},
            CANONICAL_TOPIC_BY_POLICY,
        )
        self.assertTrue(all(policy["discovery"]["schema_version"] == SCHEMA_VERSION for policy in policies))
        self.assertTrue(all(policy["discovery"]["search_terms_vi"] for policy in policies))

    def test_discovery_survives_full_ingest_without_changing_approval_hash(self):
        golden = golden_policies()
        without_discovery = copy.deepcopy(golden[0])
        without_discovery.pop("discovery")
        before = normalize_golden_candidate(without_discovery, sources=self.sources, units=self.units)
        after = normalize_golden_candidate(golden[0], sources=self.sources, units=self.units)
        self.assertEqual(policy_hash(before), policy_hash(after))
        self.assertEqual(before["normalized_rules"], after["normalized_rules"])

        rows = normalize_policy_artifact(
            apply_golden_overlay(self.base, sources=self.sources, units=self.units),
            self.units,
            self.sources,
        )
        by_id = {row["policy_id"]: row for row in rows}
        for policy in golden:
            self.assertEqual(by_id[policy["policy_id"]]["discovery"], policy["discovery"])
        self.assertEqual(len(rows), 100)
        self.assertEqual(sum(row["review_status"] == "approved" for row in rows), 4)
        self.assertEqual(sum(bool(row["eligible_for_decision"]) for row in rows), 4)

    def test_unknown_discovery_field_is_not_a_company_fact(self):
        policy = copy.deepcopy(golden_policies()[0])
        policy["discovery"]["is_sme"] = True
        row = normalize_golden_candidate(policy, sources=self.sources, units=self.units)
        self.assertEqual(row["normalized_rules"]["all"][0]["field"], "is_sme")
        self.assertNotIn("is_sme", row["normalized_rules"])
        self.assertIn("discovery_contains_company_fact", {item["code"] for item in row["validation_issues_current"]})
        self.assertEqual(row["review_status"], "rejected")

    def test_topics_outside_mvp_do_not_map_to_golden_policy(self):
        forbidden = {"tax_tndn", "natif", "corporate_income_tax", "patent", "innovative_startup"}
        self.assertTrue(forbidden.isdisjoint(set(CANONICAL_TOPIC_BY_POLICY.values())))
        policy = copy.deepcopy(golden_policies()[0])
        policy["discovery"]["topic_id"] = "tax_tndn"
        issues = validate_discovery(policy, load_catalog())
        self.assertIn("discovery_topic_invalid", {item["code"] for item in issues})
        policy = copy.deepcopy(golden_policies()[0])
        policy["discovery"]["search_terms_vi"][0] = "ưu đãi thuế TNDN"
        issues = validate_discovery(policy, load_catalog())
        self.assertIn("discovery_out_of_scope_term", {item["code"] for item in issues})

    def test_duplicate_topic_ids_fail_closed(self):
        policies = golden_policies()
        policies[1]["discovery"]["topic_id"] = policies[0]["discovery"]["topic_id"]
        with self.assertRaises(ValueError):
            validate_discovery_collection(policies, load_catalog())

    def test_discovery_is_preserved_in_mongo_payload(self):
        policy = normalize_golden_candidate(golden_policies()[0], sources=self.sources, units=self.units)
        row = _policy_row(policy, utcnow())
        self.assertEqual(row["discovery"], policy["discovery"])
        self.assertEqual(row["payload"]["discovery"], policy["discovery"])


class IngestionIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.source = {
            "document_id": "decree-80-2021-nd-cp",
            "document_number": "80/2021/NĐ-CP",
            "source_url": "https://vanban.chinhphu.vn/decree-80",
            "version": 1,
        }
        self.policy = {
            "policy_id": "integrity-test",
            "pipeline": {"document_id": self.source["document_id"]},
            "evidence_unit_ids": ["unit-1"],
            "rules": {"all": [{"field": "is_sme", "operator": "==", "value": True}]},
        }

    def test_cross_document_evidence_is_rejected(self):
        unit = {
            "unit_id": "unit-1",
            "document_id": "circular-06-2022-tt-bkhdt",
            "document_number": "06/2022/TT-BKHĐT",
            "source_url": "https://vbpl.vn/circular-06",
            "version": 1,
            "clause": "1",
        }
        row = prepare_policy_for_ingest(self.policy, source=self.source, evidence_rows=[unit])
        self.assertEqual(row["review_status"], "rejected")
        self.assertFalse(row["eligible_for_decision"])
        self.assertIn("evidence_document_mismatch", {item["code"] for item in row["validation_issues_current"]})

    def test_decree_and_circular_urls_cannot_be_swapped(self):
        unit = {
            "unit_id": "unit-1",
            "document_id": self.source["document_id"],
            "document_number": "06/2022/TT-BKHĐT",
            "source_url": "https://vbpl.vn/circular-06",
            "version": 1,
            "clause": "1",
        }
        row = prepare_policy_for_ingest(self.policy, source=self.source, evidence_rows=[unit])
        codes = {item["code"] for item in row["validation_issues_current"]}
        self.assertEqual(row["review_status"], "rejected")
        self.assertIn("evidence_document_number_mismatch", codes)
        self.assertIn("evidence_source_url_mismatch", codes)

    def test_policy_source_metadata_mismatch_is_rejected(self):
        policy = {**self.policy, "document_number": "06/2022/TT-BKHĐT", "source_url": "https://vbpl.vn/circular-06"}
        unit = {"unit_id": "unit-1", "document_id": self.source["document_id"], "version": 1, "clause": "1"}
        row = prepare_policy_for_ingest(policy, source=self.source, evidence_rows=[unit])
        codes = {item["code"] for item in row["validation_issues_current"]}
        self.assertIn("source_document_number_mismatch", codes)
        self.assertIn("source_url_mismatch", codes)
        self.assertEqual(row["review_status"], "rejected")


if __name__ == "__main__":
    unittest.main()
