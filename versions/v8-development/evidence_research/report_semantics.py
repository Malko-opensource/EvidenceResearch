"""Owner-only semantic result review; never participant self-adjudication.

Every paragraph and JSON string value is inventoried, including claims without
digits. Coverage is mechanical. Mapping natural language to predicates and
identifying every result assertion remains the independent reviewer's explicit
responsibility; this is not a proof of unrestricted natural-language entailment
or reviewer identity. Predicates accept actual pinned artifacts, not LLM scores.
"""
from __future__ import annotations

import ast
from decimal import Decimal
import json
import math
from pathlib import Path
import re

from .tasks import sha256_file, value_hash, write_json
from .verifier import verify

SEMANTIC_SCHEMA_VERSION = "whole-report-semantics-3-c7-common-context-development"
FACT_REGISTRY_SHA256 = "54217c18c38a544c9ee1094eb772170914d3f0277f9ba88ffd4192d236344907"
FACT_CORPUS_SHA256 = "64d0f27c0faae3d18fb4a57e24de80c2612ee0785936ddfa79f754aa91c6e5c9"
SEMANTIC_POLICY = {"schema_version": SEMANTIC_SCHEMA_VERSION, "required_for_both_arms": True,
    "scope": "all primary-report paragraphs and structured companion JSON keys, string/scalar values; independent result-claim mapping",
    "adoption": "numeric AND semantic inventories complete; both unsupported counts zero",
    "historical_resources": "Common eligible original ContextBoundary and full chronological receipt prefix in either arm; narrowly parsed visible historical resource list; target/later requests excluded; absent failed usage remains null. Legacy original C receipt adapter remains for explicitly versioned engineering regressions.",
    "derived_metrics": "Whitelisted same-actual-run MSE differences with exact split/direction/unit and displayed rounding only; no ratios, causes, significance or generalization",
    "source_facts": {"registry_sha256": FACT_REGISTRY_SHA256, "corpus_sha256":FACT_CORPUS_SHA256, "scope": "Fixed source-bound synopsis fact forms only; no arbitrary paraphrase, full-paper reading or locally measured benefit"},
    "direct_literature_quotes": "Exact excerpt plus source ID and URL of the externally pinned common five-synopsis corpus only; attribution, not local truth or reading. Other quote-format regressions are engineering_legacy.",
    "actual_evidence_qualification": "Actual report completeness requires semantic_evidence_qualification=actual; component_fixture, engineering_legacy and unqualified evidence cannot enable actual completion or adoption. Unbounded registered-hypothesis priors and C-only historic resources remain engineering_legacy.",
    "named_input_availability": "Original eligible request input only, distinct from full history or proof of reading/comprehension; paths without metric values do not establish value availability",
    "limits": "fixed predicates validate evidence and scope; exhaustive interpretation is an accountable independent reviewer judgement, not automatic NLP entailment or authenticated human identity; copied corpus and references do not prove agent reading or comprehension"}
_RESULT_CUE = re.compile(r"\b(?:best|better|worse|improv\w*|superior|successful|reproduc\w*|replicat\w*|caus\w*|generaliz\w*|measur\w*|execut\w*|validation|verified|evidence|result\w*)\b|개선|재현|인과|일반화|검증|실행|측정|최선|결과", re.I)
_BROAD_EFFECT = re.compile(r"(?:framework|research performance|memory|model replacement|프레임워크|연구 성능|기억|모델 교체).{0,100}(?:improv|superior|caus|benefit|개선|효과|우수)|(?:caus|generaliz|인과|일반화)", re.I | re.S)
_TENTATIVE = re.compile(r"\b(?:may|might|could|suggest|hypothes\w*|propos\w*|plan|would|next|unexecuted|untested|uncertain)\b|\bwill\s+(?:test|assess|evaluate|investigate|distinguish|examine)\b|가설|제안|추론|가능|미실행|미검증|다음", re.I)
_LIMITATION = re.compile(r"\b(?:not|no|unproven|unavailable|unknown|cannot|insufficient|limited)\b|미입증|없|불가|한계|불확실", re.I)
_REPRODUCTION = re.compile(r"\b(?:reproduced|replicated|independently replicated)\b|재현되|재현했|독립 재현", re.I)
_MINIMUM = re.compile(r"\b(?:best|minimum|lowest|optimal)\b|최선|최소|최적", re.I)
_INDEPENDENT_REPEATS = re.compile(r"\bindependent\s+(?:replicat\w*|repeat\w*|trial\w*)\b|독립.{0,12}(?:반복|재현)", re.I)
_COMPARISON = re.compile(r"\b(?:improved|improvement|better|worse|worsened|outperform\w*|reduced|superior)\b|개선|악화|우수|비교", re.I)
_ASSERTED_RESULT = re.compile(r"\b(?:improved|caused|outperformed|achieved|executed|verified|measured|reproduced|replicated|successful|better|worse|superior|best|minimum|lowest|optimal)\b|개선했|유발|실행했|검증됐|재현했|최선|우수", re.I)
_PAST_RESULT = re.compile(r"\b(?:improved|caused|outperformed|achieved|executed|verified|measured|reproduced|replicated)\b|개선했|유발|실행했|검증됐|재현했", re.I)


def parse_temporal_resource_list(raw: str) -> dict | None:
    """Finite introductory temporal/resource-list grammar, not paragraph scope.

    Only one exact sentence/clause may inherit its leading before-request cue.
    Unknown monetary cost belongs in a separate limitation span. Arbitrary
    historical design prose, final/forecast clauses and added claims fail closed.
    Returned display tokens are later checked against *every* audited quantity.
    """
    if not isinstance(raw, str): return None
    text = raw.strip().rstrip(".;").strip()
    intro = re.fullmatch(r"(?:Immediately )?[Bb]efore this (?:proposal|request),\s+(.+)", text, re.S)
    if intro is None: return None
    body = intro.group(1); number = r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
    if re.search(r"\b(?:final|overall|entire|forecast|expected|next|will|caused|improved)\b|최종|예상|인과", body, re.I): return None
    units = {"distinct CPU executions":"actual_cpu_executions", "actual CPU executions":"actual_cpu_executions",
        "CPU executions":"actual_cpu_executions", "CPU seconds":"cpu_execution_seconds",
        "distinct configurations":"distinct_configurations", "completed provider calls":"completed_provider_calls",
        "failed provider attempts":"failed_provider_attempts", "input tokens":"input_tokens", "output tokens":"output_tokens",
        "provider wall seconds":"wall_seconds", "provider seconds":"wall_seconds"}
    entries = []
    grid = re.fullmatch(r"measured resources were (.+)", body, re.I | re.S)
    if grid:
        for item in re.split(r",\s*(?:and\s+)?|\s+and\s+", grid.group(1), flags=re.I):
            match = re.fullmatch(rf"({number})\s+(.+)", item.strip())
            key = next((v for k, v in units.items() if match and match.group(2).lower() == k.lower()), None)
            if key is None: return None
            entries.append((key, match.group(1)))
    else:
        usage = re.fullmatch(rf"(?:measured )?(?:provider )?(input|output) usage was ({number}) tokens", body, re.I)
        combined = re.fullmatch(rf"({number}) distinct configurations required ({number}) CPU executions totaling ({number}) seconds, alongside ({number}) completed provider calls totaling ({number}) seconds and ({number}) input plus ({number}) output tokens", body, re.I)
        if usage: entries = [(usage.group(1).lower()+"_tokens", usage.group(2))]
        elif combined: entries = list(zip(("distinct_configurations", "actual_cpu_executions", "cpu_execution_seconds", "completed_provider_calls", "wall_seconds", "input_tokens", "output_tokens"), combined.groups()))
        else: return None
    quantities = {}
    counts = {"actual_cpu_executions", "distinct_configurations", "completed_provider_calls", "failed_provider_attempts", "input_tokens", "output_tokens"}
    for key, display in entries:
        value = Decimal(display)
        if key in quantities or not value.is_finite() or value < 0 or key in counts and value != value.to_integral_value(): return None
        if key not in counts and not -12 <= value.as_tuple().exponent <= 0: return None
        if key in counts and value > 10**15: return None
        quantities[key] = {"display":display,"value":int(value) if key in counts else float(value)}
    return {"scope":"historical_pre_request", "quantities":quantities}


def _fact_registry() -> tuple[dict, Path, Path]:
    base = Path(__file__).resolve().parents[1]; registry = base / "references/source_facts_c7.json"
    corpus = base / "references/task_literature_v2.json"
    if sha256_file(registry) != FACT_REGISTRY_SHA256: raise ValueError("source-fact registry differs from the executing fixed source pin")
    if sha256_file(corpus) != FACT_CORPUS_SHA256: raise ValueError("source-fact corpus differs from its executing external source pin")
    record = _load(registry); source = _load(corpus)
    if record.get("source_corpus_sha256") != sha256_file(corpus) or record.get("source_records_sha256") != value_hash(source["records"]):
        raise ValueError("source-fact corpus differs from registered original synopses")
    originals = {item["id"]:item for item in source["records"]}
    for fact in record["facts"]:
        original = originals.get(fact["source_id"])
        if original is None or fact["url"] != original["url"] or fact["source_record_sha256"] != value_hash(original) or fact["source_excerpt"] not in original["text"]:
            raise ValueError("fixed fact lacks exact original source/conditions binding")
    return record, registry, corpus


