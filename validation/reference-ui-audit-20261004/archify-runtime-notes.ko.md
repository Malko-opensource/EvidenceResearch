# Archify 실제 실행 준비와 비교 기준

공식 저장소 `https://github.com/tt-a1i/archify`의 commit `7158026e852f3aa6578c741e673b46d7878c92c1`, package version `3.0.1`을 별도 검증 폴더에 내려받았다. 원본 추적 파일을 수정하지 않았으며 `git diff --name-only` 결과가 비었다. 프로젝트의 연구 상태·웹 8765·전역 환경·인증 정보를 변경하지 않았다.

## 실제 실행

- 기본 예제: <http://127.0.0.1:8771/examples/web-app.html>
- 같은 예제의 공식 발표 모드: <http://127.0.0.1:8771/examples/web-app.html?present=1>
- 도구 흐름 예제: <http://127.0.0.1:8771/examples/workflow-agent-tool-call-rendered.html>
- 상태 수명주기 예제: <http://127.0.0.1:8771/examples/lifecycle-agent-run.html>

공식 README가 안내하는 standalone HTML을 Python 표준 라이브러리 HTTP 서버로 제공한다. 프론트엔드·뷰어·예제 데이터는 원본 그대로이며, 모델이나 API를 호출하지 않는다. 백엔드 스텁과 의존성 설치가 필요하지 않았다. 원본 web-app.html과 실제 HTTP 응답의 SHA256은 `8233f4f600c89559b64ac650ad11b66ee1423103e8b6c5e53f63740afc06f6da`로 일치했다. 브라우저 시각 검토와 캡처는 주 에이전트가 수행한다.

실행 명령:

```powershell
& 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\.validation-venv\Scripts\python.exe' -I -m http.server 8771 --bind 127.0.0.1 --directory 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\validation\reference-ui-audit-20261004\archify'
```

실제 숨김 서버 PID는 `49796`이다. `archify-process.json`과 HTTP 표준 출력·오류 로그가 같은 검증 폴더에 있다. 이 서버만 정리할 수 있으며 다른 프로세스는 정리 대상이 아니다.

공식 zero-dependency CLI `doctor`도 실제 실행해 ready를 확인했다. 공식 workflow JSON을 `validate workflow ... --quality showcase --json`으로 실제 검증했다. 첫 샌드박스 실행은 Windows 안전 경로 확인 EPERM으로 실패했으며 로그를 보존했다. 같은 원본·명령을 승인된 경로 확인 권한으로 다시 실행해 `ok: true`, composition pass, errors 0, warnings 0을 확인했다. 이 검증은 모델을 실행하지 않고 SVG·배치·관계 선을 검증한다. 연구 성능이나 사용자 이해도를 입증하지 않는다.

## 원본이 명시하는 단순화 원칙

| 원칙 | 원본 근거 | 현재 서비스와 직접 비교할 질문 |
|---|---|---|
| 하나의 공간적 이야기부터 보여 준다 | PRODUCT.md:30, DESIGN.md:88·228 | 기본 화면을 봤을 때 주 시각 대상 하나가 먼저 읽히는가, 여러 카드가 같은 무게로 경쟁하는가? |
| 캔버스가 화면의 주체다 | PRODUCT.md:31, DESIGN.md:88 | 실제 관계도·연구 경로가 제목·설명·상태 카드보다 큰가? |
| 세부 내용은 초점에 따라 드러난다 | PRODUCT.md:31, DESIGN.md:201·243 | 보고 싶은 노드에 집중하면 한 설명만 열리는가, 모든 설명이 계속 남아 있는가? |
| 상시 패널을 추가하기 전에 기존 초점 도구를 재사용한다 | DESIGN.md:201·243 | 메트릭·검증·병목·과거 시도 등이 각각 상시 박스로 남아 첫 인상을 복잡하게 만드는가? |
| 초점·경로·확대는 원래 캔버스의 연속성을 유지한다 | README.md의 Explore and share, examples/web-app.html 뷰어 | 요약에서 분석으로 이동할 때 공간적 문맥을 잃는가, 선택한 내용만 강조되고 주변은 물러나는가? |
| 밀집 대시보드와 반복 카드 그리드를 피한다 | PRODUCT.md:19–24 | 정확한 정보를 카드에 분산한 결과 보고서 페이지처럼 느껴지는가? |

`F` 또는 Present 버튼으로 발표 모드, 노드 focus로 Semantic Passport, `R`/PATH로 관계 경로, `L`/LENS로 의미 역할, `/`로 노드 검색을 직접 경험할 수 있다. URL `#focus=api`는 API 노드 집중을 재현한다. 이것들은 참고 앱의 원본 뷰어 기능이며 EvidenceResearch 사용자에게 클릭을 요구하자는 제안은 아니다. 연구 서비스에서는 같은 수준의 표현 전환을 외부 에이전트가 WebMCP로 수행해야 한다.

## 비교의 범위와 주의

Archify는 저자가 작성한 구조·관계를 설명하는 단일 독립 HTML이며 숫자 대시보드가 제품 범위 밖이라고 명시한다(PRODUCT.md:13). EvidenceResearch는 실행·사전등록·검증·결정과 실제 측정치의 변경 상태를 보여 주어야 한다. 따라서 연구 정보를 없애거나 검증 상태를 하나로 합치면 안 된다. 참고할 핵심은 데이터의 진실성을 줄이는 일이 아니라 **첫 화면에서 동시에 보이는 정보와 공간적 초점의 수를 줄이는 표현 방식**이다.

발표 모드만 캡처하면 기본 상태보다 단순해 보이므로 기본 모드와 발표 모드 모두 비교해야 한다. 작은 폰트·많은 뷰어 도구·좁은 화면의 한계도 함께 확인한다. 원본 문서의 원칙과 실제 사용에서 관찰한 사실을 최종 보고서에서 구분한다.
