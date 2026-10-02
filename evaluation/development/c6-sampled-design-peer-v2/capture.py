"""Read-only byte capture of candidate sampler and its pure control fixtures."""
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CANDIDATE = ROOT / "work/c6"
UPSTREAM_MANIFEST_PIN = "2b02fc8f6d2fef3f46758cb2e6855686371c94ac055298badf7d2f8970c3587f"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "source-manifest.json"
    if path.exists():
        raise FileExistsError("Keep captured review immutable; use a new revision")
    relatives = sorted(p.relative_to(CANDIDATE) for p in (CANDIDATE / "evidence_research").glob("*.py"))
    relatives += [Path(p) for p in ("tests/test_study.py", "tests/test_sampled_pilot.py",
                                   "references/manifest.json", "references/task_literature_v2.json")]
    if sha(CANDIDATE / "references/manifest.json") != UPSTREAM_MANIFEST_PIN:
        raise ValueError("External upstream manifest pin differs")
    acquisition = json.loads((CANDIDATE / "references/manifest.json").read_text(encoding="utf-8"))
    relatives += [Path(row["path"]) for row in acquisition["files"] if "upstream_path" in row]
    before = {p.as_posix(): sha(CANDIDATE / p) for p in relatives}
    for p in relatives:
        target = HERE / "source_snapshot" / p
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CANDIDATE / p, target)
        if sha(target) != before[p.as_posix()]:
            raise ValueError("Source changed during capture")
    if before != {p.as_posix(): sha(CANDIDATE / p) for p in relatives}:
        raise ValueError("Concurrent source changes; do not claim this review is coherent")
    value = {"kind": "read_only_candidate_methodology_snapshot", "files": before,
             "external_upstream_manifest_sha256": UPSTREAM_MANIFEST_PIN,
             "scope": "Candidate sampler/control contracts only; no actual research result or hidden live data"}
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_sha256": sha(path), "files": len(before)}))


if __name__ == "__main__":
    main()
