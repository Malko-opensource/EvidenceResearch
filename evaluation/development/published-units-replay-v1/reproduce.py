"""Public-only isolated replay and byte-anchor/mapping negative fixtures.

Copies the exact approved manifest, archived pinned sources and public inputs.
Never copies private owner rows, owner requests, databases or checkpoints.
"""
from pathlib import Path, PureWindowsPath
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
UNITS = ("linear-seed11", "linear-seed19", "quadratic-seed31", "quadratic-seed43")
REGISTRATION = "a8fdd8c5500961350b289b8798a0ee9dde116ed2d07ee0ef13e131701ec0be92"
PUBLICATION = "b71986a181f3c8359ca14151ce746b3110c33131001b4c225ce977c419c5cfb2"
RECORDED = r"C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch"
STUDY = "runs/development/paired-pilot-v4"
MANIFEST = "evidence/publication-review-completed-v4/manifest.json"
HELPER = "evaluation/replay_published_units.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def relative(recorded):
    path = PureWindowsPath(recorded)
    assert path.is_absolute() and ".." not in path.parts
    return Path(*path.relative_to(PureWindowsPath(RECORDED)).parts)


def main():
    manifest_path, registration_path = ROOT / MANIFEST, ROOT / STUDY / "pilot-registration.json"
    assert sha(manifest_path) == PUBLICATION and sha(registration_path) == REGISTRATION
    manifest, registration = read(manifest_path), read(registration_path)
    records = {record["path"]: record["sha256"] for record in manifest["files"]}
    records[MANIFEST], records[f"{STUDY}/pilot-registration.json"] = PUBLICATION, REGISTRATION
    for path, expected in registration["sources"].items():
        records[f"{STUDY}/source-snapshot/evidence_research/{PureWindowsPath(path).name}"] = expected
    for unit in registration["units"]:
        if unit["unit_id"] in UNITS:
            records[relative(unit["public_path"]).as_posix()] = unit["public_sha256"]
    records[HELPER] = sha(ROOT / HELPER)
    assert all(".." not in Path(name).parts and not Path(name).is_absolute() for name in records)
    assert all(not Path(name).name.endswith("-owner.json") and Path(name).name != "owner-request.json" for name in records)
    before = {name: sha(ROOT / name) for name in records}
    assert before == records
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="pur-", dir=ROOT.parent) as temporary:
        copied = Path(temporary)
        for name in records:
            target = copied / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        assert not list(copied.rglob("*-owner.json")) and not list(copied.rglob("owner-request.json"))
        command = [sys.executable, "-X", "utf8", "-B", str(__file__), "--child", str(copied), str(ROOT)]
        completed = subprocess.run(command, cwd=copied, capture_output=True, text=True, encoding="utf-8", errors="replace")
        (OUT / "stdout.log").write_text(completed.stdout, encoding="utf-8")
        (OUT / "stderr.log").write_text(completed.stderr, encoding="utf-8")
        if (copied / "proof.json").exists():
            shutil.copyfile(copied / "proof.json", OUT / "proof.json")
        if (copied / "scalar-replay.json").exists():
            shutil.copyfile(copied / "scalar-replay.json", OUT / "scalar-replay.json")
    assert before == {name: sha(ROOT / name) for name in records}, "Original publication/source bytes modified"
    result = {"kind": "isolated_public_only_multiunit_replay_proof", "exit_code": completed.returncode,
        "seconds": time.perf_counter()-started, "command": command, "copied_public_file_count": len(records),
        "source": {"path": str(__file__), "sha256": sha(__file__)},
        "reader": {"path": HELPER, "sha256": records[HELPER]},
        "registration_sha256": REGISTRATION, "publication_manifest_sha256": PUBLICATION,
        "original_publication_and_source_sha256": records, "original_before_after_identical": True,
        "stdout_sha256": sha(OUT / "stdout.log"), "stderr_sha256": sha(OUT / "stderr.log"),
        "private_owner_or_request_copied": False, "generated_hidden_rows_written_or_printed": False,
        "new_model_calls": 0, "new_runner_executions": 0,
        "scope": "Four approved completed development pairs; all generation is source-pinned pure calculation, no final-study or improvement decision."}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({"exit_code": completed.returncode, "copied_public_file_count": len(records), "result": str(OUT / "result.json")}, ensure_ascii=False))
    raise SystemExit(completed.returncode)


