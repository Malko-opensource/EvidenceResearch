"""Budget bookkeeping fixtures; no actual model or performance claim."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_research.model import PreregisteredResourcesExhausted
from evidence_research.store import sha256_file
from evidence_research.study import register_pilot, run_pilot, load
from tests.test_study import settings


class RegisteredBudgetFailureTests(unittest.TestCase):
    def test_budget_failure_keeps_both_denominators_and_never_looks_external(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            register_pilot(settings(), root)
            with patch("evidence_research.study._score_arm", side_effect=PreregisteredResourcesExhausted("fixture declared allowance consumed")) as scorer:
                result = run_pilot(root)
            self.assertEqual(scorer.call_count, 2)
            self.assertFalse(result["adopted"])
            self.assertFalse(result["design_inputs_complete"])
            for arm in ("B", "C"):
                row = result["units"][0]["arms"][arm]
                self.assertEqual(row["status"], "registered_resources_exhausted")
                score = load(root / "units" / "control-flow-fixture" / arm / "owner-score.json")
                self.assertFalse(score["task_success"])
                self.assertIsNone(score["provider_calls"])
                self.assertIn("Goal remains active", score["resource_scope"])
                self.assertFalse((root / "units" / "control-flow-fixture" / arm / "owner-attempts").exists())
            scores = list(root.rglob("owner-score.json"))
            before = {str(path): sha256_file(path) for path in scores}
            with patch("evidence_research.study._score_arm") as scorer:
                resumed = run_pilot(root)
            scorer.assert_not_called()
            self.assertFalse(resumed["adopted"])
            self.assertEqual(before, {str(path): sha256_file(path) for path in scores})


if __name__ == "__main__":
    unittest.main()
