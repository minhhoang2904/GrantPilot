"""Decision-only policy access. Audit callers must explicitly opt out."""
from __future__ import annotations


DECISION_QUERY = {
    "is_current": True,
    "review_status": "approved",
    "eligible_for_decision": True,
    "evidence_unit_ids.0": {"$exists": True},
}


class MongoPolicyRepository:
    """Mongo-backed policy access; collection injection keeps offline tests simple."""
    def __init__(self, collection): self.collection = collection

    def get_policies(self, audit: bool = False):
        return list(self.collection.find({} if audit else DECISION_QUERY, {"_id": 0}))

    def get_evidence(self, policy):
        return list(policy.get("evidence_unit_ids") or [])

    def policy_ids(self, audit: bool = False):
        return [row.get("policy_id") for row in self.get_policies(audit) if row.get("policy_id")]

    def stats(self):
        return {"decision_ready": len(self.get_policies())}


# Backwards-compatible name, not a second implementation.
PolicyRepository = MongoPolicyRepository
