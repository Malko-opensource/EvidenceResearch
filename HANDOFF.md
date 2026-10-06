# 이전 핸드오프 — Research State CLI 0.7.0

현행 0.8 설치·목표 생애주기·웹·MCP 안내는 [HANDOFF.ko.md](HANDOFF.ko.md)를 사용합니다. 아래는 0.7 이하의 당시 동작·검증 증거로 보존하며 현재 설치 확인으로 읽지 않습니다.

2026-10-04, 한국 시간. 모델 호출·문헌 조사·가설/코드 생성·과학적 판단은 외부 에이전트가, 상태·사전등록·증거·기억·검증은 CLI가 담당한다.

## 0.7.0 당시 상황판

현재 설치 서비스는 [로컬 상황판](http://127.0.0.1:8765/)이다. `.mcp-venv`와 SDK 없는 `.validation-venv`에 같은 wheel을 설치했다. Codex research_state 등록은 유지한다. 서비스의 실행 정보는 validation/web-service/process-0.7.0.json이다.

외부 에이전트는 research_view의 overview/analysis/comparison/memory/activity로 장면을 바꾸고 research_inspect_evidence로 별도 원문을 연다. comparison의 compare는 최대 6개의 workspace/registration 참조이며 조건이 다른 기록을 같은 순위에 넣지 않는다. sourceReferences와 현재 증거 상태는 WebMCP 결과에서 조회한다. 웹에는 사람 조작·모델 호출·새 연구 판단 루프가 없다.

기획·추상화 대응은 [PRODUCT-DESIGN.ko.md](PRODUCT-DESIGN.ko.md), 재현·실제 캡처·검사와 제한은 [PRODUCT-VALIDATION.ko.md](PRODUCT-VALIDATION.ko.md), 설치·사용·연결은 [WEB.ko.md](WEB.ko.md)를 따른다. 기존 고정 연구 평가의 개선 미입증 결론과 외부 Laya 경계는 유지한다. 다음 연구 성능 평가는 개발 fixture를 제외하고 별도로 사전등록한다. 사용자 이해도는 관전자 대상 평가가 아직 필요하다.

아래 0.6 이하 내용은 당시 기록이다. 현행 화면·설치 계약은 위 0.7 안내를 사용한다.

## 0.6.0 당시 관전실과 제어 계약

웹에서 사람용 메뉴·workspace 선택·검색·폼·버튼·클릭·도구 콘솔을 제거했다. 사람은 외부 에이전트에게 원하는 연구나 조회를 요청하고, 외부 에이전트가 열린 페이지의 WebMCP를 사용한다. 브라우저 기본 스크롤·텍스트 선택은 유지한다. 웹 안의 모델·대화·프롬프트·자율 연구 루프는 없다.

CLI/stdio MCP와 HTTP 연구 API의 도구·상태 계약은 17개 그대로다. 브라우저에만 화면 전용 도구 2개를 더해 19개를 등록했다. `research_view`는 overview/memory/activity·workspace·등록·필터·limit/offset을, `research_inspect_evidence`는 연결된 registration/evidence ID의 보존 원문 장면을 제어한다. 두 도구는 HTTP 연구 dispatch에서 거부하며 화면 조회로 revision·연구 이벤트를 만들지 않는다. 화면 도구의 생략 workspace는 현재 관전 workspace, 연구 도구의 기본 workspace는 `default`다. 설명 문구는 에이전트의 미검증 설명임을 표시한다.

초기 화면과 주기 갱신은 기존 상태를 읽기만 한다. 빈 목록은 에이전트 연결 대기로 남기고 자동 초기화·실행·복구 변경·검증은 하지 않는다. 끊긴 연결은 읽기 조회로 회복하되 연구 변경 요청은 자동 재전송하지 않는다. 관전 중인 장면·페이지는 유지하고 외부 에이전트가 도구로 전환한다. 네이티브 API 미지원은 관전과 CLI 변경 조회만 유지하며 사람용 대체 조작을 추가하지 않는다.

SVG 관계 그래프와 실제 상태·수치·호출 카드에 CSS 및 Web Animations API를 적용했다. reduced-motion에서는 이동·반복 애니메이션을 중지한다. 가짜 사고 메시지·진행률을 생성하지 않는다. [관전실 설계](AGENT-WEB.ko.md), [웹 실행 안내](WEB.ko.md), [stdio 연결](MCP.ko.md)이 현재 계약이다.

0.6.0 소스 검사는 SDK 환경 전체 48개 통과(`validation/agent-web-tests-0.6.0.json/log`), SDK 없는 환경 39개 통과·관련 9개 skip(`validation/core-agent-web-tests-0.6.0.json/log`)이다. HTTP 검사에는 정적 HTML의 인간 조작 요소 부재와 화면 도구 2개의 서버 변경 명령 거부를 추가했고 기존 상태 전이·스키마·동시 실행·증거·경로 검사를 유지했다. 동적 DOM·실제 네이티브 19개·장면과 원문·모션·작은 화면은 별도 실제 브라우저 확인 대상이다.

`.mcp-venv`와 `.validation-venv`에 0.6.0 wheel을 설치했고 [현재 설치 서비스](validation/web-service/process-0.6.0.json)는 포트 8765에서 실행 중이다. [SDK 없는 설치 확인](validation/web-installation-0.6.0.json)은 소스 폴더 밖의 `-I` 설치본에서 HTTP 17개·화면 파일 3개·모듈 12개 일치를 확인했다. 설치 패키지는 pip와 CLI뿐이며 연구 workspace를 만들지 않았다. [stdio 설치 확인](validation/mcp-installation-0.6.0.json)에서도 기존 Codex 등록 도구 17개가 통과했다. [소스 manifest](validation/source-manifest-0.6.0.json)는 파일 23개·wheel과 두 환경의 설치본 일치를 기록하며 core/runner/worker/transfer/mcp_bridge/web_server/web_tools는 0.5.0과 같다.

Codex 내장 브라우저의 설치본 네이티브 19개 도구로 전체 개발 흐름을 완료했다([실연 요약](validation/agent-web-0.6.0/episode-summary.json)). workspace는 `agent-observatory-20261004`, 등록은 `reg_e14e5d2699f04be5a89f71ed23adbd30`, 실행은 `run_06e2d954f4ac4636b1da7867197eabd0`다. 평균 5·분산 9, 검증 pass_rate=1.0·채택, 최종 revision 8, 실제 실행 1회를 확인했다. 검증 전 채택은 `INVALID_TRANSITION`, 변조 원문은 `EVIDENCE_TAMPERED`, 같은 실행 요청은 `started:false`였다. 화면 전환·원문 조회·동적 인간 조작 요소 0개·실제 실행 모션·reduced-motion·모바일 폭은 [관전 화면](validation/agent-web-0.6.0/desktop.png), [기억](validation/agent-web-0.6.0/memory.png), [원문](validation/agent-web-0.6.0/evidence.png), [모바일](validation/agent-web-0.6.0/mobile.png)과 해당 JSON 기록에 있다.

긴 동기 네이티브 호출은 약 30초에 브라우저 자동화 timeout을 만났다. 기존 worker는 119.625초 동안 유지돼 개발용 대기 조건 해제 후 끝났고 새 탭의 조회·`research_recover`·같은 요청 확인으로 회수했다. 이는 CLI/core 실행 시간 제한이 아니다. 응답을 잃으면 `research_status`·`research_show`로 원 실행을 확인하고 running/unknown에서 `research_recover`로 영수증을 수집한다. 실행 여부를 확인하지 않고 새 request_key·새 등록으로 다시 시작하지 않는다. 브라우저 런타임 재설정으로 초기 raw 응답 배열은 소실됐다. [부분 원본 transcript](validation/agent-web-0.6.0/native-transcript.json)의 이후 응답 20개와 영속 이벤트 8개를 구분하며 초기 응답을 합성하지 않았다.

revision 8이 유지된 상태에서 파일 변조를 기억 자동 조회가 감지했고 현재 주장의 미검증 표시를 실행 성공 기록과 구분했다. 원문 검사 거부 후 정확한 원래 바이트를 복원했다. [키 없는 export](validation/agent-web-0.6.0/research-export.zip)를 새 저장소로 복원해 고정 검증을 다시 계산했고 pass_rate=1.0·상태 변경 없음이었다([재현 결과](validation/agent-web-0.6.0/export-reproduction.json)). 아래 명령은 아직 없는 새 경로에서 재현하며 원래 실험을 다시 실행하지 않는다.

```powershell
.\.mcp-venv\Scripts\research-state --workspace .\reproduced-agent-web-0.6 restore --input .\validation\agent-web-0.6.0\research-export.zip
.\.mcp-venv\Scripts\python evaluation\reproduce_record.py --workspace .\reproduced-agent-web-0.6 --registration reg_e14e5d2699f04be5a89f71ed23adbd30
```

이 실연은 기능·관전 확인이다. 다른 AI 호스트 지원·연구 성능·기억 효과의 새 비교가 아니며 기존 미입증 결론과 Laya 외부 실행 경계는 유지한다. 외부 모델·토큰 사용량은 unknown이다.

## 0.5.0 당시 상태와 웹 채널

CLI/stdio MCP와 웹 상황판/WebMCP 두 채널이 `EvidenceResearch\research-workspaces`의 같은 상태를 사용한다. `.mcp-venv`와 `.validation-venv`에 0.5.0 wheel을 설치했다. 기존 Codex `research_state` 등록과 전역 PATH는 변경하지 않았다. 핵심 CLI·웹서비스는 표준 라이브러리만 사용하며 `.validation-venv`에는 pip와 research-state-cli만 있다. stdio MCP에만 선택 사항인 공식 SDK가 필요하다.

현재 설치본 웹서비스는 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)에서 실행 중이다. 사람의 화면 조작과 WebMCP 도구 17개는 같은 Bridge·CLI dispatch를 호출한다. 화면은 선택된 workspace·실험·진행·결과를 공유하고 CLI 변경도 읽어 반영한다. 검증기 등록은 계속 owner의 CLI 작업이며, 모델 호출·자율 연구 루프는 추가하지 않았다. 재시작은 다음 명령을 사용한다. OS 자동 시작과 외부 공개는 설정하지 않았다.

