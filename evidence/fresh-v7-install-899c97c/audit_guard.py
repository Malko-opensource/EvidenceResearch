"""Prospective fresh-public unit/replay guard; not an OS sandbox."""
import atexit
import json
import os
from pathlib import Path
import shlex
import sys

checkout=Path(os.environ["ER_FRESH_CHECKOUT"]).resolve()
proof=Path(os.environ["ER_PREP_PROOF"]).resolve()
temporary=Path(os.environ["ER_FIXTURE_TMP"]).resolve()
original=Path(os.environ["ER_ORIGINAL_PROJECT"]).resolve()
runtime=Path(os.environ["ER_RUNTIME_ROOT"]).resolve()
receipt=Path(os.environ["ER_GUARD_RECEIPT"])
counts={"original_project_access_attempts":0,"outside_allowed_root_access_attempts":0,
        "unknown_run_access_attempts":0,"nonfixture_process_attempts":0,
        "network_events":0,"allowed_cpu_fixture_subprocesses":0}


def unquote(word):
    return word[1:-1] if len(word)>=2 and word[0]==word[-1]=='"' else word


def audit(event,args):
    if event in ("open","os.listdir","os.scandir") and args and isinstance(args[0],(str,bytes)):
        path=Path(args[0]).resolve()
        allowed=any(path.is_relative_to(base) for base in (checkout,proof,temporary,runtime))
        if path.is_relative_to(original) and not path.is_relative_to(proof):
            counts["original_project_access_attempts"]+=1
            raise AssertionError("Existing EvidenceResearch source/actual/owner records are forbidden")
        if not allowed:
            counts["outside_allowed_root_access_attempts"]+=1
            raise AssertionError("Only fresh checkout/proof/synthetic temp/runtime allowed")
        runs=checkout/"versions/v7-development/runs"
        if path.is_relative_to(runs):
            parts=path.relative_to(runs).parts
            if not(parts and(parts[0]=="tf" or parts[0].startswith("c6-fixture-only-"))):
                counts["unknown_run_access_attempts"]+=1
                raise AssertionError("Only named synthetic release runs permitted")
    elif event=="subprocess.Popen":
        executable,argv,cwd=args[:3]
        words=[str(v) for v in argv] if isinstance(argv,(list,tuple)) else shlex.split(str(argv),posix=False)
        words=[unquote(v) for v in words];program=executable or(words[0] if words else "")
        def fixture_argument(flag):
            return flag in words and words.index(flag)+1<len(words) and Path(words[words.index(flag)+1]).resolve().is_relative_to(temporary)
        if(Path(program).resolve()==Path(sys.executable).resolve() and words[1:3]==["-m","evidence_research.tasks"]
                and cwd is not None and Path(cwd).resolve().is_relative_to(temporary)
                and fixture_argument("--spec") and fixture_argument("--run-dir")):
            counts["allowed_cpu_fixture_subprocesses"]+=1;return
        counts["nonfixture_process_attempts"]+=1
        raise AssertionError("Credential/model/Git/network/other subprocess forbidden in engineering tests")
    elif event.startswith("socket."):
        counts["network_events"]+=1
        raise AssertionError("Network forbidden in engineering tests")


sys.addaudithook(audit)
@atexit.register
def save():
    receipt.write_text(json.dumps({"counts":counts,"scope":"Parent Python open/list/scandir/process/network hook permits new checkout/proof/explicit synthetic temp and Python runtime. The one allowed CPU child replaces PYTHONPATH and is outside this hook; fixed runner over registered tiny synthetic arrays is trusted. This is not an OS sandbox or a global filesystem proof."},indent=2)+"\n",encoding="utf-8")
