"""FastAPI surface for deterministic company eligibility evaluation."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import config
from eligibility_service import EligibilityService
from policy_repository import MongoPolicyRepository


app = FastAPI(title="Server C - Eligibility", version="1.0.0")
_service: EligibilityService | None = None


def get_service() -> EligibilityService:
    global _service
    if _service is None:
        _service = EligibilityService()
    return _service


class EvaluateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: dict[str, Any]
    candidate_policy_ids: list[str] = Field(default_factory=list)
    only_eligible: bool = False
    top_k: int = Field(default=config.DEFAULT_TOP_K, ge=1, le=config.MAX_TOP_K)
    include_explanation: bool = True
    evaluation_date: Optional[date] = None


def _evaluate(payload: EvaluateIn) -> dict[str, Any]:
    try:
        return get_service().evaluate(
            payload.facts,
            candidate_policy_ids=payload.candidate_policy_ids,
            only_eligible=payload.only_eligible,
            top_k=payload.top_k,
            include_explanation=payload.include_explanation,
            evaluation_date=payload.evaluation_date,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Eligibility data chưa sẵn sàng: {exc}") from exc


@app.get("/health")
def health() -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": "ok",
        "mongodb_configured": config.mongodb_enabled(),
        "llm_explanation_configured": config.llm_enabled(),
        "decision_layer": "deterministic_rules",
    }
    if config.mongodb_enabled():
        try:
            repository = MongoPolicyRepository()
            repository.ping()
            response["data"] = repository.stats()
        except Exception as exc:
            response["status"] = "degraded"
            response["data_error"] = type(exc).__name__
    return response


@app.post("/eligibility/evaluate")
def evaluate_eligibility(payload: EvaluateIn) -> dict[str, Any]:
    return _evaluate(payload)
