"""Finalize existing independent evidence; no candidate imports/tests/fit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'c8'
EXPECTED = '8d4bb2c1d1ee42fea312c78ca7bedb1896127def0df4bef7d5322e9f19ca3995'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def create(path, value):
    with path.open('x',encoding='utf-8',newline='\n') as f: f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def link(path): return {'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)}

def main():
    assert sha(HERE/'attempt-0002-result.json') == EXPECTED
    final=read(HERE/'attempt-0002-result.json'); first=read(HERE/'attempt-0001-result.json')
    snapshot=read(HERE/'snapshot-manifest.json')
    stable=True
    for row in snapshot['candidate_source_rows']:
        path=SOURCE/row['relative']
        if sha(path)!=row['sha256'] or path.stat().st_size!=row['bytes']: stable=False
    snapshot_stable=all(sha(HERE/'source-snapshot'/r['relative'])==r['sha256'] for r in snapshot['selected_files'])
    assert stable and snapshot_stable and final['status']=='pass'
    assert all(v['status']=='pass' for v in final['registered_family_verdicts'])
    assert len(final['registered_family_verdicts'])==10
    assert all(not any(attempt['guard']['counts'].values()) for attempt in (first,final))
    assert all(final['native_callback_qualification'][arm]['eligible'] is False
               and final['native_callback_qualification'][arm]['fixture_only'] is True
               and final['native_callback_qualification'][arm]['adoption_eligible'] is False for arm in ('B','C'))
    final.update(candidate_source_stable=stable,snapshot_source_stable=snapshot_stable,
        candidate_source_files=110,snapshot_source_files=58,
        attempt_result_source=link(HERE/'attempt-0002-result.json'),
        preserved_first_failure=link(HERE/'attempt-0001-result.json'),
        preserved_first_helper=link(HERE/'independent-fixture-attempt-0001.py'),
        successful_native_precapture_cases_rerun=False,
        synthetic_provider_calls_this_attempt=final['synthetic_provider_calls'],
        synthetic_provider_calls_all_attempts=first['synthetic_provider_calls']+final['synthetic_provider_calls'],
        raw_logs=[link(HERE/name) for name in ('attempt-0001-tests.log','attempt-0002-tests.log',
             'native-B.stdout.log','native-B.stderr.log','native-C.stdout.log','native-C.stderr.log')],
        first_failure_classification='Independent fixture used probe-* folders not canonical upstream-*/improved-* raw discovery; no candidate source or research criteria failure. Two insufficient raw-negative assertions were discarded and rerun after correcting only the external fixture.',
        guard_limit='Python parent-process audit/profile guard; trusted snapshot and stdlib; not OS-wide isolation. No child processes/network/actual provider or tasks.run_task allowed. Explicit hand-authored public engineering arrays are not original private owner rows.',
        protected_historical_evidence_scope='No old actual v7/9-study or protected-source body opened by worker. Root supplied its separate source108/protected417 stability receipt; this independent finisher directly checks only held candidate110 and own snapshot58.',
        engineering_gain_or_model_effect_claim=False,goal_complete=False)
    create(HERE/'result.json',final)
    command={'kind':'tool_command_transcription_not_new_execution',
        'python':'C:/Users/Potato/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
        'commands':[{'arguments':['-X','utf8','-B','independent_fixture.py'],'attempt':'0001',
                    'status':'failed_independent_fixture_format','methods':5,'result':link(HERE/'attempt-0001-result.json')},
                    {'arguments':['-X','utf8','-B','independent_fixture.py','0002'],'attempt':'0002',
                    'status':'pass','methods':2,'result':link(HERE/'attempt-0002-result.json')}],
        'successful_native_precapture_tests_repeated':False,'new_actual_trials':0}
    create(HERE/'execution-commands.json',command)
    report='''c8 독립 구성 검증은 PASS다. 구현 전 등록의 10개 family를 28개 subcase로 연결했다. 고정 candidate 110개를 실행 전후 대조했고 별도 source snapshot 58개(패키지 20·참조 38)도 그대로였다. 구현자의 13개 unittest를 독립 검증 대신 다시 실행하지 않았다.

실제 UpstreamArm callback 등록 writer와 고정 원본 초기 문헌 질의 경로를 실행해 합성 질의 3개를 기록했다. 실제 ImprovedArm callback 경로에서도 같은 public/model/medium/full-envelope 조건으로 합성 질의 3개를 기록했다. 처음 요청의 완료 prefix는 0, 세 번째 요청의 완료 prefix는 2이고 합성 usage·wall time의 합이 양쪽에서 같았다. 두 callback은 fixture 자원 한계로 종료했다. 이것은 초기 handoff 통합 검사이며 전체 연구 성공·보고서 완료를 검증한 것이 아니다.

missing/changed model·effort·전체 envelope, 원본 shape의 두 필드 누락, constructor 이후 receipt와 provider 변조는 provider 호출 및 input capture 전에 거절됐다. local callback/binding/tape/transport 재해시, canonical full guard를 raw fingerprint/result/capture까지 재해시해 제거하는 공격도 거절됐다. source pin/keyset과 같은 ID의 다른 public data도 등록 조건을 대체하지 못했다. source와 원 raw model/settings는 독립적으로 고정한 anchor다.

미래 request 제외, named target identity, 물리적 완료 receipt replay의 단일 계상, unknown failed usage의 null과 알려진 완료 lower bound, missing original mapping의 pending, phase 이동과 malformed flag 거절을 확인했다. real_model 표기를 붙여도 명시적 fixture는 ineligible이며 실제 semantic gate는 거절한다. component 전용 판정은 synthetic/adoption false로만 반환된다.

첫 attempt는 별도 fixture의 probe-* 폴더가 canonical raw discovery에 등록되지 않아 prefix 검사에서 실패했다. 원 helper·raw logs·실패 결과를 보존했다. 영향을 받은 raw 재해시 부정 사례 2개와 아직 성공하지 못한 prefix/flag 사례만 정상 폴더 형식으로 보수했다. 이미 성공한 native/constructor/capture 사례는 다시 실행하지 않았다. 이 실패는 candidate 알고리즘의 실패나 실제 과제 점수가 아니다.

두 attempt 전체에서 합성 provider completion은 28개였고 실제 provider·CPU 학습·owner/private 자료 읽기·연구 trial은 0이다. open/list/scandir/process/network guard와 run_task profile guard count가 모두 0이었다. 허용 source snapshot·stdlib·합성 temp 안의 Python 구성 검사이며 OS 전체 격리를 주장하지 않는다. 후보 및 과거 source·실행·기준을 수정하거나 기존 v7 실패·보류를 채택으로 바꾸지 않았다. 연구 향상·모델 교체 효과·Goal 완료는 아직 주장하지 않는다.
'''
    with (HERE/'report.ko.md').open('x',encoding='utf-8',newline='\n') as f: f.write(report)
    files=[]
    for path in sorted(HERE.rglob('*')):
        if path.is_file() and path.name!='manifest.json':
            files.append({'relative':path.relative_to(HERE).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
    create(HERE/'manifest.json',{'kind':'independent_c8_source_helper_raw_log_result_inventory',
        'files':files,'file_count':len(files),'scope':'Held source58 + independent helpers/pins/raw logs/results only. Synthetic generated output tree is separate; not a publication authorization.'})
    print(json.dumps({'status':'pass','result_sha256':sha(HERE/'result.json'),
        'manifest_sha256':sha(HERE/'manifest.json'),'report_sha256':sha(HERE/'report.ko.md'),
        'families':10,'subcases':sum(len(v['subcases']) for v in final['registered_family_verdicts']),
        'synthetic_calls':final['synthetic_provider_calls_all_attempts'],'actual_fit_or_provider':0,'candidate_source_stable':stable}))

if __name__=='__main__': main()
