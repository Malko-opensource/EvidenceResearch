"""Public invocation wrapper for the fixed checker. Do not inspect hidden cases."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    bundle = {'registration': {'spec': {'task_id': args.task}}, 'artifacts': {
        name: str(root/name) for name in ('solution.py', 'input.csv', 'result.json', 'invocations.jsonl')}}
    bundle_path = output.with_suffix('.bundle.json')
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(json.dumps(bundle), encoding='utf-8')
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('fixed_validator.py')), str(bundle_path)],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        record = {'ok': False, 'error': result.stderr, 'metrics': {}, 'status': 'inconclusive'}
    else:
        record = json.loads(result.stdout)
    if output.exists():
        raise SystemExit('Keep previous checks; select a new output file')
    output.write_text(json.dumps(record, ensure_ascii=False, sort_keys=True), encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
