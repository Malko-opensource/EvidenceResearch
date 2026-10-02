"""Independent c8 native callback/condition adversaries; explicitly synthetic."""
from __future__ import annotations
import ast
import copy
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "source-snapshot"
OUT = HERE.parents[2] / "_c8iv1"
EXPECTED_SNAPSHOT = "168a2b33e8027babace1e21a08735b6531337140d394fa28111934f6993933ab"
assert not OUT.exists(), "fresh isolated fixture output required"
OUT.mkdir()
os.environ['TEMP'] = os.environ['TMP'] = str(OUT)
tempfile.tempdir = str(OUT)
sys.dont_write_bytecode = True

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
manifest = read(HERE / 'snapshot-manifest.json')
assert sha(HERE / 'snapshot-manifest.json') == EXPECTED_SNAPSHOT
for item in manifest['selected_files']:
    assert sha(SNAPSHOT / item['relative']) == item['sha256']

GUARD = {'outside_allowed_access': 0, 'existing_project_access': 0,
         'process_attempts': 0, 'network_attempts': 0, 'actual_provider_attempts': 0, 'actual_fit_attempts': 0}
ALLOWED = (HERE.resolve(), OUT.resolve(), Path(sys.base_prefix).resolve())
PROJECT = HERE.parents[1].resolve()
def allowed_path(value):
    if not isinstance(value, (str, bytes, os.PathLike)): return True
    try: path = Path(os.fsdecode(value)).resolve()
    except (TypeError, ValueError): return False
    return any(path.is_relative_to(root) for root in ALLOWED)
def audit(event, args):
    if event in {'open', 'os.listdir', 'os.scandir'} and args and not allowed_path(args[0]):
        try: project = Path(os.fsdecode(args[0])).resolve().is_relative_to(PROJECT)
        except (TypeError, ValueError): project = False
        GUARD['existing_project_access' if project else 'outside_allowed_access'] += 1
        raise PermissionError('independent fixture outside approved source/temp/runtime')
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn'}:
        GUARD['process_attempts'] += 1; raise PermissionError('independent fixture process blocked')
    if event.startswith('socket.'):
        GUARD['network_attempts'] += 1; raise PermissionError('independent fixture network blocked')
sys.addaudithook(audit)
sys.path.insert(0, str(SNAPSHOT))

from evidence_research.arms import UpstreamArm, frozen_literature
from evidence_research.baseline import make_literature_protocol
from evidence_research.comparison_arms import ImprovedArm
from evidence_research.context_boundary import ContextBoundaryRecorder, audit_context_boundary, _hash
from evidence_research.model import CodexProvider, PreregisteredResourcesExhausted, digest
from evidence_research.report_semantics import evaluate_predicate, evaluate_fixture_predicate
from evidence_research.tasks import TASK_VERSION, value_hash

def blocked_provider(*args, **kwargs):
    GUARD['actual_provider_attempts'] += 1; raise AssertionError('actual provider prohibited')
def blocked_fit(*args, **kwargs):
    GUARD['actual_fit_attempts'] += 1; raise AssertionError('actual fit prohibited')
CodexProvider.complete = blocked_provider
def fit_profile(frame, event, arg):
    if event == 'call' and frame.f_globals.get('__name__') == 'evidence_research.tasks' and frame.f_code.co_name == 'run_task':
        blocked_fit()
sys.setprofile(fit_profile)

def public_payload(arm):
    name, logical = 'independent-public-c8', 17
    def rows(split, xs):
        return [{'id':f'{name}:{logical}:{split}:{i}', 'x':x, 'y':x*x}
                for i,x in enumerate(xs)]
    train, valid = rows('train', [-1.5,-0.25,0.5,1.25]), rows('validation', [-0.75,0.125,0.875])
    splits = {k:{'count':len(v), 'sha256':value_hash(v), 'ids_sha256':value_hash([r['id'] for r in v])}
              for k,v in [('train',train),('validation',valid),('test',[])]}
    lit = frozen_literature()
    return {'arm':arm, 'model_id':'independent-synthetic-v8', 'baseline_provenance':None,
        'resource_envelope':{'reasoning_effort':'medium', 'proposal_calls_per_unit':3,
            'actual_cpu_executions_per_unit':3, 'device':'cpu', 'network':False,
            'tools':['trusted polynomial ridge'], 'fixture_only':True,
            'upstream_settings':{'max_steps':3,'mlesolver_max_steps':1,'papersolver_max_steps':0,'num_papers_lit_review':1},
            'literature_snapshot':lit,'literature_snapshot_sha256':digest(lit),
            'literature_protocol':make_literature_protocol(required_entries=1,shared_distinct=3)},
        'public_task':{'task_id':name,'seed':logical,'task_version':TASK_VERSION,
            'objective':'Independent public synthetic callback transport; never task success',
            'metric':'validation_mse','allowed_config':{'degree':'1..8','alpha':'0..100'},
            'task_bundle':{'train':train,'validation':valid,'split_manifest':{'task_id':name,'seed':logical,
                'task_version':TASK_VERSION,'generation':'Hand-authored public engineering only','splits':splits}}}}

