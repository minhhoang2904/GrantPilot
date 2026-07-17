import unittest
from unittest.mock import patch

from pipeline import FptClient, normalize_policy, parse_pages


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
        self.assertTrue(policy["policy_id"].startswith("sample_law_credit_support_"))
        self.assertEqual(policy["pipeline"]["document_id"], "sample-law")

    def test_repairs_policy_without_matching_evidence(self):
        policy = normalize_policy(
            {"policy_name": "Cần review", "evidence_unit_ids": ["made-up"]},
            SOURCE,
            ["sample-law_art-22_cl-1"],
        )
        self.assertEqual(policy["evidence_unit_ids"], ["sample-law_art-22_cl-1"])
        self.assertTrue(policy["review"]["evidence_repaired"])


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


if __name__ == "__main__":
    unittest.main()
