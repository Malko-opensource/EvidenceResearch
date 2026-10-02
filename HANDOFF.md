# 후속 핸드오프

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

현재 비교 구현은 공개 commit `46580f975fe72bc508a7783202c96bc15b9e5d05`이며,
`runs/development/paired-pilot-v4/pilot-registration.json`에 개발 9개 짝의 조건과
소스가 고정돼 있다. 실제 모델 실행은 도구 session `80836`에서 진행 중이다.
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
메인 v4 controller `80836`도 진행 중이며 둘의 package·등록 조건을 수정하지 않는다.
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
