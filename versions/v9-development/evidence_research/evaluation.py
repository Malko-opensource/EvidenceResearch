"""Preregistered paired evaluation. No final suite is run on module import.

The harness owns withheld outcomes; arm callbacks receive only public training
and validation data. A restricted provider/tool boundary is still required: an
LLM with general filesystem access is not a blinded participant.
"""
from __future__ import annotations

import hashlib
from contextlib import closing
import json
import math
from pathlib import Path
import random
import re
import sqlite3
import statistics
import time
from typing import Callable

from .tasks import (TASK_VERSION, SAMPLED_TASK_DISTRIBUTION, sample_task_parameters,
                    sha256_file, split_manifest, task_data, value_hash, write_json)
from .verifier import verify
from .model_attempt_audit import audit_failed_model_attempts
from .report_contract import REPORT_SCHEMA_VERSION, verify_report_contract
from .model_request_audit import audit_request_settings
from .report_semantics import (SEMANTIC_POLICY, audit_semantic_reports,
                               prepare_semantic_review, adjudicate_semantic_review, semantic_review_sidecars,
                               frozen_semantic_reference_hashes)

PROTOCOL_VERSION = "paired-evaluation-1"
SEMANTIC_QUALITY_PROTOCOL_VERSION = "paired-evaluation-5-common-source-bound-reporting-sampled-task-contract"
LEGACY_EFFICIENCY_PROTOCOL_VERSION = "paired-efficiency-4-conservative-bound-report-contract"
EFFICIENCY_PROTOCOL_VERSION = "paired-efficiency-8-common-source-bound-reporting-sampled-task-contract"


def _semantic_required(protocol: dict) -> bool:
    return (protocol.get("version") in (EFFICIENCY_PROTOCOL_VERSION, SEMANTIC_QUALITY_PROTOCOL_VERSION)
            or protocol.get("semantic_report_policy", {}).get("required_for_both_arms") is True
            or protocol.get("report_contract", {}).get("semantic_policy", {}).get("required_for_both_arms") is True)


def _semantic_score_ready(score: dict, *, required: bool = True) -> bool:
    scope_values = [score[key] for key in
                    ("evidence_class", "evaluation_scope", "semantic_evidence_qualification") if key in score]
    if (any(not isinstance(value, str) for value in scope_values)
            or any(key in score and type(score[key]) is not bool
                   for key in ("fixture_only", "component_only", "simulation_only", "test_fixture_only"))):
        return False
    if (any(score.get(key) is True for key in ("fixture_only", "component_only", "simulation_only", "test_fixture_only"))
            or any(value != "actual" for value in scope_values)):
        return False
    return not required or (score.get("semantic_report_audit_complete") is True
                            and type(score.get("unsupported_semantic_result_claims")) is int
                            and score.get("unsupported_semantic_result_claims") == 0
                            and score.get("semantic_evidence_qualification") == "actual")


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
    # A declared positive planning floor avoids a zero-size plan. It is not a
    # proven upper bound on population variability or a power guarantee.
    scale = max(std, meaningful_gain / 2)
    power_n = math.ceil(((1.6448536269514722 + 0.8416212335729143) * scale / meaningful_gain)**2)
    precision_n = math.ceil((1.959963984540054 * scale / precision_halfwidth)**2)
    n = max(minimum_pilot, power_n, precision_n)
    return {"n_pairs": n, "pilot_n": len(pilot_deltas), "pilot_std": std,
            "planning_std": scale, "power_n": power_n, "precision_n": precision_n,
            "meaningful_gain": meaningful_gain, "precision_halfwidth": precision_halfwidth,
            "alpha_one_sided": 0.05, "power": power, "variance_relative_se": variance_relative_se,
            "planning_assumption": "independent paired units; normal approximation; actual variability may differ",
            "planning_floor_scope": "max(observed SD, declared meaningful gain/2); a planning assumption, not a validated population variance bound",
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


def create_final_suite(directory: Path, *, n_pairs: int, owner_seed: int | None = None,
                       excluded_development_definition_hashes: list[str] | None = None) -> dict:
    """Owner-only operation. Do not give private-suite.json or its directory to a proposer.

    Fresh task definitions and data seeds are sampled *before* arm execution.
    This is a synthetic CPU benchmark, not general scientific research validity.
    """
    directory = Path(directory)
    if isinstance(n_pairs, bool) or not isinstance(n_pairs, int) or n_pairs < 2:
        raise ValueError("a final paired design requires at least two units")
    if owner_seed is None:
        import secrets
        owner_seed = secrets.randbits(256)
    if isinstance(owner_seed, bool) or not isinstance(owner_seed, int) or not 0 <= owner_seed < 2**256:
        raise ValueError("Final owner seed must be privately recorded as a uint256 integer")
    excluded = set(excluded_development_definition_hashes or [])
    if any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h) for h in excluded):
        raise ValueError("Development exclusion hashes must be explicit SHA-256 values")
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError("suite directory is not empty; sealed data cannot be replaced")
    rng = random.Random(owner_seed)
    prepared = []
    for i in range(n_pairs):
        definition, seed, split_seeds = sample_task_parameters(rng)
        if value_hash(definition) in excluded:
            raise ValueError("Final task definition was already development material; choose and record a fresh owner seed before registration")
        prepared.append((definition, seed, split_seeds))
    directory.mkdir(parents=True, exist_ok=True)
    units = []
    for i, (definition, seed, split_seeds) in enumerate(prepared):
        task_id = f"holdout-{i:05d}"
        data = task_data(task_id, seed, private_definition=definition, private_split_seeds=split_seeds)
        manifest = split_manifest(task_id, seed, private_definition=definition, private_split_seeds=split_seeds)
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
                      "definition_sha256": value_hash(definition), "owner_sampled_definition": definition,
                      "logical_seed": seed, "owner_split_seeds": split_seeds})
    private_file = directory / "private-suite.json"
    write_json(private_file, {"task_version": TASK_VERSION, "units": units,
                             "n_pairs": n_pairs,
                             "sampling_distribution": SAMPLED_TASK_DISTRIBUTION,
                             "sampling_distribution_sha256": value_hash(SAMPLED_TASK_DISTRIBUTION),
                             "owner_sampling_seed": owner_seed,
                             "development_exclusion_declared": excluded_development_definition_hashes is not None,
                             "excluded_development_definition_hashes": sorted(excluded)})
    return {"private_file": str(private_file), "private_sha256": sha256_file(private_file), "n_pairs": n_pairs,
            "task_ids": [unit["unit_id"] for unit in units], "visibility": "owner-only test; proposer receives public_file content only",
            "sampling_distribution": SAMPLED_TASK_DISTRIBUTION,
            "sampling_distribution_sha256": value_hash(SAMPLED_TASK_DISTRIBUTION),
            "development_exclusion_declared": excluded_development_definition_hashes is not None,
            "excluded_development_definition_hashes": sorted(excluded)}


