"""Independent arithmetic/literature/planning/coverage component attacks.

Tiny CPU computations use explicitly defined public arrays, not sampler or owner
rows. There are no provider calls. These are engineering fixtures only.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from evidence_research.report_semantics import (evaluate_predicate, prepare_semantic_review,
    adjudicate_semantic_review, validate_semantic_review, semantic_claim, run_reference)
from evidence_research.tasks import TASK_VERSION, make_spec, run_task
from transport_fixture import public_bundle, link, sha
import evidence_research.report_semantics as semantic_module

SCRATCH = None  # Independent driver supplies an isolated, durable fixture directory.


class NoncontextSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SCRATCH is None:
            raise RuntimeError("use the independent driver with an isolated fixture root")
        cls.root = Path(SCRATCH); cls.root.mkdir(parents=True, exist_ok=True)
        cls.bundle = public_bundle(TASK_VERSION)
        cls.envelope = {"reasoning_effort": "medium", "proposal_calls_per_unit": 10, "actual_cpu_executions_per_unit": 10}
        cls.runs = []
        for degree in (1, 2):
            folder = cls.root / "research/runs" / f"cpu-{degree}"
            spec = make_spec(cls.bundle["split_manifest"]["task_id"], 257, {"degree": degree, "alpha": 0.1},
                model="fixture-model", task_bundle=cls.bundle, resource_envelope=cls.envelope)
            spec["fixture_only"] = True
            result = run_task(spec, folder)
            if result["status"] != "success":
                raise AssertionError("trusted component fixture failed before semantic test: " + str(result["error"]))
            cls.runs.append({"folder": folder, "spec": spec, "result": result, "reference": run_reference(folder)})
        cls.counter = 0
        base = Path(semantic_module.__file__).resolve().parents[1]
        cls.corpus = base / "references/task_literature_v2.json"
        cls.registry_path = base / "references/source_facts_c7.json"
        cls.registry = json.loads(cls.registry_path.read_text(encoding="utf-8"))

    def new(self, text):
        type(self).counter += 1
        folder = self.root / f"claim-{self.counter:03d}"; folder.mkdir()
        report = folder / "report.txt"; report.write_text(text, encoding="utf-8")
        inventory_path = folder / "inventory.json"
        inventory = prepare_semantic_review(report, inventory_path)
        return folder, inventory_path, inventory

    def adjudicate_one(self, text, kind, outcome, *, predicate=None, args=None, context=None):
        folder, inventory_path, inventory = self.new(text)
        unit = next(item for item in inventory["units"] if item["unit_kind"] == "paragraph")
        claim = semantic_claim(unit, kind=kind, outcome=outcome, rationale="Independent registered component fixture, no research superiority.",
            predicate_id=predicate, arguments=args, nonresult_context=context)
        row = {"unit_id": unit["unit_id"], "outcome": "reviewed", "exhaustive_result_claim_mapping": True,
               "rationale": "Every original character span is bound.", "claims": [claim]}
        # Actual run evidence remains within the shared component root.
        review = adjudicate_semantic_review(inventory_path, [row], folder / "review.json",
            arm_output=self.root, reviewer_role="independent_verifier")
        validation=validate_semantic_review(folder / "review.json", arm_output=self.root,require_complete=False)
        self.assertTrue(validation["review_coverage_complete"])
        self.assertFalse(validation["semantic_report_audit_complete"])
        self.assertEqual(validation["semantic_evidence_qualification"],"component_fixture")
        with self.assertRaises(ValueError):validate_semantic_review(folder/"review.json",arm_output=self.root)
        return review,validation

    def gap_claim(self):
        metrics = self.runs[0]["result"]["metrics"]
        # Separate explicit arithmetic oracle over actual saved measured operands.
        actual = metrics["validation_mse"] - metrics["train_mse"]
        display = f"{actual:.8f}"
        return {"kind": "measured_result", "text": f"For the named verified run, validation MSE minus training MSE is {display} MSE.",
            "predicate_id": "derived_metric_arithmetic", "arguments": {"operation": "validation_minus_training",
                "run": self.runs[0]["reference"], "left_metric": "validation_mse", "right_metric": "train_mse",
                "value": float(display), "decimal_places": 8, "unit": "mse"}}

    def test_gap_valid(self):
        claim = self.gap_claim()
        proof = evaluate_predicate(claim, self.root)
        metrics = self.runs[0]["result"]["metrics"]
        self.assertEqual(proof["facts"]["derived_value"], metrics["validation_mse"] - metrics["train_mse"])
        self.assertEqual(proof["facts"]["unit"], "mse")
        self.assertIn("no additional experiment", proof["facts"]["scope"])
        self.adjudicate_one(claim["text"], "measured_result", "supported", predicate=claim["predicate_id"], args=claim["arguments"])

    def test_gap_wrong_split_sign(self):
        self.test_gap_valid()
        for change in ({"left_metric": "train_mse"}, {"operation": "training_minus_validation"},
                       {"value": self.gap_claim()["arguments"]["value"]+0.01}, {"unit": "rmse"}, {"decimal_places": 2}):
            with self.subTest(change=change):
                claim = self.gap_claim(); claim["arguments"].update(change)
                with self.assertRaises(ValueError): evaluate_predicate(claim, self.root)

    def test_gap_ratio_zero(self):
        self.test_gap_valid()
        for operation in ("relative_change", "ratio", "divide_by_zero"):
            claim = self.gap_claim(); claim["arguments"].update(operation=operation, denominator=0)
            with self.assertRaises(ValueError): evaluate_predicate(claim, self.root)

    def test_gap_generalization_cause(self):
        self.test_gap_valid()
        claim = self.gap_claim()
        for text in (claim["text"]+" This proves generalization superiority.",
                     claim["text"]+" The gap was caused by the framework.",
                     "The framework improved research performance."):
            with self.assertRaises(ValueError):
                self.adjudicate_one(text, "measured_result", "supported", predicate=claim["predicate_id"], args=claim["arguments"])

    def test_minimum_pair_subset(self):
        refs = [row["reference"] for row in self.runs]
        selected = min(self.runs, key=lambda row: row["result"]["metrics"]["validation_mse"])["reference"]
        proper = {"predicate_id": "observed_minimum", "arguments": {"runs": refs, "selected": selected}}
        self.assertEqual(evaluate_predicate(proper, self.root)["facts"]["actual_executions"], 2)
        forged = deepcopy(proper); forged["arguments"]["runs"] = [selected]
        with self.assertRaises(ValueError): evaluate_predicate(forged, self.root)

    def fact_claim(self, fact, form):
        return {"kind": "literature", "text": form["text"], "predicate_id": "source_fact_attribution",
            "arguments": {"fact_id": fact["fact_id"], "form_id": form["form_id"], "source": link(self.corpus),
                          "registry_sha256": sha(self.registry_path), "url": fact["url"]}}

    def test_literature_valid_template_both(self):
        arm_roots={arm:self.root/arm for arm in ("B","C")}
        for path in arm_roots.values():path.mkdir(exist_ok=True)
        for fact in self.registry["facts"]:
            normalized = []
            for form in fact["allowed_forms"]:
                claim = self.fact_claim(fact, form)
                proofs = [evaluate_predicate(deepcopy(claim), arm_roots[arm]) for arm in ("B", "C")]
                self.assertEqual(proofs[0], proofs[1])
                self.assertEqual(proofs[0]["facts"]["conditions"], fact["conditions"])
                self.assertEqual(proofs[0]["facts"]["polarity"], fact["polarity"])
                normalized.append({key: value for key, value in proofs[0]["facts"].items() if key != "form_id"})
                self.adjudicate_one(claim["text"], "literature", "supported", predicate=claim["predicate_id"], args=claim["arguments"])
            self.assertTrue(all(proof == normalized[0] for proof in normalized))

    def test_literature_paraphrase_extra(self):
        fact = self.registry["facts"][2]; form = fact["allowed_forms"][0]
        self.assertEqual(evaluate_predicate(self.fact_claim(fact, form), self.root)["facts"]["fact_id"], fact["fact_id"])
        base = self.fact_claim(fact, form)
        for change in ("Therefore alpha 0.1 is locally optimal.", "The task validation error was improved by ridge.",
                       "Ridge necessarily reduces estimator variance."):
            claim = deepcopy(base); claim["text"] += " " + change
            with self.assertRaises(ValueError): evaluate_predicate(claim, self.root)
        for key, value in (("url", self.registry["facts"][0]["url"]), ("fact_id", "invented-fact"),
                           ("registry_sha256", "0"*64), ("form_id", "invented-translation")):
            claim = deepcopy(base); claim["arguments"][key] = value
            with self.assertRaises(ValueError): evaluate_predicate(claim, self.root)

    def test_literature_reading_copy(self):
        fact = self.registry["facts"][0]; claim = self.fact_claim(fact, fact["allowed_forms"][0])
        for text in ("Our agent read and understood all five papers.", "에이전트는 다섯 논문을 모두 읽고 이해했다."):
            claim["text"] = text
            with self.assertRaises(ValueError): self.adjudicate_one(text, "literature", "supported", predicate=claim["predicate_id"], args=claim["arguments"])
        claim = self.fact_claim(fact, fact["allowed_forms"][0]); claim["kind"] = "measured_result"
        with self.assertRaises(ValueError): evaluate_predicate(claim, self.root)

    def test_literature_universe(self):
        fact = self.registry["facts"][0]; claim = self.fact_claim(fact, fact["allowed_forms"][0])
        for text in ("The shared five-record corpus contains three distinct records.",
                     "The supplied corpus contains three distinct sources."):
            claim["text"] = text
            with self.assertRaises(ValueError): evaluate_predicate(claim, self.root)

    def test_planning_normative_minimum(self):
        self.adjudicate_one("The procedure should choose the observed minimum.", "method", "classified_nonresult")
        with self.assertRaises(ValueError): self.adjudicate_one("The procedure achieved the minimum.", "method", "classified_nonresult")
        with self.assertRaises(ValueError): self.adjudicate_one("The procedure should choose the observed minimum, and we achieved the best result.", "method", "classified_nonresult")

    def test_planning_past_in_question(self):
        for text in ("We propose that we achieved the best result.", "We achieved the best result?", "We plan a comparison. We achieved the best result."):
            with self.assertRaises(ValueError): self.adjudicate_one(text, "proposal", "classified_nonresult")

    def test_limitation_mixed_positive(self):
        for text in ("Framework improvement is not established, but our framework improved research performance.",
                     "프레임워크 개선은 입증하지 않는다. 그러나 프레임워크가 연구 성능을 개선했다."):
            with self.assertRaises(ValueError): self.adjudicate_one(text, "limitation", "classified_nonresult")

    def test_coverage_no_digit_key(self):
        text = '{"our framework is superior": "unreviewed", "plain": "Our framework outperformed the baseline."}'
        folder, inventory_path, inventory = self.new(text)
        units = inventory["units"]
        rows = []
        for unit in units:
            claims = [] if unit["unit_kind"] == "json_structure" else [semantic_claim(unit, kind="method", outcome="classified_nonresult", rationale="Deliberate structure-laundering attack.")]
            rows.append({"unit_id": unit["unit_id"], "outcome": "reviewed", "exhaustive_result_claim_mapping": True,
                         "rationale": "Deliberate coverage attack.", "claims": claims})
        with self.assertRaises(ValueError): adjudicate_semantic_review(inventory_path, rows, folder / "bad.json", arm_output=self.root, reviewer_role="independent_verifier")
        rows = rows[:-1]
        with self.assertRaises(ValueError): adjudicate_semantic_review(inventory_path, rows, folder / "missing.json", arm_output=self.root, reviewer_role="independent_verifier")
