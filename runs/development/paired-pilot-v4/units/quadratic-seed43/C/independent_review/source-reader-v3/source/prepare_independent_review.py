"""Owner-only evidence preparation for report-specific numeric review.

This is not an automatic prose judge. JSON offsets distinguish known metric,
resource, configuration and identifier fields. Narrative numerals remain pending
until an independent reader supplies a contextual judgment. No model is called
and no hidden test data are accessed.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evidence_research.evaluation import recompute_resource_audit
from evidence_research.report_contract import verify_report_contract
from evidence_research.tasks import sha256_file
from evidence_research.verifier import verify


def json_leaves(text: str, *, offset: int=0) -> list[dict]:
    """Strict JSON parse with leaf token spans and semantic paths."""
    decoder=json.JSONDecoder();leaves=[]
    def space(i):
        while i<len(text) and text[i].isspace():i+=1
        return i
    def parse(i,path):
        i=space(i)
        if i>=len(text):raise ValueError("incomplete JSON")
        if text[i]=="{":
            i=space(i+1)
            if text[i]=="}":return i+1
            while True:
                key,end=decoder.raw_decode(text,i)
                if not isinstance(key,str):raise ValueError("invalid JSON object key")
                i=space(end)
                if text[i]!=":":raise ValueError("missing JSON colon")
                i=space(parse(i+1,path+[key]))
                if text[i]=="}":return i+1
                if text[i]!=",":raise ValueError("missing JSON comma")
                i=space(i+1)
        if text[i]=="[":
            i=space(i+1);index=0
            if text[i]=="]":return i+1
            while True:
                i=space(parse(i,path+[index]));index+=1
                if text[i]=="]":return i+1
                if text[i]!=",":raise ValueError("missing JSON array comma")
                i=space(i+1)
        value,end=decoder.raw_decode(text,i)
        leaves.append({"start":offset+i,"end":offset+end,"path":path,"value":value})
        return end
    if space(parse(0,[]))!=len(text):raise ValueError("trailing JSON content")
    return leaves


def prepare(arm_dir: Path,report: Path,inventory_path: Path,output: Path) -> dict:
    arm_dir,report,inventory_path,output=map(lambda p:Path(p).resolve(),(arm_dir,report,inventory_path,output))
    if output.exists():raise FileExistsError("independent review preparation already exists")
    response=json.loads((arm_dir / "arm-response.json").read_text(encoding="utf-8"))
    run=Path(response["selected_run_dir"]).resolve()
    spec=json.loads((run / "registered_spec.json").read_text(encoding="utf-8"));result=json.loads((run / "result.json").read_text(encoding="utf-8"))
    verification=verify(spec,result,run)
    if not verification["valid"]:raise ValueError("selected CPU result failed independent verification")
    companion=Path(response["report_contract_path"]).resolve()
    contract=verify_report_contract(companion,arm_output=arm_dir,spec=spec,verification=verification,selected_run_dir=run)
    if not contract["valid"]:raise ValueError("common report contract failed: "+str(contract["reasons"]))
    resource_path=arm_dir / "independent-resource-audit.json"
    resources=recompute_resource_audit(resource_path)
    inventory=json.loads(inventory_path.read_text(encoding="utf-8"))
    if sha256_file(report)!=inventory["report_sha256"] or Path(inventory["report_path"]).resolve()!=report:
        raise ValueError("report/inventory source mismatch")
    text=report.read_text(encoding="utf-8");leaves=[]
    if report==companion:leaves=json_leaves(text)
    else:
        fence=re.search(r"```json\s*\n(.*?)\n```",text,re.S)
        if fence:leaves=json_leaves(fence.group(1),offset=fence.start(1))
    lines=text.splitlines(keepends=True);line_offsets=[];position=0
    for line in lines:line_offsets.append(position);position+=len(line)
    judgments,pending,mapping=[],[],[]
    companion_value=json.loads(companion.read_text(encoding="utf-8"))
    reference=ROOT / "references/task_literature.json"
    reference_values={paper["url"]:paper for paper in json.loads(reference.read_text(encoding="utf-8"))["records"]}
    for item in inventory["items"]:
        start=line_offsets[item["line"]-1]+item["start"];end=start+item["end"]-item["start"]
        leaf=next((v for v in leaves if v["start"]<=start and end<=v["end"]),None)
        j={"claim_id":item["claim_id"]};source=run / "registered_spec.json"
        path=leaf["path"] if leaf else []
        rationale=None
        if path and path[0]=="measured_metrics" and path[-1]=="value":
            metric=companion_value["measured_metrics"][path[1]]["metric"]
            j.update(kind="measured",run_dir=str(run),metric=metric)
            rationale="Known structured measured metric; independently reproduced actual CPU predictions and value."
        elif path and path[0]=="resources" and path[-1] in ("input_tokens","output_tokens","seconds"):
            metric="model_seconds" if path[-1]=="seconds" else path[-1]
            j.update(kind="measured_resource",resource_audit_path=str(resource_path),resource_metric=metric)
            rationale="Structured measured resource field; independently recomputed raw request usage/settings/time, never inferred from a provider report."
        elif path and path[0] in ("selected_config","provenance","execution","evidence"):
            j.update(kind="method" if path[0]=="selected_config" or path[-1]=="seed" else "identifier",
                     source_path=str(source),source_sha256=sha256_file(source))
            rationale="Executed configuration or exact provenance/command/artifact identifier checked by the independent common-report gate; not a performance claim."
        elif path and path[0]=="measured_metrics" and path[-1] in ("evidence_path","evidence_sha256"):
            j.update(kind="identifier",source_path=str(run / "result.json"),source_sha256=sha256_file(run / "result.json"))
            rationale="Exact source identifier of the independently verified actual result, not an additional metric."
        elif path and path[0]=="references":
            record=companion_value["references"][path[1]];paper=reference_values.get(record["url"])
            if paper and record["claim"]==paper["text"]:
                j.update(kind="literature",source_path=str(reference),source_sha256=sha256_file(reference))
                rationale="This is the exact frozen primary-source synopsis/URL; classified as literature context, never a local experimental claim."
        elif not path and re.match(r"실제 실행의 독립 계산 (train|validation) MSE:",item["context"]):
            metric="train_mse" if "train MSE:" in item["context"] else "validation_mse"
            j.update(kind="measured",run_dir=str(run),metric=metric)
            rationale="Explicit deterministic report line containing actual independently computed task metric."
        if rationale:
            j["rationale"]=rationale;judgments.append(j)
        else:pending.append({**item,"json_path":path,"reason":"Narrative semantics require independent contextual review; do not auto-approve numeric prose."})
        mapping.append({"claim_id":item["claim_id"],"json_path":path,"token_span":[start,end]})
    preparation={"scope":"owner preparation only; pending narrative judgments are not adopted results",
        "reviewer_role":"independent_verifier","report_path":str(report),"report_sha256":sha256_file(report),
        "inventory_path":str(inventory_path),"inventory_sha256":sha256_file(inventory_path),
        "judgments":judgments,"pending_contexts":pending,"offset_mapping":mapping,
        "source_sha256":sha256_file(Path(__file__)),"source_path":str(Path(__file__).resolve()),
        "resource_audit_sha256":sha256_file(resource_path),"contract_valid":True,
        "independent_review_wall_seconds":None,"independent_review_usage":None,
        "limits":"Number words, missed regex decimals, prose truth and linguistic quality still require independent reading. No self-approval by the research arm."}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(preparation,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return preparation


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("arm-dir","report","inventory","out"):p.add_argument("--"+name,type=Path,required=True)
    args=p.parse_args();r=prepare(args.arm_dir,args.report,args.inventory,args.out)
    print(json.dumps({"prepared":len(r["judgments"]),"pending":len(r["pending_contexts"]),"scope":r["scope"]}))

if __name__=="__main__":main()
