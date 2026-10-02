# 비교 기준과 원본 실행 어댑터

주 비교는 **B: 원 프레임워크 + 현재 모델** 대 **C: 개선 프레임워크 + 같은 모델**이다. A: 원 연구 계열 모델은 실제 provider 권한과 모델 목록에서 사용 가능한 경우에만 실행한다. A가 실행되지 않았으면 모델 교체 효과의 실측값을 보고하지 않는다. 논문 수치를 A로 대입하지 않는다.

## 비교 종류를 분리한다

| 이름 | 실행 내용 | 허용되는 결론 |
| --- | --- | --- |
| `upstream_unmodified` | 고정된 원본 소스와 원래 provider·도구·CLI를 독립 환경에서 실행 | 조건이 일치하면 원본 동작의 직접 비교. 원 논문 재현에는 논문 과제·모델·자원 조건까지 필요하다. |
| `upstream_actual_adapted` | 원본 클래스·함수·프롬프트·단계·MLE/PaperSolver·LLM judge를 실행하고 모델/도구 경계만 명시적으로 교체 | 같은 교체를 공유하는 B/C 과제에서 제한된 프레임워크 효과. 원본 MATH-500 또는 AgentRxiv 서버 재현으로 부르지 않는다. |
| `baseline_surrogate` | 문헌 흐름을 참고해 새로 쓴 축약 알고리즘이나 규칙 기반 선택기 | 개발용 ablation. 원본 B의 증거로 사용할 수 없다. |
| `mock` / `smoke` | 가짜 provider·의도적인 중단으로 계약이나 import만 검사 | 구현 검증. 실제 모델 비교·과제 개선을 입증하지 않는다. |

이 저장소의 `evidence_research/baseline.py`는 두 번째 종류를 구현한다. 새로 쓴 축약 solver로 원본 B를 대체하지 않는다. 원본 소스 스냅샷은 수정하지 않고, Python AST에서 최상위 import만 제외해 함수·클래스 본문을 그대로 compile/exec 한다. 보존한 정의의 AST 해시, 원본 파일 해시, 제외한 import 목록을 실행 기록에 남긴다.

## 실제 B 실행 계약

```python
run_upstream_baseline(
    task_public,
    run_dir,
    query_model,
    execute_code,
    settings,
    literature=frozen_reference_records,
)
```

`settings`는 실행 전에 `model`, `max_steps`, `mlesolver_max_steps`, `papersolver_max_steps`, `num_papers_lit_review`를 정한다. 이 숫자는 사전 등록된 비교 과제의 자원 조건이다. Goal 전체 연구 루프를 종료하는 횟수 제한이 아니다. 어댑터에 임의의 새 연구 종료 횟수를 내장하지 않았다.

- `query_model`은 원본 인자 `model_str`, `prompt`, `system_prompt`, `temp`를 받는다. 전체 원본 모델 요청을 B/C와 동일한 실제 provider 및 모델로 보낸다. API key 인자는 저장·전달하지 않는다. provider 사용량·실제 모델 ID·reasoning 설정을 외부 실행 원장에 남긴다. 원본 요청의 temperature가 provider에서 지원되지 않으면 그 사실을 기록하고 같은 정책을 C에도 적용한다.
- `execute_code`는 생성 코드를 받아 실제 과제 작업을 실행하고, 원본 solver가 읽을 출력을 문자열로 반환한다. 동일한 허용 도구와 CPU 자원 조건을 C에도 제공한다. 임의 Python을 직접 `exec`하는 callback을 연결하면 이 어댑터가 OS 격리를 제공하는 것으로 오인하면 안 된다. 고정 평가 파일이나 완료된 증거를 수정할 권한은 부여하지 않는다.
- 문헌·데이터 검색은 caller가 제공한 고정 스냅샷을 반환한다. 인터넷 검색, HuggingFace 다운로드와 임베딩 서버를 재현한 것으로 보고하지 않는다. 문헌 주장에는 `literature claim` 상태를 표시한다. 최종 정답이나 숨겨진 평가 데이터는 `task_public`·문헌·notes에 넣지 않는다.
- 모델 단계 순서, 원본 MLE code repair·선택, 결과 해석, 전체 PaperSolver 보고서 생성과 reviewer 동작은 원본을 실행한다. 원본 LLM 점수는 보상 판단으로 유지하고, 최종 과제 성공은 외부의 고정 검증기로 계산한다.

