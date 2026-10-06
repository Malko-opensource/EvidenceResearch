# Research Observatory 플러그인

`plugin/`은 모호한 의뢰를 장기 목표로 구체화하는 외부 에이전트용 스킬과 Research State 도구의 연결 번들이다. CLI의 연구 엔진을 복사하지 않으며 모델 SDK·인증·대화·자체 연구 루프를 추가하지 않는다. 스킬 작성·사용·설치만으로 연구 실행 권한을 만들지 않는다.

[스킬](plugin/skills/research-goal/SKILL.md), [목표 프롬프트 양식](plugin/skills/research-goal/references/goal-template.ko.md), [채널 계약](plugin/skills/research-goal/references/channel-contract.ko.md), [설계 선택](PLUGIN-DESIGN.ko.md)을 제공한다. 초안에서 새 영속 목표 API와 실제 설치 규격으로 보완했다. 실제 도움말·스키마가 우선이다.

## 설치 번들 만들기

Python 3.11 이상에 별도 CLI를 설치한다. 모델 없는 CLI·웹은 핵심 의존성이 없고 stdio MCP는 선택 의존성이 필요하다.

```powershell
# EvidenceResearch 프로젝트 디렉터리에서 로컬 소스를 설치한다.
python -m venv .research-tools
& '.research-tools\Scripts\python.exe' -m pip install '.[mcp]'
```

공개 패키지 저장소에 이 프로젝트가 게시됐다는 뜻은 아니다. 로컬 wheel 설치 시 패키지 파일 경로와 `[mcp]` 선택 의존성을 설치 명령에 지정한다.

이미 존재하는 연구 root와 실행할 Python을 명시해 새 출력 디렉터리에 bundle을 만든다. root는 여러 상대 workspace를 담는 디렉터리다. 기존 출력은 덮어쓰지 않고 연구 root 안에는 배포 파일을 만들지 않는다.

```powershell
$researchPython = (Resolve-Path -LiteralPath '.mcp-venv\Scripts\python.exe').Path
$researchRoot = (Resolve-Path -LiteralPath 'research-workspaces').Path
& $researchPython 'plugin\scripts\configure.py' `
  --python $researchPython --root $researchRoot `
  --output 'dist\research-observatory-local' --port 8765
```

출력은 repo marketplace `.agents/plugins/marketplace.json`, 설치 가능한 `research-observatory/` 폴더, 한 개 plugin 폴더를 담은 ZIP과 `connection.json`이다. `connection.json`과 MCP 설정에는 이 컴퓨터의 절대 경로가 있으므로 다른 컴퓨터에서는 그 환경의 경로로 다시 생성한다. 원본 연구 데이터·owner key·환경·자격증명은 ZIP에 들어가지 않는다.

source의 `.mcp.json`은 빈 설정이다. 원본 skill만 발견하는 것과 runtime 연결이 완성된 것은 구분한다. `configure.py`가 실제 설치 환경을 `-I` 모드로 조회한 후 root와 Python을 연결한다. portable MCP는 bare executable 이름을 요구하므로 MCP 자식 프로세스의 PATH에 명시한 Python 디렉터리를 추가한다. 전역 PATH는 변경하지 않는다.

## Codex 연결

실제 Codex CLI 0.160.0에서 local marketplace 설치를 검증했다. [OpenAI 공식 패키징 문서](https://developers.openai.com/plugins/build/plugins)의 portable root manifest와 Codex 호환 overlay를 제공한다. 개인 프로필에 설치하려면 아래 명령을 사용한다. 이 명령은 선택한 Codex 프로필의 plugin cache·config를 변경한다. 설치를 원하는 환경에서 실행하며 기존 연결과 root를 확인한다.

```powershell
codex plugin marketplace add '.\dist\research-observatory-local'
codex plugin add research-observatory@evidence-research-local
codex plugin list --marketplace evidence-research-local --json
```

plugin skill은 호스트에서 `research-observatory:research-goal`로 발견된다. 새 대화에서 `$research-observatory:research-goal`을 지정하거나 스킬을 선택한다. installer는 웹 서버·연구·모델을 자동으로 시작하지 않는다. 이미 같은 서버가 실행 중이면 그 URL과 root를 사용한다. 별도 시작은 `connection.json`의 `web_command`를 실행하는 명시적 작업이다.

브라우저가 네이티브 WebMCP를 제공하면 열린 연구 웹 문서에서 도구를 발견한다. stdio MCP의 연구 도구와 웹의 연구 도구는 같은 root/workspace·목표 ID·버전·revision을 사용한다. 웹 전용 장면 도구는 stdio MCP에 없다. CLI는 해당 workspace의 절대 경로를 사용한다. 채널을 바꿀 때 새로운 목표나 실행을 만들지 않는다.

## 전역 프로필을 변경하지 않는 검증

```powershell
& $researchPython 'plugin\scripts\verify_host.py' `
  --marketplace 'dist\research-observatory-local' `
  --output 'validation\plugin-host-new'
```

이 스크립트는 새 출력 안의 독립 Codex home에서 실제 `plugin marketplace add`, `plugin add/list`, app-server `skills/list`와 `mcpServerStatus/list`를 실행한다. 기본 프로필의 설정·자격증명은 복사하지 않는다. 모델 turn을 요청하지 않으며 종료 시 자신이 띄운 app-server를 정리한다. 실제 응답과 오류를 보존한다. remote curated catalog 동기화가 네트워크 제한으로 실패하더라도 로컬 설치·스킬·MCP 발견 결과를 각각 검사한다.

검증 초기에는 portable MCP의 absolute executable command 제한을 발견했다. 이를 MCP 프로세스 한정 PATH와 bare executable로 수정한 뒤 실제 연결에 성공했다. 과거 실패 로그를 보존해 성공 기록으로 덮어쓰지 않았다.

초기 `host-check-v2`는 스킬 발견에 성공했지만 연결된 MCP가 0.7.0/17개 도구였던 기록이다. 최종 증거는 [host-check-release](validation/plugin-0.8.0/host-check-release/host-discovery.json)이며 plugin 0.8.0·활성 스킬·MCP 0.8.0/23개 도구를 확인했다. 실제 배포 폴더는 `dist/research-observatory-0.8.0-release`, [ZIP](dist/research-observatory-0.8.0-release/research-observatory.zip)과 [연결 명령](dist/research-observatory-0.8.0-release/research-observatory/connection.json)을 제공한다. 생성된 CLI 명령도 소스 밖에서 실제 실행했다. 이 독립 검증은 사용자의 기본 Codex 프로필에 plugin이 설치됐다는 뜻이 아니다. 최종 앱·스킬 사용·목표 채널 일치는 [통합 검증](VALIDATION-0.8.ko.md)의 원본 응답으로 확인한다.

## 한계와 재개

설치·스킬 형식·실제 도구 사용은 연구 성능이나 사용자 이해도의 개선을 입증하지 않는다. 외부 모델 사용량은 확인되지 않으면 unknown이다. 목표 생성·버전 변경에는 안정된 request key와 최신 revision을 사용한다. 등록 조건은 불변이며 goal close는 실험 검증을 대신하지 않는다. unknown 실행은 원 실행을 확인·recover한 후 이어간다.

다른 호스트의 발견·설치 동작이나 원격 공개 plugin directory 승인은 이 로컬 검증 범위 밖이다. 웹은 네이티브 WebMCP 지원 브라우저를 필요로 하며 HTTP bridge가 공개 MCP endpoint라는 뜻은 아니다. 기존 서버나 연구 실행을 임의로 종료하지 않는다.
