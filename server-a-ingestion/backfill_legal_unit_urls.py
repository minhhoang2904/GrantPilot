"""Backfill legal_units.source_url from its matching legal_documents version."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from pymongo import UpdateOne

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

from mongo_store import database  # noqa: E402


def backfill(db, apply: bool, batch_size: int = 500) -> Counter:
    """Join by document_id + version and only change missing/stale source URLs."""
    urls = {
        (doc["document_id"], doc["version"]): doc.get("source_url", "")
        for doc in db.legal_documents.find({}, {"_id": 0, "document_id": 1, "version": 1, "source_url": 1})
    }
    stats: Counter = Counter()
    operations = []

    def flush() -> None:
        nonlocal operations
        if apply and operations:
            db.legal_units.bulk_write(operations, ordered=False)
        operations = []

    for unit in db.legal_units.find({}, {"_id": 1, "document_id": 1, "version": 1, "source_url": 1}):
        stats["scanned"] += 1
        key = (unit.get("document_id"), unit.get("version"))
        url = urls.get(key)
        if key not in urls:
            stats["missing_document_version"] += 1
            continue
        if not url:
            stats["document_without_url"] += 1
            continue
        if unit.get("source_url") == url:
            stats["already_correct"] += 1
            continue
        stats["to_update"] += 1
        if apply:
            operations.append(UpdateOne({"_id": unit["_id"]}, {"$set": {"source_url": url}}))
            if len(operations) >= batch_size:
                flush()
    flush()
    stats["updated"] = stats["to_update"] if apply else 0
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill legal_units.source_url from legal_documents")
    parser.add_argument("--apply", action="store_true", help="Write changes; omit for dry-run.")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    client, db = database()
    try:
        stats = backfill(db, apply=args.apply, batch_size=args.batch_size)
    finally:
        client.close()
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(mode, dict(stats))


if __name__ == "__main__":
    main()
