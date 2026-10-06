# Archify·Graft 실행 점검 후 관전 화면 보정

2026-10-04 · Research State CLI 0.8.0의 UI 후속 보정. 원본 실행 비교는 [이전 점검](UI-SIMPLICITY-AUDIT.ko.md)에 보존했다. 현재 웹은 연구 질문 아래에 실제 관계 캔버스 하나와 교체되는 설명 하나를 둔다. 실제 연구 기록과 CLI의 상태 전이·사전등록·검증 기준은 유지했다.

## 원본과의 차이와 선택

Archify 원본의 발표 장면은 보조 목록을 숨기고 관계도에 집중했다. Graft 원본은 선택한 대상의 관계를 강조하면서 같은 상세 공간을 교체했다. 기존 웹은 종료 원문·지표·자원·단계·설명을 동시에 펼치고, 같은 가설의 경로를 여러 줄로 반복했다. 원본의 자유 배치 그래프도 100노드에서는 복잡해졌으므로 그대로 복제하지 않았다. 공유 관계를 종류별로 정렬하고 선택 경로만 강조하는 구조를 선택했다.

| 이전 구조 | 보정한 구조 | 답하는 질문 |
|---|---|---|
| 종료 보고·지표·비용·시간 카드가 기본 화면에 경쟁 | 연구 질문, 실제 관계, 선택 결과와 짧은 불확실성 | 지금 무엇을 연구했고 어떤 결과를 얻었는가? |
| 초점 설명과 반복 단계가 쌓임 | WebMCP focus가 설명 하나와 강조 대상 하나를 교체 | 지금 펼친 대상은 무엇을 의미하는가? |
| 실험별 같은 가설/5단계 경로 반복 | 공유 가설은 하나, 실제 기록의 외래키로 연결 | 어떤 시도와 근거에서 결정이 나왔는가? |
| 원시 지표 이름·긴 소수·장문이 앞에 노출 | 고정 표시 이름 우선, 제한된 이름 번역·수치 표시, 원문 별도 장면 | 측정값이 고정 기준에 어떤 의미인가? |
| 관계 장면 3건에서 문서 높이 1,555px | 1280×800 창 골격, 기본 최대 3시도/관계 조회 최대 6시도 | 많은 기록 중 지금 보는 범위는 어디인가? |
| 모바일에 전체 가로 그래프 축소 | 결과·불확실성 먼저, 선택한 시도 1개 연결을 읽을 크기로 표시 | 작은 화면에서도 핵심 결과를 먼저 이해할 수 있는가? |

짧은 기획·정보 구조·원본→표현 모델→시각화 대응표는 [후속 설계](UI-FOLLOWUP-DESIGN.ko.md)에 있다. 표시 모델 `observatory`는 summary, metric, bottleneck, uncertainty, focus, attempts, graph와 원본 refs를 반환하는 순수 함수다. 요약의 현재 revision·등록 당시 목표 버전·등록 지문·원본 필드로 추적할 수 있다. 기본은 최대 3시도, 관계 장면은 조회 최대 6시도, 모바일은 선택한 경로 하나이며 전체/조회/표시 범위를 구분한다. 장면마다 달라지는 조회 순서 번호 대신 실제 Seed를 표시한다. Seed는 고유 식별자가 아니며 원본 등록은 에이전트가 지정한다.

## 실제 데이터와 화면

기존 외부 에이전트 실연 `goal-plugin-demo-20261004`의 3회 고정 CSV 실행을 사용했다. 실행은 성공했고 고정 검증기는 계산 일치 1과 만족도 72를 측정했다. 72는 등록 기준 >=80보다 8 낮아서 검증 실패·기각이다. 이 의뢰의 전체 종료는 외부 상태 보고이며 과학적 성공이 아니다. 사전등록에 지표 단위가 없어 이후 목표 문서에서 가져오거나 이름의 pct로 추정하지 않고 **단위 미등록**을 유지했다. 차트 축은 실제 값과 기준을 포함한 확대 범위이며 진행률·퍼센트 축을 새로 만들지 않았다.

최종 데스크톱: [전체 화면](validation/observatory-followup-20261004/screenshots/25-final-desktop.jpg). 최종 모바일: [390×844 화면](validation/observatory-followup-20261004/screenshots/26-final-mobile.jpg).

기본 데스크톱은 실제 7노드(공유 가설 1, 시도 3, 선택 산출물·검증·결정)를, 관계 장면은 13노드/15연결을 표현한다. 원본에는 검증→결정의 인과 외래키가 없으므로 그런 연결을 추가하지 않는다. 실행·검증·결정 상태를 구분하며 산출물 해시 일치를 과학적 검증으로 부르지 않는다.

## 검증 결과

