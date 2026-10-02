"""Replay independent fixtures against a self-contained fixed source snapshot.

This runs tiny explicit-array CPU components, never models/research trials.
Protected original package/study trees cannot be opened by this replay process.
"""
import argparse,io,json,sys,time,unittest
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--capsule",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();capsule=args.capsule.resolve();output=args.output.resolve()
    if output.exists():raise FileExistsError("use a new short engineering output directory")
    manifest=json.loads((capsule/"source-manifest.json").read_text(encoding="utf-8"));source=capsule/"source-snapshot";fixtures=capsule/"fixture-snapshot"
    import hashlib
    for row in manifest["files"]:
        path=capsule/row["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]:raise ValueError("captured source/fixture byte changed")
    protected=[Path(p).resolve() for p in manifest["protected_original_roots"]]
    guard={"protected_original_accesses":0,"provider_calls_blocked":0}
    def audit(event,values):
        if event not in {"open","os.listdir","os.scandir"} or not values or not isinstance(values[0],(str,bytes)):return
        path=Path(values[0]).resolve()
        if any(path==root or path.is_relative_to(root) for root in protected):
            guard["protected_original_accesses"]+=1;raise PermissionError("protected original package/study access forbidden for component replay")
    sys.addaudithook(audit);sys.path.insert(0,str(source));sys.path.insert(0,str(fixtures));output.mkdir(parents=True)
    from evidence_research.model import CodexProvider
    def block(*args,**kwargs):
        guard["provider_calls_blocked"]+=1;raise AssertionError("actual provider forbidden for independent replay")
    CodexProvider.complete=block
    import test_context_semantics as context
    import test_noncontext_semantics as noncontext
    context.SCRATCH=output/"ctx";noncontext.SCRATCH=output/"nctx"
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(context),unittest.defaultTestLoader.loadTestsFromModule(noncontext)])
    stream=io.StringIO();start=time.perf_counter();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (output/"tests.log").write_text(stream.getvalue(),encoding="utf-8")
    artifacts=sorted(p for p in output.rglob("*") if p.is_file());raw_cpu=[]
    for path in artifacts:
        if path.name=="result.json" and json.loads(path.read_text(encoding="utf-8")).get("execution_kind")=="actual_cpu_execution":raw_cpu.append(path)
    out={"schema_version":"independent-source-snapshot-component-replay-1","status":"pass" if result.wasSuccessful() and not any(guard.values()) else "failed",
        "tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"guards":guard,
        "trusted_cpu_component_executions":len(raw_cpu),"actual_provider_calls":0,"research_trials":0,"owner_private_reads":False,"monetary_cost":None,
        "snapshot_manifest_sha256":hashlib.sha256((capsule/"source-manifest.json").read_bytes()).hexdigest(),"seconds":time.perf_counter()-start,
        "failure_details":[{"test":str(t),"traceback":tb} for t,tb in result.failures+result.errors],
        "artifacts":[{"path":str(p.relative_to(output)),"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in artifacts],
        "scope":"Fixed source snapshot plus explicit synthetic transports/tiny CPU components only; no actual research gain or final protocol execution."}
    (output/"result.json").write_text(json.dumps(out,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:out[key] for key in ("status","tests_run","failures","errors","guards","trusted_cpu_component_executions")}))
    if out["status"]!="pass":raise SystemExit(1)

if __name__=="__main__":main()
