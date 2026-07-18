"""Grounded explanation layer; it never changes deterministic decisions."""

from __future__ import annotations

import json
from typing import Any

import config


def deterministic_explanation(results: list[dict[str, Any]]) -> str:
    if not results:
        return "Không tìm thấy chính sách đủ dữ liệu để đánh giá."
    labels = {
        "eligible": "đủ điều kiện theo dữ liệu hiện có",
        "not_eligible": "không đạt điều kiện",
        "needs_more_information": "chưa đủ thông tin để kết luận",
        "manual_review": "cần kiểm tra thủ công",
    }
    counts: dict[str, int] = {}
    for result in results:
        status = result["status"]
        counts[status] = counts.get(status, 0) + 1
    parts = [f"Đã đánh giá {len(results)} chính sách bằng rule engine."]
    parts.extend(f"{count} chính sách {labels.get(status, status)}." for status, count in counts.items())
    return " ".join(parts)


class EligibilityExplainer:
    def explain(
        self,
        profile: dict[str, Any],
        results: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> str:
        fallback = deterministic_explanation(results)
        if not config.llm_enabled() or not results:
            return fallback
        try:
            import httpx
        except ImportError:
            return fallback

        safe_results = [
            {
                "policy_id": result.get("policy_id"),
                "policy_name": result.get("policy_name"),
                "status": result.get("status"),
                "reasons": result.get("reasons"),
                "missing_fields": result.get("missing_fields"),
                "warnings": result.get("warnings"),
                "evidence_unit_ids": result.get("evidence_unit_ids"),
            }
            for result in results
        ]
        safe_evidence = [
            {
                "unit_id": unit.get("unit_id"),
                "document_number": unit.get("document_number"),
                "article": unit.get("article"),
                "clause": unit.get("clause"),
                "point": unit.get("point"),
                "text": unit.get("text"),
            }
            for unit in evidence
        ]
        pii_fields = {
            "email",
            "company_name",
            "business_name",
            "ten_doanh_nghiep",
            "created_at",
            "updated_at",
        }
        safe_profile = {key: value for key, value in profile.items() if key not in pii_fields}
        payload: dict[str, Any] = {
            "model": config.FPT_ELIGIBILITY_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Bạn chỉ giải thích kết quả do rule engine quyết định. Không đổi status, "
                        "không tự kết luận đủ điều kiện và không thêm điều kiện hay số tiền. "
                        "Nêu rõ thông tin còn thiếu và dẫn Điều/Khoản khi evidence có đủ."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"profile": safe_profile, "results": safe_results, "evidence": safe_evidence},
                        ensure_ascii=False,
                        default=str,
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": config.FPT_ELIGIBILITY_MAX_TOKENS,
            "stream": False,
        }
        if config.FPT_ELIGIBILITY_MODEL.lower().startswith("glm-5.2"):
            payload["thinking"] = {"type": "disabled", "clear_thinking": True}
            payload["reasoning_effort"] = "none"
        try:
            with httpx.Client(timeout=config.FPT_TIMEOUT_SECONDS) as client:
                response = client.post(
                    f"{config.FPT_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.FPT_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code in {400, 422} and "thinking" in payload:
                    payload.pop("thinking", None)
                    payload.pop("reasoning_effort", None)
                    response = client.post(
                        f"{config.FPT_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.FPT_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"].get("content") or ""
                return content.strip() or fallback
        except Exception:
            return fallback
