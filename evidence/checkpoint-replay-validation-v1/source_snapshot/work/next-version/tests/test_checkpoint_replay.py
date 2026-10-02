"""Independent transport/checkpoint contract fixtures for the future copy.

Providers are local synthetic fixtures, never actual model invocations. Tiny
fixed CPU fits verify tool artifacts and replay; they are tests, not B/C trials.
Main package, registered studies and their evidence are never modified.
"""
import copy
import ast
import hashlib
import json
from pathlib import Path
import pickle
import random
import sys
import tempfile
import types
import unittest

from evidence_research.baseline import (TransportCheckpointController, _read_checkpoint_commit,
    _OriginalCheckpointUnpickler, _HostTransportAbort, _module_scope, _hash)
from evidence_research.arms import AllowlistedExperimentTool, UpstreamCodexBridge, TOOL_CONTRACT
from evidence_research.model import ModelUnavailable, PreregisteredResourcesExhausted, digest
from evidence_research.tasks import make_spec, run_task, sha256_file, write_json
from evidence_research.verifier import verify


class SyntheticRawProvider:
    """Write branch-compatible raw receipts explicitly marked fixture-only.

    real_model is the loader branch enumeration being tested. fixture_only and
    fixture-model prevent these inputs being confused with evaluation evidence.
    No Codex executable or credentials are referenced.
    """
    model = "fixture-model-never-real"
    execution_kind = "fixture_only"

    def __init__(self, directory, responses):
        self.evidence_dir = Path(directory)
        self.responses = iter(responses)
        self.calls = []
        self.last_evidence = None

    def complete(self, prompt, *, call_id, json_response=False):
        self.calls.append((prompt, call_id))
        folder = self.evidence_dir / call_id
        folder.mkdir(parents=True)
        response = next(self.responses)
        identity = {"model": self.model, "prompt": prompt, "fixture_only": True}
        write_json(folder / "request.json", {**identity, "fingerprint": digest(identity)})
        failed = isinstance(response, Exception)
        (folder / "response.txt").write_text("" if failed else response, encoding="utf-8")
        (folder / "events.jsonl").write_text(json.dumps({"type": "turn.failed" if failed else "turn.completed",
            "fixture_only": True, "call_id": call_id}) + "\n", encoding="utf-8")
        (folder / "stderr.log").write_text("synthetic no-action failure" if failed else "", encoding="utf-8")
        record = {"status": "failed" if failed else "completed", "model": self.model, "fixture_only": True,
                  "execution_kind": "real_model", "tool_calls": [],
                  "files": {path.name: sha256_file(path) for path in folder.iterdir() if path.is_file()}}
        write_json(folder / "result.json", record)
        self.last_evidence = record
        if failed:
            raise response
        return response


def context(host_ordinal, role="fixture-review", phase="fixture-phase"):
    return {"host_ordinal": host_ordinal, "phase": phase, "role": role}


def host_request(prompt, system="system"):
    return "UPSTREAM SYSTEM PROMPT:\n" + system + "\n\nUPSTREAM USER PROMPT:\n" + prompt + "\n\nSHARED HOST EXECUTION CONTRACT:\n" + TOOL_CONTRACT


