# 사람이 함께 이해하는 연구 상황판 · 0.7 설계

작성: 2026-10-04. 구현 전에 현재 웹과 실제 저장소를 읽고 정의한 서비스 기획이다.

## 서비스와 관전자의 질문

사용자는 외부 에이전트에게 보고 싶은 내용을 요청한다. 에이전트는 WebMCP로 초점과 장면을 바꾼다. 웹은 저장된 연구를 설명하고 관전하며 스스로 연구를 선택하거나 모델을 호출하지 않는다. CLI와 동일한 연구 상태를 읽고 기존 전이·등록·검증 규칙을 유지한다.

1. 무엇을 연구하는가? → 목표 제목, 연결된 가설, 시험한 변경점.
2. 지금 무엇이 진행되거나 막혔는가? → 실행·검증·결정의 별도 상태와 부족한 증거.
3. 어떤 결과와 근거가 생겼는가? → 등록 지표의 실제 측정값과 고정 기준 비교.
4. 무엇이 검증됐고 불확실한가? → 독립 검증 기록, 현재 증거 무결성, 미확인 자원과 적용 범위.
5. 이전 시도에서 무엇을 배웠는가? → 조건과 함께 읽는 기억, 실패 이유, 주요 사건.

## 현재 화면에서 확인한 문제와 선택한 방향

기존 화면은 큰 단계 관계도 옆에 등록 JSON, 자원, 모든 증거 ID·해시와 결정 이유를 한 열로 쌓는다. 실제 DOM에서 상세 패널은 약 2,053px, 옆 열은 약 2,596px였다. 핵심 결과를 보기 전에 기술적 기록을 지나야 한다. 설계 시작 시점의 웹 저장소 등록은 완료 실연 2건이며 입력과 검증 조건이 달라 순위로 비교할 수 없다. 실패·미결 표본이 없다는 사실을 숨기지 않는다.

내부 대안은 (A) 현 상세 열을 접기, (B) 모든 기록을 넓은 테이블로 전개, (C) 핵심 상황과 에이전트 설명 장면 분리였다. C를 선택했다. A는 여전히 한 열에 책임이 집중되고 B는 사람이 연구의 의미를 해석해야 하기 때문이다. 기존 어두운 색상과 청록 초점을 유지하되 읽기 크기·대비·여백을 높인다. 그림 자산이나 장식 그래프 대신 실제 수치와 사건을 그린다.

## 정보 구조 · 두 계층

기본 `overview`는 연구 질문, 짧은 상태 관계, 주요 결과의 기준 비교, 신뢰/병목, 최근 핵심 사건, 지난 시도 요약으로 구성한다. 원문·로그·경로·해시·ID·전체 JSON은 표시하지 않는다. 카드의 길이를 제한하고 생략 사실을 알린다. 긴 설명은 요약의 옆 열에 추가하지 않는다.

설명 계층은 `analysis`(등록 기준과 측정값/조건), `comparison`(조건이 확인된 시도끼리 비교), `memory`(검색된 교훈), `activity`(시간과 사건), `evidence`(선택한 원문)이다. 에이전트가 장면·등록·검색·페이지를 지정한다. 증거 장면은 기존 `research_inspect_evidence`로만 연다. 사람의 클릭·입력은 필요하지 않다. 기존 overview/memory/activity 호출은 유지한다.

데스크톱은 넓은 결과 영역과 균형 잡힌 상황 카드를 사용한다. 설명 장면은 전체 폭을 쓰고 목록은 소량을 공개하며 에이전트가 페이지를 바꾼다. 모바일은 질문→상태→결과→불확실성 순서이며 원시 기록을 연결해 붙이지 않는다. 색상 외에 문구, 실측 점/기준선, 상태 명칭과 범례를 둔다. 초점 이동과 실제 값 변경만 짧게 강조하고 reduced-motion에서는 움직임을 생략한다.

## 읽기 전용 표현 모델

