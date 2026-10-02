"""Explicit paired development pilot and owner-scored final study commands.

No model calls occur on import or registration. Pilot configuration must name the
model, matched resource envelope, development units and baseline provenance.
Final protocol creation and acceptance criteria belong to the independent owner.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil

from .arms import UpstreamArm, TOOL_CONTRACT, frozen_literature, literature_from_envelope
from .comparison_arms import ImprovedArm
from .evaluation import (_assert_frozen, _score_arm, _failure_score, _validate_saved_score,
                         _audit_model_evidence, adjudicate_numeric_review, frozen_sources, run_matched)
from .model import ModelUnavailable, PreregisteredResourcesExhausted
from .model_attempt_audit import audit_failed_model_attempts
from .store import EvidenceError, Store, atomic_json, fingerprint, sha256_file, utc_now
from .tasks import DEVELOPMENT_TASKS, TASK_VERSION, split_manifest, task_data, value_hash


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def study_events(root: Path) -> list[dict]:
    path = root / "study-events.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    previous = "0" * 64
    for row in rows:
        if row["previous_hash"] != previous or fingerprint({k: v for k, v in row.items() if k != "event_hash"}) != row["event_hash"]:
            raise EvidenceError("Study audit chain changed")
        previous = row["event_hash"]
    return rows


def append_event(root: Path, action: str, payload: dict) -> None:
    rows = study_events(root)
    path = root / "study-events.jsonl"
    previous = rows[-1]["event_hash"] if rows else "0" * 64
    event = {"timestamp": utc_now(), "action": action, "payload": payload, "previous_hash": previous}
    event["event_hash"] = fingerprint(event)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def register_pilot(config: dict, output: Path) -> dict:
    output = Path(output).resolve()
    if not config.get("model_id") or config.get("kind") != "development_pilot":
        raise ValueError("Explicit kind=development_pilot and actual model_id are required")
    envelope = config.get("resource_envelope", {})
    calls = envelope.get("proposal_calls_per_unit")
    if isinstance(calls, bool) or not isinstance(calls, int) or calls <= 0:
        raise ValueError("Matched proposal_calls_per_unit must be a positive integer")
    literature = literature_from_envelope(envelope)
    required_papers = envelope.get("upstream_settings", {}).get("num_papers_lit_review", 1)
    if isinstance(required_papers, bool) or not isinstance(required_papers, int) or required_papers <= 0 or required_papers > len(literature):
        raise ValueError("The common frozen distinct literature must satisfy the registered original review count")
    if "reasoning_effort" not in envelope:
        raise ValueError("The matched reasoning_effort must be explicit, including null")
    if config.get("baseline_provenance", {}).get("kind") != "upstream_adaptation":
        raise ValueError("This driver runs the actual upstream adaptation; declare that provenance")
    units = config.get("units", [])
    if not units:
        raise ValueError("Explicit development task/seed units are required; the driver invents no repetition count")
    seen = set()
    for unit in units:
        identity = unit["unit_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", identity) or identity in seen:
            raise ValueError("Each unit_id must be unique and safe for an artifact directory")
        seen.add(identity)
        if unit["task_id"] not in DEVELOPMENT_TASKS:
            raise ValueError("Pilot task must be a development task; final tasks belong to the owner protocol")
        task_data(unit["task_id"], unit["seed"])
    receipt = output / "pilot-registration.json"
    if receipt.exists():
        prior = load(receipt)
        if prior["config"] != config:
            raise EvidenceError("Pilot conditions cannot be retroactively changed")
        check_pilot(output)
        return prior
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Registration requires an empty output directory")
    output.mkdir(parents=True, exist_ok=True)
    sources = frozen_sources()
    source_archive = output / "source-snapshot" / "evidence_research"
    source_archive.mkdir(parents=True)
    for path, digest in sources.items():
        shutil.copy2(path, source_archive / Path(path).name)
    registered_units = []
    owner_dir = output / "owner-development-data"
    owner_dir.mkdir()
    for unit in units:
        task_id, seed, identity = unit["task_id"], unit["seed"], unit["unit_id"]
        data, manifest = task_data(task_id, seed), split_manifest(task_id, seed)
        public = {"task_id": task_id, "seed": seed, "task_version": TASK_VERSION,
            "objective": "select polynomial ridge degree and alpha using train/validation only",
            "metric": "validation_mse", "allowed_config": {"degree": "integer 1..8", "alpha": "finite 0..100"},
            "task_bundle": {"train": data["train"], "validation": data["validation"], "split_manifest": manifest}}
        if unit.get("criterion") is not None:
            public["criterion"] = unit["criterion"]
        public_path = owner_dir / f"{identity}-public.json"
        private_path = owner_dir / f"{identity}-owner.json"
        atomic_json(public_path, public)
        owner = {"unit_id": identity, "test": data["test"], "test_sha256": value_hash(data["test"]),
                 "scope": "development only; agent input excludes these test rows"}
        atomic_json(private_path, owner)
        registered_units.append({"unit_id": identity, "public_path": str(public_path),
            "public_sha256": sha256_file(public_path), "owner_path": str(private_path),
            "owner_sha256": sha256_file(private_path)})
    registered = {"config": config, "config_sha256": fingerprint(config), "sources": sources,
        "units": registered_units, "shared_tool_contract_sha256": fingerprint(TOOL_CONTRACT),
        "shared_literature_sha256": fingerprint(literature), "source_snapshot": str(source_archive.parent),
        "scope": "development paired pilot, never confirmatory adoption", "registered_at": utc_now()}
    atomic_json(receipt, registered)
    append_event(output, "REGISTER_PILOT", {"registration_sha256": sha256_file(receipt), "config_sha256": fingerprint(config)})
    return registered


def check_pilot(output: Path) -> dict:
    output = Path(output).resolve()
    registration = load(output / "pilot-registration.json")
    for event in study_events(output):
        payload = event["payload"]
        if event["action"] == "REGISTER_PILOT" and payload["registration_sha256"] != sha256_file(output / "pilot-registration.json"):
            raise EvidenceError("Pilot preregistration differs from its audit anchor")
        if event["action"] == "RECORD_ARM" and sha256_file(payload["path"]) != payload["sha256"]:
            raise EvidenceError("Completed pilot arm measurement changed")
        if event["action"] in ("RECORD_EXTERNAL_ATTEMPT", "AUTHORIZE_CONTINUATION"):
            if sha256_file(payload["path"]) != payload["sha256"]:
                raise EvidenceError("Immutable external attempt or continuation authorization changed")
            if event["action"] == "RECORD_EXTERNAL_ATTEMPT":
                _validate_saved_score(load(payload["path"]), {}, Path(payload["path"]).parent)
    if fingerprint(registration["config"]) != registration["config_sha256"]:
        raise EvidenceError("Pilot configuration hash changed")
    for path, digest in registration["sources"].items():
        # Running the archived package preserves its original implementation;
        # current package edits must never be mixed into the saved pilot.
        executing_source = Path(__file__).parent / Path(path).name
        if sha256_file(executing_source) != digest:
            raise EvidenceError("Pilot sources changed; preserve this study and register a new pilot")
    if fingerprint(TOOL_CONTRACT) != registration["shared_tool_contract_sha256"] or fingerprint(literature_from_envelope(registration["config"]["resource_envelope"])) != registration["shared_literature_sha256"]:
        raise EvidenceError("Shared permissions or literature changed")
    for unit in registration["units"]:
        for name in ("public", "owner"):
            if sha256_file(unit[f"{name}_path"]) != unit[f"{name}_sha256"]:
                raise EvidenceError("Registered development data changed")
    return registration


def _pending_snapshot(score: dict, arm_output: Path) -> dict:
    snapshot = arm_output / "owner-pending-telemetry.json"
    shutil.copy2(score["evidence"]["telemetry"]["path"], snapshot)
    result = json.loads(json.dumps(score))
    result["evidence"]["telemetry"].update(path=str(snapshot), sha256=sha256_file(snapshot))
    return result


def _record_external_attempt(output: Path, directory: Path, owner: dict, arm: str, error: Exception) -> Path:
    """Snapshot interrupted state without making a resource shortage a final score."""
    attempts = directory / "owner-attempts"
    attempts.mkdir(exist_ok=True)
    attempt = attempts / f"attempt-{len(list(attempts.glob('attempt-*'))):04d}"
    attempt.mkdir()
    snapshot = attempt / "original-state"
    snapshot.mkdir()
    for source in list(directory.rglob("*")):
        if source.is_file() and not source.is_symlink() and not source.is_relative_to(attempts):
            target = snapshot / source.relative_to(directory)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    score = _failure_score(owner, arm, attempt, error)
    score["retry_policy"] = "Explicit pilot-continue only after original raw failed requests, no-action receipts, checkpoints and completed work are audited; resource conditions remain registered."
    path = attempt / "owner-attempt.json"
    atomic_json(path, score)
    append_event(output, "RECORD_EXTERNAL_ATTEMPT", {"unit_id": owner["unit_id"], "arm": arm,
        "path": str(path), "sha256": sha256_file(path), "status": "external_resource_pending"})
    return path


def _continuation_audit(directory: Path, model_id: str, envelope: dict, reason: str) -> dict:
    """Fail closed unless every original provider attempt is definitively accounted."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Explicit continuation rationale is required")
    failed, completed, requests = [], [], []
    for request_path in directory.rglob("request.json"):
        if "owner-attempts" in request_path.relative_to(directory).parts:
            continue
        request = load(request_path)
        if request.get("execution_kind") != "real_model":
            continue
        requests.append(request_path)
        result_path = request_path.parent / "result.json"
        if not result_path.exists():
            raise EvidenceError("A prior model request has unknown execution; explicit retry cannot establish no action")
        result = load(result_path)
        if result.get("status") == "failed":
            failed.append(str(request_path.parent.resolve()))
        elif result.get("status") == "completed":
            completed.append(str(request_path.parent.resolve()))
        else:
            raise EvidenceError("Prior model result has unknown status")
    if not failed:
        raise EvidenceError("No definitive failed real-model attempt with raw no-action evidence is available")
    receipts = {}
    for receipt_path in directory.rglob("host-no-action/*.json"):
        if "owner-attempts" in receipt_path.relative_to(directory).parts:
            continue
        receipt = load(receipt_path)
        folder = str(Path(receipt["attempt_result_path"]).resolve().parent)
        if folder in receipts:
            raise EvidenceError("Duplicate host no-action receipt")
        receipts[folder] = str(receipt_path.resolve())
    if set(receipts) != set(failed):
        raise EvidenceError("No-action receipts do not cover exactly the failed original requests")
    lineage = {"kind": "explicit_model_attempt_resume_lineage", "provenance": "trusted_host_audit",
        "model_id": model_id, "retry_reason": reason, "attempts": [
            {"failed_dir": folder, "result_sha256": sha256_file(Path(folder) / "result.json"),
             "request_fingerprint": load(Path(folder) / "request.json")["fingerprint"],
             "host_action_receipt": receipts[folder], "receipt_sha256": sha256_file(receipts[folder])}
            for folder in sorted(failed)]}
    lineage_path = directory / "owner-continuation-lineages" / f"{fingerprint(lineage)[:24]}.json"
    if not lineage_path.exists():
        atomic_json(lineage_path, lineage)
    failed_audit = audit_failed_model_attempts(failed, model_id=model_id, allowed_roots=[str(directory)],
        host_action_receipts=receipts, lineage_path=str(lineage_path), resource_envelope=envelope, arm_output=str(directory))
    completed_audit = _audit_model_evidence(completed, directory, model_id, resource_envelope=envelope) if completed else {
        "provider_calls": 0, "model_seconds": 0.0, "token_usage": {"input_tokens": 0, "output_tokens": 0}, "evidence": []}
    total = len(failed) + len(completed)
    if total >= envelope["proposal_calls_per_unit"]:
        raise EvidenceError("The registered provider-attempt budget is exhausted; continuation cannot enlarge it")
    cpu_evidence = []
    from .verifier import verify
    for spec_path in directory.rglob("registered_spec.json"):
        if "owner-attempts" in spec_path.relative_to(directory).parts:
            continue
        result_path = spec_path.parent / "result.json"
        if not result_path.exists():
            # A registered C job with no execution request is durably pending.
            if (directory / "research" / "research.sqlite3").exists():
                runs = Store(directory / "research").list_runs()
                pending = any(Path(run["run_dir"]).resolve() == spec_path.parent.resolve() and run["status"] == "pending" for run in runs)
                if pending:
                    continue
            raise EvidenceError("A previous CPU execution has no result; automatic repetition is forbidden")
        verification = verify(load(spec_path), load(result_path), spec_path.parent)
        if not verification.get("valid"):
            raise EvidenceError("Completed CPU evidence does not pass its fixed independent verification")
        cpu_evidence.extend({"path": str(path), "sha256": sha256_file(path)} for path in (spec_path, result_path))
    checkpoint_evidence = []
    from .baseline import _check_baseline_artifacts
    for baseline_path in directory.glob("attempts/attempt-*/upstream/baseline_result.json"):
        baseline = load(baseline_path)
        _check_baseline_artifacts(baseline_path.parent, baseline)
        checkpoint_evidence.append({"path": str(baseline_path), "sha256": sha256_file(baseline_path)})
    return {"failed_model_attempt_audit": failed_audit, "completed_model_audit": completed_audit,
        "prior_provider_attempts": total, "remaining_provider_attempts": envelope["proposal_calls_per_unit"] - total,
        "unknown_prior_tokens": failed_audit["unknown_failed_token_usage"], "lineage_path": str(lineage_path),
        "lineage_sha256": sha256_file(lineage_path), "cpu_evidence": cpu_evidence, "checkpoint_evidence": checkpoint_evidence}


