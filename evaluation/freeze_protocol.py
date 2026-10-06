"""Freeze or check the small preregistered feasibility artifact set."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "frozen_manifest.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked_files():
    files = [ROOT / name for name in ("protocol.json", "PROTOCOL.ko.md", "task.py",
                                     "fixed_validator.py", "freeze_protocol.py", "prepare.py", "check.py")]
    files.extend(path for path in (ROOT / "tasks").rglob("*") if path.is_file()
                 and "__pycache__" not in path.parts)
    return sorted(files)


if __name__ == "__main__":
    if sys.argv[1:] == ["--freeze"]:
        if MANIFEST.exists():
            raise SystemExit("Manifest already exists; changed conditions require a new protocol")
        manifest = {"protocol_id": "csv-feasibility-20261004-v1", "algorithm": "sha256",
                    "files": {path.relative_to(ROOT).as_posix(): digest(path) for path in tracked_files()}}
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "manifest": str(MANIFEST), "files": len(manifest["files"])}))
    elif sys.argv[1:] == ["--check"]:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        invalid = [name for name, expected in manifest["files"].items()
                   if not (ROOT / name).is_file() or digest(ROOT / name) != expected]
        print(json.dumps({"ok": not invalid, "invalid": invalid}))
        raise SystemExit(bool(invalid))
    else:
        raise SystemExit("Usage: freeze_protocol.py --freeze | --check")
