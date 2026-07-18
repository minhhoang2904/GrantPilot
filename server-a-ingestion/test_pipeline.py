import unittest
from unittest.mock import patch

import ingest_mongodb
import pipeline
from pipeline import (
    FptClient,
    apply_duplicate_metadata,
    embedding_text,
    normalize_policy,
    normalize_policy_artifact,
    normalize_rules,
    parse_pages,
    policy_is_decision_eligible,
)


SOURCE = {
    "file": "sample.pdf",
    "document_id": "sample-law",
    "document_title": "Luật mẫu",
    "document_number": "01/2026/QH",
    "source_url": "https://example.test/law",
}


class ParsePagesTest(unittest.TestCase):
    def test_splits_article_clause_and_point_with_page_provenance(self):
        pages = [
            {
                "page": 1,
                "text": "CHƯƠNG II\nĐiều 22. Hỗ trợ doanh nghiệp\n1. Doanh nghiệp được hỗ trợ:\na) Tư vấn công nghệ;\nb) Đào tạo nhân lực;",
            },
            {"page": 2, "text": "2. Mức hỗ trợ do Chính phủ quy định."},
        ]

        units = parse_pages(pages, SOURCE)

        self.assertEqual([u["unit_id"] for u in units], [
            "sample-law_art-22",
            "sample-law_art-22_cl-1",
            "sample-law_art-22_cl-1_pt-a",
            "sample-law_art-22_cl-1_pt-b",
            "sample-law_art-22_cl-2",
        ])
        self.assertEqual(units[-1]["page_start"], 2)
        self.assertIn("Mức hỗ trợ", units[-1]["text"])

    def test_ignores_preamble_before_first_article(self):
        units = parse_pages([{"page": 1, "text": "QUỐC HỘI\nCăn cứ Hiến pháp\n.-Điều 1. Phạm vi"}], SOURCE)
        self.assertEqual(len(units), 1)
        self.assertNotIn("Căn cứ", units[0]["text"])

    def test_suffixes_duplicate_hierarchy_ids(self):
        pages = [{"page": 1, "text": "Điều 1. Mẫu\n1. Khoản một\n1) Dòng OCR nhầm thành khoản"}]
        units = parse_pages(pages, SOURCE)
        self.assertEqual(units[-1]["unit_id"], "sample-law_art-1_cl-1_occ-2")

    def test_handles_common_ocr_variants_in_article_heading(self):
        pages = [{"page": 1, "text": "Điều I. Phạm vi\nĐiệu 2. Đối tượng\nĐiêu 3. Nguyên tắc"}]
        units = parse_pages(pages, SOURCE)
        self.assertEqual([u["article"] for u in units], ["1", "2", "3"])


class NormalizePolicyTest(unittest.TestCase):
    def test_keeps_only_valid_evidence(self):
        policy = normalize_policy(
            {
                "policy_id": "credit-support",
                "policy_name": "Hỗ trợ tín dụng",
                "evidence_unit_ids": ["sample-law_art-22_cl-1", "made-up"],
            },
            SOURCE,
            ["sample-law_art-22_cl-1"],
        )
        self.assertEqual(policy["evidence_unit_ids"], ["sample-law_art-22_cl-1"])
        self.assertEqual(policy["policy_id"], "credit-support")
        self.assertEqual(policy["pipeline"]["document_id"], "sample-law")

    def test_does_not_expand_unmatched_evidence_to_an_entire_article(self):
        policy = normalize_policy(
            {"policy_name": "Cần review", "evidence_unit_ids": ["made-up"]},
            SOURCE,
            ["sample-law_art-22_cl-1"],
        )
        self.assertEqual(policy["evidence_unit_ids"], [])
        self.assertEqual(policy["evidence_resolution"], "unresolved")
        self.assertTrue(policy["requires_evidence_review"])
        self.assertFalse(policy["eligible_for_decision"])

    def test_article_evidence_is_fallback_and_waits_for_review(self):
        policy = normalize_policy(
            {"policy_name": "Cần review", "evidence_unit_ids": ["sample-law_art-22"]},
            SOURCE,
            ["sample-law_art-22", "sample-law_art-22_cl-1"],
        )
        self.assertEqual(policy["evidence_resolution"], "article_fallback")
        self.assertTrue(policy["requires_evidence_review"])
        self.assertFalse(policy["eligible_for_decision"])


