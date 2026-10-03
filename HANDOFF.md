# 후속 핸드오프

현재 개발 소스는 `versions/v9-development`의 `0.5.0.dev1`이다.
[v9 범위](docs/v9_development.ko.md)를 읽는다. 원 357+7의 두 실행과 독립
54+8+1의 13개 계열·63개 사례, 자체 환경의 101개 선택 검사·CLI2·참조38은 공학
증거다. 실제 보고서 완결성과 기존 대비 개선은 아직 입증하지 않았다.

새 v9 개발 비교는 별도 로컬에 사전 등록했다. 현재 모델과 원본 권장 단계,
같은 과제·도구·공통 자원 조건을 유지한다. private config와 등록 원문은 seed와
평가 정보를 포함하므로 공개하거나 연구 모델 입력에 넣지 않는다. 진행 중인
연구는 하나의 controller만 사용하고 원본 등록·완료 실행을 덮어쓰지 않는다.

이전 v8의 `0.4.1.dev0`과 276개 검사·10개 계열 28개 사례는
[v8 문서](docs/v8_development.ko.md)에 보존한다. 아래 설명은 과거 버전의
보존 이력이며 현재 소스의 실제 성공·최종 판정으로 해석하지 않는다.

이전 개발 소스는 `versions/v7-development`의 `0.4.0.dev0`이다. 새 own 환경에서 263개 공학 검사가 통과했고 정확한 원시 증거는 `versions/v7-development/validation/release-local-v1/result.json`에 있다. 실제 개발 비교는 별도 로컬 등록으로 진행하며 개선·최종 평가를 완료 처리하지 않는다. [v7 검증 범위](docs/v7_development.ko.md)를 읽는다.
v7의 B callback 등록 writer와 고정 입력 경계 auditor 사이에 필수 model/envelope metadata 계약 불일치가 확인됐다. 해당 v7 경계와 보고서의 실패·보류는 유지한다. 별도 `work/c8` 사본의 구현 전 등록에 따라 최소 writer/선행 검사 수정과 실제 callback 통합 검사를 진행한다. 기존 v7 및 과거 증거·기준을 바꾸지 않는다. 새 공개 사본의 자체 환경에서 263개 검사와 고정 소스 38개 구성 재현은 통과했으며 [공개 설치 결과](evidence/fresh-v7-install-899c97c/fresh-public-run-v1/result.json)에 연결된다. 이 설치 성공은 실제 경로 결함의 해소나 개선 입증이 아니다.


이 컴퓨터의 실행 상태·단일 controller 식별자·사전등록과 후속 판단은 공개하지 않는 `work/current-handoff-20261003.json`에서 이어 간다. 기존 컨트롤러를 중단하거나 같은 연구를 병렬로 다시 시작하지 않는다. 아래 기록은 이전 단계의 보존 기록이며 당시 진행 상태를 현재 상태로 해석하지 않는다.

사용자 Goal은 active다. `STATUS.json`과 저장된 원장을 먼저 읽는다. 기존 KoMap,
다른 프로젝트·환경·프로세스를 변경하거나 중단하지 않는다. 새 프로젝트의
`.venv`와 기존에 허용된 ChatGPT 모델·도구만 사용하고 추가 비용은 승인 범위를
먼저 확인한다. 비밀값·인증 파일을 복사하거나 저장하지 않는다.

완료된 CPU·모델 실행은 재실행하지 않는다. `Store.verify_integrity()` 확인 후
`resume`으로 영수증 기반 복구를 수행한다. 등록 설정과 코드가 바뀌었다면 해당
실행은 별도 버전이며 이유를 기록한다. 과거 증거를 새 버전에 맞춰 변경하지 않는다.
모의 모델 fixture, 실제 모델 호출, 실제 CPU 실험과 최종 비교 결과를 구분한다.

첫 공개 commit은 `3ba19f2469cb85fb0b25a48a115eaebc3cb5e6da`다. 새 clone과 별도 venv의
설치·소스 취득·검사·CPU 재현은 `evidence/install-validation/report.json`에 있다.
소유자 비교 스크립트의 필드명 오류를 수정하면서 완료된 단계는 해시 영수증으로
재사용했다. 이 확인은 B/C 개선 증거가 아니다.

초기 비교 구현은 공개 commit `46580f975fe72bc508a7783202c96bc15b9e5d05`이며,
`runs/development/paired-pilot-v4/pilot-registration.json`에 개발 9개 짝의 조건과
소스가 고정돼 있다. 초기 도구 session `80836`의 수집은 완료됐다.
해당 session과 원장을 먼저 확인하고 이미 실행 중인 연구에 같은 명령을 병렬로
추가하지 않는다. 완료된 arm과 모델 호출은 재사용하며, 확정된 외부 실패는
원본 증거를 검사한 `pilot-continue`로만 이어 간다. 알 수 없는 실행은 재실행하지 않는다.
평가자가 본 개발 결과와 숨겨진 test 자료를 연구 모델에게 전달하지 않는다.

