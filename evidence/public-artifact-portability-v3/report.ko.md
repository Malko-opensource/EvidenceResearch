원래 프로젝트의 main 코드·ignored work·references를 제공하지 않은 별도 공개 사본에서 재현했다. child process 감사 hook은 원래 프로젝트 아래 파일 open·listdir·scandir를 거부했고, 선언된 Python unittest 외 subprocess도 거부했다. 실행 기록에서 원래 프로젝트 접근 시도 및 차단된 외부 subprocess는 0건이다. 실제 모델은 0회 호출했다.

| 공개 사본 검사 | 실제 결과 | 해석 |
| --- | --- | --- |
| checkpoint v2의 기존 run.py | 14개 통과, 0.666초 | 고정된 현재 구현 snapshot으로 통과 |
| checkpoint v1의 기존 run.py | 13개 중 저장 오류 4개, 0.423초 | 원래 archived Windows 경로 실패가 재현됨 |
| 같은 v1 바이트의 얕은 snapshot 배치 | 13개 통과, 0.640초 | 구현·test 내용을 변경하지 않고 저장 위치만 짧게 바꿈 |
| 과거 replay `reproduce.py --snapshot-only` | 성공 | 5개 SHA 고정 원본 사본만으로 과거 조건부 결함 재현 |

v1에는 task-specific fixture working-root 환경 변수를 읽는 코드가 없다. 깊은 기본 layout의 실패를 성공으로 덮어쓰지 않았다. 얕은 배치는 같은 manifest의 파일 바이트를 별도 `s/` 아래 놓고 동일 unittest 명령을 실행한 추가 검사다. v2의 14개 semantic API 검사와 v1의 13개 검사를 서로 합치거나 대체하지 않는다. source-manifest와 과거 finding·result의 원래 바이트는 검사 전후 동일했다.

[result.json](result.json)은 공개 파일별 SHA, 실행 명령·working directory·exit code, fresh 출력 SHA 및 child audit hook 기록을 연결한다. source snapshot 안에 원본 LaboratoryWorkflow·agents 및 LICENSE가 이미 포함되어 있으며, 과거 replay는 원본 MLESolver와 agents의 정확한 바이트 사본을 포함한다. ignored 원본 디렉터리는 실행 중 필요하지 않았다.

```powershell
python -B evidence/public-artifact-portability-v3/run.py
```

스크립트는 원래 프로젝트에서 공개 evidence 파일만 복사하는 부모 단계와, 원래 프로젝트 접근을 차단한 child 실행을 구분한다. Python 표준 라이브러리를 쓰며 짧은 임시 sibling 디렉터리는 허용된 작업공간 안에 생성하고 삭제한다. 일반 runtime/stdlib 읽기는 허용된다. 운영체제 차원의 sandbox 검증이나 악의적인 코드를 방어하는 보안 검사는 아니다.

보조 guard의 초기 두 버전에서는 Windows `subprocess.Popen` 감사 event가 argv를 문자열, executable을 None으로 제공하는 점을 처리하지 못해 unittest subprocess를 시작하지 못했다. 그 실패 기록과 소스는 `public-artifact-portability-v1`·`v2`에 보존했다. v3는 정확한 선언 command string을 확인하며 executable이 기본 None인 Windows 표현을 허용했다. 이 두 보조 실패의 복사된 기존 result/stderr를 fresh 검사 성공으로 취급하지 않는다.

이 결과는 공개 snapshot의 의존성과 파일 배치 재현성에 관한 증거다. 실제 CLI 전체 재개, 새로운 모델 결과 또는 framework 개선 효과를 입증하지 않는다. 전체 테스트가 모두 통과했다고 표시하지 않으며 v1의 깊은 배치 실패도 공개 결과에 남긴다.
