"""Durable goals across channels; real concurrency, migration and archive checks."""
import concurrent.futures
import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile

from research_cli.core import ResearchError, Store, _SCHEMA, canonical, sha256_file
from research_cli.mcp_bridge import Bridge
from research_cli.runner import recover
from research_cli.transfer import export, restore
from research_cli.web_tools import call_tool


ROOT = Path(__file__).resolve().parents[1]


class GoalContract(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="goal-contract-")
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "dedicated"
        Store.init(self.workspace)
        self.store = Store(self.workspace)
        self.bridge = Bridge(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def error(self, code, function, *args, **kwargs):
        with self.assertRaises(ResearchError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def goal(self):
        return self.store.goal_create("실제 연구 질문", "원 의뢰", brief={"original_request": "모호한 의뢰", "unknowns": ["outside usage"]}, request_key="shared-goal", expected_revision=0)

    def preregister(self, goal):
        hypothesis = self.store.hypothesis_create(goal, "External hypothesis")
        script = self.root / "validator.py"
        script.write_text("print('{}')\n", encoding="utf-8")
        self.store.validator_register("fixed", [sys.executable, str(script), "{bundle}"], self.store.owner_key_path.read_text())
        source = self.workspace / "experiment"
        source.mkdir()
        (source / "task.py").write_text("print('fixture')\n", encoding="utf-8")
        spec = {"hypothesis_id": hypothesis["id"], "change": "fixture", "comparison": "fixed expectation",
                "data_split": "development fixture", "seed": 1, "source_version": {"label": "v1", "files": {"task.py": sha256_file(source / "task.py")}},
                "metrics": ["correct"], "criteria": [{"metric": "correct", "op": ">=", "threshold": 1}],
                "command": [sys.executable, "task.py"], "cwd": str(source), "artifacts": [{"name": "result", "path": "result.json"}], "validator": "fixed"}
        return self.store.register(goal, spec, "registration")

    def test_legacy_client_append_after_migration_is_visible_without_invented_lifecycle(self):
        goal = self.goal()['id']
        registered = self.preregister(goal)['registration']
        revision = self.store.revision()
        # Exact original-table writes made by a v1 client that remained running.
        with closing(sqlite3.connect(self.store.db_path)) as connection, connection:
            connection.execute('INSERT INTO goals VALUES (?,?,?,?)', ('legacy-writer-goal','Old client','Preserved',1234))
            row = connection.execute('SELECT * FROM registrations WHERE id=?',(registered['id'],)).fetchone()
            legacy_registration = ('legacy-writer-registration', *row[1:])
            legacy_registration = list(legacy_registration)
            legacy_spec = json.loads(legacy_registration[3])
            legacy_spec['change'] = 'Explicit second legacy writer experiment'
            legacy_registration[4] = hashlib.sha256(canonical({k:v for k,v in legacy_spec.items() if k not in ('hypothesis_id','description')}).encode()).hexdigest()
            legacy_registration[3] = canonical(legacy_spec)
            connection.execute('INSERT INTO registrations VALUES (?,?,?,?,?,?)',legacy_registration)
        detail = self.store.goal_show('legacy-writer-goal')['goal']
        self.assertEqual(detail['state'],'unknown')
        self.assertEqual(detail['state_source'],'legacy_mapping')
        self.assertEqual(detail['brief'],{})
        self.assertEqual(self.store.show('legacy-writer-registration')['registration']['goal_version_source'],'legacy_mapping')
        self.assertEqual(self.store.revision(),revision)
        self.assertEqual(self.store.goal_show(goal)['goal']['state'],'active')

    def test_actual_cli_web_and_bridge_share_idempotent_goal(self):
        payload = {"original_request": "모호한 의뢰", "unknowns": ["outside usage"]}
        completed = subprocess.run([sys.executable, "-m", "research_cli", "--workspace", str(self.workspace), "goal", "--title", "실제 연구 질문", "--description", "원 의뢰", "--input", "-", "--request-key", "shared-goal", "--expect", "0"],
                                   input=json.dumps(payload), text=True, encoding="utf-8", capture_output=True, cwd=ROOT)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        first = json.loads(completed.stdout)["data"]
        params = {"title": "실제 연구 질문", "description": "원 의뢰", "brief": payload, "request_key": "shared-goal", "expect": 0, "workspace": "dedicated"}
        web = call_tool(self.bridge, "research_goal", params)
        stdio_path = self.bridge.call("goal", **params)
        self.assertEqual(first["id"], web["data"]["id"])
        self.assertEqual(first["id"], stdio_path["data"]["id"])
        self.assertTrue(web["data"]["reused"])
        self.assertEqual(self.store.status()["goal_total"], 1)
        self.assertEqual(self.store.revision(), 1)

    def test_concurrent_same_request_creates_one_goal(self):
        def create(_):
            return self.bridge.call("goal", workspace="dedicated", title="same", brief={"facts": []}, request_key="same", expect=0)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(create, range(8)))
        self.assertTrue(all(item["ok"] for item in results), results)
        self.assertEqual(len({item["data"]["id"] for item in results}), 1)
        self.assertEqual(sum(not item["data"]["reused"] for item in results), 1)
        self.assertEqual(self.store.revision(), 1)

    def test_changed_payload_conflicts_and_concurrent_distinct_requests_detect_revision(self):
        first = self.goal()
        self.error("REQUEST_CONFLICT", self.store.goal_create, "different", request_key="shared-goal", expected_revision=0)
        def amend(index):
            return self.bridge.call("goal_amend", workspace="dedicated", goal=first["id"], brief=first["brief"] | {"plan": index}, reason="Explicit plan change", change_kind="plan", request_key=str(index), expect=1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(amend, [1, 2]))
        self.assertEqual(sum(item["ok"] for item in results), 1)
        self.assertEqual([item["error"]["code"] for item in results if not item["ok"]], ["REVISION_CONFLICT"])
        self.assertEqual(self.store.goal_show(first["id"])["version_total"], 2)

    def test_versions_are_immutable_and_registration_pins_original_version(self):
        goal = self.goal()["id"]
        registered = self.preregister(goal)["registration"]
        before = self.store.show(registered["id"])["registration"]
        self.store.goal_amend(goal, {"scope": "explicitly amended"}, "Changed goal and scope", "meaning", "scope", self.store.revision(), title="Changed title")
        after = self.store.show(registered["id"])["registration"]
        self.assertEqual(before, after)
        self.assertEqual(after["goal_version"], 1)
        detail = self.store.goal_show(goal, limit=1)
        self.assertEqual(detail["goal"]["version"], 2)
        self.assertEqual(detail["versions"][0]["change_kind"], "meaning")
        self.assertEqual(detail["version_total"], 2)
        with closing(sqlite3.connect(self.store.db_path)) as connection, connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE goal_versions SET brief='{}' WHERE goal_id=?", (goal,))
        self.error("INVALID_INPUT", self.store.goal_amend, goal, {}, "change", "implicit", "bad", self.store.revision())
        self.error("INVALID_INPUT", self.store.goal_amend, goal, {"long_term_goal": "Different scientific question"}, "silent plan change", "plan", "hidden-goal-change", self.store.revision())
        self.assertEqual(self.store.memory(query="실제 연구 질문")["items"][0]["goal_version"], 1)
        self.assertEqual(self.store.memory(query="Changed title")["total"], 0)

    def test_pause_resume_same_goal_preserves_incomplete_and_no_execution(self):
        goal = self.goal()["id"]
        revision = self.store.revision()
        paused = call_tool(self.bridge, "research_goal_close", {"workspace": "dedicated", "goal": goal, "state": "paused", "reason": "Waiting for data", "results": ["Question scoped"], "incomplete": ["Independent evaluation"], "request_key": "pause", "expect": revision})
        self.assertTrue(paused["ok"], paused)
        self.assertEqual(paused["data"]["goal"]["state"], "paused")
        self.error("INVALID_TRANSITION", self.store.hypothesis_create, goal, "do not proceed")
        replay = self.store.goal_close(goal, "paused", "Waiting for data", ["Question scoped"], ["Independent evaluation"], "pause", revision)
        self.assertTrue(replay["reused"])
        resumed = self.store.goal_resume(goal, "Data permission observed", "resume", self.store.revision())
        self.assertEqual(resumed["goal"]["id"], goal)
        self.assertEqual(resumed["goal"]["lifecycle"]["incomplete"], ["Independent evaluation"])
        self.assertEqual(self.store.status()["total"], 0)
        self.error("INVALID_TRANSITION", self.store.goal_resume, goal, "again", "again", self.store.revision())

    def test_goal_cancel_does_not_claim_worker_cancelled_and_completed_requires_resolution(self):
        goal = self.goal()["id"]
        registration = self.preregister(goal)["registration"]["id"]
        execution = self.store.claim(registration, "claim")["run"]
        self.store.mark_unknown(execution["id"], "No observed receipt")
        self.error("INVALID_TRANSITION", self.store.goal_close, goal, "completed", "declare success", [], [], "complete", self.store.revision())
        closed = self.store.goal_close(goal, "cancelled", "User stopped", [], ["Original execution confirmation"], "cancel", self.store.revision())
        self.assertEqual(closed["unresolved_runs"][0]["state"], "unknown")
        self.assertEqual(self.store.show(registration)["run"]["state"], "unknown")
        self.assertEqual(self.store.claim(registration, "same-known-run")["run"]["id"], execution["id"])

    def test_cancelled_execution_only_from_confirmed_execution_receipt(self):
        goal = self.goal()["id"]
        registration = self.preregister(goal)["registration"]["id"]
        execution = self.store.claim(registration, "claim")["run"]
        receipt = {"state": "cancelled", "run_id": execution["id"]}
        self.error("INVALID_INPUT", self.store.complete_run, execution["id"], receipt, [], {}, self.store.internal_key())
        receipt["cancellation"] = {"confirmed": True, "reason": "Executor declined before launch"}
        self.error("AUTHORITY_REQUIRED", self.store.complete_run, execution["id"], receipt, [], {}, "agent assertion")
        self.store.complete_run(execution["id"], receipt, [], {}, self.store.internal_key())
        self.assertEqual(recover(self.store, registration)["record"]["run"]["state"], "cancelled")
        self.error("INVALID_TRANSITION", self.store.mark_unknown, execution["id"], "reset")
        self.assertEqual(self.store.memory()["items"][0]["outcome"], "inconclusive")

    def test_resource_observation_dedup_unknown_units_and_scope(self):
        goal = self.goal()["id"]
        observation = {"source": "actual external log", "source_ref": "receipt-1", "cost": {"status": "known", "amount": 0.25, "currency": "USD"}, "tokens": {"status": "known", "value": 100}}
        first = self.store.resource_record(goal, observation, "cost1")
        self.assertTrue(self.store.resource_record(goal, observation, "cost2")["reused"])
        self.assertEqual(first["observation"]["provenance"], "external_report")
        self.store.resource_record(goal, {"source": "different external log", "source_ref": "receipt-2"}, "unknown")
        self.store.resource_record(goal, {"source": "third log", "source_ref": "receipt-3", "cost": {"status": "known", "amount": 100, "currency": "KRW"}}, "won")
        summary = self.store.resource_summary(goal)
        self.assertEqual(summary["cost_by_currency"], [{"currency": "KRW", "amount": 100}, {"currency": "USD", "amount": 0.25}])
        self.assertEqual((summary["known_count"], summary["unknown_count"]), (2, 1))
        self.assertEqual(summary["total_cost_status"], "unknown")
        self.assertEqual(summary["tokens"]["observed_subtotal"], 100)
        self.assertEqual(self.store.resource_show(goal, limit=1)["total"], 3)
        self.error("REQUEST_CONFLICT", self.store.resource_record, goal, observation | {"note": "changed fixed receipt"}, "changed")
        self.error("INVALID_INPUT", self.store.resource_record, goal, {"source": "log", "source_ref": "bad", "cost": {"status": "unknown", "amount": 1}}, "bad")

    def test_resource_branch_relation_and_archive_roundtrip(self):
        goal = self.goal()["id"]
        registration = self.preregister(goal)["registration"]["id"]
        execution = self.store.claim(registration, "claim")["run"]
        self.store.resource_record(goal, {"source": "receipt", "source_ref": "one", "run_id": execution["id"]}, "one")
        self.assertEqual(self.store.resource_summary(goal)["covered_registration_count"], 1)
        other = self.store.goal_create("other")["id"]
        self.error("INVALID_INPUT", self.store.resource_record, other, {"source": "receipt", "source_ref": "wrong", "run_id": execution["id"]}, "wrong")
        archive = self.root / "archive.zip"
        export(self.store, archive)
        restored = self.root / "restored"
        restore(restored, archive)
        store = Store(restored)
        self.assertEqual(store.goal_show(goal)["goal"], self.store.goal_show(goal)["goal"])
        self.assertEqual(store.resource_show(goal)["items"], self.store.resource_show(goal)["items"])
        self.assertEqual(store.show(registration)["run"]["state"], "running")
        self.assertFalse((restored / ".research" / "runs").exists())

    def test_atomic_legacy_migration_preserves_revision_records_and_concurrent_open(self):
        legacy = self.root / "legacy"
        metadata = legacy / ".research"
        metadata.mkdir(parents=True)
        (metadata / "owner.key").write_text("owner")
        (metadata / "internal.key").write_text("internal")
        database = metadata / "state.sqlite3"
        with closing(sqlite3.connect(database)) as c, c:
            c.executescript(_SCHEMA)
            c.executemany("INSERT INTO meta VALUES (?,?)", [("schema_version", "1"), ("revision", "7"), ("runner_interpreter", sys.executable)])
            c.execute("INSERT INTO goals VALUES ('old-goal','Old goal','Raw description',100)")
            c.execute("INSERT INTO hypotheses VALUES ('old-hyp','old-goal','Raw hypothesis',101)")
            c.execute("INSERT INTO registrations VALUES ('old-reg','old-goal','old-hyp','{}','old-fingerprint',102)")
            c.execute("INSERT INTO runs VALUES ('old-run','old-reg','failed','{}','{}','Raw failure',103,104)")
            c.execute("INSERT INTO events(revision,action,target,data,created) VALUES (7,'old.action','old-run','{}',104)")
            before = {table: c.execute("SELECT * FROM " + table).fetchall() for table in ("goals", "hypotheses", "registrations", "runs", "events")}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            stores = list(pool.map(lambda _: Store(legacy), range(4)))
        store = stores[0]
        self.assertEqual(store.revision(), 7)
        goal = store.goal_show("old-goal")["goal"]
        self.assertEqual((goal["version"], goal["state"], goal["state_source"], goal["brief"]), (1, "unknown", "legacy_mapping", {}))
        with closing(sqlite3.connect(database)) as c, c:
            self.assertEqual(c.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], "2")
            self.assertEqual({table: c.execute("SELECT * FROM " + table).fetchall() for table in before}, before)
        mapped = store.show("old-reg")["registration"]
        self.assertEqual((mapped["goal_version"], mapped["goal_version_source"]), (1, "legacy_mapping"))

    def test_v1_archive_restores_with_compatible_migration_and_no_new_research_event(self):
        database = self.root / "original-v1.sqlite3"
        with closing(sqlite3.connect(database)) as c, c:
            c.executescript(_SCHEMA)
            c.executemany("INSERT INTO meta VALUES (?,?)", [("schema_version", "1"), ("revision", "2"), ("runner_interpreter", sys.executable)])
            c.execute("INSERT INTO goals VALUES ('original-goal','Preserved request','Original description',100)")
        content = database.read_bytes()
        manifest = {"format": "research-state-export-v1", "files": {".research/state.sqlite3": {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}}}
        archive = self.root / "v1.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr(".research/state.sqlite3", content)
            output.writestr("manifest.json", canonical(manifest))
        destination = self.root / "restored-v1"
        restore(destination, archive)
        store = Store(destination)
        self.assertEqual(store.revision(), 2)
        self.assertEqual(store.goal_show("original-goal")["goal"]["state"], "unknown")
        with closing(sqlite3.connect(store.db_path)) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
