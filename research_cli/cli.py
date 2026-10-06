"""Human help and stable JSON command interface."""
import argparse
import json
from pathlib import Path
import sys
import sqlite3
from .core import ResearchError, Store
from .runner import run, recover, verify
from . import __version__


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ResearchError('INVALID_INPUT', message)


def _input(path):
    if isinstance(path, (dict, list)):
        return path  # The optional MCP transport supplies the same JSON directly.
    try:
        text = sys.stdin.read() if path == '-' else Path(path).read_text(encoding='utf-8-sig')
        return json.loads(text)
    except (OSError, ValueError) as exc:
        raise ResearchError('INVALID_INPUT', 'Cannot read JSON input: '+str(exc)) from exc


def _output(value, path):
    if path:
        try:
            with Path(path).open('x', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
                stream.write('\n')
        except FileExistsError as exc:
            raise ResearchError('CONFLICT', 'Output already exists; use a new path', {'path': str(Path(path).resolve())}) from exc
    return value


def parser():
    p = Parser(prog='research-state', description='Research state and evidence CLI. Models and scientific choices belong to the external agent.')
    p.add_argument('--workspace', required=True, help='Research storage directory')
    commands = p.add_subparsers(dest='command', required=True)
    commands.add_parser('init', help='Create an empty research store and local owner capability')
    help_command = commands.add_parser('help', help='Return machine-readable interface help')
    help_command.add_argument('--topic', choices=['register', 'laya', 'goal'], help='Return a public JSON input example')
    goal = commands.add_parser('goal', help='Create a research goal')
    goal.add_argument('--title', required=True)
    goal.add_argument('--description', default='')
    goal.add_argument('--input', help='Structured external goal brief JSON; no experiment authorization is inferred')
    goal.add_argument('--request-key', help='Use the same request key across CLI/stdio/WebMCP retries')
    goal.add_argument('--expect', type=int)
    for operation in ('goal_show', 'goal_amend', 'goal_close', 'goal_resume', 'resource', 'resource_show'):
        command = commands.add_parser(operation, help='Versioned goal lifecycle or external resource observations')
        command.add_argument('--goal', required=True)
        if operation in ('goal_show', 'resource_show'):
            command.add_argument('--limit', type=int, default=20)
            command.add_argument('--offset', type=int, default=0)
        else:
            command.add_argument('--request-key', required=True)
            command.add_argument('--expect', type=int, required=operation != 'resource')
        if operation in ('goal_amend', 'goal_close', 'goal_resume'):
            command.add_argument('--reason', required=True)
        if operation in ('goal_amend', 'resource'):
            command.add_argument('--input', required=True, help='Finite JSON brief or resource observation')
        if operation == 'goal_amend':
            command.add_argument('--title')
            command.add_argument('--description')
            command.add_argument('--change-kind', choices=['meaning', 'scope', 'plan'], required=True)
        if operation == 'goal_close':
            command.add_argument('--state', choices=['completed', 'paused', 'cancelled'], required=True)
            command.add_argument('--input', required=True, help='JSON object with results and incomplete text arrays')
    h = commands.add_parser('hypothesis', help='Record an externally proposed hypothesis')
    h.add_argument('--goal', required=True)
    h.add_argument('--statement', required=True)
    h.add_argument('--expect', type=int)
    v = commands.add_parser('validator', help='Owner: freeze a Python validator')
    v.add_argument('--name', required=True)
    v.add_argument('--input', required=True, help='JSON command array, or {command:[...]}')
    v.add_argument('--key', required=True, help='Path to owner.key')
    r = commands.add_parser('register', help='Freeze experiment conditions; changes require new registrations')
    r.add_argument('--goal', required=True)
    r.add_argument('--input', required=True)
    r.add_argument('--request-key', required=True)
    r.add_argument('--expect', type=int)
    st = commands.add_parser('status', help='Allowed work and missing evidence; no scientific ranking')
    st.add_argument('--goal')
    st.add_argument('--limit', type=int, default=20)
    st.add_argument('--offset', type=int, default=0)
    for name in ['run', 'recover', 'verify', 'show', 'decide', 'evidence']:
        sub = commands.add_parser(name)
        sub.add_argument('--registration', required=True)
        if name in ('run', 'recover', 'verify'):
            sub.add_argument('--full', action='store_true', help='Return original full receipts and verifier details; otherwise return a summary')
        if name == 'run':
            sub.add_argument('--request-key', required=True)
            sub.add_argument('--expect', type=int)
        elif name == 'decide':
            sub.add_argument('--decision', choices=['adopted', 'rejected', 'inconclusive'], required=True)
            sub.add_argument('--reason', required=True)
            sub.add_argument('--expect', type=int)
        elif name == 'evidence':
            sub.add_argument('--kind', choices=['measured', 'literature', 'inference', 'proposal'], required=True)
            sub.add_argument('--claim', required=True)
            sub.add_argument('--path')
            sub.add_argument('--expect', type=int)
    m = commands.add_parser('memory', help='Search summaries without returning all raw records')
    m.add_argument('--query', default='')
    m.add_argument('--outcome')
    m.add_argument('--verification')
    m.add_argument('--limit', type=int, default=20)
    m.add_argument('--offset', type=int, default=0)
    ex = commands.add_parser('export', help='Export consistent state and hashed evidence')
    ex.add_argument('--output', required=True)
    re = commands.add_parser('restore', help='Restore into a new empty directory; never launch executions')
    re.add_argument('--input', required=True)
    laya = commands.add_parser('laya', help='Optional candidate exchange with externally run Laya; no model execution')
    actions = laya.add_subparsers(dest='laya_action', required=True)
    prepared = actions.add_parser('prepare', help='Export candidates, current memory and Laya SDK request')
    prepared.add_argument('--input', required=True, help='Candidate JSON file, or - for stdin')
    prepared.add_argument('--output', help='New bundle JSON file; existing files are never overwritten')
    resolved = actions.add_parser('resolve', help='Map an external SDK response to an unverified proposal')
    resolved.add_argument('--input', required=True, help='Original bundle JSON file, or - for stdin')
    resolved.add_argument('--response', required=True, help='External Laya SDK response JSON file')
    resolved.add_argument('--expected-sha256', required=True, help='Bundle digest saved separately at prepare time')
    resolved.add_argument('--output', help='New proposal JSON file for evidence --kind proposal')
    return p


def _registration_example(root):
    interpreter = sys.executable
    if (root/'.research/state.sqlite3').is_file():
        interpreter = Store(root).runner_interpreter()
    return {'hypothesis_id': 'REPLACE_WITH_HYPOTHESIS_ID', 'change': 'Describe the candidate change',
            'comparison': 'Describe the comparator', 'data_split': {'development': 'Describe public data', 'evaluation': 'Describe independent evaluation'},
            'seed': 0, 'source_version': {'label': 'candidate-v1', 'files': {'task.py': '0'*64}},
            'metrics': ['correct'], 'criteria': [{'metric': 'correct', 'op': '>=', 'threshold': 1}],
            'command': [interpreter, 'task.py'], 'cwd': str(root/'experiment'),
            'artifacts': [{'name': 'result', 'path': 'result.json'}], 'validator': 'REPLACE_WITH_FROZEN_VALIDATOR_NAME'}


def _compact(result, store):
    """Present existing core results without repeating receipts or verifier output."""
    record = result['record']
    registration, execution, verification = record['registration'], record['run'], record['verification']
    evidence = [item for item in record['evidence'] if execution and item.get('run_id') == execution['id']]
    declared = {item['name'] for item in registration['spec']['artifacts']}
    artifacts = [item for item in evidence if item['name'] in declared]
    missing = sorted(declared - {item['name'] for item in artifacts})
    invalid = sum(item['integrity'] != 'valid' for item in evidence)
    integrity = 'invalid' if missing or invalid else 'valid'
    summary = {'registration': {name: registration[name] for name in ('id', 'goal_id', 'fingerprint')},
               'run': None, 'verification': None, 'decision': {'state': record['decision']['state']},
               'revision': record['revision'], 'evidence_integrity': integrity,
               'evidence_summary': {'total': len(evidence), 'invalid': invalid,
                                    'missing_artifact_count': len(missing), 'missing_artifacts': missing[:10]},
               'artifacts': [{name: item[name] for name in ('name', 'sha256', 'integrity', 'verified')}
                             | {'path': str((store.root/item['path']).resolve())} for item in artifacts[:10]],
               'artifact_total': len(artifacts), 'artifacts_remaining': max(0, len(artifacts)-10),
               'claim_verified': bool(verification and verification['state'] == 'passed' and integrity == 'valid'),
               'detail_retrieval': {'command': 'show', 'registration_id': registration['id'], 'workspace': str(store.root)}}
    if execution:
        summary['run'] = {name: execution[name] for name in ('id', 'state', 'resources')}
        summary['run']['execution_directory'] = str(store.metadata_dir/'runs'/execution['id']/'work')
        if (execution.get('receipt') or {}).get('error'):
            summary['run']['error'] = execution['receipt']['error']
    if verification:
        names = registration['spec']['metrics'][:20]
        details = verification['details']
        summary['verification'] = {'run_id': verification['run_id'], 'state': verification['state'],
                                   'metrics': {name: verification['metrics'][name] for name in names if name in verification['metrics']},
                                   'metric_total': len(verification['metrics']),
                                   'criteria_results': details.get('criteria_results', [])[:10],
                                   'criteria_total': len(details.get('criteria_results', []))}
        if details.get('error'):
            summary['verification']['error'] = details['error']
    output = {name: result[name] for name in ('started', 'reused', 'resume') if name in result}
    if 'recovered' in result:
        output['receipt_collected'] = result['recovered']
    output['record'] = summary
    return output


def dispatch(args):
    root = Path(args.workspace).resolve()
    name = args.command
    if name == 'help':
        if args.topic == 'goal':
            return {'version': __version__, 'brief_example': {
                    'original_request': 'Preserve the original user request', 'long_term_goal': 'Answer a research question',
                    'context': 'Where the result will be used', 'scope': {}, 'facts': [], 'assumptions': [], 'unknowns': [],
                    'deliverables': [], 'completion_criteria': [], 'evaluation': {}, 'permissions': {},
                    'resource_constraints': {'cost': 'unknown', 'time': 'not set'}, 'initial_plan': [], 'reporting': {}, 'handoff': {}},
                    'commands': ['goal', 'goal_show', 'goal_amend', 'goal_close', 'goal_resume', 'resource', 'resource_show'],
                    'authority': 'A goal brief or plugin invocation is not execution authorization or scientific verification',
                    'versions': 'Amend appends a version; registrations pin their original goal version and criteria',
                    'retry': 'Reuse exact request_key across channels. Amend/close/resume require expect; already applied identical retries reuse original results',
                    'closure_example': {'results': [], 'incomplete': []},
                    'resource_example': {'source': 'external usage log', 'source_ref': 'unique receipt reference',
                                         'cost': {'status': 'unknown', 'amount': None, 'currency': None},
                                         'tokens': {'status': 'unknown', 'value': None}},
                    'cost_scope': 'Observed subtotals only; overall cost remains unknown without complete external observation'}
        if args.topic == 'laya':
            from .laya import example
            return {'version': __version__, 'example': example(),
                    'prepare': 'laya prepare --input FILE --output NEW_BUNDLE_FILE',
                    'resolve': 'laya resolve --input BUNDLE_FILE --response SDK_RESPONSE_FILE --expected-sha256 SAVED_DIGEST --output NEW_PROPOSAL_FILE',
                    'external_inference': 'The external agent supplies bundle.request.state/questions to Laya and saves the raw SDK response',
                    'memory_links': 'Candidate evidence lists existing registration IDs; CLI reads verification and current integrity',
                    'meaning': 'All candidates and predictions are unverified proposals; no scientific choice, validation or adoption is automatic',
                    'token_preservation': 'unknown; external agent must check SDK tokenizer/context/head limits',
                    'record': 'evidence --registration ID --kind proposal --claim TEXT --path PROPOSAL_FILE',
                    'guide': 'LAYA.ko.md'}
        if args.topic == 'register':
            return {'version': __version__, 'example': _registration_example(root),
                    'replace': 'Replace IDs, validator, cwd, metric and all source hashes before registration. Zero hash is a placeholder.',
                    'source_files': 'Pin every experiment source/data file, including the executed Python file.',
                    'output_location': 'The runner writes outputs in its snapshot work directory; collected artifacts have preserved blob paths.'}
        return {'version': __version__, 'commands': ['init','goal','goal_show','goal_amend','goal_close','goal_resume','resource','resource_show','hypothesis','validator','register','status','run','recover','verify','decide','evidence','memory','show','export','restore','laya'],
                'json_input': '--input FILE or --input - for stdin',
                'registration_json': 'help --topic register returns the public example; register --help shows command arguments',
                'execution_output': 'run/recover/verify return compact data.record states, metrics and preserved artifact paths; --full or show returns full original detail',
                'memory_query': 'Literal substring search, not token or semantic search; use limit/offset pages',
                'laya': 'Optional prepare/resolve exchange for externally executed Laya; help --topic laya returns input and instructions',
                'conflicts': '--expect workspace revision to reject stale writes',
                'unknown_resume': 'recover inspects receipts; unknown executions are never automatically restarted',
                'roles': 'agent records proposals/registers/runs; owner freezes validators; fixed verifier produces verified metrics',
                'security': 'Local capabilities and hashes are not OS isolation'}
    if name == 'init':
        return Store.init(root)
    if name == 'restore':
        from .transfer import restore
        return restore(root, Path(args.input))
    store = Store(root)
    if name == 'laya':
        from .laya import prepare, resolve
        if args.laya_action == 'prepare':
            return _output(prepare(store, _input(args.input)), args.output)
        if args.input == '-' and args.response == '-':
            raise ResearchError('INVALID_INPUT', 'Only one Laya input can read stdin')
        return _output(resolve(store, _input(args.input), _input(args.response), args.expected_sha256), args.output)
    if name == 'goal':
        brief = _input(args.input) if getattr(args, 'input', None) is not None else getattr(args, 'brief', {})
        return store.goal_create(args.title, args.description, getattr(args, 'expect', None), brief=brief,
                                 request_key=getattr(args, 'request_key', None))
    if name == 'goal_show':
        return store.goal_show(args.goal, args.limit, args.offset)
    if name == 'goal_amend':
        brief = _input(args.input) if getattr(args, 'input', None) is not None else args.brief
        return store.goal_amend(args.goal, brief, args.reason, args.change_kind, args.request_key, args.expect,
                                args.title, args.description)
    if name == 'goal_close':
        report = _input(args.input) if getattr(args, 'input', None) is not None else {'results': args.results, 'incomplete': args.incomplete}
        if not isinstance(report, dict) or set(report) != {'results', 'incomplete'}:
            raise ResearchError('INVALID_INPUT', 'Closure input must contain results and incomplete arrays')
        return store.goal_close(args.goal, args.state, args.reason, report['results'], report['incomplete'], args.request_key, args.expect)
    if name == 'goal_resume':
        return store.goal_resume(args.goal, args.reason, args.request_key, args.expect)
    if name == 'resource':
        observation = _input(args.input) if getattr(args, 'input', None) is not None else args.observation
        return store.resource_record(args.goal, observation, args.request_key, args.expect)
    if name == 'resource_show':
        return store.resource_show(args.goal, args.limit, args.offset)
    if name == 'hypothesis':
        return store.hypothesis_create(args.goal, args.statement, args.expect)
    if name == 'validator':
        value = _input(args.input)
        command = value['command'] if isinstance(value, dict) else value
        return store.validator_register(args.name, command, Path(args.key).read_text(encoding='utf-8').strip())
    if name == 'register':
        return store.register(args.goal, _input(args.input), args.request_key, args.expect)
    if name == 'status':
        return store.status(args.goal, args.limit, args.offset)
    if name == 'run':
        result = run(store, args.registration, args.request_key, args.expect)
        return result if args.full else _compact(result, store)
    if name == 'recover':
        result = recover(store, args.registration)
        return result if args.full else _compact(result, store)
    if name == 'verify':
        result = verify(store, args.registration)
        return result if args.full else _compact(result, store)
    if name == 'decide':
        return store.decide(args.registration, args.decision, args.reason, args.expect)
    if name == 'evidence':
        return store.add_evidence(args.registration, args.kind, args.claim, args.path, args.expect)
    if name == 'memory':
        return store.memory(args.query, args.outcome, args.verification, args.limit, args.offset)
    if name == 'show':
        return store.show(args.registration)
    if name == 'export':
        from .transfer import export
        return export(store, Path(args.output))
    raise ResearchError('INVALID_INPUT', 'Unknown command')


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    try:
        result = dispatch(parser().parse_args(argv))
        print(json.dumps({'ok': True, 'data': result}, ensure_ascii=False, allow_nan=False))
        return 0
    except ResearchError as exc:
        print(json.dumps({'ok': False, 'error': {'code': exc.code, 'message': str(exc), 'details': exc.details}}, ensure_ascii=False))
        return {'INVALID_INPUT': 2, 'INVALID_TRANSITION': 3, 'CONFLICT': 4,
                'REVISION_CONFLICT': 4, 'STATE_CONFLICT': 4, 'REQUEST_CONFLICT': 4,
                'EVIDENCE_INVALID': 5, 'EVIDENCE_MISSING': 5, 'EVIDENCE_TAMPERED': 5,
                'PERMISSION_DENIED': 6, 'AUTHORITY_REQUIRED': 6, 'EXECUTION_UNKNOWN': 7,
                'REGISTRATION_IMMUTABLE': 3, 'DUPLICATE_EXPERIMENT': 4,
                'NOT_INITIALIZED': 2, 'NOT_FOUND': 2}.get(exc.code, 1)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(json.dumps({'ok': False, 'error': {'code': 'INVALID_INPUT', 'message': str(exc), 'details': {}}}, ensure_ascii=False))
        return 2
