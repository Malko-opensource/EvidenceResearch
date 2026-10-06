# Research State CLI 개발·검증 보고서

2026-10-04, 한국 시간. 현재 0.7.0은 사람이 연구를 함께 이해하는 상황판으로 재설계했다. 사전등록된 v0.1.0 외부 에이전트 비교 8개는 모두 완료했으며 연구 성능·기억 효과 개선은 미입증이다. 후속 버전의 개발 실연과 기능 검증을 연구 성능 개선으로 합치지 않는다.

## 0.7.0: 연구의 의미를 보여 주는 상황판

질문·현재 단계·실측 결과·검증/불확실성·지난 시도의 교훈을 기본 화면에 모으고, 분석·비교·기억·사건·증거는 에이전트가 여는 별도 장면으로 분리했다. 길게 쌓이던 상세 열을 제거했다. 읽기 전용 표현 모델이 원본 참조·조회 범위·조건·기준 비교·현재 증거 상태를 제공한다. CLI 핵심 전이·사전등록·검증·중복 방지와 모델 호출 책임은 유지한다.

[짧은 설계와 데이터 대응표](PRODUCT-DESIGN.ko.md), [현재 설치·실제 화면·검증 결과와 한계](PRODUCT-VALIDATION.ko.md), [웹 사용](WEB.ko.md)에 현행 내용을 기록한다. 개발용 성공·검증 실패·미실행 자료와 원본 변조 검사는 연구 성능 비교와 분리한다. 아래 0.6 이하 내용은 당시 구현·실험의 보존 기록이며 현재 화면 계약은 0.7 문서를 따른다.

## 후속 0.6.0: 외부 에이전트가 제어하는 관전실

웹의 인간용 메뉴·작업공간 선택·검색·입력 폼·버튼·클릭·도구 콘솔을 제거했다. 사용자는 외부 에이전트에게 원하는 연구나 조회를 요청하고 웹에서 결과를 함께 관전한다. 에이전트가 workspace·실험·기억 필터·페이지·원문·활동 장면을 제어한다. 웹에는 모델·대화·자율 연구 루프를 추가하지 않았다. 기본 브라우저 스크롤과 텍스트 선택은 유지한다.

기존 연구 도구 17개는 같은 Bridge·CLI dispatch·전이를 사용한다. 브라우저 문서가 화면 전용 `research_view`와 `research_inspect_evidence`를 추가해 네이티브 19개를 등록했다. 두 도구는 상태 전이에 추가되지 않으며 HTTP 연구 명령으로 보내면 거부된다. `research_view`는 overview/memory/activity·실험·검색·페이지를 조회하고 `research_inspect_evidence`는 기존 원문 API의 연결·해시 확인 결과를 읽어 표시한다. 화면의 에이전트 설명은 검증된 증거와 구분한다. 과학적 판단·모델 호출·Laya 추론과 owner 검증기 고정은 계속 외부 책임이다.

초기 선택·주기 조회·재연결은 읽기만 수행한다. 자동 초기화·실험·복구 변경·검증이나 변경 요청 재전송은 없다. 미지원 브라우저도 관전과 CLI 상태 조회만 제공하며 사람용 조작으로 대체하지 않는다. 실제 관계·상태·검증 수치를 SVG로 표시하고 CSS 및 Web Animations API로 호출 진행·결과·장면·수치 변화를 표현한다. 가짜 연구 진행률과 사고 메시지는 만들지 않고 reduced-motion에서는 이동·반복 애니메이션을 끈다. 범위와 입력 계약은 [관전실 설계](AGENT-WEB.ko.md)와 [웹 안내](WEB.ko.md)에 있다.

모델 없는 전체 48개 검사가 SDK 환경에서 통과했다(36.369초, `validation/agent-web-tests-0.6.0.json/log`). SDK 없는 환경에서도 39개 통과·SDK 관련 9개 skip이었다(27.041초, `validation/core-agent-web-tests-0.6.0.json/log`). 정적 HTML의 인간 control 부재와 화면 도구 2개의 HTTP dispatch 거부를 확인하고 기존 전이·CAS·중복·원문·변조·권한·17개 SDK 스키마 계약을 유지했다. 이 검사는 실제 브라우저의 동적 DOM·장면·애니메이션 확인과 구분한다.

두 가상 환경에 0.6.0 wheel을 설치했다. [웹 설치 확인](validation/web-installation-0.6.0.json)은 SDK 없는 `.validation-venv`의 소스 폴더 밖 `-I` 설치본으로 실제 임시 HTTP 서버를 실행해 API 17개·화면 파일 3개·모듈 12개의 소스 일치를 확인한 결과다. 패키지는 pip와 CLI뿐이며 의존성은 0개다. 이 확인은 연구 workspace를 만들지 않았고 임시 서버·폴더는 정리했다. 기존 Codex 등록의 stdio 설치본도 도구 17개를 통과했다([MCP 설치 확인](validation/mcp-installation-0.6.0.json)). 현재 설치 서비스는 포트 8765에서 실행 중이다([실행 기록](validation/web-service/process-0.6.0.json)).

