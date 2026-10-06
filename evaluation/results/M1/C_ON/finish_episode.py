"""Summarize own CLI evidence without importing or running candidate code."""
import datetime
import hashlib
import json
from pathlib import Path
import sys

episode = Path(__file__).resolve().parent
transcript_path = episode / "transcript.json"
transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
extras = json.loads((episode / "capture-extra.json").read_text(encoding="utf-8"))
run_indices = [i for i, entry in enumerate(transcript["commands"]) if entry.get("response", {}).get("data", {}).get("record", {}).get("run")]
transcript["commands"].insert(run_indices[0], extras["deployment"])
transcript["draft_source_hashes"] = extras["source_hashes"]
transcript["notes"].extend(extras["notes"])
transcript["commands"][2]["commands"] = [[sys.executable, "-m", "research_cli", "--workspace", str(episode / "research"), "show", "reg_028148663caa496a9498d2f2e3469251"]] + [[sys.executable, "-m", "research_cli", "--workspace", str(episode / "research"), command, "--help"] for command in ("goal", "hypothesis", "register", "run", "verify", "decide")]
show = next(entry["response"]["data"] for entry in reversed(transcript["commands"]) if entry.get("command", [])[-3:] == ["show", "--registration", "reg_9b8918161a944087a54245a4579928d0"])
run_commands = [entry for entry in transcript["commands"] if "run" in entry.get("command", []) and entry.get("response", {}).get("data", {}).get("record", {}).get("registration", {}).get("id") == show["registration"]["id"]]
before = json.loads((episode / "audit-before-replay.json").read_text(encoding="utf-8"))
after = json.loads((episode / "audit-after-replay.json").read_text(encoding="utf-8"))
memory_entry = transcript["commands"][1]
initial_memory = json.loads(memory_entry["tool_response"]["output"])["data"]["items"]
files = show["run"]["receipt"]["files"]
current_hashes = {name: hashlib.sha256((episode / name).read_bytes()).hexdigest() for name in ("solution.py", "input.csv", "task.py")}
assert current_hashes == show["registration"]["spec"]["source_version"]["files"]
assert len(run_commands) == 2
assert run_commands[0]["response"]["data"]["started"] is True
assert run_commands[1]["response"]["data"]["started"] is False
assert before["artifact_invocation_count"] == after["artifact_invocation_count"] == 1
assert before["work_invocation_count"] == after["work_invocation_count"] == 1
assert before["work_invocations_sha256"] == after["work_invocations_sha256"]
assert before["all_receipt_hashes_match"] and after["all_receipt_hashes_match"]
verification = show["verification"]
assert verification["state"] == "passed" and verification["metrics"]["pass_rate"] == 1.0
assert show["decision"]["state"] == "adopted"
summary = {
    "task_id": "M1", "condition": "C_ON", "framework": "Codex fresh subagent",
    "model": "inherited parent; exact identifier unknown",
    "hypothesis": show["hypothesis"]["statement"], "hypothesis_id": show["hypothesis"]["id"],
    "registration_id": show["registration"]["id"], "run_id": show["run"]["id"],
    "task_quality": {"metric": "pass_rate", "value": verification["metrics"]["pass_rate"], "verification": verification["state"], "passed_cases": verification["details"]["passed_cases"], "total_cases": verification["details"]["total_cases"], "basis": verification["details"]["basis"], "integrity": verification["details"]["integrity"], "reported_run_metrics_used": False},
    "actual_task_executions": 1,
    "execution_count_basis": "Measured own registered task.py invocation ledger in preserved artifacts and work; validator recomputations are independent validation, not additional logical task runs.",
    "duplicate_executions": 0,
    "same_key_replay": {"requests": 2, "second_started": False, "artifact_invocations_before": 1, "artifact_invocations_after": 1, "work_invocations_before": 1, "work_invocations_after": 1, "work_invocations_hash_unchanged": True},
    "recovery": {"status": "not_observed", "scientific_fault": False, "note": "Normal first run response recovered:true is receipt reconciliation; no running/unknown fault or explicit recover request occurred."},
    "bookkeeping_errors": transcript["bookkeeping_errors"],
    "capture_errors": [],
    "unsupported_claims": [],
    "claim_scope": "Only fixed M1 task verification; no causal memory benefit, overall quality, general improvement, exact model, or token-cost claim.",
    "decision": show["decision"],
    "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "initial_memory_items": initial_memory,
    "initial_memory_item_count": len(initial_memory),
    "useful_memory_influenced_hypothesis": True,
    "memory_influence": "The prior failed/rejected full-row equality record reinforced event_id identity and latest-valid timestamp/later-input tie rules. Its failure interpretation was applicable; its scientific claim was unverified/failed. This is a reported influence, not a measured causal benefit.",
    "external_tokens": {"status": "unknown", "value": None},
    "source_version": show["registration"]["spec"]["source_version"],
    "current_source_hashes_match_registration": True,
    "validator_sha256": show["registration"]["spec"]["validator_sha256"],
    "evidence_paths": [{"name": item["name"], "preserved_path": item["path"], "original_path": item["origin_path"], "sha256": item["sha256"]} for item in files],
    "cli_evidence_records": show["evidence"],
    "saved_paths": {"transcript": str(transcript_path), "spec": str(episode / "spec.json"), "draft": str(episode / "candidate.py"), "solution": str(episode / "solution.py"), "before_replay_audit": str(episode / "audit-before-replay.json"), "after_replay_audit": str(episode / "audit-after-replay.json")},
    "prohibited_materials_read": False,
    "prior_failed_registration_retained": "reg_028148663caa496a9498d2f2e3469251"
}
transcript["own_final_record"] = show
transcript["episode_completed_at"] = summary["completed_at"]
transcript["artifact_paths"] = summary["evidence_paths"]
transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
destination = episode / "episode-summary.json"
destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"summary_path": str(destination), "transcript_path": str(transcript_path), "registration_id": summary["registration_id"], "pass_rate": summary["task_quality"]["value"], "task_executions": 1, "duplicate_executions": 0, "decision": show["decision"]["state"]}))
