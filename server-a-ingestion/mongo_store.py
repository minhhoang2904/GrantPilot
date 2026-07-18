"""MongoDB persistence for legal documents, immutable versions, and legal units."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient, ReplaceOne


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGODB_DB") or "grantpilot"


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
    # Atlas uses TLS. Some local Python installations do not know the Atlas CA
    # chain unless it is explicitly supplied from certifi.
    if MONGO_URI.startswith("mongodb+srv://") or "tls=true" in MONGO_URI.lower():
        options["tlsCAFile"] = os.getenv("MONGO_TLS_CA_FILE", certifi.where())
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
    """Upsert policy records while preserving their original payload and review state."""
    current_versions = {
        row["document_id"]: row["version"]
        for row in db.legal_documents.find({"is_current": True}, {"_id": 0, "document_id": 1, "version": 1})
    }
    operations = []
    now = utcnow()
    for policy in policies:
        pipeline = policy.get("pipeline") or {}
        legal_source = policy.get("legal_source") or {}
        document_id = pipeline.get("document_id")
        if not document_id:
            local_file = str(legal_source.get("local_file", "")).split("/")[-1]
            document = db.legal_documents.find_one({"source_file": local_file, "is_current": True}, {"document_id": 1})
            document_id = document.get("document_id") if document else "unmapped"
        document_version = current_versions.get(document_id)
        row = {
            "policy_id": policy["policy_id"],
            "document_id": document_id,
            "document_version": document_version,
            "is_current": document_id in current_versions,
            "policy_name": policy.get("policy_name", ""),
            "category": policy.get("category", ""),
            "review_status": (policy.get("review") or {}).get("status", "unknown"),
            "evidence_unit_ids": policy.get("evidence_unit_ids", []),
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
