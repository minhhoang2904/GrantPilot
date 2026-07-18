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
    """Insert an immutable source version, or refresh metadata for the same checksum."""
    checksum = checksum_file(pdf_path)
    existing = db.legal_documents.find_one(
        {"document_id": source["document_id"], "checksum": checksum}, {"version": 1, "is_current": 1}
    )
    if existing:
        stamp = utcnow()
        metadata = {key: source.get(key) for key in (
            "document_title", "document_number", "issued_date", "effective_from", "effective_to",
            "status", "legal_status_checked_at", "source_url",
        )}
        metadata["updated_at"] = stamp
        db.legal_documents.update_one(
            {"document_id": source["document_id"], "version": existing["version"]}, {"$set": metadata}
        )
        db.legal_units.update_many(
            {"document_id": source["document_id"], "version": existing["version"]},
            {"$set": {**metadata, "document_status": source.get("status", "unknown")}},
        )
        return {"document_id": source["document_id"], "version": existing["version"], "created": False,
                "checksum": checksum, "is_current": existing.get("is_current", False)}

    previous = db.legal_documents.find_one({"document_id": source["document_id"]}, sort=[("version", -1)])
    version = int(previous["version"]) + 1 if previous else 1
    stamp = utcnow()
    db.legal_documents.update_many(
        {"document_id": source["document_id"], "is_current": True},
        {"$set": {"is_current": False, "status": "superseded", "updated_at": stamp}},
    )
    db.legal_units.update_many(
        {"document_id": source["document_id"], "is_current": True}, {"$set": {"is_current": False, "updated_at": stamp}}
    )
    document = {
        **{key: source.get(key) for key in (
            "document_id", "document_number", "document_title", "issued_date", "effective_from", "effective_to",
            "status", "legal_status_checked_at", "source_url",
        )},
        "source_file": source.get("file", ""), "version": version, "is_current": True, "checksum": checksum,
        "ingested_at": stamp, "updated_at": stamp,
    }
    db.legal_documents.insert_one(document)
    rows = []
    for unit in units:
        row = {**unit, "normalized_text": " ".join(str(unit.get("text", "")).split()), "version": version,
               "is_current": True, "document_status": source.get("status", "unknown"), "checksum": checksum,
               "ingested_at": stamp, "updated_at": stamp}
        rows.append(row)
    if rows:
        db.legal_units.insert_many(rows, ordered=False)
    return {"document_id": source["document_id"], "version": version, "created": True, "checksum": checksum, "units": len(rows)}


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
    return {**{field: policy.get(field) for field in fields}, "payload": policy,
            "updated_at": timestamp, "ingested_at": timestamp}


def ingest_policies(db, policies: Iterable[dict]) -> dict:
    """Normalize once, then persist every changed batch or existing duplicate row."""
    from policy_normalization import apply_duplicates, prepare_policy_for_ingest

    batch = [prepare_policy_for_ingest(policy, db) for policy in policies]
    existing = []
    seen_keys = set()
    for policy in batch:
        key = policy["canonical_policy_key"]
        if key in seen_keys:
            continue
        seen_keys.add(key)
        existing.extend(db.policies.find({"canonical_policy_key": key, "is_current": True}, {"_id": 0}))

    # This includes existing records intentionally: if an incoming policy wins, its
    # old Mongo duplicate must be persisted as superseded in this same bulk write.
    rows = apply_duplicates([*existing, *batch])
    timestamp = utcnow()
    operations = []
    identities = set()
    for policy in rows:
        identity = (policy["policy_id"], policy["document_id"], policy["document_version"])
        if identity in identities:
            continue
        identities.add(identity)
        operations.append(ReplaceOne(
            {"policy_id": identity[0], "document_id": identity[1], "document_version": identity[2]},
            _policy_row(policy, timestamp), upsert=True,
        ))
    if not operations:
        return {"total": 0, "upserted": 0, "updated": 0}
    result = db.policies.bulk_write(operations, ordered=False)
    return {"total": len(operations), "upserted": result.upserted_count, "updated": result.modified_count}