```powershell
.\.mcp-venv\Scripts\python -I -m research_cli.web_server --root 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces' --port 8765 --open
```

[웹 안내](WEB.ko.md)에 설치·화면·네이티브 WebMCP 지원·HTTP 계약을 기록했다. SDK 환경 전체 48개 통과는 `validation/web-tests-0.5.0.json/log`, SDK 없는 환경의 39개 통과·관련 9개 skip은 `validation/core-web-tests-0.5.0.json/log`에 있다. 실제 설치본 HTTP의 도구 17개·화면 파일 3개와 stdio 등록 도구 17개는 각각 `validation/web-installation-0.5.0.json`, `validation/mcp-installation-0.5.0.json`에서 확인한다.

[0.5.0 소스 manifest](validation/source-manifest-0.5.0.json)는 소스 23개와 설치된 모듈·화면 파일의 일치를 기록한다. core/runner/worker/transfer 해시는 0.4.0과 같고 [기존 비교 해시 검사](validation/frozen-comparison-check-0.5.0.json)에서도 v0.1.0 고정 프로토콜은 바뀌지 않았다.

현재 Codex 외부 에이전트는 내장 브라우저의 실제 `document.modelContext` WebMCP로 `상태 → 기억 → 가설 → 사전등록 → 실행 → 독립 검증 → 채택 → 기억`을 수행했다. 개발 과제의 가중 평균 5·분산 8이 고정 검증을 통과했다. 검증 전 채택은 `INVALID_TRANSITION`으로 거부됐고 반복 실행은 `started:false`, 실제 실행은 1회였다. 저장소 `web-demo-20261004`, 등록 `reg_5c7bb55e651348ea81eed839828fdaeb`, 실행 `run_33678e033758424c95eede83201b7442`, 최종 revision 8이다. 원본은 `validation/web-demo/browser-transcript.json`이며 설치본 재연결 조회는 `browser-transcript-installed.json`에 있다. 과거 실연을 다시 실행하거나 상태를 덮어쓰지 않는다.

