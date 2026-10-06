# 함께 이해하는 연구 보고 화면 · 0.8.0

CLI·stdio MCP·웹/WebMCP는 같은 root/workspace의 목표·실험·증거와 상태 전이 규칙을 사용합니다. 외부 에이전트가 연구와 판단을 수행하며 웹은 사람이 이해할 요약·비교·불확실성을 읽기 전용으로 표현합니다. 웹에는 모델 호출이나 자체 연구 판단 루프가 없습니다. 현행 관전 구조·원본 대응은 [의뢰인 설계](CLIENT-VIEW-DESIGN.ko.md), 실제 설치·화면과 확인 범위는 [의뢰인 검증](CLIENT-VIEW-VALIDATION.ko.md)을 따릅니다. [초기 0.8 기획](PRODUCT-PLAN-0.8.ko.md)·[당시 검증](VALIDATION-0.8.ko.md)·[릴리스 보고](RELEASE-0.8.ko.md)와 [0.7 보고서](PRODUCT-VALIDATION.ko.md)는 당시 증거로 보존합니다.

## 시작과 관전

[로컬 보고 화면](http://127.0.0.1:8765/)을 사용합니다. 같은 서버가 이미 실행 중이면 기존 주소를 엽니다. 프로젝트에서 설치한 환경으로 실행하며 새 컴퓨터의 설치는 [README](README.md)를 참고합니다.

```powershell
Set-Location -LiteralPath 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch'
.\.mcp-venv\Scripts\python.exe -I -m research_cli.web_server --root 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces' --port 8765 --open
```

웹은 Python 표준 라이브러리와 패키지 HTML/CSS/JavaScript를 사용합니다. MCP SDK·모델 자격증명·CDN·프론트 빌드 없이 실행합니다. stdio MCP에는 선택 의존성 `[mcp]`가 필요합니다. 공개 서비스나 OS 자동 시작은 이 실행 명령으로 설정되지 않습니다.

후속 UI wheel은 `dist/client-spectator-20261004/research_state_cli-0.8.0-py3-none-any.whl`이며 프로젝트 `.validation-venv`·`.mcp-venv`의 갱신에 사용합니다. 같은 0.8.0 이름의 `validation/wheels` wheel과 이전 릴리스 번들은 역사 기록입니다. 현재 파일·설치본·서빙 자산의 일치는 후속 검증의 해시를 확인합니다.

사람은 외부 에이전트에게 “현재 결과와 막힌 이유”, “조건이 같은 시도의 차이”, “실패 원인과 원문”을 요청합니다. 에이전트가 열린 문서의 네이티브 WebMCP로 장면과 초점을 바꿉니다. 사람용 버튼·폼·검색·메뉴 없이 관전하며 기본 스크롤·텍스트 선택은 유지합니다.

## 두 정보 계층

기본 화면은 의뢰 질문 → 선택한 시도의 답과 실제 값·기준 비교 → 확인 범위 → 다음 확인의 보고 형식입니다. 관계도, 실행·검증·결정 배지, seed, 도구 수·버전·기록 번호는 기본에서 제외합니다. 정상 연결 표식은 줄이되 연결 실패는 드러냅니다. focus 또는 explanation을 지정하면 기본 보고를 한 설명 장면으로 교체하고, 둘을 생략한 overview 호출로 돌아옵니다. 관계는 graph에서 최대 6개 조회 기록, 모바일에서는 선택 경로를 보여 주며 조회 범위를 알립니다. 분석·비교·기억·시간/비용·반복·원문은 별도 장면입니다.

핵심 지표는 등록된 `primary_metric`을 우선하고, 없으면 현재 원본·고정 검증에 연결된 미충족 기준 지표, 다음으로 등록 순서를 사용합니다. 선택 이유와 원시 지표 이름은 WebMCP 결과에서 추적하며 기준·단위는 바꾸지 않습니다. 의뢰인 요약은 진단 지표의 통과가 다른 미충족 등록 기준을 가리지 않도록 미달 지표를 먼저 설명합니다. 선언된 표시 이름을 우선하고 일부 명칭을 읽기 쉽게 표시해도 없는 단위를 추정하지 않습니다.

전체 연구의 `completed`·`paused`·`cancelled`는 외부 보고이며 과학적 검증 통과가 아닙니다. 종료·중단 이유, 확보한 결과와 미완료 범위는 원본 목표 보고에 보존하며 기본 화면에 전체 문자열을 펼치지 않습니다. 실행 성공·검증 성공·가설 채택도 별개입니다. 이전 목표의 생애주기 미기록은 `unknown`이며 채택된 실험만으로 전체 연구를 완료 처리하지 않습니다.

| 장면 | 답하는 질문 |
|---|---|
| overview | 의뢰한 질문에 선택한 시도가 어떤 답을 냈고, 어디까지 확인됐으며 다음 확인은 무엇인가? |
| analysis | 등록 기준별 실제 값·단위·차이는 무엇이며 실행·검증·결정은 어떻게 다른가? |
| comparison | 평가 조건이 같은 시도의 결과와 소스·조건 차이는 무엇인가? |
| memory | 성공·실패·미결에서 무엇을 배웠고 그 주장과 원본은 검증됐는가? |
| activity | 실제 주요 사건·실행 시간·외부 비용 관측은 언제 생겼는가? |
| graph | 공유 가설과 조회한 실제 시도·산출물·검증·결정은 어떻게 연결됐는가? |
| stability | 사전등록한 비교 가능한 반복 측정의 n·범위·평균·변동은 무엇인가? |
| evidence | 선택한 원문의 보존 상태와 실제 내용은 무엇인가? |

비용은 통화별 외부 관측 소계이고 전체 사용량은 미확인으로 남습니다. 목표 전체 집계와 표시한 최근 추이의 조회 범위를 구분하며, 목표에만 연결된 비용을 가설별로 임의 배분하지 않습니다. 실행 wall time 합계와 목표 기록 후 달력상 경과 시간도 별개입니다. 등록된 단위가 없으면 추정하지 않습니다.

반복 분포에는 명시적으로 등록한 반복 설계와 같은 목표 버전·평가 조건·변경점·소스의 고유 실제 실행만 넣습니다. seed 차이를 공개하며 기술 통계를 독립성·신뢰구간·모집단 일반화로 해석하지 않습니다. 조건이 다른 비교는 별도 묶음이며 순위·임의 점수·진행률은 만들지 않습니다.

## WebMCP 호출

공통 연구 도구는 23개이며 브라우저는 `research_view`·`research_inspect_evidence`를 더해 25개입니다. 문서마다 도구 이름 접미사가 달라지므로 현재 발견한 이름을 사용합니다. 화면 도구의 workspace 생략은 현재 관전 작업공간, 연구 도구의 생략은 `default`입니다.

```json
{"workspace":"my-study","goal":"goal_…","scene":"overview","registration":"reg_…"}
```

위 인자를 `research_view`로 보냅니다. `goal`은 선택 사항이며 새 registration만 지정하면 그 등록의 목표를 사용합니다. 명시한 목표와 등록이 다르면 거부합니다. focus는 hypothesis/experiment/evidence/verification/conclusion입니다. comparison·graph·stability에서는 `compare:[{"workspace":"…","registration":"…"}]`를 최대 6개 지정할 수 있습니다. memory는 query/outcome/verification/limit/offset을 사용합니다. 화면은 필요한 요약만 펼치고 표시·조회·전체 수를 알립니다. limit 1–100과 offset은 조회 범위이며 연구 반복·시간 제한이 아닙니다.

`research_show`로 원본 ID를 얻은 뒤 아래를 `research_inspect_evidence`로 보내고 `research_view(scene="overview")`로 돌아옵니다.

```json
{"workspace":"my-study","registration":"reg_…","evidence":"ev_…"}
```

`research_view`는 `presentation`과 장면의 `viewModel`, overview의 `clientBrief`를 반환하며 판단용 사실은 `viewModel.judgment`, 원본 연결은 refs로 제공합니다. 기억 장면은 검색한 memory, 원문 장면은 선택 evidence와 참조를 반환합니다. 각 참조의 조회 revision·등록 당시 목표 버전·등록 지문으로 표시를 추적합니다. 에이전트의 explanation은 미검증 설명으로 표시합니다. 화면 전환은 연구 기록을 변경하지 않습니다.

## 접근 범위와 한계

| 경로 | 역할 |
|---|---|
| GET /api/bootstrap | 버전·세션·공통 연구 도구 23개 |
| GET /api/workspaces | 전용 루트의 상대 작업공간 요약·페이지 |
| GET /api/snapshot | 상태·사건·선택 목표 집계·페이지; registration/goal의 적용 범위 명시 |
| POST /api/call | 공통 23개 연구 도구의 JSON 입력·결과 |
| GET /api/evidence | 등록에 연결된 원문의 현재 해시 확인·최대 256 KiB UTF-8 내용 |

서비스는 루프백·정확한 Host·동일 Origin·변경 요청의 세션을 확인합니다. 임의 파일·키·DB 다운로드나 owner 검증기 관리 도구는 제공하지 않습니다. 화면 도구는 HTTP/stdio의 연구 dispatch에 추가되지 않습니다. 이 검사와 해시·역할 분리는 OS 보안 격리가 아닙니다. 신뢰한 실험 코드를 실행하는 기존 경계를 유지합니다.

원본 무결성은 revision 변경 없이도 다시 읽습니다. 현재 누락·변조는 구분해 경고로 드러내며 과거 검증·채택 기록을 현재 성공 근거로 쓰지 않습니다. 해시 일치는 파일 보존 상태이고 과학적 타당성의 증명이 아닙니다. 초기 표시·갱신·재연결은 읽기만 하며 실행·복구·검증·변경 요청을 자동 재전송하지 않습니다. 같은 장면·선택·초점의 배경 갱신은 내부 스크롤을 보존합니다. 실제 변화·초점 이동에만 제한된 모션을 쓰고 reduced-motion을 지원합니다.

네이티브 WebMCP의 실제 지원 범위는 최종 검증 보고서를 확인합니다. 미지원 브라우저는 관전과 CLI 변경 조회만 가능합니다. 긴 동기 호출에서 호스트 응답이 끊기면 `status/show`로 원 실행을 확인하고 `recover`로 그 영수증을 수집합니다. 새 실행을 만드는 근거가 아닙니다. Laya 실행·모델 선택·토큰 확인은 외부 에이전트의 책임입니다. 화면 개선과 기능 확인은 연구 성능 개선을 입증하지 않습니다.
