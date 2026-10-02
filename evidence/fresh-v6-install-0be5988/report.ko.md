# 새 공개 체크아웃 v6 독립 설치 검증

공개 저장소 `https://github.com/Malko-opensource/EvidenceResearch.git`의 정확한 커밋 `0be5988f4760263122188ef31e7f8dfba5ccea47`을 새 sibling `_er6`에 sparse checkout으로 받았다. 체크아웃에는 `versions/v6-development`만 있고 기존 프로젝트·`_er9`·work clone·환경·진행 중인 실행을 변경하지 않았다. 공개 tracked 파일 103개의 실행 전후 바이트를 해당 commit의 Git blob SHA1 및 별도 SHA256으로 대조했고 모두 같았다. before/after source inventory를 보존했다.

새 자체 `.venv`는 bundled Python 3.12.14로 만들었다. prefix와 base_prefix가 다르고 user site가 비활성이다. 패키징 도구는 오프라인 installer에만 노출했으며 `--no-index --no-deps --no-build-isolation --editable .`로 설치했다. 런타임 CLI와 전체 시험에는 bundled site-packages 경로를 제공하지 않았다. 설치된 package path는 새 `_er6`의 v6 소스다.

새 체크아웃의 공개 `scripts/fetch_upstream.py`로 commit `d9017d90e329112d2a80b7712f37ee9094d2cd27`의 원본 35개를 직접 취득했다. acquisition 단계는 길이·SHA256·Git blob SHA1을 확인하고 원본 코드를 실행하지 않았다. 자체 provenance helper가 고정 외부 manifest와 원본 소스 35개를 합한 36개를 검증했고, 전체 시험 후에도 동일한 SHA를 확인했다. 이전 체크아웃이나 진행 중인 v6의 원본 사본을 복사하지 않았다.

공개된 전체 215개 시험이 새 cwd와 자체 venv에서 통과했다. 공개 설치 검증에서 이미 고친 외부 audit guard 원문 `73321bb6f5a5625e135c69cb90dda475f5bbe5f692c9d6512b64e102365fb934`를 보존하고 원래 EvidenceResearch 프로젝트 읽기 차단만 외부 사본에 추가했다. package/tests/config 원문은 바꾸지 않았다. original project, fresh live study/owner, 모델 process, network 접근 계수는 모두 0이었다. 선언한 합성 standalone CPU 재현 subprocess 1회는 허용했다. 합성 실제 CPU runner가 포함된 unit suite를 실제 연구 trial이나 실제 모델 실행으로 표시하지 않는다. 경로 audit는 해당 process의 원래 프로젝트·새 체크아웃 경계에 관한 도구이며 OS 전체 sandbox 증명은 아니다. 이전 sibling clone을 실행하거나 별도 읽는 명령은 수행하지 않았다.

CLI doctor도 exit 0이었다. 샌드박스 인증 진단은 `Not logged in`이므로 인증된 모델 접근 성공을 주장하지 않는다. 새 실제 모델·연구 trial·owner 정답 자료 접근·pilot/final 등록·최종 평가·Goal 완료·개선 입증은 0 또는 false로 기록했다.

최종 receipt는 `result.json`, SHA `cf03c97e3dca2a783d935ba5252193a7759a39d159870e7d40b7738e3e9497b2`다. command, cwd, 단계별 시간, stdout/stderr SHA, source-before/after, venv cfg와 실행 파일 SHA, acquisition, fixed source inventory, 공개 guard 원문·외부 guard와 전체 시험 로그를 이 폴더에 보존했다. 성공한 단계는 반복하지 않았다. 네트워크가 사용된 범위는 승인된 공개 Git/source 취득이다.

새 빈 체크아웃에서의 실행 안내는 다음과 같다. 아래는 설치·engineering fixture 명령이며 실제 연구를 시작하지 않는다.

```powershell
git clone --filter=blob:none --no-checkout https://github.com/Malko-opensource/EvidenceResearch.git NEW_CHECKOUT
git -C NEW_CHECKOUT sparse-checkout init --no-cone
git -C NEW_CHECKOUT sparse-checkout set --no-cone /versions/v6-development/
git -C NEW_CHECKOUT checkout --detach 0be5988f4760263122188ef31e7f8dfba5ccea47
cd NEW_CHECKOUT\versions\v6-development
python -m venv .venv
.venv\Scripts\python.exe scripts\fetch_upstream.py
# Offline build requires local setuptools/wheel; runtime dependencies are empty.
.venv\Scripts\python.exe -m pip install --no-index --no-deps --no-build-isolation --editable .
.venv\Scripts\python.exe -m evidence_research doctor
.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
```

이번 실행에서 offline installer는 bundled runtime의 이미 설치된 setuptools/wheel을 임시 PYTHONPATH로 제공했다. 그 정확한 조건은 `offline-editable-install.json`에 있다. 일반 빈 Python venv에 패키징 도구까지 자동으로 들어 있다는 가정은 하지 않는다. 결과는 공개 설치와 구성·검증 fixture의 재현이며 실제 B/C 연구 개선 비교의 결론이 아니다.
