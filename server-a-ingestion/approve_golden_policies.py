"""Approve the reviewed four-policy MVP through the canonical Mongo write boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

from golden_policy_mvp import apply_golden_overlay, golden_policies  # noqa: E402
from mongo_store import database, ensure_indexes, ingest_policies  # noqa: E402

GOLDEN_PATH = BASE_DIR / "data" / "golden_policies_mvp.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Approve the reviewed Golden Policy MVP")
    parser.add_argument("--reviewed-by", default="huy")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    policies = golden_policies()
    client, db = database()
    try:
        ensure_indexes(db)
        approved = apply_golden_overlay([], db=db, reviewer=args.reviewed_by)
        if args.dry_run:
            print(json.dumps(approved, ensure_ascii=False, indent=2))
            return
        result = ingest_policies(db, approved)
        ids = [policy["policy_id"] for policy in approved]
        rows = list(db.policies.find({"policy_id": {"$in": ids}}, {"_id": 0, "payload": 0}))
        print(json.dumps({"ingest": result, "policies": rows}, ensure_ascii=False, default=str, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
