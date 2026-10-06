"""Adapters connecting durable state to the local runner and fixed verifiers."""
import hashlib
import hmac
import json
import math
from pathlib import Path
import subprocess
import sys
from .core import ResearchError, canonical, sha256_file


def _signature(value, key):
    return hmac.new(key.encode(), canonical(value).encode(), hashlib.sha256).hexdigest()


def _atomic(path, value):
    import os
    temporary = path.with_suffix('.tmp')
    temporary.write_text(canonical(value), encoding='utf-8')
    os.replace(temporary, path)


def _collect(store, registration_id):
    record = store.show(registration_id)
    run = record['run']
    if not run:
        raise ResearchError('INVALID_TRANSITION', 'No execution to recover')
    if run['state'] in ('succeeded', 'failed', 'cancelled'):
        return {'recovered': False, 'record': record}
    attempt = store.metadata_dir/'runs'/run['id']
    path = attempt/'receipt.json'
    if not path.is_file():
        store.mark_unknown(run['id'], 'No durable receipt. Inspect launch/process/log files; do not automatically rerun.')
        return {'recovered': False, 'record': store.show(registration_id),
                'resume': {'receipt': str(path), 'inspection_directory': str(attempt),
                           'action': 'Recover again after the original worker produces a valid receipt. Otherwise retain unknown.'}}
    try:
        envelope = json.loads(path.read_text(encoding='utf-8'))
        receipt = envelope['receipt']
        request = json.loads((attempt/'request.json').read_text(encoding='utf-8'))['request']
        if not hmac.compare_digest(_signature(receipt, store.internal_key()), envelope['signature']):
            raise ValueError('Receipt signature mismatch')
        if receipt['run_id'] != run['id'] or receipt['registration_id'] != record['registration']['id']:
            raise ValueError('Receipt identity mismatch')
        if receipt['request_sha256'] != hashlib.sha256(canonical(request).encode()).hexdigest():
            raise ValueError('Receipt request mismatch')
        if not hmac.compare_digest(_signature(request, store.internal_key()),
                                   json.loads((attempt/'request.json').read_text(encoding='utf-8'))['signature']):
            raise ValueError('Request signature mismatch')
        evidence = []
        for item in receipt['files']:
            source = Path(item['path']).resolve()
            if not source.is_relative_to(attempt.resolve()) or not source.is_file() or sha256_file(source) != item['sha256']:
                raise ValueError('Receipt evidence missing or modified: '+item['name'])
            evidence.append({**item, 'kind': 'measured', 'claim': 'Local runner file; verification remains separate'})
        store.complete_run(run['id'], receipt, evidence, receipt['resources'], store.internal_key())
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        store.mark_unknown(run['id'], str(exc))
        raise ResearchError('EVIDENCE_INVALID', str(exc), {'resume': 'Inspect original worker evidence; do not rerun unknown execution'}) from exc
    return {'recovered': True, 'record': store.show(registration_id)}


def run(store, registration_id, request_key, expected_revision=None):
    claim = store.claim(registration_id, request_key, expected_revision)
    if not claim['claimed']:
        return {'started': False, 'record': store.show(registration_id),
                'resume': 'Use recover for running/unknown; completed executions are reused.'}
    record = store.show(registration_id)
    attempt = store.metadata_dir/'runs'/claim['run']['id']
    attempt.mkdir(parents=True, exist_ok=False)
    request = {'run_id': claim['run']['id'], 'registration_id': record['registration']['id'],
               'spec': record['registration']['spec'], 'key_path': str(store.metadata_dir/'internal.key')}
    _atomic(attempt/'request.json', {'request': request, 'signature': _signature(request, store.internal_key())})
    try:
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('worker.py')), str(attempt/'request.json')],
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        _atomic(attempt/'worker.json', {'pid': process.pid})
        process.wait()
    except (OSError, KeyboardInterrupt) as exc:
        store.mark_unknown(claim['run']['id'], f'Controller interrupted: {exc}; original worker may still be running')
        raise ResearchError('EXECUTION_UNKNOWN', 'Controller interrupted; use recover, never rerun automatically') from exc
    result = _collect(store, registration_id)
    result['started'] = True
    return result


