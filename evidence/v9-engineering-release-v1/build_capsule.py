"""Copy only explicitly pinned, completed engineering metadata into this new capsule.

This stdlib metadata copier never imports a candidate package, invokes a test,
reads a live study, or authenticates a scientific result. It must run only once.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HOLD = "926a8f0da4869641d25abdaa6937aa542f51c53055a15487423e9d73ab73bf94"
SUBSET = "269371c22e04e8c373ed22990cf73ca693c793329860243e57c36189b9fbe4e6"
VERIFY = "versions/v9-development/validation/release-local-dev1-v1/verification/"
INPUTS = [
    ("source/source-manifest125.json", "work/c9p1t1-fixture-forward-preparation-v2/source-manifest.json", HOLD),
    ("source/public-subset87.json", "work/c9p1t1-release-preparation-v1/public-subset-proposal.json", SUBSET),
    ("source/runtime-closure58.json", "work/c9p1-current63-registration-v1/runtime-closure-manifest.json", "15eb08e192e8454bc68c4152d15e25f73a65ba0369751f79d7aa1fa3ebbe5cc2"),
    ("coverage364/result.json", "work/c9p1t1-compositional-coverage-v1/result.json", "dd78c0a8a1f56a176d11b1a9bfd5f0dbcca65aa6c167c7829549ef6cfa3ff12d"),
    ("coverage364/source-comparison.json", "work/c9p1t1-compositional-coverage-v1/source-comparison.json", "6e8a971b3319ea8ff0ac28daffdcc1683d124b493fb849e786d4d496eb7a2c79"),
    ("coverage364/execution-evidence.json", "work/c9p1t1-compositional-coverage-v1/execution-evidence.json", "4660e8f79af7027598c2a9e38773793a786cdabff7dfbaf1578c3d04f1e25d0d"),
    ("coverage63/result.json", "work/c9p1-current63-compositional-coverage-v1/result.json", "0d10b8e4c93d9bd2e3e362ad4c75b5c61fe8eac13727515a546f8ca517a7ed72"),
    ("coverage63/metadata-peer.json", "work/c9p1-current63-composition-metadata-peer-v1/result.json", "2a68ed0ff96f0e99cb1433b13f730b4cd8fb41025d6220b9b7ac46369b7cf5c8"),
    ("coverage63/last1-result.json", "work/c9p1-legacy-case-validation-v1/result.json", "4a71c955118a05845236e8ab8878879d128375af6c8b755f582e40feaeffe104"),
    ("release/release-copy.json", "versions/v9-development/release-copy.json", "cbb0a66756e66ed0f7bf53415247a977ce66000c6bf92738e07ceee51f213a40"),
    ("release/installation-result.json", "versions/v9-development/validation/release-local-dev1-v1/installation-result.json", "d007eaac2b899cc4b7f66e67f31803b89b26f9e7e47d8b76aabaf15254b72eaf"),
    ("verification/result.json", VERIFY + "result.json", "d69001b926bb548dca1ef82376cad6aad90e9a3caf11c96f3c4b604889a12e12"),
    ("verification/cli-help.json", VERIFY + "cli-help.json", "b30d251edef7121807b3816993d73fb9972457bd5f8cf0cf2070f5b0f4befed4"),
    ("verification/study-help.json", VERIFY + "study-help.json", "a602cb515d5ad128ed6a8ad05f50a256657d726c18e834b9acbe85d60c0f83e3"),
    ("verification/new-contract-portability.json", VERIFY + "new-contract-portability.json", "197485cdb77c6d080cfc73060b3d2de3bf787795547f8e377a63df9acd815760"),
    ("verification/own-frozen-closure.json", VERIFY + "own-frozen-closure.json", "c178a1556e2d4ef9c6b1b4931e758fa60031bb7402ca3f8e451730f193df5fee"),
    ("verification/cli-help.guard.json", VERIFY + "cli-help.guard.json", "2de351bc9a1961e15cf5223cc6c4148e5270827fcd988f8144a83755348006d2"),
    ("verification/study-help.guard.json", VERIFY + "study-help.guard.json", "2de351bc9a1961e15cf5223cc6c4148e5270827fcd988f8144a83755348006d2"),
    ("verification/contract.guard.json", VERIFY + "contract.guard.json", "2de351bc9a1961e15cf5223cc6c4148e5270827fcd988f8144a83755348006d2"),
    ("verification/closure.guard.json", VERIFY + "closure.guard.json", "2de351bc9a1961e15cf5223cc6c4148e5270827fcd988f8144a83755348006d2"),
    ("verification/cli-help.stdout.log", VERIFY + "cli-help.stdout.log", "4b07cf83fc4aa921fd4995d0ebf2b6c250435696dc380f3b22e6213616e09253"),
    ("verification/study-help.stdout.log", VERIFY + "study-help.stdout.log", "e1fbd076ecde05c684970395e3c5a25ce104907d2024461625ad75e732ea1106"),
    ("verification/own-frozen-closure.stdout.log", VERIFY + "own-frozen-closure.stdout.log", "2128fb249a35ffbec6045a514b6a57b1c6281ceb370f0ae52eab0f6b2b6cd7b1"),
    ("verification/new-contract-portability.stderr.log", VERIFY + "new-contract-portability.stderr.log", "7528c66b162db6fd27cbd84066d404a3f3abd5979d64742d66d8c9ab5d3ca676"),
    ("verification/bootstrap-search-paths.json", VERIFY + "bootstrap-search-paths.json", "52f5faa21150d0a026c07afaf31d201f73d71dde74a12d829707701e52bfd042"),
    ("verification/discovered-test-ids.json", VERIFY + "discovered-test-ids.json", "060174cda9b837e60d22db378a17ad6d5ec97678ba95888eb33d9cb63146325e"),
    ("verification/test-inventory.json", VERIFY + "test-inventory.json", "6683e6a13c38de8fa9ae9e2b974f267d03dac4712d335bbab2040bba7e8d05b8"),
    ("verification/run_portability.source.py", VERIFY + "run_portability.source.py", "956923ce6cec922c00a6d72b48dd954bca62135c3212fa83fc250c105e450167"),
    ("verification/audit_guard.source.py", "work/c9p1t1-release-preparation-v1/audit_guard/sitecustomize.py", "ded042b483b1e2d515a1b361130c439b09909953343a4bba4a5ff42c4a3e370f"),
]
SECRET_PATTERNS = {
    "aws_access_id": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "openai_literal": re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
    "github_literal": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "private_key_header": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(relative: str, value: object) -> None:
    path = HERE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def main() -> None:
    if (HERE / "manifest.json").exists() or (HERE / "summary.json").exists():
        raise ValueError("Completed or partial capsule exists; preserve it and use a new version")
    payloads, provenance = [], []
    for destination, relative, expected in INPUTS:
        path = ROOT / relative
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Selected source leaves authorized workspace")
        data = path.read_bytes()
        if sha(data) != expected:
            raise ValueError("Selected engineering source differs: " + relative)
        for kind, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                raise ValueError("Credential-like literal found; value suppressed: " + relative + ":" + kind)
        payloads.append((destination, path, data))
        provenance.append({"destination": destination, "source": relative, "source_sha256": expected, "bytes": len(data), "copy_kind": "immutable_exact_original_bytes"})
    by_name = {destination: data for destination, _, data in payloads}
    whole = json.loads(by_name["coverage364/result.json"])
    cases = json.loads(by_name["coverage63/result.json"])
    peer = json.loads(by_name["coverage63/metadata-peer.json"])
    one = json.loads(by_name["coverage63/last1-result.json"])
    verification = json.loads(by_name["verification/result.json"])
    inventory = json.loads(by_name["verification/test-inventory.json"])
    discovered = json.loads(by_name["verification/discovered-test-ids.json"])
    installation = json.loads(by_name["release/installation-result.json"])
    copied = json.loads(by_name["release/release-copy.json"])
    if not (whole["valid"] is True and whole["engineering_assertion_coverage"] == 364 and whole["number_of_execution_harnesses"] == 2 and whole["single_fresh_whole364_PASS"] is False):
        raise ValueError("Compositional364 scope differs")
    if not (cases["status"] == "pass" and cases["registered_family_count"] == 13 and cases["current_source_case_count"] == 63 and cases["single_fresh63_pass"] is False and cases["old_source_case_passes_promoted"] == 0 and cases["fixture_only"] is True and cases["adoption_eligible"] is False):
        raise ValueError("Current63 engineering qualification differs")
    families = cases["registered_family_verdicts"]
    if len(families) != 13 or sum(len(f["subcases"]) for f in families) != 63 or any(f["status"] != "pass" or any(c["status"] != "pass" for c in f["subcases"]) for f in families):
        raise ValueError("Current63 metadata coverage differs")
    if not (peer["metadata_review_valid"] is True and peer["result_sha256"] == sha(by_name["coverage63/result.json"]) and one["status"] == "pass" and one["observed"]["pending"] is True and one["observed"]["actual_complete"] is False):
        raise ValueError("Peer/last1 direct link differs")
    if not (verification["valid"] is True and verification["selected_test_count"] == 101 and inventory["expected_tests"] == 101 and sorted(discovered) == inventory["test_ids"] and len(set(discovered)) == 101 and verification["authenticated_reference_count"] == 38 and verification["full364_repeated"] is False):
        raise ValueError("Own101 inventory/closure differs")
    if not (installation["valid"] is True and verification["installation_result_sha256"] == sha(by_name["release/installation-result.json"]) and installation["copy_receipt_sha256"] == sha(by_name["release/release-copy.json"]) and verification["copy_receipt_sha256"] == sha(by_name["release/release-copy.json"])):
        raise ValueError("Own release receipt chain differs")
    for key in ["coverage364/result.json", "coverage63/result.json", "verification/result.json", "release/installation-result.json"]:
        value = json.loads(by_name[key])
        if value.get("framework_improvement_proven") is not False or value.get("goal_complete") is not False:
            raise ValueError("Engineering/scientific scope differs")
    for phase in ["cli-help", "study-help", "new-contract-portability", "own-frozen-closure"]:
        receipt = json.loads(by_name["verification/" + phase + ".json"])
        if receipt["exit_code"] != 0:
            raise ValueError("Selected completed phase differs")
    for name in ["cli-help", "study-help", "contract", "closure"]:
        receipt = json.loads(by_name["verification/" + name + ".guard.json"])
        if any(type(value) is not int or value != 0 for value in receipt["counts"].values()):
            raise ValueError("Original hook guard counters differ")
    if not re.search(rb"Ran 101 tests in [\d.]+s\s+\nOK\s*$", by_name["verification/new-contract-portability.stderr.log"]):
        raise ValueError("Stored unittest101 completion summary differs")
    for destination, _, data in payloads:
        path = HERE / destination
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        if path.read_bytes() != data:
            raise ValueError("Copy bytes differ")
    for _, path, data in payloads:
        if path.read_bytes() != data:
            raise ValueError("Selected source changed during metadata copy")
    history = {
        "scope": "Concise derived history only. Original failed result/case bodies were not read or copied by this builder.",
        "entries": [
            {"event": "original_whole364", "original_status": "FAILED", "passed": 357, "setup_errors": 7, "source_sha256": whole["basis_source_manifest_sha256"], "result_sha256": whole["original_failed_whole_result_sha256"], "cause": "New test setup helper received str where its imported put helper required Path; affected auditor assertions were not reached.", "forward": "One fixture-only Path coercion helper;17 method assertions/364 IDs/runtime58 unchanged. Separate failure-only7 receipt.", "evidence": "coverage364/result.json"},
            {"event": "original_current63", "original_status": "FAILED", "passed": 62, "failed": 1, "result_sha256": cases["original_failed_result"]["sha256"], "failed_case_sha256": cases["original_failed_case"]["sha256"], "cause": "Synthetic legacy raw CRLF/API LF text comparison; the expected pending/actual-incomplete judgment remained unchanged.", "forward": "Separate last1 pending assertion on preserved raw byte hashes; no repeat of62/native callbacks/simulated completions.", "evidence": "coverage63/result.json;coverage63/last1-result.json"},
        ],
        "original_failures_overwritten": False,
        "failed_histories_newly_reclassified": False,
    }
    criteria = {
        "kind": "unchanged_frozen_research_criteria_summary_not_new_registration",
        "source_manifest_sha256": HOLD,
        "quality_protocol": "paired-evaluation-5-common-source-bound-reporting-sampled-task-contract",
        "efficiency_protocol": "paired-efficiency-8-common-source-bound-reporting-sampled-task-contract",
        "semantic_schema": "whole-report-semantics-4-c9-common-evidence-development",
        "context_schema": "original-context-boundary-2-local-binding-development",
        "historical_numeric_schema": "historical-numeric-context-1",
        "future_scientific_adoption_requirements": ["Independent whole primary AND companion numeric and semantic coverage complete, supported actual evidence qualification, unsupported claims0, common report sufficiency.", "Paired token gain95% lower confidence bound greater than20% AND paired log(test-MSE C/B)95% upper bound less than log(1.10), with the fixed remaining protocol conditions."],
        "criteria_modified_by_capsule": False,
        "actual_model_A": {"available": False, "effect_estimated": False},
        "development_only": True,
        "final_evaluation_performed": False,
        "adoption_eligible": False,
        "framework_improvement_proven": False,
    }
    summary = {
        "schema_version": "ordinary-v9-engineering-publication-capsule-1",
        "actor_role": "Core/context/T1 implementation collaborator; authenticates and copies engineering metadata. Not independent scientific validation of own implementation.",
        "package_version": "0.5.0.dev1",
        "source125_sha256": HOLD,
        "public87_sha256": SUBSET,
        "source_metadata_counts": {"runtime_source_files":125,"ordinary_public_source_files":87,"package_files":20,"authenticated_reference_files":38,"reference_body_files":40},
        "engineering_results": {"compositional_assertion_coverage":364,"whole_composition_harnesses":2,"original357_plus_forward7":True,"one_fresh364_PASS":False,"registered_component_families":13,"current_runtime_component_assertions":63,"current63_composition":{"fresh_current54":54,"retained_current8":8,"failure_only_forward1":1},"one_fresh63_PASS":False,"old55_passes_transferred":0,"own_environment_selected_tests":101,"own_environment_test_composition":{"previous84":84,"original_binding17":17},"CLI_help_phases":2,"own_reference_closure":38},
        "own_environment_result_sha256": sha(by_name["verification/result.json"]),
        "installed_output_independent_peer": {"status":"pending","path":None,"sha256":None,"attach_policy":"Only a separately sealed future forward capsule may add the completed peer; this capsule remains immutable."},
        "capsule_builder_actions": {"candidate_imports":0,"test_reexecutions":0,"CLI_reexecutions":0,"provider_calls":0,"new_CPU_or_reference_arithmetic":0,"owner_or_actual_study_body_reads":0,"Git_mutations":0},
        "parent_engineering_actions": {"selected101":"Synthetic transport and tiny deterministic in-process public CPU component fixtures; not research trials. No CPU subprocess permitted.","current63":"Earlier native2/SIM6 and reference arithmetic12 are stored engineering observations; the metadata composer and this copier repeat none."},
        "qualification": {"fixture_only":True,"scientific_actual_report_completeness_proven":False,"framework_improvement_proven":False,"adoption_eligible":False,"final_evaluation_performed":False,"goal_complete":False},
        "scope": {"raw_synthetic_request_bodies_copied":False,"live_study_or_private_owner_artifacts_copied":False,"private_configuration_bodies_copied":False,"credentials_or_venv_copied":False,"registered_actual_sampling_or_launch_authorized":False,"source87_mutated":False},
        "privacy_scan": {"method":"Explicit metadata/sourcehelper allowlist plus finite credential literal patterns; credential values never printed. Not a proof against arbitrary encoded secrets.","credential_literal_signals":0,"guard_scope":"Stored Python hook counters cover their declared namespaces/events, not OS isolation, all-sibling reads, or subprocess child attestation."},
        "reproducibility_limits": ["Original absolute local paths remain visible in exact engineering receipts and captured bootstrap/commands.","Raw synthetic packets/case fixtures, original full failed result bodies, and upstream35 runtime files are not included. A remote reader cannot independently replay the entire13/63 fixture history from this capsule alone.","The selected101 AST inventory and captured runner accompany the ordinary public87 sources. A new short-path checkout can fetch the manifest-pinned upstream35 and freshly run101 tests with a new environment; that is a fresh execution, not replay of these guard counts.","Offline editable installation used available bundled build tools only for the recorded install phase. A standard fresh venv needs normal build dependencies for pip install -e . or can run from the source root without editable installation.","Zero actual provider calls here does not prove authentication or model availability; CLI --help is a parser/import check."],
    }
    write_json("history-summary.json", history)
    write_json("frozen-criteria-summary.json", criteria)
    write_json("summary.json", summary)
    files = []
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            data = path.read_bytes()
            files.append({"path":path.relative_to(HERE).as_posix(),"bytes":len(data),"sha256":sha(data)})
    write_json("manifest.json", {"schema_version":"ordinary-v9-engineering-capsule-file-manifest-1","file_count":len(files),"bytes":sum(f["bytes"] for f in files),"files":files,"exact_original_copies":provenance,"original_copy_source_bytes_stable":True,"scope":"Source/engineering only; no actual研究 improvement/final/adoption authorization; pending installed-output peer omitted."})
    print(json.dumps({"status":"engineering_capsule_prepared","file_count_in_manifest":len(files),"manifest_sha256":sha((HERE/'manifest.json').read_bytes()),"summary_sha256":sha((HERE/'summary.json').read_bytes()),"copied_original_files":len(INPUTS),"installed_output_peer":"pending","actual_provider_or_research_executions":0}))


if __name__ == "__main__":
    main()
