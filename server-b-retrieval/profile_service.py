"""
server-b-retrieval / profile_service.py

CRUD hồ sơ doanh nghiệp (profiles) trong shared/policy.db.
"""

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("POLICY_DB_PATH", BASE_DIR.parent / "shared" / "policy.db"))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_profile(data: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO profiles (
                id, business_name, industry, business_type,
                num_employees, province, annual_revenue, founded_year, extra_attributes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                data.get("business_name"),
                data.get("industry"),
                data.get("business_type"),
                data.get("num_employees"),
                data.get("province"),
                data.get("annual_revenue"),
                data.get("founded_year"),
                json.dumps(data.get("extra_attributes", {}), ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_profile(profile_id)


def get_profile(profile_id: str) -> Optional[dict[str, Any]]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    profile = dict(row)
    profile["extra_attributes"] = json.loads(profile.get("extra_attributes") or "{}")
    return profile


def update_profile(profile_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
    existing = get_profile(profile_id)
    if existing is None:
        return None

    merged = {**existing, **data}
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE profiles
            SET business_name=?, industry=?, business_type=?, num_employees=?,
                province=?, annual_revenue=?, founded_year=?, extra_attributes=?,
                updated_at=datetime('now')
            WHERE id = ?
            """,
            (
                merged.get("business_name"),
                merged.get("industry"),
                merged.get("business_type"),
                merged.get("num_employees"),
                merged.get("province"),
                merged.get("annual_revenue"),
                merged.get("founded_year"),
                json.dumps(merged.get("extra_attributes", {}), ensure_ascii=False),
                profile_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_profile(profile_id)
