"""Pinned upstream control flow with local synthetic transport receipts.

No actual model is invoked. Resource counts describe fixture execution only.
"""
import ast
from contextlib import redirect_stdout
from copy import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from abc import abstractmethod

from evidence_research.arms import AllowlistedExperimentTool, UpstreamCodexBridge, development_envelope, frozen_literature
from evidence_research.baseline import run_upstream_baseline, _read_checkpoint_commit
from evidence_research.model import ModelUnavailable, PreregisteredResourcesExhausted
from evidence_research.tasks import make_spec
from tests.test_checkpoint_replay import SyntheticRawProvider, context


FUTURE = Path(__file__).resolve().parents[1]
# The frozen version must carry its own pinned sources. Never silently use the
# parent project's references when this test is copied to an independent root.
UPSTREAM = FUTURE / "references/upstream/AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27"


class BaselineTransportIntegrationTests(unittest.TestCase):
    def setUp(self):
        root = FUTURE / "runs/tf"
        root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_original_initial_phase_known_failure_reconstructs_without_repeating_completion(self):
        first = self.root / "first"
        provider = SyntheticRawProvider(first / "model", ["```SUMMARY\nridge regression\n```", ModelUnavailable("fixture definitive failure")])
        bridge = UpstreamCodexBridge(provider, first, max_model_calls=4)
        tool = AllowlistedExperimentTool(first / "experiments", lambda config: make_spec("dev-quadratic", 7, config))
        settings = development_envelope(provider.model)
        public = {"objective": "Fixture pipeline transport audit; not a research trial"}
        before = {str(path): path.read_bytes() for path in UPSTREAM.glob("*.py")}
        failure = run_upstream_baseline(public, first / "upstream", bridge, tool, settings,
                                       literature=frozen_literature(), source_dir=UPSTREAM)
        self.assertEqual(failure["status"], "failure")
        self.assertTrue(failure["error"].startswith("ModelUnavailable:"), failure["error"])
        self.assertEqual(len(provider.calls), 2)
        self.assertFalse((first / "upstream/transport_checkpoint_head.json").exists())
        self.assertTrue((first / "upstream/transport_initial_state.json").is_file())
        self.assertEqual(bridge.export_cursor()["next_ordinal"], 1)

        resumed = self.root / "resumed"
        fresh = SyntheticRawProvider(resumed / "model", [ModelUnavailable("fixture second definitive failure")])
        resumed_bridge = UpstreamCodexBridge(fresh, resumed, max_model_calls=4, replay_directories=[first])
        resumed_tool = AllowlistedExperimentTool(resumed / "experiments", lambda config: make_spec("dev-quadratic", 7, config))
        continuation_settings = {**settings, "resume_from": str(first / "upstream"),
                                 "retry_reason": "Explicit synthetic definitive no-action continuation"}
        continued = run_upstream_baseline(public, resumed / "upstream", resumed_bridge, resumed_tool,
            continuation_settings, literature=frozen_literature(), source_dir=UPSTREAM)
        self.assertEqual(continued["status"], "failure")
        self.assertTrue(continued["error"].startswith("ModelUnavailable:"), continued["error"])
        self.assertEqual(len(fresh.calls), 1)
        self.assertEqual([event["reused_completed_evidence"] for event in resumed_bridge.calls], [True, False])
        self.assertEqual(resumed_bridge.prior_attempts, 2)
        self.assertEqual(continued["continuation"]["restore_mode"], "original_initial_state_with_completed_response_replay")
        self.assertEqual(tool.completed, [])
        self.assertEqual(resumed_tool.completed, [])
        self.assertEqual(before, {str(path): path.read_bytes() for path in UPSTREAM.glob("*.py")})
        # Reopening a completed failure returns that receipt without touching transport.
        preserved_calls = len(fresh.calls)
        cached = run_upstream_baseline(public, resumed / "upstream", resumed_bridge, resumed_tool,
            continuation_settings, literature=frozen_literature(), source_dir=UPSTREAM)
        self.assertTrue(cached["resumed_without_execution"])
        self.assertEqual(len(fresh.calls), preserved_calls)

    def test_pinned_mle_stable_invalid_prompt_consumes_each_cached_receipt_once(self):
        source = UPSTREAM / "mlesolver.py"
        nodes = [node for node in ast.parse(source.read_text(encoding="utf-8")).body
                 if isinstance(node, ast.ClassDef) and node.name in {"Command", "Replace", "Edit", "MLESolver"}]
        namespace = {"copy": copy, "abstractmethod": abstractmethod, "remove_figures": lambda: None}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(source), "exec"), namespace)
        invalid = "unsupported_fixture_command_without_a_protocol_fence"

        def run_solver(bridge):
            host_ordinal = 0
            def query_model(**kwargs):
                nonlocal host_ordinal
                answer = bridge(**kwargs, _logical_context=context(host_ordinal, "fixture-original-mle", "running experiments"))
                host_ordinal += 1
                return answer
            namespace["query_model"] = query_model
            solver = namespace["MLESolver"](dataset_code="", notes=[], max_steps=3,
                insights="", plan="Fixture plan", llm_str=SyntheticRawProvider.model)
            solver.commands = [namespace["Replace"]()]
            solver.model, solver.supress_print = SyntheticRawProvider.model, True
            with redirect_stdout(io.StringIO()), self.assertRaises(PreregisteredResourcesExhausted):
                solver.gen_initial_code()

        original_dir = self.root / "original"
        original_provider = SyntheticRawProvider(original_dir / "model", [invalid] * 5)
        original = UpstreamCodexBridge(original_provider, original_dir, max_model_calls=5)
        original.configure_cursor(0)
        run_solver(original)
        self.assertEqual(len(original_provider.calls), 5)
        self.assertEqual(len({event["request_sha256"] for event in original.calls}), 5)

        exact = self.root / "exhausted-cache"
        no_fresh = SyntheticRawProvider(exact / "model", [])
        replay = UpstreamCodexBridge(no_fresh, exact, max_model_calls=5, replay_directories=[original_dir])
        replay.configure_cursor(0)
        run_solver(replay)
        self.assertEqual(len(replay.calls), 5)
        self.assertTrue(all(event["reused_completed_evidence"] for event in replay.calls))
        self.assertEqual(no_fresh.calls, [])

        extra = self.root / "two-fresh-slots"
        two_fresh = SyntheticRawProvider(extra / "model", [invalid] * 2)
        continued = UpstreamCodexBridge(two_fresh, extra, max_model_calls=7, replay_directories=[original_dir])
        continued.configure_cursor(0)
        run_solver(continued)
        self.assertEqual(len(continued.calls), 7)
        self.assertEqual(len(two_fresh.calls), 2)
        self.assertEqual([event["reused_completed_evidence"] for event in continued.calls], [True] * 5 + [False] * 2)
        self.assertEqual(len({event["request_sha256"] for event in continued.calls[4:]}), 1)

    def test_original_phase_checkpoint_restores_agents_and_cached_midphase_tail(self):
        first = self.root / "phase-first"
        responses = ["```ADD_PAPER\n1910.02373v2\nFixture-authored short source synopsis.\n```",
                     "```DIALOGUE\nFixture planning question.\n```", ModelUnavailable("fixture definitive midphase failure")]
        provider = SyntheticRawProvider(first / "model", responses)
        bridge = UpstreamCodexBridge(provider, first, max_model_calls=5)
        tool = AllowlistedExperimentTool(first / "experiments", lambda config: make_spec("dev-quadratic", 7, config))
        settings = development_envelope(provider.model)
        public = {"objective": "Fixture actual original checkpoint, not a research trial"}
        failure = run_upstream_baseline(public, first / "upstream", bridge, tool, settings,
                                       literature=frozen_literature(), source_dir=UPSTREAM)
        self.assertTrue(failure["error"].startswith("ModelUnavailable:"), failure["error"])
        commit = _read_checkpoint_commit(first / "upstream")
        self.assertIsNotNone(commit)
        self.assertEqual(commit["cursor"]["host_ordinal"], 1)
        self.assertEqual(commit["cursor"]["model"]["next_ordinal"], 1)
        self.assertEqual(commit["cursor"]["phase"], "literature review")
        self.assertEqual(bridge.export_cursor()["next_ordinal"], 2)

        resumed = self.root / "phase-resumed"
        fresh = SyntheticRawProvider(resumed / "model", [ModelUnavailable("fixture repeated definitive failure")])
        resumed_bridge = UpstreamCodexBridge(fresh, resumed, max_model_calls=5, replay_directories=[first])
        resumed_tool = AllowlistedExperimentTool(resumed / "experiments", lambda config: make_spec("dev-quadratic", 7, config))
        continued = run_upstream_baseline(public, resumed / "upstream", resumed_bridge, resumed_tool,
            {**settings, "resume_from": str(first / "upstream"), "retry_reason": "Explicit fixture checkpoint continuation"},
            literature=frozen_literature(), source_dir=UPSTREAM)
        self.assertTrue(continued["error"].startswith("ModelUnavailable:"), continued["error"])
        self.assertTrue(continued["resumed_phase_status"]["literature review"])
        self.assertFalse(continued["resumed_phase_status"]["plan formulation"])
        self.assertEqual(continued["continuation"]["restore_mode"], "hash_linked_phase_and_transport_checkpoint")
        self.assertEqual(len(fresh.calls), 1)
        self.assertEqual([item["reused_completed_evidence"] for item in resumed_bridge.calls], [True, False])
        self.assertEqual(resumed_bridge.calls[0]["logical_request"]["ordinal"], 1)
        self.assertEqual(resumed_bridge.calls[0]["logical_request"]["checkpoint_sha256"], commit["manifest"]["checkpoint_sha256"])
        self.assertEqual(resumed_tool.completed, [])

    def test_original_mle_model_cpu_model_tail_preserves_exact_host_output(self):
        first = self.root / "mle-first"
        responses = ["```ADD_PAPER\n1910.02373v2\nFixture source synopsis.\n```",
            "```PLAN\nFixture test of literal polynomial training.\n```",
            "```SUBMIT_CODE\nCONFIG = {'degree': 1, 'alpha': 0.0}\n```",
            "```REPLACE\nCONFIG = {'degree': 2, 'alpha': 0.0}\n```",
            "fixture malformed SCORE response", ModelUnavailable("fixture definitive MLE failure")]
        provider = SyntheticRawProvider(first / "model", responses)
        bridge = UpstreamCodexBridge(provider, first, max_model_calls=8)
        tool = AllowlistedExperimentTool(first / "experiments", lambda config: make_spec("dev-quadratic", 7, config))
        settings = development_envelope(provider.model)
        public = {"objective": "Fixture original MLE model/CPU/model reconstruction, not a research comparison"}
        failure = run_upstream_baseline(public, first / "upstream", bridge, tool, settings,
                                       literature=frozen_literature(), source_dir=UPSTREAM)
        self.assertTrue(failure["error"].startswith("ModelUnavailable:"), failure["error"])
        self.assertEqual(len(tool.completed), 2)
        commit = _read_checkpoint_commit(first / "upstream")
        self.assertEqual(commit["cursor"]["phase"], "data preparation")
        self.assertEqual(commit["cursor"]["model"]["next_ordinal"], 3)
        self.assertEqual(commit["cursor"]["tool"]["next_ordinal"], 1)

        resumed = self.root / "mle-resumed"
        fresh = SyntheticRawProvider(resumed / "model", [ModelUnavailable("fixture repeated MLE failure")])
        resumed_bridge = UpstreamCodexBridge(fresh, resumed, max_model_calls=8, replay_directories=[first])
        def no_repeat_cpu(*args, **kwargs):
            self.fail("A reconstructed completed MLE tail must not execute CPU again")
        resumed_tool = AllowlistedExperimentTool(resumed / "experiments",
            lambda config: make_spec("dev-quadratic", 7, config), runner=no_repeat_cpu, prior_records=tool.records)
        continued = run_upstream_baseline(public, resumed / "upstream", resumed_bridge, resumed_tool,
            {**settings, "resume_from": str(first / "upstream"), "retry_reason": "Explicit fixture MLE continuation"},
            literature=frozen_literature(), source_dir=UPSTREAM)
        self.assertTrue(continued["error"].startswith("ModelUnavailable:"), continued["error"])
        self.assertEqual(len(fresh.calls), 1)
        self.assertEqual([item["reused_completed_evidence"] for item in resumed_bridge.calls], [True, True, False])
        self.assertEqual(len(resumed_tool.completed), 2)
        self.assertEqual(resumed_tool.records[-1]["status"], "logical_tool_replay")
        self.assertEqual(resumed_bridge.calls[1]["request_sha256"], bridge.calls[4]["request_sha256"])
        self.assertEqual(resumed_tool.records[-1]["output_receipt_sha256"], tool.records[-1]["output_receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
