"""Goal-directed orchestration; no implicit global iteration or failure limits."""

from __future__ import annotations

from pathlib import Path
import time
import traceback
from typing import Callable

from .selection import rank_candidates
from .store import EvidenceError, Store, atomic_json


class Engine:
    def __init__(self, root: Path | str, runner: Callable, verifier: Callable,
                 proposer: Callable | None = None):
        if runner is verifier:
            raise ValueError("Implementation and independent verification must be separate callables")
        self.store = Store(root)
        self.runner = runner
        self.verifier = verifier
        self.proposer = proposer

    def _check_integrity(self) -> None:
        result = self.store.verify_integrity()
        if not result["valid"]:
            raise EvidenceError("Evidence integrity failed: " + "; ".join(result["errors"]))

    def progress(self, spec_or_run: dict | str) -> dict:
        self._check_integrity()
        if isinstance(spec_or_run, str):
            run = self.store.get_run(spec_or_run)
        elif "spec" in spec_or_run and "run_id" in spec_or_run:
            run = self.store.get_run(spec_or_run["run_id"])
        else:
            run = self.store.register(spec_or_run)
        if run["status"] == "completed":
            return {**run, "resumed_without_execution": True}
        if run["status"] in {"running", "unknown_execution"}:
            run = self.store.reconcile(run["run_id"])
        if run["status"] == "unknown_execution":
            return {**run, "blocked": "unknown_execution",
                    "next_action": "Reconcile durable evidence or register changed conditions with retry_reason."}
        run_dir = Path(run["run_dir"])
        if run["status"] == "pending":
            self.store.record_event("IMPLEMENT", {"run_id": run["run_id"],
                "implementation_sha256": run["spec"].get("implementation_sha256", run["spec"].get("source_hash")),
                "execution_policy": "trusted_allowlisted_runner"})
            self.store.mark_running(run["run_id"])
            start = time.perf_counter()
            try:
                result = self.runner(run["spec"], run_dir)
            except Exception as exc:
                error_path = run_dir / "runner_failure.json"
                atomic_json(error_path, {"error_type": type(exc).__name__, "message": str(exc),
                                         "traceback": traceback.format_exc()})
                result = {"status": "failure", "metrics": {}, "artifacts": [str(error_path)],
                          "failure_reason": str(exc), "claims": [{"kind": "inference",
                           "text": "Execution raised an exception; no performance improvement is claimed."}]}
            self.store.record_event("RESOURCE", {"run_id": run["run_id"],
                "usage": {} if "elapsed_seconds" in result.get("resources", {}) else {
                    "elapsed_seconds": time.perf_counter() - start},
                "provenance": "orchestrator_wall_clock"})
            run = self.store.record_execution(run["run_id"], result)
        if run["status"] == "executed":
            self.store.record_event("VERIFY", {"run_id": run["run_id"], "state": "verifying",
                "evaluator_sha256": run["spec"]["evaluator_sha256"]})
            try:
                verification = self.verifier(run["spec"], run["result"], run_dir)
            except Exception as exc:
                verification = {"valid": False, "status": "inconclusive", "metrics": {},
                                "reasons": [f"Independent verifier failed: {type(exc).__name__}: {exc}"]}
            return self.store.complete(run["run_id"], run["result"], verification)
        return run

    def step(self, spec: dict | None = None) -> dict:
        self._check_integrity()
        context = self.store.state()
        self.store.record_event("OBSERVE", {"active_runs": context["active_runs"],
            "best": context["best"], "resources": context["resources"]})
        if spec is None and context["active_runs"]:
            return self.progress(context["active_runs"][0])
        query = ""
        if spec:
            query = str(spec.get("task_id", ""))
        elif context.get("goal"):
            query = str(context["goal"].get("memory_query", ""))
        memory = self.store.search(query)
        self.store.record_event("RETRIEVE", {"query": query,
            "results": [{"run_id": item["run_id"], "outcome": item["outcome"],
                         "verification_status": item["verification_status"],
                         "evidence_hash": item["evidence_hash"]} for item in memory]})
        context["memory"] = memory
        selection = None
        if spec is None:
            if self.proposer is None:
                return {"status": "needs_proposal", "state": self.store.state()}
            proposed = self.proposer(context)
            if proposed is None:
                self.store.record_event("PROPOSE", {"decision": "no_candidate",
                    "reason": "Proposer requires a new hypothesis or external resources."})
                return {"status": "needs_proposal", "state": self.store.state()}
            if isinstance(proposed, list):
                proposed = [{**candidate, "assessment": {
                    **candidate.get("assessment", {}),
                    "duplicate": self.store.find_execution(candidate.get("spec", candidate)) is not None}}
                    for candidate in proposed]
                ranked = rank_candidates(proposed, memory)
                if not ranked:
                    return {"status": "needs_proposal", "state": self.store.state()}
                selected = ranked[0]
                spec = selected.get("spec", selected)
                selection = selected["selection"]
                self.store.record_event("PROPOSE", {"candidates": [{"hypothesis": item.get("spec", item).get("hypothesis"),
                    "assessment": item["selection"]} for item in ranked], "selection": selection})
            else:
                spec = proposed.get("spec", proposed)
                selection = proposed.get("assessment", {})
        if selection is None or not isinstance(proposed if 'proposed' in locals() else None, list):
            self.store.record_event("PROPOSE", {"hypothesis": spec["hypothesis"],
                "rationale": spec.get("selection_reason", "Explicit registered proposal."),
                "assessment": selection, "claim_kind": "proposal"})
        return self.progress(spec)

    def resume(self) -> list[dict]:
        self._check_integrity()
        return [self.progress(run["run_id"]) for run in self.store.list_runs() if run["status"] != "completed"]

    def run(self) -> dict:
        """Continue while proposals exist; explicit resource or goal checks own stopping.

        No iteration count, wall-clock limit, or consecutive-failure cap is invented.
        A proposer must return ``None`` when it lacks an actionable proposal; this
        is recorded as needing a proposal, never as goal completion.
        """
        while True:
            satisfied = self._research_goal_satisfied()
            if satisfied:
                return {"status": "research_goal_satisfied", "evidence": satisfied,
                        "framework_goal_complete": False}
            result = self.step()
            if result.get("blocked") or result.get("status") == "needs_proposal":
                return result
            if result.get("resumed_without_execution"):
                return {"status": "needs_new_hypothesis", "run_id": result["run_id"],
                        "reason": "Proposer selected completed evidence; execution was not repeated."}

    def _research_goal_satisfied(self) -> dict | None:
        """A registered task target can stop this research run, not the overall Goal."""
        state = self.store.state()
        criterion = (state.get("goal") or {}).get("research_criterion")
        if not criterion:
            return None
        if criterion.get("direction") not in {"min", "max"} or "threshold" not in criterion:
            raise ValueError("research_criterion needs direction and threshold")
        direction = 1 if criterion["direction"] == "max" else -1
        for best in state["best"].values():
            if best["task_id"] == criterion["task_id"] and best["metric"] == criterion["metric"]:
                if direction * (best["value"] - criterion["threshold"]) >= 0:
                    return best
        return None
