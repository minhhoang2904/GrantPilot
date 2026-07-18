"""Grounded answer generation tren legal units da retrieve."""

from __future__ import annotations

from clients import FptClient


NO_EVIDENCE = (
    "Không tìm thấy căn cứ pháp lý đủ liên quan trong kho dữ liệu hiện có. "
    "Bạn có thể nêu rõ loại hỗ trợ hoặc Điều/Khoản cần tra cứu."
)


def _citation(unit: dict) -> str:
    location = f"{unit.get('document_number') or unit.get('document_title', '')}, Điều {unit.get('article', '')}"
    if unit.get("clause"):
        location += f", khoản {unit['clause']}"
    if unit.get("point"):
        location += f", điểm {unit['point']}"
    pages = unit.get("page_start")
    if unit.get("page_end") and unit.get("page_end") != pages:
        pages = f"{pages}–{unit['page_end']}"
    if pages:
        location += f", trang {pages}"
    return location


def generate_answer(
    question: str,
    legal_units: list[dict],
    *,
    fpt: FptClient | None = None,
) -> str:
    if not legal_units:
        return NO_EVIDENCE
    fpt = fpt or FptClient()
    try:
        generated = fpt.answer(question, legal_units)
    except Exception:
        generated = None
    if generated:
        return generated

    # Fallback chi trich dan, khong dien giai hay ket luan eligibility.
    lines = ["Các căn cứ pháp lý có thể liên quan:"]
    for unit in legal_units:
        text = " ".join((unit.get("text") or "").split())
        excerpt = text[:320] + ("…" if len(text) > 320 else "")
        lines.append(f"- {_citation(unit)}: {excerpt}")
    lines.append("Đây là kết quả tra cứu, chưa phải kết luận doanh nghiệp đủ điều kiện hưởng hỗ trợ.")
    return "\n".join(lines)
