"""Own-v9 CLI/reference/contract guard. No provider or CPU child process."""
import atexit
import json
import os
from pathlib import Path
import sys

release = Path(os.environ["ER_RELEASE_ROOT"]).resolve()
project = Path(os.environ["ER_PROJECT_ROOT"]).resolve()
temporary = Path(os.environ["ER_FIXTURE_TMP"]).resolve()
proof = Path(os.environ["ER_PROOF_ROOT"]).resolve()
receipt = Path(os.environ["ER_AUDIT_GUARD_PATH"])
counts = {"other_project_or_version_access_attempts": 0, "live_study_access_attempts": 0,
          "credential_path_attempts": 0, "process_attempts": 0, "network_events": 0, "source_or_outside_write_attempts": 0}


def fixture_run(path):
    try:
        parts = path.relative_to(release / "runs").parts
    except ValueError:
        return False
    return bool(parts and parts[0] in ("tf", "hf"))


def writable(path):
    return path.is_relative_to(temporary) or path.is_relative_to(proof) or fixture_run(path)


def audit(event, args):
    if event in ("open", "os.listdir", "os.scandir") and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if event == "open":
            mode = args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 else 0
            writes = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
            if writes and not writable(path):
                counts["source_or_outside_write_attempts"] += 1
                raise AssertionError("Source/runtime and outside namespaces are read only")
        allowed = any(path.is_relative_to(root) for root in (release, temporary, proof))
        if path.is_relative_to(project) and not allowed:
            counts["other_project_or_version_access_attempts"] += 1
            raise AssertionError("Other versions and original evidence are forbidden")
        if path.is_relative_to(release / "runs") and not fixture_run(path):
            counts["live_study_access_attempts"] += 1
            raise AssertionError("Only explicit synthetic tf/hf callback test namespaces are allowed")
        home = os.environ.get("USERPROFILE")
        private = tuple(Path(home) / name for name in (".aws", ".ssh", ".codex/auth.json")) if home else ()
        if any(path == root.resolve() or path.is_relative_to(root.resolve()) for root in private):
            counts["credential_path_attempts"] += 1
            raise AssertionError("Credential namespaces are forbidden")
    elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime", "os.truncate") and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        container = event == "os.mkdir" and path == release / "runs"
        if not writable(path) and not container:
            counts["source_or_outside_write_attempts"] += 1
            raise AssertionError("Only explicit new proof/temp/synthetic namespaces may change")
    elif event in ("os.rename", "os.link", "os.symlink"):
        paths = [Path(os.fsdecode(p)).resolve() for p in args[:2] if isinstance(p, (str, bytes, os.PathLike))]
        if len(paths) != 2 or not all(writable(p) for p in paths):
            counts["source_or_outside_write_attempts"] += 1
            raise AssertionError("Source/outside rename or link is forbidden")
    elif event == "subprocess.Popen" or event.startswith("os.exec") or event in ("os.system", "os.posix_spawn", "os.spawn"):
        counts["process_attempts"] += 1
        raise AssertionError("This selected CLI/contract inventory permits no provider or CPU subprocess")
    elif event.startswith("socket."):
        counts["network_events"] += 1
        raise AssertionError("Network is forbidden during own release verification")


sys.addaudithook(audit)


@atexit.register
def save():
    receipt.write_text(json.dumps({"counts": counts,
        "scope": "Python hook covers workspace open/list/scandir, explicit credential namespaces and process/network events. Runtime paths elsewhere remain readable; not an OS sandbox or all-sibling read proof. Selected fixtures use only in-process deterministic public CPU components."}, indent=2) + "\n", encoding="utf-8")
