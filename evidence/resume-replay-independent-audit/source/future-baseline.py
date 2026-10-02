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

UPSTREAM_COMMIT = "d9017d90e329112d2a80b7712f37ee9094d2cd27"
SOURCE_MODULES = ("utils", "agents", "mlesolver", "papersolver", "ai_lab_repo")
_RUN_LOCK = threading.RLock()


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                    + "\n", encoding="utf-8")


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
    for field in ("kind", "commit", "task_public_sha256", "literature_sha256", "source_sha256"):
        if old_registration.get(field) != registration.get(field):
            raise ValueError(f"continuation changes registered {field}; register a new experiment instead")
    if old_conditions != new_conditions:
        raise ValueError("checkpoint continuation changes registered execution conditions")
    filename = "state_saves/Paper0.pkl"
    checkpoint = previous / filename
    expected = old_result.get("artifact_hashes", {}).get(filename)
    if expected is not None and checkpoint.stat().st_size > 10_000_000:
        raise ValueError("a bounded hash-linked original checkpoint is required")
    if expected is None and not old_result.get("error", "").startswith("ModelUnavailable:"):
        raise ValueError("pre-checkpoint replay requires a definitive model transport failure")
    return {"directory": str(previous), "checkpoint": str(checkpoint),
            "checkpoint_sha256": expected,
            "restore_mode": "original_phase_checkpoint" if expected else "original_initial_state_with_completed_response_replay",
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


def verify_literature_review(review: list[dict], papers: list[dict], required: int) -> dict:
    """Host contract check after the unchanged upstream pipeline has completed.

    This checks distinct membership and source-synopsis provenance, not whether a
    model read or understood a full paper. Summaries remain model-authored claims.
    """
    corpus = {paper["id"]: paper for paper in papers}
    entries, known_ids = [], []
    reasons = []
    for entry in review:
        identifier = entry.get("arxiv_id")
        paper = corpus.get(identifier)
        text = entry.get("full_text", "")
        source_matches = bool(paper and text == paper.get("text", paper.get("abstract", "")))
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
    if len(known_ids) != distinct:
        reasons.append("Repeated literature identifiers cannot satisfy the distinct-paper requirement")
    if distinct < required:
        reasons.append("The upstream review does not contain the registered number of distinct source records")
    return {"kind": "host_literature_contract_verification", "valid": not reasons,
            "required_distinct_records": required, "distinct_verified_source_records": distinct,
            "duplicate_source_entries": len(known_ids) - distinct, "entries": entries,
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
                return paper.get("text", paper.get("abstract", ""))
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
    source_dir = Path(source_dir or Path(__file__).resolve().parents[1] / "references" /
                      "upstream" / f"AgentLaboratory-{UPSTREAM_COMMIT}").resolve()
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    registration = {"kind": "upstream_actual_adapted", "commit": UPSTREAM_COMMIT,
                    "task_public_sha256": _hash(task_public), "settings": settings,
                    "literature_sha256": _hash(literature),
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
    def audit(event: dict) -> None:
        event = {"event_index": len(events), **event}
        events.append(event)
        with audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")

    def provider_bridge(*args, **kwargs):
        # API credentials are unnecessary for a caller-owned model transport.
        safe = {key: value for key, value in kwargs.items() if "key" not in key.lower()}
        response = query_model(*args, **safe)
        audit({"kind": "model_call", "model": safe.get("model_str", settings["model"]),
               "prompt_sha256": _hash({"args": args, "kwargs": safe}),
               "response_sha256": hashlib.sha256(response.encode()).hexdigest()})
        return response

    def execute_bridge(code: str, *args, **kwargs) -> str:
        before = getattr(execute_code, "completed", None)
        result = execute_code(code)
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
                # Keep the original phase/solver implementations, including original checkpoints.
                lab.perform_research()
                result.update({"status": "success", "phase_status": lab.phase_status,
                               "plan": lab.phd.plan, "code": lab.phd.results_code,
                               "experiment_output": lab.phd.exp_results, "report": lab.phd.report,
                               "statistics_per_phase": lab.statistics_per_phase})
                result["upstream_algorithm_status"] = "success"
                literature_check = verify_literature_review(lab.phd.lit_review, literature,
                                                           settings["num_papers_lit_review"])
                result["literature_contract_verification"] = literature_check
                audit(literature_check)
                if not literature_check["valid"]:
                    result.update(status="failure", failure_classification="host_literature_contract_failure",
                                  error="HostLiteratureContractError: " + "; ".join(literature_check["reasons"]))
            except Exception as exc:
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
