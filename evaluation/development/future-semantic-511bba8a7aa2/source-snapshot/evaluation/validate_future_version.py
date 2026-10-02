"""Archive and check the unregistered future version; never run research models.

The suite contains actual local CPU artifact fixtures and labelled synthetic
model/transport fixtures. Its test counts establish component checks only, not
research improvement, confirmatory evaluation or actual provider usage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FUTURE = ROOT / "work/next-version"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hashes(paths):
    return {str(path.resolve()): digest(path) for path in paths}


def write_once(path, value):
    text = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text: raise ValueError("immutable validation proof differs")
    else: path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    code = sorted((FUTURE / "evidence_research").glob("*.py"))
    tests = sorted((FUTURE / "tests").glob("*.py"))
    helpers = sorted((FUTURE / "scripts").glob("*.py"))
    dependencies = sorted((ROOT / "references/upstream/AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27").glob("*.py"))
    paths = code+tests+helpers+dependencies+[Path(__file__).resolve()]
    before = hashes(paths); main_before = hashes(sorted((ROOT / "evidence_research").glob("*.py")))
    relative = {str(path.relative_to(ROOT)): before[str(path.resolve())] for path in paths}
    bundle = hashlib.sha256(json.dumps(relative, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output = (args.output or ROOT / f"evaluation/development/future-semantic-{bundle[:12]}").resolve()
    if not output.is_relative_to(ROOT): raise ValueError("validation proof must stay inside the independent workspace")
    if output.exists() and any(output.iterdir()): raise FileExistsError("preserve the previous validation; select a fresh proof directory")
    output.mkdir(parents=True); archive = output / "source-snapshot"
    for path in paths:
        target = archive / path.relative_to(ROOT); target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
    # Snapshot fixture literature/config dependencies. No live study or owner
    # holdout data are copied or supplied to a participant.
    for directory in (FUTURE / "examples", FUTURE / "references"):
        if directory.exists():
            for path in directory.rglob("*.json"):
                target=archive / path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    started = time.perf_counter()
    process = subprocess.run(command, cwd=FUTURE, text=True, capture_output=True)
    seconds = time.perf_counter()-started
    (output / "stdout.log").write_text(process.stdout, encoding="utf-8")
    (output / "stderr.log").write_text(process.stderr, encoding="utf-8")
    after=hashes(paths); main_after=hashes([Path(path) for path in main_before])
    count = re.search(r"Ran (\d+) tests", process.stderr)
    result={"source_bundle_sha256":bundle,"source_hashes":before,"source_hashes_after":after,
        "sources_unchanged":before==after,"main_frozen_sources_unchanged":main_before==main_after,
        "main_source_hashes":main_before,"command":command,"cwd":str(FUTURE),"exit_code":process.returncode,
        "checks":int(count.group(1)) if count else None,"execution_seconds":seconds,
        "logs":[{"path":str(output/name),"sha256":digest(output/name)} for name in ("stdout.log","stderr.log")],
        "source_snapshot":str(archive),"actual_model_calls":0,"final_evaluation_executed":False,
        "goal_complete":False,"scope":"component regression/attack fixtures; actual CPU artifacts and explicitly synthetic provider formats, no B/C improvement evidence",
        "reproduce":"Restore source-snapshot files at the same repository-relative paths in a fresh independent workspace, retain the pinned upstream sources and fixture literature, then run the recorded command from work/next-version."}
    write_once(output / "result.json", result)
    if process.returncode or before!=after or main_before!=main_after: raise RuntimeError("validation failed or sources changed; preserve recorded failure")
    print(json.dumps({"proof":str(output / "result.json"),"checks":result["checks"],"model_calls":0,"source_bundle_sha256":bundle}))


if __name__ == "__main__": main()
