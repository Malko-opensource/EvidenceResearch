"""Read only experiment artifacts exposed by public compact CLI responses."""
import base64
import datetime
import hashlib
import json
import pathlib
import sys

own = pathlib.Path(__file__).resolve().parent
transcript_path = own / "transcript.json"
transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
run_entries = [entry for entry in transcript["entries"]
               if "run" in entry["argv"] and entry.get("response", {}).get("ok")]
entry = run_entries[-1]
record = entry["response"]["data"]["record"]
observation = {
    "label": sys.argv[1],
    "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "provenance": "Paths taken directly from latest public DEFAULT compact run response.",
    "run_id": record["run"]["id"],
    "artifacts": [],
}
execution_directory = pathlib.Path(record["run"]["execution_directory"])
execution_directory.resolve().relative_to(own)
live_invocations_path = execution_directory / "invocations.jsonl"
live_invocations = live_invocations_path.read_bytes()
observation["live_invocations"] = {
    "path": str(live_invocations_path),
    "provenance": "Public record.run.execution_directory plus preregistered invocations.jsonl artifact path.",
    "content_base64": base64.b64encode(live_invocations).decode("ascii"),
    "sha256": hashlib.sha256(live_invocations).hexdigest(),
    "actual_invocations": len([line for line in live_invocations.splitlines() if line.strip()]),
}
for artifact in record["artifacts"]:
    if artifact["name"] not in {"solution.py", "input.csv", "result.json", "invocations.jsonl"}:
        continue
    path = pathlib.Path(artifact["path"])
    path.resolve().relative_to(own)
    payload = path.read_bytes()
    item = {
        "name": artifact["name"], "path": str(path),
        "declared_sha256": artifact["sha256"],
        "actual_sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload), "content_base64": base64.b64encode(payload).decode("ascii"),
    }
    if artifact["name"] in {"invocations.jsonl", "result.json"}:
        item["text"] = payload.decode("utf-8")
    if artifact["name"] == "invocations.jsonl":
        lines = [line for line in item["text"].splitlines() if line.strip()]
        item["invocations"] = [json.loads(line) for line in lines]
        observation["actual_invocations"] = len(lines)
    observation["artifacts"].append(item)
transcript.setdefault("artifact_observations", []).append(observation)
transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in observation.items() if key != "artifacts"}, indent=2))
for item in observation["artifacts"]:
    if "text" in item:
        print(json.dumps({key: value for key, value in item.items() if key != "content_base64"}, indent=2))
