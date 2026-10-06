# 원본 실행 기반 UI 단순함 점검

2026-10-04 · Research State 0.8.0 · 이번 요청은 실행·비교·진단이다. 서비스 구현과 영속 연구 상태는 변경하지 않았다.

## 판단

현재 서비스는 Archify/Graft의 단순함을 충분히 반영하지 못했다. 연구 기록을 정확하게 구분하는 기능은 동작하지만, 화면은 여러 질문을 카드로 동시에 설명하는 문서형 대시보드다. 두 참고 앱은 중심 공간과 초점의 역할이 명확하다. 현재 구현에서 바꿔야 할 것은 색상·카드 모양보다 **처음에 무엇을 드러내고, 초점이 바뀔 때 무엇을 교체하는가**이다.

관전자가 처음 답해야 할 질문은 “지금 연구가 어디에 있고 어떤 결과를 얻었는가” 하나다. 세부 기준, 비용, 과거 시도, 원본은 에이전트가 요청에 맞춰 별도 장면으로 펼쳐야 한다.

## 실제 실행 범위

| 대상 | 실제 실행과 데이터 | 제한 |
|---|---|---|
| 현재 서비스 | 기존 8765 서버. goal-plugin-demo-20261004의 실제 저장 기록 3건. WebMCP로 분석·관계·원문·요약 장면을 조작 | 고정 합성 CSV의 개발 실연 기록이며 연구 성능 평가가 아니다 |
| [Archify 공식 원본](https://github.com/tt-a1i/archify) | v3.0.1, commit 7158026e852f3aa6578c741e673b46d7878c92c1. 원본 examples/web-app.html을 8771에서 그대로 실행. 원본·HTTP 응답 해시 일치. 기본·API Server 초점·발표 장면을 직접 조작 | 공개 샘플 관계도이며 EvidenceResearch 데이터를 연결한 것은 아니다. 모델·백엔드 호출 없음 |
| [Graft 공식 원본](https://github.com/trailhq/Graft) | v0.21.1, commit fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad. 원본 뷰어·서버·파서 실행. Context 8노드/12관계와 실제 8개 TS 파일의 Code 100노드 그래프 확인 | Context는 소스에 근거한 손작성 입력이며 모델 분석 결과가 아니다. 전역 업데이트 훅을 피하려고 원본 API를 직접 호출. 전체 CLI 통합·모델 요약을 검증한 것은 아니다 |

세 앱의 비교 캡처는 CSS 폭 1280px이다. 현재 서비스/Graft의 유효 높이는 800px, Archify는 브라우저에서 720px였다. 높이 차이를 숨기거나 화면 점유율을 정량 비교하지 않았다. 초기 크기 변경 직후의 잘못된 페인트와 CDP 배율 캡처는 판단 근거에서 제외했다. 아래 이미지는 이번 실행에서 저장한 파일을 다시 열어 확인한 실제 화면이다.

## 차이가 생기는 지점

| 질문 | 현재 서비스의 실제 화면 | 참고 앱에서 확인한 방식 | 연구 서비스에 적용할 방향 |
|---|---|---|---|
| 무엇을 먼저 보는가? | 종료 보고, 지표·비용·시간 3카드가 먼저 보인다. 핵심 경로는 800px 화면 아래로 밀린다 | Archify는 10노드 관계도와 주 흐름이 먼저 보임. Graft는 중심 그래프가 먼저 보임 | 연구 질문과 결과의 의미를 보여 주는 중심 공간 하나 |
| 자세한 설명은 언제 여는가? | 미선택 기본 장면에도 종료 원문·자원 설명·상태 구분이 모두 펼쳐짐 | Archify는 선택 노드의 작은 설명창을 엶. Graft는 미선택 상세를 비우고 선택한 한 대상만 설명 | 초점 설명은 한 공간의 내용을 교체. 원문은 별도 증거 장면 |
| 상태는 어떻게 읽히는가? | 같은 “검증 기준 미달” 판정이 현재 활동·지표·경로·검증 카드에 반복 | 주변 관계를 약하게 만들고 현재 대상을 강조 | 실행·검증·채택의 구분은 명료한 상태 묶음 한 번으로 보존 |
| 여러 기록은 어떻게 늘어나는가? | 같은 가설의 5노드 경로를 실험별로 세로 반복. 3기록 관계 장면의 높이 1,555px | Graft의 창 골격은 800px로 유지. 상세가 길면 그 영역 안에서 스크롤 | 실제 공유 관계를 하나의 공간에 묶고 선택 경로를 강조. 시도가 많아도 본문 골격 유지 |
| 원시 값을 어떻게 의미로 바꾸는가? | satisfaction_pct, 단위 미등록, 긴 소수, 영어 조건, 종료 보고 문자열이 표면에 노출 | 대상 이름·공간·관계가 먼저이고 출처는 대상 상세에 묶임 | 지표의 사람용 이름·정밀도·등록 단위를 표현 모델에 연결. 미등록 단위를 추정하지 않음 |
| 정보가 적은 장면은? | 비용 미확인도 큰 카드로 주 결과와 비슷하게 강조 | 기본 설명을 비워 두거나 제한된 선택 설명으로 보여 줌 | 미확인은 작은 상태로 명확히 남기고 필요할 때 펼침 |

Archify도 기본 모드에서는 설명·노드 목록이 아래로 이어진다(전체 높이 1,213px). 발표 모드에서 이 보조 내용이 숨겨지고 전체 높이가 720px가 된다. 따라서 “Archify는 항상 한 화면”이라고 단정할 수 없다.

Graft의 Code 100노드 전체 그래프는 선·이름이 겹쳐 복잡했다. 검색으로 renderDetail을 선택하자 주변 관계가 강조되고 상세가 같은 공간에 열렸다. **그래프를 크게 놓는 것만으로 단순해지지 않는다.** 연구 관전에서는 선택한 가설·시도와 필요한 근거의 범위를 먼저 정해야 한다.

## 직접 확인한 장면과 상태

| 단계 | 수행 | 상태와 관찰 |
|---|---|---|
| 1 | 현재 서비스 기본 화면 | 기능 정상, 관전 위계 부족. 원시 종료 보고가 중심을 차지하고 관계는 아래로 밀림 |
| 2 | WebMCP 분석 → 관계 | 전환 정상. 차트는 분석 장면에 있으나 조건·판정 설명이 경쟁. 관계 장면은 동일 경로를 시도마다 세로 반복 |
| 3 | WebMCP 원문 → 요약 | 원문 조회·복귀 정상. 파일 보존과 검증 실패 구분 유지. 전후 status 응답 동일, revision 21 유지 |
| 4 | Archify 기본 → API Server 초점 | 정상. 중심 관계도를 유지하며 작은 설명창·현재 대상 강조·주변 감쇠 |
| 5 | Archify 발표 → 기본 | 정상. 보조 설명을 숨겨 캔버스에 집중하고 복귀 가능 |
| 6 | Graft 기본 → Graph canvas → Selected node | 정상. 미선택 상세 비움, 선택 설명 교체. 앞선 설명이 새 설명 아래에 누적되지 않음 |
| 7 | Graft Code → renderDetail 초점 → Reset view | 정상. 실제 대량 그래프의 복잡함도 확인. 초점·내부 스크롤은 유용하나 전체 그래프의 선 겹침은 남음. Reset view는 선택 해제가 아니라 시점 복원 |

WebMCP는 status 2회, view 3회, show 1회, inspect_evidence 1회만 호출했다. 새 실험 실행·검증·가설 채택·모델 호출을 요청하지 않았다.

## 캡처

### 1. 현재 기본 화면

![현재 기본 화면](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/01-current-overview.jpg>)

원시 종료 보고, 세 가지 카드, 여덟 장면명이 동시에 존재한다. “지금 알아야 할 핵심”과 “뒤에 확인해도 되는 내용”의 시각적 차이가 약하다.

### 2. 현재 분석과 관계

![현재 분석](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/02a-current-analysis.jpg>)

실측과 등록 기준이 차트로 구분되는 점은 유효하다. 다만 calculation_matches/satisfaction_pct 원시 이름, 단위 미등록, 영어 조건·긴 실행 시간 소수가 읽는 부담을 만든다. 지표 카드에 붙은 반복 설명을 줄이고 비교 조건을 필요할 때 공개할 여지가 크다.

![현재 관계](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/02b-current-relations.jpg>)

실제 연결이라는 의미는 유지되지만, 경로별 동일 가설과 결론 문장이 반복된다. 공유 가설 하나에서 여러 실험으로 갈라지는 관계를 한 공간으로 표현하지 못한다.

### 3. 현재 증거 원문

![현재 원문](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/03-current-evidence.jpg>)

원문을 별도 장면으로 분리한 것은 유지할 수 있다. 내부 ID·해시의 표시 영역도 증거 장면 안에서 단계적으로 공개해 선택한 내용에 더 많은 공간을 배분해야 한다.

### 4. Archify 기본과 대상 초점

![Archify 기본](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/04a-archify-default.jpg>)

![Archify 선택](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/04b-archify-focus.jpg>)

10노드여도 중심 경로의 순서·갈림·그룹 경계가 공간으로 드러난다. 대상 선택 후 주변을 약하게 만들고 한 대상의 설명만 띄운다. 현재 서비스의 고정 5단계 카드와 달리 실제 관계 배치가 먼저 읽힌다.

### 5. Archify 발표 장면

![Archify 발표](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/05-archify-present.jpg>)

보조 설명을 숨겨 같은 관계도를 화면 중심에 유지한다. 연구 서비스의 사람 관전 기본 장면에 가장 가까운 참고다.

### 6. Graft 기본과 설명 교체

![Graft 기본](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/06a-graft-default.jpg>)

![Graft 첫 선택](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/06b-graft-focus-canvas.jpg>)

![Graft 다음 선택](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/06c-graft-focus-replaced.jpg>)

Context 입력은 손작성 샘플이다. 설명 문구의 질을 모델 성능으로 평가하지 않았으며, 실제 원본 UI가 한 대상의 설명을 교체하고 주변 관계를 강조하는 동작만 참고했다.

### 7. Graft 실제 코드 그래프

![Graft 코드 전체](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/07a-graft-code.jpg>)

![Graft 코드 초점](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/07b-graft-code-focus.jpg>)

![Graft 시점 복원](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/validation/reference-ui-audit-20261004/screenshots/07c-graft-code-reset.jpg>)

원본 파서는 100노드·234관계를 생성했고 실제 뷰어에는 224관계가 표시됐다. 원본 viewer/data.ts의 loadCodeGraph가 양쪽 노드 ID가 존재하는 관계만 표시해 외부·미해결 모듈을 가리키는 imports 10개를 제외한다. 표시 칩 part of 92 + uses 131 + references 1도 224와 일치한다. 제외된 원본 목록은 validation/reference-ui-audit-20261004/graft/code-viewer-provenance.json에 보존했다. 생성 자료와 화면 표시 수를 구분한다. 전체 그래프의 겹침은 참고 UI에도 남는 한계다.

## 다음 개편의 우선순위

1. **기본 관전 장면의 설명 범위를 줄인다.** 질문 한 줄, 전체 상태, 중심 결과·관계, 필요한 근거만 먼저 보인다. 비용·전체 종료 보고·지난 시도는 별도 설명 장면으로 이동한다.
2. **중심 시각화와 초점 설명을 분리한다.** 공간 관계를 유지한 채 에이전트가 현재 경로·시도를 강조하고 한 대상의 설명을 교체한다. 모든 시도의 5단계 카드를 반복하지 않는다.
3. **원본을 잘라 붙이는 요약을 바꾼다.** 표시용 모델에서 실제 지표·기준·조건·확실성을 묶는다. 사람용 명칭·표시 정밀도를 적용하고 원문 연결을 유지한다. 등록 단위가 없으면 그 사실을 숨기지 않는다.
4. **WebMCP를 관전 장면의 조작 방식으로 유지한다.** 인간 클릭 없이 개요 → 결과 설명 → 원문 → 개요로 이동한다. 연구 상태 전이·검증 규칙은 바꾸지 않는다.
5. **창 안에서 정보가 교체되는 구조를 검증한다.** 비용 미확인·근거 미등록·많은 시도에서도 한 열이 계속 길어지지 않아야 한다. 긴 원문은 별도 증거 장면의 제한된 영역에서 조회한다.

기본 화면에서 “실행 성공 / 검증 실패 / 가설 기각”을 구분하는 정직함은 유지해야 한다. 해시 일치·외부 종료 보고를 과학적 검증으로 바꾸거나 미확인을 성공처럼 꾸미는 방식의 단순화는 허용하지 않는다.

## 소스 확인과 후속 핸드오프

캡처에서 관찰한 누적 구조는 [app.js의 기본 장면](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/research_cli/web/app.js:93>), [실험별 경로 반복](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/research_cli/web/app.js:146>), [종료 원문 문자열 절단](<C:/Users/Potato/Documents/ChatGPT/Research Agent/EvidenceResearch/research_cli/web/view_model.js:466>)에서도 확인된다. 기능별 카드를 계속 추가하는 구조를 유지한 채 문장만 줄이면 밀도가 다시 생길 수 있다.

후속 구현의 관전 확인 기준은 “기본 데스크톱에서 연구 질문·현재 상태·핵심 결과·불확실성이 먼저 읽히는가”, “한 대상의 설명을 펼쳐도 기존 설명이 아래로 누적되지 않는가”, “같은 가설의 여러 시도가 실제 공유 관계로 묶이는가”, “0건·많은 기록에서도 장면 골격이 유지되는가”다. WebMCP 장면 전환과 영속 상태 불변을 다시 검증해야 하며, 새 UI가 더 단순하다는 판단을 사용자 이해도나 연구 성능 개선의 실증으로 대신하지 않는다.

## 가독성과 점검 한계

현재 화면의 작고 조밀한 보조 문장, 길게 반복되는 원시 필드, 많은 동일 카드 제목은 읽는 부담을 키운다. Graft 초점의 흐린 주변 노드는 주 대상 집중에 도움을 주지만, 주변 문구를 확인해야 할 때 대비가 낮다. 참고 앱의 사람이 클릭·검색하는 조작을 그대로 필수 흐름으로 가져오면 기존 에이전트 제어 원칙을 깨뜨린다.

이번에는 데스크톱 실제 화면·선택·장면 전환을 점검했다. 사용자 과제 수행 시간, 이해도, 모바일, 스크린리더, 모든 대비 비율이나 reduced-motion 동작을 새로 측정하지 않았다. 접근성 적합성이나 연구 성능 개선을 주장하지 않는다. 현재 단순함 부족은 실제 화면과 동작에 근거한 설계 진단이다.

실행 기록과 현재 호출 원본: validation/reference-ui-audit-20261004/browser-audit-manifest.json, archify-runtime-manifest.json, graft/manifest.json. 서버는 127.0.0.1에 한정해 현재 실행 중이며 기존 8765 서버를 변경하지 않았다.

