"""A separately frozen, one-next-action memory exposure diagnostic.

Register/prepare never call a model. Collect uses the real frozen Codex provider;
ON/OFF differ only in verified_memory. No framework or evaluator monkeypatching.
This seeded-information treatment is not a free research or cross-task study.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from evidence_research.arms import TOOL_CONTRACT, frozen_literature
from evidence_research.engine import Engine
from evidence_research.evaluation import (_audit_cpu_executions, _audit_model_evidence, _audit_request_inventory,
    _owner_metric, design_sample_size, frozen_sources, paired_uncertainty)
from evidence_research.model import CodexProvider, ModelUnavailable, parse_object
from evidence_research.model_attempt_audit import audit_failed_model_attempts
from evidence_research.store import EvidenceError, Store, atomic_json, fingerprint, sha256_file, utc_now
from evidence_research.tasks import DEVELOPMENT_TASKS, TASK_VERSION, make_spec, split_manifest, task_data, validate_config, value_hash
from evidence_research.verifier import verify
from evidence_research.tasks import run_task


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_once(path, value):
    path = Path(path)
    if path.exists():
        if load(path) != value:
            raise EvidenceError(f"Immutable diagnostic receipt differs: {path.name}")
    else:
        atomic_json(path, value)


def register(config, output):
    output = Path(output).resolve()
    if config.get("kind") != "memory_exposure_development_pilot" or not config.get("model_id"):
        raise ValueError("Explicit development pilot kind/model required")
    envelope = config["resource_envelope"]
    if "reasoning_effort" not in envelope:
        raise ValueError("Matched reasoning_effort must be explicit")
    calibrations = [validate_config(item) for item in config["calibration_configs"]]
    if len(calibrations) < 2 or len({fingerprint(c) for c in calibrations}) != len(calibrations):
        raise ValueError("Register at least two distinct host-selected calibration configs")
    for field in ("proposal_calls_per_unit", "actual_cpu_executions_per_unit"):
        if isinstance(envelope.get(field), bool) or not isinstance(envelope.get(field), int) or envelope[field] <= 0:
            raise ValueError("Explicit positive shared model/CPU limits required")
    if len(calibrations) + 1 > envelope["actual_cpu_executions_per_unit"]:
        raise ValueError("Common calibration plus one proposed CPU action must fit the same resources")
    inputs = config["sample_design_inputs"]
    if set(inputs) != {"meaningful_gain", "precision_halfwidth", "variance_relative_se", "power"}:
        raise ValueError("Only the frozen statistical design inputs are accepted")
    for name in ("meaningful_gain", "precision_halfwidth", "variance_relative_se"):
        if isinstance(inputs.get(name), bool) or not isinstance(inputs.get(name), (int, float)) or not math.isfinite(inputs[name]) or inputs[name] <= 0:
            raise ValueError("Declare positive statistical design inputs before actual model runs")
    if inputs.get("power") != 0.80 or inputs["variance_relative_se"] > 1:
        raise ValueError("Frozen design supports power=.80 and variance relative SE <=1")
    units, ids = config["units"], set()
    if not units:
        raise ValueError("Explicit task/seed units required; no repetition count is invented")
    for unit in units:
        identity = unit["unit_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", identity) or identity in ids or unit["task_id"] not in DEVELOPMENT_TASKS:
            raise ValueError("Distinct safe development unit identifiers required")
        ids.add(identity)
        task_data(unit["task_id"], unit["seed"])
    receipt = output / "ablation-registration.json"
    if receipt.exists():
        if load(receipt)["config"] != config:
            raise EvidenceError("Diagnostic registration cannot be retroactively changed")
        return check(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Diagnostic registration needs an empty new workspace")
    output.mkdir(parents=True, exist_ok=True)
    sources = frozen_sources([Path(__file__)])
    snapshot = output / "source-snapshot"
    for source in sources:
        relative = Path("scripts") / Path(source).name if Path(source).name == Path(__file__).name else Path("evidence_research") / Path(source).name
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    entries = []
    for unit in units:
        data, manifest = task_data(unit["task_id"], unit["seed"]), split_manifest(unit["task_id"], unit["seed"])
        public = {"task_id": unit["task_id"], "seed": unit["seed"], "task_version": TASK_VERSION,
            "objective": "choose the next polynomial-ridge experiment using public training/validation only",
            "metric": "validation_mse", "allowed_config": {"degree": "integer 1..8", "alpha": "finite 0..100"},
            "task_bundle": {"train": data["train"], "validation": data["validation"], "split_manifest": manifest}}
        owner = {"unit_id": unit["unit_id"], "test": data["test"], "test_sha256": value_hash(data["test"])}
        public_path, owner_path = output / "owner-data" / f"{unit['unit_id']}-public.json", output / "owner-data" / f"{unit['unit_id']}-private.json"
        atomic_json(public_path, public)
        atomic_json(owner_path, owner)
        entries.append({"unit_id": unit["unit_id"], "public_path": str(public_path), "public_sha256": sha256_file(public_path),
                        "owner_path": str(owner_path), "owner_sha256": sha256_file(owner_path)})
    registered = {"schema_version": "memory-exposure-diagnostic-1", "config": config, "sources": sources,
        "config_sha256": fingerprint(config), "source_snapshot": str(snapshot), "units": entries,
        "tool_sha256": fingerprint(TOOL_CONTRACT), "literature_sha256": fingerprint(frozen_literature()),
        "registered_at": utc_now(), "primary": "duplicate proposal reduction including valid stop decisions: duplicate_OFF - duplicate_ON",
        "model_order": "ON/OFF for even registered unit indices; OFF/ON for odd indices",
        "model_randomness": "Unexposed sampling seed/server weights; identical public identifier/settings do not establish identical internal randomness",
        "primary_denominator": "all preregistered paired decision opportunities; incomplete outcomes remain and block inference",
        "calibration_selection": "host-selected before results, never attributed to the model",
        "adoption_policy": "No automatic adoption; independent design/review required before a new confirmatory study",
        "scope": "seeded verified prior evidence exposure; development diagnostic, not general memory research"}
    atomic_json(receipt, registered)
    atomic_json(output / "registration-anchor.json", {"registration_sha256": sha256_file(receipt)})
    return registered


def check(output):
    output = Path(output).resolve()
    receipt = output / "ablation-registration.json"
    registration = load(receipt)
    if sha256_file(receipt) != load(output / "registration-anchor.json")["registration_sha256"] or fingerprint(registration["config"]) != registration["config_sha256"]:
        raise EvidenceError("Preregistered diagnostic conditions changed")
    for source, digest in registration["sources"].items():
        current = Path(__file__) if Path(source).name == Path(__file__).name else PROJECT / "evidence_research" / Path(source).name
        if sha256_file(current) != digest:
            raise EvidenceError("Frozen source changed; use the saved snapshot or register a fresh diagnostic")
    if fingerprint(TOOL_CONTRACT) != registration["tool_sha256"] or fingerprint(frozen_literature()) != registration["literature_sha256"]:
        raise EvidenceError("Shared tool/literature contract changed")
    for unit in registration["units"]:
        for kind in ("public", "owner"):
            if sha256_file(unit[f"{kind}_path"]) != unit[f"{kind}_sha256"]:
                raise EvidenceError("Registered diagnostic data changed")
    return registration


def _directory(output, unit_id, arm):
    return Path(output).resolve() / "units" / unit_id / arm


def _engine(directory):
    return Engine(directory / "research", run_task, verify)


def prepare(output):
    registration = check(output)
    config = registration["config"]
    results = []
    for index, entry in enumerate(registration["units"]):
        public = load(entry["public_path"])
        for arm in (("ON", "OFF") if index % 2 == 0 else ("OFF", "ON")):
            directory = _directory(output, entry["unit_id"], arm)
            directory.mkdir(parents=True, exist_ok=True)
            engine = _engine(directory)
            engine.store.init_goal({"objective": public["objective"], "task_id": public["task_id"], "experiment": "seeded memory exposure diagnostic"})
            if any(item.get("blocked") for item in engine.resume()):
                raise EvidenceError("Calibration execution is unknown; automatic repetition refused")
            runs = []
            for calibration in config["calibration_configs"]:
                spec = make_spec(public["task_id"], public["seed"], validate_config(calibration), model=config["model_id"],
                    task_bundle=public["task_bundle"], resource_envelope=config["resource_envelope"], criterion={"direction": "min"},
                    hypothesis="Host-registered calibration; its configuration was not selected by an LLM.")
                spec["calibration"] = True
                if runs:
                    anchor = runs[0]
                    spec["criterion"] = {"direction": "min", "baseline_value": anchor["verification"]["metrics"]["validation_mse"], "improvement": 0.0}
                    spec["baseline"] = {"run_id": anchor["run_id"]}
                else:
                    spec["role"] = "baseline"
                engine.store.record_event("OBSERVE", {"objective": public["objective"], "calibration_selected_by": "registered_host"})
                engine.store.record_event("RETRIEVE", {"scope": "host calibration; no model receives this event"})
                engine.store.record_event("PROPOSE", {"calibration_config": calibration, "kind": "registered_method"})
                run = engine.progress(spec)
                if run.get("blocked") or not run["verification"].get("valid") or run["result"]["status"] != "success":
                    raise EvidenceError("Calibration failed independent verification; preserve it and revise a separate protocol")
                runs.append(run)
            receipt = {"unit_id": entry["unit_id"], "arm": arm, "model_calls": 0,
                "selection_kind": "preregistered_host_calibration", "records": [{"run_id": run["run_id"],
                    "config": run["spec"]["config"], "outcome": run["outcome"], "metrics": run["verification"]["metrics"],
                    "result_path": str(Path(run["run_dir"]) / "result.json"), "result_sha256": sha256_file(Path(run["run_dir"]) / "result.json")}
                    for run in runs], "calibration_cpu_invocations": len(runs)}
            write_once(directory / "calibration-receipt.json", receipt)
            results.append(receipt)
        on, off = [load(_directory(output, entry["unit_id"], arm) / "calibration-receipt.json") for arm in ("ON", "OFF")]
        fields = lambda receipt: [(record["run_id"], record["config"], record["outcome"], record["metrics"]) for record in receipt["records"]]
        if fields(on) != fields(off):
            raise EvidenceError("ON/OFF calibration conditions or independently measured results differ")
    check(output)
    return {"status": "calibration_verified", "records": results, "model_calls": 0, "adopted": False}


def request_payload(public, store, expose, allowed_run_ids=None):
    memory = [item for item in store.search(public["task_id"]) if item["usable_as_verified_evidence"]]
    if allowed_run_ids is not None:
        memory = [item for item in memory if item["run_id"] in allowed_run_ids]
    return {"goal": public["objective"], "public_task": public, "shared_tool_contract": TOOL_CONTRACT,
        "frozen_literature": frozen_literature(), "verified_memory": [
            {"run_id": item["run_id"], "config": item["config"], "outcome": item["outcome"], "metrics": item["metrics"],
             "verification_status": item["verification_status"], "conditions": item["conditions"],
             "original_evidence": {"result_path": str(Path(item["original_evidence"]["run_dir"]) / "result.json"),
                 "result_sha256": sha256_file(Path(item["original_evidence"]["run_dir"]) / "result.json"),
                 "evidence_hash": item["evidence_hash"]}, "failure_reason": item["failure_reason"]}
            for item in memory] if expose else [],
        "instructions": "Select exactly one next experiment. Return JSON {candidate:{hypothesis,config:{degree,alpha},selection_reason},stop:null}, or {candidate:null,stop:{kind:'no_justified_experiment',reason,evidence_run_ids:[]}}. Choose legal literal conditions; do not invent improvements. A stop rationale is a planning judgment, not an outcome measurement. Stored conditions may exist; the host applies the same content deduplication and independent verification. Do not use tools or inspect files. No current best, calibration count, hidden test answers or prior feedback is supplied outside the verified_memory field."}


def _action(answer, store):
    if isinstance(answer, str):
        answer = parse_object(answer)
    if not isinstance(answer, dict):
        raise ValueError("One next-action JSON object required")
    candidate, stop = answer.get("candidate"), answer.get("stop")
    if bool(candidate) == bool(stop):
        raise ValueError("Exactly one candidate or stop decision required")
    if candidate:
        if not isinstance(candidate.get("hypothesis"), str) or not candidate["hypothesis"].strip():
            raise ValueError("Candidate needs an explicit planning hypothesis")
        return {"kind": "candidate", "candidate": {**candidate, "config": validate_config(candidate["config"])}}
    if stop.get("kind") != "no_justified_experiment" or not isinstance(stop.get("reason"), str) or not stop["reason"].strip():
        raise ValueError("Stopping requires an explicit no-justified-experiment rationale")
    linked = stop.get("evidence_run_ids", [])
    if not isinstance(linked, list):
        raise ValueError("Stop evidence links must be a list")
    for run_id in linked:
        run = store.get_run(run_id)
        if run["status"] != "completed" or not run["verification"]["valid"]:
            raise ValueError("Stop reference is not original independently verified evidence")
    if not any(run["status"] == "completed" and run["verification"]["valid"] for run in store.list_runs()):
        raise ValueError("A valid stop needs prior verified host evidence")
    return {"kind": "stop", "stop": stop, "rationale_kind": "proposal"}


def _collect_one(registration, entry, arm, output, provider_factory):
    config, public = registration["config"], load(entry["public_path"])
    directory = _directory(output, entry["unit_id"], arm)
    if not (directory / "calibration-receipt.json").exists():
        raise EvidenceError("Run prepare before requesting the model")
    engine = _engine(directory)
    if not engine.store.verify_integrity()["valid"]:
        raise EvidenceError("Original calibration evidence changed")
    if any(item.get("blocked") for item in engine.resume()):
        raise EvidenceError("Prior proposed CPU execution is unknown; automatic repetition refused")
    decision_path = directory / "decision.json"
    if decision_path.exists():
        # Re-audit immutable model/CPU evidence below; never call provider again.
        return _score_one(registration, entry, arm, directory)
    requested = directory / "decision-request.json"
    if requested.exists():
        previous_request = load(requested)
        public_request = previous_request["payload"]
        if fingerprint(public_request) != previous_request["payload_sha256"] or previous_request["registration_sha256"] != fingerprint(registration):
            raise EvidenceError("Durable next-action request changed")
    else:
        public_request = request_payload(public, engine.store, arm == "ON")
        write_once(requested, {"payload": public_request, "payload_sha256": fingerprint(public_request),
            "registration_sha256": fingerprint(registration), "decision_opportunities": 1})
    model_dir = directory / "model" / "next-action"
    if model_dir.exists() and not (model_dir / "result.json").exists():
        raise EvidenceError("Model next-action execution has no durable result; automatic repetition refused")
    provider = provider_factory(evidence_dir=directory / "model", model=config["model_id"],
        reasoning_effort=config["resource_envelope"]["reasoning_effort"], public_dir=directory / "public_model_cwd")
    if getattr(provider, "execution_kind", None) != "real_model":
        raise ValueError("Only actual-model evidence can populate this diagnostic; fixtures are ineligible")
    # The provider caches prompt-identical completed evidence. A recorded failed
    # request remains failed; this one-opportunity diagnostic never replaces it.
    attempt_window = directory / "decision-window.json"
    if not attempt_window.exists():
        write_once(attempt_window, {"requested_at": utc_now(), "decision_opportunities": 1})
    answer = provider.complete(json.dumps(public_request, ensure_ascii=False, sort_keys=True), call_id="next-action", json_response=False)
    completed_window = directory / "decision-completion.json"
    if not completed_window.exists():
        write_once(completed_window, {"returned_at": utc_now(), "original_window_sha256": sha256_file(attempt_window)})
    model_audit = _audit_model_evidence([str(model_dir)], directory, config["model_id"], resource_envelope=config["resource_envelope"])
    _audit_request_inventory([str(model_dir)], [], directory)
    try:
        action = _action(answer, engine.store)
    except (ValueError, TypeError, KeyError, EvidenceError) as error:
        write_once(decision_path, {"status": "invalid_decision", "error": str(error), "decision_opportunities": 1,
            "model_result_sha256": sha256_file(model_dir / "result.json"), "raw_response_sha256": sha256_file(model_dir / "response.txt"),
            "provider_token_usage": model_audit["token_usage"], "model_seconds": model_audit["model_seconds"],
            "model_audit": model_audit, "provider_billed_cost": None})
        return load(decision_path)
    duplicate, failed_retry, selected = 0, None, None
    calibrations = load(directory / "calibration-receipt.json")["records"]
    failed_configs = {fingerprint(record["config"]) for record in calibrations if record["outcome"] == "failure"}
    if action["kind"] == "candidate":
        candidate = action["candidate"]
        anchor = engine.store.get_run(calibrations[0]["run_id"])
        spec = make_spec(public["task_id"], public["seed"], candidate["config"], model=config["model_id"],
            task_bundle=public["task_bundle"], resource_envelope=config["resource_envelope"], hypothesis=candidate["hypothesis"],
            criterion={"direction": "min", "baseline_value": anchor["verification"]["metrics"]["validation_mse"], "improvement": 0.0})
        spec["baseline"] = {"run_id": anchor["run_id"]}
        spec["selection_reason"] = candidate.get("selection_reason", "Model planning proposal; independent runner measures its result.")
        duplicate = int(engine.store.find_execution(spec) is not None)
        failed_retry = int(fingerprint(candidate["config"]) in failed_configs) if failed_configs else None
        action_receipt = directory / "action-registration.json"
        if action_receipt.exists():
            prior_action = load(action_receipt)
            if prior_action["action"] != action or prior_action["spec"] != spec:
                raise EvidenceError("Proposed registered action changed after interruption")
            duplicate, failed_retry = prior_action["duplicate_proposal"], prior_action["failed_calibration_reproposal"]
        else:
            write_once(action_receipt, {"action": action, "spec": spec, "duplicate_proposal": duplicate,
                "failed_calibration_reproposal": failed_retry, "cpu_execution_intent": "reuse original if duplicate; otherwise invoke once"})
        engine.store.record_event("OBSERVE", {"objective": public["objective"], "best_exposed": False})
        engine.store.record_event("RETRIEVE", {"exposed": arm == "ON", "run_ids": [record["run_id"] for record in calibrations] if arm == "ON" else []})
        engine.store.record_event("PROPOSE", {"action": action, "claim_kind": "proposal"})
        selected = engine.progress(spec)
        if selected.get("blocked") or not selected["verification"].get("valid"):
            raise EvidenceError("Proposed CPU result is unverified; original records remain")
    else:
        valid = [run for run in engine.store.list_runs() if run["verification"]["valid"] and run["result"]["status"] == "success"]
        selected = min(valid, key=lambda run: run["verification"]["metrics"]["validation_mse"])
        failed_retry = 0 if failed_configs else None
    decision = {"status": "verified_decision", "action": action, "decision_opportunities": 1,
        "duplicate_proposal": duplicate, "failed_calibration_reproposal": failed_retry,
        "selected_run_id": selected["run_id"], "selection_scope": "Candidate evidence, or host-selected best prior evidence for a valid stop; no LLM calibration selection claim.",
        "model_result_sha256": sha256_file(model_dir / "result.json"), "raw_response_sha256": sha256_file(model_dir / "response.txt")}
    write_once(decision_path, decision)
    return _score_one(registration, entry, arm, directory)


def _score_one(registration, entry, arm, directory):
    decision = load(directory / "decision.json")
    if decision["status"] != "verified_decision":
        config = registration["config"]
        model_dir = directory / "model" / "next-action"
        if decision.get("status") != "invalid_decision" or sha256_file(model_dir / "result.json") != decision["model_result_sha256"] or sha256_file(model_dir / "response.txt") != decision["raw_response_sha256"]:
            raise EvidenceError("Original invalid-decision evidence changed")
        audit = _audit_model_evidence([str(model_dir)], directory, config["model_id"], resource_envelope=config["resource_envelope"])
        _audit_request_inventory([str(model_dir)], [], directory)
        if decision.get("provider_token_usage") != audit["token_usage"] or decision.get("model_seconds") != audit["model_seconds"]:
            raise EvidenceError("Invalid-decision resource numbers differ from raw provider evidence")
        try:
            _action((model_dir / "response.txt").read_text(encoding="utf-8"), _engine(directory).store)
        except (ValueError, TypeError, KeyError, EvidenceError):
            pass
        else:
            raise EvidenceError("Recorded invalid status differs from the actual raw action")
        return decision
    public, owner, config = load(entry["public_path"]), load(entry["owner_path"]), registration["config"]
    model_dir = directory / "model" / "next-action"
    if sha256_file(model_dir / "result.json") != decision["model_result_sha256"] or sha256_file(model_dir / "response.txt") != decision["raw_response_sha256"]:
        raise EvidenceError("Original decision model evidence changed")
    store = _engine(directory).store
    if not store.verify_integrity()["valid"]:
        raise EvidenceError("Completed diagnostic CPU evidence changed")
    model_audit = _audit_model_evidence([str(model_dir)], directory, config["model_id"], resource_envelope=config["resource_envelope"])
    calibration = load(directory / "calibration-receipt.json")
    _audit_request_inventory([str(model_dir)], [], directory)
    for record in calibration["records"]:
        run = store.get_run(record["run_id"])
        if record["config"] != run["spec"]["config"] or record["outcome"] != run["outcome"] or record["metrics"] != run["verification"]["metrics"] or record["result_sha256"] != sha256_file(Path(run["run_dir"]) / "result.json"):
            raise EvidenceError("Host calibration receipt differs from original independently verified Store evidence")
    if [record["config"] for record in calibration["records"]] != [validate_config(c) for c in config["calibration_configs"]]:
        raise EvidenceError("Calibration differs from preregistered host-selected conditions")
    expected_request = request_payload(public, store, arm == "ON", {record["run_id"] for record in calibration["records"]})
    if load(directory / "decision-request.json")["payload"] != expected_request or load(model_dir / "request.json")["prompt"] != json.dumps(expected_request, ensure_ascii=False, sort_keys=True):
        raise EvidenceError("Actual model prompt differs from its fixed memory exposure treatment")
    expected_action = _action((model_dir / "response.txt").read_text(encoding="utf-8"), store)
    if decision["action"] != expected_action:
        raise EvidenceError("Decision does not match original raw model response")
    if expected_action["kind"] == "candidate":
        candidate_config = expected_action["candidate"]["config"]
        expected_duplicate = int(any(record["config"] == candidate_config for record in calibration["records"]))
        if store.get_run(decision["selected_run_id"])["spec"]["config"] != candidate_config:
            raise EvidenceError("Selected actual evidence does not match the proposed literal configuration")
    else:
        expected_duplicate = 0
        expected_best = min(calibration["records"], key=lambda record: record["metrics"]["validation_mse"])
        if decision["selected_run_id"] != expected_best["run_id"]:
            raise EvidenceError("Valid stop selection differs from the host's best verified prior evidence")
    failed_configs = [record["config"] for record in calibration["records"] if record["outcome"] == "failure"]
    expected_failed_retry = int(expected_action["kind"] == "candidate" and expected_action["candidate"]["config"] in failed_configs) if failed_configs else None
    if decision["duplicate_proposal"] != expected_duplicate or decision["failed_calibration_reproposal"] != expected_failed_retry:
        raise EvidenceError("Duplicate/failure-condition observations differ from raw action and preregistered calibration evidence")
    runs = store.list_runs()
    cpu_audit = _audit_cpu_executions([run["run_dir"] for run in runs], arm_output=directory, public=public,
        model_id=config["model_id"], resource_envelope=config["resource_envelope"])
    with store._connect() as db:
        execution_ids = [json.loads(row["payload"])["run_id"] for row in db.execute("SELECT payload FROM events WHERE phase='EXECUTE'")
                         if json.loads(row["payload"]).get("state") == "running"]
    if set(execution_ids) != {run["run_id"] for run in runs}:
        raise EvidenceError("Actual CPU invocation audit IDs differ from independently discovered run artifacts")
    duplicate_cpu_executions = len(execution_ids) - len(set(execution_ids))
    selected = store.get_run(decision["selected_run_id"])
    model_path = Path(selected["run_dir"]) / "model.json"
    score = {"status": "verified_decision", "unit_id": entry["unit_id"], "arm": arm, "decision_opportunities": 1,
        "duplicate_proposal": decision["duplicate_proposal"], "failed_calibration_reproposal": decision["failed_calibration_reproposal"],
        "valid_stop": int(decision["action"]["kind"] == "stop"),
        "fresh_legal_proposal": int(decision["action"]["kind"] == "candidate" and decision["duplicate_proposal"] == 0),
        "new_cpu_executions": len(execution_ids) - len(calibration["records"]), "duplicate_cpu_executions": duplicate_cpu_executions,
        "validation_mse": selected["verification"]["metrics"]["validation_mse"], "test_mse": _owner_metric(owner["test"], load(model_path)),
        "provider_token_usage": model_audit["token_usage"], "model_seconds": model_audit["model_seconds"],
        "calibration_cpu_seconds": math.fsum(store.get_run(record["run_id"])["result"]["execution_seconds"] for record in calibration["records"]),
        "total_cpu_seconds": cpu_audit["total_cpu_execution_seconds"], "provider_billed_cost": None,
        "evidence": {"decision_path": str(directory / "decision.json"), "decision_sha256": sha256_file(directory / "decision.json"),
            "selected_result_path": str(Path(selected["run_dir"]) / "result.json"), "selected_result_sha256": sha256_file(Path(selected["run_dir"]) / "result.json"),
            "selected_model_sha256": sha256_file(model_path), "owner_test_sha256": owner["test_sha256"],
            "model_audit": model_audit, "cpu_audit": cpu_audit, "actual_cpu_event_run_ids": execution_ids},
        "scope": "seeded next-action information exposure diagnostic, no framework improvement assertion"}
    write_once(directory / "owner-score.json", score)
    return score


def _external_failure(registration, entry, arm, output, error):
    directory = _directory(output, entry["unit_id"], arm)
    folder = directory / "model" / "next-action"
    score = {"status": "external_resource_pending", "reason": str(error), "decision_opportunities": 1,
        "unknown_tokens": True, "provider_token_usage": None, "provider_billed_cost": None,
        "model_seconds": None, "provider_attempts": None,
        "retry_policy": "Original raw request is retained; never replace a failed diagnostic opportunity with a new success."}
    if all((folder / name).exists() for name in ("request.json", "result.json", "events.jsonl", "stderr.log")):
        result, request = load(folder / "result.json"), load(folder / "request.json")
        events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if result.get("tool_calls") or any(event.get("item", {}).get("type") not in (None, "agent_message", "reasoning") for event in events):
            score["status"] = "disqualified_model_tool_use"
        elif result.get("status") == "failed" and sum(event.get("type") == "turn.failed" for event in events) == 1 and not any(event.get("type") == "turn.completed" for event in events):
            receipt = directory / "failed-model-no-action.json"
            write_once(receipt, {"provenance": "trusted_host_audit", "attempt_result_path": str(folder / "result.json"),
                "attempt_result_sha256": sha256_file(folder / "result.json"), "request_fingerprint": request["fingerprint"],
                "host_action_taken": False, "model_response_consumed": False,
                "retry_reason": "The diagnostic records this failed first request; it does not replace or retry the opportunity.",
                "sources": [{"path": str(folder / name), "sha256": sha256_file(folder / name)} for name in ("request.json", "result.json", "events.jsonl", "stderr.log")]})
            lineage = directory / "failed-model-lineage.json"
            write_once(lineage, {"kind": "explicit_model_attempt_resume_lineage", "provenance": "trusted_host_audit",
                "model_id": registration["config"]["model_id"], "retry_reason": "Immutable failed diagnostic opportunity accounting; no retry executed.",
                "attempts": [{"failed_dir": str(folder), "result_sha256": sha256_file(folder / "result.json"),
                    "request_fingerprint": request["fingerprint"], "host_action_receipt": str(receipt), "receipt_sha256": sha256_file(receipt)}]})
            audit = audit_failed_model_attempts([str(folder)], model_id=registration["config"]["model_id"],
                allowed_roots=[str(directory)], host_action_receipts={str(folder): str(receipt)}, lineage_path=str(lineage),
                resource_envelope=registration["config"]["resource_envelope"], arm_output=str(directory))
            score.update(provider_attempts=audit["failed_attempts"], model_seconds=audit["failed_seconds"],
                provider_token_usage=audit["failed_token_usage"], unknown_tokens=audit["unknown_failed_token_usage"], failed_model_audit=audit)
        score["original_model_result"] = {"path": str(folder / "result.json"), "sha256": sha256_file(folder / "result.json")}
    write_once(directory / "failed-decision-observation.json", score)
    return score


def collect(output, provider_factory=CodexProvider):
    registration = check(output)
    rows, deltas = [], []
    contingency = {"OFF_duplicate_ON_duplicate": 0, "OFF_duplicate_ON_not": 0,
                   "OFF_not_ON_duplicate": 0, "OFF_not_ON_not": 0}
    external_block = None
    for index, entry in enumerate(registration["units"]):
        row = {"unit_id": entry["unit_id"], "arms": {}}
        for arm in (("ON", "OFF") if index % 2 == 0 else ("OFF", "ON")):
            if external_block:
                row["arms"][arm] = {"status": "external_resource_pending", "reason": external_block}
                continue
            try:
                score = _collect_one(registration, entry, arm, output, provider_factory)
            except ModelUnavailable as error:
                external_block = str(error)
                score = _external_failure(registration, entry, arm, output, error)
            except (EvidenceError, ValueError, OSError) as error:
                score = {"status": "attention_required", "reason": str(error), "decision_opportunities": 1}
            row["arms"][arm] = score
        if all(row["arms"][arm]["status"] == "verified_decision" for arm in ("ON", "OFF")):
            deltas.append(row["arms"]["OFF"]["duplicate_proposal"] - row["arms"]["ON"]["duplicate_proposal"])
            off_dup, on_dup = row["arms"]["OFF"]["duplicate_proposal"], row["arms"]["ON"]["duplicate_proposal"]
            contingency[f"OFF_{'duplicate' if off_dup else 'not'}_ON_{'duplicate' if on_dup else 'not'}"] += 1
            on_request = load(_directory(output, entry["unit_id"], "ON") / "decision-request.json")["payload"]
            off_request = load(_directory(output, entry["unit_id"], "OFF") / "decision-request.json")["payload"]
            if {k: v for k, v in on_request.items() if k != "verified_memory"} != {k: v for k, v in off_request.items() if k != "verified_memory"}:
                raise EvidenceError("ON/OFF prompts differ outside the registered memory exposure")
        rows.append(row)
    check(output)
    summary = {"kind": "memory_exposure_development_pilot", "units": rows, "paired_duplicate_deltas": deltas,
        "registered_paired_decision_opportunities": len(registration["units"]), "complete_pairs": len(deltas),
        "paired_duplicate_2x2_counts": contingency, "primary_delta_units": "absolute proportion difference; multiply by 100 for percentage points",
        "all_pairs_complete": len(deltas) == len(registration["units"]), "adopted": False, "framework_goal_complete": False,
        "primary_denominator_policy": "Fixed registered decision opportunities; incomplete pairs remain and block inference.",
        "scope": "Host-selected actual calibration evidence exposure; no freehand or cross-task memory effect claim"}
    atomic_json(Path(output) / "ablation-summary.json", summary)
    return summary


def design(output, destination):
    registration = check(output)
    summary = load(Path(output) / "ablation-summary.json")
    if not summary["all_pairs_complete"] or len(summary["paired_duplicate_deltas"]) != len(registration["units"]):
        raise EvidenceError("All original actual paired diagnostic opportunities are needed; no failed/unknown pair replacement")
    recomputed_deltas = []
    for entry in registration["units"]:
        scores = {}
        for arm in ("ON", "OFF"):
            scores[arm] = _score_one(registration, entry, arm, _directory(output, entry["unit_id"], arm))
        recomputed_deltas.append(scores["OFF"]["duplicate_proposal"] - scores["ON"]["duplicate_proposal"])
    if recomputed_deltas != summary["paired_duplicate_deltas"]:
        raise EvidenceError("Pilot design inputs differ from independently re-audited actual paired decisions")
    result = {"kind": "memory_exposure_independent_design_input", "primary": registration["primary"],
        "design": design_sample_size(summary["paired_duplicate_deltas"], **registration["config"]["sample_design_inputs"]),
        "descriptive_pilot_uncertainty": paired_uncertainty(summary["paired_duplicate_deltas"]),
        "pilot_summary_path": str(Path(output).resolve() / "ablation-summary.json"),
        "pilot_summary_sha256": sha256_file(Path(output) / "ablation-summary.json"), "adopted": False,
        "next_action": "Independent owner must review assumptions and register a fresh confirmatory suite before actual evaluation."}
    write_once(destination, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("register", "prepare", "collect", "design"):
        command = sub.add_parser(action)
        command.add_argument("--output", type=Path, required=True)
        if action == "register":
            command.add_argument("--config", type=Path, required=True)
        if action == "design":
            command.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = register(load(args.config), args.output) if args.action == "register" else prepare(args.output) if args.action == "prepare" else collect(args.output) if args.action == "collect" else design(args.output, args.destination)
    except (EvidenceError, ValueError, OSError) as error:
        result = {"status": "attention_required", "reason": str(error), "goal_complete": False}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
