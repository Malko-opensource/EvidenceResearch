미래 재개의 원본 응답과 체크포인트 연결 설계

현재 v4와 실행 중인 등록은 수정하지 않는다. 개발 복사본에만 적용한다. [독립 발견](../evidence/resume-replay-independent-audit/finding.json)은 원본 MLE의 오류 이력이 안정된 뒤 같은 prompt가 반복되고, 비소비 캐시가 같은 완료 응답을 계속 반환하여 실제 요청 예산도 소진하지 않는 경로를 입증했다. 원본 세 reviewer의 prompt는 서로 달랐으므로 이 발견을 세 reviewer 일반 문제로 확대하지 않는다.

원시 요청의 경로와 request/result/events 해시로 실제 receipt를 식별하고 중복 복사를 제외한다. 같은 prompt의 서로 다른 실제 요청은 서로 다른 응답으로 보존한다. 독립적인 bridge 안에서는 FIFO 응답마다 한 번씩만 소비한다. 동일 prompt의 다음 논리 호출에 남은 원본 receipt가 없으면 새 실제 요청이 필요하며 등록된 예산에 포함한다.

체크포인트 재개에는 prompt 캐시만 사용하지 않는다. 호스트의 논리 순번, 단계, 호출 역할, system/prompt 해시, 실제 원시 응답 receipt와 SHA를 연결한다. 완료된 phase 체크포인트에 이미 반영된 prefix는 다음 동일 prompt에 제공하지 않는다. 오래된 phase 상태를 복원하면 cursor 뒤의 완료 tail만 동일 순번·역할·단계·prompt로 재생한다. 일치하지 않으면 새 실행을 추측하지 않고 재개를 거부한다. 확정 provider 실패는 응답이 반환되지 않았으므로 같은 논리 순번의 후속 실제 시도가 필요하고, 기존 요청 비용은 계속 포함한다.

원본 `LaboratoryWorkflow.save_state` AST와 클래스 identity를 유지한다. 클래스 수준 wrapper가 원본 저장 메서드를 호출하고, checkpoint binary·모델 cursor·도구 cursor·호스트 RNG 상태를 불변 bundle로 연결한다. 완성된 bundle의 manifest 해시를 포함한 head pointer만 atomic replace로 게시한다. binary와 sidecar가 따로 완성된 것처럼 해석하지 않는다. 불완전한 bundle은 현재 head가 아니며, 일치하는 committed checkpoint만 복원한다. instance에 closure나 bridge 객체를 넣지 않는다.

개발 구현에서는 초기 RNG/조건 상태도 먼저 저장한다. 원본 `open(...,"wb")` 호출의 저장 대상만 host staging 경로로 연결하여 원본 저장 본문을 그대로 호출한다. Windows에서 staged pickle을 쓰기 가능한 파일 descriptor로 다시 열어 동기화한다. 최종 bundle의 cursor는 완료된 원시 응답 receipt 전체 prefix를 포함하므로 나중에 길어지는 live ledger의 전체 해시에 의존하지 않는다. 독립적인 모델·도구 순번의 합과 전역 action 순번, 순서가 일치해야 한다. 복원 직후 원본 driver가 이미 완료된 phase를 다시 저장하는 경로는 tail 재구성 전까지 저장을 억제하여 원래 checkpoint 기준 해시를 유지한다.

CPU tail도 해당 논리 도구 호출의 code/실행 조건 및 원래 반환 text receipt를 연결한다. 과거 완료 CPU를 고정 평가기로 다시 검증하고 당시의 반환 문자열을 그대로 재생한다. 새로운 attempt 경로나 현재 누적 횟수로 문자열을 다시 만들지 않는다. 전체 실제 사용량은 별도 lineage에서 집계한다. 새 논리 도구 호출은 현재 자원을 관찰하고 새 호출로 기록한다. 원본 반환 receipt가 없거나 모델·도구 순서가 달라지면 일반적인 재개 무결성 오류로 거부하며 자동 중복 실행하지 않는다.

완료된 모든 원시 모델 응답에는 서로 다른 논리 receipt가 있어야 한다. 일부 응답만 logical ledger에 있고 다른 raw completion은 없는 중단 상태도 새 모델 요청으로 대체하지 않는다. 도구는 실제 CPU 결과뿐 아니라 거부된 protocol 등 원래 callback 기록까지 반환 receipt에 연결한다. 새 literal의 실행 fingerprint가 이전 조건과 다르면 같은 code text라는 이유로 재생하지 않는다. 확정 실패 후 재시도도 원래 실패한 logical phase/role/action/prompt와 일치해야 한다.

원본 reward helper가 `except Exception`으로 모델 전송 오류나 예산 소진을 점수 실패로 삼킬 수 있다. receipt-aware host 경계는 내부 전용 `BaseException` 탈출을 사용하고, 최외곽 baseline 어댑터가 원래 오류 class를 유지하여 실패로 기록한다. 이는 명시적인 host 실행 경계 보강이다. 원본 알고리즘의 문헌·계획·실험·보고서 정의를 바꾸거나 새로운 성공 수치를 부여하지 않는다. pipeline 종료 후에도 남은 completed tail이나 sticky host 오류가 있으면 성공 판정을 거부한다.

모델 없는 의미 있는 검사는 안정된 오류 loop의 캐시 소진, 서로 다른 동일 prompt 응답의 FIFO 순서, 완료 phase prefix 뒤 동일 prompt의 새 요청, 오래된 checkpoint의 모델→CPU→모델 tail 재생과 실제 callback 중복 방지, cursor·응답·checkpoint 변조 거부를 포함한다. fixture의 반복 관찰 경계는 결함 검사에만 사용하며 연구 Goal의 중단 규칙이 아니다. 실제 모델이나 연구 개선 효과는 이 구현 검사에서 주장하지 않는다.

현재 개발 테스트는 실제 pinned 원본 workflow와 agent pickle을 저장·복원하고, 원본 MLE 오류 이력이 안정된 이후에도 각 cached raw response를 한 번씩만 소비하는지를 검사한다. 원본 pipeline에서 초기 phase 실패를 복원하는 경우와 완료 phase 이후 MLE의 모델→실제 CPU→모델 tail을 복원하는 경우를 별도로 검사한다. model provider는 모두 명시적인 synthetic fixture이며 작은 CPU fit은 계약 검사다. 실제 연구 비교 trial이나 개선 입증으로 사용하지 않는다. 최종 소스 버전과 전체 테스트 영수증은 독립 평가 담당자가 별도로 보존한다.
