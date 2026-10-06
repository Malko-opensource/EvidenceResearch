# EvidenceResearch 0.8.0 독립 구현 감사

2026-10-04. 활성 목표 첨부의 요구사항을 현재 Python/JavaScript 소스와 전용 검사에 대조했다. 문서에 적힌 기능을 구현 증거로 간주하지 않았다. 브라우저 제어, 기존 연구 공간 수정, 전역 환경·자격증명 변경은 하지 않았다.

현재 확인한 코드 결함은 담당 에이전트가 수정했고 독립 재검사에서 통과했다. 이 감사가 웹 화면 캡처나 최종 설치 번들 검증을 대신하지는 않는다.

## 요구사항 대응

| 요구사항 | 실제 구현과 검사 | 판정 |
|---|---|---|
| 목표 저장·버전·중단·종료·재개 | `core.py`의 goal_versions/goal_lifecycle, goal_amend/close/resume; `tests/test_goals.py` 실제 CLI·웹 bridge, 동일/동시 요청, 변경 충돌, 고정된 등록 목표 버전 | 통과 |
| 기존 데이터 호환 | `_migrate`의 BEGIN IMMEDIATE와 원본 행 보존, legacy unknown 매핑, FK 검사; v1 아카이브·동시 열기·구형 클라이언트의 원래 테이블 쓰기를 SQL로 재현한 검사 | 소스·격리 검사 통과; 실제 구형 프로세스 동시 mutation은 미실행 |
| 읽기 전용 표현 | `view_model.js`의 buildViewModel, supportFor, 기록 기반 flow/relationship; 깊이 동결 입력 불변 검사 | 통과 |
| 성공·검증·채택·원본 무결성 구분 | source/run/validator/artifact/criteria 연결 검사, 현재 변조 시 역사적 판정과 분리; 과거 판정을 현재 성공으로 바꾸지 않는 모델 검사 | 통과 |
| 실제 값·단위·목표 차이 | 명시된 등록 단위만 사용, ratio/% 변환, 원래 연산자와 기준 유지, 미충족·음수·극값·미등록 단위 검사 | 통과 |
| 같은 조건의 비교 | compareRecords 조건 cohort, 목표 버전·분할·seed·기준·검증기·지표 단위 비교; 복원된 동일 등록은 중복 시도로 세지 않음 | 통과 |
| 반복 측정·독립성 | 명시된 repeat_design + 실제 고유 run, 같은 소스/변경점/평가 조건, n/평균/범위/표본 SD; 신뢰구간·일반화·독립성은 미확인 | 통과; 기술 통계 범위 |
| 누적 자원과 조회 범위 | `_goal_report` 전체 고유 실행 시간 합계와 페이지별 추이 분리; 통화 분리·관측 소계·미기록 전체 비용 unknown; 실행 전 분기 비용과 연결 사건 검사 | 통과 |
| 에이전트 판단 정보 | judgment의 기준·반대/미충족 기준·누락·원 실행·자원·constraints·원본 참조, 고정 목표 버전·revision·fingerprint | 통과 |
| 실행 취소와 요청·오류 이력 | 취소를 실행 분포에서 별도 표시; 전체 선택 목표의 persisted request key 매핑과 원 실행, 실행 실패 reason 묶음, running/unknown 원 실행을 execution_audit로 제공 | 소스·격리 검사 통과; 미기록 호출·replay 횟수는 unknown |
| 빈 데이터·다량 데이터·모바일·reduced-motion | source에서 카드/지표/관계/기억 표시 상한, CSS 반응형·비색상 상태·reduced-motion, 빈 모델 검사 확인 | 코드 확인; 실제 화면 검증은 주 에이전트 증거 필요 |
| 스킬과 실행 권한 경계 | 스킬은 이미 확인된 맥락을 보존하고 사용자 질문/에이전트 설계를 분리; 설치·프롬프트 생성은 실행 승인 아님; 로컬 owner 검증기 등록은 MCP에 노출되지 않음 | 코드·스킬 확인 |
| 모델 호출 책임 | CLI/웹은 상태·명령 실행·고정 검증만 담당; Laya는 외부 입출력 교환; 내부 모델 대화·자체 연구 루프 없음 | 코드 확인 |
| 대상 호스트 발견·설치 | 기존 host-check-v2의 MCP 0.7.0/17도구 기록과 최종 host-check-final의 실제 MCP 0.8.0/23도구·스킬 enabled 기록을 구분 | 주 에이전트의 최종 기록 확인; 아래 설치 증거 참조. 감사자가 재설치하지 않음 |

## 발견한 결함과 재검사

