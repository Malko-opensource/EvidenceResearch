"""Trusted, CPU-only research tasks. Candidate configurations never execute code.

The task owner holds test data. ``public_task`` deliberately returns only training
and validation observations. This module is an allow-listed implementation, not
an OS sandbox for arbitrary generated Python.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time
from typing import Any

TASK_VERSION = "polynomial-ridge-1"
DEVELOPMENT_TASKS = ("dev-linear", "dev-quadratic", "dev-noisy")
_TASK_DEFINITIONS = {
    "dev-linear": {"coefficients": [0.4, 1.8], "noise": 0.08, "n_train": 80},
    "dev-quadratic": {"coefficients": [-0.7, 0.5, 1.3], "noise": 0.10, "n_train": 80},
    "dev-noisy": {"coefficients": [0.3, -1.2, 0.6, 0.4], "noise": 0.60, "n_train": 36},
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def value_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_json(path: Path, value: Any) -> None:
    Path(path).write_bytes(canonical_bytes(value) + b"\n")


def task_data(task_id: str, seed: int, *, private_definition: dict | None = None) -> dict:
    """Deterministic disjoint splits, whose provenance is independently hashed."""
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError("seed must be a uint32 integer")
    definition = private_definition or _TASK_DEFINITIONS.get(task_id)
    if definition is None:
        raise ValueError("unknown development task; final tasks require the evaluator")
    rng = random.Random(seed)
    splits = {}
    # Separate generators are not re-used after observing candidate performance.
    for split, n in (("train", definition["n_train"]), ("validation", 64), ("test", 96)):
        rows = []
        for i in range(n):
            x = rng.uniform(-1.5, 1.5)
            y = sum(c * x**p for p, c in enumerate(definition["coefficients"]))
            y += rng.gauss(0, definition["noise"])
            rows.append({"id": f"{task_id}:{seed}:{split}:{i}", "x": x, "y": y})
        splits[split] = rows
    return splits


def split_manifest(task_id: str, seed: int, *, private_definition: dict | None = None) -> dict:
    data = task_data(task_id, seed, private_definition=private_definition)
    return {"task_id": task_id, "task_version": TASK_VERSION, "seed": seed,
            "generation": "stdlib random.Random; split order train,validation,test",
            "splits": {name: {"count": len(rows), "sha256": value_hash(rows),
                              "ids_sha256": value_hash([r["id"] for r in rows])}
                       for name, rows in data.items()}}


def public_task(task_id: str, seed: int) -> dict:
    data = task_data(task_id, seed)
    return {"task_id": task_id, "task_version": TASK_VERSION,
            "objective": "minimize validation mean squared error using polynomial ridge regression",
            "allowed_config": {"degree": "integer 1..8", "alpha": "finite number 0..100"},
            "metric": "validation_mse", "train": data["train"],
            "validation": data["validation"]}


def validate_config(config: dict) -> dict:
    if not isinstance(config, dict) or set(config) != {"degree", "alpha"}:
        raise ValueError("config must contain exactly degree and alpha")
    degree, alpha = config["degree"], config["alpha"]
    if isinstance(degree, bool) or not isinstance(degree, int) or not 1 <= degree <= 8:
        raise ValueError("degree must be an integer from 1 to 8")
    if isinstance(alpha, bool) or not isinstance(alpha, (float, int)) or not math.isfinite(alpha) or not 0 <= alpha <= 100:
        raise ValueError("alpha must be finite and between 0 and 100")
    return {"degree": degree, "alpha": float(alpha)}


def make_spec(task_id: str, seed: int, config: dict, *, model: str = "local-trusted-cpu",
              hypothesis: str = "Polynomial features and ridge regularization reduce validation MSE.",
              criterion: dict | None = None, resource_envelope: dict | None = None,
              task_bundle: dict | None = None) -> dict:
    config = validate_config(config)
    manifest = task_bundle["split_manifest"] if task_bundle is not None else split_manifest(task_id, seed)
    implementation_hash = sha256_file(Path(__file__))
    evaluator_hash = sha256_file(Path(__file__).with_name("verifier.py"))
    spec = {"task_id": task_id, "task_version": TASK_VERSION, "seed": seed,
            "config": config, "hypothesis": hypothesis, "model": model,
            "metric": "validation_mse", "criterion": criterion or {"direction": "min", "threshold": 0.15},
            "split_manifest_sha256": value_hash(manifest),
            "data_sha256": value_hash({name: details["sha256"] for name, details in manifest["splits"].items()}),
            "implementation_sha256": implementation_hash, "source_sha256": implementation_hash,
            "evaluator_sha256": evaluator_hash, "baseline": {"degree": 1, "alpha": 0.0},
            "resource_envelope": resource_envelope or {"device": "cpu", "tools": ["trusted polynomial ridge"], "network": False},
            "command": "in_process:evidence_research.tasks.run_task(spec,run_dir)",
            "execution_entrypoint": {"kind": "in_process_trusted_callable", "callable": "evidence_research.tasks.run_task"},
            "reproduction_command": "python -m evidence_research.tasks --spec registered_spec.json --run-dir NEW_RUN_DIR",
            "evidence_kind": "actual_cpu_execution", "split_policy": "train fit; validation select; test withheld"}
    if task_bundle is not None:
        spec["task_bundle"] = task_bundle
        spec["public_bundle_sha256"] = value_hash(task_bundle)
    return spec


def registered_data(spec: dict) -> tuple[dict, dict]:
    """Evaluation-owned public bundles contain no test rows or answer definitions."""
    if "task_bundle" not in spec:
        return task_data(spec["task_id"], spec["seed"]), split_manifest(spec["task_id"], spec["seed"])
    bundle = spec["task_bundle"]
    if set(bundle) != {"train", "validation", "split_manifest"} or value_hash(bundle) != spec.get("public_bundle_sha256"):
        raise ValueError("evaluation public bundle inventory/hash mismatch")
    manifest = bundle["split_manifest"]
    if manifest.get("task_id") != spec["task_id"] or manifest.get("seed") != spec["seed"] or manifest.get("task_version") != TASK_VERSION:
        raise ValueError("evaluation bundle identity mismatch")
    data = {name: bundle[name] for name in ("train", "validation")}
    for name, rows in data.items():
        if value_hash(rows) != manifest["splits"][name]["sha256"] or len(rows) != manifest["splits"][name]["count"]:
            raise ValueError("evaluation public data does not match manifest")
        if value_hash([r["id"] for r in rows]) != manifest["splits"][name]["ids_sha256"]:
            raise ValueError("evaluation public split IDs do not match manifest")
    return data, manifest


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Partial pivoting linear solve, used only by the trusted runner."""
    aug = [row[:] + [v] for row, v in zip(matrix, rhs)]
    n = len(rhs)
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(aug[i][col]))
        aug[col], aug[pivot] = aug[pivot], aug[col]
        if abs(aug[col][col]) < 1e-12:
            raise ValueError("singular fit; change the registered configuration")
        scale = aug[col][col]
        aug[col] = [v / scale for v in aug[col]]
        for row in range(n):
            if row != col:
                scale = aug[row][col]
                aug[row] = [a - scale * b for a, b in zip(aug[row], aug[col])]
    return [row[-1] for row in aug]


