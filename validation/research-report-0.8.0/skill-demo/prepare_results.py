import datetime
import hashlib
import json
from pathlib import Path

out = Path(__file__).resolve().parent
project = out.parents[2]
workspace = project/'research-workspaces'/'goal-plugin-demo-20261004'
calls = [json.loads(line) for line in (out/'cli-transcript.jsonl').read_text(encoding='utf-8').splitlines()]
parsed = []
for call in calls:
    try:
        response = json.loads(call['stdout'])
    except ValueError:
        continue
    parsed.append((call, response))
records = {}
decisions = {}
goal_data = None
revisions = []
for call, response in parsed:
    if not response.get('ok'):
        continue
    data = response['data']
    operation = call['argv'][5]
    if 'revision' in data:
        revisions.append({'operation':operation,'revision':data['revision'],'started_at':call['started_at']})
    if operation == 'goal_amend':
        goal_data = data['goal']
    if operation == 'goal_show':
        goal_data = data['goal']
    if operation in ('run','verify','show'):
        record = data.get('record',data)
        if 'registration' in record:
            records[record['registration']['id']] = record
    if operation == 'decide':
        decisions[data['decision']['registration_id']] = data['decision']
branches = []
for registration_id, record in records.items():
    registration = record['registration']
    summary_evidence = next(item for item in record['evidence'] if item['name']=='summary')
    blob = workspace/summary_evidence['path']
    summary = json.loads(blob.read_text(encoding='utf-8'))
    if hashlib.sha256(blob.read_bytes()).hexdigest() != summary_evidence['sha256']:
        raise ValueError('Summary blob hash mismatch')
    branches.append({'seed':registration['spec']['seed'],'registration_id':registration_id,'registration_goal_version':registration['goal_version'],'run_id':record['run']['id'],'run_state':record['run']['state'],'run_created':record['run']['created'],'run_finished':record['run']['finished'],'runner_wall_seconds':record['run']['resources']['wall_seconds'],'source_version':registration['spec']['source_version'],'conditions':registration['spec']['conditions'],'criteria':registration['spec']['criteria'],'summary':summary,'summary_evidence':summary_evidence,'verification':record['verification'],'decision':decisions.get(registration_id,record['decision']),'receipt':record['run']['receipt'],'evidence':record['evidence']})
branches.sort(key=lambda branch:branch['seed'])
manifest = {'schema_version':1,'demonstration_kind':'actual external-agent skill use against source CLI; public fixed synthetic fixture','root':str(project/'research-workspaces'),'workspace':'goal-plugin-demo-20261004','workspace_path':str(workspace),'goal_id':'goal_bed1555e80744acf9e85c437baf2ff3f','goal_version':goal_data['version'],'goal_state':goal_data['state'],'hypothesis_id':'hyp_60947ff54c8e423f9a66f13c1f5d8fa3','latest_observed_revision':revisions[-1]['revision'],'revision_trace':revisions,'prompt_path':str(out/'long-term-goal-prompt.v1.ko.md'),'brief_v1_path':str(out/'goal-brief.v1.json'),'brief_v2_path':str(out/'goal-brief.v2-plan.json'),'skill_decision_record':str(out/'skill-use-decision-record.json'),'transcript_jsonl':str(out/'cli-transcript.jsonl'),'transcript_text':str(out/'cli-transcript.txt'),'validator':'csv-owner-fixed-v1','validator_sha256':branches[0]['verification']['details']['validator_sha256'],'branches':branches,'population_inference':False,'performance_improvement_claim':False,'external_agent_tokens':'unknown','external_agent_cost':'unknown','web_url':'unknown; root browser coordinator will supply actual URL','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(out/'demonstration-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
telemetry = {'source':'actual external-agent session and CLI execution receipts','source_ref':str(out/'resource-telemetry-evidence.json'),'inspected_evidence':[{'run_id':branch['run_id'],'runner_resources':{'wall_seconds':branch['runner_wall_seconds'],'external_model_usage':branch['receipt']['resources']['external_model_usage'],'external_tokens':branch['receipt']['resources']['external_tokens']}} for branch in branches],'per_demo_external_agent_token_receipt':'not exposed to this agent session','per_demo_external_agent_cost_receipt':'not exposed to this agent session','scope':'availability observation only; no cost amount or token count inferred','actual_cli_model_call':'none requested; runs execute pinned local task.py'}
(out/'resource-telemetry-evidence.json').write_text(json.dumps(telemetry,indent=2)+'\n',encoding='utf-8')
observation = {'source':telemetry['source'],'source_ref':telemetry['source_ref'],'cost':{'status':'unknown','amount':None,'currency':None},'tokens':{'status':'unknown','value':None},'period_start':branches[0]['run_created'],'period_end':max(branch['run_finished'] for branch in branches),'note':'Actual pinned local runner receipts report external_model_usage and external_tokens unknown. No per-demo external agent billing/token receipt is exposed. Source file records actual availability evidence; this is not a fabricated invoice or zero cost.'}
(out/'resource-observation.json').write_text(json.dumps(observation,indent=2)+'\n',encoding='utf-8')
closure = {'results':['합의된 누락 제외 기술통계: 전체 유효5/누락1, 만족도72%; A 평균4.0/만족도80%/유효2/누락1, B 평균3.3333333333333335/만족도66.66666666666667%/유효3/누락0.','세 실제 기능 반복 seed0,1,2의 동일 입력·소스 해시가 유지되며 모두 실행 succeeded, 독립 calculation_matches=1.0; 사전등록 satisfaction_pct>=80은72.0으로 실패.','80% 가설은 각 등록 rejected. 사업 기준 미달이 확인되어 기술통계 연구 질문에 근거 있는 부정적 답을 얻었다.','장기 목표 프롬프트, brief v1/v2, 계획 변경 사유, 실제 CLI 호출·출력, 원본 증거와 재개 연결을 보존했다.'],'incomplete':['외부 에이전트 실제 토큰·비용 영수증이 이 세션에 제공되지 않아 unknown이다.','다른 고객 집단 일반화, 누락 원인 및 인과·성능 개선은 이 승인된 고정 fixture 범위 밖이며 입증하지 않았다.','WebMCP 실제 장면 조작은 같은 목표/등록/실행 ID로 루트 에이전트가 이어서 검증한다; 새 연구 실행은 필요하지 않다.']}
(out/'goal-close-input.json').write_text(json.dumps(closure,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'manifest':str(out/'demonstration-manifest.json'),'revision':manifest['latest_observed_revision'],'goal':manifest['goal_id'],'branches':[{'seed':b['seed'],'registration':b['registration_id'],'run':b['run_id'],'metrics':b['verification']['metrics'],'verification':b['verification']['state']} for b in branches]},ensure_ascii=False))
