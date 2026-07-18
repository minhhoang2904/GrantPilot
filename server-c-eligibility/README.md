# Server C — Eligibility

Server C receives canonical decision facts, recomputes all versioned derived
facts, evaluates approved current policies with deterministic rules, hydrates
legal evidence and optionally asks an LLM to explain the fixed decision.

Statuses are `eligible`, `not_eligible`, `needs_more_information`, and
`manual_review`. Missing facts remain `null` and lead to
`needs_more_information`; they are never silently treated as false.

`POST /eligibility/evaluate` accepts `facts`, `candidate_policy_ids`, `top_k`,
`only_eligible`, `include_explanation`, and an optional `evaluation_date`.
