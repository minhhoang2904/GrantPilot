"""
server-b-retrieval / company_service.py

CRUD cho hồ sơ công ty (collection: companies) và lịch sử chat (collection:
chat_history) lưu trong MongoDB.

Kết nối qua biến môi trường:
  MONGODB_URI  — mặc định mongodb://localhost:27017
  MONGODB_DB   — mặc định policy_advisor

Schema companies (mirror shared/schema.sql profiles):
  {
    email: str (unique index, PK logic),
    company_name: str,                    -- chỉ hiển thị

    # tầng 0: phân hạng DNNVV
    sector: str | None,                   -- enum: nong_lam_ngu_nghiep | cong_nghiep_xay_dung | thuong_mai_dich_vu
    social_insurance_employees: int|None, -- BHXH, không phải tổng nhân sự
    annual_revenue_vnd: int | None,
    total_capital_vnd: int | None,

    # tầng 1: tư cách
    founded_year: int | None,             -- lưu NĂM (vd: 2019), không phải số tuổi
    is_public_offering: bool | None,
    product_type: str | None,
    has_patent: bool | None,

    # địa bàn
    province: str | None,

    # tầng 2: hồ sơ chứng từ
    has_coworking_contract: bool | None,
    has_business_registration: bool | None,

    # chi phí thực tế
    coworking_monthly_cost_vnd: int | None,

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
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

_MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
_MONGO_DB = os.environ.get("MONGODB_DB", "policy_advisor")

_client: Optional[MongoClient] = None  # type: ignore[type-arg]

# Fields allowed in create/update (excludes email, created_at, updated_at)
_COMPANY_FIELDS = {
    "company_name",
    "sector",
    "social_insurance_employees",
    "annual_revenue_vnd",
    "total_capital_vnd",
    "founded_year",
    "is_public_offering",
    "product_type",
    "has_patent",
    "province",
    "has_coworking_contract",
    "has_business_registration",
    "coworking_monthly_cost_vnd",
}


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
    return out


# ---------------------------------------------------------------------------
# Company CRUD
# ---------------------------------------------------------------------------

def get_company(email: str) -> Optional[dict[str, Any]]:
    doc = _companies().find_one({"email": email})
    return _serialize(doc) if doc else None


def create_company(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        "email": data["email"],
        "company_name": data.get("company_name") or data.get("ten_doanh_nghiep"),
        # tầng 0
        "sector": data.get("sector"),
        "social_insurance_employees": _to_int(data.get("social_insurance_employees")),
        "annual_revenue_vnd": _to_int(data.get("annual_revenue_vnd")),
        "total_capital_vnd": _to_int(data.get("total_capital_vnd")),
        # tầng 1
        "founded_year": _to_int(data.get("founded_year")),
        "is_public_offering": _to_tribool(data.get("is_public_offering")),
        "product_type": data.get("product_type"),
        "has_patent": _to_tribool(data.get("has_patent")),
        # địa bàn
        "province": data.get("province"),
        # tầng 2
        "has_coworking_contract": _to_tribool(data.get("has_coworking_contract")),
        "has_business_registration": _to_tribool(data.get("has_business_registration")),
        # chi phí
        "coworking_monthly_cost_vnd": _to_int(data.get("coworking_monthly_cost_vnd")),
        "created_at": now,
        "updated_at": now,
    }
    try:
        _companies().insert_one(doc)
    except DuplicateKeyError:
        return get_company(data["email"])  # type: ignore[return-value]
    return _serialize(doc)


def update_company(email: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
    updates = {k: v for k, v in data.items() if k in _COMPANY_FIELDS}
    if not updates:
        return get_company(email)
    updates["updated_at"] = datetime.now(timezone.utc)
    result = _companies().find_one_and_update(
        {"email": email},
        {"$set": updates},
        return_document=True,
    )
    return _serialize(result) if result else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _to_tribool(val: Any) -> Optional[bool]:
    """None/null stays None; truthy → True; falsy int/str → False."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return bool(val)
    if isinstance(val, str):
        return val.lower() in ("1", "true", "yes")
    return None


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
