원본 B의 소스는 패키지 Python 파일과 별개로 고정한다. 패키지의 `baseline.py`가 같아도 그 함수가 읽는 upstream 파일이 바뀌면 실행한 알고리즘은 달라진다. c6 첫 점검 당시 `frozen_sources()`의 19개 패키지 파일 목록에는 원본 references가 없었고, `_load_definitions`는 현재 파일을 실행한 뒤 그 파일의 해시를 기록했다. 새 조건에서 pilot과 최종 실행의 원본 알고리즘이 같다고 말하려면 실행 전 외부 고정 값 대조가 필요하다. 과거 버전의 판정이나 원본 실행을 다시 분류하지 않는다.

`baseline.frozen_upstream_sources(project_root=None)`는 원본 취득 manifest와 그 manifest의 upstream 항목 35개를 검증하고, 36개 절대 경로와 기대 SHA-256 매핑을 반환한다. `references/manifest.json`의 고정 SHA-256은 `2b02fc8f6d2fef3f46758cb2e6855686371c94ac055298badf7d2f8970c3587f`이다. 기대 값은 호출자가 제공한 새 해시가 아니다. 고정 manifest를 먼저 대조한 뒤 원본 repository와 commit, 파일 길이, SHA-256, Git blob SHA-1과 경로를 확인한다. 원본 commit은 `d9017d90e329112d2a80b7712f37ee9094d2cd27`이다.

실제로 AST를 실행하는 `utils`, `agents`, `mlesolver`, `papersolver`, `ai_lab_repo`에는 별도의 고정 module SHA-256도 둔다. `_load_definitions`는 해당 모듈 이름과 기대 바이트를 AST 파싱·실행 전에 확인한다. 변경된 원본 파일, 다른 이름의 합성 모듈 또는 바뀐 manifest를 재해시한 대체 조건은 허용하지 않는다. 알 수 없는 custom module을 원본 loader에서 실행하는 우회 옵션은 없다. fixture에서는 고정 원본 바이트를 파싱하면서 유지할 정의를 비우는 방식으로 소스 검사만 확인한다. 그것은 원본 연구 단계를 실행하거나 실제 비교를 통과시키는 모드가 아니다.

`run_upstream_baseline`은 이 버전의 자체 references 위치만 사용하고 모든 35개를 검증한 뒤 등록·transport로 진행한다. `UpstreamArm`도 새 provider를 구성하거나 완료된 callback을 반환하기 전에 원본 소스를 대조한다. baseline 등록에는 외부 manifest SHA와 상대 경로를 가진 36개 inventory의 SHA를 포함한다. checkpoint continuation에서도 이 값이 달라지면 거부한다. caller가 기록한 현재 SHA만으로 기대 원본을 대신할 수 없다.

study/protocol 담당 코드는 반환된 36개 references를 19개 패키지 소스와 구분하여 별도 archive와 freeze inventory에 연결해야 한다. pilot과 최종 비교의 model, resource envelope뿐 아니라 전체 baseline provenance 객체도 같아야 한다. 이 helper만으로 study의 모든 source/archive 매칭이 자동으로 완성되는 것은 아니다.

`tests/test_pinned_upstream_sources_c6.py`는 manifest와 35개 바이트 확인, 고정 source의 새 위치 이식, 바뀐 manifest의 재해시 거부, 실행하지 않는 원본 LICENSE의 변조 거부, 5개 실행 모듈의 변경을 AST 파싱 전에 거부, 임의 module 거부, 다른 source directory를 등록·transport 전에 거부하는 조건을 확인한다. 문헌 정책 fixture와 함께 22개 검사가 통과했다. 모든 검사에서 실제 provider, 실험 실행기, 네트워크와 subprocess 호출을 막고 호출 수가 0인지 확인했다. 원본 utils의 기존 escape SyntaxWarning은 원문 그대로 남겼다.

```powershell
python -X utf8 -B -m unittest tests.test_pinned_upstream_sources_c6 tests.test_literature_integrity_policy_c6 -v
```

이 결과는 소스 고정 및 문헌 계약 구현의 검사다. 실제 모델 비교, 연구 성능, 모델 교체 효과, 일반적인 재현 성공률이나 목표 완료를 입증하지 않는다. 별도 새 개발 pilot과 독립 판정을 거친 최종 비교가 필요하다.
