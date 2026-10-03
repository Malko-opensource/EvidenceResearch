# v9 dev1 설치 산출물 메타데이터 검토

저장된 설치 및 선택 시험 결과의 연결을 검토한 결과, 이 범위에서 불일치는 발견하지 않았다. 검사자는 c9 의미 판정기 구현에 참여했으나 이번 복사·설치·검증 도구의 작성자는 아니다. 따라서 이 문서는 저장된 산출물에 대한 별도 검토이며, 모든 의미 판정 규칙을 새로 독립 실행하여 입증한 결과가 아니다.

## 확인한 범위

- 세 단계의 별도 root GO가 복사 → 설치 → 검증 영수증에 각각 연결된다. 복사 영수증은 `cbb0a667…`, 설치는 `d007eaac…`, 선택 검증은 `d69001b9…`에 고정했다.
- 설치 기록의 버전은 `0.5.0.dev1`이고 Python prefix는 해당 v9 릴리스의 `.venv`, 모듈 위치는 동일 릴리스의 `evidence_research/__init__.py`이다. clean runtime에서 user site는 false이다. venv 생성·offline editable install·clean runtime의 세 저장 단계가 모두 exit 0이고 원 로그 해시와 일치한다. 설치 명령에는 `--isolated --no-index --no-deps --no-build-isolation`이 명시돼 있다.
- 고정 선택 목록 `6683e6a1…`의 정확한 101개 ID는 발견 ID와 실제 stderr의 101개 `... ok` ID 모두에 일치한다. 목록은 기존 84개와 새 context original-binding 17개다. 저장된 로그의 마지막 결과는 `Ran 101 tests in 27.311s / OK`이다. 이는 시험 도구가 기록한 공학 시간이다.
- 선택 시험, own frozen closure, CLI help, study help의 네 저장 실행은 모두 exit 0이며 own interpreter·own cwd와 stdout/stderr 해시가 일치한다. CLI 두 개의 마지막 인수는 `--help`이다. 검사자는 이 명령들을 다시 실행하지 않았다.
- own frozen closure 출력은 upstream 36개와 semantic 2개로 총 38개다. 모두 해당 릴리스 아래의 서로 다른 경로이고 복사/고정 소스 메타데이터 해시와 일치한다. 이 검토에서 참조 원문 파일을 다시 해시하지 않았다.
- 복사 소스 125개는 held source manifest `926a8f0d…`와 정확히 일치한다. 설치·검증의 저장된 source 125개 및 protected 886개 전후 경로/해시 맵이 같다. 보호 원본 886개 파일의 본문을 다시 열거나 재해시하지 않았다.
- 네 guard JSON에는 각각 여섯 정수 계수가 있으며 모두 0이다. 이 계수의 범위는 해당 Python 자식에서 관찰한 workspace 접근, 명시된 credential namespace, 쓰기 및 process/network 시도다. 런타임의 다른 경로는 읽을 수 있으므로 전체 OS 격리나 모든 sibling·credential 부재를 보증하지 않는다. 이 선택 목록에서는 CPU subprocess를 허용하지 않는다.

## 해석과 한계

검토자가 실행한 것은 저장된 JSON·로그·해시를 대조하는 별도 PowerShell 메타데이터 비교뿐이다. 후보/helper import, 시험·CLI 재실행, 새 환경 생성·설치, provider/model/native, CPU task/fit, actual/private/owner 자료 열람, Git 작업은 모두 0이다. 로그에 기록된 시험은 synthetic transport와 작은 공개 배열의 in-process CPU component fixture를 포함하며 연구 성능 실험이 아니다.

이번 선택 검증은 전체 364개를 새로 실행한 결과가 아니다. 이전 두 harness의 357+7 조합 및 현재 13-family/63-case 조합 검증과도 구분한다. 실제 연구 등록·모델 효과·비공개 최종 과제·비교 채택을 검토하거나 승인하지 않는다. 기존 채택 기준, 원 실패 영수증, 후보 소스, 보고서 및 연구 기록은 변경하지 않았다. Goal 완료 및 개선 입증은 false로 유지한다.

## 재검토 자료

`result.json` SHA256: `1fe823ae04ca23fa5d7c9d363f386f7a9e86b1568f3d08555553d0ffc86b003f`.

`metadata-comparison.json` SHA256: `a5d080ef4ffec9e31c490361289a68f2449fc7e274519bc13672eb2439b7758e`.

`installation-phase-supplement.json` SHA256: `3e47a84df2927a28c074af3f9b18e287ba685d4f1daeb7e0848613547c0e72a0`.

각 자료는 입력 핀, 원 로그 및 ID, 단계별 영수증·guard·참조 메타데이터 연결을 보존한다. 원 성공 단계를 재실행할 필요는 없다. Root가 다음 실제 연구 등록을 별도로 판단한다.
