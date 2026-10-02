# v8 개발 소스: callback 조건 전달 수정

패키지 식별자는 `0.4.1.dev0`이다. 이 후보는 B callback writer와 독립 ContextBoundary auditor 사이의 metadata 계약을 전향적으로 맞춘다. 이전 실행이나 완료 증거를 채우거나 다시 판정하지 않는다. 연구 향상이나 Goal 완료를 주장하지 않는다.

B writer가 최초 payload의 `model_id`와 전체 `resource_envelope`를 C와 같은 최상위 필드로 기록한다. Recorder 생성 및 요청·보고 단계 capture 전에 원래 callback 링크/SHA, model, public task와 자원 전체 해시, 명시적 reasoning effort, 실행 소스 8개를 대조한다. provider 모델과 effort도 입력 기록 전에 검사한다. 누락·변조·source 불일치는 새 입력 capture와 provider 실행 전에 거부한다. 독립 auditor는 같은 조건 검사와 기존 raw receipt/CLI/guard/source/prefix/ordinal 검증을 수행한다. 나중 binding에서 누락된 등록 필드를 보충하는 경로는 없다.

개발 통합 fixture는 실제 B callback writer와 pinned native 초기 문헌 단계, 실제 C 초기 제안 경로를 사용한다. provider만 명시적 합성 raw receipt writer이며, 데이터는 손으로 작성한 작은 공개 배열이다. 각 경로는 시험용 두 요청 allowance에서 끝나며 CPU action을 제출하지 않는다. 같은 과거 prefix가 같은 사실로 정규화되어도 합성 증거의 실제 채택 불가 상태를 유지해야 한다. 이는 전체 연구 pipeline 완료나 실제 모델 능력의 시험이 아니다.

사전등록한 10개 구성 family는 native B/C 조건 전달, 누락 형식 재현, 개별 필드 누락, 모델·effort·자원 변경, 일관 재해시 공격과 기존 prefix/합성 자격 회귀를 포함한다. 최초 fixture의 문헌 프로토콜 인자 오류는 실패 기록으로 보존하고 keyword 인자로 고쳤다. 신규 targeted 검사와 기존 회귀의 로그·소스 핀은 별도 engineering proof에 연결된다. 이후 전체 가드가 새 합성 namespace를 차단한 실패도 보존하며, 그 namespace만 명시한 새 가드 검사와 독립 family 검사를 별도로 판정한다. 이전 source proof는 수정한 후보를 대신 인증하지 않는다.

수정은 host metadata writer와 동일 조건의 조기 검사, 새 검사·버전·개발 문서에 국한된다. native 원 알고리즘과 입력, 공통 CPU task/evaluator, 문헌 사실 registry, semantic predicate와 기존 비교·채택 기준은 그대로이다. 문헌 registry는 corpus/record SHA를 pin하며 이 변경을 이유로 문형이나 승인 사실을 늘리지 않는다. 이 수정만으로 모든 자연어 주장을 판정할 수 있다고 주장하지 않는다.

릴리스 도구는 전체 276 구성 검사와 독립 10개 family의 같은 source pass, 별도 승인 계약을 모두 확인해야 새 사본이나 환경을 만든다. 이 문서는 그 실행 승인 자체가 아니다. 새 실제 개발은 별도 사전등록과 독립 공개 조건 감사를 거쳐야 하며, 최종 개선 채택에는 별도 untouched final 평가가 필요하다. A 계열 모델 효과는 실행할 수 있을 때까지 미추정이다.

등록·로그·해시의 일치는 trusted host 기록을 기준으로 한다. 공격자가 외부 등록 핀과 전체 trusted host 기록을 바꿀 수 없다는 암호학적 보장을 제공하지 않는다. Python 가드는 OS 전체 접근 검사나 허용된 tiny CPU child의 독립 계측을 대신하지 않는다. 비용이나 오류 사용량이 알려지지 않았다면 null로 남기며 0으로 바꾸지 않는다.

새 prospective 공개 base는 `examples/sampled-pilot-base-v8.json`이다. 고정 public c7 base에서 release root를 `versions/v8-development`, output을 `runs/p8`, 목적 문구를 새 forward 개발로 바꾼 metadata 세 항목만 다르다. 원 model·resource·literature·semantic policy·평가 기준·empty units는 같으며 owner sampling이나 실제 실행은 하지 않는다. original source110과 explicit derived metadata1은 별도 SHA/receipt로 구분한다.

Callback metadata 전달 구성 검사의 통과는 실제 보고서 전체 numeric/semantic 검토의 완결성을 뜻하지 않는다. 고정 문형이나 original input 범위를 검증하는 별도 adapter에서 미결 항목이 남을 수 있다. 이 도구의 source copy와 공학 환경 검증은 그 항목의 승인이나 실제 연구 우수성·새 실제 개발 실행 허가를 대신하지 않는다. 과거 판정·기준은 그대로 보존한다.
