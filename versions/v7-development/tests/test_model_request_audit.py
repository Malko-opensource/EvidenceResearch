"""Synthetic raw provider fixtures exercise rejection, never actual LLM proof."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.model import CodexProvider
from evidence_research.model_attempt_audit import _digest, _hash
from evidence_research.model_request_audit import audit_request_settings
from evidence_research.evaluation import (_audit_model_evidence, _audit_cpu_executions,
    prepare_numeric_review, adjudicate_numeric_review, recompute_resource_audit, _audit_request_inventory)
from evidence_research.tasks import make_spec, run_task, task_data, split_manifest, write_json


def rich_request(root,folder,model="fixture-model",effort="medium"):
    request={"model":model,"prompt":"Synthetic test fixture only.","reasoning_effort":effort,
             "full_prompt":CodexProvider.guard+"Synthetic test fixture only.",
             "provider_source_sha256":_hash(Path(__file__).resolve().parents[1] / "evidence_research/model.py"),
             "execution_kind":"real_model"}
    request["fingerprint"]=_digest({k:request[k] for k in ("model","prompt","reasoning_effort","full_prompt","provider_source_sha256")})
    request["command"]=["codex","exec","--ignore-user-config","--ephemeral","--skip-git-repo-check",
                        "--sandbox","read-only","--model",model,"--cd",str(root / "public_model_cwd"),
                        "--json","-c",'approval_policy="never"',"--output-last-message",str(folder / "response.txt")]
    if effort is not None:request["command"] += ["-c",f'model_reasoning_effort="{effort}"']
    request["command"].append("-")
    return request


def completed_fixture(root,folder):
    folder.mkdir();request=rich_request(root,folder);write_json(folder / "request.json",request)
    events=[{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}]
    (folder / "events.jsonl").write_text(json.dumps(events[0])+"\n",encoding="utf-8")
    (folder / "stderr.log").write_text("synthetic unit test",encoding="utf-8")
    (folder / "response.txt").write_text("fixture",encoding="utf-8")
    result={"model":"fixture-model","status":"completed","execution_kind":"real_model","fingerprint":request["fingerprint"],
            "returncode":0,"wall_seconds":1.25,"usage":events[0]["usage"],"tool_calls":[],
            "files":{v.name:_hash(v) for v in folder.iterdir()}}
    write_json(folder / "result.json",result);return request,result


class RequestAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.folder=self.root / "synthetic-completion"
        self.request,self.result=completed_fixture(self.root,self.folder)
        self.envelope={"reasoning_effort":"medium","actual_cpu_executions_per_unit":2}
    def audit(self,request=None,result=None):
        return audit_request_settings(request or self.request,result or self.result,model_id="fixture-model",resource_envelope=self.envelope,folder=self.folder,arm_output=self.root)
    def test_matched_explicit_settings_pass(self):self.assertTrue(self.audit()["valid"])
    def test_effort_changed_with_valid_identity_rejected(self):
        r=deepcopy(self.request);r["reasoning_effort"]="high"
        with self.assertRaisesRegex(ValueError,"reasoning effort"):self.audit(r)
    def test_cli_override_or_duplicate_model_rejected(self):
        for args in (("-c",'model_reasoning_effort="high"'),("--model","different-model"),("--dangerously-bypass-approvals-and-sandbox",)):
            with self.subTest(args=args):
                r=deepcopy(self.request);r["command"][-1:-1]=args
                with self.assertRaises(ValueError):self.audit(r)
    def test_missing_isolation_or_changed_sandbox_rejected(self):
        r=deepcopy(self.request);r["command"].remove("--ignore-user-config")
        with self.assertRaises(ValueError):self.audit(r)
        r=deepcopy(self.request);r["command"][r["command"].index("read-only")]="danger-full-access"
        with self.assertRaises(ValueError):self.audit(r)
    def test_changed_guard_or_provider_source_rejected(self):
        for field,value in (("full_prompt",self.request["prompt"]),("provider_source_sha256","0"*64)):
            r=deepcopy(self.request);r[field]=value
            with self.assertRaises(ValueError):self.audit(r)
    def test_public_cwd_and_response_path_cannot_escape(self):
        for option in ("--cd","--output-last-message"):
            r=deepcopy(self.request);r["command"][r["command"].index(option)+1]=str(self.root.parent)
            with self.assertRaisesRegex(ValueError,"boundary"):self.audit(r)
    def test_completed_evidence_wrapper_checks_actual_settings(self):
        self.assertEqual(_audit_model_evidence([str(self.folder)],self.root,"fixture-model",self.envelope)["provider_calls"],1)
        r=deepcopy(self.request);r["command"].remove("--ephemeral");write_json(self.folder / "request.json",r)
        self.result["files"]["request.json"]=_hash(self.folder / "request.json");write_json(self.folder / "result.json",self.result)
        with self.assertRaises(ValueError):_audit_model_evidence([str(self.folder)],self.root,"fixture-model",self.envelope)
    def test_measured_resource_numeric_review_uses_recomputation(self):
        measures={"provider_calls":1,"provider_attempts":1,"failed_model_attempts":0,"model_seconds":1.25,
                  "input_tokens":10,"output_tokens":5,"completed_input_tokens":10,"completed_output_tokens":5}
        audit_path=self.root / "independent-resource-audit.json"
        write_json(audit_path,{"schema_version":"independent-resource-audit-1","model_id":"fixture-model","resource_envelope":self.envelope,
                  "arm_output":str(self.root),"completed_model_evidence_dirs":[str(self.folder)],"failed_model_attempt_dirs":[],
                  "host_action_receipts":{},"continuation_lineage_path":None,"measures":measures})
        self.assertEqual(recompute_resource_audit(audit_path)["measures"],measures)
        report=self.root / "report.txt";report.write_text("Input tokens 10; fabricated input tokens 999; model seconds 1.25",encoding="utf-8")
        inventory=self.root / "inventory.json";items=prepare_numeric_review(report,inventory)["items"]
        judgments=[{"claim_id":item["claim_id"],"kind":"measured_resource","resource_audit_path":str(audit_path),
                    "resource_metric":"model_seconds" if item["number"]=="1.25" else "input_tokens",
                    "rationale":"Independent raw request/usage/time recomputation; synthetic fixture is a unit test, not real-model evidence."} for item in items]
        judged=adjudicate_numeric_review(inventory,judgments,self.root / "review.json",reviewer_role="independent_verifier")
        self.assertEqual(judged["unsupported_claims"],1)

    def test_actual_request_inventory_cannot_omit_an_attempt(self):
        second=self.root / "another-synthetic-completion";completed_fixture(self.root,second)
        with self.assertRaisesRegex(ValueError,"omits"):
            _audit_request_inventory([str(self.folder)],[],self.root)
        _audit_request_inventory([str(self.folder),str(second)],[],self.root)

    def test_resources_cannot_be_fabricated_in_audit_sidecar(self):
        audit_path=self.root / "resource.json"
        write_json(audit_path,{"schema_version":"independent-resource-audit-1","model_id":"fixture-model","resource_envelope":self.envelope,
                  "arm_output":str(self.root),"completed_model_evidence_dirs":[str(self.folder)],"failed_model_attempt_dirs":[],
                  "host_action_receipts":{},"continuation_lineage_path":None,"measures":{"input_tokens":999}})
        with self.assertRaisesRegex(ValueError,"independently recomputed"):
            recompute_resource_audit(audit_path)


class CpuBudgetTests(unittest.TestCase):
    def test_actual_cpu_success_failure_inventory_and_shared_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();data=task_data("dev-quadratic",71)
            bundle={"train":data["train"],"validation":data["validation"],"split_manifest":split_manifest("dev-quadratic",71)}
            public={"task_id":"dev-quadratic","seed":71,"task_bundle":bundle}
            envelope={"reasoning_effort":"medium","actual_cpu_executions_per_unit":2}
            paths=[]
            for i in range(2):
                spec=make_spec("dev-quadratic",71,{"degree":2,"alpha":0.1},model="fixture-model",resource_envelope=envelope,task_bundle=bundle)
                if i:spec["config"]["alpha"]=-1  # Actual fixed runner reports verified invalid-config failure.
                folder=root / f"actual-cpu-{i}";run_task(spec,folder);paths.append(str(folder))
            args={"arm_output":root,"public":public,"model_id":"fixture-model","resource_envelope":envelope}
            audited=_audit_cpu_executions(paths,**args)
            self.assertEqual(audited["actual_cpu_executions"],2)
            self.assertEqual(audited["total_cpu_execution_seconds"],sum(json.loads((Path(v) / "result.json").read_text())["execution_seconds"] for v in paths))
            with self.assertRaisesRegex(ValueError,"omits"):_audit_cpu_executions(paths[:1],**args)
            with self.assertRaisesRegex(ValueError,"duplicated or exceeds"):_audit_cpu_executions(paths+[paths[0]],**args)
            changed={**envelope,"actual_cpu_executions_per_unit":1}
            with self.assertRaisesRegex(ValueError,"exceeds"):_audit_cpu_executions(paths,**{**args,"resource_envelope":changed})

if __name__=="__main__":unittest.main()
