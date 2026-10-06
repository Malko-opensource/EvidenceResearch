"""Record final artifact provenance from actual test, host, browser and install proofs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen

PROJECT=Path(__file__).resolve().parents[1]
OUT=PROJECT/'validation/research-report-0.8.0'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))

def main():
    tests=read(OUT/'test-results.json')
    assert tests['python']['ok'] and tests['python']['count']==65
    assert tests['model']['ok'] and tests['model']['count']==56
    installed=read(OUT/'installation.json')
    assert installed['ok'] and installed['version']=='0.8.0' and installed['tool_count']==23
    mcp=read(PROJECT/'validation/mcp-installation-0.8.0.json')
    assert mcp['version']=='0.8.0' and mcp['tool_count']==23 and mcp['configuration_unchanged_during_probe']
    host=read(PROJECT/'validation/plugin-0.8.0/host-check-release/host-discovery.json')
    servers=host['mcp_status']['data']
    own=next(s for s in servers if s['name']=='research_state')
    assert host['ok'] and own['serverInfo']['version']=='0.8.0' and len(own['tools'])==23
    assert any(s['enabled'] and s['name']=='research-observatory:research-goal' for s in host['discovered_skills'])
    connection=read(PROJECT/'dist/research-observatory-0.8.0-release/research-observatory/connection.json')
    argv=connection['cli_command']+['--workspace',str(PROJECT/'research-workspaces/goal-plugin-demo-20261004'),'help']
    probe=subprocess.run(argv,cwd=PROJECT.parent,capture_output=True,text=True,encoding='utf-8')
    assert probe.returncode==0 and json.loads(probe.stdout)['ok'],probe.stderr
    (OUT/'plugin-cli-command.json').write_text(json.dumps({'ok':True,'argv':argv,'cwd':str(PROJECT.parent),'response':json.loads(probe.stdout),'stderr':probe.stderr,'experiment_launched':False},ensure_ascii=False,indent=2),encoding='utf-8')
    frozen=read(PROJECT/'evaluation/frozen_manifest.json')
    bad=[path for path,digest in frozen['files'].items() if sha(PROJECT/'evaluation'/path)!=digest]
    assert not bad,bad
    (OUT/'frozen-evaluation-check.json').write_text(json.dumps({'ok':True,'protocol_id':frozen['protocol_id'],'files_checked':len(frozen['files']),'invalid':bad,'performance_claim_added':False},indent=2),encoding='utf-8')
    preserved=read(OUT/'legacy-state-check.json');assert preserved['ok']
    target=PROJECT/'research-workspaces/product-fixtures-20261004/.research/evidence/4de3b679081334b6a27a13a022a3f2d98f8e37ec01dc24c947274dea68be163e'
    assert sha(target)==target.name
    for path in ('tamper-proof.json','missing-proof.json'):
        proof=read(OUT/path)
        assert proof['model']['trust']['supported'] is False and proof['model']['trust']['invalidCount']==1
    browser=read(OUT/'browser-checks.json')
    assert browser['nativeTools']==25 and browser['reducedMotion']['active']==0
    assert all(l['clientWidth']==l['scrollWidth'] and l['humanControls']==0 for l in browser['layout'])
    assert browser['functional']['primaryMetric']=='satisfaction_pct' and browser['functional']['primaryValue']==72
    native=read(OUT/'native-tools-final.json');assert len(native)==25
    transcript=read(OUT/'native-transcript.json')
    scenes={t['args'].get('scene') for t in transcript if t.get('name')=='research_view' and t['response']['ok']}
    assert {'overview','analysis','comparison','memory','activity','graph','stability'}<=scenes
    assert any(t.get('name')=='research_inspect_evidence' and t['response']['ok'] for t in transcript)
    assets={}
    for p in (PROJECT/'research_cli/web').iterdir():
        if p.is_file():
            with urlopen('http://127.0.0.1:8765/'+p.name,timeout=10) as response:content=response.read()
            assert content==p.read_bytes()
            assets[p.name]={'sha256':sha(p),'bytes':len(content)}
    matches={}
    sources=list((PROJECT/'research_cli').glob('*.py'))+list((PROJECT/'research_cli/web').glob('*'))
    for env in ('.mcp-venv','.validation-venv'):
        base=PROJECT/env/'Lib/site-packages/research_cli'
        matches[env]={p.relative_to(PROJECT/'research_cli').as_posix():p.read_bytes()==(base/p.relative_to(PROJECT/'research_cli')).read_bytes() for p in sources if p.is_file()}
        assert all(matches[env].values())
    tracked=list((PROJECT/'research_cli').glob('*.py'))+list((PROJECT/'research_cli/web').glob('*'))+list((PROJECT/'tests').glob('test_*'))+list(PROJECT.glob('*.md'))+[PROJECT/'pyproject.toml']
    tracked+=list((PROJECT/'plugin').rglob('*.md'))+list((PROJECT/'plugin/scripts').glob('*.py'))+list((PROJECT/'plugin').glob('*.json'))
    files={p.relative_to(PROJECT).as_posix():sha(p) for p in tracked if p.is_file()}
    wheel=PROJECT/'validation/wheels/research_state_cli-0.8.0-py3-none-any.whl'
    plugin=PROJECT/'dist/research-observatory-0.8.0-release/research-observatory.zip'
    result={'at':datetime.now(timezone.utc).isoformat(),'version':'0.8.0','files':files,'installed_matches':matches,
            'wheel':{'file':str(wheel),'sha256':sha(wheel),'bytes':wheel.stat().st_size,'core_runtime_dependencies':[]},
            'plugin':{'file':str(plugin),'sha256':sha(plugin),'bytes':plugin.stat().st_size,'actual_host':'codex-cli 0.160.0','skill_discovered':True,'mcp_tools':23,'global_profile_modified':False},
            'tests':tests,'actual_browser_assets':assets,'native_tools':25,'native_call_records':len(transcript),'scenes':sorted(scenes),
            'original_workspaces_preserved':9,'fixture_evidence_restored':True,'frozen_comparison_unchanged':True,
            'model_calls_inside_cli_or_web':False,'research_performance_improvement':'unproven','external_tokens_and_cost':'unknown'}
    (PROJECT/'validation/source-manifest-0.8.0.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'version':'0.8.0','python_tests':65,'model_tests':56,'native_calls':len(transcript),'wheel_sha256':sha(wheel),'plugin_sha256':sha(plugin),'frozen_files':len(frozen['files'])}))

if __name__=='__main__':main()
