# M: 중복 이벤트 CSV 요약

`summarize(rows)`는 event_id,group,timestamp,value 문자열 사전 목록을 처리한다.
event_id/group은 양끝 공백을 제거한다. 빈 ID/그룹과 파싱 불가·결측·NaN/무한대
timestamp/value 행은 거부한다. 각 event_id에서는 가장 큰 timestamp 행 하나를 유지한다.
timestamp가 같으면 입력에서 더 뒤의 행을 유지한다. 유효하지 않은 수정 행은 기존 행을 대체하지 않는다.
선택된 행의 그룹별 count와 산술 평균을 반환한다. duplicates는 유효 행 수에서
유지된 event_id 수를 뺀 값이다. 입력 변경과 추가 의존성은 금지한다.

반환 형식: `{"groups":{"그룹":{"count":정수,"mean":숫자}},"rejected":정수,"duplicates":정수}`.
빈 입력은 groups가 빈 사전이고 두 개수는 0이다.
성공 기준은 고정 검증기 pass_rate=1.0이다. 수치 허용오차는 절대 1e-8과 double 두 단계다.
평가 사례·평가기·다른 조건 답안을 읽지 않는다. 이 규약은 OS 보안 격리가 아니다.
기억 비교의 ON/OFF 여부만 다르고 초기 브리프와 파일은 같은 조건 안에서 동일하다.
