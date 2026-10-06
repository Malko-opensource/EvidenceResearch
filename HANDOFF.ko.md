# 후속 핸드오프 · Research State CLI 0.8.0

2026-10-04. 외부 에이전트가 모델 호출·문헌 조사·가설·코드·과학적 판단을 담당합니다. CLI는 목표·실험·증거·검증·기억을 영속화하고, 웹은 사람이 이해할 연구 보고를 읽기 전용으로 구성합니다. 핵심 CLI·웹의 실행 의존성은 0개이며 stdio MCP만 선택 의존성 `[mcp]`를 사용합니다. Laya 교환은 유효하며 실제 추론은 외부에서 수행합니다.

현행 기본 화면의 구조와 실제 확인 범위는 [의뢰인 설계](CLIENT-VIEW-DESIGN.ko.md)와 [의뢰인 검증](CLIENT-VIEW-VALIDATION.ko.md)을 따릅니다. [관계 중심 후속 설계](UI-FOLLOWUP-DESIGN.ko.md)·[이전 검증](UI-FOLLOWUP-VALIDATION.ko.md)은 당시 기록으로 보존합니다. [초기 0.8 검증](VALIDATION-0.8.ko.md)·[릴리스 보고](RELEASE-0.8.ko.md)·[이전 핸드오프](HANDOFF.md)·[0.7 화면 검증](PRODUCT-VALIDATION.ko.md)·[기존 연구 비교](REPORT.ko.md)는 당시 증거로 보존하며 후속 검증과 합치지 않습니다.

## 설치와 재연결

[README](README.md)의 소스·wheel 설치를 사용합니다. 후속 wheel은 `dist/client-spectator-20261004/research_state_cli-0.8.0-py3-none-any.whl`이며 버전은 0.8.0을 유지합니다. `validation/wheels`와 이전 릴리스 번들의 동일 버전 파일은 역사 기록이므로 경로·해시를 구분합니다. 이 PC의 프로젝트 환경은 SDK 없는 `.validation-venv`와 MCP용 `.mcp-venv`, Codex MCP 이름은 `research_state`, 연구 root는 프로젝트의 `research-workspaces`입니다. 갱신 전부터 열린 stdio 서버는 이전 코드가 남을 수 있으므로 호스트에서 재연결하고 23개 공통 연구 도구를 확인합니다. [MCP 안내](MCP.ko.md)의 기존 command/args를 유지하며 다른 프로젝트 프로세스나 설정을 변경하지 않습니다.

