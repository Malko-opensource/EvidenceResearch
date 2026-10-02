"""Pin/copy one held engineering closure; imports no candidate package."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
SOURCE = WORK / "c8"
MANIFEST = WORK / "c8-implementation-v1/source-manifest.json"
PINS = {
    "source-manifest": "6fce28fb5ed196717011906b9071091244f72bd7874728f2114cb399d2468d69",
    "implementation-result": "de1fae5bf157251716f3a970c8fb7993ad00f3ba6a2de8069bbb18a656d5d696",
    "registration": "21bc0d8ddb1cd3e2bb8b77c958fe7540d972318f3b6bd691406db2bb8b0f2298",
    "independent-plan": "7f018cf798c28d60956a5f7b0e64796c5ea91b178494692408537a07c962e975",
}

def sha(raw): return hashlib.sha256(raw).hexdigest()
def main():
    inputs = {"source-manifest": MANIFEST,
        "implementation-result": WORK / "c8-implementation-v1/result.json",
        "registration": WORK / "c8-method-registration-v1.json",
        "independent-plan": WORK / "c8-independent-validation-preparation-v1/fixture-plan.json"}
    raws = {name: path.read_bytes() for name, path in inputs.items()}
    for name, raw in raws.items(): assert sha(raw) == PINS[name], name
    manifest = json.loads(raws["source-manifest"])
    assert manifest["file_count"] == len(manifest["files"]) == 110
    package = [r for r in manifest["files"] if r["relative"].startswith("evidence_research/") and r["relative"].endswith(".py")]
    references = [r for r in manifest["files"] if r["relative"].startswith("references/") and r["relative"] not in {"references/README.md", "references/AgentLaboratory.LICENSE"}]
    assert len(package) == 20 and len(references) == 38
    selected = package + references
    destination = HERE / "source-snapshot"
    assert not destination.exists()
    before = []
    for item in manifest["files"]:
        path = SOURCE / item["relative"]
        assert path.resolve().is_relative_to(SOURCE.resolve()) and not path.is_symlink()
        raw = path.read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["bytes"], item["relative"]
        before.append(item)
        if item in selected:
            out = destination / item["relative"]
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("xb") as stream: stream.write(raw)
    for name, raw in raws.items():
        with (HERE / (name + ".pinned.json")).open("xb") as stream: stream.write(raw)
    record = {"kind": "independent_held_c8_source_closure_snapshot", "external_pins": PINS,
        "candidate_files_checked": 110, "candidate_source_rows": before,
        "selected_files": selected, "selected_count": 58,
        "package_modules": 20, "fixed_references": 38,
        "candidate_imports_or_executions": 0, "actual_research_or_owner_reads": 0}
    path = HERE / "snapshot-manifest.json"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"sha256": sha(path.read_bytes()), "candidate_files": 110, "snapshot_files": 58, "candidate_imports": 0}))

if __name__ == "__main__": main()
