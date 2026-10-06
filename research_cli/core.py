"""Transactional research records. No models, prompts, or agent loop live here."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import sys
import time
import uuid


class ResearchError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


def canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ResearchError("INVALID_INPUT", "Input must be finite JSON", {"reason": str(exc)}) from exc


def sha256_file(path):
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ResearchError("EVIDENCE_MISSING", "Cannot read evidence file", {"path": str(path), "reason": str(exc)}) from exc
    return digest.hexdigest()


def _id(prefix):
    return prefix + "_" + uuid.uuid4().hex


def _relative(value):
    if not isinstance(value, str) or not value:
        raise ResearchError("INVALID_INPUT", "Expected a nonempty relative path", {"path": str(value)})
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.drive:
        raise ResearchError("INVALID_INPUT", "Expected a relative path within the execution directory", {"path": str(value)})
    return path.as_posix()


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


_SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE goals(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE hypotheses(id TEXT PRIMARY KEY,goal_id TEXT NOT NULL REFERENCES goals(id),statement TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE validators(name TEXT PRIMARY KEY,record TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE registrations(id TEXT PRIMARY KEY,goal_id TEXT NOT NULL REFERENCES goals(id),hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id),spec TEXT NOT NULL,fingerprint TEXT NOT NULL UNIQUE,created REAL NOT NULL);
CREATE TABLE runs(id TEXT PRIMARY KEY,registration_id TEXT NOT NULL UNIQUE REFERENCES registrations(id),state TEXT NOT NULL CHECK(state IN ('running','succeeded','failed','unknown')),receipt TEXT,resources TEXT NOT NULL,reason TEXT,created REAL NOT NULL,finished REAL);
CREATE TABLE evidence(id TEXT PRIMARY KEY,registration_id TEXT NOT NULL REFERENCES registrations(id),run_id TEXT REFERENCES runs(id),name TEXT,kind TEXT NOT NULL CHECK(kind IN ('measured','literature','inference','proposal')),claim TEXT NOT NULL,path TEXT,sha256 TEXT,size INTEGER,original_path TEXT,created REAL NOT NULL,UNIQUE(run_id,name));
CREATE TABLE verifications(run_id TEXT PRIMARY KEY REFERENCES runs(id),state TEXT NOT NULL CHECK(state IN ('passed','failed','inconclusive')),metrics TEXT NOT NULL,details TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE decisions(registration_id TEXT PRIMARY KEY REFERENCES registrations(id),state TEXT NOT NULL CHECK(state IN ('adopted','rejected','inconclusive')),reason TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE requests(scope TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,target TEXT NOT NULL,PRIMARY KEY(scope,key));
CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,revision INTEGER NOT NULL,action TEXT NOT NULL,target TEXT,data TEXT NOT NULL,created REAL NOT NULL);
CREATE INDEX evidence_registration ON evidence(registration_id);
CREATE TRIGGER run_state_guard BEFORE UPDATE OF state ON runs WHEN NOT (OLD.state IN ('running','unknown') AND NEW.state IN ('succeeded','failed','unknown')) BEGIN SELECT RAISE(ABORT,'invalid run transition'); END;
"""

