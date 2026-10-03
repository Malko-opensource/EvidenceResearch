# v9 개발 소스와 검증 범위

`versions/v9-development`의 `0.5.0.dev1`은 고정 CPU 회귀 과제에서 증거를 연결하는
연구 프레임워크다. 실제 B/C 개선과 최종 평가는 아직 입증하지 않았다.
원 Agent Laboratory 코드 commit `d9017d90e329112d2a80b7712f37ee9094d2cd27`과
AgentRxiv의 누적 연구 구상을 기반으로 한다. 모델·문헌·도구 어댑터의 범위는
[설계](design.md), [원문 근거](sources.md)와 버전 내부 문서에 기록했다.

입력 경계는 최초 등록 경로·해시·값을 연결하고, 공개 데이터의 ID·분할·해시를
검사한다. 보고서의 과거 시점 수량은 그 모델 요청 전에 완료된 증거만 사용한다.
모델의 원래 제안 문자열을 찾았다는 사실은 그 제안의 내용이나 읽음을 입증하지 않는다.
전체 primary와 companion의 숫자 및 의미 주장은 별도 고정 검증을 통과해야 한다.
실험은 literal `degree`와 `alpha` 설정만 실행하므로 생성 코드가 평가기를 수정할 수 없다.
Python 역할·해시 보호를 전체 OS 격리나 임의 파일 읽기 차단으로 해석하지 않는다.

| 공학 확인 | 정확한 범위 | 원본 바이트의 공개 사본 |
| --- | --- | --- |
| 전체 공학 사례 | 원 357개와 후속 7개의 두 실행; 원 실패 보존 | [357+7 증거](../evidence/v9-engineering-release-v1/coverage364/result.json) |
| 독립 구성 사례 | 원 13개 계열·63개 ID/기준, 새 54+보존 8+후속 1; 이전 소스의 55개 판정 승격 없음 | [63개 연결](../evidence/v9-engineering-release-v1/coverage63/result.json), [메타데이터 검토](../evidence/v9-engineering-release-v1/coverage63/metadata-peer.json) |
| 자체 환경 | 정확한 101개 선택 검사, CLI 도움말 2개, 참조 38개 | [결과](../evidence/v9-engineering-release-v1/verification/result.json), [실행 로그](../evidence/v9-engineering-release-v1/verification/new-contract-portability.stderr.log) |
| 독립 설치 출력 검토 | 시험 ID·원시 로그·영수증·환경·참조·guard 대조; 시험 재실행 없음 | [후속 검토 캡슐](../evidence/v9-installed-output-peer-public-v1/manifest.json) |

하나의 새 실행에서 364개 또는 63개가 모두 통과한 결과가 아니다. 실패한 원 전체
검사와 사례의 판정은 [이력 요약](../evidence/v9-engineering-release-v1/history-summary.json)에
해시로 연결한다. 첫 공학 캡슐의 설치 peer `pending`은 작성 당시 상태다. 이후 봉인한
검토를 별도 캡슐에 연결하며 앞선 기록을 소급 수정하지 않는다.

런타임 원본은 125파일이며, 게시하는 정적 소스는 87파일이다. 원 업스트림 35파일은
고정 취득 도구로 받고 이전 선택 예제 3개는 새 게시 선택에서 제외한다. 참조 본문
40파일과 실행 시 인증하는 참조 38파일을 구분한다. [파일·해시 목록](../evidence/v9-engineering-release-v1/manifest.json)에
원본과 사본의 대응을 기록했다. 합성 raw 사례 전체를 게시하지 않아 이 부분집합만으로
외부 63개 감사 helper의 전 실행을 재현할 수 있다고 주장하지 않는다.

짧은 새 clone에서 해당 버전으로 이동해 원본을 취득한다. Python 3.12 이상을 사용한다.
런타임 외부 의존성은 없으며 editable 설치에는 별도 build 도구가 필요하다.

```powershell
Set-Location -LiteralPath versions\v9-development
python -m venv .venv
.\.venv\Scripts\python.exe scripts\fetch_upstream.py
.\.venv\Scripts\python.exe scripts\fetch_upstream.py --offline
.\.venv\Scripts\python.exe -m evidence_research --help
.\.venv\Scripts\python.exe -m evidence_research.study --help
```

다음 명령은 공개된 선택 목록의 101개 검사를 새 환경에서 실행한다. 기존 결과를
다시 쓴다는 뜻이 아니다. 원 검증의 guard와 역할 조건은 캡슐에 별도로 남아 있다.

```powershell
@'
import json, unittest
from pathlib import Path
p=Path('../../evidence/v9-engineering-release-v1/verification/test-inventory.json')
inventory=json.loads(p.read_text(encoding='utf-8'))
suite=unittest.TestSuite()
for name in inventory['selected_filenames']:
    suite.addTests(unittest.defaultTestLoader.discover('tests', pattern=name))
def leaves(s):
    for t in s:
        if isinstance(t, unittest.TestSuite): yield from leaves(t)
        else: yield t
assert sorted(t.id() for t in leaves(suite)) == inventory['test_ids']
r=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if r.wasSuccessful() else 1)
'@ | .\.venv\Scripts\python.exe -X utf8 -B -
```

실제 개발 비교는 별도 로컬 등록으로 진행한다. 양쪽은 `gpt-6.1-sol/medium`, 원
MLE3/Paper1/literature5/phase100, 같은 데이터·문헌·도구와 소스에서 유도한 공통
777 요청·CPU attempt 자원을 사용한다. 이 수는 단위 과제의 조건이며 Goal 반복
횟수나 실행 시간 한도가 아니다. 초기 9쌍은 `ceil(2/.5**2)+1`의 분산 정밀도 근사
계획이다. 최종 power나 효과 입증으로 사용하지 않는다.

owner 설정과 등록 원문에는 비공개 seed·과제 조건이 있으므로 로컬에 유지한다.
모델은 동일한 공개 train/validation 자료만 받는다. 원 연구 계열 A 모델은 실행할
수 없어 모델 교체 효과를 추정하지 않는다. B/C의 같은 모델 조건에서 프레임워크
묶음 효과를 비교하며 기억·선택·복구의 개별 인과 효과와 구분한다.

최종 채택은 사전 기준인 paired token gain CI95 하한 >20%와
log(test MSE C/B) CI95 상한 <log(1.10)을 모두 요구한다. 모든 등록 짝과 두 보고서의
실제 독립 검증·공통 sufficiency·unsupported 0도 필요하다. 개발 결과로 구현을
수정했다면 해당 과제는 개발 자료로 남기며 새로운 최종 과제와 표본 계획을 등록한다.
없는 비용과 실패 사용량은 `null`로 남긴다. 공학 통과는 이 채택 기준을 충족하지 않는다.
