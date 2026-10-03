# 원본 prefix 숫자의 독립 검증 계약

`measured_historical_resource`는 `historical-numeric-context-1`의 새 공통 분류다. 기존 `measured_resource`의 전체 arm 합계와 분리한다. 원래 temporal 목록 단위를 기준으로 모든 숫자 token을 검사하며 임의 subset, final total, 미래 비용 또는 metadata-only derived 분류로 대신하지 않는다.

독립 judgment의 `historical_context`에는 정확히 `schema_version`, `arm_output`, `boundary` path/SHA, `scope: historical_pre_request`, 원 보고서에서 재구성한 `unit_id`, `measure`, 실제 반올림하지 않은 `value`가 필요하다. 보고서/inventory SHA와 모든 numeric span은 원 파일에서 재구성한다. 단위는 정확한 전체 paragraph 또는 JSON string이며, companion과 주 보고서의 fenced JSON에도 같은 경로를 사용한다. 부분 인용, 다른 문장, 다른 JSON scalar, 토큰을 숨기는 escape나 다른 measure의 숫자 전용은 거부한다.

`recompute_historical_numeric(inventory_path, judgment)`와 production adjudicator/validator는 고정 `historical_context_resources` semantic predicate를 호출한다. 해당 공통 판정기의 원본 ContextBoundary 감사, 모든 목록 수치 검사, prefix 순서·source·task·model·effort·resource 조건과 actual qualification을 유지한다. 전체 단위의 모든 numeric occurrence는 같은 boundary 아래 새 분류로 연결돼야 한다. 저장된 리뷰의 caller flags와 proof는 원본 재계산을 대체하지 못한다.

`evaluate_fixture_historical_numeric`는 동일 계약을 explicit synthetic engineering fixture에서 확인하는 별도 API다. 반환은 항상 `synthetic_fixture`, `synthetic_engineering_fixture`, `adoption_eligible: false`이다. 실제 보고서 승인 함수에는 fixture mode keyword가 없고 원래 합성 영수증을 거부한다. 이 구성 검증은 모델·연구 효과의 증거가 아니다.

unknown 사용량은 null이며 숫자 0이나 completed lower bound로 대체하지 않는다. counts는 정수, seconds는 기존 temporal parser의 12자리 이내 표시와 고정 rounding tolerance를 사용한다. 비교 대상 실제 value는 반올림하지 않는다. 모델·도구·자원 조건, 전체 numeric/semantic actual 완결성, unsupported 0, 기존 token/MSE 채택 조건은 변경하지 않는다. 이전 버전·실제 연구 기록은 재판정하거나 수정하지 않는다.
