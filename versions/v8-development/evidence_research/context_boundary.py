"""Original host input boundaries, independent of native research algorithms.

Capture runs before a provider request. Later auditing checks the immutable input,
ordered host tape, original requested transport row and raw terminal receipts.
It never reconstructs an earlier input from final history. Fixture facts remain
explicitly ineligible for actual research adoption. Nothing runs on import.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path

from .store import atomic_json

SCHEMA_VERSION = 'original-context-boundary-1-development'


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _hash(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _link(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': _sha(path)}


def _checked(link, root):
    if not isinstance(link, dict) or set(link) != {'path', 'sha256'}:
        raise ValueError('Context evidence requires an exact path/SHA link')
    path = Path(link['path'])
    if not path.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('Context evidence escapes its original arm')
    parent = path.parent
    while parent != root:
        if parent.is_symlink():
            raise ValueError('Context evidence parent is a symlink')
        parent = parent.parent
    if not path.is_file() or _sha(path) != link['sha256']:
        raise ValueError('Context evidence changed or is missing')
    return path.resolve()


def _immutable(path, value):
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != value:
            raise ValueError('Immutable original context identity collision')
    else:
        atomic_json(path, value)
    return _link(path)


def _tape(path):
    raw = path.read_bytes() if path.exists() else b''
    rows, previous = [], None
    for index, line in enumerate(raw.splitlines()):
        row = json.loads(line)
        body = {key:value for key,value in row.items() if key != 'event_sha256'}
        if body.get('index') != index or body.get('previous_sha256') != previous or _hash(body) != row.get('event_sha256'):
            raise ValueError('Original context tape order or hash chain changed')
        previous = row['event_sha256']; rows.append(row)
    return rows, raw


def _settings(request):
    return {'model_id':request.get('model'), 'reasoning_effort':request.get('reasoning_effort'),
            'provider_source_sha256':request.get('provider_source_sha256')}


def _fixture_flags(*records):
    """Explicit test declarations stay nonactual; malformed tags fail closed."""
    declared=False
    for record in records:
        for key in ('fixture_only','test_fixture_only','simulation_only'):
            if key in record:
                if type(record[key]) is not bool:
                    raise ValueError('Malformed synthetic evidence qualification flag')
                declared=declared or record[key]
    return declared


def _validate_registration_conditions(registration, binding):
    """One strict contract for original host capture and independent audit.

    This checks the original callback receipt, never repairs missing metadata
    from a later binding. Resource and public-task hashes cover the whole value.
    """
    if not isinstance(registration, dict) or not isinstance(binding, dict):
        raise ValueError('Original callback registration and boundary must be objects')
    required = {'model_id', 'resource_envelope', 'public_task', 'implementation_sha256'}
    if not required.issubset(registration):
        raise ValueError('Original callback registration is missing required conditions')
    model = registration['model_id']
    envelope = registration['resource_envelope']
    if (not isinstance(model, str) or not model or not isinstance(envelope, dict)
            or 'reasoning_effort' not in envelope or not isinstance(registration['public_task'], dict)):
        raise ValueError('Malformed original callback model/public/resource conditions')
    effort = envelope['reasoning_effort']
    if effort is not None and (not isinstance(effort, str) or effort not in
            {'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'}):
        raise ValueError('Unsupported original callback reasoning effort')
    if (model != binding['model_id'] or _hash(envelope) != binding['resource_envelope_sha256']
            or _hash(registration['public_task']) != binding['public_task_sha256']
            or effort != binding['reasoning_effort']):
        raise ValueError('Original boundary conditions differ from callback registration')
    source_root = Path(__file__).resolve().parent
    expected_sources = {'context_boundary.py', 'baseline.py', 'arms.py', 'comparison_arms.py',
                        'model.py', 'model_request_audit.py', 'verifier.py', 'tasks.py'}
    if set(binding.get('sources', {})) != expected_sources:
        raise ValueError('Boundary source inventory is incomplete or has arbitrary source paths')
    if any(_sha(source_root/name) != digest for name, digest in binding['sources'].items()):
        raise ValueError('Boundary executing source differs from the frozen context adapter')
    if (binding.get('arm') not in {'B', 'C'} or registration['implementation_sha256'] !=
            binding['sources']['arms.py' if binding['arm'] == 'B' else 'comparison_arms.py']):
        raise ValueError('Callback implementation does not match the original adapter source')
    _fixture_flags(binding, registration)


@dataclass(frozen=True)
class ContextBoundary:
    path: str
    sha256: str

    def link(self):
        return {'path':self.path, 'sha256':self.sha256}


class ContextBoundaryRecorder:
    """Host-only observer; its sidecars never change the model's native input."""
    def __init__(self, arm_output, *, arm, registration, model_id, resource_envelope, public_task,
                 fixture_only=False):
        self.root = Path(arm_output).resolve()
        if arm not in {'B', 'C'}:
            raise ValueError('Context arm must be B or C')
        if type(fixture_only) is not bool:
            raise ValueError('Host context fixture qualification must be explicit boolean')
        if not isinstance(resource_envelope, dict) or not isinstance(public_task, dict):
            raise ValueError('Host context public/resource conditions must be objects')
        source_names = ('context_boundary.py', 'baseline.py', 'arms.py', 'comparison_arms.py', 'model.py', 'model_request_audit.py', 'verifier.py', 'tasks.py')
        source_root = Path(__file__).resolve().parent
        self.binding = {'schema_version':SCHEMA_VERSION, 'arm_output':str(self.root), 'arm':arm,
            'registration':_link(registration), 'model_id':model_id,
            'reasoning_effort':resource_envelope.get('reasoning_effort'),
            'resource_envelope_sha256':_hash(resource_envelope), 'public_task_sha256':_hash(public_task),
            'sources':{name:_sha(source_root/name) for name in source_names}, 'fixture_only':bool(fixture_only)}
        self._validate_original_registration()
        self.directory = self.root / 'context-boundaries'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'host-tape.jsonl'
        self.rows, _ = _tape(self.path)
        _immutable(self.directory/'binding.json', self.binding)
        self.report_era = None

    def _validate_original_registration(self):
        path = _checked(self.binding['registration'], self.root)
        registration = json.loads(path.read_text(encoding='utf-8'))
        _validate_registration_conditions(registration, self.binding)

    def _append(self, event):
        body = {'index':len(self.rows), 'previous_sha256':self.rows[-1]['event_sha256'] if self.rows else None,
                **event}
        row = {**body, 'event_sha256':_hash(body)}
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n')
            stream.flush(); os.fsync(stream.fileno())
        self.rows.append(row)
        return row

    def capture_report_era(self, *, logical_context, selected_output, selected_code, phase, selected_plan=None):
        """Observe original selected upstream fields when the reporting phase starts."""
        self._validate_original_registration()
        value = {'schema_version':SCHEMA_VERSION, 'binding':self.binding, 'logical_context':logical_context,
                 'phase':phase, 'selected_output':selected_output, 'selected_code':selected_code, 'selected_plan':selected_plan,
                 'prefix_event_count':len(self.rows),
                 'scope':'Original workflow selected fields at phase entry; not every model input or full history.'}
        link = _immutable(self.directory/f'era-{_hash(value)[:20]}.json', value)
        self._append({'event':'report_era', 'era':link})
        self.report_era = link
        return link

    def capture(self, *, call_id, prompt, full_prompt, logical_context, transport_path, provider):
        """Create the original pre-request receipt before the actual provider call."""
        self._validate_original_registration()
        if (provider.model != self.binding['model_id'] or
                getattr(provider, 'reasoning_effort', None) != self.binding['reasoning_effort']):
            raise ValueError('Provider model/reasoning effort differs before original input capture')
        rows, raw = _tape(self.path)
        if rows != self.rows:
            raise ValueError('Context tape changed before original input capture')
        from .model import CodexProvider
        value = {'schema_version':SCHEMA_VERSION, 'binding':self.binding, 'call_id':call_id,
            'prompt':prompt, 'full_prompt':full_prompt,
            'prompt_sha256':hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
            'full_prompt_sha256':hashlib.sha256(full_prompt.encode('utf-8')).hexdigest(),
            'logical_context':logical_context, 'provider_directory':str(Path(provider.evidence_dir).resolve()),
            'provider_settings':{'model_id':provider.model, 'reasoning_effort':getattr(provider,'reasoning_effort',None),
                'provider_source_sha256':self.binding['sources']['model.py']},
            'provider_implementation':{'module':type(provider).__module__,'qualname':type(provider).__qualname__,
                'canonical_frozen_codex_provider':type(provider) is CodexProvider},
            'transport_path':str(Path(transport_path).resolve()), 'prefix_event_count':len(rows),
            'prefix_tape_sha256':hashlib.sha256(raw).hexdigest(), 'report_era':self.report_era,
            'scope':'Exact original input before this named provider request; target and future responses excluded.'}
        link = _immutable(self.directory/f'input-{_hash(value)[:20]}.json', value)
        self._append({'event':'input_capture', 'boundary':link, 'logical_context':logical_context})
        return link

    def record_model(self, *, folder, logical_context, boundary, replay=False):
        folder = Path(folder).resolve()
        if not all((folder/name).is_file() for name in ('request.json','result.json','events.jsonl')):
            self._append({'event':'provider_unresolved', 'folder':str(folder), 'boundary':boundary,
                          'logical_context':logical_context})
            return
        links = {name:_link(folder/name) for name in ('request.json','result.json','events.jsonl')}
        identity = _hash(links)
        previous = [row for row in self.rows if row.get('event')=='provider_terminal' and row['receipt_identity']==identity]
        if replay:
            if len(previous) != 1 or previous[0].get('boundary') != boundary:
                raise ValueError('Replay must retain its original captured boundary and raw receipt')
            self._append({'event':'provider_replay', 'receipt_identity':identity, 'boundary':boundary,
                          'logical_context':logical_context})
            return
        if previous:
            raise ValueError('A physical provider receipt cannot be counted twice')
        result = json.loads((folder/'result.json').read_text(encoding='utf-8'))
        self._append({'event':'provider_terminal', 'receipt_identity':identity, 'boundary':boundary,
                      'logical_context':logical_context, 'status':result.get('status'), 'sources':links})

    def record_cpu_return(self, *, logical_context, returned_text, records, host_reply=None, replay=False):
        sources = []
        for record in records:
            folder = Path(record['run_dir']).resolve()
            links = {name:_link(folder/name) for name in ('registered_spec.json','result.json')}
            identity = _hash(links)
            existing = [row for row in self.rows if row.get('event')=='cpu_terminal' and row['receipt_identity']==identity]
            if not existing:
                if replay:
                    raise ValueError('Replayed CPU response has no original physical context receipt')
                self._append({'event':'cpu_terminal', 'receipt_identity':identity,
                              'logical_context':logical_context, 'sources':links})
            elif len(existing)!=1:
                raise ValueError('Physical CPU completion was counted twice')
            sources.append({'receipt_identity':identity,'sources':links})
        self._append({'event':'host_return_replay' if replay else 'host_return',
            'logical_context':logical_context, 'returned_text':returned_text,
            'returned_text_sha256':hashlib.sha256(returned_text.encode('utf-8')).hexdigest(),
            'cpu_receipts':sources, 'host_reply':host_reply})


