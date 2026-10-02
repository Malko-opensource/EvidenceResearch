"""Transparent hypothesis ranking. Scores are priorities, never measured effects."""

from __future__ import annotations

import math
from typing import Any


def rank_candidates(candidates: list[dict], memory: list[dict] | None = None) -> list[dict]:
    """Rank candidates by declared relevance, evidence, cost and uncertainty.

    A candidate may contain ``spec`` and ``assessment``. Assessments are explicit
    planning judgments. No expected improvement is converted to a measured claim.
    Verified failures count against a matching approach unless a reason and changed
    conditions are supplied. Exact duplicates are removed by the Store's fingerprint.
    """
    memory = memory or []
    ranked = []
    for original in candidates:
        candidate = dict(original)
        spec = candidate.get("spec", candidate)
        assessment = candidate.get("assessment", {})
        def unit(key: str, default: float) -> float:
            value = float(assessment.get(key, default))
            if not math.isfinite(value):
                raise ValueError(f"Non-finite selection assessment: {key}")
            return min(1.0, max(0.0, value))
        relevance = unit("relevance", 0.5)
        evidence = unit("evidence_strength", 0.0)
        uncertainty = unit("uncertainty", 0.5)
        cost = unit("normalized_cost", 0.5)
        def same_approach(item: dict) -> bool:
            prior = item.get("applicability", item.get("conditions", {}))
            if prior.get("task_id") and "config" in spec:
                if prior.get("task_id") != spec.get("task_id") or prior.get("config") != spec.get("config"):
                    return False
                for key in ("model", "implementation_sha256", "evaluator_sha256", "split_manifest_sha256"):
                    if key in prior and key in spec and prior[key] != spec[key]:
                        return False
                return True
            return item.get("hypothesis") == spec.get("hypothesis")
        failures = [item for item in memory if item.get("outcome") == "failure"
                    and item.get("verification_status") == "verified"
                    and item.get("usable_as_verified_evidence", True) and same_approach(item)]
        retry_valid = bool(spec.get("retry_reason") and spec.get("retry_of"))
        duplicate = bool(assessment.get("duplicate", False))
        score = relevance * 0.40 + evidence * 0.25 + uncertainty * 0.20 - cost * 0.15
        if duplicate:
            score -= 2.0
        if failures and not retry_valid:
            score -= 1.0
        candidate["selection"] = {
            "priority_score": score,
            "score_kind": "planning_judgment",
            "relevance": relevance,
            "evidence_strength": evidence,
            "normalized_cost": cost,
            "uncertainty": uncertainty,
            "duplicate": duplicate,
            "matching_verified_failures": [item["run_id"] for item in failures],
            "retry_reason": spec.get("retry_reason"),
            "rationale": assessment.get("rationale", "Ranked using declared planning assessments."),
        }
        ranked.append(candidate)
    return sorted(ranked, key=lambda item: (-item["selection"]["priority_score"],
                                         str(item.get("spec", item).get("hypothesis", ""))))


def choose_candidate(candidates: list[dict], memory: list[dict] | None = None) -> dict | None:
    ranked = rank_candidates(candidates, memory)
    return ranked[0] if ranked else None