def child(copied, forbidden):
    copied, forbidden = Path(copied).resolve(), Path(forbidden).resolve()
    attempts = {"original_project_access": 0, "private_owner_or_request_open": 0, "subprocess_or_network": 0}
    def audit(event, args):
        if event in ("open", "os.listdir", "os.scandir") and args and isinstance(args[0], (str, bytes)):
            path = Path(args[0]).resolve()
            if path.is_relative_to(forbidden):
                attempts["original_project_access"] += 1
                raise PermissionError("Isolated public replay cannot inspect original project")
            if path.name.endswith("-owner.json") or path.name == "owner-request.json":
                attempts["private_owner_or_request_open"] += 1
                raise PermissionError("Private owner/request rows are outside public replay")
        if event in ("subprocess.Popen", "os.system", "socket.connect", "socket.bind", "socket.getaddrinfo"):
            attempts["subprocess_or_network"] += 1
            raise PermissionError("No model process, actual runner subprocess or network in replay")
    sys.addaudithook(audit)
    spec = importlib.util.spec_from_file_location("standalone_public_reader", copied / HELPER)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    calls = []
    original_compile = reader.compiled_pure
    def observe(nodes, namespace):
        calls.extend(node.name for node in nodes)
        return original_compile(nodes, namespace)
    reader.compiled_pure = observe
    result = reader.replay(copied, RECORDED, STUDY, list(UNITS), REGISTRATION, MANIFEST, PUBLICATION)
    assert result["valid"] and len(result["units"]) == len(UNITS)
    assert all(unit["regenerated_owner_proof"]["private_owner_file_opened"] is False for unit in result["units"])
    assert set(calls) == {"canonical_bytes", "value_hash", "task_data", "split_manifest", "canonical_json", "_owner_metric"}
    assert not any(name == "evidence_research" or name.startswith("evidence_research.") for name in sys.modules)
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+"\n"
    assert '"x":' not in serialized and '"y":' not in serialized and '"test": [' not in serialized
    (copied / "scalar-replay.json").write_text(serialized, encoding="utf-8")
    fixtures = []
    def rejected(label, operation, phrase):
        before_calls = len(calls)
        try:
            operation()
        except ValueError as error:
            assert phrase in str(error), (label, str(error))
            assert len(calls) == before_calls, "Rejected bytes reached pure generation/reference evaluation"
            fixtures.append({"fixture": label, "rejected": True, "reason": str(error), "pure_functions_executed": 0})
        else:
            raise AssertionError(f"Required fail-closed rejection absent: {label}")
    def replay(**changes):
        options = dict(root=copied, recorded_root=RECORDED, study=STUDY, units=list(UNITS), registration_sha256=REGISTRATION, publication_manifest=MANIFEST, publication_sha256=PUBLICATION)
        options.update(changes)
        return reader.replay(**options)
    rejected("wrong_external_registration_pin", lambda: replay(registration_sha256="0"*64), "Unrecognized")
    rejected("wrong_external_manifest_pin", lambda: replay(publication_sha256="0"*64), "Unrecognized")
    original_task = copied / STUDY / "source-snapshot/evidence_research/tasks.py"
    task_bytes = original_task.read_bytes()
    original_task.write_bytes(task_bytes+b"\n# mutation fixture\n")
    rejected("archived_generator_byte_mutation", replay, "Original bytes changed")
    original_task.write_bytes(task_bytes)
    manifest = read(copied / MANIFEST)
    prediction_name = next(record["path"] for record in manifest["files"] if record["path"].endswith("/predictions.json"))
    prediction = copied / prediction_name
    prediction_bytes = prediction.read_bytes()
    result_path = prediction.parent / "result.json"
    result_bytes = result_path.read_bytes()
    altered = read(prediction);altered["train"][0]["prediction"] += 1
    prediction.write_text(json.dumps(altered, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    altered_result = read(result_path);altered_result["artifact_hashes"]["predictions.json"] = sha(prediction)
    result_path.write_text(json.dumps(altered_result, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    rejected("prediction_and_its_self_hash_rewritten", replay, "Original bytes changed")
    prediction.write_bytes(prediction_bytes);result_path.write_bytes(result_bytes)
    measurement = copied / STUDY / "units/linear-seed11/B/owner-measurement.json"
    measurement_bytes = measurement.read_bytes();altered = read(measurement);altered["test_mse"] += 1
    measurement.write_text(json.dumps(altered, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    rejected("scalar_owner_measurement_mutation", replay, "Original bytes changed")
    measurement.write_bytes(measurement_bytes)
    prediction.unlink()
    rejected("missing_original_prediction", replay, "Missing")
    prediction.write_bytes(prediction_bytes)
    mapping = reader.Bundle(copied, RECORDED)
    for label, path, reason in (("unmapped_old_absolute", r"C:\OtherProject\result.json", "outside"),
            ("parent_traversal", "../result.json", "traversal"), ("drive_relative", "C:result.json", "Drive-relative"),
            ("rooted_relative", r"\result.json", "Rooted"), ("alternate_stream", "result.json:stream", "Alternate")):
        rejected(label, lambda path=path: mapping.resolve(path), reason)
    assert not any(attempts.values()), attempts
    assert not any(name == "evidence_research" or name.startswith("evidence_research.") for name in sys.modules)
    proof = {"valid": True, "guard_attempts": attempts, "pure_definition_execution_names": sorted(set(calls)),
        "private_owner_files_present": False, "owner_requests_present": False, "model_or_runner_package_imported": False,
        "negative_fixtures": fixtures, "new_model_calls": 0, "new_runner_executions": 0,
        "generated_rows_persisted_or_printed": False, "reader_sha256": sha(copied / HELPER),
        "scope": "Pure deterministic generation plus independent fit/owner scalar arithmetic only; exact external byte pins checked before compiled pure references."}
    (copied / "proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"valid": True, "units": UNITS, "negative_fixtures": len(fixtures), "guards": attempts}, ensure_ascii=False))


if __name__ == "__main__":
    child(sys.argv[2], sys.argv[3]) if "--child" in sys.argv else main()
