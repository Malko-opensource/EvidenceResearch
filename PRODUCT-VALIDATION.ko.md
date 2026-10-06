# 연구 상황판 0.7 · 검증 결과

작성: 2026-10-04. 설계와 원본→표현→시각화 대응표는 [PRODUCT-DESIGN.ko.md](PRODUCT-DESIGN.ko.md)에 있다. 자동 검사 71개(49+22), 실제 개발 실행, 설치된 웹의 native WebMCP 호출과 화면을 확인했다. 연구 성능이나 사용자 이해도 향상을 실증한 결과와는 구분한다.

## 자동 검사

| 범위 | 확인 결과 | 원본 증거 |
|---|---|---|
| CLI·영속 상태·실행기·MCP·HTTP | Python 49개 통과, 실패·오류·건너뜀 0 | [결과 JSON](validation/product-web-0.7.0/python-tests-final.json), [검사 로그](validation/product-web-0.7.0/python-tests-final.log) |
| 읽기 전용 표현 모델 | Node 22개 통과, 실패·건너뜀 0 | [검사 로그](validation/product-web-0.7.0/model-tests.log) |

Python 검사는 사전등록·검증 결과의 고정, 전이와 권한 조건, 동시 요청 충돌과 실행 중복 방지, 중단 후 원래 실행 복구, 성공·실패·미확정 기억 검색, 증거·검증기 변조, 내보내기와 복원을 확인한다. 선택 실험 사건 조회가 다른 실험 사건을 포함하거나 연구 상태를 변경하지 않는지도 검사한다.

표현 모델 검사는 실제 보존 기록과 수치 대조, 원본 입력 불변, 사용자 숫자만으로 검증을 만들지 않음, 현재 변조·누락과 과거 판정의 분리, 실행·검증·등록 소스의 연결, 음수와 복수 기준, `==`/`!=`, 미확인 사용량, 페이지 범위 집계, 선택 사건 범위, 비교 조건과 반복 조회를 확인한다. 채택 이후 영속 상태의 추가 증거 요구가 비어 있어도 현재 파일 누락·변조가 있으면 표시용 병목에 원본 복원·대조 필요를 알린다. 이 설명은 영속 상태나 허용된 전이를 바꾸지 않는다. 해시 일치는 원본 보존 상태이며 과학적 검증과 별개다.

## 실제 개발 실행과 페이지 자료

[fixture 보고서](validation/product-web-0.7.0/fixture-report.json)의 `product-fixtures-20261004`는 **상황판 개발용 자료이며 연구 성능 평가가 아니다.** Core와 로컬 실행기 API를 사용했고 직접 SQL로 결과를 삽입하지 않았다.

| 개발 시도 | 실제 측정값 | 실행 | 독립 검증 | 결정 |
|---|---|---|---|---|
| 가중치를 반영한 평균 | 가중 평균 5, pass_rate 1 | 성공 | 등록 기준 통과 | 채택 |
| 가중치를 생략한 단순 평균 | 평균 16/3, pass_rate 0 | 성공 | 등록 기준 실패 | 기각 |
| 나머지 페이지 검사 자료 30건 | 미측정 | 미실행 등록 | 대기 | 대기 |

실제 실행 두 건은 같은 목표·입력 분할·seed·비교 기준·성공 기준·실행 조건·고정 검증기를 사용하고 소스 버전이 다르다. 가중치 누락이 실패 원인이라는 결정 이유를 보존했다. 가중 평균은 무차원, pass_rate는 비율로 사전등록했으며 값 1을 임의로 백분율로 바꾸지 않는다. 미실행 등록의 seed와 페이지 검사 조건은 서로 달라 비교 가능한 완료 결과처럼 세지 않는다.

전체는 등록 32건·실제 실행 2건·revision 44다. 재실행 후에도 같은 등록과 완료 실행을 재사용했고 실행 표식은 `correct`, `naive` 두 줄이다. 보고서에는 두 호출의 `execution_started=false`, `verification_reused=true`가 남아 있다. 등록·증거 ID와 보존 경로는 보고서에서 조회할 수 있으며 자격증명은 포함하지 않는다.

