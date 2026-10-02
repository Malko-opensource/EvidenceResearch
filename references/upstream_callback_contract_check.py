"""Exercise matched B plumbing with explicitly simulated replay responses.

Previously generated public development responses are a deterministic fixture.
They are not new model executions and cannot qualify for a model comparison.
The CPU tool still runs actual public-data fitting and fixed verification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evidence_research.arms import UpstreamArm
from evidence_research.tasks import task_data, split_manifest, TASK_VERSION, sha256_file, write_json


class ReplayFixture:
    execution_kind = "simulation_fixture"

    def __init__(self, responses, *, evidence_dir, model, reasoning_effort=None, public_dir=None):
        self.responses = list(responses)
        self.evidence_dir, self.model = Path(evidence_dir), model
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.last_evidence, self.calls = None, 0

    def complete(self, prompt, *, call_id, json_response=False):
        if self.calls >= len(self.responses):
            raise AssertionError("Original pipeline requested an unexpected fixture response")
        folder = self.evidence_dir / call_id
        folder.mkdir()
        answer = self.responses[self.calls]
        self.calls += 1
        write_json(folder / "request.json", {"prompt": prompt, "model": self.model,
            "execution_kind": self.execution_kind, "scope": "simulated replay; no new model execution"})
        (folder / "response.txt").write_text(answer, encoding="utf-8")
        record = {"status": "completed", "execution_kind": self.execution_kind, "model": self.model,
                  "files": {name: sha256_file(folder / name) for name in ("request.json", "response.txt")}}
        write_json(folder / "result.json", record)
        self.last_evidence = record
        return answer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", type=Path, default=Path("examples/pilot-settings.json"))
    parser.add_argument("--first", type=Path, default=Path("runs/development/B-upstream-dev-quadratic-seed7-literature"))
    parser.add_argument("--continued", type=Path, default=Path("runs/development/B-upstream-dev-quadratic-seed7-resumed"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    responses = []
    for directory in (args.first, args.continued):
        for path in sorted((directory / "model").glob("*/result.json")):
            if json.loads(path.read_text(encoding="utf-8"))["status"] == "completed":
                responses.append((path.parent / "response.txt").read_text(encoding="utf-8"))
    config = json.loads(args.settings.read_text(encoding="utf-8"))
    data = task_data("dev-quadratic", 7)
    public = {"task_id": "dev-quadratic", "seed": 7, "task_version": TASK_VERSION,
              "objective": "select polynomial ridge degree and alpha using train/validation only",
              "metric": "validation_mse", "allowed_config": {"degree": "integer 1..8", "alpha": "finite 0..100"},
              "criterion": {"direction": "min", "threshold": 0.03},
              "task_bundle": {"train": data["train"], "validation": data["validation"],
                              "split_manifest": split_manifest("dev-quadratic", 7)}}
    payload = {"arm": "B", "model_id": config["model_id"], "resource_envelope": config["resource_envelope"],
               "public_task": public, "baseline_provenance": config["baseline_provenance"]}
    instances = []
    def factory(**kwargs):
        provider = ReplayFixture(responses, **kwargs)
        instances.append(provider)
        return provider
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    callback = UpstreamArm(provider_factory=factory)
    response = callback(payload, output / "B")
    assert response["model_execution_kind"] == "simulation_fixture"
    assert response["independent_review_pending"] is True
    assert response["resource_envelope"] == config["resource_envelope"]
    folder = Path(response["selected_run_dir"])
    spec = json.loads((folder / "registered_spec.json").read_text(encoding="utf-8"))
    assert spec["task_bundle"] == public["task_bundle"] and "test" not in spec["task_bundle"]
    assert json.loads((folder / "independent_verification.json").read_text(encoding="utf-8"))["valid"]
    calls = instances[0].calls
    resumed = callback(payload, output / "B")
    assert resumed["resumed_without_execution"] is True and len(instances) == 1
    assert instances[0].calls == calls
    for private_field in ("test", "private_definition", "owner_path"):
        try:
            callback._public_payload({**payload, "public_task": {**public, private_field: "forbidden"}})
        except ValueError:
            pass
        else:
            raise AssertionError("Private field was accepted: " + private_field)
    write_json(output / "checks.json", {"all_passed": True, "model_execution_kind": "simulation_fixture",
        "actual_new_model_calls": 0, "fixture_responses": calls,
        "checks": ["original full pipeline callback plumbing", "public bundle linked to fixed verification",
                   "independent review remains pending", "completed callback resume does not execute",
                   "private task fields rejected", "fixture cannot qualify as actual model execution"],
        "comparison_evidence": False})
    print(json.dumps({"all_passed": True, "fixture_responses": calls, "actual_new_model_calls": 0,
                      "comparison_evidence": False}))


if __name__ == "__main__":
    main()