`view_model.js`는 원본 입력을 바꾸지 않는 순수 함수로 원천 참조(`registration`, `field`, `evidence` 등), 조회 범위, 요약, 상태 설명, 기준 비교, 비교 그룹, 주요 사건과 기억을 만든다. 원천 참조는 WebMCP 결과에 제공하고 기본 화면에는 내부 ID를 숨긴다. 요약은 결정적 축약이며 새로운 과학적 주장이나 판단을 생성하지 않는다.

| 원본 데이터 | 표현 모델 | 질문과 시각화 | 원본으로 추적 |
|---|---|---|---|
| goal.title, hypothesis.statement, spec.change | question, hypothesis, change | 연구 질문과 시험한 변경점 | goal/hypothesis/registration 참조 |
| run.state, verification.state, decision.state | separate states, stage, blockers | 짧은 연결 상태 + 병목 설명 | research_show, status.missing_evidence |
| spec.criteria, verification.metrics/details.criteria_results | metric comparisons | 수평 수치축의 실측 점과 기준선·허용 방향; 값 누락 표시 | 등록 criteria와 검증 metrics |
| evidence.integrity, run_id, verification.run_id | current integrity, historical verdict, supported claim | 과거 검증과 현재 원본 보존을 별도 표시 | 각 evidence와 verification |
| 전체 spec 비교 조건과 검증기 해시 | conservative cohorts, differences | 같은 조건의 시도만 나란히; 다른 조건은 별도 그룹 | 각 등록 spec/source_version |
| status.registrations, total/limit/offset | scoped execution/verification/decision counts | 조회 범위가 명시된 상태별 분포 | status 원본 페이지 |
| snapshot.events, event_total | ordered milestones with timestamps | 실제 시간축과 사건 목록 | 사건 ID·revision·created |
| memory.summary/reason/conditions/integrity | lessons, conditions, claim support | 성공·실패·미결별 교훈과 적용 조건 | 기억 ID와 원본 등록 |
| resources | known/unknown resource facts | 분석 장면의 실행 시간과 미확인 사용량 | run.resources |

단위 미등록은 그대로 알리고 이름으로 백분율을 추정하지 않는다. 같은 지표의 여러 기준도 유지한다. `==`, `!=`에 우열 순위를 부여하지 않는다. 해시 일치는 원본 보존 상태이며 과학적 검증과 별개다. 과거 passed/adopted 기록이 남아도 현재 증거가 누락·변조되면 현재 성공 주장을 확인된 것으로 표시하지 않는다. 실패 검증 기록은 실패 자체가 미확인인 것처럼 설명하지 않는다.

기본 교훈은 성공·실패·미결별 최근 1건을 조회하고 선택한 시도 외의 결정 이유를 먼저 보여 준다. 선택 방법·원본 질의·revision은 WebMCP에 반환한다. 이유가 없는 제안은 가설 기록임을 알린다. 이 선택은 설명의 정보 우선순위이며 과학적 후보 선택을 하지 않는다.

분포는 조회 페이지의 기록만 집계한다. 기억과 상태는 서로 다른 정렬·페이지를 유지한다. 타임라인은 API가 제공한 최근 사건 범위만 표시한다. 서로 다른 revision을 합치면 갱신 중임을 표시한다. 파일은 revision 변화 없이 바뀔 수 있으므로 현재 무결성을 계속 다시 읽는다. 비교에는 비교 기준·분할·seed·지표/명시 단위·criteria·conditions·검증기 해시가 필요하다. 기억 요약만으로 비교 가능하다고 판단하지 않는다.

## 구현과 검증 범위

표현 모델과 브라우저 장면만 변경하고 저장소/실행기/검증기/CLI 핵심은 유지한다. 새 런타임 의존성은 추가하지 않는다. 모델 단위 검사, 기존 상태 규칙 검사, 실제 WebMCP 장면 왕복, 원본 대조, 누락/변조, 빈 데이터/많은 기록, 데스크톱/모바일 캡처와 크기 검사를 수행한다. 개발 fixture는 실연 연구 및 동결 성능 평가와 구분한다. 디자인의 기능·가독성 개선과 연구 성능 개선은 별개다.
