# c7 독립 구성 검증

사전 고정한 36개 사례와 추가 회귀 2개를 고정 소스 사본에서 실행해 모두 통과했다. 실제 모델 호출과 연구 비교 실행은 없었다. 명시적인 작은 공개 합성 배열에 대한 trusted CPU 구성 실행은 최종 재현에서 12회였다.

양쪽 원래 입력 형식에서 같은 수치와 범위는 같은 정규화 사실을 반환했다. 전체·미래 비용 재표기, 영수증 누락·순서·중복, unknown 비용의 0 대체, 입력 경로를 값으로 취급하는 주장, 읽기·이해 주장, 산술 방향·단위·출처, 한영 문헌의 조건·극성, 미래 prior와 실행 후 조건, 혼합 긍정 문장·JSON key·누락 span을 검사했다. 같은 조건의 미래 CPU 영수증은 실제로 만들었고 원래 입력의 prior로 사용할 수 없음을 확인했다.

추가로 발견한 실패는 덮어쓰지 않고 이전 attempt에 보존했다. fixture 비용·CLI guard 형식이 모든 해시를 다시 계산한 공격에서도 검사되며, fixture CPU 측정과 측정 주장이 없는 보고서 모두 실제 채택 자격을 얻지 못한다. caller가 검토 JSON을 다시 해시하고 actual 라벨로 바꿔도 원 증거 재검산이 거부한다. boolean·null·unknown scope도 메타데이터 gate에서 거부한다.

원래 목록 309개 source/test/static-reference 파일은 변경이 없었다. 격리 재현에서 보호한 원본 경로 open/list/scandir 접근은 0이었으며 모델 호출도 0이다. 이 범위는 모든 형제 폴더나 운영체제 접근의 포괄적인 보안 증명을 뜻하지 않는다. 사적 owner/test 행과 진행 중 연구 기록은 읽거나 해시하지 않았다.

문헌 6개 fact와 영어·한국어 12개 유한 문형은 고정된 supplied synopsis의 출처·조건·극성 대응을 독립 검토했다. 논문 전체를 읽었다는 증명이나 임의 자연어의 진실 보증은 아니다.

구성 통과는 실제 연구 우수성을 입증하지 않는다. 기존 v6 보류 판정과 사전 채택 기준을 유지하며, 향상 판단에는 별도 고정 버전의 실제 개발 비교와 새로운 독립 최종 평가가 필요하다. 비용은 미계측이므로 null로 유지한다.

`result.json`은 정확한 case-map·source pin·추가 회귀 receipt를, `held-source-run-0003/source-manifest.json`은 자기 완결 source/fixture 사본을 제공한다. 재현 예시는 아래와 같다. 출력은 새로운 짧은 디렉터리를 지정해야 한다.

```powershell
python -X utf8 -B work/c7-independent-validation-v1/held-source-run-0003/fixture-snapshot/reproduce_components.py --capsule work/c7-independent-validation-v1/held-source-run-0003 --output work/t7/replay-next
```