def _provider_facts(row, root, binding, registration):
    links=row['sources']; paths={name:_checked(link,root) for name,link in links.items()}
    q=json.loads(paths['request.json'].read_text(encoding='utf-8'))
    r=json.loads(paths['result.json'].read_text(encoding='utf-8'))
    events=[json.loads(x) for x in paths['events.jsonl'].read_text(encoding='utf-8').splitlines() if x.strip()]
    if _hash(links)!=row['receipt_identity'] or q.get('fingerprint')!=r.get('fingerprint') or q.get('model')!=binding['model_id'] or r.get('model')!=binding['model_id'] or q.get('reasoning_effort')!=binding['reasoning_effort'] or q.get('provider_source_sha256')!=binding['sources']['model.py']:
        raise ValueError('Original provider source/model/settings/raw identity differs')
    if row.get('status')!=r.get('status') or r.get('tool_calls'):
        raise ValueError('Original provider status or tool permission differs')
    for name,digest in r.get('files',{}).items():
        if Path(name).name!=name or name not in {'request.json','events.jsonl','response.txt','stderr.log'}:
            raise ValueError('Provider raw file inventory differs')
        _checked({'path':str(paths['result.json'].parent/name),'sha256':digest},root)
    completed=[e for e in events if e.get('type')=='turn.completed']
    failed=[e for e in events if e.get('type')=='turn.failed']
    if r['status']=='completed':
        if len(completed)!=1 or failed or completed[0].get('usage')!=r.get('usage'):
            raise ValueError('Provider completion usage does not match its original raw event')
    elif r['status']=='failed':
        if completed or len(failed)!=1:
            raise ValueError('Unknown provider failure cannot provide an attested context prefix')
    else:
        raise ValueError('Unknown provider terminal status')
    # Canonical model/envelope/source/full guard/fingerprint/CLI isolation are
    # common structural obligations even for explicit component fixtures.
    from .model_request_audit import audit_request_settings
    audit_request_settings(q,r,model_id=binding['model_id'],resource_envelope=registration['resource_envelope'],
                           folder=paths['result.json'].parent,arm_output=root)
    fixture=_fixture_flags(binding,registration,q,r) or r.get('execution_kind')!='real_model'
    if not fixture:
        if r.get('execution_kind')!='real_model' or (r['status']=='completed' and r.get('returncode')!=0):
            raise ValueError('Provider is not an actual successful process completion or attested failure')
        required={'request.json','events.jsonl','stderr.log'}|({'response.txt'} if r['status']=='completed' else set())
        if not required.issubset(r.get('files',{})):
            raise ValueError('Original provider raw evidence inventory is incomplete')
        if any(e.get('item',{}).get('type') not in (None,'agent_message','reasoning') for e in events):
            raise ValueError('Original provider used a forbidden model tool')
    usage=r.get('usage') or {}
    known=all(isinstance(usage.get(key),int) and not isinstance(usage[key],bool) and usage[key]>=0
              for key in ('input_tokens','output_tokens'))
    if r['status']=='failed':
        known=known and bool(failed[0].get('usage')) and failed[0]['usage']==usage
    seconds=r.get('wall_seconds')
    seconds=seconds if isinstance(seconds,(int,float)) and not isinstance(seconds,bool) and math.isfinite(seconds) and seconds>=0 else None
    return q,r,usage if known else None,seconds,bool(fixture)


