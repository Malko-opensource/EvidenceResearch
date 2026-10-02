"""Run pinned Agent Laboratory definitions with explicitly recorded tool adapters.

This executes the upstream agent classes, phase ordering, prompts, MLE solver,
and LLM reward functions. It is an adapted upstream execution, not a recreation
of the paper's MATH-500 experiment or a substitute hand-written baseline.
Only top-level imports are omitted; external tools are supplied by the caller.
Use a dedicated process: upstream module aliases and cwd are process-global.
"""
from __future__ import annotations

import argparse
import ast
import collections
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import copy
import datetime
import hashlib
import builtins
import io
import itertools
import json
import logging
import math
import os
from pathlib import Path
import pickle
import random
import re
import shutil
import string
import subprocess
import sys
import threading
import time
import types
import warnings
from typing import Any, Callable

from .store import atomic_json

UPSTREAM_COMMIT = "d9017d90e329112d2a80b7712f37ee9094d2cd27"
SOURCE_MODULES = ("utils", "agents", "mlesolver", "papersolver", "ai_lab_repo")
LITERATURE_PROTOCOL_VERSION = "shared-corpus-original-review-entries-2"
_RUN_LOCK = threading.RLock()


def make_literature_protocol(required_entries: int, shared_distinct: int) -> dict:
    """Declare host source exposure separately from original review-list length."""
    for value, label in ((required_entries, "original_minimum_review_entries"),
                         (shared_distinct, "required_shared_corpus_distinct_records")):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(label + " must be a positive integer")
    return {"protocol_version": LITERATURE_PROTOCOL_VERSION,
            "required_shared_corpus_distinct_records": shared_distinct,
            "original_minimum_review_entries": required_entries}


def validate_literature_protocol(protocol: dict, *, required_entries: int | None = None) -> dict:
    """Reject unsupported contracts; do not reinterpret an older protocol."""
    if not isinstance(protocol, dict):
        raise ValueError("literature_protocol must be an explicit versioned object")
    normalized = make_literature_protocol(protocol.get("original_minimum_review_entries"),
                                         protocol.get("required_shared_corpus_distinct_records"))
    if protocol != normalized:
        raise ValueError("Unsupported literature_protocol version, fields or policy")
    if required_entries is not None:
        make_literature_protocol(required_entries, 1)
        if normalized["original_minimum_review_entries"] != required_entries:
            raise ValueError("original_minimum_review_entries must match upstream num_papers_lit_review")
    return normalized


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                    + "\n", encoding="utf-8")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_tuples(value):
    return tuple(_json_tuples(item) for item in value) if isinstance(value, list) else value


def _checked_local_json(directory: Path, relative: str, expected: str) -> dict:
    path = directory / relative
    if (Path(relative).is_absolute() or ".." in Path(relative).parts or path.is_symlink()
            or not path.resolve().is_relative_to(directory.resolve()) or not path.is_file()
            or _file_hash(path) != expected):
        raise ValueError("Committed transport checkpoint evidence changed or is missing")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_checkpoint_commit(directory: Path) -> dict | None:
    """A committed head selects an immutable checkpoint/cursor pair, never a pkl alone."""
    head_path = directory / "transport_checkpoint_head.json"
    if not head_path.exists():
        return None
    head = json.loads(head_path.read_text(encoding="utf-8"))
    manifest = _checked_local_json(directory, head["manifest_path"], head["manifest_sha256"])
    cursor = _checked_local_json(directory, manifest["cursor_path"], manifest["cursor_sha256"])
    checkpoint = directory / manifest["checkpoint_path"]
    relative = Path(manifest["checkpoint_path"])
    if (relative.is_absolute() or ".." in relative.parts or checkpoint.is_symlink()
            or not checkpoint.resolve().is_relative_to(directory.resolve()) or not checkpoint.is_file()
            or checkpoint.stat().st_size > 10_000_000 or _file_hash(checkpoint) != manifest["checkpoint_sha256"]):
        raise ValueError("Committed upstream pickle does not match its transport cursor")
    if cursor["checkpoint_sha256"] != manifest["checkpoint_sha256"]:
        raise ValueError("Transport cursor is bound to a different upstream checkpoint")
    initial = directory / "transport_initial_state.json"
    if not initial.is_file() or _file_hash(initial) != cursor["initial_state_sha256"]:
        raise ValueError("Checkpoint initial RNG/transport state changed or is missing")
    return {"head": head, "manifest": manifest, "cursor": cursor, "checkpoint": str(checkpoint)}


class _HostTransportAbort(BaseException):
    """Escape upstream reward helpers that swallow Exception; preserve the real cause."""
    def __init__(self, cause: Exception):
        self.cause = cause
        super().__init__(str(cause))


