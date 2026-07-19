"""Canonical discovery metadata for the Golden Policy MVP."""

from __future__ import annotations

from collections import Counter


SCHEMA_VERSION = "policy-discovery-v1"
CANONICAL_TOPIC_BY_POLICY = {
    "decree_80_2021_nd_cp_ho_tro_thong_tin_a26213ed": "sme_information_support",
    "decree_80_2021_nd_cp_hd_dao_tao_truc_tuyen_d470ff1d": "sme_online_training",
    "decree_80_2021_nd_cp_hd_dao_tao_truc_tiep_d470ff1d": "sme_direct_training_manufacturing_processing",
    "circular_06_2022_tt_bkhdt_ho_tro_cong_nghe_48284a5c": "sme_digital_solution_rent_purchase",
}
CANONICAL_TOPIC_IDS = frozenset(CANONICAL_TOPIC_BY_POLICY.values())
ALLOWED_FIELDS = frozenset({"schema_version", "topic_id", "topic_label_vi", "search_terms_vi", "intent_examples_vi"})
CANONICAL_METADATA_BY_TOPIC = {
    "sme_information_support": {
        "topic_label_vi": "Hỗ trợ thông tin cho doanh nghiệp nhỏ và vừa",
        "search_terms_vi": ["hỗ trợ thông tin", "thông tin cho doanh nghiệp nhỏ và vừa", "cổng thông tin doanh nghiệp", "chương trình hỗ trợ doanh nghiệp", "tư vấn thông tin cho DNNVV"],
    },
    "sme_online_training": {
        "topic_label_vi": "Đào tạo trực tuyến cho doanh nghiệp nhỏ và vừa",
        "search_terms_vi": ["đào tạo trực tuyến", "khóa học online", "đào tạo khởi sự kinh doanh", "đào tạo quản trị doanh nghiệp", "khóa học cho DNNVV"],
    },
    "sme_direct_training_manufacturing_processing": {
        "topic_label_vi": "Đào tạo trực tiếp cho DNNVV sản xuất, chế biến",
        "search_terms_vi": ["đào tạo trực tiếp", "đào tạo tại doanh nghiệp", "đào tạo doanh nghiệp sản xuất", "đào tạo doanh nghiệp chế biến", "hỗ trợ chi phí đào tạo trực tiếp"],
    },
    "sme_digital_solution_rent_purchase": {
        "topic_label_vi": "Hỗ trợ thuê hoặc mua giải pháp chuyển đổi số",
        "search_terms_vi": ["hỗ trợ chuyển đổi số", "thuê giải pháp chuyển đổi số", "mua giải pháp chuyển đổi số", "hỗ trợ phần mềm cho DNNVV", "chi phí giải pháp số"],
    },
}
OUT_OF_SCOPE_TERMS = ("thuế tndn", "ưu đãi thuế", "natif", "vay vốn", "bằng sáng chế", "doanh nghiệp khởi nghiệp sáng tạo")


def _issue(code: str, path: str, message: str) -> dict:
    return {"code": code, "severity": "blocking", "path": path, "message": message}


def _non_empty_strings(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def validate_discovery(policy: dict, catalog: dict) -> list[dict]:
    """Validate metadata without interpreting it as a company rule."""
    policy_id = policy.get("policy_id")
    discovery = policy.get("discovery")
    expected_topic = CANONICAL_TOPIC_BY_POLICY.get(policy_id)
    if discovery is None:
        requested_status = policy.get("review_status") or (policy.get("review") or {}).get("status")
        return [_issue("discovery_missing", "discovery", "Approved Golden Policy requires discovery metadata")] if expected_topic and requested_status == "approved" else []
    if not isinstance(discovery, dict):
        return [_issue("discovery_invalid", "discovery", "Discovery metadata must be an object")]

    issues = []
    unknown = set(discovery) - ALLOWED_FIELDS
    if unknown:
        issues.append(_issue("discovery_unknown_field", "discovery", f"Unsupported discovery fields: {sorted(unknown)}"))
    if discovery.get("schema_version") != SCHEMA_VERSION:
        issues.append(_issue("discovery_schema_invalid", "discovery.schema_version", f"Expected {SCHEMA_VERSION}"))
    topic_id = discovery.get("topic_id")
    if topic_id not in CANONICAL_TOPIC_IDS:
        issues.append(_issue("discovery_topic_invalid", "discovery.topic_id", "topic_id is outside the Golden Policy MVP taxonomy"))
    elif expected_topic != topic_id:
        issues.append(_issue("discovery_topic_mismatch", "discovery.topic_id", f"Expected {expected_topic!r} for {policy_id}"))
    elif discovery.get("topic_label_vi") != CANONICAL_METADATA_BY_TOPIC[topic_id]["topic_label_vi"] or discovery.get("search_terms_vi") != CANONICAL_METADATA_BY_TOPIC[topic_id]["search_terms_vi"]:
        issues.append(_issue("discovery_canonical_metadata_mismatch", "discovery", "Topic label/search terms differ from the canonical v1 taxonomy"))
    if not isinstance(discovery.get("topic_label_vi"), str) or not discovery["topic_label_vi"].strip():
        issues.append(_issue("discovery_label_invalid", "discovery.topic_label_vi", "Vietnamese topic label is required"))
    for field in ("search_terms_vi", "intent_examples_vi"):
        if not _non_empty_strings(discovery.get(field)):
            issues.append(_issue("discovery_terms_invalid", f"discovery.{field}", f"{field} must be a non-empty string list"))
    searchable_text = " ".join(str(value) for field in ("topic_label_vi", "search_terms_vi", "intent_examples_vi") for value in (discovery.get(field) if isinstance(discovery.get(field), list) else [discovery.get(field) or ""])).casefold()
    leaked = [term for term in OUT_OF_SCOPE_TERMS if term in searchable_text]
    if leaked:
        issues.append(_issue("discovery_out_of_scope_term", "discovery", f"Out-of-MVP discovery terms are forbidden: {leaked}"))

    # Discovery has a deliberately closed shape. Fact Catalog fields and rule
    # structures may only appear under policy.rules, never under discovery.
    forbidden = (set(catalog.get("fields") or {}) | {"field", "rules", "conditions", "fact_source"}) & set(discovery)
    if forbidden:
        issues.append(_issue("discovery_contains_company_fact", "discovery", f"Company fact/rule fields are forbidden: {sorted(forbidden)}"))
    return issues


def validate_discovery_collection(policies: list[dict], catalog: dict) -> None:
    """Fail closed on invalid Golden metadata or duplicate canonical topics."""
    issues = [(policy.get("policy_id"), item) for policy in policies for item in validate_discovery(policy, catalog)]
    topics = [policy["discovery"]["topic_id"] for policy in policies if isinstance(policy.get("discovery"), dict)]
    duplicates = sorted(topic for topic, count in Counter(topics).items() if count > 1)
    if duplicates:
        issues.append(("collection", _issue("discovery_topic_duplicate", "discovery.topic_id", f"Duplicate topics: {duplicates}")))
    if issues:
        details = "; ".join(f"{policy_id}: {item['code']}" for policy_id, item in issues)
        raise ValueError(f"Invalid policy discovery metadata: {details}")
