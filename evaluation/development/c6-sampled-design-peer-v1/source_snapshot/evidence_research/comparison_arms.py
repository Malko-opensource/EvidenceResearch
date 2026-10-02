"""Improved matched-evaluation callback over owner-supplied public bundles.

Nothing runs on import. A provider fixture is explicitly ineligible for an actual
model comparison. Whole-report adjudication belongs to an injected independent
reviewer; this callback never marks its own report as independently reviewed.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import time
from typing import Callable

from .arms import TOOL_CONTRACT, literature_from_envelope, recovery_summary
from .engine import Engine
from .evaluation import prepare_numeric_review
from .model import CodexProvider, ModelUnavailable, PreregisteredResourcesExhausted, digest, parse_object
from .model_attempt_audit import audit_failed_model_attempts
from .report_contract import REPORT_SCHEMA_VERSION
from .selection import rank_candidates
from .store import EvidenceError, Store, atomic_json, execution_fingerprint, fingerprint, sha256_file
from .tasks import TASK_VERSION, make_spec, registered_data, run_task, validate_config
from .verifier import verify


def _append_json(path: Path, value: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def compact_memory_record(item: dict) -> dict:
    """Expose essential conditions while retaining the complete immutable source.

    Compaction is serialization, not evidence deletion or a new success judgment.
    The original criterion and baseline remain separate from execution identity.
    """
    original = item["original_evidence"]
    spec = original["spec"]
    folder = Path(original["run_dir"])
    references = []
    for name in ("registered_spec.json", "result.json", "verification.json", "manifest.json"):
        path = folder / name
        if not path.is_file() or path.is_symlink():
            raise EvidenceError("Compact memory requires the original immutable evidence files")
        references.append({"path": str(path), "sha256": sha256_file(path)})
    if json.loads((folder / "registered_spec.json").read_text(encoding="utf-8")) != spec:
        raise EvidenceError("Compact memory's registered specification differs from original evidence")
    conditions = {key: spec[key] for key in ("task_id", "task_version", "model", "seed", "metric",
                  "implementation_sha256", "evaluator_sha256", "split_manifest_sha256", "data_sha256") if key in spec}
    conditions.update(resource_envelope_sha256=fingerprint(spec["resource_envelope"]),
                      criterion_sha256=fingerprint(spec["criterion"]),
                      baseline_sha256=fingerprint(spec.get("baseline", {})),
                      execution_fingerprint=execution_fingerprint(spec))
    return {"run_id": item["run_id"], "hypothesis": item["hypothesis"], "outcome": item["outcome"],
            "verification_status": item["verification_status"], "config": item["config"],
            "conditions": conditions, "metrics": item["metrics"], "failure_reason": item["failure_reason"],
            "registered_criterion": json.loads(json.dumps(spec["criterion"], allow_nan=False)),
            "baseline_run_id": spec.get("baseline", {}).get("run_id"),
            "evidence_hash": item["evidence_hash"], "original_evidence": references,
            "judgment_scope": "Outcome uses the original preregistered criterion, not a relabeled criterion; original evidence contains complete conditions."}


def provider_resource_observation(trace: list[dict], runs: list[dict], *, actual: bool,
                                  failed_audit: dict | None = None) -> dict:
    """Link cumulative observed resources to raw receipts; unknown is never zero.

    Simulation fixtures retain their classification and cannot establish actual
    model cost. Cached input and reasoning counts are metadata subsets, not extra
    input/output tokens. Monetary prices and a next-call cost are unavailable.
    """
    completed = [item for item in trace if item.get("status") == "completed"]
    failed = [item for item in trace if item.get("status") == "failed"]
    token_keys = ("input_tokens", "output_tokens")
    usage = {key: 0 for key in token_keys}
    known, seconds_known, seconds, sources, call_costs = actual, actual, [], [], []
    for item in trace:
        folder = Path(item["evidence_dir"])
        path = folder / "result.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("status") != item.get("status"):
            raise EvidenceError("Model resource receipt does not match the durable transport status")
        sources.append({"call_id": item["call_id"], "path": str(path), "sha256": sha256_file(path)})
        wall = record.get("wall_seconds")
        if isinstance(wall, bool) or not isinstance(wall, (int, float)) or not math.isfinite(wall) or wall < 0:
            seconds_known = False
        else:
            seconds.append(wall)
        if item.get("status") == "completed":
            raw_usage = record.get("usage", {})
            call_known = all(isinstance(raw_usage.get(key), int) and not isinstance(raw_usage[key], bool)
                             and raw_usage[key] >= 0 for key in token_keys)
            if not call_known:
                known = False
            else:
                for key in token_keys:
                    usage[key] += raw_usage[key]
            call_costs.append({"call_id": item["call_id"], "token_usage": {key: raw_usage[key] for key in token_keys} if actual and call_known else None,
                               "wall_seconds": wall if actual and isinstance(wall, (int, float)) and not isinstance(wall, bool) and math.isfinite(wall) and wall >= 0 else None,
                               "evidence_path": str(path), "evidence_sha256": sha256_file(path)})
    completed_usage = dict(usage)
    if failed:
        if failed_audit is None or not failed_audit.get("valid") or failed_audit.get("failed_attempts") != len(failed):
            known = False
        elif failed_audit["unknown_failed_token_usage"]:
            known = False
        else:
            for key in token_keys:
                usage[key] += failed_audit["failed_token_usage"][key]
    cpu_seconds = [run["result"].get("execution_seconds") for run in runs if run.get("result")]
    cpu_known = all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 for value in cpu_seconds)
    return {"kind": "measured_resource" if actual else "simulation_fixture", "provider_attempts": len(trace),
            "completed_provider_calls": len(completed), "failed_provider_attempts": len(failed),
            "tokens_known": known, "token_usage": usage if known else None,
            "completed_token_usage_lower_bound": completed_usage if actual else None,
            "wall_seconds": math.fsum(seconds) if seconds_known else None,
            "actual_cpu_executions": len(cpu_seconds), "cpu_execution_seconds": math.fsum(cpu_seconds) if cpu_known else None,
            "completed_call_costs": call_costs, "sources": sources, "provider_billed_cost": None,
            "scope": "All completed and definitive failed raw requests in this unit, once per actual request. Token totals require attested input/output usage for every attempt. CPU times are separate from provider wall time.",
            "prospective_cost": {"kind": "inference", "value": None, "reason": "Previous request costs inform planning; they do not measure the cost or gain of the next proposal."}}


def improved_recovery_timeline(runs: list[dict], decisions: list[dict], *, decisions_path: Path) -> list[dict]:
    by_call = {}
    for run in runs:
        call_id = run["spec"].get("model_evidence", {}).get("call_id")
        by_call.setdefault(call_id, []).append(run)
    timeline = []
    for decision in decisions:
        call_id = decision["call_id"]
        has_fresh = any(not item["selection"]["duplicate"] for item in decision["ranked"])
        if decision["rejected"] and not has_fresh:
            timeline.append({"kind": "protocol_error", "call_id": call_id,
                "decisions_path": str(decisions_path), "reason": [item["reason"] for item in decision["rejected"]]})
        for run in by_call.get(call_id, []):
            if run["status"] != "completed":
                continue
            folder = Path(run["run_dir"])
            reference = {"call_id": call_id, "run_id": run["run_id"], "run_dir": str(folder),
                "result_path": str(folder / "result.json"), "result_sha256": sha256_file(folder / "result.json"),
                "verification_path": str(folder / "verification.json"), "verification_sha256": sha256_file(folder / "verification.json")}
            if run["result"]["status"] == "failure":
                timeline.append({**reference, "kind": "runtime_error", "reason": run["result"].get("error")})
            elif not run["verification"].get("valid"):
                timeline.append({**reference, "kind": "verification_error", "reason": run["verification"].get("reasons")})
            else:
                timeline.append({**reference, "kind": "verified_cpu_success"})
    return timeline


class ImprovedArm:
    """Callable accepted by ``evaluation.run_matched(improved=...)``.

    ``provider_factory`` uses CodexProvider's keyword signature. ``independent_reviewer``
    receives ``(inventory_path, review_output_path)`` and must write the separately
    accountable adjudication. Without it, the report remains pending and adoption
    cannot pass the evaluation harness's whole-report gate.
    """
    def __init__(self, provider_factory: Callable = CodexProvider,
                 independent_reviewer: Callable | None = None, continuation_reason: str | None = None):
        self.provider_factory = provider_factory
        self.independent_reviewer = independent_reviewer
        self.continuation_reason = continuation_reason

    @staticmethod
    def _public_payload(payload: dict) -> tuple[dict, dict, dict | None]:
        if payload.get("arm") != "C":
            raise ValueError("ImprovedArm handles only the preregistered C arm")
        public = payload["public_task"]
        allowed = {"task_id", "seed", "task_version", "objective", "metric", "allowed_config", "task_bundle", "criterion"}
        if set(public) - allowed or public.get("task_version") != TASK_VERSION:
            raise ValueError("Unsupported public task contract; private paths/definitions are forbidden")
        if set(public["task_bundle"]) != {"train", "validation", "split_manifest"}:
            raise ValueError("Only public training/validation and hashed split metadata are allowed")
        envelope = payload["resource_envelope"]
        calls = envelope.get("proposal_calls_per_unit")
        if isinstance(calls, bool) or not isinstance(calls, int) or calls <= 0:
            raise ValueError("Preregistered proposal_calls_per_unit must be a positive integer")
        cpu_limit = envelope.get("actual_cpu_executions_per_unit", calls)
        if isinstance(cpu_limit, bool) or not isinstance(cpu_limit, int) or cpu_limit <= 0:
            raise ValueError("Matched actual_cpu_executions_per_unit must be a positive integer")
        criterion = public.get("criterion", envelope.get("success_criterion"))
        if criterion is not None:
            if criterion.get("direction") != "min" or "threshold" not in criterion:
                raise ValueError("A public stopping criterion must preregister min/threshold")
            threshold = criterion["threshold"]
            if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
                raise ValueError("The public success threshold must be finite")
        # make_spec/registered_data validate hashes without looking up task answers.
        probe = make_spec(public["task_id"], public["seed"], {"degree": 1, "alpha": 0.0},
                          model=payload["model_id"], task_bundle=public["task_bundle"],
                          criterion={"direction": "min"}, resource_envelope=envelope)
        registered_data(probe)
        return public, envelope, criterion

    def __call__(self, payload: dict, arm_output: Path) -> dict:
        output = Path(arm_output).resolve()
        output.mkdir(parents=True, exist_ok=True)
        public, envelope, stopping = self._public_payload(payload)
        literature = literature_from_envelope(envelope)
        identity = fingerprint(payload)
        receipt = output / "callback-registration.json"
        registration = {"payload_sha256": identity, "public_task": public,
                        "model_id": payload["model_id"], "resource_envelope": envelope,
                        "success_criterion": stopping, "implementation_sha256": sha256_file(Path(__file__)),
                        "visibility": "public task_bundle only; no owner test rows or private file paths",
                        "resource_scope": "Matched per-unit evaluation budget, not a research-goal iteration cap"}
        if receipt.exists():
            if json.loads(receipt.read_text(encoding="utf-8")) != registration:
                raise EvidenceError("Callback conditions/source differ from its durable registration")
        else:
            atomic_json(receipt, registration)
        study_root = output / "research"
        store = Store(study_root)
        goal = {"objective": public["objective"], "task_id": public["task_id"],
                "memory_query": public["task_id"], "payload_sha256": identity}
        if stopping:
            goal["research_criterion"] = {**stopping, "task_id": public["task_id"], "metric": "validation_mse"}
        store.init_goal(goal)
        response_file = output / "arm-response.json"
        budget_file = output / "registered-resource-exhaustion.json"
        if budget_file.exists():
            preserved = json.loads(budget_file.read_text(encoding="utf-8"))
            if preserved.get("callback_registration_sha256") != sha256_file(receipt):
                raise EvidenceError("Preserved registered-budget failure has different callback conditions")
            integrity = store.verify_integrity()
            if not integrity["valid"]:
                raise EvidenceError("Preserved budget-failure CPU evidence changed: " + "; ".join(integrity["errors"]))
            for source in preserved["sources"]:
                path = Path(source["path"])
                if not path.is_file() or path.is_symlink() or sha256_file(path) != source["sha256"]:
                    raise EvidenceError("Preserved registered-budget failure evidence changed")
            if response_file.exists():
                raise EvidenceError("A completed arm response conflicts with its registered-budget failure")
            raise PreregisteredResourcesExhausted(preserved["error"])
        if response_file.exists():
            response = json.loads(response_file.read_text(encoding="utf-8"))
            integrity = store.verify_integrity()
            if not integrity["valid"]:
                raise EvidenceError("Completed arm evidence changed: " + "; ".join(integrity["errors"]))
            self._maybe_review(output)
            return {**response, "independent_review_pending": not self._reviews_present(output),
                    "resumed_without_execution": True}
        provider = self.provider_factory(evidence_dir=output / "model", model=payload["model_id"],
            reasoning_effort=envelope.get("reasoning_effort"), public_dir=output / "public_model_cwd")
        actual = getattr(provider, "execution_kind", None) == "real_model"
        trace_path = output / "model-transport.jsonl"
        transport_rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
                          if line.strip()] if trace_path.exists() else []
        latest_calls = {}
        for row in transport_rows:
            latest_calls[row["call_id"]] = row
        trace = list(latest_calls.values())
        if any(item.get("status") not in ("completed", "failed") for item in trace):
            raise ModelUnavailable("Unknown prior proposal execution; reconcile its original evidence before resuming")
        failed_audit = None
        if any(item.get("status") == "failed" for item in trace):
            if not self.continuation_reason:
                raise ModelUnavailable("A definitive failed proposal needs an explicit continuation reason")
            _, failed_audit = self._failed_audit(output, trace, payload["model_id"], self.continuation_reason, envelope)
        candidates_path = output / "candidate-decisions.jsonl"
        existing_decisions = [json.loads(line) for line in candidates_path.read_text(encoding="utf-8").splitlines()
                              if line.strip()] if candidates_path.exists() else []
        # Pending executions reconcile before any new model call; completed work is not repeated.
        engine = Engine(study_root, run_task, verify)
        resumed = engine.resume()
        if any(run.get("blocked") for run in resumed):
            raise EvidenceError("Prior execution lacks a durable receipt; automatic repetition refused")
        stop_reason = None
        for completed in store.list_runs():
            if self._target_met(completed, stopping):
                stop_reason = "preregistered_public_target_met"
        while stop_reason is None and len(trace) < envelope["proposal_calls_per_unit"]:
            execution_events = [event for event in self._store_events(store) if event["phase"] == "EXECUTE"
                                and event["payload"].get("state") == "running"]
            if len(execution_events) >= envelope.get("actual_cpu_executions_per_unit", envelope["proposal_calls_per_unit"]):
                stop_reason = "preregistered_per_unit_cpu_resources_exhausted"
                break
            state = store.state()
            engine.store.record_event("OBSERVE", {"best": state["best"], "resources": state["resources"]})
            memory = store.search(public["task_id"])
            verified = [item for item in memory if item["usable_as_verified_evidence"]]
            actual_runs = [run for run in store.list_runs() if run.get("result") is not None]
            engine.store.record_event("RETRIEVE", {"query": public["task_id"], "results": [
                {"run_id": item["run_id"], "outcome": item["outcome"], "evidence_hash": item["evidence_hash"]}
                for item in verified]})
            compact_memory = [compact_memory_record(item) for item in verified]
            resources = provider_resource_observation(trace, actual_runs, actual=actual, failed_audit=failed_audit)
            request_payload = {"goal": goal, "public_task": public, "shared_tool_contract": TOOL_CONTRACT,
                "actual_cpu_attempts_to_date": len(actual_runs),
                "distinct_configs_to_date": len({fingerprint(run["spec"]["config"]) for run in actual_runs}),
                "selected_record_scope": "Each memory result describes its named actual CPU invocation; cumulative invocation counts and distinct configurations are separate host observations. Cached reuse never increments them.",
                "host_ledger": {"current_events_path": str(store.db_path), "actual_execution_receipts": [
                    {"execution_id": run["run_id"], "result_path": str(Path(run["run_dir"]) / "result.json"),
                     "result_sha256": sha256_file(Path(run["run_dir"]) / "result.json")}
                    for run in actual_runs]},
                "frozen_literature": literature, "literature_snapshot_sha256": fingerprint(literature),
                "verified_memory": compact_memory, "observed_resources": resources,
                "remaining_proposal_calls": envelope["proposal_calls_per_unit"] - len(trace),
                "proposal_feedback": [{"call_id": decision["call_id"], "rejected": decision["rejected"],
                    "duplicate_configs": [candidate["spec"]["config"] for candidate in decision["ranked"]
                                           if candidate["selection"]["duplicate"]],
                    "response_stop_reason": decision["response_stop_reason"]} for decision in existing_decisions],
                "instructions": "Return JSON {candidates:[{hypothesis,config:{degree,alpha},assessment:{relevance,evidence_strength,uncertainty,normalized_cost,rationale},selection_reason,retry_of,retry_reason}],stop_reason:null}. Compare plausible candidates using verified success/failure evidence, uncertainty and the cumulative actual resource receipts. Assessment numbers including normalized_cost are planning judgments, never measured cost or expected gains. Compare the information gained from additional validation queries against observed costs and validation-selection uncertainty; microscopic validation changes alone do not establish generalization. If a hypothesis family is exhausted, justify a different design or a no-justified-experiment decision from its evidence and remaining uncertainty. No fixed iteration, small-gain or consecutive-failure stopping rule is supplied. Do not repeat execution conditions. Cite changed conditions and rationale for failed-approach retries. If no justified new experiment remains return candidates:[] and a stop_reason. Only literal legal configs run. No tools, filesystem access, hidden test answers or invented gains."}
            index = len(trace)
            call_id = f"improved-{index:04d}"
            resource_path = output / "resource-observations" / f"{call_id}.json"
            resource_snapshot = {"call_id": call_id, "resources": resources,
                "serialization": {"kind": "measured_serialization", "unit": "UTF-8 bytes",
                    "complete_request_bytes": len(json.dumps(request_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")),
                    "compact_memory_bytes": len(json.dumps(compact_memory, ensure_ascii=False, sort_keys=True).encode("utf-8")),
                    "original_conditions_bytes": len(json.dumps([item["conditions"] for item in verified], ensure_ascii=False, sort_keys=True).encode("utf-8")),
                    "scope": "Host JSON serialization sizes, not a token-count estimate or a billing claim."}}
            if resource_path.exists() and json.loads(resource_path.read_text(encoding="utf-8")) != resource_snapshot:
                raise EvidenceError("An existing prerequest resource observation differs")
            if not resource_path.exists():
                atomic_json(resource_path, resource_snapshot)
            event = {"call_id": call_id, "model_id": payload["model_id"],
                     "request_sha256": digest(request_payload), "retrieved_run_ids": [i["run_id"] for i in verified],
                     "resource_observation_path": str(resource_path), "resource_observation_sha256": sha256_file(resource_path),
                     "status": "requested", "classification": "actual_model" if actual else "simulation_fixture"}
            _append_json(trace_path, event)
            # A missing completion leaves the request durable and blocks silent rerun.
            try:
                answer = provider.complete(json.dumps(request_payload, ensure_ascii=False, sort_keys=True),
                                           call_id=call_id, json_response=False)
            except ModelUnavailable:
                folder = Path(provider.evidence_dir) / call_id
                if (folder / "result.json").exists() and (folder / "events.jsonl").exists():
                    record = json.loads((folder / "result.json").read_text(encoding="utf-8"))
                    raw_events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
                    if record.get("status") == "failed" and not record.get("tool_calls") and not any(e.get("type") == "turn.completed" for e in raw_events) and sum(e.get("type") == "turn.failed" for e in raw_events) == 1:
                        request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
                        host_path = output / "host-no-action" / f"{call_id}.json"
                        atomic_json(host_path, {"provenance": "trusted_host_audit",
                            "attempt_result_path": str(folder / "result.json"), "attempt_result_sha256": sha256_file(folder / "result.json"),
                            "request_fingerprint": request["fingerprint"], "host_action_taken": False,
                            "model_response_consumed": False,
                            "retry_reason": "Definitive provider failure before proposal return; explicit continuation required.",
                            "sources": [{"path": str(folder / name), "sha256": sha256_file(folder / name)}
                                        for name in ("request.json", "result.json", "events.jsonl", "stderr.log")]})
                        _append_json(trace_path, {**event, "status": "failed", "event": "failure",
                            "evidence_dir": str(folder), "host_no_action_receipt": str(host_path),
                            "model_evidence": record})
                raise
            try:
                response = parse_object(answer) if isinstance(answer, str) else answer
                if not isinstance(response, dict):
                    raise ValueError("Proposal must be a JSON object")
            except (ValueError, TypeError) as error:
                response = {"candidates": None, "parse_error": f"{type(error).__name__}: {error}",
                            "correction": "Return the registered candidates JSON object; the invalid completed response consumed one proposal request."}
            model_evidence = provider.last_evidence or {}
            event.update(status="completed", model_evidence=model_evidence,
                         evidence_dir=str(Path(provider.evidence_dir) / call_id))
            trace.append(event)
            # Write one receipt per actual call; transport log has requested and completed events.
            _append_json(trace_path, {**event, "event": "completion"})
            raw = response.get("candidates")
            candidates = []
            rejected = []
            if not isinstance(raw, list):
                rejected.append({"candidate": response, "reason": "Proposal must contain a candidates array; correct the response shape."})
                raw = []
            anchor = self._best_verified(store)
            for item in raw:
                try:
                    config = validate_config(item["config"])
                    criterion = dict(stopping or {"direction": "min"})
                    spec = make_spec(public["task_id"], public["seed"], config, model=payload["model_id"],
                        hypothesis=item["hypothesis"], criterion=criterion,
                        resource_envelope=envelope, task_bundle=public["task_bundle"])
                    if not stopping:
                        if anchor:
                            spec["criterion"] = {"direction": "min", "baseline_value": anchor["verification"]["metrics"]["validation_mse"], "improvement": 0.0}
                            spec["baseline"] = {"run_id": anchor["run_id"]}
                        else:
                            spec["role"] = "baseline"
                    spec["selection_reason"] = item.get("selection_reason", item.get("assessment", {}).get("rationale", "Compared candidate planning judgments"))
                    for key in ("retry_of", "retry_reason"):
                        if item.get(key):
                            spec[key] = item[key]
                    spec["model_evidence"] = {"call_id": call_id, "model": payload["model_id"],
                        "fingerprint": model_evidence.get("fingerprint"), "execution_kind": model_evidence.get("execution_kind", getattr(provider, "execution_kind", "unknown")),
                        "usage": model_evidence.get("usage", {}), "wall_seconds": model_evidence.get("wall_seconds"),
                        "record": model_evidence.get("evidence_record")}
                    candidates.append({"spec": spec, "assessment": {**item.get("assessment", {}),
                        "duplicate": store.find_execution(spec) is not None}})
                except (ValueError, KeyError, TypeError) as exc:
                    rejected.append({"candidate": item, "reason": f"{type(exc).__name__}: {exc}"})
            ranked = rank_candidates(candidates, verified)
            fresh = [candidate for candidate in ranked if not candidate["selection"]["duplicate"]]
            decision = {"call_id": call_id, "ranked": ranked, "rejected": rejected,
                        "retrieved_run_ids": event["retrieved_run_ids"], "response_stop_reason": response.get("stop_reason")}
            _append_json(candidates_path, decision)
            existing_decisions.append(decision)
            if not fresh:
                explicit_stop = response.get("stop_reason")
                if not raw and not rejected and isinstance(explicit_stop, str) and explicit_stop.strip():
                    stop_reason = "model_no_justified_new_experiment: " + explicit_stop
                    break
                engine.store.record_event("PROPOSE", {"call_id": call_id, "state": "correction_required",
                    "rejected": rejected, "duplicate_configs": [candidate["spec"]["config"] for candidate in ranked],
                    "reason": "No fresh legal execution; provide corrective feedback under the registered proposal resources."})
                continue
            selected = fresh[0]
            engine.store.record_event("PROPOSE", {"candidates": [{"hypothesis": c["spec"]["hypothesis"], "assessment": c["selection"]} for c in ranked],
                                                   "selected": selected["spec"]["hypothesis"], "claim_kind": "proposal"})
            result = engine.progress(selected["spec"])
            if result.get("blocked"):
                raise EvidenceError("Registered execution blocked; independent reconciliation required")
            if self._target_met(result, stopping):
                stop_reason = "preregistered_public_target_met"
        if stop_reason is None:
            stop_reason = "preregistered_per_unit_proposal_resources_exhausted"
        if stop_reason in {"preregistered_per_unit_cpu_resources_exhausted",
                            "preregistered_per_unit_proposal_resources_exhausted"}:
            store.record_event("DECIDE", {"decision": "registered_task_budget_failure", "stop_reason": stop_reason,
                "scope": "Per-unit registered resources exhausted; this does not stop or complete the research Goal."})
            source_paths = [receipt, trace_path, candidates_path]
            source_paths += [Path(item["evidence_dir"]) / name for item in trace
                             for name in ("request.json", "result.json")]
            source_paths += [Path(run["run_dir"]) / name for run in store.list_runs()
                             for name in ("registered_spec.json", "result.json", "verification.json", "manifest.json")]
            error = "Registered per-unit resources exhausted: " + stop_reason + "; the research Goal remains incomplete"
            preserved = {"kind": "registered_task_budget_failure", "stop_reason": stop_reason, "error": error,
                "callback_registration_sha256": sha256_file(receipt), "research_state": store.state(),
                "provider_attempts": len(trace), "actual_cpu_executions": len([event for event in self._store_events(store)
                    if event["phase"] == "EXECUTE" and event["payload"].get("state") == "running"]),
                "sources": [{"path": str(path), "sha256": sha256_file(path)}
                            for path in source_paths if path.is_file()],
                "scope": "Durable terminal evaluation-unit failure. Completed CPU evidence and selected best remain preserved; no success report is fabricated."}
            atomic_json(budget_file, preserved)
            raise PreregisteredResourcesExhausted(error)
        selected = self._best_verified(store)
        if selected is None:
            raise EvidenceError("No independently verified successful CPU execution is available for selection")
        return self._finish(output, payload, store, selected, trace, existing_decisions,
                            trace_path, stop_reason, actual)

    @staticmethod
    def _target_met(run: dict, criterion: dict | None) -> bool:
        verification = run.get("verification") or {}
        value = verification.get("metrics", {}).get("validation_mse")
        return bool(criterion and verification.get("valid") and isinstance(value, (int, float))
                    and value <= criterion["threshold"])

    @staticmethod
    def _best_verified(store: Store) -> dict | None:
        valid = [run for run in store.list_runs() if run["status"] == "completed"
                 and (run.get("verification") or {}).get("valid")
                 and run["result"]["status"] == "success"]
        return min(valid, key=lambda run: run["verification"]["metrics"]["validation_mse"]) if valid else None

    @staticmethod
    def _failed_audit(output, trace, model_id, reason, envelope):
        failed = [item for item in trace if item.get("status") == "failed"]
        if not failed:
            return None, {"failed_attempts": 0, "failed_token_usage": {"input_tokens": 0, "output_tokens": 0}, "unknown_failed_token_usage": False}
        entries, receipts = [], {}
        for item in failed:
            folder = Path(item["evidence_dir"]).resolve()
            receipt_path = Path(item["host_no_action_receipt"]).resolve()
            request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
            receipts[str(folder)] = str(receipt_path)
            entries.append({"failed_dir": str(folder), "result_sha256": sha256_file(folder / "result.json"),
                "request_fingerprint": request["fingerprint"], "host_action_receipt": str(receipt_path),
                "receipt_sha256": sha256_file(receipt_path)})
        lineage = {"kind": "explicit_model_attempt_resume_lineage", "provenance": "trusted_host_audit",
                   "model_id": model_id, "retry_reason": reason, "attempts": entries}
        path = output / "model-attempt-lineages" / f"{fingerprint(lineage)[:24]}.json"
        if not path.exists():
            atomic_json(path, lineage)
        audit = audit_failed_model_attempts([item["failed_dir"] for item in entries], model_id=model_id,
            allowed_roots=[str(output)], host_action_receipts=receipts, lineage_path=str(path),
            resource_envelope=envelope, arm_output=str(output))
        return path, audit

    def _maybe_review(self, output: Path) -> None:
        pairs = ((output / "report.md", output / "numeric-inventory.json", output / "report-review.json"),
                 (output / "research_report.json", output / "companion-numeric-inventory.json", output / "companion-review.json"))
        for report, inventory, review_path in pairs:
            if self.independent_reviewer and not review_path.exists():
                self.independent_reviewer(inventory, review_path)
        if not self._reviews_present(output):
            return
        reviews = []
        for report, inventory, review_path in pairs:
            review = json.loads(review_path.read_text(encoding="utf-8"))
            if review.get("reviewer_role") != "independent_verifier" or review.get("status") != "complete" or review.get("pending_claims") != 0:
                raise EvidenceError("A supplied report review is not complete independent adjudication")
            if review.get("report_sha256") != sha256_file(report) or review.get("inventory_sha256") != sha256_file(inventory):
                raise EvidenceError("Independent review refers to changed report/inventory")
            reviews.append(review)
        telemetry_path = output / "telemetry.json"
        telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
        telemetry.update(report_review_paths=[{"path": str(review_path), "sha256": sha256_file(review_path)} for _, _, review_path in pairs],
                         unsupported_claims=sum(review["unsupported_claims"] for review in reviews),
                         claim_audit_scope="whole_report_and_companion_numeric_inventories")
        atomic_json(telemetry_path, telemetry)

    @staticmethod
    def _reviews_present(output: Path) -> bool:
        return all((output / name).exists() for name in ("report-review.json", "companion-review.json"))

    def _finish(self, output, payload, store, selected, trace, decisions, trace_path, stop_reason, actual):
        # The report contains only independently calculated task metrics. Semantic
        # review is still pending until a separate reviewer classifies every numeral.
        metrics = selected["verification"]["metrics"]
        spec = selected["spec"]
        runs = store.list_runs()
        literature = [{"kind": "literature", "url": paper["url"], "claim": paper["text"]}
                      for paper in literature_from_envelope(payload["resource_envelope"])]
        source_evidence = [{"path": str(Path(selected["run_dir"]) / name), "sha256": sha256_file(Path(selected["run_dir"]) / name)}
                           for name in ("registered_spec.json", "result.json", "predictions.json", "verification.json")]
        completed_trace = [item for item in trace if item.get("status") == "completed"]
        failed_lineage, failed_audit = self._failed_audit(output, trace, payload["model_id"], self.continuation_reason or "Registered continuation evidence retained.", payload["resource_envelope"])
        tokens_known = actual and not failed_audit["unknown_failed_token_usage"] and all(all(isinstance(item.get("model_evidence", {}).get("usage", {}).get(key), int)
                                          for key in ("input_tokens", "output_tokens")) for item in completed_trace)
        token_usage = {key: sum(item["model_evidence"]["usage"][key] for item in completed_trace) + failed_audit["failed_token_usage"][key]
                       for key in ("input_tokens", "output_tokens")} if tokens_known else None
        seconds = sum(item["model_evidence"]["wall_seconds"] for item in trace) if actual and all(
            isinstance(item.get("model_evidence", {}).get("wall_seconds"), (int, float)) for item in trace) else None
        companion = {"schema_version": REPORT_SCHEMA_VERSION, "goal": store.state()["goal"]["objective"],
            "hypothesis": spec["hypothesis"], "selected_config": spec["config"],
            "provenance": {key: spec[key] for key in ("task_id", "task_version", "seed", "split_manifest_sha256", "implementation_sha256", "evaluator_sha256")},
            "execution": {"kind": spec["execution_entrypoint"]["kind"],
                "entrypoint": spec["command"], "reproduction_command": spec["reproduction_command"]},
            "evidence": source_evidence,
            "measured_metrics": [{"kind": "measured", "metric": name, "value": value,
                "evidence_path": str(Path(selected["run_dir"]) / "result.json"),
                "evidence_sha256": sha256_file(Path(selected["run_dir"]) / "result.json")}
                for name, value in metrics.items()],
            "selection_reason": spec.get("selection_reason", "Minimum independently verified validation MSE among actual completed runs."),
            "unresolved": [{"question": run["spec"]["hypothesis"],
                "reason": (run["result"] or {}).get("error") or "; ".join((run["verification"] or {}).get("reasons", [])) or "Registered criterion not met; retained as failed evidence."}
                for run in runs if run["outcome"] in ("failure", "inconclusive")],
            "limitations": ["Training and validation data are public; test outcomes remain with the independent owner.",
                "Observed validation selection alone does not prove out-of-sample improvement.",
                "Hypothesis, selection rationale and candidate scores are model-authored planning judgments, not measurements.",
                "Model sampling randomness has no exposed seed; statistical uncertainty requires matched independent units.",
                "Provider monetary cost is unknown; token counts do not establish a billing price.",
                "The regression task and allowlisted tools do not establish general scientific discovery performance."],
            "references": literature, "next_questions": ["Does the frozen independent evaluation confirm useful generalization?",
                "Does removing retrieved verified memory change decisions under matched model and resources?",
                "Which unresolved hypothesis needs changed conditions and new preregistered evidence?"],
            "resources": {"tokens_known": tokens_known, "token_usage": token_usage, "seconds": seconds,
                "provider_billed_cost": None, "scope": "Raw completed model-call records; independent evaluator owns full attempt accounting."},
            "planning_claim_kind": "proposal", "stop_reason": stop_reason}
        companion_path = output / "research_report.json"
        atomic_json(companion_path, companion)
        report = ("선택한 실험은 공개된 학습 자료로 적합하고 공개 검증 자료로 평가했다.\n"
                  f"실제 실행의 독립 계산 train MSE: {metrics['train_mse']:.17g}\n"
                  f"실제 실행의 독립 계산 validation MSE: {metrics['validation_mse']:.17g}\n"
                  "언어모델은 후보 설정을 제안했고 고정된 실행기와 별도 평가기가 결과를 판정했다.\n"
                  "숨겨진 최종 검사 지표와 기존 프레임워크 대비 개선은 이 보고서에서 주장하지 않는다.\n\n"
                  "연구 목적·가설·설정·분할·소스·실행 및 재현 명령, 원본 증거, 미결 사항, 문헌, 한계와 다음 질문을 아래에 기록한다.\n"
                  "가설과 선택 이유는 계획 판단이고 측정 결과는 원본 예측 산출물과 별도 평가에 연결된다.\n\n"
                  "```json\n" + json.dumps(companion, ensure_ascii=False, sort_keys=True, indent=2) + "\n```\n")
        report_path = output / "report.md"
        if report_path.exists() and report_path.read_text(encoding="utf-8") != report:
            raise EvidenceError("An existing generated report differs")
        report_path.write_text(report, encoding="utf-8")
        inventory_path = output / "numeric-inventory.json"
        if not inventory_path.exists():
            inventory = prepare_numeric_review(report_path, inventory_path)
        else:
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        companion_inventory_path = output / "companion-numeric-inventory.json"
        if not companion_inventory_path.exists():
            companion_inventory = prepare_numeric_review(companion_path, companion_inventory_path)
        else:
            companion_inventory = json.loads(companion_inventory_path.read_text(encoding="utf-8"))
        hints = []
        for item in inventory["items"] + companion_inventory["items"]:
            context = item["context"]
            metric = "validation_mse" if "validation MSE" in context else "train_mse" if "train MSE" in context else None
            if '"value"' in context:
                inventory_text = report if item in inventory["items"] else companion_path.read_text(encoding="utf-8")
                previous = inventory_text.splitlines()[max(0, item["line"] - 8):item["line"]]
                metric = next((name for name in metrics if any(f'"metric": "{name}"' in line for line in previous)), None)
            hints.append({"claim_id": item["claim_id"], "suggested_kind": "measured" if metric else "requires_independent_semantic_classification",
                          "metric": metric, "run_dir": selected["run_dir"],
                          "source_path": str(companion_path), "source_sha256": sha256_file(companion_path), "author_hint_only": True})
        atomic_json(output / "claim-evidence-hints.json", {"adjudication_status": "pending_independent_verifier", "hints": hints})
        events = self._store_events(store)
        audit_path = output / "research-audit.json"
        atomic_json(audit_path, {"provenance": "trusted_host_audit", "events": events,
                                "runs": store.list_runs(), "stop_reason": stop_reason})
        invoked = [event for event in events if event["phase"] == "EXECUTE" and event["payload"].get("state") == "running"]
        execution_ids = [event["payload"]["run_id"] for event in invoked]
        execution_identities = [execution_fingerprint(store.get_run(run_id)["spec"]) for run_id in execution_ids]
        duplicate_executions = len(execution_identities) - len(set(execution_identities))
        runs = store.list_runs()
        recovery = recovery_summary(improved_recovery_timeline(runs, decisions, decisions_path=output / "candidate-decisions.jsonl"))
        verified_retries = [run for run in runs if run["status"] == "completed" and run["spec"].get("retry_of")
                            and run["result"]["status"] == "success" and run["verification"].get("valid")]
        by_id = {run["run_id"]: run for run in runs}
        failed_hypothesis_retries = [run for run in verified_retries if by_id.get(run["spec"]["retry_of"], {}).get("outcome") == "failure"]
        memory_hits = sum(len(event.get("retrieved_run_ids", [])) for event in trace)
        telemetry = {"provenance": "trusted_host_audit", "duplicate_executions": duplicate_executions,
            **recovery, "unsupported_claims": 0,
            "completed_verified_retries": len(verified_retries), "failed_hypothesis_retries": len(failed_hypothesis_retries),
            "hypothesis_retry_evidence": [{"run_id": run["run_id"], "retry_of": run["spec"]["retry_of"],
                "original_evidence_path": str(Path(run["run_dir"]) / "registered_spec.json"),
                "original_evidence_sha256": sha256_file(Path(run["run_dir"]) / "registered_spec.json"),
                "prior_hypothesis_outcome": by_id.get(run["spec"]["retry_of"], {}).get("outcome")} for run in verified_retries],
            "hypothesis_retry_scope": "Explicit retry_of registrations with successful independently verified CPU execution. A failed original hypothesis criterion is separate from a runtime/protocol error.",
            "verified_memory_hits": memory_hits,
            "verified_memory_hits_scope": "Cumulative verified-memory record exposures in model requests, not unique retrievals or causal improvement.",
            "unique_verified_memory_records": len({run_id for event in trace for run_id in event.get("retrieved_run_ids", [])}),
            "duplicate_execution_identity": "store.execution_fingerprint: task/version/seed/model/config/data/source/tool/resource conditions; changed prose or criterion does not create a new execution identity.",
            "unsupported_count_scope": "No unsupported structured metric claims; whole-report semantics pending independent adjudication.",
            "claim_audit_scope": "whole_report_numeric_inventory_pending_independent_adjudication",
            "sources": [{"path": str(path), "sha256": sha256_file(path)} for path in
                        (audit_path, trace_path, output / "candidate-decisions.jsonl", inventory_path,
                         output / "claim-evidence-hints.json", companion_path, companion_inventory_path)], "report_path": str(report_path),
            "report_sha256": sha256_file(report_path)}
        atomic_json(output / "telemetry.json", telemetry)
        self._maybe_review(output)
        response = {"model_id": payload["model_id"], "resource_envelope": payload["resource_envelope"],
            "model_execution_kind": "actual_model_execution" if actual else "simulation_fixture",
            "selected_run_dir": selected["run_dir"], "model_trace_path": str(trace_path),
            "cpu_execution_dirs": [store.get_run(run_id)["run_dir"] for run_id in execution_ids],
            "model_evidence_dirs": [item["evidence_dir"] for item in completed_trace],
            "failed_model_attempt_dirs": [item["evidence_dir"] for item in trace if item.get("status") == "failed"],
            "failed_model_host_receipts": [item["host_no_action_receipt"] for item in trace if item.get("status") == "failed"],
            "continuation_lineage_path": str(failed_lineage) if failed_lineage else None,
            "telemetry_evidence_path": str(output / "telemetry.json"), "report_path": str(report_path),
            "numeric_inventory_path": str(inventory_path), "companion_numeric_inventory_path": str(companion_inventory_path),
            "independent_review_pending": not self._reviews_present(output),
            "report_contract_path": str(companion_path),
            "stop_reason": stop_reason, "comparison_improvement_claim": False}
        atomic_json(output / "arm-response.json", response)
        return response

    @staticmethod
    def _store_events(store: Store) -> list[dict]:
        with store._connect() as db:
            return [{**dict(row), "payload": json.loads(row["payload"])}
                    for row in db.execute("SELECT * FROM events ORDER BY sequence")]


def improved_callback(payload: dict, arm_output: Path) -> dict:
    """Default callback leaves report review pending for an independent owner."""
    return ImprovedArm()(payload, arm_output)
