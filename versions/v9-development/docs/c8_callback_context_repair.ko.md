# c8 callback 조건 전달의 전향적 수정

이 문서는 사전등록 `work/c8-method-registration-v1.json`에 따른 개발 변경을 설명한다. c8 패키지 식별자는 `0.4.1.dev0`이다. 이전 v7 소스와 이미 기록된 실행·보고서·독립 판정은 변경하지 않는다. c8의 연구 향상이나 전체 Goal 달성을 주장하지 않는다.

고정 v7 B writer는 `callback-registration.json`에 최상위 `model_id`와 `resource_envelope`를 기록하지 않았다. 독립 ContextBoundary auditor는 그 두 필드와 public task, reasoning effort, 실행 소스의 일치를 요구한다. Recorder는 별도 인자를 받았지만 원래 callback 기록과의 불일치를 요청 전에 검증하지 않았다. 이 때문에 기록은 생성되었어도 원래 감사 계약을 통과하지 못했다. 과거 결과는 해당 고정 기준에서 그대로 남긴다.

c8에서는 B writer가 최초 payload의 모델과 전체 resource envelope를 C와 같은 필드로 기록한다. Recorder 생성, provider 입력 capture 및 보고 단계 snapshot 전에 원래 등록 링크/SHA, model, public task 전체 해시, resource envelope 전체 해시, 명시적 reasoning effort와 실행 소스 8개를 검사한다. 필드 누락·변경·잘못된 소스는 기록 전에 거부한다. provider 객체의 실제 요청 모델/effort도 capture 전에 대조한다. 독립 auditor는 동일한 조건 검사 함수를 사용하며, 기존 raw request/CLI/guard/source/prefix/ordinal/CPU/합성 자격 검사를 계속 수행한다. 후속 binding에서 누락 필드를 채우는 경로는 없다.

수정 범위는 B 등록 writer, ContextBoundary의 같은 계약을 일찍 검사하는 코드, 패키지 버전, 새 통합 검사 및 이 개발 문서이다. native upstream 단계·프로토콜·프롬프트·reward·공통 실행 권한·실제 task/evaluator·semantic predicate는 바꾸지 않는다. 20% token CI와 10% MSE 비열등성, 양쪽 numeric/semantic 전체 검토 및 실제 증거 자격 요건은 그대로이다. `source_facts_c7.json`은 문헌 corpus/record SHA를 묶으며, 이 두 module의 SHA를 직접 pin하지 않는다. 문형·사실 registry·문헌 핀은 수정하지 않았다.

새 `test_callback_context_handoff.py`는 실제 `UpstreamArm.__call__`의 등록 writer와 pinned native 초기 문헌 단계, 실제 `ImprovedArm.__call__`의 초기 제안 경로를 실행한다. provider만 합성 raw receipt writer이다. hand-authored public 배열을 사용하며 task generator나 owner 자료를 읽지 않는다. 각 fixture는 모델 요청 2회의 명시적 시험 자원 allowance에서 끝나고, CPU config는 제출하지 않는다. 정상 연구 pipeline 완료를 시험한 것이 아니다. 두 번째 원래 입력의 prefix는 양쪽에서 같은 합성 completed call 1개를 포함하고, 같은 측정값으로 정규화되지만 `eligible=False`와 합성 판정을 유지한다.

구현자 첫 검사 `attempt-0001`은 새 13개 중 문헌 프로토콜의 시험 인자 순서 오류 1개로 실패했다. 해당 source/log/receipt는 보존했다. 올바른 keyword 인자로 수정한 `attempt-0002`에서 새 13개가 통과했고, `attempt-0003`에서 기존 ContextBoundary 24개가 통과했다. 이 37개는 각각의 성공한 범위를 한 번씩 실행한 구성 검사다. 실제 provider·CPU fit·task generator·private owner·subprocess 가드 횟수는 모두 0이며, 검사 전후 candidate 실행 소스 및 고정 v7 source108 해시가 같았다. 구현자의 Python 가드는 OS 전체 접근 계측을 대신하지 않는다.

사전등록한 10개 family는 native B/C 전달, 과거 형식 누락 재현, 개별 필드 누락, 모델/effort/envelope 변경, 일관 재해시 공격과 기존 prefix/합성 자격 회귀를 포함한다. 추가 public-task/source-implementation 변경, receipt 사후 변조와 provider 설정 변조도 거부한다. 독립 담당자가 새 고정 소스에서 해당 family를 실행하고, 전체 회귀와 새 환경 검증을 완료해야 다음 실제 개발 실행을 준비할 수 있다. 이 문서는 실제 실행이나 새로운 평가 과제 생성 권한이 아니다.

이 검사는 trusted host가 보존한 원래 등록과 raw receipt의 조건·순서·해시 일치를 확인한다. 공격자가 모든 trusted host 기록과 외부 등록 핀을 교체해 허위 실제 실행을 만들 수 없는 암호학적 출처 증명이라고 주장하지 않는다. 합성 fixture와 과거 불완전 evidence는 실제 결과 채택에 사용하지 않는다. forward repair를 묶어 재실행하더라도 모델 교체 효과와 framework 효과를 분리하는 새 사전등록 비교·독립 final 평가가 별도로 필요하다. A 모델 계열의 효과는 현재 추정하지 않는다.
