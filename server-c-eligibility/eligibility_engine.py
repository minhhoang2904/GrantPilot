"""
server-c-eligibility / eligibility_engine.py

Đánh giá một hồ sơ doanh nghiệp (profile) có đủ điều kiện hưởng một
chính sách (policy) hay không, dựa trên `eligibility_criteria` (JSON)
lưu trong bảng policies.

Các khoá criteria hỗ trợ (mở rộng thêm khi cần):
- business_type: list[str]            -> profile.business_type phải nằm trong list
- industry: list[str]                 -> profile.industry phải nằm trong list
- province: list[str]                 -> profile.province phải nằm trong list
- min_num_employees / max_num_employees
- min_annual_revenue / max_annual_revenue
- founded_before_year / founded_after_year
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("POLICY_DB_PATH", BASE_DIR.parent / "shared" / "policy.db"))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _check_membership(value: Any, allowed: list[Any]) -> tuple[bool, str]:
    if value is None:
        return False, "Thiếu thông tin trong hồ sơ để kiểm tra điều kiện này."
    ok = value in allowed
    return ok, f"Giá trị '{value}' {'thuộc' if ok else 'không thuộc'} nhóm cho phép {allowed}."


def _check_range(value: Any, min_v: Any, max_v: Any, label: str) -> tuple[bool, str]:
    if value is None:
        return False, f"Thiếu {label} trong hồ sơ."
    if min_v is not None and value < min_v:
        return False, f"{label} = {value} nhỏ hơn mức tối thiểu {min_v}."
    if max_v is not None and value > max_v:
        return False, f"{label} = {value} lớn hơn mức tối đa {max_v}."
    return True, f"{label} = {value} thoả điều kiện."


def evaluate(profile: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Trả về {is_eligible, score, reasons} cho 1 cặp profile/policy."""
    criteria: dict[str, Any] = policy.get("eligibility_criteria") or {}
    if isinstance(criteria, str):
        criteria = json.loads(criteria or "{}")

    checks: list[tuple[bool, str]] = []

    if "business_type" in criteria:
        checks.append(_check_membership(profile.get("business_type"), criteria["business_type"]))
    if "industry" in criteria:
        checks.append(_check_membership(profile.get("industry"), criteria["industry"]))
    if "province" in criteria:
        checks.append(_check_membership(profile.get("province"), criteria["province"]))
    if "min_num_employees" in criteria or "max_num_employees" in criteria:
        checks.append(
            _check_range(
                profile.get("num_employees"),
                criteria.get("min_num_employees"),
                criteria.get("max_num_employees"),
                "Số lao động",
            )
        )
    if "min_annual_revenue" in criteria or "max_annual_revenue" in criteria:
        checks.append(
            _check_range(
                profile.get("annual_revenue"),
                criteria.get("min_annual_revenue"),
                criteria.get("max_annual_revenue"),
                "Doanh thu năm",
            )
        )
    if "founded_before_year" in criteria and profile.get("founded_year") is not None:
        ok = profile["founded_year"] < criteria["founded_before_year"]
        checks.append((ok, f"Năm thành lập {profile['founded_year']} "
                            f"{'trước' if ok else 'không trước'} {criteria['founded_before_year']}."))
    if "founded_after_year" in criteria and profile.get("founded_year") is not None:
        ok = profile["founded_year"] > criteria["founded_after_year"]
        checks.append((ok, f"Năm thành lập {profile['founded_year']} "
                            f"{'sau' if ok else 'không sau'} {criteria['founded_after_year']}."))

    if not checks:
        return {"is_eligible": True, "score": 1.0, "reasons": ["Chính sách không có điều kiện ràng buộc cụ thể."]}

    passed = sum(1 for ok, _ in checks if ok)
    score = passed / len(checks)
    is_eligible = passed == len(checks)
    reasons = [reason for _, reason in checks]

    return {"is_eligible": is_eligible, "score": round(score, 4), "reasons": reasons}


def evaluate_profile_against_all_policies(profile: dict[str, Any]) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        policy_rows = conn.execute("SELECT * FROM policies").fetchall()
    finally:
        conn.close()

    results = []
    for row in policy_rows:
        policy = dict(row)
        result = evaluate(profile, policy)
        results.append({"policy": policy, **result})
    return results
