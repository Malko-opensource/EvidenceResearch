"""Installed read-only cross-channel proof and an isolated unexecuted selection fixture."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from mcp import Client, StdioServerParameters
from research_cli.core import Store

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT/'validation/research-report-0.8.0'
ROOT = PROJECT/'research-workspaces'
WORKSPACE = 'goal-plugin-demo-20261004'
GOAL = 'goal_bed1555e80744acf9e85c437baf2ff3f'

async def main():
    argv=[str(PROJECT/'.mcp-venv/Scripts/python.exe'),'-I','-m','research_cli',
          '--workspace',str(ROOT/WORKSPACE),'goal_show','--goal',GOAL]
    completed=subprocess.run(argv,cwd=PROJECT.parent,capture_output=True,text=True,encoding='utf-8')
    assert completed.returncode==0,completed.stderr
    cli=json.loads(completed.stdout)
    params=StdioServerParameters(command=argv[0],args=['-I','-m','research_cli.mcp_server','--root',str(ROOT)],cwd=PROJECT.parent)
    async with Client(params,read_timeout_seconds=30) as client:
        result=await client.call_tool('research_goal_show',{'workspace':WORKSPACE,'goal':GOAL})
        stdio=result.structured_content
    assert cli==stdio and cli['data']['revision']==21
    proof={'ok':True,'cli':{'argv':argv,'cwd':str(PROJECT.parent),'response':cli},'stdio':stdio,
           'same_goal':GOAL,'same_version':2,'revision':21,'experiment_launched':False}
    (OUT/'channel-consistency.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    fixture=ROOT/'report-channel-fixture-20261004'
    initialized=Store.init(fixture);store=Store(fixture)
    brief={'original_request':'채널 초점·중단 보고 검증 전용; 연구 성능 평가 제외','resource_constraints':{'time':'not set','cost':'no spending'}}
    a=store.goal_create('선택 검사용 목표 A',brief=brief,request_key='channel-goal-A')
    b=store.goal_create('선택 검사용 목표 B',brief=brief,request_key='channel-goal-B')
    with store._connect() as con:
        existing=con.execute('SELECT id FROM hypotheses WHERE goal_id=?',(b['id'],)).fetchall()
    assert len(existing)<=1,'Unexpected fixture hypotheses; preserve without replacement'
    h={'id':existing[0]['id']} if existing else store.hypothesis_create(b['id'],'미실행 제안: 고정 로컬 결과가 1이다')
    validator=fixture/'fixed_validator.py';validator.write_text("import json\nprint(json.dumps({'metrics':{'value':1},'details':{'fixture':'unexecuted_selection_only'}}))\n",encoding='utf-8')
    registered=store.validator_register('selection-fixed',[initialized['runner_interpreter'],str(validator),'{bundle}'],(fixture/'.research/owner.key').read_text(encoding='utf-8').strip())
    job=fixture/'job';job.mkdir(exist_ok=True);script=job/'task.py';script.write_text("from pathlib import Path\nPath('result.json').write_text('{\"value\":1}',encoding='utf-8')\n",encoding='utf-8')
    spec={'hypothesis_id':h['id'],'change':'실행하지 않는 초점 선택 검사','comparison':'fixed one','data_split':'development only','seed':0,
          'source_version':{'label':'selection-fixture','files':{'task.py':hashlib.sha256(script.read_bytes()).hexdigest()}},
          'metrics':['value'],'metric_units':{'value':'무차원'},'criteria':[{'metric':'value','op':'==','threshold':1}],
          'conditions':{'scope':'UI selection only; no run'},'command':[initialized['runner_interpreter'],'task.py'],'cwd':str(job),
          'artifacts':[{'name':'result','path':'result.json'}],'validator':'selection-fixed'}
    reg=store.register(b['id'],spec,request_key='channel-register-B')
    data={'workspace':fixture.name,'goalA':a,'goalB':b,'brief':brief,'registrationB':reg,'owner_validator':registered,
          'actual_runs':0,'revision':store.status()['revision'],'development_only':True}
    (OUT/'selection-fixture.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'same_goal_version':2,'same_revision':21,'fixture':fixture.name,'actual_runs':0}))

if __name__=='__main__':asyncio.run(main())
