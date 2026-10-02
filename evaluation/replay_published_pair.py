"""Read-only, relocated replay of published CPU metrics and provider resources.

Original receipts are never rewritten. This is a development evidence audit,
not a fresh model run, complete semantic report review or adoption decision.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def value_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def equal(a, b):
    return isinstance(a, (float, int)) and isinstance(b, (float, int)) and math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-9)


class Bundle:
    def __init__(self, root, recorded_root):
        self.root = Path(root).resolve()
        path_class = PureWindowsPath if PureWindowsPath(recorded_root).drive else PurePosixPath
        self.path_class = path_class
        self.recorded_root = path_class(recorded_root)
        require(self.recorded_root.is_absolute(), "Explicit absolute recorded root required")
        self.checked = {}
        self.trusted_sources = {}

    def resolve(self, recorded):
        original = self.path_class(recorded)
        require(".." not in original.parts, "Parent traversal in evidence path")
        relative = original.relative_to(self.recorded_root) if original.is_absolute() else original
        actual = self.root.joinpath(*relative.parts)
        require(actual.resolve().is_relative_to(self.root), "Evidence escapes relocated bundle")
        require(not actual.is_symlink() and not any(p.is_symlink() for p in actual.parents if p.is_relative_to(self.root)), "Symlink evidence refused")
        return actual

    def check(self, actual, expected):
        actual = Path(actual)
        require(actual.resolve().is_relative_to(self.root), "Hash target escapes bundle")
        require(actual.is_file() and not actual.is_symlink(), "Missing or symlink evidence")
        require(sha(actual) == expected, f"Original bytes changed: {actual.relative_to(self.root)}")
        self.checked[actual.relative_to(self.root).as_posix()] = expected
        return actual

    def link(self, record):
        return self.check(self.resolve(record["path"]), record["sha256"])


def replay_cpu(bundle, run):
    spec, result = load(run / "registered_spec.json"), load(run / "result.json")
    require(result["execution_kind"] == "actual_cpu_execution" and result["status"] == "success", "Completed actual CPU success required")
    require(value_sha(spec) == result["spec_sha256"], "Registered specification link changed")
    hashes = result["artifact_hashes"]
    required = {"registered_spec.json", "run.log", "source/evidence_research/__init__.py",
                "source/evidence_research/tasks.py", "source/evidence_research/verifier.py",
                "model.json", "predictions.json", "train.json", "validation.json", "split_manifest.json"}
    require(set(hashes) == required, "CPU artifact inventory changed")
    for name, expected in hashes.items():
        require(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts, "Unsafe CPU artifact path")
        bundle.check(run / name, expected)
    require({bundle.resolve(path) for path in result["artifacts"]} == {run / name for name in required}, "CPU artifact path links changed")
    require(hashes["source/evidence_research/tasks.py"] == spec["implementation_sha256"] and hashes["source/evidence_research/verifier.py"] == spec["evaluator_sha256"], "Frozen CPU implementation or evaluator changed")
    require(all(hashes[f"source/evidence_research/{name}"] == bundle.trusted_sources.get(name)
                for name in ("tasks.py", "verifier.py")),
            "CPU fit/evaluator source differs from the externally pinned study registration")
    model = load(run / "model.json")
    require(model["config"] == spec["config"] and model["fit_split"] == "train", "CPU configuration or fit split changed")
    rows = {split: load(run / f"{split}.json") for split in ("train", "validation")}
    public = spec["task_bundle"]
    require(all(rows[s] == public[s] for s in rows), "Actual rows differ from registered public bundle")
    require(load(run / "split_manifest.json") == public["split_manifest"], "Registered split manifest changed")
    require(value_sha(public["split_manifest"]) == spec["split_manifest_sha256"], "Registered split digest changed")
    require(value_sha({k: v["sha256"] for k, v in public["split_manifest"]["splits"].items()}) == spec["data_sha256"], "Registered data digest changed")
    require(not (run / "test.json").exists(), "Hidden test materialized in CPU evidence")
    require(value_sha([r["id"] for r in rows["train"]]) == model["fit_ids_sha256"], "Fit observation IDs changed")
    ids = [set(r["id"] for r in rows[s]) for s in rows]
    require(all(len(ids[i]) == len(rows[s]) for i, s in enumerate(rows)) and not ids[0] & ids[1], "Duplicate or overlapping public observations")
    # Execute only the original, hash-checked independent reference-fit definition.
    # No generated candidate, model response or full archived module is executed.
    source = ast.parse((run / "source/evidence_research/verifier.py").read_text(encoding="utf-8"))
    reference = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "_reference_fit"]
    require(len(reference) == 1, "Frozen independent fit definition missing")
    namespace = {"math": math}
    exec(compile(ast.Module(body=reference, type_ignores=[]), "hash-checked-independent-reference-fit", "exec"), namespace)
    config = spec["config"]
    weights = namespace["_reference_fit"](rows["train"], config["degree"], config["alpha"])
    require(len(weights) == len(model["weights"]) and all(equal(a, b) for a, b in zip(weights, model["weights"])), "Independent fit does not reproduce saved weights")
    predictions = load(run / "predictions.json")
    require(set(predictions) == set(rows), "Prediction split inventory changed")
    metrics = {}
    for split, observed in rows.items():
        saved = predictions[split]
        require(len(saved) == len(observed) and all(p["id"] == r["id"] for p, r in zip(saved, observed)), "Prediction observation IDs changed")
        calculated = [math.fsum(w * r["x"]**p for p, w in enumerate(weights)) for r in observed]
        require(all(equal(p["prediction"], v) for p, v in zip(saved, calculated)), "Independent predictions differ")
        metrics[split + "_mse"] = math.fsum((r["y"] - p["prediction"])**2 for r, p in zip(observed, saved)) / len(observed)
    require(set(metrics) == set(result["metrics"]) and all(equal(v, result["metrics"][k]) for k, v in metrics.items()), "Actual CPU metric mismatch")
    measured = {c["metric"]: c for c in result["claims"] if c["kind"] == "measured"}
    require(set(measured) == set(metrics), "Measured claim inventory mismatch")
    for name, claim in measured.items():
        require(equal(claim["value"], metrics[name]) and bundle.resolve(claim["artifact"]) == run / "predictions.json" and claim["sha256"] == hashes["predictions.json"], "Measured claim evidence mismatch")
    return metrics, model, rows, result["execution_seconds"]


def replay_model(bundle, folder, model_id, effort):
    record = load(folder / "result.json")
    for name, expected in record["files"].items():
        require(PurePosixPath(name).name == name, "Unsafe raw provider filename")
        bundle.check(folder / name, expected)
    require(set(record["files"]) == {"request.json", "events.jsonl", "response.txt", "stderr.log"}, "Provider file inventory changed")
    request = load(folder / "request.json")
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    require(record["status"] == "completed" and record["execution_kind"] == "real_model" and record["returncode"] == 0, "Actual successful model completion required")
    require(record["model"] == model_id and request["model"] == model_id and request["reasoning_effort"] == effort, "Provider model or effort changed")
    require(not record["tool_calls"], "Forbidden provider tool invocation")
    require(not any(e.get("item", {}).get("type") in ("command_execution", "mcp_tool_call", "web_search", "file_change") for e in events), "Raw provider tool invocation")
    complete = [e for e in events if e.get("type") == "turn.completed"]
    require(len(complete) == 1, "Exactly one raw completed turn required")
    usage = complete[0]["usage"]
    for key in ("input_tokens", "output_tokens"):
        require(isinstance(usage[key], int) and usage[key] >= 0 and usage[key] == record["usage"][key], "Raw provider usage mismatch")
    return usage["input_tokens"], usage["output_tokens"], record["wall_seconds"]


def replay(root, recorded_root, study_relative, unit_id, registration_sha256):
    bundle = Bundle(root, recorded_root)
    study = bundle.resolve(study_relative)
    registration = load(bundle.check(study / "pilot-registration.json", registration_sha256))
    for path, expected in registration["sources"].items():
        # Every original executing source has a relocatable immutable archive.
        name = bundle.path_class(path).name
        require(name not in bundle.trusted_sources, "Ambiguous registered source filename")
        bundle.check(study / "source-snapshot/evidence_research" / name, expected)
        bundle.trusted_sources[name] = expected
    entry = next(e for e in registration["units"] if e["unit_id"] == unit_id)
    owner = load(bundle.check(bundle.resolve(entry["owner_path"]), entry["owner_sha256"]))
    public = load(bundle.check(bundle.resolve(entry["public_path"]), entry["public_sha256"]))
    require(value_sha(owner["test"]) == owner["test_sha256"], "Owner test digest changed")
    arms = {}
    for arm in ("B", "C"):
        output = study / "units" / unit_id / arm
        measurement, response = load(output / "owner-measurement.json"), load(output / "arm-response.json")
        resource = load(bundle.link(measurement["evidence"]["resource_audit"]))
        require(not resource["failed_model_attempt_dirs"], "Failed requests need their separate conservative-usage audit")
        cpu = [bundle.resolve(p) for p in response["cpu_execution_dirs"]]
        models = [bundle.resolve(p) for p in response["model_evidence_dirs"]]
        require(len(cpu) == len(set(cpu)) and len(models) == len(set(models)), "Repeated receipt paths in actual resource inventory")
        require(set(cpu) == {bundle.resolve(p) for p in resource["cpu_execution_dirs"]} and set(models) == {bundle.resolve(p) for p in resource["completed_model_evidence_dirs"]}, "Resource inventories disagree")
        cpu_results = {p: replay_cpu(bundle, p) for p in cpu}
        selected = bundle.resolve(response["selected_run_dir"])
        require(selected in cpu_results, "Selected CPU result absent from actual inventory")
        metrics, model, rows, _ = cpu_results[selected]
        require(all(rows[s] == public["task_bundle"][s] for s in rows), "CPU data differs from registered task")
        require(not {r["id"] for r in owner["test"]} & {r["id"] for s in rows.values() for r in s}, "Owner test overlaps public data")
        predicted = [math.fsum(w * r["x"]**p for p, w in enumerate(model["weights"])) for r in owner["test"]]
        test_mse = math.fsum((r["y"] - p)**2 for r, p in zip(owner["test"], predicted)) / len(predicted)
        require(equal(test_mse, measurement["test_mse"]) and equal(metrics["validation_mse"], measurement["validation_mse"]), "Independent owner/public metric differs")
        raw = [replay_model(bundle, p, registration["config"]["model_id"], registration["config"]["resource_envelope"]["reasoning_effort"]) for p in models]
        measures = {"input_tokens": sum(x[0] for x in raw), "output_tokens": sum(x[1] for x in raw),
                    "model_seconds": math.fsum(x[2] for x in raw), "provider_attempts": len(raw),
                    "actual_cpu_executions": len(cpu), "total_cpu_execution_seconds": math.fsum(x[3] for x in cpu_results.values())}
        require(all(equal(v, resource["measures"][k]) for k, v in measures.items()), "Raw resource totals differ from owner audit")
        for name in ("report-review.json", "companion-review.json"):
            review = load(output / name)
            require(review["reviewer_role"] == "independent_verifier" and review["status"] == "complete" and review["pending_claims"] == 0 and review["unsupported_claims"] == 0, "Historical independent review not complete")
        arms[arm] = {**metrics, "test_mse": test_mse, **measures}
    b, c = arms["B"], arms["C"]
    return {"valid": True, "kind": "relocated_published_development_metric_resource_replay", "unit_id": unit_id,
            "registration_sha256": registration_sha256, "arms": arms,
            "token_relative_reduction": 1 - (c["input_tokens"] + c["output_tokens"]) / (b["input_tokens"] + b["output_tokens"]),
            "test_mse_relative_reduction": 1 - c["test_mse"] / b["test_mse"],
            "checked_original_files": bundle.checked, "actual_model_calls": 0, "new_runner_executions": 0,
            "calculation_source_sha256": sha(__file__), "adopted": False,
            "scope": "Original bytes preserved; independent fit/prediction/owner-MSE and raw provider usage replay. Historical report reviews checked for declared status only, not freshly semantically adjudicated. Minimal-phase development diagnostic, never original-default superiority or final adoption."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--recorded-root", required=True)
    parser.add_argument("--study", default="runs/development/paired-pilot-v4")
    parser.add_argument("--unit", default="linear-seed7")
    parser.add_argument("--registration-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.root, args.recorded_root, args.study, args.unit, args.registration_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    require(not args.out.exists(), "Preserve prior replay result; choose a new output")
    args.out.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("valid", "unit_id", "arms", "token_relative_reduction", "test_mse_relative_reduction", "actual_model_calls", "new_runner_executions")}, ensure_ascii=True))