def frozen_semantic_reference_hashes() -> dict[str, str]:
    """Reader-only, externally pinned source closure for registration/archive."""
    _, registry, corpus = _fact_registry()
    return {str(registry): FACT_REGISTRY_SHA256, str(corpus): FACT_CORPUS_SHA256}


def _context_boundary(arguments: dict, root: Path, *, component_fixture: bool = False) -> dict:
    from .context_boundary import audit_context_boundary
    if set(arguments["boundary"]) != {"path", "sha256"}: raise ValueError("common boundary must be an exact source link")
    record = audit_context_boundary(arguments["boundary"], Path(root).resolve())
    if record.get("eligible") is not True:
        synthetic_only = record.get("fixture_only") is True and record.get("pending_reasons") == ["synthetic_or_fixture_receipt_ineligible_for_actual_adoption"]
        if not component_fixture or not synthetic_only:
            raise ValueError("original context has missing logical/return binding or synthetic-only evidence; actual support remains unknown or pending")
    return record


def _candidate_boundary_binding(spec: dict, record: dict) -> None:
    """A later executed hypothesis belongs to this original model request."""
    evidence = spec.get("model_evidence", {})
    if evidence.get("fingerprint") != record.get("request_fingerprint") or not record.get("call_id") or evidence.get("call_id") != record["call_id"]:
        raise ValueError("registered hypothesis is not linked to this exact original proposal request")


def recompute_historical_resources(arguments: dict, arm_output: Path) -> dict:
    """Audit a complete source-bound C prefix, never an arbitrary receipt subset.

    The final transport/history files are owner-linked and rechecked; the exact
    original proposal input, its prerequest snapshot and the chronological prefix
    decide membership. Later requests are discovered but excluded from the cost.
    Failed usage remains unknown unless attested by its raw failure event.
    """
    from .evaluation import _audit_model_evidence, _audit_request_inventory
    from .model_attempt_audit import audit_failed_model_attempts
    from .comparison_arms import provider_resource_observation

    root = Path(arm_output).resolve()
    if arguments.get("scope") != "historical_pre_proposal":
        raise ValueError("historical resources require an explicit pre-proposal scope")
    paths = {key: _checked_link(arguments[key], root) for key in
             ("proposal_request", "transport_trace", "callback_registration", "research_audit")}
    if paths["proposal_request"].name != "request.json" or paths["transport_trace"] != root / "model-transport.jsonl" or paths["callback_registration"] != root / "callback-registration.json" or paths["research_audit"] != root / "research-audit.json":
        raise ValueError("historical resources require the original C host receipt locations")
    registration = _load(paths["callback_registration"])
    if registration.get("implementation_sha256") != sha256_file(Path(__file__).with_name("comparison_arms.py")):
        raise ValueError("historical callback source differs from the executing frozen adapter source")
    model_id, envelope = registration["model_id"], registration["resource_envelope"]
    rows = [json.loads(line) for line in paths["transport_trace"].read_text(encoding="utf-8").splitlines() if line.strip()]
    requested, terminal, positions = [], {}, {}
    stable_keys = ("call_id", "model_id", "request_sha256", "retrieved_run_ids", "resource_observation_path", "resource_observation_sha256", "classification")
    for position, row in enumerate(rows):
        call = row.get("call_id")
        if row.get("status") == "requested":
            if call != f"improved-{len(requested):04d}" or call in positions or row.get("classification") != "actual_model" or row.get("model_id") != model_id:
                raise ValueError("historical model request ordinals or actual-model conditions differ")
            positions[call] = position; requested.append(row)
        elif row.get("status") in {"completed", "failed"}:
            if call not in positions or call in terminal or any(row.get(key) != requested[int(call.split('-')[-1])].get(key) for key in stable_keys):
                raise ValueError("historical completion has no unique matching original request")
            expected_event = "completion" if row["status"] == "completed" else "failure"
            if row.get("event") != expected_event:
                raise ValueError("historical terminal transport event differs")
            terminal[call] = (position, row)
        else:
            raise ValueError("historical transport contains an unknown action state")
    if not requested or set(terminal) != set(positions) or len(requested) > envelope["proposal_calls_per_unit"]:
        raise ValueError("historical request inventory is unresolved or exceeds registered resources")
    target = paths["proposal_request"].parent
    target_call = target.name
    if target_call not in positions or target != Path(terminal[target_call][1]["evidence_dir"]).resolve():
        raise ValueError("historical target is not the original request ordinal")
    target_index = int(target_call.split('-')[-1]); boundary = positions[target_call]
    if any(terminal[row["call_id"]][0] >= boundary for row in requested[:target_index]):
        raise ValueError("a prefix request was unresolved at the historical proposal boundary")
    completed, failed = [], []
    source_links = list(arguments[key] for key in paths)
    for row in requested:
        end = terminal[row["call_id"]][1]; folder = Path(end["evidence_dir"]).resolve()
        if folder != root / "model" / row["call_id"]:
            raise ValueError("historical provider directory differs from its original ordinal")
        request, result = _load(folder / "request.json"), _load(folder / "result.json")
        decoded = json.loads(request["prompt"])
        if request["prompt"] != json.dumps(decoded, ensure_ascii=False, sort_keys=True) or value_hash(decoded) != row["request_sha256"] or result.get("status") != end["status"]:
            raise ValueError("historical source input or terminal status differs")
        for key in ("fingerprint", "execution_kind", "usage", "wall_seconds"):
            if end.get("model_evidence", {}).get(key) != result.get(key):
                raise ValueError("transport resource receipt differs from raw provider completion")
        (completed if end["status"] == "completed" else failed).append(str(folder))
    _audit_request_inventory(completed, failed, root)
    # Validate settings, guard, source, request/result/raw-event hashes for all
    # completed calls, so an omitted or substituted prefix cannot hide a request.
    _audit_model_evidence(completed, root, model_id, envelope)
    failure_audit = {"calls": [], "evidence": []}
    if failed:
        lineage = _checked_link(arguments["failed_lineage"], root)
        receipts = {value: terminal[Path(value).name][1]["host_no_action_receipt"] for value in failed}
        failure_audit = audit_failed_model_attempts(failed, model_id=model_id, allowed_roots=[str(root)],
            host_action_receipts=receipts, lineage_path=str(lineage), resource_envelope=envelope, arm_output=str(root))
        source_links.append(_link(lineage))
    target_request = _load(paths["proposal_request"]); context = json.loads(target_request["prompt"])
    if context.get("public_task") != registration["public_task"] or context.get("goal", {}).get("payload_sha256") != registration["payload_sha256"] or context.get("remaining_proposal_calls") != envelope["proposal_calls_per_unit"] - target_index:
        raise ValueError("historical proposal task or registered resource boundary differs")
    snapshot_link = {"path": requested[target_index]["resource_observation_path"], "sha256": requested[target_index]["resource_observation_sha256"]}
    snapshot_path = _checked_link(snapshot_link, root)
    if snapshot_path != root / "resource-observations" / f"{target_call}.json":
        raise ValueError("historical observation path differs from the request ordinal")
    snapshot = _load(snapshot_path)
    if snapshot.get("call_id") != target_call or snapshot.get("resources") != context.get("observed_resources"):
        raise ValueError("historical resource snapshot differs from the exact original provider input")
    audit = _load(paths["research_audit"])
    if audit.get("provenance") != "trusted_host_audit":
        raise ValueError("historical CPU resources require the original trusted host ledger")
    previous = "0" * 64; execution_ids = []
    for index, event in enumerate(audit["events"], 1):
        content = {key: event[key] for key in ("timestamp", "phase", "payload", "previous_hash")}
        if event.get("sequence") != index or event["previous_hash"] != previous or event.get("event_hash") != value_hash(content):
            raise ValueError("historical CPU event order or immutable hash chain differs")
        previous = event["event_hash"]
        if event["phase"] == "EXECUTE" and event["payload"].get("state") == "running":
            execution_ids.append(event["payload"]["run_id"])
    runs = {run["run_id"]: run for run in audit["runs"]}
    if len(runs) != len(audit["runs"]) or len(execution_ids) != len(set(execution_ids)):
        raise ValueError("historical CPU ledger duplicates an actual execution")
    discovered = {path.parent.resolve() for path in root.rglob("registered_spec.json")
                  if (path.parent / "result.json").exists() and _load(path.parent / "result.json").get("execution_kind") == "actual_cpu_execution"}
    if discovered != {Path(runs[identity]["run_dir"]).resolve() for identity in execution_ids}:
        raise ValueError("historical CPU ledger omits independently discovered actual executions")
    prefix_calls = {row["call_id"] for row in requested[:target_index]}
    historical_runs, cpu_sources, cpu_order = [], [], []
    for identity in execution_ids:
        run = runs[identity]; directory = Path(run["run_dir"]).resolve()
        spec, result, checked, links = _actual_run(run_reference(directory), root, require_success=False)
        if run.get("spec") != spec or run.get("result") != result or directory.name != identity:
            raise ValueError("historical CPU ledger differs from original actual artifacts")
        evidence = spec.get("model_evidence", {}); call = evidence.get("call_id")
        if call not in terminal or terminal[call][1]["status"] != "completed" or evidence.get("fingerprint") != _load(Path(terminal[call][1]["evidence_dir"]) / "result.json")["fingerprint"]:
            raise ValueError("historical CPU invocation is not linked to the original completed proposal")
        if spec.get("model") != model_id or spec.get("resource_envelope") != envelope or spec.get("task_bundle") != registration["public_task"]["task_bundle"] or spec.get("seed") != registration["public_task"]["seed"]:
            raise ValueError("historical CPU task/model/resources differ from preregistration")
        if call in prefix_calls:
            historical_runs.append(run); cpu_sources.extend(links)
            cpu_order.append({"execution_id": identity, "result_path": str(directory / "result.json"), "result_sha256": sha256_file(directory / "result.json")})
    ledger = context.get("host_ledger", {})
    if ledger.get("current_events_path") != str(root / "research/research.sqlite3") or ledger.get("actual_execution_receipts") != cpu_order or context.get("actual_cpu_attempts_to_date") != len(historical_runs) or context.get("distinct_configs_to_date") != len({value_hash(run["spec"]["config"]) for run in historical_runs}):
        raise ValueError("historical CPU prefix or receipt order differs from the original provider input")
    prefix = [terminal[row["call_id"]][1] for row in requested[:target_index]]
    prefix_failed = [call for call in failure_audit["calls"] if Path(call["directory"]).name in prefix_calls]
    unknown = any(call["token_usage"] is None for call in prefix_failed)
    failed_usage = None if unknown else {key: sum(call["token_usage"][key] for call in prefix_failed) for key in ("input_tokens", "output_tokens")}
    expected = provider_resource_observation(prefix, historical_runs, actual=True,
        failed_audit={"valid": True, "failed_attempts": len(prefix_failed), "unknown_failed_token_usage": unknown, "failed_token_usage": failed_usage})
    if context["observed_resources"] != expected:
        raise ValueError("historical cumulative values or receipt lists differ from independently audited prefix")
    measures = {"provider_attempts": expected["provider_attempts"], "completed_provider_calls": expected["completed_provider_calls"],
        "failed_provider_attempts": expected["failed_provider_attempts"], "input_tokens": None if not expected["tokens_known"] else expected["token_usage"]["input_tokens"],
        "output_tokens": None if not expected["tokens_known"] else expected["token_usage"]["output_tokens"], "wall_seconds": expected["wall_seconds"],
        "actual_cpu_executions": expected["actual_cpu_executions"], "cpu_execution_seconds": expected["cpu_execution_seconds"]}
    return {"measures": measures, "tokens_known": expected["tokens_known"], "proposal_call_id": target_call,
        "prefix_call_ids": [row["call_id"] for row in prefix], "evidence": source_links + [snapshot_link] + expected["sources"] + cpu_sources + failure_audit["evidence"],
        "scope": "Historical cumulative resource receipts available immediately before this original proposal request; the target request and all later calls are excluded. Not final whole-unit totals, next-call cost, expected gain, billing, independent-review cost or research superiority."}


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=\S)", text) if part.strip()]


