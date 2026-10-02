import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from evidence_research.model import CodexProvider, ModelUnavailable, FileProvider


class ModelEvidenceTests(unittest.TestCase):
    def fake_call(self, command, **kwargs):
        response = Path(command[command.index("--output-last-message") + 1])
        response.write_text('{"candidates":[]}', encoding="utf-8")
        events = [
            {"type": "item.completed", "item": {"type": "agent_message", "text": '{"candidates":[]}'}},
            {"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 4}},
        ]
        return subprocess.CompletedProcess(command, 0, "\n".join(map(json.dumps, events)), "")

    def test_real_trace_contract_caches_only_identical_requests(self):
        with tempfile.TemporaryDirectory() as directory, patch("subprocess.run", side_effect=self.fake_call) as process:
            provider = CodexProvider(directory, model="test-current", executable="codex")
            self.assertEqual(provider.complete("public", call_id="one", json_response=True), {"candidates": []})
            provider.complete("public", call_id="one")
            self.assertEqual(process.call_count, 1)
            self.assertEqual(provider.last_evidence["usage"]["input_tokens"], 12)
            with self.assertRaises(ValueError):
                provider.complete("changed", call_id="one")
            (Path(directory) / "one" / "response.txt").write_text("changed", encoding="utf-8")
            with self.assertRaises(ModelUnavailable):
                provider.complete("public", call_id="one")

    def test_model_tool_use_disqualifies_execution(self):
        def tool_call(command, **kwargs):
            result = self.fake_call(command, **kwargs)
            result.stdout = json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "read forbidden"}}) + "\n" + result.stdout
            return result
        with tempfile.TemporaryDirectory() as directory, patch("subprocess.run", side_effect=tool_call):
            provider = CodexProvider(directory, executable="codex")
            with self.assertRaisesRegex(ModelUnavailable, "Forbidden"):
                provider.complete("public", call_id="one")

    def test_unknown_model_execution_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as directory, patch("subprocess.run", side_effect=KeyboardInterrupt):
            provider = CodexProvider(directory, executable="codex")
            with self.assertRaises(KeyboardInterrupt):
                provider.complete("public", call_id="one")
            with self.assertRaisesRegex(ModelUnavailable, "Unknown"):
                provider.complete("public", call_id="one")

    def test_file_bridge_cannot_impersonate_real_model_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = FileProvider(directory)
            self.assertEqual(provider.execution_kind, "external_response_unverified")
            with self.assertRaises(ModelUnavailable):
                provider.complete("public", call_id="one")


if __name__ == "__main__":
    unittest.main()
