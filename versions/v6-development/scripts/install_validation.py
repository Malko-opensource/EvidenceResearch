"""Validate a separately cloned published commit, without making model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--reconcile-completed", action="store_true",
                        help="Verify completed phase receipts without repeating their executions")
    args = parser.parse_args()
    checkout, output = args.checkout.resolve(), args.output.resolve()
    report_file = output / "report.json"
    if report_file.exists():
        report = json.loads(report_file.read_text(encoding="utf-8"))
        if report["commit"] != args.expected_commit or report["checkout"] != str(checkout):
            raise ValueError("Existing validation belongs to different conditions")
        for evidence in report["logs"]:
            if hashlib.sha256(Path(evidence["path"]).read_bytes()).hexdigest() != evidence["sha256"]:
                raise ValueError("Completed installation evidence changed")
        print(json.dumps({"valid": report["valid"], "reused_without_execution": True}))
        return
    if output.exists() and any(output.iterdir()) and not args.reconcile_completed:
        raise FileExistsError("Incomplete validation exists; reconcile its logs")
    output.mkdir(parents=True, exist_ok=True)
    git = ["git", "-c", f"safe.directory={checkout.as_posix()}"]
    commit = subprocess.run(git + ["rev-parse", "HEAD"], cwd=checkout, capture_output=True, check=True).stdout.decode().strip()
    if commit != args.expected_commit:
        raise ValueError("Cloned commit differs from published checkpoint")
    python = checkout / ".venv" / ("Scripts/python.exe" if (checkout / ".venv/Scripts").exists() else "bin/python")
    if not python.is_file():
        raise FileNotFoundError("Create a separate venv in the clone first")
    commands = [
        ("doctor", [str(python), "-m", "evidence_research", "doctor"]),
        ("upstream-acquisition", [str(python), "scripts/fetch_upstream.py"]),
        ("unit-checks", [str(python), "-m", "unittest", "discover", "-s", "tests", "-q"]),
        ("frozen-cpu-reproduction", [str(python), "evidence/core-validation-final/source-snapshot/scripts/core_validation.py", "--output", "work/frozen-install-reproduction"]),
    ]
    logs, valid = [], True
    for name, command in commands:
        prior_receipt = output / f"{name}.json"
        stdout, stderr = output / f"{name}.stdout.log", output / f"{name}.stderr.log"
        if args.reconcile_completed:
            if not prior_receipt.exists():
                raise FileNotFoundError("Phase has no durable completion receipt; refusing repetition")
            receipt = json.loads(prior_receipt.read_text(encoding="utf-8"))
            if receipt["command"] != command or receipt["cwd"] != str(checkout) or receipt["exit_code"] != 0:
                raise ValueError("Prior phase conditions or exit code differ")
            for path, key in ((stdout, "stdout_sha256"), (stderr, "stderr_sha256")):
                measured_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                if measured_hash != receipt[key]:
                    raise ValueError("Prior phase log changed")
                logs.append({"path": str(path), "sha256": measured_hash})
            print(json.dumps({"phase": name, "reconciled_without_execution": True}), flush=True)
            continue
        started = time.monotonic()
        result = subprocess.run(command, cwd=checkout, capture_output=True)
        elapsed = time.monotonic() - started
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        logs.extend({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in (stdout, stderr))
        receipt = {"name": name, "command": command, "cwd": str(checkout), "exit_code": result.returncode,
                   "elapsed_seconds": elapsed, "stdout_sha256": logs[-2]["sha256"], "stderr_sha256": logs[-1]["sha256"]}
        (output / f"{name}.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(json.dumps({"phase": name, "exit_code": result.returncode}), flush=True)
        if result.returncode:
            valid = False
            break
    reproduced = checkout / "work/frozen-install-reproduction/report.json"
    if valid:
        original = json.loads((checkout / "evidence/core-validation-final/report.json").read_text(encoding="utf-8"))
        replay = json.loads(reproduced.read_text(encoding="utf-8"))
        comparison = {"component_checks_equal": original["checks"] == replay["checks"],
                      "source_hashes_equal": original["source_hashes"] == replay["source_hashes"],
                      "observed_results_equal": original["observed"] == replay["observed"]}
        valid = all(comparison.values())
    else:
        comparison = {"status": "incomplete"}
    report = {"valid": valid, "commit": commit, "checkout": str(checkout), "logs": logs,
              "reproduction": comparison, "actual_model_calls": 0,
              "scope": "published installation and deterministic actual CPU reproduction; not B/C performance"}
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"valid": valid, "reproduction": comparison, "actual_model_calls": 0}))
    if not valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
