# 연구 의뢰 플러그인 설계

2026-10-04. 구현 전에 정한 책임과 검증 범위다.

의뢰 설계 스킬은 사용자의 모호한 요청을 장기 목표 프롬프트로 바꾸는 외부 에이전트 지침이다. 연구 질문의 완료와 성능 개선의 입증을 구분하며, 전문적인 가설·실험 설계는 에이전트가 조사한다. 기존 답변과 권한을 재사용하고, 실제 실행에 필요한 정보만 사용자에게 확인한다. 프롬프트 생성이나 플러그인 설치를 연구 실행 승인으로 간주하지 않는다.

배포 단위는 `plugin/`의 스킬·목표 양식·채널 계약과 Codex manifest다. CLI·stdio MCP·WebMCP는 같은 절대 root와 상대 workspace를 공유한다. 플러그인에 연구 엔진이나 모델 연결을 복사하지 않는다. 별도 설치된 `research-state-cli[mcp]`의 Python을 명시해 연결한다.

고정된 PC 경로를 배포용 스킬에 넣는 방식과 설치 때 연결 정보를 생성하는 방식을 비교했다. 후자를 선택한다. 설정 스크립트가 사용자가 지정한 Python·연구 root를 확인하고 새 배포 디렉터리에 host manifest, MCP 설정, repo marketplace와 연결 정보를 생성한다. 이미 있는 출력은 덮어쓰지 않고 전역 설정·자격증명·기존 서버를 변경하지 않는다. 웹 시작은 명시적 명령이며 설치 hook이나 자동 연구 실행은 두지 않는다.

Codex CLI 0.160.0의 실제 `plugin add/list`, `plugin marketplace add/list` 도움말과 로컬 bundled plugin manifest를 읽었다. [OpenAI 공식 패키징 문서](https://developers.openai.com/plugins/build/plugins)는 root `plugin.json`과 호환 `.codex-plugin/plugin.json`, `skills/`, MCP 설정과 repo marketplace를 설명한다. 실제 호스트에서 독립 `CODEX_HOME`을 사용해 로컬 marketplace 설치·스킬 발견을 검증한다. 이 검증은 사용자의 기본 Codex에 설치됐다는 뜻이 아니다.

스킬 형식 검사를 넘어, 독립 에이전트가 모호한 실제 의뢰와 이전 답변·권한을 받아 목표 프롬프트를 만들고 별도 검증용 연구 공간에서 CLI를 사용하도록 확인한다. 원시 응답과 생성물을 보존한다. 연구 효과와 사용자 이해도는 이 설치·동작 검증으로 입증하지 않는다.
