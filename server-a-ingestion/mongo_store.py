"""MongoDB persistence for legal documents, immutable versions, and legal units."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Iterable

import certifi
from pymongo import MongoClient


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


def ingest_document(db, pdf_path, source: dict, units: Iterable[dict]) -> dict:
    """Insert a new immutable version, or return the existing version for same checksum."""
    checksum = checksum_file(pdf_path)
    existing_checksum = db.legal_documents.find_one(
        {"document_id": source["document_id"], "checksum": checksum},
        {"version": 1, "checksum": 1, "is_current": 1},
    )
    if existing_checksum:
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
