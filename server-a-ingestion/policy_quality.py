"""Canonical policy schema, evidence repair, and validation for MongoDB ingestion."""

from __future__ import annotations

import copy
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from pymongo import ReplaceOne


ALLOWED_OPERATORS = {"==", "!=", ">", ">=", "<", "<=", "in", "not_in", "exists"}

# Legacy records that have the same user-facing support as a newer extracted record.
DIRECT_DUPLICATES = {
    "law04_art08_credit_access",
    "law04_art11_production_premises",
    "law04_art12_technology_support",
    "law04_art16_household_conversion",
    "law04_art19_cluster_value_chain",
}

FIELD_ALIASES = {
    "loai_doanh_nghiep": "business_type",
    "loai_hinh_doanh_nghiep": "business_type",
    "loai_doanh_nghiep_": "business_type",
    "loai_hinh_kinh_doanh": "business_type",
    "nganh_hoat_dong": "industry",
    "nganh_nghe_kinh_doanh": "industry",
    "nganh_nghe_kd": "industry",
    "linh_vuc_hoat_dong": "industry",
    "quy_mo_kd": "enterprise_size",
    "thoi_gian_thanh_lap": "company_age_years",
    "thoi_gian_hoat_dong": "company_age_years",
    "truoc_do_la_ho_kinh_doanh": "converted_from_registered_household_business",
    "da_dang_ky_va_hoat_dong": "is_registered_and_operating",
    "hoat_dong_lien_tuc": "household_business_continuous_years",
    "chao_ban_chung_khoan": "has_public_offering",
}


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFD", str(value)).replace("đ", "d").replace("Đ", "D")
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def canonical_field(value: str) -> str:
    if value.startswith("extra_attributes."):
        return value
    slug = _slug(value)
    if slug in FIELD_ALIASES:
        return FIELD_ALIASES[slug]
    # Existing English schema fields are already canonical.
    standard = {
        "is_sme", "enterprise_size", "industry", "province", "num_employees", "annual_revenue",
        "has_collateral", "has_feasible_business_plan", "has_credit_rating", "has_foreign_investment_capital",
        "has_state_capital", "organization_type", "sme_participation_ratio", "products_made_in_vietnam",
        "converted_from_registered_household_business", "household_business_continuous_years",
        "is_innovative_startup", "company_age_years", "legal_form", "has_public_offering",
        "investment_target_is_sme_innovative_startup", "selected_startup_fund_exists", "sector_group",
        "has_competitive_product", "has_process_or_technology_innovation", "participates_in_cluster_or_value_chain",
        "business_type", "founded_year",
    }
    return slug if slug in standard else f"extra_attributes.{slug}"


def canonicalize_rules(node: dict[str, Any]) -> dict[str, Any]:
    if "all" in node or "any" in node:
        result: dict[str, Any] = {}
        for group in ("all", "any"):
            if group in node:
                result[group] = [canonicalize_rules(child) for child in node[group]]
        return result
    result = copy.deepcopy(node)
    result["field"] = canonical_field(str(result.get("field", "")))
    if result.get("operator") == "contains":
        # Canonical `in` means the profile value must be one of the allowed values.
        result["operator"] = "in"
        result["value"] = result["value"] if isinstance(result.get("value"), list) else [result.get("value")]
    return result


def _article_from_legacy(policy: dict[str, Any]) -> str:
    source = (policy.get("payload") or policy).get("legal_source") or {}
    match = re.search(r"Điều\s+(\d+)", str(source.get("article", "")), re.IGNORECASE)
    return match.group(1) if match else ""


def resolve_legacy_evidence(db, policy: dict[str, Any]) -> list[str]:
    """Use all units in the cited article; each ID is validated against MongoDB."""
    article = _article_from_legacy(policy)
    if not article:
        return []
    rows = db.legal_units.find(
        {
            "document_id": policy["document_id"],
            "version": policy["document_version"],
            "is_current": True,
            "article": article,
        },
        {"_id": 0, "unit_id": 1, "clause": 1, "point": 1},
    )
    return [row["unit_id"] for row in rows]


