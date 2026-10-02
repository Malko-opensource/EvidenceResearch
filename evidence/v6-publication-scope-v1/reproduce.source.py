"""Read-only scoped publication candidate. No git, source mutation or live data."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "work/v6-publication-candidate-manifest.json"
RELEASE = ROOT / "versions/v6-development"
PINS = {
    "versions/v6-development/release-copy.json": "44941c17d0136056f97314055bcfbab77be57f4644c1c163f002a7953da9bbb7",
    "versions/v6-development/validation/release-local-v1/result.json": "b613ac36a50e0ca524944063f2b60bc53815a798595690fb98a671381b5ce809",
    "versions/v6-development/validation/release-local-v2/result.json": "4070b816c896684bdd548120e554902263dd121fd9f649c72732b4c1d1bae3ed",
    "evidence/c6-check-v1/result.json": "e3698eafeff2f63654b6ba3b7d97dd1dbb565ccbb85de4dcf001044b2ba6649d",
    "evidence/c6-independent-sampler-v5/result.json": "74916b562a82b15cf62cc6a1e159b462661c039d95c3fecae2900e39b692b1c3",
    "evidence/c6-semantic-historical-development-v1/delivery-manifest.json": "76db6eaf239227159e2029e22a46bfce5a624ebe756463fe62abcc56bed07530",
    "evidence/c6-literature-contract-v1/source-manifest.json": "db6f9f083cdbbae9cbe7b5b995368a566d8e75ad7bccfce0b85fc984a152b01d",
    "evidence/c6-literature-contract-v2/source-manifest.json": "c7a5b11961fa717bc7807d122cbb172b7cacb711c5d65739e9d45173a4027d31",
    "evidence/c6-literature-contract-v3/source-manifest.json": "e63eb42f6bb46f3723bf9fd746e469364ad777d964f4bfa524398d4e38f318ad",
    "evaluation/development/c6-sampled-design-peer-v1/source-manifest.json": "1b5599375714816490e5c6563681562be934187259f7e99172d9f37a79a0b608",
    "evaluation/development/c6-sampled-design-peer-v2/source-manifest.json": "20185e5be3613bf4748fcf3410990a363bfefc42122865644d0d764e9b0dbf1e",
}
ROOT_GROUPS = {
    "versions/v6-development/validation/release-local-v1": "engineering_environment_validation_with_preserved_external_guard_failure",
    "versions/v6-development/validation/release-local-v2": "engineering_environment_validation_completed",
    "evidence/c6-candidate-source-copy-v1": "engineering_candidate_copy_provenance",
    "evidence/c6-check-v1": "engineering_component_checks_static_source_snapshot",
    **{f"evidence/c6-independent-sampler-v{i}": "engineering_independent_sampler_fixtures" for i in range(1, 6)},
    "evidence/c6-semantic-historical-development-v1": "engineering_semantic_contract_fixtures",
    **{f"evidence/c6-literature-contract-v{i}": "engineering_literature_source_contract_fixtures" for i in range(1, 4)},
    "evaluation/development/c6-sampled-design-peer-v1": "engineering_historical_source_peer_fixtures",
    "evaluation/development/c6-sampled-design-peer-v2": "engineering_revised_source_peer_fixtures",
    "evidence/fresh-published-reader-c95471c": "fresh_public_checkout_reader_proof_four_previously_approved_units",
}
SECRET = re.compile(rb"(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def relative(path):
    return path.relative_to(ROOT).as_posix()


def excluded_path(path):
    parts = path.relative_to(ROOT).parts
    if any(p.casefold() in {".venv", "__pycache__", ".git", "work", "runs"} for p in parts):
        return "runtime_or_actual_study_path_not_in_publication_scope"
    if path.suffix.casefold() in {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".pkl", ".pickle"}:
        return "compiled_or_database_or_checkpoint_not_selected"
    if any("owner" in p.casefold() or "private" in p.casefold() for p in parts):
        return "owner_or_private_named_path_excluded_before_byte_read_even_if_synthetic"
    return None


def assert_local(path):
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(ROOT) or path.is_symlink():
        raise ValueError("File leaves the allowed own project or is a symlink")
    cursor = path.parent
    while cursor != ROOT:
        if cursor.is_symlink():
            raise ValueError("Symlink ancestor is outside publication provenance")
        cursor = cursor.parent


def no_persisted_rows_or_private_seeds(value):
    if isinstance(value, dict):
        if {"x", "y", "id"}.issubset(value) and isinstance(value["x"], (int, float)) and isinstance(value["y"], (int, float)):
            return False
        for key in ("owner_sampling_seed", "owner_split_seeds", "owner_sampled_definition"):
            if key in value and isinstance(value[key], (int, dict, list)):
                return False
        return all(no_persisted_rows_or_private_seeds(v) for v in value.values())
    if isinstance(value, list):
        return all(no_persisted_rows_or_private_seeds(v) for v in value)
    return True


def main():
    if OUTPUT.exists():
        raise FileExistsError("Keep prior candidate manifest; use a separate revision")
    for name, pin in PINS.items():
        path = ROOT / name
        assert_local(path)
        if sha(path) != pin:
            raise ValueError("External evidence pin differs: " + name)
    copy = read_json(RELEASE / "release-copy.json")
    if len(copy["files"]) != 101:
        raise ValueError("Unexpected fixed release source count")
    acquisition_path = RELEASE / "references/manifest.json"
    if sha(acquisition_path) != "2b02fc8f6d2fef3f46758cb2e6855686371c94ac055298badf7d2f8970c3587f":
        raise ValueError("Fixed upstream external manifest differs")
    upstream = {row["path"].replace("\\", "/"): row for row in read_json(acquisition_path)["files"] if "upstream_path" in row}
    files, excludes, reasons, source_checks = {}, [], Counter(), []
    def exclude(path, reason):
        excludes.append({"path": relative(path), "reason": reason, "bytes_read": False})
        reasons[reason] += 1
    def add(path, group, expected=None):
        reject = excluded_path(path)
        if reject:
            exclude(path, reject)
            return
        assert_local(path)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected is not None and digest != expected:
            raise ValueError("Pinned publication source differs: " + relative(path))
        if SECRET.search(raw):
            raise ValueError("Possible secret-shaped content detected; value never printed: " + relative(path))
        if path.suffix.casefold() == ".json" and not no_persisted_rows_or_private_seeds(json.loads(raw.decode("utf-8-sig"))):
            raise ValueError("Persisted data rows/private generation values in public proof; value never printed: " + relative(path))
        scopes = [group]
        reference = next((name for name in upstream if relative(path).endswith(name)), None)
        if reference is not None:
            record = upstream[reference]
            if digest != record["sha256"] or len(raw) != record["bytes"] or hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() != record["git_blob_sha1"]:
                raise ValueError("Engineering upstream snapshot differs from externally authenticated raw source")
            scopes.append("engineering_pinned_upstream_reproduction_source")
        item = files.setdefault(relative(path), {"path": relative(path), "bytes": len(raw), "sha256": digest, "scopes": []})
        for scope in scopes:
            if scope not in item["scopes"]:
                item["scopes"].append(scope)
    for row in copy["files"]:
        path = RELEASE / row["relative"]
        if row["ignored_upstream_runtime"] or "references/upstream/" in row["relative"].replace("\\", "/"):
            exclude(path, "v6_runtime_upstream_omitted_use_public_pinned_fetch_script")
            continue
        add(path, "v6_frozen_source_copy", row["sha256"])
    add(RELEASE / "release-copy.json", "v6_release_copy_receipt", PINS["versions/v6-development/release-copy.json"])
    for directory, group in ROOT_GROUPS.items():
        base = ROOT / directory
        if base.is_symlink():
            raise ValueError("Symlink publication root")
        for path in sorted(base.rglob("*")):
            if path.is_file():
                add(path, group)
    # Validate source-manifest-backed engineering inputs without following the
    # absolute paths embedded in earlier metadata or opening any actual study.
    for name, pin in PINS.items():
        if not name.endswith("source-manifest.json"):
            continue
        base = (ROOT / name).parent
        manifest = read_json(ROOT / name)
        records = manifest["files"]
        records = records.items() if isinstance(records, dict) else ((r["path"], r["sha256"]) for r in records)
        snapshot = base / ("source_snapshot")
        count = 0
        for source, expected in records:
            path = snapshot / source
            if excluded_path(path):
                raise ValueError("Pinned source manifest requires an excluded/private path")
            if relative(path) not in files or files[relative(path)]["sha256"] != expected:
                raise ValueError("Engineering source manifest completeness failed")
            count += 1
        source_checks.append({"manifest": name, "manifest_sha256": pin, "pinned_source_files_included": count})
    component = read_json(ROOT / "evidence/c6-check-v1/result.json")
    for name, expected in component["source_before"].items():
        if files["evidence/c6-check-v1/s/" + name.replace("\\", "/")]["sha256"] != expected:
            raise ValueError("Parent engineering static snapshot differs")
    for name, expected in read_json(ROOT / "evidence/c6-semantic-historical-development-v1/delivery-manifest.json")["files"].items():
        if files["evidence/c6-semantic-historical-development-v1/" + name]["sha256"] != expected["sha256"]:
            raise ValueError("Semantic engineering delivery differs")
    doctor = read_json(RELEASE / "validation/release-local-v1/doctor.stdout.log")
    if doctor.get("authentication", {}).get("diagnostic") != "Not logged in":
        raise ValueError("Auth log differs from expressly reviewed diagnostic-only output")
    for path, row in files.items():
        if sha(ROOT / path) != row["sha256"]:
            raise ValueError("Candidate changed during read-only manifest scan")
    count = Counter(scope for row in files.values() for scope in row["scopes"])
    value = {"kind": "read_only_scoped_v6_publication_candidate_manifest", "git_mutations": 0,
             "publication_performed": False, "files": sorted(files.values(), key=lambda r: r["path"]),
             "file_count": len(files), "total_bytes": sum(row["bytes"] for row in files.values()),
             "scope_counts": dict(sorted(count.items())), "excluded_count": len(excludes),
             "excluded_files_not_opened": sorted(excludes, key=lambda r: r["path"]), "excluded_reason_counts": dict(reasons),
             "externally_recorded_evidence_pins": PINS, "source_manifest_completeness": source_checks,
             "scope": "Frozen source and synthetic engineering fixtures plus fresh public reader proof on four previously approved units. Snapshot-only exact upstream bytes included; v6 runtime upstream omitted.",
             "not_enumerated_or_read": ["all actual v4/v5/v6 and root runs", "current v6 secure private config/owner seeds/registration/source-snapshot", "all actual owner rows/owner-request files", "credential or secret files", "root unfinished extra docs/status", ".venv/work runtime trees"],
             "auth_log_scope": "CLI diagnostic Not logged in only; no successful live model claim",
             "synthetic_scope": "Engineering fixtures do not expose current hidden task data; source literals contain synthetic test seeds only",
             "runtime_upstream_fetch_command": "From versions/v6-development: .venv/Scripts/python.exe scripts/fetch_upstream.py",
             "actual_research_effect_claim": False, "goal_complete": False}
    OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"file_count": len(files), "excluded_count": len(excludes), "total_bytes": value["total_bytes"],
                      "manifest_sha256": sha(OUTPUT), "scope_counts": value["scope_counts"]}))


if __name__ == "__main__":
    main()
