"""Independent pin/membership review plus explicit finite-form judgements.

Human-readable judgements are bounded to authored supplied synopses, not paper
truth, full-paper reading, automatic entailment or research performance.
"""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];CANDIDATE=ROOT/"work/c7"
sys.path.insert(0,str(CANDIDATE))
from transport_fixture import sha,digest,write
from evidence_research.report_semantics import FACT_REGISTRY_SHA256,FACT_CORPUS_SHA256,frozen_semantic_reference_hashes

JUDGMENTS={
 "liu-ridge-covariance":"Both forms keep the subject as a closed-form ridge solution and attribute its covariance/regularization dependence to the supplied synopsis; no task optimum or measured benefit is added.",
 "liu-no-task-optimum":"Both forms preserve the synopsis denial of a task-specific optimum and require local public train/validation measurements; neither asserts optimality or a successful execution.",
 "hoerl-conditional-bias-variance":"Both forms keep poorly conditioned linear covariance, coefficient bias and possible estimator-variance reduction; the explicit denial of a local validation benefit is preserved.",
 "craven-gcv-spline-scope":"Both forms limit the source to the publisher Summary and smoothing splines under regular-mesh/asymptotic assumptions; residual-error/trace selection is not upgraded to local polynomial-ridge measurement.",
 "laboratory-reward-not-independent":"Both forms attribute the LLM-reward/self-evaluation/hallucination description to the supplied Laboratory synopsis and deny independent present-task evidence.",
 "agentrxiv-retrieval-needs-verification":"Both forms attribute report retrieval and risk descriptions to the supplied AgentRxiv synopsis and preserve the requirement to check retrieved claims before adoption."
}

def main():
    registry=CANDIDATE/"references/source_facts_c7.json";corpus=CANDIDATE/"references/task_literature_v2.json"
    if sha(registry)!=FACT_REGISTRY_SHA256 or sha(corpus)!=FACT_CORPUS_SHA256:raise AssertionError("external finite registry/corpus pins changed")
    reg=json.loads(registry.read_text(encoding="utf-8"));records=json.loads(corpus.read_text(encoding="utf-8"))["records"]
    original={r["id"]:r for r in records};rows=[]
    if set(JUDGMENTS)!={r["fact_id"] for r in reg["facts"]}:raise AssertionError("new fact requires a fresh independent finite-form judgement")
    for fact in reg["facts"]:
        source=original[fact["source_id"]]
        checks={"source_record_sha256":digest(source)==fact["source_record_sha256"],"source_excerpt_membership":fact["source_excerpt"] in source["text"],
            "url":source["url"]==fact["url"],"languages":{f["language"] for f in fact["allowed_forms"]}=={"en","ko"},"distinct_form_ids":len({f["form_id"] for f in fact["allowed_forms"]})==2}
        if not all(checks.values()):raise AssertionError("source/translation registry structural binding failed")
        rows.append({"fact_id":fact["fact_id"],"subject":fact["subject"],"conditions":fact["conditions"],"polarity":fact["polarity"],
            "checks":checks,"form_hashes":[{"form_id":f["form_id"],"language":f["language"],"text_sha256":digest(f["text"])} for f in fact["allowed_forms"]],
            "independent_finite_correspondence_judgement":JUDGMENTS[fact["fact_id"]],"scope":"Attribution to exact supplied authored synopsis only"})
    number=len(list(HERE.glob("fact-registry-review-*.json")))+1
    out={"schema_version":"independent-finite-fact-registry-review-1","status":"finite_source_correspondence_reviewed",
        "registry":{"path":str(registry),"sha256":sha(registry)},"corpus":{"path":str(corpus),"sha256":sha(corpus)},"record_inventory_sha256":digest(records),
        "frozen_semantic_reference_hashes":frozen_semantic_reference_hashes(),"facts":rows,"full_paper_truth_or_reading_proof":False,
        "unrestricted_paraphrase_or_NLP_entailment_proof":False,"local_measurement_or_research_gain_proof":False,
        "actual_provider_calls":0,"cpu_executions":0,"owner_private_reads":False,"review_role":"independent_candidate_verifier",
        "limits":"Exact finite English/Korean forms were read and compared to the authored supplied synopses. New text, new fact IDs, source conditions or polarity need a new fixed registry and independent judgement; no general semantic truth guarantee."}
    write(HERE/f"fact-registry-review-{number:04d}.json",out)
    print(json.dumps({"status":out["status"],"facts":len(rows),"forms":sum(len(r["form_hashes"]) for r in rows),"full_paper_proof":False}))

if __name__=="__main__":main()
