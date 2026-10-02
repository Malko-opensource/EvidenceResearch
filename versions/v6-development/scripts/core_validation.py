"""Actual CPU component validation, explicitly excluding an LLM B/C comparison.

Run: python scripts/core_validation.py --output evidence/core-validation
An existing output is checked and returned, never re-executed or overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evidence_research import Engine, EvidenceError, Store, fingerprint, sha256_file
from evidence_research.store import atomic_json
from evidence_research.tasks import make_spec, run_task
from evidence_research.verifier import verify


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def validate(output: Path) -> dict:
    output = output.resolve()
    report_path = output / "report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for relative in report["stores"]:
            check = Store(output / relative).verify_integrity()
            require(check["valid"], f"Recorded validation evidence changed: {check['errors']}")
        # The intentional tamper copy is never counted as usable evidence.
        require(not Store(output / "tampered-copy").verify_integrity()["valid"], "Tamper control unexpectedly passes")
        return {**report, "reused_without_execution": True}
    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), "Incomplete output exists; reconcile it or choose a new output path.")
    project = Path(__file__).resolve().parents[1]
    source_files = [project / "evidence_research" / name for name in
                    ("__init__.py", "store.py", "engine.py", "selection.py", "tasks.py", "verifier.py")]
    source_files.append(Path(__file__).resolve())
    snapshot_hashes = {}
    for source in source_files:
        relative = source.relative_to(project)
        target = output / "source-snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        snapshot_hashes[relative.as_posix()] = sha256_file(target)
    calls = []
    def counted_runner(spec, run_dir):
        calls.append({"spec_fingerprint": fingerprint(spec), "run_dir": str(run_dir),
                      "task_id": spec["task_id"], "config": spec["config"]})
        atomic_json(output / "runner-invocations.json", calls)
        return run_task(spec, run_dir)

    study = Store(output / "study")
    study.init_goal({"objective": "Validate actual CPU evidence, failed/successful research memory and reuse",
        "task_id": "dev-quadratic", "memory_query": "dev-quadratic",
        "research_criterion": {"task_id": "dev-quadratic", "metric": "validation_mse",
                               "direction": "min", "threshold": 0.15}})
    engine = Engine(output / "study", counted_runner, verify)
    shared = {"model": "actual-cpu-component-validation; no LLM",
              "criterion": {"direction": "min", "threshold": 0.15}}
    failed = engine.step(make_spec("dev-quadratic", 7, {"degree": 1, "alpha": 0},
                                  hypothesis="A linear model explains the quadratic development task.", **shared))
    require(failed["verification"]["valid"] and failed["outcome"] == "failure", "Expected measured hypothesis failure missing")
    invalid = make_spec("dev-quadratic", 7, {"degree": 1, "alpha": 0},
                        hypothesis="Invalid configuration failure control", **shared)
    invalid["config"] = {"degree": 0, "alpha": 0.0}
    error = engine.step(invalid)
    require(error["result"]["status"] == "failure" and error["verification"]["valid"], "Invalid config failure was not independently reproduced")
    recovered_spec = make_spec("dev-quadratic", 7, {"degree": 2, "alpha": 0.1},
                               hypothesis="Restore a valid polynomial degree after invalid configuration.", **shared)
    recovered_spec.update(retry_of=error["run_id"], retry_reason="Degree 0 violates the registered allowlist; degree 2 is valid and fits nonlinear structure.")
    recovered = engine.step(recovered_spec)
    require(recovered["verification"]["valid"] and recovered["outcome"] == "success", "Changed-condition error recovery failed")
    retrieved = study.search("dev-quadratic")
    require(any(item["outcome"] == "failure" for item in retrieved), "Failure memory missing")
    require(any(item["outcome"] == "success" for item in retrieved), "Success memory missing")
    require(all(item["usable_as_verified_evidence"] for item in retrieved), "Retrieved records not linked to verified evidence")
    reused_configs = []
    def memory_guided_proposer(context):
        retrieved_memory = context["memory"]
        for item in retrieved_memory:
            require(item["original_evidence"]["verification"]["valid"], "Proposer must inspect original verification")
            reused_configs.append(item["run_id"])
        # The failure is renamed to prove the deduplication guard uses conditions.
        duplicate = make_spec("dev-quadratic", 7, {"degree": 1, "alpha": 0},
                              hypothesis="Renamed linear approach", **shared)
        successful_config = next(item["config"] for item in retrieved_memory if item["outcome"] == "success")
        next_spec = make_spec("dev-quadratic", 7,
                              {"degree": successful_config["degree"], "alpha": 0.0},
                              hypothesis="Use verified nonlinear features and test less regularization.", **shared)
        next_spec["memory_references"] = sorted(reused_configs)
        next_spec["selection_reason"] = "A verified degree 1 failure and degree 2 success motivate an independent degree 2 alpha 0 comparison."
        next_spec["baseline"] = {"run_id": recovered["run_id"]}
        return [{"spec": duplicate, "assessment": {"relevance": 1.0}},
                {"spec": next_spec, "assessment": {"relevance": 1.0, "evidence_strength": 1.0,
                    "uncertainty": 0.5, "normalized_cost": 0.0,
                    "rationale": next_spec["selection_reason"]}}]
    engine.proposer = memory_guided_proposer
    selected = engine.step()
    require(selected["spec"]["config"] == {"degree": 2, "alpha": 0.0}, "Known failed duplicate was selected")
    require(selected["verification"]["valid"] and selected["outcome"] == "success", "Memory-guided next experiment failed verification")
    best_runs = {entry["run_id"] for entry in study.state()["best"].values()}
    require(recovered["run_id"] in best_runs and selected["run_id"] not in best_runs,
            "A worse verified measurement incorrectly replaced the best result")
    before_resume = len(calls)
    duplicate = engine.step(selected["spec"])
    require(duplicate["resumed_without_execution"], "Completed run was not reused")
    require(engine.resume() == [] and len(calls) == before_resume, "Completed execution repeated during resume")

    # Crash after an fsynced receipt, before its database commit: real runner output,
    # controlled interruption at the orchestration boundary, then verifier-only resume.
    recovery = Store(output / "recovery")
    recovery.init_goal({"objective": "Validate interrupted actual CPU run with durable receipt"})
    interrupted_engine = Engine(output / "recovery", counted_runner, verify)
    recovery_spec = make_spec("dev-linear", 17, {"degree": 1, "alpha": 0}, **shared)
    original_record = interrupted_engine.store.record_execution
    def stop_after_receipt(run_id, result):
        run = interrupted_engine.store.get_run(run_id)
        atomic_json(Path(run["run_dir"]) / "execution.json", {
            "run_id": run_id, "spec_fingerprint": run["fingerprint"], "result": result})
        raise KeyboardInterrupt("controlled interruption after durable execution receipt")
    interrupted_engine.store.record_execution = stop_after_receipt
    try:
        interrupted_engine.step(recovery_spec)
    except KeyboardInterrupt:
        pass
    else:
        raise EvidenceError("Interruption control did not fire")
    interrupted_engine.store.record_execution = original_record
    receipt_calls = len(calls)
    resumed = Engine(output / "recovery", counted_runner, verify).resume()
    require(len(resumed) == 1 and resumed[0]["verification"]["valid"], "Durable receipt was not independently verified on resume")
    require(len(calls) == receipt_calls, "Recovery repeated the actual runner")

    unknown = Store(output / "unknown")
    unknown.init_goal({"objective": "Refuse automatic repeat without a durable receipt"})
    unknown_run = unknown.register(make_spec("dev-linear", 19, {"degree": 1, "alpha": 0}, **shared))
    unknown.mark_running(unknown_run["run_id"])
    unknown_calls = len(calls)
    refused = Engine(output / "unknown", counted_runner, verify).resume()
    require(refused[0].get("blocked") == "unknown_execution" and len(calls) == unknown_calls,
            "Unknown execution was silently repeated")

    # Evidence tampering is tested on a copy; the original study remains intact.
    tampered = output / "tampered-copy"
    shutil.copytree(output / "study", tampered)
    victim = Store(tampered).get_run(selected["run_id"])
    artifact = tampered / victim["manifest"][0]["path"]
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    tamper_check = Store(tampered).verify_integrity()
    require(not tamper_check["valid"], "Tampered completed evidence accepted")
    refused_by_engine = False
    try:
        Engine(tampered, counted_runner, verify).step(selected["spec"])
    except EvidenceError:
        refused_by_engine = True
    require(refused_by_engine, "Engine did not fail closed on tampered evidence")
    stores = ["study", "recovery", "unknown"]
    integrity = {name: Store(output / name).verify_integrity() for name in stores}
    require(all(check["valid"] for check in integrity.values()), "Original evidence failed integrity")
    counts = Counter(item["spec_fingerprint"] for item in calls)
    require(max(counts.values()) == 1, "Any actual CPU execution repeated")
    require(all(sha256_file(project / relative) == digest for relative, digest in snapshot_hashes.items()),
            "Source changed during component evaluation; evidence retained but report cannot be finalized.")
    report = {
        "scope": "component validation using actual deterministic CPU task execution",
        "llm_calls": 0, "framework_B_C_improvement_claim": False,
        "limitations": ["Development tasks only, not final holdout research performance.",
            "Controlled interruption validates orchestration recovery, not a host power-loss test.",
            "Trusted allowlisted configurations; no same-user arbitrary-code OS sandbox."],
        "stores": stores, "source_hashes": snapshot_hashes,
        "source_snapshot": str(output / "source-snapshot"),
        "checks": {"full_loop_actual_cpu": True, "success_failure_search": True,
            "memory_guided_selection": True, "changed_condition_error_recovery": True,
            "worse_verified_result_does_not_replace_best": True,
            "completed_resume_no_duplicate": True, "durable_receipt_resume_no_duplicate": True,
            "unknown_execution_no_repeat": True, "completed_tamper_fail_closed": True},
        "observed": {"actual_runner_invocations": len(calls), "duplicate_invocations": 0,
            "failed_linear": {"run_id": failed["run_id"], "validation_mse": failed["verification"]["metrics"]["validation_mse"]},
            "changed_condition_recovery": {"run_id": recovered["run_id"], "validation_mse": recovered["verification"]["metrics"]["validation_mse"]},
            "memory_guided": {"run_id": selected["run_id"], "validation_mse": selected["verification"]["metrics"]["validation_mse"]},
            "independently_verified_execution_failure": error["run_id"],
            "retrieved_evidence_run_ids": sorted(set(reused_configs)),
            "best_run_id": recovered["run_id"],
            "interrupted_resumed_run_id": resumed[0]["run_id"]},
        "integrity": integrity, "tamper_control": tamper_check,
        "evidence_paths": {"runner_invocations": str(output / "runner-invocations.json"),
                           "report": str(report_path)},
        "reproduce": "python scripts/core_validation.py --output NEW_EMPTY_OUTPUT",
        "reproduce_frozen": f"python {output / 'source-snapshot' / 'scripts' / 'core_validation.py'} --output NEW_EMPTY_OUTPUT",
        "reused_without_execution": False,
    }
    atomic_json(report_path, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evidence/core-validation"))
    args = parser.parse_args()
    print(json.dumps(validate(args.output), ensure_ascii=False, indent=2, sort_keys=True))
