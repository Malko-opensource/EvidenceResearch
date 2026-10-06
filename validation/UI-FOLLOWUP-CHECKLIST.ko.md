# 관전 화면 후속 보정 검증 기준

목표는 `UI-SIMPLICITY-AUDIT.ko.md`에서 확인한 문서형 누적 구조를 고치는 것이다. 기능 검사가 통과한 사실, 화면이 더 단순해졌다는 설계 판단, 사용자 이해도, 연구 성능 개선은 서로 다른 주장이다.

## 확인할 질문과 근거

| 요구 | 통과 근거 | 부족한 근거 |
|---|---|---|
| 기본 화면에서 무엇을 연구하고 현재 어디에 있는지 읽힌다 | 실제 데스크톱 캡처에 연구 질문·전체 상태·현재 경로·중심 결과가 먼저 보인다 | DOM에 필드가 존재하는 것만 확인 |
| 초점 설명이 누적되지 않는다 | 같은 장면에서 WebMCP로 대상을 바꾼 뒤 이전 설명이 교체되고 중심 공간이 유지된다 | 설명을 잘라내는 CSS만 확인 |
| 공유 가설·시도가 실제 관계로 묶인다 | 원본 등록의 가설 ID·실행·증거·검증·결정 연결과 화면 노드/관계를 대조한다 | 매 시도에 동일 5단계 카드 반복 |
| 측정과 사전 등록 기준을 의미 있게 읽는다 | 등록 단위·기준선·실측·조회 범위가 원본과 일치한다 | 미등록 단위를 추정하거나 임의 정밀도·진행률 사용 |
| 성공·실패·미결을 구분한다 | 성공/실패/미실행 실제 fixture 각각에서 실행·검증·결정이 구분되어 보인다 | 실행 성공·해시 일치를 가설 검증으로 표시 |
| 변조·누락된 증거를 성공으로 보이지 않는다 | 백업된 개발용 fixture 한 건만 임시 변조/누락하고 화면 경고·기록 유지·복원을 확인한다 | 과거 passed 판정만 읽어 현재 검증된 주장으로 표시 |
| 데이터가 없어도 장면이 성립한다 | 기존 0건 workspace에서 미등록·미측정이 명확하고 빈 차트를 가짜 수치로 채우지 않는다 | 빈 화면에 숫자 0을 성공 수치처럼 채움 |
| 기록이 많아도 한 열이 늘어나지 않는다 | 실제 32건 fixture에서 페이지 범위·전체 건수와 장면 골격·내부 조회를 함께 확인한다 | 32건을 모든 열에 그대로 펼침 |
| 인간 클릭 없이 관전한다 | native WebMCP로 개요 → 분석 → 증거 → 개요를 실행하고 툴 호출 원본을 저장한다 | 클릭 경로만 점검 |
| 모바일·reduced-motion에서 읽힌다 | 실제 좁은 뷰포트와 reduced-motion의 캡처·읽기 순서·넘침·초점 이동을 확인한다 | 미디어쿼리 문자열만 확인 |
| 연구 상태와 기준을 바꾸지 않는다 | 화면 점검 전후 모든 기존 DB 논리 해시·증거 파일 해시·실행 marker·core Python을 대조한다 | revision 한 값만 비교 |
| 현재 설치·서빙 파일이 검증한 소스와 같다 | 소스/프로젝트 설치 패키지/HTTP asset 바이트 해시가 모두 일치한다 | 소스만 테스트하거나 과거 wheel의 결과 사용 |

## 준비된 실제 fixture

| Workspace | 확인된 데이터 | 사용 범위 |
|---|---|---|
| `goal-plugin-demo-20261004` | 3개 고정 CSV 실행, 실행 성공 / 검증 실패 / 기각, 전체 연구 종료 | 종료 상태·핵심 결과·공유 가설·전체 보고와 선택 실험 구분 |
| `agent-observatory-20261004` | 외부 에이전트 실제 도구 사용 기록 | 설치된 HTTP와 기존 에이전트 기록 대조 |
| `product-empty-20261004` | 초기화된 0등록·revision 0 | 빈 데이터 |
| `product-fixtures-20261004` | 32등록, 실제 2실행, 성공 1·검증 실패 1·미실행 30, revision 44 | 성공/실패/미결·페이지·많은 기록·개발용 증거 변조/누락 |