2026-10-03 방법론 검토: 이 pilot의 B는 MLE1/Paper0/literature1/phase4인
최소전이 구성이다. pinned README 권장 YAML의 MLE3/Paper1/literature5/phase100과
다르므로 원본 권장 설정 대비 개선의 주 비교로 삼지 않는다. 실행·등록은 변경하지
않고 개발 진단으로 보존한다. 다음 별도 등록에서 권장 설정, 서로 다른 primary
문헌 최소 5편, 전체 단계에 근거한 같은 자원 봉투와 예산 소진의 과제 실패 처리를
검토한다. 그 새로운 contrast는 자체 pilot 분산으로 최종 표본을 설계해야 한다.

별도 기억 노출 개발 진단은 `runs/development/memory-exposure-pilot-v1`에 등록했고,
실제 수집 session `14447`은 정상 완료했다. `scripts/memory_ablation.py`도 source-snapshot에
고정했다. 두 arm에 동일한 실제 CPU 보정 증거를 만들었으며 차이는 첫 결정 요청의
`verified_memory` 노출이다. 완료된 모델/CPU 실행은 재사용하며 같은 수집을 병렬
시작하지 않는다. 9개 짝 모두 실제 응답이 있고 중복 제안 차이는 모두 0이다.
`design-input.json`은 원본 선택·증거를 재감사한 개발 계산이며 확인 평가 채택이
아니다. 이는 자유 연구 전체의 기억 효과나 Goal 채택 판정이 아니다.
독립 재감사는 `evidence/memory-pilot-independent-review/`에 있다. 일반 함수가
출력한 후속 `n=9`는 희소 이산 사건의 확인 설계로 거부했다. 이 결과를 최종
기억 효과의 표본 설계로 사용하지 않는다. 원본 숫자와 코드·등록은 보존한다.

권장 설정의 별도 v5 개발 버전은 `versions/v5-development`에 고정했다.
독립 전체 검사와 별도 환경의 검사 각각 161개가 통과했고 실제 모델을 호출하지
않았다. 원본 자료 35개 해시와 자체 reference 경로를 확인했다. 별도 등록
`versions/v5-development/runs/p5/pilot-registration.json`의 SHA256은
`5569d283aeb9a00087092b862ef6dace71cdf73917429c308161d1cf31ad0f81`이다.
실제 controller session `54799`가 실행 중이다. 동일 controller를 추가하지 않는다.
메인 v4 controller `80836`은 수집을 정상 완료했다. 두 버전의 package·등록 조건을 수정하지 않는다.
private handoff `work/current-handoff-20261003.json`에 각 상태를 저장한다.

v5는 MLE3/Paper1/literature5/phase100, gpt-6.1-sol/medium과 같은 과제별 자원을
양쪽에 적용한다. compact 증거 기억, 실제 누적 비용 피드백, 조건·출처 검사,
수치와 의미의 독립 보고서 검사를 묶어서 비교한다. 개별 기법의 인과 효과는
이 B/C 묶음 비교로 분리하지 않는다. 소스의 conditional resource 설계는 임의의
Goal 반복 제한이 아니다. 개발 수집·리뷰·자체 변동성 확인 후 새 최종 과제의
표본과 정책을 별도로 고정한다. 현재 최종 개선은 미입증이다.

이 연구가 진행 중인 동안 `evidence_research/`와 pilot 설정을 변경하지 않는다.
수정이 필요하면 현재 증거를 보존한 채 새 개발 버전을 등록한다. 별도 보고서 검토
도구와 기억 ablation 설계는 외부 파일에서 작업하며 최종 등록 전에 그 소스도 고정한다.

다음 순서로 진행한다.

1. 완료된 원본 adapted B 개발 재개 기록(`runs/development/B-upstream-dev-quadratic-seed7-resumed`)
   과 모델 trace, 전체 보고서의 독립 수치 검토를 확인한다. 이전 CPU 실행을 반복하지 않는다.
2. 모델·분할·문헌·도구·자원 envelope을 맞춰 C의 개발 비교를 수행한다.
3. 개발 pilot에서 변동성을 추정하고 사전 채택 기준과 최종 표본 수를 고정한다.
4. 새 holdout 과제를 만들고 모델에 정답·비공개 평가 파일을 노출하지 않는다.
5. 고정 버전에서 B/C를 실행하고 독립 계산·모델 trace·수치 주장·재개를 검증한다.
6. 성공·실패 기억 효과의 별도 matched ablation을 실행한다. 개선이 미입증이면
   원인과 불확실성을 남기고 가설 또는 검증 설계를 개선한다.