def _cpu_facts(row, root, registration, fixture_only):
    links=row['sources']; paths={name:_checked(link,root) for name,link in links.items()}
    if _hash(links)!=row['receipt_identity']:
        raise ValueError('CPU receipt identity differs')
    spec=json.loads(paths['registered_spec.json'].read_text(encoding='utf-8'))
    result=json.loads(paths['result.json'].read_text(encoding='utf-8'))
    public=registration['public_task']
    if spec.get('task_id')!=public['task_id'] or spec.get('seed')!=public['seed'] or spec.get('model')!=registration['model_id'] or spec.get('resource_envelope')!=registration['resource_envelope'] or spec.get('task_bundle')!=public.get('task_bundle'):
        raise ValueError('CPU task/model/settings differ from the original boundary registration')
    declared_fixture=_fixture_flags(spec,result)
    fixture=fixture_only or declared_fixture
    if fixture:
        verified = bool(result.get('status')=='success')
        metrics = result.get('metrics',{}) if verified else {}
    else:
        from .verifier import verify
        checked=verify(spec,result,paths['result.json'].parent)
        verified=checked.get('valid') is True
        metrics=checked.get('metrics',{}) if verified else {}
    seconds=result.get('execution_seconds')
    seconds=seconds if isinstance(seconds,(int,float)) and not isinstance(seconds,bool) and math.isfinite(seconds) and seconds>=0 else None
    reference={'run_dir':str(paths['result.json'].parent), 'sources':list(links.values())}
    return spec,result,metrics,seconds,reference,bool(fixture)


