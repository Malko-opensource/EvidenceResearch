"""Check the staged publication payload without displaying credential matches."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    git = ["git", "-c", f"safe.directory={root.as_posix()}", "-c",
           f"core.excludesFile={(root / '.gitignore').as_posix()}"]
    command = git + ["ls-files", "--cached", "-z"]
    process = subprocess.run(command, cwd=root, capture_output=True, check=True)
    files = [p for p in process.stdout.decode("utf-8").split("\0") if p]
    patterns = [re.compile(rb"gh[pousr]_[A-Za-z0-9]{25,}"),
                re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{30,}"),
                re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]
    rejected, manifest = [], []
    for name in files:
        path = root / name
        if not path.resolve().is_relative_to(root):
            rejected.append({"path": name, "reason": "outside publication workspace"})
            continue
        if any(part in (".venv", ".runtime", "private-evaluation", "model-public", "__pycache__") for part in Path(name).parts) or Path(name).name in ("auth.json", ".env"):
            rejected.append({"path": name, "reason": "private runtime/auth/evaluation file"})
            continue
        data = subprocess.run(git + ["show", ":" + name], cwd=root,
                              capture_output=True, check=True).stdout
        if path.read_bytes() != data:
            rejected.append({"path": name, "reason": "working file changed after staging; restage and verify"})
        if any(pattern.search(data) for pattern in patterns):
            rejected.append({"path": name, "reason": "credential pattern detected; value withheld"})
        manifest.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    result = {"valid": bool(files) and not rejected, "file_count": len(files),
              "credential_values_printed": False, "rejected": rejected,
              "manifest": manifest,
              "scope": "pattern check of staged paths; not a proof that arbitrary secrets cannot exist"}
    output = root / "evidence" / "release-check.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"valid": result["valid"], "file_count": len(files),
                      "credential_values_printed": False, "rejected_count": len(rejected),
                      "rejected_preview": rejected[:8]}, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
