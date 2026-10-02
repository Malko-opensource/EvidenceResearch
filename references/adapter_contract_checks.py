"""Read actual cached evidence and check adapter boundaries without new model calls.

These are implementation checks, not an actual-model comparison or scientific
result. All outputs are confined to a newly created check directory.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import pickle
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evidence_research.arms import literal_candidate, UpstreamCodexBridge
from evidence_research.baseline import _OriginalCheckpointUnpickler
from evidence_research.model import ModelUnavailable


class NoModelExecution:
    model = "gpt-6.1-sol"

    def complete(self, *args, **kwargs):
        raise AssertionError("No model execution is authorized for this check")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output, previous = args.output.resolve(), args.prior_run.resolve()
    output.mkdir(exist_ok=False, parents=True)
    checks = []
    assert literal_candidate("CONFIG = {'degree': 2, 'alpha': 0.0}") == {"degree": 2, "alpha": 0.0}
    for rejected in (
        "import os", "print(0.0)", "CONFIG = {'degree': 1 + 1, 'alpha': 0.0}",
        "__import__('os').system('bad')", "run_candidate({'degree': True, 'alpha': 0})",
        "CONFIG = {'degree': 2, 'alpha': float('nan')}",
    ):
        try:
            literal_candidate(rejected)
        except (SyntaxError, ValueError, TypeError):
            checks.append({"check": "unsafe_generated_program_rejected", "input": rejected, "passed": True})
        else:
            raise AssertionError("Unsafe program was accepted: " + rejected)
    try:
        _OriginalCheckpointUnpickler(io.BytesIO(b"cos\nsystem\n.")).load()
    except pickle.UnpicklingError:
        checks.append({"check": "arbitrary_pickle_global_rejected", "passed": True})
    else:
        raise AssertionError("Arbitrary checkpoint global was accepted")
    bridge = UpstreamCodexBridge(NoModelExecution(), output / "cache", max_model_calls=51,
                                replay_directories=[previous])
    first = next(path.parent for path in sorted((previous / "model").glob("*/request.json"))
                 if json.loads((path.parent / "result.json").read_text())["status"] == "completed")
    request = json.loads((first / "request.json").read_text())["prompt"]
    system, remainder = request.removeprefix("UPSTREAM SYSTEM PROMPT:\n").split("\n\nUPSTREAM USER PROMPT:\n", 1)
    prompt, _contract = remainder.split("\n\nSHARED HOST EXECUTION CONTRACT:\n", 1)
    response = bridge("gpt-6.1-sol", prompt, system)
    assert response == (first / "response.txt").read_text(encoding="utf-8")
    assert bridge.calls[-1]["reused_completed_evidence"]
    checks.append({"check": "completed_actual_response_hash_checked_and_reused", "passed": True,
                   "response_sha256": hashlib.sha256(response.encode()).hexdigest(), "actual_new_model_calls": 0})
    bounded = UpstreamCodexBridge(NoModelExecution(), output / "budget", max_model_calls=bridge.prior_attempts,
                                 replay_directories=[previous])
    try:
        bounded("gpt-6.1-sol", "new request outside existing cache", "new system")
    except ModelUnavailable:
        checks.append({"check": "prior_attempts_consume_same_registered_resource_envelope", "passed": True})
    else:
        raise AssertionError("Prior requests were not counted against the resource envelope")
    tampered = output / "tampered-prior" / "model" / first.name
    shutil.copytree(first, tampered)
    with (tampered / "response.txt").open("a", encoding="utf-8") as stream:
        stream.write("\nchanged")
    try:
        UpstreamCodexBridge(NoModelExecution(), output / "tamper-check", max_model_calls=51,
                            replay_directories=[tampered.parent.parent])
    except ModelUnavailable:
        checks.append({"check": "changed_raw_response_refused", "passed": True})
    else:
        raise AssertionError("Changed cache evidence was accepted")
    result = {"kind": "adapter_implementation_checks", "comparison_evidence": False,
              "actual_new_model_calls": 0, "actual_cpu_task_executions": 0, "checks": checks}
    (output / "checks.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"all_passed": True, "check_count": len(checks), "comparison_evidence": False}))


if __name__ == "__main__":
    main()
