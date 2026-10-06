# AI용 MCP 연결 · 0.8.0

MCP는 모델과 독립된 연구 CLI의 선택 연결입니다. 공식 Python MCP SDK가 stdio 전송·스키마·프로토콜을 처리하고 같은 CLI dispatch·상태 라이브러리를 사용합니다. 핵심 CLI·웹 실행 의존성은 0개이고 stdio MCP만 `[mcp]`가 필요합니다. 모델 호출·인증·대화·자체 연구 루프를 추가하지 않습니다. Laya 입력/응답 교환은 유지하며 추론은 외부 에이전트가 수행합니다.

공통 연구 도구는 **23개**입니다. 웹의 네이티브 WebMCP는 읽기 전용 화면 도구 2개를 더해 **25개**입니다. 이는 현재 구현 계약이며 이 PC의 최종 설치·도구 발견·플러그인 호스트 증거는 [0.8 검증](VALIDATION-0.8.ko.md)·[릴리스 보고](RELEASE-0.8.ko.md)에서 확인합니다. 아래 0.7 이하의 당시 결과를 현행 설치 확인으로 합치지 않습니다.

## 같은 목표를 사용하는 두 채널

CLI·stdio MCP·WebMCP를 바꿔 사용할 때 같은 root/workspace·목표 ID·버전·등록 ID·요청 키를 유지합니다. `research_status`·`research_goal_show`로 현재 revision을 읽고 수정에 최신 `expect`를 사용합니다. 이미 처리된 같은 요청은 이전 결과를 재사용하며 후속 변경을 되돌리지 않습니다. 응답의 `result_is_historical`·`applied_revision`을 확인하고 현재 판단에는 상태를 다시 읽습니다.

새 목표의 brief는 외부 의뢰이며 검증이나 실행 허가가 아닙니다. 목표 수정은 의미·범위·계획을 새 버전으로 남기고 사전등록은 당시 목표 버전을 유지합니다. `research_goal_close`는 전체 연구의 완료·일시중단·취소 이유, 결과와 미완료 범위를 외부 보고로 남깁니다. 실험의 검증·채택과 별개이고 worker 종료도 뜻하지 않습니다. 완료는 running/unknown 원 실행이 남으면 거부합니다. `research_goal_resume`는 같은 목표를 재개하며 실행을 시작하지 않습니다.

`research_resource`·`research_resource_show`는 출처가 있는 비용·토큰 관측을 추가·조회합니다. 통화별 관측 소계와 미확인 전체 사용량을 구분하며 숫자 제출만으로 독립 검증을 만들지 않습니다. 자세한 불변 기록·생애주기·페이지 계약은 [목표 저장 계약](CORE-GOALS.ko.md)에 있습니다.

서버 root 아래 상대 workspace만 허용하고 기본값은 `default`입니다. 새 실행의 cwd와 파일 입출력을 전용 경로에 제한합니다. 키·DB 다운로드와 owner 검증기 등록은 공개 도구에 없습니다. owner가 CLI로 검증기를 먼저 고정합니다. 복원된 완료·running/unknown 기록을 자동 재실행하지 않습니다. 해시·경로·로컬 역할은 OS 샌드박스가 아니며 신뢰한 실험 코드만 실행합니다.

## 설치와 기존 개인 연결의 재연결

프로젝트에서 MCP용 가상 환경을 준비합니다. 이미 환경이 있다면 만들기 단계를 생략합니다. 일반 Python 3.11 이상을 사용하며 최종 wheel 설치 안내는 README를 따릅니다.

```powershell
python -m venv .mcp-venv
.\.mcp-venv\Scripts\python.exe -m pip install '.[mcp]'
.\.mcp-venv\Scripts\research-state-mcp.exe --root 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces'
```

stdio 서버는 호스트가 시작·종료하며 HTTP 포트가 필요 없습니다. stdout은 MCP 메시지, 진단은 stderr입니다. 이 PC의 기존 Codex `research_state` 설정 경로는 `C:\Users\Potato\.codex\config.toml`입니다. 기존 연결의 command/args는 다음과 같으며 다른 설정을 덮어쓰지 않습니다.

```toml
[mcp_servers.research_state]
command = 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\.mcp-venv\Scripts\python.exe'
args = ['-I', '-m', 'research_cli.mcp_server', '--root', 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces']
```

