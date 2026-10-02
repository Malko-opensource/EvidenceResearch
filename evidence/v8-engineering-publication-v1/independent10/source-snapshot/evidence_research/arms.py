"""Actual upstream baseline tools confined to literal polynomial configurations.

Generated text is parsed, never executed. Caller-owned trusted task and verifier
perform the experiment. Raw Codex calls retain provider execution evidence.
"""
from __future__ import annotations

import argparse
import ast
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from .baseline import run_upstream_baseline, validate_literature_protocol, frozen_upstream_sources, UPSTREAM_MANIFEST_SHA256
from .model import CodexProvider, ModelUnavailable, PreregisteredResourcesExhausted, digest
from .store import atomic_json, execution_fingerprint
from .tasks import make_spec, public_task, run_task, sha256_file, validate_config, write_json
from .verifier import verify
from .context_boundary import ContextBoundaryRecorder

TOOL_CONTRACT = (
    "The host has already supplied the public task's fixed training and validation data. "
    "For owner-sampled development and final tasks, the public task seed is a logical data "
    "identifier, not a data-generation RNG seed; private per-split RNG seeds are unavailable. "
    "Legacy fixed development fixtures retain their explicitly marked public generation seeds. "
    "Use only a literal CONFIG assignment, e.g. CONFIG = {'degree': 1, 'alpha': 0.0}, "
    "or the standalone call run_candidate({'degree': 1, 'alpha': 0.0}). "
    "The host parses these actions and runs actual polynomial ridge training and validation. "
    "No imports, loops, functions, arithmetic expressions, filesystem access, print, or other Python "
    "statements are allowed. Do not include the example configuration unless you selected it. "
    "A DATA PREPARATION SUBMIT_CODE must also use a valid CONFIG assignment; data are preloaded. "
    "For MLE-Solver REPLACE or EDIT, use only these same literal configuration statements. "
    "The only legal configuration fields are degree (integer 1..8) and alpha (finite 0..100). "
    "Each permitted action evaluates one literal candidate. The host enforces the preregistered "
    "model-request and actual CPU-attempt resources; cached replay is not a new CPU attempt. "
    "Figures, external datasets, API calls and arbitrary code execution are outside the shared tool "
    "permissions. Use the original protocol command fences requested by the current phase. "
    "The frozen literature corpus is small and includes a task-relevant ridge/cross-validation paper. "
    "Different search phrasings retrieve the same fixed corpus; read a relevant result and use ADD_PAPER "
    "instead of repeating SUMMARY searches. "
    "During reporting distinguish actual host measurements, parameters, literature, and proposals. "
    "There is no test-set measurement, timing comparison, monetary price, or baseline improvement "
    "unless the host explicitly supplied its execution evidence. Do not fabricate those values."
)


def development_envelope(model: str = "gpt-6.1-sol") -> dict:
    """Smallest normal full phase transitions plus one literature submission slot."""
    return {"model": model, "max_steps": 4, "mlesolver_max_steps": 1,
            "papersolver_max_steps": 0, "num_papers_lit_review": 1,
            "max_model_calls": 51, "reasoning_effort": None,
            "execution_instructions": TOOL_CONTRACT,
            "resource_design": {
                "scope": "development task envelope; never a cap on the overall research goal",
                "max_steps_basis": "SUMMARY,FULL_TEXT,ADD_PAPER plus one submission/correction slot",
                "experiment_basis": "one actual registered candidate; upstream initial MLE solve",
                "report_basis": "all nine upstream initial scaffold/section stages; no extra EDIT round",
                "expected_minimum_normal_calls": 24,
                "call_budget_calculation": "phase limits (5 literature + 8 plan + 8 preparation + 8 interpretation) + 4 MLE generation/judge/repair + 18 report/readme/review = 51",
                "unbounded_upstream_retry_loops": "additional retries consume the same registered model-call resources; exhaustion is a resource status, not goal failure"}}


def frozen_literature() -> list[dict]:
    """Source-backed metadata; no benchmark answers or claimed local measurements."""
    return [
        {"id": "1910.02373v2", "title": "Ridge Regression: Structure, Cross-Validation, and Sketching",
         "authors": ["Sifan Liu", "Edgar Dobriban"],
         "url": "https://arxiv.org/html/1910.02373v2",
         "abstract": "The study analyzes ridge estimation, regularization selection through cross-validation, and sketching approximations.",
         "text": "Frozen source synopsis, not a full-text copy. Ridge Regression: Structure, Cross-Validation, and Sketching, sections 2 and 3, studies squared-error fitting with a quadratic coefficient penalty and selection of regularization through held-out/cross-validation error. The closed-form ridge solution depends on the feature covariance and regularization strength. The paper discusses validation bias in a high-dimensional asymptotic regime. It does not identify an optimal polynomial degree or alpha for this task; those must be measured from the supplied public training and validation data. Mathematical facts are literature context, not local experimental evidence."},
        {"id": "2501.04227v2", "title": "Agent Laboratory: Using LLM Agents as Research Assistants",
         "url": "https://arxiv.org/abs/2501.04227v2",
         "abstract": "Specialized agents perform literature review, planning, code experimentation, interpretation, and research reporting.",
         "text": "Literature claim from Agent Laboratory section 3: experiments execute generated code; an LLM reward model guides code selection. Its section 5 discusses self-evaluation and hallucinated results. This is not independent evidence of task performance here."},
        {"id": "2503.18102v1", "title": "AgentRxiv: Towards Collaborative Autonomous Research",
         "url": "https://arxiv.org/abs/2503.18102v1",
         "abstract": "Agent laboratories share and retrieve prior reports using a local preprint server and similarity-based retrieval.",
         "text": "Literature claim from AgentRxiv section 3: agents retrieve reports through a SentenceTransformer similarity search. Section 4.1 reports hallucination/reward-hacking risks and human checking of experimental outputs. Retrieved reports require verification before adoption."}]


def literature_protocol_from_envelope(envelope: dict, *, required_entries: int | None = None) -> dict:
    """Bind shared corpus exposure independently of original review-entry count.

    New comparisons require an explicit versioned policy. The original upstream
    num_papers_lit_review continues to mean len(review), including duplicates.
    This helper does not add a deduplication action or feedback to that workflow.
    """
    if "literature_protocol" not in envelope:
        raise ValueError("A new comparison requires an explicit literature_protocol")
    if required_entries is None:
        required_entries = envelope.get("upstream_settings", {}).get("num_papers_lit_review")
    return validate_literature_protocol(envelope["literature_protocol"], required_entries=required_entries)


def literature_from_envelope(envelope: dict, *, required_papers: int | None = None) -> list[dict]:
    """Use the registered corpus, rejecting repeated metadata as extra papers.

    Legacy standalone development calls may omit a snapshot. A supplied snapshot
    is authoritative; it is never silently replaced with the legacy corpus.
    Non-arXiv identifiers are adapter-local bibliographic IDs, not arXiv claims.
    required_papers is a legacy standalone shared-corpus size argument. A new
    protocol's shared distinct-source count is separate from original review
    entries and must not be inferred from num_papers_lit_review.
    """
    papers = envelope.get("literature_snapshot", frozen_literature())
    if not isinstance(papers, list) or not papers:
        raise ValueError("literature_snapshot must be a nonempty list of source records")
    ids, urls = set(), set()
    for paper in papers:
        if not isinstance(paper, dict) or any(not isinstance(paper.get(key), str) or not paper[key].strip()
                for key in ("id", "title", "url", "text")):
            raise ValueError("Each literature record requires an ID, title, URL and authored source synopsis")
        identifier = paper["id"].strip().casefold()
        arxiv_match = re.fullmatch(r"(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?", identifier)
        if arxiv_match:
            identifier = "arxiv:" + arxiv_match.group(1)
        parsed = urlsplit(paper["url"].strip())
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise ValueError("Literature source URLs must be explicit HTTP(S) primary references")
        url = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))
        if parsed.netloc.lower() in ("arxiv.org", "www.arxiv.org"):
            arxiv_url = re.fullmatch(r"/(?:abs|html|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?/?", parsed.path)
            if arxiv_url:
                url = "arxiv:" + arxiv_url.group(1)
        if identifier in ids or url in urls:
            raise ValueError("Duplicate literature ID/source URL cannot satisfy a distinct-paper requirement")
        ids.add(identifier)
        urls.add(url)
    expected = envelope.get("literature_snapshot_sha256")
    if expected is not None and expected != digest(papers):
        raise ValueError("Registered literature_snapshot_sha256 does not match the supplied source records")
    if "literature_protocol" in envelope:
        shared_required = literature_protocol_from_envelope(envelope)["required_shared_corpus_distinct_records"]
        if required_papers is not None and required_papers != shared_required:
            raise ValueError("Legacy required_papers conflicts with the explicit shared corpus count")
        required_papers = shared_required
    if required_papers is not None:
        if isinstance(required_papers, bool) or not isinstance(required_papers, int) or required_papers <= 0:
            raise ValueError("The required distinct literature count must be a positive integer")
        if len(ids) < required_papers:
            raise ValueError("The registered corpus lacks enough distinct records for the literature requirement")
    return json.loads(json.dumps(papers, ensure_ascii=False, allow_nan=False))


