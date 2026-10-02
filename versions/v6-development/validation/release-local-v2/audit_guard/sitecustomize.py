"""Unit audit with exact synthetic fixture paths and Windows subprocess syntax."""
import atexit
import json
import os
from pathlib import Path
import shlex
import sys

release = Path(os.environ["ER_RELEASE_ROOT"]).resolve()
project = Path(os.environ["ER_PROJECT_ROOT"]).resolve()
fixture_tmp = Path(os.environ["ER_FIXTURE_TMP"]).resolve()
receipt = Path(os.environ["ER_AUDIT_GUARD_PATH"])
counts = {"main_or_other_version_reads": 0, "live_private_owner_access_attempts": 0,
          "actual_model_processes": 0, "network_events": 0, "synthetic_python_fixture_subprocesses": 0}


def synthetic_run(path):
    try:
        parts = path.relative_to(release / "runs").parts
    except ValueError:
        return False
    return bool(parts and (parts[0] == "tf" or parts[0].startswith("c6-fixture-only-")))


def unquote(word):
    return word[1:-1] if len(word) >= 2 and word[0] == word[-1] == '"' else word


def audit(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        if path.is_relative_to(project) and not path.is_relative_to(release) and not path.is_relative_to(fixture_tmp):
            counts["main_or_other_version_reads"] += 1
            raise AssertionError("No other project version or original artifacts")
        if (path.is_relative_to(project / "runs")
                or path.is_relative_to(release / "runs") and not synthetic_run(path)):
            counts["live_private_owner_access_attempts"] += 1
            raise AssertionError("No live owner or actual study artifacts")
    elif event == "subprocess.Popen":
        executable, argv, cwd = args[:3]
        words = [str(x) for x in argv] if isinstance(argv, (list, tuple)) else shlex.split(str(argv), posix=False)
        words = [unquote(x) for x in words]
        program = executable or (words[0] if words else "")
        def fixture_argument(flag):
            return flag in words and Path(words[words.index(flag) + 1]).resolve().is_relative_to(fixture_tmp)
        if (Path(program).resolve() == Path(sys.executable).resolve()
                and words[1:3] == ["-m", "evidence_research.tasks"]
                and cwd is not None and Path(cwd).resolve().is_relative_to(fixture_tmp)
                and fixture_argument("--spec") and fixture_argument("--run-dir")):
            counts["synthetic_python_fixture_subprocesses"] += 1
            return
        counts["actual_model_processes"] += 1
        raise AssertionError("Only exact deterministic standalone unit fixture is permitted")
    elif event.startswith("socket."):
        counts["network_events"] += 1
        raise AssertionError("No network in test process")


sys.addaudithook(audit)


@atexit.register
def save():
    if "unittest" in sys.orig_argv:
        receipt.write_text(json.dumps({"counts": counts,
            "scope": "Synthetic v6/runs/tf, c6-fixture-only temp paths and exact deterministic task subprocess permitted; actual live owner/model/network blocked"}, indent=2) + "\n", encoding="utf-8")
