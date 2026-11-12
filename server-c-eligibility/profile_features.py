"""Canonical, deterministic company-profile derivations for eligibility rules."""

from __future__ import annotations

from datetime import date
from typing import Any


DERIVATION_VERSIONS = {
    "company_age_months": "1.0.0",
    "sme_sector_group": "1.0.0",
    "enterprise_size": "1.0.0",
    "is_sme": "1.0.0",
    "innovation_selection_criteria_met": "1.0.0",
    "is_innovative_startup": "1.0.0",
}

SECTOR_GROUPS = {
    "nong_lam_ngu_nghiep": "agri_industry",
    "cong_nghiep_xay_dung": "agri_industry",
    "thuong_mai_dich_vu": "trade_service",
}

# (size, maximum BHXH employees, maximum revenue, maximum capital)
SME_THRESHOLDS = {
    "agri_industry": (
        ("micro", 10, 3_000_000_000, 3_000_000_000),
        ("small", 100, 50_000_000_000, 20_000_000_000),
        ("medium", 200, 200_000_000_000, 100_000_000_000),
    ),
    "trade_service": (
        ("micro", 10, 10_000_000_000, 3_000_000_000),
        ("small", 50, 100_000_000_000, 50_000_000_000),
        ("medium", 100, 300_000_000_000, 100_000_000_000),
    ),
}

INNOVATION_SELECTION_FACTS = (
    "has_valid_invention_patent",
    "has_valid_innovation_award",
    "has_valid_science_technology_certificate",
    "has_valid_high_tech_certificate",
    "has_qualifying_startup_fund_investment",
    "has_qualifying_startup_support_commitment",
    "has_innovative_startup_council_approval",
)

ENTERPRISE_LEGAL_FORMS = {
    "joint_stock_company",
    "limited_liability_company",
    "partnership",
    "private_enterprise",
}


def _non_negative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _tri_any(values: list[bool | None]) -> bool | None:
    if any(value is True for value in values):
        return True
    if values and all(value is False for value in values):
        return False
    return None


def _tri_all(values: list[bool | None]) -> bool | None:
    if any(value is False for value in values):
        return False
    if values and all(value is True for value in values):
        return True
    return None


def derive_company_age_months(facts: dict[str, Any], *, as_of: date) -> int | None:
    raw = facts.get("first_business_registration_date")
    if not isinstance(raw, str):
        return None
    try:
        registered = date.fromisoformat(raw)
    except ValueError:
        return None
    if registered > as_of:
        return None
    months = (as_of.year - registered.year) * 12 + as_of.month - registered.month
    if as_of.day < registered.day:
        months -= 1
    return max(0, months)


def derive_sme_sector_group(facts: dict[str, Any]) -> str | None:
    return SECTOR_GROUPS.get(facts.get("sector"))


def derive_enterprise_size(facts: dict[str, Any]) -> str | None:
    group = facts.get("sme_sector_group") or derive_sme_sector_group(facts)
    thresholds = SME_THRESHOLDS.get(group)
    employees = _non_negative_int(facts.get("social_insurance_employees"))
    revenue = _non_negative_int(facts.get("annual_revenue_vnd"))
    capital = _non_negative_int(facts.get("total_capital_vnd"))
    for field, normalized in (
        ("social_insurance_employees", employees),
        ("annual_revenue_vnd", revenue),
        ("total_capital_vnd", capital),
    ):
        if facts.get(field) is not None and normalized is None:
            return None
    if thresholds is None or employees is None or (revenue is None and capital is None):
        return None

    for size, max_employees, max_revenue, max_capital in thresholds:
        financial_ok = ((revenue is not None and revenue <= max_revenue) or
                        (capital is not None and capital <= max_capital))
        if employees <= max_employees and financial_ok:
            return size

    _, max_employees, max_revenue, max_capital = thresholds[-1]
    if employees > max_employees:
        return "large"
    if revenue is not None and capital is not None and revenue > max_revenue and capital > max_capital:
        return "large"
    # One missing financial measure could still satisfy the legal OR condition.
    return None


def derive_is_sme(facts: dict[str, Any]) -> bool | None:
    size = facts.get("enterprise_size")
    if size in {"micro", "small", "medium"}:
        return True
    if size == "large":
        return False
    return None


def derive_innovation_selection_criteria_met(facts: dict[str, Any]) -> bool | None:
    values = [facts.get(field) if isinstance(facts.get(field), bool) else None
              for field in INNOVATION_SELECTION_FACTS]
    return _tri_any(values)


def derive_is_innovative_startup(facts: dict[str, Any]) -> bool | None:
    legal_form = facts.get("legal_form")
    legal_form_ok = None if legal_form is None else legal_form in ENTERPRISE_LEGAL_FORMS
    age = _non_negative_int(facts.get("company_age_months"))
    age_ok = None if age is None else age <= 60
    public_offering = facts.get("has_public_offering")
    no_public_offering = None if not isinstance(public_offering, bool) else not public_offering
    is_sme = facts.get("is_sme") if isinstance(facts.get("is_sme"), bool) else None
    selection = facts.get("innovation_selection_criteria_met")
    selection = selection if isinstance(selection, bool) else None
    return _tri_all([is_sme, age_ok, legal_form_ok, no_public_offering, selection])


def derive_profile_facts(direct_facts: dict[str, Any], *, as_of: date | None = None) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Return a flat decision projection and versioned derivation lineage.

    ``direct_facts`` must already contain only accepted user-input facts and
    verified/manual-review facts. Claims awaiting verification must not be passed
    into this function as decision facts.
    """
    evaluation_date = as_of or date.today()
    facts = dict(direct_facts)
    derivations = (
        ("company_age_months", ("first_business_registration_date",),
         lambda: derive_company_age_months(facts, as_of=evaluation_date)),
        ("sme_sector_group", ("sector",), lambda: derive_sme_sector_group(facts)),
        ("enterprise_size", ("sector", "social_insurance_employees", "annual_revenue_vnd", "total_capital_vnd"),
         lambda: derive_enterprise_size(facts)),
        ("is_sme", ("enterprise_size",), lambda: derive_is_sme(facts)),
        ("innovation_selection_criteria_met", INNOVATION_SELECTION_FACTS,
         lambda: derive_innovation_selection_criteria_met(facts)),
        ("is_innovative_startup", ("is_sme", "company_age_months", "legal_form", "has_public_offering", "innovation_selection_criteria_met"),
         lambda: derive_is_innovative_startup(facts)),
    )
    lineage: dict[str, dict[str, Any]] = {}
    for field, dependencies, derive in derivations:
        facts[field] = derive()
        lineage[field] = {
            "source_kind": "computed",
            "function": f"derive_{field}",
            "version": DERIVATION_VERSIONS[field],
            "depends_on": list(dependencies),
            "as_of": evaluation_date.isoformat(),
            "value": facts[field],
        }
    return facts, lineage
