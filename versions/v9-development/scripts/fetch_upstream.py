"""Acquire the pinned public source; verify bytes before trusting or writing it."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import urllib.parse
import urllib.request


def verify(data: bytes, entry: dict) -> None:
    blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    if (len(data) != entry["bytes"]
            or hashlib.sha256(data).hexdigest() != entry["sha256"]
            or hashlib.sha1(blob).hexdigest() != entry["git_blob_sha1"]):
        raise ValueError(f"Source hash mismatch: {entry['upstream_path']}")


def acquire(root: Path, *, offline: bool = False) -> dict:
    root = root.resolve()
    manifest = json.loads((root / "references" / "manifest.json").read_text(encoding="utf-8"))
    if manifest["upstream_repo"] != "https://github.com/SamuelSchmidgall/AgentLaboratory":
        raise ValueError("Unexpected upstream repository")
    commit = manifest["upstream_commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Expected a pinned Git commit")
    snapshot = root / "references" / "upstream" / f"AgentLaboratory-{commit}"
    verified, downloaded = [], []
    entries = [entry for entry in manifest["files"] if "upstream_path" in entry]
    if not entries:
        raise ValueError("No source entries in manifest")
    for entry in entries:
        relative = PurePosixPath(entry["upstream_path"])
        if relative.is_absolute() or ".." in relative.parts or "\\" in entry["upstream_path"]:
            raise ValueError("Unsafe upstream path")
        destination = (snapshot / Path(*relative.parts)).resolve()
        if not destination.is_relative_to(snapshot.resolve()):
            raise ValueError("Source path leaves the snapshot")
        expected = (root / entry["path"]).resolve()
        if destination != expected:
            raise ValueError("Manifest source paths disagree")
        if destination.exists():
            verify(destination.read_bytes(), entry)
        else:
            if offline:
                raise FileNotFoundError(f"Missing pinned source: {entry['upstream_path']}")
            url = ("https://raw.githubusercontent.com/SamuelSchmidgall/AgentLaboratory/"
                   + commit + "/" + urllib.parse.quote(relative.as_posix(), safe="/"))
            request = urllib.request.Request(url, headers={"User-Agent": "EvidenceResearch-source-acquisition"})
            with urllib.request.urlopen(request, timeout=60) as response:
                if not response.geturl().startswith("https://raw.githubusercontent.com/SamuelSchmidgall/AgentLaboratory/"):
                    raise ValueError("Unexpected source redirect")
                data = response.read(entry["bytes"] + 1)
            verify(data, entry)
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation never replaces an existing or concurrently written source.
            with destination.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            downloaded.append(relative.as_posix())
        verified.append(relative.as_posix())
    return {"valid": True, "upstream_commit": commit, "verified_files": len(verified),
            "downloaded_files": len(downloaded), "snapshot": str(snapshot),
            "executed_upstream_code": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Verify existing source without network access")
    arguments = parser.parse_args()
    print(json.dumps(acquire(Path(__file__).resolve().parents[1], offline=arguments.offline), indent=2))


if __name__ == "__main__":
    main()