_GOAL_SCHEMA = (
    "CREATE TABLE goal_versions(goal_id TEXT NOT NULL REFERENCES goals(id),version INTEGER NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL,brief TEXT NOT NULL,reason TEXT NOT NULL,change_kind TEXT NOT NULL,created REAL NOT NULL,source TEXT NOT NULL,PRIMARY KEY(goal_id,version))",
    "CREATE TABLE goal_lifecycle(id TEXT PRIMARY KEY,goal_id TEXT NOT NULL REFERENCES goals(id),goal_version INTEGER NOT NULL,state TEXT NOT NULL CHECK(state IN ('active','paused','completed','cancelled','unknown')),reason TEXT NOT NULL,results TEXT NOT NULL,incomplete TEXT NOT NULL,created REAL NOT NULL,source TEXT NOT NULL)",
    "CREATE TABLE registration_goals(registration_id TEXT PRIMARY KEY REFERENCES registrations(id),goal_id TEXT NOT NULL REFERENCES goals(id),goal_version INTEGER NOT NULL,source TEXT NOT NULL)",
    "CREATE TABLE resource_observations(id TEXT PRIMARY KEY,goal_id TEXT NOT NULL REFERENCES goals(id),registration_id TEXT REFERENCES registrations(id),run_id TEXT REFERENCES runs(id),record TEXT NOT NULL,source TEXT NOT NULL,source_ref TEXT NOT NULL,fingerprint TEXT NOT NULL,created REAL NOT NULL,UNIQUE(goal_id,source,source_ref))",
    "CREATE INDEX goal_lifecycle_goal ON goal_lifecycle(goal_id,created)",
    "CREATE INDEX resource_goal ON resource_observations(goal_id,created)",
)


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.metadata_dir = self.root / ".research"
        self.db_path = self.metadata_dir / "state.sqlite3"
        self.owner_key_path = self.metadata_dir / "owner.key"
        self.internal_key_path = self.metadata_dir / "internal.key"
        if not self.db_path.is_file():
            raise ResearchError("NOT_INITIALIZED", "Initialize this workspace first", {"workspace": str(self.root), "next": "init"})
        self._migrate()

    def _migrate(self):
        """Atomic, compatible v1→v2 extension; never start or reset research."""
        connection = sqlite3.connect(self.db_path, timeout=10)
        try:
            version = connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if version == ("2",):
                missing = connection.execute("SELECT EXISTS(SELECT 1 FROM goals g WHERE NOT EXISTS(SELECT 1 FROM goal_versions v WHERE v.goal_id=g.id) OR NOT EXISTS(SELECT 1 FROM goal_lifecycle l WHERE l.goal_id=g.id)) OR EXISTS(SELECT 1 FROM registrations p WHERE NOT EXISTS(SELECT 1 FROM registration_goals m WHERE m.registration_id=p.id))").fetchone()[0]
                if missing:
                    # A still-running v1 client can append the original tables
                    # after migration. Preserve its records; lifecycle and the
                    # goal-version relationship were not observed by that client.
                    connection.execute('BEGIN IMMEDIATE')
                    connection.execute("INSERT INTO goal_versions SELECT g.id,1,g.title,g.description,'{}','Legacy writer title/description preserved; no structured brief observed','legacy',g.created,'legacy_mapping' FROM goals g WHERE NOT EXISTS(SELECT 1 FROM goal_versions v WHERE v.goal_id=g.id)")
                    connection.execute("INSERT INTO goal_lifecycle SELECT 'legacy_'||g.id,g.id,1,'unknown','Legacy client did not record overall lifecycle','[]','[]',g.created,'legacy_mapping' FROM goals g WHERE NOT EXISTS(SELECT 1 FROM goal_lifecycle l WHERE l.goal_id=g.id)")
                    connection.execute("INSERT INTO registration_goals SELECT p.id,p.goal_id,1,'legacy_mapping' FROM registrations p WHERE NOT EXISTS(SELECT 1 FROM registration_goals m WHERE m.registration_id=p.id)")
                    connection.commit()
                return
            if version != ("1",):
                raise ResearchError("STATE_CONFLICT", "Unsupported storage schema")
            # SQLite's documented table rebuild needs FK enforcement off before
            # BEGIN. Foreign key definitions keep their original `runs` target.
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ("2",):
                connection.rollback()  # A concurrent opener already migrated.
                return
            for statement in _GOAL_SCHEMA:
                connection.execute(statement)
            connection.execute("CREATE TABLE runs_v2(id TEXT PRIMARY KEY,registration_id TEXT NOT NULL UNIQUE REFERENCES registrations(id),state TEXT NOT NULL CHECK(state IN ('running','succeeded','failed','cancelled','unknown')),receipt TEXT,resources TEXT NOT NULL,reason TEXT,created REAL NOT NULL,finished REAL)")
            connection.execute("INSERT INTO runs_v2 SELECT * FROM runs")
            connection.execute("DROP TABLE runs")
            connection.execute("ALTER TABLE runs_v2 RENAME TO runs")
            connection.execute("CREATE TRIGGER run_state_guard BEFORE UPDATE OF state ON runs WHEN NOT (OLD.state IN ('running','unknown') AND NEW.state IN ('succeeded','failed','cancelled','unknown')) BEGIN SELECT RAISE(ABORT,'invalid run transition'); END")
            connection.execute("INSERT INTO goal_versions SELECT id,1,title,description,'{}','Legacy title/description preserved; no structured brief was observed','legacy',created,'legacy_mapping' FROM goals")
            connection.execute("INSERT INTO goal_lifecycle SELECT 'legacy_'||id,id,1,'unknown','No overall lifecycle was recorded in schema v1','[]','[]',created,'legacy_mapping' FROM goals")
            connection.execute("INSERT INTO registration_goals SELECT id,goal_id,1,'legacy_mapping' FROM registrations")
            for table in ("goal_versions", "goal_lifecycle", "registration_goals", "resource_observations"):
                for operation in ("UPDATE", "DELETE"):
                    connection.execute(f"CREATE TRIGGER immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable record'); END")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ResearchError("STATE_CONFLICT", "Migration found broken original relationships")
            connection.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @classmethod
    def init(cls, root):
        root = Path(root).resolve()
        directory = root / ".research"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "state.sqlite3"
        # An exclusive filesystem creation avoids two initializers resetting state.
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
        except FileExistsError:
            store = cls(root)
            return {"workspace": str(root), "revision": store.revision(), "owner_key_path": str(store.owner_key_path), "internal_key_path": str(store.internal_key_path), "runner_interpreter": store.runner_interpreter()}
        try:
            for name in ("owner.key", "internal.key"):
                with (directory / name).open("x", encoding="utf-8") as stream:
                    stream.write(secrets.token_hex(32))
            connection = sqlite3.connect(path)
            try:
                connection.executescript(_SCHEMA)
                for table in ("goals", "hypotheses", "validators", "registrations", "evidence", "verifications", "decisions"):
                    for operation in ("UPDATE", "DELETE"):
                        connection.execute(f"CREATE TRIGGER immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable record'); END")
                connection.executemany("INSERT INTO meta VALUES (?,?)", [("schema_version", "1"), ("revision", "0"), ("runner_interpreter", str(Path(sys.executable).resolve()))])
                connection.commit()
                connection.execute("PRAGMA journal_mode=WAL")
            finally:
                connection.close()
        except Exception:
            # Never replace an existing workspace or keys after partial init.
            raise
        store = cls(root)
        return {"workspace": str(root), "revision": 0, "owner_key_path": str(store.owner_key_path), "internal_key_path": str(store.internal_key_path), "runner_interpreter": store.runner_interpreter()}

    def _connect(self):
        # Long-lived library handles also see records appended by old clients.
        self._migrate()
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _read(self, callback):
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            return callback(connection)
        finally:
            connection.close()

    def _write(self, action, expected_revision, callback, request=None):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            revision = int(connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])
            if request:
                key, fingerprint = request
                prior = connection.execute("SELECT fingerprint,target FROM requests WHERE scope=? AND key=?", (action, key)).fetchone()
                if prior:
                    if prior["fingerprint"] != fingerprint:
                        raise ResearchError("REQUEST_CONFLICT", "Request key was used with different contents", {"scope": action, "key": key})
                    result = json.loads(prior["target"])
                    result.update(reused=True, revision=revision,
                                  result_is_historical=result.get("applied_revision") != revision)
                    connection.commit()
                    return result
            if expected_revision is not None and (isinstance(expected_revision, bool) or expected_revision != revision):
                raise ResearchError("REVISION_CONFLICT", "Workspace revision changed", {"expected": expected_revision, "actual": revision, "next": "status"})
            result, target, changed = callback(connection)
            if request:
                result.update(applied_revision=revision + int(changed), result_is_historical=False)
                connection.execute("INSERT INTO requests VALUES (?,?,?,?)", (action, key, fingerprint, canonical(result)))
            if changed:
                revision += 1
                connection.execute("UPDATE meta SET value=? WHERE key='revision'", (str(revision),))
                connection.execute("INSERT INTO events(revision,action,target,data,created) VALUES (?,?,?,?,?)", (revision, action, target, canonical(result), time.time()))
            connection.commit()
            result["revision"] = revision
            return result
        except ResearchError:
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ResearchError("STATE_CONFLICT", "State constraint rejected this operation", {"reason": str(exc)}) from exc
        except sqlite3.OperationalError as exc:
            connection.rollback()
            raise ResearchError("STATE_CONFLICT", "Workspace transaction could not complete", {"reason": str(exc), "next": "status"}) from exc
        finally:
            connection.close()

    def revision(self):
        return self._read(lambda c: int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0]))

    def runner_interpreter(self):
        return self._read(lambda c: c.execute("SELECT value FROM meta WHERE key='runner_interpreter'").fetchone()[0])

    def internal_key(self):
        return self.internal_key_path.read_text(encoding="utf-8").strip()

    def _authorize(self, value, owner=False):
        expected = (self.owner_key_path if owner else self.internal_key_path).read_text(encoding="utf-8").strip()
        if not isinstance(value, str) or not hmac.compare_digest(value.strip(), expected):
            raise ResearchError("AUTHORITY_REQUIRED", "Owner capability required" if owner else "Execution component capability required")

    @staticmethod
    def _required(connection, table, identifier, column="id"):
        row = connection.execute(f"SELECT * FROM {table} WHERE {column}=?", (identifier,)).fetchone()
        if row is None:
            raise ResearchError("NOT_FOUND", "Research record does not exist", {"type": table, "id": identifier})
        return dict(row)

    @staticmethod
    def _request(key, payload, required=False):
        if key is None and not required:
            return None
        if not isinstance(key, str) or not key.strip():
            raise ResearchError("INVALID_INPUT", "A nonempty request_key is required")
        return key, hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()

    @staticmethod
    def _brief(value):
        if not isinstance(value, dict):
            raise ResearchError("INVALID_INPUT", "Goal brief must be a finite JSON object")
        return json.loads(canonical(value))

    @staticmethod
    def _mutation(reason, expected_revision):
        if not isinstance(reason, str) or not reason.strip():
            raise ResearchError("INVALID_INPUT", "An explicit change reason is required")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ResearchError("INVALID_INPUT", "Goal mutation requires an expected workspace revision")

    def _goal(self, c, goal_id):
        base = self._required(c, "goals", goal_id)
        version = dict(c.execute("SELECT * FROM goal_versions WHERE goal_id=? ORDER BY version DESC LIMIT 1", (goal_id,)).fetchone())
        lifecycle = dict(c.execute("SELECT * FROM goal_lifecycle WHERE goal_id=? ORDER BY created DESC,rowid DESC LIMIT 1", (goal_id,)).fetchone())
        lifecycle["results"], lifecycle["incomplete"] = json.loads(lifecycle["results"]), json.loads(lifecycle["incomplete"])
        return {**base, "title": version["title"], "description": version["description"],
                "version": version["version"], "brief": json.loads(version["brief"]),
                "state": lifecycle["state"], "state_source": lifecycle["source"],
                "lifecycle": lifecycle, "changed_at": max(version["created"], lifecycle["created"])}

    def _goal_writable(self, c, goal_id):
        goal = self._goal(c, goal_id)
        if goal["state"] not in ("active", "unknown"):
            raise ResearchError("INVALID_TRANSITION", "Resume the goal before new research work", {"goal": goal_id, "state": goal["state"], "next": "goal_resume"})
        return goal

    def goal_create(self, title, description="", expected_revision=None, *, brief=None, request_key=None):
        if not isinstance(title, str) or not title.strip() or not isinstance(description, str):
            raise ResearchError("INVALID_INPUT", "Goal title and description must be text")
        brief = self._brief({} if brief is None else brief)
        request = self._request(request_key, {"title": title, "description": description, "brief": brief})
        record = {"id": _id("goal"), "title": title, "description": description, "created": time.time()}
        def create(c):
            c.execute("INSERT INTO goals VALUES (:id,:title,:description,:created)", record)
            c.execute("INSERT INTO goal_versions VALUES (?,?,?,?,?,?,?,?,?)", (record["id"], 1, title, description, canonical(brief), "Original external request", "initial", record["created"], "explicit"))
            c.execute("INSERT INTO goal_lifecycle VALUES (?,?,?,?,?,?,?,?,?)", (_id("lifecycle"), record["id"], 1, "active", "Goal created; this does not authorize experiment execution", "[]", "[]", record["created"], "explicit"))
            return self._goal(c, record["id"]) | {"reused": False}, record["id"], True
        return self._write("goal.create", expected_revision, create, request)

    def goal_show(self, goal_id, limit=20, offset=0):
        self._page(limit, offset)
        def read(c):
            versions = [dict(row) for row in c.execute("SELECT * FROM goal_versions WHERE goal_id=? ORDER BY version DESC LIMIT ? OFFSET ?", (goal_id, limit, offset))]
            for item in versions:
                item["brief"] = json.loads(item["brief"])
            lifecycle = [dict(row) for row in c.execute("SELECT * FROM goal_lifecycle WHERE goal_id=? ORDER BY created DESC,rowid DESC LIMIT ? OFFSET ?", (goal_id, limit, offset))]
            for item in lifecycle:
                item["results"], item["incomplete"] = json.loads(item["results"]), json.loads(item["incomplete"])
            return {"goal": self._goal(c, goal_id), "versions": versions, "lifecycle": lifecycle,
                    "version_total": c.execute("SELECT COUNT(*) FROM goal_versions WHERE goal_id=?", (goal_id,)).fetchone()[0],
                    "lifecycle_total": c.execute("SELECT COUNT(*) FROM goal_lifecycle WHERE goal_id=?", (goal_id,)).fetchone()[0],
                    "resources": self._resource_summary(c, goal_id), "limit": limit, "offset": offset,
                    "revision": int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])}
        return self._read(read)

    def goal_amend(self, goal_id, brief, reason, change_kind, request_key, expected_revision, title=None, description=None):
        self._mutation(reason, expected_revision)
        if change_kind not in ("meaning", "scope", "plan"):
            raise ResearchError("INVALID_INPUT", "change_kind must explicitly name meaning, scope or plan")
        brief = self._brief(brief)
        if title is not None and (not isinstance(title, str) or not title.strip()) or description is not None and not isinstance(description, str):
            raise ResearchError("INVALID_INPUT", "Goal title and description must be text")
        request = self._request(request_key, {"goal": goal_id, "brief": brief, "reason": reason, "change_kind": change_kind, "title": title, "description": description}, required=True)
        def amend(c):
            previous = self._goal_writable(c, goal_id)
            meaning_changed = (title is not None and title != previous["title"] or
                               description is not None and description != previous["description"] or
                               any(brief.get(field) != previous["brief"].get(field) for field in ("original_request", "long_term_goal")))
            scope_changed = brief.get("scope") != previous["brief"].get("scope")
            if meaning_changed and change_kind != "meaning" or scope_changed and change_kind not in ("meaning", "scope"):
                raise ResearchError("INVALID_INPUT", "Goal meaning/scope fields changed; name their change kind explicitly", {"meaning_changed": meaning_changed, "scope_changed": scope_changed})
            version = previous["version"] + 1
            c.execute("INSERT INTO goal_versions VALUES (?,?,?,?,?,?,?,?,?)", (goal_id, version, previous["title"] if title is None else title, previous["description"] if description is None else description, canonical(brief), reason, change_kind, time.time(), "explicit"))
            return {"goal": self._goal(c, goal_id), "reused": False}, goal_id, True
        return self._write("goal.amend", expected_revision, amend, request)

    def goal_close(self, goal_id, state, reason, results, incomplete, request_key, expected_revision):
        self._mutation(reason, expected_revision)
        if state not in ("completed", "paused", "cancelled") or not all(isinstance(value, list) and all(isinstance(item, str) for item in value) for value in (results, incomplete)):
            raise ResearchError("INVALID_INPUT", "Goal closure needs a terminal/report state and text arrays results/incomplete")
        request = self._request(request_key, {"goal": goal_id, "state": state, "reason": reason, "results": results, "incomplete": incomplete}, required=True)
        def close(c):
            goal = self._goal(c, goal_id)
            if goal["state"] not in ("active", "unknown", "paused") or goal["state"] == state:
                raise ResearchError("INVALID_TRANSITION", "Goal is already closed; resume before another closure", {"state": goal["state"]})
            unresolved = [dict(row) for row in c.execute("SELECT r.id,r.registration_id,r.state FROM runs r JOIN registrations p ON p.id=r.registration_id WHERE p.goal_id=? AND r.state IN ('running','unknown')", (goal_id,))]
            if state == "completed" and unresolved:
                raise ResearchError("INVALID_TRANSITION", "Resolve original running/unknown executions before completion", {"unresolved_runs": unresolved})
            c.execute("INSERT INTO goal_lifecycle VALUES (?,?,?,?,?,?,?,?,?)", (_id("lifecycle"), goal_id, goal["version"], state, reason, canonical(results), canonical(incomplete), time.time(), "explicit"))
            return {"goal": self._goal(c, goal_id), "reused": False, "unresolved_runs": unresolved,
                    "report_provenance": "external_report_not_scientific_verification"}, goal_id, True
        return self._write("goal.close", expected_revision, close, request)

    def goal_resume(self, goal_id, reason, request_key, expected_revision):
        self._mutation(reason, expected_revision)
        request = self._request(request_key, {"goal": goal_id, "reason": reason}, required=True)
        def resume(c):
            goal = self._goal(c, goal_id)
            if goal["state"] == "active":
                raise ResearchError("INVALID_TRANSITION", "Goal is already active")
            c.execute("INSERT INTO goal_lifecycle VALUES (?,?,?,?,?,?,?,?,?)", (_id("lifecycle"), goal_id, goal["version"], "active", reason, "[]", canonical(goal["lifecycle"]["incomplete"]), time.time(), "explicit"))
            return {"goal": self._goal(c, goal_id), "reused": False}, goal_id, True
        return self._write("goal.resume", expected_revision, resume, request)

    @staticmethod
    def _page(limit, offset):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100 or isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ResearchError("INVALID_INPUT", "Page requires limit 1..100 and nonnegative offset")

    def resource_record(self, goal_id, observation, request_key, expected_revision=None):
        if not isinstance(observation, dict):
            raise ResearchError("INVALID_INPUT", "Resource observation must be an object")
        fields = {"source", "source_ref", "registration_id", "run_id", "period_start", "period_end", "cost", "tokens", "note"}
        if set(observation) - fields or any(not isinstance(observation.get(name), str) or not observation[name].strip() for name in ("source", "source_ref")):
            raise ResearchError("INVALID_INPUT", "Observation requires source/source_ref and known fields")
        payload = json.loads(canonical(observation))
        payload.setdefault("cost", {"status": "unknown", "amount": None, "currency": None})
        payload.setdefault("tokens", {"status": "unknown", "value": None})
        for name, number in (("cost", "amount"), ("tokens", "value")):
            value = payload[name]
            if not isinstance(value, dict) or set(value) - ({"status", number, "currency"} if name == "cost" else {"status", number}) or value.get("status") not in ("known", "unknown"):
                raise ResearchError("INVALID_INPUT", "Resource quantities require known/unknown status")
            quantity = value.get(number)
            if value["status"] == "unknown" and quantity is not None or value["status"] == "known" and (isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity < 0 or not math.isfinite(quantity)):
                raise ResearchError("INVALID_INPUT", "Known resource values must be finite nonnegative numbers; unknown has null value")
            if name == "tokens" and quantity is not None and not isinstance(quantity, int):
                raise ResearchError("INVALID_INPUT", "Token counts must be integers")
            if name == "cost" and value["status"] == "known" and (not isinstance(value.get("currency"), str) or not value["currency"].strip()):
                raise ResearchError("INVALID_INPUT", "Known cost needs a currency; currencies are never converted automatically")
            if name == "cost" and value.get("currency") is not None and not isinstance(value["currency"], str):
                raise ResearchError("INVALID_INPUT", "Cost currency must be text or null")
        for name in ("period_start", "period_end"):
            value = payload.get(name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ResearchError("INVALID_INPUT", "Resource periods must be finite timestamps")
        if payload.get("period_start") is not None and payload.get("period_end") is not None and payload["period_end"] < payload["period_start"]:
            raise ResearchError("INVALID_INPUT", "Observation period ends before it starts")
        request = self._request(request_key, {"goal": goal_id, "observation": payload}, required=True)
        fingerprint = request[1]
        def record(c):
            self._required(c, "goals", goal_id)
            registration_id, run_id = payload.get("registration_id"), payload.get("run_id")
            if run_id:
                execution = self._required(c, "runs", run_id)
                if registration_id and registration_id != execution["registration_id"]:
                    raise ResearchError("INVALID_INPUT", "Observation run and registration differ")
                registration_id = execution["registration_id"]
            if registration_id and self._required(c, "registrations", registration_id)["goal_id"] != goal_id:
                raise ResearchError("INVALID_INPUT", "Observation branch belongs to another goal")
            prior = c.execute("SELECT * FROM resource_observations WHERE goal_id=? AND source=? AND source_ref=?", (goal_id, payload["source"], payload["source_ref"])).fetchone()
            if prior:
                if prior["fingerprint"] != fingerprint:
                    raise ResearchError("REQUEST_CONFLICT", "Resource source reference is already fixed")
                return {"observation": self._resource(prior), "reused": True}, prior["id"], False
            item = {"id": _id("resource"), "goal_id": goal_id, "registration_id": registration_id, "run_id": run_id, "record": canonical(payload), "source": payload["source"], "source_ref": payload["source_ref"], "fingerprint": fingerprint, "created": time.time()}
            c.execute("INSERT INTO resource_observations VALUES (:id,:goal_id,:registration_id,:run_id,:record,:source,:source_ref,:fingerprint,:created)", item)
            return {"observation": self._resource(item), "reused": False}, item["id"], True
        return self._write("resource.record", expected_revision, record, request)

    @staticmethod
    def _resource(row):
        item = dict(row)
        item["record"] = json.loads(item["record"])
        item["provenance"] = "external_report"
        return item

    def _resource_summary(self, c, goal_id, registration_id=None):
        where, params = "goal_id=?", [goal_id]
        if registration_id:
            where += " AND registration_id=?"
            params.append(registration_id)
        costs, known, unknown, tokens, token_known, token_unknown = {}, 0, 0, 0, 0, 0
        branches = set()
        for row in c.execute("SELECT record,registration_id FROM resource_observations WHERE " + where, params):
            record = json.loads(row["record"])
            if row["registration_id"]:
                branches.add(row["registration_id"])
            cost = record["cost"]
            if cost["status"] == "known":
                costs[cost["currency"]] = costs.get(cost["currency"], 0) + cost["amount"]
                known += 1
            else:
                unknown += 1
            usage = record["tokens"]
            if usage["status"] == "known":
                tokens += usage["value"]
                token_known += 1
            else:
                token_unknown += 1
        run_sql = "SELECT COUNT(*) FROM runs r JOIN registrations p ON p.id=r.registration_id WHERE p.goal_id=?"
        run_params = [goal_id]
        if registration_id:
            run_sql += " AND p.id=?"
            run_params.append(registration_id)
        return {"goal_id": goal_id, "registration_id": registration_id,
                "cost_by_currency": [{"currency": currency, "amount": amount} for currency, amount in sorted(costs.items())],
                "known_count": known, "unknown_count": unknown, "observation_total": known + unknown,
                "tokens": {"observed_subtotal": tokens if token_known else None, "known_count": token_known, "unknown_count": token_unknown},
                "run_total": c.execute(run_sql, run_params).fetchone()[0], "covered_registration_count": len(branches),
                "scope": "recorded_external_observations_only", "total_cost_status": "unknown", "provenance": "external_report_not_independently_verified"}

    def resource_summary(self, goal_id, registration_id=None):
        def read(c):
            self._required(c, "goals", goal_id)
            if registration_id and self._required(c, "registrations", registration_id)["goal_id"] != goal_id:
                raise ResearchError("INVALID_INPUT", "Resource branch belongs to another goal")
            return self._resource_summary(c, goal_id, registration_id) | {"revision": int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])}
        return self._read(read)

    def resource_show(self, goal_id, limit=20, offset=0):
        self._page(limit, offset)
        def read(c):
            self._required(c, "goals", goal_id)
            return {"items": [self._resource(row) for row in c.execute("SELECT * FROM resource_observations WHERE goal_id=? ORDER BY created DESC,id LIMIT ? OFFSET ?", (goal_id, limit, offset))],
                    "summary": self._resource_summary(c, goal_id), "limit": limit, "offset": offset,
                    "total": c.execute("SELECT COUNT(*) FROM resource_observations WHERE goal_id=?", (goal_id,)).fetchone()[0],
                    "revision": int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])}
        return self._read(read)

    def hypothesis_create(self, goal_id, statement, expected_revision=None):
        if not isinstance(statement, str) or not statement.strip():
            raise ResearchError("INVALID_INPUT", "Hypothesis statement must be text")
        record = {"id": _id("hyp"), "goal_id": goal_id, "statement": statement, "created": time.time()}
        def create(c):
            self._goal_writable(c, goal_id)
            c.execute("INSERT INTO hypotheses VALUES (:id,:goal_id,:statement,:created)", record)
            return dict(record), record["id"], True
        return self._write("hypothesis.create", expected_revision, create)

    def validator_register(self, name, command, key, expected_revision=None):
        self._authorize(key, owner=True)
        if not isinstance(name, str) or not name.strip() or not isinstance(command, list) or len(command) < 2 or not all(isinstance(v, str) for v in command):
            raise ResearchError("INVALID_INPUT", "Validator requires a name and Python argv template")
        if Path(command[0]).resolve() != Path(self.runner_interpreter()).resolve() or "{bundle}" not in command:
            raise ResearchError("INVALID_INPUT", "Validator must use the stored Python interpreter and a {bundle} argument")
        script = Path(command[1]).resolve()
        if not script.is_file() or script.suffix.lower() != ".py":
            raise ResearchError("INVALID_INPUT", "Validator must be a local Python script")
        digest = sha256_file(script)
        frozen = self.metadata_dir / "validators" / (digest + ".py")
        frozen.parent.mkdir(exist_ok=True)
        if not frozen.exists():
            shutil.copyfile(script, frozen)
        if sha256_file(frozen) != digest:
            raise ResearchError("EVIDENCE_TAMPERED", "Frozen validator content changed")
        relative_frozen = frozen.relative_to(self.root).as_posix()
        record = {"name": name, "command": [self.runner_interpreter(), relative_frozen, *command[2:]], "sha256": digest, "hashes": {relative_frozen: digest}, "script_path": relative_frozen, "original_path": str(script)}
        def create(c):
            previous = c.execute("SELECT record FROM validators WHERE name=?", (name,)).fetchone()
            if previous:
                if json.loads(previous[0]) != record:
                    raise ResearchError("REGISTRATION_IMMUTABLE", "Validator name is already fixed; use a new name")
                return self._resolve_validator(record), name, False
            c.execute("INSERT INTO validators VALUES (?,?,?)", (name, canonical(record), time.time()))
            return self._resolve_validator(record), name, True
        return self._write("validator.register", expected_revision, create)

    def get_validator(self, name):
        return self._read(lambda c: self._resolve_validator(json.loads(self._required(c, "validators", name, "name")["record"])))

    def _resolve_validator(self, record):
        result = dict(record)
        result["command"] = list(record["command"])
        result["command"][1] = str((self.root / record["command"][1]).resolve())
        result["hashes"] = {str((self.root / path).resolve()): digest for path, digest in record["hashes"].items()}
        result["script_path"] = result["command"][1]
        return result

    def _validate_spec(self, spec):
        if not isinstance(spec, dict):
            raise ResearchError("INVALID_INPUT", "Preregistration must be a JSON object")
        required = ("hypothesis_id", "change", "comparison", "data_split", "seed", "source_version", "metrics", "criteria", "command", "cwd", "artifacts", "validator")
        missing = [key for key in required if key not in spec]
        if missing:
            raise ResearchError("INVALID_INPUT", "Missing preregistration fields", {"missing": missing})
        spec = json.loads(canonical(spec))
        for field in ("hypothesis_id", "change", "comparison", "cwd", "validator"):
            if not isinstance(spec[field], str) or not spec[field].strip():
                raise ResearchError("INVALID_INPUT", "Preregistration field must be nonempty text", {"field": field})
        split = spec["data_split"]
        if not ((isinstance(split, str) and split.strip()) or (isinstance(split, dict) and split)):
            raise ResearchError("INVALID_INPUT", "data_split must describe nonempty split conditions")
        conditions = spec.get("conditions", {})
        if not isinstance(conditions, dict):
            raise ResearchError("INVALID_INPUT", "conditions must be a JSON object")
        if "timeout_seconds" in conditions:
            timeout = conditions["timeout_seconds"]
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
                raise ResearchError("INVALID_INPUT", "Registered timeout_seconds must be finite and positive")
        if not Path(spec["cwd"]).is_absolute():
            raise ResearchError("INVALID_INPUT", "cwd must be absolute")
        spec["cwd"] = str(Path(spec["cwd"]).resolve())
        if isinstance(spec["seed"], bool) or not isinstance(spec["seed"], int):
            raise ResearchError("INVALID_INPUT", "seed must be an integer")
        source = spec["source_version"]
        if not isinstance(source, dict) or not isinstance(source.get("label"), str) or not source["label"] or not isinstance(source.get("files"), dict) or not source["files"]:
            raise ResearchError("INVALID_INPUT", "source_version requires label and pinned files")
        files = {}
        for path, digest in source["files"].items():
            relative = _relative(path)
            if not _hash(digest):
                raise ResearchError("INVALID_INPUT", "Pinned source hash must be SHA-256", {"path": path})
            files[relative] = digest
        source["files"] = files
        command = spec["command"]
        if not isinstance(command, list) or len(command) < 2 or not all(isinstance(v, str) for v in command):
            raise ResearchError("INVALID_INPUT", "command must be a Python argv list")
        if Path(command[0]).resolve() != Path(self.runner_interpreter()).resolve():
            raise ResearchError("INVALID_INPUT", "Only the stored local Python interpreter is supported")
        command[0] = self.runner_interpreter()
        command[1] = _relative(command[1])
        if command[1] not in files or Path(command[1]).suffix.lower() != ".py":
            raise ResearchError("INVALID_INPUT", "Executed Python file must be pinned in source_version.files")
        metrics = spec["metrics"]
        if not isinstance(metrics, list) or not metrics or not all(isinstance(v, str) and v for v in metrics) or len(set(metrics)) != len(metrics):
            raise ResearchError("INVALID_INPUT", "metrics must contain distinct metric names")
        criteria = spec["criteria"]
        if not isinstance(criteria, list) or not criteria:
            raise ResearchError("INVALID_INPUT", "criteria must contain a success criterion")
        for criterion in criteria:
            if not isinstance(criterion, dict) or criterion.get("metric") not in metrics or criterion.get("op") not in (">", ">=", "<", "<=", "==", "!="):
                raise ResearchError("INVALID_INPUT", "Invalid registered metric criterion")
            threshold = criterion.get("threshold")
            if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
                raise ResearchError("INVALID_INPUT", "Criterion threshold must be a finite number")
        if not isinstance(spec["artifacts"], list) or not spec["artifacts"]:
            raise ResearchError("INVALID_INPUT", "At least one artifact must be registered")
        names = set()
        for artifact in spec["artifacts"]:
            if not isinstance(artifact, dict) or not isinstance(artifact.get("name"), str) or not artifact["name"] or artifact["name"] in names:
                raise ResearchError("INVALID_INPUT", "Artifact names must be distinct")
            if artifact["name"] in ("stdout", "stderr", "launch", "process") or artifact["name"].startswith("source:"):
                raise ResearchError("INVALID_INPUT", "Artifact name is reserved for runner evidence", {"name": artifact["name"]})
            names.add(artifact["name"])
            artifact["path"] = _relative(artifact.get("path"))
        return spec

    @staticmethod
    def _registration(row):
        record = dict(row)
        record["spec"] = json.loads(record["spec"])
        return record

    @staticmethod
    def _run(row):
        if not row:
            return None
        record = dict(row)
        record["receipt"] = json.loads(record["receipt"]) if record["receipt"] else None
        record["resources"] = json.loads(record["resources"])
        return record

    def register(self, goal_id, spec, request_key=None, expected_revision=None):
        if request_key is not None and (not isinstance(request_key, str) or not request_key):
            raise ResearchError("INVALID_INPUT", "Registration request key must be nonempty text")
        spec = self._validate_spec(spec)
        validator = self.get_validator(spec["validator"])
        spec["validator_sha256"] = validator["sha256"]
        actual = {key: value for key, value in spec.items() if key not in ("hypothesis_id", "description")}
        fingerprint = hashlib.sha256(canonical(actual).encode("utf-8")).hexdigest()
        def create(c):
            self._required(c, "goals", goal_id)
            hypothesis = self._required(c, "hypotheses", spec["hypothesis_id"])
            if hypothesis["goal_id"] != goal_id:
                raise ResearchError("INVALID_INPUT", "Hypothesis belongs to a different goal")
            if request_key is not None:
                previous = c.execute("SELECT * FROM requests WHERE scope='register' AND key=?", (request_key,)).fetchone()
                if previous and previous["fingerprint"] != fingerprint:
                    raise ResearchError("REQUEST_CONFLICT", "Request key was used for different experiment conditions")
            existing = c.execute("SELECT * FROM registrations WHERE fingerprint=?", (fingerprint,)).fetchone()
            reused = existing is not None
            if existing:
                registration = self._registration(existing)
                if registration["goal_id"] != goal_id:
                    raise ResearchError("DUPLICATE_EXPERIMENT", "Experiment already exists under another goal", {"registration_id": registration["id"]})
            else:
                goal = self._goal_writable(c, goal_id)
                registration = {"id": _id("reg"), "goal_id": goal_id, "hypothesis_id": spec["hypothesis_id"], "spec": spec, "fingerprint": fingerprint, "created": time.time()}
                c.execute("INSERT INTO registrations VALUES (?,?,?,?,?,?)", (registration["id"], goal_id, spec["hypothesis_id"], canonical(spec), fingerprint, registration["created"]))
                c.execute("INSERT INTO registration_goals VALUES (?,?,?,?)", (registration["id"], goal_id, goal["version"], "explicit"))
            goal_link = c.execute("SELECT goal_version,source FROM registration_goals WHERE registration_id=?", (registration["id"],)).fetchone()
            registration.update(goal_version=goal_link["goal_version"], goal_version_source=goal_link["source"])
            changed = not reused
            if request_key is not None:
                cursor = c.execute("INSERT OR IGNORE INTO requests VALUES ('register',?,?,?)", (request_key, fingerprint, registration["id"]))
                changed = changed or bool(cursor.rowcount)
            return {"registration": registration, "reused": reused}, registration["id"], changed
        return self._write("registration.create", expected_revision, create)

    def claim(self, reg_id, request_key, expected_revision=None):
        if not isinstance(request_key, str) or not request_key:
            raise ResearchError("INVALID_INPUT", "A run request key is required")
        def create(c):
            registration = self._required(c, "registrations", reg_id)
            previous = c.execute("SELECT * FROM requests WHERE scope='run' AND key=?", (request_key,)).fetchone()
            if previous and previous["fingerprint"] != registration["fingerprint"]:
                raise ResearchError("REQUEST_CONFLICT", "Run request key was used for another experiment")
            existing = c.execute("SELECT * FROM runs WHERE registration_id=?", (reg_id,)).fetchone()
            changed = False
            if existing:
                run = self._run(existing)
                claimed = False
            else:
                self._goal_writable(c, registration["goal_id"])
                if c.execute("SELECT 1 FROM decisions WHERE registration_id=?", (reg_id,)).fetchone():
                    raise ResearchError("INVALID_TRANSITION", "A decided registration cannot start execution")
                run = {"id": _id("run"), "registration_id": reg_id, "state": "running", "receipt": None, "resources": {"tokens": {"status": "unknown", "value": None}}, "reason": None, "created": time.time(), "finished": None}
                c.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)", (run["id"], reg_id, "running", None, canonical(run["resources"]), None, run["created"], None))
                claimed, changed = True, True
            if not previous:
                c.execute("INSERT INTO requests VALUES ('run',?,?,?)", (request_key, registration["fingerprint"], run["id"]))
                changed = True
            return {"claimed": claimed, "run": run}, run["id"], changed
        return self._write("run.claim", expected_revision, create)

    def _copy_evidence(self, path):
        original = Path(path)
        if not original.is_absolute():
            original = self.root / original
        original = original.resolve()
        digest = sha256_file(original)
        destination = self.metadata_dir / "evidence" / digest
        destination.parent.mkdir(exist_ok=True)
        if not destination.exists():
            temporary = destination.with_name(digest + "." + uuid.uuid4().hex + ".tmp")
            shutil.copyfile(original, temporary)
            if sha256_file(temporary) != digest:
                temporary.unlink(missing_ok=True)
                raise ResearchError("EVIDENCE_TAMPERED", "Evidence changed during collection")
            os.replace(temporary, destination)
        if sha256_file(destination) != digest:
            raise ResearchError("EVIDENCE_TAMPERED", "Stored evidence hash mismatch")
        return {"path": destination.relative_to(self.root).as_posix(), "sha256": digest, "size": destination.stat().st_size, "original_path": str(original)}

    def _insert_evidence(self, c, reg_id, item, run_id=None):
        kind, claim = item.get("kind", "measured"), item.get("claim", "")
        if kind not in ("measured", "literature", "inference", "proposal") or not isinstance(claim, str):
            raise ResearchError("INVALID_INPUT", "Evidence kind or claim is invalid")
        record = {"id": _id("ev"), "registration_id": reg_id, "run_id": run_id, "name": item.get("name"), "kind": kind, "claim": claim, "path": item.get("path"), "sha256": item.get("sha256"), "size": item.get("size"), "original_path": item.get("original_path"), "created": time.time()}
        c.execute("INSERT INTO evidence VALUES (:id,:registration_id,:run_id,:name,:kind,:claim,:path,:sha256,:size,:original_path,:created)", record)
        record["verified"] = False
        return record

    def complete_run(self, run_id, receipt, evidence_list, resources, authority):
        self._authorize(authority)
        if not isinstance(receipt, dict) or receipt.get("state") not in ("succeeded", "failed", "cancelled") or not isinstance(evidence_list, list) or not isinstance(resources, dict):
            raise ResearchError("INVALID_INPUT", "Execution component must supply a terminal receipt and resource record")
        if receipt["state"] == "cancelled" and (not isinstance(receipt.get("cancellation"), dict) or receipt["cancellation"].get("confirmed") is not True or not isinstance(receipt["cancellation"].get("reason"), str) or not receipt["cancellation"]["reason"].strip()):
            raise ResearchError("INVALID_INPUT", "Cancelled execution needs the execution component's confirmed cancellation receipt and reason")
        if receipt.get("run_id", run_id) != run_id:
            raise ResearchError("EVIDENCE_TAMPERED", "Receipt belongs to a different execution")
        canonical(receipt)
        canonical(resources)
        prepared = []
        for item in evidence_list:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"] or not item.get("path"):
                raise ResearchError("INVALID_INPUT", "Execution evidence requires a name and file path")
            copied = self._copy_evidence(item["path"])
            if item.get("sha256") and item["sha256"] != copied["sha256"]:
                raise ResearchError("EVIDENCE_TAMPERED", "Execution evidence differs from receipt", {"name": item["name"]})
            copied["original_path"] = item.get("original_path", item.get("origin_path", copied["original_path"]))
            prepared.append({**item, **copied})
        def complete(c):
            run = self._run(self._required(c, "runs", run_id))
            if run["state"] in ("succeeded", "failed", "cancelled"):
                if run["receipt"] != receipt:
                    raise ResearchError("INVALID_TRANSITION", "Completion evidence is already fixed")
                return {"run": run, "reused": True}, run_id, False
            for item in prepared:
                self._insert_evidence(c, run["registration_id"], item, run_id)
            merged_resources = {"tokens": {"status": "unknown", "value": None}, **resources}
            c.execute("UPDATE runs SET state=?,receipt=?,resources=?,finished=?,reason=? WHERE id=?", (receipt["state"], canonical(receipt), canonical(merged_resources), time.time(), receipt.get("error"), run_id))
            return {"run": self._run(self._required(c, "runs", run_id)), "reused": False}, run_id, True
        return self._write("run.complete", None, complete)

    def mark_unknown(self, run_id, reason):
        def update(c):
            run = self._run(self._required(c, "runs", run_id))
            if run["state"] not in ("running", "unknown"):
                raise ResearchError("INVALID_TRANSITION", "Completed execution cannot become unknown")
            if run["state"] == "unknown" and run["reason"] == reason:
                return {"run": run, "next": "recover"}, run_id, False
            c.execute("UPDATE runs SET state='unknown',reason=? WHERE id=?", (str(reason), run_id))
            return {"run": self._run(self._required(c, "runs", run_id)), "next": "recover"}, run_id, True
        return self._write("run.unknown", None, update)

    def _integrity(self, evidence):
        for item in evidence:
            if item["path"]:
                path = (self.root / item["path"]).resolve()
                if not path.is_relative_to(self.metadata_dir.resolve()):
                    raise ResearchError("EVIDENCE_TAMPERED", "Evidence reference leaves the store")
                if sha256_file(path) != item["sha256"]:
                    raise ResearchError("EVIDENCE_TAMPERED", "Stored evidence no longer matches its hash", {"evidence_id": item["id"], "path": item["path"]})

    def complete_verification(self, run_id, metrics, details, authority):
        self._authorize(authority)
        if not isinstance(metrics, dict) or not isinstance(details, dict):
            raise ResearchError("INVALID_INPUT", "Verification requires metrics and details objects")
        canonical(metrics)
        canonical(details)
        input_digest = hashlib.sha256(canonical({"metrics": metrics, "details": details}).encode("utf-8")).hexdigest()
        def complete(c):
            run = self._run(self._required(c, "runs", run_id))
            if run["state"] not in ("succeeded", "failed"):
                raise ResearchError("INVALID_TRANSITION", "Verification requires a known terminal execution")
            previous = c.execute("SELECT * FROM verifications WHERE run_id=?", (run_id,)).fetchone()
            if previous:
                existing = dict(previous)
                existing["metrics"], existing["details"] = json.loads(existing["metrics"]), json.loads(existing["details"])
                if existing["details"].get("_input_sha256") != input_digest:
                    raise ResearchError("INVALID_TRANSITION", "Verification result is already fixed")
                self._integrity([dict(row) for row in c.execute("SELECT * FROM evidence WHERE run_id=?", (run_id,))])
                return {"verification": existing, "reused": True}, run_id, False
            registration = self._registration(self._required(c, "registrations", run["registration_id"]))
            evidence = [dict(row) for row in c.execute("SELECT * FROM evidence WHERE run_id=?", (run_id,))]
            info = dict(details)
            try:
                self._integrity(evidence)
            except ResearchError as exc:
                info["integrity"] = False
                info["integrity_error"] = {"code": exc.code, "message": exc.message, "details": exc.details}
            spec = registration["spec"]
            validator = self._resolve_validator(json.loads(self._required(c, "validators", spec["validator"], "name")["record"]))
            for path, digest in validator["hashes"].items():
                try:
                    if sha256_file(path) != digest or digest != spec["validator_sha256"]:
                        raise ResearchError("EVIDENCE_TAMPERED", "Registered validator has changed")
                except ResearchError as exc:
                    info["integrity"] = False
                    info["integrity_error"] = {"code": exc.code, "message": exc.message, "details": exc.details}
            names = {item["name"] for item in evidence if item["kind"] == "measured" and item["path"]}
            missing = [item["name"] for item in spec["artifacts"] if item["name"] not in names]
            absent_metrics = [name for name in spec["metrics"] if name not in metrics or isinstance(metrics[name], bool) or not isinstance(metrics[name], (int, float)) or not math.isfinite(metrics[name])]
            info["missing_artifacts"], info["missing_metrics"] = missing, absent_metrics
            tests = []
            if run["state"] != "succeeded" or missing or absent_metrics or info.get("integrity") is False or info.get("error"):
                state = "inconclusive"
            else:
                operations = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
                for criterion in spec["criteria"]:
                    value = metrics[criterion["metric"]]
                    tests.append({**criterion, "actual": value, "passed": operations[criterion["op"]](value, criterion["threshold"])})
                state = "passed" if all(test["passed"] for test in tests) else "failed"
            info["criteria_results"] = tests
            info["_input_sha256"] = input_digest
            record = {"run_id": run_id, "state": state, "metrics": metrics, "details": info, "created": time.time()}
            c.execute("INSERT INTO verifications VALUES (?,?,?,?,?)", (run_id, state, canonical(metrics), canonical(info), record["created"]))
            return {"verification": record, "reused": False}, run_id, True
        return self._write("verification.complete", None, complete)

    def decide(self, reg_id, decision, reason, expected_revision=None):
        if decision not in ("adopted", "rejected", "inconclusive") or not isinstance(reason, str) or not reason.strip():
            raise ResearchError("INVALID_INPUT", "Decision requires an allowed state and a reason")
        def create(c):
            self._required(c, "registrations", reg_id)
            previous = c.execute("SELECT * FROM decisions WHERE registration_id=?", (reg_id,)).fetchone()
            if previous:
                if previous["state"] != decision or previous["reason"] != reason:
                    raise ResearchError("INVALID_TRANSITION", "Research decision is already recorded")
                return {"decision": dict(previous), "reused": True}, reg_id, False
            run = c.execute("SELECT * FROM runs WHERE registration_id=?", (reg_id,)).fetchone()
            if decision == "adopted":
                if not run or run["state"] != "succeeded":
                    raise ResearchError("INVALID_TRANSITION", "Adoption requires successful execution and verification")
                verification = c.execute("SELECT * FROM verifications WHERE run_id=?", (run["id"],)).fetchone()
                if not verification or verification["state"] != "passed":
                    raise ResearchError("INVALID_TRANSITION", "Adoption requires independent verification to pass")
                self._integrity([dict(row) for row in c.execute("SELECT * FROM evidence WHERE run_id=?", (run["id"],))])
            record = {"registration_id": reg_id, "state": decision, "reason": reason, "created": time.time()}
            c.execute("INSERT INTO decisions VALUES (?,?,?,?)", (reg_id, decision, reason, record["created"]))
            return {"decision": record, "reused": False}, reg_id, True
        return self._write("decision.create", expected_revision, create)

    def add_evidence(self, reg_id, kind, claim, path=None, expected_revision=None):
        item = {"kind": kind, "claim": claim}
        if path:
            item.update(self._copy_evidence(path))
        def create(c):
            self._required(c, "registrations", reg_id)
            return {"evidence": self._insert_evidence(c, reg_id, item)}, reg_id, True
        return self._write("evidence.add", expected_revision, create)

    def _show(self, c, identifier):
        registration = c.execute("SELECT * FROM registrations WHERE id=?", (identifier,)).fetchone()
        if not registration:
            run = self._required(c, "runs", identifier)
            registration = self._required(c, "registrations", run["registration_id"])
        registration = self._registration(registration)
        goal_link = c.execute("SELECT goal_version,source FROM registration_goals WHERE registration_id=?", (registration["id"],)).fetchone()
        registration.update(goal_version=goal_link["goal_version"], goal_version_source=goal_link["source"])
        run = self._run(c.execute("SELECT * FROM runs WHERE registration_id=?", (registration["id"],)).fetchone())
        evidence = [dict(row) for row in c.execute("SELECT * FROM evidence WHERE registration_id=? ORDER BY created,id", (registration["id"],))]
        verification = c.execute("SELECT * FROM verifications WHERE run_id=?", (run["id"],)).fetchone() if run else None
        if verification:
            verification = dict(verification)
            verification["metrics"], verification["details"] = json.loads(verification["metrics"]), json.loads(verification["details"])
        else:
            verification = None
        for item in evidence:
            item["integrity"] = self._evidence_integrity(item)
            item["verified"] = bool(verification and verification["state"] == "passed" and item["run_id"] == (run["id"] if run else None) and item["kind"] == "measured" and item["integrity"] == "valid")
        decision = c.execute("SELECT * FROM decisions WHERE registration_id=?", (registration["id"],)).fetchone()
        hypothesis = self._required(c, "hypotheses", registration["hypothesis_id"])
        return {"registration": registration, "hypothesis": hypothesis, "run": run, "evidence": evidence, "verification": verification, "decision": dict(decision) if decision else {"state": "pending"}, "revision": int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])}

    def show(self, identifier):
        return self._read(lambda c: self._show(c, identifier))

    def _evidence_integrity(self, item):
        if not item["path"]:
            return "no_file"
        try:
            path = (self.root / item["path"]).resolve()
            if not path.is_relative_to(self.metadata_dir.resolve()):
                return "tampered"
            return "valid" if sha256_file(path) == item["sha256"] else "tampered"
        except ResearchError:
            return "missing"

    def memory(self, query="", outcome=None, verification=None, limit=20, offset=0):
        if not isinstance(query, str) or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100 or isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ResearchError("INVALID_INPUT", "Memory requires text query, limit 1..100, and nonnegative offset")
        if outcome not in (None, "success", "failure", "inconclusive") or verification not in (None, "pending", "passed", "failed", "inconclusive"):
            raise ResearchError("INVALID_INPUT", "Unknown memory outcome or verification filter")
        def search(c):
            clauses, parameters = [], []
            outcome_expr = "CASE WHEN d.state='adopted' OR (v.state='passed' AND (d.state IS NULL OR d.state='pending')) THEN 'success' WHEN r.state='failed' OR v.state='failed' OR d.state='rejected' THEN 'failure' ELSE 'inconclusive' END"
            if query:
                clauses.append("(h.statement LIKE ? ESCAPE '\\' OR g.title LIKE ? ESCAPE '\\' OR p.spec LIKE ? ESCAPE '\\' OR d.reason LIKE ? ESCAPE '\\' OR r.reason LIKE ? ESCAPE '\\' OR EXISTS(SELECT 1 FROM evidence e WHERE e.registration_id=p.id AND e.claim LIKE ? ESCAPE '\\'))")
                escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                parameters.extend(["%" + escaped + "%"] * 6)
            if outcome:
                clauses.append(outcome_expr + "=?")
                parameters.append(outcome)
            if verification:
                clauses.append("COALESCE(v.state,'pending')=?")
                parameters.append(verification)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            joined = " FROM registrations p JOIN registration_goals pg ON pg.registration_id=p.id JOIN goal_versions g ON g.goal_id=pg.goal_id AND g.version=pg.goal_version JOIN hypotheses h ON h.id=p.hypothesis_id LEFT JOIN runs r ON r.registration_id=p.id LEFT JOIN verifications v ON v.run_id=r.id LEFT JOIN decisions d ON d.registration_id=p.id"
            total = c.execute("SELECT COUNT(*)" + joined + where, parameters).fetchone()[0]
            rows = c.execute("SELECT p.id,p.goal_id,pg.goal_version,pg.source AS goal_version_source,p.spec,h.statement AS hypothesis,COALESCE(r.state,'registered') AS execution,COALESCE(v.state,'pending') AS verification,COALESCE(d.state,'pending') AS decision," + outcome_expr + " AS outcome,d.reason,r.resources,(SELECT COUNT(*) FROM evidence e WHERE e.registration_id=p.id) AS evidence_count" + joined + where + " ORDER BY p.created DESC,p.id LIMIT ? OFFSET ?", [*parameters, limit, offset]).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                spec = json.loads(item.pop("spec"))
                item["summary"] = spec["change"]
                item["conditions"] = {field: spec[field] for field in ("comparison", "data_split", "seed", "source_version")}
                run_evidence = c.execute("SELECT e.* FROM evidence e JOIN runs r ON r.id=e.run_id WHERE r.registration_id=?", (item["id"],)).fetchall()
                item["evidence_integrity"] = "valid" if all(self._evidence_integrity(dict(ev)) == "valid" for ev in run_evidence) else "invalid"
                item["claim_verified"] = item["verification"] == "passed" and item["evidence_integrity"] == "valid"
                item["resources"] = json.loads(item["resources"]) if item["resources"] else {"tokens": {"status": "unknown", "value": None}}
                items.append(item)
            return {"items": items, "total": total, "limit": limit, "offset": offset, "revision": int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])}
        return self._read(search)

    def status(self, goal_id=None, limit=20, offset=0):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100 or isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ResearchError("INVALID_INPUT", "Status requires limit 1..100 and nonnegative offset")
        def describe(c):
            if goal_id:
                goals = [self._goal(c, goal_id)]
                total = c.execute("SELECT COUNT(*) FROM registrations WHERE goal_id=?", (goal_id,)).fetchone()[0]
                registrations = c.execute("SELECT id FROM registrations WHERE goal_id=? ORDER BY created LIMIT ? OFFSET ?", (goal_id, limit, offset)).fetchall()
                hypothesis_total = c.execute("SELECT COUNT(*) FROM hypotheses WHERE goal_id=?", (goal_id,)).fetchone()[0]
                hypotheses = [dict(row) for row in c.execute("SELECT * FROM hypotheses WHERE goal_id=? ORDER BY created LIMIT ? OFFSET ?", (goal_id, limit, offset))]
            else:
                goals = [self._goal(c, row["id"]) for row in c.execute("SELECT id FROM goals ORDER BY created LIMIT ? OFFSET ?", (limit, offset))]
                total = c.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
                registrations = c.execute("SELECT id FROM registrations ORDER BY created LIMIT ? OFFSET ?", (limit, offset)).fetchall()
                hypothesis_total = c.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0]
                hypotheses = [dict(row) for row in c.execute("SELECT * FROM hypotheses ORDER BY created LIMIT ? OFFSET ?", (limit, offset))]
            summaries = []
            for row in registrations:
                record = self._show(c, row["id"])
                run, verification, decision = record["run"], record["verification"] or {"state": "pending"}, record["decision"]
                execution = run["state"] if run else "registered"
                missing, allowed = [], ["show", "memory", "evidence"]
                if decision["state"] == "pending":
                    if execution == "registered":
                        allowed += (["run"] if self._goal(c, record["registration"]["goal_id"])["state"] in ("active", "unknown") else ["goal_resume"]) + ["decide"]
                        missing += ["execution receipt", "verified artifact metrics"]
                    elif execution in ("running", "unknown"):
                        allowed += ["recover"]
                        missing += ["confirmed terminal execution receipt"]
                    elif execution == "succeeded" and verification["state"] == "pending":
                        allowed += ["verify", "decide"]
                        missing += ["independent verification"]
                    else:
                        allowed += ["decide"]
                summaries.append({"id": row["id"], "execution": execution, "verification": verification["state"], "decision": decision["state"], "allowed_actions": allowed, "missing_evidence": missing})
            allowed = ["goal", "goal_show", "goal_amend", "goal_close", "goal_resume", "resource", "resource_show", "memory", "show", "export"]
            if not goal_id or goals[0]["state"] in ("active", "unknown"):
                allowed += ["hypothesis", "register"]
            return {"workspace": str(self.root), "goals": goals, "goal_total": c.execute("SELECT COUNT(*) FROM goals").fetchone()[0], "hypotheses": hypotheses, "hypothesis_total": hypothesis_total, "registrations": summaries, "total": total, "limit": limit, "offset": offset, "allowed_actions": allowed, "revision": int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])}
        return self._read(describe)