네이티브 WebMCP는 Codex 내장 브라우저에서 확인했다. Chrome 154 직접 접속은 `ERR_BLOCKED_BY_CLIENT`였으며 브라우저 설정을 우회하지 않았다. 미지원 브라우저는 화면에 미지원 상태를 표시한다. 루프백·Origin·Host·세션·경로 검사는 OS 격리가 아니며 신뢰한 로컬 코드만 실행한다. Laya 추론과 모델 사용량 수집은 계속 외부 에이전트의 책임이고 이번 외부 토큰 사용량은 unknown이다. 이 실연은 새 연구 성능 비교가 아니며 v0.1.0 개선 미입증 결론은 유지한다.

[개발 실연 요약](validation/web-demo/episode-summary.json), `status.json`·`record.json`·`memory.json`·`registration-spec.json`과 화면 3개를 보존했다. [research-export.zip](validation/web-demo/research-export.zip)은 키를 제외한 파일 8개를 포함한다. 실제 새 경로 복원 후 고정 검증 재계산은 [export-reproduction.json](validation/web-demo/export-reproduction.json)에서 pass_rate=1.0·연구 상태 변경 없음으로 확인했다. 아래 명령도 아직 없는 새 복원 경로를 사용하며 원래 실험을 재실행하지 않는다.

