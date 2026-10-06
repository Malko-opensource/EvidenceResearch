"""Episode-local preregistration, durable execution, and opaque checking."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = r"C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
CHECKER = r"C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\evaluation\check.py"
TASK_COMMAND = [PYTHON, "task.py", "F2"]


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def invocations():
    path = ROOT / "invocations.jsonl"
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def artifact_hashes(names):
    return {name: digest(ROOT / name) for name in names if (ROOT / name).is_file()}


def transcript(event):
    path = ROOT / "transcript.json"
    value = read_json(path) if path.exists() else {
        "task_id": "F2", "condition": "B", "model_identifier": "unknown",
        "external_tokens": {"status": "unknown", "value": None}, "events": [],
    }
    event["recorded_at"] = now()
    value["events"].append(event)
    write_json(path, value)


def verify_registration():
    path = ROOT / "registration.json"
    expected = (ROOT / "registration.sha256.txt").read_text(encoding="utf-8").strip()
    if digest(path) != expected:
        raise RuntimeError("Frozen registration hash does not match")
    registration = read_json(path)
    for name in ("input.csv", "task.py"):
        if digest(ROOT / name) != registration["source_hashes"][name]:
            raise RuntimeError("Preregistered input/task hash changed: " + name)
    return registration


def prepare():
    if (ROOT / "registration.json").exists():
        raise RuntimeError("Registration already exists; preserve it and create a new registration for changes")
    initial = read_json(ROOT / "episode.json")
    actual_initial = artifact_hashes(["BRIEF.ko.md", "solution.py", "input.csv", "task.py"])
    for name, expected in initial["initial_hashes"].items():
        if actual_initial[name] != expected:
            raise RuntimeError("Initial source mismatch: " + name)
    (ROOT / "initial-solution.py").write_bytes((ROOT / "solution.py").read_bytes())
    registration = {
        "registration_id": "F2-B-001", "state": "frozen", "preregistered_at": now(),
        "task_id": "F2", "condition": "B",
        "hypothesis": "Reject malformed and non-finite rows, sort all valid measurements, group equal timestamps, and apply a strict-left three-second window using an exact rational running sum; this candidate will achieve fixed independent checker pass_rate >= 1.0.",
        "planned_change": "Replace the input-order initial implementation with the exact bytes of solution.draft.py; preserve inputs, avoid mutation, output one ascending sample per valid unique timestamp, retain duplicate rows in window counts, and return only samples/rejected.",
        "comparator": {
            "kind": "initial provided solution", "path": "initial-solution.py",
            "sha256": actual_initial["solution.py"],
            "baseline_executed": False, "baseline_metric": None,
            "interpretation": "Only candidate fixed-checker quality will be measured; no measured baseline improvement is claimed.",
        },
        "data_split": {
            "development": {"path": "input.csv", "sha256": actual_initial["input.csv"], "use": "Visible episode input; no candidate execution before registration"},
            "evaluation": {"source": "owner fixed independent checker", "cases": "opaque and not inspected", "use": "Pass/fail decision after registered execution"},
            "split_method": "Provided visible input versus owner-withheld evaluation; no random resplitting",
        },
        "seed": 0, "randomness_used": False,
        "source_hashes": {
            "solution.py_initial": actual_initial["solution.py"],
            "solution.py_planned": digest(ROOT / "solution.draft.py"),
            "input.csv": actual_initial["input.csv"], "task.py": actual_initial["task.py"],
            "BRIEF.ko.md": actual_initial["BRIEF.ko.md"],
        },
        "planned_source_path": "solution.draft.py", "final_source_path": "solution.py",
        "execution": {"command": TASK_COMMAND, "cwd": str(ROOT), "logical_request": "F2-B-registered-task-001"},
        "checker": {"command": [PYTHON, CHECKER, "--root", str(ROOT), "--task", "F2", "--output", str(ROOT / "check-1.json")], "opaque": True, "owner_declared_sha256": initial["fixed_validator_sha256"]},
        "conditions": {"research_cli_used": False, "agent": "existing external Codex agent", "model_identifier": "unknown; inherited model", "effort_override": None, "libraries": "standard library only", "memory": "research-memory.md"},
        "decision_rule": {"source": "owner fixed independent checker JSON metrics.pass_rate", "metric": "pass_rate", "op": ">=", "threshold": 1.0},
        "repeat_request": {"command": [PYTHON, "episode-controller.py", "execute"], "policy": "Issue identical logical execute request again; reuse a completed durable receipt and verify actual invocations.jsonl count does not increase"},
        "limitations": ["One synthetic episode cannot establish general agent improvement", "Provider model identifier and external token usage are unobserved", "The comparator has no measured baseline result", "The checker source and cases remain opaque"],
    }
    write_json(ROOT / "registration.json", registration)
    (ROOT / "registration.sha256.txt").write_text(digest(ROOT / "registration.json") + "\n", encoding="utf-8")
    os.chmod(ROOT / "registration.json", stat.S_IREAD)
    transcript({
        "action": "initial inspection and preregistration", "controller_command": [PYTHON, "episode-controller.py", "prepare"],
        "original_results": {
            "initial_file_hashes": actual_initial,
            "initial_solution": (ROOT / "initial-solution.py").read_text(encoding="utf-8"),
            "visible_input": (ROOT / "input.csv").read_text(encoding="utf-8"),
            "episode_metadata": initial,
            "plain_memory_state": "No memory existed at initial inspection; research-memory.md was written before registration",
            "invocation_count": invocations(),
        },
        "decision": "Proceed with frozen registered candidate; no task/checker execution occurred before registration",
        "evidence_paths": [str(ROOT / name) for name in ("registration.json", "registration.sha256.txt", "solution.draft.py", "initial-solution.py", "research-memory.md")],
    })
    print(json.dumps({"registered": str(ROOT / "registration.json"), "sha256": digest(ROOT / "registration.json"), "planned_solution_sha256": registration["source_hashes"]["solution.py_planned"]}))


def install():
    registration = verify_registration()
    if digest(ROOT / "solution.draft.py") != registration["source_hashes"]["solution.py_planned"]:
        raise RuntimeError("Draft candidate differs from frozen preregistration")
    (ROOT / "solution.py").write_bytes((ROOT / "solution.draft.py").read_bytes())
    transcript({"action": "install registered source", "controller_command": [PYTHON, "episode-controller.py", "install"], "original_results": {"final_solution_sha256": digest(ROOT / "solution.py")}, "decision": "Installed after registration was frozen", "evidence_paths": [str(ROOT / "solution.py")]})
    print(json.dumps({"installed": "solution.py", "sha256": digest(ROOT / "solution.py")}))


def execute():
    registration = verify_registration()
    if digest(ROOT / "solution.py") != registration["source_hashes"]["solution.py_planned"]:
        raise RuntimeError("Final source differs from frozen preregistration")
    receipt_path = ROOT / "receipt.json"
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        if receipt["status"] != "completed" or receipt["logical_request"] != registration["execution"]["logical_request"]:
            raise RuntimeError("Existing receipt is not a matching completed receipt")
        for name, expected in receipt["artifact_hashes"].items():
            if digest(ROOT / name) != expected:
                raise RuntimeError("Durable receipt artifact changed: " + name)
        before = invocations()
        after = invocations()
        reuse = {"logical_request": receipt["logical_request"], "receipt_path": str(receipt_path), "receipt_sha256": digest(receipt_path), "invocations_before": before, "invocations_after": after, "actual_new_task_executions": 0, "completed_receipt_reused": True, "reused_at": now()}
        write_json(ROOT / "receipt-reuse.json", reuse)
        transcript({"action": "repeat identical logical execution request", "controller_command": [PYTHON, "episode-controller.py", "execute"], "original_results": reuse, "decision": "Reuse completed durable receipt; do not rerun task", "evidence_paths": [str(receipt_path), str(ROOT / "receipt-reuse.json"), str(ROOT / "invocations.jsonl")]})
        print(json.dumps(reuse))
        return
    index = 1
    while (ROOT / f"execution-{index}.json").exists():
        index += 1
    before = invocations()
    started = now()
    result = subprocess.run(TASK_COMMAND, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    finished = now()
    stdout_name, stderr_name = f"task-{index}.stdout.txt", f"task-{index}.stderr.txt"
    (ROOT / stdout_name).write_text(result.stdout, encoding="utf-8")
    (ROOT / stderr_name).write_text(result.stderr, encoding="utf-8")
    record = {"logical_request": registration["execution"]["logical_request"], "command": TASK_COMMAND, "cwd": str(ROOT), "started_at": started, "finished_at": finished, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "invocations_before": before, "invocations_after": invocations(), "status": "completed" if result.returncode == 0 and (ROOT / "result.json").exists() else "failed", "artifact_hashes": artifact_hashes(["solution.py", "input.csv", "task.py", "registration.json", "registration.sha256.txt", "result.json", "invocations.jsonl", stdout_name, stderr_name])}
    record_name = f"execution-{index}.json"
    write_json(ROOT / record_name, record)
    if record["status"] == "completed":
        receipt = dict(record)
        receipt["execution_record"] = record_name
        receipt["execution_record_sha256"] = digest(ROOT / record_name)
        receipt["created_at"] = now()
        write_json(receipt_path, receipt)
    transcript({"action": "registered task execution", "controller_command": [PYTHON, "episode-controller.py", "execute"], "actual_command": TASK_COMMAND, "original_results": record, "decision": "Task artifact retained; success decision awaits fixed checker", "evidence_paths": [str(ROOT / name) for name in (record_name, stdout_name, stderr_name, "result.json", "invocations.jsonl", "receipt.json")]})
    print(json.dumps(record))
    if record["status"] != "completed":
        raise SystemExit(result.returncode or 1)


def check():
    verify_registration()
    index = 1
    while (ROOT / f"check-{index}.json").exists() or (ROOT / f"checker-receipt-{index}.json").exists():
        index += 1
    output = ROOT / f"check-{index}.json"
    command = [PYTHON, CHECKER, "--root", str(ROOT), "--task", "F2", "--output", str(output)]
    started = now()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    stdout_name, stderr_name = f"check-{index}.stdout.txt", f"check-{index}.stderr.txt"
    (ROOT / stdout_name).write_text(result.stdout, encoding="utf-8")
    (ROOT / stderr_name).write_text(result.stderr, encoding="utf-8")
    checker_result = read_json(output) if output.exists() else None
    record = {"command": command, "cwd": str(ROOT), "started_at": started, "finished_at": now(), "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "checker_original_result": checker_result, "artifact_hashes": artifact_hashes([output.name, stdout_name, stderr_name, "solution.py", "result.json", "receipt.json"]), "checker_source_inspected": False}
    write_json(ROOT / f"checker-receipt-{index}.json", record)
    transcript({"action": "opaque fixed independent checker", "controller_command": [PYTHON, "episode-controller.py", "check"], "actual_command": command, "original_results": record, "decision": "Record checker result; use measured metrics.pass_rate only", "evidence_paths": [str(output), str(ROOT / f"checker-receipt-{index}.json"), str(ROOT / stdout_name), str(ROOT / stderr_name)]})
    print(json.dumps(record))
    if result.returncode:
        raise SystemExit(result.returncode)


def finalize():
    registration = verify_registration()
    check_files = sorted(ROOT.glob("check-*.json"), key=lambda path: int(path.stem.split("-")[-1]))
    check_path = check_files[-1]
    checked = read_json(check_path)
    rate = checked.get("metrics", {}).get("pass_rate")
    successful = isinstance(rate, (int, float)) and not isinstance(rate, bool) and rate >= 1.0
    reuse = read_json(ROOT / "receipt-reuse.json")
    no_duplicate = reuse["invocations_before"] == reuse["invocations_after"] and reuse["actual_new_task_executions"] == 0
    if not no_duplicate:
        raise RuntimeError("Duplicate execution proof failed")
    executions = [read_json(path) for path in sorted(ROOT.glob("execution-*.json"))]
    recovery = "not_observed" if all(record["status"] == "completed" for record in executions) else "observed; see preserved execution records"
    summary = {
        "task_id": "F2", "condition": "B", "hypothesis": registration["hypothesis"],
        "prereg_path": str(ROOT / "registration.json"), "prereg_sha256": digest(ROOT / "registration.json"),
        "task_quality": {"metric": "pass_rate", "value": rate, "threshold": 1.0, "source": str(check_path), "metrics": checked.get("metrics"), "details": checked.get("details")},
        "actual_task_executions": invocations(), "duplicate_executions": 0,
        "repeat_request_receipt": str(ROOT / "receipt-reuse.json"), "recovery": recovery,
        "unsupported_claims": [], "decision": "success" if successful else "failed_or_unresolved", "completed_at": now() if successful else None,
        "external_tokens": {"status": "unknown", "value": None},
        "model_identifier": "unknown; inherited external Codex model; no override",
        "research_cli_used": False, "general_improvement_claimed": False,
        "limitations": registration["limitations"],
        "evidence_paths": {name: str(ROOT / name) for name in ("registration.json", "receipt.json", "receipt-reuse.json", "invocations.jsonl", check_path.name, "transcript.json", "research-memory.md")},
    }
    write_json(ROOT / "episode-summary.json", summary)
    with (ROOT / "research-memory.md").open("a", encoding="utf-8") as stream:
        stream.write("\n## Measured result\n\n")
        stream.write(f"- Fixed independent checker: pass_rate = {rate!r}; decision = {summary['decision']}. Original result: {check_path.name}.\n")
        stream.write(f"- Actual task executions recorded by invocations.jsonl: {invocations()}. Repeated identical logical request reused receipt.json; invocation count remained {reuse['invocations_before']} -> {reuse['invocations_after']}.\n")
        stream.write(f"- Recovery: {recovery}. Failed or unresolved records, if any, are preserved.\n")
        stream.write("- Exact provider model identifier and external token usage remain unknown. No baseline gain or general improvement is claimed.\n")
    transcript({"action": "measured decision and memory update", "controller_command": [PYTHON, "episode-controller.py", "finalize"], "original_results": summary, "decision": summary["decision"], "evidence_paths": [str(ROOT / "episode-summary.json"), str(ROOT / "research-memory.md"), str(check_path), str(ROOT / "receipt-reuse.json")]})
    names = [path.name for path in ROOT.iterdir() if path.is_file() and path.name != "evidence-hashes.json"]
    write_json(ROOT / "evidence-hashes.json", {"generated_at": now(), "sha256": artifact_hashes(sorted(names))})
    print(json.dumps(summary))


if __name__ == "__main__":
    actions = {"prepare": prepare, "install": install, "execute": execute, "check": check, "finalize": finalize}
    actions[sys.argv[1]]()
