"""Semantic retrieval trên Pinecone, có SQLite fallback cho legacy."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("POLICY_DB_PATH", BASE_DIR.parent / "shared" / "policy.db"))
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "legal_units")
SERVER_A_URL = os.getenv("SERVER_A_URL", "http://localhost:8000").rstrip("/")
FPT_BASE_URL = os.getenv("FPT_BASE_URL", "https://mkp-api.fptcloud.com").rstrip("/")
EMBEDDING_MODEL = os.getenv("FPT_EMBEDDING_MODEL", "Vietnamese_Embedding")


def _query_embedding(query: str) -> list[float]:
    api_key = os.getenv("FPT_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("FPT_API_KEY chưa được đặt cho Server B")
    response = requests.post(
        f"{FPT_BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": EMBEDDING_MODEL, "input": [query], "encoding_format": "float"},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def _semantic_search(query: str, top_k: int) -> list[dict[str, Any]]:
    try:
        from pinecone import Pinecone
    except ImportError as exc:
        raise RuntimeError("Thiếu pinecone. Chạy: pip install -r requirements.txt") from exc
    api_key = os.getenv("PINECONE_API_KEY", "").strip()
    index_name = os.getenv("PINECONE_INDEX_NAME", "").strip()
    index_host = os.getenv("PINECONE_INDEX_HOST", "").strip()
    if not api_key or not index_name:
        raise RuntimeError("Cần đặt PINECONE_API_KEY và PINECONE_INDEX_NAME")
    pc = Pinecone(api_key=api_key)
    index = pc.Index(host=index_host) if index_host else pc.Index(index_name)
    embedding = _query_embedding(query)
    result = index.query(vector=embedding, top_k=top_k, include_metadata=True, namespace=PINECONE_NAMESPACE)
    rows = []
    for match in result.matches:
        metadata = dict(match.metadata or {})
        unit_id = metadata.get("original_unit_id", match.id)
        document = metadata.pop("text", "")
        distance = match.score
        rows.append(
            {
                "id": unit_id,
                "title": f"{metadata.get('document_number', '')} {metadata.get('article_title', '')}".strip(),
                "summary": document,
                "content": document,
                "category": "legal_unit",
                "source_url": metadata.get("source_url", ""),
                "source_file": metadata.get("source_file", ""),
                "page_start": metadata.get("page_start"),
                "page_end": metadata.get("page_end"),
                "document_id": metadata.get("document_id", ""),
                "document_number": metadata.get("document_number", ""),
                "article": metadata.get("article", ""),
                "clause": metadata.get("clause", ""),
                "point": metadata.get("point", ""),
                "distance": distance,
            }
        )
    if rows:
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
    return rows


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _legacy_search(query: str, top_k: int) -> list[dict[str, Any]]:
    like_query = f"%{query.strip()}%"
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM policies
            WHERE title LIKE ? OR summary LIKE ? OR content LIKE ? OR category LIKE ?
            ORDER BY updated_at DESC LIMIT ?""",
            (like_query, like_query, like_query, like_query, top_k),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


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