def recovery_summary(timeline: list[dict]) -> dict:
    """Count error episodes closed by a later independently verified CPU success.

    A failed hypothesis with a valid CPU result is not an execution error. Many
    errors before one success form one episode; raw causes remain linked.
    """
    pending, recoveries = [], []
    for event in timeline:
        if event.get("kind") in ("protocol_error", "runtime_error", "verification_error"):
            pending.append(event)
        elif event.get("kind") == "verified_cpu_success" and pending:
            recoveries.append({"causes": pending, "success": event})
            pending = []
    return {"recovered_errors": len(recoveries), "recovery_evidence": recoveries,
            "unrecovered_error_evidence": pending,
            "recovered_errors_scope": "Actual runtime, rejected protocol, or verification-error episodes followed by a later independently verified CPU success. Failed hypothesis criteria and external provider outages are separate."}


def literal_candidate(code: str) -> dict:
    """Parse only literal CONFIG assignments or run_candidate(literal dict)."""
    if not isinstance(code, str) or len(code.encode("utf-8")) > 20_000:
        raise ValueError("configuration program exceeds the tool input boundary")
    tree = ast.parse(code, mode="exec")
    if sum(1 for _ in ast.walk(tree)) > 500:
        raise ValueError("configuration program exceeds the AST boundary")
    candidate = None
    for statement in tree.body:
        value = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name) and target.id == "CONFIG":
                value = statement.value
        elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if (isinstance(call.func, ast.Name) and call.func.id == "run_candidate" and
                    len(call.args) == 1 and not call.keywords):
                value = call.args[0]
        if not isinstance(value, ast.Dict):
            raise ValueError("only CONFIG = literal dict or run_candidate(literal dict) is allowed")
        candidate = validate_config(ast.literal_eval(value))
    if candidate is None:
        raise ValueError("no literal candidate was submitted")
    return candidate