class SyntheticProvider:
    execution_kind = 'simulation_fixture'
    guard = CodexProvider.guard
    total_calls = 0
    def __init__(self, *, evidence_dir, model, reasoning_effort, public_dir, arm='C'):
        self.evidence_dir, self.public_dir = Path(evidence_dir), Path(public_dir)
        self.model, self.reasoning_effort, self.arm = model, reasoning_effort, arm
        self.calls, self.last_evidence = [], None
    def complete(self, prompt, *, call_id, json_response=False):
        index = len(self.calls); self.calls.append(call_id); SyntheticProvider.total_calls += 1
        folder = self.evidence_dir/call_id; folder.mkdir(parents=True)
        identity = {'model':self.model,'reasoning_effort':self.reasoning_effort,'prompt':prompt,
                    'full_prompt':self.guard+prompt,'provider_source_sha256':sha(SNAPSHOT/'evidence_research/model.py')}
        q = {**identity,'fingerprint':digest(identity),'fixture_only':True,
             'command':['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only',
                        '--model',self.model,'--cd',str(self.public_dir),'--json','-c','approval_policy="never"',
                        '--output-last-message',str(folder/'response.txt'),'-c',f'model_reasoning_effort="{self.reasoning_effort}"','-']}
        put(folder/'request.json',q)
        answer = ('```SUMMARY\npolynomial regression\n```' if index==0 else 'explicit synthetic invalid literature action') if self.arm=='B' else '{"candidates":null,"stop_reason":null}'
        (folder/'response.txt').write_text(answer,encoding='utf-8')
        usage = {'input_tokens':11+index,'output_tokens':2+index,'cached_input_tokens':0}
        (folder/'events.jsonl').write_text(json.dumps({'type':'turn.completed','usage':usage,'fixture_only':True})+'\n',encoding='utf-8')
        (folder/'stderr.log').write_bytes(b'')
        result = {'status':'completed','model':self.model,'fingerprint':q['fingerprint'],
                  'execution_kind':'simulation_fixture','fixture_only':True,'tool_calls':[],'usage':usage,
                  'wall_seconds':0.5+index*0.25,'returncode':0,
                  'files':{n:sha(folder/n) for n in ('request.json','events.jsonl','response.txt','stderr.log')}}
        put(folder/'result.json',result); self.last_evidence = result
        return answer

