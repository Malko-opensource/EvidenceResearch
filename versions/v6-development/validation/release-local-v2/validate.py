"""Reconcile successful local install; rerun suite after external audit fix only."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
RELEASE = HERE.parents[1]
PROJECT = RELEASE.parents[1]
PRIOR = RELEASE / "validation/release-local-v1"
PRIOR_PIN = "b613ac36a50e0ca524944063f2b60bc53815a798595690fb98a671381b5ce809"
RELEASE_PIN = "44941c17d0136056f97314055bcfbab77be57f4644c1c163f002a7953da9bbb7"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    if (HERE / "result.json").exists() or (HERE / "before.json").exists():
        raise FileExistsError("Preserve completed validation; use a separate revision")
    if sha(PRIOR / "result.json") != PRIOR_PIN or sha(RELEASE / "release-copy.json") != RELEASE_PIN:
        raise ValueError("Externally recorded prior/release pin differs")
    prior = json.loads((PRIOR / "result.json").read_text(encoding="utf-8"))
    for phase in prior["phases"]:
        for key in ("stdout", "stderr"):
            if sha(Path(phase[key]["path"])) != phase[key]["sha256"]:
                raise ValueError("Prior immutable raw log changed")
        if phase["phase"] != "unit-checks" and phase["exit_code"]:
            raise ValueError("Do not adopt incomplete earlier installation phases")
    copy = json.loads((RELEASE / "release-copy.json").read_text(encoding="utf-8"))
    files = {row["relative"]: row["sha256"] for row in copy["files"]}
    prior_before = json.loads((PRIOR / "before.json").read_text(encoding="utf-8"))
    protected = prior_before["protected_main_v5_package"]
    if any(sha(RELEASE / name) != digest for name, digest in files.items()) or any(sha(PROJECT / name) != digest for name, digest in protected.items()):
        raise ValueError("Protected original/copied bytes changed")
    # Only fixture roots exist. The new guard permits the exact synthetic paths,
    # and fails if any unrecognized actual study appeared meanwhile.
    runs = RELEASE / "runs"
    if runs.exists() and any(p.name != "tf" or not p.is_dir() or any(p.iterdir()) for p in runs.iterdir()):
        raise ValueError("Actual or unreconciled study artifacts exist; do not read them")
    write(HERE / "before.json", {"release": files, "protected_main_v5_package": protected,
                                 "prior_result_sha256": PRIOR_PIN, "release_copy_sha256": RELEASE_PIN})
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env["PYTHONPATH"] = str(HERE / "audit_guard")
    env["PYTHONDONTWRITEBYTECODE"] = "1"; env["PYTHONUTF8"] = "1"
    temp = PROJECT / "work/v6t2"
    if temp.exists():
        raise FileExistsError("Never replace prior fixture temp")
    temp.mkdir(parents=True)
    env["TEMP"] = str(temp); env["TMP"] = str(temp)
    env["ER_RELEASE_ROOT"] = str(RELEASE); env["ER_PROJECT_ROOT"] = str(PROJECT)
    env["ER_FIXTURE_TMP"] = str(temp); env["ER_AUDIT_GUARD_PATH"] = str(HERE / "unit-guard.json")
    command = [str(RELEASE / ".venv/Scripts/python.exe"), "-X", "utf8", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"]
    started = time.monotonic()
    completed = subprocess.run(command, cwd=RELEASE, env=env, capture_output=True)
    elapsed = time.monotonic() - started
    stdout, stderr = HERE / "unit-checks.stdout.log", HERE / "unit-checks.stderr.log"
    stdout.write_bytes(completed.stdout); stderr.write_bytes(completed.stderr)
    after = {"release": {name: sha(RELEASE / name) for name in files},
             "protected_main_v5_package": {name: sha(PROJECT / name) for name in protected}}
    write(HERE / "after.json", after)
    unchanged = after["release"] == files and after["protected_main_v5_package"] == protected
    text = completed.stderr.decode("utf-8", errors="replace")
    match = re.search(r"Ran (\d+) tests in", text)
    guard = json.loads((HERE / "unit-guard.json").read_text(encoding="utf-8"))
    forbidden_counts = {k: v for k, v in guard["counts"].items() if k != "synthetic_python_fixture_subprocesses"}
    valid = completed.returncode == 0 and unchanged and not any(forbidden_counts.values())
    result = {"kind": "independent_new_release_local_environment_validation_after_harness_correction", "valid": valid,
              "prior_failed_validation": {"path": str(PRIOR / "result.json"), "sha256": PRIOR_PIN,
                  "cause": "External audit conflated synthetic v6/runs writes with live owner reads and mishandled Windows executable=None/argv command string"},
              "reused_successful_install_phases_without_execution": [r for r in prior["phases"] if r["phase"] != "unit-checks"],
              "release_copy_sha256": RELEASE_PIN, "release_files": len(files),
              "command": command, "cwd": str(RELEASE), "exit_code": completed.returncode, "seconds": elapsed,
              "checks": int(match.group(1)) if match else None,
              "stdout": {"path": str(stdout), "sha256": sha(stdout)}, "stderr": {"path": str(stderr), "sha256": sha(stderr)},
              "unit_guard": guard, "frozen_main_v5_v6_bytes_unchanged": unchanged,
              "actual_research_model_calls": 0, "actual_research_trials": 0,
              "trusted_cpu_unit_fixtures": "included; fixture-only, not actual research trials",
              "external_dependency_downloads": 0, "upstream_network_fetch": False,
              "doctor_model_access": "Sandbox CLI reported Not logged in; authenticated live model access not assessed",
              "final_registration_executed": False, "framework_improvement_proven": False}
    write(HERE / "result.json", result)
    print(json.dumps({"valid": valid, "checks": result["checks"], "unchanged": unchanged, "guard": guard}), flush=True)
    if not valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
