"""Call the owner check entrypoint without reading its implementation."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
registration = json.loads((root / "registration.json").read_text(encoding="utf-8"))
assert sha(root / "solution.py") == registration["source_sha256"]
assert not (root / "check-1.json").exists(), "Do not overwrite validation evidence"
before = len((root / "invocations.jsonl").read_text(encoding="utf-8").splitlines())
command = registration["planned_check_command"]
started = datetime.now(timezone.utc).isoformat()
run = subprocess.run(command, cwd=root, text=True, encoding="utf-8", capture_output=True)
ended = datetime.now(timezone.utc).isoformat()
(root / "check-1.stdout.log").write_text(run.stdout, encoding="utf-8")
(root / "check-1.stderr.log").write_text(run.stderr, encoding="utf-8")
receipt = {
    "task_id": "F1", "condition": "B", "command": command, "cwd": str(root),
    "started_at": started, "ended_at": ended, "returncode": run.returncode,
    "registration_sha256": sha(root / "registration.json"),
    "source_sha256": sha(root / "solution.py"),
    "output_path": "check-1.json" if (root / "check-1.json").exists() else None,
    "output_sha256": sha(root / "check-1.json") if (root / "check-1.json").exists() else None,
    "stdout_path": "check-1.stdout.log", "stderr_path": "check-1.stderr.log",
    "task_invocations_before": before,
    "task_invocations_after": len((root / "invocations.jsonl").read_text(encoding="utf-8").splitlines()),
    "validator_implementation_read": False,
}
write(root / "check-1.receipt.json", receipt)
transcript = json.loads((root / "transcript.json").read_text(encoding="utf-8"))
transcript["requests"][0]["events"].append({"event": "independent_validator_executed", "at": ended, "actual_command": command, "returncode": run.returncode, "receipt": "check-1.receipt.json", "quality": "pending_output_review"})
write(root / "transcript.json", transcript)
print(json.dumps({"command": command, "returncode": run.returncode, "receipt": "check-1.receipt.json", "stdout": run.stdout, "stderr": run.stderr}))
if (root / "check-1.json").exists():
    print((root / "check-1.json").read_text(encoding="utf-8"))
