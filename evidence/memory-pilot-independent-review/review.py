"""Read-only independent replay of a completed memory-exposure development pilot.

No providers, fitting runners, Store mutations, or registration edits are invoked.
The owner test rows are used only for local arithmetic and are never exported.
"""
from pathlib import Path
import argparse
import copy
import datetime
import hashlib
import json
import math
import sqlite3
import shutil
import statistics
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from evidence_research.evaluation import _audit_model_evidence, _audit_cpu_executions, _audit_request_inventory
from evidence_research.model import digest, parse_object
from evidence_research.store import fingerprint, execution_fingerprint
from evidence_research.verifier import verify


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_hashes(root):
    return {str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()}


def linked(path):
    return {"path": str(Path(path).resolve()), "sha256": sha(path)}


def ledger(directory):
    db_path = directory / "research" / "research.sqlite3"
    # Preserve DB+WAL+SHM bytes in a separate reviewer workspace. SQLite may
    # maintain its shared-memory index while reading WAL; only copies receive it.
    snapshot = Path(__file__).parent / "ledger-snapshots" / directory.parent.name / directory.name
    snapshot.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        source = Path(str(db_path) + suffix)
        if source.exists():
            shutil.copy2(source, snapshot / source.name)
    copied_db = snapshot / db_path.name
    db = sqlite3.connect(copied_db.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    runs = {r["run_id"]: dict(r) for r in db.execute("SELECT * FROM runs")}
    memories = {r["run_id"]: dict(r) for r in db.execute("SELECT * FROM memory")}
    events = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY sequence")]
    indexes = [dict(r) for r in db.execute("SELECT * FROM execution_index")]
    db.close()
    previous = "0" * 64
    for event in events:
        payload = json.loads(event["payload"])
        assert event["previous_hash"] == previous
        assert event["event_hash"] == fingerprint({"timestamp": event["timestamp"], "phase": event["phase"],
                                                 "payload": payload, "previous_hash": previous})
        previous = event["event_hash"]
        event["payload"] = payload
        for key, name in (("registration_sha256", "registration.json"), ("execution_sha256", "execution.json"),
                          ("verification_sha256", "verification.json"), ("manifest_sha256", "manifest.json")):
            if key in payload and payload.get("run_id"):
                assert sha(directory / "research/evidence" / payload["run_id"] / name) == payload[key]
    for run_id, run in runs.items():
        for field in ("spec", "result", "verification", "manifest"):
            run[field] = json.loads(run[field]) if run[field] is not None else None
        folder = directory / "research/evidence" / run_id
        run["run_dir"] = str(folder.resolve())
        assert run["status"] == "completed" and fingerprint(run["spec"]) == run["fingerprint"]
        assert load(folder / "registration.json") == run["spec"]
        assert load(folder / "registered_spec.json") == run["spec"]
        assert load(folder / "result.json") == run["result"]
        assert load(folder / "verification.json") == run["verification"]
        assert load(folder / "manifest.json") == run["manifest"]
        assert load(folder / "execution.json") == {"run_id": run_id, "spec_fingerprint": run["fingerprint"], "result": run["result"]}
        fresh = verify(run["spec"], run["result"], folder.resolve())
        assert fresh["valid"] and fresh["metrics"] == run["verification"]["metrics"]
        criterion = run["spec"]["criterion"]
        value = fresh["metrics"][run["spec"]["metric"]]
        assert criterion["direction"] == "min"
        if "baseline_value" in criterion:
            expected_outcome = "success" if criterion["baseline_value"] - value > criterion.get("improvement", 0) else "failure"
        else:
            assert run["spec"].get("role") == "baseline"
            expected_outcome = "success"
        assert run["outcome"] == expected_outcome
        for artifact in run["manifest"]:
            path = (directory / "research" / artifact["path"]).resolve()
            assert path.is_relative_to(folder.resolve())
            assert sha(path) == artifact["sha256"] and path.stat().st_size == artifact["bytes"]
        evidence_hash = fingerprint({"spec": run["spec"], "result": run["result"],
                                     "verification": run["verification"], "manifest": run["manifest"]})
        assert memories[run_id]["evidence_hash"] == evidence_hash
        assert memories[run_id]["outcome"] == run["outcome"]
        assert memories[run_id]["verification_status"] == "verified"
    for index in indexes:
        assert execution_fingerprint(runs[index["run_id"]]["spec"]) == index["execution_fingerprint"]
    execution_ids = [event["payload"]["run_id"] for event in events
                     if event["phase"] == "EXECUTE" and event["payload"].get("state") == "running"]
    assert set(execution_ids) == set(runs) and len(execution_ids) == len(set(execution_ids))
    return runs, memories, events, execution_ids


def metric_from_owner_rows(owner, model):
    # Independently written arithmetic; no host fitting or model-selected labels.
    errors = []
    for row in owner["test"]:
        predicted = math.fsum(coefficient * row["x"] ** degree
                              for degree, coefficient in enumerate(model["weights"]))
        errors.append((predicted - row["y"]) ** 2)
    return math.fsum(errors) / len(errors)


def review(pilot):
    pilot = pilot.resolve()
    before = tree_hashes(pilot)
    registration_path = pilot / "ablation-registration.json"
    registration = load(registration_path)
    assert sha(registration_path) == load(pilot / "registration-anchor.json")["registration_sha256"]
    assert fingerprint(registration["config"]) == registration["config_sha256"]
    config, env = registration["config"], registration["config"]["resource_envelope"]
    source_checks = []
    for source, expected in registration["sources"].items():
        source = Path(source)
        snapshot = pilot / "source-snapshot" / ("scripts" if source.name == "memory_ablation.py" else "evidence_research") / source.name
        assert sha(source) == expected == sha(snapshot)
        source_checks.append({**linked(source), "snapshot": str(snapshot)})
    pairs, arm_records = [], []
    for unit_index, entry in enumerate(registration["units"]):
        public, owner = load(entry["public_path"]), load(entry["owner_path"])
        assert sha(entry["public_path"]) == entry["public_sha256"] and sha(entry["owner_path"]) == entry["owner_sha256"]
        assert "test" not in public["task_bundle"]
        assert all(":train:" in r["id"] for r in public["task_bundle"]["train"])
        assert all(":validation:" in r["id"] for r in public["task_bundle"]["validation"])
        assert fingerprint(owner["test"]) == owner["test_sha256"]
        arm_payloads, calibrations, arm_stats, raw_guards = {}, {}, {}, {}
        for arm in ("ON", "OFF"):
            directory = pilot / "units" / entry["unit_id"] / arm
            decision_request = load(directory / "decision-request.json")
            payload = decision_request["payload"]
            assert fingerprint(payload) == decision_request["payload_sha256"]
            assert decision_request["registration_sha256"] == fingerprint(registration)
            assert payload["public_task"] == public
            assert "test_mse" not in json.dumps(payload)
            raw_folder = directory / "model/next-action"
            model_audit = _audit_model_evidence([str(raw_folder)], directory, config["model_id"], resource_envelope=env)
            _audit_request_inventory([str(raw_folder)], [], directory)
            request, result = load(raw_folder / "request.json"), load(raw_folder / "result.json")
            assert request["prompt"] == json.dumps(payload, ensure_ascii=False, sort_keys=True)
            assert request["full_prompt"].endswith(request["prompt"])
            raw_guards[arm] = request["full_prompt"][:-len(request["prompt"])]
            assert request["reasoning_effort"] == env["reasoning_effort"] == "medium"
            assert request["provider_source_sha256"] == registration["sources"][str(PROJECT / "evidence_research/model.py")]
            raw_answer = parse_object((raw_folder / "response.txt").read_text(encoding="utf-8"))
            decision, score = load(directory / "decision.json"), load(directory / "owner-score.json")
            assert decision["status"] == score["status"] == "verified_decision"
            assert decision["model_result_sha256"] == sha(raw_folder / "result.json")
            assert decision["raw_response_sha256"] == sha(raw_folder / "response.txt")
            runs, memories, events, execution_ids = ledger(directory)
            calibration = load(directory / "calibration-receipt.json")
            assert calibration["selection_kind"] == "preregistered_host_calibration" and calibration["model_calls"] == 0
            assert [r["config"] for r in calibration["records"]] == config["calibration_configs"]
            for record in calibration["records"]:
                run = runs[record["run_id"]]
                assert record["config"] == run["spec"]["config"] and run["spec"]["calibration"] is True
                assert record["outcome"] == run["outcome"] and record["metrics"] == run["verification"]["metrics"]
                assert record["result_sha256"] == sha(record["result_path"])
            assert (len(payload["verified_memory"]) == len(calibration["records"])) if arm == "ON" else payload["verified_memory"] == []
            for memory in payload["verified_memory"]:
                run = runs[memory["run_id"]]
                assert memory["run_id"] in {r["run_id"] for r in calibration["records"]}
                assert memory["config"] == run["spec"]["config"] and memory["outcome"] == run["outcome"]
                assert memory["metrics"] == run["verification"]["metrics"] and memory["verification_status"] == "verified"
                assert memory["conditions"] == json.loads(memories[memory["run_id"]]["applicability"])
                assert memory["original_evidence"]["evidence_hash"] == memories[memory["run_id"]]["evidence_hash"]
                assert memory["original_evidence"]["result_sha256"] == sha(memory["original_evidence"]["result_path"])
                assert memory["failure_reason"] == ("Registered success criterion was not met." if run["outcome"] == "failure" else None)
            cpu_audit = _audit_cpu_executions([run["run_dir"] for run in runs.values()], arm_output=directory,
                                            public=public, model_id=config["model_id"], resource_envelope=env)
            action = decision["action"]
            if action["kind"] == "candidate":
                assert raw_answer["candidate"] == action["candidate"] and raw_answer.get("stop") is None
                assert runs[decision["selected_run_id"]]["spec"]["config"] == action["candidate"]["config"]
                assert load(directory / "action-registration.json")["action"] == action
                duplicate = int(any(r["config"] == action["candidate"]["config"] for r in calibration["records"]))
            else:
                assert raw_answer["stop"] == action["stop"] and raw_answer.get("candidate") is None
                duplicate = 0
                best = min(calibration["records"], key=lambda r: r["metrics"]["validation_mse"])
                assert decision["selected_run_id"] == best["run_id"]
            assert score["duplicate_proposal"] == decision["duplicate_proposal"] == duplicate
            failed_configs = [r["config"] for r in calibration["records"] if r["outcome"] == "failure"]
            expected_failed_reproposal = int(action["kind"] == "candidate" and action["candidate"]["config"] in failed_configs) if failed_configs else None
            assert score["failed_calibration_reproposal"] == decision["failed_calibration_reproposal"] == expected_failed_reproposal
            selected = runs[decision["selected_run_id"]]
            model_path = Path(selected["run_dir"]) / "model.json"
            test_value = metric_from_owner_rows(owner, load(model_path))
            assert math.isclose(score["test_mse"], test_value, abs_tol=1e-12, rel_tol=1e-12)
            assert score["validation_mse"] == selected["verification"]["metrics"]["validation_mse"]
            assert score["model_seconds"] == model_audit["model_seconds"] and score["provider_token_usage"] == model_audit["token_usage"]
            assert score["new_cpu_executions"] == len(execution_ids) - len(calibration["records"])
            assert score["total_cpu_seconds"] == cpu_audit["total_cpu_execution_seconds"]
            assert score["duplicate_cpu_executions"] == 0
            window = load(directory / "decision-window.json")
            completed = load(directory / "decision-completion.json")
            assert completed["original_window_sha256"] == sha(directory / "decision-window.json")
            assert registration["registered_at"] <= window["requested_at"] <= completed["returned_at"]
            stats = {"unit_id": entry["unit_id"], "arm": arm, "action": action["kind"],
                     "selected_config": load(model_path)["config"], "duplicate_proposal": duplicate,
                     "failed_calibration_reproposal": score["failed_calibration_reproposal"],
                     "new_cpu_executions": score["new_cpu_executions"], "total_cpu_executions": len(runs),
                     "calibration_failures": sum(r["outcome"] == "failure" for r in calibration["records"]),
                     "stored_criterion_failures": sum(r["outcome"] == "failure" for r in runs.values()),
                     "validation_mse": score["validation_mse"], "test_mse": test_value,
                     "tokens": model_audit["token_usage"], "model_seconds": model_audit["model_seconds"],
                     "cpu_seconds": cpu_audit["total_cpu_execution_seconds"], "model_audit": model_audit,
                     "cpu_audit": cpu_audit, "evidence": [linked(directory / name) for name in
                     ("decision-request.json", "calibration-receipt.json", "decision.json", "owner-score.json")],
                     "read_only_ledger_sha256": sha(directory / "research/research.sqlite3")}
            arm_records.append(stats)
            arm_stats[arm], calibrations[arm] = stats, calibration["records"]
            arm_payloads[arm] = {k: v for k, v in payload.items() if k != "verified_memory"}
        assert arm_payloads["ON"] == arm_payloads["OFF"]
        assert raw_guards["ON"] == raw_guards["OFF"]
        comparable = lambda rows: [{k: r[k] for k in ("run_id", "config", "outcome", "metrics")} for r in rows]
        assert comparable(calibrations["ON"]) == comparable(calibrations["OFF"])
        pairs.append({"unit_id": entry["unit_id"], "payload_equal_outside_verified_memory": True,
                      "raw_full_prompt_guard_equal": True,
                      "calibration_conditions_results_equal": True,
                      "duplicate_delta_OFF_minus_ON": arm_stats["OFF"]["duplicate_proposal"] - arm_stats["ON"]["duplicate_proposal"],
                      "exploratory_ON_minus_OFF": {name: arm_stats["ON"][name] - arm_stats["OFF"][name]
                       for name in ("test_mse", "validation_mse", "model_seconds", "cpu_seconds")},
                      "input_tokens_ON_minus_OFF": arm_stats["ON"]["tokens"]["input_tokens"] - arm_stats["OFF"]["tokens"]["input_tokens"]})
    summary = load(pilot / "ablation-summary.json")
    assert summary["paired_duplicate_deltas"] == [p["duplicate_delta_OFF_minus_ON"] for p in pairs]
    assert summary["all_pairs_complete"] and summary["complete_pairs"] == len(pairs)
    totals = {}
    for arm in ("ON", "OFF"):
        rows = [r for r in arm_records if r["arm"] == arm]
        totals[arm] = {"requests": len(rows), "input_tokens": sum(r["tokens"]["input_tokens"] for r in rows),
                       "output_tokens": sum(r["tokens"]["output_tokens"] for r in rows),
                       "cached_input_tokens": sum(r["tokens"].get("cached_input_tokens", 0) for r in rows),
                       "model_seconds": math.fsum(r["model_seconds"] for r in rows),
                       "actual_cpu_executions": sum(r["total_cpu_executions"] for r in rows),
                       "new_model_proposed_cpu_executions": sum(r["new_cpu_executions"] for r in rows),
                       "cpu_seconds": math.fsum(r["cpu_seconds"] for r in rows),
                       "calibration_criterion_failures": sum(r["calibration_failures"] for r in rows),
                       "all_stored_criterion_failures": sum(r["stored_criterion_failures"] for r in rows),
                       "monetary_cost": None}
    n = len(pairs)
    assert all(p["duplicate_delta_OFF_minus_ON"] == 0 for p in pairs)
    zero_information = {"n_pairs": n, "observed_discordant_pairs": 0,
                        "one_sided_95_zero_event_upper": 1 - 0.05 ** (1 / n),
                        "two_sided_95_zero_event_upper": 1 - 0.025 ** (1 / n),
                        "meaningful_effect": registration["config"]["sample_design_inputs"]["meaningful_gain"],
                        "minimum_sd_for_discrete_delta_mean_point1": math.sqrt(0.1 - 0.1**2),
                        "probability_no_events_at_point1_discordance": 0.9**n,
                        "qualification": "Exact binomial calculations assume independent identically distributed paired opportunities; task strata/model sampling may violate this. Zero discordance bounds its population probability, not a complete paired-effect confidence interval."}
    secondary = {
        "interpretation": "Exploratory only; no inferential test or framework/memory adoption claim.",
        "total_input_tokens_ON_minus_OFF": totals["ON"]["input_tokens"] - totals["OFF"]["input_tokens"],
        "total_output_tokens_ON_minus_OFF": totals["ON"]["output_tokens"] - totals["OFF"]["output_tokens"],
        "total_model_seconds_ON_minus_OFF": totals["ON"]["model_seconds"] - totals["OFF"]["model_seconds"],
        "pairs_with_higher_input_ON": sum(p["input_tokens_ON_minus_OFF"] > 0 for p in pairs),
        "mean_paired_test_mse_ON_minus_OFF": statistics.mean(p["exploratory_ON_minus_OFF"]["test_mse"] for p in pairs),
        "mean_paired_validation_mse_ON_minus_OFF": statistics.mean(p["exploratory_ON_minus_OFF"]["validation_mse"] for p in pairs),
        "pairs_with_different_test_mse": sum(p["exploratory_ON_minus_OFF"]["test_mse"] != 0 for p in pairs),
        "total_new_cpu_executions_ON_minus_OFF": totals["ON"]["new_model_proposed_cpu_executions"] - totals["OFF"]["new_model_proposed_cpu_executions"],
    }
    assert before == tree_hashes(pilot), "Original pilot artifacts changed during independent read-only review"
    return {"kind": "independent_memory_exposure_development_review", "reviewed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "valid_original_evidence": True, "original_artifacts_unchanged": True, "new_model_calls": 0,
            "new_fitting_executions": 0, "primary_effect_observed": False, "confirmation_design_approved": False,
            "source_checks": source_checks, "pairs": pairs, "arm_records": arm_records,
            "exploratory_totals": totals, "exploratory_paired_summaries": secondary,
            "zero_information_statistical_calculations": zero_information,
            "source_links": [linked(pilot / name) for name in ("ablation-registration.json", "registration-anchor.json", "ablation-summary.json", "design-input.json")],
            "statistical_reference": {"title": "NIST: Exact Intervals for Small Numbers of Failures and/or Small Sample Sizes", "url": "https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm"},
            "scope": "All quantities are development-only diagnostics. Owner test rows were used only in local independent arithmetic and were not exported or sent to a provider. Descriptive secondary metrics do not override the unobserved registered primary effect."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=Path, default=PROJECT / "runs/development/memory-exposure-pilot-v1")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("independent-review.json"))
    args = parser.parse_args()
    reviewed = review(args.pilot)
    reviewed["reviewer_source"] = linked(__file__)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reviewed, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "pairs": len(reviewed["pairs"]),
                      "valid_original_evidence": True, "primary_effect_observed": False,
                      "confirmation_design_approved": False, "totals": reviewed["exploratory_totals"]}))