def normalize_policy(db, policy: dict[str, Any]) -> dict[str, Any]:
    """Move eligibility fields to top level and repair legacy evidence."""
    policy = copy.deepcopy(policy)
    payload = policy.get("payload") or {}
    policy["policy_name"] = policy.get("policy_name") or payload.get("policy_name", "")
    policy["category"] = policy.get("category") or payload.get("category", "")
    policy["rules_version"] = 1
    policy["rules"] = canonicalize_rules(policy.get("rules") or payload.get("rules") or {})
    policy["benefit_calculator"] = policy.get("benefit_calculator") or payload.get("benefit_calculator") or {}
    policy["required_documents"] = policy.get("required_documents") or payload.get("required_documents") or []
    policy["review_status"] = policy.get("review_status") or (payload.get("review") or {}).get("status", "unknown")
    policy["evidence_unit_ids"] = list(policy.get("evidence_unit_ids") or payload.get("evidence_unit_ids") or [])
    if policy.get("is_current") and not policy["evidence_unit_ids"]:
        policy["evidence_unit_ids"] = resolve_legacy_evidence(db, policy)
    return policy


def _walk_conditions(node: dict[str, Any]):
    if "all" in node or "any" in node:
        for group in ("all", "any"):
            for child in node.get(group, []):
                yield from _walk_conditions(child)
    else:
        yield node


