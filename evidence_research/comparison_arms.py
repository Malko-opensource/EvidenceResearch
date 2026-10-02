"""Improved matched-evaluation callback over owner-supplied public bundles.

Nothing runs on import. A provider fixture is explicitly ineligible for an actual
model comparison. Whole-report adjudication belongs to an injected independent
reviewer; this callback never marks its own report as independently reviewed.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import time
from typing import Callable

from .arms import TOOL_CONTRACT, frozen_literature
from .engine import Engine
from .evaluation import prepare_numeric_review
from .model import CodexProvider, ModelUnavailable, digest
from .selection import rank_candidates
from .store import EvidenceError, Store, atomic_json, fingerprint, sha256_file
from .tasks import TASK_VERSION, make_spec, registered_data, run_task, validate_config
from .verifier import verify


def _append_json(path: Path, value: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()


class ImprovedArm:
    """Callable accepted by ``evaluation.run_matched(improved=...)``.

    ``provider_factory`` uses CodexProvider's keyword signature. ``independent_reviewer``
    receives ``(inventory_path, review_output_path)`` and must write the separately
    accountable adjudication. Without it, the report remains pending and adoption
    cannot pass the evaluation harness's whole-report gate.
    """
    def __init__(self, provider_factory: Callable = CodexProvider,
                 independent_reviewer: Callable | None = None):
        self.provider_factory = provider_factory
        self.independent_reviewer = independent_reviewer

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
        if response_file.exists():
            response = json.loads(response_file.read_text(encoding="utf-8"))
            integrity = store.verify_integrity()
            if not integrity["valid"]:
                raise EvidenceError("Completed arm evidence changed: " + "; ".join(integrity["errors"]))
            self._maybe_review(output)
            return {**response, "independent_review_pending": not (output / "report-review.json").exists(),
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
        if any(item.get("status") != "completed" for item in trace):
            raise ModelUnavailable("Unknown or failed prior proposal execution; reconcile its original evidence before resuming")
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
            state = store.state()
            engine.store.record_event("OBSERVE", {"best": state["best"], "resources": state["resources"]})
            memory = store.search(public["task_id"])
            verified = [item for item in memory if item["usable_as_verified_evidence"]]
            engine.store.record_event("RETRIEVE", {"query": public["task_id"], "results": [
                {"run_id": item["run_id"], "outcome": item["outcome"], "evidence_hash": item["evidence_hash"]}
                for item in verified]})
            request_payload = {"goal": goal, "public_task": public, "shared_tool_contract": TOOL_CONTRACT,
                "frozen_literature": frozen_literature(), "verified_memory": [
                    {"run_id": item["run_id"], "hypothesis": item["hypothesis"], "outcome": item["outcome"],
                     "verification_status": item["verification_status"], "config": item["config"],
                     "conditions": item["conditions"], "metrics": item["metrics"],
                     "failure_reason": item["failure_reason"], "evidence_hash": item["evidence_hash"]}
                    for item in verified], "remaining_proposal_calls": envelope["proposal_calls_per_unit"] - len(trace),
                "instructions": "Return JSON {candidates:[{hypothesis,config:{degree,alpha},assessment:{relevance,evidence_strength,uncertainty,normalized_cost,rationale},selection_reason,retry_of,retry_reason}],stop_reason:null}. Compare plausible candidates using verified success/failure evidence, cost and uncertainty. Assessment numbers are planning judgments, never measurements. Do not repeat execution conditions. Cite changed conditions and rationale for failed-approach retries. If no justified new experiment remains return candidates:[] and a stop_reason. Only literal legal configs run. No tools, filesystem access, hidden test answers or invented gains."}
            index = len(trace)
            call_id = f"improved-{index:04d}"
            event = {"call_id": call_id, "model_id": payload["model_id"],
                     "request_sha256": digest(request_payload), "retrieved_run_ids": [i["run_id"] for i in verified],
                     "status": "requested", "classification": "actual_model" if actual else "simulation_fixture"}
            _append_json(trace_path, event)
            # A missing completion leaves the request durable and blocks silent rerun.
            response = provider.complete(json.dumps(request_payload, ensure_ascii=False, sort_keys=True),
                                         call_id=call_id, json_response=True)
            model_evidence = provider.last_evidence or {}
            event.update(status="completed", model_evidence=model_evidence,
                         evidence_dir=str(Path(provider.evidence_dir) / call_id))
            trace.append(event)
            # Write one receipt per actual call; transport log has requested and completed events.
            _append_json(trace_path, {**event, "event": "completion"})
            raw = response.get("candidates")
            if not isinstance(raw, list):
                raise ValueError("Proposal must contain a candidates array")
            candidates = []
            rejected = []
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
                stop_reason = response.get("stop_reason") or "no_fresh_legal_candidate"
                break
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

    def _maybe_review(self, output: Path) -> None:
        review_path = output / "report-review.json"
        if self.independent_reviewer and not review_path.exists():
            self.independent_reviewer(output / "numeric-inventory.json", review_path)
        if not review_path.exists():
            return
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if review.get("reviewer_role") != "independent_verifier" or review.get("status") != "complete" or review.get("pending_claims") != 0:
            raise EvidenceError("A supplied report review is not complete independent adjudication")
        report = output / "report.md"
        inventory = output / "numeric-inventory.json"
        if review.get("report_sha256") != sha256_file(report) or review.get("inventory_sha256") != sha256_file(inventory):
            raise EvidenceError("Independent review refers to changed report/inventory")
        telemetry_path = output / "telemetry.json"
        telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
        telemetry.update(report_review_path=str(review_path), report_review_sha256=sha256_file(review_path),
                         unsupported_claims=review["unsupported_claims"],
                         claim_audit_scope="whole_report_numeric_inventory")
        atomic_json(telemetry_path, telemetry)

    def _finish(self, output, payload, store, selected, trace, decisions, trace_path, stop_reason, actual):
        # The report contains only independently calculated task metrics. Semantic
        # review is still pending until a separate reviewer classifies every numeral.
        metrics = selected["verification"]["metrics"]
        report = ("선택한 실험은 공개된 학습 자료로 적합하고 공개 검증 자료로 평가했다.\n"
                  f"실제 실행의 독립 계산 train MSE: {metrics['train_mse']:.17g}\n"
                  f"실제 실행의 독립 계산 validation MSE: {metrics['validation_mse']:.17g}\n"
                  "언어모델은 후보 설정을 제안했고 고정된 실행기와 별도 평가기가 결과를 판정했다.\n"
                  "숨겨진 최종 검사 지표와 기존 프레임워크 대비 개선은 이 보고서에서 주장하지 않는다.\n")
        report_path = output / "report.md"
        if report_path.exists() and report_path.read_text(encoding="utf-8") != report:
            raise EvidenceError("An existing generated report differs")
        report_path.write_text(report, encoding="utf-8")
        inventory_path = output / "numeric-inventory.json"
        if not inventory_path.exists():
            inventory = prepare_numeric_review(report_path, inventory_path)
        else:
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        hints = []
        for item in inventory["items"]:
            metric = "validation_mse" if "validation MSE" in item["context"] else "train_mse"
            hints.append({"claim_id": item["claim_id"], "suggested_kind": "measured", "metric": metric,
                          "run_dir": selected["run_dir"], "author_hint_only": True})
        atomic_json(output / "claim-evidence-hints.json", {"adjudication_status": "pending_independent_verifier", "hints": hints})
        events = self._store_events(store)
        audit_path = output / "research-audit.json"
        atomic_json(audit_path, {"provenance": "trusted_host_audit", "events": events,
                                "runs": store.list_runs(), "stop_reason": stop_reason})
        invoked = [event for event in events if event["phase"] == "EXECUTE" and event["payload"].get("state") == "running"]
        execution_ids = [event["payload"]["run_id"] for event in invoked]
        duplicate_executions = len(execution_ids) - len(set(execution_ids))
        runs = store.list_runs()
        recovered_errors = sum(bool(run["spec"].get("retry_of") and run["result"]["status"] == "success" and run["verification"]["valid"])
                               for run in runs if run["status"] == "completed")
        memory_hits = sum(len(event.get("retrieved_run_ids", [])) for event in trace)
        telemetry = {"provenance": "trusted_host_audit", "duplicate_executions": duplicate_executions,
            "recovered_errors": recovered_errors, "unsupported_claims": 0,
            "verified_memory_hits": memory_hits,
            "unsupported_count_scope": "No unsupported structured metric claims; whole-report semantics pending independent adjudication.",
            "claim_audit_scope": "whole_report_numeric_inventory_pending_independent_adjudication",
            "sources": [{"path": str(path), "sha256": sha256_file(path)} for path in
                        (audit_path, trace_path, output / "candidate-decisions.jsonl", inventory_path,
                         output / "claim-evidence-hints.json")], "report_path": str(report_path),
            "report_sha256": sha256_file(report_path)}
        atomic_json(output / "telemetry.json", telemetry)
        self._maybe_review(output)
        response = {"model_id": payload["model_id"], "resource_envelope": payload["resource_envelope"],
            "model_execution_kind": "actual_model_execution" if actual else "simulation_fixture",
            "selected_run_dir": selected["run_dir"], "model_trace_path": str(trace_path),
            "model_evidence_dirs": [item["evidence_dir"] for item in trace],
            "telemetry_evidence_path": str(output / "telemetry.json"), "report_path": str(report_path),
            "numeric_inventory_path": str(inventory_path), "independent_review_pending": not (output / "report-review.json").exists(),
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
