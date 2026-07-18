"""Ingest parsed legal data into MongoDB without storing raw PDF binaries.

Usage:
    python ingest_mongodb.py
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

from mongo_store import database, ensure_indexes, ingest_document, ingest_policies  # noqa: E402
from pipeline import LEGAL_UNITS_PATH, POLICIES_PATH, load_sources, read_jsonl, source_for  # noqa: E402


def main() -> None:
    units = read_jsonl(LEGAL_UNITS_PATH)
    if not units:
        raise RuntimeError(f"Không có legal units tại {LEGAL_UNITS_PATH}")
    if not POLICIES_PATH.exists():
        raise RuntimeError(f"Không có policies tại {POLICIES_PATH}")
    policies = json.loads(POLICIES_PATH.read_text(encoding="utf-8"))
    units_by_document: dict[str, list[dict]] = {}
    for unit in units:
        units_by_document.setdefault(unit["document_id"], []).append(unit)

    sources = load_sources()
    raw_dir = BASE_DIR / "data" / "raw"
    client, db = database()
    try:
        ensure_indexes(db)
        for pdf in sorted(raw_dir.glob("*.pdf")):
            source = source_for(pdf, sources)
            result = ingest_document(db, pdf, source, units_by_document.get(source["document_id"], []))
            state = "new version" if result["created"] else "already ingested"
            print(f"[DOCUMENT] {pdf.name}: {state}; version={result['version']}")
        result = ingest_policies(db, policies)
        print(f"[POLICIES] {result}")
        print(
            "[TOTAL] "
            f"documents={db.legal_documents.count_documents({})}, "
            f"units={db.legal_units.count_documents({})}, "
            f"policies={db.policies.count_documents({})}"
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
