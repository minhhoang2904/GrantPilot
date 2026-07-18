"""
server-b-retrieval / company_service.py

CRUD cho hồ sơ công ty (collection: companies) và lịch sử chat (collection:
chat_history) lưu trong MongoDB.

Kết nối qua biến môi trường:
  MONGODB_URI  — mặc định mongodb://localhost:27017
  MONGODB_DB   — mặc định policy_advisor

Schema companies (canonical Company Profile v1):
  {
    email: str (unique index, PK logic),
    company_name: str,                    -- chỉ hiển thị

    profile_schema_version: "company-profile-v1",
    <canonical Fact Catalog user-input fields>,
    fact_provenance: {field: {source_kind, status, asserted_at}},

    created_at: datetime,
    updated_at: datetime,
  }

Schema chat_history:
  {
    email: str (unique index),
    sessions: [
      {
        session_id: str (uuid),
        started_at: datetime,
        turns: [
          { role: "user"|"assistant", content: str, results: list|None, ts: datetime }
        ]
      }
    ]
  }
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import certifi
from pymongo import MongoClient, ASCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from company_profile import (
    PROFILE_SCHEMA_VERSION,
    canonicalize_company,
    new_company_document,
    provenance_updates,
    writable_values,
)

_MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
_MONGO_DB = os.environ.get("MONGODB_DB", "policy_advisor")

_client: Optional[MongoClient] = None  # type: ignore[type-arg]

def _get_db():
    global _client
    if _client is None:
        _client = MongoClient(_MONGO_URI, tlsCAFile=certifi.where())
    return _client[_MONGO_DB]


def _companies() -> Collection:  # type: ignore[type-arg]
    col = _get_db()["companies"]
    col.create_index([("email", ASCENDING)], unique=True)
    return col


def _chat_history() -> Collection:  # type: ignore[type-arg]
    col = _get_db()["chat_history"]
    col.create_index([("email", ASCENDING)], unique=True)
    return col


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    """Chuyển ObjectId và datetime thành string để trả về qua API."""
    out = {k: v for k, v in doc.items() if k != "_id"}
    for k, v in out.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    return canonicalize_company(out)


# ---------------------------------------------------------------------------
# Company CRUD
# ---------------------------------------------------------------------------

def get_company(email: str) -> Optional[dict[str, Any]]:
    doc = _companies().find_one({"email": email})
    return _serialize(doc) if doc else None


def create_company(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = new_company_document(data, now)
    try:
        _companies().insert_one(doc)
    except DuplicateKeyError:
        # POST is idempotent for the authenticated owner and upgrades legacy
        # records when onboarding is completed again.
        return update_company(data["email"], data)  # type: ignore[return-value]
    return _serialize(doc)


def update_company(email: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
    updates = writable_values(data)
    if not updates:
        return get_company(email)
    now = datetime.now(timezone.utc)
    updates.update({
        "profile_schema_version": PROFILE_SCHEMA_VERSION,
        "updated_at": now,
    })
    for field, metadata in provenance_updates(data, now).items():
        updates[f"fact_provenance.{field}"] = metadata
    result = _companies().find_one_and_update(
        {"email": email},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    return _serialize(result) if result else None


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

def get_chat_history(email: str) -> list[dict[str, Any]]:
    doc = _chat_history().find_one({"email": email})
    if not doc:
        return []
    sessions = doc.get("sessions", [])
    for session in sessions:
        if isinstance(session.get("started_at"), datetime):
            session["started_at"] = session["started_at"].isoformat()
        for turn in session.get("turns", []):
            if isinstance(turn.get("ts"), datetime):
                turn["ts"] = turn["ts"].isoformat()
    return sessions


def append_chat_turn(
    email: str,
    session_id: Optional[str],
    turn: dict[str, Any],
) -> str:
    """Thêm một lượt hội thoại vào session (tạo session mới nếu cần).

    Trả về session_id thực tế được dùng.
    """
    now = datetime.now(timezone.utc)
    turn["ts"] = now

    col = _chat_history()

    col.update_one(
        {"email": email},
        {"$setOnInsert": {"email": email, "sessions": []}},
        upsert=True,
    )

    if session_id:
        result = col.update_one(
            {"email": email, "sessions.session_id": session_id},
            {"$push": {"sessions.$.turns": turn}},
        )
        if result.modified_count:
            return session_id

    new_sid = session_id or str(uuid.uuid4())
    col.update_one(
        {"email": email},
        {
            "$push": {
                "sessions": {
                    "session_id": new_sid,
                    "started_at": now,
                    "turns": [turn],
                }
            }
        },
    )
    return new_sid
