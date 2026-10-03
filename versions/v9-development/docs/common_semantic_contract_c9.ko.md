# c9 유한 증거 계약: 자원 지식, 기존 결과 기준, 원 제안문

이 문서는 새 개발 후보의 구현 계약이다. 실제 연구 개선·완료·채택을 증명하지 않는다. 작성자 검사와 외부 독립 검증은 구분하며, 기존 v4–v7 보고서와 판정에는 적용하지 않는다. 구현 전 등록은 `work/c9-method-registration-v1.json` SHA `4b0f4e04d66e9122ec20ab415fdab62c1cc6462c003da89d94e8d4853cce3abd`이다.

새 SEM 식별자는 `whole-report-semantics-4-c9-common-evidence-development`이다. 기존 시간 자원 목록 문법, 모든 수치의 전체 단위 연결, ContextBoundary의 원 입력·시간 순서·원 소스·모델·권한 검사, 고정 문헌 등록부 및 실제 증거 자격 조건을 유지한다. 현재 연구 채택 조건인 양쪽 보고서 전체 numeric AND semantic 검토, unsupported 0, 실제 자격, 토큰 절감 95% 신뢰구간 하한 20% 초과 AND test MSE 비율 신뢰구간 상한 1.10 미만은 이 구현으로 바뀌지 않는다.

## 자원 지식은 비용 측정값과 다르다

`resource_knowledge`의 arguments는 정확히 다음 세 필드다.

```json
{"resource_audit":{"path":"ORIGINAL_FULL_AUDIT","sha256":"PIN"},"field":"tokens_known","value":true}
```

생산 경로는 기존 `recompute_resource_audit`를 호출한다. 원 모델 request 디렉터리를 전수 발견하여 completed/failed 목록과 대조하고, 원 설정·소스·로그·모델 사용량 및 실패의 무행동/재개 계보를 재계산한다. 원 callback 등록 모델과 자원 조건도 일치해야 한다. `tokens_known`은 모든 입력·출력 토큰이 제공자 원 기록으로 확인되는지 나타내는 실제 bool이다. 누락된 실패 사용량은 알려진 0이 아니며, completed 토큰 하한을 전체 토큰으로 대체할 수 없다. 전체 원시 증거가 없으면 False를 추측하는 대신 검증이 실패하여 보류된다.

허용되는 원문은 다음 두 문장 또는 구조화 필드 `/resources/tokens_known`의 전체 `true`/`false` scalar다.

- `Token usage is known for all actual provider attempts.`
- `Token usage is not known for all actual provider attempts.`

다른 bool 필드에 붙여 성능 우수 주장으로 바꾸거나 시간 접두 사용량을 전체 값으로 바꾸지 못한다. 입력 `1`, `"true"`, null은 bool이 아니다.

`field="provider_billed_cost", value=null`은 `Provider billed cost is unavailable.` 또는 `/resources/provider_billed_cost`의 전체 null만 지원한다. 가격 산출 어댑터가 없으므로 금액 0·예상 가격·과금 총액을 승인하지 않는다. 기록에 금액이 있는데 unavailable이라고 부르는 것도 지원하지 않는다. 독립 리뷰의 시간·토큰은 별도 미계측 null이며 제공자 추론 자원에 섞지 않는다.

## 등록된 기존 결과 비교를 그대로 재계산한다

`registered_incumbent_criterion`의 arguments는 `run`, `baseline`의 원 `run_reference`, 원 `boundary` path/SHA, 실제 bool `success`다. 각 실행은 고정 verifier로 다시 검사한다. 등록 baseline ID, 값, 과제·분할·모델·코드·metric·자원·실행 조건이 일치해야 한다. 후보의 model evidence call ID/fingerprint가 원 boundary와 같고, baseline은 그 입력 이전의 실제 검증 목록에 있어야 한다. 미래 결과, 자기 자신 또는 다른 과제 결과를 기존 결과로 쓸 수 없다.

판정은 `Store.validate_spec`와 `Store._criterion_met`의 실행 코드로 수행한다. min/max 방향, absolute threshold가 같이 있을 때의 AND, strict baseline 개선량을 그대로 따른다. baseline과 동점이거나 개선량과 정확히 같은 차이는 채택되지 않는다. 이 predicate는 전체 후보의 최솟값이나 미래 개선을 보증하지 않는다.

원 문장은 다음 유한 셋이다.

- `Execution succeeded and the registered incumbent criterion was met.`
- `Execution succeeded and the registered incumbent criterion was not met.`
- `Execution failed; the registered incumbent criterion was not met.`

