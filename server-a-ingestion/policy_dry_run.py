"""Offline normalization report. Never connects to MongoDB or calls an API."""
import json
from pathlib import Path
from pipeline import LEGAL_UNITS_PATH, POLICIES_PATH, load_sources, read_jsonl
from policy_normalization import dry_run

policies = json.loads(POLICIES_PATH.read_text(encoding="utf-8"))
sources = {item["document_id"]: item for item in load_sources().values()}
report = dry_run(policies, sources, read_jsonl(LEGAL_UNITS_PATH))
print(json.dumps({key: value for key, value in report.items() if key != "policies"}, ensure_ascii=False, indent=2))
