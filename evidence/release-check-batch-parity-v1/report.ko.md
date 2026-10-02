# 게시 검사 일괄 처리 검증

기존 검사 결과와 새 검사의 staged manifest는 6,758개 파일의 경로, 바이트 수, SHA-256 및 순서까지 정확히 일치한다. 비교 근거는 `parity.json`과 보존된 두 결과 JSON이다. 기존 검사 결과는 복사 전에 SHA-256으로 고정했다.

새 검사는 `git ls-files --stage -z`의 NUL 구분 이름을 파싱하고 검증된 Git object ID만 단일 `git cat-file --batch` 프로세스에 전달한다. blob의 헤더, 타입, 선언 크기, 종료 문자와 Git object hash를 확인한 다음 기존의 private 경로, credential 정규식 세 개 및 staged/작업 파일 바이트 일치 정책을 적용한다. 충돌, symlink, 누락 파일, 변경된 index와 검사 도중 바뀐 작업 파일은 거부한다. 비밀값이나 blob 본문은 출력하지 않는다. 기존 `scripts/release_check.py`는 수정하지 않았다.

실제 index 읽기 검사는 4.7795539000071585초가 걸렸다. Git object 프로세스는 한 개였고 blob 요청은 6,758개였다. 검사 전후 index SHA-256은 동일했다. CLI의 출력 경로 사전 검사를 포함하면 index 조회 프로세스 세 개와 object 프로세스 한 개를 사용했다. 기존 검사의 실행 시간은 보존되지 않아 속도 개선 비율을 계산하지 않는다.

현재 새 검사의 `valid`는 false다. `STATUS.json` 작업 파일이 staged 바이트와 달라 기존 바이트 일치 정책에 따라 한 건을 거부했다. 따라서 전체 결과의 `valid`와 `rejected` 두 필드는 기존 완료 결과와 다르지만 staged manifest 자체는 같다. 이 감사는 파일을 restage하거나 변경하지 않았다. 다음 게시 검사는 담당자가 정리한 index에서 새로운 출력 경로를 사용해야 한다.

고립된 프로토콜/경로/credential fixture 10개가 통과했다. 실제 Git 변경과 모델 호출은 모두 없었다. 독립 평가 담당자의 읽기 전용 소스 검토에서는 구체적인 credential 본문 출력 또는 manifest parity 우회가 발견되지 않았다. 이는 지정된 패턴 검사이며 임의의 모든 비밀이 없음을 증명하지 않는다. 또한 게시 도구의 정확성과 실행 시간 검증으로, 연구 프레임워크의 성능 향상이나 Goal 완료 근거로 사용하지 않는다.

`commands.json`은 실행 파일, 인수, 작업 디렉터리와 종료 코드를 보존한다. `evidence-manifest.json`은 결과, 실행 receipt, stdout/stderr, fixture 및 당시 검사기 사본의 SHA-256을 연결한다. 저장된 증거 검사는 아래처럼 실행한다. 현재 index 재검사는 기존 결과를 덮어쓰지 않는 새 `--output`과 `--receipt` 경로가 필요하다.

```powershell
python -B evidence/release-check-batch-parity-v1/verify_evidence.py
python -B evidence/release-check-batch-parity-v1/test_batch_contract.py
python -B scripts/release_check_batch.py --root . --output evidence/release-check-next.json --receipt evidence/release-check-next.receipt.json
```

fixture 명령은 현재 검사기 소스가 보존된 SHA와 일치하는지 `verify_evidence.py`로 먼저 확인한 후 사용한다. 실제 index는 동시 변경이 가능한 외부 상태이므로 새 검사의 결과와 시간은 과거 측정과 별도 기록해야 한다.