```powershell
.\.mcp-venv\Scripts\research-state --workspace .\reproduced-web-demo restore --input .\validation\web-demo\research-export.zip
.\.mcp-venv\Scripts\python evaluation\reproduce_record.py --workspace .\reproduced-web-demo --registration reg_5c7bb55e651348ea81eed839828fdaeb
```

## 0.4.0 이하의 개발 기록

0.4.0에는 선택 사항인 MCP 래퍼가 있다. `.mcp-venv`에 CLI와 공식 MCP SDK 2.3.0을 설치하고 이 PC의 Codex에 `research_state` 서버를 등록했다. 연구 저장소는 `EvidenceResearch\research-workspaces` 아래 상대 경로로 선택한다. 등록된 isolated 설치본으로 실제 도구 17개와 상태 저장·조회를 확인했다(`validation/mcp-installation.json`). [MCP 안내](MCP.ko.md)의 설정을 다른 로컬 AI에도 사용할 수 있으며, 이미 열린 대화는 MCP 재연결 또는 새 대화가 필요할 수 있다. 핵심 CLI는 SDK 없이 설치·실행한다.

0.4.0 전체 40개(핵심 32 + 실제 stdio MCP 8)가 통과했다(`validation/mcp-tests.json/log`). 등록·복원 이후의 cwd 경로 제한, 두 서버의 동시 요청, 중복 실행·재연결·기준/증거 변조 거부와 전체 연구 흐름을 확인했다. 핵심 전용 설치 환경은 pip와 research-state-cli뿐이며 SDK 없이 isolated 도움말이 동작한다(`validation/core-installation-0.4.0.json`). 소스 기록은 `validation/source-manifest-0.4.0.json`이다. 과거 기능·성능 기록은 유지했으며 상태 라이브러리·실행기·검증기·내보내기 규칙은 바뀌지 않았다.

0.3.0에서 추가한 Laya도 계속 선택 사항이다. `help --topic laya`, `laya prepare`, `laya resolve`와 [Laya 안내](LAYA.ko.md)를 사용한다. 외부 에이전트가 모델을 실행하고 원 응답을 제출한다. CLI는 후보 순서·전체 조건·현재 연구 기억·예상 해시를 확인하며 응답을 미검증 proposal로 반환한다. 제안 파일은 기존 evidence 명령으로 보존한다. 실제 Laya 추론·선택 품질·성능 개선은 아직 검사하지 않았으며 이전 비교에 추가한 것으로 해석하지 않는다. 모델 SDK와 저장소 schema 변경은 없다.

0.3.0 전체 32개 검사(기존 22 + Laya 10)가 통과했다. 새 기록은 `validation/laya-tests.json/log`, 오프라인 설치와 합성 응답 smoke는 `validation/laya-installation.json`, `validation/laya-smoke`다. 소스 해시는 `validation/source-manifest-0.3.0.json`이며 기존 `source-manifest.json`은 v0.2.0 기록이다. 과거 검사·설치·비교 기록은 덮어쓰지 않았다. core/runner/worker/transfer 해시는 v0.2.0과 같다.

## 정리와 현재 상태

대상 `C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch`의 기존 구현·테스트·어댑터·설정·모델 로그인/호출 계층·문서·버전 사본을 제거하고 `.git`만 유지한 뒤 새로 작성했다. 과거 구현을 복사하거나 의존하지 않는다. 형제 폴더 `EvidenceResearch-preserved-20261004`에 보존했으며 범위는 `cleanup-summary.json`에 있다. 과거 실행 상태는 `interrupted_by_user_reset`, 결과는 `unknown`, 옛 루프는 재개하지 않는다. 보존 자료·다른 프로젝트·전역 환경·자격증명은 변경하지 않는다.

v0.2.0에서 모델 없는 검사 22개와 깨끗한 환경 설치·소스 폴더 밖 실행을 확인했다(`validation/model-free-tests.json`, `installation.json`). 실행 의존성은 0개이며 모델 자격증명이 필요 없다. 외부 에이전트 v0.1.0 비교 8개는 모두 통과·실행 1회·중복 0회다. B/C 및 기억 ON/OFF 성능 개선은 미입증이다. `REPORT.ko.md`, `evaluation/results/summary.json`과 원본 episode를 확인한다. v0.1.0 wheel·원본 해시·검사/설치 기록은 보존했으며 후속 버전과 비교 결과를 합치지 않는다.

