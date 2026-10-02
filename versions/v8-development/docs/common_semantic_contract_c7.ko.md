# c7 공통 의미 검증 계약

이 문서는 구현 전 등록 `work/c7-method-registration-v1.json`에 따른 후보 개발 계약이다. 고정된 과거 v4/v5/v6 연구의 판정이나 보고서를 바꾸지 않는다. 개발자가 수행한 구성요소 검사는 연구 성능 개선이나 독립 검증 완료의 근거가 아니다. 별도 담당자가 등록된 36개 합성 사례를 독립 검사하고 소스 폐쇄를 확인해야 한다.

스키마는 `whole-report-semantics-3-c7-common-context-development`이다. 실제 채택에 필요한 숫자·의미 검사, 개선 폭, 품질 조건은 완화하지 않는다. 문단과 JSON 키·문자열·스칼라 및 각 비공백 원문 span의 검토 범위를 그대로 유지한다. 자연어의 모든 의미를 자동 판정한다는 보증은 없으며, 독립 검토자가 조건·극성·시점 대응에 책임을 진다.

## 실제 입력 경계

`ContextBoundaryRecorder`는 실제 호스트 입력 생성 시점에 원문 body/full prompt, phase·role·logical ordinal, 모델·effort·실행 소스, 공통 조건, 원래 요청에 앞선 provider/CPU 영수증의 순서와 membership을 보존한다. `audit_context_boundary(link, arm_output)`는 해당 요청의 원시 입력, 원 요청 transport, 호스트 hashchain, 완료·실패 원시 영수증과 전체 발견 inventory를 대조한다. 현재 소유자가 만든 요약을 과거 입력으로 제시하는 방식은 허용하지 않는다. 다른 arm·task·model·source·settings의 영수증을 옮겨 사용할 수 없다.

정규화는 arm 이름으로 사실을 결정하지 않는다. B의 원래 도구 반환과 C의 원래 value-bearing 기억 입력은 동일한 제한 아래 처리한다. 같은 실행을 재생한 경우 실제 provider/CPU 비용을 다시 더하지 않는다. 실패 요청의 토큰 사용량이 원시 자료에 없으면 누적 토큰은 `null`이며 완료 요청의 합계는 별도 하한이다. 이 의미 검증 버전은 토큰 하한을 정확한 누적값으로 읽는 표현을 승인하지 않는다.

`historical_context_resources`의 범위는 지정한 원 요청 직전 전체 영수증 prefix이다. 마지막 선택 코드의 도구 반환이 더 이른 시점의 4회 CPU를 설명하고 보고 요청 직전 전체 기록이 5회인 경우, 4를 5로 덮어쓰지 않는다. 더 이른 반환의 시점을 별도로 증명하는 adapter가 없으면 보류한다. 최종 전체 비용, 다음 요청 비용, 가격, 원인·정보 이득을 승인하지 않는다.

## 허용된 자원 문법

한 문장 또는 분리된 한 절만 다음처럼 허용한다.

```
Before this proposal, measured resources were 20 CPU executions, 30 input tokens and 10 output tokens.
Before this request, measured provider input usage was 30 tokens.
```

`before this proposal/request` 소개부가 같은 자원 목록의 각 숫자에만 적용된다. 등록된 CPU·configuration·provider call/failure·input/output token·provider/CPU seconds 단위만 해석한다. 모든 나열된 값과 명시한 scalar를 재계산한다. 하나의 맞는 input 숫자가 다른 틀린 output 숫자를 승인하지 않는다. 정수 횟수는 정수로, 시간 표시값은 표시 자릿수에 따른 반올림 오차 안에서 확인한다.

`historical appendix`, 다른 설계에 관한 `Historically`, 부정된 소개부, 최종/예측/긍정적인 인과 절은 이 문법으로 통과하지 않는다. `; monetary cost is unknown`은 별도의 limitation span이다. 문단 전체에 시간 범위를 무차별 상속하지 않는다.

## 원 입력의 값 가용성

`report_input_availability`는 다음 한정된 문장과 지정한 boundary의 실제 값을 확인한다.

```
The named original reporting input contains validation MSE values for 1 verified run.
```

원 입력에 실제 metrics block 또는 확인된 value-bearing 기억 entry가 있고, 같은 CPU 영수증을 재검증한 값과 일치해야 한다. 경로·해시가 있다는 사실은 값이 입력에 있었다는 증거가 아니다. 이 범위는 지정한 입력 하나이며 전체 연구 이력에서 다른 결과가 없었다거나 에이전트가 논문을 읽고 이해했다는 증거가 아니다. 다른 phase의 값이나 소유자가 사후 만든 요약을 옮겨 사용할 수 없다.

## 제한된 파생 산술

`derived_metric_arithmetic`은 한 독립 검증 CPU 실행의 `validation_mse - train_mse` 또는 역순 MSE 차이만 처리한다. 원문 split·뺄셈 방향·MSE 단위, 실행/소스/분할 해시, 표시 자릿수, 표시값을 대조한다. 예시는 다음과 같다.

```
For the named verified run, validation MSE minus training MSE is 0.10000000 MSE.
```

비율, 0 분모, 다른 실행의 두 metric, 인과·유의성·일반화 우월성 주장은 이 adapter가 지원하지 않는다. 산술 계산은 새 실험이나 보편적인 연구 성능 효과가 아니다.

## 문헌 원문과 FactRecord

