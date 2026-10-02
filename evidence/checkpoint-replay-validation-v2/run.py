"""Freeze reviewed future-source inputs and replay provider-free unit checks.

The snapshot is immutable after creation and sufficient in a public clone even
when ignored work/next-version sources are absent. This is implementation
validation, never a comparative research trial or actual model run.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SNAPSHOT = OUT / "source_snapshot"
PIN = "AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "source-manifest.json"
    if not manifest_path.exists():
        future = ROOT / "work/next-version"
        source_files = list((future / "evidence_research").glob("*.py"))
        source_files.append(future / "tests/test_checkpoint_replay.py")
        source_files += [ROOT / "references/upstream" / PIN / name for name in ("ai_lab_repo.py", "agents.py", "LICENSE")]
        before = {str(path): sha(path) for path in source_files}
        records = []
        for source in source_files:
            relative = source.relative_to(ROOT)
            target = SNAPSHOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            records.append({"original_path": str(source), "snapshot_path": relative.as_posix(), "sha256": sha(target)})
        assert before == {str(path): sha(path) for path in source_files}, "Source changed during capture; keep the artifact and coordinate a new version"
        # Make this single-test snapshot independent of unrelated site packages.
        init = SNAPSHOT / "work/next-version/tests/__init__.py"
        init.write_text("", encoding="utf-8")
        records.append({"original_path": None, "snapshot_path": init.relative_to(SNAPSHOT).as_posix(),
                        "sha256": sha(init), "kind": "empty test-package marker only"})
        write(manifest_path, {"kind": "provider-free-implementation-validation-source-snapshot", "files": records,
                              "scope": "Reviewed future-source byte copies; not a final study registration"})
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in manifest["files"]:
        target = SNAPSHOT / row["snapshot_path"]
        if not target.is_file() or sha(target) != row["sha256"]:
            raise ValueError(f"Immutable validation source changed or missing: {target}")
    command = [sys.executable, "-B", "-m", "unittest", "tests.test_checkpoint_replay", "-v"]
    cwd = SNAPSHOT / "work/next-version"
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    fixture_work = ROOT / "work/crv2"
    fixture_work.mkdir(parents=True, exist_ok=True)
    environment["EVIDENCE_REPLAY_FIXTURE_TMPDIR"] = str(fixture_work)
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
    seconds = time.perf_counter() - started
    (OUT / "stdout.log").write_text(completed.stdout, encoding="utf-8")
    (OUT / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    for row in manifest["files"]:
        assert sha(SNAPSHOT / row["snapshot_path"]) == row["sha256"], "Validation mutated a captured source"
    result = {"kind": "actual_future_source_implementation_validation", "source_manifest_sha256": sha(manifest_path),
              "command": command, "cwd": str(cwd), "exit_code": completed.returncode, "elapsed_seconds": seconds,
              "actual_model_calls": 0, "provider_kind": "synthetic unit-test fixtures explicitly marked fixture_only",
              "cpu_scope": "Small fixed CPU fits are implementation unit tests, not research arm trials",
              "stdout": {"path": str(OUT / "stdout.log"), "sha256": sha(OUT / "stdout.log")},
              "stderr": {"path": str(OUT / "stderr.log"), "sha256": sha(OUT / "stderr.log")},
              "snapshot_sources_after_identical": True, "main_registered_studies_modified": False,
              "fixture_working_root": str(fixture_work),
              "prior_immutable_failure": {"path": str(OUT.parent / "checkpoint-replay-validation-v1/result.json"),
                  "sha256": sha(OUT.parent / "checkpoint-replay-validation-v1/result.json")},
              "conclusion_scope": "Transport/checkpoint correctness in these fixtures only; no framework or memory performance improvement claim"}
    write(OUT / "result.json", result)
    print(json.dumps({"result": str(OUT / "result.json"), "exit_code": completed.returncode,
                      "actual_model_calls": 0, "scope": result["conclusion_scope"]}, ensure_ascii=False))
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