| 검사 | 실제 근거와 결과 |
|---|---|
| 표현 모델 | JS 68/68 통과. 같은 가설 중복 제거·기록된 연결·음성 측정·과거 판정·누락/변조·없는 단위·표시 이름 우선순위·조회 범위 검사 |
| CLI/MCP/HTTP 회귀 | Python 65/65 통과. 전이·고정 기준·증거·동일/동시 요청 중복 방지·재개·목표·Laya·MCP·HTTP 계약. 새 웹의 디자인 사용성 검사와는 별개 |
| 에이전트 관전 | native WebMCP 25개 발견. 개요→분석→원문→개요, 가설/실험/증거/검증/결정 초점, 비교/기억/활동/반복 장면을 인간 클릭 없이 호출. 호출 원문과 DOM 증거 저장 |
| 설명 교체 | 초점 5개 모두 설명 영역 1개, 실제 선택 노드 강조. 같은 초점에서 외부 설명 변경도 화면에 반영되며 미검증으로 표시 |
| 실제 0/3/32건 | 빈 값은 미측정·미등록·상태 미확인. 32건 중 기본 3시도/조회 6개와 전체 32를 명시. 실제 성공 5==5·검증 실패 16/3!=5·미실행을 분리 |
| 변조·누락 | 백업한 개발 fixture 산출물 1건만 임시 변경/누락. 현재 무결성 경고와 과거 검증/채택을 분리. 누락은 파일 누락, 변조는 변조 감지. 새 값 999를 검증값으로 표시하지 않음. 원래 SHA-256으로 복원 |
| 데스크톱·모바일 | 1280×800 및 390×844에서 문서 너비/높이=뷰포트, 기본 설명 하나. 모바일 핵심 결과·불확실성·선택 경로가 표시되고 최종 기본 영역 내부 overflow도 없음 |
| 갱신 중 읽기 | 기존 active 목표 report-channel-fixture-20261004에서 긴 미검증 설명 스크롤 320px. 자동 갱신으로 원래 DOM 노드가 교체돼도 320 유지, revision 7 유지 |
| reduced-motion | 실제 media emulation reduce에서 초점 전환. 조건 true·실행 애니메이션 0 확인 후 임시 설정 해제 |
| 상태 불변 | 기존 13개 DB 논리 내용·전체 증거 파일·실행 marker·16개 Python 핵심 모듈이 시작 기준과 일치. 새 연구 실행·모델 호출 없음 |
| 설치/서빙 | source·최종 wheel·두 프로젝트 venv·8765 HTTP의 4개 웹 자산 해시 일치. 실행 핵심 의존성 0. 전역 환경 변경 없이 기존 서버에서 갱신 |

[검증 JSON](validation/observatory-followup-20261004/browser-validation.json), [호출 원문](validation/observatory-followup-20261004/webmcp-calls.json), [스크롤 증거](validation/observatory-followup-20261004/scroll-preservation.json), [JS 로그](validation/observatory-followup-20261004/js-regression.log), [Python 결과](validation/observatory-followup-20261004/regression-results.json), [전후 상태·HTTP 자산](validation/observatory-followup-20261004/runtime-after.json), [설치 manifest](validation/observatory-followup-20261004/source-install-manifest.json)를 보존했다. 중간 검증 캡처와 최종 캡처를 구분한다. 뷰포트 변경 직후 잘못 페인트된 23-deliverable-mobile.jpg는 검증 근거에서 제외했다.

## 설치와 재현

같은 0.8.0 버전의 UI 후속 wheel은 `dist/observatory-followup-20261004/research_state_cli-0.8.0-py3-none-any.whl`이다. 최종 SHA-256은 `8d5271d4a8b6331f17c0ee6202b95c66cd3a030e0d878046c1ab9c2db529b597`. 이전 0.8 릴리스 wheel/manifest와 별도 보존한다. 현재 `.validation-venv`와 `.mcp-venv`에 설치했다. 웹 서버 PID 40608은 기존 root·포트로 유지하며 현재 자산을 제공한다.

프로젝트 루트 PowerShell:

```powershell
node --test tests/test_view_model.mjs tests/test_observatory_projection.mjs
& '.\.mcp-venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_*.py' -v
& '.\.validation-venv\Scripts\python.exe' '.\validation\observatory_followup_check.py' after --require-assets
```

마지막 명령은 현재 설치/HTTP 자산과 연구 상태 보존을 확인한다. 브라우저의 실제 페인트·WebMCP·사용자 이해도를 대신하지 않는다. 다시 설치할 때는 [README](README.md), 장면을 제어할 때는 [웹 안내](WEB.ko.md), 이어 받을 때는 [핸드오프](HANDOFF.ko.md)를 따른다. 변조 검사를 다시 수행한다면 개발 fixture에 한정해 백업→검사→즉시 복원하고 실제 연구 산출물은 사용하지 않는다.

## 남은 한계

이번 결과는 화면 구조와 기능 검증이며 별도의 관전자 사용성 실험이나 연구 성능 개선의 증거가 아니다. 짧은 기본 화면의 정보 우선순위는 설계 판단이다. B/C 연구 성능·기억 ON/OFF 평가는 이번 UI 변경으로 새로 주장하지 않는다.

영어로 등록된 연구 조건은 그대로 남을 수 있다. 이름 번역은 만족도/계산 일치 두 용어만 다루고 임의 도메인 해석을 하지 않는다. 조회 밖 기록은 자동으로 모두 펼치지 않는다. 다중 산출물의 노드 간격은 보정했지만 현재 실제 브라우저 fixture는 등록 산출물 1개여서 다중 산출물·매우 큰 관계망의 가독성까지 입증하지 않았다. 모바일은 선택 경로와 첫 산출물 연결만 보여 주고 나머지는 명시적으로 별도 조회한다. 긴 원문·설명은 해당 장면 영역 안에서 스크롤할 수 있다. 네이티브 WebMCP 미지원 브라우저는 기존 관전 fallback을 유지한다.
