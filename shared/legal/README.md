# Server A -> Server B/C artifact contract

Server A writes all integration artifacts to this directory, which is mounted
as `/app/shared/legal` in the Docker services:

- `legal_units.jsonl`: one Điều/Khoản/Điểm per line; source of truth for RAG.
- `chroma/`: Persistent Chroma collection `legal_units`.
- `policies.json`: canonical policy records.
- `policy_candidates.json`: LLM-extracted policies requiring review.

Each legal unit includes `document_number`, `article_title`, `page_start`,
`page_end`, `source_url`, `issued_date`, `effective_from`, `effective_to`, and
`document_status`. Unknown legal dates/status are `null`/`unknown` until
verified against an authoritative legal database.

Eligibility must not treat a policy as authoritative merely because it exists
in `policies.json`. For production, accept only an explicit
`review.status == "approved"`; candidates use
`review.status == "ai_extracted_requires_review"` and are demo-only.
