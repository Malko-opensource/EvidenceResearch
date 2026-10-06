"""Capture public CLI interactions without reading its implementation or store."""
import base64
import datetime
import json
import pathlib
import subprocess
import sys
import time

OWN = pathlib.Path(__file__).resolve().parent
CLI_PYTHON = OWN.parents[1] / ".validation-venv" / "Scripts" / "python.exe"
TRANSCRIPT = OWN / "transcript.json"
command = [str(CLI_PYTHON), "-m", "research_cli", "--workspace", str(OWN / "research"), *sys.argv[1:]]
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
clock_started = time.perf_counter()
entry = {"argv": command, "cwd": str(OWN), "started_at": started}
try:
    result = subprocess.run(command, cwd=OWN, capture_output=True)
    entry.update({
        "returncode": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="replace"),
        "stderr": result.stderr.decode("utf-8", errors="replace"),
        "stdout_base64": base64.b64encode(result.stdout).decode("ascii"),
        "stderr_base64": base64.b64encode(result.stderr).decode("ascii"),
        "stdout_bytes": len(result.stdout),
        "stderr_bytes": len(result.stderr),
    })
    try:
        entry["response"] = json.loads(result.stdout)
        entry["response_format"] = "json"
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        entry["response_format"] = "text"
        if "--help" not in sys.argv[1:]:
            entry["capture_parse_error"] = repr(error)
except Exception as error:
    entry["capture_error"] = repr(error)
entry["elapsed_seconds"] = time.perf_counter() - clock_started
entry["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
transcript = json.loads(TRANSCRIPT.read_text(encoding="utf-8")) if TRANSCRIPT.exists() else {
    "task_id": "D", "kind": "development interface validation", "excluded_from_performance_comparisons": True,
    "installed_cli_version_requested": "0.2", "consumer_cwd": str(OWN),
    "scope": "Public README/help, own episode files, and public CLI only; no core, DB, owner key, internal evaluator, or other answers inspected.",
    "entries": [],
}
transcript["entries"].append(entry)
TRANSCRIPT.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if "stdout_base64" in entry:
    sys.stdout.buffer.write(base64.b64decode(entry["stdout_base64"]))
    sys.stderr.buffer.write(base64.b64decode(entry["stderr_base64"]))
else:
    print(json.dumps(entry, ensure_ascii=False, indent=2))
sys.exit(entry.get("returncode", 1))
