"""Place the already registered source bytes, recording deployment evidence."""
import datetime
import hashlib
import json
from pathlib import Path

episode = Path(__file__).resolve().parent
spec = json.loads((episode / "spec.json").read_text(encoding="utf-8"))
candidate = (episode / "candidate-draft.py").read_bytes()
expected = spec["source_version"]["files"]["solution.py"]
actual = hashlib.sha256(candidate).hexdigest()
assert actual == expected
initial = episode / "initial-solution.py"
assert not initial.exists()
initial.write_bytes((episode / "solution.py").read_bytes())
(episode / "solution.py").write_bytes(candidate)
record = {
    "action": "place preregistered candidate bytes", "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "registration_id": "reg_8d5f6ae9a92443d2abd148aa8338efe1",
    "candidate_path": str(episode / "candidate-draft.py"), "solution_path": str(episode / "solution.py"),
    "initial_solution_path": str(initial), "expected_sha256": expected,
    "actual_sha256": hashlib.sha256((episode / "solution.py").read_bytes()).hexdigest(),
    "matching": actual == expected
}
(episode / "deployment.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
transcript_path = episode / "transcript.json"
transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
transcript.setdefault("events", []).append(record)
transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
