"""Test-process evidence guard. Synthetic unit fixtures remain permitted."""
import atexit
import json
import os
from pathlib import Path
import sys

release = Path(os.environ["ER_RELEASE_ROOT"]).resolve()
project = Path(os.environ["ER_PROJECT_ROOT"]).resolve()
fixture_tmp = Path(os.environ["ER_FIXTURE_TMP"]).resolve()
receipt = Path(os.environ["ER_AUDIT_GUARD_PATH"])
initial_pid = os.getpid()
counts = {"main_or_other_version_reads": 0, "live_private_owner_reads": 0,
          "actual_model_processes": 0, "network_events": 0, "synthetic_python_fixture_subprocesses": 0}


def audit(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        if path.is_relative_to(project) and not path.is_relative_to(release) and not path.is_relative_to(fixture_tmp):
            counts["main_or_other_version_reads"] += 1
            raise AssertionError("New release tests may not read original or other-version project artifacts")
        if path.is_relative_to(release / "runs") or path.is_relative_to(project / "runs"):
            counts["live_private_owner_reads"] += 1
            raise AssertionError("No live research/private owner data")
    elif event == "subprocess.Popen":
        executable, argv = args[0], args[1]
        words = [str(x) for x in argv] if isinstance(argv, (list, tuple)) else [str(argv)]
        if (Path(executable).resolve() == Path(sys.executable).resolve()
                and words[1:3] == ["-m", "evidence_research.tasks"]):
            counts["synthetic_python_fixture_subprocesses"] += 1
            return
        counts["actual_model_processes"] += 1
        raise AssertionError("Only the declared deterministic unit fixture subprocess is permitted")
    elif event.startswith("socket."):
        counts["network_events"] += 1
        raise AssertionError("No network in unit verification")


sys.addaudithook(audit)


@atexit.register
def save():
    # The fixture child shares environment variables; preserve the parent receipt.
    if os.getpid() == initial_pid and "unittest" in sys.orig_argv:
        receipt.write_text(json.dumps({"counts": counts, "scope": "Unit test process; no research model/trials, fixture CPU subprocess explicitly permitted"}, indent=2) + "\n", encoding="utf-8")
