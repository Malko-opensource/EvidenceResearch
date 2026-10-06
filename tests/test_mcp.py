"""Optional SDK transport contracts for the installed research MCP wrapper.

These tests exercise actual stdio JSON-RPC, not an in-memory mock server. The
base CLI has no MCP dependency; its standard-library test run skips this module.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

try:
    from mcp import Client, StdioServerParameters
except ImportError:
    Client = StdioServerParameters = None

from research_cli.core import Store


ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    "research_help", "research_init", "research_goal", "research_hypothesis",
    "research_register", "research_status", "research_memory", "research_show",
    "research_run", "research_recover", "research_verify", "research_decide",
    "research_evidence", "research_export", "research_restore",
    "research_laya_prepare", "research_laya_resolve",
    "research_goal_show", "research_goal_amend", "research_goal_close", "research_goal_resume",
    "research_resource", "research_resource_show",
}


@unittest.skipUnless(Client is not None, "Optional MCP SDK is not installed")
class ResearchMCPTransport(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_root = ROOT / "tests" / ".runs"
        self.test_root.mkdir(exist_ok=True)
        self.temporary = Path(tempfile.mkdtemp(prefix="mcp-", dir=self.test_root)).resolve()
        self.server_root = self.temporary / "server-root"
        self.server_root.mkdir()
        self.workspace = self.server_root / "default"
        self.env = dict(os.environ)
        self.env["PYTHONPATH"] = str(ROOT) + os.pathsep + self.env.get("PYTHONPATH", "")
        self.env["PYTHONUTF8"] = "1"

    def tearDown(self):
        self.assertTrue(self.temporary.is_relative_to(self.test_root.resolve()))
        shutil.rmtree(self.temporary)

    def client(self):
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "research_cli.mcp_server", "--root", str(self.server_root)],
            env=self.env, cwd=self.temporary,
        )
        # This is transport hang detection for tests, not an experiment timeout.
        return Client(parameters, read_timeout_seconds=30)

    async def call(self, client, operation, error=None, **params):
        result = await client.call_tool("research_" + operation, params)
        envelope = result.structured_content
        self.assertIsInstance(envelope, dict, result)
        # Human-readable content and machine-readable content must agree.
        textual = [item.text for item in result.content if item.type == "text"]
        self.assertTrue(textual, result)
        self.assertEqual(json.loads(textual[0]), envelope)
        if error:
            self.assertTrue(result.is_error, envelope)
            self.assertFalse(envelope["ok"], envelope)
            self.assertEqual(envelope["error"]["code"], error, envelope)
            return envelope["error"]
        self.assertFalse(result.is_error, envelope)
        self.assertTrue(envelope["ok"], envelope)
        return envelope["data"]

    async def fixture(self, client, *, label="fixture", blocked=False):
        initialized = await self.call(client, "init")
        goal = (await self.call(client, "goal", title="MCP 실제 도구 계약", description="Local fixture"))["id"]
        hypothesis = (await self.call(client, "hypothesis", goal=goal,
                                      statement="An independently measured value equals three"))["id"]
        store = Store(self.workspace)
        validator = self.workspace / "fixed_validator.py"
        validator.write_text(
            "import json,sys\nfrom pathlib import Path\n"
            "bundle=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
            "value=json.loads(Path(bundle['artifacts']['result']).read_text(encoding='utf-8'))['value']\n"
            "print(json.dumps({'metrics':{'pass_rate':float(value==3)},"
            "'details':{'basis':'fixed_expected_value_3'}}))\n", encoding="utf-8")
        # Owner registration intentionally stays outside the agent-facing tools.
        store.validator_register("fixed", [sys.executable, str(validator), "{bundle}"],
                                 store.owner_key_path.read_text(encoding="utf-8").strip())
        job = self.workspace / ("job-" + label)
        job.mkdir()
        marker = self.workspace / "execution-count.txt"
        gate = self.workspace / "gate"
        source = "import json,time\nfrom pathlib import Path\n"
        if blocked:
            source += f"gate=Path({str(gate)!r})\nwhile not gate.exists():\n    time.sleep(0.02)\n"
        source += f"with Path({str(marker)!r}).open('a', encoding='utf-8') as stream:\n    stream.write('executed\\n')\n"
        source += "Path('result.json').write_text(json.dumps({'value':3}),encoding='utf-8')\n"
        script = job / "task.py"
        script.write_text(source, encoding="utf-8")
        spec = {
            "hypothesis_id": hypothesis, "change": "Measure a pinned local result",
            "comparison": "Fixed independent value 3", "data_split": "local development fixture",
            "seed": 7, "source_version": {"label": label, "files": {
                "task.py": hashlib.sha256(script.read_bytes()).hexdigest()}},
            "metrics": ["pass_rate"], "criteria": [{"metric": "pass_rate", "op": ">=", "threshold": 1}],
            "command": [initialized["runner_interpreter"], "task.py"], "cwd": str(job),
            "artifacts": [{"name": "result", "path": "result.json"}], "validator": "fixed",
        }
        registration = (await self.call(client, "register", goal=goal, spec=spec,
                                        request_key="register-" + label))["registration"]["id"]
        return goal, hypothesis, registration, marker, gate

    async def test_handshake_typed_tools_json_and_workspace_restriction(self):
        async with self.client() as client:
            self.assertTrue(client.protocol_version)
            self.assertIsNotNone(client.server_capabilities.tools)
            listed = await client.list_tools()
            by_name = {tool.name: tool for tool in listed.tools}
            self.assertEqual(set(by_name), TOOLS)
            self.assertNotIn("research_validator", by_name)
            for tool in listed.tools:
                self.assertEqual(tool.input_schema.get("type"), "object")
                self.assertIsInstance(tool.input_schema.get("properties"), dict)
            self.assertEqual(by_name["research_goal"].input_schema["properties"]["title"]["type"], "string")
            self.assertEqual(by_name["research_register"].input_schema["properties"]["spec"]["type"], "object")
            self.assertIn("request_key", by_name["research_register"].input_schema["required"])
            help_result = await self.call(client, "help")
            self.assertIn("version", help_result)
            self.assertFalse((self.workspace / ".research").exists())
            await self.call(client, "status", error="NOT_INITIALIZED")
            for unsafe in ("../outside", str(self.temporary / "outside"), ""):
                with self.subTest(workspace=unsafe):
                    await self.call(client, "init", workspace=unsafe, error="INVALID_INPUT")
            self.assertFalse((self.temporary / "outside").exists())
            initialized = await self.call(client, "init")
            self.assertNotIn("owner_key_path", initialized)
            self.assertNotIn("internal_key_path", initialized)
            bad_page = await self.call(client, "memory", limit=0, error="INVALID_INPUT")
            self.assertIn("message", bad_page)

    async def test_goal_versions_lifecycle_and_resource_share_actual_stdio_web_cli_state(self):
        from research_cli.mcp_bridge import Bridge
        from research_cli.web_tools import call_tool
        async with self.client() as client:
            await self.call(client, "init")
            initial = await self.call(client, "goal", title="Shared channel objective", brief={"original_request": "vague request"}, request_key="shared", expect=0)
            goal = initial["id"]
            store = Store(self.workspace)
            replay = store.goal_create("Shared channel objective", brief={"original_request": "vague request"}, request_key="shared", expected_revision=0)
            self.assertEqual(replay["id"], goal)
            amended = await self.call(client, "goal_amend", goal=goal, brief={"original_request": "vague request", "scope": "local fixture"}, reason="Explicit scope", change_kind="scope", request_key="scope", expect=initial["revision"])
            self.assertEqual(amended["goal"]["version"], 2)
            observed = await self.call(client, "resource", goal=goal, observation={"source": "external transcript", "source_ref": "unknown-usage"}, request_key="usage")
            self.assertEqual(observed["observation"]["provenance"], "external_report")
            resources = await self.call(client, "resource_show", goal=goal)
            self.assertEqual(resources["summary"]["unknown_count"], 1)
            closed = await self.call(client, "goal_close", goal=goal, state="paused", reason="Awaiting data", results=[], incomplete=["evaluation"], request_key="pause", expect=resources["revision"])
            bridge = Bridge(self.server_root)
            replay = call_tool(bridge, "research_goal_close", {"goal": goal, "state": "paused", "reason": "Awaiting data", "results": [], "incomplete": ["evaluation"], "request_key": "pause", "expect": resources["revision"]})
            self.assertTrue(replay["ok"], replay)
            self.assertTrue(replay["data"]["reused"])
            resumed = await self.call(client, "goal_resume", goal=goal, reason="Data ready", request_key="resume", expect=closed["revision"])
            final = await self.call(client, "goal_show", goal=goal, limit=1)
            self.assertEqual(final["goal"], store.goal_show(goal)["goal"])
            self.assertEqual(final["goal"]["id"], goal)
            self.assertEqual(final["version_total"], 2)
            self.assertEqual(final["goal"]["state"], "active")
            self.assertEqual(resumed["goal"]["version"], 2)
            self.assertEqual(store.status()["goal_total"], 1)
            self.assertEqual(store.status()["total"], 0)

    async def test_complete_workflow_duplicate_recover_and_server_restart(self):
        async with self.client() as client:
            await client.list_tools()
            goal, hypothesis, registration, marker, gate = await self.fixture(client)
            await self.call(client, "verify", registration=registration, error="INVALID_TRANSITION")
            await self.call(client, "decide", registration=registration, decision="adopted",
                            reason="agent says success", error="INVALID_TRANSITION")
            evidence = await self.call(client, "evidence", registration=registration, kind="measured",
                                       claim="Untrusted caller says pass_rate=1")
            self.assertEqual(evidence["evidence"]["kind"], "measured")
            first = await self.call(client, "run", registration=registration, request_key="execute-once")
            self.assertTrue(first["started"])
            self.assertEqual(first["record"]["run"]["state"], "succeeded")
            self.assertIsNone(first["record"]["verification"])
            await self.call(client, "decide", registration=registration, decision="adopted",
                            reason="exit zero only", error="INVALID_TRANSITION")
            repeated = await self.call(client, "run", registration=registration, request_key="execute-once")
            alternate = await self.call(client, "run", registration=registration, request_key="new-request-same-experiment")
            self.assertFalse(repeated["started"])
            self.assertFalse(alternate["started"])
            recovered = await self.call(client, "recover", registration=registration)
            self.assertEqual(recovered["record"]["run"]["id"], first["record"]["run"]["id"])
            verified = await self.call(client, "verify", registration=registration)
            self.assertEqual(verified["record"]["verification"]["state"], "passed")
            self.assertEqual(verified["record"]["verification"]["metrics"]["pass_rate"], 1)
            adopted = await self.call(client, "decide", registration=registration, decision="adopted",
                                      reason="Independent fixed verifier passed")
            self.assertEqual(adopted["decision"]["state"], "adopted")
            self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["executed"])
            memory = await self.call(client, "memory", outcome="success", verification="passed", limit=1)
            self.assertEqual(memory["total"], 1)
            self.assertTrue(memory["items"][0]["claim_verified"])
            self.assertEqual(memory["items"][0]["id"], registration)
        # A fresh stdio process reads the durable record, and cannot rerun it.
        async with self.client() as restarted:
            await restarted.list_tools()
            record = await self.call(restarted, "show", registration=registration)
            self.assertEqual(record["decision"]["state"], "adopted")
            self.assertEqual(record["verification"]["state"], "passed")
            submitted = [item for item in record["evidence"] if item["run_id"] is None]
            self.assertEqual(len(submitted), 1)
            self.assertFalse(submitted[0]["verified"])
            repeated = await self.call(restarted, "run", registration=registration, request_key="after-restart")
            self.assertFalse(repeated["started"])
            self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["executed"])

    async def test_revision_conflict_and_unverified_laya_exchange(self):
        async with self.client() as client:
            await client.list_tools()
            goal, hypothesis, registration, marker, gate = await self.fixture(client)
            before = await self.call(client, "status", goal=goal)
            await self.call(client, "hypothesis", goal=goal, statement="Another externally proposed hypothesis")
            after = await self.call(client, "status", goal=goal)
            await self.call(client, "hypothesis", goal=goal, statement="Stale proposal",
                            expect=before["revision"], error="REVISION_CONFLICT")
            final = await self.call(client, "status", goal=goal)
            self.assertEqual(after["revision"], final["revision"])
            self.assertEqual(after["hypothesis_total"], final["hypothesis_total"])
            payload = {
                "goal_id": goal, "context": "External inference only", "question": "Which proposal needs review?",
                "candidates": [{"id": "candidate-local", "hypothesis": "Test a local measurement",
                                "applicability": "Fixed local conditions", "conditions": {"seed": 7},
                                "evidence": [registration]}],
            }
            bundle = await self.call(client, "laya_prepare", payload=payload)
            self.assertEqual(bundle["labels"]["C1"], "candidate-local")
            self.assertEqual((await self.call(client, "status", goal=goal))["revision"], final["revision"])
            response = {"answers": {"research_choice": {"choice": "C1"}},
                        "usage": {"input_tokens": 37, "output_tokens": 0}}
            proposal = await self.call(client, "laya_resolve", bundle=bundle, response=response,
                                       expected_sha256=bundle["sha256"])
            self.assertEqual(proposal["candidate_id"], "candidate-local")
            self.assertEqual(proposal["kind"], "proposal")
            self.assertFalse(proposal["verified"])
            proposal_file = self.workspace / "external-proposal.json"
            proposal_file.write_text(json.dumps(proposal, ensure_ascii=False), encoding="utf-8")
            stored = await self.call(client, "evidence", registration=registration, kind="proposal",
                                     claim="External Laya response requires independent evaluation", path=str(proposal_file))
            self.assertEqual(stored["evidence"]["kind"], "proposal")
            record = await self.call(client, "show", registration=registration)
            self.assertIsNone(record["run"])
            self.assertIsNone(record["verification"])
            self.assertEqual(record["decision"]["state"], "pending")
            preserved = record["evidence"][0]
            self.assertFalse(preserved["verified"])
            self.assertEqual(preserved["integrity"], "valid")
            self.assertEqual(json.loads((self.workspace / preserved["path"]).read_text(encoding="utf-8")), proposal)
            await self.call(client, "decide", registration=registration, decision="adopted",
                            reason="Laya selected it", error="INVALID_TRANSITION")
            self.assertFalse(marker.exists())

    async def test_preregistered_criteria_and_current_evidence_cannot_be_replaced(self):
        async with self.client() as client:
            await client.list_tools()
            goal, hypothesis, registration, marker, gate = await self.fixture(client)
            original = await self.call(client, "show", registration=registration)
            changed = copy.deepcopy(original["registration"]["spec"])
            changed["criteria"][0]["threshold"] = 0
            await self.call(client, "register", goal=goal, spec=changed,
                            request_key="register-fixture", error="REQUEST_CONFLICT")
            self.assertEqual((await self.call(client, "show", registration=registration))
                             ["registration"]["spec"]["criteria"][0]["threshold"], 1)
            await self.call(client, "run", registration=registration, request_key="tamper-test")
            await self.call(client, "verify", registration=registration)
            before = await self.call(client, "show", registration=registration)
            artifact = next(item for item in before["evidence"] if item["name"] == "result")
            (self.workspace / artifact["path"]).write_text('{"value":99}', encoding="utf-8")
            await self.call(client, "verify", registration=registration, error="EVIDENCE_INVALID")
            await self.call(client, "decide", registration=registration, decision="adopted",
                            reason="Ignore tampering", error="EVIDENCE_TAMPERED")
            memory = await self.call(client, "memory", verification="passed")
            self.assertEqual(memory["items"][0]["verification"], "passed")
            self.assertFalse(memory["items"][0]["claim_verified"])
            self.assertEqual(memory["items"][0]["evidence_integrity"], "invalid")

    async def test_export_restore_keeps_verified_records_without_launching(self):
        async with self.client() as client:
            await client.list_tools()
            goal, hypothesis, registration, marker, gate = await self.fixture(client)
            await self.call(client, "run", registration=registration, request_key="export-task")
            await self.call(client, "verify", registration=registration)
            await self.call(client, "decide", registration=registration, decision="adopted",
                            reason="Fixed verifier passed")
            exported = await self.call(client, "export", output="snapshot.zip")
            archive = self.workspace / "snapshot.zip"
            self.assertTrue(archive.is_file(), exported)
            restored = await self.call(client, "restore", input=str(archive), workspace="restored")
            self.assertNotIn("owner_key_path", restored)
            self.assertNotIn("internal_key_path", restored)
            record = await self.call(client, "show", registration=registration, workspace="restored")
            self.assertEqual(record["verification"]["state"], "passed")
            self.assertEqual(record["decision"]["state"], "adopted")
            self.assertTrue(all(item["integrity"] == "valid" for item in record["evidence"]))
            repeated = await self.call(client, "run", registration=registration,
                                       request_key="after-restore", workspace="restored")
            self.assertFalse(repeated["started"])
            self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["executed"])

    async def test_scoped_files_and_experiment_cwd_reject_other_directories(self):
        async with self.client() as client:
            await client.list_tools()
            goal, hypothesis, registration, marker, gate = await self.fixture(client)
            outside = self.temporary / "outside.json"
            outside.write_text('{"private":"other-project fixture"}', encoding="utf-8")
            await self.call(client, "evidence", registration=registration, kind="literature",
                            claim="File must remain outside MCP root", path=str(outside), error="PERMISSION_DENIED")
            await self.call(client, "export", output=str(self.temporary / "outside.zip"), error="PERMISSION_DENIED")
            await self.call(client, "restore", input=str(outside), workspace="new-state", error="PERMISSION_DENIED")
            original = await self.call(client, "show", registration=registration)
            changed = copy.deepcopy(original["registration"]["spec"])
            changed["cwd"] = str(self.temporary)
            await self.call(client, "register", goal=goal, spec=changed,
                            request_key="foreign-project", error="PERMISSION_DENIED")
            self.assertEqual((await self.call(client, "status"))["total"], 1)
            self.assertEqual(outside.read_text(encoding="utf-8"), '{"private":"other-project fixture"}')
            self.assertFalse((self.temporary / "outside.zip").exists())
            self.assertFalse((self.server_root / "new-state").exists())
            self.assertFalse(marker.exists())

    async def test_cli_and_restored_foreign_cwd_cannot_launch_via_mcp(self):
        async with self.client() as client:
            await client.list_tools()
            goal, hypothesis, registration, marker, gate = await self.fixture(client)
            foreign = self.temporary / "foreign-project"
            foreign.mkdir()
            sentinel = foreign / "sentinel.txt"
            sentinel.write_text("untouched", encoding="utf-8")
            script = foreign / "task.py"
            script.write_text(
                "from pathlib import Path\n"
                f"Path({str(sentinel)!r}).write_text('executed', encoding='utf-8')\n",
                encoding="utf-8")
            original = await self.call(client, "show", registration=registration)
            spec = copy.deepcopy(original["registration"]["spec"])
            spec["cwd"] = str(foreign)
            spec["source_version"] = {"label": "foreign-cli-source", "files": {
                "task.py": hashlib.sha256(script.read_bytes()).hexdigest()}}
            # The core CLI allows a local owner to preregister another cwd.
            # Importing that record must not bypass the MCP execution scope.
            store = Store(self.workspace)
            foreign_registration = store.register(goal, spec, "foreign-cli-registration")["registration"]["id"]
            before = await self.call(client, "status")
            await self.call(client, "run", registration=foreign_registration,
                            request_key="foreign-cli-run", error="PERMISSION_DENIED")
            self.assertEqual((await self.call(client, "status"))["revision"], before["revision"])
            self.assertIsNone((await self.call(client, "show", registration=foreign_registration))["run"])
            self.assertFalse((self.workspace / ".research/runs").exists())

            await self.call(client, "export", output="foreign-cwd-snapshot.zip")
            archive = self.workspace / "foreign-cwd-snapshot.zip"
            await self.call(client, "restore", input=str(archive), workspace="imported-foreign")
            restored_root = self.server_root / "imported-foreign"
            restored_before = await self.call(client, "status", workspace="imported-foreign")
            await self.call(client, "run", registration=foreign_registration,
                            request_key="foreign-restored-run", workspace="imported-foreign",
                            error="PERMISSION_DENIED")
            restored_after = await self.call(client, "status", workspace="imported-foreign")
            self.assertEqual(restored_after["revision"], restored_before["revision"])
            self.assertIsNone((await self.call(client, "show", registration=foreign_registration,
                                              workspace="imported-foreign"))["run"])
            self.assertFalse((restored_root / ".research/runs").exists())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "untouched")
            self.assertFalse(marker.exists())

    async def test_two_servers_share_one_durable_execution_claim(self):
        async with self.client() as first, self.client() as second:
            await first.list_tools()
            await second.list_tools()
            goal, hypothesis, registration, marker, gate = await self.fixture(first, blocked=True)
            task = asyncio.create_task(self.call(first, "run", registration=registration,
                                                 request_key="concurrent"))
            try:
                deadline = asyncio.get_running_loop().time() + 20
                while not list((self.workspace / ".research/runs").glob("*/process.json")):
                    if task.done():
                        await task
                        self.fail("Execution ended before its expected durable checkpoint")
                    if asyncio.get_running_loop().time() > deadline:
                        self.fail("Worker did not reach the durable checkpoint")
                    await asyncio.sleep(0.02)
                concurrent = await self.call(second, "run", registration=registration,
                                             request_key="concurrent")
                self.assertFalse(concurrent["started"])
                self.assertEqual(concurrent["record"]["run"]["state"], "running")
            finally:
                gate.touch()
                completed = await task
            self.assertTrue(completed["started"])
            self.assertEqual(completed["record"]["run"]["state"], "succeeded")
            self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["executed"])


if __name__ == "__main__":
    unittest.main()