7. 한국어 보고서·재현 명령·진행 상태를 갱신하고 `Malko-opensource/EvidenceResearch`
   저장소에 게시한다. 로컬 GitHub CLI의 계정과 브라우저 계정은 일치하는지 확인한다.

게시된 첫 개발 짝의 경로 이동 감사는 `evaluation/replay_published_pair.py`를
사용한다. 새 checkout에서 원본 경로의 증거를 열지 않고 새 root 아래로만
매핑한다. 최초 공개 commit에는 완료된 짝의 owner/public 자료가 빠져 검사가
거절됐다. 이 실패와 보완은 `evidence/portable-replay-development/`에 기록한다.
전체 semantic report review의 대체물이 아니며, 새 model/runner 실행은 없다.

사용자의 모든 완료 기준이 실제로 충족되기 전에는 `update_goal(complete)`를 호출하지
않는다. 외부 자원 부족은 구현 오류와 구분하고 독립적으로 가능한 작업을 계속한다.

사용자가 승인한 네 완료 v4 짝의 상세 기록은 공개 commit
`9cdc234c86d4a532b47be27401e5c43d188d90cc`에 게시했다. 승인 manifest SHA는
`b71986a181f3c8359ca14151ce746b3110c33131001b4c225ce977c419c5cfb2`이며,
원본 owner 행과 owner-request는 제외했다. 이 범위를 진행 중인 v5 또는 최종
과제의 상세 기록 공개 승인으로 확대하지 않는다.

네 짝의 이동 재계산은 `evaluation/replay_published_units.py`가 고정 등록·승인
manifest·소스를 인증한 뒤 결정적 개발 test 자료를 메모리 안에서 재구성한다.
원본 private 파일을 열거나 행을 기록하지 않고 모델·실험 실행도 추가하지 않는다.
수치 재계산을 독립 semantic 판정이나 새 연구 결과로 해석하지 않는다.

같은 공개 v5 소스의 긴 Windows 경로에서 발생한 두 검사 실패와 짧은 경로의
161개 전체 통과를 모두 보존했다. `docs/windows_install_replay.md`에서 원본 증거와
재현 명령을 확인한다. 실행 중인 package를 이 설치 검증에 맞춰 수정하지 않았다.

현재 게시된 reader/source/install checkpoint는 `c95471c990d39554d0ad8427603d26865353085b`
이며 새 공개 checkout reader 검증은 `evidence/fresh-published-reader-c95471c/`에 있다.
승인된 네 짝만 대상으로 원 owner 접근과 새 연구 실행 없이 재계산했다.
상세 게시 승인을 다른 v4 짝이나 진행 중인 v5/v6 자료로 확대하지 않는다.

다음 개발 비교는 `versions/v6-development`에 고정했다. 후보 및 새 환경의 전체215
검사를 통과했고 같은 법칙의 비공개 새 개발9쌍을 등록했다. 등록 SHA는
`5d5aa351cdeac52f0745fda323acfb8ea8c6b8a4c1e9f1a6b84892182761e862`, controller `34004`이다.
package19개와 외부 manifest/원본35개를 수정하거나 같은 controller를 중복 시작하지 않는다.
v5 `54799`도 원 조건으로 실행 중이다. 최종 등록은 아직 없다. 정책과 수치/의미 리뷰
범위는 `docs/v6_development.ko.md`에 있다. 독립 판정 완료한 자체 실제 개발 분산으로만
최종 계획을 인증한다. v5 B-only distinct 문헌 postcondition 차이는 개선 증거로 채택하지 않는다.

v4 owner 정리 guard 오류는 cache 읽기를 새 실행으로 잘못 분류했다. 잘못된 실패와
audit chain은 보존하고 별도 원 기준 정정 판정을 로컬 핸드오프에 연결했다. 원 raw·
measurement·review는 변경하지 않았고 새 모델·연구 CPU trial은 없다. verifier의
수치 재계산은 있으므로 CPU 계산0이라고 표현하지 않는다. canonical pilot-summary를
새 과학적 실패로 해석하지 말고 `work/current-handoff-20261003.json`의 정정 범위를 확인한다.

공개 v6 `0be5988f4760263122188ef31e7f8dfba5ccea47`의 새 짧은 `_er6` 체크아웃도
원본35개를 직접 취득하고 새 환경에서 전체215 검사를 통과했다. 공개103개 파일은
전후 Git blob·SHA가 같다. `evidence/fresh-v6-install-0be5988/result.json` SHA는
`cf03c97e3dca2a783d935ba5252193a7759a39d159870e7d40b7738e3e9497b2`이다.
이 설치 체크아웃에서 실제 모델·연구·등록은 실행하지 않았다. 실제 v6 연구는 원
`versions/v6-development/runs/p6`의 활성34004 한 개에서만 진행한다.
