"""Preregistered paired evaluation. No final suite is run on module import.

The harness owns withheld outcomes; arm callbacks receive only public training
and validation data. A restricted provider/tool boundary is still required: an
LLM with general filesystem access is not a blinded participant.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics
import time
from typing import Callable

from .tasks import TASK_VERSION, sha256_file, split_manifest, task_data, value_hash, write_json
from .verifier import verify
from .model_attempt_audit import audit_failed_model_attempts
from .report_contract import REPORT_SCHEMA_VERSION, verify_report_contract
from .model_request_audit import audit_request_settings

PROTOCOL_VERSION = "paired-evaluation-1"
EFFICIENCY_PROTOCOL_VERSION = "paired-efficiency-4-conservative-bound-report-contract"


def design_sample_size(pilot_deltas: list[float], *, meaningful_gain: float = 0.10,
                       precision_halfwidth: float = 0.05, power: float = 0.80,
                       variance_relative_se: float = 0.5) -> dict:
    """Design by pilot variance/power/precision, not a global research loop cap.

    Normal approximation is a planning assumption; the final claim uses a paired
    bootstrap interval. A pilot has enough variance degrees of freedom when the
    normal-theory relative SE of its variance is at most the requested value.
    """
    if meaningful_gain <= 0 or precision_halfwidth <= 0 or not 0 < variance_relative_se <= 1:
        raise ValueError("design tolerances must be positive")
    if power != 0.80:
        raise ValueError("this version documents z_power for 80% power only")
    minimum_pilot = math.ceil(2 / variance_relative_se**2) + 1
    if len(pilot_deltas) < minimum_pilot or any(not math.isfinite(x) for x in pilot_deltas):
        raise ValueError(f"at least {minimum_pilot} finite paired development deltas are needed to estimate variance")
    std = statistics.stdev(pilot_deltas)
    # Conservative scale floor prevents zero-variance pilot from implying perfect certainty.
    scale = max(std, meaningful_gain / 2)
    power_n = math.ceil(((1.6448536269514722 + 0.8416212335729143) * scale / meaningful_gain)**2)
    precision_n = math.ceil((1.959963984540054 * scale / precision_halfwidth)**2)
    n = max(minimum_pilot, power_n, precision_n)
    return {"n_pairs": n, "pilot_n": len(pilot_deltas), "pilot_std": std,
            "planning_std": scale, "power_n": power_n, "precision_n": precision_n,
            "meaningful_gain": meaningful_gain, "precision_halfwidth": precision_halfwidth,
            "alpha_one_sided": 0.05, "power": power, "variance_relative_se": variance_relative_se,
            "planning_assumption": "independent paired units; normal approximation; actual variability may differ",
            "scope": "final evaluation sample size, never a cap on research improvement loops"}


def paired_uncertainty(deltas: list[float], *, seed: int = 493781,
                       monte_carlo_tail_error: float = 0.005) -> dict:
    if len(deltas) < 2 or any(not math.isfinite(x) for x in deltas):
        return {"estimable": False, "reason": "at least two finite paired units required"}
    # 95% binomial MC error <= 0.005 for a 2.5% bootstrap tail.
    n_resamples = math.ceil(1.959963984540054**2 * 0.025 * 0.975 / monte_carlo_tail_error**2)
    rng = random.Random(seed)
    means = sorted(math.fsum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(n_resamples))
    lower = means[math.floor(0.025 * (n_resamples - 1))]
    upper = means[math.ceil(0.975 * (n_resamples - 1))]
    return {"estimable": True, "mean": statistics.mean(deltas), "std": statistics.stdev(deltas),
            "ci95": [lower, upper], "n_pairs": len(deltas), "bootstrap_resamples": n_resamples,
            "bootstrap_seed": seed, "method": "paired percentile bootstrap; approximate, assumes independent units",
            "mc_tail_error_target": monte_carlo_tail_error}


def design_efficiency_sample_size(pilot_token_gains: list[float], pilot_log_quality_ratios: list[float], *,
                                  minimum_token_gain: float = 0.20, anticipated_token_gain: float = 0.50,
                                  quality_relative_margin: float = 0.10,
                                  token_precision_halfwidth: float = 0.10) -> dict:
    """Separate confirmatory efficiency design; never an OR fallback for v1."""
    if len(pilot_token_gains) != len(pilot_log_quality_ratios):
        raise ValueError("pilot efficiency and quality observations must be paired")
    if not 0 < minimum_token_gain < anticipated_token_gain < 1 or quality_relative_margin <= 0:
        raise ValueError("declare a positive meaningful token reduction and quality margin")
    token_design = design_sample_size(pilot_token_gains,
                                     meaningful_gain=anticipated_token_gain - minimum_token_gain,
                                     precision_halfwidth=token_precision_halfwidth)
    log_margin = math.log1p(quality_relative_margin)
    quality_design = design_sample_size(pilot_log_quality_ratios,
                                       meaningful_gain=log_margin,
                                       precision_halfwidth=log_margin / 2)
    return {"n_pairs": max(token_design["n_pairs"], quality_design["n_pairs"]),
            "pilot_n": len(pilot_token_gains), "endpoint": "token_efficiency_with_noninferior_quality",
            "minimum_token_gain": minimum_token_gain, "anticipated_token_gain": anticipated_token_gain,
            "quality_relative_margin": quality_relative_margin, "quality_log_margin": log_margin,
            "token_design": token_design, "quality_design": quality_design,
            "quality_planning_true_log_ratio": 0.0,
            "scope": "paired evaluation sample, not a limit on research loops",
            "multiple_testing": "intersection-union: both token efficiency and noninferiority must pass; no OR criterion",
            "token_measure": "provider input_tokens + output_tokens; not price weighted; cached_input_tokens not double-counted"}


def create_final_suite(directory: Path, *, n_pairs: int, owner_seed: int) -> dict:
    """Owner-only operation. Do not give private-suite.json or its directory to a proposer.

    Fresh task definitions and data seeds are sampled *before* arm execution.
    This is a synthetic CPU benchmark, not general scientific research validity.
    """
    directory = Path(directory)
    if n_pairs < 2:
        raise ValueError("a final paired design requires at least two units")
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError("suite directory is not empty; sealed data cannot be replaced")
    directory.mkdir(parents=True, exist_ok=True)
    rng = random.Random(owner_seed)
    units = []
    for i in range(n_pairs):
        task_id = f"holdout-{i:05d}"
        degree = rng.choice((2, 3, 4, 5))
        definition = {"coefficients": [rng.uniform(-1.4, 1.4) for _ in range(degree + 1)],
                      "noise": rng.uniform(0.08, 0.5), "n_train": rng.choice((40, 64, 96))}
        seed = rng.randrange(2**32)
        data = task_data(task_id, seed, private_definition=definition)
        manifest = split_manifest(task_id, seed, private_definition=definition)
        bundle = {"train": data["train"], "validation": data["validation"], "split_manifest": manifest}
        public = {"task_id": task_id, "seed": seed, "task_version": TASK_VERSION,
                  "objective": "select polynomial ridge degree and alpha using train/validation only",
                  "metric": "validation_mse", "allowed_config": {"degree": "integer 1..8", "alpha": "finite 0..100"},
                  "task_bundle": bundle}
        public_file = directory / "public" / f"{task_id}.json"
        public_file.parent.mkdir(exist_ok=True)
        write_json(public_file, public)
        # Owner-only test outcomes, absent from the public bundle and arm directories.
        units.append({"unit_id": task_id, "public_file": str(public_file), "public_sha256": sha256_file(public_file),
                      "test": data["test"], "test_sha256": value_hash(data["test"]),
                      "definition_sha256": value_hash(definition)})
    private_file = directory / "private-suite.json"
    write_json(private_file, {"task_version": TASK_VERSION, "units": units})
    return {"private_file": str(private_file), "private_sha256": sha256_file(private_file), "n_pairs": n_pairs,
            "task_ids": [unit["unit_id"] for unit in units], "visibility": "owner-only test; proposer receives public_file content only"}


def frozen_sources(extra_sources: list[Path] | None = None) -> dict:
    # Freeze the framework as well as the evaluator; otherwise a caller could
    # silently revise a proposer between paired units without changing protocol.
    paths = sorted(Path(__file__).parent.glob("*.py"))
    paths += extra_sources or []
    return {str(path.resolve()): sha256_file(path) for path in paths}


def register_protocol(path: Path, *, design: dict, suite: dict, model_id: str,
                      baseline_provenance: dict, resource_envelope: dict,
                      extra_sources: list[Path] | None = None,
                      original_model_unavailable: str | None = None,
                      endpoint: str = "quality") -> dict:
    path = Path(path)
    if path.exists():
        raise FileExistsError("protocol already exists; do not retroactively change acceptance criteria")
    if suite["n_pairs"] != design["n_pairs"]:
        raise ValueError("suite size differs from preregistered design")
    if baseline_provenance.get("kind") not in ("original_upstream", "upstream_adaptation", "structural_baseline"):
        raise ValueError("baseline provenance must distinguish original, adaptation and structural proxy")
    if not model_id or not resource_envelope.get("proposal_calls_per_unit"):
        raise ValueError("actual model identifier and matched per-unit model budget required")
    cpu_limit=resource_envelope.get("actual_cpu_executions_per_unit")
    if "reasoning_effort" not in resource_envelope or isinstance(cpu_limit,bool) or not isinstance(cpu_limit,int) or cpu_limit<=0:
        raise ValueError("explicit matched reasoning effort and positive actual CPU execution budget required")
    if endpoint not in ("quality", "efficiency"):
        raise ValueError("choose one confirmatory endpoint before evaluation")
    if endpoint == "efficiency" and design.get("endpoint") != "token_efficiency_with_noninferior_quality":
        raise ValueError("efficiency endpoint requires its separate variance and noninferiority design")
    protocol = {"version": PROTOCOL_VERSION if endpoint == "quality" else EFFICIENCY_PROTOCOL_VERSION,
                "status": "preregistered", "design": design, "suite": suite,
                "model_id": model_id, "baseline_provenance": baseline_provenance,
                "resource_envelope": resource_envelope, "frozen_sources": frozen_sources(extra_sources),
                "primary_metric": "heldout_test_mse", "pair_delta": "(B_test_mse-C_test_mse)/max(B_test_mse,1e-12)",
                "adoption": {"minimum_mean_relative_gain": design.get("meaningful_gain"), "ci95_lower_greater_than": 0.0,
                             "all_pairs_present": True, "all_selected_runs_verified": True,
                             "no_unsupported_numeric_claims": True, "matched_resources": True,
                             "actual_model_execution": True, "whole_report_numeric_audit_complete": True,
                             "common_report_sufficiency": True},
                "secondary_metrics": ["task_success_rate", "validation_mse", "execution_seconds", "model_seconds",
                                      "provider_calls", "provider_billed_cost_if_known", "duplicate_executions",
                                      "recovered_errors", "unsupported_claims", "verified_memory_hits",
                                      "actual_cpu_executions", "total_cpu_execution_seconds", "selected_execution_seconds"],
                "resource_measure_scope":"research-provider inference requests and actual trusted CPU attempts; offline engineering, top-level agent work and independent semantic review are excluded; unmetered review time/usage is null",
                "success_definition": "test MSE <= 0.85 * fixed degree=1,alpha=0 reference test MSE",
                "model_effect_A": {"status": "unavailable" if original_model_unavailable else "not_yet_evaluated",
                                   "reason": original_model_unavailable},
                "visibility": "test rows and task answers must never be included in proposer inputs",
                "model_sampling": {"data_seed_matched": True, "model_seed": None,
                                   "limitation": "Codex provider does not expose a model sampling seed; same model/settings and paired tasks do not guarantee identical internal randomness"},
                "failed_model_attempt_policy": "all request/time accounting includes completed and failed attempts; unknown failed usage remains null; unknown C total makes efficiency inconclusive; unknown B total permits only a preregistered conservative reduction lower bound using B known nonnegative token units",
                "report_contract": {"schema_version": REPORT_SCHEMA_VERSION,
                                    "required_for_both_arms": True,
                                    "numeric_audit_scope": "primary report AND structured companion, independent reviewed inventories",
                                    "limits": "common evidence-linked content sufficiency; literary quality and general research quality are not established"},
                "contamination_rule": "if evaluation informs a revision, relabel it development and freeze a fresh suite"}
    if endpoint == "efficiency":
        protocol["primary_metric"] = "provider_token_relative_reduction_with_noninferior_test_mse"
        protocol["pair_delta"] = "1 - C_total_input_plus_output_tokens / B_known_input_plus_output_tokens; exact if B total known, conservative lower bound if B missing nonnegative failed usage"
        protocol["adoption"].pop("minimum_mean_relative_gain")
        protocol["adoption"].update({"token_gain_ci95_lower_greater_than": design["minimum_token_gain"],
                                   "quality_log_ratio_ci95_upper_less_than": design["quality_log_margin"],
                                   "rule": "both gates required; no quality-v1 OR fallback"})
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, protocol)
    return protocol


def _assert_frozen(protocol: dict) -> None:
    if protocol.get("status") != "preregistered" or protocol.get("version") not in (PROTOCOL_VERSION, EFFICIENCY_PROTOCOL_VERSION):
        raise ValueError("a preregistered supported protocol is required")
    for path, digest in protocol["frozen_sources"].items():
        if sha256_file(Path(path)) != digest:
            raise ValueError(f"frozen source changed: {path}")
    suite = protocol["suite"]
    if sha256_file(Path(suite["private_file"])) != suite["private_sha256"]:
        raise ValueError("sealed evaluation suite changed")


def _owner_metric(rows: list[dict], model: dict) -> float:
    # Calculate directly; no model-supplied numeric claims are accepted.
    weights = model["weights"]
    predictions = [math.fsum(w * row["x"]**p for p, w in enumerate(weights)) for row in rows]
    return math.fsum((row["y"] - pred)**2 for row, pred in zip(rows, predictions)) / len(rows)


def _audit_model_evidence(paths: list[str], arm_output: Path, model_id: str,
                          resource_envelope: dict | None = None) -> dict:
    """Recompute actual model call accounting and blindness qualification."""
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("distinct actual model call evidence directories are required")
    seconds, evidence, token_usage = [], [], {}
    for value in paths:
        folder = Path(value).resolve()
        if not folder.is_relative_to(arm_output.resolve()):
            raise ValueError("model evidence is outside the arm directory")
        request_path, result_path = folder / "request.json", folder / "result.json"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if resource_envelope is not None:
            audit_request_settings(request,result,model_id=model_id,resource_envelope=resource_envelope,
                                   folder=folder,arm_output=arm_output)
        if request.get("model") != model_id or result.get("model") != model_id:
            raise ValueError("model call identifier differs from preregistration")
        if result.get("execution_kind") != "real_model" or result.get("status") != "completed" or result.get("returncode") != 0:
            raise ValueError("incomplete or simulated model call cannot qualify for final comparison")
        required = {"request.json", "events.jsonl", "stderr.log", "response.txt"}
        if not required.issubset(result.get("files", {})):
            raise ValueError("actual model evidence inventory is incomplete")
        for filename, digest in result["files"].items():
            file = folder / filename
            if Path(filename).name != filename or file.is_symlink() or sha256_file(file) != digest:
                raise ValueError("model evidence file changed")
        events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        tool_events = [e for e in events if e.get("item", {}).get("type") not in (None, "agent_message", "reasoning")]
        completions = [e for e in events if e.get("type") == "turn.completed"]
        if tool_events or result.get("tool_calls") or len(completions) != 1:
            raise ValueError("model tool access or missing completion disqualifies blinded evaluation")
        usage = completions[0].get("usage", {})
        if usage != result.get("usage"):
            raise ValueError("model usage differs from raw provider completion")
        for name, amount in usage.items():
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
                raise ValueError("provider token usage is invalid")
            token_usage[name] = token_usage.get(name, 0) + amount
        if not all(isinstance(usage.get(name), int) and usage[name] > 0 for name in ("input_tokens", "output_tokens")):
            raise ValueError("input and output token accounting is required")
        wall = result.get("wall_seconds")
        if isinstance(wall, bool) or not isinstance(wall, (int, float)) or not math.isfinite(wall) or wall < 0:
            raise ValueError("model wall-clock accounting is invalid")
        seconds.append(wall)
        evidence.append({"path": str(result_path), "sha256": sha256_file(result_path),
                         "events_sha256": sha256_file(folder / "events.jsonl")})
    return {"provider_calls": len(paths), "model_seconds": math.fsum(seconds), "provider_billed_cost": None,
            "token_usage": token_usage, "evidence": evidence,
            "qualification": "no observed tool events; filesystem read prevention is not an OS security boundary"}


def _audit_cpu_executions(paths: list[str], *, arm_output: Path, public: dict,
                          model_id: str, resource_envelope: dict) -> dict:
    limit=resource_envelope.get("actual_cpu_executions_per_unit")
    if isinstance(limit,bool) or not isinstance(limit,int) or limit<=0:
        raise ValueError("a shared positive actual CPU execution limit must be registered")
    folders=[Path(v).resolve() for v in paths]
    if not folders or len(set(folders))!=len(folders) or len(folders)>limit:
        raise ValueError("actual CPU execution inventory is empty, duplicated or exceeds shared resources")
    discovered=set()
    for spec_path in arm_output.rglob("registered_spec.json"):
        folder=spec_path.parent.resolve()
        result_path=folder / "result.json"
        if not result_path.exists():raise ValueError("CPU inventory contains an unresolved execution")
        if json.loads(result_path.read_text(encoding="utf-8")).get("execution_kind")=="actual_cpu_execution":discovered.add(folder)
    if set(folders)!=discovered:
        raise ValueError("actual CPU execution inventory omits independently discovered runs")
    evidence,seconds=[],[]
    for folder in folders:
        if not folder.is_relative_to(arm_output.resolve()) or folder.is_symlink():
            raise ValueError("actual CPU evidence outside arm directory")
        spec=json.loads((folder / "registered_spec.json").read_text(encoding="utf-8"))
        result=json.loads((folder / "result.json").read_text(encoding="utf-8"))
        if spec.get("task_id")!=public["task_id"] or spec.get("seed")!=public["seed"] or spec.get("task_bundle")!=public["task_bundle"] or spec.get("model")!=model_id or spec.get("resource_envelope")!=resource_envelope:
            raise ValueError("actual CPU run task/model/split/resources differ from registered conditions")
        if not verify(spec,result,folder)["valid"]:
            raise ValueError("actual CPU inventory contains unverifiable completed evidence")
        elapsed=result.get("execution_seconds")
        if isinstance(elapsed,bool) or not isinstance(elapsed,(int,float)) or not math.isfinite(elapsed) or elapsed<0:
            raise ValueError("actual CPU time receipt is invalid")
        seconds.append(elapsed)
        evidence.append({"path":str(folder / "result.json"),"sha256":sha256_file(folder / "result.json")})
    return {"actual_cpu_executions":len(folders),"total_cpu_execution_seconds":math.fsum(seconds),"registered_limit":limit,"evidence":evidence,
            "scope":"actual trusted runner invocations including verified failures; parser rejections are not executions"}


def _audit_request_inventory(completed: list[str], failed: list[str], arm_output: Path) -> None:
    provided=[Path(v).resolve() for v in completed+failed]
    if len(set(provided))!=len(provided):raise ValueError("model request inventory double-counts a completion/failure")
    discovered=set()
    for request_path in arm_output.rglob("request.json"):
        request=json.loads(request_path.read_text(encoding="utf-8"))
        if request.get("execution_kind")!="real_model":continue
        folder=request_path.parent.resolve()
        if not (folder / "result.json").exists():raise ValueError("model inventory contains an unresolved requested execution")
        discovered.add(folder)
    if set(provided)!=discovered:
        raise ValueError("model accounting omits independently discovered actual requests")


def recompute_resource_audit(path: Path) -> dict:
    """Independently recompute resource measures from original request evidence."""
    path=Path(path).resolve()
    audit=json.loads(path.read_text(encoding="utf-8"))
    if audit.get("schema_version")!="independent-resource-audit-1":
        raise ValueError("unsupported independent resource audit")
    arm_output=Path(audit["arm_output"]).resolve()
    if not path.is_relative_to(arm_output) or path.is_symlink():
        raise ValueError("independent resource audit outside arm directory")
    _audit_request_inventory(audit["completed_model_evidence_dirs"],audit["failed_model_attempt_dirs"],arm_output)
    usage=_audit_model_evidence(audit["completed_model_evidence_dirs"],arm_output,audit["model_id"],audit["resource_envelope"])
    failed=audit_failed_model_attempts(audit["failed_model_attempt_dirs"],model_id=audit["model_id"],
        allowed_roots=[str(arm_output)],host_action_receipts=audit["host_action_receipts"],
        lineage_path=audit["continuation_lineage_path"],resource_envelope=audit["resource_envelope"],arm_output=str(arm_output))
    measures={"provider_calls":usage["provider_calls"],"provider_attempts":usage["provider_calls"]+failed["failed_attempts"],
              "failed_model_attempts":failed["failed_attempts"],"model_seconds":usage["model_seconds"]+failed["failed_seconds"]}
    for key in ("input_tokens","output_tokens"):
        measures[key]=None if failed["unknown_failed_token_usage"] else usage["token_usage"][key]+failed["failed_token_usage"][key]
        measures["completed_"+key]=usage["token_usage"][key]
    if "cpu_execution_dirs" in audit:
        selected=Path(audit["selected_run_dir"])
        spec=json.loads((selected / "registered_spec.json").read_text(encoding="utf-8"))
        public={key:spec[key] for key in ("task_id","seed","task_bundle")}
        cpu=_audit_cpu_executions(audit["cpu_execution_dirs"],arm_output=arm_output,public=public,
                                  model_id=audit["model_id"],resource_envelope=audit["resource_envelope"])
        for key in ("actual_cpu_executions","total_cpu_execution_seconds"):measures[key]=cpu[key]
    if measures!=audit["measures"]:
        raise ValueError("resource measurement differs from independently recomputed raw requests")
    return {"measures":measures,"unknown_failed_token_usage":failed["unknown_failed_token_usage"],
            "evidence":[{"path":str(path),"sha256":sha256_file(path)}]+usage["evidence"]+failed["evidence"],
            "scope":"raw actual provider-request measures, no price conversion; unknown total tokens remain null"}


def _audit_telemetry(response: dict, arm_output: Path) -> tuple[dict, dict]:
    path = Path(response["telemetry_evidence_path"]).resolve()
    if not path.is_relative_to(arm_output.resolve()) or path.is_symlink():
        raise ValueError("host telemetry evidence must remain inside the arm directory")
    telemetry = json.loads(path.read_text(encoding="utf-8"))
    if telemetry.get("provenance") != "trusted_host_audit":
        raise ValueError("LLM self-reported secondary metrics are not accepted")
    fields = ("duplicate_executions", "recovered_errors", "unsupported_claims", "verified_memory_hits")
    metrics = {}
    for name in fields:
        amount = telemetry.get(name)
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("host telemetry counters must be nonnegative integers")
        if response.get(name, amount) != amount:
            raise ValueError("response counters differ from host audit evidence")
        metrics[name] = amount
    sources = telemetry.get("sources", [])
    if not sources:
        raise ValueError("host telemetry must link original event/claim evidence")
    for item in sources:
        source = Path(item["path"]).resolve()
        if not source.is_relative_to(arm_output.resolve()) or sha256_file(source) != item["sha256"]:
            raise ValueError("telemetry source hash/path differs")
    full_review, review_evidence = False, []
    review_links = telemetry.get("report_review_paths", [])
    if telemetry.get("report_review_path"):
        review_links = [{"path": telemetry["report_review_path"], "sha256": telemetry["report_review_sha256"]}]
    unsupported_total = 0
    if len({str(Path(v["path"]).resolve()) for v in review_links}) != len(review_links):
        raise ValueError("duplicate report review artifacts")
    for review_link in review_links:
        review_path = Path(review_link["path"]).resolve()
        if not review_path.is_relative_to(arm_output.resolve()) or sha256_file(review_path) != review_link["sha256"]:
            raise ValueError("independent report claim review changed")
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if review.get("status") != "complete" or review.get("reviewer_role") != "independent_verifier" or review.get("pending_claims") != 0:
            raise ValueError("report claim inventory has not been independently completed")
        if sha256_file(Path(review["report_path"])) != review["report_sha256"] or sha256_file(Path(review["inventory_path"])) != review["inventory_sha256"]:
            raise ValueError("report or claim inventory changed after independent review")
        unsupported = sum(c["outcome"] == "unsupported" for c in review["claims"])
        if unsupported != review["unsupported_claims"]:
            raise ValueError("unsupported claim counters differ from independent whole-report review")
        unsupported_total += unsupported
        review_evidence.append({"path": str(review_path), "sha256": sha256_file(review_path),
                               "report_path": review["report_path"], "report_sha256": review["report_sha256"]})
    if review_links:
        if unsupported_total != metrics["unsupported_claims"]:
            raise ValueError("aggregate unsupported counter differs from independently reviewed report artifacts")
        full_review = telemetry.get("claim_audit_scope") in ("whole_report_numeric_inventory", "whole_report_and_companion_numeric_inventories")
    metrics["whole_report_numeric_audit_complete"] = full_review
    return metrics, {"path": str(path), "sha256": sha256_file(path), "sources": sources,
                     "claim_audit_scope": telemetry.get("claim_audit_scope", "structured metric-linked claims only"),
                     "report_claim_review": review_evidence}


def prepare_numeric_review(report_path: Path, inventory_path: Path) -> dict:
    """Conservative numeral inventory: semantics require an independent adjudicator.

    Bibliographic IDs and formulas are intentionally included rather than silently
    assumed to be facts. Unicode words denoting numbers need human review as well.
    """
    report_path, inventory_path = Path(report_path), Path(inventory_path)
    if inventory_path.exists():
        raise FileExistsError("claim inventory already exists")
    report_hash = sha256_file(report_path)
    text = report_path.read_text(encoding="utf-8")
    items = []
    pattern = r"(?<![\w.])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?![\w.])"
    for line_no, line in enumerate(text.splitlines(), 1):
        for match in re.finditer(pattern, line):
            item = {"line": line_no, "start": match.start(), "end": match.end(),
                    "number": match.group(), "context": line}
            item["claim_id"] = value_hash({"report_sha256": report_hash, **item})
            items.append(item)
    inventory = {"report_path": str(report_path.resolve()), "report_sha256": report_hash,
                 "status": "needs_independent_adjudication", "items": items,
                 "scope": "all regex decimal/scientific numeral occurrences; semantic meaning and spelled-out numbers require independent review"}
    write_json(inventory_path, inventory)
    return inventory


def adjudicate_numeric_review(inventory_path: Path, judgments: list[dict], output_path: Path, *,
                              reviewer_role: str) -> dict:
    """Review each numeral; measured task results are independently recomputed.

    Allowed classifications are measured, measured_resource, literature, method, identifier,
    inference, proposal and unsupported. Semantic classification is accountable
    reviewer evidence, never a proposer's self assessment.
    """
    if reviewer_role != "independent_verifier":
        raise ValueError("report claim review must be performed independently of the proposer")
    inventory_path, output_path = Path(inventory_path), Path(output_path)
    if output_path.exists():
        raise FileExistsError("claim adjudication cannot be overwritten")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if sha256_file(Path(inventory["report_path"])) != inventory["report_sha256"]:
        raise ValueError("report changed after claim inventory")
    indexed = {j["claim_id"]: j for j in judgments}
    if len(indexed) != len(judgments) or set(indexed) - {i["claim_id"] for i in inventory["items"]}:
        raise ValueError("duplicate or unknown claim judgment")
    reviews = []
    for item in inventory["items"]:
        judgment = indexed.get(item["claim_id"])
        outcome, evidence, reason = "pending", [], "independent semantic review missing"
        if judgment is not None:
            kind = judgment.get("kind")
            reason = judgment.get("rationale", "")
            if not reason.strip():
                raise ValueError("every classification needs an explicit independent rationale")
            if kind == "measured":
                run_dir = Path(judgment["run_dir"])
                spec = json.loads((run_dir / "registered_spec.json").read_text(encoding="utf-8"))
                result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
                verification = verify(spec, result, run_dir)
                metric = judgment["metric"]
                if not verification["valid"] or metric not in verification["metrics"]:
                    outcome = "unsupported"
                    reason += "; no independently verified metric"
                else:
                    value = verification["metrics"][metric]
                    token = item["number"].lower()
                    decimal, _, exponent = token.partition("e")
                    places = len(decimal.partition(".")[2])
                    rounding = 0.5 * 10**(-places + (int(exponent) if exponent else 0))
                    outcome = "supported" if math.isclose(float(token), value, abs_tol=rounding + 1e-12, rel_tol=1e-12) else "unsupported"
                    evidence = [{"path": str(run_dir / "result.json"), "sha256": sha256_file(run_dir / "result.json"),
                                 "metric": metric, "independent_value": value, "display_rounding_tolerance": rounding}]
            elif kind == "measured_resource":
                audited = recompute_resource_audit(Path(judgment["resource_audit_path"]))
                metric = judgment["resource_metric"]
                value = audited["measures"].get(metric)
                if value is None:
                    outcome = "unsupported"
                    reason += "; requested resource total is unknown or not audited"
                else:
                    token = item["number"].lower()
                    decimal, _, exponent = token.partition("e")
                    places = len(decimal.partition(".")[2])
                    rounding = 0.5 * 10**(-places + (int(exponent) if exponent else 0))
                    outcome = "supported" if math.isclose(float(token),value,abs_tol=rounding+1e-12,rel_tol=1e-12) else "unsupported"
                    evidence = audited["evidence"] + [{"resource_metric":metric,"independent_value":value,"display_rounding_tolerance":rounding}]
            elif kind in ("literature", "method", "identifier"):
                source = Path(judgment["source_path"])
                if sha256_file(source) != judgment["source_sha256"]:
                    raise ValueError("claim reference changed")
                outcome = "classified_nonmeasurement"
                evidence = [{"path": str(source), "sha256": judgment["source_sha256"]}]
            elif kind in ("inference", "proposal"):
                outcome = "classified_nonmeasurement"
            elif kind == "unsupported":
                outcome = "unsupported"
            else:
                raise ValueError("unknown claim classification")
            reviews.append({**item, "kind": kind, "outcome": outcome, "reason": reason, "evidence": evidence})
        else:
            reviews.append({**item, "kind": None, "outcome": outcome, "reason": reason, "evidence": evidence})
    report = {"status": "complete" if all(i["outcome"] != "pending" for i in reviews) else "pending",
              "reviewer_role": reviewer_role, "inventory_path": str(inventory_path.resolve()),
              "inventory_sha256": sha256_file(inventory_path), "report_path": inventory["report_path"],
              "report_sha256": inventory["report_sha256"], "claims": reviews,
              "unsupported_claims": sum(i["outcome"] == "unsupported" for i in reviews),
              "pending_claims": sum(i["outcome"] == "pending" for i in reviews),
              "limits": "numeric truth is checked for measured task metrics; semantic nonmeasurement classifications are independent reviewer judgments"}
    write_json(output_path, report)
    return report


def _score_arm(protocol: dict, unit: dict, public: dict, arm: str, arm_output: Path,
               callback: Callable[[dict, Path], dict]) -> dict:
    start = time.perf_counter()
    # No test rows, private file paths or answer definitions in this payload.
    payload = {"arm": arm, "model_id": protocol["model_id"], "resource_envelope": protocol["resource_envelope"],
               "public_task": public, "baseline_provenance": protocol["baseline_provenance"] if arm == "B" else None}
    response = callback(payload, arm_output)
    wall = time.perf_counter() - start
    if response.get("model_id") != protocol["model_id"] or response.get("model_execution_kind") != "actual_model_execution":
        raise ValueError("arm must use the preregistered actual model")
    if response.get("resource_envelope") != protocol["resource_envelope"]:
        raise ValueError("arm resource permissions/budget differ from preregistration")
    run_dir = Path(response["selected_run_dir"]).resolve()
    if not run_dir.is_relative_to(arm_output.resolve()):
        raise ValueError("selected evidence is outside the arm directory")
    spec = json.loads((run_dir / "registered_spec.json").read_text(encoding="utf-8"))
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    if spec.get("task_id") != public["task_id"] or spec.get("seed") != public["seed"] or spec.get("model") != protocol["model_id"]:
        raise ValueError("selected run is not the matched task/model/seed")
    if spec.get("task_bundle") != public["task_bundle"]:
        raise ValueError("selected run used a different public split")
    verification = verify(spec, result, run_dir)
    if not verification["valid"] or result["status"] != "success":
        raise ValueError("selected candidate did not pass independent verification")
    trace = Path(response["model_trace_path"]).resolve()
    if not trace.is_relative_to(arm_output.resolve()) or not trace.is_file():
        raise ValueError("actual model calls require trace evidence inside the arm directory")
    usage = _audit_model_evidence(response["model_evidence_dirs"], arm_output, protocol["model_id"], protocol["resource_envelope"])
    cpu_audit = _audit_cpu_executions(response.get("cpu_execution_dirs",[]),arm_output=arm_output,public=public,
                                    model_id=protocol["model_id"],resource_envelope=protocol["resource_envelope"])
    if str(run_dir) not in {str(Path(v).resolve()) for v in response["cpu_execution_dirs"]}:
        raise ValueError("selected run absent from actual CPU execution inventory")
    provider_calls = usage["provider_calls"]
    failed_dirs = response.get("failed_model_attempt_dirs", [])
    _audit_request_inventory(response["model_evidence_dirs"],failed_dirs,arm_output)
    host_receipts = {}
    for receipt_value in response.get("failed_model_host_receipts", []):
        receipt_file = Path(receipt_value).resolve()
        if not receipt_file.is_relative_to(arm_output.resolve()):
            raise ValueError("failed host receipt is outside the arm directory")
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        key = str(Path(receipt["attempt_result_path"]).resolve().parent)
        if key in host_receipts:
            raise ValueError("duplicate failed host receipt")
        host_receipts[key] = str(receipt_file)
    failed_usage = audit_failed_model_attempts(failed_dirs, model_id=protocol["model_id"],
        allowed_roots=[str(arm_output.resolve())], host_action_receipts=host_receipts,
        lineage_path=response.get("continuation_lineage_path"),resource_envelope=protocol["resource_envelope"],arm_output=str(arm_output))
    provider_attempts = provider_calls + failed_usage["failed_attempts"]
    if provider_attempts > protocol["resource_envelope"]["proposal_calls_per_unit"]:
        raise ValueError("provider call budget exceeded")
    trace_content = trace.read_text(encoding="utf-8")
    if not trace_content.strip():
        raise ValueError("model trace is empty")
    counters, telemetry_evidence = _audit_telemetry(response, arm_output)
    report_contract = (verify_report_contract(Path(response["report_contract_path"]), arm_output=arm_output,
                          spec=spec, verification=verification, selected_run_dir=run_dir)
                       if response.get("report_contract_path") else
                       {"valid": False, "reasons": ["common report companion missing"], "evidence": []})
    reviewed_paths = {str(Path(item["report_path"]).resolve()) for item in telemetry_evidence["report_claim_review"]}
    required_paths = {str(Path(response[key]).resolve()) for key in ("report_path","report_contract_path") if response.get(key)}
    counters["whole_report_numeric_audit_complete"] = bool(counters["whole_report_numeric_audit_complete"] and len(required_paths)==2 and required_paths.issubset(reviewed_paths))
    model = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
    test_mse = _owner_metric(unit["test"], model)
    evidence = {"run_dir": str(run_dir), "spec_sha256": value_hash(spec), "result_sha256": sha256_file(run_dir / "result.json"),
                "model_sha256": sha256_file(run_dir / "model.json"), "trace_path": str(trace), "trace_sha256": sha256_file(trace),
                "test_sha256": unit["test_sha256"], "verification": verification,
                "model_calls": usage["evidence"], "telemetry": telemetry_evidence,
                "failed_model_attempt_audit": failed_usage, "report_contract": report_contract, "cpu_audit":cpu_audit}
    total_tokens = None if failed_usage["unknown_failed_token_usage"] else {
        key: usage["token_usage"][key] + failed_usage["failed_token_usage"][key]
        for key in ("input_tokens", "output_tokens")}
    resource_measures={"provider_calls":provider_calls,"provider_attempts":provider_attempts,
                       "failed_model_attempts":failed_usage["failed_attempts"],
                       "model_seconds":usage["model_seconds"]+failed_usage["failed_seconds"],
                       "actual_cpu_executions":cpu_audit["actual_cpu_executions"],
                       "total_cpu_execution_seconds":cpu_audit["total_cpu_execution_seconds"]}
    for key in ("input_tokens","output_tokens"):
        resource_measures[key]=None if total_tokens is None else total_tokens[key]
        resource_measures["completed_"+key]=usage["token_usage"][key]
    resource_record={"schema_version":"independent-resource-audit-1","model_id":protocol["model_id"],
                     "resource_envelope":protocol["resource_envelope"],"arm_output":str(arm_output.resolve()),
                     "completed_model_evidence_dirs":response["model_evidence_dirs"],"failed_model_attempt_dirs":failed_dirs,
                     "cpu_execution_dirs":response["cpu_execution_dirs"],"selected_run_dir":str(run_dir),
                     "host_action_receipts":host_receipts,"continuation_lineage_path":response.get("continuation_lineage_path"),
                     "measures":resource_measures}
    resource_path=arm_output / "independent-resource-audit.json"
    if resource_path.exists() and json.loads(resource_path.read_text(encoding="utf-8"))!=resource_record:
        raise ValueError("independent resource measurement changed on resume")
    if not resource_path.exists():write_json(resource_path,resource_record)
    evidence["resource_audit"]={"path":str(resource_path),"sha256":sha256_file(resource_path)}
    reported_resources = report_contract.get("reported_resources", {})
    if reported_resources.get("tokens_known") != (total_tokens is not None) or reported_resources.get("token_usage") != total_tokens:
        report_contract["reasons"].append("report resource token accounting differs from raw completed/failed attempts")
        report_contract["valid"] = False
    reported_seconds = reported_resources.get("seconds")
    if reported_seconds is not None and not math.isclose(reported_seconds, usage["model_seconds"] + failed_usage["failed_seconds"], rel_tol=1e-9, abs_tol=1e-9):
        report_contract["reasons"].append("report model seconds differ from raw completed/failed attempts")
        report_contract["valid"] = False
    return {"status": "verified", "arm": arm, "unit_id": unit["unit_id"], "model_id": protocol["model_id"], "test_mse": test_mse,
            "validation_mse": verification["metrics"]["validation_mse"],
            "selected_execution_seconds":result["execution_seconds"],
            "total_cpu_execution_seconds":cpu_audit["total_cpu_execution_seconds"],
            "execution_seconds":cpu_audit["total_cpu_execution_seconds"],
            "model_seconds": usage["model_seconds"] + failed_usage["failed_seconds"], "arm_wall_seconds": wall,
            "provider_calls": provider_calls, "provider_attempts": provider_attempts,
            "actual_cpu_executions":cpu_audit["actual_cpu_executions"],
            "failed_model_attempts": failed_usage["failed_attempts"], "failed_model_seconds": failed_usage["failed_seconds"],
            "provider_billed_cost": usage.get("provider_billed_cost"),
            **counters, "common_report_sufficiency": report_contract["valid"], "provider_token_usage": usage["token_usage"],
            "total_provider_token_usage": total_tokens, "unknown_token_usage": failed_usage["unknown_failed_token_usage"],
            "token_usage_scope": "completed calls only" if total_tokens is None else "all completed and failed requests",
            "resource_scope":"research-provider inference resources and actual trusted CPU attempts; offline framework engineering, top-level agent work and independent semantic review are excluded",
            "independent_numeric_review_seconds":None,"independent_numeric_review_usage":None,
            "evidence": evidence}


def _failure_score(unit: dict, arm: str, arm_output: Path, error: Exception) -> dict:
    """A failed arm is a durable denominator member; a fresh success cannot replace it."""
    external = type(error).__name__ == "ModelUnavailable" and "Forbidden" not in str(error)
    error_path = arm_output / "owner-failure.json"
    write_json(error_path, {"error_type": type(error).__name__, "error": str(error),
                            "classification": "external_resource_unavailable" if external else "failed_execution_or_verification"})
    files = [{"path": str(path.resolve()), "sha256": sha256_file(path)} for path in arm_output.rglob("*")
             if path.is_file() and not path.is_symlink() and path.name != "owner-score.json"]
    return {"status": "external_resource_unavailable" if external else "failed", "arm": arm, "unit_id": unit["unit_id"],
            "task_success": False, "test_mse": None, "validation_mse": None, "execution_seconds": None,
            "model_seconds": None, "arm_wall_seconds": None, "provider_calls": None, "provider_billed_cost": None,
            "duplicate_executions": None, "recovered_errors": None, "unsupported_claims": None,
            "verified_memory_hits": None, "provider_token_usage": None, "error": str(error),
            "evidence": {"failure_files": files},
            "retry_policy": "no automatic callback retry; reconcile original evidence or preregister a new development study"}


def _validate_saved_score(score: dict, unit: dict, arm_output: Path) -> None:
    evidence = score.get("evidence", {})
    if score.get("status") != "verified":
        for item in evidence.get("failure_files", []):
            path = Path(item["path"])
            if not path.resolve().is_relative_to(arm_output.resolve()) or sha256_file(path) != item["sha256"]:
                raise ValueError("completed failure evidence changed")
        return
    run_dir = Path(evidence["run_dir"])
    for name, field in (("result.json", "result_sha256"), ("model.json", "model_sha256")):
        if sha256_file(run_dir / name) != evidence[field]:
            raise ValueError("completed arm evidence changed")
    spec = json.loads((run_dir / "registered_spec.json").read_text(encoding="utf-8"))
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    verification=verify(spec,result,run_dir)
    if value_hash(spec) != evidence["spec_sha256"] or not verification["valid"]:
        raise ValueError("completed arm no longer verifies")
    if score["validation_mse"]!=verification["metrics"]["validation_mse"]:
        raise ValueError("completed validation metric differs from independent evidence")
    model = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
    if score["test_mse"] != _owner_metric(unit["test"], model):
        raise ValueError("completed owner metric differs from fixed hidden data")
    if sha256_file(Path(evidence["trace_path"])) != evidence["trace_sha256"]:
        raise ValueError("completed model trace changed")
    model_dirs = [str(Path(item["path"]).parent) for item in evidence["model_calls"]]
    usage = _audit_model_evidence(model_dirs, arm_output, score["model_id"])
    if score["provider_calls"] != usage["provider_calls"] or score["provider_token_usage"] != usage["token_usage"]:
        raise ValueError("completed model accounting differs from provider evidence")
    failed_audit = evidence.get("failed_model_attempt_audit", {})
    for item in failed_audit.get("evidence", []):
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError("failed model request/lineage evidence changed")
    resource_link=evidence.get("resource_audit")
    if resource_link:
        if sha256_file(Path(resource_link["path"]))!=resource_link["sha256"]:
            raise ValueError("independent resource evidence changed")
        audited=recompute_resource_audit(Path(resource_link["path"]))
        for name in ("provider_calls","provider_attempts","failed_model_attempts","model_seconds","actual_cpu_executions","total_cpu_execution_seconds"):
            if name in audited["measures"] and score.get(name)!=audited["measures"][name]:
                raise ValueError("saved resource counters differ from independently recomputed evidence")
        expected_totals=None if audited["unknown_failed_token_usage"] else {key:audited["measures"][key] for key in ("input_tokens","output_tokens")}
        if score.get("total_provider_token_usage")!=expected_totals or score.get("unknown_token_usage")!=audited["unknown_failed_token_usage"]:
            raise ValueError("saved token totals/uncertainty differ from independently recomputed evidence")
    for item in evidence.get("cpu_audit",{}).get("evidence",[]):
        if sha256_file(Path(item["path"]))!=item["sha256"]:
            raise ValueError("actual CPU execution evidence changed")
    for item in evidence.get("report_contract", {}).get("evidence", []):
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise ValueError("report sufficiency companion evidence changed")
    if score.get("provider_attempts") != usage["provider_calls"] + failed_audit.get("failed_attempts", 0):
        raise ValueError("completed attempt accounting differs")
    telemetry = evidence["telemetry"]
    if sha256_file(Path(telemetry["path"])) != telemetry["sha256"]:
        raise ValueError("completed host telemetry changed")
    _audit_telemetry({"telemetry_evidence_path": telemetry["path"]}, arm_output)


def run_matched(protocol_path: Path, output_dir: Path, *, baseline: Callable[[dict, Path], dict],
                improved: Callable[[dict, Path], dict]) -> dict:
    """Explicit final operation. Callback results are measurements, not LLM self scores."""
    protocol_path, output_dir = Path(protocol_path), Path(output_dir)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    _assert_frozen(protocol)
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir / "protocol-lock.json"
    lock = {"protocol_path": str(protocol_path.resolve()), "protocol_sha256": sha256_file(protocol_path)}
    if lock_path.exists():
        if json.loads(lock_path.read_text(encoding="utf-8")) != lock:
            raise ValueError("resume protocol differs from original evaluation")
    else:
        write_json(lock_path, lock)
    suite = json.loads(Path(protocol["suite"]["private_file"]).read_text(encoding="utf-8"))
    from .tasks import fit
    pairs = []
    external_blocked = None
    for index, unit in enumerate(suite["units"]):
        pair_path = output_dir / f"{unit['unit_id']}-pair.json"
        if pair_path.exists():
            saved = json.loads(pair_path.read_text(encoding="utf-8"))
            if saved.get("protocol_sha256") != lock["protocol_sha256"]:
                raise ValueError("completed pair belongs to another protocol")
            for arm in ("B", "C"):
                _validate_saved_score(saved[arm], unit, output_dir / unit["unit_id"] / arm)
            pairs.append(saved)
            continue
        public_file = Path(unit["public_file"])
        if sha256_file(public_file) != unit["public_sha256"] or value_hash(unit["test"]) != unit["test_sha256"]:
            raise ValueError("sealed task data changed")
        public = json.loads(public_file.read_text(encoding="utf-8"))
        if set(r["id"] for r in unit["test"]) & set(r["id"] for s in ("train", "validation") for r in public["task_bundle"][s]):
            raise ValueError("private test split overlaps public data")
        responses = {}
        # Alternate arm order to reduce time/order bias; both arms get fresh state.
        arm_order = (("B", baseline), ("C", improved)) if index % 2 == 0 else (("C", improved), ("B", baseline))
        for arm, callback in arm_order:
            arm_output = output_dir / unit["unit_id"] / arm
            arm_output.mkdir(parents=True, exist_ok=True)
            score_path = arm_output / "owner-score.json"
            if score_path.exists():
                score = json.loads(score_path.read_text(encoding="utf-8"))
                if score.get("protocol_sha256") != lock["protocol_sha256"]:
                    raise ValueError("completed arm belongs to another protocol")
                _validate_saved_score(score, unit, arm_output)
            else:
                try:
                    if external_blocked is not None:
                        # One known missing external resource is sufficient to avoid
                        # issuing other calls needing that same resource.
                        raise external_blocked
                    score = _score_arm(protocol, unit, public, arm, arm_output, callback)
                except Exception as error:
                    score = _failure_score(unit, arm, arm_output, error)
                    if score["status"] == "external_resource_unavailable":
                        external_blocked = error
                score["protocol_sha256"] = lock["protocol_sha256"]
                write_json(score_path, score)
            responses[arm] = score
        reference_model = fit(public["task_bundle"]["train"], {"degree": 1, "alpha": 0.0})
        reference_mse = _owner_metric(unit["test"], reference_model)
        for score in responses.values():
            score["task_success"] = score["status"] == "verified" and score["test_mse"] <= 0.85 * reference_mse
        measured_pair = all(responses[arm]["status"] == "verified" for arm in ("B", "C"))
        pair = {"unit_id": unit["unit_id"], "protocol_sha256": lock["protocol_sha256"],
                "B": responses["B"], "C": responses["C"], "fixed_reference_mse": reference_mse,
                "relative_gain": (responses["B"]["test_mse"] - responses["C"]["test_mse"]) / max(responses["B"]["test_mse"], 1e-12) if measured_pair else None}
        write_json(pair_path, pair)
        pairs.append(pair)
    _assert_frozen(protocol)
    report = analyze_pairs(protocol, pairs)
    report["protocol_sha256"] = lock["protocol_sha256"]
    report["pair_artifacts"] = [{"path": str(output_dir / f"{p['unit_id']}-pair.json"),
                                 "sha256": sha256_file(output_dir / f"{p['unit_id']}-pair.json")} for p in pairs]
    write_json(output_dir / "comparison.json", report)
    return report


def analyze_pairs(protocol: dict, pairs: list[dict]) -> dict:
    expected_ids = set(protocol["suite"]["task_ids"])
    if len(pairs) != len(expected_ids) or {p["unit_id"] for p in pairs} != expected_ids:
        return {"status": "inconclusive", "adopted": False, "reason": "preregistered paired sample incomplete"}
    failed = [{"unit_id": p["unit_id"], "arm": arm, "status": p[arm].get("status"), "error": p[arm].get("error")}
              for p in pairs for arm in ("B", "C") if p[arm].get("status") != "verified"]
    if failed:
        return {"status": "inconclusive" if any(p["status"] == "external_resource_unavailable" for p in failed) else "improvement_not_demonstrated",
                "adopted": False, "original_framework_improvement_demonstrated": False,
                "reason": "all preregistered arms must verify; failures remain in the success-rate denominator",
                "failed_arms": failed, "n_pairs": len(pairs),
                "task_success_rates": {arm: statistics.mean(bool(p[arm].get("task_success")) for p in pairs) for arm in ("B", "C")},
                "model_effect_A": protocol["model_effect_A"]}
    uncertainty = paired_uncertainty([p["relative_gain"] for p in pairs])
    unsupported = sum(p[arm]["unsupported_claims"] for p in pairs for arm in ("B", "C"))
    numeric_audit_complete = all(p[arm].get("whole_report_numeric_audit_complete") is True for p in pairs for arm in ("B", "C"))
    report_sufficiency = all(p[arm].get("common_report_sufficiency") is True for p in pairs for arm in ("B", "C"))
    efficiency = None
    if protocol["version"] == EFFICIENCY_PROTOCOL_VERSION:
        if any(p["C"].get("unknown_token_usage", False) for p in pairs):
            return {"status": "inconclusive", "adopted": False, "original_framework_improvement_demonstrated": False,
                    "reason": "a C arm has unknown failed-request tokens; its total numerator cannot support conservative efficiency inference",
                    "n_pairs": len(pairs), "model_effect_A": protocol["model_effect_A"],
                    "task_success_rates": {arm: statistics.mean(p[arm]["task_success"] for p in pairs) for arm in ("B", "C")},
                    "completed_token_units_lower_bounds": {arm: sum(sum(p[arm]["provider_token_usage"][key] for key in ("input_tokens", "output_tokens")) for p in pairs) for arm in ("B", "C")},
                    "provider_attempts": {arm: sum(p[arm].get("provider_attempts", p[arm]["provider_calls"]) for p in pairs) for arm in ("B", "C")}}
        gains, log_ratios = [], []
        conservative_units = []
        for pair in pairs:
            # B missing nonnegative cost can only increase true 1-C/B.
            # Never impute zero or describe this lower-bound measure as exact.
            b_usage = pair["B"]["total_provider_token_usage"] or pair["B"]["provider_token_usage"]
            c_usage = pair["C"]["total_provider_token_usage"]
            tokens = {"B": sum(b_usage[key] for key in ("input_tokens", "output_tokens")),
                      "C": sum(c_usage[key] for key in ("input_tokens", "output_tokens"))}
            if tokens["B"] <= 0:
                return {"status":"inconclusive","adopted":False,"reason":"B known token denominator is not positive"}
            if pair["B"].get("unknown_token_usage",False): conservative_units.append(pair["unit_id"])
            gains.append((tokens["B"] - tokens["C"]) / tokens["B"])
            log_ratios.append(math.log(max(pair["C"]["test_mse"], 1e-12) / max(pair["B"]["test_mse"], 1e-12)))
        token_uncertainty = paired_uncertainty(gains)
        quality_uncertainty = paired_uncertainty(log_ratios)
        passes = token_uncertainty["estimable"] and quality_uncertainty["estimable"] and token_uncertainty["ci95"][0] > protocol["adoption"]["token_gain_ci95_lower_greater_than"] and quality_uncertainty["ci95"][1] < protocol["adoption"]["quality_log_ratio_ci95_upper_less_than"] and unsupported == 0
        efficiency = {"token_relative_reduction": token_uncertainty, "log_test_mse_C_over_B": quality_uncertainty,
                      "token_reduction_scope": "conservative lower bounds" if conservative_units else "all request token units known",
                      "B_unknown_usage_units": conservative_units,
                      "bound_justification": "For nonnegative missing B token units and exact C total, 1-C/B_known <= 1-C/B_true. Fixed paired bootstrap sample means and percentile endpoints preserve componentwise monotonicity; bootstrap remains approximate.",
                      "rule": "intersection of token reduction and quality noninferiority; quality-v1 not an OR fallback"}
    else:
        passes = uncertainty["estimable"] and uncertainty["mean"] >= protocol["adoption"]["minimum_mean_relative_gain"] and uncertainty["ci95"][0] > 0 and unsupported == 0
    passes = passes and numeric_audit_complete and report_sufficiency
    scope = protocol["baseline_provenance"]["kind"]
    original_comparison = scope in ("original_upstream", "upstream_adaptation")
    arms = {}
    for arm in ("B", "C"):
        rows = [p[arm] for p in pairs]
        numeric = ("test_mse", "validation_mse", "execution_seconds", "arm_wall_seconds", "provider_calls",
                   "duplicate_executions", "recovered_errors", "unsupported_claims", "verified_memory_hits")
        arms[arm] = {name + "_mean": statistics.mean(r[name] for r in rows) for name in numeric}
        arms[arm]["task_success_rate"] = statistics.mean(r["task_success"] for r in rows)
        costs = [r["provider_billed_cost"] for r in rows]
        arms[arm]["provider_billed_cost_total"] = math.fsum(costs) if all(isinstance(c, (int, float)) for c in costs) else None
    return {"status": "improvement_demonstrated" if passes else "improvement_not_demonstrated",
            "adopted": bool(passes), "original_framework_improvement_demonstrated": bool(passes and original_comparison),
            "comparison_scope": scope, "framework_effect_B_vs_C": uncertainty, "arms": arms,
            "confirmatory_endpoint": protocol["primary_metric"], "efficiency_effect_B_vs_C": efficiency,
            "whole_report_numeric_audit_complete": numeric_audit_complete,
            "common_report_sufficiency": report_sufficiency,
            "model_effect_A": protocol["model_effect_A"],
            "limits": ["synthetic CPU regression tasks only; scientific discovery and generalization to other domains unproven",
                       "original model effect is unavailable unless arm A is separately run under matched conditions",
                       "bootstrap uncertainty is approximate; sequential unregistered re-testing is forbidden",
                       "cost unavailable is reported as null; subscription usage is not a monetary price"]}