def _directly_negated(sentence: str, match) -> bool:
    prefix = sentence[:match.start()]
    return bool(re.search(r"\b(?:not|never|no)\s+(?:[\w-]+\s+){0,3}$|(?:아니|없|미입증).{0,8}$", prefix, re.I))


def _clauses(sentence: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;,]|\b(?:but|however|although|even though|and)\b|하지만|그러나|반면", sentence, flags=re.I) if part.strip()]


def _negative_generalization(clause: str) -> bool:
    """An explicit denying predicate must restrict its own assertion clause."""
    denial = re.search(r"\b(?:does|do|did|can|could)\s+not\s+(?:establish|demonstrate|prove|show|support|identify)\b|\bcannot\s+(?:establish|demonstrate|prove|show|support|identify)\b", clause, re.I)
    if denial:
        return not _ASSERTED_RESULT.search(clause[:denial.start()]) and not _PAST_RESULT.search(clause[denial.end():])
    denial = re.search(r"(?:입증|증명|확인|확정)(?:하|되)?지\s*않(?:는|다|았)|(?:입증|증명|확인|확정).{0,5}(?:못한다|불가능)", clause)
    if denial is None:
        # Exact local denial of *claiming* an effect, not an unrelated negative.
        denial = re.search(r"(?:주장하지\s*않(?:는다|았다)|주장하지\s*못한다)", clause)
    return bool(denial and not _ASSERTED_RESULT.search(clause[:denial.start()]) and not _PAST_RESULT.search(clause[denial.end():]))


def _adjectival_prior(match, sentence: str) -> bool:
    if match.group().lower() not in {"verified", "measured"}: return False
    tail = sentence[match.end():]
    modifiers = r"(?:(?:unregularized|regularized|previous|registered|observed|polynomial)\s+){0,3}"
    return bool(re.match(rf"\s+{modifiers}(?:(?:linear|quadratic|cubic|quartic|quintic|sextic)\b(?:\s+(?:fit|incumbent|baseline|candidate|model))?|degree[- ](?:[1-8])\s+(?:fit|model|baseline|candidate)|(?:fit|incumbent|baseline|candidate|metric|result|error|memory)\b)", tail, re.I))


def _normative_method(raw: str) -> bool:
    return bool(re.fullmatch(r"The (?:planned )?procedure (?:should|must) (?:choose|select) the (?:observed minimum|lowest observed validation MSE)\.", raw.strip()))


def _check_prior_descriptors(raw: str, priors: list[tuple]) -> None:
    names = {"linear":1,"quadratic":2,"cubic":3,"quartic":4,"quintic":5,"sextic":6}
    for match in re.finditer(r"\b(?:verified|measured)\s+(?P<modifiers>(?:(?:unregularized|regularized|previous|registered|observed)\s+)*)(?P<degree>linear|quadratic|cubic|quartic|quintic|sextic|degree[- ][1-8])\b",raw,re.I):
        label = match.group("degree").lower(); degree = names.get(label,int(label[-1]) if label.startswith("degree") else None)
        modifiers = match.group("modifiers").lower().split()
        matching = [item[0]["config"] for item in priors if item[0]["config"]["degree"] == degree]
        if "unregularized" in modifiers: matching = [item for item in matching if item["alpha"] == 0]
        elif "regularized" in modifiers: matching = [item for item in matching if item["alpha"] > 0]
        if not matching: raise ValueError("proposal's exact prior degree/penalty descriptor lacks actual same-fit proof")


def _historical_resource_span(raw: str) -> bool:
    if parse_temporal_resource_list(raw) is not None:
        return True
    resource = re.compile(r"\b(?:tokens?|usage|costs?|seconds?|provider|CPU|executions?|attempts?)\b|토큰|사용량|자원|실행|초", re.I)
    qualifier = re.compile(r"\b(?:historical(?:\s+pre.proposal)?\s+(?:cumulative\s+)?(?:resource|receipt|input|output|provider|CPU|token|usage|cost|wall)\w*|pre.proposal\s+(?:cumulative\s+)?(?:resource|receipt|input|output|provider|CPU|token|usage|cost|wall)\w*|prefix\s+(?:resource|receipt|input|output|provider|CPU|token|usage|cost|wall)\w*)\b|\bbefore\b.{0,30}\b(?:proposal|request)\b|(?:제안\s*전|당시).{0,25}(?:자원|CPU|토큰|사용량|실행|초)", re.I)
    found = False
    for sentence in _sentences(raw):
        for clause in _clauses(sentence):
            if not resource.search(clause):
                continue
            found = True; scope = qualifier.search(clause)
            if scope is None or _directly_negated(clause, scope):
                return False
    return found


def _check_nonresult_scope(raw: str, kind: str, *, prior_adjectives: bool = False, fixed_question: bool = False) -> None:
    """Recognized result assertions cannot vanish under an arbitrary type label.

    These conservative lexical guards supplement, not replace, human semantic
    judgement. Unrecognized assertions remain the reviewer's responsibility.
    """
    for sentence in _sentences(raw):
        assertions = list(_ASSERTED_RESULT.finditer(sentence)); broad = _BROAD_EFFECT.search(sentence)
        if kind == "method" and (assertions or broad or _REPRODUCTION.search(sentence)) and not _normative_method(sentence):
            raise ValueError("recognized result assertion cannot be excluded as method")
        if kind == "proposal":
            question = fixed_question and sentence.endswith("?") and bool(re.match(r"(?:Does|Do|Will|Would|Can|Could|How|What|Which|Whether|Is|Are)\b", sentence, re.I))
            if (assertions or broad or _RESULT_CUE.search(sentence)) and not (_TENTATIVE.search(sentence) or question):
                raise ValueError("every result-bearing proposal sentence must itself be tentative")
            if any(not _directly_negated(sentence, match) and not (prior_adjectives and _adjectival_prior(match, sentence)) for match in _PAST_RESULT.finditer(sentence)):
                raise ValueError("an asserted completed result cannot be excluded as a proposal")
        if kind == "limitation":
            for clause in _clauses(sentence):
                negative = _negative_generalization(clause)
                if any(not _directly_negated(clause, match) for match in _ASSERTED_RESULT.finditer(clause)) and not negative:
                    raise ValueError("affirmative result assertion cannot be excluded as a limitation")
                if _BROAD_EFFECT.search(clause) and not negative and not re.search(r"\b(?:unproven|unknown|unavailable|not demonstrated|not established|no evidence|cannot establish)\b|미입증|불확실|입증.{0,4}없", clause, re.I):
                    raise ValueError("limitation must locally restrict the same general/causal assertion")


