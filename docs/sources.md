# 원문·업스트림 구현 근거

조회일은 2026-10-02(Asia/Seoul)이다. 소개 글 대신 원문 PDF·HTML과 고정된 업스트림 파일을 직접 확인했다. 이 문서는 문헌 주장과 코드 관찰이다. 이번 프레임워크의 성능 측정 결과는 비교 실행 기록에서만 인정한다.

| 원자료 | 고정 버전 | 저장 위치 | SHA-256 |
| --- | --- | --- | --- |
| [Agent Laboratory 논문](https://arxiv.org/abs/2501.04227v2), Samuel Schmidgall 외 | arXiv:2501.04227v2 | `references/2501.04227v2.pdf` | `67b9543ae1d8e3ad86a65e2a436ddbd12700d7c8f4a66c5b4c2a6fccc1674d75` |
| [AgentRxiv 논문](https://arxiv.org/abs/2503.18102v1), Samuel Schmidgall·Michael Moor | arXiv:2503.18102v1 | `references/2503.18102v1.pdf` | `762045781a10140f714e0f23388014286a50cce79f385d6b4a1475162cce9669` |
| [AgentLaboratory 코드](https://github.com/SamuelSchmidgall/AgentLaboratory/tree/d9017d90e329112d2a80b7712f37ee9094d2cd27) | `d9017d90e329112d2a80b7712f37ee9094d2cd27` | `references/upstream/AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27/` | 파일별 `references/manifest.json` |

코드 commit 시각은 2025-08-20T21:46:42Z이다. GitHub commit/tree API 응답도 저장했다. 스냅샷의 35개 파일은 API가 제시한 Git blob SHA-1과 대조했고, 별도로 SHA-256을 계산했다. PDF에서 추출한 `.txt`는 읽기 편의를 위한 파생물이며 원본 PDF·HTML을 보존했다. 두 논문 HTML이 표시한 라이선스는 CC BY 4.0이고, 코드 MIT LICENSE를 스냅샷 안에 보존했다. 이 저장본은 원문 그대로이며 번역·분석은 이 문서에 별도로 작성했다.

## 논문에서 출발한 설계

Agent Laboratory의 출발점은 문헌 조사 → 공동 계획 → 데이터 준비 → 코드 실행·수정 → 결과 해석 → 보고서 작성이다. MLE solver는 실행 출력과 코드가 계획에 얼마나 부합하는지를 LLM 보상으로 판정한다. 논문 §5는 자기평가, 실행되지 않은 결과의 서술, 호스트 명령 실행 등을 한계로 다룬다. 따라서 이 프레임워크는 실행 산출물의 독립 계산을 채택 기준으로 추가한다. [원문 §3·§5](https://arxiv.org/html/2501.04227v2)

AgentRxiv는 이전 보고서를 로컬 preprint 서버에 저장하고 임베딩 유사도로 검색한다. 논문 §4.1은 코드 수정을 통한 기능 제거, 실제 계산 없이 그럴듯한 출력 생성, 보고서의 결과 환각을 설명하고, 논문에 보고한 정확도는 코드와 출력을 사람이 검토했다고 밝힌다. 성공 보고서 검색만으로 사실을 보장할 수 없으므로 실패·미결 기록, 적용 조건과 원본 증거를 함께 검색하도록 확장한다. [원문 §3·§4.1](https://arxiv.org/html/2503.18102v1)

AgentRxiv가 보고한 MATH-500 기준 70.2%→78.2% 및 79.8%는 **문헌 주장**이다. 이번 연구에서 재측정한 값이 아니며, A의 실행 결과나 B/C의 비교 기준으로 대입하지 않는다. 논문의 상대 향상률과 퍼센트포인트 차이를 혼용하지 않는다. 동일 모델·동일 과제를 새로 실행해야 프레임워크 효과를 판단할 수 있다. [원문 §3.1·§3.2](https://arxiv.org/html/2503.18102v1)

## 현재 코드에서 확인한 실행 흐름

아래 줄 번호는 모두 고정 commit 기준이다. 파일 URL에 commit을 포함해 변경되는 `main`에 의존하지 않는다.

| 확인 대상 | 구현 근거 | 관찰과 개선 근거 |
| --- | --- | --- |
| 전체 단계·재실행 | [`ai_lab_repo.py:60–65,139–200`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/ai_lab_repo.py#L139-L200) | 단계별 boolean과 완료 후 pickle 저장이 있다. 실행 식별자와 산출물 해시로 중복을 막는 원장은 없다. |
| 체크포인트 | [`ai_lab_repo.py:106–113`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/ai_lab_repo.py#L106-L113) | `Paper{index}.pkl`에 워크플로 객체를 저장한다. `load-previous`는 673–674,722줄에서 해석되지만 이후 복원 호출이 없다. |
| 실험 실행 | [`tools.py:289–325`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/tools.py#L289-L325) | 생성 Python을 별도 프로세스의 `exec`로 실행하고 stdout을 회수한다. 별도 프로세스만으로 평가 파일·증거 변경 권한이 차단되지는 않는다. |
| 실험 점수 | [`mlesolver.py:141–162,351–385`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/mlesolver.py#L141-L162) | 같은 `llm_str`가 계획·코드·출력에 0~1 점수를 부여한다. 이 점수는 실제 과제 정확도나 독립 평가가 아니다. |
| 최선 코드 | [`mlesolver.py:276–316`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/mlesolver.py#L276-L316) | 보상 점수가 높은 코드를 남긴다. 최선 결과는 독립 검증 뒤에만 갱신하도록 바꿀 근거다. |
| 코드·로그 산출물 | [`ai_lab_repo.py:310–341`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/ai_lab_repo.py#L310-L341) | 선택 코드와 출력 로그를 저장한다. 설정·분할·seed·소스·산출물 해시를 묶은 실행 등록은 없다. |
| 보고서 평가 | [`agents.py:36–201`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/agents.py#L36-L201), [`papersolver.py:399–468`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/papersolver.py#L399-L468) | 논문 스타일의 LLM 평가다. 실제 수치가 산출물에서 계산되는지 판정하는 역할을 대신할 수 없다. |
| AgentRxiv 위치 | [`app.py:20–23,61–62,121–146`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/app.py#L121-L146) | 별도 공개 저장소가 아닌 이 저장소의 Flask·SQLite 서버와 `AgentRxiv` 클래스다. PDF 본문을 MiniLM 임베딩의 cosine 유사도로 순위화한다. |
| 기억 재사용 | [`ai_lab_repo.py:483–503,576–647`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/ai_lab_repo.py#L576-L647), [`agents.py:714–735`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/agents.py#L714-L735) | 이전 PDF를 검색·요약·문헌 목록에 추가한다. 요약 모델은 `gpt-4o-mini`로 고정돼 있다. 실패 상태·검증 상태·원본 실행 해시는 검색 스키마에 없다. |
| PDF 공유·서버 시작 | [`ai_lab_repo.py:240–270`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/ai_lab_repo.py#L240-L270), [`app.py:159–168`](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/app.py#L159-L168) | AgentRxiv 활성 시 생성 PDF가 필요하다. 서버 시작 때 DB를 제거하고 uploads를 다시 색인한다. 지속 원장과는 구분한다. |

## 실행 전에 해결해야 할 원본 제약

현재 `main`의 순차 경로는 서버를 만들 수 있지만 `LaboratoryWorkflow(..., agentRxiv=False)`를 고정한다(832,857줄). 병렬 경로는 PDF 컴파일을 강제하고 종료 후 `NotImplementedError`를 발생시킨다(789,828줄). `report_writing`은 인스턴스 변수 대신 모듈 전역 `research_topic`, `compile_pdf`를 참조한다(251줄). 순차·병렬 CLI를 그대로 돌렸다는 주장과 클래스를 직접 호출한 어댑터 실행을 구분해야 한다. [고정 원본 진입점](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/ai_lab_repo.py#L714-L865)

`MATH_agentrxiv.yaml`은 테스트셋 전체에 반복적으로 최적화하고, 기준 성능을 제공하며 새 기준 실행은 하지 말라고 지시한다. 따라서 최종 평가의 개발/숨김 과제 분리 설계에는 그대로 사용하지 않는다. 이 판단은 원본의 다른 논문 실험 결과를 무효라고 주장하는 것이 아니라, 이번 비교의 누출 방지 조건을 명시하는 것이다. [원본 과제 설정](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/experiment_configs/MATH_agentrxiv.yaml)

원본 requirements에는 135개 항목이 있다. torch·transformers·diffusers 등 과제와 무관한 프레임워크도 import되며, `app.py`는 AgentRxiv를 쓰지 않아도 import 단계에 SentenceTransformer 모델을 로드한다. Flask, Flask-SQLAlchemy, sentence-transformers, TensorFlow는 직접 사용되지만 requirements 목록에는 없다. 설치 성공을 실제 실행 성공으로 취급하지 않는다. [imports](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/common_imports.py), [requirements](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/requirements.txt)

원본 비용 함수는 정적인 과거 가격과 tokenizer 길이로 추정한다. 현재 모델이나 ChatGPT 구독 호출의 과금 증거로 사용할 수 없다. 새 provider는 실제 호출·토큰 사용·경과 시간을 남기고, 청구 금액을 확인할 수 없으면 `null`로 기록한다. [원본 비용 추정](https://github.com/SamuelSchmidgall/AgentLaboratory/blob/d9017d90e329112d2a80b7712f37ee9094d2cd27/inference.py#L12-L33)

개발 CPU 과제의 문헌 검색 병목을 점검하며 Sifan Liu·Edgar Dobriban의 [Ridge Regression: Structure, Cross-Validation, and Sketching §2·§3](https://arxiv.org/html/1910.02373v2)를 추가로 직접 확인했다. 정규화된 최소제곱과 validation 기반 정규화 선택의 배경으로 쓰며, 이 과제의 최적 차수·alpha를 제시하는 실행 증거로 쓰지 않는다. `references/task_literature.json`에는 URL·저자·짧은 자체 synopsis와 전체 고정 corpus 해시를 저장한다. synopsis는 원문 전체라고 표시하지 않는다.

