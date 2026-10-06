# Research State CLI

모델과 독립된 연구 상태·사전등록·증거·기억 관리 도구입니다. 현재 구현은 **0.8.0**이며 외부 에이전트가 연구를 수행하고 웹이 연구 의뢰인에게 확인된 답과 적용 범위, 다음 확인을 보고합니다. CLI·stdio MCP·WebMCP가 같은 root/workspace의 목표·실험을 사용합니다. Python 3.11 이상이며 핵심 CLI·웹의 실행 의존성은 0개입니다. stdio MCP만 선택 의존성 `[mcp]`를 사용합니다. 모델 호출과 선택적인 Laya 추론은 외부 에이전트의 책임입니다.

이 PC의 프로젝트 환경은 SDK 없는 `.validation-venv`와 선택 MCP 의존성을 설치한 `.mcp-venv`이며 Codex 서버 이름은 `research_state`입니다. 이미 열린 stdio 프로세스는 패키지 갱신 뒤에도 이전 도구 목록을 유지할 수 있으므로 재연결이 필요합니다. 공통 연구 도구는 23개, 브라우저 화면 도구를 포함하면 WebMCP 25개입니다. 현재 기본 화면은 [의뢰인 설계](CLIENT-VIEW-DESIGN.ko.md)와 [의뢰인 검증](CLIENT-VIEW-VALIDATION.ko.md)을 따릅니다. 관계 중심 화면의 [이전 후속 설계](UI-FOLLOWUP-DESIGN.ko.md)·[이전 검증](UI-FOLLOWUP-VALIDATION.ko.md)은 당시 기록으로 보존합니다. [0.8 초기 검증](VALIDATION-0.8.ko.md)과 [초기 릴리스 보고](RELEASE-0.8.ko.md)는 당시 원본 증거로 보존합니다.

## 0.8 사용 시작

