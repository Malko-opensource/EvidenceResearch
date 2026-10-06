"""Preserve the starting state and freeze a candidate before its task run."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
now = datetime.now(timezone.utc).isoformat()
episode = json.loads((root / "episode.json").read_text(encoding="utf-8-sig"))
initial_files = ["BRIEF.ko.md", "episode.json", "solution.py", "input.csv", "task.py"]
initial_state = {
    "observed_at": now,
    "initial_files": initial_files,
    "hashes": {name: sha(root / name) for name in initial_files},
    "initial_episode_hashes_match": all(sha(root / name) == digest for name, digest in episode["initial_hashes"].items()),
    "memory_present": False,
    "ledger_present": False,
    "task_invocations_present": False,
    "observation": "Directory listing contained only the five supplied files before any edits.",
}
write(root / "initial-state.json", initial_state)
shutil.copyfile(root / "solution.py", root / "source-initial.py")
registration = {
    "registration_id": "F1-B-1",
    "registered_at": now,
    "task_id": "F1",
    "condition": "B",
    "framework": "Existing external Codex fresh subagent, inherited parent model and reasoning effort",
    "model_identifier": "unknown",
    "research_cli_used": False,
    "hypothesis": "Reject missing, malformed, nonfinite, blank-group and nonpositive-weight rows; exact rational weighted calculations centered at the first valid value preserve small deviations at large common offsets and achieve fixed-validator pass_rate >= 1.0.",
    "changes": [
        "Trim group names and reject missing or blank group fields.",
        "Parse numeric fields as binary64 floats; reject parse failures, missing values, NaN, infinities and weights <= 0.",
        "Convert accepted binary64 values to exact Fraction values; calculate the weighted mean and weighted population variance using centered exact arithmetic, then round outputs to floats.",
        "Return only the prescribed groups and rejected fields without mutating input rows."
    ],
    "comparison": {
        "baseline": "Initial supplied source preserved as source-initial.py; inspected statically and not executed.",
        "baseline_source_sha256": sha(root / "source-initial.py"),
        "candidate": "candidate-1.py to be installed as solution.py",
        "comparison_type": "Candidate measured against fixed pass_rate criterion, with no measured baseline quality claim."
    },
    "split": {
        "development_input": "Provided public input.csv and BRIEF.ko.md only",
        "independent_evaluation": "Owner fixed validator called as an opaque subprocess; evaluator implementation and hidden cases not read",
        "hidden_case_access": False,
        "other_condition_access": False,
        "past_implementation_access": False
    },
    "seed": 0,
    "source_sha256": sha(root / "candidate-1.py"),
    "input_sha256": sha(root / "input.csv"),
    "runner_sha256": sha(root / "task.py"),
    "brief_sha256": sha(root / "BRIEF.ko.md"),
    "fixed_validator_sha256": episode["fixed_validator_sha256"],
    "criteria": [{"metric": "pass_rate", "op": ">=", "threshold": 1.0}],
    "criteria_policy": "No successful/adopted claim before independent verification; preserve a failed registration and run, then register a changed candidate if recovery is needed.",
    "planned_task_command": [r"C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe", "task.py", "F1"],
    "planned_check_command": [r"C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe", r"C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\evaluation\check.py", "--root", str(root), "--task", "F1", "--output", str(root / "check-1.json")],
    "iteration_or_time_limit": None,
    "external_tokens": {"status": "unknown", "value": None},
}
write(root / "registration.json", registration)
write(root / "transcript.json", {
    "task_id": "F1", "condition": "B",
    "requests": [{
        "logical_request_id": 1,
        "events": [
            {"event": "existing_state_checked", "at": now, "evidence": "initial-state.json", "memory": "absent", "ledger": "absent"},
            {"event": "external_hypothesis_proposed", "at": now, "hypothesis": registration["hypothesis"]},
            {"event": "preregistered", "at": now, "registration": "registration.json", "source_sha256": registration["source_sha256"], "criterion": "pass_rate >= 1.0"}
        ]
    }]
})
write(root / "ledger.json", {"task_id": "F1", "condition": "B", "experiments": [{"registration_path": "registration.json", "source_sha256": registration["source_sha256"], "status": "registered_pending_execution"}]})
(root / "memory.md").write_text("# F1 B plain-file memory\n\nInitial state: no memory, ledger, or task invocation marker existed.\nHypothesis and candidate source are frozen in registration.json.\nNo execution or quality claim has yet been made.\n", encoding="utf-8")
print(json.dumps({"registration": "registration.json", "source_sha256": registration["source_sha256"], "initial_hashes_match": initial_state["initial_episode_hashes_match"]}))