class Packet:
    """Independent source-bound probe built from an actual native receipt."""
    def __init__(self, root, arm='C', registration=None):
        self.root=Path(root); self.root.mkdir(parents=True)
        self.arm=arm; self.payload=public_payload(arm)
        self.registration=self.root/'callback-registration.json'
        put(self.registration, registration if registration is not None else NATIVE_REGISTRATIONS[arm])
        self.recorder=ContextBoundaryRecorder(self.root,arm=arm,registration=self.registration,
            model_id=self.payload['model_id'],resource_envelope=self.payload['resource_envelope'],
            public_task=self.payload['public_task'],fixture_only=True)
        self.provider=SyntheticProvider(evidence_dir=self.root/'model',model=self.payload['model_id'],
            reasoning_effort='medium',public_dir=self.root/'public_model_cwd',arm=arm)
        self.transport=self.root/'probe-transport.jsonl'; self.index=0
    def model(self, *, prompt=None, logical=True, failed=False, replay=None):
        if replay:
            boundary,folder,context=replay
            self.recorder.record_model(folder=folder,logical_context=context,boundary=boundary,replay=True)
            return replay
        ordinal=self.index; self.index+=1; call=f'probe-{ordinal:04d}'
        context={'ordinal':ordinal,'host_ordinal':sum(r['event']=='provider_terminal' for r in self.recorder.rows),
                 'phase':'PROPOSE' if self.arm=='C' else 'report writing','role':{'kind':'independent_synthetic_probe'}} if logical else None
        prompt=prompt or f'Original independent probe {ordinal}'
        link=self.recorder.capture(call_id=call,prompt=prompt,full_prompt=self.provider.guard+prompt,
            logical_context=context,transport_path=self.transport,provider=self.provider)
        requestrow={'call_id':call,'status':'requested','context_boundary':link,'logical_request':context}
        with self.transport.open('a',encoding='utf-8') as f: f.write(json.dumps(requestrow)+'\n')
        self.provider.complete(prompt,call_id=call)
        folder=self.provider.evidence_dir/call
        if failed:
            result=read(folder/'result.json'); result.update(status='failed',usage=None,returncode=1)
            (folder/'events.jsonl').write_text(json.dumps({'type':'turn.failed','fixture_only':True})+'\n',encoding='utf-8')
            result['files']['events.jsonl']=sha(folder/'events.jsonl'); put(folder/'result.json',result)
        self.recorder.record_model(folder=folder,logical_context=context,boundary=link)
        with self.transport.open('a',encoding='utf-8') as f:
            f.write(json.dumps({**requestrow,'status':'failed' if failed else 'completed','evidence_dir':str(folder)})+'\n')
        return link,folder,context

def rewrite_packet(packet, triple, *, callback_model=None, remove_guard=False):
    """Rehash local attacker-controlled links; keep external source/raw model anchors."""
    link,folder,_=triple; value=read(link['path'])
    if callback_model:
        reg=read(packet.registration); reg['model_id']=callback_model; put(packet.registration,reg)
        value['binding']['registration']['sha256']=sha(packet.registration)
        value['binding']['model_id']=callback_model
    if remove_guard:
        q=read(folder/'request.json'); q['full_prompt']=q['prompt']
        q['fingerprint']=digest({k:q[k] for k in ('model','reasoning_effort','prompt','full_prompt','provider_source_sha256')})
        put(folder/'request.json',q)
        result=read(folder/'result.json'); result['fingerprint']=q['fingerprint']
        result['files']['request.json']=sha(folder/'request.json'); put(folder/'result.json',result)
        value['full_prompt']=q['full_prompt']; value['full_prompt_sha256']=hashlib.sha256(q['full_prompt'].encode()).hexdigest()
    put(link['path'],value); new={'path':link['path'],'sha256':sha(link['path'])}
    rows=read_lines(packet.recorder.path)
    for row in rows:
        if row.get('boundary')==link: row['boundary']=new
        if row.get('event')=='provider_terminal' and row.get('sources',{}).get('request.json',{}).get('path')==str(folder/'request.json'):
            row['sources']={n:{'path':str(folder/n),'sha256':sha(folder/n)} for n in ('request.json','result.json','events.jsonl')}
            row['receipt_identity']=_hash(row['sources'])
    previous=None
    for row in rows:
        row['previous_sha256']=previous; row['event_sha256']=_hash({k:v for k,v in row.items() if k!='event_sha256'}); previous=row['event_sha256']
    write_lines(packet.recorder.path,rows)
    transport=read_lines(packet.transport)
    for row in transport:
        if row.get('context_boundary')==link: row['context_boundary']=new
    write_lines(packet.transport,transport)
    return new

def read_lines(path): return [json.loads(line) for line in Path(path).read_text().splitlines()]
def write_lines(path, rows): Path(path).write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows),encoding='utf-8')

FAMILY_OBSERVATIONS={}; NATIVE_REGISTRATIONS={}; NATIVE_FACTS={}
def observed(family, subcase, details): FAMILY_OBSERVATIONS.setdefault(family,[]).append({'id':subcase,'status':'pass','observed':details})

