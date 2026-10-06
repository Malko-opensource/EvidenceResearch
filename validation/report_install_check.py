"""Probe an installed SDK-free reporting web service without creating research records."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

PROJECT=Path(__file__).resolve().parents[1]
PROBE=r'''
import hashlib,importlib.metadata as m,importlib.util,json,threading
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import research_cli
from research_cli.web_server import create_server
from research_cli.web_tools import tool_descriptions
project=Path(__import__('sys').argv[1]);module=Path(research_cli.__file__).resolve()
assert m.version('research-state-cli')=='0.8.0'
assert importlib.util.find_spec('mcp') is None
assert not [r for r in m.requires('research-state-cli') or [] if 'extra ==' not in r]
assert module.is_relative_to((project/'.validation-venv/Lib/site-packages').resolve())
matches={p.name:p.read_bytes()==(module.parent/p.name).read_bytes() for p in (project/'research_cli').glob('*.py')}
assert all(matches.values())
server=create_server(project/'research-workspaces',port=0)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    base='http://%s:%s/'%server.server_address
    def read(path):
        with urlopen(base+path,timeout=10) as response:return response.read()
    bootstrap=json.loads(read('api/bootstrap'))['data'];assert bootstrap['version']=='0.8.0'
    assert {x['name'] for x in bootstrap['tools']}=={x['name'] for x in tool_descriptions()}
    assets={}
    for p in (project/'research_cli/web').iterdir():
        if not p.is_file():continue
        content=read(p.name);assert content==p.read_bytes()
        assets[p.name]={'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content)}
    path='api/snapshot?'+urlencode({'workspace':'agent-observatory-20261004','limit':2})
    first=json.loads(read(path))['data'];second=json.loads(read(path))['data']
    assert first['status']==second['status'] and first['events']==second['events']
    assert first['report']['totals']==second['report']['totals']
    assert second['report']['consistent']
    report={'ok':True,'version':m.version('research-state-cli'),'installed_module':str(module),
            'module_matches':matches,'assets':assets,'tool_count':len(bootstrap['tools']),
            'tools':[t['name'] for t in bootstrap['tools']], 'mcp_sdk_available':False,'core_runtime_dependencies':[],
            'outside_source_cwd':True,'isolated_import':True,'revision':second['status']['revision'],
            'research_state_unchanged':True,'model_calls':False,'experiment_launched':False}
finally:
    server.shutdown();server.server_close();thread.join(timeout=10)
assert not thread.is_alive() and server.socket.fileno()==-1
report['temporary_server_stopped']=True
print(json.dumps(report,ensure_ascii=False))
'''

def main():
    output=PROJECT/'validation/research-report-0.8.0/installation.json'
    with tempfile.TemporaryDirectory(prefix='research-report-installed-') as cwd:
        result=subprocess.run([str(PROJECT/'.validation-venv/Scripts/python.exe'),'-I','-c',PROBE,str(PROJECT)],cwd=cwd,
                              capture_output=True,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    report=json.loads(result.stdout) if result.returncode==0 else {'ok':False,'returncode':result.returncode,'stderr':result.stderr}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('ok','version','tool_count','mcp_sdk_available','temporary_server_stopped')}))
    return int(not report['ok'])
if __name__=='__main__':raise SystemExit(main())
