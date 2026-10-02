새 c6 후보의 초기 데이터·표본 계획·소스 경계를 읽기 전용으로 검토했다. 검토한 패키지 19개와 sampled fixture 1개를 byte snapshot으로 보존했으며 manifest 고정 SHA-256은 `1b5599375714816490e5c6563681562be934187259f7e99172d9f37a79a0b608`이다. 실제 원본 owner 자료를 열지 않았고, 모델이나 연구 CPU 실행기를 호출하지 않았다. 이는 이후 수정할 후보의 과거 상태를 나타내며 v5 또는 현재 후보의 결과 판정을 바꾸지 않는다.

양쪽 factory가 같은 `sample_task_definition`과 선언된 degree/coefficient/noise/train-size 분포를 사용하는 점은 확인했다. 모델 payload에는 공개 train/validation bundle만 있고 owner definition과 owner sampling seed를 넣지 않는다. final 등록은 자기 sampled pilot의 전체 독립 판정 완료, 같은 model/resource, 새 definition 배제와 score에서 재계산한 계획을 요구한다. 이전 고정 세 과제의 분산을 새 분포로 옮기는 경로는 닫는 방향이다. 공통 숫자와 의미 판정 조건도 유지한다.

초기 소스에서 확인한 세 가지 한계는 `finding.json`에 있다. 첫째, `frozen_sources`는 패키지 19개만 나열하고 upstream source 35개를 포함하지 않았다. 합성 module 바이트를 바꾸면 기존 loader가 둘 다 받아 실행 후의 SHA를 기록하는 조건을 별도 fixture에서 확인했다. 실제 원본 파일은 변경하지 않았다. 부모 에이전트 승인으로 후보 baseline/arms에 외부 manifest·module 고정 값 검사를 추가한다. root는 별도 references archive/freeze와 전체 baseline provenance 매칭을 연결해야 한다.

둘째, sampled definition의 값이 선언 범위 안이고 새 digest와 맞으면 owner seed에서 실제 뽑힌 값과 달라도 초기 `_pilot_definition`이 받아들였다. 범위 소속은 sampling sequence의 증명이 아니다. 합성 객체 하나의 coefficient를 바꾸고 digest를 갱신한 경우로 확인했으며 owner 행을 파일에 저장하지 않았다. root는 owner RNG에서 sequence를 재생하여 definition과 data seed를 등록 전에 대조하는 설계를 추가한다.

셋째, 공개된 data seed와 결정적인 잡음 생성 코드가 함께 있으면 잡음의 표준정규 값 `z`를 재생할 수 있다. 공개 관측의 `y = polynomial(x) + sigma*z`를 선형계로 풀면 숨겨진 계수와 잡음 크기가 식별될 수 있고, 후속 RNG 행도 예측할 수 있다. 기존 owner 행을 사용하지 않은 작은 임의 합성 예제에서 parameter 오차는 `6.106226635438361e-16`, 다음 label 예측 오차는 `8.881784197001252e-16`이었다. 실제 에이전트가 이런 방법을 사용했다는 근거는 없다. literal 도구와 no-tools transport는 실제 악용 능력을 제한하지만, 정보가 숨겨졌다는 더 강한 주장은 성립하지 않는다. root는 공개 logical seed와 실제 데이터 생성용 비공개 split seed를 분리하고, owner-only 생성 receipt를 보존하는 설계를 추가한다.

처음 peer helper를 `inspect.py`라고 이름 붙여 Python 표준 `inspect` import를 가리는 bootstrap 오류가 있었다. `review.py`로 이름을 바꾸고 재현했다. 그 오류 때 연구 실행이나 모델 호출은 없었다.

표본 수 식 `ceil(2/variance_relative_se**2)+1`은 독립 정상 paired unit의 sample variance 상대 표준오차에 대한 기획 근사다. 조건을 문서에 명시하는 것은 적절하지만, 그 식의 9개 자체가 새 결과 분포의 정상성이나 최종 검사의 충분한 검정력을 입증하지 않는다. 효과 비율과 비용 비율의 왜도, 극단치, 미지 토큰의 보수적 bound와 정상 근사·bootstrap의 coverage 한계를 새 pilot 자료에서 검토해야 한다. `meaningful_gain/2` scale floor는 0 분산으로 계획이 퇴화하는 것을 막는 장치이며, 미관측 분산의 상계 또는 보수적인 충분성 증거로 확립된 값이 아니다. 실패·미결 pilot을 성공 표본만으로 대체해서는 안 되며, 미결이 남아 새 계획을 만들 수 없다면 그 제약을 별도로 보고해야 한다.

재현은 `review.py --manifest-sha256 1b5599375714816490e5c6563681562be934187259f7e99172d9f37a79a0b608`이다. 이 과거 finding의 재현과 이후 수정 후보의 통과 검사는 분리해야 한다.
