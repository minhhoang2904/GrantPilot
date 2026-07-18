from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

import main
from main import AskIn


RETRIEVAL_RESULT = {
    "legal_units": [{"unit_id": "law_art-1", "text": "Căn cứ"}],
    "candidate_policy_ids": ["p1"],
    "route": "semantic_search",
    "original_query": "Có hỗ trợ không?",
    "retrieval_query": "Có hỗ trợ không?",
    "diagnostics": {},
}


class FakeRetriever:
    fpt = object()


class AnswerModesTest(unittest.TestCase):
    def common_patches(self):
        return (
            patch.object(main, "_run_retrieval", return_value=("thread-1", [], RETRIEVAL_RESULT)),
            patch.object(main.retrieval, "get_retriever", return_value=FakeRetriever()),
            patch.object(main.answer_gen, "generate_answer", return_value="Câu trả lời có căn cứ."),
            patch.object(main, "_persist_answer", return_value="session-1"),
        )

    def test_lookup_returns_legal_units_but_no_eligibility_rows(self):
        patches = self.common_patches()
        with patches[0], patches[1], patches[2], patches[3]:
            response = main.ask(
                AskIn(question="Có hỗ trợ không?", email="owner@example.test", mode="rag"),
                current_email="owner@example.test",
            )
        self.assertEqual(response["mode"], "lookup")
        self.assertEqual(response["legal_units"][0]["unit_id"], "law_art-1")
        self.assertEqual(response["citations"][0]["unit_id"], "law_art-1")
        self.assertEqual(response["eligibility_results"], [])
        self.assertEqual(response["results"], [])
        self.assertEqual(response["eligibility"]["diagnostics"]["skipped"], "lookup_mode")

    def test_advisory_uses_canonical_facts_and_returns_only_policy_rows(self):
        eligibility = {
            "eligibility_results": [
                {
                    "policy_id": "p1",
                    "policy_name": "Hỗ trợ DNNVV",
                    "status": "needs_more_information",
                    "missing_fields": ["is_innovative_startup"],
                    "sources": [],
                }
            ],
            "explanation": "Cần bổ sung thông tin đổi mới sáng tạo.",
            "derived_facts": {"is_innovative_startup": None},
            "derivation_lineage": {},
            "diagnostics": {},
        }
        company = {
            "profile_schema_version": "company-profile-v1",
            "company_name": "Không được gửi sang Server C",
            "sector": "thuong_mai_dich_vu",
            "has_patent": True,
        }
        patches = self.common_patches()
        with (
            patches[0], patches[1], patches[2], patches[3],
            patch.object(main.company_service, "get_company", return_value=company),
            patch.object(main.eligibility_client, "evaluate_company", return_value=eligibility) as evaluate,
        ):
            response = main.ask(
                AskIn(question="Công ty tôi có được hỗ trợ không?", email="owner@example.test", mode="eligibility"),
                current_email="owner@example.test",
            )
        sent_facts = evaluate.call_args.args[0]
        self.assertEqual(sent_facts["sector"], "thuong_mai_dich_vu")
        self.assertNotIn("company_name", sent_facts)
        self.assertNotIn("has_patent", sent_facts)
        self.assertEqual(response["mode"], "advisory")
        self.assertEqual(response["eligibility_results"][0]["policy_id"], "p1")
        self.assertEqual(response["results"][0]["status"], "partial")
        self.assertNotEqual(response["results"], response["legal_units"])
        self.assertIn("Đánh giá theo hồ sơ doanh nghiệp", response["answer"])

    def test_ask_cannot_write_another_users_history(self):
        with self.assertRaises(HTTPException) as raised:
            main.ask(
                AskIn(question="Câu hỏi", email="victim@example.test"),
                current_email="attacker@example.test",
            )
        self.assertEqual(raised.exception.status_code, 403)

    def test_advisory_requires_canonical_profile(self):
        patches = self.common_patches()
        with (
            patches[0], patches[1], patches[2], patches[3],
            patch.object(main.company_service, "get_company", return_value=None),
        ):
            with self.assertRaises(HTTPException) as raised:
                main.ask(
                    AskIn(question="Tư vấn", email="owner@example.test", mode="advisory"),
                    current_email="owner@example.test",
                )
        self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
