"""Server C client and compatibility mapping for the current frontend."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

import config


def evaluate_company(
    facts: dict[str, Any],
    candidate_policy_ids: list[str],
    *,
    top_k: int = 10,
    evaluation_date: date | None = None,
) -> dict[str, Any]:
    if not candidate_policy_ids:
        return {
            "eligibility_results": [],
            "explanation": "",
            "derived_facts": {},
            "derivation_lineage": {},
            "diagnostics": {"skipped": "retrieval_returned_no_candidate_policy_ids"},
        }
    response = httpx.post(
        f"{config.SERVER_C_URL}/eligibility/evaluate",
        json={
            "facts": facts,
            "candidate_policy_ids": candidate_policy_ids,
            "only_eligible": False,
            "top_k": top_k,
            "include_explanation": True,
            "evaluation_date": evaluation_date.isoformat() if evaluation_date else None,
        },
        timeout=config.SERVER_C_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def to_frontend_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map eligibility results only; legal units must never enter this table."""
    mapped = []
    for result in results:
        sources = result.get("sources") or []
        first = sources[0] if sources else {}
        raw_status = result.get("status")
        status = {
            "eligible": "eligible",
            "not_eligible": "not_eligible",
            "needs_more_information": "partial",
            "manual_review": "partial",
        }.get(raw_status, "partial")
        gaps = list(result.get("missing_fields") or [])
        if raw_status in {"not_eligible", "manual_review"}:
            gaps.extend(result.get("reasons") or result.get("rule_errors") or [])
        mapped.append(
            {
                "policy_id": result.get("policy_id"),
                "title": result.get("policy_name") or result.get("policy_id"),
                "status": status,
                "gap": list(dict.fromkeys(gaps)),
                "source": {
                    "dieu": f"Điều {first.get('article')}" if first.get("article") else None,
                    "khoan": f"khoản {first.get('clause')}" if first.get("clause") else None,
                    "thong_tu": first.get("document_number"),
                    "url": first.get("source_url"),
                },
                "eligibility_status": raw_status,
                "score": result.get("score"),
            }
        )
    return mapped
