from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import time

root = Path(__file__).resolve().parents[1]
checkout = root / 'work/published-9cdc234-replay'
helper = checkout / 'evaluation/replay_published_units.py'
expected = 'c95471c990d39554d0ad8427603d26865353085b'
revision = subprocess.run(['git', '-c', f'safe.directory={checkout.as_posix()}', 'rev-parse', 'HEAD'],
                          cwd=checkout, capture_output=True, check=True).stdout.decode().strip()
if revision != expected: raise ValueError('Fresh checkout commit differs')
if hashlib.sha256(helper.read_bytes()).hexdigest() != 'b9970cda47f3a3694e1cac9364c2d2206200d1c3fe5bfb0c82b8f8254ec24369':
    raise ValueError('Fresh published reader source differs')
out = root / 'evidence/fresh-published-reader-c95471c'
if out.exists(): raise FileExistsError('Preserve existing replay evidence')
out.mkdir()
spec = importlib.util.spec_from_file_location('fresh_published_reader', helper)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
original = Path.open
reads, blocked = [], []

def guarded_open(path, *args, **kwargs):
    actual = path.resolve()
    mode = args[0] if args else kwargs.get('mode', 'r')
    if not actual.is_relative_to(checkout.resolve()):
        blocked.append(str(actual)); raise AssertionError('Reader attempted to open outside fresh checkout')
    if actual.name == 'owner-request.json' or actual.name.endswith('-owner.json'):
        blocked.append(str(actual)); raise AssertionError('Reader attempted to open original owner data')
    if any(c in mode for c in 'wax+'):
        blocked.append(str(actual)); raise AssertionError('Reader attempted to mutate evidence')
    reads.append(actual.relative_to(checkout).as_posix())
    return original(path, *args, **kwargs)

Path.open = guarded_open
started = time.monotonic()
try:
    replay = reader.replay(checkout, str(root), 'runs/development/paired-pilot-v4',
                          ['linear-seed11', 'linear-seed19', 'quadratic-seed31', 'quadratic-seed43'])
finally:
    Path.open = original
elapsed = time.monotonic() - started
replay_path = out / 'scalar-replay.json'
replay_path.write_text(json.dumps(replay, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
report = {'valid': replay['valid'] and not blocked, 'commit': revision,
          'reader_path': str(helper), 'reader_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
          'scalar_replay_path': str(replay_path), 'scalar_replay_sha256': hashlib.sha256(replay_path.read_bytes()).hexdigest(),
          'seconds': elapsed, 'guarded_file_opens': len(reads), 'unique_read_paths': len(set(reads)),
          'outside_checkout_or_original_owner_attempts': blocked,
          'new_model_calls': 0, 'new_experiment_runner_executions': 0,
          'test_rows_written_or_printed': False, 'adopted': False, 'goal_complete': False,
          'scope': 'Newly published reader from exact fresh public commit on four approved development pairs; Python Path.open guard, not OS isolation or fresh semantic review.'}
(out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(out / 'reproduce.source.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps({k: report[k] for k in ('valid','commit','guarded_file_opens','outside_checkout_or_original_owner_attempts','new_model_calls','new_experiment_runner_executions')}))
