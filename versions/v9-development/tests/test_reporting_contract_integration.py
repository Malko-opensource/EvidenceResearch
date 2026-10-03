"""Narrow reporting/state contracts. No actual research or authenticated score."""
import copy
import math
import unittest
from decimal import Decimal, localcontext, ROUND_UP, ROUND_DOWN

from evidence_research.comparison_arms import historical_resource_display, unresolved_report_entry
from evidence_research.report_semantics import parse_temporal_resource_list
from evidence_research.store import EvidenceError
from evidence_research.study import _report_decision


def original_prefix():
    # Hand-authored engineering values, never an actual source-bound receipt.
    return {"scope": "historical_pre_request", "fixture_only": True, "eligible": False,
            "measures": {"actual_cpu_executions": 3, "distinct_configurations": 2,
                         "completed_provider_calls": 4, "failed_provider_attempts": 0,
                         "input_tokens": 190, "output_tokens": 17,
                         "cpu_execution_seconds": 0.07038400002056733,
                         "wall_seconds": 243.4199999999255}}


class ReportingContractIntegrationTests(unittest.TestCase):
    def test_display_interoperates_with_fixed_temporal_parser_and_rounding(self):
        original = original_prefix(); before = copy.deepcopy(original)
        display = historical_resource_display(original)
        parsed = parse_temporal_resource_list(display["display"])
        self.assertIsNotNone(parsed)
        self.assertEqual(set(parsed["quantities"]), set(original["measures"]))
        for key, entry in parsed["quantities"].items():
            if key.endswith("seconds"):
                self.assertLessEqual(abs(Decimal(entry["display"]) - Decimal(str(original["measures"][key]))),
                                     Decimal("0.0000000000005"))
                self.assertLessEqual(len(entry["display"].partition(".")[2]), 12)
            else:
                self.assertEqual(entry["value"], original["measures"][key])
        self.assertEqual(original, before)
        self.assertEqual(display["independent_adjudication"], "pending")
        self.assertNotIn("eligible", display)

    def test_unknown_failed_usage_never_becomes_zero_or_completed_lower_bound(self):
        prefix = original_prefix()
        prefix["measures"].update(input_tokens=None, output_tokens=None, failed_provider_attempts=1)
        display = historical_resource_display(prefix)
        parsed = parse_temporal_resource_list(display["display"])
        self.assertEqual(set(display["unknown_measures"]), {"input_tokens", "output_tokens"})
        self.assertNotIn("input_tokens", parsed["quantities"])
        self.assertNotIn("output_tokens", parsed["quantities"])
        self.assertEqual(parsed["quantities"]["failed_provider_attempts"]["value"], 1)

    def test_decimal_display_ignores_ambient_rounding_mode(self):
        prefix = original_prefix()
        prefix["measures"]["wall_seconds"] = 0.1234567890125
        with localcontext() as context:
            context.rounding = ROUND_UP
            up = historical_resource_display(prefix)
            context.rounding = ROUND_DOWN
            down = historical_resource_display(prefix)
        self.assertEqual(up, down)

    def test_malformed_counts_times_and_absent_original_measures_reject(self):
        for key, value in (("input_tokens", True), ("actual_cpu_executions", 1.5),
                           ("completed_provider_calls", -1), ("wall_seconds", True),
                           ("wall_seconds", math.inf), ("cpu_execution_seconds", math.nan),
                           ("cpu_execution_seconds", -0.1)):
            prefix = original_prefix(); prefix["measures"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(EvidenceError):
                historical_resource_display(prefix)
        prefix = original_prefix(); del prefix["measures"]["input_tokens"]
        with self.assertRaises(EvidenceError): historical_resource_display(prefix)

    def test_whole_arm_or_forecast_is_not_historical_display(self):
        for scope in ("final_whole_unit", "expected_next_experiment", None):
            prefix = original_prefix(); prefix["scope"] = scope
            with self.subTest(scope=scope), self.assertRaises(EvidenceError):
                historical_resource_display(prefix)

    def test_incumbent_tie_reports_rejection_after_successful_execution(self):
        run = {"spec": {"hypothesis": "This candidate may help.", "metric": "validation_mse",
                        "criterion": {"direction": "min", "baseline_value": 0.2, "improvement": 0},
                        "baseline": {"run_id": "engineering-prior"}},
               "result": {"status": "success"}, "outcome": "failure",
               "verification": {"valid": True, "status": "verified", "metrics": {"validation_mse": 0.2}}}
        entry = unresolved_report_entry(run)
        self.assertEqual(entry["question"], run["spec"]["hypothesis"])
        self.assertEqual(entry["reason"], "Execution succeeded and the registered incumbent criterion was not met.")

    def test_technical_error_is_retained_without_claiming_success(self):
        run = {"spec": {"hypothesis": "This candidate may help."}, "outcome": "failure",
               "result": {"status": "failed", "error": "Recorded numerical solver failure"},
               "verification": {"valid": False, "reasons": ["No predictions"]}}
        self.assertEqual(unresolved_report_entry(run)["reason"], run["result"]["error"])

    def test_inconclusive_without_reason_does_not_become_a_failed_criterion(self):
        run = {"spec": {"hypothesis": "This candidate may help."}, "outcome": "inconclusive",
               "result": {"status": "success"}, "verification": {"valid": True, "reasons": []}}
        entry = unresolved_report_entry(run)
        self.assertEqual(entry["question"], run["spec"]["hypothesis"])
        self.assertEqual(entry["reason"], "The hypothesis outcome remains unknown.")

    def test_metadata_only_terminal_rejection_differs_from_missing_review(self):
        # This dictionary is a control-flow input, not authenticated actual data.
        score = {"whole_report_numeric_audit_complete": True, "semantic_report_audit_complete": True,
                 "semantic_evidence_qualification": "actual", "unsupported_claims": 0,
                 "unsupported_numeric_claims": 0, "unsupported_semantic_result_claims": 2,
                 "common_report_sufficiency": True}
        self.assertEqual(_report_decision(score), "report_rejected")
        score["semantic_report_audit_complete"] = False
        self.assertEqual(_report_decision(score), "awaiting_independent_report_review")

    def test_fixture_or_unknown_numeric_counters_cannot_be_passed(self):
        base = {"whole_report_numeric_audit_complete": True, "semantic_report_audit_complete": True,
                "semantic_evidence_qualification": "actual", "unsupported_claims": 0,
                "unsupported_numeric_claims": 0, "unsupported_semantic_result_claims": 0,
                "common_report_sufficiency": True}
        fixture = {**base, "fixture_only": True}
        self.assertEqual(_report_decision(fixture), "awaiting_independent_report_review")
        for value in (None, True, -1):
            score = {**base, "unsupported_numeric_claims": value}
            self.assertEqual(_report_decision(score), "awaiting_independent_report_review")


if __name__ == "__main__": unittest.main()