def _reviews_complete(directory: Path) -> bool:
    return all((directory / name).exists() and load(directory / name).get("status") == "complete"
               for name in ("report-review.json", "companion-review.json"))


def run_pilot(output: Path, *, baseline=None, improved=None, _selected=None, _authorization=None) -> dict:
    output = Path(output).resolve()
    registration = check_pilot(output)
    config = registration["config"]
    protocol = {"model_id": config["model_id"], "resource_envelope": config["resource_envelope"],
                "baseline_provenance": config["baseline_provenance"]}
    callbacks = {"B": baseline or UpstreamArm(), "C": improved or ImprovedArm()}
    external_block = None
    rows = []
    for index, entry in enumerate(registration["units"]):
        public, owner = load(entry["public_path"]), load(entry["owner_path"])
        row = {"unit_id": entry["unit_id"], "arms": {}}
        order = ("B", "C") if index % 2 == 0 else ("C", "B")
        for arm in order:
            directory = output / "units" / entry["unit_id"] / arm
            directory.mkdir(parents=True, exist_ok=True)
            final_path = directory / "owner-score.json"
            pending_path = directory / "owner-measurement.json"
            requested_path = directory / "owner-request.json"
            targeted = _selected == (entry["unit_id"], arm)
            if final_path.exists():
                score = load(final_path)
                _validate_saved_score(score, owner, directory)
                row["arms"][arm] = {"status": score["status"], "score_path": str(final_path), "score": score,
                                    "resumed_without_execution": True}
                continue
            if pending_path.exists():
                pending = load(pending_path)
                _validate_saved_score(pending, owner, directory)
                if not _reviews_complete(directory):
                    row["arms"][arm] = {"status": "awaiting_independent_report_review", "measurement_path": str(pending_path)}
                    continue
            elif requested_path.exists() and not (directory / "arm-response.json").exists():
                if not (targeted and _authorization):
                    saved_attempts = sorted((directory / "owner-attempts").glob("attempt-*/owner-attempt.json"))
                    if saved_attempts:
                        row["arms"][arm] = {"status": "external_resource_pending", "attempt_path": str(saved_attempts[-1]),
                            "reason": "Original failure preserved; use explicit pilot-continue after raw no-action audit."}
                    else:
                        try:
                            audit = _continuation_audit(directory, config["model_id"], config["resource_envelope"], "Classify interrupted original attempt; no execution authorized.")
                        except (EvidenceError, ValueError, OSError, KeyError):
                            row["arms"][arm] = {"status": "unknown_execution", "reason": "No completed callback receipt or definitive no-action evidence; automatic repeat refused"}
                        else:
                            row["arms"][arm] = {"status": "external_resource_pending", "audit": audit,
                                "reason": "Definitive original model failure; explicit pilot-continue is required."}
                    continue
            if _selected is not None and not targeted:
                row["arms"][arm] = {"status": "not_requested_by_continuation", "reason": "Explicit continuation applies only to its named unit and arm."}
                continue
            if external_block is not None:
                row["arms"][arm] = {"status": "external_resource_blocked", "reason": external_block}
                continue
            if not requested_path.exists():
                atomic_json(requested_path, {"unit_id": entry["unit_id"], "arm": arm,
                    "registration_sha256": sha256_file(output / "pilot-registration.json"), "status": "requested"})
                append_event(output, "REQUEST_ARM", {"unit_id": entry["unit_id"], "arm": arm})
            try:
                score = _score_arm(protocol, owner, public, arm, directory, callbacks[arm])
            except Exception as error:
                if isinstance(error, ModelUnavailable) and not isinstance(error, PreregisteredResourcesExhausted) and "Forbidden" not in str(error):
                    attempt_path = _record_external_attempt(output, directory, owner, arm, error)
                    score = load(attempt_path)
                    external_block = str(error)
                    row["arms"][arm] = {"status": "external_resource_pending", "attempt_path": str(attempt_path), "score": score}
                    continue
                score = _failure_score(owner, arm, directory, error)
                if isinstance(error, PreregisteredResourcesExhausted):
                    score["resource_scope"] = "The registered evaluation unit exhausted its allowance; the research Goal remains active."
                    score["retry_policy"] = "Preserve this failed registered unit. Do not enlarge its allowance or replace it with a rerun; any changed resource design requires a separate development registration."
                atomic_json(final_path, score)
            else:
                if score.get("whole_report_numeric_audit_complete"):
                    if pending_path.exists():
                        prior = load(pending_path)
                        for key in ("test_mse", "validation_mse", "provider_calls", "provider_token_usage"):
                            if prior[key] != score[key]:
                                raise EvidenceError("Report adjudication altered completed task/provider measurements")
                        score["finalization_wall_seconds"] = score["arm_wall_seconds"]
                        score["arm_wall_seconds"] = prior["arm_wall_seconds"]
                        score["evidence"]["original_owner_measurement"] = {
                            "path": str(pending_path), "sha256": sha256_file(pending_path),
                            "reason": "Original execution wall time retained; cached review adds no model execution."}
                    atomic_json(final_path, score)
                elif not pending_path.exists():
                    atomic_json(pending_path, _pending_snapshot(score, directory))
            saved_path = final_path if final_path.exists() else pending_path
            status = score["status"] if final_path.exists() else "awaiting_independent_report_review"
            append_event(output, "RECORD_ARM", {"unit_id": entry["unit_id"], "arm": arm,
                "status": status, "path": str(saved_path), "sha256": sha256_file(saved_path)})
            row["arms"][arm] = {"status": status, "score_path": str(saved_path), "score": score}
        rows.append(row)
    paired = []
    for row in rows:
        scores = [row["arms"].get(arm, {}).get("score") for arm in ("B", "C")]
        if all(score and score["status"] == "verified" and score.get("whole_report_numeric_audit_complete")
               and score.get("common_report_sufficiency") is True and score.get("unsupported_claims") == 0 for score in scores):
            b, c = scores
            b_unknown = b.get("unknown_token_usage") is True
            c_unknown = c.get("unknown_token_usage") is True
            tokens = [b["provider_token_usage"] if b_unknown else b.get("total_provider_token_usage", b["provider_token_usage"]),
                      c.get("total_provider_token_usage", c["provider_token_usage"])]
            known = not c_unknown and all(isinstance(usage, dict) and all(isinstance(usage.get(key), int) and usage[key] > 0 for key in ("input_tokens", "output_tokens")) for usage in tokens)
            b_tokens = sum(tokens[0][k] for k in ("input_tokens", "output_tokens")) if known else None
            c_tokens = sum(tokens[1][k] for k in ("input_tokens", "output_tokens")) if known else None
            paired.append({"unit_id": row["unit_id"], "relative_test_mse_gain": (b["test_mse"] - c["test_mse"]) / max(b["test_mse"], 1e-12),
                "token_relative_gain": (b_tokens - c_tokens) / b_tokens if known else None,
                "token_accounting_complete": known and not b_unknown,
                "token_design_input_admissible": known,
                "token_gain_kind": "conservative_lower_bound" if known and b_unknown else "exact" if known else "unavailable",
                "quality_log_ratio_C_over_B": math.log(max(c["test_mse"], 1e-12) / max(b["test_mse"], 1e-12))})
    summary = {"kind": "development_pilot", "registration_sha256": sha256_file(output / "pilot-registration.json"),
        "units": rows, "reviewed_paired_observations": paired,
        "design_inputs_complete": len(paired) == len(registration["units"]) and all(pair["token_design_input_admissible"] for pair in paired),
        "adopted": False, "original_framework_improvement_demonstrated": False,
        "model_effect_A": "not evaluated by this pilot", "provider_billed_cost": None,
        "next_action": "independent statistical sample design after complete paired evidence" if len(paired) == len(rows) else "finish independent report reviews or reconcile resource/failure evidence",
        "limits": "Development data only; failed/unknown/pending units are retained and cannot certify improvement."}
    atomic_json(output / "pilot-summary.json", summary)
    return summary


