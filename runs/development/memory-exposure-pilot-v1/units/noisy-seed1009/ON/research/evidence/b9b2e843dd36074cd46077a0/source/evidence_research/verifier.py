"""Independent checks over preregistered inputs and on-disk execution evidence.

This verifier never imports generated candidate code. Metric calculation and the
reference fit below are independent of the runner's solve and metric functions.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .tasks import TASK_VERSION, registered_data, sha256_file, validate_config, value_hash


def _reference_fit(rows: list[dict], degree: int, alpha: float) -> list[float]:
    # Eliminate the intercept by centering, then Cholesky solve the slope system.
    # Unlike the runner's pivoted Gaussian solve, this only solves d-by-d slopes.
    n = len(rows)
    xs = [[row["x"]**(p + 1) for p in range(degree)] for row in rows]
    means = [math.fsum(row[p] for row in xs) / n for p in range(degree)]
    ymean = math.fsum(row["y"] for row in rows) / n
    centered = [[v - m for v, m in zip(row, means)] for row in xs]
    a = [[math.fsum(row[i] * row[j] for row in centered) + (alpha if i == j else 0.0)
          for j in range(degree)] for i in range(degree)]
    b = [math.fsum(row[p] * (target["y"] - ymean) for row, target in zip(centered, rows)) for p in range(degree)]
    lower = [[0.0] * degree for _ in range(degree)]
    for i in range(degree):
        for j in range(i + 1):
            residual = a[i][j] - math.fsum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                if residual <= 0:
                    raise ValueError("reference fit matrix is not positive definite")
                lower[i][j] = math.sqrt(residual)
            else:
                lower[i][j] = residual / lower[j][j]
    forward = []
    for i in range(degree):
        forward.append((b[i] - math.fsum(lower[i][j] * forward[j] for j in range(i))) / lower[i][i])
    slopes = [0.0] * degree
    for i in range(degree - 1, -1, -1):
        slopes[i] = (forward[i] - math.fsum(lower[j][i] * slopes[j] for j in range(i + 1, degree))) / lower[i][i]
    intercept = ymean - math.fsum(m * w for m, w in zip(means, slopes))
    return [intercept] + slopes


def _equal(a: float, b: float) -> bool:
    return math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-9)


def _safe_file(run_dir: Path, name: str) -> Path:
    path = run_dir / name
    if Path(name).is_absolute() or ".." in Path(name).parts or path.is_symlink() or not path.resolve().is_relative_to(run_dir.resolve()):
        raise ValueError("artifact path escapes the run directory")
    if any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(run_dir)):
        raise ValueError("artifact directory contains a symlink")
    if not path.is_file() or path.stat().st_size > 10_000_000:
        raise ValueError("artifact missing or exceeds size boundary")
    return path


def verify(spec: dict, result: dict, run_dir: Path) -> dict:
    """Adopt evidence only after hash, leakage, configuration and numeric checks."""
    reasons, evidence, checks, metrics = [], [], [], {}
    comparison_valid, comparison = False, None
    run_dir = Path(run_dir)
    try:
        if spec.get("implementation_sha256") != sha256_file(Path(__file__).with_name("tasks.py")):
            raise ValueError("implementation hash mismatch")
        if spec.get("evaluator_sha256") != sha256_file(Path(__file__)):
            raise ValueError("frozen evaluator hash mismatch")
        if spec.get("task_version") != TASK_VERSION:
            raise ValueError("task version mismatch")
        if result.get("spec_sha256") != value_hash(spec):
            raise ValueError("result is not linked to the registered spec")
        if json.loads(_safe_file(run_dir, "registered_spec.json").read_text(encoding="utf-8")) != spec:
            raise ValueError("registered on-disk spec was changed")
        disk_result = json.loads(_safe_file(run_dir, "result.json").read_text(encoding="utf-8"))
        if disk_result != result:
            raise ValueError("result differs from completed evidence")
        required = {"registered_spec.json", "run.log", "source/evidence_research/tasks.py",
                    "source/evidence_research/verifier.py", "source/evidence_research/__init__.py"}
        if result.get("status") == "success":
            required |= {"model.json", "predictions.json", "train.json", "validation.json", "split_manifest.json"}
        hashes = result.get("artifact_hashes", {})
        if set(hashes) != required:
            raise ValueError("artifact inventory differs from the fixed contract")
        allowed_paths = {str(run_dir / name) for name in hashes}
        if set(result.get("artifacts", [])) != allowed_paths:
            raise ValueError("artifact path list differs from the fixed contract")
        for name, expected in hashes.items():
            path = _safe_file(run_dir, name)
            if sha256_file(path) != expected:
                raise ValueError(f"artifact hash mismatch: {name}")
            evidence.append({"path": str(path), "sha256": expected})
        if hashes["source/evidence_research/tasks.py"] != spec.get("implementation_sha256") or hashes["source/evidence_research/verifier.py"] != spec.get("evaluator_sha256"):
            raise ValueError("archived source does not match preregistration")
        checks += ["registered_spec_integrity", "artifact_integrity", "frozen_code_hashes"]
        if result.get("execution_kind") != "actual_cpu_execution":
            raise ValueError("simulated execution cannot pass real task verification")
        if result.get("status") == "failure":
            try:
                validate_config(spec.get("config"))
            except (ValueError, TypeError, KeyError) as exc:
                expected_error = f"{type(exc).__name__}: {exc}"
                if result.get("error") != expected_error or result.get("metrics"):
                    raise ValueError("failure evidence is inconsistent") from exc
                checks.append("independently_confirmed_invalid_configuration")
                return {"valid": True, "status": "verified", "outcome": "failure", "metrics": {},
                        "reasons": ["invalid configuration is independently confirmed"], "evidence": evidence,
                        "checks": checks, "evaluator_sha256": sha256_file(Path(__file__))}
            return {"valid": False, "status": "inconclusive", "outcome": "failure", "metrics": {},
                    "reasons": ["runtime failure logged; cause needs independent reproduction"], "evidence": evidence,
                    "checks": checks, "evaluator_sha256": sha256_file(Path(__file__))}
        if result.get("status") != "success":
            raise ValueError("unsupported execution status")
        config = validate_config(spec["config"])
        data, manifest = registered_data(spec)
        if value_hash(manifest) != spec.get("split_manifest_sha256"):
            raise ValueError("preregistered data split hash differs")
        if value_hash({name: d["sha256"] for name, d in manifest["splits"].items()}) != spec.get("data_sha256"):
            raise ValueError("preregistered data hash differs")
        if json.loads((run_dir / "split_manifest.json").read_text(encoding="utf-8")) != manifest:
            raise ValueError("split manifest differs from independently generated data")
        ids = [set(row["id"] for row in rows) for rows in data.values()]
        if any(len(unique) != len(rows) for unique, rows in zip(ids, data.values())):
            raise ValueError("data split contains duplicate observation IDs")
        if any(ids[i] & ids[j] for i in range(len(ids)) for j in range(i + 1, len(ids))):
            raise ValueError("data leakage: overlapping split IDs")
        if (run_dir / "test.json").exists():
            raise ValueError("withheld test split was materialized in proposer-visible run evidence")
        for split in ("train", "validation"):
            if json.loads((run_dir / f"{split}.json").read_text(encoding="utf-8")) != data[split]:
                raise ValueError("execution data differs from preregistration")
        model = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
        if model.get("config") != config or model.get("fit_split") != "train":
            raise ValueError("model config/fit split differs from preregistration")
        if model.get("fit_ids_sha256") != value_hash([r["id"] for r in data["train"]]):
            raise ValueError("model fitted an unregistered split")
        reference = _reference_fit(data["train"], config["degree"], config["alpha"])
        if len(model.get("weights", [])) != len(reference) or any(not _equal(a, b) for a, b in zip(model["weights"], reference)):
            raise ValueError("model weights fail independent fit reproduction")
        predictions = json.loads((run_dir / "predictions.json").read_text(encoding="utf-8"))
        if set(predictions) != {"train", "validation"}:
            raise ValueError("prediction split inventory differs")
        for split in ("train", "validation"):
            rows, actual = data[split], predictions[split]
            if len(actual) != len(rows) or any(p.get("id") != r["id"] for p, r in zip(actual, rows)):
                raise ValueError("prediction IDs differ from registered split")
            expected = [math.fsum(w * r["x"]**p for p, w in enumerate(reference)) for r in rows]
            if any(not _equal(pred["prediction"], exp) for pred, exp in zip(actual, expected)):
                raise ValueError("saved predictions fail independent reproduction")
            metrics[split + "_mse"] = math.fsum((r["y"] - p["prediction"])**2 for r, p in zip(rows, actual)) / len(rows)
        if set(result.get("metrics", {})) != set(metrics) or any(not _equal(metrics[k], result["metrics"][k]) for k in metrics):
            raise ValueError("reported metrics differ from independently recomputed metrics")
        measured = {c.get("metric"): c for c in result.get("claims", []) if c.get("kind") == "measured"}
        if set(measured) != set(metrics):
            raise ValueError("numeric measurements require linked claims")
        for name, claim in measured.items():
            if not _equal(claim["value"], metrics[name]) or claim.get("artifact") != str(run_dir / "predictions.json") or claim.get("sha256") != hashes["predictions.json"]:
                raise ValueError("measured claim is not linked to verified prediction evidence")
        baseline_config = spec.get("baseline")
        if isinstance(baseline_config, dict) and set(baseline_config) == {"degree", "alpha"}:
            baseline_config = validate_config(baseline_config)
            baseline_weights = _reference_fit(data["train"], baseline_config["degree"], baseline_config["alpha"])
            baseline_predictions = [math.fsum(w * r["x"]**p for p, w in enumerate(baseline_weights)) for r in data["validation"]]
            baseline_value = math.fsum((r["y"] - p)**2 for r, p in zip(data["validation"], baseline_predictions)) / len(baseline_predictions)
            criterion = spec.get("criterion", {})
            if "baseline_value" in criterion and not _equal(criterion["baseline_value"], baseline_value):
                raise ValueError("preregistered baseline value differs from independent fixed baseline")
            comparison_valid = True
            comparison = {"metric": "validation_mse", "baseline_value": baseline_value,
                          "candidate_value": metrics["validation_mse"], "baseline_config": baseline_config,
                          "scope": "same task/seed/split/implementation on local CPU", "test_used": False}
            checks.append("independent_fixed_baseline_comparison")
        checks += ["disjoint_observed_splits", "test_withheld", "configuration_match",
                   "independent_cholesky_fit_reproduction", "independent_metric_recomputation", "claim_evidence_links"]
        if "test" in data:
            checks.append("disjoint_train_validation_test")
        else:
            checks.append("test_integrity_delegated_to_sealed_evaluation_owner")
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as exc:
        reasons.append(f"{type(exc).__name__}: {exc}")
    valid = not reasons
    return {"valid": valid, "status": "verified" if valid else "rejected", "outcome": result.get("status"),
            "metrics": metrics if valid else {}, "reasons": reasons, "evidence": evidence, "checks": checks,
            "comparison_valid": comparison_valid if valid else False, "comparison": comparison if valid else None,
            "evaluator_sha256": sha256_file(Path(__file__))}
