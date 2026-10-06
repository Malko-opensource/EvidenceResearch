# M_PRIOR: 실제 실패 기억을 생성하는 개발용 과제

이 과제의 결과는 최종 B/C 또는 기억 ON/OFF 성능 지표에 포함하지 않는다.
입력과 고정 평가 사례는 최종 M1/M2와 분리되어 있다.

`summarize(rows)`는 event_id,group,timestamp,value 문자열 사전 목록을 처리한다.
ID/그룹 양끝 공백을 제거하고 빈 ID/그룹, 잘못된 숫자, 결측, NaN/무한대를 거부한다.
유효한 각 event_id에서 가장 큰 timestamp 행을 유지한다. timestamp 동률은 더 뒤의
입력 행을 유지한다. 선택된 행의 그룹별 count와 mean을 계산한다.
duplicates는 유효 행 수에서 유지된 event_id 수를 뺀 값이다.

출력은 `{"groups":{"그룹":{"count":정수,"mean":숫자}},"rejected":정수,"duplicates":정수}`다.
초기 코드의 전체 행 일치 기준이 수정 이벤트를 제거하지 못한다는 실제 실패와
원본 증거를 검증하고 기억에 저장하기 위한 과제다. 초기 코드를 고쳐서 실패를 숨기지 않는다.
