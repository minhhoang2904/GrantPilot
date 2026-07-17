"""
server-b-retrieval / retrieval.py

Tra cứu chính sách liên quan tới câu hỏi của người dùng.

Hiện tại dùng keyword-matching đơn giản trên SQLite (title/summary/content/category).
TODO: nâng cấp lên semantic search (embeddings + chroma_db) khi cần độ chính xác cao hơn.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("POLICY_DB_PATH", BASE_DIR.parent / "shared" / "policy.db"))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


_STOP_WORDS = {"là", "và", "của", "cho", "có", "được", "trong", "với", "các", "không", "này", "về", "tôi", "bạn", "gì", "để"}

def _tokenize(query: str) -> list[str]:
    """Split query into significant tokens (≥2 chars, not stop-words)."""
    tokens = [t.strip("?.,!") for t in query.split()]
    return [t for t in tokens if len(t) >= 2 and t.lower() not in _STOP_WORDS]


def search_policies(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Tìm các policy có chứa từ khoá trong title/summary/content/category.

    Tách query thành từng token rồi OR-match từng cái — tránh dùng toàn bộ
    câu như một LIKE pattern duy nhất (không bao giờ khớp).
    """
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

    # Deduplicate (a row may match multiple tokens)
    seen: set[str] = set()
    results = []
    for row in rows:
        d = dict(row)
        if d["id"] not in seen:
            seen.add(d["id"])
            results.append(d)
    return results


def get_policy_by_id(policy_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None
