"""Produce the episode report exclusively from own files/public CLI captures."""
import base64
import datetime
import hashlib
import json
import pathlib

own = pathlib.Path(__file__).resolve().parent
transcript_path = own / "transcript.json"
transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
entries = transcript["entries"]
def command_entries(command):
    return [entry for entry in entries if entry["argv"][5] == command and entry.get("response", {}).get("ok")]

first_run, duplicate_run = command_entries("run")
verify = command_entries("verify")[-1]
record = verify["response"]["data"]["record"]
decision = command_entries("decide")[-1]["response"]["data"]["decision"]
memory = command_entries("memory")[-1]["response"]["data"]
registration = command_entries("register")[-1]["response"]["data"]["registration"]
observations = transcript["artifact_observations"]
after = observations[-1]
errors = [
    {"entry_index": index, "argv": entry["argv"],
     "returncode": entry.get("returncode"), "capture_error": entry.get("capture_error"),
     "capture_parse_error": entry.get("capture_parse_error"), "response": entry.get("response")}
    for index, entry in enumerate(entries)
    if entry.get("returncode", 1) != 0 or entry.get("capture_error")
       or entry.get("capture_parse_error") or entry.get("response", {}).get("ok") is False
]
assert not errors, errors
assert all(len(base64.b64decode(entry["stdout_base64"])) == entry["stdout_bytes"] for entry in entries)
assert all(len(base64.b64decode(entry["stderr_base64"])) == entry["stderr_bytes"] for entry in entries)
assert len(command_entries("run")) == 2
assert first_run["response"]["data"]["started"] is True
assert duplicate_run["response"]["data"]["started"] is False
assert first_run["response"]["data"]["record"]["run"]["id"] == duplicate_run["response"]["data"]["record"]["run"]["id"]
assert after["actual_invocations"] == after["live_invocations"]["actual_invocations"] == 1
assert record["verification"]["metrics"]["pass_rate"] == 1.0
assert memory["items"][0]["decision"] == "adopted"
assert hashlib.sha256((own / "solution.py").read_bytes()).hexdigest() == registration["spec"]["source_version"]["files"]["solution.py"]
summary = {
    "task_id": "D", "kind": "development interface validation",
    "excluded_from_performance_comparisons": True,
    "cli_version": command_entries("help")[0]["response"]["data"]["version"],
    "registration_id": registration["id"], "run_id": record["run"]["id"],
    "goal_id": registration["goal_id"], "hypothesis_id": registration["hypothesis_id"],
    "run_state": record["run"]["state"], "verification_state": record["verification"]["state"],
    "independent_metric": record["verification"]["metrics"],
    "criteria_results": record["verification"]["criteria_results"],
    "decision": decision,
    "actual_invocations": after["live_invocations"]["actual_invocations"],
    "preserved_invocation_count_before_duplicate": observations[0]["actual_invocations"],
    "preserved_invocation_count_after_duplicate": after["actual_invocations"],
    "duplicates": {
        "requests_repeated": 1, "request_key": "d-interface-run-v1",
        "same_run_id": True, "duplicate_started": duplicate_run["response"]["data"]["started"],
        "additional_invocations": 0,
    },
    "default_response_bytes": {
        "run": first_run["stdout_bytes"], "duplicate_run": duplicate_run["stdout_bytes"],
        "verify": verify["stdout_bytes"], "combined_run_verify": first_run["stdout_bytes"] + verify["stdout_bytes"],
        "counting_rule": "Original stdout bytes including trailing CRLF; responses are default compact, without --full. stderr was empty.",
    },
    "public_output": json.loads(next(item["text"] for item in after["artifacts"] if item["name"] == "result.json"))["result"],
    "artifacts": record["artifacts"], "artifact_total": record["artifact_total"],
    "evidence_integrity": record["evidence_integrity"], "claim_verified": record["claim_verified"],
    "final_memory": memory,
    "source_version": registration["spec"]["source_version"],
    "sequence": ["status", "memory", "external candidate draft and expected source hash", "goal", "hypothesis", "register", "final solution placement", "run", "same-key duplicate run", "verify", "decide", "memory"],
    "preregistration_before_solution_placement": True,
    "cli_errors": [], "capture_errors": [], "schema_clarification_needed": False,
    "schema_notes": "Public JSON help example supplied the actual stored interpreter. Public command help supplied goal/hypothesis/register/run/verify/decide/memory arguments. Default record fields and artifact paths sufficed; no undocumented field or internal store inspection was needed.",
    "tokens": {"status": "unknown", "value": None},
    "resources": record["run"]["resources"],
    "files": {"transcript": str(transcript_path), "candidate_plan": str(own / "candidate-plan.json"),
              "registration_spec": str(own / "registration-spec.json"), "solution": str(own / "solution.py")},
    "limitations": [
        "This is one development interface episode, excluded from all research performance comparisons; it supports no research-effectiveness or speed claim.",
        "The supplied baseline already computes the visible arithmetic means. The candidate is a different standard-library implementation, not evidence of a baseline bug fix.",
        "Independent evaluator code/cases, core source, database, owner key, internal keys, and other answers were not inspected.",
        "Only the normal succeeded path and one duplicate same-key request were tested; recovery/unknown-run semantics were not exercised.",
        "Default compact responses were consumed directly. Public show retrieval was advertised but not required or invoked in this episode.",
        "External model tokens and exact inherited model identifier are unavailable and recorded as unknown.",
        "One observed invocation does not establish a general exactly-once guarantee.",
    ],
    "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
(own / "episode-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: summary[key] for key in ["task_id", "registration_id", "run_id", "independent_metric", "actual_invocations", "default_response_bytes", "completed_at"]}, indent=2))
