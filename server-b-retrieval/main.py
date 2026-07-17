"""
server-b-retrieval / main.py

FastAPI app: tra cứu chính sách, quản lý hồ sơ doanh nghiệp (MongoDB),
lịch sử chat, và sinh câu trả lời.

Chạy dev: uvicorn main:app --reload --port 8001
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import answer_gen
import company_service
import retrieval

app = FastAPI(title="Server B - Retrieval", version="0.2.0")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CompanyIn(BaseModel):
    email: str
    company_name: str

    # tầng 0: phân hạng DNNVV
    sector: Optional[str] = None
    social_insurance_employees: Optional[int] = None
    annual_revenue_vnd: Optional[int] = None
    total_capital_vnd: Optional[int] = None

    # tầng 1: tư cách
    founded_year: Optional[int] = None
    is_public_offering: Optional[bool] = None
    product_type: Optional[str] = None
    has_patent: Optional[bool] = None

    # địa bàn
    province: Optional[str] = None

    # tầng 2: hồ sơ chứng từ
    has_coworking_contract: Optional[bool] = None
    has_business_registration: Optional[bool] = None

    # chi phí thực tế
    coworking_monthly_cost_vnd: Optional[int] = None


class CompanyUpdate(BaseModel):
    company_name: Optional[str] = None

    sector: Optional[str] = None
    social_insurance_employees: Optional[int] = None
    annual_revenue_vnd: Optional[int] = None
    total_capital_vnd: Optional[int] = None

    founded_year: Optional[int] = None
    is_public_offering: Optional[bool] = None
    product_type: Optional[str] = None
    has_patent: Optional[bool] = None

    province: Optional[str] = None

    has_coworking_contract: Optional[bool] = None
    has_business_registration: Optional[bool] = None

    coworking_monthly_cost_vnd: Optional[int] = None


class AskIn(BaseModel):
    question: str
    email: Optional[str] = None
    session_id: Optional[str] = None
    top_k: int = 5


class TurnIn(BaseModel):
    session_id: Optional[str] = None
    role: str
    content: str
    results: Optional[list[dict[str, Any]]] = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Company endpoints (MongoDB)
# ---------------------------------------------------------------------------

@app.get("/companies/{email}")
def get_company(email: str) -> dict[str, Any]:
    company = company_service.get_company(email)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@app.post("/companies", status_code=201)
def create_company(payload: CompanyIn) -> dict[str, Any]:
    return company_service.create_company(payload.model_dump())


@app.patch("/companies/{email}")
def update_company(email: str, payload: CompanyUpdate) -> dict[str, Any]:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    company = company_service.update_company(email, updates)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


# ---------------------------------------------------------------------------
# Chat history endpoints (MongoDB)
# ---------------------------------------------------------------------------

@app.get("/history/{email}")
def get_history(email: str) -> list[dict[str, Any]]:
    return company_service.get_chat_history(email)


@app.post("/history/{email}/turn")
def append_turn(email: str, payload: TurnIn) -> dict[str, str]:
    turn = {
        "role": payload.role,
        "content": payload.content,
    }
    if payload.results is not None:
        turn["results"] = payload.results
    sid = company_service.append_chat_turn(email, payload.session_id, turn)
    return {"session_id": sid}


# ---------------------------------------------------------------------------
# Policy search & answer generation
# ---------------------------------------------------------------------------

@app.get("/search")
def search(q: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieval.search_policies(q, top_k=top_k)


@app.post("/ask")
def ask(payload: AskIn) -> dict[str, Any]:
    policies = retrieval.search_policies(payload.question, top_k=payload.top_k)
    answer = answer_gen.generate_answer(payload.question, policies)

    # Persist both turns to chat history when an email is provided
    if payload.email:
        user_turn = {"role": "user", "content": payload.question}
        sid = company_service.append_chat_turn(
            payload.email, payload.session_id, user_turn
        )
        assistant_turn = {"role": "assistant", "content": answer, "results": policies}
        company_service.append_chat_turn(payload.email, sid, assistant_turn)
        return {"answer": answer, "policies": policies, "session_id": sid}

    return {"answer": answer, "policies": policies}


@app.post("/ask/flat")
def ask_flat(payload: AskIn) -> dict[str, Any]:
    """Baseline RAG phẳng — không xét eligibility engine, dùng cho tab benchmark."""
    policies = retrieval.search_policies(payload.question, top_k=payload.top_k)
    answer = answer_gen.generate_answer(payload.question, policies)
    return {"answer": answer}
