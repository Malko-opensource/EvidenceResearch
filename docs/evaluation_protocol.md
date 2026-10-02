# 독립 평가와 사전 등록

현재 구현은 실제 CPU 다항 회귀 연구 과제를 실행한다. 후보자는 `degree`(1~8)와
`alpha`(0~100)만 제안한다. 실행기는 학습 자료에만 적합하고 검증 자료로 후보를
선택한다. 보류 테스트 정답은 평가 소유자가 보관한다. 임의 생성 코드는 실행하지
않는다. 새로운 실험 코드가 필요하면 외부 OS sandbox와 별도 검토가 필요하다.

## 증거 계약

`tasks.make_spec(...)`는 실행 전에 과제/구현/평가 버전, 데이터와 분할 해시, seed,
설정, 모델 식별자, 허용 도구/자원, 가설, 지표와 채택 기준을 확정한다.
`run_task(spec, run_dir)`는 등록 설정, 실제 로그, 학습/검증 관측치, 모델 계수,
예측과 그 SHA-256 해시를 저장한다. 실패 역시 로그와 해시를 저장한다. 같은 완료
경로의 덮어쓰기는 거절한다. 연구 Engine의 등록 해시와 재개 기능을 함께 사용한다.

`verify(spec,result,run_dir)`는 파일 해시와 등록 설정을 확인하고 실행기의 Gaussian
elimination과 별개인 중심화 + Cholesky 해법으로 계수를 재현한다. 저장된 예측으로
MSE를 독립 재계산하고 분할 중복, 테스트 노출, 수치 주장과 원본 증거 연결을
검사한다. 검증 완료 전 결과는 최선의 결과가 될 수 없다. 이 프로세스 분리는
임의 셸을 가진 공격자를 막는 보안 sandbox가 아니다. 모델 제공자는 평가/비공개
파일을 읽는 도구를 제공해서는 안 된다. 현재 로컬 Codex bridge는 공개 전용 cwd,
읽기 전용 sandbox와 도구 금지 지시를 사용한다. 파일 읽기가 OS 수준에서 불가능하다고
주장하지 않는다. 원본 JSONL에서 tool item이 관측되면 해당 실행을 무효화한다.
엄격한 비공개 격리에는 file tool 없는 원격 API나 별도 container가 필요하다.

## B 대 C와 모델 효과

B는 원 Agent Laboratory + 현재 실제 가용 모델, C는 개선 프레임워크 + **같은**
모델이다. 모델 식별자, 각 짝의 과제/seed/학습·검증·테스트 분할, 도구 권한,
제안 호출 예산과 자원 범위를 맞춘다. 원본 호출을 수정해 연결하면 수정 내역과
원본 commit을 `upstream_adaptation`으로 기록한다. 흐름만 흉내 낸 기준선은
`structural_baseline`이며 원 프레임워크 비교라고 보고하지 않는다.

A(원 연구 계열 모델)는 실행 가능할 때만 별도 비교한다. 모델이 없으면 `unavailable`
이유를 기록하고 논문 수치로 A 실행을 대체하지 않는다. B/C만으로는 모델 발전 효과를
측정할 수 없으며 해당 효과는 미확인으로 남는다.

## 평가 설계와 반복 수

개발 과제와 최종 과제는 별개다. 개발 짝 결과의 상대 개선
`(B MSE-C MSE)/max(B MSE,1e-12)`로 분산을 추정한다.
`design_sample_size`는 유의수준 단측 0.05, 검정력 80%, 의미 있는 평균 개선 10%,
평균 구간 반폭 5%를 계획값으로 사용한다. 표본분산 상대 표준오차 50% 이하를
요구하므로 최소 pilot 자유도는 `2/0.5²=8`, 즉 9개 개발 짝이다. 최종 반복 수는
검정력과 정밀도 요구 중 큰 값을 채택한다. pilot 분산이 0이어도 효과 크기의
절반을 계획 표준편차의 하한으로 두므로 완전한 확실성을 가정하지 않는다.
정규 근사는 설계 가정이며 실제 변동성을 보장하지 않는다. 이 숫자는 **평가
표본 설계**이며 연구 루프 전체의 실행 횟수나 실패 한도가 아니다.

