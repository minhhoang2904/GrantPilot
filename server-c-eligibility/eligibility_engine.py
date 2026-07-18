"""Deterministic eligibility rule engine.

Only this module decides policy status. The explanation layer may describe a
decision, but it must never change it.
"""

from __future__ import annotations

from typing import Any, Iterable, Literal, TypedDict

import config


RuleStatus = Literal["pass", "fail", "unknown", "error"]
EligibilityStatus = Literal[
    "eligible", "not_eligible", "needs_more_information", "manual_review"
]


class RuleOutcome(TypedDict):
    status: RuleStatus
    reasons: list[str]
    missing_fields: list[str]
    errors: list[str]
    passed_checks: int
    total_checks: int


SUPPORTED_OPERATORS = {
    "==", "!=", ">", ">=", "<", "<=", "in", "not_in", "exists", "contains",
}
_MISSING = object()


def _outcome(
    status: RuleStatus,
    *,
    reasons: Iterable[str] = (),
    missing_fields: Iterable[str] = (),
    errors: Iterable[str] = (),
    passed_checks: int = 0,
    total_checks: int = 0,
) -> RuleOutcome:
    return {
        "status": status,
        "reasons": list(reasons),
        "missing_fields": list(dict.fromkeys(missing_fields)),
        "errors": list(dict.fromkeys(errors)),
        "passed_checks": passed_checks,
        "total_checks": total_checks,
    }


def _lookup(profile: dict[str, Any], field: str) -> Any:
    current: Any = profile
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _normal(value: Any) -> Any:
    return value.strip().casefold() if isinstance(value, str) else value


def _equal(actual: Any, expected: Any) -> bool:
    return _normal(actual) == _normal(expected)


def _compare(actual: Any, operator: str, expected: Any, *, exists: bool) -> bool:
    if operator == "exists":
        return exists == bool(expected)
    if operator == "==":
        return _equal(actual, expected)
    if operator == "!=":
        return not _equal(actual, expected)
    if operator in {">", ">=", "<", "<="}:
        if isinstance(actual, bool) or isinstance(expected, bool):
            raise TypeError("boolean cannot be used in numeric comparison")
        left = float(actual)
        right = float(expected)
        return {
            ">": left > right,
            ">=": left >= right,
            "<": left < right,
            "<=": left <= right,
        }[operator]
    if operator in {"in", "not_in"}:
        allowed = expected if isinstance(expected, (list, tuple, set)) else [expected]
        if isinstance(actual, (list, tuple, set)):
            matched = any(any(_equal(item, option) for option in allowed) for item in actual)
        else:
            matched = any(_equal(actual, option) for option in allowed)
        return matched if operator == "in" else not matched
    if operator == "contains":
        if isinstance(actual, str):
            return str(expected).casefold() in actual.casefold()
        if isinstance(actual, (list, tuple, set)):
            return any(_equal(item, expected) for item in actual)
        return False
    raise ValueError(f"unsupported operator: {operator}")


def _evaluate_leaf(node: dict[str, Any], profile: dict[str, Any]) -> RuleOutcome:
    field = node.get("field")
    operator = node.get("operator")
    if not isinstance(field, str) or not field.strip():
        return _outcome("error", errors=["Rule thiếu field"], total_checks=1)
    if operator not in SUPPORTED_OPERATORS:
        return _outcome(
            "error",
            errors=[f"Rule field '{field}' dùng operator không hỗ trợ: {operator}"],
            total_checks=1,
        )
    raw = _lookup(profile, field)
    exists = raw is not _MISSING and raw is not None
    if operator != "exists" and not exists:
        return _outcome(
            "unknown",
            reasons=[node.get("description") or f"Thiếu thông tin: {field}"],
            missing_fields=[field],
            total_checks=1,
        )
    try:
        passed = _compare(None if raw is _MISSING else raw, operator, node.get("value"), exists=exists)
    except (TypeError, ValueError) as exc:
        return _outcome(
            "error",
            errors=[f"Không thể đánh giá '{field} {operator}': {exc}"],
            total_checks=1,
        )
    description = node.get("description")
    reason = (
        f"{'Đạt' if passed else 'Không đạt'}: {description}"
        if description
        else (
            f"{'Đạt' if passed else 'Không đạt'} điều kiện {field} {operator} "
            f"{node.get('value')!r} (giá trị hiện tại: {None if raw is _MISSING else raw!r})."
        )
    )
    return _outcome(
        "pass" if passed else "fail",
        reasons=[reason],
        passed_checks=1 if passed else 0,
        total_checks=1,
    )


