"""FastAPI app cho hybrid legal retrieval va grounded answer."""

from __future__ import annotations

import asyncio
import functools
import json
import uuid
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import answer_gen
import auth_service
import company_service
import config
import profile_service
import retrieval
from memory import ChatMemory, build_chat_memory


app = FastAPI(title="Server B - Retrieval", version="0.2.0")
_memory: ChatMemory | None = None
_bearer = HTTPBearer(auto_error=False)


def chat_memory() -> ChatMemory:
    global _memory
    if _memory is None:
        _memory = build_chat_memory()
    return _memory


def get_current_email(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    """Validate a Bearer JWT and return its email subject."""
    if not creds:
        raise HTTPException(status_code=401, detail="Token không được cung cấp.")
    email = auth_service.decode_token(creds.credentials)
    if not email:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn.")
    return email


class CompanyIn(BaseModel):
    email: str
    company_name: str
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


class TurnIn(BaseModel):
    session_id: Optional[str] = None
    role: str
    content: str
    results: Optional[list[dict[str, Any]]] = None


class AuthIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    business_name: Optional[str] = None
    industry: Optional[str] = None
    business_type: Optional[str] = None
    num_employees: Optional[int] = None
    province: Optional[str] = None
    annual_revenue: Optional[float] = None
    founded_year: Optional[int] = None
    extra_attributes: dict[str, Any] = Field(default_factory=dict)


class RetrieveIn(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    thread_id: Optional[str] = None


class AskIn(RetrieveIn):
    email: Optional[str] = None
    session_id: Optional[str] = None
    # "rag" | "eligibility" — eligibility includes results table; both persist history
    mode: Optional[str] = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "legal_data_backend": config.LEGAL_DATA_BACKEND,
        "legal_data_configured": config.legal_data_configured(),
        "mongodb_configured": config.mongodb_enabled(),
        "pinecone_configured": config.pinecone_enabled(),
        "fpt_configured": config.fpt_enabled(),
        "redis_configured": bool(config.REDIS_URL),
    }


@app.post("/auth/register", status_code=201)
def auth_register(payload: AuthIn) -> dict[str, str]:
    email = payload.email.strip().lower()
    try:
        token = auth_service.register_user(email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"token": token, "email": email}


@app.post("/auth/login")
def auth_login(payload: AuthIn) -> dict[str, str]:
    email = payload.email.strip().lower()
    try:
        token = auth_service.login_user(email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"token": token, "email": email}


@app.get("/companies/{email}")
def get_company(email: str, current_email: str = Depends(get_current_email)) -> dict[str, Any]:
    if current_email != email:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập.")
    company = company_service.get_company(email)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@app.post("/companies", status_code=201)
def create_company(
    payload: CompanyIn,
    current_email: str = Depends(get_current_email),
) -> dict[str, Any]:
    if current_email != payload.email:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập.")
    return company_service.create_company(payload.model_dump())


@app.patch("/companies/{email}")
def update_company(
    email: str,
    payload: CompanyUpdate,
    current_email: str = Depends(get_current_email),
) -> dict[str, Any]:
    if current_email != email:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập.")
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    company = company_service.update_company(email, updates)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@app.get("/history/{email}")
def get_history(email: str, current_email: str = Depends(get_current_email)) -> list[dict[str, Any]]:
    if current_email != email:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập.")
    return company_service.get_chat_history(email)


@app.post("/history/{email}/turn")
def append_turn(
    email: str,
    payload: TurnIn,
    current_email: str = Depends(get_current_email),
) -> dict[str, str]:
    if current_email != email:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập.")
    turn: dict[str, Any] = {"role": payload.role, "content": payload.content}
    if payload.results is not None:
        turn["results"] = payload.results
    session_id = company_service.append_chat_turn(email, payload.session_id, turn)
    return {"session_id": session_id}


@app.delete("/history/{email}/sessions/{session_id}")
def delete_session(
    email: str,
    session_id: str,
    current_email: str = Depends(get_current_email),
) -> dict[str, str]:
    if current_email != email:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập.")
    deleted = company_service.delete_chat_session(email, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok", "session_id": session_id}


def _run_retrieval(payload: RetrieveIn) -> tuple[str, list[dict[str, str]], dict[str, Any]]:
    thread_id = payload.thread_id or getattr(payload, "session_id", None) or str(uuid.uuid4())
    history = chat_memory().recent(thread_id, config.CHAT_HISTORY_MESSAGES)
    try:
        result = retrieval.get_retriever().retrieve(
            payload.question,
            history=history,
            top_k=payload.top_k,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"Legal data chưa sẵn sàng: {exc}") from exc
    return thread_id, history, result


@app.post("/retrieve")
def retrieve(payload: RetrieveIn) -> dict[str, Any]:
    thread_id, _, result = _run_retrieval(payload)
    return {"thread_id": thread_id, **result}


@app.get("/search")
def search(q: str = Query(min_length=1), top_k: int = Query(default=5, ge=1, le=20)) -> list[dict[str, Any]]:
    try:
        return retrieval.search_legal_units(q, top_k=top_k)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"Legal data chưa sẵn sàng: {exc}") from exc


@app.post("/ask")
def ask(payload: AskIn) -> dict[str, Any]:
    thread_id, _, result = _run_retrieval(payload)
    units = result["legal_units"]
    answer = answer_gen.generate_answer(payload.question, units, fpt=retrieval.get_retriever().fpt)
    mode = (payload.mode or "eligibility").lower()
    include_results = mode != "rag"

    memory = chat_memory()
    memory.append(thread_id, "user", payload.question)
    memory.append(thread_id, "assistant", answer)

    session_id = thread_id
    if payload.email:
        session_id = company_service.append_chat_turn(
            payload.email,
            payload.session_id,
            {"role": "user", "content": payload.question},
        )
        assistant_turn: dict[str, Any] = {"role": "assistant", "content": answer}
        if include_results:
            assistant_turn["results"] = units
        company_service.append_chat_turn(payload.email, session_id, assistant_turn)

    response: dict[str, Any] = {
        "thread_id": thread_id,
        "session_id": session_id,
        "answer": answer,
        "candidate_policy_ids": result["candidate_policy_ids"],
        "retrieval": {
            "route": result["route"],
            "original_query": result["original_query"],
            "retrieval_query": result["retrieval_query"],
            "diagnostics": result["diagnostics"],
        },
    }
    if include_results:
        response["results"] = units
        response["legal_units"] = units
        # Alias tam thoi cho client cu; du lieu nay la legal units, khong phai
        # eligibility policies. Client moi nen dung `legal_units`.
        response["policies"] = units
    else:
        response["results"] = []
    return response


@app.post("/ask/flat")
def ask_flat(payload: AskIn) -> dict[str, Any]:
    """Compatibility baseline endpoint used by the benchmark UI."""
    units = retrieval.search_legal_units(payload.question, top_k=payload.top_k)
    answer = answer_gen.generate_answer(payload.question, units, fpt=retrieval.get_retriever().fpt)
    return {"answer": answer}


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
    updates = {key: value for key, value in payload.model_dump().items() if value not in (None, {})}
    profile = profile_service.update_profile(profile_id, updates)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


# ── New streaming chat API (/v1/chat/stream) ──────────────────────────────────

class ChatStreamOptions(BaseModel):
    top_k: int = Field(default=5, ge=1, le=20)


class ChatStreamIn(BaseModel):
    mode: str = "lookup"  # "lookup" | "advisory"
    message: str = Field(min_length=1)
    conversation_id: Optional[str] = None
    options: Optional[ChatStreamOptions] = None


def _ndjson(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


def _build_sources(legal_units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = []
    for u in legal_units:
        snippet = (u.get("text") or "")[:250].strip() or None
        item: dict[str, Any] = {
            "unit_id": u.get("unit_id", ""),
            "document_number": u.get("document_number", ""),
            "document_title": u.get("document_title", ""),
        }
        for field in ("article", "clause", "point", "source_url", "page_start", "page_end"):
            if u.get(field) is not None:
                item[field] = u[field]
        if snippet:
            item["snippet"] = snippet
        sources.append(item)
    return sources


@app.post("/v1/chat/stream")
async def chat_stream_endpoint(
    payload: ChatStreamIn,
    current_email: str = Depends(get_current_email),
) -> StreamingResponse:
    mode = payload.mode if payload.mode in ("lookup", "advisory") else "lookup"
    top_k = payload.options.top_k if payload.options else 5

    # Pre-stream check: advisory requires a company profile
    if mode == "advisory":
        company = await asyncio.to_thread(company_service.get_company, current_email)
        if not company:
            raise HTTPException(status_code=409, detail="PROFILE_REQUIRED")

    async def generate() -> Any:
        request_id = str(uuid.uuid4())
        conversation_id = payload.conversation_id or str(uuid.uuid4())

        yield _ndjson({
            "type": "started",
            "request_id": request_id,
            "conversation_id": conversation_id,
            "mode": mode,
        })

        # Retrieval (blocking → thread pool)
        retrieve_payload = RetrieveIn(
            question=payload.message,
            top_k=top_k,
            thread_id=conversation_id,
        )
        try:
            _, _, result = await asyncio.to_thread(_run_retrieval, retrieve_payload)
        except HTTPException as exc:
            yield _ndjson({
                "type": "error",
                "error": {
                    "code": "RETRIEVAL_UNAVAILABLE",
                    "message": exc.detail,
                    "retryable": True,
                },
            })
            return

        legal_units: list[dict[str, Any]] = result["legal_units"]
        fpt_client = retrieval.get_retriever().fpt

        # Answer generation (blocking FPT API call → thread pool)
        try:
            gen_fn = functools.partial(
                answer_gen.generate_answer,
                payload.message,
                legal_units,
                fpt=fpt_client,
            )
            answer: str = await asyncio.to_thread(gen_fn)
        except Exception:
            answer = answer_gen.NO_EVIDENCE

        # Stream answer word-by-word
        words = answer.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            yield _ndjson({"type": "answer_delta", "text": chunk})

        # Sources event
        sources = _build_sources(legal_units)
        if sources:
            yield _ndjson({"type": "sources", "items": sources})

        # Advisory result (Server C not yet available → warning)
        if mode == "advisory":
            yield _ndjson({
                "type": "warning",
                "code": "ELIGIBILITY_UNAVAILABLE",
                "message": "Chưa thể đánh giá hồ sơ lúc này.",
            })

        # Persist conversation history
        message_id = str(uuid.uuid4())
        try:
            actual_sid = await asyncio.to_thread(
                company_service.append_chat_turn,
                current_email,
                conversation_id,
                {"role": "user", "content": payload.message},
            )
            asst_turn: dict[str, Any] = {"role": "assistant", "content": answer}
            if sources:
                asst_turn["sources"] = sources
            await asyncio.to_thread(
                company_service.append_chat_turn,
                current_email,
                actual_sid,
                asst_turn,
            )
        except Exception:
            pass  # History write failure must not break the stream

        yield _ndjson({"type": "completed", "message_id": message_id})

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
