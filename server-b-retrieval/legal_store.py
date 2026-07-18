"""Canonical legal-unit repositories.

Production hydrate text goc tu MongoDB; JSONL duoc giu lam offline fallback.
Pinecone chi la vector search index, khong phai canonical data store.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import config


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def embedding_text(unit: dict) -> str:
    """Cung context format ma Server A nen dung khi embed/upsert Pinecone."""
    title = unit.get("document_title", "")
    number = unit.get("document_number", "")
    document = f"{title}, số {number}" if number else title
    article = f"Điều {unit.get('article', '')}. {unit.get('article_title', '')}".strip()
    location = []
    if unit.get("clause"):
        location.append(f"Khoản {unit['clause']}")
    if unit.get("point"):
        location.append(f"điểm {unit['point']}")
    return "\n".join(filter(None, [document, article, ", ".join(location), unit.get("text", "")]))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL loi tai {path}:{line_number}: {exc}") from exc
    return rows


class LegalUnitStore:
    def __init__(self, legal_units_path: Path, policies_path: Path | None = None) -> None:
        self.legal_units_path = legal_units_path
        self.policies_path = policies_path
        self.units = _read_jsonl(legal_units_path)
        self.by_id: dict[str, dict] = {}
        self.by_location: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
        self.unit_to_policy_ids: dict[str, list[str]] = defaultdict(list)

        for unit in self.units:
            unit_id = unit.get("unit_id")
            if not unit_id:
                raise ValueError(f"Legal unit thieu unit_id trong {legal_units_path}")
            if unit_id in self.by_id:
                raise ValueError(f"unit_id bi trung: {unit_id}")
            self.by_id[unit_id] = unit
            key = (
                str(unit.get("document_number", "")).lower(),
                str(unit.get("article", "")).lower(),
                str(unit.get("clause", "")).lower(),
                str(unit.get("point", "")).lower(),
            )
            self.by_location[key].append(unit)

        self._load_policy_links()

    def get_many(self, unit_ids: Iterable[str]) -> list[dict]:
        return [self.by_id[unit_id] for unit_id in unit_ids if unit_id in self.by_id]

    def _load_policy_links(self) -> None:
        if not self.policies_path or not self.policies_path.exists():
            return
        policies = json.loads(self.policies_path.read_text(encoding="utf-8"))
        if not isinstance(policies, list):
            raise ValueError(f"policies phai la JSON array: {self.policies_path}")
        for policy in policies:
            policy_id = policy.get("policy_id") or policy.get("id")
            if not policy_id:
                continue
            for unit_id in policy.get("evidence_unit_ids", []) or []:
                if unit_id in self.by_id and policy_id not in self.unit_to_policy_ids[unit_id]:
                    self.unit_to_policy_ids[unit_id].append(policy_id)

    def exact_lookup(
        self,
        *,
        article: str,
        clause: str = "",
        point: str = "",
        document_number: str = "",
    ) -> list[dict]:
        article = article.lower()
        clause = clause.lower()
        point = point.lower()
        document_number = document_number.lower()
        out = []
        for unit in self.units:
            if str(unit.get("article", "")).lower() != article:
                continue
            if clause and str(unit.get("clause", "")).lower() != clause:
                continue
            if point and str(unit.get("point", "")).lower() != point:
                continue
            if document_number and str(unit.get("document_number", "")).lower() != document_number:
                continue
            out.append(unit)
        return out

    def parents(self, unit: dict) -> list[dict]:
        document_id = unit.get("document_id", "")
        article = unit.get("article", "")
        clause = unit.get("clause", "")
        parent_ids = [f"{document_id}_art-{article}"]
        if clause:
            parent_ids.append(f"{document_id}_art-{article}_cl-{clause}")
        return [self.by_id[uid] for uid in parent_ids if uid in self.by_id and uid != unit.get("unit_id")]

    def policy_ids_for(self, unit_ids: Iterable[str]) -> list[str]:
        result: list[str] = []
        for unit_id in unit_ids:
            for policy_id in self.unit_to_policy_ids.get(unit_id, []):
                if policy_id not in result:
                    result.append(policy_id)
        return result


class MongoLegalUnitStore:
    """Lazy MongoDB repository used by the online retrieval path.

    Legal-unit documents keep the 15-field handoff schema plus ``version`` and
    ``is_current``. Document-level fields can be denormalized on each unit or
    hydrated from the ``documents`` collection shown by Server A.
    """

    units: list[dict] = []  # Khong load toan bo MongoDB de build BM25 trong RAM.

    def __init__(self, client=None) -> None:
        if client is None:
            if not config.mongodb_enabled():
                raise RuntimeError("Chua cau hinh MONGODB_URI")
            try:
                from pymongo import MongoClient
            except ImportError as exc:
                raise RuntimeError("Thieu package pymongo") from exc
            client = MongoClient(
                config.MONGODB_URI,
                connectTimeoutMS=config.MONGODB_CONNECT_TIMEOUT_MS,
                serverSelectionTimeoutMS=config.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
                appname="GrandPilot-Retrieval",
            )
        self.client = client
        database = client[config.MONGODB_DATABASE]
        self.documents_collection = database[config.MONGODB_DOCUMENTS_COLLECTION]
        self.legal_units_collection = database[config.MONGODB_LEGAL_UNITS_COLLECTION]
        self.policies_collection = database[config.MONGODB_POLICIES_COLLECTION]
        self.by_id: dict[str, dict] = {}

    @staticmethod
    def _public(row: dict) -> dict:
        result = {key: value for key, value in row.items() if key != "_id"}
        if not result.get("unit_id") and result.get("original_unit_id"):
            result["unit_id"] = result["original_unit_id"]
        return result

    def _attach_documents(self, units: list[dict]) -> None:
        document_ids = {
            unit.get("document_id")
            for unit in units
            if unit.get("document_id") and not unit.get("document_title")
        }
        if not document_ids:
            return
        documents = self.documents_collection.find(
            {
                "document_id": {"$in": list(document_ids)},
                "is_current": {"$ne": False},
            },
            {"_id": 0},
        )
        by_document_id = {row.get("document_id"): row for row in documents}
        inherited = (
            "document_number",
            "document_title",
            "issued_date",
            "effective_from",
            "effective_to",
            "status",
            "source_url",
            "version",
            "is_current",
        )
        for unit in units:
            document = by_document_id.get(unit.get("document_id"), {})
            for field in inherited:
                if unit.get(field) in (None, "") and document.get(field) not in (None, ""):
                    unit[field] = document[field]

    def _cache(self, rows: Iterable[dict]) -> list[dict]:
        units = [self._public(row) for row in rows]
        self._attach_documents(units)
        result = []
        for unit in units:
            unit_id = unit.get("unit_id")
            if not unit_id:
                continue
            self.by_id[str(unit_id)] = unit
            result.append(unit)
        return result

    def get_many(self, unit_ids: Iterable[str]) -> list[dict]:
        ordered_ids = list(dict.fromkeys(str(value) for value in unit_ids if value))
        missing = [unit_id for unit_id in ordered_ids if unit_id not in self.by_id]
        if missing:
            rows = self.legal_units_collection.find(
                {
                    "unit_id": {"$in": missing},
                    "is_current": {"$ne": False},
                },
                {"_id": 0},
            )
            self._cache(rows)
        return [self.by_id[unit_id] for unit_id in ordered_ids if unit_id in self.by_id]

    def exact_lookup(
        self,
        *,
        article: str,
        clause: str = "",
        point: str = "",
        document_number: str = "",
    ) -> list[dict]:
        query: dict = {"article": str(article), "is_current": {"$ne": False}}
        if clause:
            query["clause"] = str(clause)
        if point:
            query["point"] = str(point).lower()
        if document_number:
            documents = list(
                self.documents_collection.find(
                    {
                        "document_number": document_number,
                        "is_current": {"$ne": False},
                    },
                    {"_id": 0, "document_id": 1},
                )
            )
            document_ids = [row["document_id"] for row in documents if row.get("document_id")]
            query["$or"] = [
                {"document_number": document_number},
                {"document_id": {"$in": document_ids}},
            ]
        rows = self.legal_units_collection.find(query, {"_id": 0})
        return self._cache(rows)

    def parents(self, unit: dict) -> list[dict]:
        document_id = unit.get("document_id", "")
        article = unit.get("article", "")
        clause = unit.get("clause", "")
        parent_ids = [f"{document_id}_art-{article}"]
        if clause:
            parent_ids.append(f"{document_id}_art-{article}_cl-{clause}")
        return [
            parent
            for parent in self.get_many(parent_ids)
            if parent.get("unit_id") != unit.get("unit_id")
        ]

    def policy_ids_for(self, unit_ids: Iterable[str]) -> list[str]:
        ids = list(dict.fromkeys(unit_ids))
        if not ids:
            return []
        rows = self.policies_collection.find(
            {"evidence_unit_ids": {"$in": ids}},
            {"_id": 0, "policy_id": 1},
        )
        return list(dict.fromkeys(row.get("policy_id") for row in rows if row.get("policy_id")))


def build_legal_unit_store():
    if config.LEGAL_DATA_BACKEND == "mongodb":
        return MongoLegalUnitStore()
    if not config.LEGAL_UNITS_PATH.exists():
        raise FileNotFoundError(config.LEGAL_UNITS_PATH)
    return LegalUnitStore(config.LEGAL_UNITS_PATH, config.POLICIES_PATH)
