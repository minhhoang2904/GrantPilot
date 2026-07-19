"""Deterministic MVP policy selection from canonical discovery metadata."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Literal


SCHEMA_VERSION = "policy-discovery-v1"
AdvisoryScope = Literal["question", "profile_scan"]

_WORD_RE = re.compile(r"[^a-z0-9]+")
def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = " ".join(_WORD_RE.sub(" ", ascii_text.casefold()).split())
    return normalized.replace("online", "truc tuyen")


def load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Policy discovery manifest must be an array: {path}")
    return payload


def _search_texts(policy: dict[str, Any]) -> list[str]:
    discovery = policy.get("discovery") or (policy.get("payload") or {}).get("discovery") or {}
    if discovery.get("schema_version") != SCHEMA_VERSION:
        return []
    values = [discovery.get("topic_label_vi")]
    values.extend(discovery.get("search_terms_vi") or [])
    values.extend(discovery.get("intent_examples_vi") or [])
    return [str(value) for value in values if isinstance(value, str) and value.strip()]


def _score(question: str, policy: dict[str, Any]) -> float:
    normalized_question = _normalize(question)
    best = 0.0
    for text in _search_texts(policy):
        normalized_text = _normalize(text)
        if normalized_text and normalized_text in normalized_question:
            best = max(best, 10.0 + len(normalized_text.split()))
    return best


def select_policies(
    question: str,
    policies: Iterable[dict[str, Any]],
    *,
    scope: AdvisoryScope = "question",
) -> dict[str, Any]:
    canonical = []
    for policy in policies:
        discovery = policy.get("discovery") or (policy.get("payload") or {}).get("discovery") or {}
        policy_id = policy.get("policy_id")
        if policy_id and discovery.get("schema_version") == SCHEMA_VERSION and discovery.get("topic_id"):
            canonical.append({**policy, "discovery": discovery})

    if scope == "profile_scan":
        selected = canonical
    else:
        scored = [(policy, _score(question, policy)) for policy in canonical]
        selected = [policy for policy, score in scored if score > 0]

    return {
        "advisory_scope": scope,
        "coverage_status": "covered" if selected else "not_covered",
        "policy_ids": list(dict.fromkeys(str(policy["policy_id"]) for policy in selected)),
        "topic_ids": list(dict.fromkeys(str(policy["discovery"]["topic_id"]) for policy in selected)),
    }
