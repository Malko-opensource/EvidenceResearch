"""Capture a scoped, provider-free candidate semantic contract validation.

Only candidate source and synthetic-provider/small-CPU unit fixtures are read.
Frozen registrations, live run evidence, and private owner rows are excluded.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "work" / "c6"
OUTPUT = Path(__file__).resolve().parent
OWNED = ["evidence_research/report_semantics.py", "tests/test_historical_semantics.py", "docs/historical_semantic_resources.md"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources() -> dict:
    return {str(path.relative_to(CANDIDATE)).replace("\\", "/"): digest(path)
            for base in ("evidence_research", "tests")
            for path in sorted((CANDIDATE / base).rglob("*.py"))}


def write(name: str, value) -> None:
    target = OUTPUT / name
    if target.exists():
        raise FileExistsError(f"immutable validation output already exists: {name}")
    target.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    before = sources()
    for name in OWNED:
        target = OUTPUT / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError("immutable source snapshot already exists")
        shutil.copyfile(CANDIDATE / name, target)
    diff_command = ["git", "diff", "--no-index", "--", str(ROOT / "versions/v5-development/evidence_research/report_semantics.py"), str(CANDIDATE / OWNED[0])]
    diff = subprocess.run(diff_command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (OUTPUT / "semantic-source.diff").write_bytes(diff.stdout)
    (OUTPUT / "diff.stderr.log").write_bytes(diff.stderr)
    command = [sys.executable, "-X", "utf8", "-B", "-m", "unittest", "tests.test_historical_semantics", "tests.test_report_semantics", "-v"]
    started = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    run = subprocess.run(command, cwd=CANDIDATE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    elapsed = time.perf_counter() - clock
    (OUTPUT / "stdout.log").write_bytes(run.stdout)
    (OUTPUT / "stderr.log").write_bytes(run.stderr)
    after = sources()
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    record = {"schema_version": "scoped-candidate-semantic-validation-1", "started_utc": started,
              "command": command, "cwd": str(CANDIDATE), "returncode": run.returncode,
              "elapsed_seconds": elapsed, "python_version": sys.version,
              "source_before": before, "source_after": after, "changed_during_validation": changed,
              "sources_stable": not changed, "owned_source": {name: digest(CANDIDATE / name) for name in OWNED},
              "baseline_source": {"path": str(ROOT / "versions/v5-development/evidence_research/report_semantics.py"),
                                  "sha256": digest(ROOT / "versions/v5-development/evidence_research/report_semantics.py")},
              "scope": "targeted semantic contract fixtures only; synthetic provider formats and small trusted CPU unit executions",
              "provider_calls": 0, "research_trials": 0, "private_owner_reads": 0,
              "frozen_sources_or_records_modified": False, "whole_candidate_release_validated": False,
              "independent_peer_review": "separate read-only reviewer; this script is developer validation, not independent claim adjudication",
              "diff_command": diff_command, "diff_returncode": diff.returncode}
    write("result.json", record)
    manifest = {str(path.relative_to(OUTPUT)).replace("\\", "/"): {"bytes": path.stat().st_size, "sha256": digest(path)}
                for path in sorted(OUTPUT.rglob("*")) if path.is_file() and path.name != "manifest.json"}
    write("manifest.json", {"schema_version": "scoped-validation-files-1", "files": manifest})
    print(json.dumps({"returncode": run.returncode, "sources_stable": not changed, "changed_during_validation": changed,
                      "elapsed_seconds": elapsed, "result_path": str(OUTPUT / "result.json")}, ensure_ascii=False))
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
