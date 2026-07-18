"""Canonical Golden Policy MVP overlay used by every policy persistence entrypoint."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from policy_normalization import SCHEMA_VERSION, load_catalog, policy_hash, prepare_policy_for_ingest

BASE_DIR = Path(__file__).resolve().parent
GOLDEN_PATH = BASE_DIR / "data" / "golden_policies_mvp.json"


def golden_policies() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _source_for(document_id: str, sources: dict[str, dict] | None) -> dict:
    for source in (sources or {}).values():
        if source.get("document_id") == document_id:
            return source
    return {"document_id": document_id, "version": 1}


def approve_candidate(policy: dict, db=None, sources: dict[str, dict] | None = None, units: list[dict] | None = None, reviewer: str = "huy") -> dict:
    """Create provenance only after candidate normalization, then revalidate it."""
    document_id = (policy.get("pipeline") or {}).get("document_id") or policy.get("document_id")
    evidence_ids = set(policy.get("evidence_unit_ids") or [])
    evidence_rows = [unit for unit in (units or []) if unit.get("unit_id") in evidence_ids]
    candidate = prepare_policy_for_ingest(policy, db, _source_for(document_id, sources), evidence_rows=evidence_rows)
    if candidate["validation_issues_current"] or candidate["evidence_resolution"] != "precise":
        raise RuntimeError(f"{candidate['policy_id']} is not ready for approval")
    catalog = load_catalog()
    candidate["review_status"] = "approved"
    candidate["review"] = {"status": "approved"}
    candidate["approval"] = {
        "reviewed_by": reviewer,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_schema_version": SCHEMA_VERSION,
        "reviewed_catalog_version": catalog["catalog_version"],
        "reviewed_policy_hash": policy_hash(candidate),
    }
    approved = prepare_policy_for_ingest(candidate, db, _source_for(document_id, sources), evidence_rows=evidence_rows)
    if not (approved["review_status"] == "approved" and approved["eligible_for_decision"]):
        raise RuntimeError(f"Approval provenance is invalid for {approved['policy_id']}")
    return approved


def apply_golden_overlay(policies: list[dict], db=None, sources: dict[str, dict] | None = None, units: list[dict] | None = None, reviewer: str = "huy") -> list[dict]:
    """Replace the four reviewed policies so full ingest cannot downgrade them."""
    golden = golden_policies()
    golden_ids = {policy["policy_id"] for policy in golden}
    merged = [copy.deepcopy(policy) for policy in policies if policy.get("policy_id") not in golden_ids]
    merged.extend(approve_candidate(policy, db=db, sources=sources, units=units, reviewer=reviewer) for policy in golden)
    return merged