def _nonresult_context(claim: dict, unit: dict, root: Path, *, component_fixture: bool = False) -> tuple[bool, bool]:
    context = claim.get("nonresult_context")
    if context is None:
        return False, False
    if claim.get("kind") != "proposal" or claim.get("text") != unit["decoded_text"]:
        raise ValueError("planning context must bind the complete original proposal unit")
    if context.get("kind") == "context_boundary":
        record = _context_boundary(context, root, component_fixture=component_fixture); field = context.get("field")
        if not isinstance(field, str): raise ValueError("planning context requires a fixed original field identity")
        if re.fullmatch(r"next_questions/\d+", field):
            index = int(field.split('/')[1]); questions = record.get("next_questions", [])
            if unit["unit_kind"] != "json_string" or unit.get("pointer") != '/'+field or index >= len(questions) or questions[index] != claim["text"]:
                raise ValueError("planning question differs from original source-bound context")
            return True, True
        entry = record.get("planning_units", {}).get(field)
        if not isinstance(entry, dict) or entry.get("text") != claim["text"] or entry.get("scope") not in {"preexecution_planning", "original_plan_visible_in_named_input"}:
            raise ValueError("planning unit has no exact original preexecution field binding")
        priors = [_actual_run(item, root) for item in context.get("prior_runs", [])]
        original_prior_ids = {Path(item["run_dir"]).resolve() for item in record.get("prior_runs", [])}
        if any(Path(item["run_dir"]).resolve() not in original_prior_ids for item in context.get("prior_runs", [])):
            raise ValueError("planning prior is missing or occurs after the bound original input")
        if priors and any(not _same_conditions(priors[0][0],item[0]) for item in priors): raise ValueError("planning priors have unmatched actual conditions")
        _check_prior_descriptors(claim["text"],priors)
        return bool(priors), False
    if context.get("kind") == "fixed_next_question":
        if unit["unit_kind"] != "json_string" or not re.fullmatch(r"/next_questions/\d+", unit.get("pointer") or ""):
            raise ValueError("fixed next-question context is not its original structured field")
        source = _checked_link(context["source"])
        if source not in {Path(__file__).with_name("comparison_arms.py").resolve(),Path(__file__).with_name("arms.py").resolve()}:
            raise ValueError("planning question source is not the executing frozen host")
        tree = ast.parse(source.read_text(encoding="utf-8")); questions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "next_questions" and isinstance(value, ast.List):
                        questions.extend(child.value for child in value.elts if isinstance(child, ast.Constant) and isinstance(child.value, str))
        if claim["text"] not in questions:
            raise ValueError("planning question differs from the frozen host question literal")
        return True, True
    if context.get("kind") == "registered_hypothesis":
        spec, _, _, _ = _actual_run(context["run"], root)
        if claim["text"] != spec.get("hypothesis"):
            raise ValueError("historical proposal text differs from its actual registered hypothesis")
        priors = [_actual_run(item, root) for item in context.get("prior_runs", [])]
        if not priors or any(not _same_conditions(spec, item[0]) for item in priors):
            raise ValueError("adjectival prior evidence must match actual task/split/model/resources")
        if spec.get("baseline", {}).get("run_id") not in {Path(item["run_dir"]).name for item in context["prior_runs"]}:
            raise ValueError("historical hypothesis requires its registered actual baseline evidence")
        _check_prior_descriptors(claim["text"],priors)
        degrees = {item[0]["config"]["degree"] for item in priors}
        for word, degree in (("linear",1),("quadratic",2),("cubic",3),("quartic",4),("quintic",5),("sextic",6)):
            if re.search(rf"\b(?:verified|measured)\s+(?:(?:unregularized|regularized|previous|registered|observed)\s+)*{word}\b", claim["text"], re.I) and degree not in degrees:
                raise ValueError("hypothesis's adjectival prior configuration lacks actual proof")
        for found in re.finditer(r"\b(?:verified|measured)\s+(?:(?:unregularized|regularized|previous|registered|observed)\s+)*degree[- ]([1-8])\s+(?:fit|model|baseline|candidate)\b",claim["text"],re.I):
            if int(found.group(1)) not in degrees: raise ValueError("hypothesis's numbered prior configuration lacks actual proof")
        if re.search(r"\b(?:verified|measured)\s+unregularized\b",claim["text"],re.I) and not any(item[0]["config"]["alpha"] == 0 for item in priors):
            raise ValueError("hypothesis's unregularized prior has no zero-penalty evidence")
        if context.get("boundary"):
            record = _context_boundary(context,root,component_fixture=component_fixture)
            _candidate_boundary_binding(spec,record)
            original_ids = {Path(item["run_dir"]).resolve() for item in record.get("prior_runs",[])}
            if any(Path(item["run_dir"]).resolve() not in original_ids for item in context["prior_runs"]):
                raise ValueError("hypothesis prior is missing/future relative to original proposal boundary")
        return True, False
    raise ValueError("unknown planning context cannot bypass result classification")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _link(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def _checked_link(item: dict, root: Path | None = None) -> Path:
    if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
        raise ValueError("semantic evidence must have exact path/hash fields")
    path = Path(item["path"]).resolve()
    if root is not None and not path.is_relative_to(root.resolve()):
        raise ValueError("semantic evidence escaped the arm directory")
    if not path.is_file() or sha256_file(path) != item["sha256"]:
        raise ValueError("semantic source hash changed")
    return path


def _json_strings(source: str, offset: int = 0) -> list[dict]:
    """Parse source offsets, so repeated/escaped strings are unambiguous."""
    json.loads(source)
    decoder = json.JSONDecoder(); pos = 0; items = []
    def space():
        nonlocal pos
        while pos < len(source) and source[pos].isspace(): pos += 1
    def value(pointer):
        nonlocal pos
        space(); start = pos; ch = source[pos]
        if ch == '{':
            pos += 1; space()
            if source[pos] == '}': pos += 1; return
            while True:
                space(); key_start = pos; key, end = decoder.raw_decode(source, pos); pos = end; space()
                child_pointer = pointer + '/' + str(key).replace('~', '~0').replace('/', '~1')
                items.append({"unit_kind": "json_key", "pointer": child_pointer,
                    "start": offset+key_start, "end": offset+end, "text": source[key_start:end], "decoded_text": key})
                if source[pos] != ':': raise ValueError("invalid JSON object")
                pos += 1; value(child_pointer); space()
                if source[pos] == '}': pos += 1; return
                pos += 1
        elif ch == '[':
            pos += 1; space(); index = 0
            if source[pos] == ']': pos += 1; return
            while True:
                value(pointer + '/' + str(index)); index += 1; space()
                if source[pos] == ']': pos += 1; return
                pos += 1
        else:
            decoded, end = decoder.raw_decode(source, pos); pos = end
            if isinstance(decoded, str):
                items.append({"unit_kind": "json_string", "pointer": pointer,
                    "start": offset + start, "end": offset + end, "text": source[start:end], "decoded_text": decoded})
            else:
                items.append({"unit_kind": "json_scalar", "pointer": pointer,
                    "start": offset+start, "end": offset+end, "text": source[start:end], "decoded_text": source[start:end]})
    value(""); space()
    if pos != len(source): raise ValueError("unparsed JSON suffix")
    return items


def semantic_units(text: str, report_sha256: str) -> list[dict]:
    """All nonempty textual paragraphs, and every JSON *value* string leaf.

    JSON keys and scalar values are also inventoried; a qualitative assertion
    encoded as an object key and a boolean cannot escape semantic review.
    An explicit structural unit prevents a pure numeric JSON document from being
    mistaken for an empty report. Fenced JSON is parsed as JSON rather than prose.
    """
    blocks = []
    try:
        json.loads(text)
    except (ValueError, TypeError):
        cursor = 0
        for match in re.finditer(r"(?m)^```json[^\n]*\n([\s\S]*?)^```[ \t]*$", text):
            blocks.append((cursor, match.start(), False)); blocks.append((match.start(1), match.end(1), True)); cursor = match.end()
        blocks.append((cursor, len(text), False))
    else:
        blocks = [(0, len(text), True)]
    units = []
    for start, end, is_json in blocks:
        body = text[start:end]
        if is_json:
            units.extend(_json_strings(body, start))
            units.append({"unit_kind": "json_structure", "pointer": "", "start": start,
                "end": end, "text": body, "decoded_text": "JSON structural punctuation; keys, strings and scalar values are separate units"})
        else:
            for match in re.finditer(r"\S[\s\S]*?(?=\n[ \t]*\n|\Z)", body):
                raw = match.group(); right = len(raw.rstrip()); raw = raw[:right]
                if raw:
                    units.append({"unit_kind": "paragraph", "pointer": None, "start": start+match.start(),
                        "end": start+match.start()+right, "text": raw, "decoded_text": raw})
    for unit in units:
        unit["unit_id"] = value_hash({"report_sha256": report_sha256, **unit})
    return sorted(units, key=lambda u: (u["start"], u["end"], u["unit_kind"]))


def prepare_semantic_review(report_path: Path, output_path: Path) -> dict:
    report_path, output_path = Path(report_path).resolve(), Path(output_path).resolve()
    record = {"schema_version": SEMANTIC_SCHEMA_VERSION, "report": _link(report_path),
        "predicate_source": _link(Path(__file__)),
        "units": semantic_units(report_path.read_text(encoding="utf-8"), sha256_file(report_path)),
        "scope": SEMANTIC_POLICY["scope"]}
    if not record["units"]: raise ValueError("an empty report cannot have complete semantic coverage")
    if output_path.exists():
        if _load(output_path) != record: raise ValueError("immutable semantic inventory differs")
    else: write_json(output_path, record)
    return record


def _actual_run(link: dict, root: Path, *, require_success: bool = True) -> tuple[dict, dict, dict, list[dict]]:
    directory = Path(link["run_dir"]).resolve()
    if not directory.is_relative_to(root.resolve()): raise ValueError("semantic run is outside the arm directory")
    sources = [_link(directory / name) for name in ("registered_spec.json", "result.json")]
    if link.get("sources") != sources: raise ValueError("semantic original run source hashes differ")
    spec, result = (_load(directory / name) for name in ("registered_spec.json", "result.json"))
    checked = verify(spec, result, directory)
    if result.get("execution_kind") != "actual_cpu_execution" or (require_success and result.get("status") != "success") or checked.get("valid") is not True:
        raise ValueError("semantic predicate requires independently verified actual CPU evidence")
    return spec, result, checked, sources


def run_reference(run_dir: Path) -> dict:
    directory = Path(run_dir).resolve()
    return {"run_dir": str(directory), "sources": [_link(directory / name) for name in ("registered_spec.json", "result.json")]}


def _same_conditions(a: dict, b: dict) -> bool:
    keys = ("task_id", "task_version", "seed", "model", "implementation_sha256", "evaluator_sha256",
            "source_sha256", "split_manifest_sha256", "data_sha256", "public_bundle_sha256", "resource_envelope",
            "command", "execution_entrypoint", "metric", "tool_contract_sha256")
    return all(a.get(key) == b.get(key) for key in keys)


def _evaluate_predicate_impl(claim: dict, arm_output: Path, *, component_fixture: bool = False) -> dict:
    """Recompute fixed, narrow predicates; never infer a framework effect from a fit."""
    predicate = claim.get("predicate_id"); args = claim.get("arguments", {})
    if not isinstance(args, dict): raise ValueError("semantic predicate arguments must be an object")
    if predicate == "historical_context_resources":
        if claim.get("kind") not in {"measured_result", "execution_provenance"} or args.get("scope") != "historical_pre_request":
            raise ValueError("common historical resources need measured provenance and original pre-request scope")
        parsed = parse_temporal_resource_list(claim.get("text", ""))
        if parsed is None: raise ValueError("historical resource claim is outside the fixed temporal resource-list grammar")
        record = _context_boundary(args, arm_output, component_fixture=component_fixture)
        if record.get("scope") != "historical_pre_request": raise ValueError("boundary has no original historical prefix scope")
        counts = {"actual_cpu_executions", "distinct_configurations", "completed_provider_calls", "failed_provider_attempts", "input_tokens", "output_tokens"}
        for key, displayed in parsed["quantities"].items():
            actual = record["measures"].get(key)
            if actual is None: raise ValueError("historical resource is unknown; missing failed usage must not become zero")
            if key in counts:
                if type(actual) is not int or displayed["value"] != actual: raise ValueError("historical displayed integer differs from original prefix")
            else:
                token = Decimal(displayed["display"]); tolerance = float(Decimal(5).scaleb(token.as_tuple().exponent-1))
                if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual) or not math.isclose(displayed["value"], actual, rel_tol=0, abs_tol=tolerance+1e-12):
                    raise ValueError("historical displayed time differs from original prefix/rounding")
        key = args.get("measure"); actual = record["measures"].get(key)
        if key not in parsed["quantities"] or actual is None or type(args.get("value")) not in {int, float} or args["value"] != actual:
            raise ValueError("historical declared scalar is unknown or differs from the explicit source-bound list")
        return {"predicate_id":predicate,"facts":{"quantities":parsed["quantities"],"measure":key,"value":actual,
            "scope":"Original before-request receipt prefix only; not final totals, future costs, monetary price or information gain",
            "fixture_only":bool(record.get("fixture_only",False))},"evidence":record["evidence"]}
    if predicate == "report_input_availability":
        if args.get("scope") != "named_original_input" or claim.get("kind") != "execution_provenance":
            raise ValueError("availability supports original named-input provenance only, not measured performance or global absence")
        raw = claim.get("text", "").strip()
        match = re.fullmatch(r"The named original reporting input contains (train|validation) MSE values for (\d+) verified (runs?|configurations?)\.", raw)
        if match is None: raise ValueError("availability must explicitly name the original reporting input and bounded metric universe")
        metric = match.group(1)+"_mse"; count_kind = "configurations" if match.group(3).startswith("configuration") else "runs"
        if args.get("metric") != metric or args.get("count_kind","runs") != count_kind or type(args.get("count")) is not int or args["count"] != int(match.group(2)):
            raise ValueError("availability declared metric/count does not match its source span")
        record = _context_boundary(args, arm_output, component_fixture=component_fixture); available = []
        for row in record.get("available_metrics", []):
            if row.get("metric") != metric: continue
            spec, _, checked, sources = _actual_run(row["run"], arm_output)
            if row.get("value") != checked["metrics"][metric]: raise ValueError("available input metric differs from its actual run")
            available.append((row["run"]["run_dir"], value_hash(spec["config"])))
        actual = len({row[0 if count_kind == "runs" else 1] for row in available})
        if actual != args["count"]: raise ValueError("availability count differs from exact original input values; paths are not values")
        return {"predicate_id":predicate,"facts":{"metric":metric,"count":actual,"count_kind":count_kind,"scope":"Exact named original input only; not whole agent history, experiment absence, paper reading or comprehension", "fixture_only":bool(record.get("fixture_only",False))},"evidence":record["evidence"]}
    if predicate == "derived_metric_arithmetic":
        if claim.get("kind") != "measured_result" or args.get("unit") != "mse": raise ValueError("derived arithmetic is a same-run measured MSE difference only")
        operations = {"validation_minus_training":("validation_mse","train_mse"), "training_minus_validation":("train_mse","validation_mse")}
        if args.get("operation") not in operations: raise ValueError("unsupported arithmetic operation; ratios and zero-denominator changes are not whitelisted")
        left, right = operations[args["operation"]]
        if (args.get("left_metric"),args.get("right_metric")) != (left,right): raise ValueError("derived metric identity/split/direction differs from its fixed operation")
        first = "validation" if left == "validation_mse" else "training"; second = "training" if right == "train_mse" else "validation"
        number = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
        match = re.fullmatch(rf"For the named verified run, {first} MSE minus {second} MSE is ({number}) MSE\.", claim.get("text", "").strip())
        if match is None: raise ValueError("derived arithmetic span does not match the whitelisted same-run split expression")
        places = -Decimal(match.group(1)).as_tuple().exponent
        if type(args.get("decimal_places")) is not int or not 0 <= args["decimal_places"] <= 18 or args["decimal_places"] != places:
            raise ValueError("derived displayed rounding was omitted or differs from exact source formatting")
        _, _, checked, sources = _actual_run(args["run"], arm_output)
        operands = [checked["metrics"][left],checked["metrics"][right]]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in operands): raise ValueError("derived operands must be finite measured metrics")
        actual = operands[0]-operands[1]; value=args.get("value")
        if type(value) not in {int,float} or not math.isfinite(value) or value != float(match.group(1)) or not math.isclose(value,actual,rel_tol=0,abs_tol=.5*10**-places+1e-12):
            raise ValueError("derived displayed difference does not match measured operands/rounding")
        return {"predicate_id":predicate,"facts":{"operation":args["operation"],"left_metric":left,"right_metric":right,"left_value":operands[0],"right_value":operands[1],"derived_value":actual,"displayed_value":value,"decimal_places":places,"unit":"mse","scope":"One actual run's descriptive arithmetic; no additional experiment, cause, significance or out-of-sample superiority"},"evidence":sources}
    if predicate == "source_fact_attribution":
        if claim.get("kind") != "literature": raise ValueError("source fact attribution is external synopsis context, not locally measured result")
        registry, registry_path, corpus = _fact_registry()
        if _checked_link(args["source"]) != corpus or args.get("registry_sha256") != FACT_REGISTRY_SHA256:
            raise ValueError("fact source/registry is not the executing original fixed synopsis registry")
        facts = [row for row in registry["facts"] if row["fact_id"] == args.get("fact_id")]
        if len(facts) != 1: raise ValueError("unknown fixed source fact")
        fact = facts[0]; forms = [row for row in fact["allowed_forms"] if row["form_id"] == args.get("form_id")]
        if len(forms) != 1 or claim.get("text", "").strip() != forms[0]["text"] or args.get("url") != fact["url"]:
            raise ValueError("source-fact form/conditions/polarity/citation differs; arbitrary paraphrase remains pending")
        return {"predicate_id":predicate,"facts":{"fact_id":fact["fact_id"],"source_id":fact["source_id"],"subject":fact["subject"],"conditions":fact["conditions"],"polarity":fact["polarity"],"form_id":forms[0]["form_id"],"scope":"Finite registered synopsis attribution only; not full-paper truth/reading/comprehension or a locally measured effect"},"evidence":[_link(registry_path),_link(corpus)]}
    if predicate in {"final_framework_effect", "causal_memory_effect", "model_replacement_effect", "independent_reproduction"}:
        raise ValueError("this source version has no registered independent final/causal/replay proof adapter; claim remains pending or unsupported")
    if predicate in {"verified_execution", "train_only_disjoint_split", "registered_configuration", "registered_criterion"}:
        spec, result, checked, sources = _actual_run(args["run"], arm_output)
        if predicate == "registered_configuration":
            if args.get("config") != spec["config"]: raise ValueError("semantic claimed configuration differs from registration")
            facts = {"config": spec["config"]}
        elif predicate == "registered_criterion":
            criterion = spec.get("criterion", {}); metric = spec.get("metric")
            if criterion.get("threshold") is None or criterion.get("baseline_value") is not None:
                raise ValueError("semantic criterion adapter supports fixed absolute thresholds only")
            actual = checked["metrics"][metric]; direction = criterion["direction"]
            threshold = criterion["threshold"]
            if direction not in {"min", "max"} or isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
                raise ValueError("semantic criterion must have a finite fixed threshold and explicit direction")
            success = actual <= criterion["threshold"] if direction == "min" else actual >= criterion["threshold"]
            if args.get("success") is not success: raise ValueError("semantic registered success claim contradicts actual metric")
            facts = {"criterion": criterion, "metric": metric, "value": actual, "success": success}
        else:
            facts = {"execution_kind": result["execution_kind"], "valid": True,
                "task_id": spec["task_id"], "seed": spec["seed"], "split_manifest_sha256": spec["split_manifest_sha256"],
                "scope": "one registered train/validation experiment; train-only fit and disjoint splits checked by fixed verifier"}
        return {"predicate_id": predicate, "facts": facts, "evidence": sources}
    if predicate == "observed_validation_comparison":
        a, _, av, ae = _actual_run(args["left"], arm_output); b, _, bv, be = _actual_run(args["right"], arm_output)
        if not _same_conditions(a, b): raise ValueError("semantic comparison conditions do not match")
        metric = "validation_mse"; left, right = av["metrics"][metric], bv["metrics"][metric]
        operation = args.get("relation"); valid = {"lt": left < right, "le": left <= right, "gt": left > right, "eq": left == right}.get(operation)
        if valid is not True: raise ValueError("semantic observed comparison contradicts actual metrics")
        return {"predicate_id": predicate, "facts": {"metric": metric, "left": left, "right": right, "relation": operation,
            "scope": "observed validation metrics on one matched split; not unseen-task generalization or independent stochastic replication"}, "evidence": ae+be}
    if predicate in {"observed_minimum", "observed_inventory_counts"}:
        provided = args.get("runs", []); folders = [Path(item["run_dir"]).resolve() for item in provided]
        discovered = set()
        for path in arm_output.rglob("registered_spec.json"):
            result_path = path.parent / "result.json"
            if not result_path.exists(): raise ValueError("semantic whole-history inventory has an unresolved execution")
            if _load(result_path).get("execution_kind") == "actual_cpu_execution": discovered.add(path.parent.resolve())
        if not folders or len(set(folders)) != len(folders) or set(folders) != discovered:
            raise ValueError("semantic whole-history inventory omits, duplicates or invents an actual execution")
        records = [_actual_run(item, arm_output, require_success=False) for item in provided]
        reference = records[0][0]
        if any(not _same_conditions(reference, row[0]) for row in records):
            raise ValueError("semantic whole-history runs have different task/seed/model/split/resources")
        sources = [item for row in records for item in row[3]]
        configs = {value_hash(row[0]["config"]) for row in records}
        counts = {"actual_executions": len(records), "distinct_configurations": len(configs),
                  "repeated_configurations": len(records)-len(configs)}
        if predicate == "observed_inventory_counts":
            if args.get("counts") != counts: raise ValueError("semantic execution/configuration counts contradict the full history")
            return {"predicate_id": predicate, "facts": {**counts,
                "scope": "actual deterministic execution receipts on one task/seed; repeated configurations are not independent stochastic replications"}, "evidence": sources}
        selected, _, selected_verification, selected_sources = _actual_run(args["selected"], arm_output)
        if Path(args["selected"]["run_dir"]).resolve() not in discovered or not _same_conditions(reference, selected):
            raise ValueError("semantic selected minimum is absent from the complete matched history")
        successful = [row for row in records if row[1]["status"] == "success"]
        minimum = min(row[2]["metrics"]["validation_mse"] for row in successful)
        if selected_verification["metrics"]["validation_mse"] != minimum:
            raise ValueError("semantic selected candidate is not the minimum observed validation error")
        return {"predicate_id": predicate, "facts": {**counts, "successful_executions": len(successful),
            "validation_mse": minimum, "selected_config": selected["config"],
            "scope": "minimum among all observed verified candidates on this fixed validation split; not global optimum or test/population superiority"}, "evidence": sources+selected_sources}
    if predicate == "resource_accounting":
        from .evaluation import recompute_resource_audit
        path = _checked_link(args["resource_audit"], arm_output); record = recompute_resource_audit(path)
        key = args.get("measure"); actual = record["measures"].get(key)
        if actual is None or args.get("value") != actual: raise ValueError("semantic resource claim is unknown or differs from raw receipt accounting")
        return {"predicate_id": predicate, "facts": {"measure": key, "value": actual,
            "scope": "research-provider inference / trusted CPU receipts only; engineering and independent reviewer cost excluded"}, "evidence": [_link(path)]}
    if predicate == "historical_pre_proposal_resources":
        if claim.get("kind") not in {"measured_result", "execution_provenance"}:
            raise ValueError("historical resource receipts cannot turn a forecast or inference into measurement")
        raw = claim.get("text", "")
        if not _historical_resource_span(raw):
            raise ValueError("the exact resource claim span must explicitly restrict itself to historical pre-proposal scope")
        if re.search(r"\b(?:final|entire|overall|whole.unit|all.requests|end.of.unit|forecast|expected|next|will\s+(?:cost|consume))\b|최종|예상|다음", raw, re.I):
            raise ValueError("historical pre-proposal resources cannot support a final total or future forecast")
        record = recompute_historical_resources(args, arm_output)
        parsed = parse_temporal_resource_list(raw)
        if parsed is not None:
            for measure, displayed in parsed["quantities"].items():
                observed = record["measures"].get(measure)
                places = Decimal(displayed["display"]).as_tuple().exponent
                tolerance = float(Decimal(5).scaleb(places-1)) if measure.endswith("seconds") else 0
                if type(observed) not in {int,float} or not math.isfinite(observed) or not math.isclose(displayed["value"], observed, rel_tol=0, abs_tol=tolerance+1e-12):
                    raise ValueError("every displayed historical list quantity must match the original prefix")
        key = args.get("measure"); actual = record["measures"].get(key); value = args.get("value")
        matches = value == actual if isinstance(actual, int) else isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and actual is not None and math.isclose(value, actual, rel_tol=1e-9, abs_tol=1e-9)
        if actual is None or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not matches:
            raise ValueError("historical resource value is unknown or differs from the exact original prefix")
        return {"predicate_id": predicate, "facts": {"measure": key, "value": actual,
            "proposal_call_id": record["proposal_call_id"], "prefix_call_ids": record["prefix_call_ids"],
            "tokens_known": record["tokens_known"], "scope": record["scope"],
            "evidence_class":"engineering_legacy", "adoption_eligible":False}, "evidence": record["evidence"]}
    if predicate == "attributed_literature":
        path = _checked_link(args["source"]); excerpt = args.get("excerpt"); url = args.get("url")
        source_text = path.read_text(encoding="utf-8")
        if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in source_text or not isinstance(url, str) or not url.startswith("https://") or url not in source_text:
            raise ValueError("semantic literature attribution needs pinned original excerpt and citation")
        if isinstance(claim.get("text"), str) and claim["text"].strip() != excerpt.strip():
            raise ValueError("a source excerpt cannot support unrelated additional report assertions")
        _, _, corpus = _fact_registry()
        actual = path == corpus and claim.get("kind") == "literature"
        if actual:
            records = [record for record in _load(corpus)["records"] if record["id"] == args.get("source_id")]
            if len(records) != 1 or records[0]["url"] != url or excerpt not in records[0]["text"]:
                raise ValueError("direct quote has no exact fixed synopsis source ID/excerpt/URL binding")
        return {"predicate_id": predicate, "facts": {"url": url, "excerpt": excerpt,
            "scope": "attributed source statement; not a locally measured finding",
            "evidence_class":"actual" if actual else "engineering_legacy", "adoption_eligible":actual}, "evidence": [_link(path)]}
    if predicate == "conditional_inference":
        _, _, _, sources = _actual_run(args["run"], arm_output)
        if claim.get("kind") != "inference" or not _TENTATIVE.search(claim["text"]) or _BROAD_EFFECT.search(claim["text"]):
            raise ValueError("conditional inference must be visibly tentative and cannot establish general framework or causal effect")
        _check_nonresult_scope(claim["text"], "proposal")
        if not isinstance(args.get("conditions"), str) or not args["conditions"].strip():
            raise ValueError("conditional inference requires explicit applicability conditions")
        return {"predicate_id": predicate, "facts": {"conditions": args["conditions"], "scope": "reviewer interpretation, not measured expected improvement"}, "evidence": sources}
    raise ValueError("unknown semantic predicate; cannot accept self-defined evaluation code")


