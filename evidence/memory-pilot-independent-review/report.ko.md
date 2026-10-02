# 연구 기억 ON/OFF 개발 파일럿 독립 검토

원자료와 통제 조건은 재검증에 통과했다. **주 평가 항목인 중복 제안 감소는 관찰되지 않았으며, design-input의 후속 9쌍을 확증 설계로 승인하지 않는다.** 현재 등록·스크립트·main package·원본 산출물을 변경하지 않았다. 모델 호출이나 실험 runner 실행도 추가하지 않았다.

[독립 재계산 결과](independent-review.json)는 모든 수치의 원본 경로·SHA와 검증 결과를 연결한다. [재현 스크립트](review.py)는 모델 provider나 fitting runner를 호출하지 않는다. SQLite는 원본 DB/WAL/SHM을 별도 reviewer 작업공간에 복사하고 읽기 전용으로 조회했다. 원본 파일 전체의 검토 전후 SHA가 동일했다.

## 원자료와 통제

등록된 source19개의 현재 파일과 저장 snapshot 해시가 일치했다. 실제 모델 요청18개는 gpt-6.1-sol/medium, 단일 정상 completion, 관찰된 tool event0이며, raw request/result/response/events/stderr 해시와 CLI 설정·usage를 재감사했다. 내부 샘플링 seed와 서버 weight 버전은 공개되지 않으므로 동일한 내부 난수까지 통제됐다고 표현하지 않는다. filesystem에 대한 읽기 방지는 여기서 검증한 OS 보안 경계가 아니며, 원시 이벤트상 tool 사용이 없다는 관찰에 근거한다.

9쌍 모두 공개 payload는 verified_memory를 제외하면 정확히 같고, raw full_prompt의 guard도 같았다. 공개 task에는 train/validation과 test 분할의 해시 metadata만 있고 숨겨진 test rows/정답/점수는 없었다. ON은 사전에 host가 정한 두 calibration의 실제 검증 기록을 받고 OFF는 빈 verified_memory를 받았다. 다른 필드에 current best나 calibration 결과가 추가로 노출되지 않았다.

calibration은 degree2/alpha0과 degree8/alpha100으로 모델 선택이 아니다. 두 조건에서 설정·seed·split·실측 metrics가 같았고, 실제 CPU54회 중36회가 calibration,18회가 모델이 제안한 새로운 구성 실행이었다. 기준을 충족하지 못한 calibration18개와 전체 criterion miss27개는 ledger와 memory에 그대로 저장됐다. 이는 실행 crash가 아니라 **정상 실행·유효 측정 후 사전 기준 미충족**이다. 실패 기억의 조건·지표·failure_reason·원본 증거 해시를 검사했다. 각 ledger의 hash chain, 등록·실행·검증 manifest, execution index와 결과 선택이 유효했다.

선택된 각 모델의 public validation MSE는 고정 검증기로 재계산했다. test MSE는 owner test rows와 실제 저장 weights로 독립 산술 재계산했으며 raw rows는 이 검토 산출물에 복사하지 않았고 모델에게 보내지 않았다. 모든 단위는 처음부터 개발 과제이며 별도 최종 평가로 전용하지 않는다.

## 관찰 결과

| 항목 | ON | OFF |
|---|---:|---:|
| 실제 모델 요청 | 9 | 9 |
| 중복 제안 | 0 | 0 |
| 유효 stop | 0 | 0 |
| 신규 제안과 실제 신규 CPU 실행 | 9 | 9 |
| calibration 포함 실제 CPU 실행 | 27 | 27 |
| 입력 토큰 | 241533 | 231655 |
| 출력 토큰 | 1331 | 947 |
| cached input 토큰 | 135424 | 135424 |
| 실제 모델 wall seconds 합 | 99.078 | 83.640 |
| 실제 CPU seconds 합 | 0.131311700 | 0.134734800 |
| 실제 화폐 비용 | 알 수 없음 | 알 수 없음 |

2×2 paired counts는 양쪽 비중복9, 나머지 세 cell0이다. 따라서 OFF_duplicate−ON_duplicate는9쌍 모두0이다. host의 같은 content deduplication은 두 조건 모두에 적용됐으며 실제 중복 CPU 실행도0이다. 기억이 선택을 바꾸거나 중복을 예방했다는 주 효과를 이 자료에서 주장할 수 없다.

아래 부항목은 **탐색적 기술 통계**다. ON은9쌍 모두 더 긴 입력을 사용했고 합계9878 입력 토큰과384 출력 토큰이 추가됐다. 실제 model wall seconds 합은15.438000초 더 길었으며 한 quadratic 단위가 큰 차이를 차지한다. 직렬 요청·counterbalanced order·cache·서버 변동을 가진 작은 자료이므로 이 차이를 일반적인 인과 비용 증가로 추정하지 않는다. 토큰은 raw provider usage이며 화폐 비용으로 변환하지 않는다.

