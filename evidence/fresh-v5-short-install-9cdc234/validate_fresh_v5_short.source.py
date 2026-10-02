"""Separate short-path source-install validation; registered sources stay unchanged."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = ROOT.parent / "_er9"
VERSION = CHECKOUT / "versions/v5-development"
OUTPUT = ROOT / "evidence/fresh-v5-short-install-9cdc234"
REVISION = "9cdc234c86d4a532b47be27401e5c43d188d90cc"
BASE_PYTHON = Path("C:/Users/Potato/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe")
PYTHON = VERSION / ".venv/Scripts/python.exe"
SOURCE = ROOT / "work/published-9cdc234-replay"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    path = OUTPUT / name
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2))


def git(checkout):
    return ["git", "-c", f"safe.directory={checkout.as_posix()}", "-C", str(checkout)]


def record(name, command, cwd):
    if (OUTPUT / f"{name}.json").exists():
        raise FileExistsError("Preserve earlier phase receipts")
    start = time.monotonic()
    process = subprocess.run(command, cwd=cwd, capture_output=True)
    logs = []
    for kind, data in (("stdout", process.stdout), ("stderr", process.stderr)):
        path = OUTPUT / f"{name}.{kind}.log"
        with path.open("xb") as stream:
            stream.write(data)
        logs.append({"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    receipt = {"name": name, "command": command, "cwd": str(cwd), "exit_code": process.returncode,
               "seconds": time.monotonic() - start, "logs": logs}
    save(f"{name}.json", receipt)
    print(json.dumps({"phase": name, "exit_code": process.returncode}), flush=True)
    return receipt


def source_manifest():
    actual_revision = subprocess.run(git(CHECKOUT) + ["rev-parse", "HEAD"], capture_output=True, check=True).stdout.decode().strip()
    if actual_revision != REVISION:
        raise ValueError("Published commit differs")
    listing = subprocess.run(git(CHECKOUT) + ["ls-tree", "-r", "-z", REVISION, "versions/v5-development"],
                             capture_output=True, check=True).stdout
    files = []
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        metadata, name = raw.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        relative = PurePosixPath(name.decode("utf-8"))
        if kind != "blob" or mode not in ("100644", "100755") or ".." in relative.parts:
            raise ValueError("Unexpected source tree entry")
        path = CHECKOUT.joinpath(*relative.parts)
        if not path.resolve().is_relative_to(CHECKOUT.resolve()) or path.is_symlink():
            raise ValueError("Source path escaped checkout")
        data = path.read_bytes()
        actual_oid = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        if actual_oid != oid:
            raise ValueError("Source differs from pinned Git blob")
        files.append({"path": relative.as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "git_blob_sha1": oid})
    if not files:
        raise ValueError("No published version files")
    return {"commit": REVISION, "checkout": str(CHECKOUT), "version_root": str(VERSION), "files": files,
            "scope": "Published version tree only; no private owner file was read"}


def prepare():
    if CHECKOUT.exists() or OUTPUT.exists() or not CHECKOUT.resolve().is_relative_to(ROOT.parent.resolve()):
        raise FileExistsError("Use a new short workspace and preserve prior proof")
    OUTPUT.mkdir(parents=True)
    previous = ROOT / "evidence/fresh-v5-install-9cdc234"
    save("previous-failure-anchor.json", {"files": [{"path": str(previous / name), "sha256": sha(previous / name)}
         for name in ("result.json", "full-suite.json", "full-suite.stderr.log")], "preserved": True})
    head = subprocess.run(git(SOURCE) + ["rev-parse", "HEAD"], capture_output=True, check=True).stdout.decode().strip()
    if head != REVISION:
        raise ValueError("Public source checkout commit differs")
    steps = [record("clone", ["git", "-c", f"safe.directory={SOURCE.as_posix()}", "clone", "--no-hardlinks", "--no-checkout", str(SOURCE), str(CHECKOUT)], ROOT),
             record("sparse", git(CHECKOUT) + ["sparse-checkout", "set", "versions/v5-development"], CHECKOUT),
             record("checkout", git(CHECKOUT) + ["checkout", "--detach", REVISION], CHECKOUT)]
    if any(step["exit_code"] for step in steps):
        raise RuntimeError("New checkout preparation failed")
    save("source-manifest.before.json", source_manifest())
    record("venv", [str(BASE_PYTHON), "-m", "venv", str(VERSION / ".venv")], VERSION)


def fetch(name="upstream-fetch"):
    record(name, [str(PYTHON), "-X", "utf8", "-B", "scripts/fetch_upstream.py"], VERSION)


def validate():
    acquisition = OUTPUT / "upstream-fetch-authorized.json"
    if not acquisition.exists():
        acquisition = OUTPUT / "upstream-fetch.json"
    if json.loads(acquisition.read_text(encoding="utf-8"))["exit_code"]:
        raise RuntimeError("Pinned upstream must be acquired before tests")
    phases = []
    for name, arguments in (("upstream-offline", ["scripts/fetch_upstream.py", "--offline"]),
                            ("full-suite", ["-m", "unittest", "discover", "-s", "tests", "-v"]),
                            ("cli-help", ["-m", "evidence_research.study", "--help"])):
        phases.append(record(name, [str(PYTHON), "-X", "utf8", "-B", *arguments], VERSION))
    before = json.loads((OUTPUT / "source-manifest.before.json").read_text(encoding="utf-8"))
    after = source_manifest()
    save("source-manifest.after.json", after)
    if before != after:
        raise ValueError("Published sources changed during validation")
    status = subprocess.run(git(CHECKOUT) + ["status", "--porcelain"], capture_output=True, check=True).stdout
    save("result.json", {"commit": REVISION, "valid": all(phase["exit_code"] == 0 for phase in phases),
         "phases": phases, "git_working_tree_clean": not status, "source_bytes_unchanged": True,
         "independent_venv": True, "include_system_site_packages": False,
         "editable_distribution_install_performed": False, "actual_model_calls": 0,
         "research_task_experiments": 0, "private_owner_files_read": 0, "goal_complete": False,
         "scope": "Short-path fresh public source-run installation and full suite. Real CPU unit fixtures are contract tests; no research trial or superiority claim."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "fetch", "fetch-authorized", "validate"))
    args = parser.parse_args()
    {"prepare": prepare, "fetch": fetch, "fetch-authorized": lambda: fetch("upstream-fetch-authorized"), "validate": validate}[args.phase]()