class IndependentCases(unittest.TestCase):
    def test_01_native_handoffs(self):
        for arm, callback, family in [('B',UpstreamArm,'native_b_registration_handoff'),('C',ImprovedArm,'native_c_registration_handoff')]:
            p=public_payload(arm); output=OUT/('native-'+arm); providers=[]
            def factory(**kwargs):
                provider=SyntheticProvider(**kwargs,arm=arm); providers.append(provider); return provider
            with (HERE/('native-'+arm+'.stdout.log')).open('w',encoding='utf-8') as out, (HERE/('native-'+arm+'.stderr.log')).open('w',encoding='utf-8') as err:
                with redirect_stdout(out),redirect_stderr(err):
                    with self.assertRaises(PreregisteredResourcesExhausted): callback(factory)(p,output)
            reg=read(output/'callback-registration.json'); NATIVE_REGISTRATIONS[arm]=reg
            self.assertEqual(reg['model_id'],p['model_id']); self.assertEqual(reg['resource_envelope'],p['resource_envelope'])
            self.assertEqual(reg['public_task'],p['public_task']); self.assertEqual(len(providers[0].calls),3)
            captures=[r['boundary'] for r in read_lines(output/'context-boundaries/host-tape.jsonl') if r['event']=='input_capture']
            self.assertEqual(len(captures),3)
            first,last=[audit_context_boundary(captures[i],output) for i in (0,2)]
            self.assertEqual(first['measures']['completed_provider_calls'],0)
            self.assertEqual(last['measures']['completed_provider_calls'],2)
            self.assertEqual(last['measures']['input_tokens'],23); self.assertEqual(last['measures']['output_tokens'],5)
            self.assertEqual(last['measures']['wall_seconds'],1.25); self.assertEqual(last['measures']['actual_cpu_executions'],0)
            self.assertFalse(last['eligible']); self.assertTrue(last['fixture_only'])
            self.assertFalse(list(output.rglob('registered_spec.json')))
            claim={'predicate_id':'historical_context_resources','kind':'execution_provenance',
                'text':'Before this request, measured resources were 2 completed provider calls.',
                'arguments':{'boundary':captures[2],
                'scope':'historical_pre_request','measure':'completed_provider_calls','value':2}}
            with self.assertRaises(ValueError): evaluate_predicate(claim,output)
            proof=evaluate_fixture_predicate(claim,output); self.assertFalse(proof['facts']['adoption_eligible'])
            NATIVE_FACTS[arm]={'eligible':last['eligible'],'fixture_only':last['fixture_only'],'adoption_eligible':proof['facts']['adoption_eligible'],
                             'measures':last['measures'],'native_requests':providers[0].calls,'callback_sha256':sha(output/'callback-registration.json')}
            observed(family,'native-first-and-third-input',NATIVE_FACTS[arm])
        self.assertEqual(NATIVE_FACTS['B']['measures'],NATIVE_FACTS['C']['measures'])

    def test_02_precapture_conditions(self):
        mutations=[('v7_missing_fields_reproduction','missing-both',lambda r:(r.pop('model_id'),r.pop('resource_envelope'))),
            ('missing_model','missing-model',lambda r:r.pop('model_id')),
            ('missing_envelope','missing-envelope',lambda r:r.pop('resource_envelope')),
            ('changed_model','donor-model',lambda r:r.update(model_id='donor-synthetic-model')),
            ('changed_effort','different-effort',lambda r:r['resource_envelope'].update(reasoning_effort='high')),
            ('changed_effort','missing-effort',lambda r:r['resource_envelope'].pop('reasoning_effort')),
            ('changed_envelope','cpu-capacity',lambda r:r['resource_envelope'].update(actual_cpu_executions_per_unit=4)),
            ('changed_envelope','provider-capacity',lambda r:r['resource_envelope'].update(proposal_calls_per_unit=4)),
            ('changed_envelope','tool-permission',lambda r:r['resource_envelope'].update(tools=['unexpected tool'])),
            ('rehashed_callback_attack','wrong-source-pin',lambda r:r.update(implementation_sha256='f'*64)),
            ('rehashed_callback_attack','same-id-other-public-data',lambda r:r['public_task']['task_bundle']['train'][0].update(y=99))]
        for family,name,mutate in mutations:
            with self.subTest(family=family,case=name):
                root=OUT/'preflight'/name; root.mkdir(parents=True)
                reg=copy.deepcopy(NATIVE_REGISTRATIONS['B']); mutate(reg); path=root/'callback-registration.json'; put(path,reg)
                p=public_payload('B'); before=SyntheticProvider.total_calls
                with self.assertRaises(ValueError) as caught:
                    ContextBoundaryRecorder(root,arm='B',registration=path,model_id=p['model_id'],
                        resource_envelope=p['resource_envelope'],public_task=p['public_task'],fixture_only=True)
                self.assertEqual(SyntheticProvider.total_calls,before); self.assertFalse((root/'context-boundaries').exists())
                observed(family,name,{'rejected':type(caught.exception).__name__,'provider_calls':0,'capture_events':0})

    def test_03_after_constructor_tamper(self):
        for family,name,mutate in [('missing_model','post-constructor-model',lambda r:r.pop('model_id')),
                                  ('missing_envelope','post-constructor-envelope',lambda r:r.pop('resource_envelope')),
                                  ('changed_envelope','post-constructor-conditions',lambda r:r['resource_envelope'].update(network=True))]:
            packet=Packet(OUT/'late'/name,'B'); reg=read(packet.registration); mutate(reg); put(packet.registration,reg)
            before=SyntheticProvider.total_calls
            with self.assertRaises(ValueError): packet.model()
            self.assertEqual(before,SyntheticProvider.total_calls); self.assertEqual(packet.recorder.rows,[])
            observed(family,name,{'provider_calls':0,'capture_events':0,'receipt_hash_rejection':True})
        for family,key,value in [('changed_model','model','other-model'),('changed_effort','reasoning_effort','low')]:
            packet=Packet(OUT/'late'/key,'C'); setattr(packet.provider,key,value)
            before=SyntheticProvider.total_calls
            with self.assertRaises(ValueError): packet.model()
            self.assertEqual(before,SyntheticProvider.total_calls); self.assertEqual(packet.recorder.rows,[])
            observed(family,'provider-'+key,{'provider_calls':0,'capture_events':0})

    def test_04_rehash_and_source_negatives(self):
        packet=Packet(OUT/'attack'/'model','B'); triple=packet.model()
        new=rewrite_packet(packet,triple,callback_model='rehash-donor-model')
        with self.assertRaises(ValueError): audit_context_boundary(new,packet.root)
        observed('rehashed_callback_attack','rehash-callback-binding-tape-transport',{'original_raw_model_fixed':True,'rejected':True})
        packet=Packet(OUT/'attack'/'guard','C'); triple=packet.model()
        new=rewrite_packet(packet,triple,remove_guard=True)
        with self.assertRaises(ValueError): audit_context_boundary(new,packet.root)
        observed('rehashed_callback_attack','rehash-raw-fingerprint-result-capture-guard-stripping',{'canonical_settings_still_required':True,'rejected':True})
        packet=Packet(OUT/'attack'/'source','C'); triple=packet.model(); value=read(triple[0]['path'])
        value['binding']['sources']['unexpected.py']='0'*64; put(triple[0]['path'],value)
        with self.assertRaises(ValueError): audit_context_boundary({'path':triple[0]['path'],'sha256':sha(triple[0]['path'])},packet.root)
        observed('rehashed_callback_attack','source-keyset',{'rejected':True})

    def test_05_prefix_replay_unknown_and_qualification(self):
        family='original_prefix_and_fixture_regressions'
        packet=Packet(OUT/'prefix'/'future','C'); first=packet.model(); target=packet.model(); packet.model()
        facts=audit_context_boundary(target[0],packet.root)
        self.assertEqual(facts['measures']['completed_provider_calls'],1); self.assertEqual(facts['measures']['input_tokens'],11)
        self.assertEqual(facts['request_fingerprint'],read(target[1]/'request.json')['fingerprint'])
        self.assertNotEqual(facts['request_fingerprint'],read(first[1]/'request.json')['fingerprint'])
        observed(family,'future-exclusion-and-target-identity',{'completed_prefix':1,'input_tokens':11,'target_identity_preserved':True})
        packet=Packet(OUT/'prefix'/'replay','B'); original=packet.model(); packet.model(replay=original); target=packet.model()
        facts=audit_context_boundary(target[0],packet.root); self.assertEqual(facts['measures']['completed_provider_calls'],1)
        self.assertEqual(facts['measures']['input_tokens'],11)
        observed(family,'physical-replay-not-second-charge',{'completed_prefix':1,'input_tokens':11})
        packet=Packet(OUT/'prefix'/'unknown','C'); packet.model(); packet.model(failed=True); target=packet.model()
        facts=audit_context_boundary(target[0],packet.root); self.assertIsNone(facts['measures']['input_tokens'])
        self.assertEqual(facts['measures']['failed_provider_attempts'],1)
        self.assertEqual(facts['completed_token_usage_lower_bound'],{'input_tokens':11,'output_tokens':2})
        observed(family,'failed-usage-null',{'input_tokens':None,'failed_attempts':1,'known_completed_lower_bound':11})
        packet=Packet(OUT/'prefix'/'missinglogical','B'); packet.model(logical=False); target=packet.model()
        facts=audit_context_boundary(target[0],packet.root)
        self.assertIn('prefix_missing_original_logical_mapping',facts['pending_reasons']); self.assertFalse(facts['eligible'])
        observed(family,'missing-original-mapping-pending',{'eligible':False,'pending':True})
        packet=Packet(OUT/'prefix'/'phase','C'); packet.model(); target=packet.model()
        rows=read_lines(packet.transport); rows[0]['logical_request']['phase']='future fabricated phase'; write_lines(packet.transport,rows)
        with self.assertRaises(ValueError): audit_context_boundary(target[0],packet.root)
        observed(family,'phase-transplant',{'rejected':True})
        packet=Packet(OUT/'prefix'/'malformedflag','C'); target=packet.model()
        q=read(target[1]/'request.json'); q['simulation_only']='true'; put(target[1]/'request.json',q)
        new=rewrite_packet(packet,target)
        with self.assertRaises(ValueError): audit_context_boundary(new,packet.root)
        observed(family,'malformed-synthetic-qualification',{'rejected':True})
        packet=Packet(OUT/'prefix'/'flags','C'); target=packet.model()
        result=read(target[1]/'result.json'); result['execution_kind']='real_model'; result['test_fixture_only']=True; put(target[1]/'result.json',result)
        new=rewrite_packet(packet,target)
        facts=audit_context_boundary(new,packet.root); self.assertFalse(facts['eligible']); self.assertTrue(facts['fixture_only'])
        observed(family,'forged-actual-tags-remain-synthetic',{'eligible':False,'fixture_only':True})

