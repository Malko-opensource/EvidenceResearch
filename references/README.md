# 연구 원자료

이 디렉터리는 기존 프로젝트와 분리된 원자료 저장소다. `manifest.json`이 버전·URL·파일 크기·SHA-256·Git blob ID를 연결한다.

아래 PDF·HTML·텍스트·ZIP과 원본 소스 사본은 로컬 검토 자료이며 Git 게시 대상에서 제외한다. 원본 소스는 `python scripts/fetch_upstream.py`로 고정 commit에서 받아 해시를 확인한다. manifest와 취득 메타데이터, 자체 작성한 분석·검사 코드는 게시한다.

- `upstream/AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27/`: 2026-10-02에 직접 받은 공개 원본 소스. MIT LICENSE와 저작권 표시를 보존했다. 원본 파일을 수정하지 않는다.
- `upstream-commit.json`, `upstream-tree.json`, `AgentLaboratory-upstream.zip`: 고정 버전 확인과 재검증용 취득 기록.
- `2501.04227v2.pdf/.html/.txt`: Samuel Schmidgall 외, Agent Laboratory: Using LLM Agents as Research Assistants. 원문 [arXiv](https://arxiv.org/abs/2501.04227v2). PDF·HTML은 원본이고 `.txt`는 pypdf 추출이다. 원문의 CC BY 4.0 표시를 따르며 수정하지 않았다.
- `2503.18102v1.pdf/.html/.txt`: Samuel Schmidgall·Michael Moor, AgentRxiv: Towards Collaborative Autonomous Research. 원문 [arXiv](https://arxiv.org/abs/2503.18102v1). PDF·HTML은 원본이고 `.txt`는 pypdf 추출이다. 원문의 CC BY 4.0 표시를 따르며 수정하지 않았다.
- `task_literature.json`: 비교 과제의 고정 문헌 목록. Sifan Liu·Edgar Dobriban의 [Ridge Regression: Structure, Cross-Validation, and Sketching](https://arxiv.org/html/1910.02373v2) §2·§3을 직접 확인한 짧은 자체 synopsis를 포함한다. 해당 원문의 라이선스는 arXiv 비독점 배포 라이선스이므로 그 논문 전체를 이 저장소에 재배포하지 않는다.
- `adapter_import_smoke/`: 의도적으로 모델 provider를 사용하지 않은 원본 클래스 로드 검사. 실제 모델·비교 실행이 아니다.
- `adapter_tool_smoke/`: literal 설정으로 실제 CPU fitting과 독립 검증을 확인한 개발 검사. 실제 모델에 의한 선택이나 최종 비교가 아니다.
- `adapter_contract_checks.py`, `adapter_contract_checks/checks.json`: 임의 생성 코드·pickle 전역 차단, 실제 완료 응답의 해시 확인과 캐시 재사용, 이전 요청을 포함한 자원 계상, 변조된 캐시 거부를 검증한다. 새 모델 호출이나 CPU 과제 실행은 없으며 비교 성능 증거로 사용하지 않는다.

원 논문 결과, 저장소 코드 관찰, 자체 실행 측정값은 서로 다른 증거 종류다. PDF를 보관하거나 이전 보고서를 검색했다는 이유로 그 보고서의 수치를 독립 검증 결과로 바꾸지 않는다. 구현 분석은 `docs/sources.md`, 비교 종류와 어댑터 제약은 `docs/baseline.md`를 따른다.

