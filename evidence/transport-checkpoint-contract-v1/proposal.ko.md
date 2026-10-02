# 원본 AST를 유지하는 transport/checkpoint wrapper 제안

이 문서는 후속 복사본 구현을 위한 독립 검토다. 현재 main/v4·등록·실행 프로세스는 변경하지 않았다. [계약 fixture](fixture.py)와 [결과](result.json)는 실제 후속 코드의 통과를 주장하지 않는 provider-free executable specification이다. 실제 모델 호출·CPU 실험은 0이다.

## 설치 위치와 책임

고정 업스트림 `LaboratoryWorkflow.save_state(phase)`는 `state_saves/Paper{paper_index}.pkl`에 `pickle.dump(self)`를 수행한다(ai_lab_repo.py:106–113). `perform_research`는 각 subtask의 상태를 갱신한 다음 이 메서드를 호출한다(:163–178, :200). report refinement 종료에서는 별도 early save/return이 있다(:178–185).

소스 AST를 수정하지 않고 로딩된 **class**의 phase 메서드와 save_state를 host wrapper로 감쌀 수 있다. wrapper가 원래 callable을 저장하고 정확히 한 번 호출하면 원래 prompt·phase 순서·solver 로직을 보존하면서 transport 관측을 추가한다. 런타임 wrapper를 추가한 적응 실행임은 baseline provenance에 공개한다. AST가 변하지 않았다는 사실만으로 런타임 행동이 완전히 같다고 주장하지 않는다.

instance에 bridge/context closure/호스트 객체를 추가하면 원본 pickle의 object graph가 바뀌며 restricted unpickler의 허용 global과 충돌한다. 원본 class identity를 유지하고, context·cursor·receipt는 host의 별도 sidecar에 저장한다. `_module_scope` 종료 시 class wrapper도 복원하여 다른 실행으로 상태가 전파되지 않게 한다.

phase wrapper는 `literature_review`, `plan_formulation`, `data_preparation`, `running_experiments`, `results_interpretation`, `report_writing`, `report_refinement`의 현재 phase를 host context에 설정하고 원래 메서드를 호출한 뒤 context를 복원한다. query_model caller의 원본 module/function/code identity, self class 및 필요하면 고정 `reviewer_type` 식별자를 role로 기록할 수 있다. 역할을 모델 출력의 자유로운 문자열에서 신뢰하지 않는다. 시간·새 attempt 경로처럼 재개마다 달라지는 값은 logical identity의 기준으로 사용하지 않는다.

## ordinal, actual attempt와 checkpoint

logical ordinal은 같은 원본 상태에서 실행되는 다음 요청의 순서다. 실제 모델 시도와 별도의 값이다. 완료 응답의 receipt에는 다음 조건을 연결한다.

- checkpoint lineage와 logical ordinal, 원본 phase/role/callsite;
- 전체 요청 SHA와 요청 model/effort/permissions 등 등록 조건;
- 실제 attempt identity, request/raw completion receipt 경로와 SHA;
- 정상 완료·검증된 무응답 실패·미확정 상태, retry 이유.

새 ordinal의 같은 prompt는 새로운 논리 요청이므로 fresh provider를 호출한다. 오래된 checkpoint에서 같은 ordinal을 재구성하는 요청은 기존 완료 응답을 다시 사용할 수 있다. 같은 invocation에서 같은 prior completion을 무제한 소비하는 것은 허용하지 않는다. 동일 prompt의 여러 기존 completion은 첫 항목으로 합치지 않고 순서와 multiplicity를 유지한다.

save_state wrapper는 원래 save를 호출한 뒤 pickle SHA와 당시 logical transport cursor를 immutable checkpoint blob/sidecar로 연결한다. cursor는 checkpoint에 이미 반영된 완료 prefix의 끝이다. 모델 ledger cursor만이 아니라 실행 도구의 논리 cursor도 필요하다. 각 receipt를 durable하게 작성하고 checkpoint snapshot과 cursor manifest를 원자적으로 commit하는 경계가 있어야 한다. 원본 Paper0.pkl만 갱신되고 대응 manifest가 없는 중단 상태는 마지막 hash-linked committed snapshot으로 복구하거나 미확정으로 닫는다. 임의의 새 cursor를 추정하지 않는다.