| 개발 단위 | 중복 감소 OFF−ON | 입력 토큰 ON−OFF | wall seconds ON−OFF | test MSE ON−OFF |
|---|---:|---:|---:|---:|
| linear-seed201 | 0 | 1081 | 0.125000 | 0 |
| linear-seed307 | 0 | 1095 | -0.140000 | 0 |
| linear-seed419 | 0 | 1081 | 0.969000 | 0 |
| quadratic-seed503 | 0 | 1093 | 11.375000 | 0 |
| quadratic-seed617 | 0 | 1104 | -0.969000 | 0 |
| quadratic-seed733 | 0 | 1106 | 0.734000 | 0 |
| noisy-seed809 | 0 | 1110 | 3.390000 | 0 |
| noisy-seed911 | 0 | 1100 | 0.469000 | -6.6244877409e-05 |
| noisy-seed1009 | 0 | 1108 | -0.515000 | 0 |

선택된 설정과 test 지표는8쌍에서 같았고 noisy-seed911 한 쌍에서 달랐다. 그 단위의 ON validation MSE는 OFF보다 약0.042190646 높았고 test MSE는 약0.000066245 낮았다. 전체 paired test 차이 평균은-7.36054193434e-06, validation 차이 평균은0.00468784954139이다. 서로 다른 noise regime의 pooled MSE와 단 한 개의 달라진 샘플을 기억 효과의 확증 근거로 채택하지 않는다. 이 부항목은 사전 주 평가 항목이 아니고 다중 비교 교정이나 별도 검정도 수행하지 않았다.

## 표본 설계 판단

원본 design-input은 관찰 std0에 floor0.05를 적용해 planning std0.05, normal power_n2/precision_n4/variance 최소9 중 최대인9를 반환했다. 산식 실행은 맞지만 이산 paired endpoint의 충분한 검정력·정밀도를 보장하지 않는다. normal variance relativeSE 공식은 여기의 zero-event 비정규 자료로 정당화되지 않았다. percentile bootstrap [0,0]은 관찰한0만 다시 뽑은 결과이며 모집단 효과가 정확히0이거나 유의미한 효과를 배제했다는95% 보장이 아니다.

[NIST의 작은 사건 수에 대한 exact binomial interval 지침](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)에 따라, 독립·동일한 paired opportunity라는 가정하에서 관찰 discordance0/9의 단측95% 상한을 직접 계산하면 1−0.05^(1/9)=0.283129이다. 이는 효과 자체의 완전한 paired confidence interval이 아닌 정보 부족을 보여 주는 계산이다. 실제 discordance 확률0.10이어도9개에서 사건을 하나도 못 볼 확률은0.9^9=0.387420이다. 세 task strata와 미공개 모델 난수 때문에 i.i.d. 가정 자체도 확인이 필요하다.

추가로 D=duplicate_OFF−duplicate_ON은 −1,0,1이다. E[D]=0.10인 대안을 고려하면 E[D²]=P(D≠0)≥0.10이고 Var(D)≥0.10−0.10²=0.09이므로 population SD는 최소0.30이다. 이 대안에 planning SD0.05를 쓰는 것은 보수적인 분산 하한이 아니다. 자동 산식의 floor가 데이터 부족을 해결하지 못한다는 직접적인 이유다.

따라서 후속 확증 설계는 현재 n9을 그대로 승인하지 않고, paired binary 사건·discordance의 유효한 가정과 exact/simulation 기반 power·precision을 별도로 등록해야 한다. 또한 현재 두 calibration은 다음 정상 제안과 충돌할 기회가 적다. 더 많은 같은 구조의 zero-event 단위를 반복하는 것만으로 유용한 기억 효과가 잘 식별되는 것은 아니다. 다음 개발 설계는 성공·실패·미결 기억이 실제 선택에 관련되는 조건과 충분한 중복 기회가 있는 과제를 사전에 정의하고, 주 항목과 비교 조건을 고정한 뒤 평가한다. 결과를 보고 현 endpoint·기준을 소급 변경하지 않는다.

등록 config 안의 status 문구에는 원래 예제의 “미등록/미실행” 설명이 남아 있다. 실제 등록 timestamp·원시 모델 completion18개·CPU 증거가 실행 상태의 근거이며, 이 고정 문구만으로 현재 상태를 판정하지 않았다. 원본 문구는 보존하고 향후 문서 generation에서 상태를 구분해야 한다.

이 검토는 원자료의 유효성과 성공·실패 기억 노출이 작동했다는 구현 증거를 확인했다. 누적 연구·cross-task 기억·자유 연구 전체 루프의 일반적인 성능 향상이나 프레임워크 Goal 완료는 주장하지 않는다.

재현: 프로젝트 루트에서 `python evidence/memory-pilot-independent-review/review.py`를 실행한다. 원본 데이터는 읽기만 하고 reviewer 작업공간과 JSON 결과만 작성한다.
