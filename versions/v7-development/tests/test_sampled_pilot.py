"""Owner data separation and matched sampling contracts, not research outcomes."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_research.evaluation import create_final_suite, register_protocol, _validate_final_suite_draws
from evidence_research.study import (create_sampled_pilot_config, register_pilot,
                                     run_pilot, load, main)
from evidence_research.tasks import SAMPLED_TASK_DISTRIBUTION, value_hash, task_data
from evidence_research.tasks import write_json, sha256_file
from tests.test_study import settings, fake_score


class SampledDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def config(self, owner_seed=12345, precision=1):
        base = settings(); base.pop("units")
        path = self.root / f"owner-config-{owner_seed}.json"
        receipt = create_sampled_pilot_config(base, path, owner_seed=owner_seed,
                                              variance_relative_se=precision)
        return load(path), receipt

    def test_sampler_plan_and_final_law_match_without_reusing_definitions(self):
        config, receipt = self.config(12345, precision=0.5)
        self.assertEqual(receipt["n_pairs"], 9)
        self.assertEqual(config["pilot_variance_plan"]["formula"], "ceil(2/variance_relative_se**2)+1")
        development = [u["definition_sha256"] for u in config["units"]]
        final = create_final_suite(self.root / "final", n_pairs=3, owner_seed=54321,
                                   excluded_development_definition_hashes=development)
        self.assertEqual(final["sampling_distribution"], SAMPLED_TASK_DISTRIBUTION)
        self.assertEqual(final["sampling_distribution_sha256"], config["pilot_task_distribution_sha256"])
        self.assertTrue(final["development_exclusion_declared"])
        private = load(final["private_file"])
        self.assertFalse(set(development) & {u["definition_sha256"] for u in private["units"]})
        self.assertNotIn("owner_sampling_seed", receipt)
        self.assertNotIn("units", receipt)

    def test_final_development_definition_reuse_is_rejected_before_writing(self):
        config, _ = self.config()
        destination = self.root / "reused-final"
        with self.assertRaisesRegex(ValueError, "already development material"):
            create_final_suite(destination, n_pairs=3, owner_seed=12345,
                excluded_development_definition_hashes=[u["definition_sha256"] for u in config["units"]])
        self.assertFalse(destination.exists())

    def test_sampled_proposer_inputs_exclude_private_definitions_and_test_rows_and_resume(self):
        config, _ = self.config()
        study = self.root / "study"
        register_pilot(config, study)
        received = []
        def callback(payload, directory):
            received.append(payload)
            from evidence_research.store import atomic_json
            atomic_json(directory / "arm-response.json", {"fixture": True})
        with patch("evidence_research.study._score_arm", side_effect=fake_score), patch("evidence_research.study._validate_saved_score"):
            run_pilot(study, baseline=callback, improved=callback)
            run_pilot(study, baseline=callback, improved=callback)
        self.assertEqual(len(received), 2 * len(config["units"]))
        forbidden = {"test", "coefficients", "owner_sampled_definition", "owner_sampling_seed", "owner_split_seeds", "noise", "n_train"}
        def check(value):
            if isinstance(value, dict):
                # Split manifest exposes hashes/counts for all splits, not rows.
                for key, item in value.items():
                    if key == "splits":
                        self.assertEqual(set(item["test"]), {"count", "sha256", "ids_sha256"})
                        continue
                    self.assertNotIn(key, forbidden)
                    check(item)
            elif isinstance(value, list):
                for item in value: check(item)
        for payload in received: check(payload)
        for i in range(0, len(received), 2):
            self.assertEqual(received[i]["public_task"], received[i + 1]["public_task"])

    def test_invalid_or_relabelled_sampled_definition_leaves_no_registration(self):
        config, _ = self.config()
        variants = []
        changed = deepcopy(config); changed["pilot_task_distribution"]["degree_choices"] = [1]; variants.append(changed)
        changed = deepcopy(config); changed["units"][0]["owner_sampled_definition"]["coefficients"][0] = float("nan"); variants.append(changed)
        changed = deepcopy(config); changed["units"][0]["definition_sha256"] = "0" * 64; variants.append(changed)
        changed = deepcopy(config); changed["units"][0]["task_id"] = "dev-linear"; variants.append(changed)
        changed = deepcopy(config); changed["units"][0].pop("owner_sampled_definition"); variants.append(changed)
        for i, altered in enumerate(variants):
            destination = self.root / f"invalid-{i}"
            with self.subTest(i=i), self.assertRaises(ValueError):
                register_pilot(altered, destination)
            self.assertFalse(destination.exists())

    def test_owner_config_is_immutable_and_precision_input_is_explicit(self):
        config, _ = self.config()
        path = self.root / "owner-config-12345.json"
        base = settings(); base.pop("units")
        with self.assertRaises(FileExistsError):
            create_sampled_pilot_config(base, path, owner_seed=999)
        for precision in (0, -1, True, float("nan"), 1.1):
            with self.subTest(precision=precision), self.assertRaises(ValueError):
                create_sampled_pilot_config(base, self.root / "invalid-owner.json", owner_seed=1,
                                            variance_relative_se=precision)

    def test_cli_registration_does_not_print_owner_seed_or_answer_definitions(self):
        config, receipt = self.config()
        stream = io.StringIO()
        with redirect_stdout(stream):
            exit_code = main(["pilot-register", "--config", receipt["path"],
                              "--output", str(self.root / "cli-study")])
        self.assertEqual(exit_code, 0)
        summary = json.loads(stream.getvalue())
        self.assertFalse(summary["owner_definition_values_or_seed_printed"])
        self.assertNotIn("config", summary)
        self.assertNotIn("coefficients", stream.getvalue())
        self.assertNotIn("owner_sampling_seed", stream.getvalue())
        registered = load(summary["registration_path"])
        self.assertEqual(registered["config"], config)

    def test_new_study_requires_explicit_literature_policy_before_creating_evidence(self):
        config = settings(); config["resource_envelope"].pop("literature_protocol")
        destination = self.root / "implicit-policy"
        with self.assertRaisesRegex(ValueError, "explicit"):
            register_pilot(config, destination)
        self.assertFalse(destination.exists())

    def test_within_law_altered_and_rehashed_definition_is_not_an_actual_sample(self):
        config, _ = self.config()
        altered = deepcopy(config)
        definition = altered["units"][0]["owner_sampled_definition"]
        definition["coefficients"][0] += 0.001
        altered["units"][0]["definition_sha256"] = value_hash(definition)
        destination = self.root / "rehash-draw"
        with self.assertRaisesRegex(ValueError, "draw sequence"):
            register_pilot(altered, destination)
        self.assertFalse(destination.exists())

    def test_private_test_rng_changes_do_not_follow_the_public_seed_or_other_splits(self):
        config, _ = self.config()
        unit = config["units"][0]
        seeds = deepcopy(unit["owner_split_seeds"])
        original = task_data(unit["task_id"], unit["seed"], private_definition=unit["owner_sampled_definition"],
                             private_split_seeds=seeds)
        seeds["test"] ^= 1
        changed = task_data(unit["task_id"], unit["seed"], private_definition=unit["owner_sampled_definition"],
                            private_split_seeds=seeds)
        self.assertEqual(original["train"], changed["train"])
        self.assertEqual(original["validation"], changed["validation"])
        self.assertNotEqual(original["test"], changed["test"])
        public_seed_replay = task_data(unit["task_id"], unit["seed"], private_definition=unit["owner_sampled_definition"])
        self.assertNotEqual(original["test"], public_seed_replay["test"])

    def test_final_draw_receipt_rejects_within_law_rehashed_owner_definition(self):
        suite = create_final_suite(self.root / "draw-final", n_pairs=3, owner_seed=54321,
                                    excluded_development_definition_hashes=[])
        private = load(suite["private_file"])
        _validate_final_suite_draws(private)
        altered = deepcopy(private)
        altered["units"][0]["owner_sampled_definition"]["coefficients"][0] += 0.001
        altered["units"][0]["definition_sha256"] = value_hash(altered["units"][0]["owner_sampled_definition"])
        with self.assertRaisesRegex(ValueError, "owner-side sampling draw"):
            _validate_final_suite_draws(altered)

    def test_rehashed_truncated_final_inventory_cannot_be_preregistered(self):
        suite = create_final_suite(self.root / "truncated-final", n_pairs=3, owner_seed=54321,
                                    excluded_development_definition_hashes=[])
        private = load(suite["private_file"])
        private["units"].pop()
        with self.assertRaisesRegex(ValueError, "draw count"):
            _validate_final_suite_draws(private)
        # Changing the local checksum is insufficient to legitimize fewer units.
        write_json(Path(suite["private_file"]), private)
        suite["private_sha256"] = sha256_file(Path(suite["private_file"]))
        destination = self.root / "truncated-protocol.json"
        config = settings()
        config["resource_envelope"]["actual_cpu_executions_per_unit"] = 3
        with self.assertRaisesRegex(ValueError, "inventory/count"):
            register_protocol(destination, design={"n_pairs": 3}, suite=suite,
                model_id=config["model_id"], baseline_provenance=config["baseline_provenance"],
                resource_envelope=config["resource_envelope"])
        self.assertFalse(destination.exists())

    def test_rehashed_reordered_final_inventory_cannot_be_preregistered(self):
        suite = create_final_suite(self.root / "reordered-final", n_pairs=3, owner_seed=54321,
                                    excluded_development_definition_hashes=[])
        private = load(suite["private_file"])
        private["units"][0], private["units"][1] = private["units"][1], private["units"][0]
        write_json(Path(suite["private_file"]), private)
        suite["private_sha256"] = sha256_file(Path(suite["private_file"]))
        destination = self.root / "reordered-protocol.json"
        config = settings()
        config["resource_envelope"]["actual_cpu_executions_per_unit"] = 3
        with self.assertRaisesRegex(ValueError, "inventory/count"):
            register_protocol(destination, design={"n_pairs": 3}, suite=suite,
                model_id=config["model_id"], baseline_provenance=config["baseline_provenance"],
                resource_envelope=config["resource_envelope"])
        self.assertFalse(destination.exists())

    def test_unfinished_sampled_pilot_cannot_certify_final_planning(self):
        config, _ = self.config()
        config["resource_envelope"]["actual_cpu_executions_per_unit"] = 3
        study = self.root / "unfinished-pilot"
        register_pilot(config, study)
        suite = create_final_suite(self.root / "unfinished-final", n_pairs=3, owner_seed=54321,
            excluded_development_definition_hashes=[u["definition_sha256"] for u in config["units"]])
        destination = self.root / "final-protocol.json"
        with self.assertRaisesRegex(ValueError, "every completed independently scored"):
            register_protocol(destination, design={"n_pairs": 3, "pilot_n": 3}, suite=suite,
                model_id=config["model_id"], baseline_provenance=config["baseline_provenance"],
                resource_envelope=config["resource_envelope"],
                development_pilot_registration=study / "pilot-registration.json")
        self.assertFalse(destination.exists())

    def test_old_fixed_task_pilot_cannot_supply_new_distribution_variance(self):
        config = settings(); config["resource_envelope"]["actual_cpu_executions_per_unit"] = 3
        study = self.root / "fixed-pilot"
        register_pilot(config, study)
        suite = create_final_suite(self.root / "fixed-final", n_pairs=3, owner_seed=54321,
                                    excluded_development_definition_hashes=[])
        destination = self.root / "fixed-protocol.json"
        with self.assertRaisesRegex(ValueError, "different task sampling law"):
            register_protocol(destination, design={"n_pairs": 3, "pilot_n": 1}, suite=suite,
                model_id=config["model_id"], baseline_provenance=config["baseline_provenance"],
                resource_envelope=config["resource_envelope"],
                development_pilot_registration=study / "pilot-registration.json")
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
