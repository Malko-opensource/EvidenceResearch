"""Audited real model calls using an existing Codex login; no copied credentials."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid


class ModelUnavailable(RuntimeError):
    pass


class PreregisteredResourcesExhausted(RuntimeError):
    """This evaluation unit used its declared allowance before completing.

    This is a measured task-level budget outcome. It does not mean the provider
    is unavailable, authorize a larger allowance or stop the research Goal.
    Cached completed work remains reusable within its original registration.
    """


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def parse_object(text):
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Model response must be a JSON object")
    return value


class CodexProvider:
    """Filesystem-free model proposals with raw response and usage evidence.

    Tools are forbidden by prompt and any observed tool invocation invalidates
    the call. Read-only OS sandbox protects writes. This audit does not claim
    arbitrary filesystem reads are technically unavailable to Codex.
    """

    execution_kind = "real_model"
    guard = ("Return the requested response directly. Do not call any tools, read files, "
             "browse, execute commands, or inspect environment. You are a proposal-only "
             "model; the trusted host performs experiments and evaluates results. "
             "Never fabricate measurements.\n\n")

    def __init__(self, evidence_dir, model="gpt-6.1-sol", executable=None,
                 reasoning_effort=None, public_dir=None):
        self.evidence_dir = Path(evidence_dir).resolve()
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.public_dir = Path(public_dir or self.evidence_dir / "public").resolve()
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.executable = executable or shutil.which("codex")
        self.reasoning_effort = reasoning_effort
        self.last_evidence = None
        if not self.executable:
            raise ModelUnavailable("Install Codex CLI and authenticate with codex login")

    def complete(self, prompt, *, call_id=None, json_response=False):
        call_id = call_id or uuid.uuid4().hex
        if not call_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in call_id):
            raise ValueError("Invalid model call id")
        folder = self.evidence_dir / call_id
        identity = {"model": self.model, "prompt": prompt,
                    "full_prompt": self.guard + prompt,
                    "provider_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "reasoning_effort": self.reasoning_effort}
        fingerprint = digest(identity)
        if folder.exists():
            request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
            if request["fingerprint"] != fingerprint:
                raise ValueError("Call id reused with a different request")
            record = folder / "result.json"
            if not record.exists():
                raise ModelUnavailable("Unknown prior execution; reconcile evidence before retry")
            result = json.loads(record.read_text(encoding="utf-8"))
            self._check_files(folder, result)
            self.last_evidence = {**result, "evidence_record": self._record_link(folder)}
            if result["status"] != "completed":
                raise ModelUnavailable(result["reason"])
            answer = (folder / "response.txt").read_text(encoding="utf-8")
            return parse_object(answer) if json_response else answer
        folder.mkdir()
        final = folder / "response.txt"
        command = [self.executable, "exec", "--ignore-user-config", "--ephemeral",
                   "--skip-git-repo-check", "--sandbox", "read-only", "--model",
                   self.model, "--cd", str(self.public_dir), "--json",
                   "-c", 'approval_policy="never"', "--output-last-message", str(final)]
        if self.reasoning_effort:
            command += ["-c", f'model_reasoning_effort="{self.reasoning_effort}"']
        command.append("-")
        request = {"fingerprint": fingerprint, **identity, "command": command,
                   "execution_kind": self.execution_kind}
        (folder / "request.json").write_text(_json(request), encoding="utf-8")
        start = time.monotonic()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            process = subprocess.run(command, input=identity["full_prompt"], text=True,
                                     encoding="utf-8", errors="replace", env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     cwd=self.public_dir, check=False)
        except OSError as error:
            process = None
            error_message = f"{type(error).__name__}: {error}"
        if process is None:
            stdout, stderr, returncode = "", error_message, None
        else:
            stdout, stderr, returncode = process.stdout, process.stderr, process.returncode
        (folder / "events.jsonl").write_text(stdout, encoding="utf-8")
        (folder / "stderr.log").write_text(stderr, encoding="utf-8")
        events, parse_errors = [], []
        for line in stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                parse_errors.append(line)
        tool_items = [e.get("item", {}) for e in events if e.get("item", {}).get("type")
                      not in (None, "agent_message", "reasoning")]
        complete = [e for e in events if e.get("type") == "turn.completed"]
        usage = complete[-1].get("usage", {}) if complete else {}
        reason = None
        if returncode != 0:
            reason = "Codex failed; inspect stderr.log and events.jsonl (authentication/network/limit)"
        elif tool_items:
            reason = "Forbidden model tool invocation; call excluded from evaluation"
        elif not complete or not final.exists() or parse_errors:
            reason = "Incomplete or malformed model execution evidence"
        result = {"status": "failed" if reason else "completed", "reason": reason,
                  "execution_kind": self.execution_kind, "model": self.model,
                  "fingerprint": fingerprint, "returncode": returncode,
                  "wall_seconds": time.monotonic() - start, "usage": usage,
                  "monetary_cost": None,
                  "cost_unavailable_reason": "Subscription usage; no per-call billing evidence",
                  "tool_calls": tool_items,
                  "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in folder.iterdir() if p.is_file()}}
        (folder / "result.json").write_text(_json(result), encoding="utf-8")
        self.last_evidence = {**result, "evidence_record": self._record_link(folder)}
        if reason:
            raise ModelUnavailable(reason)
        answer = final.read_text(encoding="utf-8")
        return parse_object(answer) if json_response else answer

    @staticmethod
    def _record_link(folder):
        return {"directory": str(folder), "result_sha256": hashlib.sha256((folder / "result.json").read_bytes()).hexdigest(),
                "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in folder.iterdir() if p.is_file()}}

    @staticmethod
    def _check_files(folder, result):
        for filename, expected in result["files"].items():
            path = folder / filename
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ModelUnavailable(f"Model evidence altered: {filename}")


class FileProvider:
    """Explicit asynchronous bridge; imported responses require real provenance."""

    execution_kind = "external_response_unverified"

    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def complete(self, prompt, *, call_id, json_response=False):
        request = self.directory / f"{call_id}.request.json"
        response = self.directory / f"{call_id}.response.json"
        if not request.exists():
            request.write_text(_json({"prompt": prompt, "fingerprint": digest(prompt)}), encoding="utf-8")
        else:
            prior = json.loads(request.read_text(encoding="utf-8"))
            if prior.get("fingerprint") != digest(prompt):
                raise ValueError("Call id reused with a different prompt")
        if not response.exists():
            raise ModelUnavailable(f"Awaiting response: {response}")
        value = json.loads(response.read_text(encoding="utf-8"))
        if value.get("request_sha256") != digest(prompt):
            raise ValueError("Response does not match request")
        return parse_object(value["text"]) if json_response else value["text"]