패키지를 갱신해도 이미 열린 stdio 프로세스는 이전 코드를 유지할 수 있습니다. 사용 중인 호스트에서 이 서버를 재연결하거나 새 연결·대화를 시작하고 `research_help` 및 도구 발견으로 23개 계약을 확인합니다. 기존 도구 17개가 보이면 이전 프로세스인지 확인합니다. 앱 전체를 자동 종료하거나 다른 프로젝트 프로세스를 중단할 필요는 없습니다. 다른 로컬 MCP 호스트에도 같은 command/args·root를 사용합니다. 이는 모든 AI나 웹/클라우드에 일괄 연결하는 설정이 아닙니다.

플러그인 번들 생성·개인 Codex의 설치 명령·의뢰 인터뷰 스킬은 [플러그인 안내](PLUGIN.ko.md)를 사용합니다. 독립 `CODEX_HOME`에서 수행한 호스트 검증은 개인 프로필 설치와 별개입니다. 번들을 준비하거나 검증했다고 개인 설치 완료로 해석하지 않습니다. 원본 플러그인의 빈 `.mcp.json` 대신 절대 실행 경로·전용 root를 고정한 준비 번들을 사용합니다.

## 첫 사용과 웹 관전

1. `research_help`·`research_status`·`research_memory`로 계약·현재 허용 작업·기존 증거를 읽습니다.
2. `research_goal`로 의뢰를 저장하거나 `research_goal_show`로 기존 목표를 이어 갑니다. 새 저장소는 `research_init`으로 만들며 owner 검증기가 필요합니다.
3. 외부 에이전트가 가설·코드를 작성하고 `research_hypothesis`·`research_register`로 조건·성공 기준을 고정합니다.
4. 같은 request_key로 `research_run`을 호출합니다. running/unknown은 원 실행을 조회하고 `research_recover`로 확인하며 새 실행을 자동 시작하지 않습니다.
5. `research_verify` 후 근거와 이유를 `research_decide`에 기록합니다. 기억 검색의 기록 존재와 주장 검증 여부를 구분합니다.
6. 자원 관측을 기록하고 남은 일을 보고하며 목표를 종료·중단하거나 같은 목표로 재개합니다. `research_show`·`research_export`로 원본을 보존합니다.

등록 입력은 `research_help(topic="register")`, 목표·자원 입력은 `topic="goal"`, Laya는 `topic="laya"`를 사용합니다. 확인할 수 없는 외부 사용량은 unknown으로 둡니다.

