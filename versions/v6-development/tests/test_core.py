from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing

from evidence_research import Engine, EvidenceError, Store, fingerprint
from evidence_research.selection import rank_candidates
from evidence_research.store import atomic_json


def spec(**changes):
    value = {"hypothesis": "ridge regularization", "task_id": "core-test", "task_version": 1,
             "seed": 42, "config": {"alpha": 1.0}, "metric": "loss",
             "criterion": {"direction": "min", "baseline_value": 2.0}, "model": "test-model",
             "resource_envelope": {"max_model_calls": 0}, "command": "trusted test runner",
             "implementation_sha256": "a" * 64, "split_manifest_sha256": "b" * 64,
             "evaluator_sha256": "c" * 64}
    value.update(changes)
    return value


def runner(config, root):
    artifact = root / "measurement.json"
    atomic_json(artifact, {"loss": 1.0, "seed": config["seed"]})
    return {"status": "success", "metrics": {"loss": 1.0}, "artifacts": [str(artifact)],
            "claims": [{"kind": "measured", "metric": "loss", "value": 1.0}]}


def verifier(config, result, root):
    return {"valid": True, "status": "verified", "metrics": {"loss": 1.0},
            "comparison_valid": True,
            "reasons": ["Independently recomputed fixture measurement"]}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.store.init_goal({"objective": "Verify persistence", "memory_query": "core-test"})

    def tearDown(self):
        self.temp.cleanup()

    def test_full_loop_resume_and_best(self):
        calls = []
        def counted(spec, directory):
            calls.append(spec["seed"])
            return runner(spec, directory)
        engine = Engine(self.root, counted, verifier)
        result = engine.step(spec())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(self.store.state()["best"]), 1)
        resumed = engine.step(spec())
        self.assertTrue(resumed["resumed_without_execution"])
        self.assertEqual(calls, [42])
        self.assertTrue(Store(self.root).verify_integrity()["valid"])
        self.assertEqual(engine.resume(), [])
        memory = self.store.search("ridge", {"task_id": "core-test"})
        self.assertEqual(len(memory), 1)
        self.assertTrue(memory[0]["usable_as_verified_evidence"])
        self.assertIn("manifest", memory[0]["original_evidence"])
        with closing(sqlite3.connect(self.store.db_path)) as db:
            phases = {row[0] for row in db.execute("SELECT phase FROM events")}
        self.assertTrue(set(("OBSERVE", "RETRIEVE", "PROPOSE", "REGISTER", "IMPLEMENT", "EXECUTE", "VERIFY", "DECIDE", "UPDATE_MEMORY")) <= phases)

    def test_completed_artifact_tamper_fails_closed(self):
        engine = Engine(self.root, runner, verifier)
        run = engine.step(spec())
        (Path(run["run_dir"]) / "measurement.json").write_text("{}", encoding="utf-8")
        self.assertFalse(self.store.verify_integrity()["valid"])
        self.assertFalse(self.store.search("")[0]["usable_as_verified_evidence"])
        with self.assertRaises(EvidenceError):
            engine.step(spec(seed=43))

    def test_changed_prose_does_not_repeat_execution(self):
        calls = []
        def counted(config, directory):
            calls.append(config)
            return runner(config, directory)
        engine = Engine(self.root, counted, verifier)
        original = engine.step(spec())
        renamed = engine.step(spec(hypothesis="Renamed same experiment", selection_reason="new prose"))
        self.assertEqual(original["run_id"], renamed["run_id"])
        self.assertEqual(len(calls), 1)

    def test_unverified_baseline_number_never_adopts(self):
        engine = Engine(self.root, runner, lambda *_: {
            "valid": True, "status": "verified", "metrics": {"loss": 1.0}})
        run = engine.step(spec())
        self.assertEqual(run["outcome"], "inconclusive")
        self.assertEqual(self.store.state()["best"], {})

    def test_verified_task_failure_is_searchable(self):
        run = Engine(self.root, runner, verifier).step(spec(criterion={"direction": "min", "threshold": 0.1}))
        self.assertEqual(run["result"]["status"], "success")
        self.assertEqual(run["outcome"], "failure")
        self.assertEqual(self.store.search("ridge")[0]["outcome"], "failure")

    def test_forged_measured_claim_rejected(self):
        def liar(config, directory):
            result = runner(config, directory)
            result["claims"][0]["value"] = 0.0
            return result
        with self.assertRaises(EvidenceError):
            Engine(self.root, liar, verifier).step(spec())

    def test_best_metadata_tamper_detected(self):
        Engine(self.root, runner, verifier).step(spec())
        with closing(sqlite3.connect(self.store.db_path)) as db:
            db.execute("UPDATE metadata SET value=replace(value,'1.0','0.0') WHERE key='best'")
            db.commit()
        self.assertFalse(self.store.verify_integrity()["valid"])

    def test_semantically_equal_registration_byte_tamper_detected(self):
        run = Engine(self.root, runner, verifier).step(spec())
        path = Path(run["run_dir"]) / "registration.json"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertFalse(self.store.verify_integrity()["valid"])

    def test_unknown_execution_never_reruns(self):
        run = self.store.register(spec())
        self.store.mark_running(run["run_id"])
        engine = Engine(self.root, lambda *_: self.fail("Must not rerun"), verifier)
        recovered = engine.resume()[0]
        self.assertEqual(recovered["blocked"], "unknown_execution")
        self.assertEqual(self.store.get_run(run["run_id"])["status"], "unknown_execution")

    def test_durable_receipt_reconciles_without_runner(self):
        run = self.store.register(spec())
        self.store.mark_running(run["run_id"])
        result = runner(run["spec"], Path(run["run_dir"]))
        atomic_json(Path(run["run_dir"]) / "execution.json", {
            "run_id": run["run_id"], "spec_fingerprint": run["fingerprint"], "result": result})
        engine = Engine(self.root, lambda *_: self.fail("Must not rerun"), verifier)
        self.assertEqual(engine.resume()[0]["status"], "completed")

    def test_rejected_measurement_never_updates_best(self):
        engine = Engine(self.root, runner, lambda *_: {
            "valid": False, "status": "rejected", "metrics": {"loss": 0.0}, "reasons": ["leakage"]})
        run = engine.step(spec())
        self.assertEqual(run["outcome"], "inconclusive")
        self.assertEqual(self.store.state()["best"], {})

    def test_failure_search_and_changed_retry(self):
        def failing(config, root):
            raise ValueError("condition failed")
        def verify_failure(config, result, root):
            return {"valid": True, "status": "verified", "metrics": {}, "reasons": ["error log exists"]}
        run = Engine(self.root, failing, verify_failure).step(spec())
        self.assertEqual(self.store.search("condition failed")[0]["outcome"], "failure")
        unchanged = self.store.register(spec(retry_of=run["run_id"], retry_reason="try again"))
        self.assertFalse(unchanged["created"])
        self.assertEqual(unchanged["run_id"], run["run_id"])
        retry = spec(config={"alpha": 0.1}, retry_of=run["run_id"], retry_reason="lower regularization")
        self.assertTrue(self.store.register(retry)["created"])

    def test_sql_immutability(self):
        run = Engine(self.root, runner, verifier).step(spec())
        with closing(sqlite3.connect(self.store.db_path)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE runs SET result='{}' WHERE run_id=?", (run["run_id"],))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM events")

    def test_claim_and_registration_validation(self):
        with self.assertRaises(ValueError):
            self.store.register({"hypothesis": "missing provenance"})
        run = self.store.register(spec())
        self.store.mark_running(run["run_id"])
        with self.assertRaises(ValueError):
            self.store.record_execution(run["run_id"], {
                "status": "success", "claims": [{"kind": "fact", "text": "trust me"}]})

    def test_selection_priorities_are_not_measurements(self):
        memory = [{"run_id": "failed", "outcome": "failure", "verification_status": "verified",
                   "hypothesis": "failed approach"}]
        ranked = rank_candidates([{"spec": {"hypothesis": "failed approach"}},
                                  {"spec": {"hypothesis": "new approach"}}], memory)
        self.assertEqual(ranked[0]["spec"]["hypothesis"], "new approach")
        self.assertEqual(ranked[0]["selection"]["score_kind"], "planning_judgment")

    def test_renamed_failed_config_is_penalized(self):
        memory = [{"run_id": "failed", "outcome": "failure", "verification_status": "verified",
            "hypothesis": "old name", "applicability": {"task_id": "core-test", "config": {"alpha": 1.0}, "model": "test-model"}}]
        ranked = rank_candidates([{"spec": spec(hypothesis="renamed")},
                                  {"spec": spec(config={"alpha": 0.2})}], memory)
        self.assertEqual(ranked[0]["spec"]["config"], {"alpha": 0.2})

    def test_proposer_list_avoids_completed_configuration(self):
        engine = Engine(self.root, runner, verifier)
        engine.step(spec())
        engine.proposer = lambda _: [{"spec": spec(hypothesis="renamed")},
                                    {"spec": spec(seed=43)}]
        chosen = engine.step()
        self.assertEqual(chosen["spec"]["seed"], 43)


if __name__ == "__main__":
    unittest.main()
