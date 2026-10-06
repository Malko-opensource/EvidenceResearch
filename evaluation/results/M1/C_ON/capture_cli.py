"""Episode-only command capture; delegates research state to its public CLI."""
import datetime
import json
from pathlib import Path
import subprocess
import sys

EPISODE = Path(__file__).resolve().parent
PROJECT = EPISODE.parents[3]
TRANSCRIPT = EPISODE / "transcript.json"


def call(args):
    command = [sys.executable, "-m", "research_cli", "--workspace", str(EPISODE / "research"), *args]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = subprocess.run(command, cwd=PROJECT, capture_output=True, text=True, encoding="utf-8")
    entry = {"command": command, "cwd": str(PROJECT), "started_at": started,
             "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    try:
        entry["response"] = json.loads(result.stdout)
    except json.JSONDecodeError:
        pass
    transcript = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))
    transcript["commands"].append(entry)
    TRANSCRIPT.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return entry


if __name__ == "__main__":
    record = call(sys.argv[1:])
    raise SystemExit(record["exit_code"])
