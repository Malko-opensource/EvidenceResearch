"""Development helper for audited failed model requests and resume lineage.

This does not replace the frozen completed-call evaluator. Integrate only into
a newly frozen/preregistered evaluator version. Unknown usage is never zero.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _safe(path: Path, roots: list[Path]) -> Path:
    path = Path(path)
    resolved = path.resolve()
    if path.is_symlink() or not any(resolved.is_relative_to(root) for root in roots):
        raise ValueError("model attempt evidence escapes its explicitly allowed roots")
    if not resolved.is_file() or resolved.stat().st_size > 50_000_000:
        raise ValueError("model attempt evidence missing or exceeds size boundary")
    return resolved


def audit_failed_model_attempts(failed_dirs: list[str], *, model_id: str,
                               allowed_roots: list[str],
                               host_action_receipts: dict[str, str],
                               lineage_path: str | None) -> dict:
    """Account rejected/incomplete requests without calling them experiments.

    ``host_action_receipts`` keys are resolved failed-directory strings. A trusted
    host receipt and explicit immutable lineage are necessary to establish that
    the failed response did not lead to a host action. They must link raw sources.
    The public model identifier is checked, not unexposed server weight versions.
    """
    if not failed_dirs:
        return {"valid": True, "failed_attempts": 0, "failed_seconds": 0.0,
                "failed_token_usage": {"input_tokens": 0, "output_tokens": 0},
                "unknown_failed_token_usage": False, "provider_billed_cost": None,
                "adoption_blocked_for_token_endpoint": False, "calls": [], "evidence": []}
    roots = [Path(root).resolve() for root in allowed_roots]
    if not roots or not model_id or not lineage_path:
        raise ValueError("failed requests require model, allowed roots, and explicit resume lineage")
    directories = [Path(value).resolve() for value in failed_dirs]
    if len(set(directories)) != len(directories):
        raise ValueError("duplicate failed directory would double-count a provider request")
    lineage_file = _safe(Path(lineage_path), roots)
    lineage = json.loads(lineage_file.read_text(encoding="utf-8"))
    if lineage.get("provenance") != "trusted_host_audit" or lineage.get("kind") != "explicit_model_attempt_resume_lineage" or lineage.get("model_id") != model_id:
        raise ValueError("resume lineage must be an explicit same-model trusted host audit")
    linked = {str(Path(item["failed_dir"]).resolve()): item for item in lineage.get("attempts", [])}
    if len(linked) != len(lineage.get("attempts", [])) or set(linked) != {str(path) for path in directories}:
        raise ValueError("resume lineage does not cover exactly the failed attempts")
    calls, evidence, seen = [], [{"path": str(lineage_file), "sha256": _hash(lineage_file)}], set()
    for folder in directories:
        record_path = _safe(folder / "result.json", roots)
        result = json.loads(record_path.read_text(encoding="utf-8"))
        request_path = _safe(folder / "request.json", roots)
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if request.get("model") != model_id or result.get("model") != model_id:
            raise ValueError("failed model identifier differs from the matched model")
        if request.get("execution_kind") != "real_model" or result.get("execution_kind") != "real_model" or result.get("status") != "failed":
            raise ValueError("a simulated or completed call is not a failed real-model attempt")
        keys = ("model", "prompt", "reasoning_effort")
        limitations = []
        if "full_prompt" in request or "provider_source_sha256" in request:
            if "full_prompt" not in request or "provider_source_sha256" not in request or not request["full_prompt"].endswith(request["prompt"]):
                raise ValueError("full prompt/source lineage is incomplete")
            keys += ("full_prompt", "provider_source_sha256")
        else:
            limitations.append("legacy request did not preserve guard/full_prompt/provider source; development evidence only")
        identity = {key: request.get(key) for key in keys}
        if _digest(identity) != request.get("fingerprint") or request.get("fingerprint") != result.get("fingerprint"):
            raise ValueError("failed request fingerprint changed")
        command = request.get("command", [])
        if not isinstance(command, list) or "--model" not in command or command.index("--model") + 1 >= len(command) or command[command.index("--model") + 1] != model_id:
            raise ValueError("failed CLI request command does not name the matched model")
        hashes = result.get("files", {})
        if not {"request.json", "events.jsonl", "stderr.log"}.issubset(hashes):
            raise ValueError("failed model evidence inventory incomplete")
        for filename, digest in hashes.items():
            if Path(filename).name != filename or _hash(_safe(folder / filename, roots)) != digest:
                raise ValueError("failed model evidence hash changed")
        events_path = _safe(folder / "events.jsonl", roots)
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        if any(event.get("type") == "turn.completed" for event in events):
            raise ValueError("failed-attempt evidence contains a completed turn")
        failed = [event for event in events if event.get("type") == "turn.failed"]
        if len(failed) != 1:
            raise ValueError("failed-attempt evidence requires one explicit raw turn.failed event")
        tools = [event for event in events if event.get("item", {}).get("type") not in (None, "agent_message", "reasoning")]
        if tools or result.get("tool_calls"):
            raise ValueError("a failed request with model tool actions is disqualified")
        seconds = result.get("wall_seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError("failed request wall-clock accounting is invalid")
        receipt_path = _safe(Path(host_action_receipts[str(folder)]), roots)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        result_hash, fingerprint = _hash(record_path), request["fingerprint"]
        if receipt.get("provenance") != "trusted_host_audit" or receipt.get("attempt_result_sha256") != result_hash or receipt.get("request_fingerprint") != fingerprint:
            raise ValueError("failed host action receipt is not linked to the exact request/result")
        if receipt.get("host_action_taken") is not False or receipt.get("model_response_consumed") is not False:
            raise ValueError("failed request led to a host action or consumed response")
        if not receipt.get("sources") or not str(receipt.get("retry_reason", "")).strip():
            raise ValueError("failed host receipt needs original action evidence and explicit retry rationale")
        for source in receipt["sources"]:
            path = _safe(Path(source["path"]), roots)
            if _hash(path) != source["sha256"]:
                raise ValueError("failed host-action source changed")
        entry = linked[str(folder)]
        if entry.get("result_sha256") != result_hash or entry.get("request_fingerprint") != fingerprint or str(Path(entry.get("host_action_receipt", "")).resolve()) != str(receipt_path) or entry.get("receipt_sha256") != _hash(receipt_path):
            raise ValueError("resume lineage changed the failed attempt or host receipt")
        attempt_id = _digest({"result_sha256": result_hash, "events_sha256": _hash(events_path), "request_sha256": _hash(request_path)})
        if attempt_id in seen:
            raise ValueError("copied failure record would double-count one actual provider attempt")
        seen.add(attempt_id)
        # Only a provider-attested failure usage is eligible for exact accounting.
        # result.usage={} means absent evidence, never a measurement of zero.
        raw_usage = failed[0].get("usage")
        known = isinstance(raw_usage, dict) and all(isinstance(raw_usage.get(name), int) and not isinstance(raw_usage[name], bool) and raw_usage[name] >= 0 for name in ("input_tokens", "output_tokens"))
        token_usage = {name: raw_usage[name] for name in ("input_tokens", "output_tokens")} if known else None
        if known and any(result.get("usage", {}).get(name) != raw_usage[name] for name in token_usage):
            raise ValueError("failed usage disagrees with raw provider failure event")
        error = failed[0].get("error", {})
        calls.append({"attempt_id": attempt_id, "directory": str(folder), "fingerprint": fingerprint,
                      "wall_seconds": seconds, "token_usage": token_usage,
                      "classification": "failed_model_request_without_host_action",
                      "error": error.get("message") if isinstance(error, dict) else str(error),
                      "limitations": limitations})
        evidence.extend([{"path": str(record_path), "sha256": result_hash},
                         {"path": str(events_path), "sha256": _hash(events_path)},
                         {"path": str(receipt_path), "sha256": _hash(receipt_path)}])
    unknown = any(call["token_usage"] is None for call in calls)
    totals = None if unknown else {name: sum(call["token_usage"][name] for call in calls) for name in ("input_tokens", "output_tokens")}
    return {"valid": True, "failed_attempts": len(calls), "failed_seconds": math.fsum(call["wall_seconds"] for call in calls),
            "failed_token_usage": totals, "unknown_failed_token_usage": unknown, "provider_billed_cost": None,
            "adoption_blocked_for_token_endpoint": unknown, "calls": calls, "evidence": evidence,
            "scope": "actual request count/time plus provider-attested usage; absent failure usage remains unknown"}
