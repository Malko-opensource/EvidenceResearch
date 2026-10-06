# 연구 상태머신 CLI 설계

## 책임과 구조

Python 3.11 이상 표준 라이브러리만 사용하는 `research_cli` 패키지와 `research-state` 명령이다. 저장소는 SQLite와 상대경로 증거 파일이다. `core.py`가 유일한 상태 전이 규칙을 제공한다. CLI는 이 라이브러리를 호출한다. 별도 작은 로컬 실행기와 고정 검증기가 실제 파일을 처리한다. MCP는 필요성이 확인되기 전 추가하지 않는다.

언어 선택은 제한하지 않는다. 현재 구현은 상태·파일 I/O 중심이며 실행 의존성 0개, 별도 설치 환경에서 짧은 명령 호출 중앙값 약 66ms를 확인했다. 수치 계산은 별도 실행기에 맡긴다. 실제 성능·배포 병목이 확인되면 언어·프레임워크를 바꿀 수 있으며, 측정하지 않은 다른 언어의 성능 우위를 주장하지 않는다.

외부 에이전트가 과학적 선택을 한다. `status`는 허용된 명령과 부족한 증거만 반환한다. CLI가 가설 순위를 정하거나 모델을 호출하지 않는다.

0.3.0은 [Laya 입력·응답 계약](LAYA.ko.md)을 선택 사항으로 추가한다. `laya prepare`는 후보·참조 기억을 한 읽기 트랜잭션에서 SDK 입력과 순서·ID 매핑으로 내보내고 `laya resolve`는 외부 모델 응답을 미검증 제안에 연결한다. 예상 해시, 저장소/revision, 현재 증거와 순서를 확인한다. 모델 실행이나 상태 전이는 추가하지 않는다. 제안 보존은 기존 evidence 명령을 사용하며 상태 저장 형식·실행기·검증기를 변경하지 않는다.

## 상태와 전이

목표 → 가설 → 불변 사전등록을 저장한다. 등록별 실행은 `registered → running → succeeded | failed | unknown`이다. `running/unknown`에서 같은 요청은 재실행하지 않는다. 확인 가능한 실행기 영수증이 있으면 `recover`가 결과를 수집한다. 영수증이 없으면 unknown으로 남기며 자동 재실행하지 않는다. 이것은 exactly-once 보장이 아니다.

검증은 `pending → passed | failed | inconclusive`이며 실행 성공과 별개다. 등록 검증기의 산출물 기반 수치에 core가 고정 기준을 적용한다. 결정은 `pending → adopted | rejected | inconclusive`이며 채택에는 실행 성공과 검증 통과가 모두 필요하다. 실패·미결도 기억으로 검색된다. 저장소 revision, `BEGIN IMMEDIATE`, 고유 제약으로 동시 요청과 이전 revision을 감지한다. 변경 및 이벤트 기록은 한 트랜잭션이다.

## 사전등록

JSON에 hypothesis_id, change, comparison, data_split, seed, source_version, metrics, criteria, command, cwd, artifacts, validator를 필수로 저장한다. source_version은 label과 상대경로→SHA-256 files다. 로컬 실행기는 등록된 Python 인터프리터로 등록 파일을 실행하고, 실행 전 모든 원본 소스 해시를 확인한다. 코드를 초안으로 준비하고 예상 해시를 사전등록한 뒤 최종 실행 파일을 배치할 수 있다. 조건 변경은 새 등록이다. 기존 등록의 수정·삭제 API는 없고 DB trigger도 변경을 거부한다.

요청 키는 다른 내용에 재사용할 수 없다. 실험 지문은 hypothesis_id와 설명을 제외한 구체 조건 및 고정 검증기 해시로 계산한다. 가설 문구만 바꾸어도 같은 실험이다. 다른 실제 조건은 새로운 지문을 가진다. 실행 전 claim을 커밋하므로 중단 시 실행을 못 했어도 unknown일 수 있다. 안전을 위해 이를 자동 재시작하지 않는다.

## 증거·검증·권한

실행 명령, 원본 소스, stdout/stderr, 종료 정보, 산출물 및 SHA-256을 영수증으로 묶는다. 복사한 증거는 증거 저장소에 보존하고 수집·검증 시 해시를 확인한다. 측정, 문헌 주장, 추론, 미실행 제안은 별도 kind다. 외부 제출 수치와 성공 선언은 unverified이다.

