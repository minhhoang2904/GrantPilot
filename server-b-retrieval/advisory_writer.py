"""Guarded LLM presentation layer for advisory mode.

Eligibility remains deterministic.  The LLM can only append practical next
steps and every failure falls back to the already composed business answer.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from clients import FptClient


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
    """Return the minimum useful, PII-free company context for copywriting."""
    sector_labels = {
        "nong_lam_ngu_nghiep": "nông, lâm, ngư nghiệp",
        "cong_nghiep_xay_dung": "công nghiệp và xây dựng",
        "thuong_mai_dich_vu": "thương mại và dịch vụ",
    }
    activity_labels = {
        "agriculture": "nông nghiệp",
        "forestry": "lâm nghiệp",
        "fisheries": "thủy sản",
        "manufacturing": "sản xuất",
        "processing": "chế biến",
        "construction": "xây dựng",
        "trade": "thương mại",
        "services": "dịch vụ",
        "other": "khác",
    }
    size_labels = {
        "micro": "siêu nhỏ",
        "small": "nhỏ",
        "medium": "vừa",
        "large": "lớn",
    }
    summary: dict[str, Any] = {}
    if company.get("sector") is not None:
        sector = company["sector"]
        summary["lĩnh vực"] = sector_labels.get(sector, sector)
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


def _friendly_field(field: Any) -> str:
    labels = {
        "sector": "lĩnh vực hoạt động",
        "primary_business_activity_group": "nhóm ngành nghề kinh doanh chính",
        "legal_form": "loại hình pháp lý",
        "social_insurance_employees": "số lao động tham gia BHXH",
        "annual_revenue_vnd": "doanh thu năm",
        "total_capital_vnd": "tổng nguồn vốn",
        "first_business_registration_date": "ngày đăng ký doanh nghiệp lần đầu",
        "is_sme": "thông tin xác định doanh nghiệp nhỏ và vừa",
    }
    value = str(field or "").strip()
    return labels.get(value, value.replace("_", " "))


def _decision_notes(result: dict[str, Any]) -> list[str]:
    reasons = " ".join(str(reason) for reason in (result.get("reasons") or []))
    status = result.get("status")
    notes: list[str] = []
    if status == "not_eligible":
        if "is_sme" in reasons:
            notes.append("Hồ sơ hiện không được xác định là doanh nghiệp nhỏ và vừa theo dữ liệu quy mô.")
        if "primary_business_activity_group" in reasons:
            notes.append("Hoạt động kinh doanh chính không thuộc nhóm sản xuất hoặc chế biến.")
        if not notes:
            notes.append("Hồ sơ chưa đáp ứng ít nhất một điều kiện của chương trình.")
    elif status == "needs_more_information":
        missing = [_friendly_field(field) for field in (result.get("missing_fields") or [])]
        if missing:
            notes.append("Cần bổ sung: " + ", ".join(missing) + ".")
    elif status == "manual_review":
        notes.append("Kết quả này cần chuyên viên kiểm tra thêm.")
    return notes


def _safe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for result in results:
        safe.append({
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
                    "source_url": source.get("source_url"),
                }
                for source in (result.get("sources") or [])
            ],
        })
    return safe


def write_advisory_answer(
    question: str,
    company: dict[str, Any],
    selection: dict[str, Any],
    eligibility: dict[str, Any],
    deterministic_answer: str,
    *,
    fpt: FptClient,
) -> AdvisoryWriteResult:
    """Append optional suggestions without letting the LLM decide eligibility."""
    results = list(eligibility.get("eligibility_results") or [])
    if selection.get("coverage_status") != "covered" or not results:
        return AdvisoryWriteResult(
            answer=deterministic_answer,
            writer="deterministic_not_covered",
        )

    llm_payload = {
        "question": question,
        "company_summary": _company_summary(
            company,
            eligibility.get("derived_facts") or {},
        ),
        "coverage": {
            "coverage_status": selection.get("coverage_status"),
            "advisory_scope": selection.get("advisory_scope"),
            "matched_topic_ids": list(selection.get("topic_ids") or []),
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
        except Exception as exc:  # LLM is optional; deterministic answer is authoritative.
            last_error = exc

    if last_error is not None and not suggestion:
        reason = type(last_error).__name__
        logger.warning("Advisory LLM fallback after retry: %s", reason)
        return AdvisoryWriteResult(
            answer=deterministic_answer,
            writer="deterministic_fallback",
            fallback_reason=reason,
        )
    if not suggestion:
        return AdvisoryWriteResult(
            answer=deterministic_answer,
            writer="deterministic_fallback",
            fallback_reason="llm_disabled_or_empty",
        )
    return AdvisoryWriteResult(
        answer=f"{deterministic_answer}\n\nGợi ý dành cho doanh nghiệp:\n{suggestion}",
        writer="fpt_llm",
    )