`frozen_semantic_reference_hashes()`는 `references/source_facts_c7.json`과 `references/task_literature_v2.json` 양쪽을 실행 코드의 외부 SHA 상수와 검사한 뒤 절대 경로와 고정 SHA를 반환한다. root의 등록·archive·최종 frozen_sources는 이 closure를 포함해야 한다. JSON 자체의 자기 hash만으로 source를 채택하지 않는다.

`source_fact_attribution`은 6개 사전 고정 FactRecord의 영어·한국어 총 12개 literal form만 승인한다. subject·조건·극성·source ID·URL·원 synopsis excerpt·registry SHA를 유지한다. 임의 의역, applicability 조건 생략, 부정 반전, 현재 과제의 최적 alpha나 실제 향상을 추가하면 보류 또는 거부한다. 이 자료는 원문을 검토해 작성한 고정 synopsis이며 Craven/Wahba는 publisher Summary 범위이다. full paper 전체를 새로 읽었다거나 모든 문헌 내용이 사실로 입증되었다고 확대하지 않는다.

직접 인용 `attributed_literature`도 공통 고정 5-synopsis 파일의 동일 source ID·URL·excerpt에 한해 실제 문헌 귀속으로 처리한다. 로컬 측정이나 에이전트의 읽기·이해를 증명하지 않는다. 임의 파일의 quote-format 회귀 사례는 `engineering_legacy`이며 실제 완료를 만들지 않는다.

## 계획·질문·prior와 부정

양 arm의 고정 호스트 `next_questions` literal을 같은 AST 검사로 처리한다. 질문형이라고 긍정적인 완료 결과가 제외되지는 않는다. 원 입력에 보인 계획은 해당 boundary의 exact field 전체와 시간 범위를 확인한다. `measured unregularized degree-6 model`과 같은 prior 형용사는 그 degree와 penalty가 같은 prior 실행에 존재하고 해당 boundary 이전에 있었음을 증명해야 한다. 미래 영수증, 누락된 prior, 다른 실행에 흩어진 degree/alpha는 허용하지 않는다.

`The procedure should choose the observed minimum.`은 미실행 규범적인 방법이다. `The procedure achieved the minimum.`은 전체 actual history의 최소값 검증을 필요로 한다. 영어·한국어 부정은 같은 절의 효과 주장에만 적용한다. 다른 절의 `No`나 앞 문장의 미래 제안은 뒤의 긍정적인 성능·인과·재현 주장에 범위를 제공하지 않는다.

## 증거 자격과 합성 시험

`validate_semantic_review`와 `audit_semantic_reports`는 `semantic_evidence_qualification`을 독립 재계산한다. 허용 실제 완료는 `actual`이다. `component_fixture`, `engineering_legacy`, `unqualified`가 하나라도 있으면 실제 `semantic_report_audit_complete`는 False다. `status=complete`는 검토 span 범위가 완료되었다는 뜻일 수 있으므로 실제 채택은 별도 자격을 반드시 확인한다. 현재 source에서 boundary 없는 등록 가설 prior와 C-only historic adapter는 `engineering_legacy`다. 그 경로로 c7 공통 actual 완료를 만들 수 없다.

명시적 `evaluate_fixture_predicate`와 `evaluate_fixture_nonresult_context`는 제공된 합성 입력·영수증도 동일 source/scope/value 검사를 거친다. 정상 합성 사례만 `evaluation_scope=synthetic_engineering_fixture`, `evidence_class=synthetic_fixture`, `adoption_eligible=False`로 반환한다. synthetic-only 이유 외에 logical mapping, 누락/다른 원시 자료, unresolved 요청이 있으면 시험 양성도 거부한다. 공개 `evaluate_predicate`에는 시험 모드 인수가 없고, 실제 report adjudication은 actual-only 경로로 다시 계산하여 합성 proof를 거부한다. 전역 스위치·모델 인자·숨겨진 CLI 승인은 없다.

공개 경로의 산술·실행·비교 등도 원래 evidence JSON의 명시적 `fixture_only=True`, `simulation_only=True`, `test_fixture_only=True`나 simulation execution kind를 최종 사실에서 숨기지 않는다. 해당 CPU 값이 실제 계산되어도 합성 provenance가 전파되어 실제 완료는 불가하다. 키가 존재하는데 boolean이 아닌 경우(문자열·정수·null 등)는 거부한다. 표지가 없다는 사실을 실제 모델 실행의 증거로 간주하지 않는다. CPU의 실제 실행 계약과 모델의 원시 실행·권한·설정·전체 영수증은 각 고정 검증과 소유자 점수 계산에서 별도로 필요하다.

숫자나 측정 predicate가 전혀 없는 계획 보고서도 원 arm의 callback 등록과 정해진 CPU/provider metadata 위치에 명시된 합성 표지를 전파한다. 해당 원 출처와 SHA를 `nonactual_original_provenance`로 보존하고 재검산한다. 전체 보고서가 non-result라는 이유로 합성 실행을 `actual`로 세탁하지 않는다. 비공개 owner/test 파일이나 보고서가 임의로 지정한 경로는 이 검사로 열지 않는다.

합성 양성은 실제 증거가 아니라 구성요소 동작의 근거다. 개발자의 시험 기록은 `work/c7-semantic-implementation-v1`에 실패·수정·명령·소스 해시와 함께 보존한다. 별도 담당자의 독립 검증과 미래 실제 비교 전까지 연구 개선, 채택 또는 Goal 완료를 선언하지 않는다.
