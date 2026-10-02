"""Verify public worktree bytes against externally pinned exact commit Git blobs."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[2] / "_er6"
COMMIT = "0be5988f4760263122188ef31e7f8dfba5ccea47"
PREFIX = "versions/v6-development/"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", choices=("before", "after"), required=True)
    label = parser.parse_args().label
    path = HERE / f"source-{label}.json"
    if path.exists():
        raise FileExistsError("Preserve source receipt; do not repeat")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=CHECKOUT, capture_output=True, check=True).stdout.decode().strip()
    if head != COMMIT:
        raise ValueError("Fresh checkout is not the approved exact commit")
    listing = subprocess.run(["git", "ls-tree", "-r", "HEAD", "--", "versions/v6-development"], cwd=CHECKOUT,
                             capture_output=True, check=True).stdout.decode("utf-8")
    files = {}
    for row in listing.splitlines():
        header, name = row.split("\t", 1)
        mode, kind, oid = header.split()
        relative = PurePosixPath(name)
        if (kind != "blob" or mode not in ("100644", "100755") or not name.startswith(PREFIX)
                or relative.is_absolute() or ".." in relative.parts or "\\" in name
                or any("owner" in part.lower() or "private" in part.lower() or part.lower() == "runs" for part in relative.parts)):
            raise ValueError("Unexpected public tree path or type")
        file = CHECKOUT / Path(*relative.parts)
        if file.is_symlink() or not file.resolve().is_relative_to(CHECKOUT.resolve()):
            raise ValueError("Public tree path leaves checkout")
        raw = file.read_bytes()
        actual = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        if actual != oid:
            raise ValueError("Worktree bytes differ from exact public Git blob")
        files[name] = {"git_blob_sha1": oid, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    value = {"commit": head, "checkout": str(CHECKOUT), "label": label,
             "files": files, "tracked_version_files": len(files),
             "outside_original_project_reads": 0, "scope": "Public tracked source/proof bytes; runtime acquisition and unit outputs are untracked"}
    if label == "after":
        before = json.loads((HERE / "source-before.json").read_text(encoding="utf-8"))
        if before["files"] != files or before["commit"] != head:
            raise ValueError("Public worktree/source changed across independent installation")
        value["public_worktree_unchanged"] = True
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"commit": head, "files": len(files), "label": label, "all_git_blob_bytes_valid": True}))


if __name__ == "__main__":
    main()