직접 `LaboratoryWorkflow`를 호출하므로 원본 CLI의 경로 삭제·서버 시작은 실행하지 않는다. 원본 보고서 코드가 필요로 하는 전역 `research_topic`, `compile_pdf`를 공급한다. `compile_pdf=False`로 LaTeX 소스만 생성한다. **원본 AgentRxiv PDF/web backend는 이 CPU 어댑터가 지원하지 않으며, 활성화 요청은 오류로 반환한다.** 기억 재사용 효과는 별도 비교/ablation과 실제 기억 기록으로 검증해야 한다.

모듈 alias와 현재 디렉터리가 process 전체에 영향을 주므로 B는 전용 독립 프로세스에서 호출한다. import 때의 원본 logging/warnings/env 변경도 그 프로세스에 한정한다. 기존 KoMap, 다른 checkout, 기존 환경이나 프로세스를 참조하거나 중단하지 않는다.

## 실행 증거와 재개

`baseline_registration.json`은 public task·설정·문헌·소스 해시를 실행 전에 저장한다. `baseline_events.jsonl`은 검색, 실제 model callback, actual execution callback 및 오류를 기록한다. `baseline_stdout.log`와 원본 `lab/src/experiment_output.log`, 코드, 보고서·LaTeX, pickle checkpoints를 보존한다. 최종 `baseline_result.json`에는 소스 정의 해시, 도구 변경 목록과 과제 실행 수를 넣는다.

같은 완료 run directory와 같은 등록을 다시 호출하면 provider나 과제를 실행하지 않고 기록을 반환한다. 실패 결과도 같은 등록이면 그대로 반환한다. 다른 등록을 같은 directory에 덮어쓰지 않는다. 등록은 있지만 durable final result가 없으면 `unknown_execution`으로 반환하며 실제 작업을 다시 하지 않는다.

명시적인 `resume_from`과 `retry_reason`을 새 디렉터리에 등록하면, 이 저장소 `runs/` 안에서 직접 생성한 원본 체크포인트를 복원할 수 있다. 이전 등록·결과·모든 산출물의 해시, 원본 소스·과제·문헌·실행 조건의 일치를 먼저 검사한다. 제한된 unpickler는 고정 업스트림의 `LaboratoryWorkflow`와 여섯 agent 클래스만 복원한다. 다른 전역·외부 프로젝트의 pickle은 허용하지 않는다. 원본 `phase_status`가 완료한 단계를 건너뛰고, 프롬프트 해시가 일치하는 완료된 실제 모델 응답은 해시 검증 후 재사용한다. 기존 실패 영수증과 보고서는 변경하지 않는다. 새 호출에는 새 ID를 사용하며 이전 요청까지 포함한 사전 자원 조건을 유지한다. durable `turn.failed` 영수증 없이 상태가 불명확한 모델 호출은 자동 재실행하지 않는다. 이는 호스트 어댑터의 복원 기능이며 원본 CLI에 구현된 기능이라고 주장하지 않는다.

`evidence_research.arms.UpstreamArm`은 고정 평가 harness의 B callback이다. owner가 공급한 공개 train/validation bundle만 받으며, 별도 검사 정답이나 private task 정의를 읽지 않는다. `ImprovedArm`과 동일한 provider/model·문헌·literal CPU 도구 계약·`proposal_calls_per_unit`를 사용한다. 원본이 선택한 최종 코드와 실제 검증된 실행을 연결한 뒤 원본 보고서의 모든 숫자에 대한 독립 판정 파일을 요청한다. 독립 reviewer가 없으면 검토 대기 상태가 남고 최종 채택 조건을 통과할 수 없다. 실패한 모델 시도의 원본 영수증도 별도로 반환하여 비용·시간을 0으로 숨기지 않는다.

import smoke는 `references/adapter_import_smoke/`에 저장했다. 5개 원본 모듈의 로드와 원본 첫 literature inference 진입을 확인한 뒤 의도적으로 provider가 없다는 오류를 반환했다. 이 smoke의 모델 호출과 과제 실행은 0이며, 성능 비교에 포함하지 않는다.

## 개발 실행과 이어가기

다음 명령은 개발 과제용 실제 모델 실행이다. Codex CLI의 기존 로그인을 사용하며 별도 API key를 기록하지 않는다.