def evaluate_predicate(claim: dict, arm_output: Path) -> dict:
    """Actual-only public API; a claim or keyword cannot activate fixture mode."""
    proof = _evaluate_predicate_impl(claim,arm_output,component_fixture=False)
    synthetic = False
    for source in proof.get("evidence", []):
        if not isinstance(source,dict) or not {"path","sha256"}.issubset(source) or set(source)-{"path","sha256","call_id"}:
            raise ValueError("predicate evidence has no recognized original source link")
        path = _checked_link({key:source[key] for key in ("path","sha256")})
        if path.suffix.lower() != ".json": continue
        original = _load(path)
        if isinstance(original,dict):
            if _explicit_nonactual_provenance(original):
                synthetic = True
    if synthetic:
        proof["facts"] = {**proof["facts"], "evidence_class":"synthetic_fixture", "adoption_eligible":False,
            "contains_synthetic_original_evidence":True}
    return proof


def evaluate_fixture_predicate(claim: dict, arm_output: Path) -> dict:
    """Explicit engineering check; never a production semantic support proof.

    The original audit still validates every source, receipt, scope and quantity.
    No fixture flag from a model claim, global switch or CLI activates this mode.
    Production review recomputes with evaluate_predicate's actual-only default.
    """
    if claim.get("predicate_id") not in {"historical_context_resources", "report_input_availability", "derived_metric_arithmetic", "source_fact_attribution"}:
        raise ValueError("component fixture API allows the registered common finite predicates only")
    proof = _evaluate_predicate_impl(claim, arm_output, component_fixture=True)
    proof["facts"] = {**proof["facts"], "evidence_class":"synthetic_fixture", "evaluation_scope":"synthetic_engineering_fixture", "adoption_eligible":False}
    return proof


