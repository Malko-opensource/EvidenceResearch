"""Deferred fresh-public-checkout engineering validation, never clone/network.

Default action only prints the plan. A separately pinned parent contract and new
public commit are required for any checkout reads or environment/test execution.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
EXPECTED_SOURCE_PIN = "cf3dce0b8b81c885de0e7c813827b30b36dda997eef8ec76d987fe804c117977"
EXPECTED_UPSTREAM_PIN = "f852a10e1f67f4518344e7ec15ae4ff1379d1300dc9936ccc8c236bfe43c1a66"
EXPECTED_INDEPENDENT_PIN = "2368762de07766643e6cdcd7461ea3448c93028cac9491bae5c1a6c4224f8694"
CHECKOUT = HERE.parents[2] / "_er7"
ORIGINAL = HERE.parents[1]
BUNDLED = Path(r"C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def new_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def safe(root, text):
    p = PurePosixPath(text)
    if not p.parts or p.is_absolute() or ".." in p.parts or p.as_posix() != text or ":" in text or "\\" in text:
        raise ValueError("Invalid canonical relative path")
    root = root.absolute();node = root
    for part in (None, *p.parts):
        if part is not None:node = node / part
        if node.is_symlink() or (hasattr(node, "is_junction") and node.is_junction()):
            raise ValueError("No symlink/junction indirection in checkout/evidence")
    if not node.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes root")
    return node


def pinned_metadata():
    paths = {"expected-source71.json": EXPECTED_SOURCE_PIN,
             "expected-upstream35.json": EXPECTED_UPSTREAM_PIN,
             "expected-independent84.json": EXPECTED_INDEPENDENT_PIN}
    for relative, digest in paths.items():
        if sha(HERE / relative) != digest:
            raise ValueError("Externally fixed metadata changed")
    return tuple(load(HERE / name) for name in paths)


def contract(args, action):
    if not args.go or not args.go_sha256 or not args.public_commit:
        raise ValueError("Separate parent GO, external contract SHA and exact new public commit required")
    if sha(args.go) != args.go_sha256:
        raise ValueError("External parent-contract SHA differs")
    go = load(args.go)
    if (re.fullmatch("[0-9a-f]{40}", args.public_commit) is None or go.get("new_public_commit") != args.public_commit
            or go.get("kind") != "fresh_public_version7_engineering_execution_contract"
            or Path(go.get("checkout_root", "")).absolute() != CHECKOUT
            or go.get("parent_verified_new_checkout_was_absent_before_clone") is not True
            or go.get("no_actual_research_or_credential_access") is not True
            or action not in go.get("actions", [])
            or go.get("source71_sha256") != EXPECTED_SOURCE_PIN
            or go.get("upstream35_sha256") != EXPECTED_UPSTREAM_PIN
            or go.get("independent84_sha256") != EXPECTED_INDEPENDENT_PIN):
        raise ValueError("Parent contract does not cover exact fresh public scope")
    if (go.get("helper_sha256") != sha(Path(__file__))
            or go.get("guard_sha256") != sha(HERE / "audit_guard.py")):
        raise ValueError("External parent contract does not pin the exact prepared helper/guard")
    if go.get("template_is_not_authorization") is True:
        raise ValueError("Template cannot authorize execution")
    return go


def verify_checkout(args, go):
    source, upstream, _ = pinned_metadata()
    release = CHECKOUT / "versions/v7-development"
    if safe(CHECKOUT, ".git/HEAD").read_text(encoding="ascii").strip() != args.public_commit:
        raise ValueError("Expected new exact detached public HEAD")
    reference = go["parent_checkout_receipt"]
    receipt_path = Path(reference["path"])
    if not receipt_path.absolute().is_relative_to(HERE) or sha(receipt_path) != reference["sha256"]:
        raise ValueError("Root checkout receipt must be externally pinned in this fresh proof directory")
    receipt = load(receipt_path)
    if (receipt.get("kind") != "parent_public_source_gitblob_checkout_v1"
            or receipt.get("commit") != args.public_commit
            or Path(receipt.get("checkout_root", "")).absolute() != CHECKOUT
            or receipt.get("source_selection") != "public_v7_source71"
            or receipt.get("new_checkout_created") is not True
            or receipt.get("existing_checkout_replaced") is not False):
        raise ValueError("Unmatched or reused root checkout")
    indexed = {row["relative"]: row for row in receipt["public_source_files"]}
    if len(indexed) != 71 or set(indexed) != {row["relative"] for row in source["files"]}:
        raise ValueError("Parent Git-blob inventory differs from exact public source71")
    before = {}
    for row in source["files"]:
        path = safe(release, row["relative"]);raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        git = indexed[row["relative"]]
        if (digest != row["sha256"] or len(raw) != row["bytes"] or git["sha256"] != digest
                or git["bytes"] != len(raw) or git["git_blob_sha1"] != blob):
            raise ValueError("External public commit/source pins disagree: " + row["relative"])
        before[row["relative"]] = {"sha256": digest, "git_blob_sha1": blob}
    fetched = go["parent_fixed_upstream_acquisition_receipt"]
    fp = Path(fetched["path"])
    if not fp.absolute().is_relative_to(HERE) or sha(fp) != fetched["sha256"]:
        raise ValueError("New own public fetch receipt is missing or changed")
    fetch = load(fp)
    if (fetch.get("kind") != "parent_fixed_public_upstream35_acquisition_v1"
            or Path(fetch.get("checkout_root", "")).absolute() != CHECKOUT
            or fetch.get("new_own_acquisition") is not True or fetch.get("fixed_source35") != upstream["files"]):
        raise ValueError("Old/unmatched upstream acquisition cannot satisfy new checkout")
    for relative, digest in upstream["files"].items():
        if sha(safe(release, relative)) != digest:
            raise ValueError("Fixed public upstream source differs")
        before[relative] = {"sha256": digest, "git_blob_sha1": None}
    if len(before) != 106:
        raise ValueError("Expected public71 plus new own original35")
    return before


def clean_env(venv, temporary):
    # Read only conventional non-secret OS path fields; do not copy credential
    # variables or the running research process's complete environment.
    names = ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "PROCESSOR_ARCHITECTURE",
             "NUMBER_OF_PROCESSORS", "USERPROFILE", "LOCALAPPDATA", "APPDATA")
    env = {name: os.environ[name] for name in names if name in os.environ}
    windows = env.get("SystemRoot", r"C:\Windows")
    env.update(PATH=os.pathsep.join((str(venv / "Scripts"), windows, str(Path(windows) / "System32"))),
               PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PIP_DISABLE_PIP_VERSION_CHECK="1",
               TEMP=str(temporary), TMP=str(temporary))
    return env


def validate(args, go):
    before = verify_checkout(args, go)
    release = CHECKOUT / "versions/v7-development"
    proof = HERE / "fresh-public-run-v1"
    if proof.exists() or (release / ".venv").exists() or (release / "runs").exists():
        raise FileExistsError("Never reuse/replace a previous installation, proof or actual/unknown runs")
    proof.mkdir();venv = release / ".venv"
    temporary = CHECKOUT.parent / ("_t7p" + args.public_commit[:8])
    if temporary.exists():
        raise FileExistsError("Keep previous fixture output; choose a newly approved contract")
    temporary.mkdir()
    env = clean_env(venv, temporary)
    new_json(proof / "before.json", {"commit": args.public_commit, "source106": before,
                                    "go_sha256": args.go_sha256})
    phases = []
    unit_executed = False
    def phase(name, command, environment=None):
        started = time.monotonic()
        result = subprocess.run(command, cwd=release, env=environment or env, capture_output=True)
        stdout, stderr = proof / (name + ".stdout.log"), proof / (name + ".stderr.log")
        stdout.write_bytes(result.stdout);stderr.write_bytes(result.stderr)
        row = {"phase": name, "command": command, "cwd": str(release), "exit_code": result.returncode,
               "seconds": time.monotonic()-started, "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr)}
        new_json(proof / (name + ".json"), row);phases.append(row)
        print(json.dumps({"phase": name, "exit_code": result.returncode}), flush=True)
        if result.returncode:
            raise RuntimeError("Preserve failed phase and do not repeat earlier successes: " + name)
        return result
    outcome = {"valid": False}
    try:
        phase("new-own-venv", [str(BUNDLED), "-X", "utf8", "-B", "-m", "venv", str(venv)])
        python = venv / "Scripts/python.exe"
        build = env.copy();build["PYTHONPATH"] = str(BUNDLED.parent / "Lib/site-packages")
        phase("offline-editable", [str(python), "-X", "utf8", "-B", "-m", "pip", "--isolated", "install",
              "--no-index", "--no-deps", "--no-build-isolation", "--editable", "."], build)
        installed = phase("own-environment", [str(python), "-X", "utf8", "-B", "-c",
            'import json,sys,site,importlib.metadata as m,evidence_research;print(json.dumps({"prefix":sys.prefix,"base_prefix":sys.base_prefix,"user_site":site.ENABLE_USER_SITE,"version":m.version("evidence-research"),"package":evidence_research.__file__}))'])
        info = json.loads(installed.stdout)
        if (Path(info["prefix"]).resolve() != venv.resolve() or info["user_site"] is not False
                or info["prefix"] == info["base_prefix"] or info["version"] != "0.4.0.dev0"
                or not Path(info["package"]).resolve().is_relative_to(release.resolve())):
            raise ValueError("Not the own installed runtime/package")
        phase("fixed-reference-closure", [str(python), "-X", "utf8", "-B", "-c",
            'from evidence_research.baseline import frozen_upstream_sources;assert len(frozen_upstream_sources())==36;print("own fixed upstream36 validated; authored facts2 externally hashed")'])
        phase("cli-help-no-auth", [str(python), "-X", "utf8", "-B", "-m", "evidence_research", "--help"])
        guard_dir = proof / "audit_guard";guard_dir.mkdir()
        (guard_dir / "sitecustomize.py").write_bytes((HERE / "audit_guard.py").read_bytes())
        guarded = env.copy();guarded.update(PYTHONPATH=str(guard_dir), ER_FRESH_CHECKOUT=str(CHECKOUT),
             ER_PREP_PROOF=str(HERE), ER_FIXTURE_TMP=str(temporary), ER_ORIGINAL_PROJECT=str(ORIGINAL),
             ER_RUNTIME_ROOT=str(BUNDLED.parent), ER_GUARD_RECEIPT=str(proof / "unit-guard.json"))
        unit_executed = True
        unit = phase("full263", [str(python), "-X", "utf8", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], guarded)
        match = re.search(r"Ran (\d+) tests in", unit.stderr.decode("utf-8", errors="replace"))
        if match is None or int(match.group(1)) != 263:
            raise ValueError("Unexpected public-source test inventory")
        audit = load(proof / "unit-guard.json")
        if any(v for k,v in audit["counts"].items() if k != "allowed_cpu_fixture_subprocesses"):
            raise ValueError("Forbidden event in fresh public full-suite guard")
        outcome = {"valid": True, "checks": 263, "environment": info, "guard": audit,
                   "captured38_executed": False}
        if args.replay38:
            permission = go.get("optional_replay38", {})
            if (permission.get("enabled") is not True or "replay38" not in go["actions"]
                    or permission.get("justification") != "fresh_public_captured_source_portability"):
                raise ValueError("Separate justified fresh-public portability GO required for captured38")
            _, _, subset = pinned_metadata()
            # Only the complete replay closure is opened. Supplementary legacy
            # sidecars are outside this execution/reproduction claim.
            for row in subset["files"][:74]:
                if sha(safe(CHECKOUT, row["path"])) != row["sha256"]:
                    raise ValueError("Published captured-source original closure differs")
            capsule = CHECKOUT / "work/c7-independent-validation-v1/held-source-run-0003"
            replay_env = guarded.copy();replay_env["ER_GUARD_RECEIPT"] = str(proof / "captured38-guard.json")
            phase("captured38-fresh-public", [str(python), "-X", "utf8", "-B", str(capsule / "fixture-snapshot/reproduce_components.py"),
                  "--capsule", str(capsule), "--output", str(temporary / "captured38")], replay_env)
            component = load(temporary / "captured38/result.json")
            component_guard = load(proof / "captured38-guard.json")
            if (component["status"] != "pass" or component["tests_run"] != 38 or component["actual_provider_calls"] != 0
                    or any(component_guard["counts"].values())):
                raise ValueError("Captured-source portability check did not pass")
            outcome.update(captured38_executed=True, captured38_result_sha256=sha(temporary / "captured38/result.json"),
                           captured38_checks=38, captured38_scope="Fixed archived source/tiny synthetic components only; no supplementary5 portable claim")
    except BaseException as error:
        outcome = {"valid": False, "failure": {"type": type(error).__name__, "message": str(error)},
                   "successful_phases_must_not_be_repeated": [p["phase"] for p in phases if p["exit_code"] == 0]}
    after = {}
    for relative in before:
        path = safe(release, relative);raw=path.read_bytes()
        after[relative] = {"sha256": hashlib.sha256(raw).hexdigest(),
                           "git_blob_sha1": hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
                            if before[relative]["git_blob_sha1"] is not None else None}
    new_json(proof / "after.json", {"source106": after})
    outcome.update(kind="fresh_public_version7_own_install_engineering_validation", public_commit=args.public_commit,
                   source_variant="published71 plus newly authenticated own upstream35; optional legacy2 absent",
                   phases=phases, source106_unchanged=before == after, full_suite_executed_once=unit_executed,
                   credentials_or_actual_model_execution=False, owner_sealed_research_reads=False,
                   actual_research_trials=0, registration=False, git_or_network_executed_by_helper=False,
                   doctor_authentication="Not invoked; CLI help and own environment only",
                   bundled_build_tools="Installer-only PYTHONPATH, removed from runtime/tests",
                   fixture_scope="Synthetic unit data/tiny CPU components; no existing owner rows/seeds or actual task dataset",
                   framework_improvement_proven=False, goal_complete=False)
    outcome["valid"] = outcome["valid"] and outcome["source106_unchanged"]
    new_json(proof / "result.json", outcome)
    return outcome


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "verify", "validate"), nargs="?", default="plan")
    parser.add_argument("--go", type=Path);parser.add_argument("--go-sha256");parser.add_argument("--public-commit")
    parser.add_argument("--replay38", action="store_true")
    args=parser.parse_args()
    if args.action == "plan":
        print(json.dumps({"preparation_only": True, "new_public_commit_required": True,
                          "checkout": str(CHECKOUT), "clone_fetch_env_install_tests": 0,
                          "expected_public_source71_sha256": EXPECTED_SOURCE_PIN}, indent=2));return
    go=contract(args, "verify_checkout" if args.action=="verify" else "validate263")
    value={"valid":True,"source106":verify_checkout(args,go)} if args.action=="verify" else validate(args,go)
    print(json.dumps(value,indent=2))
    if value.get("valid") is False:raise SystemExit(1)


if __name__ == "__main__":main()