class RuleNormalizationTest(unittest.TestCase):
    def test_both_ingest_entrypoints_share_policy_persistence_gate(self):
        self.assertIs(ingest_mongodb.persist_policies, pipeline.persist_policies)

    def test_old_artifact_is_upgraded_before_mongo_ingest(self):
        rows = normalize_policy_artifact(
            [{
                "policy_id": "old-credit",
                "policy_name": "Tín dụng",
                "pipeline": {"document_id": "sample-law"},
                "evidence_unit_ids": ["sample-law_art-22_cl-1"],
                "rules": {"all": [{"field": "is_sme", "operator": "==", "value": True}]},
            }],
            [{"document_id": "sample-law", "unit_id": "sample-law_art-22_cl-1"}],
            {"sample.pdf": SOURCE},
        )
        self.assertEqual(rows[0]["policy_rule_schema_version"], "policy-rule-schema-v1")
        self.assertIn("canonical_policy_key", rows[0])
        self.assertEqual(rows[0]["review_status"], "candidate")
        self.assertEqual(rows[0]["evidence_resolution"], "article_fallback")
        self.assertFalse(rows[0]["eligible_for_decision"])

    def test_keeps_contains_distinct_from_in(self):
        catalog = {"fields": {"sample_text": {"type": "string", "source": "direct", "operators": ["contains", "in"], "aliases": ["ngành nghề"]}}}
        contains, contains_warnings, contains_status = normalize_rules(
            {"all": [{"field": "ngành nghề", "operator": "contains", "value": "công nghệ"}]}, catalog
        )
        in_rule, in_warnings, in_status = normalize_rules(
            {"all": [{"field": "ngành nghề", "operator": "in", "value": ["công nghệ", "nông nghiệp"]}]}, catalog
        )
        self.assertEqual(contains["all"][0]["operator"], "contains")
        self.assertEqual(in_rule["all"][0]["operator"], "in")
        self.assertFalse(contains_warnings)
        self.assertFalse(in_warnings)
        self.assertIsNone(contains_status)
        self.assertIsNone(in_status)

    def test_preserves_nested_all_any_structure(self):
        rules, warnings, status = normalize_rules(
            {
                "all": [
                    {"field": "is_sme", "operator": "==", "value": True},
                    {"any": [
                        {"field": "has_collateral", "operator": "==", "value": True},
                        {"field": "has_feasible_business_plan", "operator": "==", "value": True},
                    ]},
                ]
            }
        )
        self.assertEqual(rules["all"][1]["any"][1]["field"], "has_feasible_business_plan")
        self.assertFalse(warnings)
        self.assertIsNone(status)

    def test_vietnamese_alias_with_diacritics_maps_only_to_explicit_fact(self):
        rules, warnings, status = normalize_rules(
            {"all": [{"field": "quy mô doanh nghiệp", "operator": "==", "value": "micro"}]}
        )
        rule = rules["all"][0]
        self.assertEqual(rule["field"], "enterprise_size")
        self.assertEqual(rule["fact_source"], "derived")
        self.assertFalse(warnings)
        self.assertIsNone(status)

    def test_unknown_field_requires_schema_mapping_not_extra_attributes(self):
        _, warnings, status = normalize_rules(
            {"all": [{"field": "loại doanh nghiệp", "operator": "==", "value": "startup"}]}
        )
        self.assertEqual(status, "needs_schema_mapping")
        self.assertIn("not in Fact Catalog", warnings[0])

    def test_wrong_type_or_operator_is_rejected(self):
        _, _, status = normalize_rules(
            {"all": [{"field": "is_sme", "operator": "contains", "value": True}]}
        )
        self.assertEqual(status, "rejected")
        _, _, status = normalize_rules(
            {"all": [{"field": "legal_form", "operator": ">=", "value": "startup"}]}
        )
        self.assertEqual(status, "rejected")

    def test_only_approved_precise_policy_can_be_used_for_decision(self):
        policy = normalize_policy(
            {
                "policy_id": "credit",
                "evidence_unit_ids": ["sample-law_art-22_cl-1"],
                "rules": {"all": [{"field": "is_sme", "operator": "==", "value": True}]},
            },
            SOURCE,
            ["sample-law_art-22_cl-1"],
        )
        self.assertFalse(policy_is_decision_eligible(policy))
        policy["review_status"] = policy["review"]["status"] = "approved"
        self.assertFalse(policy_is_decision_eligible(policy))

    def test_semantic_duplicates_are_grouped_even_with_different_ids(self):
        base = {
            "evidence_unit_ids": ["sample-law_art-22_cl-1"],
            "rules": {"all": [{"field": "is_sme", "operator": "==", "value": True}]},
            "benefit_calculator": {"type": "credit"},
        }
        first = normalize_policy({**base, "policy_id": "credit-a"}, SOURCE, base["evidence_unit_ids"])
        second = normalize_policy({**base, "policy_id": "credit-b"}, SOURCE, base["evidence_unit_ids"])
        rows = apply_duplicate_metadata([first, second])
        self.assertEqual(rows[0]["duplicate_group_id"], rows[1]["duplicate_group_id"])
        self.assertEqual(sum(row["review_status"] == "superseded" for row in rows), 1)


class FptClientTest(unittest.TestCase):
    @patch.dict("os.environ", {"FPT_API_KEY": "test-only-key"})
    def test_policy_request_uses_locked_model_config(self):
        client = FptClient()
        captured = {}

        def fake_post(endpoint, payload):
            captured.update({"endpoint": endpoint, "payload": payload})
            return {
                "choices": [{"message": {"content": '{"policies": []}'}}]
            }

        client._post = fake_post
        client.extract_policies(
            SOURCE,
            [{"unit_id": "sample-law_art-22", "text": "Điều 22. Hỗ trợ doanh nghiệp"}],
        )

        self.assertEqual(captured["endpoint"], "chat/completions")
        self.assertEqual(captured["payload"]["model"], "Llama-3.3-70B-Instruct")
        self.assertEqual(captured["payload"]["temperature"], 0)
        self.assertEqual(captured["payload"]["response_format"], {"type": "json_object"})
        self.assertEqual(captured["payload"]["max_tokens"], 3000)


class EmbeddingTextTest(unittest.TestCase):
    def test_includes_document_and_article_context(self):
        unit = {
            "document_title": "Luật mẫu",
            "document_number": "01/2026/QH",
            "article": "17",
            "article_title": "Hỗ trợ startup",
            "clause": "2",
            "point": "b",
            "text": "Nội dung hỗ trợ.",
        }
        text = embedding_text(unit)
        self.assertIn("Luật mẫu, số 01/2026/QH", text)
        self.assertIn("Điều 17. Hỗ trợ startup", text)
        self.assertIn("Khoản 2, điểm b", text)


if __name__ == "__main__":
    unittest.main()