def evaluate_fixture_nonresult_context(claim: dict, unit: dict, arm_output: Path) -> dict:
    """Check original planning scope on audited fixtures, without approving reports."""
    if claim.get("kind") != "proposal" or claim.get("outcome") != "classified_nonresult":
        raise ValueError("planning fixture requires explicit prospective non-result classification")
    prior, question = _nonresult_context(claim, unit, arm_output, component_fixture=True)
    if not (_TENTATIVE.search(claim["text"]) or question): raise ValueError("fixture proposal must be visibly prospective")
    _check_nonresult_scope(claim["text"], "proposal", prior_adjectives=prior, fixed_question=question)
    return {"prior_adjectives":prior,"fixed_question":question,"evidence_class":"synthetic_fixture", "evaluation_scope":"synthetic_engineering_fixture", "adoption_eligible":False}


def _review_claim(claim: dict, unit: dict, arm_output: Path) -> dict:
    if not isinstance(claim, dict): raise ValueError("semantic claim must be an object")
    text = unit["decoded_text"]; start, end = claim.get("start"), claim.get("end")
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(text):
        raise ValueError("semantic claim span is invalid")
    raw = text[start:end]
    if claim.get("text") != raw or claim.get("claim_id") != value_hash({"unit_id": unit["unit_id"], "start": start, "end": end, "text": raw}):
        raise ValueError("semantic claim is not bound to the exact original source span")
    if not isinstance(claim.get("rationale"), str) or not claim["rationale"].strip(): raise ValueError("semantic reviewer rationale missing")
    outcome, kind = claim.get("outcome"), claim.get("kind")
    if outcome not in {"supported", "classified_nonresult", "unsupported", "pending"}: raise ValueError("semantic outcome is invalid")
    if kind not in {"measured_result", "execution_provenance", "literature", "inference", "proposal", "method", "limitation", "general_result"}: raise ValueError("semantic claim kind is invalid")
    if outcome == "supported":
        predicate = claim.get("predicate_id")
        if kind in {"method", "proposal", "limitation"}: raise ValueError("non-result interpretation cannot be relabelled supported measurement")
        if _BROAD_EFFECT.search(raw) and kind not in {"literature"} and predicate not in {"final_framework_effect", "causal_memory_effect", "model_replacement_effect"}:
            raise ValueError("general or causal result exceeds a local experiment predicate")
        if kind == "literature" and predicate not in {"attributed_literature","source_fact_attribution"}: raise ValueError("literature must be attributed, not accepted as local measurement")
        if predicate in {"attributed_literature","source_fact_attribution"} and kind != "literature":
            raise ValueError("source attribution cannot establish a local execution or measured result")
        if predicate in {"attributed_literature","source_fact_attribution"} and re.search(r"\b(?:we|our\s+(?:agent|framework)|the\s+(?:research\s+)?agent)\b.{0,80}\b(?:read|understood|comprehend\w*)\b|에이전트.{0,50}(?:이해|읽었)", raw, re.I):
            raise ValueError("corpus attribution has no registered local reading/comprehension proof adapter")
        if kind == "inference" and predicate != "conditional_inference": raise ValueError("inference requires tentative conditional interpretation")
        if kind != "literature" and _REPRODUCTION.search(raw) and predicate != "independent_reproduction":
            raise ValueError("actual reproduction requires independent replay proof, not one successful execution")
        if kind != "literature" and _MINIMUM.search(raw) and predicate != "observed_minimum":
            raise ValueError("observed best claim requires the complete actual candidate history, not a pair comparison")
        if kind != "literature" and _INDEPENDENT_REPEATS.search(raw) and predicate != "independent_reproduction":
            raise ValueError("deterministic repeated configurations do not establish independent stochastic replications")
        if kind != "literature" and _COMPARISON.search(raw) and predicate not in {"observed_validation_comparison", "observed_minimum", "conditional_inference", "attributed_literature"}:
            raise ValueError("comparative result requires an actual matched comparison, not an execution-success predicate")
        proof = evaluate_predicate(claim, arm_output)
        if claim.get("predicate_result") != proof: raise ValueError("semantic predicate result differs from independent recomputation")
    elif outcome == "classified_nonresult":
        if kind not in {"method", "proposal", "limitation"}: raise ValueError("result assertion cannot be excluded as non-result")
        prior, question = _nonresult_context(claim, unit, arm_output)
        if kind == "proposal" and not (_TENTATIVE.search(raw) or question): raise ValueError("proposal must be visibly prospective/tentative")
        _check_nonresult_scope(raw, kind, prior_adjectives=prior, fixed_question=question)
        if "predicate_result" in claim: raise ValueError("non-result claim contains a measurement proof")
    return claim