def main():
    started=time.perf_counter()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(IndependentCases)
    with (HERE/'tests.log').open('w',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    planned=read(HERE/'independent-plan.pinned.json')['families']
    verdicts=[{'id':f['id'],'expected':f['expected'],'status':'pass' if FAMILY_OBSERVATIONS.get(f['id']) else 'uncovered',
               'subcases':FAMILY_OBSERVATIONS.get(f['id'],[])} for f in planned]
    stable=all(sha(SNAPSHOT/r['relative'])==r['sha256'] for r in manifest['selected_files'])
    valid=result.wasSuccessful() and all(v['status']=='pass' for v in verdicts) and stable and not any(GUARD.values())
    output={'status':'pass' if valid else 'failed','registered_family_count':10,'registered_family_verdicts':verdicts,
        'source_manifest_sha256':manifest['external_pins']['source-manifest'],'snapshot_manifest_sha256':EXPECTED_SNAPSHOT,
        'snapshot_source_stable':stable,'native_callback_qualification':NATIVE_FACTS,'unittest_methods':result.testsRun,
        'failures':[{'test':str(t),'traceback':trace} for t,trace in result.failures],
        'errors':[{'test':str(t),'traceback':trace} for t,trace in result.errors],
        'actual_provider_calls':0,'synthetic_provider_calls':SyntheticProvider.total_calls,
        'actual_cpu_or_fit_executions':0,'private_owner_reads':0,'actual_research_trials':0,
        'guard':{'counts':GUARD,'scope':'Python open/list/scandir/process/network hook, approved snapshot/proof/explicit synthetic temp/runtime only. Not OS-wide isolation. No child processes allowed.'},
        'seconds':time.perf_counter()-started,'adoption_eligible':False,'retrospective_v7_adoption':False,
        'scope':'New independent synthetic native callback handoff and metadata/prefix attacks only; not full research success or framework gain.'}
    put(HERE/'attempt-0001-result.json',output)
    print(json.dumps({'status':output['status'],'methods':result.testsRun,'families':len(verdicts),'subcases':sum(len(v['subcases']) for v in verdicts),
        'failures':len(result.failures),'errors':len(result.errors),'result_sha256':sha(HERE/'attempt-0001-result.json'),'guards':GUARD}))
    return 0 if valid else 1
if __name__=='__main__': sys.exit(main())