def features(x: float, degree: int) -> list[float]:
    return [x**p for p in range(degree + 1)]


def fit(train: list[dict], config: dict) -> dict:
    config = validate_config(config)
    degree, alpha = config["degree"], config["alpha"]
    xs = [features(r["x"], degree) for r in train]
    n = degree + 1
    matrix = [[math.fsum(row[a] * row[b] for row in xs) for b in range(n)] for a in range(n)]
    for i in range(1, n):
        matrix[i][i] += alpha
    rhs = [math.fsum(row[i] * target["y"] for row, target in zip(xs, train)) for i in range(n)]
    weights = _solve(matrix, rhs)
    return {"config": config, "weights": weights,
            "fit_split": "train", "fit_ids_sha256": value_hash([r["id"] for r in train]),
            "regularization": "sum_squared_error + alpha*sum(nonintercept_weight_squared)"}


def predict(model: dict, rows: list[dict]) -> list[dict]:
    weights = model["weights"]
    return [{"id": r["id"], "prediction": math.fsum(w * r["x"]**p for p, w in enumerate(weights))} for r in rows]


def mse(rows: list[dict], predictions: list[dict]) -> float:
    if len(rows) != len(predictions) or not rows:
        raise ValueError("prediction count differs from split")
    if any(r["id"] != p["id"] for r, p in zip(rows, predictions)):
        raise ValueError("prediction IDs differ from split")
    return math.fsum((r["y"] - p["prediction"])**2 for r, p in zip(rows, predictions)) / len(rows)


