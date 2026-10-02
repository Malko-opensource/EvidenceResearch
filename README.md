# EvidenceResearch

실제 실행 증거, 검증된 성공·실패 기억, 목표에 따른 가설 선택과 독립 검증을 연결하는
연구 자동화 프레임워크다. [Agent Laboratory](https://github.com/SamuelSchmidgall/AgentLaboratory)와
[AgentRxiv](https://arxiv.org/abs/2503.18102)를 출발점으로 삼는다.

**현재 상태: 개발 및 비교 실험 진행 중. 기존 방식 대비 개선은 아직 입증되지 않았다.**
개발 과제의 실제 모델 실행과 CPU 실험, 독립 수치 재계산은 동작한다. 해당 확인을
최종 평가 통과나 일반적인 과학 연구 성능 향상으로 해석하면 안 된다.

현재 독립 개발 버전은 [v7 안내](docs/v7_development.ko.md)의 `0.4.0.dev0`이다.
공통 입력 경계와 실제 증거 자격 검사를 추가했고, 새 환경의 263개 공학 검사와
별도 38개 독립 구성 사례를 확인했다. 이는 실제 비교 개선이나 최종 평가 통과를
뜻하지 않는다. [v6 안내](docs/v6_development.ko.md)와 기존 결과는 원 조건으로 보존한다.

## 설치

Python 3.12 이상이 필요하다. 런타임 외부 의존성은 없다. 저장소 루트에서 v7로 이동한다.
이후 아래 설치·CLI 명령은 해당 버전 디렉터리에서 실행한다.

Windows에서는 짧은 새 clone 경로를 사용한다. 깊은 경로의 실패와 같은 공개
소스의 짧은 경로 재현은 [설치 검증 안내](docs/windows_install_replay.md)에 있다.

```powershell
Set-Location -LiteralPath versions\v7-development
python -m venv .venv
.\.venv\Scripts\python.exe scripts\fetch_upstream.py
.\.venv\Scripts\python.exe -m evidence_research doctor
```

Linux/macOS에서는 먼저 `cd versions/v7-development`를 실행하고 `.venv/bin/python`을 사용한다.
선택적으로 해당 환경의 `python -m pip install -e .`를
실행하면 `evidence-research` 명령을 설치할 수 있다. 실제 모델 실행에는
[Codex CLI의 기존 로그인](https://learn.chatgpt.com/docs/non-interactive-mode)이 필요하다.
`codex login`을 사용하며 API 키나 인증 파일을 저장소에 복사하지 않는다. CLI가 제한된
환경에서 로그인 정보를 읽을 수 없으면 기존 자격증명에 접근 가능한 승인된 셸에서
실행해야 한다. 계정에 없는 모델이나 구독을 넘어선 추가 결제를 자동으로 사용하지 않는다.

## 사전 등록과 실제 CPU 실행

```powershell
.\.venv\Scripts\python.exe -m evidence_research spec --task dev-quadratic --seed 7 --degree 2 --alpha 0 --output work\spec.json
.\.venv\Scripts\python.exe -m evidence_research --workspace work\demo run-spec work\spec.json
.\.venv\Scripts\python.exe -m evidence_research --workspace work\demo memory dev-quadratic
.\.venv\Scripts\python.exe -m evidence_research --workspace work\demo integrity
.\.venv\Scripts\python.exe -m evidence_research --workspace work\demo resume
```

같은 실행 조건의 완료 결과는 재실행하지 않는다. 가설 설명만 변경해도 실행 조건
지문으로 중복을 막는다. 실행 완료 영수증이 있으면 검증부터 재개한다. 실행 여부를
확인할 증거가 없으면 `unknown_execution`을 남기고 자동 재실행하지 않는다.

## 실제 모델의 자율 연구

```powershell
.\.venv\Scripts\python.exe -m evidence_research --workspace work\autonomous research --task dev-quadratic --seed 7 --model gpt-6.1-sol --target-mse 0.03
```

모델은 공개 학습·검증 데이터와 검증된 연구 기억을 보고 후보를 제안한다. 실행 전에
가설·평가 기준·분할·코드·자원 조건을 등록하고 고정 실행기가 실험한다. 독립 검증기가
실행기와 다른 수치 해법으로 모델과 지표를 재계산한다. 목표가 충족되지 않으면 다음
가설을 진행한다. 같은 명령으로 재개할 수 있으며 임의의 전체 연구 반복 한도는 없다.
개발 목표 충족은 전체 프레임워크 Goal 완료가 아니다.

현재 구현의 실험 권한은 고정된 다항 ridge 회귀 설정(`degree`, `alpha`)으로 제한된다.
임의로 생성된 코드를 실행하려면 별도의 OS sandbox와 평가·증거 보호가 필요하다.
모델의 도구 호출은 금지하며 원본 JSONL에서 발견하면 해당 실행을 비교에서 제외한다.

## 검증과 비교

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\core_validation.py --output work\core-validation
.\.venv\Scripts\python.exe ..\..\work\c7-independent-validation-v1\held-source-run-0003\fixture-snapshot\reproduce_components.py --capsule ..\..\work\c7-independent-validation-v1\held-source-run-0003 --output ..\..\work\t7\replay-new
```

단위검사의 모델 응답 fixture와 실제 모델 실행은 명확히 구분한다. core validation은
실제 CPU 실행으로 성공·실패 검색, 재사용, 재개, 중복 방지와 변조 거절을 확인한다.
마지막 명령은 별도 담당자의 최신 38개 구성 사례를 고정 소스 사본으로 재현한다.
새 짧은 출력 디렉터리를 사용하며 기존 증거를 덮어쓰지 않는다.
과거 기록의 경로와 시간은 당시 환경을 가리키며, 재현 지표·설정·소스 해시를 비교한다.
최종 B/C 비교는 [현재 v7 검증 범위](docs/v7_development.ko.md)에 따라 자체 개발 증거로
별도 사전 등록하고 새로운 과제와 고정 코드로 실행한다.
[초기 평가 설계](docs/evaluation_protocol.md)는 과거 버전의 근거로 보존한다.
A 원 연구 계열 모델에 접근할 수 없으면 그 한계를 기록한다.
논문 수치를 재현한 결과로 대입하지 않는다.

원본 baseline 소스는 다음 명령으로 고정 commit에서 받는다. 이미 받은 파일은
해시만 확인하고, 다른 바이트의 파일을 덮어쓰지 않는다. 원본 코드를 취득할 때
실행하거나 그 의존성을 설치하지 않는다.

```powershell
.\.venv\Scripts\python.exe scripts\fetch_upstream.py
.\.venv\Scripts\python.exe scripts\fetch_upstream.py --offline
```

GitHub 저장소는 코드·취득 manifest·실행 기록을 포함한다. 로컬에서 검토한 논문
PDF와 원본 ZIP은 게시하지 않으며, 원문 링크와 고정 버전을 남긴다.

개발용 paired pilot은 실행 전에 다음처럼 등록한다. 설정 파일은 모델·추론 수준·
도구·CPU 및 모델 호출 자원·개발 과제와 seed를 명시한다. 등록 후 변경된 코드를
같은 연구에 섞지 않으며, 한 연구에는 실행 프로세스 하나만 사용한다.

```powershell
.\.venv\Scripts\python.exe -m evidence_research.study pilot-sample-config --base-config examples\sampled-pilot-base-c7.json --variance-relative-se 0.5 --output work\my-pilot-private.json
.\.venv\Scripts\python.exe -m evidence_research.study pilot-register --config work\my-pilot-private.json --output runs\my-pilot
.\.venv\Scripts\python.exe -m evidence_research.study pilot-run --output runs\my-pilot
```

owner 설정·난수·test 행은 로컬에 보존하고 참가자 입력이나 공개 저장소에 넣지 않는다.
초기 9쌍은 분산 정밀도 설계이며 전체 연구 루프의 제한이 아니다.
같은 `pilot-run` 명령은 완료된 arm을 검증해 재사용한다. 본문과 JSON companion의
숫자는 별도 독립 판정 파일을 `pilot-review --report-kind primary|companion`으로,
의미 주장은 `pilot-semantic-review --report-kind primary|companion`으로 연결한다.
양쪽 검토가 완료되고 실제 증거 자격을 충족해야 한다.
확정된 무동작 외부 실패를 재개할 때는 원본 영수증을 검사하는
`pilot-continue --output ... --unit ... --arm B|C --reason ...`을 사용한다.
실행 여부가 불명확하거나 등록된 자원이 소진됐다면 재실행을 거절한다.

- [원문과 현재 코드의 근거](docs/sources.md)
- [원본 baseline 어댑터와 차이](docs/baseline.md)
- [설계](docs/design.md)
- [한국어 연구 보고서](REPORT.ko.md)
- [후속 핸드오프](HANDOFF.md)
- [저장된 진행 상태](STATUS.json)

수치 결과는 실행 증거의 경로·해시와 연결한다. 구독 사용량을 달러 비용으로
환산하지 않고 실제 청구 증거가 없으면 비용은 `null`로 기록한다.
`.gitattributes`는 증거와 소스 사본의 줄바꿈을 포함한 원래 바이트를 보존한다.
완료된 증거를 편집기로 다시 저장하거나 줄바꿈을 변환하면 해시 검증이 실패한다.

완료된 최소전이 개발 짝 `linear-seed7`의 CPU 지표와 원시 모델 자원은 다른
checkout 경로에서도 읽기 전용으로 재계산할 수 있다. 다음 명령은 모델을 새로
호출하거나 연구 실행을 반복하지 않는다. 원본 경로는 파일을 찾기 위한 기준이며
당시 사용자의 절대 경로를 실제로 열지 않는다. 새 출력 경로를 지정한다.

```powershell
Push-Location -LiteralPath ..\..
versions\v7-development\.venv\Scripts\python.exe -X utf8 evaluation/replay_published_pair.py --root . --recorded-root 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch' --registration-sha256 a8fdd8c5500961350b289b8798a0ee9dde116ed2d07ee0ef13e131701ec0be92 --out work/published-pair-replay.json
Pop-Location
```

이는 원본 해시·독립 fit·예측·별도 test MSE·원시 provider 토큰과 시간의
재계산이다. 전체 보고서의 의미를 다시 판정하거나 최종 개선을 입증하지 않는다.
선택한 개발 짝의 평가 자료는 실행이 끝난 후 재현용으로 공개했으며, 이후에는
개발 자료로 취급한다. 진행 중인 과제와 미래 최종 평가 자료는 제공하지 않는다.

원본 권장 단계 비교를 도입한 [별도 v5 버전](versions/v5-development/README.md)은
역사적 개발 기록으로 보존한다. 현재 개발 소스와 새 비교는 v7의 자체 환경·
source snapshot·등록을 사용하며 메인 v4와 기존 결과를 덮어쓰지 않는다.
프레임워크 개선이나 최종 채택은 아직 미입증이다.
