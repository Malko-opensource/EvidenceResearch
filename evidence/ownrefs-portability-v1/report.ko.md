# 독립 버전의 참고 자료 경로 검증

미래 테스트 세 파일은 테스트가 속한 프로젝트 루트의 `references`만 사용하도록 수정했다. 자료가 빠졌을 때 상위 프로젝트 자료를 대신 읽는 경로는 없다. 패키지 구현과 main/v4 파일은 변경하지 않았다.

`source-manifest.json`에 고정한 자체 복사본에는 원본 upstream manifest의 코드·자료 35개가 모두 있으며, 각 크기와 SHA256이 일치한다. 두 문헌 파일도 출처와 같은 바이트로 보존했다. 다섯 문헌 기록의 canonical SHA256은 `cc1c0f836fd87b4566b2d9a14087893e5109878c8ea5414e69f4b5542255c2e3`이다.

자체 복사본을 `work/oref1`에 재구성한 뒤 해당 루트에서 세 테스트 모듈을 실행했다. 테스트 29개가 모두 통과했다. 원래 프로젝트의 `references`, `evidence_research`, `tests`에 대한 파일 열기·디렉터리 탐색을 감사 훅으로 차단했으며, 해당 접근 시도는 없었다. provider 프로세스 실행도 차단했고 실제 모델 호출은 없었다. 결과·실행 명령·로그·소스 해시는 `result.json`, `command.json`, `evidence-manifest.json`에 연결했다.

이는 합성 provider와 작은 실제 CPU 계산을 사용한 단위 검증이다. 연구 비교 실험, 성능 향상, v5 전체 검사 완료를 주장하지 않는다. 기존 checkpoint v1/v2 검증 기록은 보존했다. Windows의 깊은 경로 한계를 피하려고 실행용 복사본을 짧은 작업 경로에 만들었으며, 공개된 byte snapshot 자체는 이동한 뒤에도 상대 경로와 해시로 재구성할 수 있다.

저장소 루트에서 아래 명령으로 별도 결과를 재현한다. `work/oref2`와 새 receipt 경로는 아직 존재하지 않아야 하며, 기존 기록을 덮어쓰지 않는다. 시스템의 Python 실행 경로를 사용하면 된다.

```powershell
python -B evidence/ownrefs-portability-v1/verify.py --work-root work/oref2 --blocked-ancestor . --receipt evidence/ownrefs-portability-v1/reproduction-0001.json
```

수정 후 SHA256:

- `test_baseline_transport_integration.py`: `1807b609f9e3b5dea83e32c09ee8054c12941352e9bf8c16db5c0ddf43c61cd3`
- `test_context_compaction.py`: `bbaa94e4c4ef8513afd2d47119952838fa27b76b2c03f2cd140b85ad5abeeca5`
- `test_checkpoint_replay.py`: `4307f07f49559e3f26ef9519236aed3a78c53d68eaeaaff98a7a175bb989f2a4`
