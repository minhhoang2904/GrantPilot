from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import main


RETRIEVAL_RESULT = {
    "legal_units": [
        {
            "unit_id": "law_art-1",
            "document_number": "01/2026/TEST",
            "document_title": "Văn bản thử nghiệm",
            "article": "1",
            "text": "Căn cứ thử nghiệm.",
            "source_url": "https://example.test/law.pdf",
        }
    ],
    "candidate_policy_ids": ["p1"],
    "route": "semantic_search",
    "original_query": "Có hỗ trợ không?",
    "retrieval_query": "Có hỗ trợ không?",
    "diagnostics": {},
}


class FakeRetriever:
    fpt = object()


async def collect_events(response) -> list[dict]:
    events = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        events.extend(json.loads(line) for line in chunk.splitlines() if line.strip())
    return events


class ChatStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_advisory_calls_server_c_and_emits_canonical_result(self):
        company = {
            "profile_schema_version": "company-profile-v1",
            "company_name": "Không gửi sang Server C",
            "sector": "thuong_mai_dich_vu",
        }
        eligibility = {
            "eligibility_results": [
                {
                    "policy_id": "p1",
                    "policy_name": "Hỗ trợ DNNVV",
                    "status": "needs_more_information",
                    "score": 0.5,
                    "missing_fields": ["has_coworking_contract"],
                    "reasons": ["Cần hợp đồng."],
                    "rule_errors": ["KeyError: internal_field"],
                    "sources": [RETRIEVAL_RESULT["legal_units"][0]],
                }
            ],
            "explanation": "Cần bổ sung hồ sơ.",
            "derived_facts": {
                "enterprise_size": "small",
                "is_sme": True,
                "company_age_months": 12,
            },
        }
        with (
            patch.object(main.company_service, "get_company", return_value=company),
            patch.object(
                main,
                "_run_retrieval",
                return_value=("conversation-1", [], RETRIEVAL_RESULT),
            ),
            patch.object(main.retrieval, "get_retriever", return_value=FakeRetriever()),
            patch.object(main.answer_gen, "generate_answer", return_value="Câu trả lời."),
            patch.object(
                main.eligibility_client,
                "evaluate_company",
                return_value=eligibility,
            ) as evaluate,
            patch.object(
                main.company_service,
                "append_chat_turn",
                return_value="conversation-1",
            ) as append,
        ):
            response = await main.chat_stream_endpoint(
                main.ChatStreamIn(
                    mode="advisory",
                    message="Có hỗ trợ không?",
                    conversation_id="conversation-1",
                ),
                current_email="owner@example.test",
            )
            events = await collect_events(response)

        event_types = [event["type"] for event in events]
        self.assertIn("advisory_result", event_types)
        self.assertNotIn("warning", event_types)
        advisory = next(event["data"] for event in events if event["type"] == "advisory_result")
        self.assertEqual(advisory["policies"][0]["policy_id"], "p1")
        self.assertEqual(advisory["policies"][0]["reasons"], ["Cần hợp đồng."])
        self.assertNotIn("KeyError", json.dumps(advisory, ensure_ascii=False))
        self.assertEqual(advisory["profile_features"]["company_age_months"], 12)
        sent_facts = evaluate.call_args.args[0]
        self.assertEqual(sent_facts["sector"], "thuong_mai_dich_vu")
        self.assertNotIn("company_name", sent_facts)
        assistant_turn = append.call_args_list[1].args[2]
        self.assertEqual(assistant_turn["advisory_result"], advisory)
        self.assertEqual(assistant_turn["sources"][0]["unit_id"], "law_art-1")

    async def test_server_c_failure_degrades_to_warning(self):
        company = {
            "profile_schema_version": "company-profile-v1",
            "sector": "thuong_mai_dich_vu",
        }
        with (
            patch.object(main.company_service, "get_company", return_value=company),
            patch.object(
                main,
                "_run_retrieval",
                return_value=("conversation-1", [], RETRIEVAL_RESULT),
            ),
            patch.object(main.retrieval, "get_retriever", return_value=FakeRetriever()),
            patch.object(main.answer_gen, "generate_answer", return_value="Câu trả lời."),
            patch.object(
                main.eligibility_client,
                "evaluate_company",
                side_effect=RuntimeError("Server C unavailable"),
            ),
            patch.object(
                main.company_service,
                "append_chat_turn",
                return_value="conversation-1",
            ),
        ):
            response = await main.chat_stream_endpoint(
                main.ChatStreamIn(mode="advisory", message="Có hỗ trợ không?"),
                current_email="owner@example.test",
            )
            events = await collect_events(response)

        warning = next(event for event in events if event["type"] == "warning")
        self.assertEqual(warning["code"], "ELIGIBILITY_UNAVAILABLE")
        self.assertNotIn("advisory_result", [event["type"] for event in events])

    async def test_advisory_rejects_legacy_profile_before_stream(self):
        with patch.object(
            main.company_service,
            "get_company",
            return_value={"profile_schema_version": "legacy"},
        ):
            with self.assertRaises(HTTPException) as raised:
                await main.chat_stream_endpoint(
                    main.ChatStreamIn(mode="advisory", message="Tư vấn"),
                    current_email="owner@example.test",
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, "PROFILE_UPDATE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
