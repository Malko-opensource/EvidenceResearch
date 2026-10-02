# v6 새 로컬 환경 독립 검증

`release-copy.json`의 외부 전달 pin `44941c17d0136056f97314055bcfbab77be57f4644c1c163f002a7953da9bbb7`에 연결된 복사 파일 101개를 확인했다. 부모의 c6 구성 검사 receipt pin은 `e3698eafeff2f63654b6ba3b7d97dd1dbb565ccbb85de4dcf001044b2ba6649d`이다. 새 `.venv`는 bundled Python 3.12.14로 생성했고 `include-system-site-packages=false`다. 기존 프로젝트 환경이나 프로세스는 바꾸지 않았다.

첫 검증 `release-local-v1`에서 venv 생성, 자체 reference 36개 바이트 확인, 오프라인 editable 설치, 설치된 패키지 metadata와 CLI doctor가 모두 exit 0이었다. 패키징 시에만 bundled runtime의 setuptools/wheel 경로를 제공하고 `pip --isolated install --no-index --no-deps --no-build-isolation --editable .`을 사용했다. 런타임 doctor와 전체 시험에서는 그 경로를 제거했다. 외부 의존성 다운로드와 업스트림 network fetch는 없었다. doctor의 샌드박스 인증 진단은 `Not logged in`이므로 인증된 실제 모델 접근 성공을 의미하지 않는다.

첫 전체 시험은 215개 중 5 failure와 1 error로 끝났다. 실패 원인은 추가한 외부 감사 도구였다. 기존 frozen tests가 명시한 `v6/runs/tf`와 `c6-fixture-only-*`의 합성 transport 자료 쓰기를 실제 owner 읽기로 잘못 분류했고, Windows subprocess audit의 `executable=None`과 command string 처리도 틀렸다. 원시 로그와 최초 도구·receipt를 그대로 보존했다. `release-local-v1/result.json` pin은 `b613ac36a50e0ca524944063f2b60bc53815a798595690fb98a671381b5ce809`이며, 그 안의 `live_private_owner_reads=6`은 합성 파일 **쓰기 시도 차단의 오분류 계수**다. 실제 소유자 정답 자료 읽기의 관측치로 해석하면 안 된다. 차단된 standalone CPU fixture는 시작 전에 TypeError가 발생했다.

두 번째 감사 도구는 이 두 처리만 수정했다. 릴리스 package/tests/config/README, main/v5 코드와 기존 연구 실행은 수정하지 않았다. 앞서 성공한 설치 단계는 raw SHA를 재확인하여 그대로 사용했고 실행하지 않았다. 알려진 합성 fixture 임시 경로만 허용하며 다른 실제 study/owner 경로, 모델 process와 network를 계속 차단했다.

새 v6 cwd와 자체 `.venv`에서 전체 215개 시험이 통과했다. `unit-checks.stderr.log`에 `Ran 215 tests in 44.453s`와 `OK`가 있다. 최종 `result.json` pin은 `4070b816c896684bdd548120e554902263dd121fd9f649c72732b4c1d1bae3ed`이고 raw 시험 로그 pin은 `13495acb2df7d540803c0e92b912c1074293b105c934b0fe21aafecf8ce33516`이다. 릴리스 101개 파일 및 main/v5 package의 before/after byte SHA는 모두 같았다. main/다른 버전 읽기, 실제 live owner 접근, 모델 process 및 network는 0이었다. 고정된 합성 CPU 재현 시험의 Python subprocess 1회는 허용·기록했다. 전체 suite에는 합성 실제 CPU runner fixture가 포함되므로 모든 CPU 실행이 0이었다고 표시하지 않는다.

이 결과는 독립 환경의 설치·원본 계약·구성·재개·평가 도구 검증이다. 새 실제 연구 trial, 모델 호출, sampled pilot 등록, 최종 등록, 최종 평가 또는 프레임워크 개선 입증은 수행하지 않았다. 새 sampled 파일럿은 별도 고정 등록과 자원 조건에서 진행해야 한다.

검증 도구는 기존 완료 receipt를 덮어쓰거나 완료된 실행을 반복하지 않도록 닫힌다. 다시 실행하려면 이 fixed release를 새로운 별도 검증 작업공간에 복사하고 새 venv를 생성한다. 현재 완료 설치를 다시 설치하거나 원시 로그를 덮어쓸 이유는 없다. 일반 시험 재현 명령은 다음과 같다.

```powershell
.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
```

이 명령만 다시 실행하면 감사 guard 수치까지 같은 검증은 아니다. guard 구현·환경·정확한 명령은 보존된 `validate.py`, `audit_guard/sitecustomize.py`, result/raw logs를 확인한다.