class AllowlistedExperimentTool:
    def __init__(self, directory: Path, spec_factory: Callable[[dict], dict],
                 *, runner: Callable = run_task, verifier: Callable = verify,
                 prior_records: list[dict] | None = None, max_cpu_executions: int | None = None,
                 context_recorder: ContextBoundaryRecorder | None = None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.spec_factory, self.runner, self.verifier = spec_factory, runner, verifier
        self.context_recorder = context_recorder
        if max_cpu_executions is not None and (isinstance(max_cpu_executions, bool) or
                not isinstance(max_cpu_executions, int) or max_cpu_executions <= 0):
            raise ValueError("CPU execution resources must be a preregistered positive integer")
        self.max_cpu_executions = max_cpu_executions
        self.context_ready, self.logical_cursor, self.logical_context = False, 0, None
        self.logical_tail = {}
        self.logical_history = {}
        self.logical_execution_coverage = set()
        self.logical_invocation_coverage = set()
        self.replay_completed = prior_records is not None and bool(prior_records)
        self.events_path = self.directory / "tool_events.jsonl"
        self.records = list(prior_records or []) + ([{**json.loads(line), "host_events_path": str(self.events_path)} for line in self.events_path.read_text(encoding="utf-8").splitlines()
                        if line.strip()] if self.events_path.exists() else [])
        if self.replay_completed:
            registered, completed = {}, {}
            for item in self.records:
                key = (item.get("candidate_identity"), item.get("code_sha256"))
                if item.get("status") == "registered":
                    registered[key] = registered.get(key, 0) + 1
                if item.get("actual_task_executed"):
                    completed[key] = completed.get(key, 0) + 1
                    folder = Path(item["run_dir"]).resolve()
                    if (json.loads((folder / "result.json").read_text(encoding="utf-8")) != item["result"] or
                            json.loads((folder / "registered_spec.json").read_text(encoding="utf-8")) != item["spec"]):
                        raise ModelUnavailable("Prior CPU receipt changed; reconcile before any new model request")
                    for name, expected in item["result"].get("artifact_hashes", {}).items():
                        path = folder / name
                        if path.is_symlink() or not path.resolve().is_relative_to(folder) or sha256_file(path) != expected:
                            raise ModelUnavailable("Prior CPU artifact changed; reconcile before any new model request")
                    if item["result"]["status"] == "success" and not self.verifier(item["spec"], item["result"], folder).get("valid"):
                        raise ModelUnavailable("Prior CPU success fails fixed verification; no model continuation permitted")
            if any(amount > completed.get(key, 0) for key, amount in registered.items()):
                raise ModelUnavailable("Unknown prior CPU execution; reconcile before any new model request")
            if self.max_cpu_executions is not None and len(self.completed) > self.max_cpu_executions:
                raise PreregisteredResourcesExhausted("Prior CPU executions exceed the registered resources; continuation refused")
        for item in self.records:
            if item.get("status") in ("logical_tool_reply", "logical_tool_replay"):
                logical = item["logical_request"]
                path = Path(item["output_receipt_path"])
                if not path.is_file() or sha256_file(path) != item["output_receipt_sha256"]:
                    raise ValueError("Prior logical tool response receipt changed or is missing")
                receipt = json.loads(path.read_text(encoding="utf-8"))
                if receipt["logical_request"] != logical:
                    raise ValueError("Prior logical tool response identity differs from its ledger")
                for evidence in receipt.get("execution_receipts", []):
                    if not Path(evidence["path"]).is_file() or sha256_file(evidence["path"]) != evidence["sha256"]:
                        raise ValueError("Prior logical tool response execution evidence changed")
                    self.logical_execution_coverage.add(str(Path(evidence["path"]).resolve()))
                for evidence in receipt.get("invocation_receipts", []):
                    matching = [record for record in self.records
                        if record.get("host_events_path") == evidence["host_events_path"]
                        and record.get("invocation") == evidence["invocation"]
                        and digest(record) == evidence["record_sha256"]]
                    if not matching:
                        raise ValueError("Prior logical tool response invocation evidence changed or is missing")
                    self.logical_invocation_coverage.add(evidence["record_sha256"])
                old = self.logical_tail.get(logical["ordinal"])
                value = {**item, "returned_text": receipt["returned_text"]}
                if old and (old["logical_request"] != logical or old["output_receipt_sha256"] != item["output_receipt_sha256"]):
                    raise ValueError("Conflicting prior logical tool responses")
                self.logical_tail[logical["ordinal"]] = value
                self.logical_history[logical["ordinal"]] = {"logical_request": logical,
                    "output_receipt_path": item["output_receipt_path"], "output_receipt_sha256": item["output_receipt_sha256"]}

    def configure_cursor(self, next_ordinal: int) -> None:
        if isinstance(next_ordinal, bool) or not isinstance(next_ordinal, int) or next_ordinal < 0:
            raise ValueError("Invalid committed logical tool cursor")
        actual = {str((Path(item["run_dir"]) / "result.json").resolve()) for item in self.completed}
        if actual - self.logical_execution_coverage:
            raise ValueError("Prior completed CPU executions lack logical response receipts; reconcile unknown work")
        physical = {digest(item) for item in self.records if item.get("status") not in
                    {"logical_tool_reply", "logical_tool_replay"}}
        if physical - self.logical_invocation_coverage:
            raise ValueError("Prior tool invocations lack logical response receipts; reconcile unknown work")
        if any(ordinal not in self.logical_history for ordinal in range(next_ordinal)):
            raise ValueError("Committed logical tool cursor has an incomplete prefix")
        self.context_ready, self.logical_cursor = True, next_ordinal
        self.logical_tail = {key: value for key, value in self.logical_tail.items() if key >= next_ordinal}

    def set_logical_context(self, context: dict) -> None:
        self.logical_context = context

    def export_cursor(self) -> dict:
        return {"next_ordinal": self.logical_cursor,
                "completed_receipts": [self.logical_history[key] for key in sorted(self.logical_history) if key < self.logical_cursor],
                "ledger_path": str(self.events_path), "ledger_sha256": sha256_file(self.events_path) if self.events_path.exists() else None}

    def _record(self, item: dict) -> None:
        item.setdefault("host_events_path", str(self.events_path))
        self.records.append(item)
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _successful_output(self, record: dict) -> str:
        executions = self.completed
        receipts = [{"execution_id": str(Path(item["run_dir"]).name),
                     "result_path": str(Path(item["run_dir"]) / "result.json"),
                     "result_sha256": sha256_file(Path(item["run_dir"]) / "result.json")}
                    for item in executions]
        return json.dumps({"execution_kind": "actual_cpu_execution", "execution_id": Path(record["run_dir"]).name,
            "config": record["config"], "metrics": record["result"]["metrics"],
            "artifacts": record["result"]["artifacts"], "independent_verification": "valid", "test_access": "withheld",
            "actual_cpu_attempts_to_date": len(executions),
            "distinct_configs_to_date": len({item["candidate_identity"] for item in executions}),
            "actual_cpu_executions_limit": self.max_cpu_executions,
            "remaining_cpu_executions": None if self.max_cpu_executions is None else self.max_cpu_executions - len(executions),
            "selected_record_scope": "This record describes the named actual CPU invocation. Pipeline attempt counts and distinct configuration counts are separate host observations; cached replay never increments them.",
            "host_ledger": {"current_events_path": str(self.events_path), "actual_execution_receipts": receipts}}, allow_nan=False)

    def __call__(self, code: str) -> str:
        if not self.context_ready:
            return self._invoke(code)
        if self.logical_context is None:
            raise ValueError("Committed tool replay requires a host phase/role/action context")
        try:
            condition_identity = execution_fingerprint(self.spec_factory(literal_candidate(code)))
        except (SyntaxError, ValueError, TypeError, RecursionError):
            condition_identity = None
        logical = {**self.logical_context, "ordinal": self.logical_cursor,
                   "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                   "execution_fingerprint": condition_identity}
        old = self.logical_tail.get(self.logical_cursor)
        if old is not None:
            if old["logical_request"] != logical:
                raise ValueError("Logical tool tail differs from the restored checkpoint; automatic execution refused")
            self.logical_tail.pop(self.logical_cursor)
            self._record({"invocation": len(self.records), "status": "logical_tool_replay", "actual_task_executed": False,
                "code_sha256": logical["code_sha256"], "logical_request": logical,
                "output_receipt_path": old["output_receipt_path"], "output_receipt_sha256": old["output_receipt_sha256"]})
            self.logical_cursor += 1
            if self.context_recorder:
                self.context_recorder.record_cpu_return(logical_context=logical,returned_text=old['returned_text'],
                    records=[],host_reply={'path':old['output_receipt_path'],'sha256':old['output_receipt_sha256']},replay=True)
            return old["returned_text"]
        if self.logical_tail:
            raise ValueError("The next logical tool response is missing from a completed tail; automatic execution refused")
        before = len(self.records)
        result = self._invoke(code)
        receipt = {"logical_request": logical, "returned_text": result,
            "scope": "Exact host response at this logical invocation; historical counts and paths are replayed unchanged. Full physical resources remain in the separate lineage ledger.",
            "execution_receipts": [{"path": str(Path(item["run_dir"]) / "result.json"),
                                    "sha256": sha256_file(Path(item["run_dir"]) / "result.json")}
                                   for item in self.records[before:] if item.get("actual_task_executed")],
            "invocation_receipts": [{"host_events_path": item["host_events_path"], "invocation": item["invocation"],
                                     "record_sha256": digest(item)} for item in self.records[before:]]}
        # Ordinal already uniquely identifies this invocation. Full logical and
        # output SHA remain in its immutable contents/ledger; shorten filenames
        # for nested Windows study paths. Existing identity collisions fail closed.
        path = self.directory / "tool-replies" / f"{self.logical_cursor:08d}-{digest(logical)[:12]}.json"
        if path.exists():
            raise ValueError("A logical tool response already exists without its committed ledger; reconcile unknown work")
        atomic_json(path, receipt)
        self._record({"invocation": len(self.records), "status": "logical_tool_reply", "actual_task_executed": False,
            "code_sha256": logical["code_sha256"], "logical_request": logical,
            "output_receipt_path": str(path), "output_receipt_sha256": sha256_file(path)})
        self.logical_history[self.logical_cursor] = {"logical_request": logical,
            "output_receipt_path": str(path), "output_receipt_sha256": sha256_file(path)}
        self.logical_cursor += 1
        if self.context_recorder:
            self.context_recorder.record_cpu_return(logical_context=logical,returned_text=result,
                records=[item for item in self.records[before:] if item.get('actual_task_executed')],
                host_reply={'path':str(path),'sha256':sha256_file(path)})
        return result

    def _invoke(self, code: str) -> str:
        invocation = len(self.records)
        code_sha = hashlib.sha256(code.encode("utf-8")).hexdigest()
        try:
            candidate = literal_candidate(code)
        except (SyntaxError, ValueError, TypeError, RecursionError) as exc:
            error = f"[CODE EXECUTION ERROR]: {type(exc).__name__}: {exc}. {TOOL_CONTRACT}"
            self._record({"invocation": invocation, "status": "rejected_code", "code_sha256": code_sha,
                          "error": error, "actual_task_executed": False})
            return error
        folder = self.directory / f"execution-{invocation:04d}"
        if folder.exists():
            raise ModelUnavailable("Unknown prior task execution; reconcile artifacts before retry")
        spec = self.spec_factory(candidate)
        identity = execution_fingerprint(spec)
        if self.replay_completed and not self.context_ready:
            matches = [item for item in self.records if item.get("candidate_identity") == identity
                       and item.get("code_sha256") == code_sha and item.get("actual_task_executed")]
            requests = [item for item in self.records if item.get("status") == "registered"
                        and item.get("candidate_identity") == identity and item.get("code_sha256") == code_sha]
            if len(requests) > len(matches):
                raise ModelUnavailable("Unknown prior task execution has no completed receipt; automatic repeat refused")
            if matches:
                prior = matches[-1]
                prior_folder = Path(prior["run_dir"]).resolve()
                if (json.loads((prior_folder / "result.json").read_text(encoding="utf-8")) != prior["result"] or
                        json.loads((prior_folder / "registered_spec.json").read_text(encoding="utf-8")) != prior["spec"]):
                    raise ModelUnavailable("Prior completed task record changed; replay refused")
                for name, expected in prior["result"].get("artifact_hashes", {}).items():
                    path = prior_folder / name
                    if path.is_symlink() or sha256_file(path) != expected:
                        raise ModelUnavailable("Prior completed task artifacts changed; replay refused")
                self._record({"invocation": invocation, "status": "reused_completed_execution",
                              "code_sha256": code_sha, "candidate_identity": identity,
                              "actual_task_executed": False, "run_dir": prior["run_dir"],
                              "result_sha256": sha256_file(prior_folder / "result.json")})
                if prior["result"]["status"] != "success":
                    return "[CODE EXECUTION ERROR]: " + str(prior["result"].get("error"))
                if not self.verifier(prior["spec"], prior["result"], prior_folder).get("valid"):
                    raise ModelUnavailable("Prior completed task does not pass the frozen verifier; replay refused")
                return self._successful_output(prior)
            if requests:
                raise ModelUnavailable("Unknown prior task execution has no completed receipt; automatic repeat refused")
        if self.max_cpu_executions is not None and len(self.completed) >= self.max_cpu_executions:
            raise PreregisteredResourcesExhausted("Preregistered per-unit CPU execution resources exhausted; research goal remains incomplete")
        duplicate = any(item.get("candidate_identity") == identity and item.get("actual_task_executed")
                        for item in self.records)
        request = {"invocation": invocation, "status": "registered", "config": candidate,
                   "code_sha256": code_sha, "candidate_identity": identity,
                   "duplicate_configuration": duplicate, "actual_task_executed": False}
        # The runner expects a new directory and is responsible for creating it.
        self._record(request)
        result = self.runner(spec, folder)
        verification = self.verifier(spec, result, folder)
        write_json(folder / "independent_verification.json", verification)
        completed = {**request, "status": result["status"], "actual_task_executed": True,
                     "run_dir": str(folder), "spec": spec, "result": result,
                     "verification": verification}
        self._record(completed)
        if result["status"] != "success":
            return "[CODE EXECUTION ERROR]: " + str(result.get("error"))
        if not verification.get("valid"):
            return "[CODE EXECUTION ERROR]: independent host verification failed: " + json.dumps(verification.get("reasons"))
        return self._successful_output(completed)

    @property
    def completed(self) -> list[dict]:
        return [item for item in self.records if item.get("actual_task_executed")]


class UpstreamCodexBridge:
    def __init__(self, provider: CodexProvider, directory: Path, *, max_model_calls: int,
                 replay_directories: list[Path] | None = None,
                 context_recorder: ContextBoundaryRecorder | None = None):
        self.provider = provider
        self.context_recorder = context_recorder
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_model_calls = max_model_calls
        self.calls = []
        self.path = self.directory / "model_transport_events.jsonl"
        self.replay, self.prior_evidence = {}, []
        self.prior_attempts = 0
        self.no_action_receipts = []
        self.context_ready, self.logical_cursor, self.logical_tail = False, 0, {}
        self.prior_entries = {}
        self.logical_history = {}
        self.failed_entries, self.failed_logical = {}, {}
        seen_paths, seen_receipts = set(), set()
        for previous in replay_directories or []:
            def prior_order(path):
                name = path.parent.name
                ordinal = name.rsplit("-", 1)[-1]
                return (0, int(ordinal), name) if ordinal.isdigit() else (1, 0, name)
            for folder in sorted((Path(previous) / "model").glob("*/request.json"), key=prior_order):
                folder = folder.parent.resolve()
                if folder in seen_paths:
                    continue
                seen_paths.add(folder)
                result_path = folder / "result.json"
                if not result_path.exists():
                    raise ModelUnavailable("Unknown prior model execution cannot be retried automatically")
                record = json.loads(result_path.read_text(encoding="utf-8"))
                CodexProvider._check_files(folder, record)
                request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
                if request.get("model") != provider.model or record.get("model") != provider.model:
                    raise ValueError("checkpoint model evidence differs from the current model")
                receipt_identity = digest({"request_sha256": sha256_file(folder / "request.json"),
                    "result_sha256": sha256_file(result_path), "events_sha256": sha256_file(folder / "events.jsonl")})
                if receipt_identity in seen_receipts:
                    continue
                seen_receipts.add(receipt_identity)
                self.prior_attempts += 1
                self.prior_evidence.append(str(folder))
                if record["status"] == "completed":
                    response_path = folder / "response.txt"
                    if record.get("tool_calls") or record.get("execution_kind") != "real_model":
                        raise ValueError("prior cache is not a tool-free real model completion")
                    key = hashlib.sha256(request["prompt"].encode()).hexdigest()
                    entry = {"response": response_path.read_text(encoding="utf-8"),
                        "original_receipt_identity": receipt_identity, "original_receipt_ordinal": self.prior_attempts - 1,
                        "original_result_path": str(result_path), "original_result_sha256": sha256_file(result_path),
                        "evidence_dir": str(folder), "model_evidence": {**record,
                            "evidence_record": CodexProvider._record_link(folder)}}
                    self.replay.setdefault(key, deque()).append(entry)
                    self.prior_entries[str(folder)] = entry
                else:
                    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
                    if (not any(event.get("type") == "turn.failed" for event in events)
                            or record.get("tool_calls")):
                        raise ModelUnavailable("Prior failure has no definitive no-action receipt; reconcile before retry")
                    self._no_action_receipt(folder, f"prior-{self.prior_attempts:04d}",
                        "Resume a definitive provider turn.failed with unchanged registered conditions; prior response was never returned to upstream.")
                    self.failed_entries[str(folder)] = receipt_identity
        for previous in replay_directories or []:
            transport = Path(previous) / "model_transport_events.jsonl"
            if not transport.exists():
                continue
            for line in transport.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if "logical_request" not in event:
                    continue
                logical = event["logical_request"]
                if event.get("status") == "failed":
                    folder = str(Path(event["evidence_dir"]).resolve())
                    if folder not in self.failed_entries:
                        raise ValueError("Logical failed model request has no definitive immutable raw receipt")
                    old_failure = self.failed_logical.get(logical["ordinal"])
                    if old_failure and old_failure["logical_request"] != logical:
                        raise ValueError("Conflicting definitive failures at the same logical model request")
                    self.failed_logical[logical["ordinal"]] = {"logical_request": logical,
                        "evidence_dirs": (old_failure["evidence_dirs"] if old_failure else []) + [folder]}
                    continue
                if event.get("status") != "completed":
                    continue
                entry = self.prior_entries.get(str(Path(event["evidence_dir"]).resolve()))
                if entry is None or entry["original_receipt_identity"] != event.get("logical_receipt_identity"):
                    raise ValueError("Logical model tail has no matching immutable raw receipt")
                old = self.logical_tail.get(logical["ordinal"])
                if old and (old["logical_request"] != logical or old["entry"]["original_receipt_identity"] != entry["original_receipt_identity"]):
                    raise ValueError("Conflicting logical model completion receipts")
                self.logical_tail[logical["ordinal"]] = {"logical_request": logical, "entry": entry}
                if event.get('context_boundary'):
                    entry['context_boundary']=event['context_boundary']
                self.logical_history[logical["ordinal"]] = {"logical_request": logical,
                    "receipt_identity": entry["original_receipt_identity"], "evidence_dir": entry["evidence_dir"],
                    "result_sha256": entry["original_result_sha256"]}
        for ordinal, failed in self.failed_logical.items():
            if ordinal in self.logical_history and self.logical_history[ordinal]["logical_request"] != failed["logical_request"]:
                raise ValueError("A completed logical request differs from its definitive failed attempt")

    def configure_cursor(self, next_ordinal: int) -> None:
        if isinstance(next_ordinal, bool) or not isinstance(next_ordinal, int) or next_ordinal < 0:
            raise ValueError("Invalid committed logical model cursor")
        covered = {value["receipt_identity"] for value in self.logical_history.values()}
        original = {entry["original_receipt_identity"] for entry in self.prior_entries.values()}
        if original - covered:
            raise ValueError("Prior model completions lack logical identities; legacy or unknown-work reconciliation is required")
        if len(covered) != len(self.logical_history):
            raise ValueError("One prior model receipt was mapped to multiple logical requests")
        failed_covered = {folder for value in self.failed_logical.values() for folder in value["evidence_dirs"]}
        if set(self.failed_entries) - failed_covered:
            raise ValueError("Prior failed model requests lack logical identities; reconcile legacy or unknown work")
        if any(ordinal not in self.logical_history for ordinal in range(next_ordinal)):
            raise ValueError("Committed logical model cursor has an incomplete prefix")
        self.context_ready, self.logical_cursor = True, next_ordinal
        self.logical_tail = {key: value for key, value in self.logical_tail.items() if key >= next_ordinal}

    def export_cursor(self) -> dict:
        return {"next_ordinal": self.logical_cursor,
                "completed_receipts": [self.logical_history[key] for key in sorted(self.logical_history) if key < self.logical_cursor],
                "ledger_path": str(self.path), "ledger_sha256": sha256_file(self.path) if self.path.exists() else None}

    def _no_action_receipt(self, folder: Path, identity: str, reason: str) -> None:
        """Host boundary receipt for an individual failed response, not the whole run."""
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
        sources = [folder / name for name in ("request.json", "result.json", "events.jsonl", "stderr.log")]
        receipt = {"provenance": "trusted_host_audit", "attempt_result_sha256": sha256_file(folder / "result.json"),
                   "attempt_result_path": str(folder / "result.json"), "request_fingerprint": request["fingerprint"],
                   "host_action_taken": False, "model_response_consumed": False,
                   "scope": "this failed provider response only; other completed calls may have executed task work",
                   "retry_reason": reason, "sources": [{"path": str(path), "sha256": sha256_file(path)} for path in sources]}
        directory = self.directory / "host-no-action"
        directory.mkdir(exist_ok=True)
        path = directory / f"{identity}.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8")) != receipt:
            raise ValueError("A completed host no-action receipt changed")
        if not path.exists():
            write_json(path, receipt)
        self.no_action_receipts.append(str(path))

    def __call__(self, model_str, prompt, system_prompt, *, temp=None, **kwargs):
        index = len(self.calls)
        call_id = f"upstream-{index:04d}"
        request = ("UPSTREAM SYSTEM PROMPT:\n" + system_prompt +
                   "\n\nUPSTREAM USER PROMPT:\n" + prompt +
                   "\n\nSHARED HOST EXECUTION CONTRACT:\n" + TOOL_CONTRACT)
        request_sha = hashlib.sha256(request.encode()).hexdigest()
        logical = None
        if self.context_ready:
            context = kwargs.get("_logical_context")
            if not isinstance(context, dict):
                raise ValueError("Committed model replay requires host phase/role/action context")
            logical = {**context, "ordinal": self.logical_cursor, "request_sha256": request_sha,
                       "system_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()}
            old = self.logical_tail.get(self.logical_cursor)
            failed = self.failed_logical.get(self.logical_cursor)
            if failed is not None and failed["logical_request"] != logical:
                raise ValueError("The failed logical model request differs from the restored checkpoint; fresh retry refused")
            if old is not None and old["logical_request"] != logical:
                raise ValueError("Logical model tail differs from the restored checkpoint; automatic model execution refused")
            if old is None and self.logical_tail:
                raise ValueError("The next logical model response is missing from a completed tail; automatic model execution refused")
            cached = self.logical_tail.pop(self.logical_cursor)["entry"] if old else None
        else:
            queue = self.replay.get(request_sha)
            cached = queue.popleft() if queue else None
        attempts = self.prior_attempts + sum(not item.get("reused_completed_evidence") for item in self.calls)
        if cached is None and attempts >= self.max_model_calls:
            raise PreregisteredResourcesExhausted("Preregistered per-unit model-call resources exhausted; research goal remains incomplete")
        event = {"call_id": call_id, "original_requested_model": model_str,
                 "actual_model": self.provider.model, "original_requested_temperature": temp,
                 "temperature_policy": "Codex CLI does not expose temperature; same policy required for C",
                 "request_sha256": request_sha, "status": "requested",
                 "reused_completed_evidence": cached is not None}
        self.calls.append(event)
        if logical is not None:
            event["logical_request"] = logical
        boundary = None
        if self.context_recorder:
            if cached:
                boundary=cached.get('context_boundary')
                if not boundary:
                    raise ValueError('Completed response has no original input boundary; do not reconstruct it posthoc')
            else:
                boundary=self.context_recorder.capture(call_id=call_id,prompt=request,
                    full_prompt=getattr(self.provider,'guard','')+request,logical_context=logical,
                    transport_path=self.path,provider=self.provider)
            event['context_boundary']=boundary
            with self.path.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
                stream.flush(); os.fsync(stream.fileno())
        try:
            if cached:
                event.update({"status": "completed", "evidence_dir": cached["evidence_dir"],
                              "model_evidence": cached["model_evidence"],
                              "replay_original_receipt_identity": cached.get("original_receipt_identity"),
                              "replay_original_receipt_ordinal": cached.get("original_receipt_ordinal"),
                              "replay_original_result_path": cached.get("original_result_path"),
                              "replay_original_result_sha256": cached.get("original_result_sha256"),
                              "replay_scope": "One prior actual completion consumed once in original receipt order during this invocation; another identical logical request needs its own prior receipt or a new budgeted provider request."})
                if logical is not None:
                    event["logical_receipt_identity"] = cached["original_receipt_identity"]
                    self.logical_history[self.logical_cursor] = {"logical_request": logical,
                        "receipt_identity": cached["original_receipt_identity"], "evidence_dir": cached["evidence_dir"],
                        "result_sha256": cached["original_result_sha256"]}
                    self.logical_cursor += 1
                return cached["response"]
            answer = self.provider.complete(request, call_id=call_id, json_response=False)
            event.update({"status": "completed", "evidence_dir": str(self.provider.evidence_dir / call_id),
                          "model_evidence": self.provider.last_evidence})
            if logical is not None:
                folder = self.provider.evidence_dir / call_id
                event["logical_receipt_identity"] = digest({"request_sha256": sha256_file(folder / "request.json"),
                    "result_sha256": sha256_file(folder / "result.json"), "events_sha256": sha256_file(folder / "events.jsonl")})
                self.logical_history[self.logical_cursor] = {"logical_request": logical,
                    "receipt_identity": event["logical_receipt_identity"], "evidence_dir": str(folder),
                    "result_sha256": sha256_file(folder / "result.json")}
                self.logical_cursor += 1
            return answer
        except Exception as exc:
            event.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}",
                          "evidence_dir": str(self.provider.evidence_dir / call_id)})
            folder = self.provider.evidence_dir / call_id
            if (folder / "result.json").exists():
                record = json.loads((folder / "result.json").read_text(encoding="utf-8"))
                events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
                if (record.get("status") == "failed" and not record.get("tool_calls")
                        and not any(item.get("type") == "turn.completed" for item in events)
                        and any(item.get("type") == "turn.failed" for item in events)):
                    self._no_action_receipt(folder, call_id, "Definitive provider failure before returning a response; explicit checkpoint continuation required.")
            raise
        finally:
            if self.context_recorder and boundary:
                self.context_recorder.record_model(folder=event['evidence_dir'],logical_context=logical,
                                                   boundary=boundary,replay=cached is not None)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())


