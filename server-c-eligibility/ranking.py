"""
server-c-eligibility / ranking.py

Xếp hạng các kết quả eligibility (output của eligibility_engine.evaluate_*)
để trả về danh sách chính sách phù hợp nhất trước.
"""

from __future__ import annotations

from typing import Any


def rank_results(
    results: list[dict[str, Any]],
    only_eligible: bool = True,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    filtered = [r for r in results if (not only_eligible or r["is_eligible"])]
    ranked = sorted(filtered, key=lambda r: r["score"], reverse=True)
    return ranked[:top_k] if top_k else ranked