def _validate_final_suite_draws(private: dict) -> None:
    """Owner-only replay of actual draw sequence and sealed data, without fitting."""
    seed = private.get("owner_sampling_seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**256:
        raise ValueError("Final sampler lacks its privately recorded owner generation seed")
    if (private.get("sampling_distribution") != SAMPLED_TASK_DISTRIBUTION
            or private.get("sampling_distribution_sha256") != value_hash(SAMPLED_TASK_DISTRIBUTION)):
        raise ValueError("Final sampler law differs from the fixed generator")
    rng = random.Random(seed)
    if (isinstance(private.get("n_pairs"), bool) or not isinstance(private.get("n_pairs"), int)
            or private["n_pairs"] < 2 or len(private["units"]) != private["n_pairs"]):
        raise ValueError("Sealed final draw count differs from its owner generation receipt")
    for i, unit in enumerate(private["units"]):
        definition, logical, split_seeds = sample_task_parameters(rng)
        identity = f"holdout-{i:05d}"
        if (unit.get("unit_id") != identity or unit.get("owner_sampled_definition") != definition
                or unit.get("logical_seed") != logical or unit.get("owner_split_seeds") != split_seeds
                or unit.get("definition_sha256") != value_hash(definition)):
            raise ValueError("Final unit differs from its actual owner-side sampling draw")
        data = task_data(identity, logical, private_definition=definition, private_split_seeds=split_seeds)
        manifest = split_manifest(identity, logical, private_definition=definition, private_split_seeds=split_seeds)
        public_path = Path(unit["public_file"])
        if sha256_file(public_path) != unit["public_sha256"]:
            raise ValueError("Final public bytes differ from their owner generation receipt")
        public = json.loads(public_path.read_text(encoding="utf-8"))
        expected_public = {"task_id": identity, "seed": logical, "task_version": TASK_VERSION,
            "objective": "select polynomial ridge degree and alpha using train/validation only",
            "metric": "validation_mse", "allowed_config": {"degree": "integer 1..8", "alpha": "finite 0..100"},
            "task_bundle": {"train": data["train"], "validation": data["validation"], "split_manifest": manifest}}
        if (public != expected_public
                or unit["test"] != data["test"] or unit["test_sha256"] != value_hash(data["test"])):
            raise ValueError("Final public/private data differ from the sealed sampled generation")


def frozen_sources(extra_sources: list[Path] | None = None) -> dict:
    # Freeze the framework as well as the evaluator; otherwise a caller could
    # silently revise a proposer between paired units without changing protocol.
    paths = sorted(Path(__file__).parent.glob("*.py"))
    paths += extra_sources or []
    return {str(path.resolve()): sha256_file(path) for path in paths}


def _registered_pilot_design_data(pilot: dict, directory: Path) -> dict:
    """Revalidate completed owner scores; registration cannot gather experiments."""
    tokens, quality, gains, evidence = [], [], [], []
    for unit in pilot["units"]:
        owner = json.loads(Path(unit["owner_path"]).read_text(encoding="utf-8"))
        scores = []
        for arm in ("B", "C"):
            arm_dir = directory / "units" / unit["unit_id"] / arm
            path = arm_dir / "owner-score.json"
            if not path.is_file():
                raise ValueError("Final design requires every completed independently scored development arm")
            score = json.loads(path.read_text(encoding="utf-8"))
            _validate_saved_score(score, owner, arm_dir)
            if (score.get("status") != "verified" or not score.get("common_report_sufficiency")
                    or not score.get("whole_report_numeric_audit_complete")
                    or not _semantic_score_ready(score, required=True)
                    or score.get("unsupported_numeric_claims", score.get("unsupported_claims")) != 0
                    or score.get("unsupported_semantic_result_claims") != 0):
                raise ValueError("Failed, pending or insufficient development results cannot supply this paired final design")
            scores.append(score)
            evidence.append({"path": str(path), "sha256": sha256_file(path)})
        b, c = scores
        if c.get("unknown_token_usage") is True:
            raise ValueError("Unknown C resource usage prevents the registered efficiency planning input")
        b_usage = b["provider_token_usage"] if b.get("unknown_token_usage") else b.get("total_provider_token_usage", b["provider_token_usage"])
        c_usage = c.get("total_provider_token_usage", c["provider_token_usage"])
        if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0
               for usage in (b_usage, c_usage) for v in (usage.get("input_tokens"), usage.get("output_tokens"))):
            raise ValueError("Positive measured development token denominators required")
        b_tokens, c_tokens = (sum(usage[k] for k in ("input_tokens", "output_tokens")) for usage in (b_usage, c_usage))
        tokens.append(1 - c_tokens / b_tokens)
        quality.append(math.log(max(c["test_mse"], 1e-12) / max(b["test_mse"], 1e-12)))
        gains.append((b["test_mse"] - c["test_mse"]) / max(b["test_mse"], 1e-12))
    return {"token_gains": tokens, "log_quality_ratios": quality, "test_mse_gains": gains,
            "score_evidence": evidence, "new_provider_or_experiment_calls": 0}


