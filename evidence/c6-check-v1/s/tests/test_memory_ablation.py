"""Real CPU calibration and decision-schema checks; no actual model comparison."""
from pathlib import Path
import tempfile
import unittest

from scripts import memory_ablation as ablation
from evidence_research import EvidenceError
from evidence_research.store import atomic_json


def config():
    return {"kind": "memory_exposure_development_pilot", "model_id": "cpu-only-test-model-label",
        "resource_envelope": {"proposal_calls_per_unit": 1, "actual_cpu_executions_per_unit": 3,
                              "reasoning_effort": "medium", "device": "cpu", "network": False},
        "calibration_configs": [{"degree": 2, "alpha": 0}, {"degree": 8, "alpha": 100}],
        "sample_design_inputs": {"meaningful_gain": 0.10, "precision_halfwidth": 0.05,
                                 "power": 0.80, "variance_relative_se": 0.5},
        "units": [{"unit_id": "cpu-only-test-unit", "task_id": "dev-quadratic", "seed": 7}]}


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "diagnostic"

    def tearDown(self):
        self.temp.cleanup()

    def test_registration_fixes_units_and_never_invents_model_observations(self):
        registered = ablation.register(config(), self.root)
        self.assertFalse((self.root / "units").exists())
        self.assertIn("host-selected", registered["calibration_selection"])
        changed = config()
        changed["resource_envelope"]["reasoning_effort"] = "high"
        with self.assertRaises(EvidenceError):
            ablation.register(changed, self.root)

    def test_calibration_is_actual_equal_and_resume_does_not_repeat_cpu(self):
        ablation.register(config(), self.root)
        prepared = ablation.prepare(self.root)
        self.assertEqual(prepared["model_calls"], 0)
        ablation.prepare(self.root)
        outcomes = []
        for arm in ("ON", "OFF"):
            directory = ablation._directory(self.root, "cpu-only-test-unit", arm)
            store = ablation._engine(directory).store
            self.assertTrue(store.verify_integrity()["valid"])
            self.assertEqual(len(store.list_runs()), 2)
            outcomes.append([run["outcome"] for run in store.list_runs()])
            with store._connect() as db:
                rows = list(db.execute("SELECT payload FROM events WHERE phase='EXECUTE'"))
            actual_starts = sum('"state":"running"' in row[0] for row in rows)
            self.assertEqual(actual_starts, 2)
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertIn("failure", outcomes[0])

    def test_only_memory_payload_differs_and_stop_is_a_planning_decision(self):
        registration = ablation.register(config(), self.root)
        ablation.prepare(self.root)
        public = ablation.load(registration["units"][0]["public_path"])
        stores = [ablation._engine(ablation._directory(self.root, "cpu-only-test-unit", arm)).store for arm in ("ON", "OFF")]
        on, off = [ablation.request_payload(public, store, expose) for store, expose in zip(stores, (True, False))]
        self.assertEqual({k: v for k, v in on.items() if k != "verified_memory"}, {k: v for k, v in off.items() if k != "verified_memory"})
        self.assertEqual(off["verified_memory"], [])
        self.assertEqual(len(on["verified_memory"]), 2)
        self.assertNotIn("best", on)
        self.assertNotIn("proposal_feedback", on)
        action = ablation._action({"candidate": None, "stop": {"kind": "no_justified_experiment",
            "reason": "Explicit planning rationale; no quality measurement claimed", "evidence_run_ids": []}}, stores[0])
        self.assertEqual(action["kind"], "stop")
        self.assertEqual(action["rationale_kind"], "proposal")
        with self.assertRaises(ValueError):
            ablation._action({"candidate": None, "stop": {"kind": "goal_fulfilled", "reason": "LLM says perfect"}}, stores[0])

    def test_fixture_model_cannot_fill_actual_paired_observations(self):
        ablation.register(config(), self.root)
        ablation.prepare(self.root)
        complete_calls = []
        class Fixture:
            execution_kind = "simulation_fixture"
            def __init__(self, **kwargs):
                pass
            def complete(self, *args, **kwargs):
                complete_calls.append(True)
        summary = ablation.collect(self.root, provider_factory=Fixture)
        self.assertEqual(complete_calls, [])
        self.assertEqual(summary["paired_duplicate_deltas"], [])
        self.assertEqual(summary["registered_paired_decision_opportunities"], 1)
        self.assertFalse(summary["all_pairs_complete"])
        self.assertFalse(summary["adopted"])
        with self.assertRaises(EvidenceError):
            ablation.design(self.root, self.root / "must-not-create.json")
        self.assertFalse((self.root / "must-not-create.json").exists())


if __name__ == "__main__":
    unittest.main()
