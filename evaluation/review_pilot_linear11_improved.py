"""Independent review of the pinned linear11 C development diagnostic report.

All preserved CPU receipts and the read-only research store are checked. Report
numeric facts are separated from stored proposals and the model's stopping
judgment. No model call, participant-file edit or hidden-test observation access.
"""
from __future__ import annotations
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_research.evaluation import adjudicate_numeric_review, recompute_resource_audit
from evidence_research.tasks import sha256_file, value_hash
from evidence_research.verifier import verify
from evaluation.review_partial_upstream import link, write_once

ARM = ROOT / "runs/development/paired-pilot-v4/units/linear-seed11/C"
REVIEW = ARM / "independent_review/complete-numeric-review-v1"
HASHES = {"primary": "86198593064ba31ed416905c569814b1d162c3be0d1cd3b25b4bcf020af44db2",
          "companion": "585b852d47782b764c1dddda571157399c570392b4225ae4e44d9497db727605"}


def main():
    REVIEW.mkdir(parents=True, exist_ok=True)
    response = json.loads((ARM / "arm-response.json").read_text(encoding="utf-8"))
    selected = Path(response["selected_run_dir"]).resolve()
    companion = json.loads((ARM / "research_report.json").read_text(encoding="utf-8"))
    resource_path = ARM / "independent-resource-audit.json"
    resources = recompute_resource_audit(resource_path)
    database = ARM / "research/research.sqlite3"
    database_hash = sha256_file(database)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        rows = [{"run_id": r[0], "spec": json.loads(r[1]), "outcome": r[2], "status": r[3]}
                for r in db.execute("SELECT run_id,spec,outcome,status FROM runs ORDER BY created_at,run_id")]
    if sha256_file(database) != database_hash:
        raise ValueError("read-only research-store query changed original evidence")
    runs = []
    for row in rows:
        run = ARM / "research/evidence" / row["run_id"]
        result = json.loads((run / "result.json").read_text(encoding="utf-8"))
        verification = verify(row["spec"], result, run)
        if row["status"] != "completed" or not verification["valid"] or result["status"] != "success":
            raise ValueError("stored execution does not independently verify")
        runs.append({**row, "run_dir": str(run), "verification": verification, "result_evidence": link(run / "result.json")})
    if len(runs) != 25 or len({value_hash(row["spec"]["config"]) for row in runs}) != 25:
        raise ValueError("25 distinct verified-configuration claim differs from original evidence")
    if {str(Path(p).resolve()) for p in response["cpu_execution_dirs"]} != {r["run_dir"] for r in runs}:
        raise ValueError("callback CPU receipts and stored completed runs differ")
    best = min(runs, key=lambda r: r["verification"]["metrics"]["validation_mse"])
    if Path(best["run_dir"]) != selected or best["spec"]["config"] != {"degree": 1, "alpha": 0.22965}:
        raise ValueError("selected configuration is not the claimed best measured one")
    non_linear = [r for r in runs if r["spec"]["config"]["degree"] >= 2]
    if {r["spec"]["config"]["degree"] for r in non_linear} != set(range(2, 9)) or any(r["verification"]["metrics"]["validation_mse"] <= best["verification"]["metrics"]["validation_mse"] for r in non_linear):
        raise ValueError("stopping rationale's tested-higher-degree comparison lacks evidence")
    failed = [r for r in runs if r["outcome"] == "failure"]
    if {r["spec"]["hypothesis"] for r in failed} != {q["question"] for q in companion["unresolved"]}:
        raise ValueError("reported unresolved hypotheses differ from original criterion-failure memory")
    evidence = REVIEW / "independent-execution-history-and-resource-evidence.json"
    write_once(evidence, {"runs": runs, "actual_cpu_executions": len(runs), "distinct_configurations": 25,
        "best_measured_run": best["run_id"], "best_measured_value": best["verification"]["metrics"]["validation_mse"],
        "failed_criterion_hypotheses": len(failed), "tested_higher_degree_values_worse": True,
        "resources": resources, "resource_audit": link(resource_path), "read_only_store": link(database),
        "hidden_test_observations_opened": False, "source": link(Path(__file__)),
        "limits": "The stopping statement about weak expected information value and unlikely future improvement is a planning inference, not an independently established probability or global optimum."})
    corpus = ROOT / "references/task_literature.json"
    literature = json.loads(corpus.read_text(encoding="utf-8"))
    for label, report_name, inventory_name, output_name in (
            ("primary", "report.md", "numeric-inventory.json", "report-review.json"),
            ("companion", "research_report.json", "companion-numeric-inventory.json", "companion-review.json")):
        report = ARM / report_name
        if sha256_file(report) != HASHES[label]:
            raise ValueError("independent classifications are pinned to exact reported content")
        preparation = json.loads((ARM / f"independent_review/prepared-{label}.json").read_text(encoding="utf-8"))
        judgments = preparation["judgments"][:]
        for item in preparation["pending_contexts"]:
            path, number = item["json_path"], item["number"]
            j = {"claim_id": item["claim_id"]}
            if path == ["hypothesis"] or path and path[0] == "unresolved":
                j.update(kind="proposal", rationale="Parameter within a explicitly tagged proposed/stored hypothesis. The unresolved item preserves its original failed criterion and does not claim a successful numerical improvement.")
            elif path == ["schema_version"]:
                j.update(kind="identifier", source_path=str(ARM / "research_report.json"), source_sha256=HASHES["companion"], rationale="Report schema version suffix, not a measured research outcome.")
            elif path == ["stop_reason"] and number == "0.007415982704051579":
                j.update(kind="measured", run_dir=str(selected), metric="validation_mse", rationale="Actual selected validation MSE independently recomputed. All 25 preserved candidates confirm it is the minimum among observed results; global optimality is unestablished.")
            elif path == ["stop_reason"] and number == "25":
                j.update(kind="measured_resource", resource_audit_path=str(resource_path), resource_metric="actual_cpu_executions", rationale="All 25 hash-linked CPU receipts independently verify and contain 25 distinct configurations, not 25 independent statistical repetitions.")
            elif path == ["stop_reason"] and number in ("1", "0.22965", "2", "8"):
                j.update(kind="method", source_path=str(evidence), source_sha256=sha256_file(evidence), rationale="Selected literal setting or tested degree range. Independent verification of every configuration confirms higher-degree recorded validation errors exceed the selected result; no population/test superiority is asserted.")
            else:
                raise ValueError(f"unreviewed narrative numeric context: {path}:{number}")
            judgments.append(j)
        inventory = ARM / inventory_name
        primitive_path = REVIEW / f"{label}-primitive-adjudication.json"
        write_once(REVIEW / f"{label}-primitive-judgments.json", judgments)
        primitive = (json.loads(primitive_path.read_text(encoding="utf-8")) if primitive_path.exists() else
                     adjudicate_numeric_review(inventory, judgments, primitive_path, reviewer_role="independent_verifier"))
        supplement = []
        for ln, text in enumerate(report.read_text(encoding="utf-8").splitlines(), 1):
            for match in re.finditer(r"\b\d{4}\.\d{5}v\d+\b", text):
                token = match.group()
                if token not in {r["id"] for r in literature["records"]}:
                    raise ValueError("unknown report bibliography ID")
                item = {"line": ln, "start": match.start(), "end": match.end(), "number": token, "context": text}
                item["claim_id"] = value_hash({"report_sha256": HASHES[label], **item})
                supplement.append({**item, "kind": "literature", "outcome": "classified_nonmeasurement",
                    "reason": "Bibliographic URL matches the exact frozen primary-source synopsis. Paper statements remain literature claims and are not local empirical outcomes.", "evidence": [link(corpus)]})
        supplemental_path = REVIEW / f"{label}-supplemental-inventory.json"
        write_once(supplemental_path, {"report_sha256": HASHES[label], "items": supplement})
        claims = primitive["claims"] + supplement
        if any(c["outcome"] in ("unsupported", "pending") for c in claims):
            raise ValueError("the independent review has unresolved or unsupported quantities")
        final = {**primitive, "claims": claims, "whole_report_numeric_audit_complete": True,
            "regex_occurrences": len(primitive["claims"]), "supplemental_occurrences": len(supplement),
            "supplemental_inventory": link(supplemental_path), "semantic_review_source": link(Path(__file__)),
            "actual_history_evidence": link(evidence), "original_report_modified": False,
            "independent_review_wall_seconds": None, "independent_review_usage": None,
            "final_evaluation": False, "comparison_improvement_claim": False,
            "study_scope": "Minimal upstream B settings paired development diagnostic; excluded from confirmatory variance design.",
            "limits": "Quantity occurrences are not independent scientific claims. Model stop forecasts and stored hypotheses remain planning judgments. Local validation selection, report sufficiency and numeric truth do not establish equal literary quality, general scientific discovery, hidden-test superiority or framework improvement. Provider resources exclude engineering and independent semantic review costs."}
        write_once(REVIEW / f"{label}-comprehensive-review.json", final)
        write_once(ARM / output_name, final)
        print(json.dumps({"label": label, "occurrences": len(claims), "unsupported": 0, "pending": 0, "final_evaluation": False}))
    source = REVIEW / "source";source.mkdir(exist_ok=True)
    for original in (Path(__file__), ROOT / "evaluation/prepare_independent_review.py", ROOT / "evaluation/review_partial_upstream.py"):
        destination = source / original.name
        if destination.exists() and destination.read_bytes() != original.read_bytes():
            raise ValueError("independent source snapshot changed")
        if not destination.exists():destination.write_bytes(original.read_bytes())


if __name__ == "__main__":main()
