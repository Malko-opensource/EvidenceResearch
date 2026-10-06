"""Prepare expected source hashes before placing the final implementation."""
import hashlib
import json
from pathlib import Path

episode = Path(__file__).resolve().parent
python = r"C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

spec = {
    "hypothesis_id": "hyp_625dd5a9eaa14750be3e6b35103905ce",
    "change": "Reject invalid rows before latest timestamp selection by trimmed event ID; later valid input wins ties; use exact rational summation of finite float values for stable means.",
    "comparison": "The provided initial tactic compares entire rows. This candidate changes identity and validation according to the brief. No baseline pass rate is measured or claimed.",
    "data_split": {"development": "Public supplied input.csv and BRIEF.ko.md only", "evaluation": "Owner fixed independent csv-fixed-v1; cases and implementation not read"},
    "seed": 0,
    "source_version": {
        "label": "M1-C_OFF-latest-valid-event-v1",
        "files": {
            "solution.py": sha(episode / "candidate-draft.py"),
            "input.csv": sha(episode / "input.csv"),
            "task.py": sha(episode / "task.py")
        }
    },
    "metrics": ["pass_rate"],
    "criteria": [{"metric": "pass_rate", "op": ">=", "threshold": 1.0}],
    "command": [python, "task.py", "M1"],
    "cwd": str(episode),
    "artifacts": [
        {"name": "result.json", "path": "result.json"},
        {"name": "invocations.jsonl", "path": "invocations.jsonl"},
        {"name": "solution.py", "path": "solution.py"},
        {"name": "input.csv", "path": "input.csv"}
    ],
    "validator": "csv-fixed-v1",
    "task_id": "M1",
    "conditions": {"dependencies": "Python standard library only", "input_mutation": "forbidden", "memory": "C_OFF: no seeded memory, no useful initial record returned"}
}
(episode / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"spec_path": str(episode / "spec.json"), "candidate_sha256": sha(episode / "candidate-draft.py"), "source_files": spec["source_version"]["files"]}))
