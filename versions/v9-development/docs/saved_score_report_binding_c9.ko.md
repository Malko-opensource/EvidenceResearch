# 저장된 보고서 판정의 원문 대조

이 변경은 이미 저장된 점수의 `common_report_sufficiency`와 `whole_report_numeric_audit_complete`를 원문으로 재계산한다. 점수의 결정 문구를 바꾸는 것은 원문 검증을 대신하지 않는다. 연구 채택 기준, 보고서 검증 기준, 실제 모델·도구·데이터 조건은 바꾸지 않는다.

`_validate_saved_score`는 원 콜백의 `arm-response.json`에서 선택한 실행, telemetry, primary와 companion 경로를 읽는다. 이 영수증이 없으면 두 보고서를 추정하지 않고 거부한다. 현재 두 native 콜백 모두 영수증을 저장한다. 사용자 정의 콜백이 같은 저장 점수 재개 경로를 사용한다면 원 출력 영수증도 보존해야 한다.

숫자 검토는 기존 `_audit_telemetry`가 원 inventory와 독립 검토를 다시 검증한다. 유효한 검토가 존재한다는 사실만으로 완료하지 않으며, 원 primary와 companion 둘 모두를 포함해야 한다. 두 플래그는 정확한 bool만 허용한다.

보고서 충분성은 원 companion에 `verify_report_contract`를 다시 적용한다. 기존 점수 생성과 동일하게 전체 completed/failed 모델 비용의 token 불확실성과 wall seconds를 대조한다. unknown은 null이며 completed-only 하한이나 0으로 대신하지 않는다. 완료 companion의 저장된 `valid`와 최상위 충분성 플래그 둘 모두 원 재계산과 같아야 한다.

새 검사는 CPU·모델 단계를 명시적으로 무실행 stub으로 바꾸고 합성 파일만 사용한다. 원 보고서 contract, inventory, 숫자 검토 validator와 저장 점수 검증은 실제 함수로 실행한다. 합성 수치는 연구 결과가 아니며 합성 검사 통과는 실제 의미 검토 완결성이나 채택을 증명하지 않는다. 원 historical numeric 구현 증거는 수정하지 않는다.
