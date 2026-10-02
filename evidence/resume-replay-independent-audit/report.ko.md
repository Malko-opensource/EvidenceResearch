# 재개 모델 응답 replay 독립 정합성 검토

**재개 캐시의 무제한 재사용 경로를 재현했다. 미래 비교 버전을 등록하기 전에 수정할 높은 우선순위의 실행 정합성 문제다.** 현재 활성 파일럿에서 무한 반복이 발생했다는 주장은 아니다. main/future 소스와 등록·실험·프로세스는 변경하지 않았다. 실제 모델 호출과 CPU 실험은 모두 0이며, 아래 요청 수는 명시적인 synthetic fixture 관찰이다.

[소스 해시와 fixture 결과](finding.json), [재현 코드](reproduce.py), [캡처한 소스](source/)를 보존했다. 감사한 미래 arms.py SHA256은 `c91f5e61b90feb119d002e2143f1b6cc3664462010a20124ff8ddbdfc344330f`이다. 향후 소스를 수정해도 이 캡처로 당시 동작을 재현한다. 재현 명령은 프로젝트 루트의 `python -B evidence/resume-replay-independent-audit/reproduce.py`다. 외부 provider·실험 runner·원본 모듈 body를 실행하지 않는다.

## 무제한 replay 경로

캡처한 미래 `UpstreamCodexBridge`의 생성자는 완료 응답을 prompt SHA별 dictionary에 `setdefault`로 넣는다(source/future-arms.py:329). 동일 SHA의 여러 원래 completion은 첫 항목으로 합쳐진다. `__call__`은 `self.replay.get(request_sha)`로 조회하고 항목을 제거하거나 소비한 요청의 논리 identity를 저장하지 않는다(:366, :377–380). `reused_completed_evidence`인 호출은 `attempts` 계산에서 제외되고, 캐시가 존재하면 등록된 모델 요청 상한 검사를 통과한다(:367–369).

원본 `MLESolver.gen_initial_code`는 유효 score가 나올 때까지 `while True`를 수행한다(source/upstream-mlesolver.py:253–276). 이전 오류를 더한 뒤 길이가 5가 되면 가장 오래된 오류를 제거하므로 실제 유지되는 오류는 최대 4개다(:259–262). attempt 번호는 출력 로그에만 사용되고 모델 prompt에는 들어가지 않는다.

fixture는 원본 `Command`, `Replace`, `Edit`, `MLESolver` ClassDef와 실제 미래 bridge ClassDef를 그대로 컴파일했다. 원본의 filesystem 정리 함수 `remove_figures`만 no-op으로 대체했다. 프로토콜 fence 없는 동일 응답은 실제 `Replace.matches_command`에서 실패하여 실제 `process_command`가 항상 `Command not supported, choose from existing commands`를 반환한다. 실행 도구에 도달하지 않는다. 원본 full system prompt도 유지했다.

그 결과 첫 12개 논리 요청의 서로 다른 full prompt SHA는 5개이고, zero-based index 4부터 고정된다. prior attempts가 777이고 등록 상한도 777인 조건에서 그 5개 응답을 캐시에 넣으면 13개 논리 요청 모두 재사용되고 provider fixture 호출은 0이다. 캐시는 그대로 5개다. 동일 prompt·동일 응답·동일 오류와 소비되지 않는 캐시가 상태를 유지하므로, 실제 무한 실행 대신 13개를 관찰한 뒤 로컬 fixture observer로 중단했다. 이 observer는 연구 루프의 중단 기준이 아니다.

이 경로는 재개 lineage에 과거의 같은 실패 응답이 있어야 한다. fresh 실행의 완료 응답은 현재 bridge의 replay dictionary에 추가되지 않는다. 별도 fresh fixture에서는 같은 prompt도 provider fixture를 각각 호출했고 2회 상한에서 세 번째 요청이 정상 차단됐다. 따라서 일반 fresh 실행의 모든 요청이 캐시로 합쳐진다고 확대하지 않는다. 재개 이후의 host CPU·로그·disk 소비는 계속될 수 있는데 실제 모델 요청 상한이 이를 멈추지 못한다는 점이 핵심이다.

## reviewer sampling의 정확한 범위