def continue_pilot(output: Path, unit_id: str, arm: str, reason: str, *, baseline=None, improved=None) -> dict:
    """Authorize one known failed arm's continuation, never an automatic retry loop."""
    output = Path(output).resolve()
    registration = check_pilot(output)
    if unit_id not in {unit["unit_id"] for unit in registration["units"]} or arm not in {"B", "C"}:
        raise ValueError("Unknown pilot unit/arm")
    directory = output / "units" / unit_id / arm
    if (directory / "owner-score.json").exists():
        raise EvidenceError("A final scored arm cannot be replaced by a later success")
    if not (directory / "owner-request.json").exists() or (directory / "arm-response.json").exists():
        raise EvidenceError("Continuation requires a requested unfinished arm; completed callbacks use pilot-run cached review")
    config = registration["config"]
    audit = _continuation_audit(directory, config["model_id"], config["resource_envelope"], reason)
    original_attempts = sorted((directory / "owner-attempts").glob("attempt-*/owner-attempt.json"))
    if not original_attempts:
        owner_entry = next(unit for unit in registration["units"] if unit["unit_id"] == unit_id)
        original_attempts.append(_record_external_attempt(output, directory, load(owner_entry["owner_path"]), arm,
            ModelUnavailable("Interrupted host reconciled with definitive original provider failure; original state preserved before continuation.")))
    authorization = {"unit_id": unit_id, "arm": arm, "reason": reason, "authorized_at": utc_now(),
        "registration_sha256": sha256_file(output / "pilot-registration.json"), "audit": audit,
        "original_attempts": [{"path": str(path), "sha256": sha256_file(path)} for path in original_attempts],
        "resource_policy": "Same registered model/effort/envelope; all prior requests count, unknown usage remains null, completed actions are reused."}
    path = directory / "owner-continuations" / f"{fingerprint(authorization)[:24]}.json"
    atomic_json(path, authorization)
    append_event(output, "AUTHORIZE_CONTINUATION", {"unit_id": unit_id, "arm": arm,
        "path": str(path), "sha256": sha256_file(path)})
    return run_pilot(output, baseline=baseline or UpstreamArm(continuation_reason=reason),
        improved=improved or ImprovedArm(continuation_reason=reason), _selected=(unit_id, arm), _authorization=path)


