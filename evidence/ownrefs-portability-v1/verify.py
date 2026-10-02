"""Reproduce own-reference unit fixtures from the immutable byte snapshot.

No provider process may launch. Tiny trusted CPU fits are unit fixtures, not
research trials. The short work root avoids Windows deep-snapshot path limits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import unittest


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--blocked-ancestor", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parent
    manifest_path = evidence / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot = evidence / "source"
    work = args.work_root.resolve()
    receipt_path = args.receipt.resolve()
    if work.exists() or receipt_path.exists():
        raise FileExistsError("Preserve prior evidence; use fresh versioned work/receipt paths")
    for item in manifest["files"]:
        source = (snapshot / item["relative_path"]).resolve()
        if not source.is_relative_to(snapshot.resolve()):
            raise ValueError("Snapshot entry escaped the immutable source root")
        if sha256(source) != item["sha256"] or source.stat().st_size != item["bytes"]:
            raise ValueError("Byte snapshot differs from its source manifest")
    work.mkdir(parents=True)
    for item in manifest["files"]:
        source = snapshot / item["relative_path"]
        destination = work / item["relative_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if sha256(destination) != item["sha256"]:
            raise ValueError("Runtime snapshot copy changed bytes")
    refs = work / "references"
    upstream = json.loads((refs / "manifest.json").read_text(encoding="utf-8-sig"))
    for item in upstream["files"]:
        if sha256(work / item["path"]) != item["sha256"]:
            raise ValueError("Own-reference upstream pin changed")
    literature = json.loads((refs / "task_literature_v2.json").read_text(encoding="utf-8"))
    canonical = json.dumps(literature["records"], ensure_ascii=False,
                           sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != literature["records_sha256"]:
        raise ValueError("Own-reference literature canonical hash changed")
    blocked = [args.blocked_ancestor.resolve() / name
               for name in ("references", "evidence_research", "tests")]
    if any(work.is_relative_to(path) for path in blocked):
        raise ValueError("Runtime snapshot must be outside the blocked original directories")
    rejected = []
    provider_launches = []

    def audit(event, values):
        if event == "subprocess.Popen":
            provider_launches.append(repr(values))
            raise RuntimeError("Fixture verifier forbids launching provider subprocesses")
        if event not in {"open", "os.listdir", "os.scandir"} or not values:
            return
        value = values[0]
        if not isinstance(value, (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(value)).resolve()
        if any(path == root or path.is_relative_to(root) for root in blocked):
            rejected.append({"event": event, "path": str(path)})
            raise RuntimeError("Own-reference fixture tried to access the parent project")

    os.chdir(work)
    os.environ["EVIDENCE_REPLAY_FIXTURE_TMPDIR"] = str(work / "work/replay")
    sys.path.insert(0, str(work))
    sys.addaudithook(audit)
    modules = ("tests.test_baseline_transport_integration",
               "tests.test_context_compaction", "tests.test_checkpoint_replay")
    started = time.perf_counter()
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    elapsed = time.perf_counter() - started
    changed = [item["relative_path"] for item in manifest["files"]
               if sha256(work / item["relative_path"]) != item["sha256"]]
    loaded = {name: str(Path(sys.modules[name].__file__).resolve()) for name in modules}
    passed = result.wasSuccessful() and not rejected and not provider_launches and not changed
    receipt = {"schema_version": "ownrefs-portability-validation-1", "fixture_only": True,
        "python": sys.executable, "argv": sys.argv, "working_directory": str(work),
        "immutable_source_manifest": {"path": str(manifest_path), "sha256": sha256(manifest_path)},
        "loaded_test_modules": loaded, "own_references_root": str(refs),
        "pinned_upstream_files": len(upstream["files"]),
        "literature_records_sha256": literature["records_sha256"],
        "blocked_parent_directories": [str(path) for path in blocked],
        "blocked_parent_access_attempts": rejected, "provider_launch_attempts": provider_launches,
        "actual_model_calls": 0, "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "fixture_wall_seconds": elapsed, "changed_runtime_source_files": changed,
        "passed": passed, "scope": "Own-reference portability and transport unit fixtures only; synthetic model providers and tiny real CPU fits; not a comparative research run or final full-suite proof."}
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
