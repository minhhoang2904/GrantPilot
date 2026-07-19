"""FastAPI app cho hybrid legal retrieval va grounded answer."""

from __future__ import annotations

import asyncio
import functools
import json
import uuid
from datetime import date
from typing import Any, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

import answer_gen
import auth_service
import company_service
from company_profile import PROFILE_SCHEMA_VERSION, decision_facts
import config
import eligibility_client
import profile_service
import policy_discovery
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


class CompanyFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: Optional[str] = Field(default=None, min_length=1)
    sector: Optional[Literal[
        "nong_lam_ngu_nghiep", "cong_nghiep_xay_dung", "thuong_mai_dich_vu",
    ]] = None
    primary_business_activity_group: Optional[Literal[
        "agriculture", "forestry", "fisheries", "manufacturing", "processing",
        "construction", "trade", "services", "other",
    ]] = None
    legal_form: Optional[Literal[
        "joint_stock_company", "limited_liability_company", "partnership",
        "private_enterprise", "cooperative", "household_business", "other",
    ]] = None
    province_code: Optional[str] = Field(default=None, min_length=1, max_length=20)
    province_name: Optional[str] = Field(default=None, min_length=1)
    business_description: Optional[str] = Field(default=None, min_length=1, max_length=500)
    social_insurance_employees: Optional[int] = Field(default=None, ge=0)
    annual_revenue_vnd: Optional[int] = Field(default=None, ge=0)
    total_capital_vnd: Optional[int] = Field(default=None, ge=0)
    first_business_registration_date: Optional[date] = None
    has_public_offering: Optional[StrictBool] = None
    has_business_registration: Optional[StrictBool] = None
    has_state_capital: Optional[StrictBool] = None
    has_foreign_investment_capital: Optional[StrictBool] = None
    has_coworking_contract: Optional[StrictBool] = None
    coworking_monthly_cost_vnd: Optional[int] = Field(default=None, ge=0)
    has_collateral: Optional[StrictBool] = None
    has_received_same_interest_support: Optional[StrictBool] = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.first_business_registration_date and self.first_business_registration_date > date.today():
            raise ValueError("first_business_registration_date cannot be in the future")
        return self


class CompanyIn(CompanyFields):
    email: str
    company_name: str = Field(min_length=1)
    sector: Literal[
        "nong_lam_ngu_nghiep", "cong_nghiep_xay_dung", "thuong_mai_dich_vu",
    ]
    primary_business_activity_group: Literal[
        "agriculture", "forestry", "fisheries", "manufacturing", "processing",
        "construction", "trade", "services", "other",
    ]
    legal_form: Literal[
        "joint_stock_company", "limited_liability_company", "partnership",
        "private_enterprise", "cooperative", "household_business", "other",
    ]
    province_name: str = Field(min_length=1)
    business_description: str = Field(min_length=1, max_length=500)
    social_insurance_employees: int = Field(ge=0)
    annual_revenue_vnd: int = Field(ge=0)
    total_capital_vnd: int = Field(ge=0)
    first_business_registration_date: date
    has_public_offering: StrictBool
    has_business_registration: StrictBool
    has_coworking_contract: StrictBool

    @model_validator(mode="after")
    def validate_conditional_cost(self):
        activity_by_sector = {
            "nong_lam_ngu_nghiep": {"agriculture", "forestry", "fisheries", "other"},
            "cong_nghiep_xay_dung": {"manufacturing", "processing", "construction", "other"},
            "thuong_mai_dich_vu": {"trade", "services", "other"},
        }
        if self.primary_business_activity_group not in activity_by_sector[self.sector]:
            raise ValueError("primary_business_activity_group does not match sector")
        if self.has_coworking_contract is True and self.coworking_monthly_cost_vnd is None:
            raise ValueError("coworking_monthly_cost_vnd is required when a coworking contract exists")
        if self.has_coworking_contract is False and self.coworking_monthly_cost_vnd is not None:
            raise ValueError("coworking_monthly_cost_vnd must be null without a coworking contract")
        return self


