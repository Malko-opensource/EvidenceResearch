# v9 공학 출시 증거

패키지 `0.5.0.dev1`의 고정 소스125개와 일반 공개 소스87개에 대한 설치·구성 검증 자료다. 원본 영수증은 바이트 그대로 복사했고 각 원본/목적지·크기·SHA는 `manifest.json`에 연결했다. 이 capsule 작성자는 context/T1 구현에 참여했다. 이 자료를 작성자의 독립 과학 검증으로 취급하지 않는다.

- `coverage364`: 처음 364개 검사에서357개 통과와7개 setup 오류를 보존하고, fixture Path 변환 helper만 수정한 별도7개 실행을 연결한다. 두 harness의 구성적 coverage이며 한 번의 새364 PASS가 아니다.
- `coverage63`: 같은 runtime58에서 현재54개, 앞서 검증한 현재8개, 실패 원인만 수정한1개를 연결한13 family/63개의 공학 assertion이다. 합성 입력의 native B/C와 지원거부 공격을 포함한다. 한 번의 새63 PASS나 과거55개 통과의 이전이 아니다. 별도 metadata peer도 assertion 재실행은 하지 않았다.
- `release`와 `verification`: 자체환경의101개 검사(기존84+원 binding17), CLI 도움말2개, 고정 참조38개 확인이다. 합성 transport 및 작은 공개 CPU 구성 fixture의 결과이며 실제 연구 성능 측정이 아니다. 전체364개와 성공 phase를 반복하지 않았다.

원 실패를 요약한 `history-summary.json`은 실패 상태를 유지한다. 원 실패 결과·raw packet/owner 자료 본문은 이 capsule에 넣지 않았다. 복사 당시 아직 pending인 선행 영수증의 필드도 원본 그대로 유지하고, 뒤에 완료된 각 결과를 별도 연결했다. 설치본의 추가 독립 output peer는 아직 보류 중이며 `summary.json`의 path/SHA는 null이다. 이 capsule을 고치지 않고 별도 forward 증거로만 추가할 수 있다.

모든 수치는 공학 검증 범위다. 실제 primary/companion 보고서 완결성, 모델 접근 가능성, 연구 향상, 최종평가, Goal 완료를 입증하지 않는다. 고정20% token CI 및10% MSE noninferiority 기준과 실제 evidence qualification은 `frozen-criteria-summary.json`에 요약했다. A 계열 모델 효과는 실행·추정하지 않았다. 새 owner sampling/등록/연구 controller 권한도 이 자료에서 나오지 않는다.

원 명령과 bootstrap에는 로컬 절대 경로가 남아 있다. `coverage63`의 원 합성 case fixture와 raw packet, upstream35 바이트를 생략했으므로 원13/63 전체를 이 자료만으로 원격 재현할 수 없다. 공개 소스87개, 고정 upstream fetch, 검사 inventory와 runner를 사용하면101개 검사는 새 환경에서 새로 실행할 수 있다. 다음 명령은 새로운 짧은 checkout과 새로운 출력 경로를 위한 안내이며 이번 capsule 작성 중에는 실행하지 않았다.

```powershell
Set-Location '<짧은 새 checkout>\versions\v9-development'
py -3.12 -m venv .venv
$python = '.\.venv\Scripts\python.exe'
& $python -X utf8 -B scripts\fetch_upstream.py
# 소스 루트에서 직접 실행하므로 editable 설치가 필수는 아니다.
& $python -X utf8 -B -m evidence_research --help
& $python -X utf8 -B -m evidence_research.study --help
# 선택 사항: 일반 editable 설치에는 build dependencies가 필요하다.
# & $python -m pip install -e .
```

101개 검사에는 공개 `test-inventory.json`의 `selected_filenames`/`test_ids`를 사용한다. 캡처한 runner를 새 출력 폴더에 바인딩할 수 있다. `ER_RELEASE_ROOT`는 위 소스 루트, `ER_PROOF_ROOT`는 존재하지 않았던 새 출력 폴더, `ER_EXPECTED_TEST_INVENTORY`는 이 capsule의 inventory 절대 경로, `ER_EXPECTED_TEST_INVENTORY_SHA256`는 `6683e6a13c38de8fa9ae9e2b974f267d03dac4712d335bbab2040bba7e8d05b8`로 지정한다. 긴 Windows 경로를 피하고 별도 쓰기 가능한 짧은 TEMP/TMP를 사용한다. 원 증거/출력 폴더를 재사용하거나 덮어쓰지 않는다. 원 Python audit hook의 guard JSON은 원 실행의 제한된 관측이며, 새 runner만 실행했다고 그 guard를 재현한 것으로 주장할 수 없다.

원 offline installer는 당시 제공된 bundled build tools를 설치 단계에만 사용했다. 표준 fresh venv에서 build backend 준비 없이 `--no-index --no-build-isolation -e .`가 동작한다고 주장하지 않는다. `audit_guard.source.py`와 `run_portability.source.py`는 캡처한 도구 소스이며 자동 실행되지 않는다. Python hook은 OS sandbox가 아니고 모든 sibling 접근을 독립 관측한 것도 아니다.
