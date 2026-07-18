"""MongoDB CRUD for company profiles used by Server B and Server C."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / "server-a-ingestion" / ".env")
load_dotenv(BASE_DIR.parent / ".env")
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGODB_DB") or "grantpilot"
_client: MongoClient | None = None


def _profiles():
    global _client
    if _client is None:
        options: dict[str, Any] = {"serverSelectionTimeoutMS": 5000}
        if MONGO_URI.startswith("mongodb+srv://") or "tls=true" in MONGO_URI.lower():
            options["tlsCAFile"] = os.getenv("MONGO_TLS_CA_FILE", certifi.where())
        _client = MongoClient(MONGO_URI, **options)
        _client.admin.command("ping")
        _client[MONGO_DB].profiles.create_index("id", unique=True)
        _client[MONGO_DB].profiles.create_index([("business_type", 1), ("province", 1)])
    return _client[MONGO_DB].profiles


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(profile: Optional[dict]) -> Optional[dict]:
    if profile is None:
        return None
    profile.pop("_id", None)
    return profile


def create_profile(data: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(uuid.uuid4())
    now = _now()
    profile = {"id": profile_id, **data, "created_at": now, "updated_at": now}
    _profiles().insert_one(profile)
    return _serialize(profile)  # type: ignore[return-value]


def get_profile(profile_id: str) -> Optional[dict]:
    return _serialize(_profiles().find_one({"id": profile_id}))


def update_profile(profile_id: str, data: dict[str, Any]) -> Optional[dict]:
    updates = {key: value for key, value in data.items() if key != "id"}
    updates["updated_at"] = _now()
    result = _profiles().find_one_and_update(
        {"id": profile_id}, {"$set": updates}, return_document=ReturnDocument.AFTER
    )
    return _serialize(result)


def upsert_profile(profile: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    _profiles().update_one(
        {"id": profile["id"]},
        {"$set": {**profile, "updated_at": now}, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return get_profile(profile["id"])  # type: ignore[return-value]