```powershell
python -m evidence_research.arms --development-baseline runs/development/B-first --task dev-quadratic --seed 7 --model gpt-6.1-sol
python -m evidence_research.arms --development-baseline runs/development/B-continued --resume-from runs/development/B-first --retry-reason "Known provider capacity error; continue unchanged registered conditions."
```

개발 자원 설계는 정상 문헌 검색·읽기·추가 및 제출 슬롯을 위한 단계 `max_steps=4`, 원본 MLE 초기 실행, 원본 보고서의 아홉 초기 단계와 추가 수정 없음이다. 원본 분기별 모델 요청 상한을 합산한 51회는 한 과제의 B/C 공통 자원 조건이며 Goal 연구 횟수 상한이 아니다. 상세 산식은 `development_protocol.json`의 `resource_design`에 실행 전에 저장한다.

2026-10-02 개발 중 첫 B 실행은 문헌 단계가 완료되지 않아 실패했다. 고정 문헌에 과제 관련 ridge 논문의 출처를 추가하고 같은 입력을 B/C에 공유한 다음 실행에서는 실제 CPU 계산과 독립 검증이 완료됐다. 보고서 도중 provider의 `Selected model is at capacity` 오류가 발생했고 그 실패를 보존한 새 디렉터리에서 체크포인트 재개를 실행했다. 이 개발 기록은 최종 평가나 일반 연구 능력 향상의 증거로 사용하지 않는다. 개별 상태와 수치는 `runs/development/*/development_result.json`, 모델 `events.jsonl`, 실제 실험 `result.json`과 `independent_verification.json`을 따른다.

## 비교를 사전 고정할 항목

평가 과제와 seed 묶음, 모델 ID·provider·reasoning 설정, 공개 문헌, 초기 기억, 실행 도구·CPU 자원, 호출·토큰 허용량, 성공 지표·효과 크기·불확실성 계산, 반복 수의 통계적 근거, 오류 복구·중복·근거 없는 주장 판정 규칙을 실행 전에 저장한다. B와 C가 다른 모델을 사용하면 그 결과에서 프레임워크 효과를 분리하지 않는다.

분모에는 실행 실패와 검증 실패를 포함한다. 자원 초과나 provider 접근 실패는 원인을 별도 상태로 저장한다. `null` 청구 금액을 무료 또는 0원으로 해석하지 않는다. LLM reviewer 점수의 상승을 실제 과제 지표 향상으로 보고하지 않는다. 최종 과제를 보고 구현을 수정했다면 해당 과제를 개발 자료로 이동하고 새로운 별도 과제로 고정 버전을 평가한다.

프레임워크 전체의 성공 주장은 전체 루프, 실패·성공 기억 재사용, 중단 재개, 수치와 계산 증거, 독립 평가·재현, 사전 기준을 충족한 B/C 향상이 모두 확인될 때만 한다. CPU 과제의 제한된 비교가 통과해도 일반적인 과학 연구 능력이나 원 논문 모델 개선이 증명됐다고 확대하지 않는다.

## 원본을 완전히 실행하는 추가 경로

원본 `references/upstream`을 실행용 새 디렉터리에 복사하고 독립 venv에 필요한 패키지를 설치한다. 부족한 Flask·Flask-SQLAlchemy·sentence-transformers·TensorFlow와 MiniLM 모델 다운로드를 명시적으로 해결해야 한다. AgentRxiv는 로컬 서버·SQLite·uploads·PDF 컴파일이 필요하다. 현재 모델을 지원하는 provider 어댑터는 `inference`뿐 아니라 star import로 복사된 `agents`, `mlesolver`, `papersolver`, `ai_lab_repo`의 `query_model` 경계까지 연결해야 한다. 모델 helper를 호출하는 생성 실험 코드도 같은 모델로 보내야 한다.

그 경로를 실행할 수 있을 때까지 `upstream_unmodified`와 A를 실행 완료로 표시하지 않는다. 업스트림 구현·의존성 제약은 [sources.md](sources.md)의 고정 코드 링크를 따른다. 추가 모델 API 결제, 원래 계열 모델 접근, GPU·대용량 패키지 설치가 필요한 경우 기존 승인 범위를 먼저 확인한다. 연구 결과의 외부 업로드는 이 어댑터가 수행하지 않는다.

