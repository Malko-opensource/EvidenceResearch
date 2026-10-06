# CLI·stdio MCP·WebMCP 연결 계약

이 스킬은 외부 에이전트의 지침이며 연구 도구에 모델 호출을 추가하지 않는다. 배포 시 생성된 `connection.json`의 절대 연구 root와 상대 workspace를 확인한다. 명시적 연결이 없다면 사용 중인 원본 위치를 조사하고 서로 다른 `default`를 같은 연구로 간주하지 않는다.

## 실제 채널 계약

| 작업 | CLI 하위 명령 | stdio MCP·WebMCP 도구 |
|---|---|---|
| 도움말·상태·기억 | `help`, `status`, `memory` | `research_help`, `research_status`, `research_memory` |
| 목표 생성·조회 | `goal`, `goal_show` | `research_goal`, `research_goal_show` |
| 목표 버전 변경 | `goal_amend` | `research_goal_amend` |
| 종료·중단·재개 | `goal_close`, `goal_resume` | `research_goal_close`, `research_goal_resume` |
| 가설·사전등록 | `hypothesis`, `register` | `research_hypothesis`, `research_register` |
| 실행·복구·검증 | `run`, `recover`, `verify` | `research_run`, `research_recover`, `research_verify` |
| 결정·근거·원본 | `decide`, `evidence`, `show` | `research_decide`, `research_evidence`, `research_show` |
| 보존·복원 | `export`, `restore` | `research_export`, `research_restore` |
| 선택적 외부 Laya | `laya_prepare`, `laya_resolve` | `research_laya_prepare`, `research_laya_resolve` |
| 웹 장면·원문 공개 | CLI 장면 기능 없음 | 열린 웹 문서에만 `research_view`, `research_inspect_evidence` |

CLI는 `--workspace <절대 root/상대 workspace>`로 지정한다. MCP·웹 도구는 설치된 `--root` 아래의 상대 `workspace`를 사용한다. 동일 상태를 쓰는지 root와 workspace, 목표 ID·버전, revision을 조회해 대조한다. HTTP bridge의 내부 `input`과 공개 도구의 `spec`/`brief`를 혼동하지 않는다.

## 목표 저장·변경

`research_goal(title, description, brief, request_key, expect, workspace)`로 저장한다. 신규 스킬 흐름에서는 `request_key`와 최신 workspace revision인 `expect`를 항상 보낸다. 정확히 같은 요청은 stale expect로 재전송해도 기존 결과를 재사용한다. 같은 key에 다른 내용은 `REQUEST_CONFLICT`다. 이 key와 입력을 채널 전환 때도 유지한다.

`research_goal_show(goal, limit, offset, workspace)`는 목표의 현재 버전·상태, 페이지 처리된 변경과 lifecycle 이력을 반환한다. 목표 수정은 `research_goal_amend(goal, brief, reason, change_kind, request_key, expect, ...)`다. `change_kind`는 `meaning`, `scope`, `plan`이며 제목·설명은 필요할 때만 추가한다. 실험 등록은 바뀌지 않는다.

`research_goal_close(goal, state, reason, results, incomplete, request_key, expect, ...)`의 `state`는 `completed`, `paused`, `cancelled`다. 이는 외부 에이전트의 명시적 보고로, 과학적 검증을 대신하지 않고 worker를 자동 종료하지 않는다. 실행 중·unknown 원 실행이 남으면 그 사실과 조사·복구 절차를 먼저 보고한다. 재개는 `research_goal_resume(goal, reason, request_key, expect, ...)`다.

기존 목표의 lifecycle 정보가 없으면 `unknown`이며 실행 단계와 구분한다. 완료 상태만 보고 실험·가설이 검증됐다고 하지 않는다. 프롬프트 원본 파일과 목표 DB 저장은 하나의 트랜잭션이 아니다.

## 실행과 재개

실제 연결의 `research_help`와 등록 JSON 예시를 읽는다. 실험 등록 입력은 CLI의 `--input` 파일·stdin 또는 공개 도구의 `spec` 객체다. owner의 고정 검증기 등록은 허용된 로컬 CLI에서 수행하며 에이전트 MCP에 없는 관리자 기능을 우회하지 않는다.

등록과 실행은 각각 안정된 key를 사용한다. 설명을 바꿔도 동일 실험으로 판별되며 완료된 실행을 다시 시작하지 않는다. unknown이면 `show`와 `recover`로 원 실행·receipt·로그를 확인한다. `recover`는 대체 실험을 시작하지 않는다. stale revision 충돌이면 상태를 조회하고 계획을 맞추되 새 key로 원 실행을 숨기지 않는다.

CLI·MCP·웹 접근을 바꾸기 위해 새 목표·새 workspace·새 실행을 만들지 않는다. 서버를 종료하거나 전역 설정·인증을 바꿀 필요가 있다고 추정하지 않는다. 선택적 Laya의 모델 실행은 외부이며 응답은 검증 완료나 자동 채택이 아니다.

## 화면과 설치 경계

브라우저가 네이티브 WebMCP를 제공해야 열린 문서의 도구를 발견할 수 있다. `research_view`의 장면은 `overview`, `analysis`, `comparison`, `memory`, `activity`, `graph`, `stability`이며 `goal`과 `focus`로 범위를 지정할 수 있다. 초점은 `hypothesis`, `experiment`, `evidence`, `verification`, `conclusion`이다. 실제 연결의 스키마를 다시 확인한다. 화면 도구는 표현·범위·초점만 바꾸고 원본 연구 상태를 변경하지 않는다. `research_inspect_evidence`로 원본·로그·경로·해시를 별도 장면에 펼친 후 요약으로 돌아간다.

배포용 스킬에 특정 PC의 경로를 고정하지 않는다. `scripts/configure.py`로 사용자가 명시한 Python과 root를 연결한 설치 번들을 생성한다. 기본 소스의 빈 MCP 설정을 실제 연결 완료로 보고하지 않는다. marketplace 설치, 호스트의 스킬 발견, 실제 stdio 및 웹 도구 호출은 각각 확인한다. 독립 `CODEX_HOME` 검증은 사용자의 기본 프로필 설치와 구분한다.
