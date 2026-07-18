"""Generate a stable Golden Policy approval manifest without touching MongoDB."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from golden_policy_mvp import APPROVALS_PATH, golden_policies, normalize_golden_candidate
from pipeline import LEGAL_UNITS_PATH, load_sources, read_jsonl
from policy_normalization import SCHEMA_VERSION, load_catalog, policy_hash


def build_manifest(reviewer: str, reviewed_at: str | None = None) -> list[dict]:
    """Normalize candidates first, then compute provenance for explicit review."""
    catalog = load_catalog()
    units = read_jsonl(LEGAL_UNITS_PATH)
    sources = load_sources()
    timestamp = reviewed_at or datetime.now(timezone.utc).isoformat()
    manifest = []
    for raw in golden_policies():
        candidate = normalize_golden_candidate(raw, sources=sources, units=units)
        if candidate["validation_issues_current"] or candidate["evidence_resolution"] != "precise":
            raise RuntimeError(f"{candidate['policy_id']} is not ready for approval")
        manifest.append({
            "policy_id": candidate["policy_id"],
            "approval": {
                "reviewed_by": reviewer,
                "reviewed_at": timestamp,
                "reviewed_schema_version": SCHEMA_VERSION,
                "reviewed_catalog_version": catalog["catalog_version"],
                "reviewed_policy_hash": policy_hash(candidate),
            },
        })
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the reviewed Golden Policy manifest")
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--apply", action="store_true", help="Write the manifest; omit for a state-free dry-run.")
    args = parser.parse_args()
    manifest = build_manifest(args.reviewed_by)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if args.apply:
        APPROVALS_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
