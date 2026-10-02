"""Check staged publication bytes using one read-only Git object process.

Path/private/credential policy and core manifest fields match release_check.py.
NUL-delimited index paths never become object-protocol inputs; only validated
object IDs are sent to cat-file. No staged file or credential match is printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


PRIVATE_PARTS = (".venv", ".runtime", "private-evaluation", "model-public", "__pycache__")
PRIVATE_NAMES = ("auth.json", ".env")
PATTERNS = (re.compile(rb"gh[pousr]_[A-Za-z0-9]{25,}"),
            re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{30,}"),
            re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"))
SCOPE = "pattern check of staged paths; not a proof that arbitrary secrets cannot exist"


class ReleaseCheckError(RuntimeError):
    """Controlled metadata-only error; never echo Git stderr or blob content."""


def parse_index_records(data: bytes) -> list[dict]:
    if data and not data.endswith(b"\0"):
        raise ReleaseCheckError("NUL index inventory is incomplete")
    entries = []
    for record in data.split(b"\0"):
        if not record:
            continue
        metadata, separator, raw_name = record.partition(b"\t")
        if not separator:
            raise ReleaseCheckError("Index entry header is malformed")
        match = re.fullmatch(rb"([0-7]{6}) ([0-9a-f]{40}|[0-9a-f]{64}) ([0-3])", metadata)
        if not match or not raw_name or b"\0" in raw_name:
            raise ReleaseCheckError("Index entry identity is malformed")
        try:
            name = raw_name.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReleaseCheckError("Index filename is not valid UTF-8") from exc
        entries.append({"path": name, "mode": match[1].decode("ascii"),
                        "oid": match[2].decode("ascii"), "stage": int(match[3])})
    return entries


def read_exact(stream, size: int) -> bytes:
    pieces = []
    remaining = size
    while remaining:
        piece = stream.read(min(remaining, 1 << 20))
        if not piece:
            raise ReleaseCheckError("Git object body ended before its declared size")
        pieces.append(piece)
        remaining -= len(piece)
    return b"".join(pieces)


def read_batch_blob(stream, oid: str) -> bytes:
    header = stream.readline(1024)
    match = re.fullmatch(rb"([0-9a-f]{40}|[0-9a-f]{64}) blob ([0-9]+)\n", header)
    if not match or match[1].decode("ascii") != oid:
        raise ReleaseCheckError("Git object response identity/type/header is invalid")
    size = int(match[2])
    data = read_exact(stream, size)
    if stream.read(1) != b"\n":
        raise ReleaseCheckError("Git object body terminator is invalid")
    object_hash = hashlib.sha1 if len(oid) == 40 else hashlib.sha256
    if object_hash(b"blob " + str(size).encode("ascii") + b"\0" + data).hexdigest() != oid:
        raise ReleaseCheckError("Git object body differs from its requested identity")
    return data


def git_command(root: Path) -> list[str]:
    return ["git", "-c", f"safe.directory={root.as_posix()}", "-c",
            f"core.excludesFile={(root / '.gitignore').as_posix()}"]


def git_index(root: Path) -> bytes:
    env = os.environ.copy(); env["GIT_OPTIONAL_LOCKS"] = "0"
    process = subprocess.run(git_command(root) + ["ls-files", "--stage", "-z"],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, check=False)
    if process.returncode:
        raise ReleaseCheckError("Read-only staged index inventory failed")
    return process.stdout


class GitBatch:
    def __init__(self, root: Path):
        env = os.environ.copy(); env["GIT_OPTIONAL_LOCKS"] = "0"
        self.process = subprocess.Popen(git_command(root) + ["cat-file", "--batch"],
            cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=env)
        self.requests = 0

    def get(self, oid: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid):
            raise ReleaseCheckError("Invalid staged object ID")
        try:
            self.process.stdin.write(oid.encode("ascii") + b"\n")
            self.process.stdin.flush()
            self.requests += 1
            return read_batch_blob(self.process.stdout, oid)
        except (BrokenPipeError, OSError) as exc:
            raise ReleaseCheckError("Git object stream failed") from exc

    def close(self, *, abort=False):
        if abort:
            self.process.kill()  # Only this helper's own object-reader child.
        elif self.process.stdin:
            self.process.stdin.close()
        code = self.process.wait()
        if self.process.stdout:
            self.process.stdout.close()
        if not abort and code:
            raise ReleaseCheckError("Git object reader exited unsuccessfully")


def scan_entries(root: Path, entries: list[dict], read_blob) -> dict:
    rejected, manifest = [], []
    seen = set()
    for entry in entries:
        name = entry["path"]
        if entry["stage"] != 0 or name in seen:
            rejected.append({"path": name, "reason": "conflicted or duplicate staged index entry"})
            continue
        seen.add(name)
        path = root / name
        if not path.resolve().is_relative_to(root):
            rejected.append({"path": name, "reason": "outside publication workspace"})
            continue
        if any(part in PRIVATE_PARTS for part in Path(name).parts) or Path(name).name in PRIVATE_NAMES:
            rejected.append({"path": name, "reason": "private runtime/auth/evaluation file"})
            continue
        if entry["mode"] not in ("100644", "100755") or path.is_symlink():
            rejected.append({"path": name, "reason": "unsupported staged file type or symlink"})
            continue
        data = read_blob(entry["oid"])
        try:
            working = path.read_bytes()
        except OSError:
            rejected.append({"path": name, "reason": "staged working file is missing or unreadable"})
        else:
            if working != data:
                rejected.append({"path": name, "reason": "working file changed after staging; restage and verify"})
        if any(pattern.search(data) for pattern in PATTERNS):
            rejected.append({"path": name, "reason": "credential pattern detected; value withheld"})
        manifest.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return {"valid": bool(entries) and not rejected, "file_count": len(entries),
        "credential_values_printed": False, "rejected": rejected,
        "manifest": manifest, "scope": SCOPE}


def scan(root: Path) -> tuple[dict, dict]:
    root = root.resolve(); start = time.perf_counter()
    before = git_index(root); entries = parse_index_records(before)
    batch = GitBatch(root)
    try:
        result = scan_entries(root, entries, batch.get)
        batch.close()
    except BaseException:
        batch.close(abort=True)
        raise
    after = git_index(root)
    if before != after:
        result["rejected"].append({"path": "<index>", "reason": "staged index changed during verification"})
        result["valid"] = False
    # Detect changes occurring after an early staged file was checked. Compare
    # the exact bytes again against its object ID, without more Git processes.
    entries_by_name = {item["path"]: item for item in entries if item["stage"] == 0}
    for row in result["manifest"]:
        path = root / row["path"]
        try:
            data = path.read_bytes()
            entry = entries_by_name[row["path"]]
            function = hashlib.sha1 if len(entry["oid"]) == 40 else hashlib.sha256
            unchanged = function(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest() == entry["oid"]
        except OSError:
            unchanged = False
        if not unchanged and not any(item["path"] == row["path"] for item in result["rejected"]):
            result["rejected"].append({"path": row["path"], "reason": "working file changed during verification"})
            result["valid"] = False
    receipt = {"schema_version": "batch-release-check-execution-1", "root": str(root),
        "index_before_sha256": hashlib.sha256(before).hexdigest(),
        "index_after_sha256": hashlib.sha256(after).hexdigest(),
        "index_stable": before == after, "git_index_processes": 2, "git_object_processes": 1,
        "blob_requests": batch.requests, "staged_blob_bytes": sum(row["bytes"] for row in result["manifest"]),
        "wall_seconds": time.perf_counter() - start, "credential_values_printed": False,
        "git_mutation": False, "model_calls": 0,
        "scope": "Publication scanner runtime only; no research performance/model-cost claim"}
    return result, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv); root = args.root.resolve()
    output = (args.output or root / "evidence/release-check-batch.json").resolve()
    receipt_path = (args.receipt or output.with_suffix(".receipt.json")).resolve()
    if not output.is_relative_to(root) or not receipt_path.is_relative_to(root):
        raise ReleaseCheckError("Output must stay within the named publication workspace")
    if output.exists() or receipt_path.exists() or output == receipt_path:
        raise ReleaseCheckError("Preserve prior scan evidence; use fresh output paths")
    staged_names = {entry["path"] for entry in parse_index_records(git_index(root))}
    if output.relative_to(root).as_posix() in staged_names or receipt_path.relative_to(root).as_posix() in staged_names:
        raise ReleaseCheckError("Scanner output is staged; choose an untracked evidence path")
    result, receipt = scan(root)
    output.parent.mkdir(parents=True, exist_ok=True); receipt_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    receipt["output"] = {"path":str(output),"sha256":hashlib.sha256(output.read_bytes()).hexdigest()}
    receipt["preflight_index_processes"] = 1
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"valid":result["valid"],"file_count":result["file_count"],"credential_values_printed":False,
        "rejected_count":len(result["rejected"]),"rejected_preview":result["rejected"][:8],"wall_seconds":receipt["wall_seconds"]},ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ReleaseCheckError, OSError, ValueError, KeyError):
        print(json.dumps({"valid":False,"credential_values_printed":False,
            "reason":"Publication verification failed; staged state or protocol requires reconciliation"}))
        sys.exit(2)
