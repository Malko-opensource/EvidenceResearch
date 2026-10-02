"""Actual upstream baseline tools confined to literal polynomial configurations.

Generated text is parsed, never executed. Caller-owned trusted task and verifier
perform the experiment. Raw Codex calls retain provider execution evidence.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Callable

from .baseline import run_upstream_baseline
from .model import CodexProvider, ModelUnavailable, digest
from .tasks import make_spec, public_task, run_task, sha256_file, validate_config, write_json
from .verifier import verify

TOOL_CONTRACT = (
    "The host has already supplied the public task's fixed training and validation data. "
    "Use only a literal CONFIG assignment, e.g. CONFIG = {'degree': 1, 'alpha': 0.0}, "
    "or the standalone call run_candidate({'degree': 1, 'alpha': 0.0}). "
    "The host parses these actions and runs actual polynomial ridge training and validation. "
    "No imports, loops, functions, arithmetic expressions, filesystem access, print, or other Python "
    "statements are allowed. Do not include the example configuration unless you selected it. "
    "A DATA PREPARATION SUBMIT_CODE must also use a valid CONFIG assignment; data are preloaded. "
    "For MLE-Solver REPLACE or EDIT, use only these same literal configuration statements. "
    "The only legal configuration fields are degree (integer 1..8) and alpha (finite 0..100). "
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
                 prior_records: list[dict] | None = None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.spec_factory, self.runner, self.verifier = spec_factory, runner, verifier
        self.events_path = self.directory / "tool_events.jsonl"
        self.records = list(prior_records or []) + ([json.loads(line) for line in self.events_path.read_text(encoding="utf-8").splitlines()
                        if line.strip()] if self.events_path.exists() else [])

    def _record(self, item: dict) -> None:
        self.records.append(item)
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")

    def __call__(self, code: str) -> str:
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
        identity = digest({"task": spec["task_id"], "seed": spec["seed"], "config": candidate,
                           "split": spec["split_manifest_sha256"]})
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
        return json.dumps({"execution_kind": "actual_cpu_execution", "config": candidate,
                           "metrics": result["metrics"], "artifacts": result["artifacts"],
                           "independent_verification": "valid", "test_access": "withheld"}, allow_nan=False)

    @property
    def completed(self) -> list[dict]:
        return [item for item in self.records if item.get("actual_task_executed")]


class UpstreamCodexBridge:
    def __init__(self, provider: CodexProvider, directory: Path, *, max_model_calls: int,
                 replay_directories: list[Path] | None = None):
        self.provider = provider
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_model_calls = max_model_calls
        self.calls = []
        self.path = self.directory / "model_transport_events.jsonl"
        self.replay, self.prior_evidence = {}, []
        self.prior_attempts = 0
        self.no_action_receipts = []
        for previous in replay_directories or []:
            for folder in sorted((Path(previous) / "model").glob("*/request.json")):
                folder = folder.parent.resolve()
                result_path = folder / "result.json"
                if not result_path.exists():
                    raise ModelUnavailable("Unknown prior model execution cannot be retried automatically")
                record = json.loads(result_path.read_text(encoding="utf-8"))
                CodexProvider._check_files(folder, record)
                request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
                if request.get("model") != provider.model or record.get("model") != provider.model:
                    raise ValueError("checkpoint model evidence differs from the current model")
                self.prior_attempts += 1
                self.prior_evidence.append(str(folder))
                if record["status"] == "completed":
                    response_path = folder / "response.txt"
                    if record.get("tool_calls") or record.get("execution_kind") != "real_model":
                        raise ValueError("prior cache is not a tool-free real model completion")
                    key = hashlib.sha256(request["prompt"].encode()).hexdigest()
                    self.replay.setdefault(key, {"response": response_path.read_text(encoding="utf-8"),
                        "evidence_dir": str(folder), "model_evidence": {**record,
                            "evidence_record": CodexProvider._record_link(folder)}})
                else:
                    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
                    if (not any(event.get("type") == "turn.failed" for event in events)
                            or record.get("tool_calls")):
                        raise ModelUnavailable("Prior failure has no definitive no-action receipt; reconcile before retry")
                    self._no_action_receipt(folder, f"prior-{self.prior_attempts:04d}",
                        "Resume a definitive provider turn.failed with unchanged registered conditions; prior response was never returned to upstream.")

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
        cached = self.replay.get(request_sha)
        attempts = self.prior_attempts + sum(not item.get("reused_completed_evidence") for item in self.calls)
        if cached is None and attempts >= self.max_model_calls:
            raise ModelUnavailable("Preregistered per-unit model-call resources exhausted; research goal remains incomplete")
        event = {"call_id": call_id, "original_requested_model": model_str,
                 "actual_model": self.provider.model, "original_requested_temperature": temp,
                 "temperature_policy": "Codex CLI does not expose temperature; same policy required for C",
                 "request_sha256": request_sha, "status": "requested",
                 "reused_completed_evidence": cached is not None}
        self.calls.append(event)
        try:
            if cached:
                event.update({"status": "completed", "evidence_dir": cached["evidence_dir"],
                              "model_evidence": cached["model_evidence"]})
                return cached["response"]
            answer = self.provider.complete(request, call_id=call_id, json_response=False)
            event.update({"status": "completed", "evidence_dir": str(self.provider.evidence_dir / call_id),
                          "model_evidence": self.provider.last_evidence})
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
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")


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
        output = Path(arm_output).resolve()
        output.mkdir(parents=True, exist_ok=True)
        public, envelope, criterion = self._public_payload(payload)
        settings = development_envelope(payload["model_id"])
        settings.update(envelope.get("upstream_settings", {}))
        settings.update(model=payload["model_id"], max_model_calls=envelope["proposal_calls_per_unit"],
                        reasoning_effort=envelope.get("reasoning_effort"), execution_instructions=TOOL_CONTRACT)
        registration = {"payload_sha256": digest(payload), "public_task": public,
                        "settings": settings, "implementation_sha256": sha256_file(Path(__file__)),
                        "kind": "upstream_actual_adapted", "source_commit": __import__(
                            "evidence_research.baseline", fromlist=["UPSTREAM_COMMIT"]).UPSTREAM_COMMIT,
                        "stopping_criterion": criterion,
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
                    "independent_review_pending": not (output / "report-review.json").exists()}
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
                records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        provider = self.provider_factory(evidence_dir=attempt / "model", model=payload["model_id"],
            reasoning_effort=envelope.get("reasoning_effort"), public_dir=attempt / "public_model_cwd")
        actual = getattr(provider, "execution_kind", None) == "real_model"
        def spec_factory(config):
            spec = make_spec(public["task_id"], public["seed"], config, model=payload["model_id"],
                criterion=criterion, resource_envelope=envelope, task_bundle=public["task_bundle"],
                hypothesis="Pinned upstream agent selected a literal polynomial ridge configuration.")
            if "threshold" not in criterion:
                spec["role"] = "baseline"
            return spec
        tool = AllowlistedExperimentTool(attempt / "experiments", spec_factory, prior_records=records)
        bridge = UpstreamCodexBridge(provider, attempt, max_model_calls=envelope["proposal_calls_per_unit"],
                                    replay_directories=lineage)
        baseline = run_upstream_baseline(public, attempt / "upstream", bridge, tool, settings,
                                         literature=frozen_literature())
        if baseline["status"] != "success":
            error = baseline.get("error", "upstream pipeline did not complete")
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
        inventory_path = output / "numeric-inventory.json"
        if not inventory_path.exists():
            prepare_numeric_review(report_path, inventory_path)
        numeric_hints = audit_report_numbers(baseline["report"], tool.completed, public["task_bundle"])
        write_json(output / "claim-evidence-hints.json", numeric_hints)
        trace_path = output / "model-transport.jsonl"
        trace_paths = [ancestor / "model_transport_events.jsonl" for ancestor in lineage] + [bridge.path]
        trace_path.write_text("".join(path.read_text(encoding="utf-8") for path in trace_paths if path.exists()), encoding="utf-8")
        all_dirs = list(dict.fromkeys(bridge.prior_evidence + [str(path.parent) for path in sorted((attempt / "model").glob("*/result.json"))]))
        completed_dirs, failed_dirs = [], []
        for value in all_dirs:
            record = json.loads((Path(value) / "result.json").read_text(encoding="utf-8"))
            (completed_dirs if record["status"] == "completed" else failed_dirs).append(value)
        pending_error, recovered = False, 0
        for event in tool.records:
            if event["status"] == "rejected_code" or event.get("actual_task_executed") and event["status"] == "failure":
                pending_error = True
            elif pending_error and event.get("actual_task_executed") and event["status"] == "success":
                recovered += 1
                pending_error = False
        evidence_paths = [receipt, trace_path, inventory_path, output / "claim-evidence-hints.json",
                          attempt / "upstream" / "baseline_result.json"]
        evidence_paths += [ancestor / "experiments" / "tool_events.jsonl" for ancestor in lineage]
        evidence_paths += [tool.events_path] if tool.events_path.exists() else []
        telemetry = {"provenance": "trusted_host_audit",
                     "duplicate_executions": sum(bool(run["duplicate_configuration"]) for run in tool.completed),
                     "recovered_errors": recovered, "verified_memory_hits": 0, "unsupported_claims": 0,
                     "unsupported_count_scope": "Pending independent whole-report adjudication; zero is not an accepted report conclusion",
                     "external_model_failures": len(failed_dirs),
                     "external_checkpoint_recoveries": len(lineage),
                     "claim_audit_scope": "whole_report_numeric_inventory_pending_independent_adjudication",
                     "sources": [{"path": str(path), "sha256": sha256_file(path)} for path in evidence_paths if path.exists()],
                     "report_path": str(report_path), "report_sha256": sha256_file(report_path)}
        write_json(output / "telemetry.json", telemetry)
        lineage_path = output / "continuation-lineage.json"
        write_json(lineage_path, {"provenance": "trusted_host_audit", "current_arm_output": str(output),
            "current_attempt": str(attempt), "retry_reason": self.continuation_reason,
            "previous_results": [{"path": str(ancestor / "upstream" / "baseline_result.json"),
                "sha256": sha256_file(ancestor / "upstream" / "baseline_result.json")} for ancestor in lineage],
            "failed_model_attempt_dirs": failed_dirs,
            "failed_request_fingerprints": [json.loads((Path(path) / "request.json").read_text(encoding="utf-8"))["fingerprint"] for path in failed_dirs],
            "completed_response_cache_scope": "prompt-identical raw completion reuse; never a second actual model execution"})
        self._maybe_review(output)
        response = {"model_id": payload["model_id"], "resource_envelope": envelope,
                    "model_execution_kind": "actual_model_execution" if actual else "simulation_fixture",
                    "selected_run_dir": selected["run_dir"], "model_trace_path": str(trace_path),
                    "model_evidence_dirs": completed_dirs, "failed_model_evidence_dirs": failed_dirs,
                    "failed_model_attempt_dirs": failed_dirs,
                    "failed_model_host_receipts": bridge.no_action_receipts,
                    "continuation_lineage_path": str(lineage_path),
                    "telemetry_evidence_path": str(output / "telemetry.json"), "report_path": str(report_path),
                    "numeric_inventory_path": str(inventory_path),
                    "independent_review_pending": not (output / "report-review.json").exists(),
                    "comparison_improvement_claim": False, "baseline_result_path": str(attempt / "upstream" / "baseline_result.json")}
        self._verify_selected(response)
        write_json(response_path, response)
        return response

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
        review_path = output / "report-review.json"
        if self.independent_reviewer and not review_path.exists():
            self.independent_reviewer(output / "numeric-inventory.json", review_path)
        if not review_path.exists():
            return
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if review.get("reviewer_role") != "independent_verifier" or review.get("status") != "complete" or review.get("pending_claims") != 0:
            raise ValueError("Supplied report review is not complete independent adjudication")
        if review.get("report_sha256") != sha256_file(output / "report.txt") or review.get("inventory_sha256") != sha256_file(output / "numeric-inventory.json"):
            raise ValueError("Independent review refers to changed upstream report/inventory")
        telemetry_path = output / "telemetry.json"
        telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
        telemetry.update(report_review_path=str(review_path), report_review_sha256=sha256_file(review_path),
                         unsupported_claims=review["unsupported_claims"], claim_audit_scope="whole_report_numeric_inventory")
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
