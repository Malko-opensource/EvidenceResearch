"""Owner-fixed independent checks of preserved solution source.

This is a reliability boundary, not an OS security sandbox. The candidate is
trusted local code. Evaluation instructions prohibit reading these cases.
"""
from __future__ import annotations

import contextlib
import copy
import csv
import importlib.machinery
import importlib.util
import io
import json
import math
import subprocess
import sys
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path


def number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def weighted_reference(rows):
    valid = {}
    rejected = 0
    for row in rows:
        group = str(row.get("group", "")).strip()
        value, weight = number(row.get("value")), number(row.get("weight"))
        if not group or value is None or weight is None or weight <= 0:
            rejected += 1
        else:
            valid.setdefault(group, []).append((value, weight))
    groups = {}
    with localcontext() as context:
        context.prec = 60
        for group, entries in valid.items():
            weight = sum((entry[1] for entry in entries), Decimal(0))
            mean = sum((v * w for v, w in entries), Decimal(0)) / weight
            variance = sum((w * (v - mean) ** 2 for v, w in entries), Decimal(0)) / weight
            groups[group] = {"count": len(entries), "weight": float(weight),
                             "mean": float(mean), "variance": float(variance)}
    return {"groups": groups, "rejected": rejected}


def window_reference(rows):
    valid = []
    rejected = 0
    for row in rows:
        timestamp, value = number(row.get("timestamp")), number(row.get("value"))
        if timestamp is None or value is None:
            rejected += 1
        else:
            valid.append((timestamp, value))
    samples = []
    with localcontext() as context:
        context.prec = 60
        for timestamp in sorted({t for t, _ in valid}):
            window = [v for t, v in valid if timestamp - 3 < t <= timestamp]
            samples.append({"timestamp": float(timestamp), "count": len(window),
                            "mean": float(sum(window, Decimal(0)) / len(window))})
    return {"samples": samples, "rejected": rejected}


def event_reference(rows):
    valid = {}
    rejected, accepted = 0, 0
    for position, row in enumerate(rows):
        event_id, group = str(row.get("event_id", "")).strip(), str(row.get("group", "")).strip()
        timestamp, value = number(row.get("timestamp")), number(row.get("value"))
        if not event_id or not group or timestamp is None or value is None:
            rejected += 1
            continue
        accepted += 1
        previous = valid.get(event_id)
        if previous is None or (timestamp, position) > (previous[0], previous[1]):
            valid[event_id] = (timestamp, position, group, value)
    grouped = {}
    for _, _, group, value in valid.values():
        grouped.setdefault(group, []).append(value)
    with localcontext() as context:
        context.prec = 60
        groups = {group: {"count": len(values),
                          "mean": float(sum(values, Decimal(0)) / len(values))}
                  for group, values in grouped.items()}
    return {"groups": groups, "rejected": rejected, "duplicates": accepted - len(valid)}


def dev_reference(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["group"], []).append(Decimal(row["value"]))
    return {"groups": {group: float(sum(values) / len(values)) for group, values in grouped.items()}}


