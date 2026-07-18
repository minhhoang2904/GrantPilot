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
    if rows:
        try:
            response = requests.post(
                f"{SERVER_A_URL}/internal/legal-units/batch",
                json={"unit_ids": [row["id"] for row in rows]},
                timeout=30,
            )
            response.raise_for_status()
            hydrated = {item["unit_id"]: item for item in response.json().get("items", [])}
            for row in rows:
                unit = hydrated.get(row["id"])
                if unit:
                    row["content"] = unit.get("text", "")
                    row["summary"] = unit.get("normalized_text", row["content"])
                    row["version"] = unit.get("version")
                    row["is_current"] = unit.get("is_current")
        except Exception:
            pass
    return rows


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


_STOP_WORDS = {"là", "và", "của", "cho", "có", "được", "trong", "với", "các", "không", "này", "về", "tôi", "bạn", "gì", "để"}


def _tokenize(query: str) -> list[str]:
    tokens = [t.strip("?.,!") for t in query.split()]
    return [t for t in tokens if len(t) >= 2 and t.lower() not in _STOP_WORDS]


def _legacy_search(query: str, top_k: int) -> list[dict[str, Any]]:
    tokens = _tokenize(query)
    if not tokens:
        return []

    fields = ["title", "summary", "content", "category"]
    clauses = " OR ".join(f"{f} LIKE ?" for f in fields for _ in tokens)
    params = [f"%{t}%" for _ in fields for t in tokens]
    params.append(top_k)

    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM policies WHERE {clauses} ORDER BY updated_at DESC LIMIT ?",
            params,
        ).fetchall()
    finally:
        conn.close()

    seen: set[str] = set()
    results = []
    for row in rows:
        d = dict(row)
        if d["id"] not in seen:
            seen.add(d["id"])
            results.append(d)
    return results


def search_policies(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Dùng semantic Pinecone khi đã cấu hình; SQLite là fallback khi chưa ingest."""
    if os.getenv("PINECONE_API_KEY") and os.getenv("PINECONE_INDEX_NAME"):
        return _semantic_search(query, top_k)
    return _legacy_search(query, top_k)


def get_policy_by_id(policy_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None
