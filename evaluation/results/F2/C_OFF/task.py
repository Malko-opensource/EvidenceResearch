"""Small external-agent task runner; no model or agent process is called."""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
import time
from pathlib import Path


def main() -> int:
    task_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    root = Path.cwd()
    with (root / "invocations.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"task_id": task_id, "started_ns": time.time_ns()}) + "\n")
    with (root / "input.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    spec = importlib.util.spec_from_file_location("candidate_solution", root / "solution.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load solution.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    started = time.perf_counter()
    result = module.summarize(rows)
    payload = {"task_id": task_id, "result": result,
               "resources": {"elapsed_seconds": time.perf_counter() - started,
                             "external_tokens": {"status": "unknown", "value": None}}}
    (root / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"artifact": "result.json", "task_id": task_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