[소스 manifest](validation/source-manifest-0.6.0.json)에 파일 23개와 두 환경의 모든 설치 모듈·화면 자산 일치·wheel 해시를 기록했다. core/runner/worker/transfer/mcp_bridge/web_server/web_tools의 해시는 0.5.0과 같다. 프론트 화면과 관전 계약 변경을 기존 상태 규칙 변경으로 해석하지 않는다.

현재 Codex 외부 에이전트가 설치본 웹의 실제 `document.modelContext` 도구 19개로 `상태 → 기억 → 가설 → 사전등록 → 구현·실행 → 독립 검증 → 채택 → 기억`을 완료했다([실연 요약](validation/agent-web-0.6.0/episode-summary.json)). 고정 개발 입력 [2,4,10]·가중치 [1,2,1]의 평균 5·분산 9를 owner의 독립 검증기가 확인했고 pass_rate=1.0을 만족했다. 등록 `reg_e14e5d2699f04be5a89f71ed23adbd30`, 실행 `run_06e2d954f4ac4636b1da7867197eabd0`의 최종 revision은 8, 실행 기록·실제 launch marker는 각각 1개다. 검증 전 채택은 `INVALID_TRANSITION`으로 거부됐고 반복 실행은 `started:false`였다. 서비스가 모델을 호출하지 않았으며 외부 모델 식별·토큰 사용량은 unknown이다.

개발용 대기 조건이 있는 동기 실행 호출에서 약 30초 뒤 브라우저 자동화 CDP 응답 timeout과 런타임 재설정을 만났다. 원래 worker는 119.625초 동안 유지돼 외부 대기 조건 해제 후 완료됐고 새 탭의 실행 상태 관전·native recover·반복 요청으로 같은 실행을 회수했다. 새 실행은 시작하지 않았다. 이는 CLI/core의 실행 시간 제한이 아니며 오래 걸리는 동기 호출이 브라우저 호스트 제한을 넘을 수 있다는 실제 한계다. 초기 raw 응답 배열은 소실됐고 [원본 transcript](validation/agent-web-0.6.0/native-transcript.json)는 이후 응답 20개만 보존한다. 초기 흐름은 대화의 도구 결과와 영속 이벤트 8개로 뒷받침하며 소실 응답을 합성하거나 전체 원본 보존을 주장하지 않는다.

실제 브라우저에서 인간 조작 요소 0개·관계 노드 6개, 장면·기억·원문·활동 전환, 실행 중 `signal-breath` 모션과 reduced-motion의 실행 애니메이션 0개를 확인했다. 모바일에서는 clientWidth와 scrollWidth가 모두 375였다. [관전](validation/agent-web-0.6.0/desktop.png), [실행 중](validation/agent-web-0.6.0/running.png), [기억](validation/agent-web-0.6.0/memory.png), [원문](validation/agent-web-0.6.0/evidence.png), [활동](validation/agent-web-0.6.0/activity.png), [모바일](validation/agent-web-0.6.0/mobile.png)과 JSON 관찰 기록을 보존했다. 이 브라우저 결과는 앞의 모델 없는 검사와 별개다.

실연에서 발견한 목록 페이지의 개수 표시, revision 변화 없는 파일 변조 반영, 미검증 주장과 실행 unknown의 라벨 혼용을 수정했다. 최종 JavaScript 구문 검사·설치본 일치·실제 브라우저의 해당 동작을 재확인했다. 파일을 변조했을 때 revision 8을 유지한 기억 자동 조회가 무결성 invalid를 표시했고 원문 조회는 `EVIDENCE_TAMPERED`로 거부했다. 현재 주장 미검증과 과거 실행 성공·검증 통과·채택 기록을 구분했고 정확한 원래 바이트 복원 후 정상 원문을 확인했다([자동 조회](validation/agent-web-0.6.0/memory-integrity-poll.json), [현재 주장 표시](validation/agent-web-0.6.0/claim-label-check.json)).

[키 없는 export](validation/agent-web-0.6.0/research-export.zip)를 실제 새 저장소에 복원한 뒤 고정 검증기를 다시 계산했다. [재현 결과](validation/agent-web-0.6.0/export-reproduction.json)는 pass_rate=1.0·연구 상태 변경 없음이었다. 새 경로의 재현 명령은 [핸드오프](HANDOFF.md)에 있다. Codex 내장 브라우저에서의 성공을 다른 브라우저·AI 호스트 지원으로 일반화하지 않는다. 별도 Chrome 접속은 클라이언트 차단을 우회하지 않았다.

이번 변경은 에이전트의 화면 제어와 사용자 관전 기능이다. 새 연구 성능·B/C·기억 ON/OFF·Laya 효과 비교를 수행하지 않았으며 이전 동결 평가의 개선 미입증 결론은 유지한다. 로컬 경로·역할·HTTP 접근 검사도 OS 보안 격리가 아니다.

