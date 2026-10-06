"""Model-free Laya input/response boundary and public CLI contracts.

These checks use fabricated SDK responses. They neither load a Laya model nor
claim that a tokenizer preserves the projection or that candidate choice helps
research performance.
"""
from __future__ import annotations

import builtins
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from research_cli.core import ResearchError, Store, canonical
from research_cli.laya import example, prepare, resolve


ROOT = Path(__file__).resolve().parents[1]


class LayaBoundaryContract(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tests" / ".runs"
        self.test_root.mkdir(exist_ok=True)
        self.temporary = Path(tempfile.mkdtemp(prefix="laya-", dir=self.test_root)).resolve()
        self.workspace = self.temporary / "state"
        self.initial = Store.init(self.workspace)
        self.store = Store(self.workspace)
        self.goal = self.store.goal_create("라야 외부 선택 입력", "Model-free boundary fixture")["id"]
        self.payload = {
            "goal_id": self.goal,
            "context": "외부 에이전트가 최종 연구 판단을 한다.",
            "question": "Which proposal should the external agent review?",
            "candidates": [
                {"id": "candidate-full-id-" + "가설" * 40,
                 "hypothesis": "A candidate may improve the registered measurement.",
                 "applicability": "Only under the declared fixed conditions.",
                 "conditions": {"seed": 7, "data_split": "development", "nested": {"a": 1}},
                 "evidence": [], "observation": "This is an unexecuted proposal."},
                {"id": "candidate-second",
                 "hypothesis": "An alternative proposal needs independent evaluation.",
                 "applicability": "For the same development split.",
                 "conditions": {"seed": 9}, "evidence": []},
            ],
        }
        self.env = dict(os.environ)
        self.env["PYTHONPATH"] = str(ROOT) + os.pathsep + self.env.get("PYTHONPATH", "")

    def tearDown(self):
        self.assertTrue(self.temporary.is_relative_to(self.test_root.resolve()))
        shutil.rmtree(self.temporary)

    def assert_error(self, code, function, *args):
        with self.assertRaises(ResearchError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code, caught.exception.details)

    def response(self, choice="C1", **answer_fields):
        return {"answers": {"research_choice": {"choice": choice, **answer_fields}},
                "usage": {"input_tokens": 71, "output_tokens": 0},
                "routing": {"model": "external-fixture"}}

    def digest(self, value):
        return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()

    def cli(self, *args, payload=None, error=None):
        completed = subprocess.run(
            [sys.executable, "-m", "research_cli", "--workspace", str(self.workspace),
             *map(str, args)], cwd=ROOT, env=self.env,
            input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
            capture_output=True, text=True, encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            result = json.loads(completed.stdout)
        except ValueError:
            self.fail(f"CLI output was not JSON: {completed.stdout!r}; {completed.stderr!r}")
        if error:
            self.assertNotEqual(completed.returncode, 0, result)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["error"]["code"], error, result)
            return result["error"]
        self.assertEqual(completed.returncode, 0, result)
        self.assertTrue(result["ok"], result)
        return result["data"]

    def registration_with_submitted_claim(self):
        """Create a real unexecuted registration with a preserved, untrusted file."""
        job = self.temporary / "job"
        job.mkdir()
        source = job / "task.py"
        source.write_text("print('not executed by Laya preparation')\n", encoding="utf-8")
        validator = self.temporary / "validator.py"
        validator.write_text("import json\nprint(json.dumps({'metrics': {'pass_rate': 0}}))\n",
                             encoding="utf-8")
        self.store.validator_register(
            "laya-fixed", [sys.executable, str(validator), "{bundle}"],
            Path(self.initial["owner_key_path"]).read_text(encoding="utf-8").strip())
        hypothesis = self.store.hypothesis_create(self.goal, "Declared claim is not a verified result")["id"]
        spec = {
            "hypothesis_id": hypothesis, "change": "Record an unexecuted fixture",
            "comparison": "Independent fixed expected result", "data_split": "development",
            "seed": 7, "source_version": {"label": "laya-test", "files": {
                "task.py": hashlib.sha256(source.read_bytes()).hexdigest()}},
            "metrics": ["pass_rate"], "criteria": [{"metric": "pass_rate", "op": ">=", "threshold": 1}],
            "command": [sys.executable, "task.py"], "cwd": str(job),
            "artifacts": [{"name": "result", "path": "result.json"}], "validator": "laya-fixed",
        }
        registration = self.store.register(self.goal, spec, "laya-test-register")["registration"]["id"]
        declared = self.temporary / "declared-result.json"
        declared.write_text('{"pass_rate":1,"agent_claim":"success"}', encoding="utf-8")
        evidence = self.store.add_evidence(registration, "measured", "Agent declares success", declared)["evidence"]
        return registration, self.workspace / evidence["path"]

    def test_prepare_is_deterministic_untruncated_and_model_free(self):
        original = copy.deepcopy(self.payload)
        tail = " END-OF-FULL-HYPOTHESIS 한국어 조건 보존"
        self.payload["candidates"][0]["hypothesis"] = "research detail " * 600 + tail
        revision = self.store.revision()
        importer = builtins.__import__

        def forbid_model_import(name, *args, **kwargs):
            if name.split(".")[0] in ("laya", "torch", "transformers", "openai", "anthropic"):
                raise AssertionError(f"Preparation imported a model dependency: {name}")
            return importer(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=forbid_model_import), \
             mock.patch("subprocess.run", side_effect=AssertionError("Preparation launched a process")), \
             mock.patch("subprocess.Popen", side_effect=AssertionError("Preparation launched a process")):
            bundle = prepare(self.store, self.payload)
            repeated = prepare(self.store, copy.deepcopy(self.payload))
        self.assertEqual(bundle, repeated)
        self.assertEqual(bundle["schema"], "research-laya-choice-v1")
        self.assertEqual(bundle["workspace"], str(self.workspace.resolve()))
        self.assertEqual(bundle["revision"], revision)
        self.assertEqual(bundle["input"], self.payload)
        self.assertEqual(self.payload["candidates"][1], original["candidates"][1])
        self.assertEqual(bundle["labels"], {"C1": self.payload["candidates"][0]["id"],
                                            "C2": "candidate-second", "abstain": None})
        question = bundle["request"]["questions"]["research_choice"]
        self.assertEqual(question["type"], "choice")
        self.assertEqual(list(question["criteria"]), ["C1", "C2", "abstain"])
        self.assertEqual(bundle["option_order"], ["C1", "C2", "abstain"])
        self.assertIn(tail, question["criteria"]["C1"])
        unsigned = {key: value for key, value in bundle.items() if key != "sha256"}
        self.assertEqual(bundle["sha256"], self.digest(unsigned))
        self.assertEqual(self.store.revision(), revision)
        self.assertEqual(self.store.status(self.goal)["hypothesis_total"], 0)

    def test_invalid_candidates_and_nonfinite_values_are_rejected(self):
        invalid = []
        for field, value in (("question", " "), ("context", {}), ("candidates", [])):
            payload = copy.deepcopy(self.payload)
            payload[field] = value
            invalid.append(payload)
        for field, value in (("id", ""), ("hypothesis", ""), ("applicability", []),
                             ("conditions", []), ("evidence", "reg-id"),
                             ("observation", {"verified": True})):
            payload = copy.deepcopy(self.payload)
            payload["candidates"][0][field] = value
            invalid.append(payload)
        payload = copy.deepcopy(self.payload)
        payload["candidates"][1]["id"] = payload["candidates"][0]["id"]
        invalid.append(payload)
        payload = copy.deepcopy(self.payload)
        payload["candidates"][0]["conditions"]["unbounded"] = float("nan")
        invalid.append(payload)
        revision = self.store.revision()
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assert_error("INVALID_INPUT", prepare, self.store, payload)
        self.assertEqual(self.store.revision(), revision)

    def test_response_is_an_unverified_read_only_proposal(self):
        bundle = prepare(self.store, self.payload)
        response = self.response(answer_confidence=0.99)
        original_response = copy.deepcopy(response)
        revision = self.store.revision()
        result = resolve(self.store, bundle, response, bundle["sha256"])
        self.assertEqual(result["kind"], "proposal")
        self.assertFalse(result["verified"])
        self.assertEqual(result["candidate_id"], self.payload["candidates"][0]["id"])
        self.assertEqual(result["state"], "proposed")
        self.assertTrue(result["requires_external_review"])
        self.assertEqual(result["projection_sha256"], bundle["sha256"])
        self.assertEqual(result["response_sha256"], self.digest(response))
        self.assertEqual(result["raw_response"], response)
        self.assertEqual(result["projection"], bundle)
        self.assertEqual(result["context_revision"], revision)
        self.assertEqual(result["token_preservation"], "unknown")
        self.assertEqual(response, original_response)
        self.assertEqual(self.store.revision(), revision)
        self.assertEqual(self.store.status(self.goal)["total"], 0)

    def test_abstention_and_collapsed_options_do_not_select_a_candidate(self):
        bundle = prepare(self.store, self.payload)
        collapsed = self.response()
        collapsed["usage"]["options"] = {"research_choice": {"distinct": 1, "total": 3}}
        cases = [self.response("abstain"), self.response(None),
                 self.response(low_confidence=True), self.response(abstention="abstained"), collapsed]
        for response in cases:
            with self.subTest(response=response):
                result = resolve(self.store, bundle, response, bundle["sha256"])
                self.assertEqual(result["state"], "abstained")
                self.assertIsNone(result["candidate_id"])
                self.assertFalse(result["verified"])
                self.assertTrue(result["requires_external_review"])

    def test_malformed_unknown_and_nonfinite_responses_are_rejected(self):
        bundle = prepare(self.store, self.payload)
        invalid = [{}, {"answers": []}, self.response("C99"), self.response({"choice": "C1"}),
                   self.response(answer_confidence=float("inf"))]
        for response in invalid:
            with self.subTest(response=response):
                self.assert_error("INVALID_INPUT", resolve, self.store, bundle, response, bundle["sha256"])

    def test_projection_digest_and_workspace_mismatch_are_rejected(self):
        bundle = prepare(self.store, self.payload)
        response = self.response()
        self.assert_error("EVIDENCE_TAMPERED", resolve, self.store, bundle, response, "0" * 64)
        changed = copy.deepcopy(bundle)
        changed["request"]["questions"]["research_choice"]["criteria"]["C1"] = "changed meaning"
        self.assert_error("EVIDENCE_TAMPERED", resolve, self.store, changed, response, bundle["sha256"])
        reordered = copy.deepcopy(bundle)
        criteria = reordered["request"]["questions"]["research_choice"]["criteria"]
        reordered["request"]["questions"]["research_choice"]["criteria"] = {
            key: criteria[key] for key in ("C2", "C1", "abstain")}
        # JSON canonicalization sorts object keys; the explicit order contract
        # must still detect reordering even though the canonical digest matches.
        self.assertEqual(self.digest({key: value for key, value in reordered.items() if key != "sha256"}),
                         bundle["sha256"])
        self.assert_error("EVIDENCE_TAMPERED", resolve, self.store, reordered, response, bundle["sha256"])
        changed = copy.deepcopy(bundle)
        changed["workspace"] = str(self.temporary / "another-workspace")
        changed["sha256"] = self.digest({key: value for key, value in changed.items() if key != "sha256"})
        self.assert_error("INVALID_INPUT", resolve, self.store, changed, response, changed["sha256"])

    def test_stale_context_requires_a_new_projection(self):
        bundle = prepare(self.store, self.payload)
        self.store.hypothesis_create(self.goal, "A new research record changed the context")
        self.assert_error("REVISION_CONFLICT", resolve, self.store, bundle, self.response(), bundle["sha256"])
        refreshed = prepare(self.store, self.payload)
        self.assertNotEqual(refreshed["sha256"], bundle["sha256"])
        result = resolve(self.store, refreshed, self.response(), refreshed["sha256"])
        self.assertEqual(result["state"], "proposed")

    def test_record_claim_is_unverified_and_current_file_tampering_is_detected(self):
        registration, blob = self.registration_with_submitted_claim()
        self.payload["candidates"][0]["evidence"] = [registration]
        bundle = prepare(self.store, self.payload)
        before = self.store.show(registration)
        self.assertEqual(before["evidence"][0]["integrity"], "valid")
        self.assertFalse(before["evidence"][0]["verified"])
        self.assertIsNone(before["run"])
        self.assertIsNone(before["verification"])
        snapshot_text = canonical(bundle["snapshot"])
        self.assertIn(registration, snapshot_text)
        self.assertIn('"kind":"measured"', snapshot_text)
        self.assertIn('"verified":false', snapshot_text)
        resolved = resolve(self.store, bundle, self.response(), bundle["sha256"])
        self.assertFalse(resolved["verified"])
        self.assertIsNone(self.store.show(registration)["verification"])
        revision = self.store.revision()
        blob.write_text('{"pass_rate":0,"changed":true}', encoding="utf-8")
        self.assertEqual(self.store.revision(), revision)
        self.assertEqual(self.store.show(registration)["evidence"][0]["integrity"], "tampered")
        self.assert_error("EVIDENCE_TAMPERED", resolve, self.store, bundle, self.response(), bundle["sha256"])

    def test_resolved_proposal_can_be_preserved_without_execution_verification_or_adoption(self):
        registration, _ = self.registration_with_submitted_claim()
        self.payload["candidates"][0]["evidence"] = [registration]
        bundle = prepare(self.store, self.payload)
        resolved = resolve(self.store, bundle, self.response(answer_confidence=1.0), bundle["sha256"])
        proposal_file = self.temporary / "resolved-proposal.json"
        proposal_file.write_text(json.dumps(resolved, ensure_ascii=False), encoding="utf-8")
        self.store.add_evidence(registration, "proposal", "External Laya proposal requires review", proposal_file)

        record = self.store.show(registration)
        self.assertIsNone(record["run"])
        self.assertIsNone(record["verification"])
        self.assertEqual(record["decision"]["state"], "pending")
        proposal = next(item for item in record["evidence"] if item["kind"] == "proposal")
        self.assertEqual(proposal["integrity"], "valid")
        self.assertFalse(proposal["verified"])
        self.assertIsNone(proposal["run_id"])
        preserved = self.workspace / proposal["path"]
        self.assertEqual(json.loads(preserved.read_text(encoding="utf-8")), resolved)
        self.assertEqual(hashlib.sha256(preserved.read_bytes()).hexdigest(), proposal["sha256"])

        memory = self.store.memory(query="External Laya proposal")
        self.assertEqual(memory["total"], 1)
        item = memory["items"][0]
        self.assertEqual(item["id"], registration)
        self.assertEqual(item["execution"], "registered")
        self.assertEqual(item["verification"], "pending")
        self.assertEqual(item["decision"], "pending")
        self.assertEqual(item["outcome"], "inconclusive")
        self.assertFalse(item["claim_verified"])
        self.assert_error("INVALID_TRANSITION", self.store.decide, registration, "adopted", "Laya claimed confidence 1")

    def test_cli_json_help_exclusive_files_and_no_state_mutation(self):
        revision = self.store.revision()
        help_data = self.cli("help", "--topic", "laya")
        self.assertIsInstance(help_data["example"], dict)
        self.assertIn("candidates", help_data["example"])
        self.assertIn("candidates", example(self.goal))
        prepared = self.cli("laya", "prepare", "--input", "-", payload=self.payload)
        bundle = prepared if "schema" in prepared else prepared["projection"]
        self.assertEqual(bundle["schema"], "research-laya-choice-v1")
        self.assertEqual(bundle["input"], self.payload)
        input_path = self.temporary / "input.json"
        input_path.write_text(json.dumps(self.payload, ensure_ascii=False), encoding="utf-8")
        bundle_path = self.temporary / "projection.json"
        self.cli("laya", "prepare", "--input", input_path, "--output", bundle_path)
        stored = json.loads(bundle_path.read_text(encoding="utf-8"))
        self.assertEqual(stored, bundle)
        original_bytes = bundle_path.read_bytes()
        self.cli("laya", "prepare", "--input", input_path, "--output", bundle_path, error="CONFLICT")
        self.assertEqual(bundle_path.read_bytes(), original_bytes)
        response_path = self.temporary / "response.json"
        response_path.write_text(json.dumps(self.response()), encoding="utf-8")
        result_path = self.temporary / "proposal.json"
        result = self.cli("laya", "resolve", "--input", bundle_path, "--response", response_path,
                          "--expected-sha256", stored["sha256"])
        self.assertEqual(result["state"], "proposed")
        self.assertFalse(result["verified"])
        self.cli("laya", "resolve", "--input", bundle_path, "--response", response_path,
                 "--expected-sha256", stored["sha256"], "--output", result_path)
        stored_result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(stored_result, result)
        self.cli("laya", "resolve", "--input", bundle_path, "--response", response_path,
                 "--expected-sha256", stored["sha256"], "--output", result_path, error="CONFLICT")
        self.assertEqual(json.loads(result_path.read_text(encoding="utf-8")), result)
        self.assertEqual(self.store.revision(), revision)


if __name__ == "__main__":
    unittest.main()
