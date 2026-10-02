"""Capture candidate literature fixtures and dependency bytes without live runs."""
from pathlib import Path
import difflib
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATE = ROOT / "work/c6"
FROZEN = ROOT / "versions/v5-development"
PARENT_PIN = "5569d283aeb9a00087092b862ef6dace71cdf73917429c308161d1cf31ad0f81"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if (HERE / "source-manifest.json").exists():
        raise FileExistsError("Keep immutable capture; write a new evidence revision")
    registration_path = FROZEN / "runs/p5/pilot-registration.json"
    if sha(registration_path) != PARENT_PIN:
        raise ValueError("Parent registration pin differs")
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    for path, expected in registration["sources"].items():
        if sha(Path(path)) != expected:
            raise ValueError("Frozen parent source changed")
    relatives = sorted(path.relative_to(CANDIDATE) for path in (CANDIDATE / "evidence_research").glob("*.py"))
    relatives += [Path(name) for name in ("tests/test_literature_integrity_policy_c6.py",
        "references/task_literature_v2.json", "examples/literature-protocol-c6.json", "docs/literature-contract-c6.ko.md")]
    upstream = "references/upstream/AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27/"
    relatives += [Path(upstream + name + ".py") for name in ("utils", "agents", "ai_lab_repo", "mlesolver", "papersolver")]
    before = {relative.as_posix(): sha(CANDIDATE / relative) for relative in relatives}
    snapshot = HERE / "source_snapshot"
    for relative in relatives:
        source, target = CANDIDATE / relative, snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha(target) != before[relative.as_posix()]:
            raise ValueError("Candidate changed during capture")
    if before != {relative.as_posix(): sha(CANDIDATE / relative) for relative in relatives}:
        raise ValueError("Candidate concurrently changed; retain incomplete capture without claiming pass")
    differences = []
    for name in ("evidence_research/baseline.py", "evidence_research/arms.py",
                 "tests/test_context_compaction.py", "tests/test_pilot_literature_receipt.py"):
        original = HERE / "original_source" / name
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FROZEN / name, original)
        candidate_copy = HERE / "candidate_owned_source" / name
        candidate_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CANDIDATE / name, candidate_copy)
        differences.extend(difflib.unified_diff(original.read_text(encoding="utf-8").splitlines(True),
            candidate_copy.read_text(encoding="utf-8").splitlines(True), fromfile="v5/" + name, tofile="c6/" + name))
    (HERE / "owned-code.diff").write_text("".join(differences), encoding="utf-8")
    manifest = {"kind": "unexecuted_candidate_contract_source_snapshot", "parent_registration_sha256": PARENT_PIN,
        "files": [{"path": name, "sha256": value} for name, value in sorted(before.items())],
        "scope": "Source-contract fixtures only. Not model or research task performance evidence.",
        "frozen_parent_sources_unchanged": True, "captured_candidate_sources_stable": True}
    path = HERE / "source-manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failure_source = HERE / "test-fixture-guard-failed.py"
    (HERE / "fixture-guard-failure.json").write_text(json.dumps({
        "kind": "fixture_bootstrap_error", "source_sha256": sha(failure_source),
        "actual_tests": 15, "errors": 15, "failure_point": "setUp before any test body",
        "cause": "AttributeError: CodexProvider has no attribute propose", "correction": "Patch the actual complete API",
        "real_model_calls": 0, "research_cpu_executions": 0,
        "scope": "This tooling error is retained separately from the corrected contract fixture results."}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_sha256": sha(path), "snapshot_files": len(before),
                      "baseline_sha256": before["evidence_research/baseline.py"], "arms_sha256": before["evidence_research/arms.py"]}))


if __name__ == "__main__":
    main()
