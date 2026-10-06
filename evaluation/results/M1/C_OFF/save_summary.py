"""Save conclusions derived from original CLI responses and artifact audits."""
import datetime
import hashlib
import json
from pathlib import Path

episode = Path(__file__).resolve().parent
transcript_path = episode / "transcript.json"
transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
def records(action):
    return [entry for entry in transcript["commands"] if entry["command"][5] == action]

initial_memory = records("memory")[0]["response"]["data"]
final_memory = records("memory")[-1]["response"]["data"]
registration = records("register")[0]["response"]["data"]["registration"]
final_record = records("show")[-1]["response"]["data"]
verification = final_record["verification"]
decision = final_record["decision"]
before = json.loads((episode / "artifact-audit-before-repeat.json").read_text(encoding="utf-8"))
after = json.loads((episode / "artifact-audit-after-repeat.json").read_text(encoding="utf-8"))
before_log = next(item for item in before["files"] if item["name"] == "invocations.jsonl")
after_log = next(item for item in after["files"] if item["name"] == "invocations.jsonl")
assert len(records("run")) == 2
assert before["started"] is True and after["started"] is False
assert before["run_id"] == after["run_id"]
assert before_log["invocation_count"] == after_log["invocation_count"] == 1
assert before_log["work_invocation_count"] == after_log["work_invocation_count"] == 1
assert before_log["work_sha256"] == after_log["work_sha256"]
assert before["all_hashes_match"] and after["all_hashes_match"]
assert verification["state"] == "passed" and verification["metrics"]["pass_rate"] == 1.0
assert verification["details"]["integrity"] is True
assert verification["details"]["reported_run_metrics_used"] is False
assert decision["state"] == "adopted"
assert initial_memory["items"] == []
assert final_memory["items"][0]["claim_verified"] is True

snapshots = {
    "registration.json": registration,
    "verification.json": verification,
    "final-memory.json": final_memory,
    "final-record.json": final_record,
}
for filename, payload in snapshots.items():
    (episode / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
summary = {
    "task_id": "M1", "condition": "C_OFF",
    "framework": "Codex fresh subagent", "model": "inherited parent; exact identifier unknown",
    "hypothesis": final_record["hypothesis"]["statement"],
    "hypothesis_id": final_record["hypothesis"]["id"],
    "registration_id": registration["id"], "registration_ids": [registration["id"]],
    "run_id": after["run_id"],
    "task_quality": {"metric": "pass_rate", "value": verification["metrics"]["pass_rate"], "verification": verification["state"], "validator": registration["spec"]["validator"], "validator_sha256": verification["details"]["validator_sha256"], "source": verification["details"]["source"], "basis": verification["details"]["basis"], "passed_checks": verification["details"]["passed_cases"], "total_checks": verification["details"]["total_cases"], "artifact_integrity": verification["details"]["integrity"], "reported_run_metrics_used": False},
    "actual_task_executions": after_log["work_invocation_count"],
    "execution_count_basis": "Actual preserved task.py invocations.jsonl; fixed validator subprocess checks are independent validation, not task.py launches.",
    "duplicate_executions": after_log["work_invocation_count"] - before_log["work_invocation_count"],
    "duplicate_request": {"request_key": "m1-c-off-run-v1-e35dfbb29e2c", "started": False, "same_run_id": True, "invocations_before": before_log["work_invocation_count"], "invocations_after": after_log["work_invocation_count"], "invocation_sha256_unchanged": True},
    "recovery": "not_observed",
    "recovery_notes": "No scientific failure or unknown execution required recovery. The first run response used recovered:true for ordinary receipt ingestion; no recover command was invoked.",
    "bookkeeping_capture_errors": [], "scientific_failures": [], "unsupported_claims": [],
    "decision": decision["state"], "decision_reason": decision["reason"], "completed_at": completed_at,
    "initial_memory_items": initial_memory["items"], "initial_memory_total": initial_memory["total"],
    "useful_memory_influenced_hypothesis": False,
    "memory_interpretation": "The initial event search returned zero records. After verification and decision, memory contains this episode with claim_verified:true, supported by show and fixed verifier evidence.",
    "external_tokens": {"status": "unknown", "value": None},
    "source_version": registration["spec"]["source_version"],
    "source_files_match_preregistered_hashes": after["all_hashes_match"],
    "iterations": {"registered_candidates": 1, "criterion_changes": 0, "source_changes_after_registration": 0},
    "limitations": ["Outcome is limited to M1 and the owner fixed validator; no baseline measurement or general improvement claim.", "Exact inherited model identifier and token usage were not observed.", "No global iteration, time, or failure cap was imposed."],
    "paths": {"episode": str(episode), "transcript": str(transcript_path), "spec": str(episode / "spec.json"), "candidate": str(episode / "candidate-draft.py"), "solution": str(episode / "solution.py"), "initial_solution": str(episode / "initial-solution.py"), "registration": str(episode / "registration.json"), "verification": str(episode / "verification.json"), "final_memory": str(episode / "final-memory.json"), "final_record": str(episode / "final-record.json"), "artifact_audits": [str(episode / "artifact-audit-before-repeat.json"), str(episode / "artifact-audit-after-repeat.json")], "preserved_artifacts": [item["path"] for item in after["files"]]}
}
summary_path = episode / "episode-summary.json"
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
transcript["completed_at"] = completed_at
transcript["summary_path"] = str(summary_path)
transcript["snapshot_paths"] = [str(episode / filename) for filename in snapshots]
transcript["scope"] = {"read": "Own episode files, public README/CLI help and parent-provided public schema contract only; runner-reported preserved artifacts and CLI records", "not_read": "Other episode solutions, hidden evaluator implementation/cases, prior archives, owner/internal keys", "write": "Own episode files and own research workspace through CLI only; no direct DB/core mutation"}
transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"summary_path": str(summary_path), "transcript_path": str(transcript_path), "registration_id": registration["id"], "pass_rate": verification["metrics"]["pass_rate"], "decision": decision["state"], "actual_task_executions": summary["actual_task_executions"], "duplicate_executions": summary["duplicate_executions"]}))
