"""
server-c-eligibility / main.py

FastAPI app: kiểm tra điều kiện hưởng chính sách cho một hồ sơ doanh nghiệp
và xếp hạng kết quả.

Chạy dev: uvicorn main:app --reload --port 8002
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import eligibility_engine
import ranking

app = FastAPI(title="Server C - Eligibility", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("POLICY_DB_PATH", BASE_DIR.parent / "shared" / "policy.db"))


class ProfilePayload(BaseModel):
    business_name: Optional[str] = None
    industry: Optional[str] = None
    business_type: Optional[str] = None
    num_employees: Optional[int] = None
    province: Optional[str] = None
    annual_revenue: Optional[float] = None
    founded_year: Optional[int] = None
    extra_attributes: dict[str, Any] = {}


class CheckIn(BaseModel):
    profile: ProfilePayload
    only_eligible: bool = True
    top_k: Optional[int] = None


def _fetch_profile_by_id(profile_id: str) -> dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile = dict(row)
    profile["extra_attributes"] = json.loads(profile.get("extra_attributes") or "{}")
    return profile


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/eligibility/check")
def check_eligibility(payload: CheckIn) -> list[dict[str, Any]]:
    profile = payload.profile.model_dump()
    results = eligibility_engine.evaluate_profile_against_all_policies(profile)
    return ranking.rank_results(results, only_eligible=payload.only_eligible, top_k=payload.top_k)


@app.get("/eligibility/check/{profile_id}")
def check_eligibility_by_profile_id(
    profile_id: str, only_eligible: bool = True, top_k: Optional[int] = None
) -> list[dict[str, Any]]:
    profile = _fetch_profile_by_id(profile_id)
    results = eligibility_engine.evaluate_profile_against_all_policies(profile)
    return ranking.rank_results(results, only_eligible=only_eligible, top_k=top_k)
