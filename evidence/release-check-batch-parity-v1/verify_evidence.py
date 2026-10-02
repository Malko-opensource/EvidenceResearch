"""Verify saved publication-scan evidence; no Git/provider execution or blob output."""
import hashlib
import json
from pathlib import Path


def main():
    directory = Path(__file__).resolve().parent
    manifest = json.loads((directory / "evidence-manifest.json").read_text(encoding="utf-8"))
    for name, record in manifest["files"].items():
        path = directory / name
        data = path.read_bytes()
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError("Saved evidence hash mismatch")
    project = directory.parents[1]
    for key, filename in (("script_source", "release_check_batch.py"), ("legacy_script_unchanged_source", "release_check.py")):
        data = (project / "scripts" / filename).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest[key]["sha256"]:
            raise ValueError("Scanner source differs from execution anchor")
    legacy = json.loads((directory / "legacy-release-check.json").read_text(encoding="utf-8"))
    batch = json.loads((directory / "batch-result.json").read_text(encoding="utf-8"))
    parity = json.loads((directory / "parity.json").read_text(encoding="utf-8"))
    receipt = json.loads((directory / "batch-receipt.json").read_text(encoding="utf-8"))
    if legacy["manifest"] != batch["manifest"] or legacy["file_count"] != batch["file_count"]:
        raise ValueError("Staged manifest parity failed")
    differences = [key for key in legacy if legacy[key] != batch.get(key)]
    if differences != parity["different_core_fields"] or not parity["staged_manifest_exact_equal"]:
        raise ValueError("Stored parity classification disagrees")
    if not receipt["index_stable"] or receipt["index_before_sha256"] != receipt["index_after_sha256"]:
        raise ValueError("Execution index was unstable")
    if receipt["blob_requests"] != batch["file_count"] or receipt["git_object_processes"] != 1:
        raise ValueError("Execution accounting differs from manifest")
    if any(item["reason"] != "working file changed after staging; restage and verify" for item in batch["rejected"]):
        raise ValueError("Unexpected rejection category")
    print(json.dumps({"saved_evidence_valid": True, "staged_manifest_exact_equal": True,
                      "file_count": batch["file_count"], "original_current_worktree_scan_valid": batch["valid"],
                      "original_rejected_count": len(batch["rejected"]), "credential_values_printed": False,
                      "git_mutation": False, "model_calls": 0}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError):
        print(json.dumps({"saved_evidence_valid": False, "credential_values_printed": False,
                          "reason": "Saved evidence requires reconciliation"}))
        raise SystemExit(1)
