c9p1은 구현 전에 등록한 최소 ContextBoundary 무결성 수정이다. 패키지 식별자는 `0.5.0.dev1`, 경계 schema는 `original-context-boundary-2-local-binding-development`이다. 원 c9 source123 및 실제 연구·독립 실패 결과는 보존한다. 이 문서는 구현 설명이며 테스트 또는 설치·릴리스의 성공 증거가 아니다.

Recorder가 원 `context-boundaries/binding.json`을 저장할 때 받은 path/SHA 연결을 후속 capture와 report-era에 함께 저장한다. 감사 함수와 모든 prefix input은 그 연결의 정확한 원 위치·SHA 및 전체 canonical value를 확인한다. normalized evidence에도 연결을 포함한다. 이후 registration과 boundary를 함께 재해시해도 남아 있는 원 binding을 사용하지 않던 누락을 보강한다. 원 schema나 원 binding이 없는 자료를 새 증거처럼 소급 수리하지 않는다.

실제 공개 bundle이 있는 registration은 capture 이전과 audit 양쪽에서 기존 `tasks.registered_data`의 row/ID/count/identity 검사를 사용한다. 최소 spec에는 `task_bundle`을 반드시 넣으므로 해당 함수의 legacy `task_data` 생성 경로로 내려가지 않는다. fitting·owner test 행·private definition·seed 접근이나 새로운 metric 계산을 추가하지 않는다.

bundle 자체가 없는 legacy input은 원 source-bound 처리로 남는다. 정확히 `{'kind':'explicit_synthetic_fixture'}`인 opaque engineering marker는 원 binding/registration에 유효한 명시 fixture qualification이 있을 때만 허용한다. 이 표지는 공개 rows를 뜻하지 않으며 fixture facts의 actual eligibility를 켜지 않는다. qualification이 없는 caller가 나중 raw request에 alias를 넣어 capture를 통과시키는 것은 허용하지 않는다. 추가 row key, 다른 marker 또는 불완전한 실제 bundle은 이 예외를 사용하지 않는다.

기존 `test_context_boundaries.py`의 raw qualification alias 전파 검사는 목적과 최종 expected assertions를 유지한다. 기존 setup이 qualification 없는 opaque marker를 먼저 만들던 부분만 no-bundle legacy 입력으로 바꾼다. 해당 조건을 통해 raw aliases 자체의 전파를 검사할 수 있으며, 무자격 marker→나중 alias 우회는 새 negative로 따로 기록했다. 이것은 실패 결과를 pass로 다시 이름 붙이거나 fixture를 실제 측정으로 승격하는 변경이 아니다.

새 `test_context_original_binding.py`는 유효 B/C prefix와 원 binding evidence, 누락·바이트변조·전체값변조·잘못된 위치, registration/task/model/resource 재해시, 이후 capture 차단, 모든 prior input 연결, 공개 rows/ID/count/identity 및 불완전 bundle, audit 시점 데이터 무결성, legacy 무생성, qualified/unqualified marker 및 이전 schema 거절을 검사하도록 작성했다. 합성 provider receipt와 공개 literal 행만 쓰며 CPU fit과 실제 provider를 실행할 코드 경로를 추가하지 않았다. 테스트는 별도 root GO 전까지 실행하지 않는다.

원 binding은 로컬 무결성 앵커이며, 모든 metadata와 외부 evidence pin을 함께 다시 쓸 수 있는 host에 대한 외부 attestation이 아니다. 실제 owner preregistration의 공개 파일/hash와 모든 CPU 결과의 독립 검증은 계속 필요하다. 이번 발견은 합성 조건 rejection failure이며 실제 adoption 우회로 실증한 것이 아니다.

B/C의 연구 알고리즘·모델 입력·도구/모델/effort·resource 조건, task/verifier 수치, numeric/semantic predicates, 20% token CI·10% MSE AND 기준과 별도 fresh final 요구는 변경하지 않는다. 실제 우수성·보고서 완전성·목표 완료는 이 수정만으로 입증되지 않는다. 독립 forward 판정과 전체 회귀, 그 뒤 별도 자체 환경·릴리스 결정이 필요하다.
