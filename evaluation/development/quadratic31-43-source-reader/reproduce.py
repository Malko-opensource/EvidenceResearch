"""Capture guarded re-review and immutable participant-byte comparison.

Only the independent verifier recomputes predictions/metrics. Explicitly deny
provider.complete and the experiment runner; deny private owner-data row files.
"""
from pathlib import Path
import hashlib
import json
import runpy
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    records=[]
    for seed in (31,43):
        for arm in ("B","C"):
            folder=ROOT / f"runs/development/paired-pilot-v4/units/quadratic-seed{seed}/{arm}"
            response=json.loads((folder / "arm-response.json").read_text(encoding="utf-8"))
            paths=[folder / name for name in ("report.txt" if arm=="B" else "report.md","research_report.json","arm-response.json","independent-resource-audit.json","report-review.json","companion-review.json")]
            paths += [Path(value) / name for value in response["cpu_execution_dirs"] for name in ("registered_spec.json","result.json","predictions.json","train.json","validation.json","split_manifest.json")]
            paths += [Path(value) / name for value in response["model_evidence_dirs"] for name in ("request.json","result.json","events.jsonl","response.txt","stderr.log")]
            records += paths
    records=sorted(set(records))
    before={str(path):sha(path) for path in records}
    command=[sys.executable,"-B",str(__file__),"--child"]
    started=time.perf_counter()
    completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    seconds=time.perf_counter()-started
    (OUT / "stdout.log").write_text(completed.stdout,encoding="utf-8")
    (OUT / "stderr.log").write_text(completed.stderr,encoding="utf-8")
    assert before=={str(path):sha(path) for path in records},"Original completed participant/review bytes changed"
    result={"kind":"guarded_independent_development_report_reproduction","exit_code":completed.returncode,"seconds":seconds,
        "command":command,"cwd":str(ROOT),"participant_and_prior_review_before_after_identical":True,
        "original_file_sha256":before,"source":{"path":str(__file__),"sha256":sha(__file__)},
        "review_bridge":{"path":str(ROOT / "evaluation/reproduce_quadratic31_43_reviews.py"),"sha256":sha(ROOT / "evaluation/reproduce_quadratic31_43_reviews.py")},
        "stdout":{"path":str(OUT / "stdout.log"),"sha256":sha(OUT / "stdout.log")},
        "stderr":{"path":str(OUT / "stderr.log"),"sha256":sha(OUT / "stderr.log")},
        "scope":"Four completed minimal-phase development arms, not final evaluation or a new experiment; independent reference-fit arithmetic is allowed while actual runner/provider are prohibited."}
    (OUT / "result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"result":str(OUT / "result.json"),"exit_code":completed.returncode,"unchanged_files":len(records)},ensure_ascii=False))
    raise SystemExit(completed.returncode)


def child():
    sys.path.insert(0,str(ROOT))
    attempted={"actual_provider_calls":0,"actual_runner_calls":0,"private_owner_row_opens":0}
    def audit(event,args):
        if event=="open" and args and isinstance(args[0],(str,bytes)):
            path=Path(args[0]).resolve()
            if path.name.endswith("-owner.json") and "owner-development-data" in path.parts:
                attempted["private_owner_row_opens"]+=1
                raise PermissionError("Private owner observation rows are outside this independent source-reader audit")
        if event=="subprocess.Popen":
            raise PermissionError("No external subprocess or model transport permitted by source-reader audit")
    sys.addaudithook(audit)
    import evidence_research.tasks as tasks
    import evidence_research.model as model
    def no_provider(*args,**kwargs):
        attempted["actual_provider_calls"]+=1
        raise RuntimeError("Actual model/provider calls forbidden")
    def no_runner(*args,**kwargs):
        attempted["actual_runner_calls"]+=1
        raise RuntimeError("Actual experiment runner calls forbidden")
    tasks.run_task=no_runner
    model.CodexProvider.complete=no_provider
    runpy.run_path(str(ROOT / "evaluation/reproduce_quadratic31_43_reviews.py"),run_name="__main__")
    assert not any(attempted.values())
    print(json.dumps({"guarded_attempt_counts":attempted,"scope":"Reference verifier arithmetic only; no new model or runner execution"},ensure_ascii=False))


if __name__=="__main__":
    child() if "--child" in sys.argv else main()