## 후속 0.5.0: 사용자와 공유하는 WebMCP 상황판

CLI에 웹 채널을 추가했다. 웹 상황판은 목표·가설·등록·실행·검증·결정의 실제 관계, 부족한 증거·자원 known/unknown·최근 이벤트·기억과 보존 증거를 표시한다. 사람의 버튼과 네이티브 WebMCP 도구 17개는 같은 화면 동작 함수를 사용하며 기존 Bridge·CLI dispatch로 영속 상태를 변경한다. 에이전트가 조작한 workspace·실험·진행·결과를 사용자가 함께 보고, CLI/stdio MCP 변경도 화면에 반영된다. [Archify](https://github.com/tt-a1i/archify)의 관계 흐름·선택 상세·증거 연결 아이디어를 참고했으며 원 코드는 복사하거나 의존하지 않았다.

Python 표준 라이브러리 HTTP 서버와 패키지의 HTML·CSS·JavaScript만 사용한다. 웹 실행에는 MCP SDK·모델 SDK·로그인·API 키가 필요 없다. owner 검증기 등록·키·완료 권한은 웹에 노출하지 않고 Laya 모델 실행도 계속 외부에 둔다. 루프백 Host·Origin·교차 사이트·세션·경로 검사와 증거 해시 확인은 접근 계약이며 OS 보안 격리가 아니다. 신뢰한 실험 코드만 실행한다. 상세 사용·HTTP 계약·브라우저 지원은 [웹 안내](WEB.ko.md)에 있다.

SDK 환경에서 전체 48개 검사가 통과했다(37.295초, `validation/web-tests-0.5.0.json/log`). SDK 없는 환경에서는 48개를 발견하고 39개가 통과했으며 SDK 관련 9개만 skip했다(27.814초, `validation/core-web-tests-0.5.0.json/log`). 실제 HTTP의 CLI↔웹 상태 공유, 실행 중 동시 조회·중복 요청, 고정 기준·증거 변조 거부, 연결된 원문 조회와 Host·Origin·세션·경로 제한을 확인했다. 네이티브 WebMCP 실연은 이 모델 없는 검사와 별도로 기록했다.

현재 Codex 외부 에이전트가 내장 브라우저의 실제 `document.modelContext`로 도구 17개를 발견하고 개발용 고정 가중 입력 과제에서 `상태 → 기억 → 가설 → 사전등록 → 구현·실행 → 독립 검증 → 채택 → 기억`을 완료했다. 평균 5·분산 8의 보존 산출물이 owner의 고정 검증기에서 pass_rate=1.0을 만족했다. 검증 전 채택은 `INVALID_TRANSITION`으로 거부됐고 같은 실행 요청의 반복은 `started:false`를 반환했다. 실제 실험 실행은 1회, 최종 revision은 8이다. 등록은 `reg_5c7bb55e651348ea81eed839828fdaeb`, 실행은 `run_33678e033758424c95eede83201b7442`다. 원본 도구 호출은 `validation/web-demo/browser-transcript.json`, 설치본 재연결 조회는 `browser-transcript-installed.json`, 화면은 같은 폴더에 보존했다. 페이지 도구 핸들이 오래된 최종 조회는 현재 도구 목록을 다시 가져와 회수했으며 실험을 재실행하지 않았다. 서비스 내부 모델 호출은 없고 외부 에이전트의 토큰 사용량은 unknown이다.

0.5.0 wheel을 `.mcp-venv`와 `.validation-venv`에 설치했다. SDK 없는 설치 환경의 패키지는 pip와 research-state-cli뿐이다. 소스 폴더 밖의 isolated 설치본에서 HTTP 도구 17개·정적 화면 파일 3개와 공유 상태를 확인했다(`validation/web-installation-0.5.0.json`). 기존 Codex 등록 경로의 stdio 설치본도 도구 17개·상태 저장/조회를 통과했다(`validation/mcp-installation-0.5.0.json`). 기존 등록과 전역 PATH는 변경하지 않았다. 현재 설치본 웹서비스는 `http://127.0.0.1:8765/`에서 실행 중이며 OS 자동 시작·외부 공개는 설정하지 않았다.

[소스 manifest](validation/source-manifest-0.5.0.json)에 소스 23개·wheel 해시·설치 모듈/자산 일치를 기록했다. core/runner/worker/transfer는 0.4.0과 해시가 같다. [동결 비교 검사](validation/frozen-comparison-check-0.5.0.json)에서도 v0.1.0 고정 파일의 변경은 없었다. 과거 소스·설치·검사·평가 기록을 덮어쓰지 않았다.

[실연 요약](validation/web-demo/episode-summary.json)과 상태·등록 조건·원본 기록을 함께 보존했다. [키 없는 export](validation/web-demo/research-export.zip)의 파일 8개를 실제 새 저장소로 복원하고 고정 검증기를 다시 계산했다. [재현 결과](validation/web-demo/export-reproduction.json)는 평균 5·분산 8, pass_rate=1.0·연구 상태 변경 없음이다. 원래 실제 실행 수 1과 revision 8도 유지했다. 아래 명령은 아직 없는 새 복원 경로에서 이 개발 기록을 재확인하며 실험을 다시 실행하거나 기존 결정을 덮어쓰지 않는다.

```powershell
.\.mcp-venv\Scripts\research-state --workspace .\reproduced-web-demo restore --input .\validation\web-demo\research-export.zip
.\.mcp-venv\Scripts\python evaluation\reproduce_record.py --workspace .\reproduced-web-demo --registration reg_5c7bb55e651348ea81eed839828fdaeb
```

네이티브 WebMCP 동작은 Codex 내장 브라우저에서 확인했다. 이 PC의 Chrome 154 직접 접속은 `ERR_BLOCKED_BY_CLIENT`로 실패했으며 플래그·브라우저 제한을 우회하지 않았다. 네이티브 API가 없으면 화면은 미지원 상태를 표시하고 사람의 조작을 계속 제공한다. 특정 브라우저의 성공을 모든 AI 호스트·브라우저 지원으로 일반화하지 않는다.

이 과제는 웹 도구와 공유 상황판의 개발 검증이다. 새로운 B/C·기억 ON/OFF·Laya 효과 비교를 수행하지 않았고 원 Agent Laboratory 전체와 직접 비교하지 않는다. 기존 v0.1.0 동결 평가와 성공·실패·미결 기록은 유지하며 연구 성능 개선 미입증 결론도 유지한다. 후속 효과 평가는 별도 과제·고정 평가기·채택 기준·반복 근거를 실행 전에 새로 등록해야 한다.

## 후속 0.4.0: 이 PC의 AI용 MCP 연결

사용자 요청으로 CLI가 검증된 뒤 얇은 stdio MCP 래퍼를 추가했다. 도구 17개는 같은 CLI dispatch·상태 규칙을 사용하며 선택 사항인 공식 MCP SDK 2.3.0만 별도 환경에 설치한다. 핵심 CLI의 실행 의존성은 0개다. 모델 호출·모델 인증·프롬프트 관리·자체 연구 루프·HTTP 서비스는 없다. 검증기 등록과 owner/internal 권한은 MCP에 노출하지 않으며 Laya 응답은 계속 미검증 제안이다. 경로 검사와 로컬 역할은 OS 보안 격리가 아니다.

모델 없는 전체 40개 검사(핵심 32 + 실제 stdio MCP 8)가 통과했다(53.655초, `validation/mcp-tests.json/log`). 독립 고정 검증까지의 전체 흐름, 두 서버 동시 요청의 실제 실행 1회, 같은 요청·재연결·복원, 오류 코드, 기준 불변·증거 변조 거부와 경로 제한을 확인했다. 최종 점검에서 CLI로 만들거나 복원한 등록의 외부 cwd가 새 MCP 실행의 검사를 우회할 수 있음을 찾아 수정했다. 새 회귀 검사에서 상태 revision·실행 기록·외부 파일이 변하지 않음을 확인했다.

CLI 0.4.0과 SDK를 프로젝트의 `.mcp-venv`에 설치하고 실제 Codex 설정에 `research_state`를 등록했다. 원본 설정을 같은 전역 폴더에 백업했으며 다른 설정은 그대로 유지했다. 등록된 command/args를 읽어 소스 폴더 밖에서 `-I` 설치본으로 연결했고 도구 17개·목표/가설 저장·상태/기억 조회를 확인했다(`validation/mcp-installation.json`). 소스와 설치 파일의 일치·wheel 해시를 보존했으며 핵심 전용 환경에는 SDK 없이 pip와 research-state-cli만 설치되어 있다(`validation/core-installation-0.4.0.json`). 전역 PATH나 다른 AI 호스트의 설정은 추가하지 않았다. 이미 열린 대화에서는 MCP 재연결 또는 새 대화가 필요할 수 있다.

이 결과는 설치·도구 연결·기능 검증이다. 실제 Laya 추론이나 연구 성능·기억 효과의 새 비교를 실행하지 않았다. core/runner/worker/transfer는 v0.3.0과 해시가 같고 고정 v0.1.0 비교 manifest 검사도 통과했다. 기존 비교 결과와 보존 자료는 유지한다. 사용·재확인은 [MCP 안내](MCP.ko.md), 소스 기록은 `validation/source-manifest-0.4.0.json`에 있다.

## 후속 0.3.0: 선택 사항인 Laya 연결

사용자 지시에 따라 Laya를 외부 후보 선택 보조 옵션으로 추가했다. 과거 확장의 안내와 공식 SDK 입력 계약만 참고했으며 기존 구현 코드는 복사하지 않았다. `laya prepare`는 외부 후보·전체 조건·순서·ID 매핑과 참조 기억의 현재 검증·무결성을 내보낸다. `laya resolve`는 외부 SDK 응답을 원 후보 ID에 연결하고 입력 해시·저장소·revision·현재 증거·옵션 순서를 확인한다. 낮은 신뢰도, 명시적 기권과 보고된 옵션 충돌은 기권으로 남긴다. 모델 실행은 외부 에이전트가 담당하며 CLI는 미검증 proposal만 반환한다. 기존 evidence 명령으로 제안을 보존해도 실행·검증·채택은 자동으로 바뀌지 않는다.

모델 없는 새 계약 검사 10개와 전체 32개가 통과했다(21.641초, `validation/laya-tests.json/log`). 새 wheel을 오프라인 설치한 뒤 isolated 실행에서도 후보 입력·합성 SDK 응답 연결을 확인했다(`validation/laya-installation.json`, `validation/laya-smoke/transcript.json`). 설치 패키지는 pip와 research-state-cli뿐이며 추가 실행 의존성은 0개다. 실제 Laya 모델 추론·tokenizer 적합성·선택 품질·연구 효과는 확인하지 않았다. 후속 효과 평가는 Laya 사용/미사용 및 추가 자원을 별도 사전등록해야 한다.

core/runner/worker/transfer는 v0.2.0과 해시가 같다. `validation/source-manifest-0.3.0.json`에 새 소스를 기록했고 기존 `source-manifest.json`·검사·설치·평가 기록을 유지했다. 고정 비교 manifest 검사도 통과했다. 아래 v0.1.0 비교와 v0.2.0 개발 실연은 당시 조건의 기록이며 Laya 추가 결과로 해석하지 않는다. 설치·새 명령은 [현재 안내](README.md), 외부 SDK 사용 경계와 입력 계약은 [Laya 안내](LAYA.ko.md)에 있다.

## 기존 작업 정리

대상 절대 경로는 `C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch`다. 이 경로에서 시작한 이전 연구 루프 두 Python 프로세스와 그 모델 실행 자식 하나를 실행 명령·부모 관계로 확인하고 중단했다. 종료 전에 상태·실행 메타데이터를 보존했다. 종료 후 원래 실행 시간과 부모 관계로 다시 확인했을 때 살아 있는 해당 실행의 자식은 없었다. 다른 프로젝트의 프로세스는 종료하지 않았다.

성공·실패·미결 실험, 로그, 산출물, 원문 자료와 그 원본 소스 연결을 형제 폴더 `EvidenceResearch-preserved-20261004`에 보존했다. 보존 파일은 72,277개, 합계 4,683,120,094바이트다. `manifest.json`, `cleanup-summary.json`, `processes-before.json`, `descendant-audit.json`에서 범위와 기록을 확인할 수 있다. 진행 중이던 옛 실행은 `interrupted_by_user_reset`, 결과는 `unknown`으로 남겼다.

대상의 기존 구현·테스트·어댑터·환경·빌드·버전 복사본·임시 구현·설계·진행 문서를 제거하고 `.git`만 유지한 빈 디렉터리에서 새 설계를 작성했다. 기존 HEAD는 `4f278d7`이며 이력을 다시 쓰지 않았다. 보존 폴더를 새 패키지의 소스 또는 의존성으로 연결하지 않았다. 상위 작업공간, KoMap, 다른 프로젝트, 전역 환경과 자격증명은 변경하지 않았다.

## 새 도구의 책임

외부 에이전트가 모델 호출, 문헌 조사, 가설 선택, 실험 코드와 과학적 판단을 맡는다. CLI는 목표·가설·불변 사전등록·실행·검증·결정·기억을 저장한다. `status`가 돌려주는 것은 허용된 작업과 부족한 증거다. 가설 순위나 가중 종합 점수는 만들지 않는다.

Python 3.11 이상과 표준 라이브러리 SQLite를 사용하며 실행 의존성은 0개다. 언어 선택은 열려 있다. 현재 작업은 상태·파일 I/O 중심이고 수치 계산은 별도 실행기에 맡긴다. 다른 언어의 성능 우위는 측정하지 않았다. 별도 설치 환경의 v0.1.0 짧은 명령 호출 중앙값은 약 64ms였고, 연구 과제의 처리 시간이나 다른 언어와의 비교 수치는 아니다.

핵심 라이브러리와 CLI는 같은 상태 전이 규칙을 사용한다. 실행은 `registered → running → succeeded/failed/unknown`, 검증은 `pending → passed/failed/inconclusive`, 결정은 `pending → adopted/rejected/inconclusive`다. 채택은 실행 성공, 고정 기준의 검증 통과와 현재 증거 무결성을 요구한다. 트랜잭션·고유 제약·workspace revision이 충돌을 감지한다.

사전등록은 가설, 변경점, 비교 대상, 데이터 분할, seed, 소스·데이터 해시, 명령, 실행 조건, 지표, 성공 기준, 산출물과 검증기를 고정한다. 변경은 새 등록이다. 가설 문구만 바뀐 같은 구체 조건은 같은 실험으로 식별한다. 의미가 비슷한 임의의 다른 조건을 자동으로 동치 판정하지는 않는다.

실행기는 고정된 파일을 작업 사본에 복사하고 실제 명령·로그·종료 상태·산출물을 해시로 연결한다. 등록된 별도 검증기가 보존된 소스와 산출물을 다시 계산하고, core가 고정 기준을 적용한다. 제출 수치, 문헌 주장, 추론과 미실행 제안은 자체로 검증 완료를 만들지 않는다. 기억은 성공·실패·미결의 요약·페이지·원본 조회를 제공하며, 기록 존재와 현재 검증 여부를 따로 표시한다.

완료된 실행 요청은 재사용한다. 실행 여부가 불명확한 요청은 `unknown`으로 남기고 원래 worker 영수증으로 확인한다. 확인되지 않은 실행을 자동으로 다시 시작하지 않으며 exactly-once를 보장하지 않는다. export/restore는 일관된 DB와 고정 증거를 보존하고 키를 제외한다. 복원만으로 실행하지 않는다.

키와 역할 분리는 API 수준 경계다. 같은 OS 계정은 파일·키·DB를 직접 수정할 수 있다. 로컬 실행기는 신뢰한 코드용이며 악성 코드 샌드박스나 OS 보안 격리가 아니다. 초기 실행기·검증기는 단일 Python 파일을 지원한다. 다른 구현은 같은 상태·증거 계약을 만족하도록 별도 어댑터로 교체할 수 있다.

## 모델 없는 검증과 설치

v0.1.0 계약 검사 16개와 고정 평가기 검사 5개, 총 21개를 모델 호출 전에 통과했다. 잘못된 전이·오래된 revision·불변 기준·권한 없는 완료 주장 거부, 성공/실패/미결 검색, 소스/산출물/검증기 누락·변조, 실제 제어 프로세스 중단 뒤 원래 worker 회수, 동시 두 CLI 요청의 실제 실행 1회, 완료 요청 재사용, export/restore와 경로 탈출 거부를 확인했다. 원본은 `validation/model-free-tests-0.1.0.json`과 로그에 보존했다.

v0.2.0은 상태 라이브러리·실행기·worker·export 코드를 변경하지 않고 응답과 공개 입력 안내를 보완했다. 기존 21개와 실제 큰 검증 상세를 사용하는 응답 회귀 1개, 총 22개가 통과했다. 상세 조회, 현재 변조 표시, 원본 보존과 중복 방지를 함께 확인했다. 최종 기록은 `validation/model-free-tests.json`과 로그다. 첫 개발 검사에서 표시 코드의 검증 식별자 참조 오류를 발견해 `run_id`로 수정했다. 최초 전체 개발 로그는 덮어써졌으며 실패 이름·오류·원인·수정은 `interface-development-failure.json`에 정직하게 남겼다. 원본 연구 실험 기록은 변경하지 않았다.

깨끗한 가상 환경에 오프라인 wheel을 설치하고 소스 폴더 밖에서 실행했다. 설치 패키지는 pip와 이 패키지뿐이며 모델 SDK·모델 자격증명이 필요 없다. v0.2.0 짧은 명령 호출 중앙값은 약 65ms다. 실행 자식은 로컬 Python worker·사전등록된 Python 실험·고정 검증기다. CLI에 모델 API·모델 인증·Codex 자식 호출·자체 연구 루프가 없다.

## 사전등록된 외부 에이전트 비교

`evaluation/PROTOCOL.ko.md`, `protocol.json`, `frozen_manifest.json`에 실행 전에 과제·기준·순서·반복 수 근거를 고정했다. 개발 과제 D와 기억 시드 M_PRIOR는 최종 평가에서 제외한다. 주 비교는 F1 가중 요약과 F2 불규칙 시간창, 기억 비교는 별도 M1/M2 이벤트 수정 자료다. M1/M2는 같은 과제의 입력 변형이다.

B는 현재 Codex 외부 에이전트와 상속된 모델이 일반 파일로 상태·등록·증거·기억을 관리한다. C는 같은 에이전트·모델에 CLI를 추가한다. 각 episode는 이전 대화를 전달하지 않은 새 외부 에이전트가 수행한다. 각 쌍의 초기 브리프·소스·입력·실행기는 동일한 해시이고, 파일 권한·Python·표준 라이브러리·고정 검증기·성공 기준을 맞췄다. 과제별 순서는 교차했고 직렬 실행했다. 정확한 서비스 모델 식별자와 외부 토큰 사용량은 관측할 수 없어 `unknown`이다.

C ON에는 별도 입력에서 실제 검증 실패한 과거 기록을 제공하고 C OFF에는 제공하지 않았다. 이전 실패는 전체 행 일치로 수정 이벤트를 식별하지 못한 경우이며, 실행·검증·적용 조건·원본 증거를 연결했다. 이 기록이 존재한다는 사실과 실패 원인 해석의 검증 여부를 구분했다.

고정 평가기는 보존된 `summarize(rows)`를 별도 프로세스에서 실행하고 독립 Decimal 기준값·실제 산출물과 대조한다. 성공 기준은 `pass_rate >= 1.0`이다. 각 조건은 완료 후 같은 논리 실행 요청을 한 번 반복해 실제 invocation 수를 확인한다. 실행 오류가 없으면 오류 복구는 `not_observed`이며 개선 효과로 세지 않는다.

주 비교의 수집 결과는 다음과 같다. 시간은 부모의 dispatch부터 결과 수집까지이며 서비스·조정·수집 지연을 포함한다.

| 과제 | 조건 | 고정 검증 | 실제 실험 실행 | 중복 | 수집 시간(초) |
|---|---|---:|---:|---:|---:|
| F1 가중 평균·분산 | B | 8/8 | 1 | 0 | 308 |
| F1 가중 평균·분산 | C OFF | 8/8 | 1 | 0 | 373 |
| F2 시간창 요약 | B | 8/8 | 1 | 0 | 335 |
| F2 시간창 요약 | C OFF | 8/8 | 1 | 0 | 437 |

두 조건 모두 성공했고 중복이 없었다. 관측된 C 시간은 더 길었다. 작은 표본·모델 변동·부모 수집 지연·일반 파일 또는 CLI 연결의 기록 작업이 섞인 값이므로 속도 개선이나 인과적 성능 저하를 추정하지 않는다. B에도 파일 사전등록·영수증·기억을 요구했기 때문에 일반적인 코딩만 수행하는 에이전트와의 시간 비교가 아니다.

F1 C에는 긴 응답을 제한된 도구 출력에서 읽다가 JSON이 잘린 오류가 있었다. 같은 요청을 다시 읽어 회수했으며 실험을 다시 실행하지 않았다. F2 C의 별도 common checker는 snapshot 산출물 대신 원래 episode 위치를 찾다가 미결을 반환했다. 보존된 실제 산출물을 연결한 새 검사 기록은 통과했고 기존 미결 기록도 남겼다. 이어 성공 응답에 없는 `ok` 키를 요구한 기록 wrapper 오류를 수정했다. F2 B에서도 bundle 파일 이름을 결과 파일 번호로 해석한 최종 요약 오류를 회수했다. 모두 기록·연결 오류이며 과학적 실행 실패나 실행 장애 복구 효과로 세지 않는다.

별도 기억 비교 결과는 다음과 같다. ON에서 검색된 이전 기록은 실제 검증 실패·거부 상태이며 원본 무결성은 유효했다. 에이전트는 가설의 검증 완료 여부가 false라는 것과 실패 원인 해석을 구분해 사용했다.

| 입력 변형 | 기억 | 초기 실패 기억 | 고정 검증 | 실제 실험 실행 | 중복 | 수집 시간(초) |
|---|---|---:|---:|---:|---:|---:|
| M1 | OFF | 0 | 7/7 | 1 | 0 | 288 |
| M1 | ON | 1 | 7/7 | 1 | 0 | 277 |
| M2 | ON | 1 | 7/7 | 1 | 0 | 313 |
| M2 | OFF | 0 | 7/7 | 1 | 0 | 234 |

ON 두 에이전트가 실제 CLI 검색으로 실패 기억을 조회했고 가설에 반영했다고 기록했다. 점수·중복 차이는 없고 시간 방향도 일관되지 않았다. 기억의 일반적 효과는 미입증이다. 과제 브리프 자체가 올바른 처리 규칙을 제공해 이전 기억의 추가 정보가 작다는 한계도 있다. M1/M2를 독립 과제의 반복으로 해석하지 않는다.

최종 읽기 전용 집계는 `evaluation/results/summary.json`, 원본은 `evaluation/results/{F1,F2,M1,M2}/{조건}`에 있다. 제공된 요약·transcript의 검증 없는 성공·채택 주장은 8개에서 0건이었다. 이 범위 밖의 모든 모델 추론을 감사했다는 뜻은 아니다. 과학적 실행 장애 복구는 모두 `not_observed`다. 별도 계약 검사에서 중단 복구가 통과한 사실을 이 비교의 복구 효과로 합치지 않는다. CLI 문법·수집·기록 오류와 일부 preflight 응답 수집 누락도 원본 선언과 따로 보존했다. 정확한 모델 식별자·외부 토큰·추가 외부 자원 사용량은 `unknown`이다.

기능 채택과 일반적인 연구 성능 개선은 별도 판정이다. 작은 과제의 상한 효과, 작은 표본, 명령별 안내·기록 작업, 공유 호스트와 부모 수집 지연 때문에 통계적·일반적 개선을 입증하지 않는다. 원 Agent Laboratory 전체와의 직접 비교도 아니다.

## 관측된 원인의 수정

비교는 v0.1.0을 끝까지 유지했다. 이후 v0.2.0에서 run/recover/verify 기본 JSON의 반복된 receipt·evidence·verifier 상세를 제거하고 상태·지표·현재 무결성·최대 10개 보존 artifact 위치와 전체 조회 안내를 제공했다. `show`와 `--full` 및 라이브러리에는 원본 상세가 유지된다. 영수증 수집과 실제 장애 복구를 구분하기 위해 기본 응답에 `receipt_collected`를 사용한다. `help --topic register`는 공개 JSON 형식을 보여주며 snapshot 산출물 위치·문자열 기억 검색도 설명했다.

같은 F1 보존 결과의 읽기 전용 표현을 비교했을 때 정규화한 JSON은 19,368바이트에서 2,960바이트로 약 84.7% 줄었다(`validation/output-comparison.json`). 이는 출력 표현의 크기이며 provider 토큰·연구 성능 개선 수치가 아니다.

사전등록된 v0.2.0 개발용 D 실연에서 새 외부 에이전트가 소스 폴더 밖에서 설치된 패키지를 호출해 전체 흐름을 완료했다. 실제 고정 검증 pass_rate=1.0·채택·실행 1회·중복 0회를 원본 상태에서 확인했다. 기본 응답은 run 2,654바이트, 반복 2,707바이트, verify 2,849바이트였고 추가 형식 질문·CLI/수집 오류는 없었다. `validation/interface-protocol.json`, `interface-agent/episode-summary.json`, `transcript.json`에 보존했다. 개발용 확인이며 이전 성능 비교에 합치지 않는다.

연구 성능 미입증을 양의 효과로 바꾸어 보고하지 않는다. 실제 연결 문제는 수정했고, 상한 효과·실행 장애·장기 연구 기억을 다루는 더 어려운 과제는 새 프로토콜로 개발/최종 과제·평가기·기준·반복 근거를 먼저 정해야 한다. 전체 연구에 반복·시간·연속 실패 한도를 두지 않는다.

## 재현과 한계

설치·사람의 사용·외부 에이전트 연결은 README.md, 중단 복구·후속 작업은 HANDOFF.md에 있다. `python -m unittest discover -s tests -v`는 모델 없는 검사를, `python evaluation/freeze_protocol.py --check`는 고정 파일 해시를, `python evaluation/summarize_results.py`는 보존 결과의 읽기 전용 집계를 수행한다. 예제 실행에는 새 저장소 경로를 사용한다. 보존된 비교 디렉터리를 재실행하거나 덮어쓰지 않는다.

실제 C 연구 저장소 6개의 재현용 export는 `evaluation/exports`에 있고 키를 포함하지 않는다. F1 export를 새 저장소로 복원해 현재 검증된 기억을 확인했다. `manifest.json`이 각 archive 해시를 제공한다. 완결된 DB·조건·고정 검증기·소스·산출물·검증 상세를 보존한다.

프로젝트 폴더에서 새 복원 경로를 사용해 다음처럼 고정 검증을 다시 계산할 수 있다. `reproduce_record.py`는 복원된 증거·검증기 해시를 실행 전후 확인하고 원래 등록 인터프리터로 고정 검증기를 실행한다. 결과를 출력하며 과거 연구 상태·검증·결정을 덮어쓰지 않는다. 실제 재계산은 `validation/export-reproduction.json`에서 pass_rate=1.0을 확인했다.

```powershell
.\.venv\Scripts\research-state --workspace .\reproduced-f1 restore --input .\evaluation\exports\F1-C_OFF.zip
.\.venv\Scripts\python evaluation\reproduce_record.py --workspace .\reproduced-f1 --registration reg_93d884bc142f461f8d1bf24f15378bad
```

기억 검색은 문자열 부분 일치이며 의미 검색은 제공하지 않는다. 런타임 전체·외부 모듈은 자동 동결하지 않는다. cwd·환경이 바뀐 재현 실행은 새 등록이 필요하며, 저장소 초기화 인터프리터 경로가 바뀌면 새 작업 저장소·검증기·등록을 준비하고 기존 복원은 조회용으로 보존한다. 진행 중 실행의 export는 원래 worker 영수증을 운반하지 않으므로 원위치 recover를 완료한 뒤 다시 export한다. Windows에서 검증했고 다른 OS의 동작은 미검증이다.

연구 흐름과 누적 기억은 [Agent Laboratory 원문](https://arxiv.org/abs/2501.04227), [AgentRxiv 원문](https://arxiv.org/abs/2503.18102), [공식 코드](https://github.com/SamuelSchmidgall/AgentLaboratory)를 참고했다. 모델 호출 계층, 에이전트 실행 환경과 기존 체크포인트 구현을 가져오지 않았다.