평가 소유자는 `create_final_suite`로 새 과제 정의와 고정 분할을 생성하고
`register_protocol`로 실행 전에 표본 수, 코드 해시, 모델, 예산, 채택 기준을 저장한다.
최종 주 지표는 보류 test MSE이다. 각 짝을 재표집한 percentile bootstrap 95% 구간을
제공한다. 재표집 횟수는 2.5% tail의 Monte Carlo 95% 오차 목표 0.005에서 계산한다.
평균 상대 개선 ≥10%, 구간 하한 >0, 모든 짝과 검증 증거 존재, 동일 권한/예산,
근거 없는 수치 주장 0을 동시에 만족해야 채택한다. 성공률의 개별 성공은 고정
degree=1, alpha=0 참조보다 test MSE가 15% 이상 낮은 경우다.

소요 시간, provider 호출, 알 수 있는 실제 비용, 중복 실행, 오류 복구, 근거 없는
주장, 검증된 기억 활용은 보조 지표로 함께 보고한다. 구독 사용량을 임의의 달러
가격으로 환산하지 않고 실제 비용을 알 수 없으면 null로 둔다. 추가 비용/자원
요구가 기존 허용 범위를 넘으면 필요한 수량을 먼저 계산해 사용자에게 요청한다.

## 실행·재개와 오염 방지

최종 평가 진입점은 `run_matched(protocol_path,output_dir,baseline=...,improved=...)`다.
두 callback에는 공개 학습·검증 자료와 도구 schema만 주며 테스트 행, 비공개 파일
경로와 정답 정의를 주지 않는다. 각 callback은 검증 가능한 선택 실행 경로,
모델 실제 호출 trace, 정확한 모델 식별자와 자원 회계를 반환해야 한다. 완료된
짝/arm은 해시와 protocol lock으로 재사용하여 재개 시 모델을 중복 호출하지 않는다.

개발 smoke, 임시 fixture 단위검사와 구조 기준선 비교는 최종 연구 성능 증거가 아니다.
최종 결과를 보고 코드를 수정하면 해당 suite는 개발 자료가 된다. 새 버전과 새
최종 과제를 다시 고정한다. 채택 실패 시 기준을 완화하지 않고 실패 조건과
불확실성을 연구 기억에 남기고 설계를 개선한다. 최종 평가를 반복해서 유리한
결과만 고르는 것은 허용되지 않는다.

회귀 benchmark의 개선은 해당 CPU 과제에만 적용된다. 실제 문헌 조사·과학적 발견
전체의 품질 향상은 별도의 과제와 독립 평가 없이는 주장할 수 없다.

## 별도 VERSION 4 효율성 확인 설계

최종 사전 등록 전에 주 가설을 계산 자원 효율로 정하면
`design_efficiency_sample_size`와 `register_protocol(endpoint='efficiency')`를 사용한다.
주효과는 실제 provider `input_tokens + output_tokens`의 상대 절감이다. cached input은
input에 이미 포함되므로 중복 합산하지 않는다. 가격 가중치가 없는 자원 지표이며
달러 비용 절감으로 부르지 않는다.

기본 실질 절감은 20%, 계획 대립가설은 50% 절감이다. 이 값은 사전 설계 가정이며
측정된 개선이 아니다. 절감의 paired 95% bootstrap 구간 하한이 20%를 넘고, 보류
test MSE의 `log(C/B)` 구간 상한이 `log(1.10)`보다 작아야 한다. 즉 benchmark 품질의
상대 악화를 10% 이내로 제한하면서 자원 절감을 입증한다. 10%는 이 좁은 benchmark에서
선언한 허용오차이며 모든 과학 연구의 품질 허용치가 아니다. 최종 실행 전에 확정한다.

비용 절감과 품질 비열등성을 **모두** 요구하는 intersection-union 판정이다. v1 품질
개선 또는 효율 중 유리한 쪽을 골라 성공이라고 하지 않는다. 양쪽 pilot 분산으로
표본수를 별도 계산하고 큰 수를 고정한다. 품질 계획 가설은 `log(C/B)=0`이다.

