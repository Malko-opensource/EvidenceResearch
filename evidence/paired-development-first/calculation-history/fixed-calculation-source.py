"""Recompute a completed paired diagnostic; never a confirmatory adoption test."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evidence_research.evaluation import _owner_metric, _validate_saved_score, recompute_resource_audit
from evidence_research.store import atomic_json, sha256_file
from evidence_research.verifier import verify


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def describe(study, unit_id, destination):
    study, destination = Path(study).resolve(), Path(destination).resolve()
    registration_path = study / "pilot-registration.json"
    registration = load(registration_path)
    entry = next(item for item in registration["units"] if item["unit_id"] == unit_id)
    owner_path = Path(entry["owner_path"])
    if sha256_file(owner_path) != entry["owner_sha256"]:
        raise ValueError("Registered owner data changed")
    owner = load(owner_path)
    arms, evidence = {}, [{"path": str(registration_path), "sha256": sha256_file(registration_path)},
                          {"path": str(owner_path), "sha256": sha256_file(owner_path)}]
    for arm in ("B", "C"):
        directory = study / "units" / unit_id / arm
        measurement_path = directory / "owner-measurement.json"
        measurement = load(measurement_path)
        if measurement["status"] != "verified":
            raise ValueError("Both completed independently measured arms required")
        _validate_saved_score(measurement, owner, directory)
        response = load(directory / "arm-response.json")
        run = Path(response["selected_run_dir"])
        verified = verify(load(run / "registered_spec.json"), load(run / "result.json"), run)
        if not verified["valid"]:
            raise ValueError("Selected experiment did not pass the fixed verifier")
        test_mse = _owner_metric(owner["test"], load(run / "model.json"))
        audit_path = Path(measurement["evidence"]["resource_audit"]["path"])
        resource = recompute_resource_audit(audit_path)
        if resource["unknown_failed_token_usage"]:
            raise ValueError("This descriptive exact-token ratio requires complete usage")
        for name in ("report-review.json", "companion-review.json"):
            review_path = directory / name
            review = load(review_path)
            if (review.get("reviewer_role") != "independent_verifier" or review.get("status") != "complete"
                    or review.get("pending_claims") != 0 or review.get("unsupported_claims") != 0):
                raise ValueError("Complete separate report reviews required")
            evidence.append({"path": str(review_path), "sha256": sha256_file(review_path)})
        measures = resource["measures"]
        arms[arm] = {"validation_mse": verified["metrics"]["validation_mse"], "test_mse": test_mse,
            "input_tokens": measures["input_tokens"], "output_tokens": measures["output_tokens"],
            "provider_attempts": measures["provider_attempts"], "actual_cpu_executions": measures["actual_cpu_executions"],
            "model_seconds": measures["model_seconds"], "provider_billed_cost": None,
            "total_cpu_execution_seconds": measures["total_cpu_execution_seconds"]}
        evidence += [{"path": str(path), "sha256": sha256_file(path)} for path in
                     (measurement_path, audit_path, run / "registered_spec.json", run / "result.json", run / "model.json")]
    b_tokens = arms["B"]["input_tokens"] + arms["B"]["output_tokens"]
    c_tokens = arms["C"]["input_tokens"] + arms["C"]["output_tokens"]
    if b_tokens <= 0 or arms["B"]["test_mse"] <= 0:
        raise ValueError("Positive denominators required")
    result = {"kind": "independently_recomputed_single_development_pair", "unit_id": unit_id,
        "arms": arms, "token_relative_reduction": 1 - c_tokens / b_tokens,
        "test_mse_relative_reduction": 1 - arms["C"]["test_mse"] / arms["B"]["test_mse"],
        "formula_scope": "Descriptive ratios in this one registered minimal-phase development pair; no population inference.",
        "excluded_metric": "recovered_errors: v4 B counts runtime/protocol recovery while C counts completed verified retries; incomparable semantics, never claimed as error recovery here.",
        "baseline_limitation": "MLE1/Paper0/literature1/phase4 differs from upstream recommended settings; not the main original-default comparison or its confirmatory variance input.",
        "adopted": False, "goal_complete": False, "evidence": evidence,
        "calculation_source": {"path": str(Path(__file__).resolve()), "sha256": sha256_file(Path(__file__))}}
    if destination.exists():
        if load(destination) != result:
            raise ValueError("Preserve the original completed descriptive receipt")
    else:
        atomic_json(destination, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(describe(args.study, args.unit, args.out), ensure_ascii=True, indent=2))
