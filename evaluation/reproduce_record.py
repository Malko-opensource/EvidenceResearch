"""Recompute a frozen verifier from an original or restored record; never update state."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_cli.core import ResearchError, Store, sha256_file


def reproduce(workspace, registration):
    store = Store(workspace)
    record = store.show(registration)
    if not record['run'] or record['run']['state'] not in ('succeeded', 'failed'):
        raise ValueError('A known completed execution is required')
    validator = store.get_validator(record['registration']['spec']['validator'])
    evidence = []
    hashes = dict(validator['hashes'])
    for item in record['evidence']:
        if item.get('run_id') != record['run']['id'] or not item.get('path'):
            continue
        path = (store.root/item['path']).resolve()
        if item['integrity'] != 'valid':
            raise ValueError('Evidence missing or modified: '+item['name'])
        evidence.append(item | {'path': str(path)})
        hashes[str(path)] = item['sha256']
    names = {item['name']: item['path'] for item in evidence}
    artifacts = {item['name']: names[item['name']] for item in record['registration']['spec']['artifacts']}
    bundle = {'registration': record['registration'], 'run': record['run'], 'evidence': evidence, 'artifacts': artifacts}
    for path, expected in hashes.items():
        if sha256_file(path) != expected:
            raise ValueError('Pinned hash mismatch: '+path)
    with tempfile.TemporaryDirectory(prefix='research-reproduction-') as directory:
        source = Path(directory)/'bundle.json'
        source.write_text(json.dumps(bundle, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        command = [part.replace('{bundle}', str(source)) for part in validator['command']]
        completed = subprocess.run(command, cwd=directory, capture_output=True, text=True, encoding='utf-8',
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    for path, expected in hashes.items():
        if sha256_file(path) != expected:
            raise ValueError('Evidence or verifier changed during reproduction: '+path)
    if completed.returncode:
        raise ValueError('Frozen verifier failed: '+completed.stderr)
    result = json.loads(completed.stdout)
    return {'registration_id': registration, 'result': result,
            'registered_criteria': record['registration']['spec']['criteria'],
            'interpreter': command[0], 'validator_sha256': validator['sha256'], 'research_state_updated': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--registration', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps({'ok': True, 'data': reproduce(args.workspace, args.registration)}, ensure_ascii=False, allow_nan=False))
    except (OSError, ValueError, KeyError, ResearchError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
