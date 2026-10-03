# 실험용 Laya 후보 입력

[Laya](https://github.com/NandhaKishorM/laya)는 연구 후보를 고르는 보조 모듈로 검토한다. 이 확장은 모델을 실행하기 전의 순수 입력 형식만 제공한다. 연구 결과의 측정·검증·채택은 기존 연구 호스트와 독립 평가가 담당한다. 현재 연구 성공률·선택 품질·보정·비용 절감에 대한 개선 주장은 없다.

`semantic_first_choice.py`는 전체 후보 ID와 config/conditions/changed_conditions를 host receipt에 보존한다. 모델 질문에는 짧은 label과 가설 `H:`, 적용 조건 `IF:`, 이전 증거의 종류와 검증 상태 `V:`, 관측 `E:`를 앞에 배치한다. 입력과 evidence registry의 독립 예상 해시가 다르면 거절한다. evidence registry는 호스트의 선언이며, 이 formatter가 원본 증거 내용을 검증하지는 않는다. unknown·unsupported·unexecuted를 측정된 성공으로 바꾸지 않는다.

원 SDK의 고정 검토 대상은 commit `fa9a2a7070b1789912a49ae24603bbfb1a78b001`이다. `common.build_head`는 후보별 48토큰 한도와 후보 수에 따른 추가 head 절단을 적용한다. 옵션 순서·instruction·annotation을 바꾸면 실험 조건도 바뀐다. 문자 길이 제한으로 실제 토큰 보존을 보장할 수 없다. 이 formatter에는 후보 수·언어별 토큰 보존 검사와 손실 시 자동 기권 정책이 아직 없다. 실제 사용 전 별도 tokenizer/SDK 경계 검사가 필요하다.

준비한 JSON payload의 필드는 다음과 같다.

```text
prepared                         원 호스트가 만든 전체 적격 후보·state·questions
annotations                      전체 후보 ID별 hypothesis/applicability/observation 선언
registry                         허용된 공개 evidence link·kind·verification_status
expected_prepared_sha256         별도로 고정한 prepared canonical SHA256
expected_evidence_registry_sha256 별도로 고정한 registry canonical SHA256
```

같은 payload에서 즉석 계산한 해시는 파일 인증이나 독립 증거 검증을 대신하지 않는다. 입력 shape와 합성 예시는 `test_semantic_first_choice.py`의 fixture를 참고한다. 모델 품질의 정답 자료로 사용하지 않는다.

설치할 모델이나 SDK 없이 Python 표준 라이브러리로 projection을 내보낼 수 있다.

```powershell
python -I -B extensions/laya/format_choices.py --input prepared-input.json --output new-projection.json
```

출력 파일이 이미 있으면 덮어쓰지 않는다. CLI는 Source formatter와 같은 폴더에서 import하며, isolated mode에서도 해당 폴더를 명시적으로 추가한다. 출력의 short label과 원 ID는 host receipt로 연결되며 아직 실행되지 않은 제안이다.

개별 계약 검사를 실행하려면 다음 명령을 사용한다. 합성 계약 검사이며 실제 Laya 모델 추론·토큰 적합성·연구 개선의 검증이 아니다.

```powershell
python -B extensions/laya/test_semantic_first_choice.py
```

후속 품질 비교는 같은 연구 모델·과제·후보 풀에서 제안만 기록하는 조건과 실제 사용하는 조건을 사전에 등록해야 한다. Laya 모델·CPU를 추가한 효과는 주 B/C의 프레임워크 효과와 구분한다. 점수나 미보정 confidence를 과제 성공 확률로 사용하지 않는다. 가중치·원시 응답·연구 평가 기록은 이 코드 패키지에 포함하지 않는다.
