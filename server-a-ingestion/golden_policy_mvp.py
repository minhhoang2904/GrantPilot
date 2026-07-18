"""Golden Policy MVP overlay with committed, immutable approval provenance."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from policy_normalization import approval_valid, load_catalog, prepare_policy_for_ingest

BASE_DIR = Path(__file__).resolve().parent
GOLDEN_PATH = BASE_DIR / "data" / "golden_policies_mvp.json"
APPROVALS_PATH = BASE_DIR / "data" / "golden_policy_approvals.json"


class StaleGoldenApprovalError(RuntimeError):
    """Raised when reviewed content no longer matches its committed manifest."""


def golden_policies() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def approval_manifest() -> dict[str, dict]:
    rows = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    return {row["policy_id"]: row["approval"] for row in rows}


def _source_for(document_id: str, sources: dict[str, dict] | None) -> dict:
    for source in (sources or {}).values():
        if source.get("document_id") == document_id:
            return source
    return {"document_id": document_id, "version": 1}


def _evidence_rows(policy: dict, units: list[dict] | None) -> list[dict]:
    evidence_ids = set(policy.get("evidence_unit_ids") or [])
    return [unit for unit in (units or []) if unit.get("unit_id") in evidence_ids]


def normalize_golden_candidate(policy: dict, db=None, sources: dict[str, dict] | None = None, units: list[dict] | None = None) -> dict:
    document_id = (policy.get("pipeline") or {}).get("document_id") or policy.get("document_id")
    return prepare_policy_for_ingest(
        policy,
        db,
        _source_for(document_id, sources),
        evidence_rows=_evidence_rows(policy, units),
    )


def validate_committed_approval(policy: dict, approval: dict, db=None, sources: dict[str, dict] | None = None, units: list[dict] | None = None) -> dict:
    """Attach existing provenance and fail closed if content/hash has drifted."""
    candidate = normalize_golden_candidate(policy, db=db, sources=sources, units=units)
    candidate["review_status"] = "approved"
    candidate["review"] = {"status": "approved"}
    candidate["approval"] = copy.deepcopy(approval)
    validated = normalize_golden_candidate(candidate, db=db, sources=sources, units=units)
    if not approval_valid(validated, load_catalog()) or not validated["eligible_for_decision"]:
        raise StaleGoldenApprovalError(f"Stale approval manifest for {validated['policy_id']}")
    return validated


def apply_golden_overlay(policies: list[dict], db=None, sources: dict[str, dict] | None = None, units: list[dict] | None = None) -> list[dict]:
    """Replace reviewed policy IDs and validate their committed approvals."""
    golden = golden_policies()
    approvals = approval_manifest()
    golden_ids = {policy["policy_id"] for policy in golden}
    if set(approvals) != golden_ids:
        raise StaleGoldenApprovalError("Golden candidate and approval manifest IDs differ")
    merged = [copy.deepcopy(policy) for policy in policies if policy.get("policy_id") not in golden_ids]
    merged.extend(
        validate_committed_approval(policy, approvals[policy["policy_id"]], db=db, sources=sources, units=units)
        for policy in golden
    )
    return merged