class CompanyUpdate(CompanyFields):
    @model_validator(mode="after")
    def validate_update(self):
        if "company_name" in self.model_fields_set and self.company_name is None:
            raise ValueError("company_name cannot be null")
        activity_by_sector = {
            "nong_lam_ngu_nghiep": {"agriculture", "forestry", "fisheries", "other"},
            "cong_nghiep_xay_dung": {"manufacturing", "processing", "construction", "other"},
            "thuong_mai_dich_vu": {"trade", "services", "other"},
        }
        if (
            self.sector is not None
            and self.primary_business_activity_group is not None
            and self.primary_business_activity_group not in activity_by_sector[self.sector]
        ):
            raise ValueError("primary_business_activity_group does not match sector")
        if (
            self.has_coworking_contract is True
            and self.coworking_monthly_cost_vnd is None
        ):
            raise ValueError("coworking_monthly_cost_vnd is required when a coworking contract exists")
        return self


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
    # rag/eligibility are retained for the current frontend; lookup/advisory are
    # the canonical public names for the two backend pipelines.
    mode: Literal["rag", "eligibility", "lookup", "advisory"] = "rag"
    advisory_scope: Literal["question", "profile_scan"] = "question"


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
    return company_service.create_company(payload.model_dump(mode="json"))


@app.patch("/companies/{email}")
def update_company(
    email: str,
    payload: CompanyUpdate,
    current_email: str = Depends(get_current_email),
) -> dict[str, Any]:
    if current_email != email:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập.")
    updates = payload.model_dump(mode="json", exclude_unset=True)
    if updates.get("has_coworking_contract") is False:
        updates["coworking_monthly_cost_vnd"] = None
    company = company_service.update_company(email, updates)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@app.get("/companies/{email}/decision-facts")
def get_company_decision_facts(
    email: str,
    current_email: str = Depends(get_current_email),
) -> dict[str, Any]:
    if current_email != email:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập.")
    company = company_service.get_company(email)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return decision_facts(company)


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


def _canonical_mode(mode: str) -> Literal["lookup", "advisory"]:
    return "advisory" if mode in {"eligibility", "advisory"} else "lookup"


def _legal_citations(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "unit_id": unit.get("unit_id"),
            "document_number": unit.get("document_number"),
            "article": unit.get("article"),
            "clause": unit.get("clause"),
            "point": unit.get("point"),
            "source_url": unit.get("source_url"),
        }
        for unit in units
    ]


NOT_COVERED_ANSWER = (
    "Chủ đề này hiện chưa nằm trong bộ chính sách MVP. "
    "Hệ thống chưa thể đánh giá doanh nghiệp đủ hay không đủ điều kiện cho nội dung này. "
    "Hiện bạn có thể hỏi về hỗ trợ thông tin, đào tạo trực tuyến, đào tạo trực tiếp "
    "hoặc thuê/mua giải pháp chuyển đổi số."
)


def _select_advisory_policies(
    question: str,
    scope: Literal["question", "profile_scan"],
) -> dict[str, Any]:
    store = retrieval.get_retriever().store
    policies = store.decision_policy_discovery()
    return policy_discovery.select_policies(question, policies, scope=scope)


def _advisory_answer(eligibility: dict[str, Any]) -> str:
    explanation = str(eligibility.get("explanation") or "").strip()
    return explanation or "Đã đánh giá các chính sách liên quan theo hồ sơ doanh nghiệp."


def _persist_answer(
    payload: AskIn,
    email: str,
    thread_id: str,
    answer: str,
    frontend_results: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    mode: Literal["lookup", "advisory"],
) -> str:
    memory = chat_memory()
    memory.append(thread_id, "user", payload.question)
    memory.append(thread_id, "assistant", answer)

    session_id = company_service.append_chat_turn(
        email,
        payload.session_id,
        {"role": "user", "content": payload.question, "mode": mode},
    )
    assistant_turn: dict[str, Any] = {
        "role": "assistant",
        "content": answer,
        "mode": mode,
        "citations": citations,
    }
    if frontend_results:
        assistant_turn["results"] = frontend_results
    company_service.append_chat_turn(email, session_id, assistant_turn)
    return session_id


