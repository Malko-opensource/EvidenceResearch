# 선택 사항: Laya 후보 선택 보조

## 책임과 계약

Laya 사용을 선택 사항으로 유지한다. CLI의 `laya prepare`는 외부 에이전트가 작성한 후보를 Laya 입력과 후보 ID 매핑으로 내보낸다. `laya resolve`는 외부 실행의 응답을 원 후보에 연결한다. 모델 설치·호출·체크포인트·자원 설정과 최종 과학적 선택은 외부 에이전트의 책임이다. CLI는 모델을 가져오거나 실행하지 않으며 런타임 의존성을 추가하지 않는다.

기존 확장의 코드는 가져오지 않는다. 새로운 입력은 `goal_id`, `question`, 선택 사항 `context`, `candidates`다. 후보에는 `id`, `hypothesis`, `applicability`, `conditions`, 선택 사항 `evidence`(기존 등록 ID 목록)와 `observation`이 들어간다. observation은 외부 선언이며 측정 증거가 아니다. 후보 순서와 전체 조건은 보존한다. 연결한 연구 기억의 실행·검증·결정과 현재 파일 무결성은 저장소에서 읽는다.

prepare는 같은 읽기 트랜잭션에서 목표와 참조 기억을 조회한다. bundle에 입력, snapshot, workspace/revision, 짧은 label 매핑, 명시적 option_order, SDK request와 canonical SHA-256을 반환한다. 배열과 option_order가 순서를 고정한다. 별도 저장한 예상 해시와 원래 bundle을 resolve에 제출해야 한다. 다른 저장소·변경된 revision·현재 증거 불일치는 새 prepare를 요구한다. 해시는 입력 연결 검사이며 인증이나 OS 격리가 아니다.

resolve는 알려진 선택 label만 받아 원 후보 ID를 반환한다. 결과 kind는 항상 proposal, verified는 false이며 외부 검토가 필요하다. 명시적 기권·low_confidence·보고된 옵션 충돌은 기권으로 남긴다. 검증·채택·실험 실행 상태를 변경하지 않는다. 연구 기억에 연결하려면 기존 evidence 명령으로 제안 파일을 보존한다.

문자 수로 SDK의 토큰 보존을 보장하지 않는다. formatter는 텍스트를 자르지 않지만 외부 SDK의 토큰 경계 검사는 별도다. 사용한 SDK/모델 버전, tokenizer, head/context 설정, 기권 정책과 실제 자원을 외부 실행 기록 및 후속 비교 사전등록에 남긴다. confidence는 과제 성공 확률로 사용하지 않는다.

## 사용

후보 입력 예제를 확인하고 실제 목표 ID와 후보로 바꾼다.

```powershell
research-state --workspace .\my-research help --topic laya
research-state --workspace .\my-research laya prepare --input candidates.json --output laya-bundle.json
```

stdout의 `data.sha256`을 별도로 보존한다. 출력 파일에는 JSON envelope 없이 bundle 자체가 들어가며, 기존 파일은 덮어쓰지 않는다. SDK request의 `state`, `questions`를 외부 에이전트의 Laya 환경에 전달한다. [공식 SDK 안내](https://github.com/NandhaKishorM/laya/blob/fa9a2a7070b1789912a49ae24603bbfb1a78b001/README.md)의 Router 인터페이스를 참고한다. 별도 환경에서 실행하는 예시는 다음과 같다.

```python
import json
from pathlib import Path
from laya import Router  # 외부 에이전트 환경에 선택적으로 설치

bundle = json.loads(Path("laya-bundle.json").read_text(encoding="utf-8"))
request = bundle["request"]
response = Router().predict(request["state"], request["questions"])
with Path("laya-response.json").open("x", encoding="utf-8") as stream:
    json.dump(response, stream, ensure_ascii=False, allow_nan=False)
```

이 코드는 연구 CLI에서 실행하지 않는다. 모델·토큰 설정은 외부 사용자가 과제에 맞춰 고정한다. 위 기본값 호출은 최소 연결 예시이며 연구 평가의 고정 설정을 대신하지 않는다.

```powershell
research-state --workspace .\my-research laya resolve --input laya-bundle.json --response laya-response.json --expected-sha256 SAVED_DIGEST --output laya-proposal.json
research-state --workspace .\my-research evidence --registration REG_ID --kind proposal --claim "Laya의 미검증 후보 제안; 최종 선택은 외부 에이전트가 검토" --path laya-proposal.json
```

`laya resolve`는 SDK의 원 응답, 입력 bundle과 연결 해시를 제안 파일에 보존한다. 후보는 아직 실행되지 않은 제안이고 참조된 과거 결과의 검증과 분리된다. memory/show에서 해당 제안은 unverified로 조회된다. 저장소가 바뀌면 이전 bundle을 편집하지 말고 새 출력 파일에 prepare부터 수행한다.

## 검증과 후속 평가

모델 없이 입력 계약, 순서·ID 연결, 해시·revision·증거 변경 거부, 기권과 상태 비변경, 파일 보존을 검사한다. 실제 Laya 추론·토큰 보존·선택 품질·연구 개선은 이 검사의 범위에 포함하지 않는다. 기존 v0.1.0 비교와 v0.2.0 개발 실연에는 Laya가 없었으며 결과를 합치지 않는다. 후속 사용/미사용 비교는 같은 후보 풀과 연구 에이전트 조건으로 따로 사전등록하고 Laya의 추가 모델·시간·토큰 자원을 기록한다.

0.3.0에서 새 계약 검사 10개와 전체 32개가 통과했다(`validation/laya-tests.json/log`). v0.3.0 wheel의 오프라인 설치 후 소스 패키지를 참조하지 않는 실행에서도 prepare/resolve를 확인했다(`validation/laya-installation.json`, `validation/laya-smoke/transcript.json`). 사용한 응답은 합성 fixture이고 실제 Laya 추론 결과가 아니다. 실행 의존성은 계속 0개다.

입력 호환성 참고점은 공식 저장소 commit `fa9a2a7070b1789912a49ae24603bbfb1a78b001`이다. [토큰 경계 구현](https://github.com/NandhaKishorM/laya/blob/fa9a2a7070b1789912a49ae24603bbfb1a78b001/laya/common.py)은 별도 SDK가 후보·상태 텍스트를 절단할 수 있음을 보여준다. 새 formatter가 원 SDK 코드나 과거 구현을 포함하는 것은 아니다.
