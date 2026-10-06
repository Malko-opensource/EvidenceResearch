"""Read-only descriptive collection of the preregistered external-agent episodes.

This postprocessing helper never runs a task, verifier, model or agent and never
writes research state. Agent summaries are declarations, not verification proof.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluation"
sys.path.insert(0, str(ROOT))
from research_cli.core import Store


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def stamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def elapsed(start, end):
    first, last = stamp(start), stamp(end)
    return (last - first).total_seconds() if first and last else None


def marker(path, expected_hash=None, task_id=None):
    if expected_hash is not None and sha(path) != expected_hash:
        return {"count": None, "integrity": "invalid", "path": str(path)}
    try:
        rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
        count = sum(row.get("task_id") == task_id for row in rows) if task_id else len(rows)
        return {"count": count, "integrity": "valid", "path": str(path), "sha256": sha(path)}
    except (OSError, ValueError, AttributeError):
        return {"count": None, "integrity": "missing_or_invalid", "path": str(path)}


def c_records(directory, task_id, metadata):
    workspace = Path(metadata.get("research_workspace", directory / "research"))
    if not (workspace / ".research/state.sqlite3").is_file():
        return [], None, None, []
    store = Store(workspace)
    records, total, offset = [], None, 0
    while total is None or offset < total:
        page = store.memory(limit=100, offset=offset)
        total = page["total"]
        for item in page["items"]:
            record = store.show(item["id"])
            if record["registration"]["spec"].get("task_id") != task_id:
                continue
            execution, verification = record.get("run"), record.get("verification")
            spec = record['registration']['spec']
            by_name = {item.get('name'): item for item in record['evidence'] if item.get('run_id')}
            source_links = []
            for name, expected in spec['source_version']['files'].items():
                source = by_name.get('source:' + name, {})
                artifact = by_name.get(name)
                source_links.append({'file': name, 'registered_sha256': expected,
                                     'preserved_source_sha256': source.get('sha256'),
                                     'matches': source.get('sha256') == expected and source.get('integrity') == 'valid'
                                     and (artifact is None or artifact.get('sha256') == expected)})
            criteria_match = spec['criteria'] == metadata.get('criteria')
            validator_match = spec.get('validator_sha256') == metadata.get('fixed_validator_sha256')
            protocol_links = criteria_match and validator_match and all(link['matches'] for link in source_links)
            run_markers = [marker(workspace / e["path"], e["sha256"], task_id)
                           for e in record["evidence"]
                           if e.get("name") == "invocations.jsonl" and e.get("run_id") and e.get("path")]
            count = sum(m["count"] for m in run_markers) if run_markers and all(m["count"] is not None for m in run_markers) else None
            if execution is None:
                count = 0
            records.append({"registration_id": record["registration"]["id"],
                            "registered_at": record["registration"]["created"],
                            "fingerprint": record["registration"]["fingerprint"],
                            "execution": execution["state"] if execution else "registered",
                            "execution_error": (execution.get("receipt") or {}).get("error") if execution else None,
                            "verification": verification["state"] if verification else "pending",
                            "metrics": verification["metrics"] if verification else {},
                            "verification_details": verification["details"] if verification else {},
                            "verification_at": datetime.fromtimestamp(verification["created"], timezone.utc).isoformat() if verification else None,
                            "evidence_integrity": item["evidence_integrity"], "claim_verified": item["claim_verified"],
                            "source_links": source_links, "criteria_match_owner": criteria_match,
                            "validator_matches_owner": validator_match, "protocol_links_valid": protocol_links,
                            "decision": record["decision"]["state"], "marker": run_markers,
                            "actual_execution_count": count, "resources": execution["resources"] if execution else {}})
            if not protocol_links:
                records[-1]['claim_verified'] = False
        offset += len(page["items"])
        if not page["items"]:
            break
    records.sort(key=lambda r: r["registered_at"])
    counts = [record["actual_execution_count"] for record in records if record["execution"] != "registered"]
    total_count = sum(counts) if counts and all(value is not None for value in counts) else None
    duplicates = sum(max(value - 1, 0) for value in counts) if total_count is not None else None
    faults = [record["registration_id"] for record in records
              if record["execution"] in ("failed", "unknown") or record.get("execution_error")
              or record["verification_details"].get("error")]
    return records, total_count, duplicates, faults


def b_records(directory, task_id):
    paths = [path for path in directory.glob("check-*.json") if re.fullmatch(r"check-\d+\.json", path.name)]
    paths.sort(key=lambda path: int(re.search(r"\d+", path.name).group()))
    records, faults, identities = [], [], {}
    for path in paths:
        check = read(path, {})
        index = re.search(r"\d+", path.name).group()
        receipt_path = next((candidate for candidate in (path.with_suffix(".receipt.json"),
                            directory / f"checker-receipt-{index}.json") if candidate.is_file()), None)
        receipt = read(receipt_path, {}) if receipt_path else {}
        linked_hashes = receipt.get("artifact_hashes", {})
        output_hash = receipt.get("output_sha256", linked_hashes.get(path.name))
        integrity = "valid" if output_hash and sha(path) == output_hash else "unknown"
        if output_hash and sha(path) != output_hash:
            integrity = "invalid"
        broken_links = [name for name, expected in linked_hashes.items()
                        if not (directory / name).resolve().is_relative_to(directory.resolve())
                        or sha(directory / name) != expected]
        if broken_links:
            integrity = "invalid"
        registration = read(directory / receipt.get('registration_path', 'registration.json'), {})
        criteria = registration.get('criteria', [registration.get('decision_rule', {})])
        normalized = [{key: item.get(key) for key in ('metric', 'op', 'threshold')} for item in criteria]
        metadata = read(directory / 'episode.json', {})
        criteria_match = normalized == metadata.get('criteria')
        validator_hash = registration.get('fixed_validator_sha256', registration.get('checker', {}).get('owner_declared_sha256'))
        validator_match = validator_hash == metadata.get('fixed_validator_sha256')
        metrics = check.get("metrics", {})
        rate = metrics.get("pass_rate") if isinstance(metrics, dict) else None
        verification = "passed" if rate == 1.0 else "failed" if isinstance(rate, (int, float)) else "inconclusive"
        if integrity == "invalid":
            verification = "inconclusive"
        records.append({"check_path": str(path), "verification": verification,
                        "checker_receipt_path": str(receipt_path) if receipt_path else None,
                        "broken_receipt_hash_links": broken_links,
                        "criteria_match_owner": criteria_match, "validator_matches_owner": validator_match,
                        "metrics": metrics, "verification_details": check.get("details", {}),
                        "verification_at": receipt.get("ended_at", receipt.get("finished_at")), "evidence_integrity": integrity,
                        "claim_verified": verification == "passed" and integrity == "valid" and receipt.get('returncode') == 0
                                          and criteria_match and validator_match,
                        "decision": "agent_declaration_only"})
        if receipt.get("returncode") not in (None, 0) or check.get("status") == "inconclusive" or check.get("error"):
            faults.append(str(path))
    receipts = sorted([*directory.glob("task-run-*.receipt.json"), *directory.glob("execution-*.json")])
    if not receipts and (directory / 'receipt.json').is_file():
        receipts = [directory / 'receipt.json']
    execution_links = []
    expected_marker_hash = None
    for path in receipts:
        receipt = read(path, {})
        if receipt.get("returncode") not in (None, 0):
            faults.append(str(path))
        registration = read(directory / receipt.get("registration_path", "registration.json"), {})
        hashes = receipt.get('artifact_hashes', {})
        registered_hashes = registration.get('source_hashes', {})
        source_hash = receipt.get("source_sha256_before", hashes.get('solution.py', registration.get("source_sha256")))
        registered_source = registration.get('source_sha256', registered_hashes.get('solution.py_planned'))
        identity = {"source": source_hash,
                    "input": registration.get("input_sha256", registered_hashes.get('input.csv')),
                    "runner": registration.get("runner_sha256", registered_hashes.get('task.py')),
                    "criteria": registration.get("criteria", registration.get('decision_rule')),
                    "seed": registration.get("seed"), "task": task_id}
        broken_links = [name for name, expected in hashes.items()
                        if not (directory / name).resolve().is_relative_to(directory.resolve())
                        or sha(directory / name) != expected]
        snapshot = receipt.get('source_snapshot_path')
        if snapshot and sha(directory / snapshot) != receipt.get('source_snapshot_sha256', source_hash):
            broken_links.append(snapshot)
        execution_links.append({'path': str(path), 'returncode': receipt.get('returncode'),
                                'broken_hash_links': broken_links, 'source_sha256': source_hash,
                                'registered_source_matches': source_hash == registered_source if registered_source else None,
                                'registered_input_matches': sha(directory / 'input.csv') == identity['input'],
                                'registered_runner_matches': sha(directory / 'task.py') == identity['runner']})
        if hashes.get('invocations.jsonl'):
            expected_marker_hash = hashes['invocations.jsonl']
        delta = receipt.get("invocations_after", 0) - receipt.get("invocations_before", 0)
        if identity["source"] and delta > 0:
            key = json.dumps(identity, sort_keys=True)
            identities[key] = identities.get(key, 0) + delta
    actual_marker = marker(directory / "invocations.jsonl", expected_marker_hash, task_id)
    count = actual_marker["count"]
    matched = count is not None and sum(identities.values()) == count
    duplicates = sum(max(value - 1, 0) for value in identities.values()) if matched else None
    for record in records:
        record["marker"] = actual_marker
        record['execution_receipts'] = execution_links
        links_valid = any(link['returncode'] == 0 and not link['broken_hash_links'] and link['source_sha256']
                         and link['registered_source_matches'] and link['registered_input_matches'] and link['registered_runner_matches']
                         for link in execution_links)
        record['protocol_links_valid'] = bool(links_valid and count is not None and record['criteria_match_owner']
                                             and record['validator_matches_owner'] and record['evidence_integrity'] == 'valid')
        if not any(link['returncode'] == 0 and not link['broken_hash_links'] and link['source_sha256']
                   and link['registered_source_matches'] and link['registered_input_matches'] and link['registered_runner_matches']
                   for link in execution_links) or count is None:
            record['claim_verified'] = False
    return records, count, duplicates, faults


def events(value):
    if isinstance(value, dict):
        if isinstance(value.get("event"), str):
            yield value
        for child in value.values():
            yield from events(child)
    elif isinstance(value, list):
        for child in value:
            yield from events(child)


def wrapper_checks(directory):
    """Keep checker invocation failures separate from scientific metric failures."""
    paths = [path for path in directory.glob('check-*.json') if re.fullmatch(r'check-\d+\.json', path.name)]
    paths.sort(key=lambda path: int(re.search(r'\d+', path.name).group()))
    checks = []
    for path in paths:
        payload = read(path, {})
        metrics = payload.get('metrics', {})
        rate = metrics.get('pass_rate') if isinstance(metrics, dict) else None
        valid = not isinstance(rate, bool) and isinstance(rate, (int, float)) and math.isfinite(rate)
        checks.append({'path': str(path), 'sha256': sha(path),
                       'wrapper_state': 'completed_check' if valid else 'wrapper_error_or_inconclusive',
                       'pass_rate': rate if valid else None,
                       'error_present': bool(payload.get('error')), 'original_history_preserved': True})
    failures = [index for index, check in enumerate(checks) if check['wrapper_state'] != 'completed_check']
    recovery = ('resolved' if failures and any(check['wrapper_state'] == 'completed_check'
                                              for check in checks[failures[-1] + 1:])
                else 'unresolved' if failures else 'not_observed')
    return {'checks': checks, 'error_count': len(failures), 'recovery': recovery,
            'scope': 'Actual fixed-checker output files; a completed check with pass_rate below 1 is a scientific failure, not a wrapper error'}
def declarations(summary, transcript, records):
    last = records[-1] if records else {}
    verified = last.get("claim_verified", False)
    assertions = []
    for event in events(transcript):
        label = event["event"].lower()
        if "hypothesis" in label or "preregister" in label:
            continue
        success = event.get("criterion_met") is True or event.get("verification") == "passed"
        adopted = str(event.get("decision", "")).lower() in ("adopt", "adopted")
        if success or adopted:
            assertions.append({"source": "transcript", "event": event["event"], "at": event.get("at"),
                               "claims_verified_success": True})
    quality = summary.get("task_quality", {})
    claimed_rate = quality.get("value", quality.get("pass_rate")) if isinstance(quality, dict) else None
    if not isinstance(quality, bool) and isinstance(quality, (int, float)) and summary.get('task_quality_metric') == 'pass_rate':
        claimed_rate = quality
    if claimed_rate == 1.0 or (isinstance(quality, dict) and
                             (quality.get("criterion_met") is True or quality.get("verification_state") == "passed")):
        assertions.append({"source": "episode-summary", "event": "task_quality", "at": summary.get("completed_at"),
                           "claims_verified_success": True})
    decision = summary.get("decision", "")
    decision_state = decision.get("state", decision.get("decision", "")) if isinstance(decision, dict) else decision
    if str(decision_state).lower().startswith("adopt"):
        assertions.append({"source": "episode-summary", "event": "decision", "at": summary.get("completed_at"),
                           "claims_verified_success": True})
    unsupported = []
    for assertion in assertions:
        available = [record for record in records if record.get("claim_verified")
                     and (not stamp(assertion.get("at")) or not stamp(record.get("verification_at"))
                          or stamp(record["verification_at"]) <= stamp(assertion["at"]))]
        if not available:
            unsupported.append(assertion)
    actual_rate = last.get("metrics", {}).get("pass_rate")
    return {"declared_pass_rate": claimed_rate, "actual_pass_rate": actual_rate,
            "pass_rate_agrees": claimed_rate == actual_rate if claimed_rate is not None and actual_rate is not None else None,
            "declared_decision": summary.get("decision"), "actual_decision": last.get("decision"),
            "decision_agrees": str(decision_state).lower().startswith(str(last.get("decision")))
                               if decision_state and last.get("decision") not in (None, "agent_declaration_only") else None,
            "declared_complete_pass_supported": verified if assertions else None,
            "unsupported_claims": {"count": len(unsupported) if summary or transcript else None,
                                   "status": "observed_supplied_declarations" if summary or transcript else "not_observed",
                                   "checked_explicit_declarations": len(assertions),
                                   "items": unsupported,
                                   "scope": "Supplied transcript and summary explicit success/adoption declarations only; no inference about hidden behavior"}}


def memory_pages(value, path='transcript.json'):
    """Extract recorded CLI pages, including JSON stdout inside tool envelopes."""
    if isinstance(value, dict):
        if isinstance(value.get('items'), list) and 'total' in value and 'revision' in value:
            yield {'source': path, 'revision': value['revision'], 'total': value['total'],
                   'items': [{key: item.get(key) for key in ('id', 'verification', 'outcome', 'claim_verified', 'evidence_integrity')}
                             for item in value['items']]}
        for key, child in value.items():
            if key == 'output' and isinstance(child, str):
                try:
                    yield from memory_pages(json.loads(child), path + '.output')
                except ValueError:
                    pass
            elif isinstance(child, (dict, list)):
                yield from memory_pages(child, path + '.' + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from memory_pages(child, path + '[' + str(index) + ']')


def episode(task_id, condition, dispatch):
    directory = EVAL / "results" / task_id / condition
    metadata, summary = read(directory / "episode.json", {}), read(directory / "episode-summary.json", {})
    transcript = read(directory / "transcript.json", {})
    records, count, duplicates, faults = b_records(directory, task_id) if condition == "B" else c_records(directory, task_id, metadata)
    last = records[-1] if records else {}
    observed_memory = list(memory_pages(transcript))
    for path in directory.glob('*memory*.json'):
        observed_memory.extend(memory_pages(read(path, {}), path.name))
    prior_id = metadata.get('prior_registration')
    prior_retrieved = any(item['id'] == prior_id for page in observed_memory for item in page['items']) if prior_id else False
    timing = next((entry for entry in dispatch.get("episodes", [])
                   if entry.get("task_id") == task_id and entry.get("condition") == condition), {})
    complete = bool(summary and records and last.get("verification") in ("passed", "failed", "inconclusive"))
    return {"task_id": task_id, "condition": condition, "status": "complete" if complete else "pending",
            "directory": str(directory), "initial_hashes": metadata.get("initial_hashes"),
            "fixed_validator_sha256": metadata.get("fixed_validator_sha256"),
            "records": records, "final_pass_rate": last.get("metrics", {}).get("pass_rate"),
            "complete_pass": bool(last.get("claim_verified")), "actual_task_execution_count": count,
            "duplicate_executions": duplicates,
            "recovery": "resolved" if faults and last.get("claim_verified") else "unresolved" if faults else "not_observed",
            "observed_fault_evidence": faults,
            "wrapper_checks": wrapper_checks(directory),
            "declared_recovery": summary.get("recovery"),
            "reported_transcript_errors": transcript.get("errors", transcript.get('bookkeeping_errors')),
            "additional_declared_context": {key: summary[key] for key in (
                "recovery_notes", "recovery_details", "bookkeeping_capture_errors", "bookkeeping_errors", "capture_errors",
                "scientific_failures", "iterations") if key in summary},
            "memory_context": {"prior_registration_id": metadata.get('prior_registration'),
                               "prior_excluded_from_task_metrics": True,
                               "recorded_prior_retrieval_confirmed": prior_retrieved,
                               "observed_cli_memory_pages": observed_memory,
                               "declared_initial_memory_total": summary.get('initial_memory_total'),
                               "declared_initial_memory_item_count": summary.get('initial_memory_item_count'),
                               "declared_initial_memory_items": summary.get('initial_memory_items')
                                    if isinstance(summary.get('initial_memory_items'), int)
                                    else len(summary['initial_memory_items']) if isinstance(summary.get('initial_memory_items'), list) else None,
                               "declared_useful_memory_influenced_hypothesis": summary.get('useful_memory_influenced_hypothesis'),
                               "declared_interpretation": summary.get('memory_interpretation', summary.get('memory_influence'))},
            "declaration_comparison": declarations(summary, transcript, records),
            "external_tokens": {"status": "unknown", "value": None},
            "timing": {"dispatch_started_at": timing.get("started_at"), "root_collected_at": timing.get("collected_at"),
                       "agent_declared_completed_at": summary.get("completed_at"),
                       "root_collection_elapsed_seconds": elapsed(timing.get("started_at"), timing.get("collected_at")),
                       "agent_declared_completion_elapsed_seconds": elapsed(timing.get("started_at"), summary.get("completed_at")),
                       "root_collection_basis": dispatch.get("timing_basis")}}


def pair(spec, collected):
    left, right = [collected[(spec["task_id"], condition)] for condition in spec["order"]]
    match = None
    if left["initial_hashes"] and right["initial_hashes"]:
        match = left["initial_hashes"] == right["initial_hashes"]
        if not match or left["fixed_validator_sha256"] != right["fixed_validator_sha256"]:
            raise ValueError("Paired initial files or validator differ: " + spec["task_id"])
    return {"task_id": spec["task_id"], "order": spec["order"], "initial_hashes_identical": match,
            "status": "complete" if left["status"] == right["status"] == "complete" else "pending",
            "conditions": {episode["condition"]: {key: episode[key] for key in (
                "status", "final_pass_rate", "complete_pass", "actual_task_execution_count", "duplicate_executions", "recovery", "timing")}
                           for episode in (left, right)}}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    protocol = read(EVAL / "protocol.json", {})
    dispatch = read(EVAL / "dispatch.json", {})
    ordered = [(spec["task_id"], condition) for key in ("primary_pairs", "memory_pairs")
               for spec in protocol[key] for condition in spec["order"]]
    collected = {key: episode(*key, dispatch) for key in ordered}
    completed = sum(value["status"] == "complete" for value in collected.values())
    result = {"schema_version": 1, "protocol_id": protocol["protocol_id"],
              "collected_at": datetime.now(timezone.utc).isoformat(), "completed_episodes": completed,
              "expected_episodes": len(ordered), "status": "complete" if completed == len(ordered) else "pending",
              "primary_pairs": [pair(spec, collected) for spec in protocol["primary_pairs"]],
              "memory_pairs": [pair(spec, collected) for spec in protocol["memory_pairs"]],
              "episodes": list(collected.values()), "research_improvement": "unproven", "weighted_score": None,
              "limitations": protocol["limitations"],
              "evidence_policy": "C uses read-only Store records and copied artifact hashes; B uses fixed-check files and receipt hash links. Local records are not an OS security boundary."}
    output = EVAL / "results" / "summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({"output": str(output), "completed_episodes": completed, "expected_episodes": len(ordered),
                      "status": result["status"], "research_improvement": "unproven"}))


if __name__ == "__main__":
    main()