def _original_input(row, root, binding, rows, raw, request):
    """Check every physical provider completion against its original input.

    A replay transport row observes an old boundary; it cannot become another
    original pre-provider request or change the original prefix membership.
    """
    link=row.get('boundary')
    original_path=_checked(link,root)
    if original_path.parent!=root/'context-boundaries':
        raise ValueError('Prefix provider input is not its original host capture location')
    original=json.loads(original_path.read_text(encoding='utf-8'))
    if original.get('binding')!=binding or original.get('schema_version')!=SCHEMA_VERSION:
        raise ValueError('Prefix provider has a different original source/condition binding')
    captures=[event for event in rows if event.get('event')=='input_capture' and event.get('boundary')==link]
    if len(captures)!=1:
        raise ValueError('Prefix provider has no unique original input capture')
    capture=captures[0]
    prefix_bytes=b''.join(raw.splitlines(keepends=True)[:capture['index']])
    if (capture['index']!=original['prefix_event_count'] or capture['index']>=row['index']
            or hashlib.sha256(prefix_bytes).hexdigest()!=original['prefix_tape_sha256']
            or capture.get('logical_context')!=original.get('logical_context')
            or row.get('logical_context')!=original.get('logical_context')):
        raise ValueError('Prefix provider original capture order or logical mapping differs')
    transport=Path(original['transport_path'])
    if not transport.is_absolute() or transport.is_symlink() or not transport.resolve().is_relative_to(root):
        raise ValueError('Original prefix transport moved outside its arm')
    requested=[event for line in transport.read_text(encoding='utf-8').splitlines() if line.strip()
               for event in [json.loads(line)] if event.get('status')=='requested'
               and event.get('context_boundary')==link and not event.get('reused_completed_evidence')]
    if (len(requested)!=1 or requested[0].get('call_id')!=original['call_id']
            or requested[0].get('logical_request')!=original.get('logical_context')
            or Path(row['sources']['request.json']['path']).parent.resolve()!=Path(original['provider_directory']).resolve()/original['call_id']):
        raise ValueError('Prefix provider is not its original named transport request')
    if (request.get('prompt')!=original['prompt'] or request.get('full_prompt')!=original['full_prompt']
            or _settings(request)!=original['provider_settings']
            or hashlib.sha256(original['prompt'].encode('utf-8')).hexdigest()!=original['prompt_sha256']
            or hashlib.sha256(original['full_prompt'].encode('utf-8')).hexdigest()!=original['full_prompt_sha256']):
        raise ValueError('Prefix provider original input or settings differs from raw request')
    return original


