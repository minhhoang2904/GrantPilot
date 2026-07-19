from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import config
from clients import FptClient, PineconeDenseIndex, _decode_physical_unit_id


class FptClientPayloadTest(unittest.TestCase):
    def test_embed_does_not_depend_on_answer_state(self):
        client = FptClient(api_key="test-key")
        captured = {}

        def fake_post(url, payload):
            captured.update(url=url, payload=payload)
            return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}

        client._post = fake_post
        self.assertEqual(client.embed(["xin chào"]), [[0.1, 0.2]])
        self.assertEqual(captured["payload"]["model"], config.FPT_EMBEDDING_MODEL)

    def test_rewrite_uses_fast_model_and_small_budget(self):
        client = FptClient(api_key="test-key")
        captured = {}

        def fake_chat(payload):
            captured.update(payload)
            return {"choices": [{"message": {"content": "Câu hỏi độc lập"}}]}

        client._post_chat = fake_chat
        with (
            patch.object(config, "FPT_QUERY_REWRITE_MODEL", "DeepSeek-V4-Flash"),
            patch.object(config, "FPT_QUERY_REWRITE_MAX_TOKENS", 512),
        ):
            result = client.rewrite_query(
                "Thế tối đa bao nhiêu?",
                [{"role": "user", "content": "Hỗ trợ thuê văn phòng không?"}],
            )

        self.assertEqual(result, "Câu hỏi độc lập")
        self.assertEqual(captured["model"], "DeepSeek-V4-Flash")
        self.assertEqual(captured["max_tokens"], 512)
        self.assertNotIn("thinking", captured)

    def test_glm_answer_disables_thinking_and_uses_safe_budget(self):
        client = FptClient(api_key="test-key")
        captured = {}

        def fake_chat(payload):
            captured.update(payload)
            return {
                "choices": [
                    {
                        "message": {"content": "Câu trả lời có căn cứ."},
                        "finish_reason": "stop",
                    }
                ]
            }

        client._post_chat = fake_chat
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
            patch.object(config, "FPT_ANSWER_MODEL", "GLM-5.2"),
            patch.object(config, "FPT_ANSWER_MAX_TOKENS", 8192),
            patch.object(config, "FPT_ANSWER_THINKING", "disabled"),
            patch.object(config, "FPT_ANSWER_REASONING_EFFORT", "none"),
        ):
            result = client.answer("Có được hỗ trợ không?", evidence)

        self.assertEqual(result, "Câu trả lời có căn cứ.")
        self.assertEqual(captured["model"], "GLM-5.2")
        self.assertEqual(captured["max_tokens"], 8192)
        self.assertEqual(captured["thinking"], {"type": "disabled", "clear_thinking": True})
        self.assertEqual(captured["reasoning_effort"], "none")

    def test_empty_glm_content_is_explicit_error(self):
        client = FptClient(api_key="test-key")
        client._post_chat = lambda payload: {
            "choices": [
                {
                    "message": {"content": None, "reasoning_content": "đang suy luận"},
                    "finish_reason": "length",
                }
            ]
        }
        evidence = [
            {
                "unit_id": "law-04_art-17",
                "document_number": "04/2017/QH14",
                "article": "17",
                "text": "Nội dung căn cứ.",
            }
        ]
        with patch.object(config, "FPT_ANSWER_MODEL", "GLM-5.2"):
            with self.assertRaisesRegex(RuntimeError, "content rỗng"):
                client.answer("Câu hỏi", evidence)

    def test_advisory_prompt_keeps_decisions_immutable_and_uses_small_budget(self):
        client = FptClient(api_key="test-key")
        captured = {}

        def fake_chat(payload):
            captured.update(payload)
            return {"choices": [{"message": {"content": "- Nên ưu tiên đào tạo."}}]}

        client._post_chat = fake_chat
        advisory_payload = {
            "question": "Tôi nên làm gì?",
            "eligibility_results": [{"policy_name": "Đào tạo", "status": "eligible"}],
        }
        with (
            patch.object(config, "FPT_ADVISORY_ENABLED", True),
            patch.object(config, "FPT_ADVISORY_MODEL", "GLM-5.2"),
            patch.object(config, "FPT_ADVISORY_MAX_TOKENS", 1600),
        ):
            result = client.advise(advisory_payload)

        self.assertEqual(result, "- Nên ưu tiên đào tạo.")
        self.assertIn("tuyệt đối không thay đổi", captured["messages"][0]["content"])
        self.assertIn("Không thêm chính sách", captured["messages"][0]["content"])
        self.assertIn("không được nói doanh nghiệp đã hoặc đang được nhận", captured["messages"][0]["content"])
        self.assertEqual(json.loads(captured["messages"][1]["content"]), advisory_payload)
        self.assertEqual(captured["temperature"], 0.2)
        self.assertEqual(captured["max_tokens"], 1600)
        self.assertEqual(captured["thinking"]["type"], config.FPT_ANSWER_THINKING)


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
