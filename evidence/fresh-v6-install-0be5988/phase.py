"""Record one fresh-public-checkout phase, reusing only exact successful receipt."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--packaging-tools-root")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command or not args.name.replace("-", "").isalnum():
        raise ValueError("A safe phase name and exact command are required")
    receipt = HERE / f"{args.name}.json"
    stdout = HERE / f"{args.name}.stdout.log"
    stderr = HERE / f"{args.name}.stderr.log"
    cwd = str(Path(args.cwd).resolve())
    if receipt.exists():
        prior = json.loads(receipt.read_text(encoding="utf-8"))
        if (prior["command"] != command or prior["cwd"] != cwd or prior["exit_code"] != 0
                or prior.get("packaging_tools_root") != args.packaging_tools_root
                or sha(stdout) != prior["stdout_sha256"] or sha(stderr) != prior["stderr_sha256"]):
            raise ValueError("Prior failure/conditions need a separately named recovery phase")
        print(json.dumps({"phase": args.name, "reused_without_execution": True}))
        return
    if stdout.exists() or stderr.exists():
        raise FileExistsError("Unknown prior phase remains; no automatic repetition")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    if args.packaging_tools_root:
        environment["PYTHONPATH"] = str(Path(args.packaging_tools_root).resolve())
    started = time.monotonic()
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True)
    elapsed = time.monotonic() - started
    stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
    value = {"phase": args.name, "command": command, "cwd": cwd, "exit_code": result.returncode,
             "seconds": elapsed, "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
             "packaging_tools_root": args.packaging_tools_root,
             "scope": "Fresh public exact-commit installation/control tests; no new research/model/publication"}
    receipt.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"phase": args.name, "exit_code": result.returncode, "seconds": elapsed}), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
