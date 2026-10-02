"""c8 original callback-to-recorder integration; synthetic provider only.

The pinned upstream initial literature phase really runs. Both arms terminate at
their tiny fixture model allowance, before any CPU action. This checks metadata
handoff, not successful whole research pipelines or model performance.
"""
from copy import deepcopy
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.arms import UpstreamArm, frozen_literature
from evidence_research.baseline import make_literature_protocol
from evidence_research.comparison_arms import ImprovedArm
from evidence_research.context_boundary import (ContextBoundaryRecorder, audit_context_boundary,
                                               _hash, _sha)
from evidence_research.model import CodexProvider, PreregisteredResourcesExhausted, digest
from evidence_research.tasks import TASK_VERSION, value_hash, write_json, sha256_file
from tests.test_context_boundaries import TapeFixture


def payload(arm):
    """Public hand-authored arrays; no owner sampler or hidden task answers."""
    task_id, seed = 'synthetic-public-c8', 8
    train = [{'id':f'{task_id}:{seed}:train:{i}', 'x':x, 'y':y}
             for i,(x,y) in enumerate(((-1.0,1.0),(0.0,0.0),(1.0,1.0)))]
    validation = [{'id':f'{task_id}:{seed}:validation:{i}', 'x':x, 'y':y}
                  for i,(x,y) in enumerate(((-0.5,0.25),(0.5,0.25)))]
    manifest = {'task_id':task_id,'task_version':TASK_VERSION,'seed':seed,
        'generation':'Explicit hand-authored public engineering fixture only',
        'splits':{name:{'count':len(rows),'sha256':value_hash(rows),
            'ids_sha256':value_hash([row['id'] for row in rows])}
            for name,rows in (('train',train),('validation',validation),('test',[]))}}
    literature = frozen_literature()
    return {'arm':arm,'model_id':'synthetic-c8-model','baseline_provenance':None,
        'resource_envelope':{'reasoning_effort':'medium','proposal_calls_per_unit':2,
            'actual_cpu_executions_per_unit':2,'device':'cpu','network':False,
            'tools':['trusted polynomial ridge'], 'fixture_only':True,
            'upstream_settings':{'max_steps':2,'mlesolver_max_steps':1,
                'papersolver_max_steps':0,'num_papers_lit_review':1},
            'literature_snapshot':literature,'literature_snapshot_sha256':digest(literature),
            'literature_protocol':make_literature_protocol(required_entries=1,shared_distinct=3)},
        'public_task':{'task_id':task_id,'seed':seed,'task_version':TASK_VERSION,
            'objective':'Exercise original callback handoff; no research claim',
            'metric':'validation_mse','allowed_config':{'degree':'1..8','alpha':'0..100'},
            'task_bundle':{'train':train,'validation':validation,'split_manifest':manifest}}}


class SyntheticCallbackProvider:
    execution_kind = 'simulation_fixture'
    guard = CodexProvider.guard
    def __init__(self, *, evidence_dir, model, reasoning_effort, public_dir, arm):
        self.evidence_dir = Path(evidence_dir)
        self.model, self.reasoning_effort = model, reasoning_effort
        self.public_dir, self.arm = Path(public_dir), arm
        self.calls, self.last_evidence = [], None

    def complete(self, prompt, *, call_id, json_response=False):
        self.calls.append(call_id)
        folder = self.evidence_dir/call_id
        folder.mkdir(parents=True)
        identity = {'model':self.model,'reasoning_effort':self.reasoning_effort,
            'prompt':prompt,'full_prompt':self.guard+prompt,
            'provider_source_sha256':sha256_file(Path(__file__).resolve().parents[1]/'evidence_research/model.py')}
        request = {**identity,'fingerprint':digest(identity),'fixture_only':True,
            'command':['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check',
                '--sandbox','read-only','--model',self.model,'--cd',str(self.public_dir),
                '--json','-c','approval_policy="never"','--output-last-message',str(folder/'response.txt'),
                '-c',f'model_reasoning_effort="{self.reasoning_effort}"','-']}
        write_json(folder/'request.json',request)
        if self.arm == 'B':
            answer = '```SUMMARY\nridge regression\n```' if len(self.calls)==1 else 'synthetic unsupported literature command'
        else:
            answer = json.dumps({'candidates':None,'stop_reason':None})
        (folder/'response.txt').write_text(answer,encoding='utf-8')
        usage = {'input_tokens':10,'output_tokens':3,'cached_input_tokens':0}
        (folder/'events.jsonl').write_text(json.dumps({'type':'turn.completed','usage':usage,'fixture_only':True})+'\n',encoding='utf-8')
        (folder/'stderr.log').write_bytes(b'')
        result = {'status':'completed','model':self.model,'fingerprint':request['fingerprint'],
            'execution_kind':'simulation_fixture','fixture_only':True,'tool_calls':[],
            'usage':usage,'wall_seconds':1.25,'returncode':0,
            'files':{name:sha256_file(folder/name) for name in ('request.json','events.jsonl','response.txt','stderr.log')}}
        write_json(folder/'result.json',result)
        self.last_evidence = result
        return answer


class CallbackHandoffTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]/'runs/hf'
        root.mkdir(parents=True,exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temp.name).resolve()
    def tearDown(self): self.temp.cleanup()

    def test_native_b_c_writers_recorder_auditor_same_conditions(self):
        normalized = []
        for arm, callback in (('B',UpstreamArm),('C',ImprovedArm)):
            registered = payload(arm); output = self.root/arm; providers = []
            def factory(**kwargs):
                provider = SyntheticCallbackProvider(**kwargs,arm=arm)
                providers.append(provider); return provider
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                with self.assertRaises(PreregisteredResourcesExhausted):
                    callback(factory)(registered,output)
            self.assertEqual(providers[0].calls, [f'{"upstream" if arm=="B" else "improved"}-0000',
                                                  f'{"upstream" if arm=="B" else "improved"}-0001'])
            receipt = json.loads((output/'callback-registration.json').read_text(encoding='utf-8'))
            self.assertEqual(receipt['public_task'],registered['public_task'])
            self.assertEqual(receipt['model_id'],registered['model_id'])
            self.assertEqual(receipt['resource_envelope'],registered['resource_envelope'])
            tape = [json.loads(line) for line in (output/'context-boundaries/host-tape.jsonl').read_text().splitlines()]
            captures = [row['boundary'] for row in tape if row['event']=='input_capture']
            self.assertEqual(len(captures),2)
            facts = audit_context_boundary(captures[1],output)
            self.assertFalse(facts['eligible']); self.assertTrue(facts['fixture_only'])
            self.assertEqual(facts['pending_reasons'],['synthetic_or_fixture_receipt_ineligible_for_actual_adoption'])
            self.assertEqual(facts['measures']['completed_provider_calls'],1)
            self.assertEqual(facts['measures']['actual_cpu_executions'],0)
            self.assertEqual(len(list(output.rglob('registered_spec.json'))),0)
            normalized.append(facts['measures'])
            if arm=='B':
                baseline=json.loads((output/'attempts/attempt-0000/upstream/baseline_result.json').read_text())
                self.assertEqual(baseline['status'],'failure')
                self.assertTrue(baseline['source_metadata']['agents'])
                self.assertTrue(baseline['error'].startswith('PreregisteredResourcesExhausted:'))
                self.assertIn('UPSTREAM USER PROMPT:',json.loads((providers[0].evidence_dir/'upstream-0000/request.json').read_text())['prompt'])
        self.assertEqual(normalized[0],normalized[1])

    def reject_registration(self,change,*,argument_change=None):
        root=self.root/str(len(list(self.root.iterdir()))); root.mkdir()
        good={'model_id':'synthetic-model','resource_envelope':{'reasoning_effort':'medium','proposal_calls_per_unit':20},
              'public_task':{'task_id':'fixture'},'implementation_sha256':_sha(Path(__file__).resolve().parents[1]/'evidence_research/arms.py')}
        bad=deepcopy(good); change(bad); receipt=root/'callback-registration.json'; write_json(receipt,bad)
        kwargs={'model_id':good['model_id'],'resource_envelope':good['resource_envelope'],'public_task':good['public_task']}
        if argument_change: argument_change(kwargs)
        with self.assertRaises(ValueError):
            ContextBoundaryRecorder(root,arm='B',registration=receipt,fixture_only=True,**kwargs)
        self.assertFalse((root/'context-boundaries').exists())
        self.assertFalse(list(root.rglob('request.json')))

    def test_v7_missing_two_field_shape_rejects(self):
        self.reject_registration(lambda x:(x.pop('model_id'),x.pop('resource_envelope')))
    def test_missing_model_rejects_before_capture(self): self.reject_registration(lambda x:x.pop('model_id'))
    def test_missing_envelope_rejects_before_capture(self): self.reject_registration(lambda x:x.pop('resource_envelope'))
    def test_changed_model_rejects_before_capture(self): self.reject_registration(lambda x:x.update(model_id='other-model'))
    def test_changed_effort_rejects_before_capture(self): self.reject_registration(lambda x:x['resource_envelope'].update(reasoning_effort='high'))
    def test_changed_envelope_rejects_before_capture(self): self.reject_registration(lambda x:x['resource_envelope'].update(proposal_calls_per_unit=21))
    def test_changed_public_bundle_rejects_before_capture(self): self.reject_registration(lambda x:x['public_task'].update(task_id='different'))
    def test_changed_implementation_rejects_before_capture(self): self.reject_registration(lambda x:x.update(implementation_sha256='0'*64))
    def test_missing_explicit_effort_rejects_before_capture(self): self.reject_registration(lambda x:x['resource_envelope'].pop('reasoning_effort'))

    def test_receipt_tamper_after_constructor_rejects_without_provider_request(self):
        fixture=TapeFixture(self.root/'tamper','B')
        receipt=json.loads(fixture.registration.read_text()); receipt['model_id']='changed'
        write_json(fixture.registration,receipt)
        with self.assertRaises(ValueError): fixture.model()
        self.assertEqual(fixture.recorder.rows,[])
        self.assertFalse(list(fixture.root.rglob('request.json')))

    def test_provider_effort_and_model_checked_before_capture(self):
        for key,value in (('model','other'),('reasoning_effort','high')):
            fixture=TapeFixture(self.root/key,'B'); setattr(fixture.provider,key,value)
            with self.assertRaises(ValueError): fixture.model()
            self.assertEqual(fixture.recorder.rows,[])
            self.assertFalse(list(fixture.root.rglob('request.json')))

    def test_rehashed_callback_and_local_binding_cannot_replace_original_raw_conditions(self):
        fixture=TapeFixture(self.root/'rehash','B'); boundary,_,_=fixture.model()
        path=Path(boundary['path']); value=json.loads(path.read_text()); receipt=json.loads(fixture.registration.read_text())
        receipt['model_id']='changed'; write_json(fixture.registration,receipt)
        value['binding']['registration']['sha256']=_sha(fixture.registration)
        value['binding']['model_id']='changed'; write_json(path,value)
        link={'path':str(path),'sha256':_sha(path)}
        rows=[json.loads(line) for line in fixture.recorder.path.read_text().splitlines()]
        for row in rows:
            if row.get('boundary')==boundary: row['boundary']=link
            if 'boundary' in row and row['boundary']['path']==str(path): row['boundary']=link
        previous=None
        for row in rows:
            row['previous_sha256']=previous; body={k:v for k,v in row.items() if k!='event_sha256'}
            row['event_sha256']=_hash(body); previous=row['event_sha256']
        fixture.recorder.path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        transport=[json.loads(line) for line in fixture.transport.read_text().splitlines()]
        for row in transport: row['context_boundary']=link
        fixture.transport.write_text(''.join(json.dumps(row)+'\n' for row in transport))
        with self.assertRaises(ValueError): audit_context_boundary(link,fixture.root)


if __name__=='__main__': unittest.main()
