from __future__ import annotations

import unittest
from unittest.mock import patch

import config
from clients import LLMClient, FptClient, PineconeDenseIndex, _decode_physical_unit_id


class LLMClientPayloadTest(unittest.TestCase):
    def test_embed_sends_correct_model(self):
        client = LLMClient(embedding_api_key="test-key")
        captured = {}

        def fake_post(url, api_key, payload):
            captured.update(url=url, payload=payload)
            return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}

        client._post = staticmethod(fake_post)
        self.assertEqual(client.embed(["xin chào"]), [[0.1, 0.2]])
        self.assertEqual(captured["payload"]["model"], config.EMBEDDING_MODEL)

    def test_fptclient_alias_is_llmclient(self):
        self.assertIs(FptClient, LLMClient)

    def test_rewrite_uses_configured_model_and_budget(self):
        client = LLMClient(embedding_api_key="test-key")
        captured = {}

        def fake_post(url, api_key, payload):
            captured.update(payload)
            return {"choices": [{"message": {"content": "Câu hỏi độc lập"}}]}

        client._post = staticmethod(fake_post)
        with (
            patch.object(config, "REWRITE_MODEL", "llama-3.3-70b-versatile"),
            patch.object(config, "REWRITE_MAX_TOKENS", 512),
            patch.object(config, "REWRITE_API_KEY", "test-key"),
        ):
            result = client.rewrite_query(
                "Thế tối đa bao nhiêu?",
                [{"role": "user", "content": "Hỗ trợ thuê văn phòng không?"}],
            )

        self.assertEqual(result, "Câu hỏi độc lập")
        self.assertEqual(captured["model"], "llama-3.3-70b-versatile")
        self.assertEqual(captured["max_tokens"], 512)
        self.assertNotIn("thinking", captured)

    def test_answer_no_glm_specific_fields(self):
        client = LLMClient(embedding_api_key="test-key")
        captured = {}

        def fake_post(url, api_key, payload):
            captured.update(payload)
            return {
                "choices": [
                    {
                        "message": {"content": "Câu trả lời có căn cứ."},
                        "finish_reason": "stop",
                    }
                ]
            }

        client._post = staticmethod(fake_post)
        evidence = [
            {
                "unit_id": "law-04_art-17",
                "document_number": "04/2017/QH14",
                "article": "17",
                "clause": "",
                "point": "",
                "text": "Nội dung căn cứ.",
            }
        ]
        with (
            patch.object(config, "ANSWER_MODEL", "llama-3.3-70b-versatile"),
            patch.object(config, "ANSWER_MAX_TOKENS", 8192),
            patch.object(config, "ANSWER_API_KEY", "test-key"),
        ):
            result = client.answer("Có được hỗ trợ không?", evidence)

        self.assertEqual(result, "Câu trả lời có căn cứ.")
        self.assertEqual(captured["model"], "llama-3.3-70b-versatile")
        self.assertEqual(captured["max_tokens"], 8192)
        self.assertNotIn("thinking", captured)
        self.assertNotIn("reasoning_effort", captured)

    def test_empty_content_is_explicit_error(self):
        client = LLMClient(embedding_api_key="test-key")

        def fake_post(url, api_key, payload):
            return {
                "choices": [
                    {
                        "message": {"content": None},
                        "finish_reason": "length",
                    }
                ]
            }

        client._post = staticmethod(fake_post)
        evidence = [
            {
                "unit_id": "law-04_art-17",
                "document_number": "04/2017/QH14",
                "article": "17",
                "text": "Nội dung căn cứ.",
            }
        ]
        with (
            patch.object(config, "ANSWER_MODEL", "llama-3.3-70b-versatile"),
            patch.object(config, "ANSWER_API_KEY", "test-key"),
        ):
            with self.assertRaisesRegex(RuntimeError, "content rỗng"):
                client.answer("Câu hỏi", evidence)

    def test_advisory_prompt_keeps_decision_fixed_and_budget_small(self):
        client = LLMClient(embedding_api_key="test-key")
        captured = {}

        def fake_post(url, api_key, payload):
            captured.update(payload)
            return {"choices": [{"message": {"content": "- Chuẩn bị hồ sơ."}}]}

        client._post = staticmethod(fake_post)
        with (
            patch.object(config, "ADVISORY_ENABLED", True),
            patch.object(config, "ADVISORY_MODEL", "llama-3.3-70b-versatile"),
            patch.object(config, "ADVISORY_MAX_TOKENS", 1200),
            patch.object(config, "ADVISORY_API_KEY", "test-key"),
        ):
            result = client.advise({"eligibility_results": [{"status": "eligible"}]})

        system_prompt = captured["messages"][0]["content"]
        self.assertEqual(result, "- Chuẩn bị hồ sơ.")
        self.assertEqual(captured["max_tokens"], 1200)
        self.assertIn("Trạng thái eligibility là kết quả cố định", system_prompt)
        self.assertIn("không thay đổi", system_prompt)
        self.assertIn("Không thêm chính sách", system_prompt)
        self.assertIn("Không nói doanh nghiệp chắc chắn", system_prompt)
        self.assertNotIn("thinking", captured)


class PineconeDenseIndexTest(unittest.TestCase):
    def test_search_prefers_original_legal_unit_id_over_physical_id(self):
        class FakeIndex:
            def query(self, **kwargs):
                return {
                    "matches": [
                        {
                            "id": "u_6c61772d30345f6172742d38",
                            "score": 0.75,
                            "metadata": {"original_unit_id": "law-04_art-8"},
                        }
                    ]
                }

        index = PineconeDenseIndex()
        index._index = FakeIndex()
        with patch.object(config, "PINECONE_API_KEY", "test-key"), patch.object(
            config, "PINECONE_INDEX_NAME", "test-index"
        ):
            self.assertEqual(index.search([0.1, 0.2], 1), [("law-04_art-8", 0.75)])

    def test_encoded_physical_id_is_reversible_fallback(self):
        value = "law-04-2017-qh14_art-12_cl-3_pt-đ"
        encoded = "u_" + value.encode("utf-8").hex()
        self.assertEqual(_decode_physical_unit_id(encoded), value)
        self.assertIsNone(_decode_physical_unit_id("unrelated-id"))


if __name__ == "__main__":
    unittest.main()
