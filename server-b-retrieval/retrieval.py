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
        merged[unit_id].update(
            unit_id=unit_id,
            bm25_score=score,
            bm25_rank=rank,
            fusion_score=merged[unit_id].get("fusion_score", 0.0) + 1 / (rrf_k + rank),
        )
    return sorted(merged.values(), key=lambda item: item.get("fusion_score", 0.0), reverse=True)


class HybridRetriever:
    def __init__(
        self,
        store: Any,
        *,
        fpt: FptClient | None = None,
        dense_index: DenseIndex | None = None,
    ) -> None:
        self.store = store
        self.fpt = fpt or FptClient()
        self.dense_index = dense_index or PineconeDenseIndex()
        self.bm25 = BM25Index(store.units)

    def retrieve(
        self,
        query: str,
        *,
        history: list[dict[str, str]] | None = None,
        top_k: int = config.RERANK_TOP_K,
    ) -> RetrievalResult:
        history = history or []
        route, reference = detect_route(query, bool(history))
        retrieval_query = query
        diagnostics: dict[str, Any] = {"dense_error": None, "rerank_error": None}

        if route == "exact_citation":
            exact = self.store.exact_lookup(**reference)
            selected = [self._hydrate(unit, score=1.0, mode="exact") for unit in exact[:top_k]]
            return self._result(query, retrieval_query, route, selected, diagnostics)

        if route == "follow_up":
            retrieval_query = self.fpt.rewrite_query(query, history)

        dense: list[tuple[str, float]] = []
        if self.dense_index.enabled and self.fpt.enabled:
            try:
                vector = self.fpt.embed([retrieval_query])[0]
                dense = self.dense_index.search(vector, config.DENSE_TOP_K)
                hydrated_ids = {
                    unit["unit_id"] for unit in self.store.get_many(uid for uid, _ in dense)
                }
                dense = [(uid, score) for uid, score in dense if uid in hydrated_ids]
            except Exception as exc:  # de BM25 fallback van phuc vu request
                diagnostics["dense_error"] = f"{type(exc).__name__}: {exc}"

        sparse = self.bm25.search(retrieval_query, config.BM25_TOP_K)
        candidates = reciprocal_rank_fusion(dense, sparse, rrf_k=config.RRF_K)[: config.FUSION_TOP_K]
        candidates = self._rerank(retrieval_query, candidates, diagnostics)
        selected = self._select(candidates, top_k)
        units = [
            self._hydrate(
                self.store.by_id[candidate["unit_id"]],
                score=float(candidate.get("rerank_score", candidate.get("fusion_score", 0.0))),
                mode="hybrid_rerank" if "rerank_score" in candidate else "hybrid_rrf",
            )
            for candidate in selected
        ]
        diagnostics.update(
            dense_count=len(dense),
            bm25_count=len(sparse),
            fusion_count=len(candidates),
        )
        return self._result(query, retrieval_query, route, units, diagnostics)

    def _rerank(
        self,
        query: str,
        candidates: list[RankedCandidate],
        diagnostics: dict[str, Any],
    ) -> list[RankedCandidate]:
        if not candidates or not self.fpt.enabled:
            return candidates
        documents = [embedding_text(self.store.by_id[item["unit_id"]]) for item in candidates]
        try:
            ranking = self.fpt.rerank(query, documents, min(config.RERANK_TOP_K * 3, len(documents)))
        except Exception as exc:
            diagnostics["rerank_error"] = f"{type(exc).__name__}: {exc}"
            return candidates
        out = []
        for index, score in ranking:
            if not 0 <= index < len(candidates):
                continue
            item = dict(candidates[index])
            item["rerank_score"] = score
            out.append(item)
        return out or candidates

    def _select(self, candidates: list[RankedCandidate], top_k: int) -> list[RankedCandidate]:
        selected = []
        per_article: Counter[tuple[str, str]] = Counter()
        for candidate in candidates:
            score = float(candidate.get("rerank_score", candidate.get("fusion_score", 0.0)))
            if "rerank_score" in candidate and score < config.RERANK_MIN_SCORE:
                continue
            unit = self.store.by_id.get(candidate["unit_id"])
            if not unit:
                continue
            group = (unit.get("document_id", ""), unit.get("article", ""))
            if per_article[group] >= config.MAX_RESULTS_PER_ARTICLE:
                continue
            per_article[group] += 1
            selected.append(candidate)
            if len(selected) >= top_k:
                break
        return selected

    def _hydrate(self, unit: dict, *, score: float, mode: str) -> dict:
        out = dict(unit)
        out["score"] = round(score, 6)
        out["retrieval_mode"] = mode
        out["context_units"] = [dict(parent) for parent in self.store.parents(unit)]
        return out

    def _result(
        self,
        original_query: str,
        retrieval_query: str,
        route: Route,
        units: list[dict],
        diagnostics: dict[str, Any],
    ) -> RetrievalResult:
        unit_ids: list[str] = []
        for unit in units:
            unit_ids.append(unit["unit_id"])
            unit_ids.extend(context["unit_id"] for context in unit.get("context_units", []))
        return {
            "original_query": original_query,
            "retrieval_query": retrieval_query,
            "route": route,
            "legal_units": units,
            "candidate_policy_ids": self.store.policy_ids_for(dict.fromkeys(unit_ids)),
            "diagnostics": diagnostics,
        }


_default_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = HybridRetriever(build_legal_unit_store())
    return _default_retriever


def search_legal_units(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Backward-compatible wrapper cho GET /search."""
    return get_retriever().retrieve(query, top_k=top_k)["legal_units"]
