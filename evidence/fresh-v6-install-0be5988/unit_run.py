"""Run exact published full unit suite in its fresh own venv with external guard."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parents[1]
CHECKOUT = HERE.parents[2] / "_er6"
RELEASE = CHECKOUT / "versions/v6-development"
GUARD_PIN = "73321bb6f5a5625e135c69cb90dda475f5bbe5f692c9d6512b64e102365fb934"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = HERE / "unit-checks.json"
    if receipt.exists():
        raise FileExistsError("Do not repeat a completed or failed full suite")
    original_guard = RELEASE / "validation/release-local-v2/audit_guard/sitecustomize.py"
    if sha(original_guard) != GUARD_PIN:
        raise ValueError("Published previously corrected guard bytes differ")
    # Keep the exact published guard and the additive original-root protection.
    raw = original_guard.read_text(encoding="utf-8")
    (HERE / "guard-original.source.py").write_bytes(original_guard.read_bytes())
    addition = '''
original_project = Path(os.environ["ER_ORIGINAL_ROOT"]).resolve()
proof_root = Path(os.environ["ER_PROOF_ROOT"]).resolve()
counts["original_project_reads"] = 0

def original_guard(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        if path.is_relative_to(original_project) and not path.is_relative_to(proof_root):
            counts["original_project_reads"] += 1
            raise AssertionError("No original project or live study/private data")

sys.addaudithook(original_guard)
'''
    folder = HERE / "audit_guard"
    folder.mkdir()
    guard_path = folder / "sitecustomize.py"
    guard_path.write_text(raw + addition, encoding="utf-8")
    temp = CHECKOUT / "t"
    if temp.exists():
        raise FileExistsError("Preserve earlier synthetic fixture temp")
    temp.mkdir()
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env["PYTHONPATH"] = str(folder)
    env["PYTHONDONTWRITEBYTECODE"] = "1"; env["PYTHONUTF8"] = "1"
    env["TEMP"] = str(temp); env["TMP"] = str(temp)
    env["ER_RELEASE_ROOT"] = str(RELEASE); env["ER_PROJECT_ROOT"] = str(CHECKOUT)
    env["ER_FIXTURE_TMP"] = str(temp); env["ER_AUDIT_GUARD_PATH"] = str(HERE / "unit-guard.json")
    env["ER_ORIGINAL_ROOT"] = str(ORIGINAL); env["ER_PROOF_ROOT"] = str(HERE)
    command = [str(RELEASE / ".venv/Scripts/python.exe"), "-X", "utf8", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"]
    started = time.monotonic()
    completed = subprocess.run(command, cwd=RELEASE, env=env, capture_output=True)
    elapsed = time.monotonic() - started
    stdout, stderr = HERE / "unit-checks.stdout.log", HERE / "unit-checks.stderr.log"
    stdout.write_bytes(completed.stdout); stderr.write_bytes(completed.stderr)
    text = completed.stderr.decode("utf-8", errors="replace")
    match = re.search(r"Ran (\d+) tests in", text)
    guard = json.loads((HERE / "unit-guard.json").read_text(encoding="utf-8"))
    forbidden = {k: v for k, v in guard["counts"].items() if k != "synthetic_python_fixture_subprocesses"}
    value = {"phase": "unit-checks", "command": command, "cwd": str(RELEASE), "seconds": elapsed,
             "exit_code": completed.returncode, "checks": int(match.group(1)) if match else None,
             "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr), "unit_guard": guard,
             "published_guard_sha256": GUARD_PIN, "external_additive_guard_sha256": sha(guard_path),
             "valid": completed.returncode == 0 and match is not None and int(match.group(1)) == 215 and not any(forbidden.values()),
             "actual_research_model_calls": 0, "actual_research_trials": 0,
             "trusted_cpu_unit_fixtures": "included; exact synthetic test suite, not new research trials"}
    receipt.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"valid": value["valid"], "checks": value["checks"], "guard": guard}), flush=True)
    if not value["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
