# v7 개발 버전과 설치 증거

`versions/v7-development`는 공통 입력 경계와 증거 자격 검사를 추가한 `0.4.0.dev0` 개발 버전이다. 기존 연구의 보고서·판정·실행은 보존한다. 실제 연구 개선과 별도 최종 평가는 아직 완료되지 않았으며 Goal은 active다.

현재 알려진 결함은 B callback 등록 계약의 불일치다. `evidence_research/arms.py`의 등록 writer에는 최상위 `model_id`·`resource_envelope`가 없지만, 같은 고정 버전의 `context_boundary.py` 검사는 두 필드를 요구한다. Recorder의 별도 binding에 값이 있다고 해서 원래 callback 계약을 충족한 것으로 취급하지 않는다. v7 보고서의 해당 경계 판정은 유지하며 검증된 B/C 개선 근거로 채택하지 않는다. 별도 사전 등록한 개발 사본에서 writer 계약과 callback부터 auditor까지의 통합 검사를 수정한다. 기존 기준·원본 증거를 바꾸지 않는다. 공학 검사의 통과와 실제 경로의 계약 충족은 별도로 판정한다.

새 독립 `.venv`에서 오프라인 editable 설치와 전체 263개 검사가 통과했다. 설치 후 자체 패키지 경로와 버전을 확인했고 user site는 비활성화됐다. 실행 명령, 원시 로그, 시간과 해시는 [설치 결과](../versions/v7-development/validation/release-local-v1/result.json)와 [검사 영수증](../versions/v7-development/validation/release-local-v1/unit-checks.json)에 연결돼 있다. 검사 단계의 wall time은 48.063초이며 모델 호출과 실제 연구 비교는 포함하지 않는다.

별도 담당자의 고정 소스 재현에서 사전 등록 36개 사례와 추가 회귀 2개가 통과했다. [독립 결과](../work/c7-independent-validation-v1/result.json), [원시 검사 로그](../work/t7/rctx0003/tests.log), [재현 코드](../work/c7-independent-validation-v1/held-source-run-0003/fixture-snapshot/reproduce_components.py)를 연결했다. [84개 공개 subset](../work/c7-release-preparation-v1/independent38-exact-subset84-v1.json)은 최신 38개 사례의 완전한 소스·fixture 재현 경로와 추가 판정 5개·작성 코드 5개를 제공한다. 전체 원래 manifest 255개 파일이나 생성된 합성 산출물 487개의 본문을 모두 공개·전수 감사했다는 뜻은 아니다. 일부 추가 판정 코드에는 원래 로컬 경로 의존성이 남아 있어 다섯 sidecar 전체의 독립적인 portable 재실행을 주장하지 않는다. 보존된 원본 실패도 최신 성공으로 덮어쓰지 않았다.

소스 기준 108개 중 106개는 검증된 기준과 동일하고, 두 설명 문서만 공개 범위로 파생했다. 원본·파생 SHA는 [복사 영수증](../versions/v7-development/release-copy.json)에 보존했다. 검사 전후에 새 소스 108개와 보호된 기존 source/test/static-reference 309개가 일치했다. 이 목록은 소스 경로와 해시이며 기존 연구 산출물이나 비공개 평가 행을 포함하지 않는다. 현재 패키지는 20개 모듈과 고정 참조 38개를 사용한다. 상속된 c6 문서의 패키지 수 19개는 해당 과거 버전의 설명으로 읽어야 한다.

부모 Python audit hook은 이 저장소 내에서 새 릴리스·검증 폴더·명시적인 합성 임시 폴더를 제외한 접근을 검사했다. 허용된 CPU 구성 검사 child는 1개였으며 그 child는 부모 hook의 범위 밖이다. 이 기록은 운영체제 전체의 격리를 입증하지 않는다. `doctor`는 해당 sandbox에서 실제 모델 인증을 확인하지 못했으며, 모델 접근은 실제 완료 영수증으로 별도 확인해야 한다.

공통 ContextBoundary는 원래 모델 요청에 들어간 값과 그 요청 전에 완료된 실행 이력을 구분한다. 값이 입력에 있었다는 사실은 모델이 읽고 이해했다는 증거가 아니다. 합성 구성 자료·범위가 불명확한 과거 자료·미상 사용량은 실제 채택의 근거가 될 수 없다. 양쪽 보고서는 같은 수치·의미 검사를 거치며 원문과 산출물에서 다시 판정한다.

다음 실제 개발 비교는 같은 모델·과제·도구 권한·자원 조건으로 진행한다. 개발 결과는 별도 최종 표본 설계에만 사용하며 그 자체로 개선을 채택하지 않는다. 최종 채택에는 사전 등록한 토큰 절감 신뢰구간 하한 20% 초과와 test MSE 비열등성 10% 조건을 함께 요구한다. 공통 독립 보고서 검사와 실제 증거 자격도 모두 충족해야 한다. 원 연구 계열 모델 A는 현재 승인된 실행 경로에서 사용할 수 없어 모델 교체 효과는 미추정이다. B와 C의 비교는 같은 현재 모델에서의 프레임워크 묶음 효과이며 각 변경의 개별 인과 효과는 분리되지 않는다.

공개 설치와 실행은 [v7 README](../versions/v7-development/README.md)를 따른다. 공개 선택은 소스 71개이며 로컬 검사에 사용한 108개 전체와 구분한다. 생략된 원본 runtime 35개는 고정 commit과 해시를 검사하는 `scripts/fetch_upstream.py`로 취득한다. 나머지 두 과거 example은 실제 개발 영수증 경로를 포함해 이번 선택에서 제외했다. 이 optional example은 패키지·테스트·script의 의존성이 아니며 새 `sampled-pilot-base-c7.json`은 포함한다. 현재 실제 연구 기록·private config·owner 행·인증 자료는 이번 소스와 공학 증거 게시 범위에 포함하지 않는다.

별도 [새 공개 설치 보고서](../evidence/fresh-v7-install-899c97c/fresh-public-run-v1/report.ko.md)는 공개 commit `899c97cdab5d557db8b80a6bf479779ed13282d1`의 소스 71개와 새로 취득한 원본 35개를 자체 환경에서 확인했다. 263개 전체 검사와 고정 캡처 소스의 38개 구성 사례가 한 번씩 통과했고 106개 소스가 전후 동일했다. 38개 재현의 CPU 구성 12회는 공개 합성 자료이며 실제 연구·모델 호출이 아니다. 원시 결과·명령·로그와 부모 hook 밖 CPU child 1개의 한계를 보고서에 남겼다. 이 검사는 v7 B 등록 결함의 해소, 모델 인증이나 프레임워크 개선을 입증하지 않는다.
