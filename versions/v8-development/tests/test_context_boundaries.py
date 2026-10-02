"""Synthetic transport component checks; never actual provider/research trials."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from evidence_research.context_boundary import ContextBoundaryRecorder, audit_context_boundary, _provider_facts
from evidence_research.model import CodexProvider


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')


class TapeFixture:
    def __init__(self,root,arm='C',fixture_only=True):
        self.root=Path(root); self.root.mkdir(parents=True)
        self.arm=arm
        self.envelope={'reasoning_effort':'medium','proposal_calls_per_unit':20,'actual_cpu_executions_per_unit':20}
        self.public={'task_id':'synthetic-only','seed':7,'task_bundle':{'kind':'explicit_synthetic_fixture'}}
        source=Path(__file__).resolve().parents[1]/'evidence_research'
        self.registration=self.root/'callback-registration.json'
        put(self.registration,{'public_task':self.public,'model_id':'synthetic-model','resource_envelope':self.envelope,
                              'implementation_sha256':sha(source/('arms.py' if arm=='B' else 'comparison_arms.py'))})
        self.recorder=ContextBoundaryRecorder(self.root,arm=arm,registration=self.registration,
            model_id='synthetic-model',resource_envelope=self.envelope,public_task=self.public,fixture_only=fixture_only)
        self.provider=SimpleNamespace(model='synthetic-model',reasoning_effort='medium',guard=CodexProvider.guard,
                                      evidence_dir=self.root/'model')
        self.transport=self.root/'model-transport.jsonl'
        self.index=0

    def model(self,prompt='empty public input',usage=None,failed=False,logical=True,forged_actual_tags=False,
              full_guard=True,cli_effort='medium',qualification_flag=None,qualification_value=True):
        call=f'improved-{self.index:04d}'; self.index+=1
        context={'ordinal':self.index-1,'host_ordinal':len([r for r in self.recorder.rows if r['event'] in ('provider_terminal','host_return')]),
                 'phase':'PROPOSE' if self.arm=='C' else 'report writing','role':{'kind':'synthetic_fixture'}} if logical else None
        full_prompt=(CodexProvider.guard if full_guard else '')+prompt
        boundary=self.recorder.capture(call_id=call,prompt=prompt,full_prompt=full_prompt,
            logical_context=context,transport_path=self.transport,provider=self.provider)
        row={'call_id':call,'status':'requested','context_boundary':boundary,'logical_request':context}
        with self.transport.open('a',encoding='utf-8') as stream: stream.write(json.dumps(row)+'\n')
        folder=self.provider.evidence_dir/call; folder.mkdir(parents=True)
        request={'model':'synthetic-model','reasoning_effort':'medium','prompt':prompt,'full_prompt':full_prompt,
                 'fixture_only':not forged_actual_tags,
                 'provider_source_sha256':self.recorder.binding['sources']['model.py']}
        identity={key:request[key] for key in ('model','prompt','reasoning_effort','full_prompt','provider_source_sha256')}
        request['fingerprint']=hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        request['command']=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only',
            '--model','synthetic-model','--cd',str(self.root/'public_model_cwd'),'--json','-c','approval_policy="never"',
            '--output-last-message',str(folder/'response.txt'),'-c',f'model_reasoning_effort="{cli_effort}"','-']
        if qualification_flag: request[qualification_flag]=qualification_value
        put(folder/'request.json',request)
        status='failed' if failed else 'completed'
        raw={'type':'turn.failed' if failed else 'turn.completed'}
        if not failed: raw['usage']=usage or {'input_tokens':10,'output_tokens':3,'cached_input_tokens':0}
        (folder/'events.jsonl').write_text(json.dumps(raw)+'\n',encoding='utf-8')
        (folder/'response.txt').write_text('synthetic response',encoding='utf-8')
        (folder/'stderr.log').write_bytes(b'')
        result={'status':status,'model':'synthetic-model','fingerprint':request['fingerprint'],
            'execution_kind':'real_model' if forged_actual_tags else 'simulation_fixture','fixture_only':not forged_actual_tags,'tool_calls':[],
            'usage':usage if failed else raw['usage'],'wall_seconds':1.25,'returncode':1 if failed else 0,
            'files':{name:sha(folder/name) for name in ('request.json','events.jsonl','response.txt','stderr.log')}}
        if qualification_flag: result[qualification_flag]=qualification_value
        put(folder/'result.json',result)
        self.recorder.record_model(folder=folder,logical_context=context,boundary=boundary)
        with self.transport.open('a',encoding='utf-8') as stream: stream.write(json.dumps({**row,'status':status,'evidence_dir':str(folder)})+'\n')
        return boundary,folder,context

    def cpu(self,*,output_includes_metrics=True,task_bundle=None):
        folder=self.root/'research/runs/synthetic-run'; folder.mkdir(parents=True)
        spec={'task_id':self.public['task_id'],'seed':7,'model':'synthetic-model','task_bundle':self.public['task_bundle'] if task_bundle is None else task_bundle,
              'resource_envelope':self.envelope,'config':{'degree':1,'alpha':0.0},'fixture_only':True}
        metrics={'train_mse':0.2,'validation_mse':0.3}
        result={'status':'success','metrics':metrics,'execution_seconds':0.25,'fixture_only':True}
        put(folder/'registered_spec.json',spec); put(folder/'result.json',result)
        block=json.dumps({'execution_kind':'actual_cpu_execution','execution_id':folder.name,
                          **({'metrics':metrics} if output_includes_metrics else {'result_path':str(folder/'result.json')})},sort_keys=True)
        self.recorder.record_cpu_return(logical_context={'ordinal':0,'host_ordinal':1,'phase':'EXECUTE','role':'synthetic_fixture'},
            returned_text=block,records=[{'run_dir':str(folder)}])
        return folder,metrics,block


class ContextBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='context-boundary-')
        self.base=Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def test_equivalent_arm_label_preserves_prefix_facts(self):
        normalized=[]
        for arm in ('B','C'):
            f=TapeFixture(self.base/arm,arm); f.model(); b,_,_=f.model()
            result=audit_context_boundary(b,f.root)
            self.assertFalse(result['eligible']); self.assertTrue(result['fixture_only'])
            normalized.append(result['measures'])
        self.assertEqual(normalized[0],normalized[1])

    def test_target_fingerprint_never_replaced_by_prefix(self):
        f=TapeFixture(self.base/'C'); _,old,_=f.model('prior'); b,target,_=f.model('target')
        result=audit_context_boundary(b,f.root)
        target_q=json.loads((target/'request.json').read_text())
        self.assertEqual(result['request_fingerprint'],target_q['fingerprint'])
        self.assertNotEqual(result['request_fingerprint'],json.loads((old/'request.json').read_text())['fingerprint'])

    def test_future_provider_excluded_from_prefix(self):
        f=TapeFixture(self.base/'C'); f.model(); b,_,_=f.model(); f.model(usage={'input_tokens':999,'output_tokens':999})
        result=audit_context_boundary(b,f.root)
        self.assertEqual(result['measures']['input_tokens'],10)
        self.assertEqual(result['measures']['completed_provider_calls'],1)

    def test_unknown_failed_usage_is_null_with_completed_lower_bound(self):
        f=TapeFixture(self.base/'C'); f.model(); f.model(failed=True); b,_,_=f.model()
        result=audit_context_boundary(b,f.root)
        self.assertIsNone(result['measures']['input_tokens'])
        self.assertEqual(result['completed_token_usage_lower_bound'],{'input_tokens':10,'output_tokens':3})
        self.assertEqual(result['measures']['failed_provider_attempts'],1)

    def test_missing_logical_mapping_is_pending(self):
        f=TapeFixture(self.base/'C'); b,_,_=f.model(logical=False)
        self.assertIn('missing_original_logical_mapping',audit_context_boundary(b,f.root)['pending_reasons'])

    def test_donor_arm_rejects(self):
        a=TapeFixture(self.base/'B','B'); b,_,_=a.model(); other=self.base/'C'; other.mkdir()
        with self.assertRaises(ValueError): audit_context_boundary(b,other)

    def test_tampered_raw_request_rejects(self):
        f=TapeFixture(self.base/'C'); b,folder,_=f.model()
        (folder/'request.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError): audit_context_boundary(b,f.root)

    def test_transport_mapping_tamper_rejects(self):
        f=TapeFixture(self.base/'C'); b,_,_=f.model()
        rows=[json.loads(x) for x in f.transport.read_text().splitlines()]
        rows[0]['logical_request']['ordinal']=999
        f.transport.write_text('\n'.join(json.dumps(x) for x in rows)+'\n')
        with self.assertRaises(ValueError): audit_context_boundary(b,f.root)

    def test_exact_host_return_metric_available_only_in_named_input(self):
        f=TapeFixture(self.base/'B','B'); f.model(); _,metrics,block=f.cpu(); b,_,_=f.model('Original report input: '+block)
        result=audit_context_boundary(b,f.root)
        self.assertEqual({x['metric']:x['value'] for x in result['available_metrics']},metrics)
        self.assertEqual(result['measures']['actual_cpu_executions'],1)
        self.assertEqual(len(result['prior_runs']),1)

    def test_path_only_never_implies_value_availability(self):
        f=TapeFixture(self.base/'B','B'); f.model(); _,_,block=f.cpu(output_includes_metrics=False); b,_,_=f.model(block)
        self.assertEqual(audit_context_boundary(b,f.root)['available_metrics'],[])

    def test_metric_not_in_target_cannot_be_imported_from_other_phase(self):
        f=TapeFixture(self.base/'B','B'); f.model(); _,_,block=f.cpu(); f.model(block); b,_,_=f.model('Different report input')
        self.assertEqual(audit_context_boundary(b,f.root)['available_metrics'],[])

    def test_actual_replay_no_second_provider_charge(self):
        f=TapeFixture(self.base/'C'); original,folder,ctx=f.model()
        f.recorder.record_model(folder=folder,logical_context=ctx,boundary=original,replay=True)
        b,_,_=f.model(); result=audit_context_boundary(b,f.root)
        self.assertEqual(result['measures']['completed_provider_calls'],1)
        self.assertEqual(result['measures']['input_tokens'],10)

    def test_original_transport_replay_is_not_a_second_capture(self):
        f=TapeFixture(self.base/'B','B'); original,folder,ctx=f.model()
        with f.transport.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'call_id':'upstream-replay','status':'requested',
                'context_boundary':original,'logical_request':ctx,'reused_completed_evidence':True})+'\n')
        f.recorder.record_model(folder=folder,logical_context=ctx,boundary=original,replay=True)
        b,_,_=f.model(); result=audit_context_boundary(b,f.root)
        self.assertEqual(result['measures']['completed_provider_calls'],1)
        self.assertEqual(result['call_id'],'improved-0001')
        self.assertEqual(result['request_source']['path'],str(f.provider.evidence_dir/'improved-0001/request.json'))

    def test_prior_transport_phase_transplant_rejects(self):
        f=TapeFixture(self.base/'C'); f.model(); b,_,_=f.model()
        rows=[json.loads(x) for x in f.transport.read_text().splitlines()]
        rows[0]['logical_request']['phase']='later fabricated report'
        f.transport.write_text('\n'.join(json.dumps(x) for x in rows)+'\n')
        with self.assertRaises(ValueError): audit_context_boundary(b,f.root)

    def test_missing_prior_logical_mapping_remains_pending(self):
        f=TapeFixture(self.base/'C'); f.model(logical=False); b,_,_=f.model()
        self.assertIn('prefix_missing_original_logical_mapping',audit_context_boundary(b,f.root)['pending_reasons'])

    def test_same_task_and_seed_different_split_bundle_rejects(self):
        f=TapeFixture(self.base/'C'); f.model(); f.cpu(task_bundle={'kind':'a different public split'}); b,_,_=f.model()
        with self.assertRaises(ValueError): audit_context_boundary(b,f.root)

    def test_synthetic_actual_tags_cannot_promote_to_adoption(self):
        f=TapeFixture(self.base/'C'); f.provider.execution_kind='real_model'
        boundary,folder,_=f.model(forged_actual_tags=True)
        self.assertEqual(json.loads((folder/'result.json').read_text())['execution_kind'],'real_model')
        self.assertFalse(json.loads((folder/'request.json').read_text())['fixture_only'])
        facts=audit_context_boundary(boundary,f.root)
        self.assertFalse(facts['eligible']); self.assertTrue(facts['fixture_only'])
        self.assertIn('synthetic_or_fixture_receipt_ineligible_for_actual_adoption',facts['pending_reasons'])

    def test_fixture_full_guard_omission_rejects_even_consistent_hashes(self):
        f=TapeFixture(self.base/'C'); b,_,_=f.model(full_guard=False)
        with self.assertRaisesRegex(ValueError,'guard'): audit_context_boundary(b,f.root)

    def test_fixture_cli_effort_mismatch_rejects_even_consistent_hashes(self):
        f=TapeFixture(self.base/'C'); b,_,_=f.model(cli_effort='high')
        with self.assertRaisesRegex(ValueError,'reasoning effort'): audit_context_boundary(b,f.root)

    def test_alias_fixture_flags_propagate_from_real_model_tagged_raw(self):
        for flag in ('test_fixture_only','simulation_only'):
            f=TapeFixture(self.base/flag,fixture_only=False); b,_,_=f.model(forged_actual_tags=True,qualification_flag=flag)
            original=next(row for row in f.recorder.rows if row['event']=='provider_terminal')
            facts=_provider_facts(original,f.root,f.recorder.binding,json.loads(f.registration.read_text()))
            self.assertTrue(facts[-1])
            self.assertFalse(audit_context_boundary(b,f.root)['eligible'])

    def test_malformed_qualification_flag_rejects(self):
        for flag in ('fixture_only','test_fixture_only','simulation_only'):
            f=TapeFixture(self.base/flag); b,_,_=f.model(qualification_flag=flag,qualification_value='false')
            with self.assertRaisesRegex(ValueError,'qualification'): audit_context_boundary(b,f.root)

    def test_duplicate_physical_provider_record_rejects(self):
        f=TapeFixture(self.base/'C'); b,folder,ctx=f.model()
        with self.assertRaises(ValueError): f.recorder.record_model(folder=folder,logical_context=ctx,boundary=b)

    def test_era_fields_are_original_snapshot_not_current_history(self):
        f=TapeFixture(self.base/'B','B'); f.model()
        era=f.recorder.capture_report_era(logical_context={'host_ordinal':1},selected_output='original selected output',
            selected_code='CONFIG = {}',selected_plan='We propose a comparison.',phase='report writing')
        b,_,_=f.model('We propose a comparison.')
        result=audit_context_boundary(b,f.root)
        self.assertEqual(result['report_era'],era)
        self.assertEqual(result['planning_units']['selected_native_plan']['text'],'We propose a comparison.')

    def test_c_value_memory_bound_to_original_cpu(self):
        f=TapeFixture(self.base/'C'); f.model(); folder,metrics,_=f.cpu()
        prompt=json.dumps({'verified_memory':[{'run_id':folder.name,'metrics':metrics}],'instructions':'Propose a future test.'},sort_keys=True)
        b,_,_=f.model(prompt); result=audit_context_boundary(b,f.root)
        self.assertEqual(len(result['available_metrics']),2)
        self.assertEqual(result['planning_units']['instructions']['scope'],'preexecution_planning')


if __name__=='__main__': unittest.main()
