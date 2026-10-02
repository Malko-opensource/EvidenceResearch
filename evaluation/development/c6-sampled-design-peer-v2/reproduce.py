"""Pure sampler/control fixtures from caller-pinned snapshot. No fitting/models."""
import argparse
from contextlib import ExitStack
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(pin, forbidden_root):
    manifest_path = HERE / "source-manifest.json"
    if sha(manifest_path) != pin:
        raise ValueError("Caller-supplied external source pin differs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot = HERE / "source_snapshot"
    for name, digest in manifest["files"].items():
        if sha(snapshot / name) != digest:
            raise ValueError("Snapshot differs from pinned capture")
    sys.path.insert(0, str(snapshot))
    from evidence_research import baseline, tasks
    from tests.test_sampled_pilot import SampledDevelopmentTests
    if not Path(tasks.__file__).resolve().is_relative_to(snapshot):
        raise ValueError("Imported a different package")
    forbidden = str(Path(forbidden_root).resolve()).casefold().rstrip("\\/") + "\\"
    own = str(HERE.resolve()).casefold().rstrip("\\/") + "\\"
    counters = {"original_project_reads": 0, "subprocess_events": 0, "network_events": 0}
    def guard(event, args):
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = str(Path(args[0]).resolve()).casefold()
            if path.startswith(forbidden) and not path.startswith(own):
                counters["original_project_reads"] += 1
                raise AssertionError("Original project reads are forbidden")
        if event == "subprocess.Popen":
            counters["subprocess_events"] += 1
            raise AssertionError("No process execution")
        if event.startswith("socket."):
            counters["network_events"] += 1
            raise AssertionError("No network")
    # Imports precede this filesystem audit; no imported module reads live data.
    sys.addaudithook(guard)
    output = io.StringIO()
    with ExitStack() as stack:
        blocked = {target: stack.enter_context(patch(target, side_effect=AssertionError("Pure fixture only")))
                   for target in ("evidence_research.model.CodexProvider.complete", "evidence_research.tasks.run_task",
                                  "evidence_research.arms.run_task", "evidence_research.tasks.fit",
                                  "evidence_research.evaluation._owner_metric", "subprocess.Popen", "socket.socket")}
        stack.enter_context(patch("tempfile.tempdir", str(HERE / "fixture_tmp")))
        (HERE / "fixture_tmp").mkdir(exist_ok=True)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SampledDevelopmentTests)
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
        call_counts = {target: mocked.call_count for target, mocked in blocked.items()}
        if any(call_counts.values()):
            raise AssertionError("Unexpected model, fit, runner, network or process call")
        reference_count = len(baseline.frozen_upstream_sources())
    unchanged = all(sha(snapshot / name) == digest for name, digest in manifest["files"].items())
    proof = {"kind": "read_only_sampler_control_peer_fixture_result", "manifest_sha256": pin,
             "success": result.wasSuccessful(), "tests_run": result.testsRun,
             "failures": len(result.failures), "errors": len(result.errors),
             "fixed_upstream_reference_files": reference_count, "source_bytes_unchanged": unchanged,
             "blocked_actual_call_counts": call_counts, "guards": counters,
             "real_model_calls": 0, "research_cpu_executions": 0,
             "synthetic_owner_fixture_files_only": True,
             "limits": "Registration/control and data privacy fixtures; no statistical power, comparative improvement or actual final reproducibility claim"}
    (HERE / "test.log").write_text(output.getvalue(), encoding="utf-8")
    (HERE / "result.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof))
    if not proof["success"] or not unchanged:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--forbidden-root", required=True)
    args = parser.parse_args()
    main(args.manifest_sha256, args.forbidden_root)