fixture 실행기와 검증기에는 모델 호출이 없다. 외부 에이전트의 모델 사용량·토큰 사용량은 확인되지 않아 `unknown`으로 남긴다. 실행 경과 시간은 로컬 작업의 기록이며 전체 연구 시간이나 외부 모델 추론 시간을 나타내지 않는다.

## 실제 WebMCP·화면 검증과 캡처

실제 [native 도구 목록](validation/product-web-0.7.0/native-tools.json)은 19개다. HTTP의 연구 도구 17개에 브라우저 표시용 `research_view`, `research_inspect_evidence` 2개가 더해진다. [호출 기록](validation/product-web-0.7.0/native-transcript.json)에서 요약→분석→증거→요약 장면 왕복을 확인했다. 장면 전환은 에이전트가 수행했고 확인한 화면의 사람 입력·클릭 제어는 0개였다. 기본 화면에는 원문 JSON을 두지 않고 증거 장면에서만 공개했다.

| 확인 대상 | 실제 결과 |
|---|---|
| 조건과 수치 비교 | 개발 fixture 두 실행은 비교 가능한 1개 그룹이다. 이전 가중 통계 실연 두 건은 목표·입력·비교 기준·검증기가 달라 2개 그룹으로 분리했고 순위를 만들지 않았다. |
| 실패 기억 | 실행 성공·검증 실패·기각과 가중치 누락 이유를 표시했다. 과거 기록의 존재와 현재 성공 주장을 구분했다. |
| 많은 자료와 빈 상태 | 총 32건 중 기본 조회 20건, offset 20의 조회 5건은 21–25번째로 표시했다. 선택된 미실행 등록은 측정값을 만들지 않았다. 빈 저장소는 등록·지표 0건으로 표시했다. |
| 현재 변조·누락 | `trust.supported=false`, 속이 빈 과거 수치 점과 ‘현재 확인 안 됨’, ‘과거 검증 통과·과거 채택’, 원본 복원·대조 병목을 표시했다. 원문 조회는 각각 `EVIDENCE_TAMPERED`, `EVIDENCE_MISSING`으로 거부했다. |
| 원본 복원 | 검증용 파일은 보존한 원본 바이트로 되돌렸고 등록 SHA-256과 일치했다. 복원된 원문 조회와 현재 주장 확인도 다시 통과했다. 영속 검증·결정 기록은 덮어쓰지 않았다. |
| 사건 범위 | 선택 실험과 연결된 8개 사건을 별도로 읽어 대량의 후속 등록 때문에 실행·검증 사건이 묻히지 않게 했다. 전체 저장소 사건과 선택 범위를 구분했다. |

크기와 표시값은 [브라우저 검사 기록](validation/product-web-0.7.0/browser-checks.json)에 있다. 같은 원본 실연을 1280×720 창에서 비교한 문서 높이는 기존 3,004px에서 852px로 줄었다. 최종 기본 데스크톱 1349×1244 창에서는 결과·신뢰 카드가 각각 약 250px, 아래 세 카드가 각각 약 193px였다. 문서 높이 1,244px는 viewport 최소 높이의 영향이 있으므로 콘텐츠가 그 높이를 모두 사용한다는 뜻은 아니다. 1280×720에서는 하단 사건·기억을 읽는 데 작은 스크롤이 남는다.

모바일 390×844 창에서는 clientWidth와 scrollWidth가 모두 375px로 가로 넘침이 없었다. 요약의 문서 높이는 1,726px로, 핵심 상황을 먼저 놓고 원시 기록을 길게 붙이지 않았다. 분석·증거 장면도 가로 넘침이 없었다. 임시 reduced-motion 조건에서 `reduced=true`, 실행 중인 애니메이션 0개를 확인했고 viewport·미디어 설정은 원래대로 복원했다.

실제 캡처는 다음과 같다. 진단용 프레임 캡처는 완료 근거에서 제외했다.

