"""Transactional registration, durable execution and append-only evidence ledger.

The runner is trusted, allowlisted application code. These guards detect accidental
or application-level mutation; this is not an OS sandbox against arbitrary code
running as the same user. Completed evidence is only read by public mutation APIs.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any
from datetime import datetime, timezone


PHASES = ("OBSERVE", "RETRIEVE", "PROPOSE", "REGISTER", "IMPLEMENT", "EXECUTE",
          "VERIFY", "DECIDE", "UPDATE_MEMORY")
CLAIM_KINDS = {"measured", "literature", "inference", "proposal"}


class EvidenceError(RuntimeError):
    """Evidence is missing, inconsistent, or attempted to be mutated."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def execution_fingerprint(spec: dict) -> str:
    """The execution identity ignores renamed hypotheses and changed prose.

    New success criteria cannot cause a completed experiment to run again. The
    original preregistration remains authoritative when its evidence is reused.
    """
    keys = ("task_id", "task_version", "seed", "config", "model", "resource_envelope", "command",
            "implementation_sha256", "source_hash", "source_sha256", "split_manifest_sha256",
            "data_hash", "data_sha256", "evaluator_sha256", "public_bundle_sha256", "tool_permissions")
    return fingerprint({key: spec[key] for key in keys if key in spec})


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: Any) -> None:
    """Flush before replace so resume can reconcile a durable execution receipt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (canonical_json(value) + "\n").encode("utf-8")
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.evidence = self.root / "evidence"
        self.evidence.mkdir(exist_ok=True)
        self.db_path = self.root / "research.sqlite3"
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(
                    run_id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL,
                    spec TEXT NOT NULL, status TEXT NOT NULL,
                    outcome TEXT, result TEXT, verification TEXT, manifest TEXT,
                    created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT);
                CREATE TABLE IF NOT EXISTS events(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                    phase TEXT NOT NULL, payload TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS execution_index(
                    execution_fingerprint TEXT PRIMARY KEY,
                    run_id TEXT UNIQUE NOT NULL REFERENCES runs(run_id));
                CREATE TABLE IF NOT EXISTS memory(
                    run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
                    hypothesis TEXT NOT NULL, outcome TEXT NOT NULL,
                    verification_status TEXT NOT NULL, applicability TEXT NOT NULL,
                    search_text TEXT NOT NULL, evidence_hash TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS immutable_completed_run
                    BEFORE UPDATE ON runs WHEN OLD.status='completed'
                    BEGIN SELECT RAISE(ABORT, 'Completed evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS no_run_delete BEFORE DELETE ON runs
                    BEGIN SELECT RAISE(ABORT, 'Registered runs are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS no_event_update BEFORE UPDATE ON events
                    BEGIN SELECT RAISE(ABORT, 'Audit events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS no_event_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT, 'Audit events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS no_memory_update BEFORE UPDATE ON memory
                    BEGIN SELECT RAISE(ABORT, 'Memory is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS no_memory_delete BEFORE DELETE ON memory
                    BEGIN SELECT RAISE(ABORT, 'Memory is append-only'); END;
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _append_event(self, db, phase: str, payload: dict) -> dict:
        if phase not in PHASES and phase not in {"GOAL", "STATE", "RECOVERY", "RESOURCE"}:
            raise ValueError(f"Unknown research phase {phase}")
        previous = db.execute("SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        previous_hash = previous[0] if previous else "0" * 64
        event = {"timestamp": utc_now(), "phase": phase, "payload": payload,
                 "previous_hash": previous_hash}
        event_hash = fingerprint(event)
        cursor = db.execute("INSERT INTO events(timestamp,phase,payload,previous_hash,event_hash) VALUES (?,?,?,?,?)",
                            (event["timestamp"], phase, canonical_json(payload), previous_hash, event_hash))
        return {"sequence": cursor.lastrowid, **event, "event_hash": event_hash}

    def record_event(self, phase: str, payload: dict) -> dict:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._append_event(db, phase, payload)

    def init_goal(self, goal: dict) -> dict:
        encoded = canonical_json(goal)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT value FROM metadata WHERE key='goal'").fetchone()
            if existing and existing[0] != encoded:
                raise EvidenceError("An existing goal cannot be silently replaced; use a new store.")
            if not existing:
                db.execute("INSERT INTO metadata(key,value) VALUES ('goal',?)", (encoded,))
                atomic_json(self.root / "goal.json", goal)
                self._append_event(db, "GOAL", {"goal_sha256": fingerprint(goal)})
        return self.state()

    def _decode_run(self, row) -> dict:
        if row is None:
            raise KeyError("Run not found")
        result = dict(row)
        for key in ("spec", "result", "verification", "manifest"):
            result[key] = json.loads(result[key]) if result[key] is not None else None
        result["run_dir"] = str(self.evidence / result["run_id"])
        return result

    def get_run(self, run_id: str) -> dict:
        with self._connect() as db:
            return self._decode_run(db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())

    def list_runs(self) -> list[dict]:
        with self._connect() as db:
            return [self._decode_run(row) for row in db.execute("SELECT * FROM runs ORDER BY created_at,run_id")]

    def find_execution(self, spec: dict) -> dict | None:
        digest = execution_fingerprint(spec)
        with self._connect() as db:
            row = db.execute("SELECT runs.* FROM runs JOIN execution_index USING(run_id) WHERE execution_fingerprint=?",
                             (digest,)).fetchone()
        if row:
            return self._decode_run(row)
        return next((run for run in self.list_runs() if execution_fingerprint(run["spec"]) == digest), None)

    def state(self) -> dict:
        runs = self.list_runs()
        with self._connect() as db:
            meta = {row["key"]: json.loads(row["value"]) for row in db.execute("SELECT * FROM metadata")}
            latest = db.execute("SELECT phase,payload FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
            usage_events = [json.loads(row[0]) for row in db.execute("SELECT payload FROM events WHERE phase='RESOURCE'")]
        resources = {"elapsed_seconds": 0.0, "cost_usd": None,
                     "model_calls": None, "registered_model_calls": 0,
                     "registered_model_seconds": 0.0, "registered_model_usage": {},
                     "scope": "Registered runs and logged orchestrator usage; model-call repository owns unresolved proposal costs."}
        for run in runs:
            for key, value in (run.get("result") or {}).get("resources", {}).items():
                if isinstance(value, (int, float)) and math.isfinite(value):
                    prior = resources.get(key)
                    resources[key] = (prior if isinstance(prior, (int, float)) else 0) + value
        for event in usage_events:
            for key, value in event.get("usage", {}).items():
                if isinstance(value, (int, float)) and math.isfinite(value):
                    prior = resources.get(key)
                    resources[key] = (prior if isinstance(prior, (int, float)) else 0) + value
        linked_calls = {}
        for run in runs:
            trace = run["spec"].get("model_evidence", {})
            if trace.get("call_id"):
                linked_calls.setdefault(trace["call_id"], trace)
        resources["registered_model_calls"] = len(linked_calls)
        for trace in linked_calls.values():
            seconds = trace.get("wall_seconds")
            if isinstance(seconds, (int, float)) and math.isfinite(seconds):
                resources["registered_model_seconds"] += seconds
            for key, value in trace.get("usage", {}).items():
                if isinstance(value, (int, float)) and math.isfinite(value):
                    resources["registered_model_usage"][key] = resources["registered_model_usage"].get(key, 0) + value
        active = [run["run_id"] for run in runs if run["status"] != "completed"]
        return {"goal": meta.get("goal"), "phase": latest["phase"] if latest else "OBSERVE",
                "best": meta.get("best", {}), "resources": resources, "runs": runs,
                "hypotheses": [run["spec"]["hypothesis"] for run in runs],
                "active_runs": active, "next_action": "resume" if active else "observe_and_propose"}

    @staticmethod
    def validate_spec(spec: dict) -> None:
        required = ("hypothesis", "task_id", "seed", "config", "metric", "criterion", "model",
                    "resource_envelope", "command")
        missing = [key for key in required if key not in spec]
        for alternatives in (("implementation_sha256", "source_hash"),
                             ("split_manifest_sha256", "data_hash"), ("evaluator_sha256",)):
            if not any(spec.get(key) for key in alternatives):
                missing.append(" or ".join(alternatives))
        if missing:
            raise ValueError("Registration requires: " + ", ".join(missing))
        if not isinstance(spec["config"], dict) or not isinstance(spec["resource_envelope"], dict):
            raise ValueError("config and resource_envelope must be objects")
        if spec["criterion"].get("direction") not in {"min", "max"}:
            raise ValueError("criterion.direction must be min or max")
        for key in ("threshold", "baseline_value", "improvement"):
            if key in spec["criterion"]:
                value = spec["criterion"][key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"Registered criterion must be a finite number: {key}")
                if key == "improvement" and value < 0:
                    raise ValueError("Registered minimum improvement cannot be negative")
        canonical_json(spec)

    def register(self, spec: dict) -> dict:
        self.validate_spec(spec)
        digest = fingerprint(spec)
        run_id = digest[:24]
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM runs WHERE fingerprint=?", (digest,)).fetchone()
            execution_digest = execution_fingerprint(spec)
            if not existing:
                existing = db.execute("SELECT runs.* FROM runs JOIN execution_index USING(run_id) WHERE execution_fingerprint=?",
                                      (execution_digest,)).fetchone()
            # Older stores remain resumable without rewriting completed evidence.
            if not existing:
                for row in db.execute("SELECT * FROM runs"):
                    if execution_fingerprint(json.loads(row["spec"])) == execution_digest:
                        existing = row
                        break
            if existing:
                run = self._decode_run(existing)
                run["created"] = False
                run["reused_execution_conditions"] = run["fingerprint"] != digest
                return run
            if spec.get("retry_of"):
                previous = self._decode_run(db.execute("SELECT * FROM runs WHERE run_id=?", (spec["retry_of"],)).fetchone())
                changed = {key: {"before": previous["spec"].get(key), "after": spec.get(key)}
                           for key in ("config", "seed", "model", "implementation_sha256", "source_hash",
                                       "split_manifest_sha256", "data_hash", "resource_envelope", "command")
                           if previous["spec"].get(key) != spec.get(key)}
                if not spec.get("retry_reason") or not changed:
                    raise ValueError("A retry requires changed execution conditions and an explicit retry_reason")
                if previous["status"] != "completed" and previous["status"] != "unknown_execution":
                    raise ValueError("Cannot retry an unresolved active run")
            else:
                changed = None
            path = self.evidence / run_id / "registration.json"
            if path.exists() and json.loads(path.read_text(encoding="utf-8")) != spec:
                raise EvidenceError("Existing registration evidence differs")
            atomic_json(path, spec)
            db.execute("INSERT INTO runs(run_id,fingerprint,spec,status,created_at) VALUES (?,?,?,?,?)",
                       (run_id, digest, canonical_json(spec), "pending", utc_now()))
            db.execute("INSERT INTO execution_index VALUES (?,?)", (execution_digest, run_id))
            self._append_event(db, "REGISTER", {"run_id": run_id, "fingerprint": digest,
                                                "execution_fingerprint": execution_digest,
                                                "registration_sha256": sha256_file(path),
                                                "retry_changed_conditions": changed})
        run = self.get_run(run_id)
        run["created"] = True
        return run

    def mark_running(self, run_id: str) -> dict:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row[0] != "pending":
                raise EvidenceError("Only a pending registration may start execution")
            db.execute("UPDATE runs SET status='running',started_at=? WHERE run_id=?", (utc_now(), run_id))
            self._append_event(db, "EXECUTE", {"run_id": run_id, "state": "running"})
        return self.get_run(run_id)

    def record_execution(self, run_id: str, result: dict) -> dict:
        run = self.get_run(run_id)
        if run["status"] not in {"running", "unknown_execution", "executed"}:
            raise EvidenceError("Run must be running to record execution evidence")
        if result.get("status") not in {"success", "failure", "inconclusive"}:
            raise ValueError("Execution result status must be success, failure, or inconclusive")
        for claim in result.get("claims", []):
            if claim.get("kind") not in CLAIM_KINDS:
                raise ValueError("Every claim requires measured/literature/inference/proposal kind")
            if claim["kind"] == "measured" and not (claim.get("evidence") or claim.get("artifact") or claim.get("metric")):
                raise ValueError("Measured claims must name a metric or evidence artifact")
        receipt = {"run_id": run_id, "spec_fingerprint": run["fingerprint"], "result": result}
        path = Path(run["run_dir"]) / "execution.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != receipt:
                raise EvidenceError("Durable execution evidence cannot be overwritten")
        else:
            atomic_json(path, receipt)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE runs SET status='executed',outcome=?,result=? WHERE run_id=?",
                       (result["status"], canonical_json(result), run_id))
            self._append_event(db, "EXECUTE", {"run_id": run_id, "state": "executed",
                                               "execution_sha256": sha256_file(path)})
        return self.get_run(run_id)

    def reconcile(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        if run["status"] not in {"running", "unknown_execution"}:
            return run
        path = Path(run["run_dir"]) / "execution.json"
        if path.is_file():
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if receipt.get("run_id") != run_id or receipt.get("spec_fingerprint") != run["fingerprint"]:
                raise EvidenceError("Execution receipt does not match registration")
            return self.record_execution(run_id, receipt["result"])
        if run["status"] != "unknown_execution":
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE runs SET status='unknown_execution' WHERE run_id=?", (run_id,))
                self._append_event(db, "RECOVERY", {"run_id": run_id, "state": "unknown_execution",
                                                     "reason": "No durable completion receipt. Automatic rerun refused."})
        return self.get_run(run_id)

    def _artifact_manifest(self, run: dict, result: dict) -> list[dict]:
        manifest = []
        run_dir = Path(run["run_dir"]).resolve()
        for item in result.get("artifacts", []):
            path = Path(item["path"] if isinstance(item, dict) else item)
            if not path.is_absolute():
                path = run_dir / path
            path = path.resolve()
            if not path.is_relative_to(run_dir):
                raise EvidenceError("Runner artifacts must stay inside their registered run directory")
            if not path.is_file():
                raise EvidenceError(f"Missing execution artifact: {path}")
            manifest.append({"path": path.relative_to(self.root).as_posix(),
                             "sha256": sha256_file(path), "bytes": path.stat().st_size})
        return manifest

    @staticmethod
    def _criterion_met(spec: dict, verification: dict) -> bool:
        if not verification.get("valid", False) or verification.get("status") != "verified":
            return False
        value = verification.get("metrics", {}).get(spec["metric"])
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return False
        criterion = spec["criterion"]
        direction = 1 if criterion["direction"] == "max" else -1
        if "threshold" in criterion and direction * (value - criterion["threshold"]) < 0:
            return False
        if "baseline_value" in criterion:
            if direction * (value - criterion["baseline_value"]) <= float(criterion.get("improvement", 0)):
                return False
        return "threshold" in criterion or "baseline_value" in criterion or spec.get("role") == "baseline"

    @staticmethod
    def _comparison_key(spec: dict) -> str:
        return fingerprint({"task": spec["task_id"], "task_version": spec.get("task_version"),
            "metric": spec["metric"], "evaluator_sha256": spec["evaluator_sha256"],
            "split": spec.get("split_manifest_sha256", spec.get("data_hash")),
            "model": spec["model"], "envelope": spec["resource_envelope"]})

    def _comparison_valid(self, spec: dict, verification: dict) -> bool:
        if "baseline_value" not in spec["criterion"]:
            return True
        baseline_id = spec.get("baseline", {}).get("run_id") if isinstance(spec.get("baseline"), dict) else None
        if baseline_id:
            try:
                baseline = self.get_run(baseline_id)
            except KeyError:
                return False
            if baseline["status"] != "completed" or not baseline["verification"].get("valid"):
                return False
            if self._comparison_key(spec) != self._comparison_key(baseline["spec"]):
                return False
            value = baseline["verification"].get("metrics", {}).get(spec["metric"])
            return isinstance(value, (int, float)) and math.isclose(value, spec["criterion"]["baseline_value"],
                                                                   rel_tol=1e-9, abs_tol=1e-12)
        return verification.get("comparison_valid") is True

    def complete(self, run_id: str, result: dict, verification: dict) -> dict:
        run = self.get_run(run_id)
        if run["status"] == "completed":
            check = self.verify_integrity(run_id)
            if not check["valid"]:
                raise EvidenceError("Completed evidence integrity failed: " + "; ".join(check["errors"]))
            if result != run["result"] or verification != run["verification"]:
                raise EvidenceError("Completed evidence cannot be replaced")
            return run
        if run["status"] != "executed" or run["result"] != result:
            raise EvidenceError("Complete requires the exact durable execution result")
        verification = dict(verification)
        verification.setdefault("status", "verified" if verification.get("valid") else "rejected")
        if verification["status"] not in {"verified", "rejected", "inconclusive"}:
            raise ValueError("Unknown verification status")
        if verification.get("valid") and verification["status"] != "verified":
            raise ValueError("Only verified results may be valid")
        if verification.get("valid"):
            metrics = verification.get("metrics", {})
            for name, value in metrics.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise EvidenceError(f"Independent metric {name} is not finite numeric evidence")
            for name, value in result.get("metrics", {}).items():
                actual = metrics.get(name)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or actual is None or not math.isclose(value, actual, rel_tol=1e-7, abs_tol=1e-9):
                    raise EvidenceError(f"Execution metric {name} lacks matching independent calculation")
            for claim in result.get("claims", []):
                if claim["kind"] == "measured" and claim.get("metric"):
                    name, value = claim["metric"], claim.get("value")
                    actual = metrics.get(name)
                    if actual is None or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isclose(value, actual, rel_tol=1e-7, abs_tol=1e-9):
                        raise EvidenceError(f"Measured claim {name} lacks matching independent calculation")
        manifest = self._artifact_manifest(run, result)
        run_dir = Path(run["run_dir"])
        verification_path = run_dir / "verification.json"
        manifest_path = run_dir / "manifest.json"
        for path, value in ((verification_path, verification), (manifest_path, manifest)):
            if path.exists() and json.loads(path.read_text(encoding="utf-8")) != value:
                raise EvidenceError("Existing completion evidence differs")
            atomic_json(path, value)
        evidence_hash = fingerprint({"spec": run["spec"], "result": result,
                                     "verification": verification, "manifest": manifest})
        applicability = run["spec"].get("applicability", {
            "task_id": run["spec"]["task_id"], "task_version": run["spec"].get("task_version"),
            "model": run["spec"]["model"], "config": run["spec"]["config"], "seed": run["spec"]["seed"],
            "resource_envelope": run["spec"]["resource_envelope"],
            "implementation_sha256": run["spec"].get("implementation_sha256", run["spec"].get("source_hash")),
            "evaluator_sha256": run["spec"]["evaluator_sha256"],
            "split_manifest_sha256": run["spec"].get("split_manifest_sha256", run["spec"].get("data_hash")),
        })
        criterion_met = self._criterion_met(run["spec"], verification)
        comparison_valid = self._comparison_valid(run["spec"], verification)
        outcome = result["status"] if verification.get("valid") else "inconclusive"
        if outcome == "success":
            has_criterion = any(key in run["spec"]["criterion"] for key in ("threshold", "baseline_value")) or run["spec"].get("role") == "baseline"
            outcome = ("success" if criterion_met else "failure") if has_criterion and comparison_valid else "inconclusive"
        accepted = outcome == "success" and criterion_met and comparison_valid
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._append_event(db, "VERIFY", {"run_id": run_id, "verification": verification,
                                              "verification_sha256": sha256_file(verification_path),
                                              "manifest_sha256": sha256_file(manifest_path)})
            self._append_event(db, "DECIDE", {"run_id": run_id,
                "decision": "adopt" if accepted else "reject" if outcome == "failure" else "defer",
                "criterion_met": criterion_met, "comparison_valid": comparison_valid,
                "execution_outcome": result["status"], "hypothesis_outcome": outcome,
                "evidence_hash": evidence_hash})
            db.execute("UPDATE runs SET status='completed',outcome=?,verification=?,manifest=?,completed_at=? WHERE run_id=?",
                       (outcome, canonical_json(verification), canonical_json(manifest), utc_now(), run_id))
            db.execute("INSERT INTO memory VALUES (?,?,?,?,?,?,?)",
                       (run_id, str(run["spec"]["hypothesis"]), outcome, verification["status"],
                        canonical_json(applicability), canonical_json({"spec": run["spec"], "result": result,
                                                                      "verification": verification}), evidence_hash))
            if accepted:
                best_row = db.execute("SELECT value FROM metadata WHERE key='best'").fetchone()
                best = json.loads(best_row[0]) if best_row else {}
                key = self._comparison_key(run["spec"])
                value = verification["metrics"][run["spec"]["metric"]]
                old = best.get(key)
                direction = 1 if run["spec"]["criterion"]["direction"] == "max" else -1
                if old is None or direction * (value - old["value"]) > 0:
                    best[key] = {"run_id": run_id, "value": value, "metric": run["spec"]["metric"],
                                 "task_id": run["spec"]["task_id"], "evidence_hash": evidence_hash}
                    db.execute("INSERT INTO metadata(key,value) VALUES ('best',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                               (canonical_json(best),))
            self._append_event(db, "UPDATE_MEMORY", {"run_id": run_id, "outcome": outcome,
                                                     "verification_status": verification["status"],
                                                     "evidence_hash": evidence_hash})
        return self.get_run(run_id)

    def search(self, query: str, conditions: dict | None = None) -> list[dict]:
        terms = query.lower().split()
        with self._connect() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM memory ORDER BY rowid DESC")]
        results = []
        for row in rows:
            text = row["search_text"].lower()
            if terms and not all(term in text for term in terms):
                continue
            applicability = json.loads(row["applicability"])
            if conditions and any(applicability.get(key) != value for key, value in conditions.items()):
                continue
            run = self.get_run(row["run_id"])
            integrity = self.verify_integrity(run["run_id"])
            results.append({"run_id": row["run_id"], "hypothesis": row["hypothesis"],
                            "outcome": row["outcome"], "verification_status": row["verification_status"],
                            "applicability": applicability, "evidence_hash": row["evidence_hash"],
                            "config": run["spec"]["config"], "conditions": applicability,
                            "metrics": run["verification"].get("metrics", {}) if run["verification"].get("valid") else {},
                            "failure_reason": run["result"].get("failure_reason", run["result"].get("error")) or (
                                "Registered success criterion was not met." if row["outcome"] == "failure" else None),
                            "evidence": run["manifest"],
                            "integrity": integrity, "original_evidence": {
                                "spec": run["spec"], "result": run["result"],
                                "verification": run["verification"], "manifest": run["manifest"],
                                "run_dir": run["run_dir"]},
                            "usable_as_verified_evidence": integrity["valid"] and row["verification_status"] == "verified"})
        return results

    def verify_integrity(self, run_id: str | None = None) -> dict:
        errors = []
        with self._connect() as db:
            events = [dict(row) for row in db.execute("SELECT * FROM events ORDER BY sequence")]
            goal_row = db.execute("SELECT value FROM metadata WHERE key='goal'").fetchone()
            memories = {row["run_id"]: dict(row) for row in db.execute("SELECT * FROM memory")}
            best_row = db.execute("SELECT value FROM metadata WHERE key='best'").fetchone()
            indexes = [dict(row) for row in db.execute("SELECT * FROM execution_index")]
        previous = "0" * 64
        for event in events:
            try:
                payload = json.loads(event["payload"])
                expected = fingerprint({"timestamp": event["timestamp"], "phase": event["phase"],
                                        "payload": payload, "previous_hash": previous})
            except (ValueError, TypeError) as exc:
                errors.append(f"Audit event {event['sequence']} invalid: {exc}")
                continue
            if event["previous_hash"] != previous or event["event_hash"] != expected:
                errors.append(f"Audit chain mismatch at event {event['sequence']}")
            previous = event["event_hash"]
            for key, name in (("registration_sha256", "registration.json"), ("execution_sha256", "execution.json"),
                              ("verification_sha256", "verification.json"), ("manifest_sha256", "manifest.json")):
                if key in payload and payload.get("run_id") and (not run_id or payload["run_id"] == run_id):
                    try:
                        path = self.evidence / payload["run_id"] / name
                        if sha256_file(path) != payload[key]:
                            errors.append(f"{payload['run_id']}: audit-anchored {name} hash mismatch")
                    except OSError as exc:
                        errors.append(f"{payload['run_id']}: audit-anchored {name} missing: {exc}")
        if goal_row:
            try:
                if json.loads((self.root / "goal.json").read_text(encoding="utf-8")) != json.loads(goal_row[0]):
                    errors.append("Goal evidence mismatch")
            except (OSError, ValueError) as exc:
                errors.append(f"Goal evidence unreadable: {exc}")
        runs = [self.get_run(run_id)] if run_id else self.list_runs()
        for index in indexes:
            if run_id and index["run_id"] != run_id:
                continue
            try:
                indexed_run = self.get_run(index["run_id"])
                if execution_fingerprint(indexed_run["spec"]) != index["execution_fingerprint"]:
                    errors.append(f"{index['run_id']}: execution identity index mismatch")
            except KeyError:
                errors.append(f"{index['run_id']}: missing indexed registration")
        for run in runs:
            prefix = run["run_id"]
            if fingerprint(run["spec"]) != run["fingerprint"]:
                errors.append(f"{prefix}: registration fingerprint mismatch")
            checks = [("registration.json", run["spec"])]
            if run["result"] is not None:
                checks.append(("execution.json", {"run_id": prefix, "spec_fingerprint": run["fingerprint"],
                                                   "result": run["result"]}))
            if run["status"] == "completed":
                checks += [("verification.json", run["verification"]), ("manifest.json", run["manifest"])]
            for name, expected in checks:
                try:
                    actual = json.loads((Path(run["run_dir"]) / name).read_text(encoding="utf-8"))
                    if actual != expected:
                        errors.append(f"{prefix}: {name} content mismatch")
                except (OSError, ValueError) as exc:
                    errors.append(f"{prefix}: {name} unreadable: {exc}")
            for artifact in run["manifest"] or []:
                try:
                    path = (self.root / artifact["path"]).resolve()
                    if not path.is_relative_to(Path(run["run_dir"]).resolve()):
                        errors.append(f"{prefix}: artifact escapes registered run directory")
                    elif sha256_file(path) != artifact["sha256"] or path.stat().st_size != artifact["bytes"]:
                        errors.append(f"{prefix}: artifact hash mismatch: {artifact['path']}")
                except OSError as exc:
                    errors.append(f"{prefix}: missing artifact: {exc}")
            if run["status"] == "completed":
                evidence_hash = fingerprint({"spec": run["spec"], "result": run["result"],
                                             "verification": run["verification"], "manifest": run["manifest"]})
                memory = memories.get(prefix)
                if memory is None or memory["evidence_hash"] != evidence_hash:
                    errors.append(f"{prefix}: memory evidence mismatch")
                elif memory["outcome"] != run["outcome"] or memory["verification_status"] != run["verification"]["status"]:
                    errors.append(f"{prefix}: memory verification status mismatch")
        if best_row:
            for best in json.loads(best_row[0]).values():
                if run_id and best["run_id"] != run_id:
                    continue
                try:
                    run = self.get_run(best["run_id"])
                    metric = run["spec"]["metric"]
                    expected_hash = fingerprint({"spec": run["spec"], "result": run["result"],
                                                 "verification": run["verification"], "manifest": run["manifest"]})
                    if run["status"] != "completed" or run["outcome"] != "success" or not self._criterion_met(run["spec"], run["verification"]) or not self._comparison_valid(run["spec"], run["verification"]):
                        errors.append(f"{best['run_id']}: best result lacks a valid registered comparison")
                    elif best["value"] != run["verification"]["metrics"][metric] or best["metric"] != metric or best["task_id"] != run["spec"]["task_id"] or best["evidence_hash"] != expected_hash:
                        errors.append(f"{best['run_id']}: best result evidence mismatch")
                except (KeyError, TypeError) as exc:
                    errors.append(f"Best-result evidence missing: {exc}")
        return {"valid": not errors, "errors": errors, "audit_head": previous,
                "checked_runs": len(runs), "checked_events": len(events)}