def continuation_directories(settings: dict) -> list[Path]:
    """Follow this adapter's registered failed-run lineage; oldest first."""
    directories, seen = [], set()
    upstream = settings.get("resume_from")
    root = Path(__file__).resolve().parents[1] / "runs"
    while upstream:
        previous = Path(upstream).resolve()
        if not previous.is_relative_to(root) or previous in seen:
            raise ValueError("invalid or cyclic checkpoint lineage")
        seen.add(previous)
        directories.append(previous.parent)
        registration = json.loads((previous / "baseline_registration.json").read_text(encoding="utf-8"))
        upstream = registration["settings"].get("resume_from")
    return list(reversed(directories))


def audit_report_numbers(report: str, executions: list[dict], task: dict) -> dict:
    """Conservative evidence matching; unresolved claims never count as verified.

    This assists independent review, not an LLM self judgment. Formula coefficients
    and literature citations are excluded; ambiguous quantitative language remains
    unresolved and must be adjudicated against the original report by the owner.
    """
    measured = []
    for run in executions:
        for metric, value in run.get("result", {}).get("metrics", {}).items():
            if run.get("verification", {}).get("valid"):
                measured.append({"metric": metric, "value": value, "run_dir": run["run_dir"],
                                 "evidence": str(Path(run["run_dir"]) / "independent_verification.json")})
    claims = []
    normalized = re.sub(r"arXiv\s*:?\s*\d{4}\.\d{4,5}(?:v\d+)?", "[literature identifier]", report, flags=re.I)
    for line in normalized.splitlines():
        clean = line.replace("\\%", "%").replace("{", " ").replace("}", " ").replace("$", " ")
        if not re.search(r"\b(?:MSE|accuracy|seconds|runtime|cost)\b|\d\s*%", clean, re.I):
            continue
        if "\\frac" in clean or "\\sum" in clean:
            continue
        for match in re.finditer(r"(?<![A-Za-z])[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", clean):
            token, value = match.group(), float(match.group())
            decimals = len(token.partition(".")[2].split("e")[0].split("E")[0]) if "." in token else 0
            tolerance = 0.5 * 10**(-decimals) if decimals else 0.0
            evidence = [item for item in measured if abs(item["value"] - value) <= max(tolerance, 1e-9)]
            # Parameter/data counts are source facts, not performance estimates.
            parameters = [run.get("config", {}).get(key) for run in executions for key in ("degree", "alpha")]
            counts = [len(task.get(name, [])) for name in ("train", "validation")]
            if evidence:
                status = "matched_actual_measurement"
            elif value in parameters or value in counts:
                status = "matches_parameter_or_public_data_count; metric attribution requires review"
            else:
                status = "unresolved_requires_independent_adjudication"
            claims.append({"text": line, "number": token, "status": status, "evidence": evidence})
    return {"kind": "independent_numeric_inventory", "claims": claims,
            "unresolved_count": sum(c["status"].startswith("unresolved") for c in claims),
            "matched_count": sum(c["status"] == "matched_actual_measurement" for c in claims),
            "adjudication_status": "requires owner review; unresolved is not automatically zero unsupported claims"}


