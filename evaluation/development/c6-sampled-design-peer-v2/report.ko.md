# c6 표본 생성·비교 등록의 읽기 전용 재검토

검토한 후보 바이트를 `source_snapshot/`에 보존했다. 외부 전달용 snapshot pin은 `20185e5be3613bf4748fcf3410990a363bfefc42122865644d0d764e9b0dbf1e`이다. `isolated-result.json`과 `isolated-test.log`는 짧은 별도 작업공간 `work/s2`에서 캡처된 소스만 가져와 수행한 결과다. 원본 프로젝트를 읽는 시도, 실제 모델 호출, 실제 연구 runner, fitting, network, subprocess 호출은 모두 차단했으며 각 계수는 0이다. 기존 실행의 소유자 정답 행은 읽지 않았다. 테스트가 생성한 임시 소유자 자료는 합성 계약 fixture이며 실제 연구 결과가 아니다.

표본·등록 fixture 14개가 통과했고, 공개된 소스 58개 바이트는 실행 전후 같았다. 고정 업스트림 provenance helper가 반환한 36개 자료는 외부 고정 acquisition manifest와 35개 원본 소스이다. 최신 후보와 검토 snapshot의 바이트 차이가 없다는 점도 별도로 확인했다. 이는 이 fixture 범위의 검증이며 전체 suite나 실제 최종 비교 통과를 뜻하지 않는다.

앞선 후보에서 확인한 공개 RNG seed 재생, 과제 정의의 범위·해시만 검사하는 문제, 업스트림 소스 고정 누락은 다음 경로로 수정됐다.

- `tasks.sample_task_parameters`가 공개 논리 식별자와 비공개 분할 seed들을 구분한다. `task_data`는 비공개 seed가 있을 때 각 분할에 별도 generator를 사용한다. test 분할의 비공개 seed만 바꾸는 fixture에서 train/validation은 그대로이고 test만 달라졌다. 공개 논리 seed로 이전의 연속 RNG 경로를 재생한 test는 원래 분할과 달랐다. 공개 데이터에서 통계적으로 계수나 노이즈를 추정할 수 없다는 주장은 하지 않는다.
- `study._validate_sampled_pilot_draws`와 `evaluation._validate_final_suite_draws`가 동일 sampling law, 비공개 owner seed, 정의, 논리 식별자, 분할 seed, 순서와 개수를 다시 계산한다. 최종 public/private 자료도 그 생성 결과와 대조한다. 범위 안의 계수를 바꾸고 로컬 해시를 다시 계산하거나 최종 inventory를 줄이거나 순서를 바꾼 fixture는 거절됐다.
- pilot은 package와 별도로 36개 reference를 고정·보관하고 실행 소스와 archive 둘 다 대조한다. 실제 adapted final 등록은 같은 source/model/resource/full baseline provenance를 사용한 자체 sampled pilot을 요구한다. 이전의 고정 linear/quadratic/noisy pilot, 미완료 arms, failed/pending/불충분한 보고서를 분산 설계 입력으로 받아들이지 않는다. 완료 점수는 저장된 독립 검증 근거를 재감사하고 설계 입력을 다시 계산한다.
- pilot/final의 공통 law는 같지만 final 정의 목록은 등록한 development 정의들과 겹치지 않아야 한다. 양쪽 arm에는 같은 public task만 전달하며 비공개 생성 정의·분할 seed·정답 행은 payload와 CLI 요약에서 제외된다. 원본 workflow/문헌 entry 정책과 공통 보고서 평가 정책을 별도로 버전 고정한다.

통계 설계에는 여전히 실험 뒤 확인할 가정이 있다. `ceil(2 / variance_relative_se**2)+1`은 독립 쌍과 정규 이론의 표본 분산 근사에 따른 초기 파일럿 크기다. `max(observed SD, meaningful_gain/2)`는 선언한 planning floor이고 검증된 모집단 분산 상한이 아니다. relative test MSE gain은 B 분모가 작을 때 큰 음의 꼬리를 가질 수 있으며, percentile paired bootstrap도 작은 표본이나 비정규 꼬리에서 명목 coverage를 자동 보장하지 않는다. 현재 코드는 이 floor와 정규 근사를 검정력·확증 충분성의 증명으로 표시하지 않는다. 새 실제 파일럿의 분포, 실패·보류 상태와 실제 자원 자료를 관찰한 뒤 별도 최종 설계를 결정해야 한다. 동일 모델의 내부 sampling seed는 제공되지 않으므로 동일 공개 과제와 reasoning 설정이 같은 응답 난수까지 보장하지 않는다.

이 검토는 v5의 실패나 pending 결과를 재분류하지 않았고, 개선 효과·메모리 효과·모델 효과를 입증하지 않았다. source/read-only contract 범위 안에서 새 구체 결함을 발견하지 않았다는 결과만 전달한다.

재현은 이 폴더의 파일과 snapshot을 새 짧은 폴더로 복사한 후 실행한다. `--forbidden-root`에는 원래 프로젝트 절대 경로를 지정한다. 출력 result/log는 그 복사본에만 기록된다.

```powershell
python -X utf8 -B reproduce.py --manifest-sha256 20185e5be3613bf4748fcf3410990a363bfefc42122865644d0d764e9b0dbf1e --forbidden-root ORIGINAL_PROJECT_ABSOLUTE_PATH
```

초기 capture 시 존재하지 않는 `tests/__init__.py`를 목록에 넣어 파일 읽기 단계에서 중단됐다. 실제 snapshot이나 시험 실행 전에 발생했고, namespace test 구조에 맞춰 목록을 수정했다. 연구 runner 또는 모델은 실행되지 않았다. 이전 v1 발견과 소스는 그대로 보존했다.
