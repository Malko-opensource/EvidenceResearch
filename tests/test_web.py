"""Real loopback HTTP contracts for the agent-controlled spectator dashboard."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import asyncio
import copy
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from research_cli.core import Store
from research_cli.web_server import create_server
from research_cli.web_tools import tool_descriptions

try:
    from mcp.server import MCPServer
except ImportError:
    MCPServer = None


ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    "research_help", "research_init", "research_goal", "research_hypothesis",
    "research_register", "research_status", "research_memory", "research_show",
    "research_run", "research_recover", "research_verify", "research_decide",
    "research_evidence", "research_export", "research_restore",
    "research_laya_prepare", "research_laya_resolve",
    "research_goal_show", "research_goal_amend", "research_goal_close", "research_goal_resume", "research_resource", "research_resource_show",
}


class SpectatorMarkup(HTMLParser):
    """Inspect the served page for user controls, allowing passive reading focus."""

    def __init__(self):
        super().__init__()
        self.human_controls = []

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        role = (attributes.get("role") or "").strip().lower()
        reasons = []
        if tag in {"button", "input", "select", "textarea", "form", "details", "summary"}:
            reasons.append("human control element")
        if tag == "a" and "href" in attributes:
            reasons.append("clickable link")
        if "contenteditable" in attributes and (attributes["contenteditable"] or "").lower() != "false":
            reasons.append("editable content")
        if "onclick" in attributes:
            reasons.append("click handler")
        if role in {"button", "link", "tab", "menuitem", "checkbox", "radio", "switch",
                    "textbox", "combobox", "spinbutton", "slider", "searchbox", "option", "treeitem"}:
            reasons.append("interactive role")
        if "tabindex" in attributes:
            try:
                keyboard_control = int(attributes["tabindex"]) >= 0
            except (TypeError, ValueError):
                keyboard_control = False
            if keyboard_control and tag != "svg" and role not in {"img", "graphics-document", "graphics-symbol"}:
                reasons.append("interactive keyboard focus")
        if reasons:
            self.human_controls.append({"element": tag, "id": attributes.get("id"), "reasons": reasons})


class ResearchWebHTTP(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tests" / ".runs"
        self.test_root.mkdir(exist_ok=True)
        self.temporary = Path(tempfile.mkdtemp(prefix="web-", dir=self.test_root)).resolve()
        self.server_root = self.temporary / "server-root"
        self.server_root.mkdir()
        self.workspace = self.server_root / "default"
        self.gate = self.workspace / "gate"
        self.server = create_server(self.server_root, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.bootstrap = self.get("/api/bootstrap")
        self.token = self.bootstrap["session_token"]
        self.env = dict(os.environ)
        self.env["PYTHONPATH"] = str(ROOT) + os.pathsep + self.env.get("PYTHONPATH", "")

    def tearDown(self):
        # Only release this fixture's blocked worker. This is not a research time limit.
        if self.workspace.exists():
            self.gate.touch()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=10)
        self.assertFalse(self.thread.is_alive())
        self.assertTrue(self.temporary.is_relative_to(self.test_root.resolve()))
        shutil.rmtree(self.temporary)

    def request(self, path, *, method="GET", payload=None, raw=None, headers=None):
        body = raw if raw is not None else (
            json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None)
        request_headers = {"Content-Type": "application/json"} if body is not None else {}
        request_headers.update(headers or {})
        request = Request(self.base + path, data=body, method=method, headers=request_headers)
        try:
            response = urlopen(request, timeout=30)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, dict(response.headers.items()), response.read()

    def json_request(self, path, **options):
        status, headers, body = self.request(path, **options)
        self.assertIn("application/json", headers.get("Content-Type", ""))
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        try:
            envelope = json.loads(body)
        except ValueError:
            self.fail(f"HTTP response did not contain JSON: {body!r}")
        self.assertIsInstance(envelope.get("ok"), bool)
        return status, envelope

    def get(self, path, *, error=None, expected_status=200):
        status, envelope = self.json_request(path)
        self.assertEqual(status, expected_status, envelope)
        if error:
            self.assertFalse(envelope["ok"], envelope)
            self.assertEqual(envelope["error"]["code"], error, envelope)
            return envelope["error"]
        self.assertTrue(envelope["ok"], envelope)
        return envelope["data"]

    def call(self, operation, *, error=None, expected_status=200, **params):
        status, envelope = self.json_request(
            "/api/call", method="POST", payload={"tool": "research_" + operation, "arguments": params},
            headers={"X-Research-Session": self.token, "Origin": self.base,
                     "Sec-Fetch-Site": "same-origin"})
        self.assertEqual(status, expected_status, envelope)
        if error:
            self.assertFalse(envelope["ok"], envelope)
            self.assertEqual(envelope["error"]["code"], error, envelope)
            return envelope["error"]
        self.assertTrue(envelope["ok"], envelope)
        return envelope["data"]

    def cli(self, *args, payload=None):
        completed = subprocess.run(
            [sys.executable, "-m", "research_cli", "--workspace", str(self.workspace), *args],
            cwd=ROOT, env=self.env, input=json.dumps(payload) if payload is not None else None,
            capture_output=True, text=True, encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        envelope = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, (envelope, completed.stderr))
        self.assertTrue(envelope["ok"], envelope)
        return envelope["data"]

    def fixture(self, *, label="fixture", blocked=False):
        initialized = self.call("init")
        goal = self.call("goal", title="웹 실제 연구 계약")['id']
        hypothesis = self.call("hypothesis", goal=goal, statement="The measured value equals three")['id']
        validator = self.workspace / "fixed_validator.py"
        validator.write_text(
            "import json,sys\nfrom pathlib import Path\n"
            "bundle=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
            "value=json.loads(Path(bundle['artifacts']['result']).read_text(encoding='utf-8'))['value']\n"
            "print(json.dumps({'metrics':{'pass_rate':float(value==3)},"
            "'details':{'basis':'fixed_expected_value_3'}}))\n", encoding="utf-8")
        # The owner freezes the evaluator through the public local CLI, outside web tools.
        self.cli("validator", "--name", "fixed", "--input", "-", "--key",
                 str(self.workspace / ".research" / "owner.key"),
                 payload=[initialized["runner_interpreter"], str(validator), "{bundle}"])
        marker = self.workspace / "execution-count.txt"
        job = self.workspace / ("job-" + label)
        job.mkdir()
        source = "import json,time\nfrom pathlib import Path\n"
        if blocked:
            source += f"gate=Path({str(self.gate)!r})\nwhile not gate.exists():\n    time.sleep(0.02)\n"
        source += f"with Path({str(marker)!r}).open('a',encoding='utf-8') as stream:\n    stream.write('executed\\n')\n"
        source += "Path('result.json').write_text(json.dumps({'value':3}),encoding='utf-8')\n"
        script = job / "task.py"
        script.write_text(source, encoding="utf-8")
        spec = {
            "hypothesis_id": hypothesis, "change": "Measure a pinned local result",
            "comparison": "Independent fixed value three", "data_split": "local development fixture",
            "seed": 7, "source_version": {"label": label, "files": {
                "task.py": hashlib.sha256(script.read_bytes()).hexdigest()}},
            "metrics": ["pass_rate"], "criteria": [{"metric": "pass_rate", "op": ">=", "threshold": 1}],
            "command": [initialized["runner_interpreter"], "task.py"], "cwd": str(job),
            "artifacts": [{"name": "result", "path": "result.json"}], "validator": "fixed",
        }
        registration = self.call("register", goal=goal, spec=spec,
                                 request_key="register-" + label)["registration"]["id"]
        return goal, hypothesis, registration, spec, marker

    def test_bootstrap_discoverable_tools_and_static_assets(self):
        self.assertTrue(self.bootstrap["version"])
        self.assertIsInstance(self.token, str)
        self.assertGreater(len(self.token), 20)
        tools = {tool["name"]: tool for tool in self.bootstrap["tools"]}
        self.assertEqual(set(tools), TOOLS)
        for tool in tools.values():
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertTrue(tool["description"])
        self.assertEqual(tools["research_goal"]["inputSchema"]["properties"]["title"]["type"], "string")
        self.assertIn("spec", tools["research_register"]["inputSchema"]["required"])
        self.assertNotIn("research_validator", tools)
        self.assertNotIn("research_complete", tools)
        self.assertFalse((self.workspace / ".research").exists())
        for path, content_type in (("/", "text/html"), ("/app.js", "javascript"),
                                   ("/view_model.js", "javascript"), ("/styles.css", "text/css")):
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(content_type, headers.get("Content-Type", ""))
                self.assertTrue(body)
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                if path == "/":
                    markup = SpectatorMarkup()
                    markup.feed(body.decode("utf-8"))
                    markup.close()
                    self.assertEqual(markup.human_controls, [],
                                     "The spectator page must not expose human input, navigation, or actions")
        help_result = self.call("help", topic="register")
        self.assertIsInstance(help_result, dict)

    @unittest.skipUnless(MCPServer is not None, "Optional MCP SDK metadata check")
    def test_web_tool_schemas_match_sdk_tools(self):
        from research_cli.mcp_server import create_server as create_mcp_server

        def semantic(value):
            if isinstance(value, dict):
                return {key: semantic(item) for key, item in value.items()
                        if key not in ("title", "description", "additionalProperties")}
            if isinstance(value, list):
                return [semantic(item) for item in value]
            return value

        sdk_tools = asyncio.run(create_mcp_server(self.server_root).list_tools())
        sdk = {tool.name: tool.input_schema for tool in sdk_tools}
        web = {tool["name"]: tool["inputSchema"] for tool in tool_descriptions()}
        self.assertEqual(set(web), set(sdk))
        for name in sorted(web):
            with self.subTest(tool=name):
                self.assertEqual(set(web[name].get("required", [])), set(sdk[name].get("required", [])))
                self.assertEqual(semantic(web[name]["properties"]), semantic(sdk[name]["properties"]))

    def test_cli_and_http_share_state_events_and_pagination(self):
        initialized = self.call("init")
        self.assertNotIn("owner_key_path", initialized)
        self.assertNotIn("internal_key_path", initialized)
        goal = self.cli("goal", "--title", "CLI에서 만든 목표")['id']
        snapshot = self.get("/api/snapshot?" + urlencode({"workspace": "default"}))
        self.assertIn(goal, [item["id"] for item in snapshot["status"]["goals"]])
        self.assertIn("goal.create", [item["action"] for item in snapshot["events"]])
        hypothesis = self.call("hypothesis", goal=goal, statement="웹에서 만든 가설")['id']
        from_cli = self.cli("status")
        self.assertIn(hypothesis, [item["id"] for item in from_cli["hypotheses"]])
        current = self.get("/api/snapshot?" + urlencode({"workspace": "default", "limit": 1, "offset": 0}))
        self.assertEqual(current["status"]["revision"], from_cli["revision"])
        self.assertLessEqual(len(current["events"]), 20)
        self.assertGreaterEqual(current["event_total"], 2)
        for event in current["events"]:
            self.assertNotIn("data", event)  # Never expose owner/internal capabilities via event payloads.
            self.assertIn("revision", event)
        revision = current["status"]["revision"]
        self.call("hypothesis", goal=goal, statement="Fresh revision", expect=revision)
        self.call("hypothesis", goal=goal, statement="Stale revision", expect=revision,
                  error="REVISION_CONFLICT")
        self.assertEqual(Store(self.workspace).status()["hypothesis_total"], 2)
        self.call("init", workspace="second")
        first_page = self.get("/api/workspaces?limit=1&offset=0")
        second_page = self.get("/api/workspaces?limit=1&offset=1")
        self.assertEqual(first_page["total"], 2)
        self.assertEqual(len(first_page["items"]), 1)
        self.assertEqual(len(second_page["items"]), 1)
        self.assertNotEqual(first_page["items"][0]["name"], second_page["items"][0]["name"])
        serialized = json.dumps([initialized, current, first_page])
        for name in ("owner.key", "internal.key"):
            key = (self.workspace / ".research" / name).read_text(encoding="utf-8").strip()
            self.assertNotIn(key, serialized)

    def test_selected_timeline_excludes_other_experiments_without_mutation(self):
        goal, hypothesis, registration, _, _ = self.fixture(label="selected")
        other_goal, other_hypothesis, other_registration, _, _ = self.fixture(label="other")
        self.call("run", registration=registration, request_key="timeline-run")
        record = self.call("show", registration=registration)
        before = self.call("status")
        snapshot = self.get("/api/snapshot?" + urlencode({
            "workspace": "default", "registration": registration}))
        self.assertEqual(snapshot["event_scope"], "selected_registration")
        self.assertEqual(snapshot["registration"], registration)
        targets = {event["target"] for event in snapshot["events"]}
        self.assertTrue({goal, hypothesis, registration, record["run"]["id"]} <= targets)
        self.assertFalse({other_goal, other_hypothesis, other_registration} & targets)
        self.assertEqual(snapshot["event_total"], len(snapshot["events"]))
        self.assertTrue(all(event["revision"] <= before["revision"] for event in snapshot["events"]))
        self.assertEqual(before["revision"], self.call("status")["revision"])
        self.get("/api/snapshot?" + urlencode({
            "workspace": "default", "registration": "unknown"}), error="NOT_FOUND")
        self.get("/view_model.js?extra=1", error="INVALID_INPUT", expected_status=400)

    def test_goal_report_aggregates_all_runs_outside_the_page_and_excludes_other_goals(self):
        goal, hypothesis, registration, _, marker = self.fixture(label="aggregate")
        other_goal, _, other_registration, _, _ = self.fixture(label="foreign")
        self.call("run", registration=registration, request_key="aggregate-original")
        self.call("run", registration=registration, request_key="aggregate-repeat-request")
        self.call("run", registration=other_registration, request_key="foreign-original")
        original = self.call("show", registration=registration)
        revision = self.call("status")["revision"]
        snapshot = self.get("/api/snapshot?" + urlencode({"workspace":"default", "goal":goal,
                                                            "limit":1, "offset":100}))
        report = snapshot['report']
        self.assertEqual(snapshot['status']['registrations'], [])
        self.assertEqual(report['scope']['goal_id'], goal)
        self.assertEqual(report['scope']['runs_total'], 1)
        self.assertEqual(report['execution_audit']['request_keys_total'], 2)
        self.assertIsNone(report['execution_audit']['replay_attempt_count'])
        self.assertEqual(report['execution_audit']['per_run'][0]['run'],original['run']['id'])
        self.assertEqual(report['records'], [])
        self.assertEqual(report['records_total'], 1)
        self.assertEqual(report['totals']['run_wall_seconds']['value'], original['run']['resources']['wall_seconds'])
        self.assertEqual(report['totals']['run_wall_seconds']['known'], 1)
        self.assertEqual(report['branches'][0]['hypothesis_id'], hypothesis)
        self.assertEqual([item['id'] for item in report['runs']], [original['run']['id']])
        self.assertEqual(report['revision'], revision)
        self.assertTrue(report['consistent'])
        # This fixture's marker is shared by the selected and foreign goal.
        self.assertEqual(marker.read_text(encoding='utf-8').splitlines(), ['executed', 'executed'])
        self.assertEqual(self.call('status')['revision'], revision)
        self.get('/api/snapshot?'+urlencode({'workspace':'default','goal':other_goal,'registration':registration}),
                 error='INVALID_INPUT', expected_status=400)

    def test_preexecution_branch_cost_and_resource_arrival_are_scoped_without_invented_run(self):
        goal, hypothesis, registration, _, _ = self.fixture(label='preexecution-cost')
        observed = self.call('resource', goal=goal, request_key='reported-local-test-charge', observation={
            'source':'synthetic external ledger used only for HTTP contract testing',
            'source_ref':'ledger-entry-1','registration_id':registration,
            'cost':{'status':'known','amount':2,'currency':'USD'}, 'tokens':{'status':'unknown','value':None}})
        identifier = observed['observation']['id']
        revision = self.call('status')['revision']
        for selection in ({'goal':goal}, {'registration':registration}):
            snapshot = self.get('/api/snapshot?'+urlencode({'workspace':'default',**selection}))
            branch = snapshot['report']['branches'][0]
            self.assertEqual(branch['hypothesis_id'],hypothesis)
            self.assertEqual(branch['runs_total'],0)
            self.assertIsNone(branch['wall_seconds'])
            self.assertEqual(branch['resources']['cost_by_currency'],[{'currency':'USD','amount':2}])
            self.assertEqual(branch['resources']['total_cost_status'],'unknown')
            self.assertIn(identifier,[event['target'] for event in snapshot['events'] if event['action']=='resource.record'])
        self.assertEqual(self.call('status')['revision'],revision)
        self.assertIsNone(self.call('show',registration=registration)['run'])

    def test_goal_only_report_does_not_invent_execution_cost_or_lifecycle(self):
        self.call('init')
        goal = self.call('goal', title='No execution yet', request_key='report-empty-goal')['id']
        revision = self.call('status')['revision']
        snapshot = self.get('/api/snapshot?'+urlencode({'workspace':'default','goal':goal}))
        report = snapshot['report']
        self.assertEqual(report['goal']['state'], 'active')
        self.assertEqual(report['scope']['runs_total'], 0)
        self.assertIsNone(report['totals']['run_wall_seconds']['value'])
        self.assertEqual(report['runs'], [])
        self.assertEqual(report['records'], [])
        self.assertEqual(self.call('status')['revision'], revision)

    def test_long_execution_concurrent_state_and_duplicate_request(self):
        _, _, registration, _, marker = self.fixture(blocked=True)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.call, "run", registration=registration, request_key="once")
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    record = self.call("show", registration=registration)
                    if record["run"] and record["run"]["state"] == "running":
                        break
                    time.sleep(0.02)
                else:
                    self.fail("Worker did not reach its durable running checkpoint")
                snapshot = self.get("/api/snapshot?workspace=default")
                self.assertEqual(snapshot["status"]["registrations"][0]["execution"], "running")
                self.assertFalse(future.done(), "A blocked task must not prevent another HTTP state request")
                repeated = self.call("run", registration=registration, request_key="once")
                self.assertFalse(repeated["started"])
                self.assertEqual(repeated["record"]["run"]["state"], "running")
            finally:
                self.gate.touch()
            finished = future.result(timeout=30)
        self.assertTrue(finished["started"])
        self.assertEqual(finished["record"]["run"]["state"], "succeeded")
        another_key = self.call("run", registration=registration, request_key="another-key")
        self.assertFalse(another_key["started"])
        self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["executed"])
        recovered = self.call("recover", registration=registration)
        self.assertEqual(recovered["record"]["run"]["state"], "succeeded")

    def test_immutable_registration_verification_adoption_and_tamper(self):
        goal, _, registration, spec, _ = self.fixture()
        changed = copy.deepcopy(spec)
        changed["criteria"][0]["threshold"] = 0
        self.call("register", goal=goal, spec=changed, request_key="register-fixture", error="REQUEST_CONFLICT")
        record = self.call("show", registration=registration)
        self.assertEqual(record["registration"]["spec"]["criteria"], spec["criteria"])
        self.call("verify", registration=registration, error="INVALID_TRANSITION")
        self.call("decide", registration=registration, decision="adopted", reason="claim without run",
                  error="INVALID_TRANSITION")
        self.call("evidence", registration=registration, kind="measured", claim="Agent claims pass_rate=1")
        self.call("run", registration=registration, request_key="actual-run")
        self.call("decide", registration=registration, decision="adopted", reason="claim without evaluator",
                  error="INVALID_TRANSITION")
        verified = self.call("verify", registration=registration)
        self.assertEqual(verified["record"]["verification"]["state"], "passed")
        record = self.call("show", registration=registration)
        artifact = next(item for item in record["evidence"] if item["name"] == "result")
        preview_path = "/api/evidence?" + urlencode({"workspace": "default", "registration": registration,
                                                     "evidence": artifact["id"]})
        preview = self.get(preview_path)
        self.assertEqual(json.loads(preview["text"]), {"value": 3})
        self.assertEqual(preview["evidence"]["sha256"], artifact["sha256"])
        self.assertFalse(preview["truncated"])
        self.assertEqual(preview["bytes"], len((self.workspace / artifact["path"]).read_bytes()))
        (self.workspace / artifact["path"]).write_text('{"value":4}', encoding="utf-8")
        self.get(preview_path, error="EVIDENCE_TAMPERED")
        self.call("decide", registration=registration, decision="adopted", reason="historical pass",
                  error="EVIDENCE_TAMPERED")
        current = self.call("show", registration=registration)
        self.assertEqual(current["verification"]["state"], "passed")
        current_artifact = next(item for item in current["evidence"] if item["id"] == artifact["id"])
        self.assertEqual(current_artifact["integrity"], "tampered")
        self.assertFalse(current_artifact["verified"])
        self.assertNotEqual(current["decision"]["state"], "adopted")
        memory = self.call("memory", verification="passed")
        remembered = next(item for item in memory["items"] if item["id"] == registration)
        self.assertEqual(remembered["verification"], "passed")
        self.assertFalse(remembered["claim_verified"])

    def test_linked_preview_and_foreign_file_and_execution_restrictions(self):
        goal, _, registration, spec, marker = self.fixture()
        self.call("run", registration=registration, request_key="run-preview")
        record = self.call("show", registration=registration)
        artifact = next(item for item in record["evidence"] if item["name"] == "result")
        other_spec = copy.deepcopy(spec)
        other_spec["source_version"]["label"] = "other-registration"
        other = self.call("register", goal=goal, spec=other_spec, request_key="register-other")["registration"]["id"]
        wrong_link = "/api/evidence?" + urlencode({"workspace": "default", "registration": other,
                                                  "evidence": artifact["id"]})
        self.get(wrong_link, error="NOT_FOUND")
        for name in (".research/owner.key", ".research/internal.key", ".research/state.sqlite3"):
            with self.subTest(private=name):
                path = "/api/evidence?" + urlencode({"workspace": "default", "registration": registration,
                                                     "evidence": name})
                self.get(path, error="NOT_FOUND")
                self.call("evidence", registration=registration, kind="literature", claim="private source",
                          path=name, error="PERMISSION_DENIED")
        owner_key = self.workspace / ".research" / "owner.key"
        secret = owner_key.read_text(encoding="utf-8").strip()
        # Legacy/CLI-created evidence can contain a private original source. A
        # hash-correct linked blob still must not turn this endpoint into key download.
        private_evidence = Store(self.workspace).add_evidence(
            registration, "literature", "private original source", str(owner_key))["evidence"]
        denied = self.get("/api/evidence?" + urlencode({"workspace": "default", "registration": registration,
                                                      "evidence": private_evidence["id"]}),
                          error="PERMISSION_DENIED")
        self.assertNotIn(secret, json.dumps(denied))
        large_source = self.workspace / "long-literature.txt"
        large_source.write_text("A cited observation.\n" * 20000, encoding="utf-8")
        large_evidence = self.call("evidence", registration=registration, kind="literature",
                                   claim="A large original document", path="long-literature.txt")["evidence"]
        large_preview = self.get("/api/evidence?" + urlencode({"workspace": "default", "registration": registration,
                                                             "evidence": large_evidence["id"]}))
        self.assertTrue(large_preview["truncated"])
        self.assertEqual(large_preview["bytes"], large_source.stat().st_size)
        self.assertLessEqual(len(large_preview["text"].encode("utf-8")), 256 * 1024)
        self.assertFalse(large_preview["evidence"]["verified"])
        outside = self.temporary / "outside.txt"
        outside.write_text("private foreign text", encoding="utf-8")
        self.call("evidence", registration=registration, kind="literature", claim="foreign",
                  path=str(outside), error="PERMISSION_DENIED")
        status, _, body = self.request("/" + quote(str(outside).replace("\\", "/"), safe="/"))
        self.assertNotEqual(status, 200)
        self.assertNotIn(b"private foreign text", body)
        foreign_job = self.temporary / "foreign-job"
        foreign_job.mkdir()
        shutil.copyfile(Path(spec["cwd"]) / "task.py", foreign_job / "task.py")
        foreign_spec = copy.deepcopy(spec)
        foreign_spec["cwd"] = str(foreign_job)
        foreign_spec["source_version"]["label"] = "foreign"
        self.call("register", goal=goal, spec=foreign_spec, request_key="web-foreign",
                  error="PERMISSION_DENIED")
        # Registrations created by a CLI outside the web scope cannot bypass run's pre-claim check.
        foreign_id = Store(self.workspace).register(goal, foreign_spec, "local-foreign")["registration"]["id"]
        self.call("run", registration=foreign_id, request_key="do-not-claim", error="PERMISSION_DENIED")
        self.assertIsNone(Store(self.workspace).show(foreign_id)["run"])
        self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["executed"])

    def test_http_guards_reject_before_mutation(self):
        self.call("init")
        before = Store(self.workspace).status()["revision"]
        base_headers = {"X-Research-Session": self.token, "Origin": self.base,
                        "Sec-Fetch-Site": "same-origin"}
        variations = [
            {"Host": "127.0.0.1:9"}, {"Origin": "https://example.invalid"},
            {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"},
            {"X-Research-Session": "invalid"}, {"X-Research-Session": ""},
        ]
        for variation in variations:
            with self.subTest(headers=variation):
                status, envelope = self.json_request(
                    "/api/call", method="POST",
                    payload={"tool": "research_goal", "arguments": {"title": "must not be stored"}},
                    headers=base_headers | variation)
                self.assertEqual(status, 403, envelope)
                self.assertFalse(envelope["ok"])
                self.assertEqual(envelope["error"]["code"], "PERMISSION_DENIED")
                self.assertEqual(Store(self.workspace).status()["revision"], before)
        status, envelope = self.json_request(
            "/api/call", method="POST",
            payload={"tool": "research_goal", "arguments": {"title": "missing token"}},
            headers={"Origin": self.base})
        self.assertEqual(status, 403, envelope)
        self.assertEqual(envelope["error"]["code"], "PERMISSION_DENIED")
        status, envelope = self.json_request(
            "/api/bootstrap", headers={"Origin": "https://example.invalid"})
        self.assertEqual(status, 403, envelope)
        self.assertNotIn("session_token", json.dumps(envelope))
        self.assertEqual(Store(self.workspace).status()["goal_total"], 0)

    def test_invalid_json_schema_and_admin_fields_have_clear_errors(self):
        self.call("init")
        before = Store(self.workspace).status()["revision"]
        status, envelope = self.json_request("/api/call", method="POST", raw=b"{invalid",
                                              headers={"X-Research-Session": self.token})
        self.assertEqual(status, 400)
        self.assertEqual(envelope["error"]["code"], "INVALID_INPUT")
        for tool, arguments in (
            ("research_validator", {"name": "new", "command": ["anything"]}),
            ("research_complete", {"state": "succeeded", "authority": "pretend"}),
            # These two tools belong to the browser presentation layer. They
            # must not become new persisted-state operations on the HTTP API.
            ("research_view", {"workspace": "default", "scene": "memory", "query": "example"}),
            ("research_inspect_evidence", {"workspace": "default", "registration": "reg_none", "evidence": "ev_none"}),
            ("research_goal", {"title": "bad extra", "internal_key": "pretend"}),
            ("research_goal", {"title": 17}),
            ("research_status", {"limit": True}),
        ):
            with self.subTest(tool=tool, arguments=arguments):
                status, envelope = self.json_request(
                    "/api/call", method="POST", payload={"tool": tool, "arguments": arguments},
                    headers={"X-Research-Session": self.token})
                self.assertEqual(status, 400, envelope)
                self.assertEqual(envelope["error"]["code"], "INVALID_INPUT", envelope)
        self.call("status", limit=0, error="INVALID_INPUT")
        self.assertEqual(Store(self.workspace).status()["revision"], before)
        self.assertEqual(Store(self.workspace).status()["goal_total"], 0)


if __name__ == "__main__":
    unittest.main()