프로젝트 디렉터리에서 설치합니다. 일반 환경에서는 설치한 Python 3.11 이상을 사용합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-deps .
.\.venv\Scripts\research-state.exe --workspace '.\my-research' help --topic goal
```

후속 UI를 포함한 오프라인 wheel은 `.\.venv\Scripts\python.exe -m pip install --no-index --no-deps dist\client-spectator-20261004\research_state_cli-0.8.0-py3-none-any.whl`로 설치합니다. 버전은 0.8.0을 유지하므로 `validation/wheels`의 초기 wheel 및 이전 릴리스 번들과 경로·해시를 구분합니다. stdio MCP를 사용할 별도 환경에는 `pip install '.[mcp]'`로 선택 의존성을 설치합니다. 전역 PATH나 모델 인증은 필요하지 않습니다.

[로컬 보고 화면](http://127.0.0.1:8765/)은 의뢰 질문, 선택한 시도의 답과 실제 값·등록 기준, 확인 범위와 다음 확인을 먼저 보여 줍니다. 관계도·실행 상태 묶음·seed·도구 수·기록 번호는 기본 화면에 쌓지 않습니다. 에이전트가 초점이나 설명을 지정하면 한 설명 장면으로 교체하며, 분석·비교·기억·시간/비용·관계·반복·원문은 별도 장면으로 펼칩니다. 사람의 클릭이나 입력은 필수 조건이 아닙니다. 단위 미등록·현재 근거 누락·변조·목표 범위 차이는 해당 결과 옆에 유지합니다.

```powershell
.\.mcp-venv\Scripts\python.exe -I -m research_cli.web_server --root 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces' --port 8765 --open
```

이미 같은 서버가 실행 중이면 기존 URL을 사용합니다. 웹을 시작해도 실험·모델·복구·검증을 자동 실행하지 않습니다. 웹은 MCP SDK 없이도 실행하며 네이티브 WebMCP를 지원하지 않는 브라우저에서는 관전만 가능합니다.

목표는 `goal`로 저장하고 `goal_show`로 버전·전체 상태를 읽습니다. `goal_amend`는 의미·범위·계획 변경을 새 버전으로 남기며 등록 기준을 덮어쓰지 않습니다. `goal_close`는 이유·확보한 결과·미완료 범위를 외부 보고로 기록합니다. `completed`는 running/unknown 원 실행이 남으면 거부됩니다. 중단·취소 보고가 worker를 종료하지는 않습니다. `goal_resume`는 같은 목표를 재개하며 실행을 시작하지 않습니다. `resource`/`resource_show`는 통화별 외부 관측 소계를 보존하고 미확인 총사용량을 추정하지 않습니다.

[연구 의뢰 설계 스킬·설치 번들](PLUGIN.ko.md)은 모호한 요청을 필요한 인터뷰와 장기 목표 프롬프트로 구체화합니다. 스킬 호출이나 목표 프롬프트 생성 자체가 실행 허가는 아닙니다. CLI·MCP·웹을 바꿀 때 같은 목표 ID·버전·request key와 workspace를 유지합니다. 플러그인의 독립 검증 프로필과 사용자의 개인 프로필 설치는 구분합니다.

현재 화면 구조와 원본 대응은 [의뢰인 설계](CLIENT-VIEW-DESIGN.ko.md), 사용은 [웹 안내](WEB.ko.md), [MCP 재연결](MCP.ko.md), [목표 저장 계약](CORE-GOALS.ko.md), [핸드오프](HANDOFF.ko.md)를 참고합니다. 연구 질문에 답한 것, 기능 검사, 화면 개선, 연구 성능 개선은 별개이며 개선을 주장하려면 별도 사전등록 평가가 필요합니다.

## 0.7.0 당시 상황판과 검증 기록

이 절은 0.7.0 당시 동작·설치 기록입니다. 현행 설치와 도구 수는 위 0.8 안내를 사용합니다. 원본 검증·캡처는 [PRODUCT-VALIDATION.ko.md](PRODUCT-VALIDATION.ko.md)에 그대로 보존합니다.

[로컬 상황판](http://127.0.0.1:8765/)에서 연구 질문·현재 상태·주요 측정값·검증 여부·병목을 함께 봅니다. 상세 정보를 옆 열에 계속 쌓는 구조를 제거하고, 에이전트가 분석·비교·기억·사건·증거 장면을 전체 폭으로 펼칩니다. 사용자는 보고 싶은 내용을 외부 에이전트에게 요청하며 화면 전환에 사람의 클릭·입력은 필요하지 않습니다.

원본 영속 상태와 화면 사이에 순수한 읽기 전용 표현 모델을 둡니다. 실제 측정값과 고정 기준, 같은 조건의 시도 간 차이, 조회 범위의 상태 분포와 실제 사건 시간축을 표시하고 원본 참조를 WebMCP 결과에 반환합니다. 단위 미등록·미측정·불명확한 사용량은 추정하지 않습니다. 실행 성공·검증 통과·채택, 현재 원본 보존·과학적 검증을 구분합니다. 원문·로그·경로·해시·내부 ID는 별도 증거 장면에서만 공개합니다.

CLI/stdio MCP와 HTTP의 기존 연구 도구는 17개입니다. 브라우저는 `research_view`와 `research_inspect_evidence`를 더해 네이티브 WebMCP 19개를 제공합니다. `research_view`의 장면은 overview/analysis/comparison/memory/activity이며 comparison은 최대 6개의 명시적 원본을 평가 조건별로 묶습니다. 화면 도구는 연구 상태를 바꾸거나 모델을 호출하지 않습니다. 움직임은 실제 변화에만 적용하고 reduced-motion을 지원합니다.

[짧은 기획·데이터 대응표](PRODUCT-DESIGN.ko.md), [실제 화면·검증 결과](PRODUCT-VALIDATION.ko.md), [실행·에이전트 연결 안내](WEB.ko.md)를 참고하세요. 기능 검사와 개발 계산 실연은 연구 성능 개선의 증거가 아니며 기존 미입증 결론을 유지합니다. 이전 0.6 실연과 제한은 REPORT.ko.md와 validation/agent-web-0.6.0에 보존합니다.

```powershell
.\.mcp-venv\Scripts\python -I -m research_cli.web_server --root 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces' --port 8765 --open
```

## 0.5.0 당시 웹 상황판 기록

0.5.0 당시 [연구 상황판](http://127.0.0.1:8765/)을 실행하고 workspace를 선택해 목표·가설·등록·실행·검증·결정, 남은 증거와 최근 활동을 함께 조회했습니다. CLI나 stdio MCP로 바꾼 상태도 같은 화면에 반영됐습니다. 당시 사람의 버튼과 WebMCP 도구 17개는 같은 화면 동작과 CLI 상태 규칙을 사용했습니다. 0.6.0부터 이 사람용 조작을 제거했습니다.

당시 웹서비스 실행 명령도 동일했습니다. 일반 설치 환경에서는 `.mcp-venv` 대신 해당 가상 환경을 사용하며 웹 실행에 MCP SDK나 모델 자격증명은 필요하지 않습니다.

```powershell
.\.mcp-venv\Scripts\python -I -m research_cli.web_server --root 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces' --port 8765 --open
```

0.5.0은 Codex 내장 브라우저에서 실제 `document.modelContext` WebMCP 도구로 개발 과제의 전체 흐름을 완료했습니다. 당시 네이티브 API가 없는 브라우저는 미지원 표시와 사람의 화면 조작을 제공했습니다. 이 PC의 Chrome 154 직접 접속은 `ERR_BLOCKED_BY_CLIENT`로 막혀 설정을 우회하지 않았습니다. 공개 인터넷 서비스와 OS 자동 시작은 설정하지 않았습니다.

0.5.0은 SDK 환경에서 전체 48개 검사를 통과했습니다(`validation/web-tests-0.5.0.json/log`). SDK가 없는 환경에서는 39개가 통과하고 관련 9개만 건너뛰었습니다(`validation/core-web-tests-0.5.0.json/log`). 설치본의 HTTP·정적 화면과 stdio 도구 17개도 확인했습니다(`validation/web-installation-0.5.0.json`, `mcp-installation-0.5.0.json`). 이 결과와 `validation/web-demo`의 실연은 개발·연결 기능 확인이며 연구 성능이나 기억 효과 개선의 새 비교가 아닙니다. 이전 v0.1.0 비교의 미입증 결론은 유지합니다.

[소스·설치본 해시 기록](validation/source-manifest-0.5.0.json)에서 핵심 상태·실행·복원 코드가 0.4.0과 같음을, [개발 실연 요약](validation/web-demo/episode-summary.json)에서 실제 실행 1회와 상태를 확인할 수 있습니다. 키를 제외한 [실연 export](validation/web-demo/research-export.zip)를 새 경로로 복원해 고정 검증기를 다시 계산했고 pass_rate=1.0, 연구 상태 변경 없음이었습니다([재현 결과](validation/web-demo/export-reproduction.json)). 새 복원·재현 명령은 [핸드오프](HANDOFF.md)에 있습니다.

설치:

```powershell
$PythonExe = 'C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $PythonExe -m venv .venv
.\.venv\Scripts\python -m pip install --no-deps .
.\.venv\Scripts\research-state --workspace .\my-research help
```

`$PythonExe`는 이 기계에서 검증한 실행 경로입니다. 다른 환경에서는 독립적으로 설치한 Python 3.11 이상 경로로 바꾸면 됩니다. `python` 명령이 있는 환경에서는 설치 없이 현재 소스에서 `python -m research_cli --workspace PATH ...`도 가능합니다. 패키지·실행기·검증기에 모델 SDK, 모델 로그인 또는 API 키가 필요하지 않습니다.

wheel을 사용한 오프라인 설치:

```powershell
.\.venv\Scripts\python -m pip install --no-index --no-deps dist/client-spectator-20261004/research_state_cli-0.8.0-py3-none-any.whl
```

일반 소스 설치는 build isolation에서 setuptools를 내려받을 수 있습니다. 이미 로컬에 setuptools>=61이 있는 빌드 환경이라면 `python -m pip wheel --no-deps --no-build-isolation --wheel-dir validation/wheels .`로 오프라인 wheel을 만들 수 있습니다.

작은 전체 흐름:

```powershell
.\.venv\Scripts\python examples/demo.py .\demo-research
.\.venv\Scripts\research-state --workspace .\demo-research status
.\.venv\Scripts\research-state --workspace .\demo-research memory --limit 10
.\.venv\Scripts\research-state --workspace .\demo-research export --output .\demo-export.zip
.\.venv\Scripts\research-state --workspace .\demo-restored restore --input .\demo-export.zip
```

저장소 초기화 시 발급되는 owner.key는 검증기 등록용 로컬 capability입니다. 에이전트에 필요한 명령은 status, memory, hypothesis, register, run, recover, verify, decide, evidence, show입니다. 검증기는 owner가 먼저 고정합니다. 검증기의 명령은 `[python실행경로, 검증기.py, "{bundle}"]`이며 JSON `{metrics:{...},details:{...}}`를 stdout으로 반환합니다. 초기 검증기는 표준 라이브러리만 사용하는 단일 파일이어야 합니다. 평가 데이터는 그 파일에 포함하거나 고정된 bundle 증거로 전달합니다. 별도 외부 모듈 의존성은 자동 동결하지 않습니다. 별도 검증기는 보존된 실제 산출물에서 수치를 계산해야 합니다.

사전등록 JSON 예제는 `help --topic register`로 조회합니다. examples/demo.py의 spec과 [설계](DESIGN.ko.md)도 참고할 수 있습니다. 예제의 ID·검증기·경로·지표·0으로 채운 해시는 실제 값으로 바꿉니다. `source_version.files`는 상대경로→SHA-256 사전이고 `artifacts`는 `[{name:"result",path:"result.json"}]` 배열입니다. 명령 스크립트·데이터·실험 소스를 고정하고 기준을 바꾸면 새 등록이 필요합니다. revision과 `--expect`는 workspace 전체의 오래된 상태 변경을 거부합니다. 입력 JSON은 `--input FILE` 또는 `--input -`로 받습니다. 결과는 `{ok:true,data:...}` 또는 `{ok:false,error:{code,message,details}}`입니다. `--help`는 사람이 읽는 도움말입니다.

0.2.0의 run/recover/verify 기본 응답은 `data.record.run.state`, `verification.state/metrics`, `decision.state`, 현재 무결성과 보존 artifact 경로를 제공합니다. artifact는 최대 10개를 표시하고 남은 개수와 `show` 조회 안내를 반환합니다. 원본 영수증·검증 상세는 `show --registration ID` 또는 각 명령의 `--full`로 조회합니다. 라이브러리 결과와 `--full`은 0.1.0의 상세 형식을 유지합니다. `receipt_collected`는 영수증 수집 여부이며 장애 복구 성공을 뜻하지 않습니다.

실험은 등록 cwd의 파일을 snapshot 작업 디렉터리로 복사해 실행합니다. 원래 cwd에 결과가 생성된다고 가정하지 않습니다. 기본 응답의 `run.execution_directory`와 `artifacts[].path`에서 실행 위치와 보존된 파일을 찾습니다. memory의 query는 입력 전체 문자열의 부분 일치 검색이며 단어·의미 검색이 아닙니다.

외부 에이전트 연결 순서:

1. status로 허용된 작업과 부족한 증거를 확인하고 memory로 성공·실패·미결 기록을 검색합니다.
2. 외부 에이전트가 가설을 제안하고 실험 코드 초안의 예상 해시를 준비합니다.
3. register로 가설·조건·분할·seed·소스·지표·기준·검증기를 고정합니다.
4. 초안과 동일한 구현을 실행 위치에 배치하고 run을 호출합니다.
5. verify로 고정 평가기를 실행하고 decide로 외부 판단과 이유를 남깁니다.
6. memory/show로 검증 상태와 원본 증거를 확인합니다. 기억은 영속 상태에서 자동 갱신됩니다.

같은 실행 요청과 같은 실험 조건은 재실행되지 않습니다. running/unknown이면 recover를 사용합니다. 영수증이 없으면 실행 여부를 확정할 수 없으므로 자동 재시작하지 않습니다. 원래 worker의 launch/process/log와 산출물을 확인하고 영수증이 생기면 recover를 다시 호출합니다. 재현 실험은 조건과 source_version을 명시한 별도의 새 등록으로 남깁니다. exactly-once 실행을 보장하지 않습니다.

실행 성공, 검증 통과, 가설 채택은 별개의 상태입니다. 사용자가 제출한 숫자나 문헌·추론·제안은 검증 완료를 만들지 않습니다. 검색에 기록이 있다고 해서 그 주장이 검증됐다는 뜻도 아닙니다.

로컬 실행기는 신뢰한 코드용이며 OS 샌드박스가 아닙니다. 같은 계정은 키·DB·파일에 직접 접근할 수 있습니다. 해시와 역할 분리를 악성 에이전트에 대한 보안 격리라고 해석하면 안 됩니다. export는 키를 포함하지 않으며 새 저장소에 restore해도 실행을 시작하지 않습니다. 진행 중 실행은 원래 위치에서 recover를 끝낸 후 새 export를 만듭니다. 원래 cwd·환경이 바뀌면 새 등록이 필요합니다. 인터프리터 경로는 저장소 초기화 때 고정되므로 다른 인터프리터에서는 새 작업 저장소·검증기·등록을 준비하고 복원 기록은 조회용으로 보존합니다.

0.4.0 당시 모델 없는 검사: `python -m unittest discover -s tests -v`입니다. MCP 환경에서 핵심 32개와 실제 stdio MCP 검사 8개, 총 40개가 통과했습니다(`validation/mcp-tests.json/log`). SDK가 없는 핵심 환경에서는 MCP 검사만 건너뜁니다. [보고서](REPORT.ko.md)에 사전등록 비교 8개와 한계를, [핸드오프](HANDOFF.md)에 후속 작업을 기록했습니다. 비교는 0.1.0을 고정해 진행했고 해당 wheel과 원본 기록을 보존했습니다. 모든 조건이 통과해 연구 성능·기억 효과 개선은 미입증입니다. 후속 표현 개선·Laya·MCP 기능 검증은 그 비교에 합치지 않습니다. B/C 비교는 원 Agent Laboratory 전체와의 직접 비교가 아닙니다.

실제 v0.2.0 에이전트 사용 기록은 validation/interface-agent에 있습니다. 비교의 C export 6개는 evaluation/exports에 있으며, 복원 후 `evaluation/reproduce_record.py`로 고정 검증을 상태 변경 없이 다시 계산합니다. [보고서의 재현 명령](REPORT.ko.md)을 사용하고 이미 보존된 비교 저장소를 덮어쓰지 않습니다.

## Laya 선택 사항

`laya prepare`는 외부 에이전트가 작성한 후보·조건과 기존 연구 기억을 공식 SDK 입력으로 내보냅니다. 외부에서 실행한 응답은 `laya resolve`로 원 후보 ID에 연결합니다. CLI가 모델을 호출하지 않으며 추천은 미검증 제안입니다. [Laya 사용 안내](LAYA.ko.md)에 입력 예제, 외부 SDK 호출과 제안 증거 저장 방법이 있습니다.

```powershell
research-state --workspace .\my-research help --topic laya
research-state --workspace .\my-research laya prepare --input candidates.json --output laya-bundle.json
research-state --workspace .\my-research laya resolve --input laya-bundle.json --response laya-response.json --expected-sha256 SAVED_DIGEST --output laya-proposal.json
```

예상 해시는 prepare 결과에서 따로 보존합니다. 목표·기억의 revision이나 참조 증거가 바뀌면 새 prepare가 필요합니다. 라벨 순서와 전체 후보를 보존하며 기존 출력 파일은 덮어쓰지 않습니다. 실제 Laya 추론·토큰 경계·연구 효과는 별도 평가 대상입니다.