| 장면 | 실제 화면 |
|---|---|
| 기본 요약 | [1280px 요약](validation/product-web-0.7.0/01-summary-1280.png) |
| 기준 분석 | [등록 기준과 실측](validation/product-web-0.7.0/02-analysis.png) |
| 실험 비교 | [동일 조건](validation/product-web-0.7.0/04-comparison.png), [다른 조건 분리](validation/product-web-0.7.0/04b-incompatible-comparison.png) |
| 원본 증거 | [보존 원문](validation/product-web-0.7.0/03-evidence.png) |
| 현재 변조 | [과거 판정과 복원 병목](validation/product-web-0.7.0/05-tampered.png) |
| 실패 기억 | [실패 이유와 검증 상태](validation/product-web-0.7.0/06-failure-memory.png) |
| 주요 사건 | [선택 실험 타임라인](validation/product-web-0.7.0/07-activity.png) |
| 많은 자료 | [32건 중 페이지 조회](validation/product-web-0.7.0/08-many-unexecuted.png) |
| 빈 상태 | [미등록·미측정](validation/product-web-0.7.0/09-empty.png) |
| 모바일 | [요약](validation/product-web-0.7.0/10-mobile-overview.png), [분석](validation/product-web-0.7.0/10b-mobile-analysis.png), [증거](validation/product-web-0.7.0/10c-mobile-evidence.png) |

## 설치 확인

[설치 검사](validation/product-web-0.7.0/installation.json)는 소스 디렉터리 밖에서 격리된 Python 환경의 0.7.0 설치본을 실행했다. 모델 SDK·MCP SDK를 설치하지 않은 환경에서 핵심 런타임 의존성 0개, HTTP 도구 17개, 설치된 모듈·웹 자산과 소스의 일치를 확인했다. 임시 서버는 종료했고 이 검사는 모델 호출·실험 시작·새 연구 저장소 생성 없이 기존 상태의 revision 8을 유지했다. SDK가 필요한 별도 stdio MCP 실행 환경과 구분한다.

[현재 소스·wheel·두 설치본 대응](validation/source-manifest-0.7.0.json)은 핵심 CLI·상태·실행·복원·Laya·MCP 코드 9개가 0.6.0과 같음을 확인한다. SDK 없는 설치 CLI를 소스 밖에서 실행한 [상태 조회](validation/product-web-0.7.0/installed-cli-status.json)도 등록 32건·revision 44를 유지했다. [기존 Codex stdio 연결](validation/mcp-installation-0.7.0.json)은 설정 변경 없이 17개 도구를 확인했다. 개발용 서버는 종료하고 현재 설치 서비스 하나를 남겼다.

## 재현과 해석의 한계

프로젝트 디렉터리에서 다음을 실행한다. 준비 스크립트를 반복 실행해도 완료한 두 작업을 새로 시작하지 않는다.

```powershell
& '.mcp-venv\Scripts\python.exe' validation\product_fixture.py
& '.mcp-venv\Scripts\python.exe' -m unittest discover -s tests
& 'C:\Program Files\nodejs\node.exe' --test tests\test_view_model.mjs
```

fixture 보고서의 `reproduction`에는 원본 상태 페이지와 성공 등록을 조회하는 정확한 인자도 있다. 기존 성능 비교의 동결 자료와 개발 fixture는 별개다.

이 결과는 상태·표현의 기능 검사와 작은 실제 계산 실연이다. 연구 성능 개선이나 관전자의 이해도 향상을 실증한 결과가 아니다. 비교 묶음은 등록된 조건의 일치만 확인하며 미등록 환경까지 동일하다고 보장하지 않는다. 역할·해시 검사는 동일 OS 계정의 보안 격리를 제공하지 않는다. 사용자 이해도와 장기 연구 효용은 별도 평가가 필요하다.

실제 WebMCP 확인은 지원 API가 있는 Codex 인앱 브라우저에서 수행했다. 다른 모든 브라우저·에이전트 호스트에서 같은 방식으로 도구가 제공된다고 보장하지 않는다. WebMCP 미지원 브라우저의 관전 표시는 유지되지만 에이전트의 native 장면 제어에는 지원 호스트가 필요하다.
