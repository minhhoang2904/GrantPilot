"""FastAPI surface for deterministic company eligibility evaluation."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    facts: Optional[dict[str, Any]] = None
    # Compatibility alias used by Server B v0.2 during rolling deployments.
    profile: Optional[dict[str, Any]] = None
    candidate_policy_ids: list[str] = Field(default_factory=list)
    only_eligible: bool = False
    top_k: int = Field(default=config.DEFAULT_TOP_K, ge=1, le=config.MAX_TOP_K)
    include_explanation: bool = True
    evaluation_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_fact_source(self):
        if self.facts is None and self.profile is None:
            raise ValueError("facts is required")
        if self.facts is not None and self.profile is not None:
            raise ValueError("send facts or profile, not both")
        return self

    @property
    def direct_facts(self) -> dict[str, Any]:
        return self.facts if self.facts is not None else self.profile or {}


def _evaluate(payload: EvaluateIn) -> dict[str, Any]:
    try:
        return get_service().evaluate(
            payload.direct_facts,
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
    response = _evaluate(payload)
    # Transitional response alias for Server B v0.2. New clients must consume
    # ``eligibility_results``; remove this alias after the old image is retired.
    response.setdefault("results", response.get("eligibility_results", []))
    return response