def register_protocol(path: Path, *, design: dict, suite: dict, model_id: str,
                      baseline_provenance: dict, resource_envelope: dict,
                      extra_sources: list[Path] | None = None,
                      original_model_unavailable: str | None = None,
                      development_pilot_registration: Path | None = None,
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
    private = json.loads(Path(suite["private_file"]).read_text(encoding="utf-8"))
    if (sha256_file(Path(suite["private_file"])) != suite["private_sha256"]
            or len(private["units"]) != suite["n_pairs"] or private.get("n_pairs") != suite["n_pairs"]
            or [u["unit_id"] for u in private["units"]] != suite["task_ids"]):
        raise ValueError("Sealed final unit inventory/count differs from the preregistered evaluation design")
    _validate_final_suite_draws(private)
    pilot_provenance = None
    reference_paths = [Path(path) for path in frozen_semantic_reference_hashes()]
    if baseline_provenance["kind"] == "upstream_adaptation":
        from .arms import literature_protocol_from_envelope, literature_from_envelope
        from .study import check_pilot
        from .baseline import frozen_upstream_sources
        reference_paths += [Path(path) for path in frozen_upstream_sources()]
        literature_protocol_from_envelope(resource_envelope,
            required_entries=resource_envelope.get("upstream_settings", {}).get("num_papers_lit_review", 1))
        literature_from_envelope(resource_envelope)
        if development_pilot_registration is None:
            raise ValueError("New adapted final comparison requires its own sampled-development pilot registration")
        pilot_path = Path(development_pilot_registration).resolve()
        if pilot_path.name != "pilot-registration.json":
            raise ValueError("Use the exact completed development registration receipt")
        pilot = check_pilot(pilot_path.parent)
        config = pilot["config"]
        if (config.get("pilot_task_distribution") != SAMPLED_TASK_DISTRIBUTION
                or config.get("pilot_task_distribution_sha256") != value_hash(SAMPLED_TASK_DISTRIBUTION)):
            raise ValueError("Development variance source has a different task sampling law")
        if (config["model_id"] != model_id or config["resource_envelope"] != resource_envelope
                or config["baseline_provenance"] != baseline_provenance):
            raise ValueError("Development planning model/resource contrast differs from final registration")
        definitions = sorted({u["definition_sha256"] for u in config["units"]})
        if (not suite.get("development_exclusion_declared")
                or suite.get("excluded_development_definition_hashes") != definitions
                or suite.get("sampling_distribution_sha256") != value_hash(SAMPLED_TASK_DISTRIBUTION)):
            raise ValueError("Final suite must explicitly exclude every registered development task definition")
        if design.get("pilot_n") != len(pilot["units"]):
            raise ValueError("Final sample design must identify the actual size of its own development pilot")
        observed = _registered_pilot_design_data(pilot, pilot_path.parent)
        if endpoint == "efficiency":
            recomputed = design_efficiency_sample_size(observed["token_gains"], observed["log_quality_ratios"],
                minimum_token_gain=design["minimum_token_gain"], anticipated_token_gain=design["anticipated_token_gain"],
                quality_relative_margin=design["quality_relative_margin"],
                token_precision_halfwidth=design["token_design"]["precision_halfwidth"])
        else:
            recomputed = design_sample_size(observed["test_mse_gains"], meaningful_gain=design["meaningful_gain"],
                precision_halfwidth=design["precision_halfwidth"], power=design["power"],
                variance_relative_se=design["variance_relative_se"])
        if recomputed != design:
            raise ValueError("Final sample design differs from independently recomputed complete development scores")
        if (sha256_file(Path(suite["private_file"])) != suite["private_sha256"]
                or private.get("sampling_distribution_sha256") != suite["sampling_distribution_sha256"]
                or private.get("excluded_development_definition_hashes") != definitions
                or {u["definition_sha256"] for u in private["units"]} & set(definitions)):
            raise ValueError("Sealed final sampling/exclusion evidence differs from declared suite")
        pilot_provenance = {"path": str(pilot_path), "sha256": sha256_file(pilot_path),
                            "config_sha256": pilot["config_sha256"], "n_pairs": len(pilot["units"]),
                            "sampling_distribution_sha256": value_hash(SAMPLED_TASK_DISTRIBUTION),
                            "score_evidence": observed["score_evidence"],
                            "scope": "same-source/model/resource development planning; observations are not final results"}
    protocol = {"version": SEMANTIC_QUALITY_PROTOCOL_VERSION if endpoint == "quality" else EFFICIENCY_PROTOCOL_VERSION,
                "status": "preregistered", "design": design, "suite": suite,
                "model_id": model_id, "baseline_provenance": baseline_provenance,
                "resource_envelope": resource_envelope,
                "frozen_sources": frozen_sources((extra_sources or []) + reference_paths),
                "development_pilot_provenance": pilot_provenance,
                "primary_metric": "heldout_test_mse", "pair_delta": "(B_test_mse-C_test_mse)/max(B_test_mse,1e-12)",
                "adoption": {"minimum_mean_relative_gain": design.get("meaningful_gain"), "ci95_lower_greater_than": 0.0,
                             "all_pairs_present": True, "all_selected_runs_verified": True,
                             "no_unsupported_numeric_claims": True, "matched_resources": True,
                             "actual_model_execution": True, "whole_report_numeric_audit_complete": True,
                             "whole_report_semantic_audit_complete": True,
                             "no_unsupported_semantic_result_claims": True,
                             "common_report_sufficiency": True},
                "secondary_metrics": ["task_success_rate", "validation_mse", "execution_seconds", "model_seconds",
                                      "provider_calls", "provider_billed_cost_if_known", "duplicate_executions",
                                      "recovered_errors", "unsupported_numeric_claims", "unsupported_semantic_result_claims", "verified_memory_hits",
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
                                    "semantic_policy": SEMANTIC_POLICY,
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
    if protocol.get("status") != "preregistered" or protocol.get("version") not in (PROTOCOL_VERSION, SEMANTIC_QUALITY_PROTOCOL_VERSION, LEGACY_EFFICIENCY_PROTOCOL_VERSION, EFFICIENCY_PROTOCOL_VERSION):
        raise ValueError("a preregistered supported protocol is required")
    for path, digest in protocol["frozen_sources"].items():
        if sha256_file(Path(path)) != digest:
            raise ValueError(f"frozen source changed: {path}")
    suite = protocol["suite"]
    if sha256_file(Path(suite["private_file"])) != suite["private_sha256"]:
        raise ValueError("sealed evaluation suite changed")
    pilot = protocol.get("development_pilot_provenance")
    if pilot is not None and sha256_file(Path(pilot["path"])) != pilot["sha256"]:
        raise ValueError("registered development planning provenance changed")
    if pilot is not None:
        for score in pilot["score_evidence"]:
            if sha256_file(Path(score["path"])) != score["sha256"]:
                raise ValueError("registered development sample-design score changed")


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


def _numeric_inventory_items(text: str, report_hash: str) -> list[dict]:
    """Reconstruct the registered decimal inventory without writing new evidence."""
    items = []
    pattern = r"(?<![\w.])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?![\w.])"
    for line_no, line in enumerate(text.splitlines(), 1):
        for match in re.finditer(pattern, line):
            item = {"line": line_no, "start": match.start(), "end": match.end(),
                    "number": match.group(), "context": line}
            item["claim_id"] = value_hash({"report_sha256": report_hash, **item})
            items.append(item)
    return items


def _checked_review_link(item: dict, *, boundary: Path | None = None) -> Path:
    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
        raise ValueError("numeric review source path/hash missing")
    digest = item.get("sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("numeric review source hash invalid")
    original = Path(item["path"])
    source = original.resolve()
    if original.is_symlink() or not source.is_file() or (boundary is not None and not source.is_relative_to(boundary.resolve())):
        raise ValueError("numeric review source outside boundary or unavailable")
    if sha256_file(source) != digest:
        raise ValueError("numeric review source hash changed")
    return source


HISTORICAL_NUMERIC_SCHEMA_VERSION = "historical-numeric-context-1"


def _historical_numeric_unit(inventory: dict, context: dict) -> tuple[Path, Path, dict, list[dict]]:
    """Bind one complete temporal unit and *all* its original numeric tokens.

    A short excerpt, caller-provided receipt subset or a whole-arm aggregate is
    not a historical source. JSON strings and fenced JSON use the same exact
    source units as semantic review; escaped/extra numeral spellings fail closed.
    """
    from .report_semantics import parse_temporal_resource_list, semantic_units

    keys = {"schema_version", "arm_output", "boundary", "scope", "unit_id", "measure", "value"}
    if not isinstance(context, dict) or set(context) != keys:
        raise ValueError("historical numeric context has unknown or missing fields")
    if context["schema_version"] != HISTORICAL_NUMERIC_SCHEMA_VERSION or context["scope"] != "historical_pre_request":
        raise ValueError("historical numeric schema/scope is not the fixed original prefix")
    if not isinstance(context["arm_output"], str) or not context["arm_output"]:
        raise ValueError("historical numeric arm boundary missing")
    arm = Path(context["arm_output"]).resolve()
    if Path(context["arm_output"]).is_symlink() or not arm.is_dir():
        raise ValueError("historical numeric arm boundary is unavailable")
    report = _checked_review_link({"path": inventory.get("report_path"), "sha256": inventory.get("report_sha256")}, boundary=arm)
    text = report.read_text(encoding="utf-8")
    items = _numeric_inventory_items(text, inventory["report_sha256"])
    if inventory.get("items") != items:
        raise ValueError("historical numeric inventory differs from full original report")
    units = [unit for unit in semantic_units(text, inventory["report_sha256"])
             if unit["unit_id"] == context["unit_id"]]
    if len(units) != 1 or units[0]["unit_kind"] not in {"paragraph", "json_string"}:
        raise ValueError("historical numeric evidence is not one complete original textual unit")
    unit = units[0]
    parsed = parse_temporal_resource_list(unit["decoded_text"])
    if parsed is None or context["measure"] not in parsed["quantities"]:
        raise ValueError("historical numeric unit is outside the complete fixed temporal list")
    pattern = r"(?<![\w.])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?![\w.])"
    matches = list(re.finditer(pattern, unit["text"]))
    quantities = list(parsed["quantities"].items())
    if len(matches) != len(quantities) or any(match.group() != quantity["display"]
                                               for match, (_, quantity) in zip(matches, quantities)):
        raise ValueError("historical numeric raw/decoded quantity coverage differs")
    line_offsets, offset = [], 0
    for line in text.splitlines(keepends=True):
        line_offsets.append(offset); offset += len(line)
    tokens = []
    for match, (measure, quantity) in zip(matches, quantities):
        start, end = unit["start"] + match.start(), unit["start"] + match.end()
        found = [item for item in items if line_offsets[item["line"]-1]+item["start"] == start
                 and line_offsets[item["line"]-1]+item["end"] == end and item["number"] == quantity["display"]]
        if len(found) != 1:
            raise ValueError("historical numeric token is not its exact original inventory span")
        tokens.append({"claim_id": found[0]["claim_id"], "measure": measure,
                       "display": quantity["display"], "source_start": start, "source_end": end})
    return arm, report, unit, tokens


def _recompute_historical_numeric(inventory: dict, judgment: dict, *, component_fixture: bool = False) -> dict:
    from .report_semantics import evaluate_predicate, evaluate_fixture_predicate

    if not isinstance(judgment, dict) or judgment.get("kind") != "measured_historical_resource":
        raise ValueError("historical numeric recomputation requires its explicit measurement kind")
    context = judgment.get("historical_context")
    arm, report, unit, tokens = _historical_numeric_unit(inventory, context)
    selected = [token for token in tokens if token["claim_id"] == judgment.get("claim_id")]
    if len(selected) != 1 or selected[0]["measure"] != context["measure"]:
        raise ValueError("historical numeric token cannot be reassigned to another quantity")
    if type(context["value"]) not in {int, float} or not math.isfinite(context["value"]):
        raise ValueError("historical numeric measured value is unknown or not a finite scalar")
    predicate = {"kind": "measured_result", "predicate_id": "historical_context_resources",
                 "text": unit["decoded_text"], "arguments": {key: context[key] for key in ("boundary", "scope", "measure", "value")}}
    proof = (evaluate_fixture_predicate if component_fixture else evaluate_predicate)(predicate, arm)
    facts = proof["facts"]
    if not component_fixture and (facts.get("evidence_class", "actual") != "actual"
            or facts.get("adoption_eligible") is False or facts.get("fixture_only") is True
            or facts.get("evaluation_scope", "actual") != "actual"):
        raise ValueError("historical numeric original evidence is ineligible for actual support")
    return {"schema_version": HISTORICAL_NUMERIC_SCHEMA_VERSION, "historical_context": context,
            "report": {"path": str(report), "sha256": inventory["report_sha256"]},
            "unit": unit, "quantity_tokens": tokens, "selected_token": selected[0],
            "predicate_result": proof, "evidence": proof["evidence"],
            "evidence_class": "synthetic_fixture" if component_fixture else "actual",
            "evaluation_scope": "synthetic_engineering_fixture" if component_fixture else "actual",
            "adoption_eligible": not component_fixture}


def recompute_historical_numeric(inventory_path: Path, judgment: dict) -> dict:
    """Actual-only historical measurement; caller flags cannot select test mode."""
    inventory_path = Path(inventory_path).resolve()
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    arm = Path(judgment.get("historical_context", {}).get("arm_output", "")).resolve()
    if not inventory_path.is_relative_to(arm) or inventory_path.is_symlink():
        raise ValueError("historical numeric inventory lies outside its original arm")
    return _recompute_historical_numeric(inventory, judgment)


def evaluate_fixture_historical_numeric(inventory_path: Path, judgment: dict) -> dict:
    """Same audited original mapping on fixtures; never approves a real report."""
    inventory_path = Path(inventory_path).resolve()
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    arm = Path(judgment.get("historical_context", {}).get("arm_output", "")).resolve()
    if not inventory_path.is_relative_to(arm) or inventory_path.is_symlink():
        raise ValueError("fixture historical numeric inventory lies outside its arm")
    return _recompute_historical_numeric(inventory, judgment, component_fixture=True)


def _historical_numeric_group_coverage(inventory: dict, judgments: list[dict]) -> None:
    """Every numeral of a supported temporal unit must use the same prefix."""
    groups = {}
    for judgment in judgments:
        if judgment.get("kind") != "measured_historical_resource" or judgment.get("outcome", "supported") != "supported":
            continue
        context = judgment.get("historical_context")
        _, _, unit, tokens = _historical_numeric_unit(inventory, context)
        identity = {key: context[key] for key in ("schema_version", "arm_output", "boundary", "scope", "unit_id")}
        group = groups.setdefault(unit["unit_id"], {"identity": identity, "expected": {token["claim_id"] for token in tokens}, "provided": set()})
        if identity != group["identity"] or judgment["claim_id"] in group["provided"]:
            raise ValueError("historical numeric full unit has conflicting prefixes or duplicate tokens")
        group["provided"].add(judgment["claim_id"])
    if any(group["expected"] != group["provided"] for group in groups.values()):
        raise ValueError("historical numeric temporal unit has omitted or relabelled quantity tokens")


def _validate_numeric_review(review: dict, *, arm_output: Path) -> dict:
    """Check every original claim and source rather than trusting completion flags.

    A semantic reviewer is an owner-authorized role outside participant writes.
    These checks prove coverage, provenance and primitive measurements; a role
    string does not authenticate a person or automatically judge prose meaning.
    """
    if review.get("status") != "complete" or review.get("reviewer_role") != "independent_verifier":
        raise ValueError("report claim review role/status is not independent complete adjudication")
    report = _checked_review_link({"path": review.get("report_path"), "sha256": review.get("report_sha256")}, boundary=arm_output)
    inventory_path = _checked_review_link({"path": review.get("inventory_path"), "sha256": review.get("inventory_sha256")}, boundary=arm_output)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if Path(inventory.get("report_path", "")).resolve() != report or inventory.get("report_sha256") != review["report_sha256"]:
        raise ValueError("numeric review inventory refers to another report")
    original_items = _numeric_inventory_items(report.read_text(encoding="utf-8"), review["report_sha256"])
    if inventory.get("items") != original_items:
        raise ValueError("numeric review original inventory coverage differs from report reconstruction")
    originals = {item["claim_id"]: item for item in original_items}
    supplemental = {}
    if review.get("supplemental_inventory"):
        supplement_path = _checked_review_link(review["supplemental_inventory"], boundary=arm_output)
        supplement = json.loads(supplement_path.read_text(encoding="utf-8"))
        if supplement.get("report_sha256") != review["report_sha256"] or not isinstance(supplement.get("items"), list):
            raise ValueError("supplemental numeric inventory belongs to another report")
        lines = report.read_text(encoding="utf-8").splitlines()
        for item in supplement["items"]:
            try:
                number = lines[item["line"] - 1][item["start"]:item["end"]]
                if item["line"] <= 0 or item["start"] < 0 or item["end"] <= item["start"] or number != item["number"]:
                    raise ValueError("supplemental span differs")
            except (TypeError, KeyError, IndexError):
                raise ValueError("supplemental numeric item malformed") from None
            core = {field: item[field] for field in ("line", "start", "end", "number", "context")}
            if not isinstance(item["context"], str) or item["context"] not in lines[item["line"] - 1] or item["claim_id"] != value_hash({"report_sha256": review["report_sha256"], **core}):
                raise ValueError("supplemental numeric source context or ID differs")
            if item["claim_id"] in originals or item["claim_id"] in supplemental:
                raise ValueError("duplicate supplemental numeric claim")
            supplemental[item["claim_id"]] = item
    claims = review.get("claims")
    if not isinstance(claims, list) or any(not isinstance(item, dict) for item in claims):
        raise ValueError("numeric review claims must be a complete list")
    ids = [item.get("claim_id") for item in claims]
    if any(not isinstance(item, str) for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("duplicate or invalid numeric claim ID")
    expected = {**originals, **supplemental}
    if set(ids) != set(expected):
        raise ValueError("numeric review claim coverage omits or adds unregistered claims")
    allowed_kinds = {"measured", "measured_resource", "measured_historical_resource", "literature", "method", "identifier", "inference", "proposal", "unsupported",
                     "derived_measured", "derived_resource_allowance", "derived_execution_coverage"}
    allowed_outcomes = {"supported", "classified_nonmeasurement", "unsupported", "pending"}
    measured_kinds = {"measured", "measured_resource", "measured_historical_resource", "derived_measured", "derived_resource_allowance", "derived_execution_coverage"}
    _historical_numeric_group_coverage(inventory, claims)
    metric_cache, resource_cache = {}, {}
    for claim in claims:
        item = expected[claim["claim_id"]]
        if any(claim.get(field) != item.get(field) for field in ("line", "start", "end", "number", "context")):
            raise ValueError("numeric review claim differs from exact inventoried source")
        kind, outcome = claim.get("kind"), claim.get("outcome")
        if kind not in allowed_kinds or outcome not in allowed_outcomes or not isinstance(claim.get("reason"), str) or not claim["reason"].strip():
            raise ValueError("numeric review kind/outcome/rationale is invalid")
        if outcome == "supported" and kind not in measured_kinds or outcome == "classified_nonmeasurement" and kind in measured_kinds | {"unsupported"}:
            raise ValueError("numeric review outcome contradicts claim kind")
        if kind == "unsupported" and outcome != "unsupported":
            raise ValueError("unsupported claim cannot be classified as supported")
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or any(not isinstance(link, dict) for link in evidence):
            raise ValueError("numeric review evidence list invalid")
        linked = [_checked_review_link(link) for link in evidence if "path" in link or "sha256" in link]
        if outcome != "unsupported" and kind not in ("proposal", "inference") and not linked:
            raise ValueError("numeric review claim lacks hash-linked source evidence")
        if kind == "measured" and outcome == "supported":
            records = [link for link in evidence if "metric" in link and "independent_value" in link and "path" in link]
            if len(records) != 1 or Path(records[0]["path"]).name != "result.json":
                raise ValueError("measured claim lacks a unique actual result metric")
            record = records[0];run = Path(record["path"]).resolve().parent
            if not run.is_relative_to(arm_output.resolve()):
                raise ValueError("measured claim CPU source lies outside its arm")
            if run not in metric_cache:
                spec = json.loads((run / "registered_spec.json").read_text(encoding="utf-8"))
                result = json.loads((run / "result.json").read_text(encoding="utf-8"))
                verification = verify(spec, result, run)
                if not verification["valid"]:
                    raise ValueError("numeric review measurement no longer verifies")
                metric_cache[run] = verification["metrics"]
            value = metric_cache[run].get(record["metric"])
            if value is None or record["independent_value"] != value:
                raise ValueError("numeric review independent metric value differs")
            token = claim["number"].lower(); decimal, _, exponent = token.partition("e")
            tolerance = 0.5 * 10**(-len(decimal.partition(".")[2]) + (int(exponent) if exponent else 0))
            if not math.isclose(float(token), value, abs_tol=tolerance + 1e-12, rel_tol=1e-12):
                raise ValueError("numeric review supported metric differs from displayed number")
        elif kind == "measured_resource" and outcome == "supported":
            audits = []
            for path in linked:
                if path.suffix != ".json":
                    continue
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict) and value.get("schema_version") == "independent-resource-audit-1":
                    audits.append(path)
            records = [link for link in evidence if "resource_metric" in link and "independent_value" in link]
            if len(audits) != 1 or len(records) != 1:
                raise ValueError("measured resource claim lacks one independently auditable source")
            if not audits[0].is_relative_to(arm_output.resolve()):
                raise ValueError("measured resource claim source lies outside its arm")
            if audits[0] not in resource_cache:
                resource_cache[audits[0]] = recompute_resource_audit(audits[0])
            value = resource_cache[audits[0]]["measures"].get(records[0]["resource_metric"])
            if value is None or records[0]["independent_value"] != value:
                raise ValueError("numeric review independent resource value differs or is unknown")
            token = claim["number"].lower();decimal, _, exponent = token.partition("e")
            tolerance = 0.5 * 10**(-len(decimal.partition(".")[2]) + (int(exponent) if exponent else 0))
            if not math.isclose(float(token), value, abs_tol=tolerance + 1e-12, rel_tol=1e-12):
                raise ValueError("numeric review supported resource differs from displayed number")
        elif kind == "measured_historical_resource" and outcome == "supported":
            context = claim.get("historical_context")
            if Path(context.get("arm_output", "")).resolve() != arm_output.resolve():
                raise ValueError("historical numeric support was transplanted from another arm")
            source = _checked_review_link(review.get("historical_numeric_source", {}))
            if source != Path(__file__).resolve() or review.get("historical_numeric_schema_version") != HISTORICAL_NUMERIC_SCHEMA_VERSION:
                raise ValueError("historical numeric source/schema differs from executing fixed evaluator")
            recomputed = _recompute_historical_numeric(inventory, claim)
            if claim.get("historical_numeric_result") != recomputed or evidence != recomputed["evidence"]:
                raise ValueError("historical numeric proof differs from original source recomputation")
        elif kind in {"derived_measured", "derived_resource_allowance", "derived_execution_coverage"}:
            if not review.get("semantic_review_source") or not review.get("derived_calculation"):
                raise ValueError("derived numeric claim lacks independently pinned calculation and review source")
    for name in ("semantic_review_source", "derived_calculation"):
        if review.get(name):
            _checked_review_link(review[name])
    pending = sum(claim["outcome"] == "pending" for claim in claims)
    unsupported = sum(claim["outcome"] == "unsupported" for claim in claims)
    for key, count in (("pending_claims", pending), ("unsupported_claims", unsupported)):
        if isinstance(review.get(key), bool) or not isinstance(review.get(key), int) or review.get(key) != count:
            raise ValueError("numeric review pending/outcome counters differ from claims")
    if pending:
        raise ValueError("numeric review has pending claims despite complete flag")
    return {"unsupported_claims": unsupported, "original_claims": len(originals), "supplemental_claims": len(supplemental)}


def _audit_research_counters(telemetry: dict, arm_output: Path) -> dict:
    """Recompute common secondary measures from the fixed host's original ledgers.

    Error recovery is temporal episode closure, not a causal proof of repair.
    Memory hits count explicitly exposed verified Store records, not all prose
    context or latent knowledge. Host rejection classification remains a trusted
    parser observation, while CPU success and measurement are reverified here.
    """
    extra = ("completed_verified_retries", "failed_hypothesis_retries", "unique_verified_memory_records")
    if not any(name in telemetry for name in extra):
        return {"status": "historical_host_aggregate_only",
                "limits": "Legacy host counters lack the common runtime/protocol/retry/exposure contract and cannot establish comparative error recovery."}
    if any(isinstance(telemetry.get(name), bool) or not isinstance(telemetry.get(name), int) or telemetry[name] < 0 for name in extra):
        raise ValueError("common research telemetry counters missing or invalid")
    for name in ("recovered_errors_scope", "verified_memory_hits_scope", "hypothesis_retry_scope", "duplicate_execution_identity"):
        if not isinstance(telemetry.get(name), str) or not telemetry[name].strip():
            raise ValueError("common research counter scope missing")
    from .store import execution_fingerprint
    arm_output = arm_output.resolve()
    sources = [Path(v["path"]).resolve() for v in telemetry["sources"]]
    recovery_timeline, identities, source_evidence = [], [], []
    metrics = {"completed_verified_retries": 0, "failed_hypothesis_retries": 0,
               "verified_memory_hits": 0, "unique_verified_memory_records": 0}

    def read_cpu(folder, stored=None):
        folder = Path(folder).resolve()
        if not folder.is_relative_to(arm_output):
            raise ValueError("research counter CPU evidence is outside its arm")
        spec = json.loads((folder / "registered_spec.json").read_text(encoding="utf-8"))
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        verification = verify(spec, result, folder)
        if stored and (stored["spec"] != spec or stored["result"] != result or stored["verification"].get("valid") != verification["valid"]
                       or stored["verification"].get("status") != verification.get("status")
                       or stored["verification"].get("metrics") != verification.get("metrics")):
            raise ValueError("research counter stored CPU record differs from original independent evidence")
        source_evidence.extend({"path": str(folder / name), "sha256": sha256_file(folder / name)} for name in ("registered_spec.json", "result.json"))
        return spec, result, verification

    audits = [path for path in sources if path.name == "research-audit.json"]
    if audits:
        if len(audits) != 1:
            raise ValueError("multiple improved research audit ledgers")
        audit = json.loads(audits[0].read_text(encoding="utf-8"))
        database = arm_output / "research/research.sqlite3"
        # No Store construction, writable transaction, hidden owner data or model call.
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            runs = []
            for row in db.execute("SELECT * FROM runs ORDER BY created_at,run_id"):
                value = dict(row)
                for key in ("spec", "result", "verification", "manifest"):
                    value[key] = json.loads(value[key]) if value[key] is not None else None
                value["run_dir"] = str(arm_output / "research/evidence" / value["run_id"]);runs.append(value)
            events = [dict(row) for row in db.execute("SELECT sequence,timestamp,phase,payload,previous_hash,event_hash FROM events ORDER BY sequence")]
        for event in events:event["payload"] = json.loads(event["payload"])
        if audit.get("provenance") != "trusted_host_audit" or audit.get("runs") != runs or audit.get("events") != events:
            raise ValueError("research counter audit differs from original read-only Store ledger")
        previous = "0" * 64
        for event in events:
            expected = value_hash({"timestamp": event["timestamp"], "phase": event["phase"],
                "payload": event["payload"], "previous_hash": previous})
            if event["previous_hash"] != previous or event["event_hash"] != expected:
                raise ValueError("research counter Store event chain differs")
            previous = event["event_hash"]
        by_id = {r["run_id"]: r for r in runs};by_call = {}; independent = {}
        for run in runs:
            if run["status"] == "completed":
                independent[run["run_id"]] = read_cpu(run["run_dir"], run)[2]
            by_call.setdefault(run["spec"].get("model_evidence", {}).get("call_id"), []).append(run)

        def comparison_key(spec):
            return value_hash({"task": spec["task_id"], "task_version": spec.get("task_version"),
                "metric": spec["metric"], "evaluator_sha256": spec["evaluator_sha256"],
                "split": spec.get("split_manifest_sha256", spec.get("data_hash")),
                "model": spec["model"], "envelope": spec["resource_envelope"]})

        def observed_outcome(run):
            spec, result = run["spec"], run["result"]
            check = independent[run["run_id"]]
            outcome = result["status"] if check.get("valid") else "inconclusive"
            if outcome != "success":return outcome
            criterion = spec["criterion"]
            criterion_present = any(name in criterion for name in ("threshold", "baseline_value")) or spec.get("role") == "baseline"
            comparison_valid = "baseline_value" not in criterion
            if not comparison_valid:
                baseline_id = spec.get("baseline", {}).get("run_id")
                baseline = by_id.get(baseline_id)
                if baseline and baseline_id in independent and independent[baseline_id].get("valid"):
                    baseline_value = independent[baseline_id].get("metrics", {}).get(spec["metric"])
                    comparison_valid = (comparison_key(spec) == comparison_key(baseline["spec"]) and
                        isinstance(baseline_value, (int, float)) and math.isclose(baseline_value,
                        criterion["baseline_value"], rel_tol=1e-9, abs_tol=1e-12))
                elif not baseline_id:comparison_valid = check.get("comparison_valid") is True
            if not criterion_present or not comparison_valid:return "inconclusive"
            value = check.get("metrics", {}).get(spec["metric"])
            direction = 1 if criterion["direction"] == "max" else -1
            met = check.get("status") == "verified" and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            if met and "threshold" in criterion:met = direction * (value - criterion["threshold"]) >= 0
            if met and "baseline_value" in criterion:met = direction * (value - criterion["baseline_value"]) > float(criterion.get("improvement", 0))
            return "success" if met else "failure"

        for run in runs:
            if run["status"] == "completed" and run["outcome"] != observed_outcome(run):
                raise ValueError("research counter hypothesis outcome differs from independently recomputed criterion")
        invoked = [event["payload"]["run_id"] for event in events if event["phase"] == "EXECUTE" and event["payload"].get("state") == "running"]
        if set(invoked) != {r["run_id"] for r in runs if r["result"] is not None}:
            raise ValueError("research counter actual CPU invocations differ from completed artifact inventory")
        identities = [execution_fingerprint(by_id[run_id]["spec"]) for run_id in invoked]
        decisions_path, = [path for path in sources if path.name == "candidate-decisions.jsonl"]
        decisions = [json.loads(line) for line in decisions_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for decision in decisions:
            call_id = decision["call_id"]
            has_fresh = any(not item["selection"]["duplicate"] for item in decision["ranked"])
            if decision["rejected"] and not has_fresh:
                recovery_timeline.append({"kind": "protocol_error", "call_id": call_id,
                    "decisions_path": str(decisions_path), "reason": [item["reason"] for item in decision["rejected"]]})
            for run in by_call.get(call_id, []):
                if run["status"] != "completed":continue
                folder = Path(run["run_dir"])
                reference = {"call_id": call_id, "run_id": run["run_id"], "run_dir": str(folder),
                    "result_path": str(folder / "result.json"), "result_sha256": sha256_file(folder / "result.json"),
                    "verification_path": str(folder / "verification.json"), "verification_sha256": sha256_file(folder / "verification.json")}
                if run["result"]["status"] == "failure":
                    recovery_timeline.append({**reference, "kind": "runtime_error", "reason": run["result"].get("error")})
                elif not run["verification"].get("valid"):
                    recovery_timeline.append({**reference, "kind": "verification_error", "reason": run["verification"].get("reasons")})
                else:recovery_timeline.append({**reference, "kind": "verified_cpu_success"})
        retry_evidence = []
        for run in runs:
            prior_id = run["spec"].get("retry_of")
            if run["status"] == "completed" and prior_id and run["result"]["status"] == "success" and run["verification"].get("valid"):
                if prior_id not in by_id:
                    raise ValueError("research counter retry refers to unavailable original hypothesis")
                metrics["completed_verified_retries"] += 1
                metrics["failed_hypothesis_retries"] += int(by_id[prior_id]["outcome"] == "failure")
                retry_evidence.append({"run_id": run["run_id"], "retry_of": prior_id,
                    "original_evidence_path": str(Path(run["run_dir"]) / "registered_spec.json"),
                    "original_evidence_sha256": sha256_file(Path(run["run_dir"]) / "registered_spec.json"),
                    "prior_hypothesis_outcome": by_id[prior_id]["outcome"]})
        if telemetry.get("hypothesis_retry_evidence") != retry_evidence:
            raise ValueError("research counter hypothesis-retry evidence differs")
        trace_path, = [path for path in sources if path.name == "model-transport.jsonl"]
        records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        actual = [record for record in records if record.get("status") in ("completed", "failed")]
        if len({record["call_id"] for record in actual}) != len(actual):
            raise ValueError("research counter counts a cached/repeated model request twice")
        exposed = []
        for record in actual:
            request = Path(record["evidence_dir"]) / "request.json"
            if not request.resolve().is_relative_to(arm_output):raise ValueError("memory-exposure request outside arm")
            payload = json.loads(json.loads(request.read_text(encoding="utf-8"))["prompt"])
            memory = payload["verified_memory"]
            ids = [item["run_id"] for item in memory]
            if ids != record["retrieved_run_ids"] or len(set(ids)) != len(ids):
                raise ValueError("research counter memory exposures differ from actual model request")
            for item in memory:
                run = by_id.get(item["run_id"])
                if not run or run["status"] != "completed" or not run["verification"].get("valid") or item["config"] != run["spec"]["config"] or item["metrics"] != run["verification"]["metrics"] or item["outcome"] != run["outcome"]:
                    raise ValueError("research counter memory exposure lacks verified original conditions")
                spec = run["spec"];folder = Path(run["run_dir"])
                conditions = {key: spec[key] for key in ("task_id", "task_version", "model", "seed", "metric",
                    "implementation_sha256", "evaluator_sha256", "split_manifest_sha256", "data_sha256") if key in spec}
                conditions.update(resource_envelope_sha256=value_hash(spec["resource_envelope"]),
                    criterion_sha256=value_hash(spec["criterion"]), baseline_sha256=value_hash(spec.get("baseline", {})),
                    execution_fingerprint=execution_fingerprint(spec))
                references = [{"path": str(folder / name), "sha256": sha256_file(folder / name)}
                    for name in ("registered_spec.json", "result.json", "verification.json", "manifest.json")]
                for reference in item["original_evidence"]:_checked_review_link(reference, boundary=arm_output)
                expected_evidence_hash = value_hash({"spec": spec, "result": run["result"],
                    "verification": run["verification"], "manifest": run["manifest"]})
                if (item.get("conditions") != conditions or item.get("registered_criterion") != spec["criterion"] or
                        item.get("baseline_run_id") != spec.get("baseline", {}).get("run_id") or
                        item.get("original_evidence") != references or item.get("hypothesis") != spec["hypothesis"] or
                        item.get("verification_status") != run["verification"]["status"] or
                        item.get("evidence_hash") != expected_evidence_hash):
                    raise ValueError("research counter compact memory conditions differ from immutable original evidence")
            exposed.extend(ids)
            source_evidence.append({"path": str(request), "sha256": sha256_file(request)})
        metrics["verified_memory_hits"], metrics["unique_verified_memory_records"] = len(exposed), len(set(exposed))
        source_evidence.append({"path": str(database), "sha256": sha256_file(database)})
    else:
        ledgers = [path for path in sources if path.name == "tool_events.jsonl"]
        if not ledgers:raise ValueError("common research counters lack original upstream tool ledgers")
        seen = set()
        for path in ledgers:
            for event in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()):
                reference = {"tool_events_path": str(path), "tool_events_sha256": sha256_file(path), "invocation": event["invocation"],
                             "code_sha256": event["code_sha256"], "run_dir": event.get("run_dir")}
                if event["status"] == "rejected_code":
                    recovery_timeline.append({**reference, "kind": "protocol_error", "reason": event["error"]})
                elif event.get("actual_task_executed"):
                    folder = Path(event["run_dir"]).resolve()
                    if folder in seen:raise ValueError("upstream counter actual CPU receipt repeated")
                    seen.add(folder)
                    spec, result, verification = read_cpu(folder, event)
                    identities.append(execution_fingerprint(spec))
                    if event.get("candidate_identity") != execution_fingerprint(spec):raise ValueError("upstream execution identity differs from original conditions")
                    if result["status"] == "failure":
                        recovery_timeline.append({**reference, "kind": "runtime_error", "reason": result.get("error")})
                    elif not verification["valid"]:
                        recovery_timeline.append({**reference, "kind": "verification_error", "reason": verification.get("reasons")})
                    else:recovery_timeline.append({**reference, "kind": "verified_cpu_success"})
    pending, recoveries = [], []
    for event in recovery_timeline:
        if event["kind"] in ("protocol_error", "runtime_error", "verification_error"):pending.append(event)
        elif event["kind"] == "verified_cpu_success" and pending:
            recoveries.append({"causes": pending, "success": event});pending = []
    metrics.update(duplicate_executions=len(identities) - len(set(identities)), recovered_errors=len(recoveries))
    if telemetry.get("recovery_evidence") != recoveries or telemetry.get("unrecovered_error_evidence") != pending:
        raise ValueError("research counter recovery episodes differ from original evidence")
    if any(telemetry.get(name) != amount for name, amount in metrics.items()):
        raise ValueError("research counters differ from independent ledger recomputation")
    return {"status": "independently_recomputed_from_fixed_host_ledgers", "metrics": metrics, "evidence": source_evidence,
            "limits": "Recovery is later verified CPU success after a host-recorded technical error episode, not a causal repair claim. Hypothesis rejection is separate. Memory exposures are explicit verified Store records, not proof of memory benefit."}


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
    counter_audit = _audit_research_counters(telemetry, arm_output)
    if counter_audit.get("metrics"):
        metrics.update(counter_audit["metrics"])
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
        audited_review = _validate_numeric_review(review, arm_output=arm_output)
        unsupported = audited_review["unsupported_claims"]
        unsupported_total += unsupported
        review_evidence.append({"path": str(review_path), "sha256": sha256_file(review_path),
                               "report_path": review["report_path"], "report_sha256": review["report_sha256"],
                               "review_audit": audited_review})
    if review_links:
        if unsupported_total != metrics["unsupported_claims"]:
            raise ValueError("aggregate unsupported counter differs from independently reviewed report artifacts")
        full_review = telemetry.get("claim_audit_scope") in ("whole_report_numeric_inventory", "whole_report_and_companion_numeric_inventories")
    metrics["whole_report_numeric_audit_complete"] = full_review
    return metrics, {"path": str(path), "sha256": sha256_file(path), "sources": sources,
                     "claim_audit_scope": telemetry.get("claim_audit_scope", "structured metric-linked claims only"),
                   "report_claim_review": review_evidence, "secondary_counter_audit": counter_audit}


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
    items = _numeric_inventory_items(text, report_hash)
    inventory = {"report_path": str(report_path.resolve()), "report_sha256": report_hash,
                 "status": "needs_independent_adjudication", "items": items,
                 "scope": "all regex decimal/scientific numeral occurrences; semantic meaning and spelled-out numbers require independent review"}
    write_json(inventory_path, inventory)
    return inventory


def adjudicate_numeric_review(inventory_path: Path, judgments: list[dict], output_path: Path, *,
                              reviewer_role: str) -> dict:
    """Review each numeral; measured task results are independently recomputed.

    Allowed classifications are measured, measured_resource, measured_historical_resource, literature, method, identifier,
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
    _historical_numeric_group_coverage(inventory, [
        {**judgment, "outcome": "supported"} if judgment.get("kind") == "measured_historical_resource" else judgment
        for judgment in judgments])
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
            elif kind == "measured_historical_resource":
                historical = recompute_historical_numeric(inventory_path, judgment)
                evidence = historical["evidence"]
                outcome = "supported"
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
            if kind == "measured_historical_resource":
                reviews[-1].update(historical_context=judgment["historical_context"], historical_numeric_result=historical)
        else:
            reviews.append({**item, "kind": None, "outcome": outcome, "reason": reason, "evidence": evidence})
    report = {"status": "complete" if all(i["outcome"] != "pending" for i in reviews) else "pending",
              "reviewer_role": reviewer_role, "inventory_path": str(inventory_path.resolve()),
              "inventory_sha256": sha256_file(inventory_path), "report_path": inventory["report_path"],
              "report_sha256": inventory["report_sha256"], "claims": reviews,
              "unsupported_claims": sum(i["outcome"] == "unsupported" for i in reviews),
              "pending_claims": sum(i["outcome"] == "pending" for i in reviews),
              "limits": "numeric truth is checked for measured task metrics; semantic nonmeasurement classifications are independent reviewer judgments"}
    if any(claim.get("kind") == "measured_historical_resource" for claim in reviews):
        report.update(historical_numeric_schema_version=HISTORICAL_NUMERIC_SCHEMA_VERSION,
                      historical_numeric_source={"path": str(Path(__file__).resolve()), "sha256": sha256_file(Path(__file__))})
    write_json(output_path, report)
    return report


def _native_callback_response_evidence(response: dict, arm_output: Path) -> dict:
    """Preserve the original native output receipt, including its report names.

    Cached callbacks add a resume annotation and update only review-pending
    metadata. Those exact bool fields do not redefine original measurements,
    selected evidence, model/resources, trace or report output identities.
    """
    path = Path(arm_output).resolve() / "arm-response.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("original native callback response receipt is missing")
    original = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(original, dict) or not isinstance(response, dict):
        raise ValueError("native callback response must be an object")
    annotations = {"resumed_without_execution", "independent_review_pending"}
    for value in (original, response):
        if any(name in value and type(value[name]) is not bool for name in annotations):
            raise ValueError("native callback cache/review annotations must be exact bool")
    if ({key: value for key, value in original.items() if key not in annotations}
            != {key: value for key, value in response.items() if key not in annotations}):
        raise ValueError("callback returned outputs differ from the original native response")
    return {"path": str(path), "sha256": sha256_file(path),
            "original_value_sha256": value_hash(original),
            "comparison_scope": "all original output fields except bool cache/review annotations",
            "cache_annotation_fields": sorted(annotations)}


def _score_arm(protocol: dict, unit: dict, public: dict, arm: str, arm_output: Path,
               callback: Callable[[dict, Path], dict]) -> dict:
    start = time.perf_counter()
    # No test rows, private file paths or answer definitions in this payload.
    payload = {"arm": arm, "model_id": protocol["model_id"], "resource_envelope": protocol["resource_envelope"],
               "public_task": public, "baseline_provenance": protocol["baseline_provenance"] if arm == "B" else None}
    response = callback(payload, arm_output)
    wall = time.perf_counter() - start
    response_evidence = _native_callback_response_evidence(response, arm_output)
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
    if telemetry_evidence["secondary_counter_audit"]["status"] != "independently_recomputed_from_fixed_host_ledgers":
        raise ValueError("actual matched evaluation requires independently recomputed common research counters")
    report_contract = (verify_report_contract(Path(response["report_contract_path"]), arm_output=arm_output,
                          spec=spec, verification=verification, selected_run_dir=run_dir)
                       if response.get("report_contract_path") else
                       {"valid": False, "reasons": ["common report companion missing"], "evidence": []})
    reviewed_paths = {str(Path(item["report_path"]).resolve()) for item in telemetry_evidence["report_claim_review"]}
    required_paths = {str(Path(response[key]).resolve()) for key in ("report_path","report_contract_path") if response.get(key)}
    counters["whole_report_numeric_audit_complete"] = bool(counters["whole_report_numeric_audit_complete"] and len(required_paths)==2 and required_paths.issubset(reviewed_paths))
    counters["unsupported_numeric_claims"] = counters["unsupported_claims"]
    semantic_paths, semantic_history = semantic_review_sidecars(arm_output)
    semantics = audit_semantic_reports([Path(path) for path in required_paths], semantic_paths, arm_output=arm_output)
    semantics["review_history"] = semantic_history
    counters["semantic_report_audit_complete"] = semantics["semantic_report_audit_complete"]
    counters["semantic_evidence_qualification"] = semantics["semantic_evidence_qualification"]
    counters["unsupported_semantic_result_claims"] = semantics["unsupported_semantic_result_claims"]
    counters["independent_report_review_status"] = ("complete" if counters["whole_report_numeric_audit_complete"]
        and (not _semantic_required(protocol) or semantics["semantic_report_audit_complete"]) else "awaiting_independent_report_review")
    model = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
    test_mse = _owner_metric(unit["test"], model)
    evidence = {"run_dir": str(run_dir), "spec_sha256": value_hash(spec), "result_sha256": sha256_file(run_dir / "result.json"),
                "callback_response": response_evidence,
                "model_sha256": sha256_file(run_dir / "model.json"), "trace_path": str(trace), "trace_sha256": sha256_file(trace),
                "test_sha256": unit["test_sha256"], "verification": verification,
                "model_calls": usage["evidence"], "telemetry": telemetry_evidence,
                "failed_model_attempt_audit": failed_usage, "report_contract": report_contract, "cpu_audit":cpu_audit,
                "semantic_report_audit": semantics, "semantic_report_policy_required": _semantic_required(protocol)}
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
            "independent_semantic_review_seconds":None,"independent_semantic_review_usage":None,
            "evidence": evidence}


def _failure_score(unit: dict, arm: str, arm_output: Path, error: Exception) -> dict:
    """A failed arm is a durable denominator member; a fresh success cannot replace it."""
    from .model import PreregisteredResourcesExhausted
    budget_exhausted = isinstance(error, PreregisteredResourcesExhausted)
    external = type(error).__name__ == "ModelUnavailable" and "Forbidden" not in str(error)
    classification = ("registered_resources_exhausted" if budget_exhausted else
                      "external_resource_unavailable" if external else "failed_execution_or_verification")
    error_path = arm_output / "owner-failure.json"
    write_json(error_path, {"error_type": type(error).__name__, "error": str(error),
                            "classification": classification})
    files = [{"path": str(path.resolve()), "sha256": sha256_file(path)} for path in arm_output.rglob("*")
             if path.is_file() and not path.is_symlink() and path.name != "owner-score.json"]
    return {"status": "registered_resources_exhausted" if budget_exhausted else "external_resource_unavailable" if external else "failed",
            "classification": classification, "arm": arm, "unit_id": unit["unit_id"],
            "task_success": False, "test_mse": None, "validation_mse": None, "execution_seconds": None,
            "model_seconds": None, "arm_wall_seconds": None, "provider_calls": None, "provider_billed_cost": None,
            "duplicate_executions": None, "recovered_errors": None, "unsupported_claims": None,
            "unsupported_numeric_claims": None, "unsupported_semantic_result_claims": None,
            "semantic_report_audit_complete": False,
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
    response_link = evidence.get("callback_response")
    if not isinstance(response_link, dict):
        raise ValueError("original callback response evidence is missing from saved score")
    try:
        response_path = _checked_review_link(response_link, boundary=arm_output)
    except (OSError, ValueError) as error:
        raise ValueError("original callback response output receipt hash changed or unavailable") from error
    if response_path != arm_output.resolve() / "arm-response.json":
        raise ValueError("saved callback response is not the original native output receipt")
    if value_hash(json.loads(response_path.read_text(encoding="utf-8"))) != response_link.get("original_value_sha256"):
        raise ValueError("saved callback response value differs from original evidence")
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
    counters, recomputed_telemetry = _audit_telemetry({"telemetry_evidence_path": telemetry["path"]}, arm_output)
    if score.get("unsupported_numeric_claims", score.get("unsupported_claims")) != counters["unsupported_claims"]:
        raise ValueError("saved numeric unsupported count differs from independently re-audited reviews")
    # Native callbacks retain the original named report outputs. Completeness
    # and sufficiency must be reconstructed from those outputs rather than
    # from a saved flag or a substituted pair of otherwise valid reviews.
    response_path = arm_output / "arm-response.json"
    if response_path.is_symlink() or not response_path.is_file():
        raise ValueError("original callback report output receipt is missing")
    response = json.loads(response_path.read_text(encoding="utf-8"))
    if (Path(response.get("selected_run_dir", "")).resolve() != run_dir.resolve()
            or Path(response.get("telemetry_evidence_path", "")).resolve() != Path(telemetry["path"]).resolve()):
        raise ValueError("original callback selected evidence/report telemetry differs")
    required_paths = set()
    for key in ("report_path", "report_contract_path"):
        if response.get(key):
            original = Path(response[key]).resolve()
            if not original.is_relative_to(arm_output.resolve()) or Path(response[key]).is_symlink() or not original.is_file():
                raise ValueError("original callback report output is outside or missing from the arm")
            required_paths.add(str(original))
    if not response.get("report_path"):
        raise ValueError("original callback primary report output is missing")
    raw_telemetry = json.loads(Path(telemetry["path"]).read_text(encoding="utf-8"))
    if (raw_telemetry.get("report_path") is not None
            and Path(raw_telemetry["report_path"]).resolve() != Path(response["report_path"]).resolve()):
        raise ValueError("original primary report differs from host telemetry")
    if (raw_telemetry.get("report_sha256") is not None
            and raw_telemetry["report_sha256"] != sha256_file(Path(response["report_path"]))):
        raise ValueError("original primary report changed")
    reviewed_paths = {str(Path(item["report_path"]).resolve())
                      for item in recomputed_telemetry["report_claim_review"]}
    numeric_complete = bool(counters["whole_report_numeric_audit_complete"]
                            and len(required_paths) == 2 and required_paths.issubset(reviewed_paths))
    if (type(score.get("whole_report_numeric_audit_complete")) is not bool
            or score["whole_report_numeric_audit_complete"] != numeric_complete):
        raise ValueError("saved whole-report numeric completeness differs from original report reviews")
    report_contract = (verify_report_contract(Path(response["report_contract_path"]), arm_output=arm_output,
                      spec=spec, verification=verification, selected_run_dir=run_dir)
                      if response.get("report_contract_path") else
                      {"valid": False, "reasons": ["common report companion missing"], "evidence": []})
    if resource_link:
        expected_report_tokens = expected_totals
        expected_report_seconds = audited["measures"]["model_seconds"]
    else:
        # Legacy synthetic/engineering scores may have no aggregate resource
        # sidecar. They still cannot substitute unknown usage with zero.
        expected_report_tokens = None if failed_audit.get("unknown_failed_token_usage") else {
            key: usage["token_usage"][key] + failed_audit.get("failed_token_usage", {}).get(key, 0)
            for key in ("input_tokens", "output_tokens")}
        expected_report_seconds = usage["model_seconds"] + failed_audit.get("failed_seconds", 0)
    reported_resources = report_contract.get("reported_resources", {})
    if (reported_resources.get("tokens_known") != (expected_report_tokens is not None)
            or reported_resources.get("token_usage") != expected_report_tokens):
        report_contract["valid"] = False
    reported_seconds = reported_resources.get("seconds")
    if reported_seconds is not None and not math.isclose(reported_seconds, expected_report_seconds, rel_tol=1e-9, abs_tol=1e-9):
        report_contract["valid"] = False
    saved_contract_valid = evidence.get("report_contract", {}).get("valid")
    if (type(saved_contract_valid) is not bool or saved_contract_valid != report_contract["valid"]
            or type(score.get("common_report_sufficiency")) is not bool
            or score["common_report_sufficiency"] != report_contract["valid"]):
        raise ValueError("saved report sufficiency differs from independently reconstructed original companion")
    semantic = evidence.get("semantic_report_audit")
    if semantic is not None:
        for link in semantic.get("review_history", []):
            if sha256_file(Path(link["path"])) != link["sha256"]:
                raise ValueError("historical semantic review was changed rather than versioned")
        # The snapshot controls which immutable review sidecars are used, not
        # which original reports they must cover. A second arm-local reviewed
        # report cannot replace the callback's original companion.
        report_paths = [Path(path) for path in sorted(required_paths)]
        # Preserve a pending measurement's review snapshot. Later owner sidecars
        # cannot silently upgrade an immutable pending score on validation.
        reviews = [Path(a["review"]["path"]) for a in semantic["audits"]]
        for audit in semantic["audits"]:
            for key in ("review", "inventory", "report", "predicate_source"):
                link = audit[key]
                if sha256_file(Path(link["path"])) != link["sha256"]:
                    raise ValueError("completed semantic review/source evidence changed")
        audited_semantic = audit_semantic_reports(report_paths, reviews, arm_output=arm_output)
        for field in ("semantic_report_audit_complete", "semantic_evidence_qualification", "unsupported_semantic_result_claims"):
            if semantic.get(field) != audited_semantic[field]:
                raise ValueError("saved semantic evidence aggregate differs from reconstructed immutable reviews")
        if (score.get("semantic_report_audit_complete") != audited_semantic["semantic_report_audit_complete"]
                or score.get("semantic_evidence_qualification") != audited_semantic["semantic_evidence_qualification"]
                or score.get("unsupported_semantic_result_claims") != audited_semantic["unsupported_semantic_result_claims"]):
            raise ValueError("saved semantic gate differs from actual immutable review evidence")
    elif evidence.get("semantic_report_policy_required"):
        raise ValueError("registered semantic review proof is missing")


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
    unsupported_numeric = sum(p[arm].get("unsupported_numeric_claims", p[arm]["unsupported_claims"]) for p in pairs for arm in ("B", "C"))
    if unsupported_numeric != unsupported:
        raise ValueError("numeric unsupported legacy alias contradicts the scoped count")
    semantic_required = _semantic_required(protocol)
    semantic_complete = all(_semantic_score_ready(p[arm], required=True) for p in pairs for arm in ("B", "C"))
    semantic_counts = [p[arm].get("unsupported_semantic_result_claims") for p in pairs for arm in ("B", "C")]
    unsupported_semantic = sum(semantic_counts) if all(type(v) is int and v >= 0 for v in semantic_counts) else None
    numeric_audit_complete = all(p[arm].get("whole_report_numeric_audit_complete") is True for p in pairs for arm in ("B", "C"))
    report_sufficiency = all(p[arm].get("common_report_sufficiency") is True for p in pairs for arm in ("B", "C"))
    efficiency = None
    if protocol["version"] in (LEGACY_EFFICIENCY_PROTOCOL_VERSION, EFFICIENCY_PROTOCOL_VERSION):
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
    nonactual_scope_absent = all(_semantic_score_ready(p[arm], required=False) for p in pairs for arm in ("B", "C"))
    passes = passes and numeric_audit_complete and report_sufficiency and nonactual_scope_absent
    passes = passes and (not semantic_required or (semantic_complete and unsupported_semantic == 0))
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
            "component_or_legacy_scope_absent": nonactual_scope_absent,
            "unsupported_numeric_claims": unsupported_numeric,
            "semantic_report_audit_required": semantic_required,
            "semantic_report_audit_complete": semantic_complete,
            "unsupported_semantic_result_claims": unsupported_semantic,
            "common_report_sufficiency": report_sufficiency,
            "model_effect_A": protocol["model_effect_A"],
            "limits": ["synthetic CPU regression tasks only; scientific discovery and generalization to other domains unproven",
                       "original model effect is unavailable unless arm A is separately run under matched conditions",
                       "bootstrap uncertainty is approximate; sequential unregistered re-testing is forbidden",
                       "cost unavailable is reported as null; subscription usage is not a monetary price",
                       "numeric claim auditing and semantic result-claim review are separate; fixed predicates do not prove unrestricted language entailment or reviewer identity",
                       "common report sufficiency establishes evidence-linked task-fitting content, not equal literary quality or scientific discovery quality"]}