실행 성공과 기준 성공은 별도 facts이며, 결과 상태는 `criterion_success`, `criterion_rejection`, `technical_failure`로 구분한다. 실행 오류를 단순한 품질 기준 미달로 바꾸지 않는다. 확인되지 않은 오류나 미완료 실행은 고정 verifier를 통과하지 못한다.

## 원 제안문 연결은 내용의 사실성을 증명하지 않는다

새 nonresult_context `original_proposal_output`은 정확히 다음 필드를 요구한다.

```json
{"kind":"original_proposal_output","boundary":{"path":"ORIGINAL_BOUNDARY","sha256":"PIN"},"response":{"path":"ORIGINAL_RESPONSE","sha256":"PIN"},"field_pointer":"/candidates/0/hypothesis","prior_runs":[]}
```

C에서는 원 `PROPOSE`/`ImprovedArm.__call__` 역할의 완료 응답에서 `/candidates/N/hypothesis`, `/candidates/N/selection_reason`, `/candidates/N/assessment/rationale`, `/stop_reason`의 전체 문자열만 연결한다. B에서는 원 `plan formulation`/`agents.BaseAgent.inference`의 Postdoc 또는 PhD 역할에서 `field_pointer=""`로 원 response 전체를 연결한다. report/Paper 출력이나 다른 역할·단계는 계획으로 바꾸지 못한다. 이 단계 차이는 원 두 알고리즘의 실제 형식을 유지한다.

원 boundary의 전체 guard·설정·source·request fingerprint·terminal response 해시를 재검사한다. C JSON은 완전한 원 객체여야 하며 중복 key, 객체 외 추가 문장, 훼손된 코드 fence를 거부한다. 문자열은 그대로 일치해야 하고 문장의 일부만 떼거나 다른 call의 응답을 가져올 수 없다. 연결된 prior는 원 입력 이전에 있어야 하며 같은 실제 조건의 고정 verifier 증거로 검사한다.

이 경로는 **작성 경위와 미실행 계획 분류만** 허용한다. 기존 문장별 tentative/result/prior 및 한국어 부정 guards를 그대로 거친다. 예를 들어 `We propose next steps. Memory caused the improvement.` 또는 `The outcome was independently replicated.`는 원 응답에서 그대로 나온 문장이더라도 계획이나 측정 사실로 승인되지 않는다. 자원절·실제 오류 차이·인과·일반화·읽기 증명은 각각 해당 증거 predicate가 필요하며 없으면 보류 또는 거부다. 형식상 알려진 prior 표현 밖의 문구도 자동 확장하지 않는다.

원 hypothesis/rationale/stop 및 응답 파일을 유지하는 것은 필수적이다. 보고서에 인용·복사된 원 필드의 모든 비공백 내용은 기존 fullspan inventory에서 빠짐없이 분류해야 한다. authorship 경로로 임의 결과 문장을 `supported`로 만들 수 없으며, raw 제안에 남은 factual 주장도 독립 해석 책임의 대상이다.

## 구성 요소 검사는 실제 연구 판정과 분리한다

실제 `evaluate_predicate`에는 fixture 활성화 인자가 없다. `evaluate_fixture_predicate`와 `evaluate_fixture_nonresult_context`만 명시적인 합성 구성 요소를 검사한다. 새 자원 fixture 경로도 전체 source-bound terminal/context와 모든 request의 집합을 대조하고 원 설정·소스·순서를 검사한다. 정상 값이어도 항상 `synthetic_fixture`/`synthetic_engineering_fixture`, `adoption_eligible=false`이다. 누락된 시간 계보 같은 다른 오류를 합성이라는 이유로 무시하지 않는다.

원 `fixture_only`, `simulation_only`, `test_fixture_only`는 명시 bool이어야 한다. True 또는 합성 실행 종류는 실제 자격으로 승격하지 않으며 null/string/int 같은 불량 표지도 거부한다. 생산 리뷰는 caller의 cached facts/자격을 믿지 않고 원 predicate를 다시 계산한다. 전체 보고서가 계획뿐이어도 arm의 합성 출처를 실제 보고서로 바꾸지 못한다.

`tests/test_semantic_evidence_c9.py`는 별도로 명시된 합성 transport와 6 train/3 validation 공개 행만 사용한다. 새 실제 provider·원 owner 데이터·연구 실험은 사용하지 않는다. 작성자의 PASS는 외부 독립 13-family 검증이나 실제 연구 효과의 증거가 아니다. 실행 실패와 수정은 `work/c9-semantic-implementation-v1` 새 attempt별로 보존한다.
