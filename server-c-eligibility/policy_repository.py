"""Read current policies and legal evidence from MongoDB."""

from __future__ import annotations

import os
from typing import Any, Iterable

try:
    import config
except ModuleNotFoundError:  # standalone Server C tests inject a Mongo client
    config = None


DECISION_QUERY = {
    "is_current": True,
    "review_status": "approved",
    "eligible_for_decision": True,
    "evidence_unit_ids.0": {"$exists": True},
}


class MongoPolicyRepository:
    def __init__(self, client=None) -> None:
        if client is None:
            if config is None:
                raise RuntimeError("Thiếu Server C config")
            if not config.mongodb_enabled():
                raise RuntimeError("Chưa cấu hình MONGODB_URI")
            try:
                from pymongo import MongoClient
            except ImportError as exc:
                raise RuntimeError("Thiếu package pymongo") from exc
            client = MongoClient(
                config.MONGODB_URI,
                connectTimeoutMS=config.MONGODB_CONNECT_TIMEOUT_MS,
                serverSelectionTimeoutMS=config.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
                appname="GrandPilot-Eligibility",
            )
        self.client = client
        database_name = config.MONGODB_DATABASE if config is not None else os.getenv("MONGODB_DB", "grantpilot")
        database = client[database_name]
        self.policies = database[getattr(config, "MONGODB_POLICIES_COLLECTION", "policies")]
        self.legal_units = database[getattr(config, "MONGODB_LEGAL_UNITS_COLLECTION", "legal_units")]
        self.documents = database[getattr(config, "MONGODB_DOCUMENTS_COLLECTION", "legal_documents")]
        self._document_cache: dict[tuple[str, int], dict[str, Any]] = {}

    @staticmethod
    def _public(row: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in row.items() if key != "_id"}

    def ping(self) -> None:
        self.client.admin.command("ping")

    def get_policies(
        self,
        policy_ids: Iterable[str] | None = None,
        *,
        require_evidence: bool = True,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = dict(DECISION_QUERY)
        ids = list(dict.fromkeys(policy_ids or []))
        if ids:
            query["policy_id"] = {"$in": ids}
        if require_evidence:
            query["evidence_unit_ids.0"] = {"$exists": True}
        rows = [self._normalize(self._public(row)) for row in self.policies.find(query)]
        by_id = {row.get("policy_id"): row for row in rows}
        return [by_id[policy_id] for policy_id in ids if policy_id in by_id] if ids else rows

    def _normalize(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        for key in (
            "policy_id",
            "policy_name",
            "category",
            "rules",
            "benefit_calculator",
            "required_documents",
            "evidence_unit_ids",
        ):
            if row.get(key) in (None, "", [], {}):
                row[key] = payload.get(key)
        document_id = str(row.get("document_id") or "")
        version = int(row.get("document_version") or 1)
        cache_key = (document_id, version)
        document = self._document_cache.get(cache_key)
        if document is None:
            document = self.documents.find_one(
                {"document_id": document_id, "version": version},
                {"_id": 0},
            )
            if not document:
                document = self.documents.find_one(
                    {"document_id": document_id, "is_current": {"$ne": False}},
                    {"_id": 0},
                )
            self._document_cache[cache_key] = document or {}
        if document:
            row["document_status"] = document.get("status", "unknown")
            row["document_number"] = document.get("document_number", "")
            row["document_title"] = document.get("document_title", "")
            row["effective_from"] = document.get("effective_from")
            row["effective_to"] = document.get("effective_to")
            row["source_url"] = document.get("source_url", "")
        return row

    def get_evidence(self, unit_ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = list(dict.fromkeys(unit_ids))
        if not ids:
            return []
        rows = list(
            self.legal_units.find(
                {"unit_id": {"$in": ids}, "is_current": {"$ne": False}},
                {"_id": 0},
            )
        )
        by_id = {row.get("unit_id"): self._public(row) for row in rows}
        return [by_id[unit_id] for unit_id in ids if unit_id in by_id]

    def stats(self) -> dict[str, int]:
        current = {"is_current": {"$ne": False}}
        return {
            "current_policies": self.policies.count_documents(current),
            "current_policies_with_evidence": self.policies.count_documents(
                {**current, "evidence_unit_ids.0": {"$exists": True}}
            ),
            "current_legal_units": self.legal_units.count_documents(current),
        }
