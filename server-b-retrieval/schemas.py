"""Kieu du lieu cong khai cua retrieval pipeline."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


Route = Literal["exact_citation", "follow_up", "semantic_search"]


class ChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class RankedCandidate(TypedDict, total=False):
    unit_id: str
    dense_score: float
    bm25_score: float
    fusion_score: float
    rerank_score: float
    dense_rank: int
    bm25_rank: int


class RetrievedUnit(TypedDict, total=False):
    document_id: str
    document_title: str
    document_number: str
    source_file: str
    source_url: str
    chapter: str
    section: str
    article: str
    article_title: str
    clause: str
    point: str
    page_start: int
    page_end: int
    text: str
    unit_id: str

    score: float
    retrieval_mode: str
    context_units: list[dict[str, Any]]


class RetrievalResult(TypedDict):
    original_query: str
    retrieval_query: str
    route: Route
    legal_units: list[RetrievedUnit]
    candidate_policy_ids: list[str]
    diagnostics: dict[str, Any]
