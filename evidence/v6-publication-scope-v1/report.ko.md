# v6 게시 후보 목록의 읽기 전용 점검

후보 manifest는 `work/v6-publication-candidate-manifest.json`, SHA는 `631860d41b96c4b8a1231e5c54ad53b9b145ede361085b2cfdac435c47ac3ba2`이다. 총 738개 파일, 21,501,409 bytes다. 경로·길이·SHA와 공개 범주를 기록했으며 Git 변경·게시·새 모델·연구 실행은 하지 않았다.

포함한 자료는 다음의 완료된 공학 증거와 소스뿐이다. 범주별 숫자는 주 범주이고, 업스트림 재현 소스는 중복 태그다.

| 범주 | 파일 수 |
|---|---:|
| v6 고정 소스 / release-copy | 66 / 1 |
| 새 환경 검증 v1 실패 보존 / v2 통과 | 27 / 9 |
| c6 구성 검사와 등록 전 static source snapshot | 105 |
| 후보 복사 provenance | 2 |
| 독립 sampler fixture v1..v5 | 219 |
| semantic 계약 fixture | 12 |
| 문헌·원본 소스 계약 fixture v1..v3 | 206 |
| source peer v1 / v2 | 24 / 64 |
| 새 공개 checkout reader proof | 3 |

격리 snapshot 재현용 고정 업스트림 파일 250개 사본은 위 범주 안에 있고 `engineering_pinned_upstream_reproduction_source`를 추가로 표시했다. 공개 acquisition manifest 외부 pin, 길이·SHA256·Git blob SHA1과 대조했다. v6 자체 런타임 업스트림 파일 35개와 compiled/cache 76개는 제외했다. 이 111개는 bytes를 읽지 않았다. v6 런타임의 원본은 자체 공개 `scripts/fetch_upstream.py`로 고정 commit에서 확보한다. proof snapshot 사본과 실행용 대형 runtime tree를 구분한다.

문헌/source-peer manifest 5개의 source inventory, 부모 c6 static source 101개, semantic delivery manifest를 전부 대조했고 누락이나 변경은 없었다. 파일 내용의 비밀값 형태·persisted observation row·비공개 생성 seed 값 검사도 통과했다. CLI 인증 로그는 명시적으로 확인했던 `Not logged in` 진단만 포함한다. 합성 unit fixture의 고정 seed나 source code는 현재 비공개 과제 seed가 아니다. owner/private라는 이름을 포함한 파일경로는 내용을 출력하지 않고 제외하도록 닫힌다.

현재 v4/v5/v6 실제 study tree, 현재 v6의 secure config·등록·source-snapshot·owner-request·원 정답 행, `.venv`, root 미확정 docs/status, 다른 work runtime tree는 열거하지 않았다. 이전에 승인·게시한 네 쌍의 상세 기록도 이 목록으로 추가하지 않았다. fresh reader proof는 그 네 쌍의 이미 승인된 공개 scalar 재계산 증거이고 새 연구 결과는 아니다.

`release-copy.json`의 registered=false는 복사 시점의 역사적 provenance다. 현재 실행 중인 v6의 등록·결과를 이 후보에 포함하거나 그 상태를 판정한 것이 아니다. 이전 실패·pending 결과를 재분류하지 않으며 프레임워크 개선 입증 또는 Goal 완료 주장을 하지 않는다.

Root가 별도 Git 게시를 담당한다. 후보 manifest는 정확한 경로를 추가할 근거일 뿐이며 향후 파일을 재귀 wildcard로 넓혀 추가할 승인 범위가 아니다. 생성 도구 `work/build_v6_publication_manifest.py`는 완료 manifest 덮어쓰기를 거절하고 모든 source pin·scope 검사를 먼저 수행한다.
