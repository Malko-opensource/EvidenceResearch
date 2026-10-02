# v6 독립 개발 후보

이 폴더는 권장 원본 단계와 개선 프레임워크를 비교하는 별도 개발 후보이다.
메인 v4와 실행 중인 v5의 등록 조건과 실행 파일을 변경하지 않는다. 배포 복사 시 소스의 해시는
`release-copy.json`, 별도 환경의 검사 영수증은 `validation/release-local`에
보존한다. 구현 검사 통과는 실제 연구 개선이나 최종 평가 채택을 뜻하지 않는다.

설정과 실행은 이 디렉터리를 cwd로 사용한다. 부모 v4 환경에 설치하지 않고
새 venv에서 실행한다. 긴 Windows 경로에서는 짧은 새 체크아웃 경로를 사용한다.
upstream 원본은 scripts/fetch_upstream.py로 고정
manifest를 검증하여 취득한다. 실제 모델은 기존 Codex 인증을 사용하고
비밀값을 이 프로젝트에 복사하지 않는다. 실행 중인 연구의 package 파일은
편집하지 않으며, 수정이 필요하면 새 버전과 개발 과제를 등록한다.

Python 3.12 이상과 로그인된 Codex CLI가 필요하다. 연구 패키지는 표준
라이브러리만 사용한다. 아래 명령은 이 폴더에서 실행한다. 새 checkout에서는
환경을 만들고 고정 upstream 소스를 취득한다. 취득은 원본 코드를 실행하지 않는다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 scripts\fetch_upstream.py
.\.venv\Scripts\python.exe -X utf8 -m evidence_research doctor
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

등록과 실제 실행은 서로 다른 명령이다. 이미 등록된 연구에서 조건이 다르면
거절하며, 실행 중에는 같은 연구에 두 번째 controller를 시작하지 않는다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m evidence_research.study pilot-sample-config --base-config examples\sampled-pilot-base-v6.json --output work\private-pilot-config.json
.\.venv\Scripts\python.exe -X utf8 -m evidence_research.study pilot-register --config work\private-pilot-config.json --output runs\p6
.\.venv\Scripts\python.exe -X utf8 -m evidence_research.study pilot-run --output runs\p6
```

`pilot-sample-config`는 기본적으로 비공개 256-bit 난수 상태로 개발 과제를 생성한다.
설정과 등록 파일에는 owner 전용 데이터 정의와 난수가 있으므로 연구 참가자 입력이나
공개 저장소에 제공하지 않는다. stdout 영수증은 해당 값을 출력하지 않는다.
공개 train/validation만 B/C에 동일하게 전달한다. 실행 전 등록 문서가 존재하는지
확인한다. 재개에는 같은 `pilot-run`을 사용한다.
완료된 실험을 새로 실행하지 않고 원본 해시와 독립 검증을 확인한다. 확정된
무동작 외부 실패는 영수증과 이유를 검사하는 다음 명령으로 별도 승인 lineage를
남긴다. 미확정 실행과 소진한 등록 자원을 자동으로 재시도하지 않는다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m evidence_research.study pilot-continue --output runs\p6 --unit UNIT_ID --arm B --reason '확인된 외부 무동작 실패의 재개 근거'
```

독립 검토자는 본문과 companion을 각각 `pilot-review`로 수치 검토하고
`pilot-semantic-review`로 의미 주장 검토한다. `--report-kind primary|companion`과
`--judgments`를 명시한다. 의미 목록을 먼저 준비하려면 해당 명령에서 judgments를
생략한다. 새 리뷰 버전은 이전 보류 판정을 보존한다. 검토 결과를 자기평가로
대신할 수 없다.

등록된 자원 상한은 과제별 공통 평가 조건이다. 연구 Goal의 반복·시간·연속
실패 제한이 아니다. 이 개발 자료를 보고 설계를 바꾸면 별도 버전과 새 과제를
사용하며, 최종 확인 과제로 재분류하지 않는다. A의 원 연구 모델 계열은 현재
승인된 전송 방식으로 실행하지 못해 모델 교체 효과는 미측정이다. B/C는 동일한
모델 식별자·추론 수준·권한·자원으로 프레임워크 묶음의 효과를 비교한다.

원 문헌 검토의 완료 조건은 중복을 포함한 유효한 review entry 5개이다. 공통
corpus의 서로 다른 문헌 5개와 구분하며 B에 별도 중복 제거 요구를 추가하지 않는다.
C의 참조 목록만으로 독해나 이해를 증명하지 않는다. 새 최종 등록은 이 버전의 같은
분포·모델·권한·자원으로 완료된 독립 개발 판정과 실제 분산을 확인하고, 별도 숨긴
과제를 생성하여야 한다. 기존 v4/v5 결과를 새 기준으로 소급 채택하지 않는다.
자세한 계약은 docs의 literature-contract-c6.ko.md와 sampled-evaluation-c6.ko.md에 있다.
