"""Read-only candidate methodology fixtures; no provider or task runner."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CANDIDATE = ROOT / "work/c6"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    if (HERE / "source-manifest.json").exists():
        raise FileExistsError("Keep historical peer bytes; create a new revision")
    sources = sorted((CANDIDATE / "evidence_research").glob("*.py"))
    sources += [CANDIDATE / "tests/test_sampled_pilot.py"]
    before = {path.relative_to(CANDIDATE).as_posix(): sha(path) for path in sources}
    for path in sources:
        target = HERE / "source_snapshot" / path.relative_to(CANDIDATE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if sha(target) != before[path.relative_to(CANDIDATE).as_posix()]:
            raise ValueError("Candidate changed during read-only capture")
    if before != {path.relative_to(CANDIDATE).as_posix(): sha(path) for path in sources}:
        raise ValueError("Candidate concurrently changed; do not claim frozen review")
    manifest = {"kind": "read_only_candidate_methodology_snapshot", "files": before,
                "scope": "Historical reviewed candidate bytes only; root may revise afterward"}
    path = HERE / "source-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_sha256": sha(path), "files": len(before)}))


def solve(matrix, target):
    """Small synthetic algebra fixture, not the research fitting implementation."""
    n = len(target)
    augmented = [list(row) + [value] for row, value in zip(matrix, target)]
    for k in range(n):
        pivot = max(range(k, n), key=lambda i: abs(augmented[i][k]))
        augmented[k], augmented[pivot] = augmented[pivot], augmented[k]
        value = augmented[k][k]
        if abs(value) < 1e-12:
            raise ValueError("Synthetic identification fixture is singular")
        augmented[k] = [v / value for v in augmented[k]]
        for i in range(n):
            if i != k:
                value = augmented[i][k]
                augmented[i] = [a - value * b for a, b in zip(augmented[i], augmented[k])]
    return [row[-1] for row in augmented]


def review(pin):
    manifest_path = HERE / "source-manifest.json"
    if sha(manifest_path) != pin:
        raise ValueError("Caller-supplied external manifest pin differs")
    manifest = json.loads(manifest_path.read_text())
    snapshot = HERE / "source_snapshot"
    for name, expected in manifest["files"].items():
        if sha(snapshot / name) != expected:
            raise ValueError("Source snapshot changed")
    sys.path.insert(0, str(snapshot))
    from evidence_research import baseline, evaluation, study, tasks
    blockers = []
    with patch("evidence_research.model.CodexProvider.complete", side_effect=AssertionError("No provider")) as provider, \
         patch("evidence_research.tasks.run_task", side_effect=AssertionError("No task runner")) as runner, \
         patch("evidence_research.arms.run_task", side_effect=AssertionError("No arm runner")) as arm_runner, \
         patch("subprocess.Popen", side_effect=AssertionError("No subprocess")) as process, \
         patch("socket.socket", side_effect=AssertionError("No network")) as network:
        blockers = [provider, runner, arm_runner, process, network]
        # Range/hash validation is not a check of an exact random draw sequence.
        seed = 13579
        rng = random.Random(seed)
        original = tasks.sample_task_definition(rng)
        data_seed = rng.randrange(2**32)
        altered = json.loads(json.dumps(original))
        altered["coefficients"][0] = altered["coefficients"][0] / 2
        config = {"owner_sampling_seed": seed, "pilot_task_distribution": tasks.SAMPLED_TASK_DISTRIBUTION,
                  "pilot_task_distribution_sha256": tasks.value_hash(tasks.SAMPLED_TASK_DISTRIBUTION)}
        unit = {"unit_id": "dev-sampled-00000", "task_id": "dev-sampled-00000", "seed": data_seed,
                "owner_sampled_definition": altered, "definition_sha256": tasks.value_hash(altered)}
        checked = study._pilot_definition(config, unit)
        draw_check = {"synthetic_fixture_only": True, "altered_definition_differs_from_seed_draw": altered != original,
                      "within_law_rehashed_alteration_accepted_by_definition_check": checked == altered,
                      "no_owner_rows_written": True}
        # Package freezing does not inventory the referenced upstream source.
        frozen = evaluation.frozen_sources()
        source_check = {"frozen_package_files": len(frozen),
            "all_frozen_entries_are_package_py": all(Path(path).parent == Path(evaluation.__file__).parent for path in frozen),
            "upstream_reference_modules_in_frozen_inventory": sum("references" in Path(path).parts for path in frozen)}
        with tempfile.TemporaryDirectory(prefix="synthetic-source-only-") as folder:
            path = Path(folder) / "peer_fixture_module.py"
            values = []
            for value in (1, 2):
                path.write_text("def fixture_value():\n    return " + str(value) + "\n", encoding="utf-8")
                module, metadata = baseline._load_definitions("peer_fixture_module", Path(folder), {})
                values.append({"returned": module.fixture_value(), "source_sha256": metadata["sha256"]})
            sys.modules.pop("peer_fixture_module", None)
            source_check.update(synthetic_loader_fixture_only=True, loader_accepted_changed_source=True,
                                source_sha_was_recorded_but_no_fixed_expected_sha_checked=values[0]["source_sha256"] != values[1]["source_sha256"],
                                actual_upstream_files_changed=0)
        # Public deterministic noise seed makes hidden coefficients identifiable.
        # Use a tiny invented algebra example, never existing owner data or run_task.
        coefficients, noise, seed = [0.3, -0.2, 0.4], 0.12, 2468
        generator = random.Random(seed)
        public = []
        for i in range(8):
            x, z = generator.uniform(-1.5, 1.5), generator.gauss(0, 1)
            y = sum(c * x ** p for p, c in enumerate(coefficients)) + noise * z
            public.append((x, y))
        predictor_generator = random.Random(seed)
        augmented, y_values = [], []
        for x, y in public:
            predicted_x, z = predictor_generator.uniform(-1.5, 1.5), predictor_generator.gauss(0, 1)
            if predicted_x != x:
                raise ValueError("Seed sequence differs")
            augmented.append([1.0, x, x * x, z]); y_values.append(y)
        gram = [[math.fsum(row[j] * row[k] for row in augmented) for k in range(4)] for j in range(4)]
        rhs = [math.fsum(row[j] * y for row, y in zip(augmented, y_values)) for j in range(4)]
        recovered = solve(gram, rhs)
        parameter_error = max(abs(a - b) for a, b in zip(recovered, coefficients + [noise]))
        prediction_error = 0.0
        for _ in range(3):
            x, z = generator.uniform(-1.5, 1.5), generator.gauss(0, 1)
            px, pz = predictor_generator.uniform(-1.5, 1.5), predictor_generator.gauss(0, 1)
            actual = sum(c * x ** p for p, c in enumerate(coefficients)) + noise * z
            recovered_value = sum(c * px ** p for p, c in enumerate(recovered[:-1])) + recovered[-1] * pz
            prediction_error = max(prediction_error, abs(actual - recovered_value))
        seed_check = {"synthetic_algebra_fixture_only": True, "actual_model_cheating_observed": False,
                      "existing_private_owner_data_accessed": False, "owner_rows_written_or_printed": False,
                      "max_parameter_reconstruction_error": parameter_error,
                      "max_future_label_prediction_error": prediction_error,
                      "scope": "Public deterministic RNG source and data seed imply identifiability; restricted literal/model tools limit actual exploit capability."}
        if parameter_error > 1e-12 or prediction_error > 1e-12:
            raise ValueError("Synthetic seed-identification argument not reproduced")
        if any(block.call_count for block in blockers):
            raise ValueError("Unexpected actual runner/provider/network/subprocess call")
    proof = {"kind": "read_only_methodology_peer_fixture_result", "manifest_sha256": pin,
             "sampling_sequence_check": draw_check, "upstream_source_freeze_check": source_check,
             "public_seed_information_check": seed_check, "real_model_calls": 0, "research_cpu_executions": 0,
             "scope": "Historical candidate limitations, not original v5 failure reclassification or actual research outcome"}
    for name, expected in manifest["files"].items():
        if sha(snapshot / name) != expected:
            raise ValueError("Peer fixtures changed captured sources")
    (HERE / "finding.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    if args.capture:
        capture()
    elif args.manifest_sha256:
        review(args.manifest_sha256)
    else:
        parser.error("Choose capture or supply the externally recorded manifest pin")
