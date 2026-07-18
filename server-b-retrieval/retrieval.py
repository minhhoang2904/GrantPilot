"""Hybrid legal retrieval: routing -> Pinecone + BM25 -> RRF -> rerank.

Module khong tao Pinecone index va khong upsert. Server A so huu indexing;
Server B chi query va hydrate text goc tu MongoDB (JSONL la offline fallback).
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any, Protocol

import config
from clients import FptClient, PineconeDenseIndex
from legal_store import build_legal_unit_store, embedding_text, normalize_text
from schemas import RankedCandidate, RetrievalResult, Route


LEGAL_REF_RE = re.compile(
    r"(?:([0-9]{1,3}/[0-9]{4}/[A-ZĐ-]+).*?)?"
    r"\bđi[eềệ]u\s+([0-9]+)"
    r"(?:\s*[,;]?\s*kho[aả]n\s+([0-9]+))?"
    r"(?:\s*[,;]?\s*đi[eể]m\s+([a-zđ]))?",
    re.IGNORECASE,
)
FOLLOW_UP_RE = re.compile(
    r"^(thế|vậy|còn|nó|cái đó|chính sách đó|trường hợp đó|mức tối đa|bao nhiêu|"
    r"cần giấy tờ gì|nộp ở đâu)\b",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


class DenseIndex(Protocol):
    @property
    def enabled(self) -> bool: ...

    def search(self, vector: list[float], top_k: int, filters: dict | None = None) -> list[tuple[str, float]]: ...


class BM25Index:
    """BM25 index nho trong RAM; dung rank-bm25 neu da cai, co fallback offline."""

    def __init__(self, units: list[dict]) -> None:
        self.unit_ids = [unit["unit_id"] for unit in units]
        self.corpus = [self.tokenize(embedding_text(unit)) for unit in units]
        self._engine = None
        try:
            from rank_bm25 import BM25Okapi

            self._engine = BM25Okapi(self.corpus) if self.corpus else None
        except ImportError:
            self._engine = None
        self._idf = self._build_idf(self.corpus)

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return TOKEN_RE.findall(normalize_text(text))

    @staticmethod
    def _build_idf(corpus: list[list[str]]) -> dict[str, float]:
        n = len(corpus)
        df = Counter(token for doc in corpus for token in set(doc))
        return {token: math.log(1 + (n - count + 0.5) / (count + 0.5)) for token, count in df.items()}

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        tokens = self.tokenize(query)
        if not tokens or not self.corpus:
            return []
        if self._engine is not None:
            scores = [float(score) for score in self._engine.get_scores(tokens)]
        else:
            scores = self._fallback_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        return [(self.unit_ids[i], score) for i, score in ranked[:top_k] if score > 0]

    def _fallback_scores(self, query_tokens: list[str]) -> list[float]:
        scores = []
        avgdl = sum(map(len, self.corpus)) / max(len(self.corpus), 1)
        for doc in self.corpus:
            counts = Counter(doc)
            score = 0.0
            for token in query_tokens:
                tf = counts.get(token, 0)
                if not tf:
                    continue
                denom = tf + 1.5 * (1 - 0.75 + 0.75 * len(doc) / max(avgdl, 1))
                score += self._idf.get(token, 0.0) * (tf * 2.5 / denom)
            scores.append(score)
        return scores


def detect_route(query: str, has_history: bool) -> tuple[Route, dict[str, str]]:
    match = LEGAL_REF_RE.search(query)
    if match:
        return "exact_citation", {
            "document_number": match.group(1) or "",
            "article": match.group(2) or "",
            "clause": match.group(3) or "",
            "point": (match.group(4) or "").lower(),
        }
    if has_history and FOLLOW_UP_RE.search(query.strip()):
        return "follow_up", {}
    return "semantic_search", {}


def reciprocal_rank_fusion(
    dense: list[tuple[str, float]],
    sparse: list[tuple[str, float]],
    *,
    rrf_k: int,
) -> list[RankedCandidate]:
    merged: dict[str, RankedCandidate] = defaultdict(dict)
    for rank, (unit_id, score) in enumerate(dense, start=1):
        merged[unit_id].update(
            unit_id=unit_id,
            dense_score=score,
            dense_rank=rank,
            fusion_score=merged[unit_id].get("fusion_score", 0.0) + 1 / (rrf_k + rank),
        )
    for rank, (unit_id, score) in enumerate(sparse, start=1):
        merged[unit_id].setdefault("unit_id", unit_id)
        merged[unit_id]["bm25_score"] = score
        merged[unit_id]["bm25_rank"] = rank
        merged[unit_id]["fusion_score"] = (
            merged[unit_id].get("fusion_score", 0.0) + 1 / (rrf_k + rank)
        )
    return sorted(merged.values(), key=lambda c: c.get("fusion_score", 0.0), reverse=True)


# ── LegalRetriever ────────────────────────────────────────────────────────────

class LegalRetriever:
    """Hybrid retriever: dense (Pinecone) + sparse (BM25) -> RRF -> rerank."""

    def __init__(self) -> None:
        self.fpt = FptClient()
        self._dense = PineconeDenseIndex()
        self._store: Any = None
        self._bm25: BM25Index | None = None
        self._bm25_loaded = False

    @property
    def store(self) -> Any:
        if self._store is None:
            self._store = build_legal_unit_store()
        return self._store

    def _get_bm25(self) -> BM25Index | None:
        """BM25 chỉ khả dụng khi backend JSONL (toàn bộ units trong RAM)."""
        if self._bm25_loaded:
            return self._bm25
        self._bm25_loaded = True
        units = getattr(self.store, "units", None)
        if units:
            self._bm25 = BM25Index(units)
        return self._bm25

    def retrieve(
        self,
        question: str,
        *,
        history: list[dict[str, str]] | None = None,
        top_k: int = 5,
    ) -> RetrievalResult:
        history = history or []
        route, filters = detect_route(question, bool(history))
        diagnostics: dict[str, Any] = {}

        # Rewrite câu hỏi follow-up thành câu độc lập
        if route == "follow_up" and history:
            retrieval_query = self.fpt.rewrite_query(question, history)
        else:
            retrieval_query = question

        legal_units: list[dict[str, Any]] = []

        if route == "exact_citation":
            legal_units = self.store.exact_lookup(**filters)
            # Thêm context cấp cha (điều/khoản)
            seen = {u.get("unit_id") for u in legal_units}
            for unit in list(legal_units):
                for parent in self.store.parents(unit):
                    pid = parent.get("unit_id")
                    if pid and pid not in seen:
                        legal_units.append(parent)
                        seen.add(pid)
            legal_units = legal_units[:top_k]
            diagnostics["exact_hits"] = len(legal_units)

        else:
            # Dense search (Pinecone)
            dense_results: list[tuple[str, float]] = []
            if self._dense.enabled and self.fpt.enabled:
                try:
                    vectors = self.fpt.embed([retrieval_query])
                    dense_results = self._dense.search(vectors[0], top_k=config.DENSE_TOP_K)
                except Exception as exc:
                    diagnostics["dense_error"] = str(exc)

            # Sparse search (BM25, JSONL backend only)
            sparse_results: list[tuple[str, float]] = []
            bm25 = self._get_bm25()
            if bm25:
                sparse_results = bm25.search(retrieval_query, top_k=config.BM25_TOP_K)

            diagnostics.update(
                dense_count=len(dense_results),
                sparse_count=len(sparse_results),
            )

            # Fuse + hydrate
            if dense_results or sparse_results:
                fused = reciprocal_rank_fusion(
                    dense_results, sparse_results, rrf_k=config.RRF_K
                )
                top_ids = [c["unit_id"] for c in fused[: config.FUSION_TOP_K]]
                hydrated = self.store.get_many(top_ids)
            else:
                hydrated = []

            diagnostics["hydrated_count"] = len(hydrated)

            # Rerank
            if hydrated and self.fpt.enabled and config.FPT_RERANK_MODEL:
                docs = [embedding_text(u) for u in hydrated]
                try:
                    ranked = self.fpt.rerank(retrieval_query, docs, top_n=top_k)
                    scored = [(hydrated[idx], score) for idx, score in ranked]
                    if config.RERANK_MIN_SCORE >= 0:
                        scored = [(u, s) for u, s in scored if s >= config.RERANK_MIN_SCORE]
                    for u, score in scored:
                        u["rerank_score"] = score
                    legal_units = [u for u, _ in scored]
                except Exception as exc:
                    diagnostics["rerank_error"] = str(exc)
                    legal_units = hydrated[:top_k]
            else:
                legal_units = hydrated[:top_k]

        # Tìm candidate policy IDs từ unit_ids
        unit_ids = [u.get("unit_id") for u in legal_units if u.get("unit_id")]
        candidate_policy_ids = self.store.policy_ids_for(unit_ids) if unit_ids else []

        return RetrievalResult(
            original_query=question,
            retrieval_query=retrieval_query,
            route=route,
            legal_units=legal_units,
            candidate_policy_ids=candidate_policy_ids,
            diagnostics=diagnostics,
        )


# ── Singleton + helpers ───────────────────────────────────────────────────────

_retriever: LegalRetriever | None = None


def get_retriever() -> LegalRetriever:
    global _retriever
    if _retriever is None:
        _retriever = LegalRetriever()
    return _retriever


def search_legal_units(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Wrapper cho /search endpoint."""
    return get_retriever().retrieve(query, top_k=top_k)["legal_units"]