## 구조와 작업 흐름

| 구성 | 책임 |
|---|---|
| `research_cli/core.py` | SQLite·트랜잭션·불변 기록·충돌·공통 상태 전이 |
| `cli.py`, `__main__.py` | JSON 인터페이스·오류·도움말 |
| `mcp_bridge.py`, `mcp_server.py` | 선택 사항인 MCP stdio·도구 스키마·경로 검사·같은 CLI dispatch 연결 |
| `web_server.py`, `web_tools.py` | 루프백 HTTP·WebMCP 도구 계약·같은 Bridge 연결·상태/원문 조회 |
| `research_cli/web` | 에이전트 전용 화면 제어·SVG 상태 흐름·기억·증거 관전·실제 호출 모션 |
| `laya.py` | 선택 사항인 외부 Laya의 후보 입력·응답 연결 |
| `runner.py`, `worker.py` | 로컬 실행·로그/영수증 수집·고정 검증기 연결 |
| `transfer.py` | DB snapshot·증거 export/restore |
| `examples`, `tests`, `evaluation` | 예제·계약 검사·사전등록 비교 |

상태는 `.research/state.sqlite3`, 증거·검증기·영수증은 `.research` 아래에 둔다. owner가 `init`, `validator`로 검증기를 고정하고 `goal`로 목표를 만든다. 외부 에이전트는 `status → memory → hypothesis → register → run → verify → decide → memory/show`를 사용한다. `evidence`는 측정·문헌·추론·제안을 구분한다. 기억은 영속 상태에서 자동 갱신된다.

`--workspace PATH`, `--input FILE/-`를 사용한다. 출력은 `{ok:true,data:...}` 또는 `{ok:false,error:{code,message,details}}`다. 종료 코드 2=입력, 3=전이/불변 기록, 4=충돌, 5=증거, 6=권한, 7=실행 불명확이다. 충돌 시 `status`를 다시 읽는다. `--expect`는 **workspace 전체 revision**이다.

0.2.0은 상태 규칙을 바꾸지 않고 run/recover/verify 기본 응답을 요약한다. `data.record`의 실행·검증·결정, metrics, 현재 무결성과 최대 10개 artifact의 보존 경로를 읽는다. 추가 증거는 `show` 또는 `--full`로 조회한다. 영수증 수집은 `receipt_collected`로 표시하며 장애 복구 성공과 구분한다. 등록 형식은 `help --topic register`로 조회하고 자리표시자를 실제 값으로 바꾼다. snapshot 작업 디렉터리와 원래 cwd를 혼동하지 않는다. memory query는 전체 문자열의 부분 일치다.

설치된 0.2.0을 사용한 실제 외부 에이전트 개발 실연은 `validation/interface-agent`다. 전체 흐름·고정 검증·채택을 완료했고 실제 실행 1회·중복 0회·추가 형식 질문/수집 오류 0회다. 기본 응답은 약 2.7–2.8KB였다. 이 과제 D와 검사는 주 비교·기억 비교에서 제외한다.

## 불변조건과 권한 한계

- 실행은 `registered → running → succeeded/failed/unknown`, 검증은 `pending → passed/failed/inconclusive`, 결정은 `pending → adopted/rejected/inconclusive`다. 채택에는 실행 성공과 검증 통과가 필요하다.
- 등록은 가설·변경점·비교·분할·seed·소스 해시·명령/cwd·지표/기준·산출물·검증기를 고정한다. 변경은 새 등록이다. 요청 키의 다른 내용은 충돌, 가설 문구만 바꾼 같은 조건은 중복이다.
- 완료·검증 기록은 덮어쓰지 않는다. 제출 숫자/성공 문장은 검증이 아니다. 기록 존재·과거 검증·현재 증거 무결성을 따로 확인한다.
- owner.key는 검증기 등록용, internal.key는 실행기/검증 계약용 로컬 capability다. 해시·역할 분리는 OS 보안 격리가 아니며 같은 계정은 파일·DB·키에 접근할 수 있다. 신뢰한 코드만 실행한다.
- 검증기는 보존 산출물을 읽어 JSON metrics를 반환하는 표준 라이브러리 단일 Python 파일이다. 외부 모듈·환경 전체는 자동 동결하지 않는다. 교체 구성 요소는 같은 증거 계약을 지킨다.

## 재현과 unknown 복구

