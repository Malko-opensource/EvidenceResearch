"""Owner's explicit semantic review of two pinned minimal-baseline reports.

These source reports were read independently in full. The line/token allowlists
are specific review judgments, not an automatic evaluator for unseen prose.
Original fitting/model receipts and participant reports are read only; test rows
and model providers are never opened or executed. Failed helper attempts remain.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1];sys.path.insert(0, str(ROOT))
from evidence_research.evaluation import adjudicate_numeric_review, recompute_resource_audit
from evidence_research.tasks import sha256_file, value_hash
from evidence_research.verifier import verify
from evaluation.review_partial_upstream import link, write_once

CASES = {
    11: {"primary": "a723c5c420a6a18169b482185a181041000feb9367216c184a95952cb951b0d8",
         "companion": "303d5e6674916abb7e031fe1a3f0eb6ba090c1ed6f1b91537173299269ab176d",
         "config": {"degree": 1, "alpha": 0.1}, "gap": "0.00224434",
         "lines": {18,21,23,27,29,33,38,46,54,56,58,61,65,68,70,78,82,90,91,96,98,101,103,112,117,121,123,135,137,145,159,160,162,171,174,176,178,180,186,187,189,191,193,196,200,206,207,216,218,223,225,228,230,232},
         "proposal_lines": {159,160,162,193,232}, "parameters": {"-1","0","0.01","0.1","1","2","8","10","100"}},
    19: {"primary": "99daf0f32e9de46b25fbd3ed236e9f3dfa410aadcf1505d453e8da95dd20ff30",
         "companion": "d59644c063a751951facf5b776c61cb4280c487f72828cee68d87fbb539773a7",
         "config": {"degree": 1, "alpha": 0.0}, "gap": "0.002419",
         "lines": {13,16,20,22,23,27,35,38,40,45,48,58,64,68,76,78,81,85,87,97,102,107,112,117,118,119,126,127,129,130,139,147,148,153,155,157,158,159,165,166,168,169,173,176,183,184,187,193,195,202,204,208,210,213},
         "proposal_lines": {20,81,117,118,119,148,157,158,159,208}, "parameters": {"-1","0","0.0","0.1","1","1.0","2","3","8","100"}},
}


def judgment(kind, source, rationale):
    return {"kind": kind, "source_path": str(source), "source_sha256": sha256_file(source), "rationale": rationale}


def finish_review(primitive, supplement, report, inventory, supplemental, evidence, derived):
    claims = primitive["claims"] + supplement
    pending = sum(item["outcome"] == "pending" for item in claims)
    unsupported = sum(item["outcome"] == "unsupported" for item in claims)
    return {**primitive, "claims": claims, "unsupported_claims": unsupported, "pending_claims": pending,
        "status": "pending" if pending else "complete", "whole_report_numeric_audit_complete": not pending,
        "regex_occurrences": len(primitive["claims"]), "supplemental_occurrences": len(supplement),
        "supplemental_inventory": link(supplemental), "semantic_review_source": link(Path(__file__)),
        "actual_history_evidence": link(evidence), "derived_calculation": link(derived),
        "original_report_modified": False, "independent_review_wall_seconds": None, "independent_review_usage": None,
        "final_evaluation": False, "comparison_improvement_claim": False,
        "study_scope": "Minimal upstream settings development diagnostic, excluded from confirmatory variance design.",
        "limits": "Quantity occurrences are not independent claims. Method/formula definitions, literature and unexecuted proposals are separate from measurements. No general discovery, literary quality, global optimum, test superiority or framework improvement is established. Provider resources exclude engineering and unmetered independent review."}


def review_case(seed, case):
    arm = ROOT / f"runs/development/paired-pilot-v4/units/linear-seed{seed}/B"
    review = arm / "independent_review/complete-numeric-review-v1";review.mkdir(parents=True, exist_ok=True)
    report, companion = arm / "report.txt", arm / "research_report.json"
    if sha256_file(report) != case["primary"] or sha256_file(companion) != case["companion"]:
        raise ValueError("semantic review belongs only to the exact two independently read reports")
    response = json.loads((arm / "arm-response.json").read_text(encoding="utf-8"))
    resource_path = arm / "independent-resource-audit.json";resources = recompute_resource_audit(resource_path)
    selected = Path(response["selected_run_dir"]).resolve();runs = []
    for folder in map(Path, response["cpu_execution_dirs"]):
        spec = json.loads((folder / "registered_spec.json").read_text(encoding="utf-8"))
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"));verification = verify(spec, result, folder)
        if result["status"] != "success" or not verification["valid"] or spec["config"] != case["config"]:
            raise ValueError("reported configuration failed original CPU verification")
        runs.append({"run_dir": str(folder), "spec": spec, "verification": verification, "result_evidence": link(folder / "result.json")})
    if len(runs) != 2 or len({value_hash(run["spec"]["config"]) for run in runs}) != 1:
        raise ValueError("two actual attempts / one distinct configuration does not match original inventory")
    metrics = next(run["verification"]["metrics"] for run in runs if Path(run["run_dir"]) == selected)
    if any(run["verification"]["metrics"] != metrics for run in runs):raise ValueError("repeated same-condition measurements differ")
    manifest = selected / "split_manifest.json";split = json.loads(manifest.read_text(encoding="utf-8"))
    if [split["splits"][key]["count"] for key in ("train", "validation", "test")] != [80,64,96]:raise ValueError("split metadata counts differ")
    evidence = review / "independent-execution-and-resource-evidence.json"
    write_once(evidence, {"runs": runs, "actual_cpu_executions": 2, "distinct_configurations": 1,
        "resources": resources, "resource_audit": link(resource_path), "public_split_manifest": link(manifest),
        "hidden_test_observations_opened": False, "source": link(Path(__file__))})
    gap = metrics["validation_mse"] - metrics["train_mse"]
    grid = [(d,a) for d in (range(1,9) if seed == 11 else (1,2,3))
            for a in ((0,0.01,0.1,1,10,100) if seed == 11 else (0,0.1,1))]
    digits = len(case["gap"].partition(".")[2])
    if abs(gap-float(case["gap"])) > .5*10**(-digits):raise ValueError("displayed gap rounding differs")
    remaining = response["resource_envelope"]["actual_cpu_executions_per_unit"] - resources["measures"]["actual_cpu_executions"]
    if remaining != 49:raise ValueError("reported remaining CPU allowance differs")
    derived = review / "independent-derived-arithmetic.json"
    write_once(derived, {"validation_minus_training": {"inputs": metrics, "value": gap, "display": case["gap"], "rounding_matches": True},
        "proposal_grid": {"candidates": grid, "count": len(grid), "actual_distinct": 1, "unmeasured": len(grid)-1,
            "kind": "proposal_arithmetic", "remaining_candidates_executed": False},
        "remaining_cpu_allowance": {"limit": response["resource_envelope"]["actual_cpu_executions_per_unit"], "actual": 2, "remaining": remaining},
        "inputs": [link(evidence)], "source": link(Path(__file__))})
    corpus = ROOT / "references/task_literature.json";literature = json.loads(corpus.read_text(encoding="utf-8"))
    if value_hash(literature["records"]) != literature["records_sha256"]:raise ValueError("frozen literature source differs")
    note = review / "independent-method-context.json"
    write_once(note, {"source": link(selected / "source/evidence_research/tasks.py"), "literature": link(corpus),
        "note": "Polynomial powers, indices, squared residual loss/normalizers and inverses are definitions. For the report's explicitly conventional centered design with unpenalized intercept and summed loss, ridge coefficients are (Z'Z+lambda I)^-1 Z'y, singular weights s/(s^2+lambda), and feature effective degrees of freedom sum s^2/(s^2+lambda). Positive lambda makes that coefficient system invertible. Nested exact unpenalized polynomial classes cannot increase minimum training squared loss. These conditional algebra statements do not assert the host's unspecified conventions or a measured regularization effect. Contrasts are algebraic definitions requiring both candidate measurements.",
        "limits": "Pre-registered candidate language refers to the upstream model's preexecution plan, not a completed comparison or the owner confirmatory protocol. Proposals are not executions. No statistical/test superiority is established."})
    inventory_path = arm / "numeric-inventory.json";inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    judgments = []
    for item in inventory["items"]:
        number, line = item["number"], item["line"];normalized = number.rstrip(".");entry = {"claim_id": item["claim_id"]}
        if line not in case["lines"]:raise ValueError(f"new unreviewed primary line {line}")
        if normalized in (str(metrics["train_mse"]), str(metrics["validation_mse"])):
            metric = "train_mse" if normalized == str(metrics["train_mse"]) else "validation_mse"
            entry.update(kind="measured", run_dir=str(selected), metric=metric, rationale="Independently reproduced actual CPU MSE, with local split scope and no independent test inference.")
        elif normalized in (case["gap"], "49"):continue
        elif normalized in ("0000", "0002"):
            source = next(Path(run["run_dir"]) / "registered_spec.json" for run in runs if Path(run["run_dir"]).name == "execution-"+normalized)
            entry.update(judgment("identifier", source, "Named actual invocation identifier, not a new experiment quantity."))
        elif normalized in ("80", "64", "96", str(seed)):
            entry.update(judgment("method", manifest, "Split count, MSE denominator or registered seed checked against public metadata; hidden test rows remain unopened."))
        elif normalized == "256":entry.update(judgment("identifier", manifest, "SHA-256 hash algorithm name, not measured task performance."))
        elif normalized == "51":entry.update(judgment("method", arm / "callback-registration.json", "Fixed shared CPU ceiling, not actual use or a Goal research-loop cap."))
        elif normalized in ("48", "47") or line in case["proposal_lines"]:
            entry.update(kind="proposal", rationale="Value/count/index in the explicitly unexecuted proposed grid. Independent arithmetic confirms the grid size and remaining count; no additional candidate measurement is asserted.")
        elif normalized in case["parameters"]:
            entry.update(judgment("method", note, "Literal model/allowed-domain parameter, polynomial exponent/index or mathematical constant in independently read context; conditional estimator/contrast definition, not a measured performance claim."))
        else:raise ValueError(f"new unreviewed primary quantity {line}:{number}")
        judgments.append(entry)
    primitive_path = review / "primary-primitive-adjudication.json";write_once(review / "primary-judgments.json", judgments)
    primitive = (json.loads(primitive_path.read_text(encoding="utf-8")) if primitive_path.exists() else
        adjudicate_numeric_review(inventory_path, judgments, primitive_path, reviewer_role="independent_verifier"))
    for item in primitive["claims"]:
        if item["number"].rstrip(".") in (case["gap"], "49"):
            item.update(kind="derived_measured" if item["number"].rstrip(".") == case["gap"] else "derived_resource_allowance",
                outcome="supported", reason="Independent subtraction of actual verified measurements or registered ceiling minus unique actual CPU receipts matches the display.", evidence=[link(derived)])
    supplement = []
    pattern = r"\b(?:one|two|three|four|eight|nine|single|singleton|zero|first|second|third)\b|\b\d{4}\.\d{5}v\d+\b|\[(?:11pt|margin=1in|T1)\]|_[0-9]+|(?<![\w.])[+-]?(?:\d+\.\d+|\.\d+)(?:[eE][+-]?\d+)?(?=\.(?:\s|$))"
    for ln, text in enumerate(report.read_text(encoding="utf-8").splitlines(),1):
        for match in re.finditer(pattern,text,re.I):
            token = match.group().lower();item = {"line":ln,"start":match.start(),"end":match.end(),"number":match.group(),"context":text}
            item["claim_id"] = value_hash({"report_sha256":case["primary"],**item})
            kind, outcome, why, links = "method", "classified_nonmeasurement", "", []
            if ln <= 4:kind,why,links = "identifier","Typesetting option, not scientific task quantity.",[link(report)]
            elif re.fullmatch(r"\d{4}\.\d{5}v\d+",token):
                if token not in {record["id"] for record in literature["records"]}:raise ValueError("unknown bibliography identifier")
                kind,why,links = "literature","Exact bibliographic ID from the frozen primary-source synopsis, not reproduced paper performance.",[link(corpus)]
            elif token == case["gap"]:kind,outcome,why,links = "derived_measured","supported","Terminal decimal missed by regex; verified metric subtraction matches displayed rounding.",[link(derived)]
            elif token in ("eight","nine") and seed == 19:
                kind,why,links = "proposal","Nine planned grid members / eight still unmeasured; actual one-configuration evidence remains separate.",[link(derived)]
            elif token in ("one","two") and re.match(r"(?:one|two)\s+(?:(?:actual|reported)\s+CPU\s+attempts|distinct\s+configuration|distinct\s+evaluated\s+configuration|evaluated\s+configuration)",text[match.start():],re.I):
                kind,outcome,why,links = "derived_execution_coverage","supported","Both actual CPU receipts have one distinct configuration; this is neither independent replication nor an alternative-model comparison.",[link(evidence)]
            else:
                why,links = "Polynomial degree/contrast parameter, mathematical subscript, split/one-action convention, negated inference, ordinal rule or literal report enumeration in independently read context; no unrecorded outcome implied.",[link(note),link(manifest),link(arm / "callback-registration.json")]
            supplement.append({**item,"kind":kind,"outcome":outcome,"reason":why,"evidence":links})
    supplemental = review / "primary-supplemental-inventory.json";write_once(supplemental,{"report_sha256":case["primary"],"items":supplement})
    final = finish_review(primitive,supplement,report,inventory_path,supplemental,evidence,derived)
    write_once(review / "primary-comprehensive-review.json",final);write_once(arm / "report-review.json",final)
    preparation = json.loads((arm / "independent_review/prepared-companion.json").read_text(encoding="utf-8"));judgments = preparation["judgments"][:]
    for item in preparation["pending_contexts"]:
        path = item["json_path"];entry = {"claim_id":item["claim_id"]}
        if path == ["hypothesis"]:entry.update(kind="proposal",rationale="Original hypothesis/ordered-grid parameter, explicitly a preexecution plan; only the named measured configuration was run.")
        elif path in (["limitations",0],["schema_version"]):entry.update(judgment("identifier",companion,"Benchmark or schema-version name, not an actual task count/measurement."))
        elif path == ["resources","actual_cpu_executions"]:entry.update(kind="measured_resource",resource_audit_path=str(resource_path),resource_metric="actual_cpu_executions",rationale="Independent hash-linked unique CPU inventory confirms two actual attempts, one distinct configuration.")
        elif path and path[0] == "resources" and path[-1] in ("proposal_calls_per_unit","actual_cpu_executions_per_unit"):
            entry.update(judgment("method",arm / "callback-registration.json","Registered shared resource allowance, not actual use or total research-loop cap."))
        else:raise ValueError(f"unreviewed companion context {path}")
        judgments.append(entry)
    ci = arm / "companion-numeric-inventory.json";cp = review / "companion-primitive-adjudication.json";write_once(review / "companion-judgments.json",judgments)
    primitive = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else adjudicate_numeric_review(ci,judgments,cp,reviewer_role="independent_verifier")
    supplement = []
    for ln,text in enumerate(companion.read_text(encoding="utf-8").splitlines(),1):
        for match in re.finditer(r"\b(?:one|two|three|eight|nine|zero|first|second|single)\b|\b\d{4}\.\d{5}v\d+\b",text,re.I):
            token = match.group().lower();item = {"line":ln,"start":match.start(),"end":match.end(),"number":match.group(),"context":text[max(0,match.start()-100):match.end()+100]}
            item["claim_id"] = value_hash({"report_sha256":case["companion"],**item})
            if re.fullmatch(r"\d{4}\.\d{5}v\d+",token):
                if token not in {record["id"] for record in literature["records"]}:raise ValueError("unknown companion bibliography")
                kind,why,links = "literature","Exact frozen source bibliographic URL.",[link(corpus)]
            else:kind,why,links = "proposal","Word-valued count/ordinal/literal degree in tagged original planning procedure or split/action convention; no extra execution or successful improvement asserted.",[link(derived),link(manifest),link(arm / "callback-registration.json")]
            supplement.append({**item,"kind":kind,"outcome":"classified_nonmeasurement","reason":why,"evidence":links})
    supplemental = review / "companion-supplemental-inventory.json";write_once(supplemental,{"report_sha256":case["companion"],"items":supplement})
    final = finish_review(primitive,supplement,companion,ci,supplemental,evidence,derived)
    write_once(review / "companion-comprehensive-review.json",final);write_once(arm / "companion-review.json",final)
    source = review / "source";source.mkdir(exist_ok=True)
    for original in (Path(__file__),ROOT / "evaluation/prepare_independent_review.py",ROOT / "evaluation/review_partial_upstream.py"):
        target = source / original.name
        if target.exists() and target.read_bytes() != original.read_bytes():raise ValueError("review source snapshot changed")
        if not target.exists():target.write_bytes(original.read_bytes())
    print(json.dumps({"seed":seed,"primary_occurrences":len(json.loads((arm / "report-review.json").read_text(encoding="utf-8"))["claims"]),"companion_occurrences":len(final["claims"]),"unsupported":final["unsupported_claims"],"pending":final["pending_claims"],"final_evaluation":False}))


if __name__ == "__main__":
    for seed,case in CASES.items():review_case(seed,case)
