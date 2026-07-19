"""LLM presentation layer for advisory mode with deterministic fallback."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import advisory_answer
from clients import FptClient
from policy_discovery import DiscoveryResult


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdvisoryWriteResult:
    answer: str
    writer: str
    fallback_reason: str | None = None


def _company_summary(
    company: dict[str, Any],
    derived_facts: dict[str, Any],
) -> dict[str, Any]:
    # Deliberately excludes email, company_name, timestamps and provenance.
    sector_labels = {
        "nong_lam_ngu_nghiep": "nông, lâm, ngư nghiệp",
        "cong_nghiep_xay_dung": "công nghiệp và xây dựng",
        "thuong_mai_dich_vu": "thương mại và dịch vụ",
    }
    activity_labels = {
        "agriculture": "nông nghiệp", "forestry": "lâm nghiệp",
        "fisheries": "thủy sản", "manufacturing": "sản xuất",
        "processing": "chế biến", "construction": "xây dựng",
        "trade": "thương mại", "services": "dịch vụ", "other": "khác",
    }
    size_labels = {
        "micro": "siêu nhỏ", "small": "nhỏ", "medium": "vừa", "large": "lớn",
    }
    summary: dict[str, Any] = {}
    if company.get("sector") is not None:
        summary["lĩnh vực"] = sector_labels.get(company["sector"], company["sector"])
    if company.get("primary_business_activity_group") is not None:
        activity = company["primary_business_activity_group"]
        summary["hoạt động chính"] = activity_labels.get(activity, activity)
    if company.get("business_description") is not None:
        summary["mô tả hoạt động"] = company["business_description"]
    if derived_facts.get("enterprise_size") is not None:
        size = derived_facts["enterprise_size"]
        summary["quy mô suy dẫn"] = size_labels.get(size, size)
    if derived_facts.get("is_sme") is not None:
        summary["thuộc nhóm DNNVV"] = bool(derived_facts["is_sme"])
    return summary


def _decision_notes(result: dict[str, Any]) -> list[str]:
    reasons = " ".join(str(reason) for reason in (result.get("reasons") or []))
    notes: list[str] = []
    if result.get("status") == "not_eligible":
        if "is_sme" in reasons:
            notes.append("Hồ sơ hiện không được xác định là doanh nghiệp nhỏ và vừa theo dữ liệu quy mô.")
        if "primary_business_activity_group" in reasons:
            notes.append("Hoạt động kinh doanh chính không thuộc nhóm sản xuất hoặc chế biến.")
        if not notes:
            notes.append("Hồ sơ chưa đáp ứng ít nhất một điều kiện đã được chuẩn hóa.")
    elif result.get("status") == "needs_more_information":
        missing = [
            advisory_answer.friendly_field(field)
            for field in (result.get("missing_fields") or [])
        ]
        if missing:
            notes.append("Cần bổ sung: " + ", ".join(missing) + ".")
    elif result.get("status") == "manual_review":
        notes.append("Kết quả này cần chuyên viên kiểm tra thêm.")
    return notes


def _safe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe = []
    for result in results:
        safe.append(
            {
                "policy_name": result.get("policy_name") or result.get("policy_id"),
                "status": result.get("status"),
                "decision_notes": _decision_notes(result),
                "application_requirements": list(result.get("application_requirements") or []),
                "required_documents": list(result.get("required_documents") or []),
                "benefit": result.get("benefit_calculator") or {},
                "warnings": list(result.get("warnings") or []),
                "sources": [
                    {
                        "document_number": source.get("document_number"),
                        "article": source.get("article"),
                        "clause": source.get("clause"),
                        "point": source.get("point"),
                    }
                    for source in (result.get("sources") or [])
                ],
            }
        )
    return safe


def write_advisory_answer(
    question: str,
    company: dict[str, Any],
    scope: DiscoveryResult,
    eligibility: dict[str, Any],
    *,
    fpt: FptClient,
) -> AdvisoryWriteResult:
    results = eligibility.get("eligibility_results") or []
    deterministic = advisory_answer.build_advisory_answer(scope, results)
    llm_payload = {
        "question": question,
        "company_summary": _company_summary(company, eligibility.get("derived_facts") or {}),
        "coverage": {
            "coverage_status": scope.coverage_status,
            "matched_topics": list(scope.matched_topics),
            "unsupported_topics": list(scope.unsupported_topics),
        },
        "eligibility_results": _safe_results(results),
    }
    last_error: Exception | None = None
    suggestion: str | None = None
    for _attempt in range(2):
        try:
            suggestion = fpt.advise(llm_payload)
            if suggestion:
                break
        except Exception as exc:
            last_error = exc
    if last_error is not None and not suggestion:
        reason = type(last_error).__name__
        logger.warning("Advisory LLM fallback after retry: %s", reason)
        return AdvisoryWriteResult(
            answer=deterministic,
            writer="deterministic_fallback",
            fallback_reason=reason,
        )
    if not suggestion:
        logger.warning("Advisory LLM fallback: disabled or empty")
        return AdvisoryWriteResult(
            answer=deterministic,
            writer="deterministic_fallback",
            fallback_reason="llm_disabled_or_empty",
        )
    return AdvisoryWriteResult(
        answer=f"{deterministic}\n\nGợi ý dành cho doanh nghiệp:\n{suggestion}",
        writer="fpt_llm",
    )