모델 호출·토큰·시간은 원본 completion JSONL와 provider artifact hash로 재계산한다.
`model_request_audit`는 완료·실패 요청의 실제 model/explicit reasoning effort를
등록 envelope와 대조한다. 원본 fingerprint, 정확한 guard 포함 full prompt,
provider source hash와 CLI model/effort/read-only/ignore-user-config/ephemeral/JSON/
approval-never/public-cwd/stdin/response-path 설정을 검사한다. 모델 이름이 같다는
이유로 서로 다른 추론 설정을 같은 자원으로 인정하지 않는다. 서버 weight 버전과
모델 sampling seed가 노출되지 않는 한 동일하다고 주장하지 않는다.

양쪽은 `actual_cpu_executions_per_unit`라는 같은 CPU 실행 예산을 등록한다.
이 개발 설계의 51은 등록된 proposal 자원/최대 host 후보 행동에서 유도한
**과제별 비교 자원**이며 Goal 루프 횟수 제한이 아니다. callback inventory와 arm
폴더의 원본 실행 자료를 별도로 대조한다. 성공·실패 CPU 호출을 모두 포함하고
parser가 거절한 제안은 실제 실행으로 세지 않는다. 선택 후보의 시간은
`selected_execution_seconds`, 모든 실제 CPU 시도의 시간 합은
`total_cpu_execution_seconds`로 별도 보고한다. cached 모델 응답의 transport
event를 실제 새 호출이나 새로운 provider 시간으로 다시 합산하지 않는다.

provider 토큰 지표는 연구 실행 provider의 추론 자원이다. framework 구현,
상위 작업 에이전트의 대화/추론, 독립 의미 검토의 비용을 포함한 전체 개발 비용으로
부르지 않는다. 독립 수치 검토의 시간·토큰이 직접 계측되지 않으면 null로 기록하고
0으로 가정하지 않는다. 이 비용 범위는 최종 사전 등록에서 고정한다.
중복·복구·기억 활용 보조 수치는 host audit와 원본 event 파일에 연결한다.
실행·검증 실패는 immutable owner receipt로 남기고 성공률 분모에서 제외하지 않는다.
한 arm 실패가 나머지 독립 과제의 실행을 지우지 않는다. 외부 모델 자원 부재는
실험 실패와 구분하고 동일 자원이 없는 상태에서 추가 모델 호출을 하지 않는다.
재개 시 완료 arm과 실패 receipt의 해시를 검사하며 자동 재실행하지 않는다.

현재 개발 버전은 `paired-efficiency-4-conservative-bound-report-contract`다.
이 규칙은 최종 실행 전에 별도 사전 등록해야 하며 과거 v2/v3 사전 등록 파일을
소급 변경하지 않는다. 완료 요청과 definite 실패 요청의 횟수와 소요 시간을 모두
합산한다. 실패에는 원본 `turn.failed`, 도구 행동 없음, 호스트 행동/응답 소비 없음,
정확한 모델·요청 fingerprint, 해시와 명시적 재개 lineage가 필요하다. 불명확한 실행
상태를 실패 완료로 간주하지 않는다. 토큰 사용량을 제공하지 않은 실패는 null로 남긴다.

C의 전체 토큰이 알려져 있고 B의 실패 토큰만 미지인 경우, B 완료 요청 토큰 합을
`B_known`이라는 **하한**으로 사용한다. 비음수 미지 사용량에 대해
`1-C_total/B_known <= 1-C_total/B_true`이므로 각 짝 절감률도 보수적 하한이다.
같은 bootstrap 재표집 index에서 표본평균과 percentile 끝점은 이 단조성을 유지한다.
따라서 하한으로 계산한 구간이 채택 기준을 넘으면 해당 절감 기준을 보수적으로
충족하지만, 실제 토큰 비용이나 정확한 절감률을 측정했다고 쓰지 않는다. 이 논리는
bootstrap의 근사·독립 표본 가정을 제거하지 않는다. C의 미지 사용량은 절감률 분자의
상한을 알 수 없게 하므로 효율 판정이 inconclusive다. 미지 토큰을 0으로 대체하지 않는다.