원본 `ReviewersAgent.inference`의 세 reviewer는 서로 다른 `reviewer_type` 문구를 전달한다(source/upstream-agents.py:191–199). 실제 원본 `get_score`를 모델 없는 fixture로 수행한 결과 전체 prompt SHA도 3개로 서로 달랐다. **원본의 그 세 reviewer가 동일 prompt라서 한 응답으로 합쳐진다는 구체적인 우려는 성립하지 않는다.**

같은 reviewer·plan·report를 다시 요청하는 별개의 논리 호출은 다른 문제다. 과거 응답 한 개를 캐시에 넣은 fixture에서는 3개 요청 모두 같은 증거 한 개를 재사용했고 신규 provider fixture 호출이 없었다. 동일 prompt로 새로운 샘플을 요청하려던 기회가 첫 원래 completion으로 합쳐진다. 각 completion의 원래 prompt가 같아도 별도 샘플인지 재개를 위한 동일 논리 호출 replay인지 구분해야 한다.

## 한 번 소비하는 queue와 재개 idempotence

prior completion을 prompt별 순서 있는 queue에 보관하고 같은 invocation 안에서 각 항목을 한 번만 소비하는 방식은 무제한 재사용을 막는다. 별도 sidecar mapping prototype은 prior completion 5개를 한 번씩 소비하고 이어지는 같은 prompt를 fresh provider fixture 요청 3개로 집계했다. prior 5+fresh 3인 상한 8에서 다음 요청이 정상 차단됐다. 미래 실제 코드는 수정하지 않았다.

그러나 **queue만으로 재개 idempotence가 완성되지는 않는다.** 현재 baseline은 원본 phase checkpoint를 복원하거나 최초 상태에서 replay를 시작한다(source/future-baseline.py:386–414). 모든 과거 완료 응답을 아무 제한 없이 다시 queue에 넣으면, checkpoint가 이미 반영한 과거 phase의 응답을 새로운 논리 요청에 잘못 대응시킬 수 있다. 반대로 '소비 완료'를 전역 영구 표기하여 재개에서도 모두 제외하면, 오래된 checkpoint를 다시 실행할 때 이미 완료한 같은 논리 요청을 모델에 중복 실행한다.

필요한 구분은 다음과 같다.

- 완료 모델 실행 identity와 solver의 논리 요청 identity를 분리한다. phase/role/논리 ordinal 및 전체 request SHA, 실제 completion receipt SHA를 연결한다. 같은 prompt를 요청한 서로 다른 logical ordinal은 fresh 요청이며 원래 completion도 서로 유지한다.
- checkpoint SHA에 대응하는 transport cursor를 저장한다. 최초 상태 복원은 순서·multiplicity를 보존한 전체 prefix를 replay하고, phase checkpoint 복원은 그 cursor 뒤의 미반영 tail만 replay한다. cursor나 요청 대응을 확인할 수 없으면 추측해서 재사용하지 않는다.
- 논리 요청을 먼저 등록하고 완료 raw receipt를 원자적으로 연결한다. 중단 후 같은 logical identity는 해당 완료 응답을 재사용하지만, 정상 진행 중 새 identity가 같은 prompt를 만든 것은 새 모델 요청으로 집계한다.
- completion 이후 checkpoint commit 전에 중단된 경우와 실패한 provider `turn.failed`의 무응답 경우를 구분한다. 미확정 실행은 계속 차단하고, 검증된 무응답은 명시적 retry lineage 아래 새 actual attempt로 남긴다. prior/fresh/failed 실제 사용량을 모두 등록 상한에 포함한다.

이는 원본 solver 반복 횟수에 새로운 임의의 제한을 추가하는 문제가 아니다. 모델 호출의 동일성·서로 다른 샘플링·완료한 요청의 정확한 재개를 보존하는 transport 수정이다. 수정 후에는 같은 prompt의 여러 기존 completion, 정상 fresh 반복, checkpoint가 반영한 prefix, 완료 후 checkpoint 전 중단, 실패 무응답 재시도, 동일 invocation의 반복 실패에서 budget exhaustion을 독립 fixture로 확인해야 한다. 현재 동결 study는 그대로 보존하고 새 버전에서 별도로 검증·등록한다.
