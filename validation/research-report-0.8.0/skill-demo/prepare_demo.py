"""External agent authors the goal and experiment; this does not run a model."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

out = Path(__file__).resolve().parent
project = out.parents[2]
workspace = project / 'research-workspaces' / 'goal-plugin-demo-20261004'
experiment = workspace / 'skill-demo-experiment'
experiment.mkdir(exist_ok=True)
prompt = '''# 고객 응답 CSV 기술통계 연구: 장기 목표 프롬프트 v1

역할과 책임
당신은 원래 의뢰를 이어가는 외부 연구 에이전트다. 의뢰 해석, 가설, 코드, 실행 계획, 해석과 보고는 에이전트가 담당한다. Research State CLI·stdio MCP·WebMCP는 같은 영속 연구 상태의 채널이며 도구 내부에서 모델을 호출하지 않는다.

원래 의뢰
“누락값이 섞인 고객 응답 CSV로 팀별 만족도를 믿고 보고할 수 있는지 연구해 줘.”

장기 목표
공개 합성 data.csv에 대해 합의된 누락 제외 규칙으로 전체·팀별 기술통계를 재현 가능하게 계산하고, 소유자가 이미 고정한 독립 검증기로 정확성을 확인한다. 사업 기준 80% 충족 여부와 계산 정확성을 분리해 한국어로 답한다. 누락과 표본 크기 때문에 생기는 해석 한계를 수치와 함께 보고한다.

적용 상황과 범위
이 설치 스킬·CLI·웹 개발 실연의 고정 CSV에만 적용한다. 실제 고객 연구, 다른 집단으로의 일반화, 인과 효과, 통계 검정력, 모집단 신뢰구간 및 연구 성능 개선 주장은 범위 밖이다. 별도 채널로 이동할 때도 같은 목표·실행·작업공간을 이어간다.

확정 사실·가정·미확인
확정 사실은 validation/skill-demo-request.ko.md의 의뢰자 정보다. 평점 1–5가 유효하며 빈 평점은 누락으로 세고 계산에서 제외한다. 만족도는 유효 평점 평균/5×100, 단위는 percentage다. 사업 기준은 80% 이상이다. 요청자는 연구 비전문 엔지니어이고 단계·목표 대비 지표·관측 비용·시간·확인 결과를 받는다. 파일 작성과 이 데이터의 로컬 실행은 승인됐다.
가정: CSV의 team은 이 fixture의 보고 단위이고 누락 제외 요약은 관측된 응답만의 기술통계다. 이 가정이 달라지면 해석 범위를 새 목표 버전으로 기록한다. 누락이 무작위라고 가정하지 않는다.
미확인: 에이전트 세션의 실제 토큰 및 비용 영수증이 현재 인터페이스에 제공되지 않는다. 에이전트가 관측 가능성을 기록하고 unknown으로 보고한다. 핵심 목표·자료·권한·사업 기준은 이미 제공되어 추가 사용자 질문이 필요하지 않다.

산출물과 완료 기준
장기 목표 프롬프트와 구조화 brief, 재현 코드, 해시 고정 원본·소스, 사전등록, 실제 로그·요약 산출물, 고정 검증 결과, 결정, 한국어 보고, 원본 연결 및 재개 안내를 남긴다. 세 prescribed fixed-input 실행에서 실제 산출물을 수집하고 검증 결과를 확인해 이 CSV의 기술통계와 80% 기준 질문에 근거 있는 답을 하면 완료다. 기준 미달도 답이 될 수 있다. 실행 종료, 검증의 모든 기준 통과, 가설 채택, 원본 해시 일치와 연구 완료는 각각 구분한다. 실행 실패만으로 가설을 반박하지 않는다.

성능·과학적 주장 판정
처음의 검증 가능한 가설은 합의된 누락 제외 공식으로 전체 만족도가 80% 이상이라는 것이다. 사전등록 지표는 calculation_matches(독립 계산 일치 여부, 1이 일치)와 satisfaction_pct(percentage, 높을수록 사업 기준에 가까움)다. 기준은 calculation_matches==1 및 satisfaction_pct>=80이며 결과를 보고 덮어쓰지 않는다. 비교는 소유자의 고정 독립 재계산과 명시된 사업 기준으로 한정한다. 성능 개선 baseline이나 개발/최종 holdout은 이 고정 fixture 기술통계 질문에 해당하지 않는다. 같은 입력·같은 소스·같은 조건을 seed 0,1,2로 세 번 실행하고 conditions.repeat_design=three_fixed_input_replications를 등록한다. seed는 재현 기록이며 계산에 확률 요소가 없다. 이는 최소 표시 fixture의 반복 분포이며 독립 표본이나 모집단 검증이 아니다. 반복 수를 전체 연구의 종료 한도로 쓰지 않는다.

권한과 실제 제약
허용된 data.csv, 전용 workspace, 고정 검증기 csv-owner-fixed-v1, 로컬 Python과 Research State 채널을 사용한다. 네트워크, 외부 모델 비용 지출, 전역 설정 변경, 검증기·소유권 키·원본 CSV 변경은 허용되지 않는다. 관측되지 않은 비용·토큰은 unknown, 임의 전체 시간·비용·실패 한도는 미설정이다. 이미 주어진 실행 승인을 재질문하지 않는다.

초기 계획
상태와 성공·실패·미결 기억을 조회한다. 안정된 key로 목표를 저장하고 동일 요청 재전송의 원본 재사용을 확인한다. 가설을 기록한다. 외부 에이전트가 CSV 요약 코드를 작성하고 task.py와 복사한 data.csv를 각각 SHA-256 고정한다. 실행 전에 seed별 세 등록과 owner의 고정 검증기를 연결한다. 등록 후 계획 변경은 이유를 갖는 goal_amend(plan)로 기록하며 목표 의미·범위와 등록 기준을 보존한다. 각 등록의 실제 실행·검증·반대 증거를 수집하고 80% 가설 결정을 기록한다. 자원 관측의 범위와 telemetry unknown을 저장한다. goal_close의 사유·결과·미완료를 명시하고 완료 요청을 같은 key로 재전송해 추가 worker가 없음을 확인한다.

보고
현재 단계, 전체 및 팀별 지표와 기준 차이, 누락·유효 행, 고정 검증의 정확성 일치와 전체 기준 판정, 시간, 비용·토큰 관측 범위를 먼저 보고한다. 에이전트의 종료 보고는 독립 검증을 대신하지 않는다. 웹 채널에서는 실제 지원되는 overview→analysis/comparison/stability/resource 관련 실제 장면→필요한 원본 증거→overview 흐름을 에이전트가 선택하며 가짜 품질 점수나 과학적 관계를 만들지 않는다.

변경·인수인계
절대 root와 상대 workspace, 목표 ID·버전·현재 revision, 등록·실행 ID·원본 경로·해시는 demonstration-manifest.json에서 확인한다. 프롬프트 파일과 DB 저장은 별도이며 원자성을 주장하지 않는다. 재개 전에 goal_show·status·memory와 원 실행 상태를 읽는다. unknown 실행은 show/recover로 원본을 확인하며 자동 재실행하지 않는다. 동일 key의 과거 재사용 응답은 최신 상태를 다시 조회한다. 완료 이후 새 범위나 자료에 대한 연구는 그 권한과 목표 변경을 먼저 확인한다.
'''
prompt_path = out / 'long-term-goal-prompt.v1.ko.md'
prompt_path.write_text(prompt, encoding='utf-8')
prompt_sha = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
brief = {
 'original_request': '누락값이 섞인 고객 응답 CSV로 팀별 만족도를 믿고 보고할 수 있는지 연구해 줘.',
 'long_term_goal': '고정 공개 합성 CSV의 합의된 기술통계를 재현·독립 검증하고 계산 정확성과 80% 사업 기준의 충족 여부를 분리해 답한다.',
 'context': '비전문 연구 분야 엔지니어를 위한 설치 스킬·CLI·웹 개발 실연',
 'scope': {'population': 'public synthetic data.csv only', 'exclusions': ['population generalization', 'causal effects', 'performance improvement', 'power or population intervals']},
 'facts': ['ratings 1–5 valid; empty excluded and counted', 'satisfaction_pct = mean valid rating / 5 * 100; percentage', 'business criterion >=80', 'local writes/execution approved', 'three fixed-input display replications seed0,1,2 prescribed', 'owner frozen csv-owner-fixed-v1'],
 'assumptions': [{'assumption': 'team is fixture reporting unit; complete-case descriptive means describe observed responses only', 'impact_if_false': 'revise interpretation with explicit new goal version'}],
 'unknowns': [{'item': 'external agent tokens and costs', 'owner': 'agent telemetry observation', 'resolution': 'record unavailable per-demo telemetry as unknown, without inventing a receipt'}],
 'deliverables': ['goal prompt and structured brief', 'task.py and source/data hashes', 'preregistered real runs and original evidence', 'fixed independent verifier results', 'decisions', 'Korean report and resume handoff'],
 'completion_criteria': ['three prescribed fixed-input runs collected and fixed verifier checked', 'answer exact CSV calculation and >=80 business criterion separately', 'evidence-backed negative result can complete question', 'no unknown/running executions left at closure'],
 'evaluation': {'metrics': ['calculation_matches', 'satisfaction_pct'], 'units': {'calculation_matches': 'boolean represented as 0 or 1', 'satisfaction_pct': 'percentage'}, 'criteria': [{'metric': 'calculation_matches', 'op': '==', 'threshold': 1}, {'metric': 'satisfaction_pct', 'op': '>=', 'threshold': 80}], 'comparison': 'owner fixed independent recalculation and supplied 80% threshold; no improvement baseline', 'split': 'all public fixed fixture; no held-out population inference', 'seeds': [0,1,2], 'repeat_design': 'three_fixed_input_replications', 'repeat_rationale': 'prescribed minimal development display fixture; deterministic repeat distribution only'},
 'permissions': {'allowed': ['dedicated workspace writes', 'local execution of supplied fixture', 'same root CLI/stdio/WebMCP'], 'excluded': ['network', 'external model cost spending', 'global config mutation', 'frozen validator mutation', 'owner key mutation', 'original CSV mutation'], 'source': 'validation/skill-demo-request.ko.md'},
 'resource_constraints': {'cost': 'unknown; no external spending authorized', 'tokens': 'unknown', 'time': 'not set', 'whole_research_iteration_limit': 'not set'},
 'initial_plan': ['status then memory', 'idempotent goal', 'hypothesis', 'external-agent code and hash-pinned preregistration', 'actual run and fixed independent verify', 'decision and telemetry observation', 'goal close and exact completed-request replay'],
 'reporting': {'language': 'Korean', 'persona': 'engineering owner with no research expertise required', 'first': ['phase', 'observed metrics versus goal', 'cost scope', 'elapsed time', 'results and verification'], 'scientific_scope': 'fixed-input technical descriptive verification only'},
 'handoff': {'root': str(project / 'research-workspaces'), 'workspace': 'goal-plugin-demo-20261004', 'prompt_path': str(prompt_path), 'prompt_version': 1, 'prompt_sha256': prompt_sha, 'manifest_path': str(out / 'demonstration-manifest.json'), 'goal_request_key': 'skill-demo-goal-original-20261004-v1', 'resume': 'goal_show/status/memory, inspect original run IDs; recover unknown rather than create replacement; resume only if authorized new work remains'}
}
(out / 'goal-brief.v1.json').write_text(json.dumps(brief, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
amended = copy.deepcopy(brief)
amended['initial_plan'] = ['status then memory', 'idempotent goal', 'hypothesis', 'external-agent code and three hash-pinned registrations at goal version1', 'after registration, collect every run and verify result before writing the joint Korean report', 'retain per-registration decisions and unchanged >=80 / calculation==1 criteria', 'record telemetry unknown and goal-close evidence-backed answer', 'replay original completed requests and read current state']
(out / 'goal-brief.v2-plan.json').write_text(json.dumps(amended, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
decision_record = {'skill': 'research-goal', 'skill_source': str(project/'plugin'/'skills'/'research-goal'/'SKILL.md'), 'request_source': str(project/'validation'/'skill-demo-request.ko.md'), 'references_read': ['references/goal-template.ko.md','references/channel-contract.ko.md'], 'user_questions': [], 'why_no_user_questions': 'original request plus known owner context settles goal, deliverables, data, authority, threshold, repeat design and environment; reasking would duplicate known answers', 'agent_questions': [{'question':'What exact source CLI schema is installed in source?', 'action':'read actual --help and help --topic goal/register'}, {'question':'How to calculate reproducible team descriptive means with missing ratings?', 'action':'author csv-based code, pin both source and copied CSV, use unchanged fixed owner validator'}, {'question':'Can the 80% business target be met?', 'action':'preregister threshold before runs and answer from real outputs'}, {'question':'Can repeated fixed inputs support independent population inference?', 'answer':'No; prescribed deterministic functional replications only'}, {'question':'Are per-demo external-agent tokens/costs observable?', 'action':'record actual lack of per-demo receipts as unknown with telemetry evidence source'}], 'assumptions': brief['assumptions'], 'unresolved': brief['unknowns'], 'external_agent_usage': {'actual_agent_authored': ['goal prompt','structured brief','hypothesis','experiment source','preregistrations','interpretation','next actions'], 'cli_llm_calls': 'none requested; tools persist and execute local Python only', 'actual_tokens_and_cost': 'unknown'}, 'diagnostic_note':'Two initial unsupported help topic guesses registration/execution returned INVALID_INPUT; preserved in transcript and corrected using actual help topics. No state mutation resulted.'}
(out / 'skill-use-decision-record.json').write_text(json.dumps(decision_record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
shutil.copyfile(workspace/'data.csv', experiment/'data.csv')
task = '''"""Descriptive summary for the fixed public CSV; no model or random sampling."""
import argparse
import csv
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--seed', type=int, required=True)
args = parser.parse_args()
rows = list(csv.DictReader(Path('data.csv').open(encoding='utf-8', newline='')))
teams = {}
values = []
missing = 0
for row in rows:
    team = teams.setdefault(row['team'], {'valid_rows': 0, 'missing_rows': 0, 'values': []})
    rating = row['rating'].strip()
    if not rating:
        missing += 1
        team['missing_rows'] += 1
        continue
    value = float(rating)
    if not 1 <= value <= 5:
        raise ValueError('Rating outside authorized 1-5 range')
    values.append(value)
    team['valid_rows'] += 1
    team['values'].append(value)
if not values:
    raise ValueError('No valid ratings for descriptive satisfaction')
team_means = {name: sum(record['values']) / len(record['values']) for name, record in teams.items() if record['values']}
summary = {'valid_rows': len(values), 'missing_rows': missing, 'total_rows': len(rows), 'satisfaction_pct': sum(values) / len(values) / 5 * 100, 'team_means': team_means, 'teams': {name: {'valid_rows': record['valid_rows'], 'missing_rows': record['missing_rows'], 'mean_rating': team_means.get(name), 'satisfaction_pct': team_means[name] / 5 * 100 if name in team_means else None} for name, record in teams.items()}, 'seed': args.seed, 'repeat_design': 'three_fixed_input_replications', 'scope': 'fixed public synthetic CSV descriptive values only'}
Path('summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
'''
(experiment/'task.py').write_text(task, encoding='utf-8')
hashes = {name:hashlib.sha256((experiment/name).read_bytes()).hexdigest() for name in ['task.py','data.csv']}
(out/'source-manifest.json').write_text(json.dumps({'label':'skill-demo-descriptive-csv-v1','experiment_cwd':str(experiment),'files':hashes,'original_csv_sha256':hashlib.sha256((workspace/'data.csv').read_bytes()).hexdigest(),'validator_original_sha256':hashlib.sha256((workspace/'fixed_validator.py').read_bytes()).hexdigest()},indent=2)+'\n', encoding='utf-8')
print(json.dumps({'prompt_sha256':prompt_sha,'source_files':hashes,'experiment':str(experiment)}))