def review_pilot(output: Path, unit_id: str, arm: str, judgments_path: Path, *, report_kind: str = "primary") -> dict:
    output = Path(output).resolve()
    registration = check_pilot(output)
    if unit_id not in {unit["unit_id"] for unit in registration["units"]} or arm not in {"B", "C"}:
        raise ValueError("Unknown pilot unit/arm")
    directory = output / "units" / unit_id / arm
    judgments = load(judgments_path)
    if isinstance(judgments, dict):
        judgments = judgments["judgments"]
    if report_kind not in {"primary", "companion"}:
        raise ValueError("report_kind must be primary or companion")
    inventory = directory / ("numeric-inventory.json" if report_kind == "primary" else "companion-numeric-inventory.json")
    review_path = directory / ("report-review.json" if report_kind == "primary" else "companion-review.json")
    report = adjudicate_numeric_review(inventory, judgments, review_path, reviewer_role="independent_verifier")
    append_event(output, "INDEPENDENT_REVIEW", {"unit_id": unit_id, "arm": arm,
        "judgments_path": str(Path(judgments_path).resolve()), "judgments_sha256": sha256_file(judgments_path),
        "report_kind": report_kind, "review_sha256": sha256_file(review_path)})
    return report


def score_final(protocol_path: Path, output: Path) -> dict:
    """Score independently registered final artifacts after independent reviews.

    This command intentionally gathers no fresh model calls. Gathered callback
    receipts and reviews must already exist; missing report review cannot become
    an irrevocably recorded final arm failure merely by premature scoring.
    """
    protocol = load(protocol_path)
    _assert_frozen(protocol)
    for unit_id in protocol["suite"]["task_ids"]:
        for arm in ("B", "C"):
            directory = Path(output) / unit_id / arm
            response = directory / "arm-response.json"
            if not response.exists() or not _reviews_complete(directory):
                raise EvidenceError("Final scoring requires completed callback receipts and independent whole-report reviews")
    return run_matched(protocol_path, output, baseline=UpstreamArm(), improved=ImprovedArm())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pilot-register")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("pilot-run")
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("pilot-review")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--arm", choices=("B", "C"), required=True)
    p.add_argument("--judgments", type=Path, required=True)
    p.add_argument("--report-kind", choices=("primary", "companion"), default="primary")
    p = sub.add_parser("pilot-continue")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--arm", choices=("B", "C"), required=True)
    p.add_argument("--reason", required=True)
    p = sub.add_parser("final-score")
    p.add_argument("--protocol", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "pilot-register":
            result = register_pilot(load(args.config), args.output)
        elif args.command == "pilot-run":
            result = run_pilot(args.output)
        elif args.command == "pilot-review":
            result = review_pilot(args.output, args.unit, args.arm, args.judgments, report_kind=args.report_kind)
        elif args.command == "pilot-continue":
            result = continue_pilot(args.output, args.unit, args.arm, args.reason)
        else:
            result = score_final(args.protocol, args.output)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False))
    except (EvidenceError, ValueError, OSError) as error:
        print(json.dumps({"status": "attention_required", "reason": str(error), "goal_complete": False}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
