"""Ledger control-flow fixtures; no actual model or performance comparison."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_research import EvidenceError
from evidence_research.model import ModelUnavailable, CodexProvider
from evidence_research import model as model_module
from evidence_research.store import atomic_json
from evidence_research.store import fingerprint, sha256_file
from evidence_research.study import register_pilot, run_pilot, continue_pilot, check_pilot, load, study_events


def settings():
    return {"kind": "development_pilot", "model_id": "fixture-model",
        "baseline_provenance": {"kind": "upstream_adaptation", "fixture": True},
        "resource_envelope": {"proposal_calls_per_unit": 1, "reasoning_effort": None,
            "success_criterion": {"direction": "min", "threshold": 0.03}},
        "units": [{"unit_id": "control-flow-fixture", "task_id": "dev-quadratic", "seed": 7}]}


def fake_score(protocol, owner, public, arm, directory, callback):
    callback({"arm": arm, "model_id": protocol["model_id"],
              "resource_envelope": protocol["resource_envelope"], "public_task": public}, directory)
    telemetry = directory / "telemetry.json"
    atomic_json(telemetry, {"scope": "simulation ledger fixture only"})
    return {"status": "verified", "arm": arm, "model_id": "fixture-model",
        "unit_id": owner["unit_id"], "test_mse": 1.0, "validation_mse": 1.0,
        "provider_calls": 1, "provider_token_usage": {"input_tokens": 1, "output_tokens": 1},
        "total_provider_token_usage": {"input_tokens": 1, "output_tokens": 1},
        "unknown_token_usage": False, "arm_wall_seconds": 42.0,
        "common_report_sufficiency": True, "unsupported_claims": 0,
        "unsupported_numeric_claims": 0, "unsupported_semantic_result_claims": 0,
        "semantic_report_audit_complete": all((directory / name).exists() for name in ("semantic-report-review.json", "semantic-companion-review.json")),
        "whole_report_numeric_audit_complete": (directory / "report-review.json").exists(),
        "evidence": {"telemetry": {"path": str(telemetry), "sha256": "fixture"}}}


def failed_format_fixture(directory, effort=None):
    """Synthetic raw transport format only; no model was actually called."""
    folder = directory / "model" / "failure-format-fixture"
    folder.mkdir(parents=True)
    public_dir = directory / "public_model_cwd"
    public_dir.mkdir(exist_ok=True)
    identity = {"model": "fixture-model", "prompt": "format fixture", "reasoning_effort": effort,
        "full_prompt": CodexProvider.guard + "format fixture", "provider_source_sha256": sha256_file(model_module.__file__)}
    command = ["codex", "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
        "--sandbox", "read-only", "--model", "fixture-model", "--cd", str(public_dir), "--json",
        "-c", 'approval_policy="never"', "--output-last-message", str(folder / "response.txt")]
    if effort is not None:
        command.extend(["-c", f'model_reasoning_effort="{effort}"'])
    command.append("-")
    atomic_json(folder / "request.json", {**identity, "execution_kind": "real_model",
        "fingerprint": fingerprint(identity), "command": command,
        "test_fixture_only": True})
    (folder / "events.jsonl").write_text('{"type":"turn.failed","error":{"message":"fixture unavailable"}}\n', encoding="utf-8")
    (folder / "stderr.log").write_text("synthetic fixture, no execution", encoding="utf-8")
    atomic_json(folder / "result.json", {"model": "fixture-model", "execution_kind": "real_model",
        "status": "failed", "fingerprint": fingerprint(identity), "wall_seconds": 2.0, "tool_calls": [], "usage": {},
        "files": {name: sha256_file(folder / name) for name in ("request.json", "events.jsonl", "stderr.log")}, "test_fixture_only": True})
    host_path = directory / "host-no-action" / "failure-format-fixture.json"
    atomic_json(host_path, {"provenance": "trusted_host_audit", "attempt_result_path": str(folder / "result.json"),
        "attempt_result_sha256": sha256_file(folder / "result.json"), "request_fingerprint": fingerprint(identity),
        "host_action_taken": False, "model_response_consumed": False, "retry_reason": "Synthetic no-action format test",
        "sources": [{"path": str(folder / name), "sha256": sha256_file(folder / name)}
                    for name in ("request.json", "result.json", "events.jsonl", "stderr.log")]})
    return folder


class PilotLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "pilot"

    def tearDown(self):
        self.temp.cleanup()

    def test_registration_does_not_run_callbacks_and_fixes_conditions(self):
        registered = register_pilot(settings(), self.root)
        self.assertEqual(len(registered["units"]), 1)
        self.assertEqual(registered["scope"], "development paired pilot, never confirmatory adoption")
        changed = settings()
        changed["model_id"] = "different-model"
        with self.assertRaises(EvidenceError):
            register_pilot(changed, self.root)
        self.assertEqual(check_pilot(self.root)["config"], settings())

    def test_explicit_semantic_policy_hash_must_match_before_registration(self):
        from evidence_research.report_semantics import SEMANTIC_POLICY
        config=settings();config["resource_envelope"].update(report_semantic_policy=SEMANTIC_POLICY,report_semantic_policy_sha256="f"*64)
        with self.assertRaisesRegex(ValueError,"semantic review policy/hash"):register_pilot(config,self.root)
        self.assertFalse(self.root.exists())
        config["resource_envelope"]["report_semantic_policy_sha256"]=fingerprint(SEMANTIC_POLICY)
        registered=register_pilot(config,self.root)
        self.assertEqual(registered["semantic_report_policy"],SEMANTIC_POLICY)

    def test_pending_review_collects_both_arms_and_resumes_without_calls(self):
        register_pilot(settings(), self.root)
        calls = []
        def callback(payload, directory):
            calls.append(payload)
            atomic_json(directory / "arm-response.json", {"fixture": True})
        with patch("evidence_research.study._score_arm", side_effect=fake_score), patch("evidence_research.study._validate_saved_score"):
            first = run_pilot(self.root, baseline=callback, improved=callback)
            second = run_pilot(self.root, baseline=callback, improved=callback)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["public_task"], calls[1]["public_task"])
        self.assertNotIn("test", calls[0]["public_task"]["task_bundle"])
        self.assertFalse(first["adopted"])
        self.assertFalse(second["design_inputs_complete"])
        self.assertTrue(all(v["status"] == "awaiting_independent_report_review" for v in second["units"][0]["arms"].values()))

    def test_unknown_requested_arm_is_not_repeated(self):
        register_pilot(settings(), self.root)
        directory = self.root / "units" / "control-flow-fixture" / "B"
        directory.mkdir(parents=True)
        atomic_json(directory / "owner-request.json", {"fixture": True})
        calls = []
        def callback(payload, folder):
            calls.append(payload["arm"])
            atomic_json(folder / "arm-response.json", {"fixture": True})
        with patch("evidence_research.study._score_arm", side_effect=fake_score):
            result = run_pilot(self.root, baseline=callback, improved=callback)
        self.assertEqual(calls, ["C"])
        self.assertEqual(result["units"][0]["arms"]["B"]["status"], "unknown_execution")

    def test_external_resource_failure_is_durable_and_not_free(self):
        register_pilot(settings(), self.root)
        with patch("evidence_research.study._score_arm", side_effect=ModelUnavailable("fixture missing external resource")) as scorer:
            result = run_pilot(self.root)
        self.assertEqual(scorer.call_count, 1)
        score = result["units"][0]["arms"]["B"]["score"]
        self.assertIsNone(score["provider_calls"])
        self.assertIsNone(score["provider_billed_cost"])
        self.assertEqual(result["units"][0]["arms"]["C"]["status"], "external_resource_blocked")
        self.assertFalse(result["design_inputs_complete"])
        self.assertEqual(result["units"][0]["arms"]["B"]["status"], "external_resource_pending")
        self.assertFalse((self.root / "units" / "control-flow-fixture" / "B" / "owner-score.json").exists())

    def test_explicit_known_failure_continuation_preserves_attempt_and_cached_measurement(self):
        config = settings()
        config["resource_envelope"]["proposal_calls_per_unit"] = 2
        register_pilot(config, self.root)
        directory = self.root / "units" / "control-flow-fixture" / "B"
        def unavailable(protocol, owner, public, arm, folder, callback):
            failed_format_fixture(folder)
            raise ModelUnavailable("synthetic format failure, no actual model")
        with patch("evidence_research.study._score_arm", side_effect=unavailable):
            run_pilot(self.root)
        attempt = next((directory / "owner-attempts").glob("attempt-*/owner-attempt.json"))
        original_hash = sha256_file(attempt)
        calls = []
        def callback(payload, folder):
            calls.append(payload["arm"])
            atomic_json(folder / "arm-response.json", {"fixture": True})
        with patch("evidence_research.study._score_arm", side_effect=fake_score), patch("evidence_research.study._validate_saved_score"):
            result = continue_pilot(self.root, "control-flow-fixture", "B", "Explicit synthetic ledger recovery", baseline=callback)
            resumed = run_pilot(self.root, baseline=callback, improved=callback)
        self.assertEqual(calls, ["B", "C"])
        self.assertEqual(sha256_file(attempt), original_hash)
        self.assertEqual(result["units"][0]["arms"]["B"]["status"], "awaiting_independent_report_review")
        authorization = next(event for event in study_events(self.root) if event["action"] == "AUTHORIZE_CONTINUATION")
        audit = load(authorization["payload"]["path"])["audit"]
        self.assertTrue(audit["unknown_prior_tokens"])
        self.assertEqual(audit["remaining_provider_attempts"], 1)
        self.assertFalse(resumed["adopted"])

    def test_unknown_and_exhausted_attempts_cannot_be_explicitly_retried(self):
        register_pilot(settings(), self.root)
        directory = self.root / "units" / "control-flow-fixture" / "B"
        directory.mkdir(parents=True)
        atomic_json(directory / "owner-request.json", {"fixture": True})
        with self.assertRaises(EvidenceError):
            continue_pilot(self.root, "control-flow-fixture", "B", "Unknown action cannot be approved away")
        folder = failed_format_fixture(directory)
        with self.assertRaisesRegex(EvidenceError, "budget is exhausted"):
            continue_pilot(self.root, "control-flow-fixture", "B", "Cannot exceed registered budget")
        (folder / "result.json").unlink()
        with self.assertRaisesRegex(EvidenceError, "unknown execution"):
            continue_pilot(self.root, "control-flow-fixture", "B", "Missing original result")

    def test_pilot_uses_conservative_B_bound_and_requires_common_report_gate(self):
        register_pilot(settings(), self.root)
        def callback(payload, directory):
            atomic_json(directory / "arm-response.json", {"fixture": True})
            atomic_json(directory / "report-review.json", {"status": "complete"})
            atomic_json(directory / "companion-review.json", {"status": "complete"})
            atomic_json(directory / "semantic-report-review.json", {"status": "complete", "simulation_only": True})
            atomic_json(directory / "semantic-companion-review.json", {"status": "complete", "simulation_only": True})
        def scored(protocol, owner, public, arm, folder, callback):
            result = fake_score(protocol, owner, public, arm, folder, callback)
            if arm == "B":
                result.update(unknown_token_usage=True, total_provider_token_usage=None,
                              provider_token_usage={"input_tokens": 2, "output_tokens": 2})
            return result
        with patch("evidence_research.study._score_arm", side_effect=scored):
            result = run_pilot(self.root, baseline=callback, improved=callback)
        pair = result["reviewed_paired_observations"][0]
        self.assertEqual(pair["token_gain_kind"], "conservative_lower_bound")
        self.assertFalse(pair["token_accounting_complete"])
        self.assertTrue(result["design_inputs_complete"])
        self.assertFalse(result["adopted"])

    def test_continuation_rejects_matched_effort_change_before_any_callback(self):
        config = settings()
        config["resource_envelope"]["proposal_calls_per_unit"] = 2
        register_pilot(config, self.root)
        directory = self.root / "units" / "control-flow-fixture" / "B"
        directory.mkdir(parents=True)
        atomic_json(directory / "owner-request.json", {"fixture": True})
        failed_format_fixture(directory, effort="medium")
        with patch("evidence_research.study._score_arm") as scorer:
            with self.assertRaisesRegex(ValueError, "reasoning effort differs"):
                continue_pilot(self.root, "control-flow-fixture", "B", "A rationale cannot alter the registered effort")
            scorer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
