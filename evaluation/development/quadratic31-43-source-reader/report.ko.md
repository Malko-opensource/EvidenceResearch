quadratic seed 31과 43의 B/C 원문 및 companion 총 8개를 독립적으로 읽고 검산했다. 실제 predictions·등록된 조건·실행 receipt를 고정 verifier로 확인하고, 자원 수치는 원시 request/result/events에서 다시 계산했다. 숨겨진 owner test 관측값은 열지 않았다. 별도 guard 아래 재현 시 provider·실험 runner 호출 및 private owner row 열기는 모두 0회였고, 기존 참가자 산출물과 기존 review 802개 파일의 SHA는 전후 동일했다.

| 과제/arm | 원문 / companion 수량 occurrence | 실제 CPU / 서로 다른 설정 | provider 호출 | input / output tokens | provider 초 |
| --- | ---: | ---: | ---: | ---: | ---: |
| quadratic31 B | 290 / 121 | 2 / 1 | 26 | 757,663 / 15,403 | 716.613 |
| quadratic31 C | 54 / 52 | 19 / 19 | 20 | 882,630 / 8,454 | 440.220 |
| quadratic43 B | 328 / 111 | 2 / 1 | 26 | 758,893 / 15,010 | 681.750 |
| quadratic43 C | 51 / 49 | 25 / 25 | 26 | 1,291,288 / 10,356 | 530.860 |

8개 peer review는 unsupported 0, pending 0이다. occurrence는 regex 숫자와 추가로 읽은 number words·문헌 ID·수식 첨자를 합친 lexical 수량 위치의 개수이며 독립적인 과학적 주장이나 실험 반복 수가 아니다. provider 시간은 각 실제 완료 요청의 wall time 합계이며 전체 연구 시간·독립 검토 시간이나 비용이 아니다. 금전 가격과 독립 검토 token/time은 알 수 없다. 현재 사례에서 C의 provider token 사용량은 B보다 많으므로 이 결과를 비용 개선으로 주장하지 않는다.

실제 selected validation MSE는 B31 `0.007530714510483641`, C31 `0.007519794976732067`, B43 `0.008575589501453651`, C43 `0.008510616278258974`이다. 원문과 companion의 train/validation MSE가 원시 예측값의 독립 계산과 일치했다. C의 최솟값 선택, 실패 criterion 가설의 유지, stop_reason 및 보존된 가설 문장 속 과거 설정 간 비교도 실제 실행 목록과 대조했다. 이는 관찰한 validation 후보 집합의 비교이며 모집단 개선·유의성·전역 최적성·숨겨진 test 개선을 의미하지 않는다.

B의 원래 report-generation 요청에는 execution-0002의 지표 객체 하나와 전체 CPU 2회·조건 1개의 별도 누적 정보가 들어 있다. execution-0000은 hash-linked receipt로 연결되지만 그 요청의 선택 지표 객체는 아니다. 원문의 “other metrics not supplied”는 이 reporting input 범위로 해석하며, 호스트에 다른 원시 결과가 없다는 주장으로 바꾸지 않았다. 호스트 전체 두 실행은 실제로 같은 조건·같은 수치를 갖는다. 원문에 명시된 12/8개 후보와 남은 11/7개 후보는 실행 전 계획이며 추가 수행 결과로 채택하지 않았다. 등록 CPU 상한 51에서 실제 2회를 빼면 남은 49회가 된다.

C의 기대 정보 가치·stable local minimum·추가 degree 1 시도의 가치 같은 문장은 계획 추론이다. 그 수치를 독립 측정이나 확률로 승인하지 않았다. 실제 과거 validation 비교는 해당 원본 결과의 두 값과 차이에 연결했다. 미실행 또는 criterion을 충족하지 못한 가설은 proposal 및 failed evidence로 유지했다.

B31은 `independent_review/source-reader-v2`, 나머지 세 arm의 peer review는 `independent_review/source-reader-v3`에 있다. C31에 먼저 생성된 다른 독립 리뷰는 덮어쓰지 않았으며 해당 peer review를 별도 sidecar로 보존했다. B31/B43/C43의 원문·companion root review는 생성했다. 본 검토는 원문 및 main/v4 코드, study event/controller를 변경하지 않는다.

```powershell
python -B evaluation/development/quadratic31-43-source-reader/reproduce.py
```

[result.json](result.json)은 source·command·stdout/stderr·802개 원본 SHA와 변경 없음 검사를 연결한다. 각 arm의 source-reader 폴더에는 실제 전체 CPU history, resource audit, report-writing request 범위, 가설 실패와 비교 계산, primitive/supplemental inventory 및 helper 사본이 저장된다. 이 재현은 당시 로컬 연구 기록의 hash-linked 경로를 사용하며 이 보고서만으로 모든 원시 receipt의 임의 경로 이전 가능성을 주장하지 않는다.

보조 도구 수정도 분리해 기록했다. 첫 helper는 “one distinct configuration and two CPU attempts” 문장에서 뒤의 CPU 단어를 앞의 one에도 적용하는 분류 오류를 발견하고 중단했다. v2는 해당 quantity 바로 뒤의 문구를 기준으로 수정했다. C31의 이미 존재하는 다른 리뷰를 overwrite하려는 시도는 write_once에 의해 거부되었고, v3는 기존 리뷰를 보존한다. 또한 보존된 helper의 proposal grid가 Python tuple이고 JSON에서는 list인 차이 때문에 직접 재실행 equality guard가 중단되었다. 별도 `reproduce_quadratic31_43_reviews.py`는 write_once 입력의 JSON 동등 표현만 canonicalize한다. 판단·수치·원본 pinned helper 및 완료된 review는 변경하지 않았으며 guard 아래 전체 재현이 통과했다.

현재 v4는 최소 단계 전이 설정의 개발 진단이다. README 권장 원본 구성과의 일반 우월성이나 최종 개선 채택 근거로 사용하지 않는다. 보고서 정보·숫자 게이트는 문학적 품질, 일반 과학 발견 능력 또는 framework 개선을 입증하지 않는다.
