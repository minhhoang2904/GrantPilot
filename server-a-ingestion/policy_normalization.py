"""Single canonical policy normalizer; Fact Catalog v1.0.0 is authoritative."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from policy_discovery import CANONICAL_TOPIC_BY_POLICY, validate_discovery

BASE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = BASE_DIR / "fact-catalog-v1.json"
SCHEMA_VERSION = "policy-rule-schema-v1"
STATUSES = {"candidate", "needs_schema_mapping", "approved", "rejected", "superseded"}
POLICY_PARAMETERS = {"chi_phi", "gia_tri_hop_dong", "noi_dung_ho_tro", "loai_ho_tro", "dieu_kien_ho_tro", "loai_khoa_dao_tao", "hinh_thuc_dao_tao", "thoi_gian_ho_tro", "ngan_sach_nha_nuoc"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def token(value: object) -> str:
    value = unicodedata.normalize("NFD", str(value or ""))
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if (catalog.get("schema_version"), catalog.get("catalog_version"), catalog.get("status")) != ("fact-catalog-v1", "1.0.0", "approved"):
        raise RuntimeError("Fact Catalog v1.0.0 approved is required")
    return catalog


def issue(code: str, path: str, message: str, severity: str = "blocking") -> dict:
    return {"code": code, "severity": severity, "path": path, "message": message}


def aliases(catalog: dict) -> dict[str, str]:
    result = {}
    for field, definition in catalog["fields"].items():
        for alias in [field, *(definition.get("aliases") or [])]:
            result[token(alias)] = field
    return result


def valid_value(value, definition: dict, operator: str) -> bool:
    if operator == "exists": return isinstance(value, bool)
    values = value if operator in {"in", "not_in"} else [value]
    if operator in {"in", "not_in"} and (not isinstance(value, list) or not value): return False
    typ = definition["type"]
    if typ == "boolean": return all(isinstance(x, bool) for x in values)
    if typ == "integer": return all(isinstance(x, int) and not isinstance(x, bool) for x in values)
    if typ == "number": return all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in values)
    if typ == "enum": return all(isinstance(x, str) and x in definition["enum"] for x in values)
    return all(isinstance(x, str) for x in values)


def value_migration(condition: dict) -> dict | None:
    """Only migrations whose field and value meaning are both unambiguous."""
    raw, value = token(condition.get("field")), condition.get("value")
    text = token(value) if isinstance(value, str) else ""
    sizes = {"doanh_nghiep_nho_va_vua": None, "dnnvv": None, "doanh_nghiep_sieu_nho": "micro", "doanh_nghiep_nho": "small", "doanh_nghiep_vua": "medium"}
    if raw in {"loai_doanh_nghiep", "loai_hinh_doanh_nghiep"} and condition.get("operator") == "==" and text in sizes:
        return {"field": "is_sme", "operator": "==", "value": True} if sizes[text] is None else {"field": "enterprise_size", "operator": "==", "value": sizes[text]}
    if raw in {"loai_doanh_nghiep", "loai_hinh_doanh_nghiep"} and condition.get("operator") == "==" and text == "dnnvv_khoi_nghiep_sang_tao":
        return {"all": [{"field": "is_sme", "operator": "==", "value": True}, {"field": "is_innovative_startup", "operator": "==", "value": True}]}
    if raw in {"loai_doanh_nghiep", "loai_hinh_doanh_nghiep"} and condition.get("operator") == "==" and text == "dnnvv_co_von_dau_tu_nuoc_ngoai":
        return {"all": [{"field": "is_sme", "operator": "==", "value": True}, {"field": "has_foreign_investment_capital", "operator": "==", "value": True}]}
    if raw in {"loai_doanh_nghiep", "loai_hinh_doanh_nghiep"} and condition.get("operator") == "==" and text == "dnnvv_co_von_nha_nuoc":
        return {"all": [{"field": "is_sme", "operator": "==", "value": True}, {"field": "has_state_capital", "operator": "==", "value": True}]}
    if raw in {"company_age_years", "thoi_gian_thanh_lap", "thoi_gian_hoat_dong"} and isinstance(value, (int, float)):
        return {"field": "company_age_months", "operator": condition.get("operator"), "value": int(value * 12)}
    if raw in {"household_business_continuous_years", "hoat_dong_lien_tuc"} and isinstance(value, (int, float)):
        return {"field": "household_business_continuous_months", "operator": condition.get("operator"), "value": int(value * 12)}
    return None


def normalize_rules(raw: object, catalog: dict | None = None) -> tuple[dict, list[dict], list[dict]]:
    catalog = catalog or load_catalog(); by_alias = aliases(catalog); issues=[]; parameters=[]
    def visit(node, path="rules"):
        if not isinstance(node, dict): issues.append(issue("invalid_rule", path, "Rule must be an object")); return node
        groups=[x for x in ("all", "any") if x in node]
        if groups:
            key=groups[0]
            if len(groups)!=1 or not isinstance(node[key], list) or not node[key]: issues.append(issue("invalid_group", path, "all/any must be a non-empty list"))
            return {key:[visit(x, f"{path}.{key}[{i}]") for i,x in enumerate(node.get(key, []))]}
        if not {"field","operator","value"} <= set(node): issues.append(issue("incomplete_rule", path, "field, operator and value are required")); return dict(node)
        migrated=value_migration(node)
        if migrated: return visit(migrated, path+".migrated")
        raw_field=token(node["field"])
        if raw_field in POLICY_PARAMETERS:
            parameters.append({"raw_condition": copy.deepcopy(node), "path": path}); issues.append(issue("policy_parameter", path, "Condition is a policy parameter, not a company fact")); return dict(node)
        field=by_alias.get(raw_field)
        if not field: issues.append(issue("unknown_field", path, f"{node['field']} is not in Fact Catalog")); return dict(node)
        definition=catalog["fields"][field]; operator=node["operator"]
        if operator not in definition["operators"]: issues.append(issue("invalid_operator", path, f"{operator} cannot be used with {field}"));
        elif not valid_value(node["value"], definition, operator): issues.append(issue("invalid_value", path, f"Value does not match {field}"));
        return {**node, "field":field, "fact_source":definition["source"]}
    rules=visit(raw)
    def repair_startup_public_offering(node):
        if not isinstance(node, dict): return node
        for group in ("all", "any"):
            if isinstance(node.get(group), list):
                node[group]=[repair_startup_public_offering(child) for child in node[group]]
        if isinstance(node.get("all"), list):
            legal = next((x for x in node["all"] if isinstance(x,dict) and x.get("field")=="legal_form" and x.get("operator")=="!=" and x.get("value")=="joint_stock_company"), None)
            offering = next((x for x in node["all"] if isinstance(x,dict) and x.get("field")=="has_public_offering" and x.get("operator")=="==" and x.get("value") is False), None)
            if legal and offering:
                node["all"]=[x for x in node["all"] if x not in (legal, offering)] + [{"any":[legal, offering]}]
        return node
    rules=repair_startup_public_offering(rules)
    if not isinstance(rules,dict) or not ({"all","any"}&rules.keys()): issues.append(issue("missing_rules","rules","rules.all or rules.any required"))
    return rules, issues, parameters


def evidence_context(db, document_id: str, version: int | None, ids: list[str], evidence_rows: list[dict] | None = None) -> tuple[str,bool,list[dict],list[dict]]:
    rows=evidence_rows or []
    if db is not None and ids:
        candidates=list(db.legal_units.find({"unit_id":{"$in":ids}}, {"_id":0}))
        by_id=defaultdict(list)
        for row in candidates: by_id[row.get("unit_id")].append(row)
        rows=[]
        for unit_id in ids:
            options=by_id.get(unit_id, [])
            preferred=next((row for row in options if row.get("document_id")==document_id and row.get("version")==version and row.get("is_current",True)), None)
            rows.append(preferred or next((row for row in options if row.get("is_current",True)), None) or (options[0] if options else None))
        rows=[row for row in rows if row]
    if len({row.get("unit_id") for row in rows})!=len(set(ids)): return "unresolved", True, [issue("evidence_not_found","evidence_unit_ids","Evidence unit_id could not be resolved")], rows
    if not rows: return "unresolved", True, [issue("evidence_not_found","evidence_unit_ids","Evidence is required")], rows
    if any(not row.get("clause") and not row.get("point") for row in rows): return "article_fallback", True, [issue("article_fallback","evidence_unit_ids","Article-level evidence requires review", "blocking")], rows
    return "precise", False, [], rows


def source_evidence_issues(policy: dict, source: dict, document_id: str, version: int | None, evidence_rows: list[dict]) -> list[dict]:
    """Verify the legal source chain without trusting policy payload metadata."""
    issues=[]
    source_id=source.get("document_id")
    if document_id != "unmapped" and not source_id:
        issues.append(issue("source_document_not_found","document_id",f"No current source document resolves {document_id}"))
    if source_id and source_id != document_id:
        issues.append(issue("source_document_mismatch","document_id",f"Source document {source_id} does not match policy document {document_id}"))
    if policy.get("policy_id") in CANONICAL_TOPIC_BY_POLICY:
        if not source_id or not source.get("document_number") or not source.get("source_url"):
            issues.append(issue("source_document_not_found","document_id","Golden Policy source document metadata could not be resolved"))

    expected_number=source.get("document_number")
    expected_url=str(source.get("source_url") or "").rstrip("/")
    policy_number=policy.get("document_number")
    policy_url=str(policy.get("source_url") or "").rstrip("/")
    if policy_number and expected_number and policy_number != expected_number:
        issues.append(issue("source_document_number_mismatch","document_number","document_number does not belong to policy document_id"))
    if policy_url and expected_url and policy_url != expected_url:
        issues.append(issue("source_url_mismatch","source_url","source_url does not belong to policy document_id"))

    cross_document={item.get("document_id"): set(item.get("evidence_unit_ids") or []) for item in policy.get("cross_document_evidence") or [] if isinstance(item,dict)}
    for row in evidence_rows:
        unit_id=row.get("unit_id")
        row_document=row.get("document_id")
        allowed=row_document == document_id or unit_id in cross_document.get(row_document, set())
        if not allowed:
            issues.append(issue("evidence_document_mismatch","evidence_unit_ids",f"{unit_id} belongs to {row_document}, not {document_id}"))
            continue
        if row_document == document_id and row.get("version") not in (None, "", version):
            issues.append(issue("evidence_version_mismatch","evidence_unit_ids",f"{unit_id} belongs to document version {row.get('version')}, not {version}"))
        if row_document == document_id and expected_number and row.get("document_number") and row.get("document_number") != expected_number:
            issues.append(issue("evidence_document_number_mismatch","evidence_unit_ids",f"{unit_id} has a document_number from another source"))
        row_url=str(row.get("source_url") or "").rstrip("/")
        if row_document == document_id and expected_url and row_url and row_url != expected_url:
            issues.append(issue("evidence_source_url_mismatch","evidence_unit_ids",f"{unit_id} has a source_url from another document"))
    return issues


def policy_hash(policy: dict) -> str:
    payload={"rules":policy.get("normalized_rules"),"evidence":sorted(policy.get("evidence_unit_ids") or []),"document":policy.get("document_id"),"version":policy.get("source_document_version"),"key":policy.get("canonical_policy_key")}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def approval_valid(policy: dict, catalog: dict) -> bool:
    a=policy.get("approval") or {}
    return bool(a.get("reviewed_by") and a.get("reviewed_at") and a.get("reviewed_schema_version")==SCHEMA_VERSION and a.get("reviewed_catalog_version")==catalog["catalog_version"] and a.get("reviewed_policy_hash")==policy_hash(policy))


def prepare_policy_for_ingest(raw: dict, db=None, source: dict | None=None, catalog: dict | None=None, evidence_rows: list[dict] | None=None) -> dict:
    catalog=catalog or load_catalog(); source=source or {}; p=copy.deepcopy(raw); old=p.get("validation_issues_current") or []
    document_id=(p.get("pipeline") or {}).get("document_id") or p.get("document_id") or source.get("document_id", "unmapped")
    doc=db.legal_documents.find_one({"document_id":document_id,"is_current":True},{"_id":0}) if db is not None else source
    source_doc=doc or source; version=(source_doc or {}).get("version",1); rules, issues, parameters=normalize_rules(p.get("rules") or (p.get("payload") or {}).get("rules") or {},catalog)
    issues += validate_discovery(p, catalog)
    evidence=list(dict.fromkeys(p.get("evidence_unit_ids") or (p.get("payload") or {}).get("evidence_unit_ids") or []))
    matching_rows = evidence_rows if evidence_rows is not None else None
    resolution, needs_review, evidence_issues, resolved_rows=evidence_context(db,document_id,version,evidence,matching_rows); issues += evidence_issues
    integrity_issues=source_evidence_issues(p, source_doc or {}, document_id, version, resolved_rows); issues += integrity_issues
    if integrity_issues:
        resolution, needs_review = "unresolved", True
    support_type=str((p.get("benefit_calculator") or {}).get("type") or p.get("category") or "other")
    first=(db.legal_units.find_one({"unit_id":evidence[0],"document_id":document_id,"version":version},{"_id":0}) if db is not None and evidence else next((row for row in (evidence_rows or []) if row.get("unit_id")==evidence[0]), {})) or {}
    rule_hash=hashlib.sha256(json.dumps(rules,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    key="|".join(map(str,[document_id,first.get("article",""),first.get("clause",""),first.get("point",""),token(support_type),rule_hash]))
    stamp = now(); old_history=p.get("validation_history",[]); previous={ (x.get("code"),x.get("path"),x.get("message")):x for x in [*old_history,*old] }; current_keys={(x["code"],x["path"],x["message"]) for x in issues}; history=[]
    for history_key, prior in previous.items():
        record={**prior, "first_seen_at":prior.get("first_seen_at",stamp), "last_seen_at":stamp, "catalog_version":catalog["catalog_version"], "schema_version":SCHEMA_VERSION}
        if history_key not in current_keys: record["resolved_at"]=stamp
        else: record.pop("resolved_at",None)
        history.append(record)
    p.update({"document_id":document_id,"document_number":(source_doc or {}).get("document_number") or p.get("document_number"),"source_url":(source_doc or {}).get("source_url") or p.get("source_url"),"document_version":version,"source_document_version":version,"rules":rules,"normalized_rules":rules,"policy_rule_schema_version":SCHEMA_VERSION,"fact_catalog_version":catalog["catalog_version"],"evidence_unit_ids":evidence,"evidence_resolution":resolution,"requires_evidence_review":needs_review,"normalized_rule_hash":rule_hash,"canonical_policy_key":key,"validation_issues_current":issues,"validation_history":history,"policy_parameters":parameters})
    blocking=any(x["severity"]=="blocking" for x in issues)
    status=p.get("review_status") or (p.get("review") or {}).get("status") or "candidate"; requested_approved = status == "approved"
    if status not in STATUSES: status="candidate"
    if any(x["code"]=="unknown_field" for x in issues): status="needs_schema_mapping"
    elif blocking: status="rejected" if any(x["code"] in {"invalid_rule","invalid_operator","invalid_value","evidence_not_found"} or x["code"].startswith(("source_","evidence_","discovery_")) for x in issues) else "candidate"
    if requested_approved and not approval_valid(p,catalog): status="candidate"; p["validation_issues_current"].append(issue("approval_invalidated","approval","Approval provenance/hash is missing or stale"))
    p["review_status"]=status; p.setdefault("review",{})["status"]=status; p["is_current"]=bool(p.get("is_current",True) and doc)
    p["eligible_for_decision"]=bool(p["is_current"] and status=="approved" and resolution=="precise" and not needs_review and not any(x["severity"]=="blocking" for x in p["validation_issues_current"]) and approval_valid(p,catalog))
    return p


def apply_duplicates(policies: list[dict]) -> list[dict]:
    groups=defaultdict(list)
    for p in policies: groups[p["canonical_policy_key"]].append(p)
    for key, rows in groups.items():
        if len(rows)<2: continue
        def rank(row):
            return (-int(bool(row.get("eligible_for_decision"))), -int(row.get("review_status")=="approved"), -int(row.get("evidence_resolution")=="precise"), -int(bool(row.get("is_current"))), -int(row.get("document_version") or 0), row["policy_id"])
        primary=sorted(rows,key=rank)[0]; gid="duplicate_"+hashlib.sha256(key.encode()).hexdigest()[:16]
        for row in rows:
            row["duplicate_group_id"]=gid
            if row is not primary: row.update({"review_status":"superseded","is_current":False,"eligible_for_decision":False,"superseded_by_policy_id":primary["policy_id"]})
    return policies


def dry_run(policies: list[dict], source_by_document: dict[str,dict], units: list[dict]) -> dict:
    by_id = {unit.get("unit_id"): unit for unit in units}
    rows=[]
    for raw in policies:
        source=source_by_document.get((raw.get("pipeline") or {}).get("document_id"),{})
        evidence=[by_id.get(unit_id) for unit_id in raw.get("evidence_unit_ids", [])]
        row=prepare_policy_for_ingest(raw,None,source,evidence_rows=[x for x in evidence if x])
        row["eligible_for_decision"]=False
        rows.append(row)
    apply_duplicates(rows)
    unknown=Counter(x["message"].split(" is ")[0] for p in rows for x in p["validation_issues_current"] if x["code"]=="unknown_field")
    counts = Counter(p["review_status"] for p in rows)
    def walk(node):
        if not isinstance(node,dict): return []
        if "all" in node or "any" in node: return [leaf for group in ("all","any") for child in node.get(group,[]) for leaf in walk(child)]
        return [node]
    return {"total_policies":len(rows), **{status: counts[status] for status in ("candidate","needs_schema_mapping","approved","rejected","superseded")}, "eligible_for_decision":sum(p["eligible_for_decision"] for p in rows), "conditions_mapped":sum(1 for p in rows for x in walk(p["normalized_rules"]) if x.get("fact_source")), "conditions_unknown":sum(unknown.values()), "unknown_fields":dict(unknown), "policy_parameters":[p["policy_id"] for p in rows if p["policy_parameters"]], "approval_invalidated":[p["policy_id"] for p in rows if any(x["code"]=="approval_invalidated" for x in p["validation_issues_current"])], "article_fallback":[p["policy_id"] for p in rows if p["evidence_resolution"]=="article_fallback"], "duplicate_groups":sorted({p.get("duplicate_group_id") for p in rows if p.get("duplicate_group_id")}), "policies":rows}
