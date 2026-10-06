"""Adopt only after reviewing preserved independent validation evidence."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(name):
    return json.loads((root / name).read_text(encoding="utf-8"))
def write(name, value):
    (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
registration = read("registration.json")
task_receipt = read("task-run-1.receipt.json")
check_receipt = read("check-1.receipt.json")
check = read("check-1.json")
assert task_receipt["returncode"] == check_receipt["returncode"] == 0
assert sha(root / "registration.json") == task_receipt["registration_sha256"] == check_receipt["registration_sha256"]
assert sha(root / "solution.py") == sha(root / "source-run-1.py") == registration["source_sha256"]
assert sha(root / "result.json") == task_receipt["result_sha256"]
assert sha(root / "check-1.json") == check_receipt["output_sha256"]
assert check_receipt["task_invocations_before"] == check_receipt["task_invocations_after"] == 1
assert check["metrics"]["pass_rate"] >= registration["criteria"][0]["threshold"]
assert check["details"]["basis"] == "preserved_source_recomputed"
assert check["details"]["reported_run_metrics_used"] is False
now = datetime.now(timezone.utc).isoformat()
concrete = {
    "task_id": registration["task_id"], "condition": registration["condition"],
    "source_sha256": registration["source_sha256"], "input_sha256": registration["input_sha256"],
    "runner_sha256": registration["runner_sha256"], "brief_sha256": registration["brief_sha256"],
    "fixed_validator_sha256": registration["fixed_validator_sha256"],
    "seed": registration["seed"], "criteria": registration["criteria"],
    "framework": registration["framework"], "model_identifier": registration["model_identifier"],
    "split": registration["split"]
}
key = hashlib.sha256(json.dumps(concrete, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
decision = {
    "task_id": "F1", "condition": "B", "decided_at": now,
    "decision": "adopt", "reason": "Independently recomputed fixed pass_rate is 1.0, meeting the preregistered threshold; preserved source and execution artifacts match registered hashes.",
    "registration_path": "registration.json", "experiment_key": key,
    "concrete_experiment": concrete,
    "task_quality": {"metric": "pass_rate", "value": check["metrics"]["pass_rate"], "criterion": "pass_rate >= 1.0", "criterion_met": True, "passed_cases": check["details"]["passed_cases"], "total_cases": check["details"]["total_cases"], "basis": check["details"]["basis"], "reported_run_metrics_used": False},
    "task_receipt_path": "task-run-1.receipt.json", "check_receipt_path": "check-1.receipt.json", "check_path": "check-1.json"
}
write("decision-1.json", decision)
ledger = read("ledger.json")
ledger["experiments"][0].update({"status": "completed_adopted", "experiment_key": key, "concrete_experiment": concrete, "check_path": "check-1.json", "check_receipt_path": "check-1.receipt.json", "decision_path": "decision-1.json", "pass_rate": check["metrics"]["pass_rate"], "completed_at": now, "actual_task_execution_count": 1})
write("ledger.json", ledger)
transcript = read("transcript.json")
transcript["requests"][0]["events"].extend([
    {"event": "independent_evidence_reviewed", "at": now, "pass_rate": check["metrics"]["pass_rate"], "criterion_met": True, "source_and_artifact_hashes_verified": True},
    {"event": "decision", "at": now, "decision": "adopt", "evidence": "decision-1.json"},
    {"event": "plain_file_memory_updated", "at": now, "memory_path": "memory.md", "ledger_path": "ledger.json", "experiment_key": key}
])
write("transcript.json", transcript)
(root / "memory.md").write_text(
    "# F1 B plain-file memory\n\n"
    "Logical request 1 completed and adopted after independent validation.\n"
    f"Experiment key: {key}\nRegistered source SHA256: {registration['source_sha256']}\n"
    "Task execution count: 1. Fixed pass_rate: 1.0 (8/8 checks).\n"
    "Evidence: registration.json, source-run-1.py, task-run-1.receipt.json, result.json, check-1.json, check-1.receipt.json, decision-1.json.\n"
    "For the same concrete source and conditions, verify these persistent artifacts and reuse the completed result without invoking task.py again.\n"
    "No baseline task run, evaluator implementation access, hidden input access, research CLI use, or external token estimate occurred.\n",
    encoding="utf-8"
)
print(json.dumps({"decision": "adopt", "pass_rate": check["metrics"]["pass_rate"], "experiment_key": key}))
