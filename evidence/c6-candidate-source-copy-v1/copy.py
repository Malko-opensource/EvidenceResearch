"""Create the unexecuted c6 source candidate from the externally pinned v5 source."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "versions/v5-development"
DESTINATION = ROOT / "work/c6"
REGISTRATION_PIN = "5569d283aeb9a00087092b862ef6dace71cdf73917429c308161d1cf31ad0f81"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    registration = SOURCE / "runs/p5/pilot-registration.json"
    if sha(registration) != REGISTRATION_PIN:
        raise ValueError("Frozen v5 registration bytes do not match the independent fixed pin")
    document = json.loads(registration.read_text(encoding="utf-8"))
    sources = document["sources"]
    for original, expected in sources.items():
        path = Path(original)
        if not path.resolve().is_relative_to(SOURCE / "evidence_research") or sha(path) != expected:
            raise ValueError("Frozen v5 registered source mismatch: " + original)
    if DESTINATION.exists():
        raise FileExistsError("Candidate already exists; never overwrite an existing candidate")
    selected = []
    for dirname in ("evidence_research", "tests", "examples", "docs", "scripts", "references"):
        for path in sorted((SOURCE / dirname).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                if path.is_symlink():
                    raise ValueError("Do not copy symlinks")
                selected.append(path)
    selected.extend(SOURCE / name for name in (".gitignore", "LICENSE", "NOTICE.md", "pyproject.toml", "README.md") if (SOURCE / name).is_file())
    manifest = []
    for path in selected:
        relative = path.relative_to(SOURCE)
        target = DESTINATION / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        expected = sha(path)
        if sha(target) != expected:
            raise ValueError("Copied bytes changed")
        manifest.append({"relative_path": relative.as_posix(), "sha256": expected})
    receipt = {"kind": "unexecuted_source_candidate", "candidate": "work/c6", "source": "versions/v5-development",
               "parent_registration_sha256": REGISTRATION_PIN, "registered_package_source_count": len(sources),
               "copied_files": manifest, "excluded": ["runs", "work", ".venv", "validation", "private owner rows and requests"],
               "real_model_calls": 0, "research_cpu_executions": 0, "no_existing_outcome_reclassification": True}
    output = Path(__file__).with_name("copy-receipt.json")
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate": str(DESTINATION), "copied": len(manifest), "registered_sources": len(sources), "receipt_sha256": sha(output)}))


if __name__ == "__main__":
    main()
