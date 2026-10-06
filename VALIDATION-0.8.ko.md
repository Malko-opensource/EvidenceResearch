# 0.8.0 실제 검증과 재현

2026-10-04. 설치·상태 기능·표현 정확성·실제 도구 사용을 확인했다. 사용자 이해도와 연구 성능 개선은 미입증이다. [결과와 한계](RELEASE-0.8.ko.md), [기획·대응표](PRODUCT-PLAN-0.8.ko.md), [독립 소스 감사](validation/audit/release-0.8.0-audit.ko.md)를 함께 읽는다.

## 검사 결과

| 항목 | 실제 근거 | 결과와 범위 |
|---|---|---|
| 상태·사전등록·증거·기억·unknown·중복·동시 요청·목표 전이 | `validation/research-report-0.8.0/test-results.json`, Python 로그 | 65/65 통과 |
| 읽기 전용 모델·참조 버전·비교·분포·단위·변조·핵심 지표 | 같은 경로의 모델 로그 | 56/56 통과 |
| 모델 SDK 없는 설치 | `installation.json` | 0.8.0/23개 도구, 핵심 의존성 0, 소스 밖 `-I` 실행·실제 HTTP·자산 일치 |
| 기존 Codex stdio launcher | `validation/mcp-installation-0.8.0.json` | 새 클라이언트 0.8.0/23개 도구; 기존 설정 bytes 불변 |
| 설치 번들·실제 호스트 | `validation/plugin-0.8.0/host-check-release/host-discovery.json` | Codex 0.160.0에서 plugin 0.8.0·활성 스킬·MCP 23개; 독립 프로필·모델 turn 없음 |
| CLI·stdio·WebMCP 같은 목표 | `channel-consistency.json`, `native-transcript.json` | 같은 목표 v2/revision 21/실행 3개; 조회·장면 전환으로 새 실행 없음 |
| 외부 에이전트 스킬→연구 수행 | `skill-demo/demonstration-manifest.json`, `cli-transcript.jsonl` | 고정 독립 계산·실제 3회 실행, 72<80 부정적 답, 기준 불변 |
| 실제 네이티브 WebMCP 장면 | `native-tools-final.json`, `native-transcript.json` | 25개 발견; 요약·분석·비교·기억·활동·관계·안정성·증거·복귀 |
| 다른 목표 초점·불일치 거부 | 실제 transcript와 선택 fixture | A→등록 B는 B로 전환, 명시 A+B는 INVALID_INPUT; fixture 실제 실행 0개 |
| 목표 재사용·중단·재개 | 같은 선택 fixture·transcript | 과거 응답 재사용이 재개된 현재 상태를 되돌리지 않음 |
| 변조·누락 표시 | `tamper-proof.json`, `missing-proof.json` | 현재 근거 supported=false, 과거 통과·채택은 역사적 기록; 개발 원본 동일 해시 복원 |
| 32개 등록과 빈 기록 | 실제 페이지 조회·화면 13/14 | limit=5/offset=20 조회, 화면 3개 공개, 부족한 데이터는 미측정·미확인 |
| 데스크톱·모바일·모션 감소 | `browser-checks.json`, 화면 15–17 | 1280×800·390×844 가로 넘침 없음, 인간 필수 조작 0개, reduce 실제 활성 애니메이션 0개 |
| 표시 대비 | 같은 브라우저 검사 | 요약의 읽는 텍스트 표본 최소 7.24:1; SVG/장식·전체 접근성 감사 범위 아님 |
| 기존 기록·고정 비교 보존 | `legacy-state-check.json`, `frozen-evaluation-check.json` | 기존 9개 공간 원본 행·고정 프로토콜 파일 해시 일치 |

검사 도중 Windows의 잘못된 session 요청 응답에서 TCP reset을 발견해 유효한 길이의 거부 요청 body를 처리하고 재검사했다. 실제 CSV에서 처음 지표가 진단값이었던 문제는 등록된 미충족 기준을 우선 표시하도록 고쳤다. 검사 첫 실패 로그도 보존했다. 소스·설치·배포·검증 파일의 해시는 `validation/source-manifest-0.8.0.json`에 있다.

## 원본 → 표현 → 시각화

| 원본 | 추상화 | 화면·범위 |
|---|---|---|
| `goal_versions`, `goal_lifecycle` | 현재 목표·전체 상태·이유·확보/미완료 | 상단·종료 보고; 전체 상태는 외부 보고, legacy unknown |
| `registration_goals`, 불변 `spec.criteria` | 실험에 고정된 목표 버전·기준 | 현재 목표 버전과 별개로 참조·대조 안내 |
| 실제 검증 `metrics`와 현재 연결 원본 | 값·기준·차이·단위·미충족 여부 | 핵심 카드·기준선/측정점; 단위 미등록은 미등록 |
| 가설·등록·run·evidence·verification·decision 연결 | 의미가 붙은 기록 경로 | 기본 흐름과 별도 관계 장면; 인과·독립성 미추정 |
| 명시 `repeat_design`, 고유 실행 | n·평균·min/max·표본 SD | 실제 분포; 미실행 제외, 표본 독립성·CI 없음 |
| 같은 평가 조건, 서로 다른 변경·소스 | 비교 가능한 묶음·조건 차이 | 비교표·실측 차트; 다른 조건은 별도 묶음, 순위 없음 |
| 실제 사건 시각·목표 전체 고유 run | 주요 사건과 시간 관측 | 실제 간격의 사건축·실행 시간 추이, 페이지 범위 표시 |
| 자원 관측 source/source_ref·run/reg 연결 | 통화별 소계·알 수 없는 사용량·분기 귀속 | 비용 카드·추이·분기별 관측; 임의 배분·통화 합산 없음 |
| persisted run request key 매핑·failed/unknown 원 실행 | 확인된 키 매핑·실패 이유군·확인할 원 실행 | 구조화 `judgment.executionAudit`; 받은 호출/replay 횟수는 null |
| 기억의 성공·실패·미결·조건·원본 참조 | 이전 시도의 교훈과 주장의 검증 여부 | 페이지·요약·원본 조회; 존재를 검증으로 취급하지 않음 |
| 파일·해시·무결성·원문 | 현재 보존과 과거 검증 기록 구분 | 별도 증거 장면; 해시 일치≠과학적 검증 |

