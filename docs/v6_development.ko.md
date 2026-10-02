# v6 개발 비교

기존 방식 대비 개선은 아직 입증하지 못했다. [새 실행 버전](../versions/v6-development/README.md)은
후보 전체215 검사와 별도 환경의215 검사를 통과했고, 새 개발9쌍을 등록했다.
이는 최종 확인 평가나 일반적인 과학 연구 성능의 향상을 뜻하지 않는다.
상세 계약은 해당 버전의 docs/sampled-evaluation-c6.ko.md와 문헌·소스·의미 검증 문서에 있다.

공개 commit `0be5988f4760263122188ef31e7f8dfba5ccea47`도 새 짧은 체크아웃과
독립 환경에서 설치·원본35개 직접 취득·전체215 검사를 재현했다. 공개103개 파일의
전후 Git blob·SHA가 일치한다. [새 공개 설치 보고서](../evidence/fresh-v6-install-0be5988/report.ko.md)에
원시 명령·로그·provenance·감사 범위를 보존했다. 실제 모델·연구·등록 실행은 없었다.

설치 receipt의 `original_project_or_old_checkout_reads_during_tests: 0`은 모든
외부 sibling 체크아웃의 파일 열기를 독립적으로 센 값이 아니다. 실제 guard는 원
EvidenceResearch와 새 `_er6` 내부 경계를 검사한다. 이전 체크아웃을 별도로 읽는
명령은 수행하지 않았으나, 이 필드를 OS 전체 파일 접근 차단의 증명으로 해석하지 않는다.

v5에서는 원본이 유효한 문헌 entry5개로 완료한 뒤 host가 서로 다른 문헌5개를
추가 요구하여 B를 실패로 판정하는 비대칭을 발견했다. 원 판정은 보존하고 C
완료와의 차이를 개선으로 채택하지 않는다. v6은 원본 entry 수와 공통 corpus의
distinct 수를 구분한다. 중복 진단과 source 회원성·synopsis 일치는 유지한다.
C의 참조 목록만으로 독해·이해를 증명하지 않는다.

공개 seed는 식별값이며 비공개256-bit owner 난수와 분할별 난수, 데이터 정의,
test 행은 참가자 요청에 제공하지 않는다. 등록은 실제 draw 순서·count·정확한
public schema·package19개와 외부 고정 manifest/원본35개를 확인한다. 같은 법칙
안의 데이터를 바꾸고 재해시해도 기존 등록에 합칠 수 없다.

개발9쌍은 분산 상대 표준오차.5에 대한 정규 근사 계획이다. 검정력·분산 상한이나
Goal 반복 제한이 아니다. 미결·실패를 임의로 제외하지 않는다. 최종 등록은 같은
버전·모델·권한·자원·분포의 독립 판정 완료 개발 score와 실제 변동성, 개발 정의
제외 hash를 요구한다. 계획 기준은 paired95% token 감소 구간 하한>20%와
log test-MSE ratio 구간 상한<log(1.10)을 모두 만족하고 양쪽 수치·의미 inventory,
공통 내용·모든 짝·실행 증거를 갖추는 것이다. 최종 등록은 아직 없다.

복사된 README의 “새 리뷰 버전”은 의미 리뷰에 해당한다. 수치 `pilot-review`는
기존 고정 파일명이 있으면 거부한다. 완료 판정을 덮어쓰지 않는다. 새 환경의 첫
외부 audit guard는 합성 fixture 쓰기와 Windows subprocess 인자를 잘못 분류했다.
실패를 보존하고 guard만 수정한 새 proof에서 전체 검사를 통과했다. 성공한
오프라인 설치·환경 생성·원자료·CLI 검사는 반복하지 않았다. sandbox doctor의
Not logged in은 실제 모델 인증 성공을 뜻하지 않는다.

main v4의 owner 정리 guard도 cached response loader를 새 실행으로 잘못
분류했다. 잘못된 판정과 event chain을 보존하고 원 실행·독립 리뷰에 근거한
별도 정정 판정을 연결했다. 원 데이터·측정·리뷰와 기준은 변경하지 않았다.
새 모델·연구 CPU trial은 없지만 verifier의 수치 재계산은 있다. 이 상세 정정은
승인된 네 짝의 공개 범위 밖이므로 로컬 핸드오프에 유지한다.

B/C는 같은 gpt-6.1-sol/medium과 MLE3/Paper1/lit5/phase100, 과제별777 요청·CPU
조건을 사용한다. 이는 source 기반 공통 과제 자원이며 전체 연구 반복 제한이
아니다. 내부 모델 sampling seed·서버 weight 버전은 미상, A 모델 교체 효과는
미실행·미측정이다. 여러 설계 요소의 묶음 비교로 개별 인과 효과를 분리하지 못한다.
요청 경계를 OS 전체 읽기 격리로 해석하지 않는다. 수정이 필요하면 새 개발 버전과
새 최종 과제를 사용한다. 실제 private 설정·등록과 진행 중인 연구 기록은 게시하지 않는다.
