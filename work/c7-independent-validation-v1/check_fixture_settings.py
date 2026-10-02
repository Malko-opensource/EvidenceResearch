"""Independent fully rehashed original-input guard attack, provider/CPU zero."""
from pathlib import Path
import json,hashlib,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];CANDIDATE=ROOT/"work/c7"
sys.path.insert(0,str(CANDIDATE))
from transport_fixture import BoundaryFixture,sha,link,write,digest
from evidence_research.context_boundary import audit_context_boundary
from evidence_research.report_semantics import evaluate_fixture_predicate,evaluate_predicate

def main():
    number=len(list(HERE.glob("fixture-settings-attempt-*.json")))+1
    f=BoundaryFixture(ROOT/"work/t7"/f"gctx{number:04d}","C",with_cpu=False)
    prior=audit_context_boundary(f.target(),f.root)
    request=f.folders[2]/"request.json";q=json.loads(request.read_text(encoding="utf-8"))
    q["full_prompt"]=q["prompt"] # Full guard omitted, all visible costs unchanged.
    q["fingerprint"]=digest({k:q[k] for k in ("model","prompt","reasoning_effort","full_prompt","provider_source_sha256")});write(request,q)
    result=f.folders[2]/"result.json";r=json.loads(result.read_text(encoding="utf-8"));r["fingerprint"]=q["fingerprint"]
    r["files"]={name:sha(f.folders[2]/name) for name in r["files"]};write(result,r)
    path=Path(f.target()["path"]);capture=json.loads(path.read_text(encoding="utf-8"))
    capture["full_prompt"]=q["full_prompt"];capture["full_prompt_sha256"]=hashlib.sha256(q["full_prompt"].encode()).hexdigest();write(path,capture)
    old=f.target();new=link(path);rows=[json.loads(x) for x in f.recorder.path.read_text().splitlines()];out=[]
    for original in rows:
        row={k:v for k,v in original.items() if k not in {"index","previous_sha256","event_sha256"}}
        if row.get("boundary")==old:row["boundary"]=new
        if row.get("event")=="provider_terminal" and row.get("boundary")==new:
            row["sources"]={name:link(Path(item["path"])) for name,item in row["sources"].items()};row["receipt_identity"]=digest(row["sources"])
        row={"index":len(out),"previous_sha256":out[-1]["event_sha256"] if out else None,**row};row["event_sha256"]=digest(row);out.append(row)
    f.recorder.path.write_text("".join(json.dumps(row,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n" for row in out),encoding="utf-8")
    for row in f.transport:
        if row.get("context_boundary")==old:row["context_boundary"]=new
    f.flush_transport()
    claim={"text":"Before this proposal, measured input usage was 30 tokens.","kind":"execution_provenance","predicate_id":"historical_context_resources","arguments":{"boundary":new,"scope":"historical_pre_request","measure":"input_tokens","value":30}}
    output={"schema_version":"independent-rehashed-fixture-guard-attack-1","actual_provider_calls":0,"cpu_executions":0,"owner_private_reads":False,
        "source_context_sha256":sha(CANDIDATE/"evidence_research/context_boundary.py"),"source_semantics_sha256":sha(CANDIDATE/"evidence_research/report_semantics.py"),
        "all_outer_hashes_recomputed":True,"mutation":"Target full_prompt guard omitted; raw fingerprint/result/capture/tape/transport hashes refreshed","original_fixture_prefix_measures":prior["measures"]}
    try:evaluate_fixture_predicate(claim,f.root);output["component_fixture_guard_rejected"]=False
    except ValueError as error:output.update(component_fixture_guard_rejected=True,component_error=str(error))
    try:evaluate_predicate(claim,f.root);output["production_rejected"]=False
    except ValueError as error:output.update(production_rejected=True,production_error=str(error))
    output["artifacts"]=[{"path":str(p.relative_to(ROOT)),"bytes":p.stat().st_size,"sha256":sha(p)} for p in f.root.rglob("*") if p.is_file()]
    write(HERE/f"fixture-settings-attempt-{number:04d}.json",output)
    print(json.dumps({k:output.get(k) for k in ("component_fixture_guard_rejected","component_error","production_rejected")},ensure_ascii=True))

if __name__=="__main__":main()
