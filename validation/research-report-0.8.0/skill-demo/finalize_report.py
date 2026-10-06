import datetime
import hashlib
import json
from pathlib import Path

out = Path(__file__).resolve().parent
project = out.parents[2]
workspace = project/'research-workspaces'/'goal-plugin-demo-20261004'
manifest_path = out/'demonstration-manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
calls = [json.loads(line) for line in (out/'cli-transcript.jsonl').read_text(encoding='utf-8').splitlines()]
responses = []
for call in calls:
    try:
        response = json.loads(call['stdout'])
    except ValueError:
        continue
    responses.append((call,response))
goal_show = [response['data'] for call,response in responses if call['argv'][5]=='goal_show' and response.get('ok')][-1]
status = [response['data'] for call,response in responses if call['argv'][5]=='status' and response.get('ok')][-1]
resources = [response['data'] for call,response in responses if call['argv'][5]=='resource_show' and response.get('ok')][-1]
memory = [response['data'] for call,response in responses if call['argv'][5]=='memory' and response.get('ok')][-1]
goal = goal_show['goal']
before = json.loads((out/'workers-before-replay.json').read_text(encoding='utf-8'))
after = json.loads((out/'workers-after-current-replay.json').read_text(encoding='utf-8'))
assert before['runs']==after['runs'] and before['run_directory_count']==after['run_directory_count']==3
source = json.loads((out/'source-manifest.json').read_text(encoding='utf-8'))
integrity = {'original_csv_unchanged':hashlib.sha256((workspace/'data.csv').read_bytes()).hexdigest()==source['original_csv_sha256'],'original_validator_unchanged':hashlib.sha256((workspace/'fixed_validator.py').read_bytes()).hexdigest()==source['validator_original_sha256'],'frozen_validator_registered_hash':manifest['validator_sha256'],'copied_data_matches_original':source['files']['data.csv']==source['original_csv_sha256'],'all_three_source_labels_and_hashes_equal':all(branch['source_version']==manifest['branches'][0]['source_version'] for branch in manifest['branches']),'all_three_conditions_equal':all(branch['conditions']==manifest['branches'][0]['conditions'] for branch in manifest['branches'])}
assert all(value for name,value in integrity.items() if isinstance(value,bool))
goal_replays = [response['data'] for call,response in responses if call['argv'][5]=='goal' and response.get('ok') and response['data'].get('reused')]
run_replays = [response['data'] for call,response in responses if call['argv'][5]=='run' and response.get('ok') and response['data'].get('started') is False]
replay = {'goal':{key:goal_replays[-1][key] for key in ('id','version','state','reused','applied_revision','revision','result_is_historical')},'current_goal_after_historical_replay':{'id':goal['id'],'version':goal['version'],'state':goal['state'],'revision':status['revision']},'run_stale_expect_error':[response['error'] for call,response in responses if call['argv'][5]=='run' and not response.get('ok')],'run_same_key_latest_expect':{'started':run_replays[-1]['started'],'run_id':run_replays[-1]['record']['run']['id'],'revision':run_replays[-1]['record']['revision']},'worker_count_before':before['run_directory_count'],'worker_count_after':after['run_directory_count'],'launch_process_receipt_hashes_unchanged':before['runs']==after['runs'],'new_workers_observed':0,'scope':'actual local worker directories and preserved launch/process/receipt evidence; no external exactly-once guarantee'}
elapsed_goal = goal['lifecycle']['created']-goal['created']
elapsed_transcript = datetime.datetime.fromisoformat([call['finished_at'] for call,response in responses if call['argv'][5]=='goal_close' and response.get('ok') and not response['data'].get('reused')][0])-datetime.datetime.fromisoformat(calls[0]['started_at'])
wall_sum = sum(branch['runner_wall_seconds'] for branch in manifest['branches'])
manifest.update({'goal_state':goal['state'],'goal_version':goal['version'],'latest_observed_revision':status['revision'],'goal_lifecycle':goal['lifecycle'],'goal_version_history':goal_show.get('versions',[]),'goal_lifecycle_history':goal_show.get('lifecycle',[]),'resource_observations':resources,'integrity_checks':integrity,'replay':replay,'memory_failure_search':memory,'elapsed':{'goal_created_to_close_seconds':elapsed_goal,'first_recorded_cli_status_to_close_seconds':elapsed_transcript.total_seconds(),'runner_execution_wall_seconds_sum':wall_sum,'scope':'recorded timestamps and worker wall only; excludes unobservable external-model timing'},'artifacts':{'korean_report':str(out/'research-report.ko.md'),'resume_handoff':str(out/'resume-handoff.ko.md'),'resource_telemetry_evidence':str(out/'resource-telemetry-evidence.json')},'transcript_capture':{'mutation_and_run_calls':'unmodified UTF-8 stdout/stderr plus exact byte base64; argv array and cwd recorded','initial_read_only_discovery_calls':'text capture before recorder switched to byte preservation; CRLF normalized by subprocess text mode','recorder_issue':'First goal succeeded and raw output was recorded; its display failed on cp949. UTF-8 display fix and same goal key confirmed reuse without duplicate.'}})
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
record_path = out/'skill-use-decision-record.json'
record = json.loads(record_path.read_text(encoding='utf-8'))
record['observed_interface_recovery']=[{'operation':'goal initial response display','issue':'Recorder cp949 display failed after actual CLI goal success','recovery':'UTF-8 display; same key returned reused=true, same goal ID'},{'operation':'completed run replay','issue':'original stale expect7 returned REVISION_CONFLICT expected7 actual21','recovery':'read current status; same request key with expect21 returned started=false and original run; no worker evidence changed'},{'operation':'memory failure lookup','issue':'--outcome rejected was INVALID_INPUT; actual source accepts success/failure/inconclusive','recovery':'--outcome failure --verification failed returned actual three rejected registrations'}]
record['final_outcome']={'goal_completed':True,'performance_improvement_demonstrated':False,'population_generalization_supported':False,'business_threshold_met':False,'correct_calculation_independently_matched':True,'new_workers_after_completed_replay':0,'external_tokens':'unknown','external_cost':'unknown'}
record_path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
rows='\n'.join(f"| {branch['seed']} | succeeded | 1.0 | 72% | failed (80% 미달) | rejected |" for branch in manifest['branches'])
report=f'''# 스킬 실제 사용 및 고정 CSV 연구 보고

연구 질문에 대한 답을 확보해 목표 v2를 completed로 종료했다(revision {status['revision']}). 전체 만족도는 72%로 80% 기준보다 8 percentage points 낮다. 고정 독립 검증의 계산 일치는 세 실행 모두 1.0이며 전체 사전등록 판정은 사업 기준 미달 때문에 failed다. 근거 있는 부정적 답이 완료 기준을 충족한다. 총비용·실제 외부 에이전트 토큰은 unknown이다. 목표 생성부터 종료까지 관측 시간은 {elapsed_goal:.3f}초, 최초 기록 CLI 상태 조회부터 종료까지 {elapsed_transcript.total_seconds():.3f}초, 세 worker 실행 wall time 합은 {wall_sum:.3f}초다. 이 시간들은 서로 다른 집계 범위다.

원래 의뢰는 “누락값이 섞인 고객 응답 CSV로 팀별 만족도를 믿고 보고할 수 있는지 연구해 줘.”였다. 이미 제공된 적용 범위·데이터·누락 규칙·산출물·승인·80% 기준으로 구체화했으므로 사용자에게 같은 답이나 전문 통계 설계를 다시 요구하지 않았다. 외부 Codex 에이전트가 실제 research-goal 스킬과 두 참조를 읽고 장기 목표 프롬프트·구조화 brief·가설·코드·사전등록·해석을 작성했다. CLI 안에서 모델을 호출하지 않았다. 실제 이 외부 에이전트의 토큰·비용 영수증은 세션에 노출되지 않아 수치를 추정하지 않았다.

| 범위 | 전체 행 | 유효 평점 | 누락 | 유효 평점 평균 | 만족도 |
|---|---:|---:|---:|---:|---:|
| 전체 | 6 | 5 | 1 | 3.6 | 72% |
| A | 3 | 2 | 1 | 4.0 | 80% |
| B | 3 | 3 | 0 | 3.3333333333333335 | 66.66666666666667% |

값은 원본 평점의 평균/5×100으로 계산했다. 빈 평점은 누락으로 집계하고 평균에서 제외했다. 이 CSV의 관측된 응답 기술통계는 정확하게 재현할 수 있다. A는 3행 중 1행이 누락이고 유효 응답은 2개이므로 이 평균을 응답하지 않은 사람이나 다른 고객 집단의 만족도로 확대할 근거는 없다. 누락이 무작위라는 가정을 두지 않았다. 누락 원인은 이 fixture에 제공되지 않았다. 전체 80% 가설은 이 고정 입력에 대해 반대 증거로 기각했다. 팀별 기술통계 자체를 계산 오류로 판정한 것은 아니다.

| seed | 실행 | 독립 계산 일치 | 전체 만족도 | 전체 사전등록 검증 | 결정 |
|---:|---|---:|---:|---|---|
{rows}

세 등록은 동일 소스 라벨 skill-demo-descriptive-csv-v1, 동일 task.py·data.csv 해시, 동일 conditions를 사용하고 seed만 0,1,2로 구분했다. repeat_design은 three_fixed_input_replications이다. 계산에는 무작위 요소가 없다. 분포 [72,72,72]는 고정 입력 기능 반복의 실제 분포이며 독립 고객 표본·모집단 신뢰구간·검정력·성능 개선의 근거가 아니다.

소유자가 사전에 고정한 csv-owner-fixed-v1 검증기는 실제 summary 산출물을 읽고 고정 원본 CSV를 별도 코드로 재계산했다. 원본 해시 일치와 독립 calculation_matches==1은 확인됐고 satisfaction_pct>=80은 실패했다. validator와 원본 CSV는 수정하지 않았다. 두 사전등록 기준은 결과 이후에도 유지했다. 실행 succeeded, 검증 failed, 결정 rejected, 연구 목표 completed는 각각 다른 사실이다.

상태→기억→목표 및 동일 key 재사용→가설→코드·해시 고정·seed별 사전등록→plan-only 목표 변경→실행→고정 독립 검증→결정→자원 관측→종료→완료 요청 replay를 실제 소스 CLI로 수행했다. 계획 변경은 세 검증을 모은 뒤 공동 보고를 작성한다는 순서를 명확히 했고 의미·범위·등록 기준은 바꾸지 않았다. 현재 목표는 v2, 각 등록이 고정한 목표는 v1이다. 파일 작성과 DB 갱신의 원자성은 주장하지 않는다.

완료된 goal 원 요청의 stale expect 재전송은 reused=true, applied_revision=2, 현재 revision=21, result_is_historical=true를 반환했다. 이후 goal_show/status에서 현재 v2/completed를 확인해 과거 응답으로 상태를 되돌리지 않았다. 완료 run의 원 expect7은 REVISION_CONFLICT를 반환했고, 최신 상태 조회 후 같은 run key와 expect21로 재전송하면 started=false 및 원 run ID를 반환했다. 전후 run directory는 모두 3개이고 launch/process/receipt 해시는 동일했다. close 재전송도 reused=true였다. 새 worker가 관측되지 않았으며 외부 부작용의 exactly-once 보장은 주장하지 않는다.

비용 관측은 원 runner receipt의 external_model_usage/external_tokens=unknown과 실제 세션의 영수증 부재에 연결된 관측 1건이다. resource_show는 관측 비용 소계 없음, 토큰 observed_subtotal=null, 총비용 상태 unknown, 집계 범위 recorded_external_observations_only를 반환한다. 비용 0으로 해석하지 않는다. 이 관측은 외부 에이전트 보고이며 독립 비용 감사가 아니다.

미완료·미입증 범위는 실제 외부 에이전트 토큰·비용, 누락 원인, 다른 모집단에 대한 일반화 및 인과·성능 개선이다. WebMCP의 같은 상태 읽기와 장면 검사는 루트 에이전트가 이 manifest의 원 ID로 이어간다. 이 보고는 스킬을 이용한 실제 연구 도구 사용의 기능 실연이며 연구 성능 향상의 검증 결과로 바꾸지 않는다.

재개 시 demonstration-manifest.json의 절대 root/상대 workspace, 목표 ID·v2·현재 상태와 revision을 읽고 goal_show/status/memory를 조회한다. 원 실행이 unknown이면 show/recover로 원 run을 수집하며 대체 실행을 자동 시작하지 않는다. 현재 세 원 실행은 모두 terminal이고 질문은 답했으므로 추가 worker는 필요하지 않다. 새 자료나 범위를 연구하려면 그 변경과 승인된 범위를 명시한다.

원본 연결은 long-term-goal-prompt.v1.ko.md, goal-brief.v1.json, goal-brief.v2-plan.json, skill-use-decision-record.json, preregistration.seed0/1/2.json, cli-transcript.jsonl/txt, source-manifest.json, resource-telemetry-evidence.json, workers-before-replay.json, workers-after-current-replay.json 및 demonstration-manifest.json이다. manifest에는 원 등록·run·evidence 경로·해시·검증 상세가 있다. substantive CLI 호출의 argv와 stdout/stderr는 raw-byte base64도 보존했다. 초기 read-only 도움말 발견 기록은 text mode였으므로 Windows 줄바꿈만 정규화됐다. 도움말 topic 두 추측과 memory outcome 추측의 INVALID_INPUT, recorder의 표시 오류, stale revision 충돌을 숨기지 않고 보존했다.
'''
(out/'research-report.ko.md').write_text(report,encoding='utf-8')
handoff=f'''# 같은 연구 재개 연결

- 절대 root: {manifest['root']}
- 상대 workspace: {manifest['workspace']}
- 목표: {goal['id']}, 현재 버전 {goal['version']}, 상태 {goal['state']}, 마지막 확인 revision {status['revision']}
- 확인 시각: {datetime.datetime.now(datetime.timezone.utc).isoformat()}
- 가설: {manifest['hypothesis_id']}
- 원 등록·실행: demonstration-manifest.json의 branches 참조
- 완료 답: 전체 72%, 계산 일치 1.0, 전체 사업 기준 80% 미달; 팀 A80%, B66.67%; 관측된 고정 입력 기술통계만
- 미확인: 외부 에이전트 실제 토큰·비용 영수증, 누락 원인; 모집단·효과·성능 개선은 미입증 및 범위 밖
- 다음 허용 작업: 같은 goal_show/status/memory 및 원 show/evidence 조회, 같은 상태 WebMCP 표시 검사. 새로운 연구 worker는 현재 질문의 답에 필요하지 않음.
- unknown 실행을 발견하면 원 run을 show/recover로 확인하고 같은 request key 유지; 원본을 숨기는 새 key/대체 실행 금지
- 완료 이후 승인된 새 연구가 남을 때만 goal_resume하고 범위·의미 변경은 명시적 goal_amend 및 새 preregistration. 기존 criteria/validator/source 변경 금지.
- 파일 prompt v1과 DB goal v2는 별도 버전이며 prompt hash는 brief.handoff와 source artifacts에 유지됨.
- 웹 URL: 실제 브라우저 coordinator가 연결 확인 후 기록하며 이 파일은 미관측 URL을 만들지 않음.
'''
(out/'resume-handoff.ko.md').write_text(handoff,encoding='utf-8')
(out/'final-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(out/'final-goal-show.json').write_text(json.dumps(goal_show,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'goal_state':goal['state'],'version':goal['version'],'revision':status['revision'],'elapsed_goal_seconds':elapsed_goal,'runner_wall_seconds':wall_sum,'replay_no_extra_worker':replay['new_workers_observed'],'integrity':integrity,'report':str(out/'research-report.ko.md')}))