def audit_context_boundary(boundary_link: dict, arm_output: Path) -> dict:
    """Normalize source-bound original facts; arm names never determine facts."""
    root=Path(arm_output).resolve()
    path=_checked(boundary_link,root); boundary=json.loads(path.read_text(encoding='utf-8'))
    binding=boundary['binding']
    if boundary.get('schema_version')!=SCHEMA_VERSION or binding.get('schema_version')!=SCHEMA_VERSION or binding.get('arm_output')!=str(root):
        raise ValueError('Boundary version or donor arm differs')
    if path.parent!=root/'context-boundaries':
        raise ValueError('Boundary is not the original host capture location')
    registration_path=_checked(binding['registration'],root)
    registration=json.loads(registration_path.read_text(encoding='utf-8'))
    _validate_registration_conditions(registration, binding)
    tape_path=root/'context-boundaries/host-tape.jsonl'; rows,raw=_tape(tape_path)
    captures=[row for row in rows if row.get('event')=='input_capture' and row.get('boundary')==boundary_link]
    if len(captures)!=1:
        raise ValueError('Boundary has no unique original input capture event')
    capture=captures[0]; prefix=rows[:capture['index']]
    raw_prefix=b''.join(raw.splitlines(keepends=True)[:capture['index']])
    if capture['index']!=boundary['prefix_event_count'] or hashlib.sha256(raw_prefix).hexdigest()!=boundary['prefix_tape_sha256'] or capture.get('logical_context')!=boundary['logical_context']:
        raise ValueError('Boundary original prefix order, membership or mapping changed')
    era = None
    if boundary.get('report_era'):
        era=json.loads(_checked(boundary['report_era'],root).read_text(encoding='utf-8'))
        matches=[row for row in prefix if row.get('event')=='report_era' and row.get('era')==boundary['report_era']]
        if len(matches)!=1 or era.get('binding')!=binding or era.get('prefix_event_count')!=matches[0]['index']:
            raise ValueError('Report-selected fields are not their original phase-entry capture')
    transport_path=Path(boundary['transport_path'])
    if not transport_path.is_absolute() or not transport_path.resolve().is_relative_to(root) or transport_path.is_symlink():
        raise ValueError('Boundary transport moved outside the original arm')
    transport=[json.loads(x) for x in transport_path.read_text(encoding='utf-8').splitlines() if x.strip()]
    originals=[row for row in transport if row.get('status')=='requested' and row.get('context_boundary')==boundary_link and not row.get('reused_completed_evidence')]
    if len(originals)!=1 or originals[0].get('call_id')!=boundary['call_id']:
        raise ValueError('Context was not attached to the original pre-provider transport request')
    if originals[0].get('logical_request')!=boundary.get('logical_context'):
        raise ValueError('Original transport logical phase/role/ordinal differs from its capture')
    terminals=[row for row in rows if row.get('event')=='provider_terminal' and row.get('boundary')==boundary_link]
    pending=[]; fixture=_fixture_flags(binding,registration) or boundary.get('provider_implementation',{}).get('canonical_frozen_codex_provider') is not True
    context=boundary.get('logical_context')
    if not isinstance(context,dict) or any(context.get(key) is None for key in ('ordinal','host_ordinal','phase','role')):
        pending.append('missing_original_logical_mapping')
    if len(terminals)!=1:
        pending.append('target_provider_request_not_terminal')
    else:
        if terminals[0].get('logical_context')!=context or Path(terminals[0]['sources']['request.json']['path']).parent.resolve()!=Path(boundary['provider_directory']).resolve()/boundary['call_id']:
            raise ValueError('Target provider receipt moved to a different logical request or directory')
        q,_,_,_,f=_provider_facts(terminals[0],root,binding,registration); fixture=fixture or f
        target_request_fingerprint=q.get('fingerprint')
        if q.get('prompt')!=boundary['prompt'] or q.get('full_prompt')!=boundary['full_prompt'] or _settings(q)!=boundary['provider_settings'] or q.get('fingerprint') is None or q['prompt'] is None:
            raise ValueError('Captured original body/full prompt/settings do not match raw provider request')
    if hashlib.sha256(boundary['prompt'].encode('utf-8')).hexdigest()!=boundary['prompt_sha256'] or hashlib.sha256(boundary['full_prompt'].encode('utf-8')).hexdigest()!=boundary['full_prompt_sha256']:
        raise ValueError('Original input byte binding differs')
    providers=[r for r in rows if r.get('event')=='provider_terminal']
    cpus=[r for r in rows if r.get('event')=='cpu_terminal']
    for group in (providers,cpus):
        identities=[r['receipt_identity'] for r in group]
        if len(set(identities))!=len(identities):
            raise ValueError('An actual receipt is replayed as another physical completion')
    for event in prefix:
        if event.get('event') not in {'provider_terminal','cpu_terminal'}: continue
        original_context=event.get('logical_context')
        if not isinstance(original_context,dict) or any(original_context.get(key) is None for key in ('ordinal','host_ordinal','phase','role')):
            pending.append('prefix_missing_original_logical_mapping')
    cpu_by_identity={row['receipt_identity']:row for row in cpus}
    for event in rows:
        if event.get('event') not in {'host_return','host_return_replay'}: continue
        text=event.get('returned_text')
        if not isinstance(text,str) or hashlib.sha256(text.encode('utf-8')).hexdigest()!=event.get('returned_text_sha256'):
            raise ValueError('Original host return bytes changed')
        for receipt in event.get('cpu_receipts',[]):
            original=cpu_by_identity.get(receipt['receipt_identity'])
            if not original or receipt.get('sources')!=original['sources'] or original['index']>=event['index']:
                raise ValueError('Host return CPU source, order or provenance differs')
        if event.get('host_reply'):
            reply=json.loads(_checked(event['host_reply'],root).read_text(encoding='utf-8'))
            if reply.get('returned_text')!=text or reply.get('logical_request')!=event.get('logical_context'):
                raise ValueError('Original tool output differs from its source-bound logical reply')
    # Completeness is checked against the entire original arm inventory, including
    # later records. Later records are discovered for integrity, never counted here.
    actual_provider={str(_checked(r['sources']['request.json'],root)) for r in providers}
    discovered_provider={str(p.resolve()) for parent in (root/'model',root/'attempts') if parent.exists()
                         for p in parent.rglob('request.json') if p.parent.name.startswith(('improved-','upstream-'))}
    actual_cpu={str(_checked(r['sources']['registered_spec.json'],root)) for r in cpus}
    discovered_cpu={str(p.resolve()) for parent in (root/'research',root/'attempts') if parent.exists()
                    for p in parent.rglob('registered_spec.json')}
    if actual_provider-discovered_provider or actual_cpu-discovered_cpu:
        raise ValueError('Context tape contains a transplanted or undiscovered physical receipt')
    unmapped_provider=discovered_provider-actual_provider
    for value in unmapped_provider:
        folder=Path(value).parent
        for model_trace in root.rglob('*transport*.jsonl'):
            if model_trace==tape_path: continue
            for line in model_trace.read_text(encoding='utf-8').splitlines():
                if not line.strip(): continue
                row=json.loads(line)
                if row.get('status') in {'completed','failed'} and row.get('context_boundary') and row.get('evidence_dir') and Path(row['evidence_dir']).resolve()==folder:
                    raise ValueError('Context tape omits an originally mapped provider completion')
    if unmapped_provider or discovered_cpu-actual_cpu:
        pending.append('raw_terminal_receipt_has_missing_original_host_mapping')
    for value in discovered_cpu-actual_cpu:
        result_path=str(Path(value).parent/'result.json')
        for reply_path in root.rglob('tool-replies/*.json'):
            reply=json.loads(reply_path.read_text(encoding='utf-8'))
            if any(str(Path(link['path']).resolve())==result_path for link in reply.get('execution_receipts',[])):
                raise ValueError('Context tape omits an originally mapped CPU completion')
    all_provider={}
    for row in providers:
        all_provider[row['receipt_identity']]=_provider_facts(row,root,binding,registration)
        _original_input(row,root,binding,rows,raw,all_provider[row['receipt_identity']][0])
    all_cpu={}
    for row in cpus:
        all_cpu[row['receipt_identity']]=_cpu_facts(row,root,registration,fixture)
    selected_provider=[r for r in prefix if r.get('event')=='provider_terminal']
    selected_cpu=[r for r in prefix if r.get('event')=='cpu_terminal']
    input_tokens=output_tokens=0; wall=[]; cpu_time=[]; known=True; wall_known=True; cpu_known=True
    completed_lower={'input_tokens':0,'output_tokens':0}; completed=failed=0
    evidence=[boundary_link,binding['registration'],_link(tape_path),_link(transport_path)]
    for row in selected_provider:
        q,r,usage,seconds,f=all_provider[row['receipt_identity']]; fixture=fixture or f
        completed+=r['status']=='completed'; failed+=r['status']=='failed'
        if usage is None: known=False
        else:
            input_tokens+=usage['input_tokens']; output_tokens+=usage['output_tokens']
            if r['status']=='completed':
                for key in completed_lower: completed_lower[key]+=usage[key]
        if seconds is None: wall_known=False
        else: wall.append(seconds)
        evidence.extend(row['sources'].values())
    configs=[]; metric_entries=[]
    for row in selected_cpu:
        spec,result,metrics,seconds,reference,f=all_cpu[row['receipt_identity']]; fixture=fixture or f
        configs.append(_hash(spec['config']))
        if seconds is None: cpu_known=False
        else: cpu_time.append(seconds)
        evidence.extend(row['sources'].values())
        metric_entries.append((row,reference,metrics))
    prompt=boundary['prompt']; available=[]
    # Availability is value-bearing original input, never a path/hash inference.
    try: decoded=json.loads(prompt)
    except json.JSONDecodeError: decoded=None
    for row,reference,metrics in metric_entries:
        folder=Path(reference['run_dir']); rid=folder.name
        spans=[]
        if isinstance(decoded,dict):
            for record in decoded.get('verified_memory',[]):
                if record.get('run_id')==rid and record.get('metrics')==metrics:
                    candidates=(json.dumps(record,ensure_ascii=False,sort_keys=True),
                                json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':')))
                    for block in candidates:
                        start=prompt.find(block)
                        if start>=0: spans.append((start,start+len(block),{'kind':'original_memory_value','run_id':rid}))
        for event in prefix:
            if event.get('event') not in {'host_return','host_return_replay'}: continue
            if not any(item['receipt_identity']==row['receipt_identity'] for item in event.get('cpu_receipts',[])): continue
            block=event['returned_text']; start=prompt.find(block)
            if start>=0 and block:
                try: host=json.loads(block)
                except json.JSONDecodeError: continue
                if host.get('metrics')==metrics:
                    spans.append((start,start+len(block),{'kind':'original_host_return','event_sha256':event['event_sha256']}))
        if spans:
            start,end,source=spans[0]
            for metric,value in metrics.items():
                available.append({'run':reference,'metric':metric,'value':value,
                    'input_span':{'start':start,'end':end,'sha256':hashlib.sha256(prompt[start:end].encode('utf-8')).hexdigest()},
                    'source_binding':{**source,'boundary':boundary_link,'cpu_receipt_identity':row['receipt_identity']}})
    planning={}
    if isinstance(decoded,dict):
        for key in ('goal','instructions','proposal_feedback'):
            if key in decoded:
                planning[key]={'text':decoded[key] if isinstance(decoded[key],str) else json.dumps(decoded[key],ensure_ascii=False,sort_keys=True),
                               'scope':'preexecution_planning',
                               'source_binding':{'boundary':boundary_link,'json_pointer':'/'+key}}
    if era and isinstance(era.get('selected_plan'),str) and era['selected_plan'] and era['selected_plan'] in prompt:
        planning['selected_native_plan']={'text':era['selected_plan'],'scope':'original_plan_visible_in_named_input',
                                         'source_binding':{'boundary':boundary_link,'report_era':boundary['report_era'],'field':'selected_plan'}}
    return {'schema_version':SCHEMA_VERSION,'eligible':not pending and not fixture,'fixture_only':bool(fixture),
        'pending_reasons':pending+(['synthetic_or_fixture_receipt_ineligible_for_actual_adoption'] if fixture else []),
        'scope':'historical_pre_request','phase':context.get('phase') if isinstance(context,dict) else None,
        'role':context.get('role') if isinstance(context,dict) else None,
        'logical_ordinal':context.get('ordinal') if isinstance(context,dict) else None,
        'call_id':boundary['call_id'],
        'request_fingerprint':target_request_fingerprint if len(terminals)==1 else None,
        'request_source':terminals[0]['sources']['request.json'] if len(terminals)==1 else None,
        'original_conditions':{'model_id':binding['model_id'],'reasoning_effort':binding['reasoning_effort'],
                               'resource_envelope_sha256':binding['resource_envelope_sha256'],
                               'public_task_sha256':binding['public_task_sha256'],'registration':binding['registration']},
        'measures':{'actual_cpu_executions':len(selected_cpu),'distinct_configurations':len(set(configs)),
                    'completed_provider_calls':completed,'failed_provider_attempts':failed,
                    'input_tokens':input_tokens if known else None,'output_tokens':output_tokens if known else None,
                    'wall_seconds':math.fsum(wall) if wall_known else None,
                    'cpu_execution_seconds':math.fsum(cpu_time) if cpu_known else None},
        'completed_token_usage_lower_bound':completed_lower,'available_metrics':available,
        'prior_runs':[reference for _,reference,_ in metric_entries],
        'planning_units':planning,'next_questions':{},'evidence':evidence,
        'report_era':boundary.get('report_era'),
        'limits':'Original named input availability only; not absence in full history, reading/comprehension, final totals or a future improvement.'}
