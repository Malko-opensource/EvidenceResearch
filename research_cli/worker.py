"""Small replaceable local runner. This file uses only the standard library."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sign(value, key):
    return hmac.new(key.encode(), canonical(value).encode(), hashlib.sha256).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(canonical(value), encoding='utf-8')
    os.replace(temporary, path)


def execute(request_path):
    request_path = Path(request_path).resolve()
    envelope = json.loads(request_path.read_text(encoding='utf-8'))
    request = envelope['request']
    key = Path(request['key_path']).read_text(encoding='utf-8').strip()
    if not hmac.compare_digest(sign(request, key), envelope['signature']):
        raise ValueError('Request signature mismatch')
    spec = request['spec']
    attempt = request_path.parent
    stage = attempt / 'work'
    stage.mkdir()
    began = time.monotonic()
    receipt = {'run_id': request['run_id'], 'registration_id': request['registration_id'],
               'request_sha256': hashlib.sha256(canonical(request).encode()).hexdigest(),
               'state': 'failed', 'exit_code': None, 'files': [], 'error': None}
    stdout = attempt/'stdout.log'
    stderr = attempt/'stderr.log'
    stdout.touch()
    stderr.touch()
    try:
        for relative, expected in spec['source_version']['files'].items():
            origin = (Path(spec['cwd'])/relative).resolve()
            if not origin.is_relative_to(Path(spec['cwd']).resolve()):
                raise ValueError('Source escaped cwd')
            destination = stage/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, destination)
            if digest(destination) != expected:
                raise ValueError('Pinned source hash mismatch: '+relative)
            receipt['files'].append({'name': 'source:'+relative, 'path': str(destination),
                                     'origin_path': str(origin), 'sha256': expected})
        command = list(spec['command'])
        script = Path(command[1])
        if script.is_absolute():
            script = script.resolve().relative_to(Path(spec['cwd']).resolve())
        command[1] = str(script)
        atomic_json(attempt/'launch.json', {'command': command, 'cwd': str(stage), 'at': time.time()})
        with stdout.open('wb') as out, stderr.open('wb') as err:
            process = subprocess.Popen(command, cwd=stage, stdout=out, stderr=err,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            atomic_json(attempt/'process.json', {'pid': process.pid, 'worker_pid': os.getpid(), 'at': time.time()})
            timeout = spec.get('conditions', {}).get('timeout_seconds')
            try:
                receipt['exit_code'] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                receipt['error'] = 'Registered task timeout; child process terminated'
            receipt['state'] = 'succeeded' if receipt['exit_code'] == 0 else 'failed'
        for artifact in spec['artifacts']:
            source = (stage/artifact['path']).resolve()
            if not source.is_relative_to(stage.resolve()):
                raise ValueError('Artifact escaped execution directory')
            if source.is_file():
                saved = attempt/'artifacts'/artifact['path']
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, saved)
                receipt['files'].append({'name': artifact['name'], 'path': str(saved),
                                         'origin_path': str(source), 'sha256': digest(saved)})
    except Exception as exc:
        receipt['error'] = f'{type(exc).__name__}: {exc}'
    for name, path in [('stdout', stdout), ('stderr', stderr), ('launch', attempt/'launch.json'), ('process', attempt/'process.json')]:
        if path.is_file():
            receipt['files'].append({'name': name, 'path': str(path), 'origin_path': str(path), 'sha256': digest(path)})
    receipt['resources'] = {'wall_seconds': time.monotonic()-began,
                            'external_tokens': 'unknown', 'external_model_usage': 'unknown'}
    atomic_json(attempt/'receipt.json', {'receipt': receipt, 'signature': sign(receipt, key)})


if __name__ == '__main__':
    execute(sys.argv[1])