class TransportCheckpointController:
    """Host state kept outside original pickled classes and pinned AST definitions.

    Zero-based logical model/tool cursors and one interleaved action cursor bind
    a completed checkpoint prefix to immutable response receipts. A reconstructed
    tail consumes each response once per reconstruction. Physical resource costs
    remain in the complete attempt lineage.
    """
    phase_methods = {"literature_review": "literature review", "plan_formulation": "plan formulation",
        "data_preparation": "data preparation", "running_experiments": "running experiments",
        "results_interpretation": "results interpretation", "report_writing": "report writing",
        "report_refinement": "report refinement"}

    def __init__(self, directory: Path, model_transport, tool_transport, conditions_sha256: str,
                 *, restored_cursor: dict | None = None, initial_state: dict | None = None):
        self.directory = Path(directory).resolve()
        self.model, self.tool = model_transport, tool_transport
        self.conditions_sha256 = conditions_sha256
        self.host_ordinal, self.phase = 0, "initialization"
        self.restoring_prefix = restored_cursor is not None
        self.transport_errors = []
        self.enabled = all(callable(getattr(transport, method, None)) for transport in (self.model, self.tool)
                           for method in ("configure_cursor", "export_cursor"))
        if restored_cursor and not self.enabled:
            raise ValueError("Restored transport checkpoint requires receipt-aware model and tool adapters")
        initial_path = self.directory / "transport_initial_state.json"
        self.initial_state = initial_state or {"schema_version": "transport-checkpoint-1",
            "conditions_sha256": conditions_sha256, "random_state": random.getstate(),
            "host_ordinal": 0, "model_cursor": 0, "tool_cursor": 0}
        # Round-trip tuples exactly as persisted so fresh and restored receipts hash identically.
        self.initial_state = json.loads(json.dumps(self.initial_state))
        if self.initial_state.get("conditions_sha256") != conditions_sha256:
            raise ValueError("Initial transport state has different registered conditions")
        if initial_path.exists() and json.loads(initial_path.read_text(encoding="utf-8")) != self.initial_state:
            raise ValueError("Initial transport state changed")
        if not initial_path.exists():
            atomic_json(initial_path, self.initial_state)
        self.checkpoint_sha256 = _file_hash(initial_path)
        if restored_cursor:
            if restored_cursor.get("conditions_sha256") != conditions_sha256:
                raise ValueError("Checkpoint transport conditions do not match this continuation")
            host_ordinal = restored_cursor.get("host_ordinal")
            cursors = [restored_cursor[label]["next_ordinal"] for label in ("model", "tool")]
            if (isinstance(host_ordinal, bool) or not isinstance(host_ordinal, int) or host_ordinal < 0
                    or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in cursors)
                    or sum(cursors) != host_ordinal):
                raise ValueError("Committed model/tool/action cursors are inconsistent")
            prefix = [receipt["logical_request"]["host_ordinal"] for label in ("model", "tool")
                      for receipt in restored_cursor[label]["completed_receipts"]]
            if sorted(prefix) != list(range(host_ordinal)):
                raise ValueError("Committed interleaved action cursor has an incomplete or duplicated prefix")
            self.host_ordinal = restored_cursor["host_ordinal"]
            self.checkpoint_sha256 = restored_cursor["checkpoint_sha256"]
            random.setstate(_json_tuples(restored_cursor["random_state"]))
        elif initial_state is not None:
            random.setstate(_json_tuples(self.initial_state["random_state"]))
        if self.enabled:
            for label, transport in (("model", self.model), ("tool", self.tool)):
                committed = restored_cursor[label] if restored_cursor else {"next_ordinal": 0, "completed_receipts": []}
                transport.configure_cursor(committed["next_ordinal"])
                actual = transport.export_cursor()
                if actual["completed_receipts"] != committed["completed_receipts"]:
                    raise ValueError("Committed transport prefix differs from immutable logical receipt history")

    def context(self, role: dict) -> dict:
        return {"host_ordinal": self.host_ordinal, "phase": self.phase, "role": role,
                "checkpoint_sha256": self.checkpoint_sha256}

    @staticmethod
    def caller_role(frame) -> dict:
        actor = frame.f_locals.get("self")
        return {"module": frame.f_globals.get("__name__"), "qualname": frame.f_code.co_qualname,
                "actor_class": type(actor).__name__ if actor is not None else None,
                "reviewer_type": frame.f_locals.get("reviewer_type")}

    def completed_action(self) -> None:
        self.host_ordinal += 1
        self.restoring_prefix = False

    def abort(self, error: Exception):
        self.transport_errors.append(f"{type(error).__name__}: {error}")
        raise _HostTransportAbort(error)

    def require_reconciled(self) -> None:
        if self.transport_errors:
            raise ValueError("Host transport failure cannot be replaced with upstream success: " + self.transport_errors[0])
        if self.enabled and (getattr(self.model, "logical_tail", {}) or getattr(self.tool, "logical_tail", {})):
            raise ValueError("Completed logical response tail was not consumed; restored workflow needs reconciliation")

    def install(self, upstream) -> None:
        """Wrap class methods; never attach closures or host objects to pickled instances."""
        workflow = upstream.LaboratoryWorkflow
        controller = self
        for method_name, phase in self.phase_methods.items():
            original = getattr(workflow, method_name, None)
            if original is None:
                continue
            def phase_wrapper(instance, *args, _original=original, _phase=phase, **kwargs):
                previous = controller.phase
                controller.phase = _phase
                try:
                    return _original(instance, *args, **kwargs)
                finally:
                    controller.phase = previous
            setattr(workflow, method_name, phase_wrapper)
        original_save = workflow.save_state
        def save_wrapper(instance, phase):
            return controller.save_checkpoint(upstream, original_save, instance, phase)
        workflow.save_state = save_wrapper

    def save_checkpoint(self, upstream, original_save, instance, phase) -> None:
        """Call the original save body, stage its output, then atomically publish the pair."""
        if not self.enabled:
            original_save(instance, phase)
            return
        if self.restoring_prefix:
            # The unchanged upstream driver re-saves already completed phases.
            # Do not create a new base identity before reconstructing its tail.
            return
        bundle_root = self.directory / "transport_checkpoints"
        bundle_root.mkdir(exist_ok=True)
        stage = bundle_root / f".stage-{self.host_ordinal:08d}-{time.time_ns()}"
        stage.mkdir()
        staged_pickle = stage / "workflow.pkl"
        target = self.directory / "state_saves" / f"Paper{instance.paper_index}.pkl"
        absent = object()
        prior_open = upstream.__dict__.get("open", absent)
        def checkpoint_open(path, mode="r", *args, **kwargs):
            if Path(path).resolve() == target.resolve() and mode == "wb":
                return builtins.open(staged_pickle, mode, *args, **kwargs)
            return builtins.open(path, mode, *args, **kwargs)
        upstream.__dict__["open"] = checkpoint_open
        try:
            original_save(instance, phase)
        finally:
            if prior_open is absent:
                upstream.__dict__.pop("open", None)
            else:
                upstream.__dict__["open"] = prior_open
        if not staged_pickle.exists():
            raise ValueError("Original save did not produce the expected staged checkpoint")
        with staged_pickle.open("r+b") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        checkpoint_sha = _file_hash(staged_pickle)
        def stable_cursor(transport):
            value = transport.export_cursor()
            return {"next_ordinal": value["next_ordinal"], "completed_receipts": value["completed_receipts"]}
        cursor = {"schema_version": "transport-checkpoint-1", "checkpoint_sha256": checkpoint_sha,
            "conditions_sha256": self.conditions_sha256, "host_ordinal": self.host_ordinal,
            "phase": str(phase), "model": stable_cursor(self.model), "tool": stable_cursor(self.tool),
            "random_state": random.getstate(), "initial_state_sha256": _file_hash(self.directory / "transport_initial_state.json")}
        atomic_json(stage / "cursor.json", cursor)
        cursor_sha = _file_hash(stage / "cursor.json")
        bundle = bundle_root / f"{self.host_ordinal:08d}-{_hash({'checkpoint': checkpoint_sha, 'cursor': cursor_sha})[:24]}"
        if bundle.exists():
            raise ValueError("A checkpoint bundle identity already exists; reconcile before saving again")
        os.replace(stage, bundle)
        manifest = {"schema_version": "transport-checkpoint-1",
            "checkpoint_path": (bundle / "workflow.pkl").relative_to(self.directory).as_posix(),
            "checkpoint_sha256": checkpoint_sha,
            "cursor_path": (bundle / "cursor.json").relative_to(self.directory).as_posix(), "cursor_sha256": cursor_sha}
        atomic_json(bundle / "manifest.json", manifest)
        atomic_json(self.directory / "transport_checkpoint_head.json", {
            "manifest_path": (bundle / "manifest.json").relative_to(self.directory).as_posix(),
            "manifest_sha256": _file_hash(bundle / "manifest.json")})
        # Compatibility artifact only. The committed head remains authoritative.
        target.parent.mkdir(exist_ok=True)
        temporary = target.with_suffix(".pkl.staged")
        shutil.copyfile(bundle / "workflow.pkl", temporary)
        os.replace(temporary, target)
        self.checkpoint_sha256 = checkpoint_sha


