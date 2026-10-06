"""Read own CLI-reported artifacts and logs without invoking task code."""
import datetime
import hashlib
import json
from pathlib import Path
import sys

episode = Path(__file__).resolve().parent
transcript_path = episode / "transcript.json"
transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
run_entries = [entry for entry in transcript["commands"] if entry.get("response", {}).get("ok") and entry.get("response", {}).get("data", {}).get("record", {}).get("run")]
record = run_entries[-1]["response"]["data"]["record"]
run = record["run"]
files = run["receipt"]["files"]
checks = []
contents = {}
for item in files:
    path = Path(item["path"])
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    checks.append({"name": item["name"], "path": str(path), "sha256": digest, "receipt_sha256": item["sha256"], "matches": digest == item["sha256"]})
    if item["name"] in ("result.json", "invocations.jsonl", "stdout", "stderr", "launch", "process"):
        contents[item["name"]] = raw.decode("utf-8")
artifact_invocations = [line for line in contents["invocations.jsonl"].splitlines() if line.strip()]
work_invocation_path = next(Path(item["origin_path"]) for item in files if item["name"] == "invocations.jsonl")
work_raw = work_invocation_path.read_bytes()
work_count = len([line for line in work_raw.decode("utf-8").splitlines() if line.strip()])
payload = {"run_id": run["id"], "registration_id": record["registration"]["id"],
           "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "files": checks, "original_contents": contents,
           "artifact_invocation_count": len(artifact_invocations), "work_invocation_count": work_count,
           "work_invocations_path": str(work_invocation_path),
           "work_invocations_sha256": hashlib.sha256(work_raw).hexdigest(),
           "all_receipt_hashes_match": all(item["matches"] for item in checks)}
destination = episode / sys.argv[1]
destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
entry = {"command": [sys.executable, str(Path(__file__).resolve()), sys.argv[1]], "cwd": str(Path.cwd()),
         "response": payload, "note": "Read-only inspection; no solution import or task invocation"}
transcript["commands"].append(entry)
transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"saved": str(destination), "artifact_invocation_count": len(artifact_invocations), "work_invocation_count": work_count, "all_receipt_hashes_match": payload["all_receipt_hashes_match"]}))
