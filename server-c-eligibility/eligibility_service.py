"""Application service joining derivation, decisions, evidence and explanation."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

import config
import eligibility_engine
import ranking
from explanation import EligibilityExplainer
from policy_repository import MongoPolicyRepository
from profile_features import DERIVATION_VERSIONS, derive_profile_facts


class EligibilityService:
    def __init__(self, repository=None, explainer=None) -> None:
        self.repository = repository or MongoPolicyRepository()
        self.explainer = explainer or EligibilityExplainer()

    def evaluate(
        self,
        direct_facts: dict[str, Any],
        *,
        candidate_policy_ids: Iterable[str] | None = None,
        only_eligible: bool = False,
        top_k: int | None = None,
        include_explanation: bool = True,
        evaluation_date: date | None = None,
    ) -> dict[str, Any]:
        requested_ids = list(dict.fromkeys(candidate_policy_ids or []))
        policies = self.repository.get_policies(requested_ids or None, require_evidence=True)
        facts, lineage = derive_profile_facts(direct_facts, as_of=evaluation_date)
        raw_results = eligibility_engine.evaluate_profile_against_all_policies(facts, policies)
        selected = ranking.rank_results(
            raw_results,
            only_eligible=only_eligible,
            top_k=top_k if top_k is not None else config.DEFAULT_TOP_K,
        )

        unit_ids = [
            unit_id
            for result in selected
            for unit_id in result.get("evidence_unit_ids", [])
        ]
        evidence = self.repository.get_evidence(unit_ids)
        evidence_by_id = {unit.get("unit_id"): unit for unit in evidence}
        for result in selected:
            result["sources"] = [
                _source(evidence_by_id[unit_id])
                for unit_id in result.get("evidence_unit_ids", [])
                if unit_id in evidence_by_id
            ]

        explanation = (
            self.explainer.explain(facts, selected, evidence)
            if include_explanation
            else ""
        )
        found_ids = {policy.get("policy_id") for policy in policies}
        derived_fields = set(DERIVATION_VERSIONS)
        return {
            "eligibility_results": selected,
            "explanation": explanation,
            "derived_facts": {field: facts.get(field) for field in derived_fields},
            "derivation_lineage": lineage,
            "diagnostics": {
                "requested_policy_count": len(requested_ids),
                "evaluated_policy_count": len(policies),
                "returned_policy_count": len(selected),
                "excluded_candidate_policy_ids": [
                    policy_id for policy_id in requested_ids if policy_id not in found_ids
                ],
                "decision_layer": "deterministic_rules",
                "explanation_layer": "fpt_llm" if config.llm_enabled() else "deterministic_fallback",
            },
        }


def _source(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_id": unit.get("unit_id"),
        "document_number": unit.get("document_number"),
        "article": unit.get("article"),
        "clause": unit.get("clause"),
        "point": unit.get("point"),
        "page_start": unit.get("page_start"),
        "page_end": unit.get("page_end"),
        "source_url": unit.get("source_url"),
    }
