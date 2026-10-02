"""Reconcile immutable fresh-install receipts; no repeated execution."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[2] / "_er6"
RELEASE = CHECKOUT / "versions/v6-development"
PHASES = ("clone", "sparse-init", "sparse-set", "exact-checkout", "public-source-before", "venv-create",
          "upstream-acquisition", "offline-editable-install", "environment", "fixed-upstream", "doctor", "public-source-after")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    if (HERE / "result.json").exists():
        raise FileExistsError("Preserve completed public installation proof")
    receipts = []
    for name in PHASES + ("unit-checks",):
        path = HERE / f"{name}.json"
        item = load(path)
        if item["exit_code"] != 0:
            raise ValueError("Failed phase must remain a failure: " + name)
        for stream in ("stdout", "stderr"):
            raw = HERE / f"{name}.{stream}.log"
            if sha(raw) != item[f"{stream}_sha256"]:
                raise ValueError("Immutable log changed")
        receipts.append({"phase": name, "path": str(path), "sha256": sha(path)})
    before, after = load(HERE / "source-before.json"), load(HERE / "source-after.json")
    if before["commit"] != "0be5988f4760263122188ef31e7f8dfba5ccea47" or before["files"] != after["files"]:
        raise ValueError("Public Git blob provenance changed")
    fixed = load(HERE / "fixed-upstream.stdout.log")
    if fixed["fixed_files"] != 36:
        raise ValueError("External fixed manifest plus35 count differs")
    for path, digest in fixed["sources"].items():
        source = Path(path)
        if not source.resolve().is_relative_to(RELEASE.resolve()) or sha(source) != digest:
            raise ValueError("Own fixed upstream bytes changed or leave fresh checkout")
    tests = load(HERE / "unit-checks.json")
    acquisition = load(HERE / "upstream-acquisition.stdout.log")
    doctor = load(HERE / "doctor.stdout.log")
    environment = load(HERE / "environment.stdout.log")
    if (not tests["valid"] or tests["checks"] != 215 or not after["public_worktree_unchanged"]
            or acquisition["downloaded_files"] != 35 or acquisition["verified_files"] != 35
            or environment["prefix"] == environment["base_prefix"] or environment["user_site_enabled"]):
        raise ValueError("Independent install conditions incomplete")
    result = {"kind": "fresh_public_v6_installation_independent_validation", "valid": True,
              "public_repo": "https://github.com/Malko-opensource/EvidenceResearch.git",
              "commit": before["commit"], "checkout": str(CHECKOUT), "sparse_checkout": "versions/v6-development only",
              "tracked_source_proof_files": len(before["files"]), "git_blob_bytes_before_after_unchanged": True,
              "before": {"path": str(HERE / "source-before.json"), "sha256": sha(HERE / "source-before.json")},
              "after": {"path": str(HERE / "source-after.json"), "sha256": sha(HERE / "source-after.json")},
              "environment": environment, "own_venv_python_sha256": sha(RELEASE / ".venv/Scripts/python.exe"),
              "venv_cfg": {"path": str(HERE / "venv-pyvenv.cfg"), "sha256": sha(HERE / "venv-pyvenv.cfg")},
              "upstream": {"commit": acquisition["upstream_commit"], "downloaded_files": 35, "verified_fixed_files": 36,
                  "network_scope": "Pinned public raw source acquisition only; executed_upstream_code=false for acquisition",
                  "raw_sources_after_tests_still_match_fixed_external_pins": True},
              "offline_editable_install": True,
              "packaging_scope": "Bundled setuptools/wheel exposed only to installer with --no-index --no-deps --no-build-isolation; not runtime env",
              "checks": 215, "unit_guard": tests["unit_guard"], "phase_receipts": receipts,
              "doctor_authentication": doctor["authentication"],
              "model_access_established": False, "actual_research_model_calls": 0, "actual_research_trials": 0,
              "trusted_cpu_unit_fixtures": "Included; one allowed standalone CPU fixture subprocess, not a research trial",
              "original_project_or_old_checkout_reads_during_tests": 0,
              "actual_private_owner_data_accessed": False, "registration_executed": False,
              "final_evaluation_executed": False, "framework_improvement_proven": False, "goal_complete": False,
              "limits": "Published installation and engineering/verification fixtures. Synthetic source tasks and mocked model receipts do not establish actual B/C research outcomes."}
    (HERE / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"valid": True, "commit": before["commit"], "checks": 215,
                      "result_sha256": sha(HERE / "result.json"), "actual_research_model_calls": 0}))


if __name__ == "__main__":
    main()