def _check_baseline_artifacts(directory: Path, result: dict) -> None:
    for filename, expected in result.get("artifact_hashes", {}).items():
        artifact = directory / filename
        if (Path(filename).is_absolute() or ".." in Path(filename).parts or
                not artifact.resolve().is_relative_to(directory.resolve()) or
                not artifact.is_file() or artifact.is_symlink() or
                hashlib.sha256(artifact.read_bytes()).hexdigest() != expected):
            raise ValueError(f"completed baseline evidence altered: {filename}")


def _resume_source(settings: dict, registration: dict, destination: Path) -> dict | None:
    """Validate only our own hash-linked checkpoint, without loading pickle yet."""
    if not settings.get("resume_from"):
        return None
    if not settings.get("retry_reason"):
        raise ValueError("checkpoint continuation requires an explicit retry_reason")
    previous = Path(settings["resume_from"]).resolve()
    project = Path(__file__).resolve().parents[1]
    if not previous.is_relative_to(project / "runs") or previous == destination:
        raise ValueError("only this workspace's own registered runs can be resumed")
    old_registration = json.loads((previous / "baseline_registration.json").read_text(encoding="utf-8"))
    old_result = json.loads((previous / "baseline_result.json").read_text(encoding="utf-8"))
    if old_result.get("status") != "failure" or old_result.get("registration_sha256") != _hash(old_registration):
        raise ValueError("resume requires a durable registered failure, not unknown execution")
    _check_baseline_artifacts(previous, old_result)
    metadata = {"retry_of", "retry_reason", "resume_from"}
    old_conditions = {k: v for k, v in old_registration["settings"].items() if k not in metadata}
    new_conditions = {k: v for k, v in settings.items() if k not in metadata}
    for field in ("kind", "commit", "task_public_sha256", "literature_sha256", "source_sha256",
                  "literature_protocol", "literature_protocol_origin"):
        if old_registration.get(field) != registration.get(field):
            raise ValueError(f"continuation changes registered {field}; register a new experiment instead")
    if old_conditions != new_conditions:
        raise ValueError("checkpoint continuation changes registered execution conditions")
    commit = _read_checkpoint_commit(previous)
    initial_path = previous / "transport_initial_state.json"
    initial_expected = old_result.get("artifact_hashes", {}).get("transport_initial_state.json")
    if initial_expected is None or not initial_path.is_file() or _file_hash(initial_path) != initial_expected:
        raise ValueError("Continuation lacks a committed initial transport/RNG state; reconcile legacy work")
    initial = json.loads(initial_path.read_text(encoding="utf-8"))
    if commit is None and (previous / "state_saves/Paper0.pkl").exists():
        raise ValueError("An original checkpoint without a committed transport cursor cannot be guessed")
    if commit is None and not old_result.get("error", "").startswith("ModelUnavailable:"):
        raise ValueError("pre-checkpoint replay requires a definitive model transport failure")
    return {"directory": str(previous), "checkpoint": commit["checkpoint"] if commit else None,
            "checkpoint_sha256": commit["manifest"]["checkpoint_sha256"] if commit else None,
            "transport_cursor": commit["cursor"] if commit else None, "initial_state": initial,
            "transport_manifest": commit["manifest"] if commit else None,
            "restore_mode": "hash_linked_phase_and_transport_checkpoint" if commit else "original_initial_state_with_completed_response_replay",
            "registration_sha256": _hash(old_registration),
            "result_sha256": hashlib.sha256((previous / "baseline_result.json").read_bytes()).hexdigest(),
            "retry_reason": settings["retry_reason"]}


