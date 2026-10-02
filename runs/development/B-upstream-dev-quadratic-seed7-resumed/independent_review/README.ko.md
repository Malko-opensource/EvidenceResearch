이 폴더는 완료된 B **개발 실행**의 원본 보고서를 별도로 검토한 자료다. 최종 평가가 아니며 개선 효과를 주장하지 않는다. 원본 `upstream/lab/report.txt`와 실제 CPU 실험 기록은 변경하지 않았다.

유효한 전체 판정은 `full-report-review-v2/comprehensive_numeric_adjudication.json`이다. `evaluation/review_final_upstream.py`로 같은 원문 해시와 실제 CPU 기록을 다시 검증할 수 있다. 검토 대상은 decimal/scientific 출현 215개와 단어 수량·bibliographic ID·초기 regex가 놓친 terminal decimal 33개다. 이 248개는 독립적인 과학 주장 248개라는 뜻이 아니다.

실제 train/validation MSE, 차이의 산술 계산, 데이터 크기, 실행 설정, 문헌 ID, 방법 수식과 미실행 제안의 수량을 구분했다. 동일 설정은 두 번 실제 실행되었고, 독립 검증 지표가 같다. 따라서 서로 다른 측정 설정은 한 개다. 제안한 grid의 20+6=26개와 미측정 25개는 계획 수량이며 26개 실험을 실행했다고 판단하지 않았다.

명백히 근거 없는 수치는 없지만 본문 31행의 “one actual host execution”은 전체 실행 두 번인지 작성자에게 전달된 선택 기록 한 개인지 범위가 불명확하다. 이 수량은 pending으로 남았다. 전체 숫자 검증 완료와 최종 개선 증거는 선언하지 않는다. 문장 품질과 일반적인 과학적 발견 품질은 이 검토 범위 밖이다.

루트의 `derived_arithmetic.json`, `mathematical_context.json`, 초기 inventory는 검토 스크립트 개발 중 남긴 중간 자료다. 이를 삭제하거나 소급 수정하지 않았다. `draft-review-source-recovery/provenance.json`은 중간 산술 기록에 저장된 최초 스크립트 해시와 정확히 같은 소스를 content archive로 복구하여 출처를 보존한다. 이 중간 자료를 완료 판정으로 사용하지 않는다.