@app.post("/ask")
def ask(
    payload: AskIn,
    current_email: str = Depends(get_current_email),
) -> dict[str, Any]:
    if not payload.email or current_email != payload.email:
        raise HTTPException(status_code=403, detail="Không có quyền ghi phiên tư vấn này.")

    mode = _canonical_mode(payload.mode)
    thread_id, _, result = _run_retrieval(payload)
    units = result["legal_units"]
    citations = _legal_citations(units)
    answer = answer_gen.generate_answer(payload.question, units, fpt=retrieval.get_retriever().fpt)

    eligibility = {
        "eligibility_results": [],
        "explanation": "",
        "derived_facts": {},
        "derivation_lineage": {},
        "diagnostics": {"skipped": "lookup_mode"},
    }
    frontend_results: list[dict[str, Any]] = []
    selection = {
        "advisory_scope": payload.advisory_scope,
        "coverage_status": "not_applicable",
        "policy_ids": [],
        "topic_ids": [],
    }
    if mode == "advisory":
        company = company_service.get_company(current_email)
        if company is None:
            raise HTTPException(status_code=409, detail="Cần tạo hồ sơ doanh nghiệp trước khi tư vấn.")
        if company.get("profile_schema_version") != PROFILE_SCHEMA_VERSION:
            raise HTTPException(status_code=409, detail="Cần cập nhật hồ sơ doanh nghiệp lên phiên bản mới.")
        selection = _select_advisory_policies(payload.question, payload.advisory_scope)
        if selection["coverage_status"] == "not_covered":
            answer = NOT_COVERED_ANSWER
            eligibility["diagnostics"] = {"skipped": "topic_not_covered"}
        else:
            try:
                eligibility = eligibility_client.evaluate_company(
                    decision_facts(company),
                    selection["policy_ids"],
                    top_k=min(payload.top_k, 10),
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Eligibility service chưa sẵn sàng: {type(exc).__name__}",
                ) from exc
            raw_results = eligibility.get("eligibility_results") or []
            frontend_results = eligibility_client.to_frontend_results(raw_results)
            answer = _advisory_answer(eligibility)

    session_id = _persist_answer(
        payload,
        current_email,
        thread_id,
        answer,
        frontend_results,
        citations,
        mode,
    )

    response: dict[str, Any] = {
        "mode": mode,
        "thread_id": thread_id,
        "session_id": session_id,
        "answer": answer,
        "legal_units": units,
        "citations": citations,
        "eligibility_results": eligibility.get("eligibility_results") or [],
        "eligibility": eligibility,
        # Compatibility field consumed by Hoàng's current frontend. It now
        # contains only policy eligibility rows, never legal units.
        "results": frontend_results,
        "advisory_scope": selection["advisory_scope"],
        "coverage_status": selection["coverage_status"],
        "matched_topic_ids": selection["topic_ids"],
        "candidate_policy_ids": selection["policy_ids"] if mode == "advisory" else result["candidate_policy_ids"],
        "retrieval": {
            "route": result["route"],
            "original_query": result["original_query"],
            "retrieval_query": result["retrieval_query"],
            "diagnostics": result["diagnostics"],
        },
    }
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
    advisory_scope: Literal["question", "profile_scan"] = "question"
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