class CheckpointReplayTests(unittest.TestCase):
    def setUp(self):
        future = Path(__file__).resolve().parents[1]
        temporary_root = future / "work/test-checkpoint-replay"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=temporary_root)
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(temporary_root.resolve()))

    def tearDown(self):
        self.temporary.cleanup()

    def bridge(self, name, responses, *, prior=(), cursor=0, budget=20):
        directory = self.root / name
        provider = SyntheticRawProvider(directory / "model", responses)
        bridge = UpstreamCodexBridge(provider, directory, max_model_calls=budget,
                                     replay_directories=[self.root / item for item in prior])
        bridge.configure_cursor(cursor)
        return bridge, provider

    def call(self, bridge, prompt, host_ordinal, *, role="fixture-review", phase="fixture-phase"):
        return bridge(SyntheticRawProvider.model, prompt, "system",
                      _logical_context=context(host_ordinal, role, phase))

    def tool(self, name, *, prior_records=None, cursor=0, runner=run_task, budget=5):
        tool = AllowlistedExperimentTool(self.root / name,
            lambda config: make_spec("dev-quadratic", 7, config),
            runner=runner, verifier=verify, prior_records=prior_records, max_cpu_executions=budget)
        tool.configure_cursor(cursor)
        return tool

    def test_committed_prefix_same_prompt_is_a_fresh_logical_request(self):
        first, original = self.bridge("first", ["completion A"], budget=2)
        self.assertEqual(self.call(first, "identical prompt", 0), "completion A")
        cursor = first.export_cursor()
        self.assertEqual(cursor["next_ordinal"], 1)
        self.assertEqual(cursor["ledger_sha256"], sha256_file(cursor["ledger_path"]))
        resumed, fresh = self.bridge("resumed", ["completion B"], prior=["first"], cursor=1, budget=2)
        self.assertEqual(self.call(resumed, "identical prompt", 1), "completion B")
        self.assertEqual(len(original.calls), 1)
        self.assertEqual(len(fresh.calls), 1)
        self.assertFalse(resumed.calls[0]["reused_completed_evidence"])
        self.assertEqual(resumed.calls[0]["logical_request"]["ordinal"], 1)
        with self.assertRaises(PreregisteredResourcesExhausted):
            self.call(resumed, "identical prompt", 2)
        self.assertEqual(len(fresh.calls), 1)

    def test_stale_checkpoint_replays_tail_once_then_same_prompt_is_fresh(self):
        first, _ = self.bridge("first", ["completion A", "completion B"], budget=3)
        self.call(first, "identical prompt", 0)
        stale_cursor = first.export_cursor()["next_ordinal"]
        self.call(first, "identical prompt", 1)
        resumed, provider = self.bridge("resumed", ["completion C"], prior=["first"], cursor=stale_cursor, budget=3)
        self.assertEqual(self.call(resumed, "identical prompt", 1), "completion B")
        self.assertEqual(len(provider.calls), 0)
        self.assertEqual(self.call(resumed, "identical prompt", 2), "completion C")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual([call["reused_completed_evidence"] for call in resumed.calls], [True, False])
        # Restoring the same stale checkpoint in a new invocation must replay B
        # again, not globally mark it consumed and issue a duplicate model call.
        again, no_new = self.bridge("again", [], prior=["first", "resumed"], cursor=stale_cursor, budget=3)
        self.assertEqual(self.call(again, "identical prompt", 1), "completion B")
        self.assertEqual(len(no_new.calls), 0)

    def test_initial_reconstruction_preserves_identical_prompt_multiplicity(self):
        first, _ = self.bridge("first", ["sample A", "sample B", "sample C"], budget=3)
        for ordinal, answer in enumerate(("sample A", "sample B", "sample C")):
            self.assertEqual(self.call(first, "same reviewer prompt", ordinal), answer)
        replay, provider = self.bridge("replay", [], prior=["first"], cursor=0, budget=3)
        identities = []
        for ordinal, answer in enumerate(("sample A", "sample B", "sample C")):
            self.assertEqual(self.call(replay, "same reviewer prompt", ordinal), answer)
            identities.append(replay.calls[-1]["logical_receipt_identity"])
        self.assertEqual(len(set(identities)), 3)
        self.assertEqual(len(provider.calls), 0)
        with self.assertRaises(PreregisteredResourcesExhausted):
            self.call(replay, "same reviewer prompt", 3)

    def test_tail_role_phase_hostordinal_and_prompt_mismatches_fail_closed(self):
        first, _ = self.bridge("first", ["completion"], budget=2)
        self.call(first, "expected", 0)
        variants = [("expected", 0, "other role", "fixture-phase"),
                    ("expected", 0, "fixture-review", "other phase"),
                    ("expected", 1, "fixture-review", "fixture-phase"),
                    ("different", 0, "fixture-review", "fixture-phase")]
        for index, (prompt, host, role, phase) in enumerate(variants):
            replay, provider = self.bridge(f"replay-{index}", ["must never be called"], prior=["first"], cursor=0, budget=2)
            with self.assertRaises(ValueError):
                self.call(replay, prompt, host, role=role, phase=phase)
            self.assertEqual(provider.calls, [])
            self.assertEqual(replay.export_cursor()["next_ordinal"], 0)

    def test_model_cpu_model_tail_replays_exact_original_response(self):
        first, _ = self.bridge("first", ["CONFIG = {'degree': 2, 'alpha': 0}", "score completion"], budget=2)
        tool = self.tool("first-cpu", budget=1)
        code = self.call(first, "choose candidate", 0, role="generator")
        tool.set_logical_context(context(1, "cpu"))
        original_return = tool(code)
        original_result = self.call(first, original_return, 2, role="reward")
        old_records = copy.deepcopy(tool.records)
        model_replay, provider = self.bridge("model-resume", [], prior=["first"], cursor=0, budget=2)
        def never_fit(*args, **kwargs):
            raise AssertionError("Completed logical CPU invocation must not train again")
        cpu_replay = self.tool("new-attempt-cpu", prior_records=old_records, cursor=0, runner=never_fit, budget=1)
        reconstructed_code = self.call(model_replay, "choose candidate", 0, role="generator")
        cpu_replay.set_logical_context(context(1, "cpu"))
        replay_return = cpu_replay(reconstructed_code)
        self.assertEqual(replay_return, original_return)
        self.assertNotEqual(str(cpu_replay.events_path), json.loads(replay_return)["host_ledger"]["current_events_path"])
        self.assertEqual(self.call(model_replay, replay_return, 2, role="reward"), original_result)
        self.assertEqual(provider.calls, [])
        self.assertEqual(len(cpu_replay.completed), 1)
        self.assertEqual(cpu_replay.export_cursor()["next_ordinal"], 1)
        self.assertTrue(all(call["reused_completed_evidence"] for call in model_replay.calls))

    def test_committed_cpu_prefix_does_not_replay_into_new_logical_cpu_call(self):
        original = self.tool("original-cpu", budget=2)
        code = "CONFIG = {'degree': 2, 'alpha': 0}"
        original.set_logical_context(context(0, "cpu"))
        old_return = original(code)
        resumed = self.tool("new-cpu", prior_records=copy.deepcopy(original.records), cursor=1, budget=2)
        resumed.set_logical_context(context(1, "cpu"))
        new_return = resumed(code)
        self.assertNotEqual(old_return, new_return)
        self.assertEqual(json.loads(new_return)["actual_cpu_attempts_to_date"], 2)
        self.assertEqual(len(resumed.completed), 2)
        self.assertEqual(resumed.export_cursor()["next_ordinal"], 2)
        self.assertEqual(resumed.records[-1]["status"], "logical_tool_reply")

    def test_partial_model_logical_ledger_cannot_repeat_an_orphan_completion(self):
        first, provider = self.bridge("first", ["committed logical completion", "orphan raw completion"], budget=3)
        self.call(first, "identical prompt", 0)
        # Crash boundary: provider saved raw completion, but host bridge never
        # appended its logical completion mapping. One other mapping exists.
        provider.complete(host_request("identical prompt"), call_id="upstream-0001", json_response=False)
        with self.assertRaises((ValueError, ModelUnavailable)):
            self.bridge("resume", ["must not repeat"], prior=["first"], cursor=0, budget=3)

    def test_cpu_completed_without_logical_reply_requires_reconciliation(self):
        # Reproduce the analogous tool boundary by running the lower boundary:
        # actual completion is durable, logical response receipt is not.
        original = AllowlistedExperimentTool(self.root / "original-cpu",
            lambda config: make_spec("dev-quadratic", 7, config), max_cpu_executions=2)
        original._invoke("CONFIG = {'degree': 2, 'alpha': 0}")
        self.assertEqual(len(original.completed), 1)
        with self.assertRaises((ValueError, ModelUnavailable)):
            self.tool("resume-cpu", prior_records=copy.deepcopy(original.records), cursor=0, budget=2)

    def test_definitive_no_action_failure_retries_same_logical_request_and_counts_attempt(self):
        first, _ = self.bridge("failed", [ModelUnavailable("fixture definitive no-action failure")], budget=2)
        with self.assertRaises(ModelUnavailable):
            self.call(first, "unchanged request", 0)
        self.assertEqual(first.export_cursor()["next_ordinal"], 0)
        resumed, provider = self.bridge("success", ["completion after failure"], prior=["failed"], cursor=0, budget=2)
        self.assertEqual(self.call(resumed, "unchanged request", 0), "completion after failure")
        self.assertEqual(resumed.prior_attempts, 1)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(len(resumed.no_action_receipts), 1)
        self.assertEqual(resumed.export_cursor()["next_ordinal"], 1)
        with self.assertRaises(PreregisteredResourcesExhausted):
            self.call(resumed, "another request", 1)

    def test_definitive_failure_does_not_authorize_a_different_logical_request(self):
        first, _ = self.bridge("failed", [ModelUnavailable("fixture no-action failure")], budget=2)
        with self.assertRaises(ModelUnavailable):
            self.call(first, "unchanged request", 0)
        for index, (prompt, role) in enumerate((("changed request", "fixture-review"),
                                                ("unchanged request", "changed role"))):
            resumed, provider = self.bridge(f"mismatched-resume-{index}", ["must not be called"], prior=["failed"], cursor=0, budget=2)
            with self.assertRaises(ValueError):
                self.call(resumed, prompt, 0, role=role)
            self.assertEqual(provider.calls, [])
            self.assertEqual(resumed.export_cursor()["next_ordinal"], 0)

    def original_workflow_module(self):
        project = Path(__file__).resolve().parents[3]
        source_path = project / "references/upstream/AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27/ai_lab_repo.py"
        source = source_path.read_text(encoding="utf-8")
        workflow = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.ClassDef) and node.name == "LaboratoryWorkflow")
        # Compile the complete original ClassDef. Module bodies and imports do
        # not execute; phase responsibilities are not fabricated here.
        namespace = {"__name__": "ai_lab_repo", "__file__": str(source_path),
                     "DEFAULT_LLM_BACKBONE": "fixture", "pickle": pickle}
        module = types.ModuleType("ai_lab_repo")
        module.__dict__.update(namespace)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[workflow], type_ignores=[])), str(source_path), "exec"), module.__dict__)
        sys.modules["ai_lab_repo"] = module
        original = module.LaboratoryWorkflow.__new__(module.LaboratoryWorkflow)
        original.paper_index = 0
        original.phase_status = {"data preparation": True, "running experiments": False}
        original.openai_api_key = None
        original.sentinel = "class-wrapper keeps original object graph"
        return module, original, sha256_file(source_path), _hash(ast.dump(workflow, include_attributes=False))

    def controller_call(self, controller, bridge, prompt, *, role=None):
        result = bridge(SyntheticRawProvider.model, prompt, "system", _logical_context=controller.context(
            role or {"module": "fixture", "qualname": "fixture.reward", "actor_class": None, "reviewer_type": None}))
        controller.completed_action()
        return result

    def test_actual_checkpoint_wrapper_prefix_rng_and_stale_reconstruction(self):
        rng_before = random.getstate()
        try:
            directory = self.root / "workflow-original"
            directory.mkdir()
            with _module_scope(directory):
                random.seed(91817)
                bridge, _ = self.bridge("attempt-original", ["A", "B"], budget=3)
                tool = self.tool("cpu-original")
                controller = TransportCheckpointController(directory, bridge, tool, "fixed-conditions")
                module, lab, source_sha, ast_sha = self.original_workflow_module()
                original_save = module.LaboratoryWorkflow.save_state
                controller.install(module)
                lab.last_response = self.controller_call(controller, bridge, "same prompt")
                self.assertEqual(lab.last_response, "A")
                lab.save_state("data preparation")
                commit = _read_checkpoint_commit(directory)
                self.assertEqual(commit["cursor"]["model"]["next_ordinal"], 1)
                self.assertEqual(commit["cursor"]["host_ordinal"], 1)
                self.assertEqual(commit["cursor"]["tool"]["next_ordinal"], 0)
                self.assertEqual(controller.checkpoint_sha256, commit["manifest"]["checkpoint_sha256"])
                self.assertNotIn("transport", vars(lab))
                self.assertFalse(any("bridge" in key or "controller" in key for key in vars(lab)))
                self.assertNotEqual(module.LaboratoryWorkflow.save_state, original_save)
                self.assertEqual(sha256_file(module.__file__), source_sha)
                saved_random_next = random.random()
                # Completed tail B exists after the saved cursor but the old
                # workflow state still contains A, as on a mid-phase failure.
                lab.last_response = self.controller_call(controller, bridge, "same prompt")
                self.assertEqual(lab.last_response, "B")
                initial = json.loads((directory / "transport_initial_state.json").read_text(encoding="utf-8"))

            resumed_dir = self.root / "workflow-resumed"
            resumed_dir.mkdir()
            with _module_scope(resumed_dir):
                resumed_bridge, resumed_provider = self.bridge("attempt-resumed", ["C"], prior=["attempt-original"], cursor=1, budget=3)
                resumed_tool = self.tool("cpu-resumed")
                resumed_controller = TransportCheckpointController(resumed_dir, resumed_bridge, resumed_tool,
                    "fixed-conditions", restored_cursor=commit["cursor"], initial_state=initial)
                self.assertEqual(random.random(), saved_random_next)
                resumed_module, _, second_source_sha, second_ast_sha = self.original_workflow_module()
                resumed_controller.install(resumed_module)
                with Path(commit["checkpoint"]).open("rb") as stream:
                    restored_lab = _OriginalCheckpointUnpickler(stream).load()
                self.assertIs(type(restored_lab), resumed_module.LaboratoryWorkflow)
                self.assertEqual(restored_lab.last_response, "A")
                old_base = resumed_controller.checkpoint_sha256
                # The pinned driver re-saves already completed phases. Suppress
                # this write before tail reconstruction so original base SHA stays.
                restored_lab.save_state("data preparation")
                self.assertIsNone(_read_checkpoint_commit(resumed_dir))
                self.assertEqual(resumed_controller.checkpoint_sha256, old_base)
                self.assertEqual(self.controller_call(resumed_controller, resumed_bridge, "same prompt"), "B")
                self.assertEqual(resumed_provider.calls, [])
                self.assertEqual(self.controller_call(resumed_controller, resumed_bridge, "same prompt"), "C")
                self.assertEqual(len(resumed_provider.calls), 1)
                resumed_controller.require_reconciled()
                restored_lab.last_response = "C"
                restored_lab.phase_status["running experiments"] = True
                restored_lab.save_state("running experiments")
                next_commit = _read_checkpoint_commit(resumed_dir)
                self.assertEqual(next_commit["cursor"]["model"]["next_ordinal"], 3)
                self.assertEqual(next_commit["cursor"]["host_ordinal"], 3)
                self.assertEqual(source_sha, second_source_sha)
                self.assertEqual(ast_sha, second_ast_sha)
        finally:
            random.setstate(rng_before)

    def test_checkpoint_raw_pickle_alone_and_torn_stage_do_not_replace_committed_head(self):
        directory = self.root / "workflow"
        directory.mkdir()
        with _module_scope(directory):
            bridge, _ = self.bridge("attempt", ["A"])
            tool = self.tool("cpu")
            controller = TransportCheckpointController(directory, bridge, tool, "fixed-conditions")
            module, lab, _, _ = self.original_workflow_module()
            controller.install(module)
            lab.last_response = self.controller_call(controller, bridge, "prompt")
            lab.save_state("data preparation")
            head = (directory / "transport_checkpoint_head.json").read_bytes()
            committed = _read_checkpoint_commit(directory)
            # Fixture-owned artifacts simulate interrupted compatibility/staging
            # writes. Immutable committed bundle remains authoritative.
            (directory / "state_saves/Paper0.pkl").write_bytes(b"uncommitted raw write")
            stage = directory / "transport_checkpoints/.stage-interrupted-fixture"
            stage.mkdir()
            (stage / "workflow.pkl").write_bytes(b"uncommitted stage")
            self.assertEqual((directory / "transport_checkpoint_head.json").read_bytes(), head)
            self.assertEqual(_read_checkpoint_commit(directory)["checkpoint"], committed["checkpoint"])
            Path(committed["checkpoint"]).write_bytes(b"altered committed blob")
            with self.assertRaises(ValueError):
                _read_checkpoint_commit(directory)

    def test_host_abort_escapes_original_reward_exception_handler_and_stays_failed(self):
        directory = self.root / "host-abort"
        directory.mkdir()
        bridge, _ = self.bridge("attempt", [])
        tool = self.tool("cpu")
        controller = TransportCheckpointController(directory, bridge, tool, "fixed-conditions")
        project = Path(__file__).resolve().parents[3]
        path = project / "references/upstream/AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27/agents.py"
        function = next(node for node in ast.parse(path.read_text(encoding="utf-8")).body
                        if isinstance(node, ast.FunctionDef) and node.name == "get_score")
        def query_model(**kwargs):
            controller.abort(ValueError("fixture logical role mismatch"))
        namespace = {"query_model": query_model}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(path), "exec"), namespace)
        with self.assertRaises(_HostTransportAbort) as raised:
            namespace["get_score"]("plan", "report", SyntheticRawProvider.model)
        self.assertIsInstance(raised.exception.cause, ValueError)
        with self.assertRaises(ValueError):
            controller.require_reconciled()


if __name__ == "__main__":
    unittest.main()