[로컬 웹](http://127.0.0.1:8765/)의 `research_view`는 overview/analysis/comparison/memory/activity/graph/stability를 펼칩니다. 원문은 `research_inspect_evidence`가 별도 evidence 장면으로 보여 줍니다. 화면 전용 도구는 stdio/HTTP 연구 dispatch에 추가되지 않습니다. 사람의 클릭·입력은 화면 전환이나 연구 진행의 필수 조건이 아닙니다. 장면·focus·선택 목표·비교 범위와 버전별 참조는 [웹 안내](WEB.ko.md)를 따릅니다.

초기 화면·주기 갱신·재연결은 읽기만 합니다. 동기 호출에서 호스트 응답 제한이 발생하면 status/show로 원 실행을 확인하고 recover로 원래 영수증을 수집합니다. 전체 연구 시간·반복 횟수 제한을 만드는 근거가 아닙니다. WebMCP 지원 범위·최종 캡처·변조와 unknown의 실제 표시는 현행 검증 보고서에서 확인합니다. 화면 개선·연결 성공과 연구 성능 개선을 구분합니다.

## 0.7.0 당시 확인 상태

두 가상 환경에 현재 wheel을 설치했다. 기존 Codex 설정을 변경하지 않은 실제 stdio 연결에서 17개 도구를 확인했다([설치 확인](validation/mcp-installation-0.7.0.json)). SDK 없는 설치본의 독립 실행도 HTTP 17개·정적 자산 4개·핵심 의존성 0·원본 상태 읽기만 수행함을 확인했다([웹 설치 확인](validation/product-web-0.7.0/installation.json)).

브라우저의 네이티브 19개, 화면 왕복·비교·기억·원문·대량 페이지와 빈 상태, 변조·누락과 과거 판정 구분, 모바일·reduced-motion의 실제 결과는 [현재 검증 보고서](PRODUCT-VALIDATION.ko.md)에 있다. 이는 기능·화면 확인이며 연구 성능 개선의 새 평가가 아니다. 아래 0.6 이하 기록은 당시 증거다.

## 0.6.0 당시 확인 상태

CLI 0.6.0을 두 가상 환경에 설치했다. 기존 Codex `research_state` 설정은 그대로 유지했고 실제 isolated stdio 설치본에서 도구 17개가 통과했다([MCP 설치 기록](validation/mcp-installation-0.6.0.json)). [웹 설치 기록](validation/web-installation-0.6.0.json)은 SDK 없는 설치본의 실제 HTTP 17개와 화면 파일 3개·모듈 일치, pip와 CLI만 설치된 환경을 확인한다. [소스 manifest](validation/source-manifest-0.6.0.json)에 두 환경의 설치본과 source/wheel 해시를 기록했다.

소스 기능 검사는 SDK 환경 48개 통과(`validation/agent-web-tests-0.6.0.json/log`), SDK 없는 환경 39개 통과·관련 9개 skip(`validation/core-agent-web-tests-0.6.0.json/log`)이다. 서버 연구 도구 17개의 입력·전이와 화면 도구의 서버 dispatch 거부를 유지했다.

설치본 Codex 내장 브라우저에서 실제 네이티브 19개 도구를 확인하고 전체 개발 연구 흐름과 화면 전환·원문 조회를 완료했다([실연 요약](validation/agent-web-0.6.0/episode-summary.json)). 평균 5·분산 9, 독립 검증 pass_rate=1.0·채택, 실제 실행 1회·반복 요청 `started:false`였다. 검증 전 채택·변조 원문 조회를 거부했고 동적 인간 조작 요소는 0개였다. 실제 모션·reduced-motion·모바일 결과도 같은 요약과 화면 기록에 있다. 키 없는 export의 새 복원 후 고정 검증은 상태 변경 없이 통과했다([재현](validation/agent-web-0.6.0/export-reproduction.json)). 이것은 연결·기능 증거이며 연구 성능·기억 효과나 다른 AI 호스트 지원을 입증하지 않는다.

긴 동기 네이티브 호출은 약 30초 뒤 브라우저 자동화 응답 제한에 걸릴 수 있다. 이번 실연에서도 원 worker는 119.625초 동안 유지됐고 새 탭의 조회·`research_recover`·반복 요청으로 같은 실행을 회수했다. 응답이 끊기면 `research_status`·`research_show`로 상태를 확인하고 running/unknown에서 `research_recover`로 원 영수증을 확인한다. CLI/core의 실행 시간 제한이 아니며 변경 요청은 자동 재전송하지 않는다. 초기 raw 응답 배열은 런타임 재설정으로 소실됐고 [부분 원본 transcript](validation/agent-web-0.6.0/native-transcript.json)는 이후 응답 20개, 요약은 영속 이벤트 8개를 구분해 보존한다. 초기 응답을 합성하지 않았다. 외부 모델·토큰 사용량은 unknown이다.

## 0.5.0 당시 이 PC의 설치 확인

2026-10-04 한국 시간, CLI 0.5.0과 MCP SDK 2.3.0이 `.mcp-venv`에 설치되어 있고 `research_state`가 Codex에 등록되어 있다. 기본 명령을 전역 PATH에 추가하지 않았으므로 사람은 `.mcp-venv\Scripts\research-state.exe`를 사용한다. MCP 서버는 AI가 위 command/args로 시작한다. 웹 추가 때 기존 Codex 등록은 변경하지 않았다.

실제 Codex 설정에서 명령을 읽어 소스 폴더 밖에서 `-I`로 설치본을 시작했다. 도구 17개 발견과 도움말·초기화·목표·가설·상태·기억 호출이 통과했다. 당시 `validation/mcp-installation-0.5.0.json`에 설치본과 소스의 일치·wheel 해시·JSON 응답을 보존했고, 최초 0.4.0의 `mcp-installation.json`도 유지했다. 설치 확인용 workspace는 `installation-check-*`이며 과학적 평가 기록이 아니다. 최초 등록 때 기존 Codex 설정을 같은 전역 폴더에 백업했고 서버 하나를 추가한 뒤 다른 설정의 일치를 확인했다. 0.5.0 재확인은 설정 파일을 변경하지 않았다.

재확인은 `.mcp-venv\Scripts\python.exe -I validation\mcp_install_check.py`로 수행한다. 이 명령은 새 설치 확인용 workspace를 만들며 모델이나 실험을 실행하지 않는다. 전체 기능 검사는 `.mcp-venv\Scripts\python.exe -m unittest discover -s tests -v`이다. 당시 48개 통과 결과는 `validation/web-tests-0.5.0.json/log`, 최초 40개 통과 결과는 `validation/mcp-tests.json/log`에 보존했다. 이 확인은 MCP 연결·CLI 기능 검사다. Laya 모델 추론이나 연구 성능 개선을 입증한 결과로 해석하지 않는다.
