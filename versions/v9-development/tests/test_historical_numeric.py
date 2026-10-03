"""Historical numeric engineering checks; no actual model, fit or study.

Synthetic raw tapes deliberately retain their provenance. Their exact prefix
can be normalized only by the explicit component API and cannot approve an
actual numeric review. These are representation tests, not research results.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.evaluation import (
    HISTORICAL_NUMERIC_SCHEMA_VERSION, _historical_numeric_group_coverage,
    _validate_numeric_review, adjudicate_numeric_review,
    evaluate_fixture_historical_numeric, prepare_numeric_review,
    recompute_historical_numeric)
from evidence_research.report_semantics import semantic_units
from evidence_research.tasks import sha256_file
from tests.test_context_boundaries import TapeFixture


class HistoricalNumericTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c9-hnum-")
        self.base = Path(self.temp.name).resolve()
        self.number = 0

    def tearDown(self):
        self.temp.cleanup()

    def tape(self, arm="C", *, prior_usage=None, failed=False, future=False, logical=True, cpu=False):
        root = self.base / f"arm{self.number}"; self.number += 1
        fixture = TapeFixture(root, arm)
        fixture.model(usage=prior_usage)
        if cpu:
            fixture.cpu()  # Explicit synthetic CPU receipt; run_task/fit are never called.
        if failed:
            fixture.model(failed=True)
        boundary, _, _ = fixture.model(logical=logical)
        if future:
            fixture.model(usage={"input_tokens":999, "output_tokens":999})
        return fixture, boundary

    def review_inputs(self, fixture, boundary, text=None, *, fmt="text"):
        sentence = text or "Before this proposal, measured resources were 10 input tokens, 3 output tokens, and 1.250000000000 provider wall seconds."
        if fmt == "json":
            content = json.dumps({"historical_resource_statement":sentence}, ensure_ascii=False, indent=2)
        elif fmt == "fenced":
            content = "Source-bound resources follow.\n\n```json\n" + json.dumps({"historical_resource_statement":sentence}, ensure_ascii=False, indent=2) + "\n```\n"
        else:
            content = sentence
        report = fixture.root/f"report-{self.number}.txt"
        report.write_text(content, encoding="utf-8")
        path = fixture.root/f"inventory-{self.number}.json"
        inventory = prepare_numeric_review(report,path)
        unit = next(unit for unit in semantic_units(content,inventory["report_sha256"])
                    if unit["unit_kind"] in {"paragraph","json_string"} and unit["decoded_text"] == sentence)
        from evidence_research.report_semantics import parse_temporal_resource_list
        parsed = parse_temporal_resource_list(sentence)
        measures = list(parsed["quantities"]) if parsed else ["input_tokens"] * len(inventory["items"])
        values = {"input_tokens":10,"output_tokens":3,"wall_seconds":1.25,
                  "actual_cpu_executions":0,"cpu_execution_seconds":0.0,"completed_provider_calls":1}
        judgments=[]
        for item, measure in zip(inventory["items"], measures):
            judgments.append({"claim_id":item["claim_id"],"kind":"measured_historical_resource",
                "rationale":"Explicit source-bound engineering prefix, never actual report approval.",
                "historical_context":{"schema_version":HISTORICAL_NUMERIC_SCHEMA_VERSION,
                    "arm_output":str(fixture.root),"boundary":deepcopy(boundary),"scope":"historical_pre_request",
                    "unit_id":unit["unit_id"],"measure":measure,"value":values[measure]}})
        return path, inventory, judgments

    def check_fixture(self,path,judgment):
        proof=evaluate_fixture_historical_numeric(path,judgment)
        self.assertEqual(proof["evidence_class"],"synthetic_fixture")
        self.assertEqual(proof["evaluation_scope"],"synthetic_engineering_fixture")
        self.assertFalse(proof["adoption_eligible"])
        return proof

    def test_same_b_c_original_prefix_and_every_token_have_nonactual_fixture_proof(self):
        observed=[]
        for arm in ("B","C"):
            f,b=self.tape(arm,future=True)
            path,inventory,judgments=self.review_inputs(f,b)
            _historical_numeric_group_coverage(inventory,judgments)
            proofs=[self.check_fixture(path,j) for j in judgments]
            self.assertEqual(len(proofs[0]["quantity_tokens"]),3)
            observed.append([proof["predicate_result"]["facts"]["value"] for proof in proofs])
            self.assertEqual(observed[-1],[10,3,1.25])
        self.assertEqual(observed[0],observed[1])

    def test_plain_json_and_fenced_json_use_exact_original_unit_and_tokens(self):
        for fmt in ("text","json","fenced"):
            with self.subTest(fmt=fmt):
                f,b=self.tape();path,inventory,js=self.review_inputs(f,b,fmt=fmt)
                _historical_numeric_group_coverage(inventory,js)
                proof=self.check_fixture(path,js[0])
                self.assertEqual(proof["unit"]["unit_kind"],"paragraph" if fmt=="text" else "json_string")
                self.assertEqual(proof["selected_token"]["claim_id"],inventory["items"][0]["claim_id"])

    def test_all_tokens_must_be_classified_in_same_complete_temporal_unit(self):
        f,b=self.tape();path,inventory,js=self.review_inputs(f,b)
        with self.assertRaises(ValueError):_historical_numeric_group_coverage(inventory,js[:1])
        changed=deepcopy(js);changed[1]["kind"]="method"
        with self.assertRaises(ValueError):_historical_numeric_group_coverage(inventory,changed)
        changed=deepcopy(js);changed[1]["historical_context"]["boundary"]["sha256"]="0"*64
        with self.assertRaises(ValueError):_historical_numeric_group_coverage(inventory,changed)
        changed=deepcopy(js);changed[0]["historical_context"]["measure"]="output_tokens"
        with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,changed[0])

    def test_correct_selected_number_cannot_hide_wrong_other_quantity(self):
        f,b=self.tape();path,_,js=self.review_inputs(f,b,"Before this proposal, measured resources were 10 input tokens and 99 output tokens.")
        with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,js[0])

    def test_target_and_future_totals_are_not_the_original_prefix(self):
        f,b=self.tape(future=True);path,_,js=self.review_inputs(f,b)
        self.check_fixture(path,js[0])
        bad=deepcopy(js[0]);bad["historical_context"]["value"]=1019
        with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,bad)

    def test_unknown_failed_usage_never_uses_zero_or_completed_lower_bound(self):
        f,b=self.tape(failed=True)
        for text in ("Before this request, measured provider input usage was 0 tokens.",
                     "Before this request, measured provider input usage was 10 tokens."):
            self.number+=1;path,_,js=self.review_inputs(f,b,text)
            js[0]["historical_context"]["value"]=0 if " 0 " in text else 10
            with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,js[0])
        self.number+=1;path,_,js=self.review_inputs(f,b,"Before this request, measured resources were 2.500000000000 provider wall seconds.")
        js[0]["historical_context"]["value"]=2.5
        self.check_fixture(path,js[0])

    def test_exact_zero_counts_and_synthetic_cpu_counts_are_bound_separately(self):
        for cpu in (False,True):
            f,b=self.tape(cpu=cpu)
            count=1 if cpu else 0;elapsed=0.25 if cpu else 0
            text=f"Before this proposal, measured resources were {count} actual CPU executions and {elapsed:.12f} CPU seconds."
            path,_,js=self.review_inputs(f,b,text)
            js[0]["historical_context"]["value"]=count;js[1]["historical_context"]["value"]=elapsed
            for judgment in js:self.check_fixture(path,judgment)

    def test_scope_laundering_compound_forecast_final_and_unsupported_precision_reject(self):
        cases=("Provider input usage was 10 tokens.",
            "This document has a historical appendix. Provider input usage was 10 tokens.",
            "Before this proposal, measured input usage was 10 tokens; final usage was 10 tokens.",
            "Before this proposal, measured resources were 10 input tokens and the next experiment will consume 3 tokens.",
            "Before this proposal, measured resources were 1.2500000000000 provider wall seconds.",
            "Before this proposal, measured resources were -1 CPU executions.",
            "Before this proposal, measured resources were 0.5 CPU executions.")
        for text in cases:
            with self.subTest(text=text):
                f,b=self.tape();path,_,js=self.review_inputs(f,b,text)
                with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,js[0])

    def test_rounding_does_not_change_original_comparison_value(self):
        f,b=self.tape()
        path,_,js=self.review_inputs(f,b,"Before this proposal, measured resources were 1.250000000001 provider wall seconds.")
        proof=self.check_fixture(path,js[0]);self.assertEqual(proof["predicate_result"]["facts"]["value"],1.25)
        self.number+=1;path,_,js=self.review_inputs(f,b,"Before this proposal, measured resources were 1.250000000003 provider wall seconds.")
        with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,js[0])

    def test_bool_null_nonfinite_and_caller_fixture_flags_cannot_override_contract(self):
        f,b=self.tape();path,_,js=self.review_inputs(f,b)
        for value in (True,None,float("nan"),float("inf")):
            j=deepcopy(js[0]);j["historical_context"]["value"]=value
            with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,j)
        for key,value in (("fixture_only",False),("evaluation_scope","actual"),("scope","final")):
            j=deepcopy(js[0]);j["historical_context"][key]=value
            with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,j)

    def test_original_inventory_and_report_hash_cannot_be_replaced_or_shortened(self):
        f,b=self.tape();path,inventory,js=self.review_inputs(f,b)
        changed=deepcopy(inventory);changed["items"]=changed["items"][:1]
        path.write_text(json.dumps(changed),encoding="utf-8")
        with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,js[0])
        path.write_text(json.dumps(inventory),encoding="utf-8")
        Path(inventory["report_path"]).write_text("Before this proposal, measured input usage was 10 tokens.",encoding="utf-8")
        with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,js[0])

    def test_missing_logical_or_orphan_original_request_is_not_a_fixture_positive(self):
        f,b=self.tape(logical=False);path,_,js=self.review_inputs(f,b)
        with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,js[0])
        f,b=self.tape();path,_,js=self.review_inputs(f,b)
        orphan=f.root/"model/improved-9999";orphan.mkdir();(orphan/"request.json").write_text("{}",encoding="utf-8")
        with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,js[0])

    def test_consistently_hashed_raw_guard_and_effort_substitution_fail_closed(self):
        for kwargs in ({"full_guard":False},{"cli_effort":"high"}):
            f,b=self.tape()
            f.model(**kwargs)
            path,_,js=self.review_inputs(f,b)
            with self.assertRaises(ValueError):evaluate_fixture_historical_numeric(path,js[0])

    def test_production_recompute_and_adjudication_cannot_promote_fixture_positive(self):
        f,b=self.tape();path,_,js=self.review_inputs(f,b)
        self.check_fixture(path,js[0])
        with self.assertRaises(ValueError):recompute_historical_numeric(path,js[0])
        output=f.root/"actual-review.json"
        with self.assertRaises(ValueError):adjudicate_numeric_review(path,js,output,reviewer_role="independent_verifier")
        self.assertFalse(output.exists())
        with self.assertRaises(TypeError):recompute_historical_numeric(path,js[0],component_fixture=True)

    def test_rehashed_caller_actual_labels_still_fail_saved_review_recomputation(self):
        f,b=self.tape();path,inventory,js=self.review_inputs(f,b)
        claims=[]
        for item,j in zip(inventory["items"],js):
            proof=self.check_fixture(path,j)
            proof.update(evidence_class="actual",evaluation_scope="actual",adoption_eligible=True)
            proof["predicate_result"]["facts"].update(evidence_class="actual",evaluation_scope="actual",adoption_eligible=True,fixture_only=False)
            claims.append({**item,"kind":"measured_historical_resource","outcome":"supported","reason":"Forged caller label must not defeat original source.",
                "evidence":proof["evidence"],"historical_context":j["historical_context"],"historical_numeric_result":proof})
        from evidence_research import evaluation
        review={"status":"complete","reviewer_role":"independent_verifier","report_path":inventory["report_path"],"report_sha256":inventory["report_sha256"],
            "inventory_path":str(path),"inventory_sha256":sha256_file(path),"claims":claims,"unsupported_claims":0,"pending_claims":0,
            "historical_numeric_schema_version":HISTORICAL_NUMERIC_SCHEMA_VERSION,
            "historical_numeric_source":{"path":str(Path(evaluation.__file__).resolve()),"sha256":sha256_file(Path(evaluation.__file__))}}
        with self.assertRaises(ValueError):_validate_numeric_review(review,arm_output=f.root)


if __name__ == "__main__":
    unittest.main()
