"""Read-only live-C evidence audit; writes only an independent sidecar snapshot."""
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import shutil
import sqlite3
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from evidence_research.evaluation import _audit_model_evidence
from evidence_research.store import Store, atomic_json, execution_fingerprint, fingerprint, sha256_file
from evidence_research.verifier import verify


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def audit():
    source = PROJECT / "runs/development/paired-pilot-v4/units/linear-seed7/C"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = Path(__file__).parent / stamp
    output.mkdir()
    connection = sqlite3.connect((source / "research/research.sqlite3").as_uri() + "?mode=ro", uri=True)
    destination = sqlite3.connect(output / "research-snapshot.sqlite3")
    connection.backup(destination)
    connection.close()
    destination.row_factory = sqlite3.Row
    events = [dict(row) for row in destination.execute("SELECT * FROM events ORDER BY sequence")]
    rows = [dict(row) for row in destination.execute("SELECT * FROM runs ORDER BY created_at,run_id")]
    memories = {row["run_id"]: dict(row) for row in destination.execute("SELECT * FROM memory")}
    meta = {row["key"]: json.loads(row["value"]) for row in destination.execute("SELECT * FROM metadata")}
    destination.close()
    runs = {}
    for row in rows:
        run = {**row, **{key: json.loads(row[key]) if row[key] else None for key in ("spec", "result", "verification", "manifest")}}
        run["run_dir"] = str(source / "research/evidence" / run["run_id"])
        runs[run["run_id"]] = run
    errors, checks, original_links = [], [], []
    previous = "0" * 64
    for event in events:
        event["payload"] = json.loads(event["payload"])
        expected = fingerprint({"timestamp": event["timestamp"], "phase": event["phase"], "payload": event["payload"], "previous_hash": previous})
        if event["previous_hash"] != previous or event["event_hash"] != expected:
            errors.append("Durable audit chain differs")
        previous = event["event_hash"]
    for run in runs.values():
        if run["status"] != "completed":
            continue
        folder = Path(run["run_dir"])
        fixed = verify(run["spec"], run["result"], folder)
        if not fixed["valid"] or fixed["metrics"] != run["verification"]["metrics"]:
            errors.append(f"Fixed independent verification failed: {run['run_id']}")
        if fingerprint(run["spec"]) != run["fingerprint"]:
            errors.append("Registered spec fingerprint differs")
        for name, expected in (("registration.json", run["spec"]), ("execution.json", {"run_id": run["run_id"], "spec_fingerprint": run["fingerprint"], "result": run["result"]}),
                               ("verification.json", run["verification"]), ("manifest.json", run["manifest"])):
            if load(folder / name) != expected:
                errors.append("Completed durable receipt content differs")
        for item in run["manifest"]:
            path = source / "research" / item["path"]
            if sha256_file(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
                errors.append("Completed artifact hash differs")
        evidence_hash = fingerprint({key: run[key] for key in ("spec", "result", "verification", "manifest")})
        if memories[run["run_id"]]["evidence_hash"] != evidence_hash:
            errors.append("Memory lacks original completed evidence")
        per_run = [event["phase"] for event in events if event["payload"].get("run_id") == run["run_id"]]
        required = ("REGISTER", "IMPLEMENT", "EXECUTE", "VERIFY", "DECIDE", "UPDATE_MEMORY")
        if any(phase not in per_run for phase in required) or [per_run.index(phase) for phase in required] != sorted(per_run.index(phase) for phase in required):
            errors.append("Durable run phase order differs")
        original_links.extend({"path": str(folder / name), "sha256": sha256_file(folder / name)} for name in ("registered_spec.json", "result.json", "execution.json", "verification.json", "manifest.json"))
        checks.append({"run_id": run["run_id"], "config": run["spec"]["config"], "outcome": run["outcome"],
            "metrics": fixed["metrics"], "fixed_independent_valid": fixed["valid"], "phases": per_run,
            "criterion": run["spec"]["criterion"], "command": run["spec"]["command"],
            "execution_entrypoint": run["spec"]["execution_entrypoint"], "source_sha256": run["spec"]["implementation_sha256"],
            "evaluator_sha256": run["spec"]["evaluator_sha256"], "evidence_hash": evidence_hash})
    prefix_links = []
    logs = {}
    for name in ("model-transport.jsonl", "candidate-decisions.jsonl"):
        raw = (source / name).read_bytes()
        prefix = raw[:raw.rfind(b"\n") + 1]
        (output / name).write_bytes(prefix)
        logs[name] = [json.loads(line) for line in prefix.decode("utf-8").splitlines()]
        prefix_links.append({"source_path": str(source / name), "snapshot_path": str(output / name), "snapshot_sha256": sha256_file(output / name),
            "source_prefix_bytes": len(prefix), "scope": "immutable captured prefix; the active original may append more records"})
    calls = {}
    for event in logs["model-transport.jsonl"]:
        calls[event["call_id"]] = event
    completed = [event for event in calls.values() if event["status"] == "completed"]
    registration = load(source / "callback-registration.json")
    usage = _audit_model_evidence([event["evidence_dir"] for event in completed], source, registration["model_id"], resource_envelope=registration["resource_envelope"])
    memory_exposure, costs, deferred = [], [], []
    for event in completed:
        folder = Path(event["evidence_dir"])
        request, result = load(folder / "request.json"), load(folder / "result.json")
        payload = json.loads(request["prompt"])
        verified_ids = []
        for record in payload["verified_memory"]:
            run = runs.get(record["run_id"])
            if run is None:
                deferred.append(record["run_id"])
                continue
            if record["metrics"] != run["verification"]["metrics"] or record["outcome"] != run["outcome"] or record["evidence_hash"] != memories[record["run_id"]]["evidence_hash"]:
                errors.append("Actual model memory exposure differs from original verification")
            verified_ids.append(record["run_id"])
        memory_exposure.append({"call_id": event["call_id"], "verified_run_ids_at_snapshot": verified_ids,
            "success_refs": [run_id for run_id in verified_ids if runs[run_id]["outcome"] == "success"],
            "failure_refs": [run_id for run_id in verified_ids if runs[run_id]["outcome"] == "failure"],
            "feedback_records": len(payload["proposal_feedback"]), "prior_actual_cpu_attempts_in_prompt": payload["actual_cpu_attempts_to_date"],
            "raw_request_path": str(folder / "request.json"), "raw_request_sha256": sha256_file(folder / "request.json")})
        condition_chars = sum(len(json.dumps(record["conditions"], ensure_ascii=False, sort_keys=True)) for record in payload["verified_memory"])
        costs.append({"call_id": event["call_id"], "prompt_chars": len(request["prompt"]), "full_prompt_chars": len(request["full_prompt"]),
            "repeated_condition_chars": condition_chars, "memory_records": len(payload["verified_memory"]),
            "provider_usage": result["usage"], "model_seconds": result["wall_seconds"],
            "result_path": str(folder / "result.json"), "result_sha256": sha256_file(folder / "result.json")})
        for name in ("request.json", "result.json", "events.jsonl", "stderr.log", "response.txt"):
            target = output / "model" / event["call_id"] / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(folder / name, target)
    execution_ids = [event["payload"]["run_id"] for event in events if event["phase"] == "EXECUTE" and event["payload"].get("state") == "running"]
    best_checks = []
    for best in meta.get("best", {}).values():
        selected = runs[best["run_id"]]
        group = [run for run in runs.values() if run["status"] == "completed" and run["verification"]["valid"] and Store._comparison_key(run["spec"]) == Store._comparison_key(selected["spec"])]
        minimum = min(run["verification"]["metrics"]["validation_mse"] for run in group)
        valid = best["value"] == minimum and best["value"] == selected["verification"]["metrics"]["validation_mse"] and Store._criterion_met(selected["spec"], selected["verification"])
        if not valid:
            errors.append("Current best is not a valid minimum among matched completed runs")
        best_checks.append({"metadata": best, "config": selected["spec"]["config"], "independent_minimum": minimum, "valid": valid,
            "scope": "Current durable best; final arm selection is separate and may still be pending"})
    atomic_json(output / "events.json", events)
    atomic_json(output / "runs.json", list(runs.values()))
    report = {"kind": "independent_read_only_live_C_prefix_audit", "captured_at_utc": stamp,
        "source": str(source), "audit_source_sha256": sha256_file(Path(__file__)), "source_read_mode": "SQLite mode=ro online backup; no source writes, provider calls, interrupts or re-execution",
        "checks_valid_for_captured_prefix": not errors, "errors": errors, "completed_cpu_runs": len(checks),
        "actual_cpu_start_receipts": len(execution_ids), "duplicate_actual_cpu_starts": len(execution_ids) - len(set(execution_ids)),
        "full_loop_observe_retrieve_present": all(phase in [event["phase"] for event in events] for phase in ("OBSERVE", "RETRIEVE", "PROPOSE")),
        "runs": checks, "best": best_checks, "completed_actual_model_requests": len(completed),
        "pending_model_requests": [event["call_id"] for event in calls.values() if event["status"] == "requested"],
        "actual_memory_exposure": memory_exposure, "context_cost_observations": costs,
        "actual_model_resource_audit": usage, "deferred_cross_snapshot_refs": sorted(set(deferred)),
        "candidate_decision_records": len(logs["candidate-decisions.jsonl"]),
        "duplicate_feedback_status": "Feedback field exists in actual prompts; no duplicate or rejected response in captured candidate prefix." if not any(item["rejected"] or any(c["selection"]["duplicate"] for c in item["ranked"]) for item in logs["candidate-decisions.jsonl"]) else "Duplicate/rejected candidate feedback is present; see captured decision prefix.",
        "final_response_present": (source / "arm-response.json").exists(), "independent_whole_report_review_complete": False,
        "goal_complete": False, "framework_improvement_demonstrated": False, "memory_causal_effect_demonstrated": False,
        "links": original_links + prefix_links + [{"path": str(output / name), "sha256": sha256_file(output / name)} for name in ("research-snapshot.sqlite3", "events.json", "runs.json")],
        "limitations": ["A live prefix is an observation, not final arm acceptance or a matched B/C effect.",
            "Snapshots of append-only JSON and SQLite may have slightly different capture times; later references are deferred.",
            "Successful and failed evidence reached actual prompts, but causal memory benefit requires the separate preregistered ablation.",
            "Chars are measured serialization length, not model token attribution; actual input/output token totals come from raw provider records."]}
    atomic_json(output / "audit.json", report)
    print(json.dumps({"path": str(output / "audit.json"), "valid": not errors, "completed_cpu_runs": len(checks), "completed_model_calls": len(completed), "pending": report["pending_model_requests"], "best": best_checks}, ensure_ascii=False))


if __name__ == "__main__":
    audit()
