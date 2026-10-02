"""Adversarial fixtures for the standalone owner replay; no model/runner calls."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import shutil


def validate(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    if destination.exists():
        raise FileExistsError("Use a new fixture output; preserve prior evidence")
    destination.mkdir(parents=True)
    script = root / "evaluation/replay_published_pair.py"
    module_spec = importlib.util.spec_from_file_location("owner_replay", script)
    audit = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(audit)
    study = root / "runs/development/paired-pilot-v4"
    registration_path = study / "pilot-registration.json"
    registration = audit.load(registration_path)
    recorded_root = str(PureWindowsPath(next(iter(registration["sources"]))).parent.parent)
    baseline = audit.replay(root, recorded_root, "runs/development/paired-pilot-v4", "linear-seed7", audit.sha(registration_path))
    checks = []
    bundle = audit.Bundle(root, recorded_root)
    for path in (recorded_root + "\\..\\outside", "C:\\outside\\secret.json"):
        try:
            bundle.resolve(path)
        except ValueError:
            checks.append({"check": "unsafe_path_rejected", "valid": True})
        else:
            raise AssertionError("Unsafe relocation was accepted")
    original = audit.load(study / "units/linear-seed7/C/arm-response.json")["selected_run_dir"]
    relative = PureWindowsPath(original).relative_to(PureWindowsPath(recorded_root))
    fixture_root = destination / "tampered-bundle"
    run = fixture_root.joinpath(*relative.parts)
    shutil.copytree(bundle.resolve(original), run)
    spec, result = audit.load(run / "registered_spec.json"), audit.load(run / "result.json")
    frozen = run / "source/evidence_research/verifier.py"
    # This body is harmless even if the guard fails: it only raises an exception.
    frozen.write_text('def _reference_fit(rows, degree, alpha):\n    raise RuntimeError("unauthorized reference executed")\n', encoding="utf-8")
    spec["evaluator_sha256"] = audit.sha(frozen)
    (run / "registered_spec.json").write_text(json.dumps(spec, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    result["spec_sha256"] = audit.value_sha(spec)
    result["artifact_hashes"]["registered_spec.json"] = audit.sha(run / "registered_spec.json")
    result["artifact_hashes"]["source/evidence_research/verifier.py"] = audit.sha(frozen)
    (run / "result.json").write_text(json.dumps(result), encoding="utf-8")
    fixture = audit.Bundle(fixture_root, recorded_root)
    fixture.trusted_sources = {PureWindowsPath(p).name: h for p, h in registration["sources"].items()}
    try:
        audit.replay_cpu(fixture, run)
    except ValueError as error:
        if "externally pinned study registration" not in str(error):
            raise
        checks.append({"check": "self_rehashed_untrusted_fit_rejected_before_exec", "valid": True, "reason": str(error)})
    else:
        raise AssertionError("Self-rehashed untrusted reference accepted")
    tampered = run / "train.json"
    tampered.write_bytes(tampered.read_bytes() + b" ")
    try:
        fixture.check(tampered, result["artifact_hashes"]["train.json"])
    except ValueError as error:
        checks.append({"check": "artifact_byte_tamper_rejected", "valid": True, "reason": str(error)})
    else:
        raise AssertionError("Changed original artifact accepted")
    payload = {"valid": all(c["valid"] for c in checks), "checks": checks,
               "baseline_replay_valid": baseline["valid"], "actual_model_calls": 0, "new_runner_executions": 0,
               "scope": "Actual published development bytes plus explicit malicious-source/path/tamper fixtures; not an actual new research comparison.",
               "auditor_source_sha256": audit.sha(script), "validation_source_sha256": audit.sha(__file__),
               "registration_sha256": audit.sha(registration_path)}
    (destination / "validation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"valid": payload["valid"], "checks": len(checks), "actual_model_calls": 0, "new_runner_executions": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    validate(args.root, args.out)
