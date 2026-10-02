"""Archive an independent candidate and run component checks, without research inference.

Synthetic provider fixtures and real trusted CPU unit fixtures are distinguished
from an actual matched research study. Failed proofs are retained as new records.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate, output = args.candidate.resolve(), args.output.resolve()
    if not candidate.is_relative_to(ROOT) or not output.is_relative_to(ROOT):
        raise ValueError("Candidate and proof must stay inside this independent workspace")
    if output.exists():
        raise FileExistsError("Retain previous proofs; select a new output directory")
    files = sorted(p for p in candidate.rglob("*") if p.is_file()
                   and not any(part in (".venv", "runs", "work", "__pycache__", ".git")
                               for part in p.relative_to(candidate).parts))
    if not (candidate / "references/upstream-agentlaboratory-manifest.json").is_file():
        # The required manifest name is externally fixed by the loader, not this helper.
        manifests = list((candidate / "references").glob("*manifest*.json"))
        if not manifests:
            raise ValueError("Candidate must contain its own pinned upstream manifest")
    before = {str(p.relative_to(candidate)): sha(p) for p in files}
    frozen = sorted((ROOT / "evidence_research").glob("*.py"))
    frozen += sorted((ROOT / "versions/v5-development/evidence_research").glob("*.py"))
    frozen_before = {str(p.relative_to(ROOT)): sha(p) for p in frozen}
    output.mkdir(parents=True)
    snapshot = output / "s"
    for p in files:
        target = snapshot / p.relative_to(candidate)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    shutil.copyfile(__file__, output / "reproduce.source.py")
    command = [sys.executable, "-X", "utf8", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"]
    started = time.perf_counter()
    process = subprocess.run(command, cwd=candidate, capture_output=True, text=True, encoding="utf-8")
    elapsed = time.perf_counter() - started
    (output / "stdout.log").write_text(process.stdout, encoding="utf-8")
    (output / "stderr.log").write_text(process.stderr, encoding="utf-8")
    after = {str(p.relative_to(candidate)): sha(p) for p in files}
    frozen_after = {str(p.relative_to(ROOT)): sha(p) for p in frozen}
    count = re.search(r"Ran (\d+) tests", process.stderr)
    result = {"valid": process.returncode == 0 and before == after and frozen_before == frozen_after,
        "candidate": str(candidate), "command": command, "cwd": str(candidate),
        "exit_code": process.returncode, "checks": int(count.group(1)) if count else None,
        "execution_seconds": elapsed, "source_before": before, "source_after": after,
        "candidate_unchanged": before == after, "frozen_original_versions_unchanged": frozen_before == frozen_after,
        "frozen_before": frozen_before, "frozen_after": frozen_after,
        "source_snapshot": str(snapshot), "actual_research_model_calls": 0,
        "actual_research_trials": 0, "trusted_cpu_unit_fixtures": "included; not research trials",
        "provider_fixtures": "synthetic; not actual model evidence", "final_evaluation_executed": False,
        "framework_improvement_proven": False, "goal_complete": False,
        "reproduce": "Restore s/ to a separate short workspace with its own Python environment and run the recorded unittest command. No private study data are needed.",
        "logs": [{"path": name, "sha256": sha(output / name)} for name in ("stdout.log", "stderr.log")]}
    write(output / "result.json", result)
    print(json.dumps({k: result[k] for k in ("valid", "checks", "exit_code", "execution_seconds", "goal_complete")}))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