웹은 [localhost:8765](http://127.0.0.1:8765/)를 사용합니다. 같은 서버가 있으면 기존 주소를 열고 새로 시작해야 할 때만 다음을 사용합니다.

```powershell
.\.mcp-venv\Scripts\python.exe -I -m research_cli.web_server --root 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces' --port 8765 --open
```

공통 23개와 화면 전용 2개로 네이티브 WebMCP 계약은 25개입니다. 페이지 도구 이름은 매번 발견합니다. overview→analysis/graph/stability→evidence→overview는 외부 에이전트가 제어하며 사람이 버튼·입력을 사용할 필요가 없습니다. [웹 안내](WEB.ko.md)에 장면·goal·registration·focus·비교 범위를 설명했습니다.

[플러그인 안내](PLUGIN.ko.md)의 준비 번들과 의뢰 인터뷰 스킬은 기존 에이전트의 사용을 돕습니다. 독립 검증용 Codex 프로필에서 설치·발견한 것과 사용자의 개인 프로필 설치를 구분합니다. 스킬 호출·프롬프트 작성은 실행 허가나 검증 완료가 아닙니다.

## 이어 갈 때 유지할 상태

CLI·stdio·웹에서 같은 root/workspace·goal ID·등록 ID·request key를 사용합니다. 먼저 `status`·`goal_show`·`memory`로 현재 revision·전체 연구 상태·남은 근거를 읽습니다. 목표 수정·종료·재개에는 최신 expect가 필요합니다. 이전 요청 재전송의 `applied_revision`과 현재 `revision`, `result_is_historical`을 구분하며 현재 판단은 다시 조회합니다.

목표 수정은 새 버전이고 사전등록은 원래 목표 버전·평가 기준을 유지합니다. 전체 완료·중단·취소는 외부 보고이며 성공 실행·독립 검증·채택과 별개입니다. 완료는 running/unknown이 남으면 거부합니다. 목표 중단·취소가 worker를 종료하지 않으며 `goal_resume`도 실행을 시작하지 않습니다. running/unknown은 원 worker·로그·산출물·영수증을 확인해 `recover`하고 불명확하면 unknown을 유지합니다. exactly-once를 주장하지 않습니다.

비용·토큰은 출처가 있는 외부 관측이며 통화별 소계·미확인 관측·집계 범위를 함께 읽습니다. 관측 소계를 전체 사용량으로 해석하거나 목표 비용을 가설별로 임의 배분하지 않습니다. 원본 숫자 제출·문헌·추론·제안은 독립 검증을 만들지 않습니다. 해시 일치는 보존 상태이고 과학적 타당성이나 OS 보안 격리가 아닙니다. 자세한 계약은 [CORE-GOALS.ko.md](CORE-GOALS.ko.md)와 CLI 도움말에 있습니다.

## 화면과 실제 개발 기록

[의뢰인 설계·원본 대응표](CLIENT-VIEW-DESIGN.ko.md)는 질문·선택한 답·확인 범위·다음 확인을 기본으로 정의합니다. 순수 `buildClientView`는 기존 `buildViewModel`을 읽으며 현재 근거가 불확실하면 과거 통과를 현재 답으로 승격하지 않습니다. 관계도와 운영 정보는 graph/analysis/evidence에 두고, focus 또는 explanation은 기본 보고를 한 설명 장면으로 교체합니다. 둘을 생략한 overview 호출로 보고로 돌아옵니다. 관계 장면은 최대 6개 조회 기록, 모바일은 선택 경로에 집중합니다. 비용·실행 시간은 activity에서 보고 분석·기억·원문은 별도 장면으로 펼칩니다. `view_model.js`는 원본을 변경하지 않는 순수 표현 레이어이며 각 표시의 revision·고정 목표 버전·등록 지문을 참조로 제공합니다. 핵심 지표는 등록 primary_metric, 현재 검증된 미충족 기준 지표, 등록 순서로 선택하고 이유를 WebMCP 결과에 반환합니다. 단위가 미등록이면 추정하지 않습니다.

[실제 외부 에이전트 사용 기록](validation/research-report-0.8.0/skill-demo/demonstration-manifest.json)은 고정된 공개 합성 CSV와 독립 고정 계산기를 사용합니다. 등록된 3회 기능 반복은 같은 입력에서 계산 일치 1과 만족도 72를 측정했고 사업 기준 80에 미달했습니다. 실행 성공·검증 실패·가설 기각·전체 의뢰 완료 보고가 함께 존재합니다. 동일 입력의 반복은 독립 표본·모집단 추론·연구 성능 향상을 입증하지 않으며 이 반복 수를 전체 연구의 제한으로 쓰지 않습니다. [연구 보고](validation/research-report-0.8.0/skill-demo/research-report.ko.md)·[해당 연구 재개 안내](validation/research-report-0.8.0/skill-demo/resume-handoff.ko.md)를 따르고 이미 완료된 실행을 다시 만들지 않습니다.

핵심 회귀 명령은 `python -m unittest discover -s tests -v`, 표현 검사는 `node --test tests/test_view_model.mjs tests/test_observatory_projection.mjs tests/test_client_view.mjs`입니다. 후속 wheel·설치 자산·실제 WebMCP·브라우저 확인은 [의뢰인 검증](CLIENT-VIEW-VALIDATION.ko.md)의 산출물을 확인합니다. 이미 열린 stdio 호스트의 재연결 여부는 별도로 확인합니다. 표현 검사 통과를 연구 성능 향상으로 주장하지 않습니다.

## 남은 한계와 다음 작업

외부 모델 사용량이 없으면 비용·토큰·호출 시간은 unknown입니다. 실제 요청 수나 replay 시도 수를 관측하지 못하면 집계에서 null을 유지합니다. 화면 추이는 최근 조회 범위이고 전체 기록을 매번 반환하지 않습니다. 기록된 관계는 과학적 인과관계가 아니며 반복 분포는 등록된 비교 가능한 실제 측정의 기술 통계입니다. 다른 브라우저·AI 호스트의 WebMCP 지원은 해당 환경에서 별도 확인해야 합니다.

새 효과 입증은 개발 과제와 최종 평가를 분리하고, 동일 에이전트·모델의 B/C와 기억 ON/OFF를 별도로 사전등록한 후 수행합니다. 채택 기준·조건·반복 근거를 실행 전에 정하고 측정 불가 사용량은 unknown으로 남깁니다. 현재 화면 개선과 기능 실연은 기존 개선 미입증 결론을 바꾸지 않습니다. 보존된 과거 구현·평가·원본 자료는 조회 대상으로 유지하고 새 구현에 복사하거나 의존하지 않습니다.