fixture의 원본 식별자는 `validation/product-web-0.7.0/fixture.json`에 있다. `success`, `failure`, `unexecuted`, `goal` 키를 사용한다. 이 데이터는 화면 개발용이며 연구 성능 평가 과제가 아니다.

`validation/product_evidence_probe.py`는 이 fixture의 성공 산출물 하나만 다룬다. 반드시 `backup` → `tamper` 또는 `missing` → 화면 조회 → `restore` 순서로 수행하며, 변조와 누락 사이에도 복원한다. 원문 해시는 `4de3b679081334b6a27a13a022a3f2d98f8e37ec01dc24c947274dea68be163e`이다. 실제 연구 workspace와 다른 프로젝트의 증거는 변경하지 않는다. 사용 후 현재 해시와 저장한 백업을 다시 대조한다.

## 실행된 검사와 남은 점검

2026-10-04 후속 보정 시작 시 Python 65개 검사가 모두 통과했다. CLI JSON 출력 1, 상태·증거·전이 16, 평가 5, 전체 목표 12, Laya 10, MCP 9, HTTP 12개다. HTTP 검사는 실험 전 등록 고정, 동시·동일 요청 중복 실행 방지, 검증 전 채택 거부, 변조 증거 거부, 외부 파일/비공개 파일 제한, 반복 조회의 상태 불변, 페이지 조회, 별도 목표 집계 범위를 실제 임시 서버에서 확인한다. 임시 fixture는 각 검사 소유 경로에서만 생성·정리한다.

재현 명령(프로젝트 루트 PowerShell):

```powershell
& '.\.mcp-venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_*.py' -v
& '.\.validation-venv\Scripts\python.exe' '.\validation\observatory_followup_check.py' after --require-assets
```

첫 번째 로그와 모듈별 결과는 `validation/observatory-followup-20261004/python-regression.log`, `regression-results.json`에 저장했다. `observatory_followup_check.py before`는 이미 실행되어 `state-before.json`의 기준을 저장했다. 같은 `before`를 덮어쓰지 않는다. 두 번째 명령은 보정 소스의 프로젝트 내 설치/서빙이 완료되고 임시 변조 fixture를 복원한 뒤 실행한다. core·영속 상태의 불변과 source/installed/HTTP 파일 일치를 함께 요구한다.

이 검사 도구는 GET만 호출하고 모델·실험을 실행하지 않는다. DB는 SQLite read-only transaction으로 논리 내용을 해시하며, owner/internal key는 읽지 않는다. 실제 브라우저 레이아웃, native WebMCP, summary/그래프의 원본 대응, 접근성은 이 스크립트로 입증되지 않으며 별도 실제 화면 증거가 필요하다.

## 설치된 서버의 안전한 갱신 범위

기존 서비스는 프로젝트 `.validation-venv\Scripts\python.exe`의 설치 패키지이며 시작 기록은 `validation/research-report-0.8.0/web-service.json`이다. 후속 점검 시 PID 40608이 살아 있고 8765 HTTP가 응답함을 확인했다. 서비스는 정적 asset을 설치된 `site-packages/research_cli/web`에서 읽으므로 소스 폴더만 바꾸면 브라우저에는 보정이 전달되지 않는다.

갱신은 프로젝트 내 wheel과 프로젝트 `.validation-venv`에 한정한다. 재시작이 필요하면 기존 PID의 실제 실행 파일과 8765 점유를 먼저 확인하고 해당 프로세스만 정리한다. 루트는 기존 `EvidenceResearch/research-workspaces`로 유지한다. `Start-Process`는 `-WindowStyle Hidden`을 사용하고 로그를 새 validation 경로에 보존한다. 전역 Python, 다른 프로젝트 프로세스, 기존 연구 DB, 자격증명은 변경하지 않는다.

독립 실행 경로:

```powershell
& 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\.validation-venv\Scripts\python.exe' -I -m research_cli.web_server --root 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces' --port 8765
```

위 명령은 실제 프로젝트 설치 패키지를 격리 import한다. `--open`은 필요하지 않으며 브라우저 표시는 Codex의 기존 관전 탭을 사용한다. `/api/health`는 존재하지 않는다. 동작 확인은 `/api/bootstrap`, `/api/workspaces`, `/api/snapshot`으로 한다. bootstrap session token을 보고서에 출력하지 않는다.
