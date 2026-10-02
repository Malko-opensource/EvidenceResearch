"""Retrospective serialization of captured evidence; never calls a model or runner."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import sqlite3
import sys

PROJECT = Path(__file__).resolve().parents[2]
FUTURE = PROJECT / "work" / "next-version"
sys.path.insert(0, str(FUTURE))
from evidence_research.comparison_arms import compact_memory_record
from evidence_research.store import atomic_json, sha256_file


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def size(value):
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def audit(snapshot):
    snapshot = Path(snapshot).resolve()
    captured = load(snapshot / "audit.json")
    if not captured["checks_valid_for_captured_prefix"]:
        raise ValueError("Original captured prefix audit must be valid")
    runs = {run["run_id"]: run for run in load(snapshot / "runs.json")}
    db_path = snapshot / "research-snapshot.sqlite3"
    db = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    memories = {row["run_id"]: dict(row) for row in db.execute("SELECT * FROM memory")}
    db.close()
    compact = {}
    for run_id, row in memories.items():
        run = runs[run_id]
        original = {"spec": run["spec"], "result": run["result"], "verification": run["verification"],
                    "manifest": run["manifest"], "run_dir": run["run_dir"]}
        item = {"run_id": run_id, "hypothesis": row["hypothesis"], "outcome": row["outcome"],
            "verification_status": row["verification_status"], "config": run["spec"]["config"],
            "conditions": json.loads(row["applicability"]), "metrics": run["verification"].get("metrics", {}),
            "failure_reason": run["result"].get("failure_reason", run["result"].get("error")) or (
                "Registered success criterion was not met." if row["outcome"] == "failure" else None),
            "evidence_hash": row["evidence_hash"], "original_evidence": original}
        compact[run_id] = compact_memory_record(item)
    comparisons = []
    for observation in captured["actual_memory_exposure"]:
        request_path = Path(observation["raw_request_path"])
        if sha256_file(request_path) != observation["raw_request_sha256"]:
            raise ValueError("The captured raw request changed")
        request = load(request_path)
        payload = json.loads(request["prompt"])
        if any(item["run_id"] not in compact for item in payload["verified_memory"]):
            continue  # Different prefix capture times are already disclosed.
        proposed = {**payload, "verified_memory": [compact[item["run_id"]] for item in payload["verified_memory"]]}
        comparisons.append({"call_id": observation["call_id"], "retrieved_records": len(payload["verified_memory"]),
            "original_prompt_utf8_bytes": len(request["prompt"].encode("utf-8")),
            "memory_only_compacted_prompt_utf8_bytes": size(proposed),
            "original_memory_utf8_bytes": size(payload["verified_memory"]),
            "compacted_memory_utf8_bytes": size(proposed["verified_memory"]),
            "actual_original_provider_usage": load(request_path.parent / "result.json")["usage"],
            "actual_original_provider_usage_path": str(request_path.parent / "result.json"),
            "actual_original_provider_usage_sha256": sha256_file(request_path.parent / "result.json"),
            "raw_request_path": str(request_path), "raw_request_sha256": sha256_file(request_path),
            "compacted_request_executed": False, "compacted_request_tokens": None})
    source = Path(captured["source"])
    final = None
    response_path = source / "arm-response.json"
    if response_path.exists():
        response = load(response_path)
        selected_id = Path(response["selected_run_dir"]).name
        selected = runs.get(selected_id)
        best_ids = {check["metadata"]["run_id"] for check in captured["best"] if check["valid"]}
        final = {"arm_response_path": str(response_path), "arm_response_sha256": sha256_file(response_path),
                 "selected_run_id": selected_id, "selected_is_independently_valid_captured_best": bool(selected and selected_id in best_ids),
                 "stop_reason": response["stop_reason"],
                 "report_review_files_present": {name: (source / name).exists() for name in ("report-review.json", "companion-review.json")},
                 "review_scope": "Presence only; independent numeric adjudication belongs to the separate accountable reviewer."}
    output = Path(__file__).parent / "context-bytes" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True)
    report = {"kind": "retrospective_memory_serialization_diagnostic", "classification": "measured_serialization",
        "unit": "UTF-8 bytes", "captured_prefix_audit_path": str(snapshot / "audit.json"),
        "captured_prefix_audit_sha256": sha256_file(snapshot / "audit.json"), "snapshot_db_sha256": sha256_file(db_path),
        "source_files": [{"path": str(path), "sha256": sha256_file(path)} for path in
            (Path(__file__), FUTURE / "evidence_research" / "comparison_arms.py", FUTURE / "evidence_research" / "arms.py")],
        "comparisons": comparisons, "final_selection": final,
        "new_model_requests": 0, "new_cpu_executions": 0, "performance_claim": False,
        "limitations": ["This changes only memory serialization of old captured requests; no compacted request was sent to a model.",
            "New future cost feedback and the future five-record corpus are not included in this memory-only counterfactual serialization.",
            "Bytes do not measure tokens, billing savings, quality, or framework improvement.",
            "Original measured token counts are retained only for the original executed requests."]}
    atomic_json(output / "serialization.json", report)
    print(json.dumps({"path": str(output / "serialization.json"), "comparison_count": len(comparisons),
        "last": comparisons[-1] if comparisons else None, "final_selection": final}, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    audit(parser.parse_args().snapshot)
