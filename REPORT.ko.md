# 연구 진행 보고서

2026-10-03(Asia/Seoul). Goal은 진행 중이며 최종 개선 판정은 보류다.

원문 PDF·HTML과 현재 업스트림 코드 commit을 직접 검토했다. 논문 수치는 문헌
주장으로만 취급한다. 원본 단계·agent·solver·LLM 심사 구현을 실행하는 어댑터를
만들었고, 도구·문헌·모델 연결에 필요한 대체 내역을 별도로 기록한다.

개발용 실제 모델 호출과 CPU 실험이 성공했다. 실행 증거는
`evidence/model-development/`에 보존한다. 성공·실패 기억, 실제 오류 원인 재현,
증거에 따른 설정 변경, 완료 실행과 중단 후 재개의 중복 방지, 변조 거절은
`evidence/core-validation-final/report.json`과 실행 원장에서 확인할 수 있다.
개발 도중 코드가 수정된 기록은 해당 시점의 코드 해시를 보존하며, 다른 버전에서
검증한 결과와 혼합하지 않는다. 개발용 확인은 최종 평가가 아니다.

| 검증된 개발 확인 | 관찰 | 원본 증거 |
| --- | --- | --- |
| 실제 CPU 기능 검사 | 실행 5회, 중복 실행 0회, 기능 검사 9개 통과 | `evidence/core-validation-final/report.json`, `runner-invocations.json` |
| 고정 소스로 재실행 | 관찰값·실행 ID·소스 해시 일치 | `evidence/core-validation-final/reproduction-check.json` |
| 공개 저장소의 독립 설치 | 별도 clone·venv에서 원본 35개 파일 검증, 51개 검사 통과, 당시 소스의 CPU 관찰값 일치 | `evidence/install-validation/report.json`, 각 단계의 해시 연결 로그 |
| 실제 모델 제안 실험 | validation MSE 0.012638906669511679 | `evidence/model-development/evidence/bbe438e4943ebb772dc9f0e2/` |
| 원본 adapted 개발 실행 | 같은 설정의 실제 측정 MSE 0.012638906669511679; 과제 지표 향상 미입증 | `runs/development/B-upstream-dev-quadratic-seed7-literature/independent_review/verified_experiment_evidence.json` |

위 수치는 서로 다른 검증 목적의 개발 기록이다. 실제 모델 C와 원본 B의 완결된
사전 등록 최종 비교나 연구 기억 성능 향상으로 대체하지 않는다. B의 전체 보고서
작성은 일시적인 모델 용량 부족으로 중단된 후 완료됐다. 원본 기록을 보존한
`runs/development/B-upstream-dev-quadratic-seed7-resumed/development_result.json`에
재개 계보와 최종 보고서 해시가 있다. 재개 중 새 CPU 실행은 없었다. 전체 보고서의
수량 표현 248개를 독립 검토했으며, 실행 횟수의 범위가 불명확한 표현 하나는 보류했다.
판정과 근거는 `independent_review/full-report-review-v2/comprehensive_numeric_adjudication.json`에
있다. 보고서 생성 성공만으로 과제 개선을 판정하지 않는다.

독립 평가 도구는 별개 train/validation/test, 고정 구현·평가 해시, 실제 예측의
수치 재계산과 모델 호출 감사 증거를 요구한다. 과제·모델·seed·도구 권한·자원
예산을 맞춘 원본 B와 개선 C를 주 비교로 삼는다. 현재 모델 계열이 원 연구 모델과
다르지만 A를 실제로 실행하기 전에는 모델 발전 효과를 추정하지 않는다.

진행 중인 pilot은 원본 단계의 최소전이 설정을 사용한다. 원본 권장 설정과
반복·문헌 수가 달라 원본 권장 방식 대비 개선의 주 비교로 해석할 수 없다.
현재 등록과 증거를 보존하고 개발 진단으로 분류한다. 다음 별도 비교는 원본
권장 설정과 같은 모델·도구·충분한 공통 자원을 등록하고 자체 pilot 변동성으로
최종 표본을 설계한다. 별도의 기억 ON/OFF 진단도 실제 모델 수집을 시작했으나
효과 판정은 아직 없다. 아직 기존 대비 개선을 입증하는
최종 B/C 결과는 없다. 실패한 단계와 자원 제약은 원인별로 저장해 다음 설계에
반영한다. 목표에 맞춘 기준을 실행 후 완화해 성공을 선언하지 않는다.

최소전이 pilot의 첫 짝은 양쪽 실제 CPU·모델 기록과 보고서의 수치 검토를
마쳤다. 원시 토큰은 B 761,923개, C 1,522,689개로 C가 더 많았다. 별도 test
MSE는 B 0.005875021578368766, C 0.0056166178927978755였다. 이 한 개발 짝은
모집단 개선이나 원본 권장 설정 대비 효과의 증거가 아니다. 계산식·원본 검증·
소스 해시는 `evidence/paired-development-first/result.json`에 있다. v4의
`recovered_errors`는 두 arm의 정의가 달라 오류 복구 효과로 보고하지 않는다.
기억 ON/OFF pilot은 9개 짝에서 양쪽 중복 제안이 모두 없었다. 효과를 관찰하지
못한 결과를 보존하며, 이산 희소 사건에 대한 확인 설계는 별도로 검토한다.

현 범위는 고정 CPU 회귀 과제다. 임의 생성 연구 코드의 안전한 실행, AgentRxiv의
원본 PDF 서버 전체 재현, MATH-500 논문 성능 재현과 일반 과학적 발견 성능은
추가 실행·검증이 필요하다. 외부 연구 서버에 결과를 업로드하지 않는다. GitHub
게시 대상은 사용자가 지정한 열린 브라우저 계정 `Malko-opensource`다.
