"""Prospective v7 engineering release helpers; inspect is the only default action.

Copy/install require a separately supplied execution contract after the parent's
go signal. That contract is a checked scope record, not authentication of a human.
This helper never starts providers, registers studies, or executes research tasks.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import tomllib

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
BASIS_BEFORE_SHA = "a2a4eaf635c8618a8ca45f8b6686059554a7b31058f0a9571dc5c9cf4dbe8bd0"
BASIS_RESULT_SHA = "805f3d0adea4cdf2f868a923feb13d33f528a53484a40a4da195f18781182e2b"
UPSTREAM_MANIFEST_SHA = "2b02fc8f6d2fef3f46758cb2e6855686371c94ac055298badf7d2f8970c3587f"
FACT_REGISTRY_SHA = "54217c18c38a544c9ee1094eb772170914d3f0277f9ba88ffd4192d236344907"
FACT_CORPUS_SHA = "64d0f27c0faae3d18fb4a57e24de80c2612ee0785936ddfa79f754aa91c6e5c9"
SEMANTIC_SOURCE_SHA = "bcfb3dc95facb0eeaec52ee5587c512a654a0aebc2316ff9f4ef98c53b06e529"
VERSION = "0.4.0.dev0"
BUNDLED = Path(r"C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
DOCUMENT_OVERRIDES = {"README.md": "README.md",
                      "docs/c7_development_status.ko.md": "c7_development_status.ko.md"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def new_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def checked_relative(text: str) -> Path:
    p = PurePosixPath(text)
    if (not isinstance(text, str) or not p.parts or p.is_absolute()
            or p.as_posix() != text or ".." in p.parts or "\\" in text or ":" in text
            or any(part.endswith((".", " ")) for part in p.parts)):
        raise ValueError("Noncanonical or escaping source path")
    return Path(*p.parts)


def checked_path(root: Path, relative: str) -> Path:
    root = root.absolute()
    relative_path = checked_relative(relative)
    path = root / relative_path
    node = root
    for part in (None, *relative_path.parts):
        if part is not None:
            node = node / part
        if node.is_symlink() or (hasattr(node, "is_junction") and node.is_junction()):
            raise ValueError("Source/target paths may not use symlinks or junctions")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Source path escapes root")
    return path


def literal_constants(path: Path) -> dict:
    values = {}
    for statement in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(statement, ast.Assign):
            for name in statement.targets:
                if isinstance(name, ast.Name):
                    try:
                        values[name.id] = ast.literal_eval(statement.value)
                    except (ValueError, TypeError):
                        pass
    return values


def expected_files() -> dict[str, str]:
    before, result = HERE / "pins/before.json", HERE / "pins/result.json"
    if sha(before) != BASIS_BEFORE_SHA or sha(result) != BASIS_RESULT_SHA:
        raise ValueError("Pinned parent proof/inventory bytes changed")
    r = load(result)
    if not (r["valid"] is True and r["checks"] == 263 and r["candidate_unchanged"] is True
            and r["protected_sources_unchanged"] is True):
        raise ValueError("Source basis is not the recorded engineering pass")
    files = load(before)["candidate"]
    if len(files) != 108:
        raise ValueError("Source basis must contain exactly 108 pinned files")
    for relative, digest in files.items():
        checked_relative(relative)
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Invalid expected digest")
    return files


def inspect_basis(root: Path, *, exact_inventory: bool = True, approved_document_overrides: dict | None = None) -> dict:
    files = expected_files()
    if approved_document_overrides:
        files = {**files, **{r: row["sha256"] for r, row in approved_document_overrides.items()}}
    root = root.absolute()
    for relative, digest in files.items():
        if sha(checked_path(root, relative)) != digest:
            raise ValueError("Source differs from external reviewed basis: " + relative)
    if exact_inventory:
        actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        if actual != set(files):
            raise ValueError("Source root inventory has additions or omissions")
    package = [r for r in files if r.startswith("evidence_research/") and r.endswith(".py")]
    if len(package) != 20 or sha(root / "evidence_research/report_semantics.py") != SEMANTIC_SOURCE_SHA:
        raise ValueError("Expected package20/semantic source changed")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if project["project"]["version"] != VERSION or project["project"]["dependencies"] != []:
        raise ValueError("Version or standard-library runtime dependency contract differs")
    sem = literal_constants(root / "evidence_research/report_semantics.py")
    baseline = literal_constants(root / "evidence_research/baseline.py")
    if (sem["FACT_REGISTRY_SHA256"] != FACT_REGISTRY_SHA
            or sem["FACT_CORPUS_SHA256"] != FACT_CORPUS_SHA
            or baseline["UPSTREAM_MANIFEST_SHA256"] != UPSTREAM_MANIFEST_SHA):
        raise ValueError("External reference hardpins disagree with implementation")
    for relative, digest in {"references/manifest.json": UPSTREAM_MANIFEST_SHA,
                             "references/source_facts_c7.json": FACT_REGISTRY_SHA,
                             "references/task_literature_v2.json": FACT_CORPUS_SHA}.items():
        if files[relative] != digest:
            raise ValueError("Reference hardpin differs")
    manifest = load(root / "references/manifest.json")
    entries = [row for row in manifest["files"] if "upstream_path" in row]
    if len(entries) != 35 or manifest["upstream_commit"] != baseline["UPSTREAM_COMMIT"]:
        raise ValueError("Expected pinned original source35/commit differs")
    for row in entries:
        raw = checked_path(root, row["path"]).read_bytes()
        blob = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
        if (files[row["path"]] != row["sha256"] or len(raw) != row["bytes"]
                or hashlib.sha1(blob).hexdigest() != row["git_blob_sha1"]):
            raise ValueError("Pinned upstream byte length/Git blob differs")
    for module, digest in baseline["UPSTREAM_MODULE_SHA256"].items():
        relative = "references/upstream/AgentLaboratory-" + baseline["UPSTREAM_COMMIT"] + "/" + module + ".py"
        if files[relative] != digest:
            raise ValueError("Pinned original executable module differs")
    return {"kind": "version7_release_preparation_source_inspection", "valid": True,
            "source_files": len(files), "package_modules": len(package), "reference_closure_files": 38,
            "references_directory_files": sum(r.startswith("references/") for r in files),
            "version": VERSION, "before_sha256": BASIS_BEFORE_SHA, "whole_suite_result_sha256": BASIS_RESULT_SHA,
            "whole_suite_checks": 263, "semantic_source_sha256": SEMANTIC_SOURCE_SHA,
            "source_root": str(root), "independent_case_review_completed": False,
            "version_copy_executed": False, "new_environment_installation_validated": False,
            "actual_model_calls": 0, "research_trials": 0, "study_registration": False,
            "document_overrides": list(approved_document_overrides or {}),
            "source_hash_scope": "Externally pinned 108-file engineering basis, with explicitly permitted derived document overrides only; no runtime imports"}


def check_go(path: Path, expected: str, action: str, target: Path) -> dict:
    if sha(path) != expected:
        raise ValueError("Externally supplied go-contract pin differs")
    go = load(path)
    if (go.get("kind") != "version7_release_execution_contract" or go.get("basis_before_sha256") != BASIS_BEFORE_SHA
            or go.get("independent_case_review_complete") is not True or action not in go.get("actions", [])
            or Path(go.get("target", "")).absolute() != target.absolute()
            or go.get("no_actual_research") is not True):
        raise ValueError("Execution scope contract does not cover this action/target/source")
    review = go.get("independent_review", {})
    if not review.get("path") or sha(Path(review["path"])) != review.get("sha256"):
        raise ValueError("Go contract must link an immutable completed independent review")
    # Shape/hash scope is checked. Reviewer identity and the go signal are external
    # trusted session decisions; writing this JSON alone does not authenticate them.
    return go


def document_overrides(go: dict) -> dict:
    rows = go.get("document_overrides", [])
    if not isinstance(rows, list):
        raise ValueError("Document overrides must be a list")
    original = expected_files()
    result = {}
    for row in rows:
        relative = row.get("relative")
        if relative not in DOCUMENT_OVERRIDES or relative in result:
            raise ValueError("Only the two named publication-scope documents may be overridden once")
        path = HERE / "public-docs" / DOCUMENT_OVERRIDES[relative]
        if (row.get("basis_sha256") != original[relative] or row.get("source_path") != str(path)
                or row.get("qualification") != "publication_scope_derived_documentation"
                or sha(path) != row.get("sha256")):
            raise ValueError("Derived document provenance/hash/path differs from explicit go contract")
        result[relative] = row
    return result


def check_target(target: Path) -> None:
    target = target.absolute()
    if target != PROJECT / "versions/v7-development":
        raise ValueError("This preparation helper is restricted to the new v7 release path")
    checked_path(PROJECT, target.relative_to(PROJECT).as_posix())


def copy_release(args) -> dict:
    target = args.target.absolute()
    check_target(target)
    go = check_go(args.go_receipt, args.go_sha256, "copy", target)
    overrides = document_overrides(go)
    inspect_basis(args.basis)
    if target.exists():
        raise FileExistsError("Never replace or merge a prior release")
    files = expected_files()
    output_files = {**files, **{r: row["sha256"] for r, row in overrides.items()}}
    stage = target.parent / ("v7-stage-" + BASIS_BEFORE_SHA[:12])
    if stage.exists():
        raise FileExistsError("Preserve unfinished staging directory for reconciliation")
    stage.mkdir(parents=True)
    for relative in files:
        dest = checked_path(stage, relative)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as stream:
            source = Path(overrides[relative]["source_path"]) if relative in overrides else checked_path(args.basis, relative)
            stream.write(source.read_bytes())
    inspect_basis(stage, approved_document_overrides=overrides)
    receipt = {"kind": "version7_development_code_exact_document_derived_release_copy", "basis_before_sha256": BASIS_BEFORE_SHA,
               "basis_result_sha256": BASIS_RESULT_SHA, "source": str(args.basis.absolute()),
               "files": [{"relative": r, "sha256": d} for r, d in output_files.items()],
               "basis_files": [{"relative": r, "sha256": d} for r, d in files.items()],
               "document_overrides": list(overrides.values()),
               "exact_basis_files": len(files) - len(overrides),
               "documentation_qualification": "Only explicitly named, separately pinned publication-scope documentation differs from the exact engineering basis",
               "source_file_count": len(files), "version": VERSION,
               "go_contract_sha256": args.go_sha256, "copy_only": True,
               "actual_model_calls": 0, "research_trials": 0, "study_registration": False}
    new_json(stage / "release-copy.json", receipt)
    stage.rename(target)
    return {"release": str(target), "release_copy_sha256": sha(target / "release-copy.json"), **receipt}


def clean_environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(key, None)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    return env


def validate_release(args) -> dict:
    target = args.target.absolute()
    check_target(target)
    go = check_go(args.go_receipt, args.go_sha256, "install_validate", target)
    overrides = document_overrides(go)
    output_files = {**expected_files(), **{r: row["sha256"] for r, row in overrides.items()}}
    receipt = target / "release-copy.json"
    if sha(receipt) != args.release_copy_sha256:
        raise ValueError("External exact-copy receipt pin differs")
    copied = load(receipt)
    if (copied["basis_before_sha256"] != BASIS_BEFORE_SHA or copied["files"] != [
            {"relative": r, "sha256": d} for r, d in output_files.items()]
            or copied["basis_files"] != [{"relative": r, "sha256": d} for r, d in expected_files().items()]
            or copied["document_overrides"] != list(overrides.values())):
        raise ValueError("Copied release inventory differs from independently reviewed source")
    inspect_basis(target, exact_inventory=False, approved_document_overrides=overrides)
    # Do not enumerate actual or unrelated study trees. A new installation must
    # precede every research registration; allow no runs root at entry.
    if (target / "runs").exists():
        raise ValueError("Unreconciled runs root exists; keep this engineering validation separate")
    proof = target / "validation/release-local-v1"
    if proof.exists():
        raise FileExistsError("Never repeat/overwrite completed or failed validation; use explicit revision")
    proof.mkdir(parents=True)
    env = clean_environment()
    files = output_files
    protected = load(HERE / "pins/before.json")["protected"]
    if len(protected) != 309 or any(sha(checked_path(PROJECT, r)) != digest for r, digest in protected.items()):
        raise ValueError("Externally pinned protected source309 differs; no environment action allowed")
    new_json(proof / "before.json", {"source": files, "protected_sources": protected,
                                    "copy_receipt_sha256": args.release_copy_sha256})
    phases = []
    def phase(name, command, environment=None):
        started = time.monotonic()
        process = subprocess.run(command, cwd=target, env=environment or env, capture_output=True)
        stdout, stderr = proof / (name + ".stdout.log"), proof / (name + ".stderr.log")
        stdout.write_bytes(process.stdout); stderr.write_bytes(process.stderr)
        row = {"phase": name, "command": list(map(str, command)), "cwd": str(target),
               "exit_code": process.returncode, "seconds": time.monotonic() - started,
               "stdout": {"path": str(stdout), "sha256": sha(stdout)},
               "stderr": {"path": str(stderr), "sha256": sha(stderr)}}
        new_json(proof / (name + ".json"), row); phases.append(row)
        print(json.dumps({"phase": name, "exit_code": row["exit_code"]}), flush=True)
        if process.returncode:
            raise RuntimeError("Phase failed; preserve receipt and do not repeat successful phases: " + name)
        return process
    try:
        venv = target / ".venv"
        if venv.exists():
            raise FileExistsError("A new release requires a new own environment")
        phase("venv-create", [str(BUNDLED), "-X", "utf8", "-B", "-m", "venv", str(venv)])
        python = venv / "Scripts/python.exe"
        environment = phase("environment", [str(python), "-X", "utf8", "-B", "-c",
            'import json,sys,site;print(json.dumps({"python":sys.version,"executable":sys.executable,"prefix":sys.prefix,"base_prefix":sys.base_prefix,"user_site_enabled":site.ENABLE_USER_SITE}))'])
        info = json.loads(environment.stdout)
        if Path(info["prefix"]).resolve() != venv.resolve() or info["prefix"] == info["base_prefix"] or info["user_site_enabled"] is not False:
            raise ValueError("Environment is not an isolated own non-system venv")
        refs = phase("fixed-references", [str(python), "-X", "utf8", "-B", "-c",
            'import json;from evidence_research.baseline import frozen_upstream_sources;from evidence_research.report_semantics import FACT_REGISTRY_SHA256,FACT_CORPUS_SHA256;print(json.dumps({"fixed_upstream":frozen_upstream_sources(),"registry":FACT_REGISTRY_SHA256,"corpus":FACT_CORPUS_SHA256}))'])
        values = json.loads(refs.stdout)
        if len(values["fixed_upstream"]) != 36 or values["registry"] != FACT_REGISTRY_SHA or values["corpus"] != FACT_CORPUS_SHA:
            raise ValueError("Runtime reference closure differs")
        build_env = env.copy()
        build_env["PYTHONPATH"] = str(BUNDLED.parent / "Lib/site-packages")
        phase("offline-editable-install", [str(python), "-X", "utf8", "-B", "-m", "pip", "--isolated", "install",
            "--no-index", "--no-deps", "--no-build-isolation", "--editable", "."], build_env)
        installed = phase("installed-environment", [str(python), "-X", "utf8", "-B", "-c",
            'import json,sys,site,importlib.metadata as m,evidence_research;print(json.dumps({"prefix":sys.prefix,"base_prefix":sys.base_prefix,"user_site_enabled":site.ENABLE_USER_SITE,"package_path":evidence_research.__file__,"package_version":m.version("evidence-research")}))'])
        info = json.loads(installed.stdout)
        if (info["package_version"] != VERSION or not Path(info["package_path"]).resolve().is_relative_to(target.resolve())
                or Path(info["prefix"]).resolve() != venv.resolve() or info["user_site_enabled"] is not False):
            raise ValueError("Installed runtime uses another project/version/environment")
        phase("doctor", [str(python), "-X", "utf8", "-B", "-m", "evidence_research", "doctor"])
        guard = proof / "audit_guard"
        guard.mkdir()
        guard_source = HERE / "audit_guard.py"
        if sha(guard_source) != "e70a47cb59fb86c305c2802e948ab8ba7fe520bcedfd22e2bfd64f8a31be63f3":
            raise ValueError("Fixed corrected engineering audit guard changed")
        shutil.copyfile(guard_source, guard / "sitecustomize.py")
        temp = PROJECT.parent / ("_t7" + hashlib.sha256(str(proof).encode()).hexdigest()[:8])
        if temp.exists():
            raise FileExistsError("Never replace earlier synthetic fixture temp")
        temp.mkdir()
        unit_env = env.copy()
        unit_env.update(PYTHONPATH=str(guard), TEMP=str(temp), TMP=str(temp), ER_RELEASE_ROOT=str(target),
                        ER_PROJECT_ROOT=str(PROJECT), ER_FIXTURE_TMP=str(temp), ER_PROOF_ROOT=str(proof),
                        ER_AUDIT_GUARD_PATH=str(proof / "unit-guard.json"))
        phase("unit-checks", [str(python), "-X", "utf8", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], unit_env)
        audit = load(proof / "unit-guard.json")
        if any(v for k, v in audit["counts"].items() if k != "allowed_cpu_fixture_subprocesses"):
            raise ValueError("Forbidden access/event recorded by external engineering guard")
        raw = (proof / "unit-checks.stderr.log").read_text(encoding="utf-8")
        match = re.search(r"Ran (\d+) tests in", raw)
        if not match or int(match.group(1)) != 263:
            raise ValueError("Unexpected test inventory; do not silently substitute a smaller suite")
        result = {"kind": "new_version7_own_environment_engineering_validation", "valid": True,
                  "checks": int(match.group(1)), "guard": audit,
                  "guard_source_sha256": sha(guard_source), "environment": info}
    except BaseException as error:
        result = {"kind": "new_version7_own_environment_engineering_validation", "valid": False,
                  "failure": {"type": type(error).__name__, "message": str(error)},
                  "successful_phases_must_not_be_repeated": [r["phase"] for r in phases if r["exit_code"] == 0]}
    after = {r: sha(checked_path(target, r)) for r in files}
    protected_after = {r: sha(checked_path(PROJECT, r)) for r in protected}
    new_json(proof / "after.json", {"source": after, "protected_sources": protected_after})
    result.update(phases=phases, source_file_count=len(files), source_unchanged=after == files,
                  copy_receipt_sha256=args.release_copy_sha256, go_contract_sha256=args.go_sha256,
                  protected_source_files=len(protected), protected_sources_unchanged=protected_after == protected,
                  actual_model_calls=0, research_trials=0, study_registration=False,
                  external_dependency_downloads=0, upstream_fetch=False,
                  build_tool_scope="Bundled runtime site-packages only during offline installer; removed for runtime checks/tests",
                  doctor_model_access="Read-only sandbox CLI check; actual authenticated provider execution not assessed",
                  trusted_cpu_unit_fixtures="Engineering tests only, not research trials or framework improvement evidence",
                  framework_improvement_proven=False, goal_complete=False)
    result["valid"] = result["valid"] and result["source_unchanged"] and result["protected_sources_unchanged"]
    new_json(proof / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "copy", "validate"), nargs="?", default="inspect")
    parser.add_argument("--basis", type=Path, default=PROJECT / "work/c7-full-check-v2/s")
    parser.add_argument("--target", type=Path, default=PROJECT / "versions/v7-development")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--go-receipt", type=Path)
    parser.add_argument("--go-sha256")
    parser.add_argument("--release-copy-sha256")
    args = parser.parse_args()
    if args.action != "inspect" and (not args.go_receipt or not args.go_sha256):
        parser.error("copy/validate are deferred until a separate parent go signal and pinned scope contract")
    if args.action == "validate" and not args.release_copy_sha256:
        parser.error("validate requires the externally supplied new release-copy SHA")
    value = inspect_basis(args.basis) if args.action == "inspect" else copy_release(args) if args.action == "copy" else validate_release(args)
    if args.output:
        if not args.output.absolute().is_relative_to(HERE):
            parser.error("Preparation output is restricted to this fresh own proof directory")
        new_json(args.output, value)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    if value.get("valid") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