def run_development_baseline(directory: Path, *, task_id="dev-quadratic", seed=7,
                             model="gpt-6.1-sol", criterion=None, settings=None,
                             provider: CodexProvider | None = None) -> dict:
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    settings = settings or development_envelope(model)
    criterion = criterion or {"direction": "min", "threshold": 0.03}
    task = public_task(task_id, seed)
    provider = provider or CodexProvider(directory / "model", model=model,
                                        reasoning_effort=settings.get("reasoning_effort"),
                                        public_dir=directory / "public_model_cwd")
    lineage = continuation_directories(settings)
    prior_records = []
    for ancestor in lineage:
        path = ancestor / "experiments" / "tool_events.jsonl"
        if path.exists():
            prior_records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    tool = AllowlistedExperimentTool(directory / "experiments", lambda config: make_spec(
        task_id, seed, config, model=model, criterion=criterion,
        hypothesis="Original upstream agent selected a literal polynomial-ridge configuration.",
        resource_envelope={"device": "cpu", "network": False, "tools": ["trusted polynomial ridge"],
                           "model_call_envelope": settings["max_model_calls"]}), prior_records=prior_records)
    bridge = UpstreamCodexBridge(provider, directory, max_model_calls=settings["max_model_calls"],
                                replay_directories=lineage)
    write_json(directory / "development_protocol.json", {"task_id": task_id, "seed": seed,
        "criterion": criterion, "settings": settings, "model": model,
        "comparison_scope": "development; not final evaluation", "literature": frozen_literature()})
    baseline = run_upstream_baseline(task, directory / "upstream", bridge, tool,
                                     settings, literature=frozen_literature())
    selected = None
    if baseline.get("status") == "success":
        try:
            selected_config = literal_candidate(baseline["code"])
            matches = [run for run in tool.completed if run["config"] == selected_config
                       and run["verification"].get("valid")]
            if matches:
                selected = matches[-1]
        except (SyntaxError, ValueError):
            pass
    audit = audit_report_numbers(baseline.get("report", ""), tool.completed, task)
    write_json(directory / "numeric_claim_audit.json", audit)
    response = {"kind": "upstream_actual_adapted", "baseline": baseline,
                "selected": selected, "task_id": task_id, "seed": seed,
                "task_success": bool(selected and selected["result"]["metrics"]["validation_mse"] <= criterion["threshold"]),
                "criterion": criterion, "numeric_claim_audit": str(directory / "numeric_claim_audit.json"),
                "quantitative_claims_adjudicated": False,
                "duplicate_executions": sum(item["duplicate_configuration"] for item in tool.completed),
                "rejected_code_actions": sum(item["status"] == "rejected_code" for item in tool.records),
                "model_evidence_dirs": bridge.prior_evidence + [str(path.parent) for path in sorted((directory / "model").glob("*/result.json"))],
                "completed_responses_reused": sum(item.get("reused_completed_evidence", False) for item in bridge.calls),
                "continuation_lineage": [str(path) for path in lineage]}
    write_json(directory / "development_result.json", response)
    return response


