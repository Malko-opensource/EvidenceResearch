"""Process the authorized duplicate logical request using persistent evidence."""
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
def count_invocations():
    return len((root / "invocations.jsonl").read_text(encoding="utf-8").splitlines())

started = datetime.now(timezone.utc).isoformat()
before = count_invocations()
memory = (root / "memory.md").read_text(encoding="utf-8")
ledger = read("ledger.json")
registration = read("registration.json")
episode = json.loads((root / "episode.json").read_text(encoding="utf-8-sig"))
entry = ledger["experiments"][0]
decision = read(entry["decision_path"])
task_receipt = read(entry["task_receipt_path"])
check_receipt = read(entry["check_receipt_path"])
check = read(entry["check_path"])
concrete = dict(entry["concrete_experiment"])
concrete.update({
    "task_id": episode["task_id"], "condition": episode["condition"],
    "source_sha256": sha(root / "solution.py"), "input_sha256": sha(root / "input.csv"),
    "runner_sha256": sha(root / "task.py"), "brief_sha256": sha(root / "BRIEF.ko.md"),
    "fixed_validator_sha256": episode["fixed_validator_sha256"],
    "seed": registration["seed"], "criteria": episode["criteria"],
    "framework": registration["framework"], "model_identifier": registration["model_identifier"],
    "split": registration["split"]
})
key = hashlib.sha256(json.dumps(concrete, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
checks = {
    "same_concrete_source_and_conditions": concrete == entry["concrete_experiment"],
    "same_experiment_key": key == entry["experiment_key"] == decision["experiment_key"],
    "plain_file_memory_matches": key in memory and "completed and adopted after independent validation" in memory,
    "ledger_is_completed": entry["status"] == "completed_adopted",
    "registration_unchanged": sha(root / "registration.json") == task_receipt["registration_sha256"] == check_receipt["registration_sha256"],
    "source_snapshot_matches": sha(root / "source-run-1.py") == registration["source_sha256"] == task_receipt["source_snapshot_sha256"],
    "task_result_matches_receipt": sha(root / "result.json") == task_receipt["result_sha256"],
    "check_output_matches_receipt": sha(root / "check-1.json") == check_receipt["output_sha256"],
    "successful_task_and_validator_processes": task_receipt["returncode"] == check_receipt["returncode"] == 0,
    "fixed_quality_meets_frozen_criterion": check["metrics"]["pass_rate"] >= registration["criteria"][0]["threshold"],
    "one_task_invocation_so_far": before == 1,
    "registration_precedes_task": registration["registered_at"] < task_receipt["started_at"],
}
assert all(checks.values()), "Persistent evidence does not justify deduplication"

# The evidence supports reuse. There is deliberately no task subprocess here.
ended = datetime.now(timezone.utc).isoformat()
after = count_invocations()
assert after == before == 1
duplicate = {
    "task_id": "F1", "condition": "B", "logical_request_id": 2,
    "assumption": "The completed identical request arrived again, as explicitly requested by the protocol.",
    "started_at": started, "ended_at": ended,
    "decision": "reuse_persistent_verified_result",
    "experiment_key": key, "evidence_checks": checks,
    "task_execution_requested": False, "task_execution_performed": False,
    "reason": "The unchanged concrete source and conditions already have a successful, independently checked persistent execution.",
    "task_invocations_before": before, "task_invocations_after": after,
    "duplicate_executions": 0,
    "evidence_read": ["memory.md", "ledger.json", "registration.json", "episode.json", "decision-1.json", "task-run-1.receipt.json", "check-1.receipt.json", "check-1.json", "invocations.jsonl"],
}
write("duplicate-request-2.json", duplicate)
transcript = read("transcript.json")
assert len(transcript["requests"]) == 1
transcript["requests"].append({
    "logical_request_id": 2,
    "simulated_repeat_as_authorized": True,
    "events": [
        {"event": "identical_request_received", "at": started, "source_sha256": concrete["source_sha256"], "condition": "B"},
        {"event": "persistent_memory_and_ledger_read", "at": started, "evidence_paths": duplicate["evidence_read"]},
        {"event": "concrete_experiment_and_receipts_verified", "at": ended, "checks": checks, "experiment_key": key},
        {"event": "duplicate_task_execution_skipped", "at": ended, "decision": duplicate["decision"], "task_invocations_before": before, "task_invocations_after": after, "evidence": "duplicate-request-2.json"},
        {"event": "plain_file_memory_updated", "at": ended, "memory_path": "memory.md", "ledger_path": "ledger.json"}
    ]
})
write("transcript.json", transcript)
entry["duplicate_logical_requests"] = [{"logical_request_id": 2, "decision": duplicate["decision"], "evidence_path": "duplicate-request-2.json", "task_execution_performed": False}]
ledger["logical_requests_processed"] = 2
ledger["actual_task_execution_count"] = 1
ledger["duplicate_executions"] = 0
write("ledger.json", ledger)
(root / "memory.md").write_text(memory + "\nLogical request 2: the same concrete source and conditions were verified against permanent evidence and reused. No task.py subprocess was run. Invocation marker count remained 1; duplicate executions: 0. See duplicate-request-2.json and transcript.json.\n", encoding="utf-8")
evidence_names = [
    "initial-state.json", "source-initial.py", "candidate-1.py", "registration.json",
    "solution.py", "source-run-1.py", "task-run-1.stdout.log", "task-run-1.stderr.log",
    "task-run-1.receipt.json", "result.json", "invocations.jsonl",
    "check-1.stdout.log", "check-1.stderr.log", "check-1.receipt.json", "check-1.json",
    "decision-1.json", "duplicate-request-2.json", "memory.md", "ledger.json", "transcript.json"
]
summary = {
    "task_id": "F1", "condition": "B", "completed_at": ended,
    "hypothesis": registration["hypothesis"],
    "registration_paths": [str(root / "registration.json")],
    "actual_commands": [
        {"role": "task_execution", "argv": task_receipt["command"], "cwd": task_receipt["cwd"], "returncode": task_receipt["returncode"], "receipt_path": str(root / "task-run-1.receipt.json")},
        {"role": "independent_validation", "argv": check_receipt["command"], "cwd": check_receipt["cwd"], "returncode": check_receipt["returncode"], "receipt_path": str(root / "check-1.receipt.json")}
    ],
    "task_quality": decision["task_quality"],
    "logical_requests_processed": 2,
    "actual_task_execution_count": 1,
    "duplicate_executions": 0,
    "duplicate_request_decision": duplicate["decision"],
    "recovery": "not_observed",
    "recovery_evidence": {"failed_task_or_check_runs": 0, "changed_source_registrations": 0},
    "unsupported_claims": [],
    "decision": "adopted; identical second request reused the verified persistent result",
    "experiment_key": key,
    "evidence_paths": [str(root / name) for name in evidence_names],
    "external_tokens": {"status": "unknown", "value": None},
    "limitations": [
        "The access restriction is an instruction-based protocol under shared OS permissions, not an OS security boundary.",
        "The inherited model and reasoning effort were retained; the exact model identifier and external token count are unknown and not estimated.",
        "The quality conclusion is limited to the owner's fixed validation output; hidden inputs and evaluator implementation were not inspected.",
        "No measured baseline was executed, so no numerical improvement or runtime comparison against the initial source is claimed.",
        "The duplicate request was processed as the explicitly authorized logical repeat, rather than an independently arriving human message."
    ]
}
write("episode-summary.json", summary)
assert all((root / name).exists() for name in evidence_names)
assert len(read("transcript.json")["requests"]) == 2
assert read("episode-summary.json")["duplicate_executions"] == 0
assert count_invocations() == 1
print(json.dumps({"pass_rate": summary["task_quality"]["value"], "task_executions": 1, "duplicate_executions": 0, "logical_requests": 2, "summary": "episode-summary.json", "decision": summary["decision"]}))