초기화 시 로컬 owner capability를 발급한다. owner만 검증기를 등록할 수 있고, 등록 명령·검증기 파일 해시는 고정한다. agent 명령으로 평가 기준, 완료 증거, 검증 결과를 덮어쓰는 경로를 제공하지 않는다. 내부 실행기 영수증은 별도 capability에 연결하고 CLI에 완료 선언 명령은 두지 않는다. 검증기는 실제 산출물을 읽고 JSON metrics를 반환하며, core가 등록된 기준을 판단한다. 검증 전후 증거와 검증기 해시를 확인한다.

capability·해시·역할은 API 수준 경계다. 같은 OS 계정이 파일·DB·키를 직접 수정할 수 있으므로 보안 격리나 악성 코드 샌드박스라고 주장하지 않는다. 로컬 실행기는 신뢰한 실험 코드용이다. 교체하려면 동일한 영수증·검증 계약을 구현한다.

## 명령과 저장

`init`, `goal`, `hypothesis`, `validator`, `register`, `status`, `run`, `recover`, `verify`, `decide`, `evidence`, `memory`, `show`, `export`, `restore`를 제공한다. 전역 `--workspace`로 연구 저장소를 지정한다. JSON 입력은 파일 또는 stdin, 결과는 `{ok, data}` / `{ok:false,error:{code,message,details}}` 형태다. 사람이 읽는 `--help`와 JSON `help`도 제공한다. 오류는 입력·전이·충돌·증거·권한·미결을 구분한다.

SQLite에는 goals, hypotheses, registrations, runs, evidence, verifications, decisions, validators, requests, events를 둔다. source 조건·criteria·검증기·증거·검증 결과는 불변이다. 로그·산출물은 content hash와 상대경로로 연결한다. memory는 요약, outcome/verification 필터, limit/offset 페이지를 제공하고 show는 원본 조건과 증거 연결을 보여준다. 기록 존재와 주장 검증 여부를 분리한다. 자원에는 실제 시간과 외부 사용량의 known/unknown을 저장한다.

0.2.0의 CLI 표현은 run/recover/verify 기본 응답에서 반복된 영수증·검증 상세를 생략한다. 실행·검증·결정, 현재 무결성, 지표와 최대 10개 보존 산출물 경로를 반환하며 전체 내용은 show 또는 --full로 조회한다. 라이브러리의 상세 반환과 상태 규칙은 변경하지 않는다. help --topic register는 공개 입력 JSON 예제를 제공한다. 영수증 수집과 과학적 실행 장애 복구는 구분한다. 실행 결과는 원래 cwd가 아니라 snapshot 작업 디렉터리에 생성한다.

export는 일관된 DB snapshot과 증거·manifest를 묶는다. restore는 해시와 경로를 검사하고 비어 있는 새 저장소로 복원한다. 실행은 복원만으로 재개되지 않는다. 원래 실험 cwd가 바뀌면 재실행용 새 등록이 필요하다.

인터프리터 경로는 저장소 초기화 때 고정된다. 다른 인터프리터 환경의 새 실행은 새 작업 저장소·검증기·등록을 준비하고 기존 복원은 조회용으로 보존한다. 실행 중 export는 원위치 recover 완료 후 다시 만든다. 평가의 reproduce_record.py는 복원된 고정 증거와 검증기를 원래 인터프리터로 재계산하며 과거 상태를 덮어쓰지 않는다.

## 참고와 검증 순서

[Agent Laboratory 원문](https://arxiv.org/abs/2501.04227), [AgentRxiv 원문](https://arxiv.org/abs/2503.18102), [공식 코드](https://github.com/SamuelSchmidgall/AgentLaboratory)를 연구 단계·누적 기억의 참고로만 사용한다. 원래 모델 계층·전체 실행 환경·pickle 체크포인트를 가져오지 않는다. 계획과 실제 구현 불일치, 자기평가·미실행 주장, 누적 자료의 검색 문제를 새 CLI의 상태·증거 경계로 해결한다.

먼저 모델 없는 상태 전이·불변 등록·성공/실패/미결 검색·증거 변조·중단 재개·동시 중복 실행 검사를 통과시킨다. 이후 동일 에이전트·모델의 B/C 비교와 별도 기억 ON/OFF 비교를 사전등록한다. 개발/최종 과제는 분리하고 작은 feasibility 결과로 연구 성능 개선을 주장하지 않는다. 개선 미입증은 보고하고 실제 결함은 수정한다.
