"""Capture this external agent's research CLI commands and original responses."""
import datetime
import json
import subprocess
import sys
from pathlib import Path

EPISODE = Path(__file__).resolve().parent
PROJECT = EPISODE.parents[3]
PYTHON = r"C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"


def main():
    command = [PYTHON, "-m", "research_cli", "--workspace", str(EPISODE / "research"), *sys.argv[1:]]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    proc = subprocess.run(command, cwd=PROJECT, text=True, encoding="utf-8", capture_output=True)
    transcript_path = EPISODE / "transcript.json"
    if transcript_path.exists():
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    else:
        transcript = {
            "task_id": "M1", "condition": "C_OFF",
            "external_agent": {"framework": "Codex fresh subagent", "model": "inherited parent; exact identifier unknown", "external_tokens": {"status": "unknown", "value": None}},
            "commands": [], "evidence_paths": [], "bookkeeping_errors": []
        }
    index = len(transcript["commands"]) + 1
    log_path = EPISODE / "capture_logs" / f"{index:02d}-{sys.argv[1]}.json"
    log_path.parent.mkdir(exist_ok=True)
    record = {
        "index": index, "command": command, "cwd": str(PROJECT),
        "started_at": started, "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
        "log_path": str(log_path)
    }
    try:
        record["response"] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        pass
    transcript["commands"].append(record)
    log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
