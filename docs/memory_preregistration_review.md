실제 기억 노출 진단의 사전 등록과 자원 검토

이 문서는 이미 등록된 `runs/development/memory-exposure-pilot-v1`의 실행 계약을 검토한다. 새로운 모델 호출이나 중복 등록을 수행하지 않았다. [등록 원본](../runs/development/memory-exposure-pilot-v1/ablation-registration.json)과 anchor가 완료된 준비와 모델 요청의 조건을 고정한다. 예제 설정의 `status` 문장은 예제를 작성한 시점의 설명이며 실제 상태를 판단하는 근거는 등록·실행·원시 요청 기록이다.

등록된 조건은 실제 공통 `gpt-6.1-sol`, 요청 effort `medium`, 같은 공개 train/validation 자료, 같은 seed, 같은 도구와 문헌이다. 원시 요청 감사는 실제 CLI의 모델·effort·읽기 전용 공개 cwd·사용자 설정 무시·approval never를 확인한다. 서버의 내부 샘플링 seed와 가중치 버전은 노출되지 않으므로 같다고 주장하지 않는다. 숨겨진 owner test 자료는 요청 payload에 포함하지 않는다.

ON/OFF의 치료 차이는 `verified_memory`뿐이다. 호스트가 결과 전에 선택한 degree=2, alpha=0의 anchor와 degree=8, alpha=100의 비교를 양쪽 Store에서 실제 CPU로 실행하고 검증한다. 이 선택을 모델이 발견한 설정으로 서술하지 않는다. 성공·실패라는 가설 판정은 실제 기준 계산에 따르며, 어떤 조건에 실패 기록이 없으면 실패 회피 지표는 적용 불가다. 두 조건은 같은 calibration 비용과 같은 중복 방지 기능을 가진다. OFF에는 최선값, 이전 설정 목록, 성공·실패 피드백, 출처 해시 등의 우회 노출을 추가하지 않는다. 기억을 제공하지 않는 조건에서도 완료된 실행은 중복 실행되지 않는다.

각 등록 과제·조건에는 다음 행동을 선택하는 의사결정 기회가 한 번 있다. 이는 연구 Goal의 루프 횟수 제한이 아니라 정보 노출의 첫 결정을 분리하는 좁은 실험 단위다. 공개 목표에 절대 성공 기준이 없으므로 모델의 목표 달성 자기평가는 과제 성공으로 채택하지 않는다. 증거와 불확실성에 근거한 `no_justified_experiment` 중단은 계획 결정으로 기록한다. 중단도 의사결정 분모에 남는다.

주요 지표는 `duplicate_OFF - duplicate_ON`, 즉 이전 실행 조건의 중복 제안 감소이며 유효한 중단 선택을 포함한다. 단위는 절대 비율 차이다. 등록된 의미 있는 차이 .10은 상대 감소율이 아니라 10 percentage points다. 유효한 중단 비율, 새로운 합법적 제안 비율, 실패 calibration 재제안, 새 CPU 실행 수, 실제 모델 토큰·시간, 독립 과제 지표를 함께 보고한다. 중복 CPU 실행은 실제 EXECUTE receipt와 고유 CPU 산출물 inventory를 대조한다. 기억 검색 hit만으로 효과가 있었다고 판단하지 않는다.

등록된 9개 개발 pair는 세 과제 계열의 서로 다른 seed를 사용한다. 작은 pilot의 분산 계획 근거는 `ceil(2/.5^2)+1=9`이며 전체 연구의 상한이 아니다. ON/OFF 요청 순서는 등록된 단위 인덱스에 따라 교차한다. 각 조건의 허용 모델·CPU 상한은 동일하게 51이지만 실제 첫 행동 요청은 조건당 하나다. 모든 pair가 완전하다면 실제 모델 요청 기회는 18개, 양쪽 calibration CPU는 36개, 새로운 합법 후보가 모두 제출되면 추가 CPU는 최대 18개다. 이 값들은 등록된 계약의 계산이며 실제 사용량은 원시 기록에서 별도로 센다. 가격은 알 수 없다.

재현용 CLI는 다음과 같다. 아래는 기존 실행의 명령 계약을 문서화한 것으로, 이 검토에서 실행하지 않았다. 동일 output의 `register`는 원본 조건을 대조하고, `prepare`는 완료된 CPU calibration을 재사용하며, `collect`는 완료된 원시 요청을 재사용한다. unknown 실행이나 변조는 자동 재실행하지 않는다.

```powershell
$memoryPython = 'C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$memoryScript = 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\scripts\memory_ablation.py'
$memoryOutput = 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\runs\development\memory-exposure-pilot-v1'
& $memoryPython $memoryScript register --config 'C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch\examples\memory-ablation-settings.json' --output $memoryOutput
& $memoryPython $memoryScript prepare --output $memoryOutput
& $memoryPython $memoryScript collect --output $memoryOutput
```

`design --output ... --destination NEW_DESIGN_PATH`는 완료된 실제 pair를 다시 감사하고 이 진단 자체의 분산으로 새 표본 설계 입력을 만든다. B/C pilot의 비용 분산을 기억의 이진 지표 분산으로 대체하지 않는다. incomplete·invalid·external failure 기회를 성공 실행으로 교체하거나 분모에서 제거하지 않는다. 전체 등록 pair가 필요하며, 독립 검토 후 새로운 확인 과제와 프로토콜을 따로 등록해야 한다. 자동 채택은 수행하지 않는다. 작은 이산 표본, 동률과 discordant pair의 2×2 수, bootstrap 경계의 한계도 검토해야 한다.

검증할 인과 범위는 호스트가 선택하고 실제 검증한 이전 증거를 첫 다음 행동에 노출하는 효과다. 자유로운 전체 연구, 장기간의 누적 연구, 과제 간 기억 전이, 최신 모델 효과, 프레임워크 전체의 품질·효율 개선으로 확대하지 않는다. 이 진단이 좋아도 사용자 Goal의 전체 완료 기준과 별도의 동일 모델 B/C 개선 입증은 계속 필요하다.

수집 후 독립 검토에서는 9개 짝의 중복 차이가 모두 0이었다. 이 결과로 효과가 없다고 입증한 것은 아니다. 이산 짝 차이 `D ∈ {-1, 0, 1}`에 일반 정규분산 함수의 작은 분산 하한을 적용한 후속 표본 수는 확인 평가에 사용하지 않는다. 양의 차이 확률에 대한 9개 무사건의 단측 95% 상한은 `1 - .05**(1/9)`이며, 관찰된 bootstrap `[0, 0]`도 모집단의 확실성을 뜻하지 않는다. 원본 계산을 보존했고 [독립 감사](../evidence/memory-pilot-independent-review/report.ko.md)에 판단과 원시 증거를 연결했다. 새로운 확인 실험이 필요하다면 이산 짝 지표에 적합한 설계와 별도 과제를 사전 등록한다.
