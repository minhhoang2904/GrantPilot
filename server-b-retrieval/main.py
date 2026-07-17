"""
server-b-retrieval / main.py

FastAPI app: tra cứu chính sách, quản lý hồ sơ doanh nghiệp, sinh câu trả lời.

Chạy dev: uvicorn main:app --reload --port 8001
"""

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import answer_gen
import profile_service
import retrieval

app = FastAPI(title="Server B - Retrieval", version="0.1.0")


class ProfileIn(BaseModel):
    business_name: Optional[str] = None
    industry: Optional[str] = None
    business_type: Optional[str] = None
    num_employees: Optional[int] = None
    province: Optional[str] = None
    annual_revenue: Optional[float] = None
    founded_year: Optional[int] = None
    extra_attributes: dict[str, Any] = {}


class AskIn(BaseModel):
    question: str
    top_k: int = 5


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search")
def search(q: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieval.search_policies(q, top_k=top_k)


@app.post("/ask")
def ask(payload: AskIn) -> dict[str, Any]:
    policies = retrieval.search_policies(payload.question, top_k=payload.top_k)
    answer = answer_gen.generate_answer(payload.question, policies)
    return {"answer": answer, "policies": policies}


@app.post("/profiles")
def create_profile(payload: ProfileIn) -> dict[str, Any]:
    return profile_service.create_profile(payload.model_dump())


@app.get("/profiles/{profile_id}")
def get_profile(profile_id: str) -> dict[str, Any]:
    profile = profile_service.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.patch("/profiles/{profile_id}")
def update_profile(profile_id: str, payload: ProfileIn) -> dict[str, Any]:
    updates = {k: v for k, v in payload.model_dump().items() if v not in (None, {})}
    profile = profile_service.update_profile(profile_id, updates)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
