"""Record source CLI calls and unaltered stdout/stderr for the external-agent demo."""
import datetime
import base64
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

project = Path(__file__).resolve().parents[3]
out = Path(__file__).resolve().parent
workspace = project / 'research-workspaces' / 'goal-plugin-demo-20261004'
command = [str(project / '.mcp-venv' / 'Scripts' / 'python.exe'), '-m', 'research_cli', '--workspace', str(workspace), *sys.argv[1:]]
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
result = subprocess.run(command, cwd=project, capture_output=True)
stdout = result.stdout.decode('utf-8')
stderr = result.stderr.decode('utf-8')
record = {'started_at': started, 'finished_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'cwd': str(project), 'argv': command, 'returncode': result.returncode, 'stdout': stdout, 'stderr': stderr, 'stdout_base64': base64.b64encode(result.stdout).decode('ascii'), 'stderr_base64': base64.b64encode(result.stderr).decode('ascii')}
with (out / 'cli-transcript.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write(json.dumps(record, ensure_ascii=False) + '\n')
with (out / 'cli-transcript.txt').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\nCALL ' + json.dumps(command, ensure_ascii=False) + '\nCWD ' + str(project) + '\nSTART ' + started + '\nRETURN ' + str(result.returncode) + '\nSTDOUT\n' + stdout + '\nSTDERR\n' + stderr + '\n')
sys.stdout.write(stdout)
sys.stderr.write(stderr)
raise SystemExit(result.returncode)
