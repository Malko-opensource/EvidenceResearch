# 원 의미 검토 대상 고정

저장된 의미 검토를 재계산할 때 대상은 원 콜백의 primary와 companion 두 보고서다. 저장 점수에 넣은 `semantic.audits`의 보고서 목록을 대상 정의로 사용하지 않는다. 같은 arm 안에서 검토가 완료된 다른 보고서를 companion 대신 넣으면 원 대상과 맞지 않아 거부한다.

검토 sidecar 목록은 저장된 원 snapshot만 사용한다. 이후에 작성한 검토를 자동 검색하여 기존 pending 점수를 완료 상태로 승격하지 않는다. companion 검토가 없는 snapshot은 계속 불완전하며, 단순 누락만으로 실제 완료 판정을 우회할 수 있다는 주장은 하지 않는다. 기존 auditor도 대상 수 두 개를 요구한다.

새 합성 검사는 실제 고정 의미 inventory·adjudicator·validator로 양쪽 원문 span을 검토한다. CPU·모델·owner metric 단계만 명시적인 무실행 fixture이고 원 provenance의 fixture 표지를 유지한다. 모든 양성 결과는 `component_fixture`, actual-complete false다. 다른 보고서 두 개의 검토와 aggregate를 정확히 맞춰도 원 대상이 다르면 거부하는지 검사한다. 테스트 통과는 실제 연구 채택이나 보고서 완전성 증명이 아니다.
