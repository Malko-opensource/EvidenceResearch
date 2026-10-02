# v8 개발 버전의 검증 범위

`versions/v8-development`의 패키지 `0.4.1.dev0`은 원래 B callback에 등록된 모델과 자원 봉투를 기록하고, 요청 전에 원본 조건을 검사한다. 원본 native 알고리즘과 모델 입력, 공통 도구·자원 조건은 유지한다. 조건이 누락되거나 달라진 등록을 완료된 과거 증거에 소급 보충하지 않는다.

별도 own 환경에서 설치, 패키지 위치·버전, CLI, 원본 참조 closure와 276개 검사를 확인했다. Python user site는 꺼져 있고, bundled build tools는 offline 설치 단계에만 노출했다. 일반 독자는 Python 3.12 이상으로 새 환경을 만들고 해당 디렉터리에서 설치 없이 `python -m evidence_research --help`를 실행할 수 있다. 선택적인 `pip install -e .`에는 build dependencies가 필요하다. 새 환경에 setuptools가 있다고 가정한 무조건적인 offline 설치 명령은 제공하지 않는다.

원본 참조 전체는 40개이며 실행 검증 closure는 38개다. README와 라이선스 두 문서는 전체 소스의 해시 인증에 포함하고 runtime closure와 구분한다. 공개 소스는 73개를 선택했다. 원본 upstream runtime 35개는 이 버전의 `scripts/fetch_upstream.py`로 고정 공개 snapshot을 취득하고 인증한다. 이전 실제 연구 경로를 가리키는 선택적 예제 세 개는 공개 선택에서 제외했다. 새 `examples/sampled-pilot-base-v8.json`은 units가 비어 있는 미래 등록용 metadata이며 실제 과제를 포함하지 않는다.

별도 독립 검증에서 등록된 10개 공격·통합 계열과 28개 하위 사례를 확인했다. 실제 callback writer와 prefix 연결, 누락·변경된 조건, 재해시 공격, 미래 요청 제외와 합성 자격의 유지가 범위다. Synthetic transport는 실제 보고서 지원이나 채택에 사용할 수 없다. 이 구성 검증과 설치 검사는 새 실제 모델 비교를 실행하지 않았다.

원시 검사 로그와 소스 해시, 선택한 실패 검토·fixture 기록은 공개 공학 증거에 연결한다. 공개 선택은 전체 로컬 synthetic 출력 tree를 포함하지 않으므로 해당 부분집합만으로 모든 외부 독립 helper의 전체 replay를 완료했다고 주장하지 않는다. 버전 소스의 회귀 검사 재현은 pinned upstream을 취득한 후 own Python에서 `-m unittest discover -s tests -v`로 실행한다.

검사 가드는 Python 부모 과정의 명시된 workspace 파일·network·process 이벤트를 확인한다. 허용된 작은 CPU fixture child는 부모의 hook 경로를 대체하므로 그 hook의 감시 밖이다. 이 결과를 OS 격리나 모든 파일 읽기 방지의 증명으로 해석하지 않는다.

콜백 등록의 연결 성공은 실제 보고서의 수치·의미 주장 완결성을 보장하지 않는다. 과거 자원 수치와 최종 합계의 구분, 자원 사용량의 불확실성, 실행 성공과 가설 기각의 구분 등 후속 통합 검증이 남아 있다. 이 수정은 별도 사전 등록된 로컬 사본에서 진행한다. v8의 실제 연구 등록과 별도 최종 평가는 실행하지 않았다.

현재 개선은 미입증이다. 같은 모델 B/C의 유효한 비교와 완전한 독립 보고서 검토, 사전 등록된 token 감소 및 MSE 비열등성 조건, 별도 손대지 않은 최종 평가가 필요하다. A 원 모델 계열은 사용할 수 없어 모델 교체 효과를 추정하지 않았다. 공학 검사를 연구 성능 개선으로 바꾸어 보고하지 않는다.
