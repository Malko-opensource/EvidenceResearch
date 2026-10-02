"""Model proposals are confined to public data and allow-listed configurations."""
from __future__ import annotations

import json

from .model import digest
from .tasks import make_spec, public_task, validate_config


class ResearchProposer:
    def __init__(self, provider, task_id, seed, criterion, baseline_run_id=None,
                 resource_envelope=None):
        self.provider = provider
        self.task_id = task_id
        self.seed = seed
        self.criterion = criterion
        self.baseline_run_id = baseline_run_id
        self.resource_envelope = resource_envelope or {
            "device": "cpu", "tools": ["trusted polynomial ridge"],
            "network": False, "model_tools": "forbidden; audited"}

    def __call__(self, context):
        goal = context.get("goal") or {}
        memory = context.get("memory", [])
        observations = []
        for item in memory:
            evidence = item.get("original_evidence", {})
            spec = evidence.get("spec", {})
            result = evidence.get("result", {})
            verification = evidence.get("verification", {})
            observations.append({
                "run_id": item["run_id"], "hypothesis": item.get("hypothesis"),
                "outcome": item.get("outcome"), "verification_status": item.get("verification_status"),
                "config": spec.get("config"), "conditions": item.get("conditions"),
                "verified_metrics": verification.get("metrics", {}),
                "failure_reason": result.get("error", result.get("failure_reason")),
                "evidence_hash": item.get("evidence_hash"),
                "evidence": verification.get("evidence", [])})
        payload = {
            "goal": goal, "task": public_task(self.task_id, self.seed),
            "verified_memory": observations,
            "instructions": (
                "Choose the next experiment based on the goal and actual evidence. "
                "Return JSON {candidates:[{hypothesis,config:{degree,alpha},"
                "assessment:{relevance,evidence_strength,uncertainty,normalized_cost,rationale},"
                "selection_reason}], stop_reason:null}. Compare at least two plausible "
                "approaches. Every assessment number is a planning judgment in [0,1]. "
                "Do not repeat completed configurations. For an earlier failure, explain "
                "changed conditions and include retry_of and retry_reason. Never report "
                "expected gains as measured performance. If no justified experiment "
                "exists return {candidates:[],stop_reason: explanation}; this does not "
                "declare the research goal complete. Use only public train/validation "
                "data. Test data, evaluator code, filesystem and external tools are "
                "unavailable through the experiment API.")}
        call_id = "proposal-" + digest({"task": self.task_id, "seed": self.seed,
                                       "payload": payload})[:32]
        response = self.provider.complete(json.dumps(payload, ensure_ascii=False),
                                          call_id=call_id, json_response=True)
        candidates = []
        for item in response.get("candidates", []):
            config = validate_config(item["config"])
            if any(obs["config"] == config and obs["verification_status"] == "verified"
                   and obs["conditions"].get("seed") == self.seed
                   and obs["conditions"].get("task_id") == self.task_id
                   and obs["conditions"].get("model") == self.provider.model
                   for obs in observations if isinstance(obs["conditions"], dict)):
                continue
            spec = make_spec(self.task_id, self.seed, config,
                             model=self.provider.model,
                             hypothesis=item["hypothesis"], criterion=self.criterion,
                             resource_envelope=self.resource_envelope)
            spec["selection_reason"] = item.get("selection_reason", "Model compared registered candidates")
            if self.baseline_run_id:
                spec["baseline_run_id"] = self.baseline_run_id
            for key in ("retry_of", "retry_reason"):
                if item.get(key):
                    spec[key] = item[key]
            trace = self.provider.last_evidence
            spec["model_evidence"] = {
                "call_id": call_id, "fingerprint": trace["fingerprint"],
                "model": trace["model"], "execution_kind": trace["execution_kind"],
                "usage": trace["usage"], "wall_seconds": trace["wall_seconds"],
                "record": trace["evidence_record"]}
            candidates.append({"spec": spec, "assessment": item.get("assessment", {})})
        return candidates or None
