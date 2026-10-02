"""Candidate-only source-contract fixtures; zero model calls or CPU research runs."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import types
import unittest
from unittest.mock import patch

from evidence_research import baseline
from evidence_research.arms import literature_from_envelope, literature_protocol_from_envelope
from evidence_research.model import CodexProvider, digest
from evidence_research.store import atomic_json

PROJECT = Path(__file__).resolve().parents[1]
UPSTREAM = PROJECT / "references/upstream/AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27"
PINS = {"utils": "ea23c00695613ab346ac6646f69dbf2b0972efda7c1cafeccd5ffdb4f5f439c8",
        "agents": "d8d1eda040eb1fa897d84596a1b36f277e83da75433c1a9ac2d9efe5be5c749a",
        "ai_lab_repo": "799a3c078d835cd632487f52ed5b8e9f155bb9514ca104a30442ecfbcb7765ff",
        "mlesolver": "cc110f2b07642532cca11bd8cbf74becfc41016c7f876c16f6d40379ec59882c",
        "papersolver": "8c16d68577570fbf6332d3f070e5aec975ed3fd3e1440918940f16eb8911366c"}
C_REFERENCE_COPY_AST_PIN = "ebaf5c6ec4942cff60f42739c8609636ac73d4e0dd64bee863469c975fecc525"


def corpus():
    value = json.loads((PROJECT / "references/task_literature_v2.json").read_text(encoding="utf-8"))
    if digest(value["records"]) != value["records_sha256"]:
        raise ValueError("Source corpus digest differs")
    return value["records"]


def entry(paper):
    return {"arxiv_id": paper["id"], "full_text": paper["text"],
            "summary": "Synthetic source-exposure fixture; not an actual model reading result."}


def policy(entries=5, shared=5):
    return baseline.make_literature_protocol(entries, shared)


class StopBeforeUpstream(Exception):
    pass


class LiteratureIntegrityPolicyTests(unittest.TestCase):
    def setUp(self):
        # These are control/source fixtures. Fail if they accidentally call any
        # transport, generated experiment runner, subprocess or network service.
        self.blockers = []
        for target in ("evidence_research.tasks.run_task", "evidence_research.arms.run_task",
                       "evidence_research.model.CodexProvider.complete", "subprocess.Popen", "socket.socket"):
            blocker = patch(target, side_effect=AssertionError("No model/CPU/network/subprocess is allowed in these fixtures"))
            mock = blocker.start()
            self.addCleanup(blocker.stop)
            self.blockers.append(mock)

    def tearDown(self):
        for blocked in self.blockers:
            self.assertEqual(blocked.call_count, 0)

    def test_original_sources_remain_exactly_pinned(self):
        for module, pin in PINS.items():
            self.assertEqual(hashlib.sha256((UPSTREAM / (module + ".py")).read_bytes()).hexdigest(), pin)

    def test_valid_duplicate_entries_are_source_verified_diagnostics(self):
        papers = corpus()
        review = [entry(papers[i]) for i in (0, 3, 4, 0, 3)]
        result = baseline.verify_literature_review(review, papers, 5, protocol=policy())
        self.assertTrue(result["valid"], result["reasons"])
        self.assertEqual((result["original_review_entry_count"], result["provenance_verified_review_entries"],
                          result["distinct_verified_source_records"], result["duplicate_source_entries"]), (5, 5, 3, 2))
        self.assertFalse(result["selection_integrity_diagnostics"]["duplicates_are_common_task_failure"])
        self.assertEqual(len(result["selection_integrity_diagnostics"]["unselected_shared_source_ids"]), 2)
        self.assertIn("not proof of full-paper reading", result["scope"])
        self.assertTrue(all(row["summary_kind"] == "model_authored_literature_claim" for row in result["entries"]))

    def test_known_entries_still_need_original_minimum_length(self):
        papers = corpus()
        result = baseline.verify_literature_review([entry(papers[i]) for i in (0, 3, 4, 0)], papers, 5, protocol=policy())
        self.assertFalse(result["valid"])
        self.assertFalse(result["original_entry_count_satisfies_minimum"])
        self.assertIn("original minimum", " ".join(result["reasons"]))

    def test_unknown_source_cannot_be_promoted_by_original_list_length(self):
        papers = corpus()
        review = [entry(papers[0])] * 4 + [{"arxiv_id": "unregistered-id", "full_text": papers[0]["text"], "summary": "unsupported"}]
        result = baseline.verify_literature_review(review, papers, 5, protocol=policy())
        self.assertTrue(result["original_entry_count_satisfies_minimum"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["provenance_verified_review_entries"], 4)
        self.assertFalse(result["entries"][-1]["source_membership"])

    def test_mismatched_blank_or_nonstring_synopsis_always_fails(self):
        papers = corpus()
        for text in ("different source", "", "   ", None, [papers[0]["text"]]):
            review = [entry(papers[0])] * 4 + [{**entry(papers[0]), "full_text": text}]
            result = baseline.verify_literature_review(review, papers, 5, protocol=policy())
            self.assertFalse(result["valid"])
            self.assertFalse(result["entries"][-1]["source_synopsis_matches_registered_record"])

    def test_missing_registered_synopsis_cannot_fall_back_to_abstract(self):
        papers = corpus()
        broken = copy.deepcopy(papers)
        review = [entry(broken[0])] * 5
        broken[0]["abstract"] = broken[0].pop("text")
        result = baseline.verify_literature_review(review, broken, 5, protocol=policy())
        self.assertFalse(result["valid"])
        self.assertEqual(result["provenance_verified_review_entries"], 0)
        with self.assertRaisesRegex(ValueError, "source synopsis"):
            literature_from_envelope({"literature_snapshot": broken, "literature_protocol": policy()})
        with self.assertRaisesRegex(ValueError, "source synopsis"):
            baseline.SnapshotLiterature(broken, lambda event: None).retrieve_full_paper_text(broken[0]["id"])

    def test_malformed_entries_do_not_bypass_provenance(self):
        papers = corpus()
        for malformed in (None, [], {"arxiv_id": []}, {"arxiv_id": {"id": papers[0]["id"]}}):
            result = baseline.verify_literature_review([entry(papers[0])] * 4 + [malformed], papers, 5, protocol=policy())
            self.assertFalse(result["valid"])

    def test_shared_corpus_requirement_is_separate_from_entry_count(self):
        papers = corpus()[:3]
        envelope = {"literature_snapshot": papers, "literature_protocol": policy(5, 3),
                    "upstream_settings": {"num_papers_lit_review": 5}}
        self.assertEqual(len(literature_from_envelope(envelope)), 3)
        result = baseline.verify_literature_review([entry(papers[0])] * 5, papers, 5, protocol=policy(5, 3))
        self.assertTrue(result["valid"])
        with self.assertRaisesRegex(ValueError, "enough distinct"):
            literature_from_envelope({**envelope, "literature_protocol": policy(5, 5)})
        result = baseline.verify_literature_review([entry(papers[0])] * 5, papers, 5, protocol=policy(5, 5))
        self.assertFalse(result["valid"])
        self.assertIn("shared registered corpus", " ".join(result["reasons"]))

    def test_registered_corpus_duplicate_ids_or_urls_still_fail_closed(self):
        papers = corpus()
        for field in ("id", "url"):
            altered = copy.deepcopy(papers)
            altered[-1][field] = altered[0][field]
            with self.assertRaisesRegex(ValueError, "Duplicate literature"):
                literature_from_envelope({"literature_snapshot": altered, "literature_protocol": policy()})
        altered = copy.deepcopy(papers)
        altered[-1]["id"] = "1910.02373v99"
        with self.assertRaisesRegex(ValueError, "Duplicate literature"):
            literature_from_envelope({"literature_snapshot": altered, "literature_protocol": policy()})

    def test_protocol_version_fields_counts_and_original_setting_are_bound(self):
        for altered in ({**policy(), "protocol_version": "v5-distinct-selected-sources"},
                        {**policy(), "original_minimum_review_entries": True},
                        {**policy(), "required_shared_corpus_distinct_records": 0},
                        {**policy(), "duplicates_are_failures": True}, {}):
            with self.assertRaises(ValueError):
                baseline.validate_literature_protocol(altered)
        with self.assertRaisesRegex(ValueError, "explicit literature_protocol"):
            literature_protocol_from_envelope({})
        with self.assertRaisesRegex(ValueError, "must match"):
            literature_protocol_from_envelope({"literature_protocol": policy(), "upstream_settings": {"num_papers_lit_review": 3}})
        self.assertEqual(literature_protocol_from_envelope({"literature_protocol": policy()}, required_entries=5), policy())

    def test_supplied_corpus_hash_cannot_be_replaced_by_local_default(self):
        papers = corpus()
        with self.assertRaisesRegex(ValueError, "does not match"):
            literature_from_envelope({"literature_snapshot": papers, "literature_protocol": policy(),
                                     "literature_snapshot_sha256": "0" * 64})
        detached = literature_from_envelope({"literature_snapshot": papers, "literature_protocol": policy(),
                                            "literature_snapshot_sha256": digest(papers)})
        detached[0]["text"] = "changed local caller copy"
        self.assertNotEqual(detached, papers)

    def test_original_add_review_and_completion_still_use_entries(self):
        path = UPSTREAM / "agents.py"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), PINS["agents"])
        tree = ast.parse(path.read_text(encoding="utf-8"))
        student = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PhDStudentAgent")
        method = next(node for node in student.body if isinstance(node, ast.FunctionDef) and node.name == "add_review")
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), str(path), "exec"), namespace)
        student_fixture = types.SimpleNamespace(lit_review=[])
        tool = baseline.SnapshotLiterature(corpus(), lambda event: None)
        for index in (0, 3, 4, 0, 3):
            paper = corpus()[index]
            feedback, text = namespace["add_review"](student_fixture, paper["id"] + "\nsynthetic synopsis", tool)
            self.assertTrue(feedback.startswith("Successfully added paper"))
            self.assertEqual(text, paper["text"])
        self.assertEqual(len(student_fixture.lit_review), 5)
        workflow_path = UPSTREAM / "ai_lab_repo.py"
        self.assertEqual(hashlib.sha256(workflow_path.read_bytes()).hexdigest(), PINS["ai_lab_repo"])
        workflow_tree = ast.parse(workflow_path.read_text(encoding="utf-8"))
        checks = [node for node in ast.walk(workflow_tree) if isinstance(node, ast.Compare)
                  and ast.unparse(node) == "len(self.phd.lit_review) >= self.num_papers_lit_review"]
        self.assertEqual(len(checks), 2)
        host = types.SimpleNamespace(phd=student_fixture, num_papers_lit_review=5)
        self.assertTrue(eval(compile(ast.Expression(checks[0]), str(workflow_path), "eval"), {"self": host}))
        self.assertTrue(baseline.verify_literature_review(student_fixture.lit_review, corpus(), 5, protocol=policy())["valid"])

    def test_direct_baseline_default_is_new_version_bound_and_explicitly_tagged(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = {"model": "synthetic-no-model", "max_steps": 2, "mlesolver_max_steps": 1,
                        "papersolver_max_steps": 0, "num_papers_lit_review": 1}
            def forbidden(*args, **kwargs):
                raise AssertionError("No upstream model or execution may occur")
            with patch.object(baseline, "_module_scope", side_effect=StopBeforeUpstream("Stop after registration-only contract")):
                with self.assertRaises(StopBeforeUpstream):
                    baseline.run_upstream_baseline({"objective": "synthetic contract"}, Path(folder), forbidden, forbidden,
                        settings, literature=corpus(), source_dir=UPSTREAM)
            registration = json.loads((Path(folder) / "baseline_registration.json").read_text())
            self.assertEqual(registration["literature_protocol"], policy(1, 1))
            self.assertEqual(registration["literature_protocol_origin"], "unregistered_standalone_candidate_default")
            self.assertFalse((Path(folder) / "baseline_result.json").exists())

    def test_old_protocol_failure_cannot_be_reclassified_by_resume(self):
        runs = PROJECT / "runs"
        runs.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="c6-fixture-only-", dir=runs) as folder:
            previous = Path(folder) / "previous"
            previous.mkdir()
            settings = {"model": "fixture", "num_papers_lit_review": 5}
            old = {"kind": "upstream_actual_adapted", "commit": baseline.UPSTREAM_COMMIT,
                   "task_public_sha256": "synthetic", "settings": settings,
                   "literature_sha256": "synthetic", "source_sha256": PINS, "fixture_only": True}
            result = {"status": "failure", "registration_sha256": baseline._hash(old), "artifact_hashes": {},
                      "error": "HostLiteratureContractError: historical distinct-selected gate", "fixture_only": True}
            atomic_json(previous / "baseline_registration.json", old)
            atomic_json(previous / "baseline_result.json", result)
            before = {p.name: p.read_bytes() for p in previous.iterdir()}
            new = {**old, "literature_protocol": policy(), "literature_protocol_origin": "explicit_registered_envelope"}
            with self.assertRaisesRegex(ValueError, "changes registered literature_protocol"):
                baseline._resume_source({**settings, "resume_from": str(previous), "retry_reason": "synthetic candidate"}, new,
                                        Path(folder) / "new")
            self.assertEqual(before, {p.name: p.read_bytes() for p in previous.iterdir()})

    def test_c_companion_reference_copy_does_not_depend_on_reading_evidence(self):
        # Evaluate only the exact pinned bibliography comprehension from _finish,
        # not the task runner or report function. Empty model trace is irrelevant
        # to this host-generated field and therefore cannot prove consumption.
        path = PROJECT / "evidence_research/comparison_arms.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ImprovedArm")
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_finish")
        assigned = next(node.value for node in method.body if isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name) and target.id == "literature" for target in node.targets))
        # This fixed subtree pin was derived from the externally recorded v5
        # module SHA e9936619...b00b9, not from the changing candidate itself.
        self.assertEqual(hashlib.sha256(ast.dump(assigned, include_attributes=False).encode()).hexdigest(), C_REFERENCE_COPY_AST_PIN)
        self.assertNotIn("trace", {node.id for node in ast.walk(assigned) if isinstance(node, ast.Name)})
        references = eval(compile(ast.Expression(assigned), str(path), "eval"),
                          {"literature_from_envelope": literature_from_envelope,
                           "payload": {"resource_envelope": {"literature_snapshot": corpus(), "literature_protocol": policy()}}})
        self.assertEqual(len(references), 5)
        self.assertTrue(all(reference["kind"] == "literature" for reference in references))
        self.assertFalse(any(key in reference for reference in references for key in ("read", "understood", "measured", "comprehension")))


if __name__ == "__main__":
    unittest.main()