def _explicit_nonactual_provenance(original: dict) -> bool:
    """Known explicit markers, without inferring real execution from absence."""
    flags=("fixture_only","simulation_only","test_fixture_only")
    if any(key in original and type(original[key]) is not bool for key in flags):
        raise ValueError("original source has malformed fixture provenance metadata")
    return (any(original.get(key) is True for key in flags)
        or original.get("execution_kind") in {"simulation","simulation_fixture","synthetic_fixture"})


def _arm_provenance_sources(root: Path) -> list[dict]:
    """Original arm-wide markers apply even to entirely prospective reports.

    These markers do not establish real provider execution when absent. The
    owner scorer must independently audit the full actual resource inventory.
    This reader checks only known host/CPU/provider metadata namespaces, never
    owner test data or an arbitrary report-supplied file path.
    """
    root=Path(root).resolve(); paths=set()
    for name in ("callback-registration.json","arm-response.json"):
        path=root/name
        if path.exists(): paths.add(path)
    for parent in (root/"research",root/"attempts",root/"model"):
        if parent.exists():
            paths.update(parent.rglob("registered_spec.json")); paths.update(parent.rglob("result.json"))
    sources=[]
    for path in sorted(paths):
        checked=_checked_link(_link(path),root); original=_load(checked)
        if not isinstance(original,dict): raise ValueError("original arm provenance metadata must be an object")
        if _explicit_nonactual_provenance(original):
            sources.append(_link(path))
    return sources


def _evidence_qualification(rows: list[dict], arm_output: Path) -> str:
    """Qualification is recomputed, never accepted from reviewer complete flags."""
    classes = {"component_fixture"} if _arm_provenance_sources(arm_output) else set()
    for row in rows:
        if row.get("outcome") == "pending": classes.add("unqualified")
        for claim in row.get("claims", []):
            if claim.get("outcome") == "pending": classes.add("unqualified")
            if claim.get("outcome") == "supported":
                facts = claim.get("predicate_result", {}).get("facts", {})
                value = facts.get("evidence_class", "actual")
                if value in {"synthetic_fixture", "component_fixture"} or facts.get("fixture_only") is True:
                    classes.add("component_fixture")
                elif value == "engineering_legacy": classes.add(value)
                elif value != "actual" or facts.get("adoption_eligible") is False: classes.add("unqualified")
            context = claim.get("nonresult_context", {})
            if claim.get("outcome") == "classified_nonresult" and context.get("kind") == "registered_hypothesis" and not context.get("boundary"):
                classes.add("engineering_legacy")
    for value in ("component_fixture", "engineering_legacy", "unqualified"):
        if value in classes: return value
    return "actual"


