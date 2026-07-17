"""
server-a-ingestion / ingest.py

Nạp dữ liệu chính sách từ policy.json vào shared/policy.db (SQLite),
tạo schema nếu chưa tồn tại (từ shared/schema.sql), và upsert từng policy.

Chạy: python ingest.py
"""

import json
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SHARED_DIR = Path(os.environ.get("SHARED_DIR", BASE_DIR.parent / "shared"))
DB_PATH = Path(os.environ.get("POLICY_DB_PATH", SHARED_DIR / "policy.db"))
SCHEMA_PATH = SHARED_DIR / "schema.sql"
POLICY_JSON_PATH = BASE_DIR / "policy.json"


def load_schema(conn: sqlite3.Connection) -> None:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy schema tại {SCHEMA_PATH}")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_policies() -> list[dict]:
    if not POLICY_JSON_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy {POLICY_JSON_PATH}")
    with POLICY_JSON_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def upsert_policy(conn: sqlite3.Connection, policy: dict) -> None:
    conn.execute(
        """
        INSERT INTO policies (
            id, title, summary, content, category,
            issuing_agency, effective_date, source_url, eligibility_criteria,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            summary=excluded.summary,
            content=excluded.content,
            category=excluded.category,
            issuing_agency=excluded.issuing_agency,
            effective_date=excluded.effective_date,
            source_url=excluded.source_url,
            eligibility_criteria=excluded.eligibility_criteria,
            updated_at=datetime('now')
        """,
        (
            policy["id"],
            policy["title"],
            policy.get("summary"),
            policy.get("content"),
            policy.get("category"),
            policy.get("issuing_agency"),
            policy.get("effective_date"),
            policy.get("source_url"),
            json.dumps(policy.get("eligibility_criteria", {}), ensure_ascii=False),
        ),
    )


def main() -> None:
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    policies = load_policies()

    conn = sqlite3.connect(DB_PATH)
    try:
        load_schema(conn)
        for policy in policies:
            upsert_policy(conn, policy)
        conn.commit()
        print(f"Đã nạp {len(policies)} policy vào {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