def cases_for(task_id):
    if task_id == "F1":
        cases = [
            [],
            [{"group": "a", "value": "1", "weight": "1"},
             {"group": "a", "value": "3", "weight": "3"}],
            [{"group": "offset", "value": str(10**12 + d), "weight": "1"} for d in (-2, 0, 2)],
            [{"group": "a", "value": "7", "weight": "0"},
             {"group": "a", "value": "4", "weight": "-2"},
             {"group": "a", "value": "NaN", "weight": "1"},
             {"group": "a", "value": "2", "weight": "inf"},
             {"group": " ", "value": "3", "weight": "1"},
             {"group": " a ", "value": "5", "weight": "2"}],
            [{"group": "x", "value": "-4", "weight": "0.5"},
             {"group": "x", "value": "2", "weight": "1.5"},
             {"group": "y", "value": "10", "weight": "2"}],
            [{"group": "x", "value": "", "weight": "1"},
             {"group": "x", "value": "abc", "weight": "2"},
             {"group": "x", "value": "1", "weight": ""}],
            [{"group": "offset", "value": str(10**9 + d), "weight": str(w)}
             for d, w in ((-3, 1), (0, 2), (4, 1))],
        ]
        return cases, weighted_reference
    if task_id == "F2":
        cases = [
            [],
            [{"timestamp": "0", "value": "2"}],
            [{"timestamp": str(t), "value": str(v)} for t, v in ((4, 8), (0, 2), (2, 4), (1, 6))],
            [{"timestamp": str(t), "value": str(v)} for t, v in ((0, 2), (3, 8), (3, 4), (6, 10))],
            [{"timestamp": str(t), "value": str(v)} for t, v in ((-2, -4), (-0.5, 2), (0.5, 8), (2.5, 4))],
            [{"timestamp": "bad", "value": "2"}, {"timestamp": "1", "value": "NaN"},
             {"timestamp": "inf", "value": "2"}, {"timestamp": "2", "value": ""},
             {"timestamp": "3", "value": "7"}],
            [{"timestamp": str(t), "value": str(10**12 + d)}
             for t, d in ((2, -2), (1, 0), (3, 2), (7, -4))],
        ]
        return cases, window_reference
    if task_id == "M_PRIOR":
        # Memory-seed development cases are disjoint from final M1/M2 cases.
        cases = [
            [{"event_id": "warmup_17", "group": "calibration", "timestamp": "20", "value": "7"},
             {"event_id": "warmup_17", "group": "calibration", "timestamp": "21", "value": "15"},
             {"event_id": "warmup_18", "group": "calibration", "timestamp": "21", "value": "25"}],
            [{"event_id": "prior_A", "group": "control", "timestamp": "40", "value": "11"},
             {"event_id": "prior_B", "group": "control", "timestamp": "42", "value": "19"},
             {"event_id": "prior_A", "group": "treated", "timestamp": "41", "value": "23"}],
        ]
        return cases, event_reference
    if task_id in {"M1", "M2"}:
        cases = [
            [],
            [{"event_id": "e1", "group": "a", "timestamp": "1", "value": "10"},
             {"event_id": "e1", "group": "a", "timestamp": "2", "value": "20"}],
            [{"event_id": "e1", "group": "a", "timestamp": "2", "value": "20"},
             {"event_id": "e1", "group": "a", "timestamp": "1", "value": "10"},
             {"event_id": "e2", "group": "a", "timestamp": "3", "value": "40"}],
            [{"event_id": "e1", "group": "a", "timestamp": "2", "value": "20"},
             {"event_id": "e1", "group": "b", "timestamp": "2", "value": "30"}],
            [{"event_id": " e1 ", "group": " a ", "timestamp": "1", "value": "3"},
             {"event_id": "e1", "group": "a", "timestamp": "1", "value": "3"},
             {"event_id": "", "group": "a", "timestamp": "2", "value": "4"},
             {"event_id": "e2", "group": "a", "timestamp": "bad", "value": "4"},
             {"event_id": "e3", "group": "a", "timestamp": "2", "value": "NaN"}],
            [{"event_id": "e1", "group": "a", "timestamp": "1", "value": "5"},
             {"event_id": "e1", "group": "a", "timestamp": "2", "value": "invalid"},
             {"event_id": "e2", "group": "b", "timestamp": "0", "value": "-5"}],
        ]
        return cases, event_reference
    if task_id == "D":
        return [[{"group": "a", "value": "1"}, {"group": "a", "value": "3"}]], dev_reference
    raise ValueError("Unknown preregistered task_id")


def matches(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(
            matches(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            matches(a, e) for a, e in zip(actual, expected))
    if isinstance(expected, int):
        return type(actual) is int and actual == expected
    if isinstance(expected, float):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
            return False
        # Absolute tolerance + two representable double steps; no loose large-value relative tolerance.
        tolerance = 1e-8 + 2 * math.ulp(expected)
        return abs(actual - expected) <= tolerance
    return actual == expected


def worker(source):
    rows = json.load(sys.stdin)
    loader = importlib.machinery.SourceFileLoader("preserved_candidate", str(source))
    spec = importlib.util.spec_from_loader("preserved_candidate", loader)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load preserved source")
    module = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(module)
        result = module.summarize(copy.deepcopy(rows))
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


def validate(bundle_path):
    bundle = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    spec = bundle["registration"]["spec"]
    task_id = spec["task_id"]
    artifacts = bundle["artifacts"]
    source = Path(artifacts["solution.py"])
    if not source.is_file():
        raise ValueError("Preserved solution.py artifact is missing")
    # A successful run must produce a parseable result of the declared task.
    run_result = json.loads(Path(artifacts["result.json"]).read_text(encoding="utf-8"))
    if run_result.get("task_id") != task_id or "result" not in run_result:
        raise ValueError("Run artifact does not identify the preregistered task")
    cases, reference = cases_for(task_id)
    with Path(artifacts["input.csv"]).open(encoding="utf-8", newline="") as stream:
        run_rows = list(csv.DictReader(stream))
    checks = [{"case": "run_artifact", "passed": matches(run_result["result"], reference(run_rows)),
               "reason": "run_artifact_recomputed", "exit_code": None}]
    for index, rows in enumerate(cases):
        completed = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).resolve()), "--worker", str(source)],
            input=json.dumps(rows), capture_output=True, text=True, encoding="utf-8")
        try:
            actual = json.loads(completed.stdout)
            passed = completed.returncode == 0 and matches(actual, reference(rows))
            reason = "matched" if passed else "result_mismatch"
        except (ValueError, TypeError):
            passed, reason = False, "candidate_error_or_invalid_json"
        checks.append({"case": index, "passed": passed, "reason": reason,
                       "exit_code": completed.returncode})
    count = sum(check["passed"] for check in checks)
    return {"metrics": {"pass_rate": count / len(checks)},
            "details": {"task_id": task_id, "passed_cases": count, "total_cases": len(checks),
                        "checks": checks, "basis": "preserved_source_recomputed",
                        "reported_run_metrics_used": False}}


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(sys.argv[2])
    elif len(sys.argv) == 2:
        print(json.dumps(validate(sys.argv[1]), sort_keys=True, allow_nan=False))
    else:
        raise SystemExit("Usage: fixed_validator.py BUNDLE | --worker SOURCE")