1. 실제 스킬 brief의 객체형 resource_constraints가 빈 배열로 투영되던 문제를 재현했다. 수정 후 실제 brief에서 비용·토큰·시간·전체 연구 반복 한도의 네 항목과 원본 참조가 보존된다.
2. selected snapshot 참조가 stamp 이후 추가되어 revision/goal_version이 없던 문제를 재현했다. 수정 후 모든 해당 참조에 버전이 있다.
3. 조회되지 않은 과거 기억의 goal_version을 현재 목표 버전으로 덮던 문제를 재현했다. 수정 후 원래 목표 버전 1과 기억 조회 revision 7이 유지된다.
4. 성공 기준이 없는 등록 진단 지표가 실제 검증 측정인데도 과거 수치로 표시되던 문제를 재현했다. 수정 후 측정과 반복 분포에 포함하되 성공 판정을 만들어 내지 않는다.
5. standalone 비교·반복 응답의 참조에 버전이 없던 문제를 재현했다. 수정 후 각 원본 기록의 revision/goal_version/fingerprint가 포함된다.
6. 실행이 없는 등록 분기에 연결된 실제 비용이 전체 합계에는 있으나 분기 보고에서 사라지던 문제와 비용 도착 사건 누락을 재현했다. 수정 후 실행 0회, 시간 미확인, USD 2의 귀속과 연결 사건이 함께 표시된다.
7. 같은 workspace에서 목표 A를 본 뒤 다른 목표의 등록 B만 선택하면 stale goal A와 registration B를 함께 요청하던 문제를 실제 app 함수로 재현했다. 수정 후 이전 goal 필터를 제거하고 B의 목표로 연결된다. `multigoal-selection.mjs`는 최소 DOM/HTTP 응답 harness를 사용하며 브라우저 사용 증거가 아니다.
8. 역사적 검증·채택 노드의 텍스트는 과거를 표시하지만 badge 색은 성공으로 남던 표현 문제를 코드에서 확인했다. 현재 semanticPath는 historical을 badge 상태 판정에 전달해 경고 표현을 사용한다. 최종 실제 화면은 주 에이전트가 확인한다.

## 독립 실행 결과

- 최종 소스에서 `node --test tests/test_view_model.mjs`: 54/54 통과. 취소 분포·장면 routing·execution_audit의 미확인 값과 입력 불변 검사를 포함한다.
- `.mcp-venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p test_goals.py -v`: 12/12 통과.
- 세 개의 실제 HTTP 전용 검사(전체 실행 집계, 실행 전 분기 비용/사건, 목표만 있는 보고): 3/3 통과. 임시 fixture는 validation/audit 아래에서 생성·정리했다.
- `node validation/audit/multigoal-selection.mjs`: 통과. B 선택 요청에 stale goal A가 없고 presentation.goal=goal-B다.
- 최종 집중 재검사 4/4 통과: 전체 실행/key 매핑 집계, 실행 전 분기 비용/resource 사건, v1 원래 테이블 append 호환, 실행 컴포넌트의 확인된 취소 receipt. 모든 새 임시 fixture는 validation/audit 아래에서 생성·정리했다.
- 별도 격리 ledger 계약 검사: 실행 명령을 띄우지 않고 테스트용 상태를 저장했다. 등록 4개/고유 run 4개에서 동일 key 재요청은 매핑을 추가하지 않고 새 key로 같은 원 실행을 조회하면 매핑만 추가된다. 매핑 합계 5, 받은 요청·replay 횟수 null, 동일 reason의 실패 원 실행 2개, unknown 원 실행 1개를 확인했다. limit=1/offset=999에도 전체 합계는 유지됐고 per_run은 최근 1개 취소 기록을 반환했다. 이는 실제 연구 결과나 실제 실행 성능을 입증하는 fixture가 아니다.

## 최종 소스의 집계 의미와 호환 범위

`view_model.js:311`은 cancelled를 failed/unknown과 구분해 이번 status 페이지의 실행 분포에 포함한다. 전체 목표의 취소(`goal_close(state='cancelled')`)가 worker 실행 취소로 변환되지는 않는다. 실제 run 취소는 `core.py:713`의 실행 컴포넌트 권한과 `cancellation.confirmed=true`·사유가 있는 terminal receipt가 있어야 저장된다. 취소 기록을 과학적 기각으로 해석하지 않는다.

`web_server.py:138–140,192–204`의 execution_audit는 선택 목표의 모든 고유 run과 `requests(scope='run', target=run.id)` 사이의 실제 저장 매핑을 집계한다. `request_keys_total`은 호출 횟수가 아니다. 같은 key의 재요청 시도 횟수와 전체 수신 호출은 저장되지 않아 `replay_attempt_count`와 `requests_received_count`를 null로 둔다. `per_run`은 최근 min(limit,100)개의 원 실행과 매핑 수를 제공한다. error_groups는 state=failed의 저장된 reason 문자열이 정확히 같은 고유 run만 묶으며 과학적 기준 미달은 실행 오류에 포함하지 않는다. 최대 6묶음/묶음별 6개 run ID를 보여 주고 전체 묶음 수를 따로 제공한다. running/unknown 원 실행은 최대 100개와 `unresolved_total`을 함께 제공하고 원 실행의 recover를 가리킨다. 오류 원인 분석·동일 key replay 횟수·자동 대체 실행을 만들어 내지 않는다.

