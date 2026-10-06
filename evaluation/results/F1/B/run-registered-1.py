"""Install only the registered source and record its real task execution."""
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def count_invocations():
    path = root / "invocations.jsonl"
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
registration = json.loads((root / "registration.json").read_text(encoding="utf-8"))
assert sha(root / "candidate-1.py") == registration["source_sha256"], "Candidate changed since registration"
assert sha(root / "input.csv") == registration["input_sha256"]
assert sha(root / "task.py") == registration["runner_sha256"]
assert count_invocations() == 0, "A prior task invocation requires a ledger decision before rerunning"
shutil.copyfile(root / "candidate-1.py", root / "solution.py")
assert sha(root / "solution.py") == registration["source_sha256"]
shutil.copyfile(root / "solution.py", root / "source-run-1.py")
started = datetime.now(timezone.utc).isoformat()
before = count_invocations()
command = registration["planned_task_command"]
run = subprocess.run(command, cwd=root, text=True, encoding="utf-8", capture_output=True)
ended = datetime.now(timezone.utc).isoformat()
(root / "task-run-1.stdout.log").write_text(run.stdout, encoding="utf-8")
(root / "task-run-1.stderr.log").write_text(run.stderr, encoding="utf-8")
receipt = {
    "task_id": "F1", "condition": "B", "registration_path": "registration.json",
    "registration_sha256": sha(root / "registration.json"),
    "command": command, "cwd": str(root), "started_at": started, "ended_at": ended,
    "returncode": run.returncode,
    "source_sha256_before": registration["source_sha256"],
    "source_sha256_after": sha(root / "solution.py"),
    "source_snapshot_path": "source-run-1.py", "source_snapshot_sha256": sha(root / "source-run-1.py"),
    "invocations_before": before, "invocations_after": count_invocations(),
    "stdout_path": "task-run-1.stdout.log", "stderr_path": "task-run-1.stderr.log",
    "result_path": "result.json" if (root / "result.json").exists() else None,
    "result_sha256": sha(root / "result.json") if (root / "result.json").exists() else None,
    "success_claim": "Task process completion only; quality remains unverified until independent validation."
}
write(root / "task-run-1.receipt.json", receipt)
transcript = json.loads((root / "transcript.json").read_text(encoding="utf-8"))
transcript["requests"][0]["events"].extend([
    {"event": "registered_source_installed", "at": started, "source_sha256": receipt["source_sha256_before"], "snapshot": "source-run-1.py"},
    {"event": "task_executed", "at": ended, "actual_command": command, "returncode": run.returncode, "receipt": "task-run-1.receipt.json", "quality": "unverified"}
])
write(root / "transcript.json", transcript)
ledger = json.loads((root / "ledger.json").read_text(encoding="utf-8"))
ledger["experiments"][0].update({"status": "executed_pending_independent_validation", "task_receipt_path": "task-run-1.receipt.json", "returncode": run.returncode})
write(root / "ledger.json", ledger)
print(json.dumps({"command": command, "returncode": run.returncode, "invocations_after": receipt["invocations_after"], "receipt": "task-run-1.receipt.json"}))
