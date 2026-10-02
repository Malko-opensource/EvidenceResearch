"""Synthetic audit fixtures. No fixture is real model execution evidence."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from evidence_research.model_attempt_audit import audit_failed_model_attempts, _digest, _hash


class FailedAttemptAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "unit-test-failed-request"
        self.folder.mkdir()
        self.request = {"model": "unit-test-model", "prompt": "test only", "reasoning_effort": None,
                        "command": ["codex", "exec", "--model", "unit-test-model"], "execution_kind": "real_model"}
        self.request["fingerprint"] = _digest({k: self.request[k] for k in ("model", "prompt", "reasoning_effort")})
        self.events = [{"type": "turn.started"}, {"type": "turn.failed", "error": {"message": "Selected model is at capacity"}}]
        self.receipt = self.root / "host-receipt.json"
        self.lineage = self.root / "lineage.json"
        self.rewrite()

    @staticmethod
    def write(path, data):
        path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")

    def rewrite(self, *, consumed=False):
        self.write(self.folder / "request.json", self.request)
        (self.folder / "events.jsonl").write_text("\n".join(json.dumps(e) for e in self.events), encoding="utf-8")
        (self.folder / "stderr.log").write_text("unit-test fixture", encoding="utf-8")
        usage = next((e["usage"] for e in self.events if e.get("type") == "turn.failed" and "usage" in e), {})
        result = {"status": "failed", "model": "unit-test-model", "execution_kind": "real_model",
                  "fingerprint": self.request["fingerprint"], "tool_calls": [], "wall_seconds": 2.5,
                  "usage": usage, "files": {name: _hash(self.folder / name) for name in ("request.json", "events.jsonl", "stderr.log")}}
        self.write(self.folder / "result.json", result)
        self.write(self.receipt, {"provenance": "trusted_host_audit", "attempt_result_sha256": _hash(self.folder / "result.json"),
                                 "request_fingerprint": self.request["fingerprint"], "host_action_taken": False,
                                 "model_response_consumed": consumed, "retry_reason": "recover provider capacity",
                                 "sources": [{"path": str(self.folder / "events.jsonl"), "sha256": _hash(self.folder / "events.jsonl")}]})
        self.write(self.lineage, {"provenance": "trusted_host_audit", "kind": "explicit_model_attempt_resume_lineage", "model_id": "unit-test-model",
                                 "attempts": [{"failed_dir": str(self.folder), "result_sha256": _hash(self.folder / "result.json"),
                                               "request_fingerprint": self.request["fingerprint"], "host_action_receipt": str(self.receipt), "receipt_sha256": _hash(self.receipt)}]})

    def audit(self, **kwargs):
        args = {"model_id": "unit-test-model", "allowed_roots": [str(self.root)],
                "host_action_receipts": {str(self.folder): str(self.receipt)}, "lineage_path": str(self.lineage)}
        args.update(kwargs)
        return audit_failed_model_attempts([str(self.folder)], **args)

    def test_absent_failure_tokens_are_unknown_not_zero(self):
        result = self.audit()
        self.assertEqual(result["failed_attempts"], 1)
        self.assertEqual(result["failed_seconds"], 2.5)
        self.assertIsNone(result["failed_token_usage"])
        self.assertTrue(result["adoption_blocked_for_token_endpoint"])

    def test_raw_attested_failure_usage_can_be_accounted(self):
        self.events[-1]["usage"] = {"input_tokens": 7, "output_tokens": 1}
        self.rewrite()
        result = self.audit()
        self.assertEqual(result["failed_token_usage"], {"input_tokens": 7, "output_tokens": 1})
        self.assertFalse(result["unknown_failed_token_usage"])

    def test_hash_or_fingerprint_change_is_rejected(self):
        (self.folder / "events.jsonl").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            self.audit()

    def test_tool_action_disqualifies_failure(self):
        self.events.insert(1, {"type": "item.completed", "item": {"type": "command_execution"}})
        self.rewrite()
        with self.assertRaisesRegex(ValueError, "tool actions"):
            self.audit()

    def test_completed_turn_is_not_failed_request(self):
        self.events.insert(1, {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 3}})
        self.rewrite()
        with self.assertRaisesRegex(ValueError, "completed turn"):
            self.audit()

    def test_consumed_response_or_missing_lineage_rejected(self):
        self.rewrite(consumed=True)
        with self.assertRaisesRegex(ValueError, "consumed response"):
            self.audit()
        self.rewrite()
        with self.assertRaisesRegex(ValueError, "explicit resume lineage"):
            self.audit(lineage_path=None)

    def test_duplicate_copied_record_is_not_a_second_request(self):
        copy = self.root / "copied-failure-record"
        shutil.copytree(self.folder, copy)
        lineage = json.loads(self.lineage.read_text())
        second = dict(lineage["attempts"][0], failed_dir=str(copy))
        lineage["attempts"].append(second)
        self.write(self.lineage, lineage)
        with self.assertRaisesRegex(ValueError, "double-count"):
            audit_failed_model_attempts([str(self.folder), str(copy)], model_id="unit-test-model", allowed_roots=[str(self.root)],
                                       host_action_receipts={str(self.folder): str(self.receipt), str(copy): str(self.receipt)}, lineage_path=str(self.lineage))

    def test_failed_request_settings_match_same_registered_envelope(self):
        from tests.test_model_request_audit import rich_request
        self.request=rich_request(self.root,self.folder,model="unit-test-model")
        self.rewrite()
        self.assertTrue(self.audit(resource_envelope={"reasoning_effort":"medium"},arm_output=str(self.root))["valid"])
        with self.assertRaisesRegex(ValueError,"reasoning effort"):
            self.audit(resource_envelope={"reasoning_effort":"high"},arm_output=str(self.root))


if __name__ == "__main__":
    unittest.main()
