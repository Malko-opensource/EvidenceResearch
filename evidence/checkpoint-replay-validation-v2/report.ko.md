14개 실제 구현 검사가 통과했다. 검사는 개발용 미래 코드의 고정 바이트 사본을 실행했으며 실제 모델은 호출하지 않았다. 일부 검사는 실제 고정 CPU fitting을 수행하지만 작은 구현 fixture이며 연구 비교 실험이 아니다.

검증한 조건은 다음과 같다.

- checkpoint에 이미 반영된 동일 prompt 다음 호출은 새 요청으로 처리한다.
- 오래된 checkpoint의 미반영 model tail을 원래 logical ordinal·역할·단계·prompt 순서대로 한 번 재생하고, 이후 동일 prompt는 새 요청으로 처리한다. 같은 오래된 checkpoint에서 다시 복원할 때도 해당 tail을 재구성할 수 있다.
- 같은 prompt의 여러 실제 완료 receipt를 서로 다른 logical 호출로 보존한다.
- model → CPU → model tail에서 원래 CPU 반환 문자열과 산출물을 그대로 재사용하고 CPU 계산은 중복 실행하지 않는다.
- 같은 literal이라도 seed 등 실행 조건이 바뀌면 재생과 새 실행을 모두 거부한다.
- 불완전한 raw/logical 대응, 역할·단계·prompt 불일치와 변경된 checkpoint를 확인하면 실행을 중단한다.
- definitively failed/no-action 모델 호출만 같은 logical 요청으로 재시도할 수 있으며 실패한 시도도 자원을 소비한다.
- 원본 LaboratoryWorkflow 클래스와 원본 save_state 본문을 이용한 pickle 복원, committed head·cursor·RNG·receipt prefix 연결을 검사한다. 원본 객체에 adapter 속성을 넣지 않는다.
- 원본 reward 함수의 Exception 처리에 가려지지 않는 host abort와 최종 reconciliation 실패를 확인한다.

stdout·stderr·실행 명령·경과 시간과 소스 사본 SHA는 [result.json](result.json), [source-manifest.json](source-manifest.json), [stderr.log](stderr.log)에 연결된다. unittest 출력은 `Ran 14 tests in 0.674s`, `OK`이다. 이 수치는 해당 구현 검사의 실행 결과이며 연구 성능, 재현 CLI 전체 성공, 모델 효과 또는 framework 개선 효과를 뜻하지 않는다.

재현 명령은 저장소 루트에서 다음과 같다.

```powershell
python -B evidence/checkpoint-replay-validation-v2/run.py
```

이미 생성된 고정 source_snapshot을 우선 사용하므로 ignored `work/next-version`이 없는 공개 clone에서도 검사를 재실행할 수 있다. 검사 임시 경로는 이 저장소의 `work/crv2`에만 생성된다. Python 표준 라이브러리를 사용한다. 원본 AgentLaboratory의 두 파일과 MIT LICENSE 사본도 snapshot에 포함한다.

이전 v1 검사에서 Windows 경로 깊이 때문에 발생한 실패와 그 당시 소스는 그대로 보존되어 있다. v2는 짧은 fixture working root를 사용하고 현재 짧은 tool reply 이름 및 실행 조건 binding이 반영된 새 사본이다. 제안 단계의 [transport-checkpoint-contract-v1](../transport-checkpoint-contract-v1/proposal.ko.md) fixture 통과와 현재 구현 사본의 통과를 구분한다. 별도로 원본 solver를 포함한 전체 pipeline fixture는 core 담당자의 다른 검사이며 이 보고서의 14개 수치에 포함하지 않는다.

현재 main 및 동결된 v4 연구 기록·설정은 변경하지 않았다. 실제 예정 release 디렉터리에서의 모델 호출과 CLI 재개는 수행하지 않았다.
