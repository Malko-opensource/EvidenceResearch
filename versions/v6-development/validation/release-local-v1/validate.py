"""Fresh local release environment checks; no external publication or research."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
RELEASE = HERE.parents[1]
PROJECT = RELEASE.parents[1]
BUNDLED = Path(r"C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
RELEASE_COPY_PIN = "44941c17d0136056f97314055bcfbab77be57f4644c1c163f002a7953da9bbb7"
COMPONENT_PROOF_PIN = "e3698eafeff2f63654b6ba3b7d97dd1dbb565ccbb85de4dcf001044b2ba6649d"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    if (HERE / "result.json").exists() or (HERE / "before.json").exists():
        raise FileExistsError("Preserve previous logs; do not repeat completed validation")
    copy_path = RELEASE / "release-copy.json"
    if sha(copy_path) != RELEASE_COPY_PIN:
        raise ValueError("Externally supplied release-copy pin differs")
    copy = json.loads(copy_path.read_text(encoding="utf-8"))
    component = PROJECT / copy["component_proof"]["path"]
    if copy["component_proof"]["sha256"] != COMPONENT_PROOF_PIN or sha(component) != COMPONENT_PROOF_PIN:
        raise ValueError("Parent component proof differs")
    files = {row["relative"]: row["sha256"] for row in copy["files"]}
    if len(files) != 101 or any(sha(RELEASE / name) != digest for name, digest in files.items()):
        raise ValueError("Release no longer equals the reviewed exact copy")
    protected = {}
    for folder in (PROJECT / "evidence_research", PROJECT / "versions/v5-development/evidence_research"):
        for path in folder.glob("*.py"):
            protected[path.relative_to(PROJECT).as_posix()] = sha(path)
    before = {"release": files, "protected_main_v5_package": protected,
              "release_copy_sha256": RELEASE_COPY_PIN, "component_proof_sha256": COMPONENT_PROOF_PIN}
    write(HERE / "before.json", before)
    venv = RELEASE / ".venv"
    if venv.exists():
        raise FileExistsError("New non-system venv must not replace an existing environment")
    clean = os.environ.copy()
    clean.pop("PYTHONPATH", None)
    clean.pop("PYTHONHOME", None)
    clean["PYTHONDONTWRITEBYTECODE"] = "1"
    clean["PYTHONUTF8"] = "1"
    clean["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    phase_receipts = []
    def phase(name, command, env=None):
        started = time.monotonic()
        result = subprocess.run(command, cwd=RELEASE, env=env or clean, capture_output=True)
        elapsed = time.monotonic() - started
        stdout, stderr = HERE / f"{name}.stdout.log", HERE / f"{name}.stderr.log"
        stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
        receipt = {"phase": name, "command": list(map(str, command)), "cwd": str(RELEASE),
                   "exit_code": result.returncode, "seconds": elapsed,
                   "stdout": {"path": str(stdout), "sha256": sha(stdout)},
                   "stderr": {"path": str(stderr), "sha256": sha(stderr)}}
        write(HERE / f"{name}.json", receipt)
        phase_receipts.append(receipt)
        print(json.dumps({"phase": name, "exit_code": result.returncode, "seconds": elapsed}), flush=True)
        return result
    created = phase("venv-create", [str(BUNDLED), "-X", "utf8", "-B", "-m", "venv", str(venv)])
    python = venv / "Scripts/python.exe"
    if created.returncode:
        raise RuntimeError("Venv creation failed; preserve its receipt")
    package_info = phase("environment", [str(python), "-X", "utf8", "-B", "-c",
        'import json,sys,site;print(json.dumps({"python":sys.version,"executable":sys.executable,"prefix":sys.prefix,"base_prefix":sys.base_prefix,"system_site_packages":site.ENABLE_USER_SITE}))'])
    references = phase("fixed-upstream", [str(python), "-X", "utf8", "-B", "-c",
        'import json;from evidence_research.baseline import frozen_upstream_sources;f=frozen_upstream_sources();print(json.dumps({"fixed_files":len(f),"network_acquisition":False,"files":f}))'])
    if references.returncode:
        raise RuntimeError("Fixed upstream validation failed; no install/tests")
    build_env = clean.copy()
    build_env["PYTHONPATH"] = str(BUNDLED.parent / "Lib/site-packages")
    install = phase("offline-editable-install", [str(python), "-X", "utf8", "-B", "-m", "pip", "--isolated",
        "install", "--no-index", "--no-deps", "--no-build-isolation", "--editable", "."], build_env)
    phase("installed-environment", [str(python), "-X", "utf8", "-B", "-c",
        'import json,sys,importlib.metadata as m,evidence_research;print(json.dumps({"prefix":sys.prefix,"base_prefix":sys.base_prefix,"package_path":evidence_research.__file__,"package_version":m.version("evidence-research")}))'])
    doctor = phase("doctor", [str(python), "-X", "utf8", "-B", "-m", "evidence_research", "doctor"])
    unit_env = clean.copy()
    unit_env["PYTHONPATH"] = str(HERE / "audit_guard")
    temp = PROJECT / "work/v6t"
    if temp.exists():
        raise FileExistsError("Keep prior synthetic fixture temp unchanged")
    temp.mkdir(parents=True)
    unit_env["TEMP"] = str(temp); unit_env["TMP"] = str(temp)
    unit_env["ER_RELEASE_ROOT"] = str(RELEASE)
    unit_env["ER_PROJECT_ROOT"] = str(PROJECT)
    unit_env["ER_FIXTURE_TMP"] = str(temp)
    unit_env["ER_AUDIT_GUARD_PATH"] = str(HERE / "unit-guard.json")
    tests = phase("unit-checks", [str(python), "-X", "utf8", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], unit_env)
    after = {"release": {name: sha(RELEASE / name) for name in files},
             "protected_main_v5_package": {name: sha(PROJECT / name) for name in protected}}
    write(HERE / "after.json", after)
    unchanged = after["release"] == files and after["protected_main_v5_package"] == protected
    guard = json.loads((HERE / "unit-guard.json").read_text(encoding="utf-8")) if (HERE / "unit-guard.json").exists() else None
    report = {"kind": "independent_new_release_local_environment_validation", "valid": all(r["exit_code"] == 0 for r in phase_receipts) and unchanged,
              "release_copy_sha256": RELEASE_COPY_PIN, "component_proof_sha256": COMPONENT_PROOF_PIN,
              "release_files": len(files), "frozen_main_v5_v6_bytes_unchanged": unchanged,
              "phases": phase_receipts, "unit_guard": guard,
              "actual_research_model_calls": 0, "actual_research_trials": 0,
              "trusted_cpu_unit_fixtures": "included; fixture-only tests, no new research trials",
              "external_dependency_downloads": 0, "upstream_network_fetch": False,
              "editable_packaging_tool_scope": "Bundled runtime site-packages are exposed only during offline installer execution; removed for runtime doctor and full tests",
              "final_registration_executed": False, "framework_improvement_proven": False}
    write(HERE / "result.json", report)
    print(json.dumps({"valid": report["valid"], "unchanged": unchanged, "unit_exit_code": tests.returncode,
                      "actual_research_model_calls": 0}), flush=True)
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