def _validate_registered_spec(spec: dict) -> None:
    if spec.get("task_version") != TASK_VERSION:
        raise ValueError("task version mismatch")
    if spec.get("implementation_sha256") != sha256_file(Path(__file__)):
        raise ValueError("implementation version differs from preregistration")
    if spec.get("evaluator_sha256") != sha256_file(Path(__file__).with_name("verifier.py")):
        raise ValueError("evaluator version differs from preregistration")
    _, manifest = registered_data(spec)
    if value_hash(manifest) != spec.get("split_manifest_sha256"):
        raise ValueError("data split differs from preregistration")
    data_digest = value_hash({name: details["sha256"] for name, details in manifest["splits"].items()})
    if data_digest != spec.get("data_sha256"):
        raise ValueError("data hash differs from preregistration")
    if spec.get("metric") != "validation_mse":
        raise ValueError("only preregistered validation_mse is available to the research loop")
    validate_config(spec["config"])


def run_task(spec: dict, run_dir: Path) -> dict:
    """Run real numeric computation and preserve exact input/output evidence."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    # Overwriting evidence requires a different run directory. Restart belongs to Engine.
    if any(run_dir.glob("result.json")):
        raise FileExistsError("completed runner evidence already exists; use Engine.resume")
    started = time.perf_counter()
    write_json(run_dir / "registered_spec.json", spec)
    source_dir = run_dir / "source" / "evidence_research"
    source_dir.mkdir(parents=True, exist_ok=True)
    for name in ("tasks.py", "verifier.py"):
        (source_dir / name).write_bytes(Path(__file__).with_name(name).read_bytes())
    (source_dir / "__init__.py").write_text('"""Content-addressed standalone execution snapshot."""\n', encoding="utf-8")
    log = ["execution_kind=actual_cpu_execution", "actual_invocation=in_process:evidence_research.tasks.run_task(spec,run_dir)",
           "implementation=trusted allow-listed polynomial ridge", "test_access=withheld"]
    artifacts = ["registered_spec.json", "run.log", "source/evidence_research/tasks.py",
                 "source/evidence_research/verifier.py", "source/evidence_research/__init__.py"]
    metrics = {}
    try:
        _validate_registered_spec(spec)
        data, manifest = registered_data(spec)
        write_json(run_dir / "split_manifest.json", manifest)
        write_json(run_dir / "train.json", data["train"])
        write_json(run_dir / "validation.json", data["validation"])
        model = fit(data["train"], spec["config"])
        predictions = {name: predict(model, data[name]) for name in ("train", "validation")}
        metrics = {name + "_mse": mse(data[name], predictions[name]) for name in predictions}
        write_json(run_dir / "model.json", model)
        write_json(run_dir / "predictions.json", predictions)
        artifacts += ["split_manifest.json", "train.json", "validation.json", "model.json", "predictions.json"]
        log += ["fit_split=train", "selection_split=validation", "configuration=" + canonical_bytes(spec["config"]).decode(),
                "metrics=" + canonical_bytes(metrics).decode()]
        status, error = "success", None
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        status, error = "failure", f"{type(exc).__name__}: {exc}"
        log.append("error=" + error)
    elapsed = time.perf_counter() - started
    log.append(f"execution_seconds={elapsed:.9f}")
    (run_dir / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    hashes = {name: sha256_file(run_dir / name) for name in artifacts}
    claims = [{"kind": "measured", "metric": name, "value": value, "artifact": str(run_dir / "predictions.json"),
               "sha256": hashes["predictions.json"], "scope": "development validation"} for name, value in metrics.items()]
    result = {"status": status, "metrics": metrics, "error": error, "execution_kind": "actual_cpu_execution",
              "execution_seconds": elapsed, "cost": {"provider_billed_cost": None, "local_cpu_seconds": elapsed},
              "artifacts": [str(run_dir / name) for name in artifacts], "artifact_hashes": hashes,
              "claims": claims, "spec_sha256": value_hash(spec), "command": spec.get("command"),
              "execution_entrypoint": spec.get("execution_entrypoint"), "reproduction_command": spec.get("reproduction_command")}
    write_json(run_dir / "result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_task(json.loads(args.spec.read_text(encoding="utf-8")), args.run_dir)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    if result["status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
