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


def search_policies(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Tìm các policy có chứa từ khoá trong title/summary/content/category.

    Đây là baseline đơn giản; có thể thay bằng semantic search sau này
    mà không cần đổi interface (vẫn nhận query, trả list[dict] policy).
    """
    like_query = f"%{query.strip()}%"
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM policies
            WHERE title LIKE ? OR summary LIKE ? OR content LIKE ? OR category LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (like_query, like_query, like_query, like_query, top_k),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_policy_by_id(policy_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None