`view_model.js:342–345`의 에이전트 판단 응답은 이 audit 정보를 깊이 복사하고 현재 보고의 goal version/revision 참조를 추가한다. 개별 원 실행의 등록 당시 목표 버전은 원 registration을 show로 조회해 대조한다. 집계에 여러 목표 버전의 실행이 포함될 수 있으므로 전체 audit를 하나의 실험 조건 cohort로 해석하지 않는다.

`core.py:103–114`는 v2 DB에도 아직 매핑이 없는 원래 goals/registrations 행이 있으면 BEGIN IMMEDIATE 안에서 호환 매핑을 추가한다. 구형 writer가 lifecycle을 기록하지 않았다는 사실은 unknown/legacy_mapping과 빈 structured brief로 보존한다. 연구 revision·원본 이벤트·원래 행을 새 연구 수행으로 갱신하지 않는다. `tests/test_goals.py:58`은 옛 클라이언트의 원래 테이블 INSERT를 격리 DB에서 재현한 검사다. 기존 연구를 오염시키는 실제 옛 프로세스 mutation은 수행하지 않았다. `validation/research-report-0.8.0/legacy-state-check.json`의 주 에이전트 기록은 기존 9개 연구 공간의 원래 테이블 보존 검사 결과(`ok=true`, `invalid=[]`)이며 구형 프로세스 실행 증거와 구분한다.

`web_server.py:247–259`의 사건 조회는 status revision 이하의 원본 사건만 읽고 최근 20개와 전체 연결 사건 수를 제공한다. 선택 등록에서는 해당 등록의 FK로 연결된 resource observation ID를 포함하고, 선택 목표에서는 그 목표의 resource observation ID를 포함한다. 다른 등록의 비용을 선택 실험 사건으로 배분하지 않는다. 목표에만 연결된 비용은 목표 사건·전체 소계에 남고 임의로 분기·등록에 귀속하지 않는다. 실제 HTTP 검사 `tests/test_web.py:340`은 실행 없는 등록의 USD 2 관측이 선택 목표/등록의 사건과 분기 보고에 나타나면서 run은 생성되지 않는 것을 확인한다. 선택 등록 장면에는 연결된 목표·가설·검증기 사건도 들어가므로 이 목록은 그 실험의 실행 명령만 나열한 목록이 아니다.

## 주 에이전트의 최종 설치 기록과 남은 화면 증거

감사자가 재설치하거나 최종 서비스·브라우저를 제어하지 않았다. 다음 주 에이전트의 실제 채널 기록을 읽어 소스 감사와 분리했다.

- `validation/research-report-0.8.0/installation.json`: 소스 밖 cwd의 isolated 설치 모듈 0.8.0, SDK 없는 core runtime, 23도구, Python 모듈·웹 asset 일치와 기존 연구 revision 불변. 실험·모델 호출 없음.
- `validation/mcp-installation-0.8.0.json`: 실제 stdio transport 0.8.0/23도구, 소스 밖 실행과 설치 모듈 일치, configuration 변경 없음. 전용 설치 확인 공간의 호출 기록이다.
- `validation/plugin-0.8.0/host-check-final/host-discovery.json`: 실제 Codex CLI 0.160.0의 isolated plugin 설치, enabled 연구 스킬, pluginId로 연결된 MCP serverInfo 0.8.0/23도구. 모델 turn·전역 프로필 변경 없음. 이전 host-check-v2의 0.7.0 기록을 이 최종 증거로 바꿔 해석하지 않는다.
- `validation/research-report-0.8.0/test-results.json`: 주 에이전트의 최종 전체 Python 65/65, JavaScript 54/54 기록. 감사자의 집중 재실행 결과와 구분한다.

최종 installed 웹 서비스의 실제 WebMCP 발견·장면/초점 전환·증거 장면 후 요약 복귀, 실제 보고 수치/비용/시간/상태와 원본 대조, 변조·unknown·취소 표시, 다량/빈 데이터·모바일·reduced-motion 화면 및 캡처는 주 에이전트의 별도 최종 기록이 필요하다. 여기서 그 화면 검증을 통과했다고 선언하지 않는다.

최종 패키징·현재 서비스·실제 WebMCP·화면 캡처는 주 에이전트가 검증한다. 최신 원본 해시와 설치 버전을 최종 증거와 함께 고정해야 한다. 본 검사들은 기능·표현의 정확성 검사다. 연구 성능 개선, 모집단 불확실성, 독립 확인 횟수 또는 외부 모델 전체 비용을 입증한 결과가 아니다.