class UpstreamArm:
    """Matched B callback: pinned upstream phases plus shared literal CPU tools.

    Only the supplied public bundle is visible. Independent report adjudication
    is an injected responsibility. A completed response is reused; a failed run
    requires an explicit continuation reason, and its original evidence remains
    immutable in a separate attempt directory.
    """
    def __init__(self, provider_factory: Callable = CodexProvider,
                 independent_reviewer: Callable | None = None,
                 continuation_reason: str | None = None):
        self.provider_factory = provider_factory
        self.independent_reviewer = independent_reviewer
        self.continuation_reason = continuation_reason

    @staticmethod
    def _public_payload(payload: dict) -> tuple[dict, dict, dict]:
        from .tasks import TASK_VERSION, registered_data
        if payload.get("arm") != "B":
            raise ValueError("UpstreamArm handles only the preregistered B arm")
        public, envelope = payload["public_task"], payload["resource_envelope"]
        allowed = {"task_id", "seed", "task_version", "objective", "metric", "allowed_config", "task_bundle", "criterion"}
        if set(public) - allowed or public.get("task_version") != TASK_VERSION:
            raise ValueError("Unsupported public task contract; private definitions/paths are forbidden")
        if set(public["task_bundle"]) != {"train", "validation", "split_manifest"}:
            raise ValueError("Only owner-supplied public training/validation and split hashes are allowed")
        calls = envelope.get("proposal_calls_per_unit")
        if isinstance(calls, bool) or not isinstance(calls, int) or calls <= 0:
            raise ValueError("Preregistered proposal_calls_per_unit must be positive")
        cpu_calls = envelope.get("actual_cpu_executions_per_unit")
        if isinstance(cpu_calls, bool) or not isinstance(cpu_calls, int) or cpu_calls <= 0:
            raise ValueError("Preregistered actual_cpu_executions_per_unit must be positive")
        criterion = public.get("criterion", envelope.get("success_criterion", {"direction": "min"}))
        if criterion.get("direction") != "min":
            raise ValueError("The fixed task metric is minimized")
        if "threshold" in criterion and (isinstance(criterion["threshold"], bool) or
                not isinstance(criterion["threshold"], (int, float)) or not math.isfinite(criterion["threshold"])):
            raise ValueError("A supplied public threshold must be finite")
        probe = make_spec(public["task_id"], public["seed"], {"degree": 1, "alpha": 0.0},
                          model=payload["model_id"], task_bundle=public["task_bundle"],
                          criterion=criterion, resource_envelope=envelope)
        registered_data(probe)
        return public, envelope, criterion

    def __call__(self, payload: dict, arm_output: Path) -> dict:
        from .evaluation import prepare_numeric_review
        upstream_sources = frozen_upstream_sources()
        output = Path(arm_output).resolve()
        output.mkdir(parents=True, exist_ok=True)
        public, envelope, criterion = self._public_payload(payload)
        settings = development_envelope(payload["model_id"])
        settings.update(envelope.get("upstream_settings", {}))
        settings.update(model=payload["model_id"], max_model_calls=envelope["proposal_calls_per_unit"],
                        reasoning_effort=envelope.get("reasoning_effort"), execution_instructions=TOOL_CONTRACT,
                        actual_cpu_executions_per_unit=envelope["actual_cpu_executions_per_unit"])
        literature_protocol = literature_protocol_from_envelope(envelope,
            required_entries=settings["num_papers_lit_review"])
        settings["literature_protocol"] = literature_protocol
        literature = literature_from_envelope(envelope)
        registration = {"payload_sha256": digest(payload), "public_task": public,
                        "model_id": payload["model_id"], "resource_envelope": envelope,
                        "settings": settings, "implementation_sha256": sha256_file(Path(__file__)),
                        "kind": "upstream_actual_adapted", "source_commit": __import__(
                            "evidence_research.baseline", fromlist=["UPSTREAM_COMMIT"]).UPSTREAM_COMMIT,
                        "stopping_criterion": criterion, "literature_snapshot_sha256": digest(literature),
                        "literature_protocol": literature_protocol,
                        "upstream_source_manifest_sha256": UPSTREAM_MANIFEST_SHA256,
                        "upstream_source_inventory": {Path(path).relative_to(Path(__file__).resolve().parents[1]).as_posix(): value
                                                      for path, value in upstream_sources.items()},
                        "visibility": "public bundle only; no hidden evaluator task definitions",
                        "resource_scope": "Matched per-unit phase/model resource envelope; not a Goal loop limit"}
        receipt = output / "callback-registration.json"
        if receipt.exists():
            if json.loads(receipt.read_text(encoding="utf-8")) != registration:
                raise ValueError("Callback source/conditions differ from its durable registration")
        else:
            write_json(receipt, registration)
        response_path = output / "arm-response.json"
        if response_path.exists():
            response = json.loads(response_path.read_text(encoding="utf-8"))
            self._verify_selected(response)
            self._maybe_review(output)
            return {**response, "resumed_without_execution": True,
                    "independent_review_pending": not all((output / name).exists() for name in ("report-review.json", "companion-review.json"))}
        attempts_root = output / "attempts"
        attempts_root.mkdir(exist_ok=True)
        attempts = sorted(attempts_root.glob("attempt-*"))
        if attempts:
            previous = attempts[-1]
            result_path = previous / "upstream" / "baseline_result.json"
            if not result_path.exists():
                raise ModelUnavailable("Unknown prior upstream execution; reconcile without repeating it")
            prior = json.loads(result_path.read_text(encoding="utf-8"))
            if prior["status"] != "success":
                if prior.get("error", "").startswith("PreregisteredResourcesExhausted:"):
                    raise PreregisteredResourcesExhausted(prior["error"])
                if not prior.get("error", "").startswith("ModelUnavailable:"):
                    raise ValueError("Preserved upstream software/host-contract failure: " + prior.get("error", "missing failure cause"))
                if not self.continuation_reason:
                    raise ModelUnavailable("Recorded failed upstream run needs explicit checkpoint continuation reason")
                settings.update(resume_from=str(previous / "upstream"), retry_reason=self.continuation_reason)
                attempt = attempts_root / f"attempt-{len(attempts):04d}"
            else:
                attempt = previous
                settings = json.loads((previous / "upstream" / "baseline_registration.json").read_text(encoding="utf-8"))["settings"]
        else:
            attempt = attempts_root / "attempt-0000"
        attempt.mkdir(exist_ok=True)
        lineage = continuation_directories(settings)
        records = []
        for ancestor in lineage:
            path = ancestor / "experiments" / "tool_events.jsonl"
            if path.exists():
                records.extend({**json.loads(line), "host_events_path": str(path)} for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        provider = self.provider_factory(evidence_dir=attempt / "model", model=payload["model_id"],
            reasoning_effort=envelope.get("reasoning_effort"), public_dir=attempt / "public_model_cwd")
        actual = getattr(provider, "execution_kind", None) == "real_model"
        boundary_recorder=ContextBoundaryRecorder(output,arm='B',registration=receipt,
            model_id=payload['model_id'],resource_envelope=envelope,public_task=public,fixture_only=not actual)
        def spec_factory(config):
            spec = make_spec(public["task_id"], public["seed"], config, model=payload["model_id"],
                criterion=criterion, resource_envelope=envelope, task_bundle=public["task_bundle"],
                hypothesis="Pinned upstream agent selected a literal polynomial ridge configuration.")
            if "threshold" not in criterion:
                spec["role"] = "baseline"
            return spec
        tool = AllowlistedExperimentTool(attempt / "experiments", spec_factory, prior_records=records,
                                        max_cpu_executions=envelope["actual_cpu_executions_per_unit"],
                                        context_recorder=boundary_recorder)
        bridge = UpstreamCodexBridge(provider, attempt, max_model_calls=envelope["proposal_calls_per_unit"],
                                    replay_directories=lineage,context_recorder=boundary_recorder)
        baseline = run_upstream_baseline(public, attempt / "upstream", bridge, tool, settings,
                                         literature=literature)
        if baseline["status"] != "success":
            error = baseline.get("error", "upstream pipeline did not complete")
            if error.startswith("PreregisteredResourcesExhausted:"):
                raise PreregisteredResourcesExhausted(error)
            if error.startswith("ModelUnavailable:"):
                raise ModelUnavailable(error)
            raise ValueError(error)
        selected_config = literal_candidate(baseline["code"])
        selected = [run for run in tool.completed if run["config"] == selected_config
                    and run["verification"].get("valid") and run["result"]["status"] == "success"]
        if not selected:
            raise ValueError("Original upstream selected code has no independently verified actual execution")
        selected = selected[-1]
        report_path = output / "report.txt"
        original_report = attempt / "upstream" / "lab" / "report.txt"
        report_path.write_bytes(original_report.read_bytes())
        all_dirs = list(dict.fromkeys(bridge.prior_evidence + [str(path.parent) for path in sorted((attempt / "model").glob("*/result.json"))]))
        companion = self._report_companion(public, selected, baseline, tool.completed, all_dirs, actual)
        companion_path = output / "research_report.json"
        write_json(companion_path, companion)
        inventory_path = output / "numeric-inventory.json"
        if not inventory_path.exists():
            prepare_numeric_review(report_path, inventory_path)
        companion_inventory = output / "companion-numeric-inventory.json"
        if not companion_inventory.exists():
            prepare_numeric_review(companion_path, companion_inventory)
        numeric_hints = audit_report_numbers(baseline["report"], tool.completed, public["task_bundle"])
        write_json(output / "claim-evidence-hints.json", numeric_hints)
        trace_path = output / "model-transport.jsonl"
        trace_paths = [ancestor / "model_transport_events.jsonl" for ancestor in lineage] + [bridge.path]
        trace_path.write_text("".join(path.read_text(encoding="utf-8") for path in trace_paths if path.exists()), encoding="utf-8")
        completed_dirs, failed_dirs = [], []
        for value in all_dirs:
            record = json.loads((Path(value) / "result.json").read_text(encoding="utf-8"))
            (completed_dirs if record["status"] == "completed" else failed_dirs).append(value)
        recovery_timeline = []
        for event in tool.records:
            events_file = Path(event.get("host_events_path", str(tool.events_path)))
            reference = {"tool_events_path": str(events_file), "tool_events_sha256": sha256_file(events_file), "invocation": event["invocation"],
                         "code_sha256": event["code_sha256"], "run_dir": event.get("run_dir")}
            if event["status"] == "rejected_code":
                recovery_timeline.append({**reference, "kind": "protocol_error", "reason": event["error"]})
            elif event.get("actual_task_executed"):
                if event["status"] == "failure":
                    recovery_timeline.append({**reference, "kind": "runtime_error", "reason": event["result"].get("error")})
                elif not event["verification"].get("valid"):
                    recovery_timeline.append({**reference, "kind": "verification_error", "reason": event["verification"].get("reasons")})
                else:
                    recovery_timeline.append({**reference, "kind": "verified_cpu_success"})
        recovery = recovery_summary(recovery_timeline)
        evidence_paths = [receipt, trace_path, inventory_path, output / "claim-evidence-hints.json",
                          attempt / "upstream" / "baseline_result.json", companion_path, companion_inventory]
        evidence_paths += [ancestor / "experiments" / "tool_events.jsonl" for ancestor in lineage]
        evidence_paths += [tool.events_path] if tool.events_path.exists() else []
        telemetry = {"provenance": "trusted_host_audit",
                     "duplicate_executions": sum(bool(run["duplicate_configuration"]) for run in tool.completed),
                     **recovery, "verified_memory_hits": 0, "unsupported_claims": 0,
                     "unique_verified_memory_records": 0,
                     "verified_memory_hits_scope": "Cumulative verified-memory record exposures in model requests; zero because this upstream adapter does not inject the improved Store retrieval.",
                     "completed_verified_retries": 0, "failed_hypothesis_retries": 0,
                     "hypothesis_retry_scope": "Only explicitly linked retry_of registrations count; upstream unlinked pipeline actions are not labeled failed-hypothesis retries.",
                     "duplicate_execution_identity": "store.execution_fingerprint: task/version/seed/model/config/data/source/tool/resource conditions; changed prose or criterion does not create a new execution identity.",
                     "unsupported_count_scope": "Pending independent whole-report adjudication; zero is not an accepted report conclusion",
                     "external_model_failures": len(failed_dirs),
                     "external_checkpoint_recoveries": len(lineage),
                     "claim_audit_scope": "whole_report_numeric_inventory_pending_independent_adjudication",
                     "sources": [{"path": str(path), "sha256": sha256_file(path)} for path in evidence_paths if path.exists()],
                     "report_path": str(report_path), "report_sha256": sha256_file(report_path)}
        write_json(output / "telemetry.json", telemetry)
        lineage_path = output / "continuation-lineage.json"
        receipts = {}
        for receipt_value in bridge.no_action_receipts:
            receipt_path = Path(receipt_value)
            receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipts[str(Path(receipt_data["attempt_result_path"]).parent.resolve())] = str(receipt_path)
        write_json(lineage_path, {"provenance": "trusted_host_audit",
            "kind": "explicit_model_attempt_resume_lineage", "model_id": payload["model_id"],
            "current_arm_output": str(output),
            "current_attempt": str(attempt), "retry_reason": self.continuation_reason,
            "previous_results": [{"path": str(ancestor / "upstream" / "baseline_result.json"),
                "sha256": sha256_file(ancestor / "upstream" / "baseline_result.json")} for ancestor in lineage],
            "failed_model_attempt_dirs": failed_dirs,
            "failed_request_fingerprints": [json.loads((Path(path) / "request.json").read_text(encoding="utf-8"))["fingerprint"] for path in failed_dirs],
            "attempts": [{"failed_dir": value, "result_sha256": sha256_file(Path(value) / "result.json"),
                "request_fingerprint": json.loads((Path(value) / "request.json").read_text(encoding="utf-8"))["fingerprint"],
                "host_action_receipt": receipts[value], "receipt_sha256": sha256_file(Path(receipts[value]))}
                for value in failed_dirs],
            "completed_response_cache_scope": "prompt-identical raw completion reuse; never a second actual model execution"})
        self._maybe_review(output)
        response = {"model_id": payload["model_id"], "resource_envelope": envelope,
                    "model_execution_kind": "actual_model_execution" if actual else "simulation_fixture",
                    "selected_run_dir": selected["run_dir"], "model_trace_path": str(trace_path),
                    "cpu_execution_dirs": list(dict.fromkeys(run["run_dir"] for run in tool.completed)),
                    "model_evidence_dirs": completed_dirs, "failed_model_evidence_dirs": failed_dirs,
                    "failed_model_attempt_dirs": failed_dirs,
                    "failed_model_host_receipts": bridge.no_action_receipts,
                    "host_action_receipts": receipts,
                    "continuation_lineage_path": str(lineage_path),
                    "telemetry_evidence_path": str(output / "telemetry.json"), "report_path": str(report_path),
                    "numeric_inventory_path": str(inventory_path),
                    "companion_numeric_inventory_path": str(companion_inventory),
                    "report_contract_path": str(companion_path),
                    "independent_review_pending": not all((output / name).exists() for name in ("report-review.json", "companion-review.json")),
                    "comparison_improvement_claim": False, "baseline_result_path": str(attempt / "upstream" / "baseline_result.json")}
        self._verify_selected(response)
        write_json(response_path, response)
        return response

    @staticmethod
    def _report_companion(public, selected, baseline, executions, model_dirs, actual):
        from .report_contract import REPORT_SCHEMA_VERSION
        spec, metrics = selected["spec"], selected["verification"]["metrics"]
        folder = Path(selected["run_dir"])
        evidence_paths = [folder / name for name in ("registered_spec.json", "result.json", "predictions.json", "independent_verification.json")]
        evidence_paths += [Path(value) / "result.json" for value in model_dirs]
        records = [json.loads((Path(value) / "result.json").read_text(encoding="utf-8")) for value in model_dirs]
        usages = []
        tokens_known = actual
        for value, record in zip(model_dirs, records):
            usage = record.get("usage", {})
            if record["status"] == "failed":
                events = [json.loads(line) for line in (Path(value) / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
                failure = next((event for event in events if event.get("type") == "turn.failed"), {})
                usage = failure.get("usage") or {}
            if not all(isinstance(usage.get(key), int) and not isinstance(usage[key], bool)
                       and usage[key] >= 0 for key in ("input_tokens", "output_tokens")):
                tokens_known = False
            usages.append(usage)
        token_usage = {key: sum(usage[key] for usage in usages) for key in ("input_tokens", "output_tokens")} if tokens_known else None
        seconds = math.fsum(record["wall_seconds"] for record in records) if actual and all(
            isinstance(record.get("wall_seconds"), (int, float)) and not isinstance(record["wall_seconds"], bool)
            and math.isfinite(record["wall_seconds"]) for record in records) else None
        unresolved = [{"question": "Would another configuration improve held-out performance?",
                       "reason": "The original solver's selection is guided by its LLM reward; hidden test results are unavailable to the research arm."}]
        unresolved += [{"question": "Why did a registered CPU configuration fail?", "reason": str(run["result"].get("error"))}
                       for run in executions if run["result"]["status"] == "failure"]
        return {"schema_version": REPORT_SCHEMA_VERSION, "goal": public["objective"],
            "hypothesis": "Planning proposal, not a measured outcome:\n" + baseline.get("plan", spec["hypothesis"]),
            "selected_config": spec["config"],
            "provenance": {key: spec[key] for key in ("task_id", "task_version", "seed", "split_manifest_sha256", "implementation_sha256", "evaluator_sha256")},
            "execution": {"kind": spec["execution_entrypoint"]["kind"], "entrypoint": spec["command"],
                          "reproduction_command": spec["reproduction_command"]},
            "evidence": [{"path": str(path), "sha256": sha256_file(path)} for path in evidence_paths],
            "measured_metrics": [{"kind": "measured", "metric": name, "value": value,
                "evidence_path": str(folder / "result.json"), "evidence_sha256": sha256_file(folder / "result.json")}
                for name, value in metrics.items()],
            "selection_reason": "The original upstream MLE reward selected the final code. The trusted host links it to an independently verified actual execution; this does not establish optimality or framework improvement.",
            "unresolved": unresolved,
            "limitations": ["This adapts original imports, model transport and tools to fixed public polynomial-ridge tasks; original MATH-500 and AgentRxiv web/PDF results were not reproduced.",
                "Only training and validation are available to the agent. The independent owner holds test observations.",
                "Upstream reward scores are model judgments, not independent task metrics.",
                "Planned comparisons and estimated gains are proposals unless separate execution records support them.",
                "Original-model arm A is unexecuted; model replacement effects are not empirically estimated.",
                "Provider billed monetary cost is unknown. A failed request without raw usage has unknown tokens, not zero tokens.",
                "A common information checklist does not establish equal literary quality or general scientific discovery quality.",
                "Both this companion and the unchanged original report require separate independent numeric adjudication."],
            "references": [{"kind": "literature", "url": paper["url"], "claim": paper["text"]} for paper in literature_from_envelope(spec["resource_envelope"])],
            "next_questions": ["Do independently held-out outcomes support the same-model framework comparison?",
                "Which failed or unresolved hypothesis needs changed conditions and a new preregistration?",
                "Does removing evidence-linked memory change duplication and decisions under matched resources?"],
            "resources": {"tokens_known": tokens_known, "token_usage": token_usage, "seconds": seconds,
                "actual_cpu_executions": len(executions),
                "actual_cpu_executions_per_unit": spec["resource_envelope"].get("actual_cpu_executions_per_unit"),
                "proposal_calls_per_unit": spec["resource_envelope"].get("proposal_calls_per_unit"),
                "provider_billed_cost": None, "scope": "Raw completed and definitive failed provider-request records across the explicit continuation lineage; cached responses are counted only once. Unknown failed usage remains null."},
            "planning_claim_kind": "proposal"}

    @staticmethod
    def _verify_selected(response: dict) -> None:
        folder = Path(response["selected_run_dir"]).resolve()
        spec = json.loads((folder / "registered_spec.json").read_text(encoding="utf-8"))
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        if not verify(spec, result, folder).get("valid"):
            raise ValueError("Completed selected CPU evidence changed or failed fixed verification")
        baseline = Path(response["baseline_result_path"])
        from .baseline import _check_baseline_artifacts
        _check_baseline_artifacts(baseline.parent, json.loads(baseline.read_text(encoding="utf-8")))

    def _maybe_review(self, output: Path) -> None:
        pairs = ((output / "report.txt", output / "numeric-inventory.json", output / "report-review.json"),
                 (output / "research_report.json", output / "companion-numeric-inventory.json", output / "companion-review.json"))
        for report_path, inventory_path, review_path in pairs:
            if self.independent_reviewer and not review_path.exists():
                self.independent_reviewer(inventory_path, review_path)
        if any(not review_path.exists() for _, _, review_path in pairs):
            return
        reviews = []
        for report_path, inventory_path, review_path in pairs:
            review = json.loads(review_path.read_text(encoding="utf-8"))
            if review.get("reviewer_role") != "independent_verifier" or review.get("status") != "complete" or review.get("pending_claims") != 0:
                raise ValueError("Supplied report review is not complete independent adjudication")
            if review.get("report_sha256") != sha256_file(report_path) or review.get("inventory_sha256") != sha256_file(inventory_path):
                raise ValueError("Independent review refers to changed upstream report/companion inventory")
            reviews.append(review)
        telemetry_path = output / "telemetry.json"
        telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
        telemetry.update(report_review_paths=[{"path": str(review_path), "sha256": sha256_file(review_path)} for _, _, review_path in pairs],
                         unsupported_claims=sum(review["unsupported_claims"] for review in reviews),
                         claim_audit_scope="whole_report_and_companion_numeric_inventories")
        write_json(telemetry_path, telemetry)


def upstream_callback(payload: dict, arm_output: Path) -> dict:
    """Default actual baseline callback leaves independent report review pending."""
    return UpstreamArm()(payload, arm_output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-baseline", type=Path, required=True)
    parser.add_argument("--task", default="dev-quadratic")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--retry-of", type=Path)
    parser.add_argument("--retry-reason")
    parser.add_argument("--resume-from", type=Path,
                        help="failed development run directory whose original phase checkpoint continues")
    args = parser.parse_args()
    settings = development_envelope(args.model)
    criterion = None
    if args.resume_from:
        if not args.retry_reason:
            parser.error("checkpoint continuation requires --retry-reason")
        previous = args.resume_from.resolve()
        protocol = json.loads((previous / "development_protocol.json").read_text(encoding="utf-8"))
        settings = protocol["settings"]
        args.task, args.seed, args.model = protocol["task_id"], protocol["seed"], protocol["model"]
        criterion = protocol["criterion"]
        settings.update({"resume_from": str(previous / "upstream"), "retry_reason": args.retry_reason})
    elif args.retry_of:
        if not args.retry_reason:
            parser.error("a retry requires changed conditions and --retry-reason")
        settings.update({"retry_of": str(args.retry_of.resolve()), "retry_reason": args.retry_reason})
    result = run_development_baseline(args.development_baseline, task_id=args.task, seed=args.seed,
                                      model=args.model, settings=settings, criterion=criterion)
    print(json.dumps({"baseline_status": result["baseline"]["status"], "task_success": result["task_success"],
                      "selected_config": result["selected"]["config"] if result["selected"] else None,
                      "selected_metrics": result["selected"]["result"]["metrics"] if result["selected"] else None,
                      "numeric_claim_audit": result["numeric_claim_audit"]}, ensure_ascii=False))
    if result["baseline"]["status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