def validate_policy_collection(db, strict_document_status: bool = False) -> list[str]:
    errors: list[str] = []
    duplicate_ids = list(
        db.policies.aggregate([
            {"$match": {"is_current": True}},
            {"$group": {"_id": "$policy_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
        ])
    )
    errors.extend(f"duplicate current policy_id={row['_id']}" for row in duplicate_ids)
    valid_unit_ids = {row["unit_id"] for row in db.legal_units.find({"is_current": True}, {"_id": 0, "unit_id": 1})}
    current_documents = {
        row["document_id"]: row
        for row in db.legal_documents.find({"is_current": True}, {"_id": 0, "document_id": 1, "status": 1})
    }
    for policy in db.policies.find({"is_current": True}, {"_id": 0}):
        policy_id = policy["policy_id"]
        evidence = policy.get("evidence_unit_ids") or []
        if not evidence:
            errors.append(f"{policy_id}: missing evidence")
        for unit_id in evidence:
            if unit_id not in valid_unit_ids:
                errors.append(f"{policy_id}: evidence missing legal_unit {unit_id}")
        rules = policy.get("rules") or {}
        if not isinstance(rules, dict) or not (rules.get("all") or rules.get("any")):
            errors.append(f"{policy_id}: missing rules.all/rules.any")
        for condition in _walk_conditions(rules):
            if not condition.get("field") or not condition.get("operator") or "value" not in condition:
                errors.append(f"{policy_id}: incomplete rule")
            elif condition["operator"] not in ALLOWED_OPERATORS:
                errors.append(f"{policy_id}: unsupported operator {condition['operator']}")
        document = current_documents.get(policy.get("document_id"))
        if not document:
            errors.append(f"{policy_id}: missing current legal_document")
        elif strict_document_status and document.get("status") == "unknown":
            errors.append(f"{policy_id}: document status is unknown")
    return errors


def validate_policy_for_ingest(db, policy: dict[str, Any], strict_document_status: bool = False) -> list[str]:
    """Validate one normalized policy before it is written to MongoDB."""
    errors: list[str] = []
    policy_id = policy.get("policy_id", "<missing policy_id>")
    evidence = policy.get("evidence_unit_ids") or []
    if not evidence:
        errors.append(f"{policy_id}: missing evidence")
    existing_units = {
        row["unit_id"]
        for row in db.legal_units.find(
            {"unit_id": {"$in": evidence}, "is_current": True}, {"_id": 0, "unit_id": 1}
        )
    }
    errors.extend(f"{policy_id}: evidence missing legal_unit {unit_id}" for unit_id in evidence if unit_id not in existing_units)
    rules = policy.get("rules") or {}
    if not isinstance(rules, dict) or not (rules.get("all") or rules.get("any")):
        errors.append(f"{policy_id}: missing rules.all/rules.any")
    for condition in _walk_conditions(rules):
        if not condition.get("field") or not condition.get("operator") or "value" not in condition:
            errors.append(f"{policy_id}: incomplete rule")
        elif condition["operator"] not in ALLOWED_OPERATORS:
            errors.append(f"{policy_id}: unsupported operator {condition['operator']}")
    document = db.legal_documents.find_one(
        {"document_id": policy.get("document_id"), "version": policy.get("document_version"), "is_current": True},
        {"_id": 0, "status": 1},
    )
    if not document:
        errors.append(f"{policy_id}: missing current legal_document")
    elif strict_document_status and document.get("status") == "unknown":
        errors.append(f"{policy_id}: document status is unknown")
    return errors


def prepare_policy_for_ingest(db, raw_policy: dict[str, Any]) -> dict[str, Any]:
    """Attach current document/version then normalize before MongoDB upsert."""
    pipeline = raw_policy.get("pipeline") or {}
    source = raw_policy.get("legal_source") or {}
    document_id = pipeline.get("document_id")
    if not document_id:
        local_file = str(source.get("local_file", "")).split("/")[-1]
        document = db.legal_documents.find_one({"source_file": local_file, "is_current": True}, {"document_id": 1, "version": 1})
    else:
        document = db.legal_documents.find_one({"document_id": document_id, "is_current": True}, {"document_id": 1, "version": 1})
    if not document:
        raise ValueError(f"{raw_policy.get('policy_id')}: cannot resolve current document")
    policy = {
        "policy_id": raw_policy["policy_id"],
        "policy_name": raw_policy.get("policy_name", ""),
        "category": raw_policy.get("category", ""),
        "document_id": document["document_id"],
        "document_version": document["version"],
        "is_current": True,
        "evidence_unit_ids": raw_policy.get("evidence_unit_ids", []),
        "review_status": (raw_policy.get("review") or {}).get("status", "unknown"),
        "payload": raw_policy,
    }
    policy = normalize_policy(db, policy)
    if policy["policy_id"] in DIRECT_DUPLICATES:
        policy["is_current"] = False
        policy["review_status"] = "superseded"
        policy["superseded_reason"] = "duplicate_of_newer_extracted_policy"
    return policy


def ingest_policies(db, raw_policies: list[dict[str, Any]], strict_document_status: bool = False) -> dict[str, Any]:
    """Validate the whole batch before making any policy write."""
    prepared = [prepare_policy_for_ingest(db, raw) for raw in raw_policies]
    duplicate_ids = [policy_id for policy_id, count in Counter(p["policy_id"] for p in prepared).items() if count > 1]
    errors = [f"duplicate incoming policy_id={policy_id}" for policy_id in duplicate_ids]
    for policy in prepared:
        if policy.get("is_current"):
            errors.extend(validate_policy_for_ingest(db, policy, strict_document_status))
    if errors:
        raise ValueError("Policy ingestion rejected:\n" + "\n".join(errors))
    now = datetime.now(timezone.utc)
    operations = []
    for policy in prepared:
        policy["updated_at"] = now
        operations.append(
            ReplaceOne(
                {"policy_id": policy["policy_id"], "document_id": policy["document_id"], "document_version": policy["document_version"]},
                {**policy, "ingested_at": now},
                upsert=True,
            )
        )
    result = db.policies.bulk_write(operations, ordered=True)
    return {"total": len(prepared), "upserted": result.upserted_count, "updated": result.modified_count}


def repair_policies(db) -> dict[str, Any]:
    """Apply canonical schema and only supersede direct legacy duplicates."""
    now = datetime.now(timezone.utc)
    superseded = []
    updated = 0
    for raw in db.policies.find({"is_current": True}):
        policy = normalize_policy(db, raw)
        if policy["policy_id"] in DIRECT_DUPLICATES:
            policy["is_current"] = False
            policy["review_status"] = "superseded"
            policy["superseded_reason"] = "duplicate_of_newer_extracted_policy"
            policy["superseded_at"] = now
            superseded.append(policy["policy_id"])
        policy["updated_at"] = now
        db.policies.replace_one({"_id": raw["_id"]}, policy)
        updated += 1
    errors = validate_policy_collection(db)
    return {"updated": updated, "superseded": superseded, "validation_errors": errors}


def field_and_operator_inventory(db) -> tuple[list[str], list[str]]:
    fields: Counter[str] = Counter()
    operators: Counter[str] = Counter()
    for policy in db.policies.find({"is_current": True}, {"_id": 0, "rules": 1}):
        for condition in _walk_conditions(policy.get("rules") or {}):
            fields[condition.get("field", "")] += 1
            operators[condition.get("operator", "")] += 1
    return sorted(field for field in fields if field), sorted(operator for operator in operators if operator)