def recover(store, registration_id):
    return _collect(store, registration_id)


def verify(store, registration_id):
    record = store.show(registration_id)
    if not record['run'] or record['run']['state'] not in ('succeeded', 'failed'):
        raise ResearchError('INVALID_TRANSITION', 'Verification requires a known completed execution')
    validator = store.get_validator(record['registration']['spec']['validator'])
    if record.get('verification'):
        try:
            for path, expected in validator['hashes'].items():
                if sha256_file(path) != expected:
                    raise ValueError('Fixed validator hash mismatch')
            for item in record['evidence']:
                if item.get('path'):
                    path = Path(item['path'])
                    if not path.is_absolute():
                        path = store.root/path
                    if sha256_file(path) != item['sha256']:
                        raise ValueError('Evidence changed after verification')
        except (ResearchError, OSError, ValueError) as exc:
            raise ResearchError('EVIDENCE_INVALID', str(exc), {'historical_verification': record['verification']['state']}) from exc
        return {'reused': True, 'record': record}
    attempt = store.metadata_dir/'runs'/record['run']['id']
    evidence = []
    metrics = {}
    details = {'integrity': True}
    try:
        for path, expected in validator['hashes'].items():
            if sha256_file(path) != expected:
                raise ValueError('Fixed validator hash mismatch')
        for item in record['evidence']:
            if not item.get('path'):
                continue
            path = Path(item['path'])
            if not path.is_absolute():
                path = store.root/path
            if not path.is_file() or sha256_file(path) != item['sha256']:
                raise ValueError('Evidence missing or modified: '+item['name'])
            evidence.append({**item, 'path': str(path.resolve())})
        names = {e['name']: e['path'] for e in evidence if e['kind'] == 'measured'}
        declared = record['registration']['spec']['artifacts']
        if any(a['name'] not in names for a in declared):
            raise ValueError('Declared artifact missing')
        bundle = {'registration': record['registration'], 'run': record['run'], 'evidence': evidence,
                  'artifacts': {a['name']: names[a['name']] for a in declared}}
        _atomic(attempt/'verification-input.json', bundle)
        command = [arg.replace('{bundle}', str(attempt/'verification-input.json')) for arg in validator['command']]
        completed = subprocess.run(command, cwd=attempt, capture_output=True, text=True, encoding='utf-8',
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (attempt/'verifier.stdout.log').write_text(completed.stdout, encoding='utf-8')
        (attempt/'verifier.stderr.log').write_text(completed.stderr, encoding='utf-8')
        if completed.returncode:
            raise ValueError('Fixed verifier exited with '+str(completed.returncode))
        output = json.loads(completed.stdout)
        if not isinstance(output, dict) or not isinstance(output.get('metrics'), dict) or not isinstance(output.get('details', {}), dict):
            raise ValueError('Verifier output must contain metrics and details objects')
        metrics = output['metrics']
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in metrics.values()):
            raise ValueError('Verifier metrics must be finite numbers')
        canonical(output)
        details.update(output.get('details', {}))
        details['verifier_output'] = output
        details['verifier_stdout_sha256'] = sha256_file(attempt/'verifier.stdout.log')
        details['verifier_stderr_sha256'] = sha256_file(attempt/'verifier.stderr.log')
        details['integrity'] = True
        for path, expected in validator['hashes'].items():
            if sha256_file(path) != expected:
                raise ValueError('Fixed validator changed during verification')
        for item in evidence:
            if sha256_file(item['path']) != item['sha256']:
                raise ValueError('Evidence changed during verification')
    except (OSError, ValueError, KeyError, json.JSONDecodeError, ResearchError) as exc:
        metrics = {}
        details = {'integrity': False, 'error': str(exc)}
    details['validator_sha256'] = validator['sha256']
    details['source'] = 'fixed_local_verifier'
    result = store.complete_verification(record['run']['id'], metrics, details, store.internal_key())
    return {'verification': result, 'record': store.show(registration_id)}