프로젝트 폴더에서 실행한다. 예제·복원에는 새 경로를 쓴다.

```powershell
$PythonExe = 'C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $PythonExe -m venv .venv
.\.venv\Scripts\python -m pip install --no-index --no-deps .\validation\wheels\research_state_cli-0.6.0-py3-none-any.whl
.\.venv\Scripts\research-state --workspace .\handoff-demo help
.\.venv\Scripts\python examples/demo.py .\handoff-demo
.\.venv\Scripts\research-state --workspace .\handoff-demo status
.\.venv\Scripts\research-state --workspace .\handoff-demo memory --limit 10 --offset 0
.\.venv\Scripts\research-state --workspace .\handoff-demo export --output .\handoff-export.zip
.\.venv\Scripts\research-state --workspace .\handoff-restored restore --input .\handoff-export.zip
.\.venv\Scripts\python -m unittest discover -s tests -v
```

다른 기계에서는 `$PythonExe`를 독립적으로 설치한 Python 3.11+ 경로로 바꾼다. 재빌드는 로컬 `setuptools>=61`을 준비하고 `python validation/install_check.py`로 확인한다. 소스 설치의 `--no-build-isolation`은 빌드 의존성 자동 다운로드를 피한다. 핵심 실행에는 setuptools가 필요 없다.

`running/unknown`에 `run`을 반복해도 재실행하지 않는다. `recover --registration ID`가 `.research/runs/RUN_ID`의 원래 요청·영수증·해시를 확인한다. 영수증이 없으면 worker/launch·로그·산출물을 확인하고 원래 worker의 영수증이 생긴 뒤 recover한다. 확인 불가능하면 unknown을 유지한다. 영수증을 직접 만들거나 자동 재실행하지 않는다. exactly-once 보장이 아니다.

export는 키·미수집 worker 요청/영수증·가변 파일을 제외한다. 진행 중 상태의 restore는 running/unknown을 보존하지만 새 위치에서 확정할 수 없다. **원래 저장소와 키를 유지하고 원위치 recover 완료 → 새 export → restore**를 따른다. 복원은 실행을 시작하지 않는다. cwd·환경 변경 후 재현 실행은 새 등록이다. 저장소의 인터프리터 경로도 고정되므로 다른 인터프리터에서는 새 작업 저장소·검증기·등록을 준비하고 기존 복원은 조회용으로 보존한다.

실제 비교 C export 6개는 `evaluation/exports`에 있다. 새 위치에 F1-C_OFF.zip을 restore한 뒤 `python evaluation/reproduce_record.py --workspace 복원경로 --registration reg_93d884bc142f461f8d1bf24f15378bad`로 고정 검증을 재계산한다. 원본 상태를 덮어쓰지 않으며 원래 인터프리터가 필요하다. 이번 재계산 pass_rate=1.0은 `validation/export-reproduction.json`에 있다. 변경된 과제·환경의 실행을 기존 등록으로 재현했다고 주장하지 않는다.

## 다음 개발과 성능 평가

언어 선택은 열려 있다. Python 3.11+/SQLite는 표준 라이브러리만으로 작은 전체 흐름을 설치·검증하기 쉬워 선택했다. 다른 언어보다 빠르다는 미측정 주장은 하지 않는다. 실제 유지보수·배포·성능 필요로 언어를 변경해도 상태 계약을 유지한다. 0.4.0 당시 사용자 요청으로 얇은 MCP 연결을 추가했으며 모델 연결·자율 연구 루프·상주 HTTP 서비스는 없었다. 현재 0.6.0의 관전실은 위의 새 채널 안내를 따른다.

`evaluation/PROTOCOL.ko.md`, `protocol.json`, `frozen_manifest.json`은 이번 feasibility의 고정 기록이다. 후속 평가는 **새 프로토콜/등록**으로 과제·개발/최종 분리·동일 에이전트/모델·초기 정보·권한·환경·자원·평가기·성공 기준·반복 수 근거·실행 순서를 미리 고정한다. B/C와 기억 ON/OFF를 분리하고 지표·중복·복구·근거 없는 주장·시간/토큰을 원본에 연결한다. 사용량 미관측은 unknown, 복구 미관측은 not_observed다. 작은 표본으로 일반적 개선을 채택하거나 원 Agent Laboratory 전체와 직접 비교하지 않는다. 미입증·실패를 보존하고 원인을 수정한 뒤 새 조건으로 검증한다. 전체 연구에 임의의 반복·시간·연속 실패 한도를 추가하지 않는다.
