# 연구 진행 보고서

2026-10-02(Asia/Seoul). Goal은 진행 중이며 최종 개선 판정은 보류다.

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
| 실제 모델 제안 실험 | validation MSE 0.012638906669511679 | `evidence/model-development/evidence/bbe438e4943ebb772dc9f0e2/` |
| 원본 adapted 개발 실행 | 같은 설정의 실제 측정 MSE 0.012638906669511679; 과제 지표 향상 미입증 | `runs/development/B-upstream-dev-quadratic-seed7-literature/independent_review/verified_experiment_evidence.json` |

위 수치는 서로 다른 검증 목적의 개발 기록이다. 실제 모델 C와 원본 B의 완결된
사전 등록 최종 비교나 연구 기억 성능 향상으로 대체하지 않는다. B의 전체 보고서
작성은 일시적인 모델 용량 부족으로 중단된 후 완료됐다. 원본 기록을 보존한
`runs/development/B-upstream-dev-quadratic-seed7-resumed/development_result.json`에
재개 계보와 최종 보고서 해시가 있다. 재개 중 새 CPU 실행은 없었다. 전체 보고서의
수치 주장은 독립 검토 중이며, 보고서 생성 성공만으로 과제 개선을 판정하지 않는다.

독립 평가 도구는 별개 train/validation/test, 고정 구현·평가 해시, 실제 예측의
수치 재계산과 모델 호출 감사 증거를 요구한다. 과제·모델·seed·도구 권한·자원
예산을 맞춘 원본 B와 개선 C를 주 비교로 삼는다. 현재 모델 계열이 원 연구 모델과
다르지만 A를 실제로 실행하기 전에는 모델 발전 효과를 추정하지 않는다.

현재 병목은 같은 조건의 개발 pilot과 보고서 수치 검토를 완료하고, 관찰한 pilot
분산에 따른 최종 표본 설계를 고정하는 것이다. 아직 기존 대비 개선을 입증하는
최종 B/C 결과는 없다. 실패한 단계와 자원 제약은 원인별로 저장해 다음 설계에
반영한다. 목표에 맞춘 기준을 실행 후 완화해 성공을 선언하지 않는다.

현 범위는 고정 CPU 회귀 과제다. 임의 생성 연구 코드의 안전한 실행, AgentRxiv의
원본 PDF 서버 전체 재현, MATH-500 논문 성능 재현과 일반 과학적 발견 성능은
추가 실행·검증이 필요하다. 외부 연구 서버에 결과를 업로드하지 않는다. GitHub
게시 대상은 사용자가 지정한 열린 브라우저 계정 `Malko-opensource`다.
