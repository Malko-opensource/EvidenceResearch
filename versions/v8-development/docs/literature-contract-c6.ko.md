이 후보는 `versions/v5-development`의 등록된 소스를 복사한 새 개발 설계다. 부모 등록 파일의 고정 SHA-256은 `5569d283aeb9a00087092b862ef6dace71cdf73917429c308161d1cf31ad0f81`이고, 복사 전에 패키지 소스 19개를 그 등록 값과 대조했다. `evidence/c6-candidate-source-copy-v1/copy-receipt.json`에 복사한 91개 파일의 원래 해시를 보존했다. 기존 main/v4/v5 소스, 실행 기록, 실패 판정과 진행 중인 프로세스는 변경하지 않았다.

v5 첫 B 실행에서는 원본 문헌 단계가 리뷰 목록 5개를 만들었지만 서로 다른 출처는 3개였고 중복은 2개였다. 원본 파이프라인은 목록 길이로 완료했으나, 그 후 호스트의 서로 다른 출처 5개 조건이 실패했다. C는 같은 문헌 코퍼스를 입력으로 받고 호스트가 전체 코퍼스의 서지 항목을 companion에 복사한다. 따라서 B에만 별도의 선택 목록 유일성 조건을 추가하면 공통 과제 성능과 원본 단계의 출처 다양성을 섞게 된다. 원시 근거와 원본 소스 대조는 `evidence/v5-linear137-literature-failure-audit-v1/finding.json`에 있고, 그 finding의 SHA-256은 `119bf71f0c442906033cabd0dc0bad6e23b924d6d51eabeb6aa63dd9739883b9`이다. 그 실행의 원래 실패는 유지한다. c6 조건을 적용해 과거 실행을 통과 또는 채택으로 바꾸지 않는다.

새 envelope에는 `literature_protocol`을 명시한다. 지원 버전은 `shared-corpus-original-review-entries-2`이다. `required_shared_corpus_distinct_records`는 양쪽에 제공되는 등록 코퍼스의 서로 다른 출처 수이고, `original_minimum_review_entries`는 원본 B가 만드는 리뷰 목록의 최소 항목 수다. 후자는 원래 `upstream_settings.num_papers_lit_review`와 정확히 같아야 한다. 실험 설정 조각은 `examples/literature-protocol-c6.json`에 있다. 이 조각은 등록되거나 실행된 pilot이 아니다.

| 검사 | c6 의미 |
|---|---|
| 공유 코퍼스 | ID, URL, 제목과 비어 있지 않은 저자 작성 synopsis가 필요하며, 정규화된 ID/URL 중복과 등록 해시 불일치는 거부한다. |
| 원본 리뷰 항목 수 | 원본 `len(self.phd.lit_review) >= self.num_papers_lit_review`를 그대로 둔다. 같은 등록 출처의 반복 항목도 원래 목록 길이에 포함된다. |
| 선택 항목의 출처 | 모든 선택 항목의 ID가 등록 코퍼스에 속하고 반환된 synopsis가 등록 원문과 정확히 일치해야 한다. 알 수 없는 ID, synopsis 누락·변조·공백은 실패다. |
| 출처 다양성 | 서로 다른 검증 출처 수, 중복 수와 선택하지 않은 공유 출처 ID를 진단으로 남긴다. 중복만으로 공통 과제 실패를 추가하지 않는다. |
| 공통 보고서 | 실제 산출물에 대한 고정 평가, 원본 보고서와 companion의 독립 숫자·의미 판정을 양쪽에 계속 요구한다. 원본 단계 완료만으로 공통 과제 성공을 선언하지 않는다. |

원본 `agents.py:714`의 `add_review`는 ID와 요약을 나눈 뒤 도구의 반환값을 목록에 append한다. `ai_lab_repo.py:506`과 `:528`은 그 목록 길이를 확인한다. 원본 클래스와 함수, 단계 순서, 프롬프트와 reward 함수는 수정하지 않는다. 중복 제거 또는 원본에 없는 재선택 피드백을 B에 넣지 않는다. CPU·모델 도구와 source synopsis 전송은 이미 공개된 호스트 어댑터이며, synopsis가 없을 때 abstract로 대신 반환하는 경로는 c6에서 닫는다.

새 정책은 B callback 등록과 baseline 등록 모두에 포함한다. 기존 폴더에서 다른 조건으로 callback을 재사용할 수 없고, checkpoint continuation도 버전과 정책 출처가 달라지면 거부한다. 기존 단독 baseline fixture가 정책을 생략하는 경우에는 새 버전의 공유 출처 최소 1개와 원본 항목 수로 정책을 생성하고 `unregistered_standalone_candidate_default`로 명시한다. 실제 새 study 등록은 envelope에 정책이 없으면 거부해야 한다. fixture 기본값은 v5 등록에 새 의미를 붙이는 통로가 아니다.

C companion의 `references`는 `_finish`에서 코퍼스의 URL과 synopsis를 복사한 결과다. 빈 모델 trace에서도 그 표현식은 같은 서지 목록을 만들 수 있다. 따라서 reference 목록의 존재, synopsis 전송 또는 원본 B의 ADD 성공 메시지는 LLM이 논문 전체를 읽었거나 이해했다는 근거가 아니다. 반환하는 요약은 계속 `model_authored_literature_claim`으로 표시한다. 문헌 인용 근거는 원문 주장에 대한 귀속일 뿐 로컬 측정이나 이해도 검사가 아니다. 독립 의미 판정에서도 이 범위를 유지해야 한다.

새 fixture는 알려진 출처의 반복 5개 항목/출처 3개가 진단을 유지하며 통과하는지, 알려지지 않은 출처와 바뀐 synopsis가 여전히 거부되는지, 공유 코퍼스 수와 원본 항목 수를 별개로 등록하는지, 과거 정책의 실패를 재개로 바꿀 수 없는지 확인한다. 고정된 원본 함수 AST의 `add_review`와 길이 비교를 작은 합성 객체로 실행하며, 실제 모델·CPU 실험 실행기·네트워크·subprocess 호출은 차단한다. 이것은 구현 계약 검사다. 실제 연구 성능이나 개선 효과의 검증이 아니다.

```powershell
python -X utf8 -B -m unittest tests.test_literature_integrity_policy_c6 -v
```

실행 위치는 새 후보 `work/c6`이다. 재현 가능한 소스와 로그는 별도 `evidence/c6-literature-contract-v1`에 보존한다. 초기에 테스트 guard가 존재하지 않는 provider 메서드 `propose`를 참조해서 setup 단계에서 실패했다. 실제 API `complete`로 수정했고, 실패한 테스트 소스도 별도로 보존했다. 실패 시 원본 연구 실행이나 모델 호출은 없었다.

후속 비교에는 새로 등록한 개발 과제와 새 데이터가 필요하다. 이전 고정 linear/quadratic/noisy 과제의 분산은 random degree, coefficient, noise, training-size를 가진 새 분포의 확인 설계로 옮길 수 없다. 같은 선언된 분포에서 pilot과 최종 과제의 정의·자료를 분리하고, 새 contrast의 검토된 변동성으로 확인 설계를 정해야 한다. 모델 교체 효과 A 대 B는 원래 계열 모델을 실행하지 못한 상태이며 경험적으로 추정할 수 없다. B 대 C는 같은 현재 모델 아래의 어댑터·기억·선택·보고서 정책 패키지 차이를 비교한다. 이 변경은 비대칭의 제거를 목적으로 하지만, 문헌 선택 다양성 자체의 향상이나 개별 설계 요인의 인과 효과를 입증하지 않는다.
