# Company Profile v1

Company Profile v1 is the write contract between onboarding, document review,
and Server C. The Fact Catalog remains the authority for decision-field names.

## Stored aggregate

```text
company_id, owner_email
identity: company_name, tax_code, business_description, province_name
facts: canonical direct facts accepted from user input or verification
fact_provenance[field]: source_kind, status, evidence_refs, asserted_at, verified_at
derived_facts: computed values plus function/version/dependencies/as_of
profile_schema_version, created_at, updated_at
```

Identity and descriptive fields are not decision facts. `product_type`, free-text
industry descriptions, and company name must never be injected into rules.

## Collection domains

1. Onboarding collects identity plus Fact Catalog fields whose `source_kinds`
   include `user_input`.
2. Document-only and manual-review facts remain `null` until a trusted process
   supplies them. The MVP does not implement a claim/review workflow.
3. Server C receives a flat projection of accepted direct facts and recomputes
   all derived facts for the evaluation date.

For MVP demos and tests, a document-only fact may be seeded as an already
verified fact. The public onboarding API must not accept it as authoritative
user input. A future evidence phase can add claims, uploads, and review states
without changing the decision-fact contract.

Legacy fields are handled conservatively:

- `is_public_offering` may migrate to `has_public_offering`.
- `founded_year` must not become a fabricated registration date.
- `has_patent` must not become `has_valid_invention_patent` without evidence.
- A province name must not be guessed into `province_code`.
- `business_type` must not become `legal_form` or `is_sme`.

## Derived facts

Every derivation is deterministic, versioned, and three-valued. Missing input
produces `null`, not `false`.

- `company_age_months`: completed calendar months from the first registration
  date to the explicit evaluation date.
- `sme_sector_group`: deterministic mapping from `sector`.
- `enterprise_size`: BHXH employee threshold AND the revenue-or-capital test.
  When a missing alternative could change a `large` result, return `null`.
- `is_sme`: true for micro/small/medium, false for large, otherwise null.
- `innovation_selection_criteria_met`: true when any verified selection method
  is true; false only when every method is explicitly false; otherwise null.
- `is_innovative_startup`: three-valued AND of SME status, age at most 60
  months, enterprise legal form, no public offering, and verified innovation
  selection criteria.

## Delivery order

1. Derivation engine and contract tests.
2. One canonical company collection and migration adapter for legacy records.
3. Strict API models that preserve explicit null and reject invalid values.
4. Progressive onboarding for user-input facts.
5. Server C integration and end-to-end eligibility tests.
6. Post-MVP: claims, uploads, and evidence-review workflow.
