"""Decision-only policy access. Audit callers must explicitly opt out."""
from __future__ import annotations


DECISION_QUERY = {
    "is_current": True,
    "review_status": "approved",
    "eligible_for_decision": True,
    "evidence_unit_ids.0": {"$exists": True},
}


class PolicyRepository:
    def __init__(self, collection): self.collection = collection

    def get_policies(self, audit: bool = False):
        return list(self.collection.find({} if audit else DECISION_QUERY, {"_id": 0}))
