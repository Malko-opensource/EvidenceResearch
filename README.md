# EvidenceResearch

실제 실행 증거, 검증된 성공·실패 기억, 목표에 따른 가설 선택과 독립 검증을 연결하는
연구 자동화 프레임워크다. [Agent Laboratory](https://github.com/SamuelSchmidgall/AgentLaboratory)와
[AgentRxiv](https://arxiv.org/abs/2503.18102)를 출발점으로 삼는다.

**현재 상태: 개발 및 비교 실험 진행 중. 기존 방식 대비 개선은 아직 입증되지 않았다.**
개발 과제의 실제 모델 실행과 CPU 실험, 독립 수치 재계산은 동작한다. 해당 확인을
최종 평가 통과나 일반적인 과학 연구 성능 향상으로 해석하면 안 된다.

## 설치

Python 3.12 이상이 필요하다. 런타임 외부 의존성은 없다. 새 프로젝트 디렉터리에서:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m evidence_research doctor
```

Linux/macOS에서는 `.venv/bin/python`을 사용한다. 선택적으로 `python -m pip install -e .`를
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
```

단위검사의 모델 응답 fixture와 실제 모델 실행은 명확히 구분한다. core validation은
실제 CPU 실행으로 성공·실패 검색, 재사용, 재개, 중복 방지와 변조 거절을 확인한다.
최종 B/C 비교는 [사전 평가 설계](docs/evaluation_protocol.md)에 따라 별도 과제와
고정 코드로 실행한다. A 원 연구 계열 모델에 접근할 수 없으면 그 한계를 기록한다.
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