def _build_advisory_result(
    eligibility: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    policies = []
    allowed_statuses = {
        "eligible",
        "not_eligible",
        "needs_more_information",
        "manual_review",
    }
    for result in eligibility.get("eligibility_results") or []:
        status = result.get("status")
        if status not in allowed_statuses:
            status = "manual_review"
        policies.append({
            "policy_id": result.get("policy_id") or "",
            "title": result.get("policy_name") or result.get("policy_id") or "",
            "status": status,
            "score": float(result.get("score") or 0.0),
            "missing_fields": list(result.get("missing_fields") or []),
            # ``rule_errors`` is internal diagnostics and must not be exposed
            # through the user-facing advisory contract.
            "reasons": list(dict.fromkeys(result.get("reasons") or [])),
            "application_requirements": list(result.get("application_requirements") or []),
            "sources": _build_sources(result.get("sources") or []),
        })

    derived = eligibility.get("derived_facts") or {}
    return {
        "advisory_scope": selection["advisory_scope"],
        "coverage_status": selection["coverage_status"],
        "matched_topic_ids": selection["topic_ids"],
        "explanation": str(eligibility.get("explanation") or ""),
        "profile_features": {
            "enterprise_size": derived.get("enterprise_size"),
            "is_sme": derived.get("is_sme"),
            "company_age_months": derived.get("company_age_months"),
        },
        "policies": policies,
    }


def _eligibility_sources(eligibility: dict[str, Any]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in eligibility.get("eligibility_results") or []:
        for unit in result.get("sources") or []:
            key = str(unit.get("unit_id") or "")
            if key and key not in seen:
                seen.add(key)
                units.append(unit)
    return _build_sources(units)



@app.post("/v1/chat/stream")
async def chat_stream_endpoint(
    payload: ChatStreamIn,
    current_email: str = Depends(get_current_email),
) -> StreamingResponse:
    mode = payload.mode if payload.mode in ("lookup", "advisory") else "lookup"
    top_k = payload.options.top_k if payload.options else 5

    # Pre-stream check: advisory requires a company profile
    company: dict[str, Any] | None = None
    if mode == "advisory":
        company = await asyncio.to_thread(company_service.get_company, current_email)
        if not company:
            raise HTTPException(status_code=409, detail="PROFILE_REQUIRED")
        if company.get("profile_schema_version") != PROFILE_SCHEMA_VERSION:
            raise HTTPException(status_code=409, detail="PROFILE_UPDATE_REQUIRED")

    async def generate() -> Any:
        request_id = str(uuid.uuid4())
        conversation_id = payload.conversation_id or str(uuid.uuid4())

        yield _ndjson({
            "type": "started",
            "request_id": request_id,
            "conversation_id": conversation_id,
            "mode": mode,
        })

        legal_units: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        advisory_result: dict[str, Any] | None = None
        warning: dict[str, str] | None = None

        if mode == "lookup":
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
            legal_units = result["legal_units"]
            fpt_client = retrieval.get_retriever().fpt
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
            sources = _build_sources(legal_units)
        else:
            try:
                selection = await asyncio.to_thread(
                    _select_advisory_policies,
                    payload.message,
                    payload.advisory_scope,
                )
            except Exception:
                yield _ndjson({
                    "type": "error",
                    "error": {
                        "code": "POLICY_DISCOVERY_UNAVAILABLE",
                        "message": "Chưa thể xác định nhóm chính sách lúc này.",
                        "retryable": True,
                    },
                })
                return

            if selection["coverage_status"] == "not_covered":
                answer = NOT_COVERED_ANSWER
                advisory_result = _build_advisory_result(
                    {"eligibility_results": [], "derived_facts": {}, "explanation": ""},
                    selection,
                )
            else:
                try:
                    evaluate_fn = functools.partial(
                        eligibility_client.evaluate_company,
                        decision_facts(company or {}),
                        selection["policy_ids"],
                        top_k=min(top_k, 10),
                    )
                    eligibility = await asyncio.to_thread(evaluate_fn)
                    answer = _advisory_answer(eligibility)
                    advisory_result = _build_advisory_result(eligibility, selection)
                    sources = _eligibility_sources(eligibility)
                except Exception:
                    answer = "Chưa thể đánh giá hồ sơ lúc này. Vui lòng thử lại sau."
                    warning = {
                        "code": "ELIGIBILITY_UNAVAILABLE",
                        "message": "Chưa thể đánh giá hồ sơ lúc này.",
                    }

        # Stream answer word-by-word
        words = answer.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            yield _ndjson({"type": "answer_delta", "text": chunk})

        if sources:
            yield _ndjson({"type": "sources", "items": sources})

        if advisory_result is not None:
            yield _ndjson({"type": "advisory_result", "data": advisory_result})
        if warning is not None:
            yield _ndjson({
                "type": "warning",
                **warning,
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
            asst_turn: dict[str, Any] = {
                "role": "assistant",
                "content": answer,
                "mode": mode,
            }
            if sources:
                asst_turn["sources"] = sources
            if advisory_result is not None:
                asst_turn["advisory_result"] = advisory_result
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
