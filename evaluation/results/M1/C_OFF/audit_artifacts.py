"""Read only runner-reported evidence files; do not launch the task."""
import datetime
import hashlib
import json
import sys
from pathlib import Path

episode = Path(__file__).resolve().parent
transcript_path = episode / "transcript.json"
transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
run_commands = [entry for entry in transcript["commands"] if "run" in entry["command"] and entry.get("response", {}).get("ok")]
response = run_commands[-1]["response"]
record = response["data"]["record"]
receipt = record["run"]["receipt"]
files = []
for item in receipt["files"]:
    path = Path(item["path"])
    content = path.read_bytes()
    entry = {"name": item["name"], "path": str(path), "expected_sha256": item["sha256"], "actual_sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
    entry["matching"] = entry["actual_sha256"] == entry["expected_sha256"]
    if item["name"] in ("invocations.jsonl", "result.json", "stdout", "stderr", "launch", "process"):
        entry["original_content"] = content.decode("utf-8")
    if item["name"] == "invocations.jsonl":
        entry["invocation_count"] = len([line for line in content.decode("utf-8").splitlines() if line.strip()])
        work_path = Path(item["origin_path"])
        work_content = work_path.read_bytes()
        entry["work_path"] = str(work_path)
        entry["work_invocation_count"] = len([line for line in work_content.decode("utf-8").splitlines() if line.strip()])
        entry["work_sha256"] = hashlib.sha256(work_content).hexdigest()
    files.append(entry)
audit = {"action": "audit preserved artifacts without executing task", "label": sys.argv[1], "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "registration_id": record["registration"]["id"], "run_id": record["run"]["id"], "started": response["data"]["started"], "files": files, "all_hashes_match": all(item["matching"] for item in files)}
path = episode / f"artifact-audit-{sys.argv[1]}.json"
path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
transcript.setdefault("artifact_audits", []).append({"path": str(path), "audit": audit})
transcript["evidence_paths"] = sorted(set(transcript["evidence_paths"] + [item["path"] for item in files]))
transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"audit_path": str(path), "run_id": audit["run_id"], "started": audit["started"], "all_hashes_match": audit["all_hashes_match"], "invocations": [item for item in files if item["name"] == "invocations.jsonl"], "result": [item for item in files if item["name"] == "result.json"]}))
