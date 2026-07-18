from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from legal_store import LegalUnitStore
from retrieval import HybridRetriever, detect_route, reciprocal_rank_fusion


UNITS = [
    {
        "document_id": "law-04",
        "document_title": "Luật Hỗ trợ doanh nghiệp nhỏ và vừa",
        "document_number": "04/2017/QH14",
        "source_file": "data/raw/04.pdf",
        "source_url": "https://example.test/law",
        "chapter": "IV",
        "section": "",
        "article": "17",
        "article_title": "Hỗ trợ doanh nghiệp nhỏ và vừa khởi nghiệp sáng tạo",
        "clause": "",
        "point": "",
        "page_start": 7,
        "page_end": 7,
        "text": "Điều 17. Hỗ trợ doanh nghiệp nhỏ và vừa khởi nghiệp sáng tạo",
        "unit_id": "law-04_art-17",
    },
    {
        "document_id": "law-04",
        "document_title": "Luật Hỗ trợ doanh nghiệp nhỏ và vừa",
        "document_number": "04/2017/QH14",
        "source_file": "data/raw/04.pdf",
        "source_url": "https://example.test/law",
        "chapter": "IV",
        "section": "",
        "article": "17",
        "article_title": "Hỗ trợ doanh nghiệp nhỏ và vừa khởi nghiệp sáng tạo",
        "clause": "2",
        "point": "",
        "page_start": 8,
        "page_end": 8,
        "text": "2. Nội dung hỗ trợ bao gồm:",
        "unit_id": "law-04_art-17_cl-2",
    },
    {
        "document_id": "law-04",
        "document_title": "Luật Hỗ trợ doanh nghiệp nhỏ và vừa",
        "document_number": "04/2017/QH14",
        "source_file": "data/raw/04.pdf",
        "source_url": "https://example.test/law",
        "chapter": "IV",
        "section": "",
        "article": "17",
        "article_title": "Hỗ trợ doanh nghiệp nhỏ và vừa khởi nghiệp sáng tạo",
        "clause": "2",
        "point": "b",
        "page_start": 8,
        "page_end": 8,
        "text": "b) Hỗ trợ sử dụng cơ sở ươm tạo và khu làm việc chung;",
        "unit_id": "law-04_art-17_cl-2_pt-b",
    },
    {
        "document_id": "law-04",
        "document_title": "Luật Hỗ trợ doanh nghiệp nhỏ và vừa",
        "document_number": "04/2017/QH14",
        "source_file": "data/raw/04.pdf",
        "source_url": "https://example.test/law",
        "chapter": "II",
        "section": "",
        "article": "8",
        "article_title": "Hỗ trợ tiếp cận tín dụng",
        "clause": "",
        "point": "",
        "page_start": 3,
        "page_end": 3,
        "text": "Doanh nghiệp được hỗ trợ tiếp cận tín dụng.",
        "unit_id": "law-04_art-8",
    },
]


class FakeFpt:
    enabled = True

    def embed(self, texts):
        return [[0.1, 0.2] for _ in texts]

    def rerank(self, query, documents, top_n):
        ranked = sorted(
            enumerate(documents),
            key=lambda item: 1 if "khu làm việc chung" in item[1] else 0,
            reverse=True,
        )
        return [(index, 0.95 if rank == 0 else 0.2) for rank, (index, _) in enumerate(ranked[:top_n])]

    def rewrite_query(self, question, history):
        return "Mức hỗ trợ thuê khu làm việc chung là bao nhiêu?"


class FakeDense:
    enabled = True

    def search(self, vector, top_k, filters=None):
        return [
            ("law-04_art-17_cl-2_pt-b", 0.91),
            ("law-04_art-8", 0.4),
            ("unknown-unit", 0.99),
        ][:top_k]


def make_store(tmp_path: Path) -> LegalUnitStore:
    units_path = tmp_path / "legal_units.jsonl"
    units_path.write_text(
        "".join(json.dumps(unit, ensure_ascii=False) + "\n" for unit in UNITS),
        encoding="utf-8",
    )
    policies_path = tmp_path / "policies.json"
    policies_path.write_text(
        json.dumps(
            [
                {
                    "policy_id": "coworking_support",
                    "evidence_unit_ids": ["law-04_art-17_cl-2_pt-b"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return LegalUnitStore(units_path, policies_path)


class RetrievalTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = make_store(Path(self.temp_dir.name))
        self.retriever = HybridRetriever(self.store, fpt=FakeFpt(), dense_index=FakeDense())

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_citation_hydrates_parent_context_and_policy(self):
        result = self.retriever.retrieve("Điều 17 khoản 2 điểm b quy định gì?")

        self.assertEqual(result["route"], "exact_citation")
        self.assertEqual(
            [unit["unit_id"] for unit in result["legal_units"]],
            ["law-04_art-17_cl-2_pt-b"],
        )
        self.assertEqual(
            [unit["unit_id"] for unit in result["legal_units"][0]["context_units"]],
            ["law-04_art-17", "law-04_art-17_cl-2"],
        )
        self.assertEqual(result["candidate_policy_ids"], ["coworking_support"])

    def test_hybrid_filters_unknown_pinecone_ids_and_reranks(self):
        result = self.retriever.retrieve("hỗ trợ thuê văn phòng cho startup", top_k=2)

        self.assertEqual(result["route"], "semantic_search")
        self.assertEqual(result["legal_units"][0]["unit_id"], "law-04_art-17_cl-2_pt-b")
        self.assertTrue(all(unit["unit_id"] != "unknown-unit" for unit in result["legal_units"]))
        self.assertEqual(result["legal_units"][0]["retrieval_mode"], "hybrid_rerank")

    def test_follow_up_is_rewritten_before_search(self):
        history = [{"role": "user", "content": "Có hỗ trợ thuê khu làm việc chung không?"}]
        result = self.retriever.retrieve("Thế mức tối đa là bao nhiêu?", history=history)

        self.assertEqual(result["route"], "follow_up")
        self.assertEqual(result["retrieval_query"], "Mức hỗ trợ thuê khu làm việc chung là bao nhiêu?")

    def test_rrf_uses_rank_not_raw_score(self):
        results = reciprocal_rank_fusion(
            [("a", 0.1), ("b", 0.09)],
            [("b", 100.0), ("c", 90.0)],
            rrf_k=60,
        )
        self.assertEqual(results[0]["unit_id"], "b")

    def test_router_does_not_rewrite_self_contained_query(self):
        route, reference = detect_route("Điều 8 quy định gì?", has_history=True)
        self.assertEqual(route, "exact_citation")
        self.assertEqual(reference["article"], "8")


if __name__ == "__main__":
    unittest.main()
