"""Offline build/clean installation check and development-only launch timing."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
directory = Path(__file__).resolve().parent
environment = dict(os.environ)
environment.pop('PYTHONPATH', None)
environment['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
wheel_directory = directory/'wheels'


def invoke(command, cwd=root):
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    return result.stdout


build_log = invoke([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '--wheel-dir', str(wheel_directory), str(root)])
python = root/'.validation-venv'/'Scripts'/'python.exe' if os.name == 'nt' else root/'.validation-venv'/'bin'/'python'
if not python.exists():
    invoke([sys.executable, '-m', 'venv', str(root/'.validation-venv')])
install_log = invoke([str(python), '-m', 'pip', 'install', '--no-index', '--no-deps', '--force-reinstall', '--find-links', str(wheel_directory), 'research-state-cli'])
packages = json.loads(invoke([str(python), '-m', 'pip', 'list', '--format=json'], cwd=python.parent))
assert {p['name'].lower() for p in packages} <= {'pip', 'setuptools', 'research-state-cli'}
help_command = [str(python), '-m', 'research_cli', '--workspace', str(directory/'unused-timing-workspace'), 'help']
help_output = json.loads(invoke(help_command, cwd=python.parent))
assert help_output['ok']
times = []
for _ in range(20):
    start = time.perf_counter()
    invoke(help_command, cwd=python.parent)
    times.append(time.perf_counter()-start)
record = {'at': datetime.now(timezone.utc).isoformat(), 'installed_packages': packages, 'runtime_dependencies': [],
          'build_network_required': False, 'installation_network_required': False,
          'tested_outside_source_directory': True, 'model_credentials_required': False,
          'command_launch_timing': {'development_only': True, 'samples': 20, 'rationale': 'Measure short command startup variation; not research evaluation repeats',
                                    'median_seconds': statistics.median(times), 'min_seconds': min(times), 'max_seconds': max(times)},
          'language_decision': 'Python/SQLite currently avoids runtime dependencies. Timing describes this implementation; no unmeasured language speed comparison.'}
(directory/'installation.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
(directory/'build-install.log').write_text(build_log+install_log, encoding='utf-8')
print(json.dumps(record))
