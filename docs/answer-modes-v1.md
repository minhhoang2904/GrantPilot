# Answer Modes v1

`POST /ask` is authenticated and exposes two explicit pipelines.

## Request

```json
{
  "email": "owner@example.com",
  "question": "Công ty tôi có đủ điều kiện không?",
  "mode": "lookup | advisory",
  "session_id": null,
  "top_k": 5
}
```

The current frontend aliases remain accepted:

- `rag` -> `lookup`
- `eligibility` -> `advisory`

The JWT subject must equal `email`; otherwise the API returns `403` and does
not write chat history.

## Lookup

Lookup runs legal retrieval and grounded answer generation only. It does not
read the company profile and remains independent of Server C.

The response contains:

- `mode: "lookup"`
- `answer`
- `legal_units`: full retrieval evidence for the current response
- `citations`: stable source projection persisted with chat history
- `eligibility_results: []`
- `results: []` (frontend compatibility)

## Advisory

Advisory runs:

```text
retrieval -> candidate policy IDs
canonical companies profile -> decision_facts projection
Server C derivations -> deterministic rule evaluation -> evidence hydration
grounded explanation of the fixed decisions
```

The response contains:

- `mode: "advisory"`
- `legal_units` and `citations` from retrieval
- `eligibility_results`: canonical Server C results
- `eligibility.derived_facts` and `eligibility.derivation_lineage`
- `results`: compatibility mapping for the current policy table UI

Canonical eligibility statuses are:

- `eligible`
- `not_eligible`
- `needs_more_information`
- `manual_review`

Missing facts produce `needs_more_information`; they are never converted to
false. Advisory requires `company-profile-v1`; a missing or legacy profile
returns `409`.

Only policies satisfying the Mongo decision gate are evaluated:

```text
is_current=true
review_status=approved
eligible_for_decision=true
evidence_unit_ids is non-empty
```

Therefore an empty `eligibility_results` with excluded candidate IDs means the
ingestion review gate has not approved those policies; it is not permission to
evaluate candidate or unreviewed rules.

## Server B/C rolling compatibility

The canonical Server C endpoint is `POST /eligibility/evaluate`. Its v1 request
uses `facts` and its canonical response field is `eligibility_results`.

During the v0.2 retirement window, Server C also accepts the legacy request key
`profile` and returns the legacy response alias `results`. Server B first sends
the v1 request, retries a `422` once with `profile`, and normalizes `results` to
`eligibility_results`. This compatibility is only for staggered container
rollouts; new code must use the v1 names.