pilot도 최종 실행과 같은 운영 정책을 사용한다. 임의 절대 MSE threshold로 조기
종료한 기존 smoke는 최종 정책의 분산 추정값에 섞지 않는다. 서로 다른 regime의
자료 seed를 따로 두며 B/C 각 짝만 같은 seed와 split을 사용한다. 서로 다른 seed가
통계적 독립을 증명하지는 않으며 독립 짝이라는 표본 설계 가정을 명시한다.

## 양쪽 보고서의 공통 필수 내용

효율 비교에서 B의 긴 원본 보고서와 C의 짧은 요약 때문에 필수 연구 내용을
생략한 절감을 채택하지 않는다. 양쪽 모두 `research-report-sufficiency-1` JSON
companion을 제공한다. 목표·가설·선택 설정·선택 근거, 과제 버전/seed/split/source/evaluator
해시, 실제 실행 entrypoint와 별도 재현 명령, 실제 지표와 원본 증거 해시, 미해결
질문/실패 이유, 한계, 문헌 주장/URL, 자원 회계의 알려진 범위와 다음 질문을 요구한다.
`verify_report_contract`는 선택 실행의 독립 검증 지표와 설정/출처/증거를 대조한다.
스키마만 채우거나 LLM이 스스로 성공이라고 판정해서 통과할 수 없다.

원본 보고서와 companion의 수치 주장은 각각 별도 inventory와 독립 review를
만들고 host telemetry의 `report_review_paths=[{path,sha256},...]`에 연결한다.
검토 범위는 `whole_report_and_companion_numeric_inventories`다. 두 보고서 모두
필수 정보와 전체 숫자 검토를 통과해야 효율 개선을 채택한다. 이 검사는 공통 정보
충족을 확인하며, 문장 품질·독창성·과학 연구 전체의 품질이 동등하다고 주장하지 않는다.

## 보고서 수치의 별도 독립 판정

`prepare_numeric_review(report_path,inventory_path)`는 보고서의 decimal/scientific
숫자 출현을 문맥·행·claim ID로 목록화한다. 문헌 번호·방법 수식도 자동으로 사실로
간주하지 않는다. 독립 판정자는 `adjudicate_numeric_review(...,
reviewer_role='independent_verifier')`에 measured/literature/method/identifier/
inference/proposal/unsupported 구분과 근거를 제공한다. 실제 측정 주장은 해당 실행을
다시 검증하고 표시 정밀도를 고려해 수치가 독립 지표와 일치하는지 확인한다.
토큰·provider 시간·요청 횟수·실제 CPU 시간은 `measured_resource`로 구분한다.
독립 판정자는 `resource_audit_path`와 `resource_metric`을 연결하며 평가기는
`independent-resource-audit.json`의 실제 요청 디렉터리, 실패 lineage와 CPU
inventory에서 자원 수치를 다시 계산한다. 측정된 자원을 method 설정이나
문헌 주장으로 분류하지 않는다. 미지 토큰 총량은 측정값으로 채택하지 않는다.
분류되지 않은 수치는 pending이며 근거 없는 주장 0이라고 간주하지 않는다.

이 도구는 원본 prose의 의미를 완전 자동 판정하지 않는다. 의미 분류와 숫자를
단어로 쓴 문장은 독립 검토가 필요하다. 구조화된 metric 주장 감사만 완료했으면
그 범위를 명시하고 전체 보고서 사실 검증 완료를 주장하지 않는다.

## 실행 당시 소스로 재현

각 실행의 `source/evidence_research/`에 정확한 tasks.py/verifier.py와 최소 package
파일을 저장하고 해시를 증거 manifest에 포함한다. 실제 실행 entrypoint는
`in_process:evidence_research.tasks.run_task(spec,run_dir)`다. `reproduction_command`는
별도 새 디렉터리에서 쓰는 명령이며 과거 실제 셸 실행이라고 표시하지 않는다.
소스 archive를 `PYTHONPATH`로 지정해 이후 버전과 분리하여 재현한다. 경로/시간은
재현 때 달라질 수 있으나 데이터/설정/모델/예측/지표의 결정성은 확인한다.