def _merge_group(kind: Literal["all", "any"], children: list[RuleOutcome]) -> RuleOutcome:
    if not children:
        return _outcome("error", errors=[f"Nhóm rules.{kind} đang rỗng"])
    statuses = [child["status"] for child in children]
    if "error" in statuses:
        status: RuleStatus = "error"
    elif kind == "all":
        status = "fail" if "fail" in statuses else "unknown" if "unknown" in statuses else "pass"
    else:
        status = "pass" if "pass" in statuses else "unknown" if "unknown" in statuses else "fail"
    return _outcome(
        status,
        reasons=[reason for child in children for reason in child["reasons"]],
        missing_fields=[field for child in children for field in child["missing_fields"]],
        errors=[error for child in children for error in child["errors"]],
        passed_checks=sum(child["passed_checks"] for child in children),
        total_checks=sum(child["total_checks"] for child in children),
    )


def evaluate_rules(node: Any, profile: dict[str, Any]) -> RuleOutcome:
    if not isinstance(node, dict):
        return _outcome("error", errors=["Rules phải là JSON object"])
    groups = []
    for kind in ("all", "any"):
        if kind not in node:
            continue
        raw_children = node.get(kind)
        if not isinstance(raw_children, list):
            groups.append(_outcome("error", errors=[f"rules.{kind} phải là array"]))
            continue
        groups.append(_merge_group(kind, [evaluate_rules(child, profile) for child in raw_children]))
    if groups:
        return groups[0] if len(groups) == 1 else _merge_group("all", groups)
    if "field" in node or "operator" in node:
        return _evaluate_leaf(node, profile)
    return _outcome("error", errors=["Rule phải có all, any hoặc field/operator"])


def policy_rules(policy: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(policy.get("rules"), dict):
        return policy["rules"]
    payload = policy.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("rules"), dict):
        return payload["rules"]
    return None


def evaluate(profile: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    rules = policy_rules(policy)
    outcome = (
        evaluate_rules(rules, profile)
        if rules is not None
        else _outcome("error", errors=["Policy không có rules hợp lệ"])
    )
    status_map: dict[RuleStatus, EligibilityStatus] = {
        "pass": "eligible",
        "fail": "not_eligible",
        "unknown": "needs_more_information",
        "error": "manual_review",
    }
    status = status_map[outcome["status"]]

    legal_status = str(
        policy.get("document_status") or policy.get("status") or "unknown"
    ).lower()
    warnings = []
    if legal_status in {"expired", "inactive", "not_yet_effective", "repealed", "superseded"}:
        status = "not_eligible"
        outcome["reasons"].append(f"Văn bản có trạng thái {legal_status}.")
    elif legal_status == "partially_effective":
        warnings.append("Văn bản chỉ còn hiệu lực một phần; cần kiểm tra phạm vi áp dụng.")
        if config.STRICT_LEGAL_STATUS and status == "eligible":
            status = "manual_review"
    elif legal_status == "unknown":
        warnings.append("Chưa xác minh trạng thái hiệu lực của văn bản.")
        if config.STRICT_LEGAL_STATUS and status == "eligible":
            status = "manual_review"

    total = outcome["total_checks"]
    score = outcome["passed_checks"] / total if total else 0.0
    return {
        "policy_id": policy.get("policy_id") or policy.get("id"),
        "policy_name": policy.get("policy_name") or policy.get("title") or "",
        "category": policy.get("category") or "",
        "status": status,
        "is_eligible": True if status == "eligible" else False if status == "not_eligible" else None,
        "score": round(score, 4),
        "reasons": outcome["reasons"],
        "missing_fields": outcome["missing_fields"],
        "rule_errors": outcome["errors"],
        "warnings": warnings,
        "checks": {"passed": outcome["passed_checks"], "total": outcome["total_checks"]},
        "evidence_unit_ids": list(policy.get("evidence_unit_ids") or []),
        "benefit_calculator": policy.get("benefit_calculator") or {},
        "required_documents": policy.get("required_documents") or [],
        "review_status": policy.get("review_status"),
    }


def evaluate_profile_against_all_policies(
    profile: dict[str, Any], policies: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [evaluate(profile, policy) for policy in policies]
