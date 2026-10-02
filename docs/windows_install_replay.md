# Windows 공개 소스 설치 재현

공개 commit `9cdc234c86d4a532b47be27401e5c43d188d90cc`의 v5 소스를 새 checkout과
독립 Python 3.12.14 환경에서 확인했다. 깊은 checkout 경로에서는 전체 161개
검사 중 두 transport checkpoint fixture가 `WinError 206`으로 실패했다.
실패 기록은 [원본 결과](../evidence/fresh-v5-install-9cdc234/result.json)와
해시 연결 stderr에 보존했다. 패키지나 해당 검사 코드를 변경하지 않았다.

같은 commit을 짧은 새 sibling 경로에 취득한 뒤 원본 소스와 자체 upstream
35개 파일의 바이트를 확인하고 전체 161개 검사를 다시 실행했다. 전부 통과했고,
검사 전후 소스는 같으며 tracked working tree는 깨끗했다.
[짧은 경로 결과](../evidence/fresh-v5-short-install-9cdc234/result.json)에 실제
명령, 종료 코드, 시간과 로그 해시가 있다. 새 모델 호출과 연구 과제 실험은 없다.
trusted CPU unit fixture는 실제 수치 계약 검사이며 연구 비교 측정과 구분한다.

현재 Windows 버전은 짧은 새 clone 경로와 짧은 연구 출력 이름을 사용한다.
긴 경로 지원을 모든 설치 위치에서 검증했다고 주장하지 않는다. 예를 들어
사용자가 선택한 새 짧은 디렉터리에서 다음 명령으로 소스 실행을 확인한다.
이미 존재하는 프로젝트 디렉터리를 덮어쓰지 않는다.

```powershell
git clone https://github.com/Malko-opensource/EvidenceResearch.git ER
Set-Location ER
git checkout 9cdc234c86d4a532b47be27401e5c43d188d90cc
Set-Location versions\v5-development
python -X utf8 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -B scripts\fetch_upstream.py
.\.venv\Scripts\python.exe -X utf8 -B scripts\fetch_upstream.py --offline
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -X utf8 -B -m evidence_research.study --help
```

이 확인은 checkout에서 패키지를 직접 실행한 설치 경로다. editable distribution
설치는 수행하지 않았다. 모델 인증, 실제 연구 루프와 최종 비교는 별도 증거를
요구한다. 공개 CPU 자료의 이동 재계산은
[독립 평가 안내](../evaluation/README.md)의 고정 reader로 수행한다.
