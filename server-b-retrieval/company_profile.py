"""Company Profile v1 persistence contract and conservative legacy adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any


PROFILE_SCHEMA_VERSION = "company-profile-v1"

IDENTITY_FIELDS = {
    "company_name",
    "business_description",
    "province_name",
}

USER_INPUT_FACT_FIELDS = {
    "sector",
    "primary_business_activity_group",
    "legal_form",
    "province_code",
    "social_insurance_employees",
    "annual_revenue_vnd",
    "total_capital_vnd",
    "first_business_registration_date",
    "has_public_offering",
    "has_business_registration",
    "has_state_capital",
    "has_foreign_investment_capital",
    "has_coworking_contract",
    "coworking_monthly_cost_vnd",
    "has_collateral",
    "has_received_same_interest_support",
}

WRITABLE_FIELDS = IDENTITY_FIELDS | USER_INPUT_FACT_FIELDS

SAFE_LEGACY_RENAMES = {
    "is_public_offering": "has_public_offering",
    "product_type": "business_description",
    "province": "province_name",
}


def canonicalize_company(document: dict[str, Any]) -> dict[str, Any]:
    """Expose safe legacy spellings without fabricating decision facts."""
    company = dict(document)
    for legacy, canonical in SAFE_LEGACY_RENAMES.items():
        if company.get(canonical) is None and company.get(legacy) is not None:
            company[canonical] = company[legacy]
    company.setdefault("profile_schema_version", "legacy")
    return company


def writable_values(data: dict[str, Any]) -> dict[str, Any]:
    return {field: data[field] for field in WRITABLE_FIELDS if field in data}


def provenance_updates(data: dict[str, Any], timestamp: datetime) -> dict[str, dict[str, Any]]:
    return {
        field: {
            "source_kind": "user_input",
            "status": "accepted" if value is not None else "missing",
            "asserted_at": timestamp,
        }
        for field, value in data.items()
        if field in USER_INPUT_FACT_FIELDS
    }


def new_company_document(data: dict[str, Any], timestamp: datetime) -> dict[str, Any]:
    values = writable_values(data)
    return {
        "email": data["email"],
        **values,
        "profile_schema_version": PROFILE_SCHEMA_VERSION,
        "fact_provenance": provenance_updates(values, timestamp),
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def decision_facts(document: dict[str, Any]) -> dict[str, Any]:
    """Return only canonical Fact Catalog inputs accepted from onboarding."""
    company = canonicalize_company(document)
    return {field: company.get(field) for field in USER_INPUT_FACT_FIELDS}
