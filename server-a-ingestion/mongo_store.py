"""MongoDB persistence for legal documents, immutable versions, and legal units."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import certifi
from pymongo import MongoClient, ReplaceOne


MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGODB_DB") or os.getenv("MONGO_DB", "grantpilot")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def checksum_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def database():
    kwargs = {"serverSelectionTimeoutMS": 5000}
    if "mongodb+srv" in MONGO_URI or "mongodb.net" in MONGO_URI:
        kwargs["tlsCAFile"] = certifi.where()
    client = MongoClient(MONGO_URI, **kwargs)
    client.admin.command("ping")
    return client, client[MONGO_DB]


def ensure_indexes(db) -> None:
    db.legal_documents.create_index([("document_id", 1), ("version", 1)], unique=True)
    db.legal_documents.create_index([("document_id", 1), ("is_current", 1)])
    db.legal_documents.create_index("checksum")
    db.legal_units.create_index([("document_id", 1), ("version", 1), ("unit_id", 1)], unique=True)
    db.legal_units.create_index([("document_number", 1), ("article", 1), ("clause", 1), ("point", 1), ("is_current", 1)])
    db.legal_units.create_index([("document_id", 1), ("version", 1), ("is_current", 1)])
    db.policies.create_index([("policy_id", 1), ("document_id", 1), ("document_version", 1)], unique=True)
    db.policies.create_index([("document_id", 1), ("document_version", 1), ("is_current", 1)])
    db.policies.create_index("review_status")
    db.policies.create_index("canonical_policy_key")
    db.policies.create_index([("eligible_for_decision", 1), ("review_status", 1), ("is_current", 1)])


def ingest_document(db, pdf_path, source: dict, units: Iterable[dict]) -> dict:
    """Insert a new immutable version, or return the existing version for same checksum."""
    checksum = checksum_file(pdf_path)
    existing_checksum = db.legal_documents.find_one(
        {"document_id": source["document_id"], "checksum": checksum},
        {"version": 1, "checksum": 1, "is_current": 1},
    )
    if existing_checksum:
        metadata = {
            "document_title": source.get("document_title", ""),
            "document_number": source.get("document_number", ""),
            "issued_date": source.get("issued_date"),
            "effective_from": source.get("effective_from"),
            "effective_to": source.get("effective_to"),
            "status": source.get("status", "unknown"),
            "legal_status_checked_at": source.get("legal_status_checked_at"),
            "source_url": source.get("source_url", ""),
            "updated_at": utcnow(),
        }
        db.legal_documents.update_one(
            {"document_id": source["document_id"], "version": existing_checksum["version"]}, {"$set": metadata}
        )
        db.legal_units.update_many(
            {"document_id": source["document_id"], "version": existing_checksum["version"]},
            {"$set": {"document_status": metadata["status"], "issued_date": metadata["issued_date"], "effective_from": metadata["effective_from"], "effective_to": metadata["effective_to"], "source_url": metadata["source_url"], "legal_status_checked_at": metadata["legal_status_checked_at"], "updated_at": metadata["updated_at"]}},
        )
        return {
            "document_id": source["document_id"],
            "version": existing_checksum["version"],
            "created": False,
            "checksum": checksum,
            "is_current": existing_checksum.get("is_current", False),
        }

    last = db.legal_documents.find_one({"document_id": source["document_id"]}, sort=[("version", -1)])
    version = int(last["version"]) + 1 if last else 1
    now = utcnow()
    db.legal_documents.update_many(
        {"document_id": source["document_id"], "is_current": True},
        {"$set": {"is_current": False, "status": "superseded", "updated_at": now}},
    )
    db.legal_units.update_many(
        {"document_id": source["document_id"], "is_current": True},
        {"$set": {"is_current": False, "updated_at": now}},
    )
    document = {
        "document_id": source["document_id"],
        "version": version,
        "is_current": True,
        "document_number": source.get("document_number", ""),
        "document_title": source.get("document_title", ""),
        "issued_date": source.get("issued_date"),
        "effective_from": source.get("effective_from"),
        "effective_to": source.get("effective_to"),
        "status": source.get("status", "unknown"),
        "legal_status_checked_at": source.get("legal_status_checked_at"),
        "source_url": source.get("source_url", ""),
        "source_file": source.get("file", ""),
        "checksum": checksum,
        "ingested_at": now,
        "updated_at": now,
    }
    db.legal_documents.insert_one(document)
    unit_rows = []
    for unit in units:
        normalized = " ".join(str(unit.get("text", "")).split())
        row = {k: unit.get(k, "") for k in (
            "unit_id", "document_id", "document_number", "document_title", "article", "article_title",
            "clause", "point", "chapter", "section", "page_start", "page_end", "source_url", "text",
        )}
        row.update({
            "normalized_text": normalized,
            "version": version,
            "is_current": True,
            "document_status": source.get("status", "unknown"),
            "issued_date": source.get("issued_date"),
            "effective_from": source.get("effective_from"),
            "effective_to": source.get("effective_to"),
            "checksum": checksum,
            "ingested_at": now,
            "updated_at": now,
        })
        unit_rows.append(row)
    if unit_rows:
        db.legal_units.insert_many(unit_rows, ordered=False)
    return {"document_id": source["document_id"], "version": version, "created": True, "checksum": checksum, "units": len(unit_rows)}


def current_units(db, document_ids: set[str] | None = None) -> list[dict]:
    query = {"is_current": True}
    if document_ids:
        query["document_id"] = {"$in": list(document_ids)}
    return list(db.legal_units.find(query, {"_id": 0}))


def ingest_policies(db, policies: Iterable[dict]) -> dict:
    """Persist policies only after the same Fact Catalog/evidence gate used by pipeline."""
    from pipeline import POLICY_RULE_SCHEMA_VERSION, REVIEW_STATUSES, normalize_rules, policy_is_decision_eligible

    current_versions = {
        row["document_id"]: row["version"]
        for row in db.legal_documents.find({"is_current": True}, {"_id": 0, "document_id": 1, "version": 1})
    }
    operations = []
    now = utcnow()
    for policy in policies:
        policy = dict(policy)
        pipeline = policy.get("pipeline") or {}
        legal_source = policy.get("legal_source") or {}
        document_id = pipeline.get("document_id")
        if not document_id:
            local_file = str(legal_source.get("local_file", "")).split("/")[-1]
            document = db.legal_documents.find_one({"source_file": local_file, "is_current": True}, {"document_id": 1})
            document_id = document.get("document_id") if document else "unmapped"
        document_version = current_versions.get(document_id)
        normalized_rules, warnings, blocking_status = normalize_rules(policy.get("rules", {"all": []}))
        review_status = policy.get("review_status") or (policy.get("review") or {}).get("status") or "candidate"
        if review_status not in REVIEW_STATUSES:
            review_status = "candidate"
            warnings.append("review_status cũ đã được chuyển thành candidate")
        if blocking_status:
            review_status = blocking_status
        evidence = list(dict.fromkeys(policy.get("evidence_unit_ids") or []))
        valid_evidence = set()
        if document_version is not None and evidence:
            valid_evidence = {
                row["unit_id"]
                for row in db.legal_units.find(
                    {"document_id": document_id, "version": document_version, "unit_id": {"$in": evidence}},
                    {"_id": 0, "unit_id": 1},
                )
            }
        missing_evidence = [unit_id for unit_id in evidence if unit_id not in valid_evidence]
        if not document_version:
            warnings.append("document_id không tồn tại ở legal_documents current")
            review_status = "rejected"
        if missing_evidence or not evidence:
            warnings.append("evidence_unit_ids thiếu hoặc không tồn tại trong legal_units current")
            review_status = "rejected"
        policy.update(
            {
                "rules": normalized_rules,
                "normalized_rules": normalized_rules,
                "normalization_warnings": list(dict.fromkeys([*(policy.get("normalization_warnings") or []), *warnings])),
                "policy_rule_schema_version": policy.get("policy_rule_schema_version", POLICY_RULE_SCHEMA_VERSION),
                "review_status": review_status,
                "evidence_unit_ids": evidence,
                "source_document_version": document_version,
            }
        )
        policy.setdefault("review", {})["status"] = review_status
        # A policy cannot be decision-ready when its source document version is no longer current.
        policy["is_current"] = bool(policy.get("is_current", True) and document_id in current_versions)
        policy["eligible_for_decision"] = policy_is_decision_eligible(policy)
        row = {
            "policy_id": policy["policy_id"],
            "document_id": document_id,
            "document_version": document_version,
            "is_current": policy["is_current"],
            "policy_name": policy.get("policy_name", ""),
            "category": policy.get("category", ""),
            "review_status": review_status,
            "eligible_for_decision": policy["eligible_for_decision"],
            "evidence_unit_ids": evidence,
            "evidence_resolution": policy.get("evidence_resolution", "unresolved"),
            "requires_evidence_review": bool(policy.get("requires_evidence_review", True)),
            "policy_rule_schema_version": policy["policy_rule_schema_version"],
            "canonical_policy_key": policy.get("canonical_policy_key", ""),
            "normalized_rule_hash": policy.get("normalized_rule_hash", ""),
            "duplicate_group_id": policy.get("duplicate_group_id"),
            "supersedes_policy_id": policy.get("supersedes_policy_id"),
            "normalized_rules": normalized_rules,
            "normalization_warnings": policy["normalization_warnings"],
            "source_document_version": document_version,
            "payload": policy,
            "updated_at": now,
        }
        operations.append(
            ReplaceOne(
                {"policy_id": row["policy_id"], "document_id": document_id, "document_version": document_version},
                {**row, "ingested_at": now},
                upsert=True,
            )
        )
    if not operations:
        return {"upserted": 0}
    result = db.policies.bulk_write(operations, ordered=False)
    return {"upserted": result.upserted_count, "updated": result.modified_count, "total": len(operations)}


# Canonical writer: do not trust client evidence/review/eligibility metadata.
def ingest_policies(db, policies: Iterable[dict]) -> dict:
    from policy_normalization import apply_duplicates, prepare_policy_for_ingest

    prepared = [prepare_policy_for_ingest(policy, db) for policy in policies]
    apply_duplicates(prepared)
    timestamp = utcnow()
    operations = []
    for policy in prepared:
        row = {key: policy.get(key) for key in (
            "policy_id", "policy_name", "category", "document_id", "document_version", "source_document_version",
            "is_current", "review_status", "eligible_for_decision", "evidence_unit_ids", "evidence_resolution",
            "requires_evidence_review", "policy_rule_schema_version", "fact_catalog_version", "canonical_policy_key",
            "normalized_rule_hash", "duplicate_group_id", "superseded_by_policy_id", "normalized_rules",
            "validation_issues_current", "validation_history", "policy_parameters",
        )}
        row.update({"payload": policy, "updated_at": timestamp})
        operations.append(ReplaceOne(
            {"policy_id": row["policy_id"], "document_id": row["document_id"], "document_version": row["document_version"]},
            {**row, "ingested_at": timestamp}, upsert=True,
        ))
    if not operations:
        return {"total": 0, "upserted": 0, "updated": 0}
    result = db.policies.bulk_write(operations, ordered=False)
    return {"total": len(operations), "upserted": result.upserted_count, "updated": result.modified_count}