## 화면 캡처

[최종 기본 보고](validation/research-report-0.8.0/01-demo-overview-final.png), [기준 비교](validation/research-report-0.8.0/02-demo-analysis.png), [실제 반복](validation/research-report-0.8.0/03-demo-stability.png), [관계](validation/research-report-0.8.0/04-demo-graph.png), [시간](validation/research-report-0.8.0/05-demo-activity.png), [원문](validation/research-report-0.8.0/06-demo-evidence.png), [중단](validation/research-report-0.8.0/08-paused-report.png), [변조](validation/research-report-0.8.0/10-tampered-history.png), [비교 조건](validation/research-report-0.8.0/12-condition-comparison.png), [모바일](validation/research-report-0.8.0/15-mobile-overview.png)을 제공한다. 상세 설명은 전체 폭의 별도 장면이고, 기본 카드 행은 균형 있게 배치됐다. 모바일은 핵심 보고부터 보여 주며 원문 전체를 요약에 이어 붙이지 않는다.

## 재현 명령

프로젝트 디렉터리에서 실행한다. 기능 검사는 임시 검사 공간을 사용한다. 설치 검사는 개발용 설치 공간을 추가할 수 있으며 연구 실험은 실행하지 않는다.

```powershell
.\.mcp-venv\Scripts\python.exe -X utf8 validation/run_report_checks.py
& 'C:\Program Files\nodejs\node.exe' validation/audit/multigoal-selection.mjs
.\.mcp-venv\Scripts\python.exe -X utf8 validation/report_install_check.py
.\.mcp-venv\Scripts\python.exe -X utf8 validation/mcp_install_check.py
.\.mcp-venv\Scripts\python.exe -X utf8 validation/preserve_legacy_state.py --check
.\.mcp-venv\Scripts\python.exe -I -X utf8 validation/finalize_release_report.py
```

별도 모델 호출 없이 기존 실제 연구의 원본을 조회한다.

```powershell
.\.mcp-venv\Scripts\python.exe -I -m research_cli --workspace 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces\goal-plugin-demo-20261004' goal_show --goal goal_bed1555e80744acf9e85c437baf2ff3f
.\.mcp-venv\Scripts\python.exe -I -m research_cli --workspace 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\research-workspaces\goal-plugin-demo-20261004' show --registration reg_3f105fe7b8834fdc8132663fa815073e
```

네이티브 WebMCP에서 문서 도구를 새로 발견한 뒤 아래 인수를 호출한다. UUID가 붙은 실제 이름은 `fetchTools()` 결과를 사용한다.

```json
{"workspace":"goal-plugin-demo-20261004","scene":"overview","registration":"reg_3f105fe7b8834fdc8132663fa815073e","focus":"conclusion"}
```

같은 등록으로 `scene:"analysis"`, `"graph"`, `"stability"`를 호출한다. `research_show`에서 증거 ID를 얻고 `research_inspect_evidence`로 원문을 펼친 뒤 `research_view` overview로 돌아온다. 실제 원문 ID·도구 인수와 응답은 transcript에 있다. 화면 범위만 변경하며 실험을 재실행하지 않는다.

플러그인은 [PLUGIN 안내](PLUGIN.ko.md)의 새 출력 디렉터리·독립 프로필 검증 명령을 사용한다. 실제 배포 폴더는 `dist/research-observatory-0.8.0-release`다. 기존 `host-check-v2`는 0.7/17개 도구였던 역사적 증거이며 최종 설치 증거로 사용하지 않는다. 최신 `host-check-release`를 기준으로 한다.

## 한계

기본 요약은 일부 결과·조건을 줄여 표시하며 생략 수·조회 범위를 밝힌다. 전체를 읽으려면 에이전트가 다른 장면·페이지·원문을 펼친다. 반복 평균·SD는 명시된 고정 개발 입력의 기술통계이고 독립 표본의 추론이 아니다. 비용·토큰은 관측되지 않은 전체 사용량을 확정할 수 없다. 영구 저장된 키 매핑은 요청 호출 횟수가 아니므로 replay 통계를 만들어 내지 않는다.

실제 사용자 이해도 평가, 다른 호스트/브라우저의 설치, 원격 배포와 연구 성능 개선은 별도 검증이 필요하다. 기능 통과·디자인 변경을 과학적 성공이나 성능 개선으로 표현하지 않았다. CLI·웹에는 모델 호출·인증·대화·자체 연구 루프를 추가하지 않았다.