def validate_semantic_review(review_path: Path, *, arm_output: Path, require_complete: bool = True) -> dict:
    review_path = Path(review_path).resolve(); arm_output = Path(arm_output).resolve()
    if not review_path.is_relative_to(arm_output): raise ValueError("semantic review escaped the arm directory")
    review = _load(review_path)
    if review.get("schema_version") != SEMANTIC_SCHEMA_VERSION or review.get("reviewer_role") != "independent_verifier":
        raise ValueError("independent semantic reviewer/schema required")
    predicate = _checked_link(review["predicate_source"])
    if sha256_file(predicate) != sha256_file(Path(__file__)):
        raise ValueError("semantic predicate source is not the executing frozen evaluator")
    inventory_path = _checked_link(review["inventory"], arm_output); inventory = _load(inventory_path)
    report_path = _checked_link(inventory["report"], arm_output)
    expected = semantic_units(report_path.read_text(encoding="utf-8"), sha256_file(report_path))
    if inventory.get("schema_version") != SEMANTIC_SCHEMA_VERSION or inventory.get("predicate_source") != review["predicate_source"] or inventory.get("units") != expected or not expected:
        raise ValueError("semantic inventory does not reconstruct the entire original report")
    rows = review.get("units", []); ids = [row.get("unit_id") for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != {unit["unit_id"] for unit in expected}:
        raise ValueError("semantic paragraph/string coverage omitted, duplicated or invented a unit")
    unit_map = {unit["unit_id"]: unit for unit in expected}; pending = unsupported = 0; claim_ids = set()
    for row in rows:
        unit = unit_map[row["unit_id"]]
        if row.get("exhaustive_result_claim_mapping") is not True or not isinstance(row.get("rationale"), str) or not row["rationale"].strip():
            raise ValueError("reviewer must attest exhaustive meaning/condition mapping per unit")
        outcome = row.get("outcome"); claims = row.get("claims", [])
        if outcome not in {"reviewed", "pending"}: raise ValueError("semantic unit status invalid")
        if outcome == "pending": pending += 1
        if not isinstance(claims, list): raise ValueError("semantic claims must be a list")
        if not claims and outcome != "pending" and unit["unit_kind"] != "json_structure" and (
                _RESULT_CUE.search(unit["decoded_text"]) or _ASSERTED_RESULT.search(unit["decoded_text"]) or _COMPARISON.search(unit["decoded_text"])):
            raise ValueError("result-bearing text cannot pass solely as an unexamined non-result unit")
        for claim in claims:
            _review_claim(claim, unit, arm_output)
            if claim["claim_id"] in claim_ids: raise ValueError("duplicate semantic claim span")
            claim_ids.add(claim["claim_id"])
            pending += claim["outcome"] == "pending"; unsupported += claim["outcome"] == "unsupported"
        if claims:
            spans = sorted((claim["start"], claim["end"]) for claim in claims)
            if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
                raise ValueError("semantic assertion spans overlap")
            covered = {index for start, end in spans for index in range(start, end)}
            if any(not char.isspace() and index not in covered for index, char in enumerate(unit["decoded_text"])):
                raise ValueError("semantic claim spans omit non-whitespace original content")
    for key, actual in (("pending_items", pending), ("unsupported_semantic_result_claims", unsupported)):
        if type(review.get(key)) is not int or review[key] != actual: raise ValueError("semantic counters differ from reconstructed judgments")
    complete = pending == 0
    if review.get("status") != ("complete" if complete else "pending"): raise ValueError("semantic complete flag contradicts actual review coverage")
    qualification = _evidence_qualification(rows,arm_output)
    if review.get("semantic_evidence_qualification") != qualification: raise ValueError("semantic evidence qualification differs from reconstructed original proofs/context")
    nonactual_sources = _arm_provenance_sources(arm_output)
    if review.get("nonactual_original_provenance") != nonactual_sources: raise ValueError("arm-wide original nonactual provenance differs from the saved review")
    actual_complete = complete and qualification == "actual"
    if require_complete and not actual_complete: raise ValueError("independent semantic review is pending or lacks actual eligible evidence")
    return {"semantic_report_audit_complete": actual_complete, "review_coverage_complete":complete,
        "semantic_evidence_qualification":qualification, "nonactual_original_provenance":nonactual_sources, "unsupported_semantic_result_claims": unsupported,
        "pending_items": pending, "units": len(expected), "claims": len(claim_ids), "report": inventory["report"],
        "review": _link(review_path), "inventory": review["inventory"], "predicate_source": review["predicate_source"],
        "review_wall_seconds": None, "review_usage": None, "limits": SEMANTIC_POLICY["limits"]}


def semantic_claim(unit: dict, *, kind: str, outcome: str, rationale: str, predicate_id: str | None = None,
                   arguments: dict | None = None, start: int = 0, end: int | None = None,
                   nonresult_context: dict | None = None) -> dict:
    end = len(unit["decoded_text"]) if end is None else end; text = unit["decoded_text"][start:end]
    claim = {"claim_id": value_hash({"unit_id": unit["unit_id"], "start": start, "end": end, "text": text}),
        "start": start, "end": end, "text": text, "kind": kind, "outcome": outcome, "rationale": rationale}
    if predicate_id is not None: claim.update(predicate_id=predicate_id, arguments=arguments or {})
    if nonresult_context is not None: claim["nonresult_context"] = nonresult_context
    return claim


def adjudicate_semantic_review(inventory_path: Path, judgments: list[dict], output_path: Path, *,
                              arm_output: Path, reviewer_role: str) -> dict:
    if reviewer_role != "independent_verifier": raise ValueError("only an independent owner reviewer can adjudicate semantic claims")
    inventory_path, output_path = Path(inventory_path).resolve(), Path(output_path).resolve()
    rows = json.loads(json.dumps(judgments)); pending = unsupported = 0
    for row in rows:
        pending += row.get("outcome") == "pending"
        for claim in row.get("claims", []):
            pending += claim.get("outcome") == "pending"; unsupported += claim.get("outcome") == "unsupported"
            if claim.get("outcome") == "supported": claim["predicate_result"] = evaluate_predicate(claim, Path(arm_output))
    record = {"schema_version": SEMANTIC_SCHEMA_VERSION, "reviewer_role": reviewer_role,
        "inventory": _link(inventory_path), "predicate_source": _link(Path(__file__)), "units": rows,
        "pending_items": pending, "unsupported_semantic_result_claims": unsupported,
        "status": "pending" if pending else "complete", "review_wall_seconds": None, "review_usage": None,
        "responsibility": SEMANTIC_POLICY["limits"]}
    record["semantic_evidence_qualification"] = _evidence_qualification(rows,Path(arm_output))
    record["nonactual_original_provenance"] = _arm_provenance_sources(Path(arm_output))
    # Validate a temporary new file before atomically preserving the final review.
    if output_path.exists():
        if _load(output_path) != record: raise ValueError("immutable semantic review differs; write a versioned sidecar")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        probe = output_path.with_name(output_path.name + ".candidate")
        if probe.exists(): raise FileExistsError("prior semantic candidate requires reconciliation")
        write_json(probe, record)
        try: validate_semantic_review(probe, arm_output=arm_output, require_complete=False)
        except Exception:
            # Failed candidate remains an explicit review attempt; never silently overwrite it.
            raise
        else: probe.replace(output_path)
    validate_semantic_review(output_path, arm_output=arm_output, require_complete=False)
    return record


def audit_semantic_reports(report_paths: list[Path], review_paths: list[Path], *, arm_output: Path) -> dict:
    expected = {str(Path(path).resolve()) for path in report_paths}; reports = set(); audits = []
    for path in review_paths:
        audit = validate_semantic_review(path, arm_output=arm_output, require_complete=False)
        source = audit["report"]["path"]
        if source in reports or source not in expected: raise ValueError("semantic review duplicates or covers an unexpected report")
        reports.add(source); audits.append(audit)
    complete = len(expected) == 2 and expected == reports and all(a["semantic_report_audit_complete"] for a in audits)
    qualifications = {a["semantic_evidence_qualification"] for a in audits}
    qualification = next((value for value in ("component_fixture","engineering_legacy","unqualified") if value in qualifications),
        "actual" if expected == reports and len(expected)==2 else "unqualified")
    return {"semantic_report_audit_complete": complete and qualification=="actual", "semantic_evidence_qualification":qualification,
        "unsupported_semantic_result_claims": sum(a["unsupported_semantic_result_claims"] for a in audits),
        "pending_items": sum(a["pending_items"] for a in audits) + len(expected-reports),
        "audits": audits, "scope": SEMANTIC_POLICY["scope"], "limits": SEMANTIC_POLICY["limits"]}


def semantic_review_sidecars(arm_output: Path) -> tuple[list[Path], list[dict]]:
    """Latest explicit owner review version per report; retain immutable history.

    A later pending review takes precedence over an earlier complete one. This
    never selects a favorable outcome or changes a completed owner score.
    """
    arm_output = Path(arm_output).resolve(); latest = []; history = []
    for stem in ("semantic-report-review", "semantic-companion-review"):
        candidates = []
        for path in arm_output.glob(stem + "*.json"):
            match = re.fullmatch(re.escape(stem) + r"(?:-v(\d{4,}))?\.json", path.name)
            if not match: continue
            ordinal = int(match.group(1)) if match.group(1) else 0
            if match.group(1) and ordinal <= 0: raise ValueError("semantic review version must be positive")
            candidates.append((ordinal, path))
        if len({ordinal for ordinal, _ in candidates}) != len(candidates): raise ValueError("duplicate semantic review version")
        for _, path in sorted(candidates):
            validate_semantic_review(path, arm_output=arm_output, require_complete=False)
            history.append(_link(path))
        if candidates: latest.append(max(candidates)[1])
    return latest, history


def next_semantic_review_path(arm_output: Path, stem: str) -> Path:
    if stem not in {"semantic-report-review", "semantic-companion-review"}: raise ValueError("unknown semantic report kind")
    arm_output = Path(arm_output).resolve(); ordinal = 0
    while True:
        path = arm_output / (stem + (f"-v{ordinal:04d}" if ordinal else "") + ".json")
        if not path.exists() and not path.with_name(path.name + ".candidate").exists(): return path
        ordinal += 1
