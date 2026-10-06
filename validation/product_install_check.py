"""Check the installed SDK-free web package from an external cwd, without research writes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile


# One isolated interpreter owns the HTTP server, its thread and all cleanup.
# Avoid terminating the Windows venv launcher while its Python child still runs.
PROBE = r"""
import hashlib, importlib.metadata as metadata, importlib.util, json, os, sys, threading
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
project, workspace_name = Path(sys.argv[1]).resolve(), sys.argv[2]
root = project / 'research-workspaces'
report = {'ok': False, 'temporary_server_started': False, 'temporary_server_stopped': True}
server = thread = None
try:
    import research_cli
    from research_cli.web_server import create_server
    workspace = (root / workspace_name).resolve()
    assert workspace.is_relative_to(root.resolve()), 'Workspace leaves the dedicated root'
    assert (workspace / '.research/state.sqlite3').is_file(), 'Use an existing workspace; no initialization'
    assert metadata.version('research-state-cli') == '0.7.0', 'Install 0.7.0 before running this check'
    assert importlib.util.find_spec('mcp') is None, 'Validation environment contains the MCP SDK'
    module = Path(research_cli.__file__).resolve()
    assert module.is_relative_to((project / '.validation-venv/Lib/site-packages').resolve())
    requirements = [r for r in metadata.requires('research-state-cli') or [] if 'extra ==' not in r]
    assert not requirements, 'Core runtime dependencies must remain empty'
    digest = lambda content: hashlib.sha256(content).hexdigest()
    matches = {p.name: digest(p.read_bytes()) == digest((module.parent / p.name).read_bytes())
               for p in (project / 'research_cli').glob('*.py')}
    assert all(matches.values()), 'Installed modules differ from current source'
    report.update({'installed_module': str(module), 'mcp_sdk_available': False,
                   'core_runtime_dependencies': requirements, 'module_matches': matches})
    server = create_server(root, port=0)
    assert server.server_address[0] == '127.0.0.1' and server.bridge.root == root.resolve()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report.update({'temporary_server_started': True, 'temporary_server_stopped': False,
                   'temporary_server_pid': os.getpid()})
    base = 'http://%s:%s/' % server.server_address
    def read(path):
        with urlopen(base + path, timeout=10) as response:
            return response.read()
    bootstrap = json.loads(read('api/bootstrap'))
    assert bootstrap['ok'] and bootstrap['data']['version'] == '0.7.0'
    tools = bootstrap['data']['tools']
    assert len(tools) == 17
    snapshot_path = 'api/snapshot?' + urlencode({'workspace': workspace_name, 'limit': 20, 'offset': 0})
    before = json.loads(read(snapshot_path))
    assert before['ok'], 'Existing workspace snapshot could not be read'
    assets = {}
    for name in ('index.html', 'styles.css', 'app.js', 'view_model.js'):
        received = read(name)
        assert received == (project / 'research_cli/web' / name).read_bytes(), 'Static asset differs: ' + name
        assets[name] = {'sha256': digest(received), 'bytes': len(received), 'source_matches': True}
    after = json.loads(read(snapshot_path))
    assert after['ok'] and before['data'] == after['data'], 'Status changed during read-only check'
    report.update({'ok': True, 'tool_count': len(tools), 'tools': sorted(t['name'] for t in tools),
                   'assets': assets, 'workspace': workspace_name, 'read_only_snapshot_unchanged': True,
                   'revision': after['data']['status']['revision']})
except Exception as error:
    report.update({'ok': False, 'error': type(error).__name__ + ': ' + str(error)})
finally:
    try:
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
            if thread is not None:
                thread.join(timeout=10)
            report['temporary_server_stopped'] = thread is None or not thread.is_alive()
            report['temporary_server_socket_closed'] = server.socket.fileno() == -1
            assert report['temporary_server_stopped'] and report['temporary_server_socket_closed'], 'Server cleanup incomplete'
    except Exception as error:
        report.update({'ok': False, 'cleanup_error': type(error).__name__ + ': ' + str(error)})
print(json.dumps(report, ensure_ascii=False))
raise SystemExit(0 if report['ok'] else 1)
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workspace', default='agent-observatory-20261004')
    args = parser.parse_args()
    project = args.project.resolve()
    python = project / '.validation-venv/Scripts/python.exe'
    output = project / 'validation/product-web-0.7.0/installation.json'
    report = {'at': datetime.now(timezone.utc).isoformat(), 'version': '0.7.0', 'ok': False,
              'isolated_python': str(python), 'model_calls': False, 'experiment_launched': False,
              'workspace_created': False, 'tested_outside_source_directory': False}
    try:
        with tempfile.TemporaryDirectory(prefix='research-installed-web-') as cwd:
            assert not Path(cwd).resolve().is_relative_to(project), 'Expected an external cwd'
            report['tested_outside_source_directory'] = True
            completed = subprocess.run([str(python), '-I', '-c', PROBE, str(project), args.workspace],
                                       cwd=cwd, capture_output=True, text=True, encoding='utf-8',
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            report.update(json.loads(completed.stdout))
            assert completed.returncode == 0 and report['ok'], report.get('error', report.get('cleanup_error', 'Installed probe failed'))
    except Exception as error:
        report.update({'ok': False, 'error': type(error).__name__ + ': ' + str(error)})
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report.get(k) for k in ('ok', 'version', 'tool_count', 'mcp_sdk_available', 'temporary_server_stopped')}))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
