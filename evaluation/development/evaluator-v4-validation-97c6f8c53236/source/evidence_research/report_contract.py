"""Common research-report sufficiency gate, separate from prose quality.

The companion's presence is insufficient: identifiers, metrics, execution
entrypoint and evidence hashes are checked against independently verified runs.
Numeric semantic reviews remain a separate responsibility.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from .tasks import sha256_file

REPORT_SCHEMA_VERSION = "research-report-sufficiency-1"


def verify_report_contract(path: Path, *, arm_output: Path, spec: dict,
                           verification: dict, selected_run_dir: Path) -> dict:
    path, arm_output, selected_run_dir = Path(path).resolve(), Path(arm_output).resolve(), Path(selected_run_dir).resolve()
    reasons, evidence = [], []
    if not path.is_relative_to(arm_output) or path.is_symlink():
        return {"valid": False, "reasons": ["report companion outside arm directory"], "evidence": []}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return {"valid": False, "reasons": [f"invalid report companion: {error}"], "evidence": []}
    evidence.append({"path": str(path), "sha256": sha256_file(path)})
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        reasons.append("unsupported report sufficiency schema")
    for field in ("goal", "hypothesis", "selection_reason"):
        if not isinstance(report.get(field), str) or not report[field].strip(): reasons.append(f"missing {field}")
    for field in ("limitations", "next_questions"):
        value = report.get(field)
        if not isinstance(value, list) or not value or any(not isinstance(v,str) or not v.strip() for v in value): reasons.append(f"missing meaningful {field}")
    unresolved = report.get("unresolved")
    if not isinstance(unresolved,list) or any(not isinstance(v,dict) or not all(isinstance(v.get(k),str) and v[k].strip() for k in ("question","reason")) for v in unresolved):
        reasons.append("unresolved questions/failures must be explicit, including an empty list if none")
    if report.get("selected_config") != spec["config"]: reasons.append("reported selected configuration differs")
    provenance = report.get("provenance", {})
    for key in ("task_id", "task_version", "seed", "split_manifest_sha256", "implementation_sha256", "evaluator_sha256"):
        if provenance.get(key) != spec.get(key): reasons.append(f"provenance mismatch: {key}")
    execution = report.get("execution", {})
    if execution.get("kind") != spec["execution_entrypoint"]["kind"] or execution.get("entrypoint") != spec["command"]:
        reasons.append("reported actual execution entrypoint differs")
    if execution.get("reproduction_command") != spec["reproduction_command"]:
        reasons.append("reproduction command missing or differs from registered command")
    result_path = selected_run_dir / "result.json"
    expected_hash = sha256_file(result_path)
    metrics = report.get("measured_metrics")
    seen = set()
    if not isinstance(metrics,list) or not metrics: reasons.append("actual measured metrics missing")
    else:
        for metric in metrics:
            name = metric.get("metric")
            value = metric.get("value")
            expected = verification.get("metrics",{}).get(name)
            if name in seen or metric.get("kind") != "measured" or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or expected is None or not math.isclose(value,expected,rel_tol=1e-12,abs_tol=1e-12):
                reasons.append("metric is duplicate, unverified or differs from independent recomputation")
            seen.add(name)
            if Path(metric.get("evidence_path","")).resolve() != result_path or metric.get("evidence_sha256") != expected_hash:
                reasons.append("measured metric lacks exact selected result evidence")
    if spec["metric"] not in seen: reasons.append("registered selection metric absent")
    links = report.get("evidence")
    if not isinstance(links,list) or not links: reasons.append("reproducible artifact links missing")
    else:
        for item in links:
            source = Path(item.get("path","")).resolve()
            if not source.is_relative_to(arm_output) or source.is_symlink() or not source.is_file() or sha256_file(source) != item.get("sha256"):
                reasons.append("report artifact source/hash invalid")
            else: evidence.append({"path":str(source),"sha256":item["sha256"]})
        if not any(Path(v.get("path","")).resolve()==result_path and v.get("sha256")==expected_hash for v in links):
            reasons.append("selected result artifact absent")
    references = report.get("references")
    if not isinstance(references,list) or not references or any(v.get("kind")!="literature" or not isinstance(v.get("url"),str) or not v["url"].startswith("https://") or not isinstance(v.get("claim"),str) or not v["claim"].strip() for v in references):
        reasons.append("primary-source references must be distinguished as literature claims")
    resources = report.get("resources", {})
    if not isinstance(resources.get("tokens_known"),bool) or not isinstance(resources.get("scope"),str) or not resources["scope"].strip():
        reasons.append("resource accounting uncertainty/scope absent")
    usage = resources.get("token_usage")
    if resources.get("tokens_known") is False and usage is not None: reasons.append("unknown total token usage must be null")
    if resources.get("tokens_known") is True and (not isinstance(usage,dict) or any(isinstance(usage.get(k),bool) or not isinstance(usage.get(k),int) or usage[k]<0 for k in ("input_tokens","output_tokens"))):
        reasons.append("known token usage requires nonnegative actual counts")
    seconds=resources.get("seconds")
    if seconds is not None and (isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<0): reasons.append("invalid seconds")
    return {"valid": not reasons, "schema_version":REPORT_SCHEMA_VERSION,"reasons":reasons,"evidence":evidence,
            "reported_resources": resources,
            "limits":"Checks common required research information and exact evidence links; does not establish equal literary quality or general scientific research quality."}
