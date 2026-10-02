# 공개 v5의 짧은 Windows 경로 설치 검증

공개 commit `9cdc234c86d4a532b47be27401e5c43d188d90cc`의 같은 버전 파일을 짧은 새 sibling checkout `_er9`에서 실행하자 전체 161개 테스트와 study CLI 도움말 검사가 통과했다. Git으로 추출한 버전 파일 93개의 blob ID와 SHA-256을 실행 전후 대조했고 바이트 변경은 없었다. 새 checkout의 tracked 파일은 clean 상태다. 기존 등록 v5, main/v4 및 진행 중 controller는 변경하지 않았다.

이전 `evidence/fresh-v5-install-9cdc234/result.json`의 실패와 로그는 보존했다. 전체 검사의 두 실패는 `test_baseline_transport_integration`에서 깊은 `transport_checkpoints/.stage-*` 경로를 생성할 때 발생한 Windows `WinError 206`이다. 새 검사에서 이 두 검사를 포함한 원래 suite 전체가 통과했다. 테스트나 완료 기준을 완화하거나 Windows 전역 설정을 바꾸지 않았다. 구체적인 파일 경로 길이와 기존 증거의 SHA는 `diagnosis.json`에 연결된다.

독립 venv는 Python 3.12.14이며 system site packages를 사용하지 않는다. 설치 형태는 새 환경에서의 소스 실행이다. `pip install -e`와 배포 wheel 설치는 수행하지 않았으므로 editable/wheel packaging 검증으로 해석하면 안 된다. 소스 checkout은 앞서 가져온 공개 commit의 local clone으로 분리했고, AgentLaboratory 원본 35개 파일은 새 checkout의 own references에 공개 네트워크에서 새로 가져와 manifest로 검증했다. 원본 commit은 `d9017d90e329112d2a80b7712f37ee9094d2cd27`이다.

처음 공개 원본 fetch는 sandbox 소켓 제한 `WinError 10013`으로 실패했다. 그 receipt를 덮어쓰지 않고 보존한 후, 공개 자료 읽기 권한으로 별도 fetch를 수행해 35개 파일 다운로드와 검증에 성공했다. `upstream-fetch-authorized.json`과 stdout이 이를 기록하고, 뒤의 `upstream-offline.json`은 같은 own references를 다시 검증한다.

전체 suite의 unittest 기록 시간은 26.014초이며 전체 subprocess receipt 시간은 26.34399999998277초다. 모델 호출, 연구 비교 trial, private owner 파일 읽기와 Git 게시는 없었다. trusted CPU 단위 fixture는 기능 계약을 검증하기 위해 실행했으며 연구 실험으로 집계하지 않는다. 이 결과는 설치와 기능 재현성의 증거로만 사용하며 연구 성능 향상이나 Goal 완료를 뜻하지 않는다.

Windows에서는 긴 checkout 이름과 깊은 임시 fixture 경로의 조합을 피해야 한다. 아래는 충분히 짧은 새 작업 디렉터리를 선택하는 소스 실행 안내다. `C:\r\er`는 안내 예시이며 이 감사가 실제로 쓴 경로는 `diagnosis.json`의 `_er9`다. 기존 작업 디렉터리를 덮어쓰거나 실행 중 연구를 새로 등록하지 않는다.

```powershell
git clone https://github.com/Malko-opensource/EvidenceResearch.git C:\r\er
Set-Location C:\r\er
git checkout --detach 9cdc234c86d4a532b47be27401e5c43d188d90cc
Set-Location versions\v5-development
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -B scripts\fetch_upstream.py
.\.venv\Scripts\python.exe -X utf8 -B scripts\fetch_upstream.py --offline
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -X utf8 -B -m evidence_research.study --help
```

원본 fetch에는 공개 GitHub 접근이 필요하고 모델 API는 필요하지 않다. 이 안내는 Windows Python 3.12의 소스 실행 경로다. 다른 플랫폼, 더 긴 디렉터리 또는 editable/wheel 설치를 자동으로 검증했다는 주장으로 확대하지 않는다. 새 actual 연구의 등록·모델 호출은 이 검사 명령에 포함하지 않는다.