초기 상태 복원은 cursor 0부터 전체 ordered completed tail을 재생한다. phase checkpoint 복원은 그 checkpoint cursor 뒤의 미반영 tail만 재생한다. 다음 요청의 ordinal/phase/role/request SHA가 tail과 다르면 다른 SHA queue에서 찾아 주거나 fresh 요청으로 덮지 않고 reconcile 필요 상태로 닫는다. provider 완료 raw receipt가 있으나 bridge의 completion event 기록 전에 중단되는 경계도 사전 등록한 request identity로 대조하여 재구성해야 한다.

## CPU response의 원문 보존

감사한 미래 `AllowlistedExperimentTool._successful_output`은 replay 시에도 현재 `self.events_path`, 전체 완료 CPU 수·receipt 목록·remaining resource를 새로 생성한다. 새 attempt 경로가 바뀌므로 동일한 과거 CPU 결과를 읽어도 원래 반환 text와 달라질 수 있다. 그 text가 solver의 다음 모델 prompt에 들어가면 ordered completion replay의 request SHA가 달라진다.

동일한 logical tool invocation의 재구성에는 원래 host 반환 문자열과 그 SHA/CPU receipt를 보존하고 재생해야 한다. 이 문자열의 ledger 경로와 count는 **원래 논리 시점의 역사적 관측**이다. 원래 고정 실행 조건과 artifact hash·verifier를 다시 확인하고, 완료 실험을 새로 실행하지 않는다. 현재 실제 resource 사용량은 전체 actual lineage를 독립적으로 집계하여 상한에 반영한다. 다음 새로운 논리 tool 요청에는 현재 관측을 반환한다. 역사적 response replay와 현재 usage audit를 하나의 필드로 섞지 않는다.

원래 tool response가 저장되어 있지 않거나 같은 요청의 매칭을 확인할 수 없으면 새 정보를 넣어 tail을 맞추려고 하지 않는다. 이전 원자료를 보존하고 해당 재개를 불완전/판단 보류로 남긴다. CPU가 실행되었는지 미확정인 경우도 원래 정책대로 자동 재실행하지 않는다.

## fixture가 요구하는 동작

provider-free 계약 fixture는 원본 save_state AST와 class-level wrapper를 실행하고 다음 두 핵심 경로를 보였다. 이 fixture의 synthetic 값 A/B/C는 실제 모델 결과가 아니다.

1. checkpoint cursor 1이 prompt P의 완료 A를 이미 반영했다. 다음 ordinal 2의 같은 P는 fresh B이고 A를 다시 반환하지 않는다.
2. cursor 1 checkpoint가 오래된 상태이며 ordinal 2의 완료 B는 아직 반영되지 않았다. 재개는 B를 model 재호출 없이 재생하고, 이어지는 ordinal 3의 같은 P는 fresh C다. 같은 오래된 checkpoint에서 다시 재구성할 때도 B를 replay해야 한다. '전역 consumed'라는 이유로 B를 제외하면 같은 완료 요청을 모델에 다시 실행하게 된다.

또한 초기 cursor 0의 A/B/C 순서·multiplicity, 다른 role의 same-prompt mismatch fail-closed, 원본 save_state AST hash 불변과 pickled instance에 bridge/context 속성이 없는 조건을 확인했다. 이는 필요 의미를 설명하는 specification이다. 실제 복사본 wrapper의 fixture는 이 경로에 더해 다음을 확인해야 한다.

- 정상 checkpoint prefix filtering과 role/request/cursor raw receipt 감사;
- 완료 raw receipt 이후 transport event/checkpoint commit 전 중단;
- unknown 실행 차단 및 definitive no-action 실패의 명시적 새 actual attempt;
- 원문 CPU response replay와 실제 CPU budget 누적 계상;
- original initializer의 안정된 실패 prompt에서 한 번씩 소비한 뒤 fresh 요청 budget exhaustion;
- 원본 AST hash와 runtime wrapper provenance, 허용 unpickler global 불변.

원본 random 상태와 비모델 외부 관측이 prompt에 영향을 준다면 checkpoint sidecar에도 해당 재구성 상태를 연결해야 한다. 현재 MLE source에는 `random.choice(self.best_codes)`가 있고 기본 `max_codes=1`이지만, 그 기본값만으로 모든 후속 설정의 결정성을 가정하지 않는다. 역할·요청 불일치는 복구 가능성을 숨기기 위한 임의 반복 제한이 아니라, 증거 대응을 확인할 수 없다는 독립적인 종료 상태다. 새 연구 가설·목표 루프의 전역 cap은 추가하지 않는다.
