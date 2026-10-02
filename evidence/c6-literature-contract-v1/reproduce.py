"""Reproduce isolated source-contract fixtures; supply the externally recorded pin."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    path = here / "source-manifest.json"
    if sha(path) != args.manifest_sha256:
        raise ValueError("Source manifest differs from the caller's external fixed pin")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    snapshot = here / "source_snapshot"
    files = {}
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        target = snapshot / relative
        if relative.is_absolute() or ".." in relative.parts or target.is_symlink() or not target.resolve().is_relative_to(snapshot.resolve()):
            raise ValueError("Snapshot source path escaped")
        if entry["path"] in files or sha(target) != entry["sha256"]:
            raise ValueError("Snapshot source bytes differ")
        files[entry["path"]] = entry["sha256"]
    # No imported module can borrow the original project or its ignored work.
    sys.path.insert(0, str(snapshot))
    buffer = io.StringIO()
    started = time.perf_counter()
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_literature_integrity_policy_c6")
    result = unittest.TextTestRunner(stream=buffer, verbosity=2).run(suite)
    (here / "contract-test.log").write_text(buffer.getvalue(), encoding="utf-8")
    for relative, expected in files.items():
        if sha(snapshot / relative) != expected:
            raise ValueError("Fixtures changed their captured sources")
    proof = {"kind": "source_contract_fixture_result", "success": result.wasSuccessful(),
        "tests_run": result.testsRun, "errors": len(result.errors), "failures": len(result.failures),
        "seconds": time.perf_counter() - started, "manifest_sha256": args.manifest_sha256,
        "snapshot_source_files": len(files), "source_bytes_unchanged": True,
        "real_model_calls": 0, "research_cpu_executions": 0,
        "fixture_guards": "Each test blocks and asserts zero provider.complete/task.run_task/subprocess/network calls",
        "scope": "Candidate contract implementation only; no comparative performance/adoption claim"}
    (here / "result.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, ensure_ascii=False))
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()
