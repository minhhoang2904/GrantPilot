"""Mongo persistence for immutable legal versions and canonical policies."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
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
    options = {"serverSelectionTimeoutMS": 5000}
    if "mongodb+srv" in MONGO_URI or "mongodb.net" in MONGO_URI:
        options["tlsCAFile"] = certifi.where()
    client = MongoClient(MONGO_URI, **options)
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
            "document_title": source.get("document_title", ""), "document_number": source.get("document_number", ""),
            "issued_date": source.get("issued_date"), "effective_from": source.get("effective_from"),
            "effective_to": source.get("effective_to"), "status": source.get("status", "unknown"),
            "legal_status_checked_at": source.get("legal_status_checked_at"), "source_url": source.get("source_url", ""),
            "updated_at": utcnow(),
        }
        db.legal_documents.update_one(
            {"document_id": source["document_id"], "version": existing_checksum["version"]}, {"$set": metadata}
        )
        db.legal_units.update_many(
            {"document_id": source["document_id"], "version": existing_checksum["version"]},
            {"$set": {"document_status": metadata["status"], "issued_date": metadata["issued_date"],
                      "effective_from": metadata["effective_from"], "effective_to": metadata["effective_to"],
                      "source_url": metadata["source_url"], "legal_status_checked_at": metadata["legal_status_checked_at"],
                      "updated_at": metadata["updated_at"]}},
        )
        return {"document_id": source["document_id"], "version": existing_checksum["version"], "created": False,
                "checksum": checksum, "is_current": existing_checksum.get("is_current", False)}

    last = db.legal_documents.find_one({"document_id": source["document_id"]}, sort=[("version", -1)])
    version = int(last["version"]) + 1 if last else 1
    now = utcnow()
    db.legal_documents.update_many({"document_id": source["document_id"], "is_current": True},
                                   {"$set": {"is_current": False, "status": "superseded", "updated_at": now}})
    db.legal_units.update_many({"document_id": source["document_id"], "is_current": True},
                               {"$set": {"is_current": False, "updated_at": now}})
    document = {
        "document_id": source["document_id"], "version": version, "is_current": True,
        "document_number": source.get("document_number", ""), "document_title": source.get("document_title", ""),
        "issued_date": source.get("issued_date"), "effective_from": source.get("effective_from"),
        "effective_to": source.get("effective_to"), "status": source.get("status", "unknown"),
        "legal_status_checked_at": source.get("legal_status_checked_at"), "source_url": source.get("source_url", ""),
        "source_file": source.get("file", ""), "checksum": checksum, "ingested_at": now, "updated_at": now,
    }
    db.legal_documents.insert_one(document)
    unit_rows = []
    for unit in units:
        row = {key: unit.get(key, "") for key in (
            "unit_id", "document_id", "document_number", "document_title", "article", "article_title",
            "clause", "point", "chapter", "section", "page_start", "page_end", "source_url", "text",
        )}
        row.update({"normalized_text": " ".join(str(unit.get("text", "")).split()), "version": version,
                    "is_current": True, "document_status": source.get("status", "unknown"),
                    "issued_date": source.get("issued_date"), "effective_from": source.get("effective_from"),
                    "effective_to": source.get("effective_to"), "checksum": checksum, "ingested_at": now, "updated_at": now})
        unit_rows.append(row)
    if unit_rows:
        db.legal_units.insert_many(unit_rows, ordered=False)
    return {"document_id": source["document_id"], "version": version, "created": True, "checksum": checksum,
            "units": len(unit_rows)}


def current_units(db, document_ids: set[str] | None = None) -> list[dict]:
    query = {"is_current": True}
    if document_ids:
        query["document_id"] = {"$in": list(document_ids)}
    return list(db.legal_units.find(query, {"_id": 0}))


def _policy_row(policy: dict, timestamp: datetime) -> dict:
    fields = (
        "policy_id", "policy_name", "category", "document_id", "document_version", "source_document_version",
        "is_current", "review_status", "eligible_for_decision", "evidence_unit_ids", "evidence_resolution",
        "requires_evidence_review", "policy_rule_schema_version", "fact_catalog_version", "canonical_policy_key",
        "normalized_rule_hash", "duplicate_group_id", "superseded_by_policy_id", "normalized_rules",
        "validation_issues_current", "validation_history", "policy_parameters",
    )
    payload = dict(policy)
    # A Mongo persistence row may have been read back during duplicate handling.
    # Store only the canonical artifact, never a row containing another payload.
    payload.pop("payload", None)
    return {**{field: payload.get(field) for field in fields}, "payload": payload,
            "updated_at": timestamp, "ingested_at": timestamp}


def _identity(policy: dict) -> tuple[object, object, object]:
    return policy["policy_id"], policy["document_id"], policy["document_version"]


def _canonical_existing(row: dict) -> dict:
    """Hydrate the prior canonical payload, then apply its persisted state fields."""
    policy = dict(row.get("payload") or {})
    policy.pop("payload", None)
    state_fields = (
        "policy_id", "policy_name", "category", "document_id", "document_version", "source_document_version",
        "is_current", "review_status", "eligible_for_decision", "evidence_unit_ids", "evidence_resolution",
        "requires_evidence_review", "policy_rule_schema_version", "fact_catalog_version", "canonical_policy_key",
        "normalized_rule_hash", "duplicate_group_id", "superseded_by_policy_id", "normalized_rules",
        "validation_issues_current", "validation_history", "policy_parameters",
    )
    policy.update({field: row[field] for field in state_fields if field in row})
    return policy


def ingest_policies(db, policies: Iterable[dict]) -> dict:
    """Normalize once, then persist every changed batch or existing duplicate row."""
    from policy_normalization import apply_duplicates, prepare_policy_for_ingest

    batch = [prepare_policy_for_ingest(policy, db) for policy in policies]
    batch_by_identity = {_identity(policy): policy for policy in batch}
    batch = list(batch_by_identity.values())
    existing = []
    seen_keys = set()
    for policy in batch:
        key = policy["canonical_policy_key"]
        if key in seen_keys:
            continue
        seen_keys.add(key)
        for row in db.policies.find({"canonical_policy_key": key, "is_current": True}, {"_id": 0}):
            policy = _canonical_existing(row)
            # Re-ingest of the same identity replaces it with the incoming artifact
            # before semantic duplicate grouping, preventing self-supersession.
            if _identity(policy) not in batch_by_identity:
                existing.append(policy)

    # This includes existing records intentionally: if an incoming policy wins, its
    # old Mongo duplicate must be persisted as superseded in this same bulk write.
    rows = apply_duplicates([*existing, *batch])
    timestamp = utcnow()
    operations = []
    identities = set()
    for policy in rows:
        identity = _identity(policy)
        if identity in identities:
            continue
        if policy.get("superseded_by_policy_id") == policy["policy_id"]:
            raise RuntimeError("A policy cannot supersede itself")
        identities.add(identity)
        operations.append(ReplaceOne(
            {"policy_id": identity[0], "document_id": identity[1], "document_version": identity[2]},
            _policy_row(policy, timestamp), upsert=True,
        ))
    if not operations:
        return {"total": 0, "upserted": 0, "updated": 0}
    result = db.policies.bulk_write(operations, ordered=False)
    return {"total": len(operations), "upserted": result.upserted_count, "updated": result.modified_count}
