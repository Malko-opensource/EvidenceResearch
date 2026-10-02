# 권장 원본 설정 후속 개발 비교 등록안

상태: **미등록·미실행 제안**. 현재 paired-pilot-v4의 소스, 설정, 프로세스, 기준과 산출물을 변경하지 않는다. 실행 가능한 등록 파일로 오인하지 않도록 JSON은 configuration_proposal을 포함한 계획 wrapper다. 등록 전 조건을 해결한 뒤 새 소스·새 출력으로 별도 등록한다.

원본 README는 MATH_agentlab.yaml을 실행하라고 안내한다(README.md:84–86). 그 YAML의 문헌 수는5, MLE는3, Paper는1이다(YAML:19,26,28). 단계100은 LaboratoryWorkflow 생성자 기본값이고(ai_lab_repo.py:20), 원본 main은 이를 따로 덮어쓰지 않는다(:845–859). 생성자/YAML누락 기본 Paper5는 별도 정책이며 README권장 Paper1과 같다고 표현하지 않는다. 원본 소스 해시·줄 번호는 JSON primary_sources에 저장했다.

새 비교는 두 arm 모두 gpt-6.1-sol, 명시적 medium, 같은 공개 과제, 같은 문헌, 같은 literal CPU도구 권한, 요청51/CPU51 최대를 사용한다. B 설정은 max_steps100/MLE3/Paper1/lit5이며 원본의 계획·MLE내부판정·수정·보고서·리뷰 로직은 유지한다. 초기 파일럿에서 사용하지 않은 각 regime3개씩9개의 distinct seeds를 제안했다. 반복9는 현재 분산 평가 설계의 relativeSE .5 가정에서 나온 숫자이며 전체 연구 루프 상한이 아니다. C를 이전 study에서 복사하지 않고 같은 새 입력 아래 다시 실행한다.

등록 전 해결할 두 제약이 있다. 첫째, 현재 문헌 corpus는 distinct3편이다. 원본 add_review는 중복 ID를 허용하지만(agents.py:714–729), 이를 이용해5entry를 채우는 방식은 문헌5편 재현으로 인정할 수 없다. 후속 비교용으로 직접 확인한 primary문헌5편 이상을 새 snapshot에 담고 동일B/C 입력과 해시를 고정한다. 둘째, 원본 adapter의 로컬 예산소진은 모델 호출 전 ModelUnavailable가 발생하는 경우다(arms.py:306–307). provider turn.failed가 없는 이 사건을 capacity사건으로 위장하거나 자동retry해서는 안 된다. 새 개발 revision에서 예산 내 과제 미완료/실패로 분모에 포함하는 owner정책을 사전에 고정한다.

첫 최소전이 B의26요청을 기준으로 추가 문헌 FULL_TEXT/ADD_PAPER8, MLE 두 solve의 generation/judge8+reflection0..2, Paper 한 solve의 generation/judge6을 더하면 정상 유효 경로 예상은48..50요청이다. 이는 **코드 계산·미실행 예상**이고 모든 분기의 상한이 아니다. 원본 재시도·수리·판정파싱 오류가 발생하면51내 최종 보고서를 못 마칠 수 있다. 그런 결과도 그대로 기록하며, outcome을 보고 자원을 소급 늘리거나 완료 기준을 바꾸지 않는다. 더 큰 공통 자원이 필요하면 별도 개발 연구를 등록한다.

독립 검증은 actualCPU/데이터누출/모델권한과 설정/모든 실측숫자 증거/전체보고서 및 companion검토를 사용한다. 같은 required-content gate는 문학적 보고서 품질 동등성을 증명하지 않는다. 실제사용tokens/time/CPU/중복/복구는 각각 측정하고 알 수 없는 billing은 null로 유지한다. 최종 hidden평가를 보고 정책을 바꾸지 않는다.

이 연구는 원본 권장 반복 정책을 현재 모델에 적용한 **CPU도구 적응 비교**다. MATH-500논문수치, 원본모델A, 원본AgentRxiv PDF/웹/MiniLM 다중lab backend를 재현하지 않는다. 별도 재현 근거 없이 범용적인 원본 프레임워크 우월성을 선언할 수 없다.
