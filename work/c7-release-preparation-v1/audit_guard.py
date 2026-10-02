"""Externally controlled c7 engineering guard; no live research."""
import atexit, json, os, shlex, sys
from pathlib import Path
release=Path(os.environ["ER_RELEASE_ROOT"]).resolve()
project=Path(os.environ["ER_PROJECT_ROOT"]).resolve()
temporary=Path(os.environ["ER_FIXTURE_TMP"]).resolve()
proof=Path(os.environ["ER_PROOF_ROOT"]).resolve()
receipt=Path(os.environ["ER_AUDIT_GUARD_PATH"])
counts={"other_project_or_version_access_attempts":0,"live_study_access_attempts":0,
        "nonfixture_process_attempts":0,"network_events":0,"allowed_cpu_fixture_subprocesses":0}
def fixture_run(path):
    try: parts=path.relative_to(release/"runs").parts
    except ValueError: return False
    return bool(parts and (parts[0]=="tf" or parts[0].startswith("c6-fixture-only-")))
def unquote(word):
    return word[1:-1] if len(word)>=2 and word[0]==word[-1]=='"' else word
def audit(event,args):
    if event=="open" and isinstance(args[0],(str,bytes)):
        path=Path(args[0]).resolve()
        allowed=any(path.is_relative_to(base) for base in (release,temporary,proof))
        if path.is_relative_to(project) and not allowed:
            counts["other_project_or_version_access_attempts"]+=1
            raise AssertionError("Other source versions and original artifacts are forbidden")
        if path.is_relative_to(release/"runs") and not fixture_run(path):
            counts["live_study_access_attempts"]+=1
            raise AssertionError("Only named synthetic test runs are allowed")
    elif event=="subprocess.Popen":
        executable,argv,cwd=args[:3]
        words=[str(x) for x in argv] if isinstance(argv,(list,tuple)) else shlex.split(str(argv),posix=False)
        words=[unquote(x) for x in words]
        program=executable or (words[0] if words else "")
        def fixture_argument(flag):
            return flag in words and words.index(flag)+1<len(words) and Path(words[words.index(flag)+1]).resolve().is_relative_to(temporary)
        if (Path(program).resolve()==Path(sys.executable).resolve()
            and words[1:3]==["-m","evidence_research.tasks"] and cwd is not None
            and Path(cwd).resolve().is_relative_to(temporary)
            and fixture_argument("--spec") and fixture_argument("--run-dir")):
            counts["allowed_cpu_fixture_subprocesses"]+=1
            return
        counts["nonfixture_process_attempts"]+=1
        raise AssertionError("Only the exact standalone deterministic CPU fixture is allowed")
    elif event.startswith("socket."):
        counts["network_events"]+=1
        raise AssertionError("Network is forbidden during engineering tests")
sys.addaudithook(audit)
@atexit.register
def save():
    receipt.write_text(json.dumps({"counts":counts,
        "scope":"Parent Python audit hook covers this workspace except candidate/proof/synthetic temp; runtime files elsewhere remain readable. The allowed archived CPU child replaces PYTHONPATH and is not covered by this hook. This is not an OS sandbox or a filesystem-wide read proof."},indent=2)+"\n",encoding="utf-8")