class _OriginalCheckpointUnpickler(pickle.Unpickler):
    """Restore upstream data-only state; no arbitrary pickle globals are allowed."""
    allowed = {"ai_lab_repo": {"LaboratoryWorkflow"},
               "agents": {"ReviewersAgent", "PhDStudentAgent", "PostdocAgent", "ProfessorAgent",
                          "MLEngineerAgent", "SWEngineerAgent"}}

    def find_class(self, module: str, name: str):
        if name not in self.allowed.get(module, set()):
            raise pickle.UnpicklingError(f"checkpoint global is not an original agent class: {module}.{name}")
        return getattr(sys.modules[module], name)


def _stdlib_namespace() -> dict:
    return {"os": os, "sys": sys, "json": json, "time": time, "re": re,
            "math": math, "logging": logging, "random": random, "shutil": shutil,
            "pathlib": __import__("pathlib"), "Path": Path, "argparse": argparse,
            "itertools": itertools, "datetime": datetime, "date": datetime.date,
            "collections": collections, "subprocess": subprocess, "pickle": pickle,
            "copy": copy.copy, "deepcopy": copy.deepcopy, "warnings": warnings,
            "string": string, "threading": threading,
            "abstractmethod": __import__("abc").abstractmethod}


def _load_definitions(name: str, source_dir: Path, namespace: dict,
                      *, selected_functions: set[str] | None = None) -> tuple[types.ModuleType, dict]:
    path = source_dir / f"{name}.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    removed_imports = [ast.get_source_segment(source, node) for node in tree.body
                       if isinstance(node, (ast.Import, ast.ImportFrom))]
    definitions = {node.name: ast.dump(node, include_attributes=False)
                   for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    if selected_functions is None:
        tree.body = [node for node in tree.body
                     if not isinstance(node, (ast.Import, ast.ImportFrom))]
    else:
        tree.body = [node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name in selected_functions]
    module = types.ModuleType(name)
    module.__dict__.update(namespace)
    module.__dict__.update({"__name__": name, "__file__": str(path)})
    sys.modules[name] = module
    exec(compile(ast.fix_missing_locations(tree), str(path), "exec"), module.__dict__)
    retained = {node.name for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    return module, {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "omitted_top_level_imports": removed_imports,
                    "retained_definition_sha256": {
                        key: hashlib.sha256(value.encode()).hexdigest()
                        for key, value in definitions.items() if key in retained}}


@contextmanager
def _module_scope(run_dir: Path):
    names = (*SOURCE_MODULES, "common_imports", "tools", "inference", "app")
    old_modules = {name: sys.modules.get(name) for name in names}
    old_cwd = Path.cwd()
    old_environment = {name: os.environ.get(name) for name in ("JOBLIB_VERBOSITY", "TOKENIZERS_PARALLELISM")}
    old_warning_filters = list(warnings.filters)
    logger = logging.getLogger()
    old_log_level, old_handlers = logger.level, list(logger.handlers)
    sklearn_logger = logging.getLogger("sklearn.model_selection")
    old_sklearn_level = sklearn_logger.level
    old_random_state = random.getstate()
    try:
        os.chdir(run_dir)
        yield
    finally:
        os.chdir(old_cwd)
        for name, value in old_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        warnings.filters[:] = old_warning_filters
        logger.setLevel(old_log_level)
        for handler in list(logger.handlers):
            if handler not in old_handlers:
                logger.removeHandler(handler)
                handler.close()
        sklearn_logger.setLevel(old_sklearn_level)
        random.setstate(old_random_state)
        for name, previous in old_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def verify_literature_review(review: list[dict], papers: list[dict], required: int,
                             *, protocol: dict | None = None) -> dict:
    """Host contract check after the unchanged upstream pipeline has completed.

    Original len(review) completion and exact source provenance are checked.
    Repeated known-source entries remain explicit diagnostics. The shared corpus
    has its own distinct-source requirement; this does not require B to select
    every source while C receives the corpus. Neither arm's source exposure proves
    full-paper reading, comprehension, or summary factuality.
    """
    policy = validate_literature_protocol(make_literature_protocol(required, 1) if protocol is None else protocol,
                                          required_entries=required)
    if not isinstance(review, list) or not isinstance(papers, list):
        raise ValueError("Literature review and corpus must be explicit lists")
    corpus, corpus_reasons = {}, []
    for paper in papers:
        if not isinstance(paper, dict) or any(not isinstance(paper.get(key), str) or not paper[key].strip()
                                             for key in ("id", "title", "url", "text")):
            corpus_reasons.append("A registered source lacks its ID, title, URL or nonempty authored synopsis")
            continue
        if paper["id"] in corpus:
            corpus_reasons.append("The shared registered corpus contains repeated source IDs")
        corpus[paper["id"]] = paper
    entries, known_ids = [], []
    reasons = list(corpus_reasons)
    for entry in review:
        entry = entry if isinstance(entry, dict) else {}
        identifier = entry.get("arxiv_id")
        paper = corpus.get(identifier) if isinstance(identifier, str) else None
        text = entry.get("full_text", "")
        source_matches = bool(paper and isinstance(text, str) and text.strip() and text == paper["text"])
        entries.append({"identifier": identifier, "identifier_schema": "adapter-local bibliographic ID; legacy upstream field is named arxiv_id",
            "summary": entry.get("summary", ""), "summary_kind": "model_authored_literature_claim",
            "source_membership": paper is not None, "source_url": paper.get("url") if paper else None,
            "retrieved_source_synopsis_sha256": hashlib.sha256(str(text).encode("utf-8")).hexdigest(),
            "source_synopsis_matches_registered_record": source_matches})
        if paper and source_matches:
            known_ids.append(identifier)
        else:
            reasons.append("A review entry lacks matching registered source-synopsis evidence")
    distinct = len(set(known_ids))
    if len(corpus) < policy["required_shared_corpus_distinct_records"]:
        reasons.append("The shared registered corpus lacks its declared distinct source records")
    if len(review) < required:
        reasons.append("The upstream review lacks the original minimum number of review entries")
    return {"kind": "host_literature_contract_verification", "valid": not reasons,
            "literature_protocol": policy, "original_minimum_review_entries": required,
            "original_review_entry_count": len(review), "provenance_verified_review_entries": len(known_ids),
            "original_entry_count_satisfies_minimum": len(review) >= required,
            "shared_corpus_distinct_records": len(corpus), "distinct_verified_source_records": distinct,
            "duplicate_source_entries": len(known_ids) - distinct, "entries": entries,
            "selection_integrity_diagnostics": {"duplicates_are_common_task_failure": False,
                "unselected_shared_source_ids": [identifier for identifier in corpus if identifier not in known_ids],
                "interpretation": "Original selected review-entry count and source coverage; no automatic scientific-quality or comprehension judgment."},
            "corpus_sha256": _hash(papers), "reasons": reasons,
            "scope": "Access to frozen bibliographic metadata and short authored source synopses. This is not proof of full-paper reading, summary factuality, or research performance."}


class SnapshotLiterature:
    """Deterministic reference tool, shared with the improved arm by the caller."""
    def __init__(self, papers: list[dict], audit: Callable[[dict], None]):
        self.papers, self.audit = papers, audit

    def find_papers_by_str(self, query: str, N: int = 5) -> str:
        self.audit({"kind": "literature_search", "query": str(query), "requested": N})
        query_terms = set(re.findall(r"\w+", str(query).lower()))
        ranked = sorted(self.papers, key=lambda paper: -len(query_terms.intersection(
            re.findall(r"\w+", (paper.get("title", "") + " " + paper.get("abstract", "")).lower()))))
        return "\n\n".join(
            f"Title: {paper['title']}\nSummary: {paper.get('abstract', '')}\n"
            f"arXiv paper ID (legacy command field; may be adapter-local bibliographic ID): {paper['id']}\nSource: {paper.get('url', '')}\n"
            "Evidence status: literature claim; not independently verified here."
            for paper in ranked[:N])

    def retrieve_full_paper_text(self, identifier: str) -> str:
        self.audit({"kind": "literature_full_text", "id": str(identifier)})
        for paper in self.papers:
            if paper["id"] == str(identifier).strip():
                text = paper.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("Registered literature record lacks a nonempty authored source synopsis")
                return text
        return "Paper ID not found in the fixed literature snapshot."


def run_upstream_baseline(task_public: dict, run_dir: Path,
                          query_model: Callable[..., str],
                          execute_code: Callable[[str], str], settings: dict,
                          *, literature: list[dict], source_dir: Path | None = None) -> dict:
    """Execute the complete upstream phase pipeline against caller-owned tools.

    ``settings`` must preregister model, max_steps, mlesolver_max_steps,
    papersolver_max_steps, and num_papers_lit_review. These are evaluation resource
    settings, never a stopping condition for the overall research goal.
    The callback must run actual task work, retain artifacts, and enforce the same
    tool restrictions as C. This module does not sandbox generated Python itself.
    AgentRxiv's original PDF/web backend is deliberately unsupported by this CPU
    adapter. Its memory effect requires a separately identified experiment.
    """
    required = {"model", "max_steps", "mlesolver_max_steps", "papersolver_max_steps",
                "num_papers_lit_review"}
    if not required.issubset(settings):
        raise ValueError("preregister baseline resource settings: " + ", ".join(sorted(required)))
    if settings.get("agentRxiv", False):
        raise ValueError("original AgentRxiv PDF/web backend is not supported by this adapter")
    if settings["max_steps"] < 2 or settings["mlesolver_max_steps"] < 1:
        raise ValueError("upstream requires max_steps >= 2 and mlesolver_max_steps >= 1")
    if settings["papersolver_max_steps"] < 0 or settings["num_papers_lit_review"] < 1:
        raise ValueError("invalid upstream phase resource settings")
    # Standalone host fixtures retain a declared c6 policy. Registered comparisons
    # must supply the explicit shared-corpus policy through their envelope.
    literature_protocol = validate_literature_protocol(settings.get("literature_protocol",
        make_literature_protocol(settings["num_papers_lit_review"], 1)),
        required_entries=settings["num_papers_lit_review"])
    source_dir = Path(source_dir or Path(__file__).resolve().parents[1] / "references" /
                      "upstream" / f"AgentLaboratory-{UPSTREAM_COMMIT}").resolve()
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    registration = {"kind": "upstream_actual_adapted", "commit": UPSTREAM_COMMIT,
                    "task_public_sha256": _hash(task_public), "settings": settings,
                    "literature_sha256": _hash(literature),
                    "literature_protocol": literature_protocol,
                    "literature_protocol_origin": "explicit_registered_envelope" if "literature_protocol" in settings
                        else "unregistered_standalone_candidate_default",
                    "source_sha256": {name: hashlib.sha256((source_dir / f"{name}.py").read_bytes()).hexdigest()
                                      for name in SOURCE_MODULES}}
    continuation = _resume_source(settings, registration, run_dir)
    if continuation:
        registration["continuation"] = continuation
    registration_hash = _hash(registration)
    registration_path = run_dir / "baseline_registration.json"
    result_path = run_dir / "baseline_result.json"
    existing_registration = registration_path.exists()
    if registration_path.exists():
        if _hash(json.loads(registration_path.read_text(encoding="utf-8"))) != registration_hash:
            raise ValueError("existing baseline registration differs; use a new run directory")
    else:
        _write_json(registration_path, registration)
    if result_path.exists():
        previous = json.loads(result_path.read_text(encoding="utf-8"))
        _check_baseline_artifacts(run_dir, previous)
        return {**previous, "resumed_without_execution": True}
    if existing_registration:
        return {"kind": "upstream_actual_adapted", "status": "unknown_execution",
                "registration_sha256": registration_hash, "resumed_without_execution": True,
                "error": "Prior registration has no durable final result; do not repeat unknown work.",
                "next_action": "Reconcile existing artifacts or preregister changed conditions and retry_reason in a new directory."}

    audit_path = run_dir / "baseline_events.jsonl"
    events: list[dict] = []
    transport: TransportCheckpointController | None = None
    def audit(event: dict) -> None:
        event = {"event_index": len(events), **event}
        events.append(event)
        with audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def provider_bridge(*args, **kwargs):
        # API credentials are unnecessary for a caller-owned model transport.
        safe = {key: value for key, value in kwargs.items() if "key" not in key.lower()}
        if transport and transport.enabled:
            safe["_logical_context"] = transport.context(transport.caller_role(sys._getframe(1)))
        try:
            response = query_model(*args, **safe)
        except Exception as error:
            if transport and transport.enabled:
                transport.abort(error)
            raise
        if transport:
            transport.completed_action()
        audit({"kind": "model_call", "model": safe.get("model_str", settings["model"]),
               "prompt_sha256": _hash({"args": args, "kwargs": safe}),
               "response_sha256": hashlib.sha256(response.encode()).hexdigest()})
        return response

    def execute_bridge(code: str, *args, **kwargs) -> str:
        before = getattr(execute_code, "completed", None)
        if transport and transport.enabled:
            execute_code.set_logical_context(transport.context(transport.caller_role(sys._getframe(1))))
        try:
            result = execute_code(code)
        except Exception as error:
            if transport and transport.enabled:
                transport.abort(error)
            raise
        if transport:
            transport.completed_action()
        after = getattr(execute_code, "completed", None)
        delta = len(after) - len(before) if isinstance(before, list) and isinstance(after, list) else None
        audit({"kind": "actual_execution_callback", "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
               "output_sha256": hashlib.sha256(result.encode()).hexdigest(),
               "new_actual_cpu_executions": delta,
               "scope": "callback invocation; cached replies and rejected code need not execute a new task"})
        return result

    class FrozenHFSearch:
        def retrieve_ds(self, query, *args, **kwargs):
            audit({"kind": "dataset_search", "query": str(query)})
            return [task_public]
        def results_str(self, results):
            return [json.dumps({"source": "fixed task owner's training and validation data",
                                "task": result}, ensure_ascii=False) for result in results]

    namespace = _stdlib_namespace()
    namespace.update({"query_model": provider_bridge, "execute_code": execute_bridge,
                      "ArxivSearch": lambda: SnapshotLiterature(literature, audit),
                      "HFDataSearch": FrozenHFSearch, "curr_cost_est": lambda: None})
    adaptations = ["top-level optional imports replaced by explicit stdlib/tool namespace",
                   "current model transport supplied by caller for every upstream model request",
                   "Python execution supplied by shared restricted actual-task tool",
                   "arXiv and HuggingFace search use frozen task/literature snapshots",
                   "direct LaboratoryWorkflow invocation supplies missing report globals",
                   "compile_pdf=False; original LaTeX source generation remains active",
                   "AgentRxiv PDF/web backend disabled; no claim of its reproduction",
                   "original code/report selection retains upstream LLM reward functions"]
    adaptations.append("source import environment/warning/logging/random side effects restored after serialized invocation")
    adaptations.append("class-level host wrappers commit original pickle with model/tool/action cursors and RNG state; pinned phase and solver definitions remain unchanged")
    adaptations.append("versioned host literature protocol separates shared distinct corpus exposure from original review-list length; known-source duplicate review entries remain diagnostics, without deduplication or extra original-workflow feedback")
    started = time.perf_counter()
    source_metadata = {}
    result = {"kind": "upstream_actual_adapted", "registration_sha256": registration_hash,
              "commit": UPSTREAM_COMMIT, "adaptations": adaptations,
              "cost": {"provider_billed_cost": None}, "status": "failure"}
    with _RUN_LOCK, _module_scope(run_dir), (run_dir / "baseline_stdout.log").open("a", encoding="utf-8") as log:
        with redirect_stdout(log), redirect_stderr(log):
            try:
                for subdir in ("state_saves", "lab/src", "lab/tex"):
                    (run_dir / subdir).mkdir(parents=True, exist_ok=True)
                utils, source_metadata["utils"] = _load_definitions(
                    "utils", source_dir, namespace,
                    selected_functions={"extract_prompt", "compile_latex", "remove_figures", "save_to_file"})
                namespace.update({key: value for key, value in vars(utils).items() if not key.startswith("__")})
                agents, source_metadata["agents"] = _load_definitions("agents", source_dir, namespace)
                mle, source_metadata["mlesolver"] = _load_definitions("mlesolver", source_dir, namespace)
                paper_namespace = {**namespace, "get_score": agents.get_score}
                _, source_metadata["papersolver"] = _load_definitions("papersolver", source_dir, paper_namespace)
                workflow_namespace = {**namespace,
                    **{key: value for key, value in vars(agents).items() if not key.startswith("__")},
                    "MLESolver": mle.MLESolver, "research_topic": task_public.get("objective", "research task"),
                    "compile_pdf": False}
                upstream, source_metadata["ai_lab_repo"] = _load_definitions("ai_lab_repo", source_dir, workflow_namespace)
                conditions = {key: value for key, value in registration.items() if key != "continuation"}
                conditions["settings"] = {key: value for key, value in settings.items()
                    if key not in {"retry_of", "retry_reason", "resume_from"}}
                transport = TransportCheckpointController(run_dir, query_model, execute_code, _hash(conditions),
                    restored_cursor=continuation.get("transport_cursor") if continuation else None,
                    initial_state=continuation.get("initial_state") if continuation else None)
                transport.install(upstream)
                result["transport_checkpoint_schema"] = "transport-checkpoint-1" if transport.enabled else "legacy_callback_without_transport_receipts"
                if continuation:
                    audit({"kind": "transport_prefix_validated", "host_ordinal": transport.host_ordinal,
                        "checkpoint_sha256": transport.checkpoint_sha256,
                        "model_cursor": query_model.export_cursor() if transport.enabled else None,
                        "tool_cursor": execute_code.export_cursor() if transport.enabled else None})
                phases = ["literature review", "plan formulation", "data preparation", "running experiments",
                          "results interpretation", "report writing", "report refinement"]
                task_note = ("Use only the fixed public task and caller-provided execution tool. "
                             "The tool permissions and resources are identical to the improved arm. "
                             "Hidden test data and evaluator answers are unavailable. "
                             "Follow these execution instructions: " + settings.get("execution_instructions", "") +
                             "\nPublic task: " + json.dumps(task_public, ensure_ascii=False))
                notes = [{"phases": phases, "note": task_note}] + settings.get("notes", [])
                models = {phase: settings["model"] for phase in phases}
                if continuation and continuation["checkpoint_sha256"]:
                    previous = Path(continuation["directory"])
                    for dirname in ("lab", "state_saves"):
                        shutil.copytree(previous / dirname, run_dir / dirname, dirs_exist_ok=True)
                    checkpoint = Path(continuation["checkpoint"])
                    # The artifact inventory was checked before copying, and the
                    # unpickler can construct only seven pinned upstream classes.
                    with checkpoint.open("rb") as stream:
                        lab = _OriginalCheckpointUnpickler(stream).load()
                    if type(lab) is not upstream.LaboratoryWorkflow or lab.openai_api_key is not None:
                        raise ValueError("checkpoint is not our credential-free upstream workflow")
                    result["continuation"] = continuation
                    result["resumed_phase_status"] = dict(lab.phase_status)
                    audit({"kind": "checkpoint_restored", **continuation,
                           "completed_phases": [phase for phase, done in lab.phase_status.items() if done]})
                else:
                    lab = upstream.LaboratoryWorkflow(
                        research_topic=task_public.get("objective", "research task"), openai_api_key=None,
                        max_steps=settings["max_steps"], num_papers_lit_review=settings["num_papers_lit_review"],
                        agent_model_backbone=models, notes=notes, human_in_loop_flag={phase: False for phase in phases},
                        compile_pdf=False, mlesolver_max_steps=settings["mlesolver_max_steps"],
                        papersolver_max_steps=settings["papersolver_max_steps"], except_if_fail=True,
                        lab_dir="lab", agentRxiv=False)
                    if continuation:
                        result["continuation"] = continuation
                        result["resumed_phase_status"] = dict(lab.phase_status)
                        audit({"kind": "original_initial_state_restored_for_cache_replay", **continuation,
                               "completed_phases": []})
                # Original phase/solver implementations call the original save body through
                # a class wrapper. The checkpoint/cursor pair is the authoritative receipt.
                lab.perform_research()
                transport.require_reconciled()
                result.update({"status": "success", "phase_status": lab.phase_status,
                               "plan": lab.phd.plan, "code": lab.phd.results_code,
                               "experiment_output": lab.phd.exp_results, "report": lab.phd.report,
                               "statistics_per_phase": lab.statistics_per_phase})
                result["upstream_algorithm_status"] = "success"
                literature_check = verify_literature_review(lab.phd.lit_review, literature,
                    settings["num_papers_lit_review"], protocol=literature_protocol)
                result["literature_contract_verification"] = literature_check
                audit(literature_check)
                if not literature_check["valid"]:
                    result.update(status="failure", failure_classification="host_literature_contract_failure",
                                  error="HostLiteratureContractError: " + "; ".join(literature_check["reasons"]))
            except (Exception, _HostTransportAbort) as exc:
                if isinstance(exc, _HostTransportAbort):
                    exc = exc.cause
                result["error"] = f"{type(exc).__name__}: {exc}"
                audit({"kind": "baseline_failure", "error": result["error"]})
                import traceback
                traceback.print_exc()
    result.update({"elapsed_seconds": time.perf_counter() - started,
                   "source_metadata": source_metadata, "event_count": len(events),
                   "execution_count": sum(e["kind"] == "actual_execution_callback" for e in events),
                   "execution_count_scope": "tool callback invocations; physical CPU attempts are separately audited",
                   "new_actual_cpu_executions": sum(e["new_actual_cpu_executions"] for e in events
                       if e["kind"] == "actual_execution_callback") if all(
                       e.get("new_actual_cpu_executions") is not None for e in events
                       if e["kind"] == "actual_execution_callback") else None,
                   "model_call_count": sum(e["kind"] == "model_call" for e in events),
                   "log": str(run_dir / "baseline_stdout.log"), "events": str(audit_path),
                   "metric_status": "upstream LLM scores are judgments; use the independent fixed evaluator for task metrics"})
    result["artifact_hashes"] = {path.relative_to(run_dir).as_posix():
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in run_dir.rglob("*") if path.is_file() and not path.is_symlink()
        and path != result_path}
    _write_json(result_path, result)
    return result
