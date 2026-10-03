"""External original-source pins; no model, fitting, or original phase run."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from evidence_research import baseline

PROJECT = Path(__file__).resolve().parents[1]
UPSTREAM = PROJECT / "references/upstream" / ("AgentLaboratory-" + baseline.UPSTREAM_COMMIT)


class PinnedUpstreamSourceTests(unittest.TestCase):
    def setUp(self):
        self.blockers = []
        for target in ("evidence_research.model.CodexProvider.complete", "evidence_research.tasks.run_task",
                       "evidence_research.arms.run_task", "subprocess.Popen", "socket.socket"):
            blocker = patch(target, side_effect=AssertionError("No research/provider/network/subprocess allowed"))
            mock = blocker.start()
            self.addCleanup(blocker.stop)
            self.blockers.append(mock)

    def tearDown(self):
        for blocker in self.blockers:
            self.assertEqual(blocker.call_count, 0)

    def copy_sources(self, root):
        (root / "references").mkdir(parents=True)
        shutil.copyfile(PROJECT / "references/manifest.json", root / "references/manifest.json")
        shutil.copytree(UPSTREAM, root / "references/upstream" / UPSTREAM.name)

    def test_external_manifest_authenticates_all_35_files_and_five_executables(self):
        inventory = baseline.frozen_upstream_sources()
        self.assertEqual(len(inventory), 36)
        self.assertEqual(inventory[str(PROJECT / "references/manifest.json")], baseline.UPSTREAM_MANIFEST_SHA256)
        for name, expected in baseline.UPSTREAM_MODULE_SHA256.items():
            self.assertEqual(inventory[str(UPSTREAM / (name + ".py"))], expected)
        self.assertEqual(set(baseline.SOURCE_MODULES), set(baseline.UPSTREAM_MODULE_SHA256))

    def test_known_source_is_portable_but_no_manifest_rehash_override_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copy_sources(root)
            inventory = baseline.frozen_upstream_sources(root)
            self.assertEqual(len(inventory), 36)
            path = root / "references/manifest.json"
            changed = json.loads(path.read_text(encoding="utf-8"))
            changed["files"][0]["sha256"] = "0" * 64
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "external fixed SHA"):
                baseline.frozen_upstream_sources(root)

    def test_changed_nonexecutable_source_is_rejected_by_complete_reference_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copy_sources(root)
            path = root / "references/upstream" / UPSTREAM.name / "LICENSE"
            path.write_bytes(path.read_bytes() + b"\nfixture mutation")
            with self.assertRaisesRegex(ValueError, "source bytes changed"):
                baseline.frozen_upstream_sources(root)

    def test_changed_each_original_executable_is_rejected_before_ast_parse_or_exec(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            for name in baseline.SOURCE_MODULES:
                path = source / (name + ".py")
                path.write_bytes((UPSTREAM / path.name).read_bytes() + b"\n# unchanged AST but different original bytes\n")
                with self.subTest(module=name), patch.object(baseline.ast, "parse") as parse:
                    with self.assertRaisesRegex(ValueError, "external fixed SHA"):
                        baseline._load_definitions(name, source, {}, selected_functions=set())
                    parse.assert_not_called()

    def test_unknown_custom_module_cannot_use_original_loader(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.py"
            path.write_text("raise AssertionError('must never execute')\n", encoding="utf-8")
            with patch.object(baseline.ast, "parse") as parse:
                with self.assertRaisesRegex(ValueError, "Only externally pinned"):
                    baseline._load_definitions("fixture", Path(folder), {})
                parse.assert_not_called()

    def test_pinned_original_bytes_can_be_parsed_without_running_any_phase(self):
        old = sys.modules.get("utils")
        try:
            # Empty retained definitions isolate only the pin/AST loader contract.
            module, metadata = baseline._load_definitions("utils", UPSTREAM, {}, selected_functions=set())
            self.assertEqual(metadata["sha256"], baseline.UPSTREAM_MODULE_SHA256["utils"])
            self.assertEqual(metadata["source_authentication"], "external_fixed_module_sha256_before_AST_execution")
            self.assertEqual(metadata["retained_definition_sha256"], {})
        finally:
            if old is None:
                sys.modules.pop("utils", None)
            else:
                sys.modules["utils"] = old

    def test_actual_baseline_rejects_other_source_directory_before_registration_or_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = {"model": "synthetic-no-model", "max_steps": 2, "mlesolver_max_steps": 1,
                        "papersolver_max_steps": 0, "num_papers_lit_review": 1}
            called = []
            def forbidden(*args, **kwargs):
                called.append(True)
                raise AssertionError("No transport call")
            with self.assertRaisesRegex(ValueError, "this version's separately frozen"):
                baseline.run_upstream_baseline({"objective": "source-only fixture"}, root / "output", forbidden,
                    forbidden, settings, literature=[], source_dir=root / "custom-original-copy")
            self.assertFalse((root / "output").exists())
            self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
