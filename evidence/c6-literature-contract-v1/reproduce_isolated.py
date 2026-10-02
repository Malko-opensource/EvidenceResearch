"""Verify that the captured contract fixtures need neither ignored c6 nor v5."""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DESTINATION = ROOT / "work/c6-lit-iso-v1"
PIN = "db6f9f083cdbbae9cbe7b5b995368a566d8e75ad7bccfce0b85fc984a152b01d"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if DESTINATION.exists():
        raise FileExistsError("Keep prior isolated proof; do not overwrite it")
    if sha(HERE / "source-manifest.json") != PIN:
        raise ValueError("Externally fixed manifest pin differs")
    DESTINATION.mkdir(parents=True)
    for name in ("source-manifest.json", "reproduce.py"):
        shutil.copyfile(HERE / name, DESTINATION / name)
    shutil.copytree(HERE / "source_snapshot", DESTINATION / "source_snapshot")
    reads = {"original_project_reads": 0, "private_owner_reads": 0, "subprocess_events": 0, "network_events": 0}
    def guard(event, args):
        if event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn"):
            reads["subprocess_events"] += 1
            raise RuntimeError("No subprocess is allowed in isolated contract replay")
        if event in ("socket.connect", "socket.bind", "socket.getaddrinfo"):
            reads["network_events"] += 1
            raise RuntimeError("No network is allowed in isolated contract replay")
        if event not in ("open", "os.listdir", "os.scandir") or not args or not isinstance(args[0], (str, bytes)):
            return
        path = Path(args[0]).resolve()
        if path.is_relative_to(ROOT) and not path.is_relative_to(DESTINATION):
            reads["original_project_reads"] += 1
            raise RuntimeError("Captured replay read original project: " + str(path))
        if "owner-development-data" in path.parts or path.name.endswith("-owner.json") or path.name == "owner-request.json":
            reads["private_owner_reads"] += 1
            raise RuntimeError("No private original owner rows or request may be opened")
    sys.addaudithook(guard)
    sys.argv = [str(DESTINATION / "reproduce.py"), "--manifest-sha256", PIN]
    runpy.run_path(str(DESTINATION / "reproduce.py"), run_name="__main__")
    result_path = DESTINATION / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    proof = {"kind": "isolated_candidate_contract_reproduction", "result": result,
        "result_sha256": sha(result_path), "guards": reads,
        "scope": "Physical copy uses only public source snapshot. No original project, live/frozen runs, model or CPU research."}
    (DESTINATION / "isolation-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, ensure_ascii=False))


if __name__ == "__main__":
    main()
