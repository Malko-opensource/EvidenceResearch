"""Run public snapshots in an isolated sibling tree with original access denied.

The child audit hook rejects every open/list/scan under the original project,
and every subprocess except the declared Python unittest subprocess. Only this
runner copies approved public evidence bytes before the guard is installed.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PUBLIC = ("checkpoint-replay-validation-v1", "checkpoint-replay-validation-v2", "resume-replay-independent-audit")

GUARD = r'''
import atexit, json, os, subprocess, sys
denied = os.path.normcase(os.path.abspath(os.environ["EVIDENCE_PORTABILITY_DENIED_PROJECT"]))
isolated = os.path.normcase(os.path.abspath(os.environ["EVIDENCE_PORTABILITY_ISOLATED_ROOT"]))
case = os.environ["EVIDENCE_PORTABILITY_CASE"]
events = []
blocked = []
def under(path, root):
    return path == root or path.startswith(root + os.sep)
def audit(event, args):
    if event in ("open", "os.listdir", "os.scandir") and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
        if under(path, denied):
            blocked.append({"event": event, "path": path})
            raise PermissionError("Original project access prohibited by portability fixture")
        if under(path, isolated):
            events.append({"event": event, "path": path})
    if event == "subprocess.Popen":
        argv = args[1]
        expected = [sys.executable, "-B", "-m", "unittest", "tests.test_checkpoint_replay", "-v"]
        valid_args = argv == expected or isinstance(argv, str) and argv == subprocess.list2cmdline(expected)
        valid_executable = args[0] is None or os.path.normcase(os.path.abspath(args[0])) == os.path.normcase(os.path.abspath(sys.executable))
        if not valid_args or not valid_executable:
            blocked.append({"event": event, "command": repr(argv)})
            raise PermissionError("Only declared provider-free unittest subprocess is allowed")
sys.addaudithook(audit)
def finish():
    path = os.path.join(os.environ["EVIDENCE_PORTABILITY_GUARD_LOG"], case + "-" + str(os.getpid()) + ".json")
    value = {"case": case, "pid": os.getpid(), "argv": sys.argv, "blocked_attempts": list(blocked),
        "owned_path_events": list(events), "guard": "Original project open/list/scan denied; only provider-free unittest subprocess permitted"}
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
atexit.register(finish)
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def public_files():
    files = []
    for name in PUBLIC[:2]:
        folder = ROOT / "evidence" / name
        files += [folder / filename for filename in ("run.py", "source-manifest.json", "result.json", "stdout.log", "stderr.log")]
        manifest = json.loads((folder / "source-manifest.json").read_text(encoding="utf-8"))
        files += [folder / "source_snapshot" / row["snapshot_path"] for row in manifest["files"]]
    folder = ROOT / "evidence" / PUBLIC[2]
    files += [folder / filename for filename in ("reproduce.py", "finding.json")]
    files += sorted((folder / "source").glob("*.py"))
    return sorted(set(files))


def main():
    source_files = public_files()
    before = {str(path.relative_to(ROOT)): sha(path) for path in source_files}
    attempts = []
    guard_receipts = []
    # This sibling remains inside the authorized workspace, while its short name
    # avoids mixing artifact storage depth with transport tests' temporary files.
    with tempfile.TemporaryDirectory(prefix="pp-", dir=ROOT.parent) as temp:
        isolated = Path(temp).resolve()
        assert isolated.is_relative_to(ROOT.parent.resolve()) and not isolated.is_relative_to(ROOT.resolve())
        for source in source_files:
            target = isolated / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            assert sha(target) == before[str(source.relative_to(ROOT))]
        absent = [isolated / relative for relative in ("work/next-version", "references", "evidence_research")]
        assert not any(path.exists() for path in absent), "Only public sidecar snapshots may enter the copy"
        guard = isolated / "guard"
        guard.mkdir()
        (guard / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
        guard_logs = isolated / "guard-logs"
        guard_logs.mkdir()
        fixture = isolated / "work/fx"
        fixture.mkdir(parents=True)
        env = dict(os.environ)
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTHONPATH=str(guard),
            EVIDENCE_PORTABILITY_DENIED_PROJECT=str(ROOT), EVIDENCE_PORTABILITY_ISOLATED_ROOT=str(isolated),
            EVIDENCE_PORTABILITY_GUARD_LOG=str(guard_logs), EVIDENCE_REPLAY_FIXTURE_TMPDIR=str(fixture))
        commands = [
            ("v2", [sys.executable, "-B", str(isolated / "evidence/checkpoint-replay-validation-v2/run.py")]),
            ("v1", [sys.executable, "-B", str(isolated / "evidence/checkpoint-replay-validation-v1/run.py")]),
            ("historical-replay", [sys.executable, "-B", str(isolated / "evidence/resume-replay-independent-audit/reproduce.py"), "--snapshot-only"]),
        ]
        for case, command in commands:
            env["EVIDENCE_PORTABILITY_CASE"] = case
            started = time.perf_counter()
            result = subprocess.run(command, cwd=isolated, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace")
            seconds = time.perf_counter() - started
            (OUT / f"{case}-stdout.log").write_text(result.stdout, encoding="utf-8")
            (OUT / f"{case}-stderr.log").write_text(result.stderr, encoding="utf-8")
            outputs = {}
            if case in ("v1", "v2"):
                folder = isolated / "evidence" / ("checkpoint-replay-validation-" + case)
                for filename in ("result.json", "stdout.log", "stderr.log"):
                    target = OUT / case / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((folder / filename).read_bytes())
                    outputs[filename] = {"path": str(target), "sha256": sha(target)}
            else:
                target = OUT / "historical-replay/portable-replay.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((isolated / "evidence/resume-replay-independent-audit/portable-replay.json").read_bytes())
                outputs["portable-replay.json"] = {"path": str(target), "sha256": sha(target)}
            attempts.append({"case": case, "command": command, "cwd": str(isolated), "exit_code": result.returncode,
                "seconds": seconds, "outputs": outputs, "isolated_live_sources_absent": [str(path) for path in absent],
                "stdout_sha256": sha(OUT / f"{case}-stdout.log"), "stderr_sha256": sha(OUT / f"{case}-stderr.log")})
        # The immutable v1 fixture predates the task-specific temp-root option.
        # Its exact bytes can also run from a shallower snapshot layout. No test
        # or implementation definition is patched; references stay in the copy.
        short_snapshot = isolated / "s"
        manifest = json.loads((isolated / "evidence/checkpoint-replay-validation-v1/source-manifest.json").read_text(encoding="utf-8"))
        for row in manifest["files"]:
            original = isolated / "evidence/checkpoint-replay-validation-v1/source_snapshot" / row["snapshot_path"]
            target = short_snapshot / row["snapshot_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
            assert sha(target) == row["sha256"]
        case = "v1-short-placement"
        command = [sys.executable, "-B", "-m", "unittest", "tests.test_checkpoint_replay", "-v"]
        env["EVIDENCE_PORTABILITY_CASE"] = case
        started = time.perf_counter()
        completed = subprocess.run(command, cwd=short_snapshot / "work/next-version", env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        seconds = time.perf_counter() - started
        (OUT / f"{case}-stdout.log").write_text(completed.stdout, encoding="utf-8")
        (OUT / f"{case}-stderr.log").write_text(completed.stderr, encoding="utf-8")
        attempts.append({"case": case, "command": command, "cwd": str(short_snapshot / "work/next-version"),
            "exit_code": completed.returncode, "seconds": seconds,
            "stdout_sha256": sha(OUT / f"{case}-stdout.log"), "stderr_sha256": sha(OUT / f"{case}-stderr.log"),
            "source_manifest_sha256": sha(isolated / "evidence/checkpoint-replay-validation-v1/source-manifest.json"),
            "scope": "Same archived13 test and implementation bytes in a shallow snapshot layout; storage location only, never current14-test semantics."})
        for source in sorted(guard_logs.glob("*.json")):
            target = OUT / "guard-logs" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            receipt = json.loads(source.read_text(encoding="utf-8"))
            guard_receipts.append({"path": str(target), "sha256": sha(target), "case": receipt["case"],
                "blocked_attempts": receipt["blocked_attempts"], "owned_path_events": len(receipt["owned_path_events"])})
        assert not any(path.exists() for path in absent), "Reproduction must not create a live source tree"
    after = {str(path.relative_to(ROOT)): sha(path) for path in source_files}
    assert before == after, "Original public source, prior findings or result changed"
    validated_cases = [row for row in attempts if row["case"] != "v1"]
    verified = all(row["exit_code"] == 0 for row in validated_cases) and not any(row["blocked_attempts"] for row in guard_receipts)
    result = {"public_reproduction_verified": verified, "prior_guard_failure_receipt": {"path": str(OUT.parent / "public-artifact-portability-v2/result.json"), "sha256": sha(OUT.parent / "public-artifact-portability-v2/result.json")}, "kind": "actual_isolated_public_artifact_reproduction", "source_files": before,
        "attempts": attempts, "guard_receipts": guard_receipts, "all_passed": all(row["exit_code"] == 0 for row in attempts),
        "original_public_bytes_before_after_identical": True, "original_live_or_ignored_source_tree_used": False,
        "actual_model_calls": 0, "main_and_current_study_modified": False,
        "scope": "Public sidecar reproductions only. Original result/finding bytes are unchanged; v1 historical failure and new short-working-directory pass are separate records. No full CLI resume or research effect validation."}
    write(OUT / "result.json", result)
    print(json.dumps({"result": str(OUT / "result.json"), "all_passed": result["all_passed"],
        "attempts": [{"case": row["case"], "exit_code": row["exit_code"]} for row in attempts],
        "blocked_attempts": sum(len(row["blocked_attempts"]) for row in guard_receipts), "public_reproduction_verified": verified, "actual_model_calls": 0}, ensure_ascii=False))
    raise SystemExit(0 if verified else 1)


if __name__ == "__main__":
    main()
