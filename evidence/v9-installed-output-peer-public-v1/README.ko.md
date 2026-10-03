# v9 설치 산출물 peer의 별도 공개 연결

완료된 설치 산출물 metadata peer 세 파일을 원본 바이트 그대로 `peer/`에 복사했다. `source-copy-table.json`과 `manifest.json`에서 원본 경로·SHA·크기와 목적지를 대조할 수 있다.

기존 `evidence/v9-engineering-release-v1/manifest.json` (`5866250251d0895d0f8b6c732c78649898e8fd7352f048aacfbbae39d5f33f0d`)의 pending 표시는 당시 상태이며 수정하지 않았다. 새 peer는 저장된 설치 결과 `d69001b926bb548dca1ef82376cad6aad90e9a3caf11c96f3c4b604889a12e12`에 연결되고, result SHA는 `1fe823ae04ca23fa5d7c9d363f386f7a9e86b1568f3d08555553d0ffc86b003f`이다.

검토자는 이전 c9 의미 판정기 구현자이지만 이번 복사·설치·검증 도구의 제작자는 아니다. 이 capsule 작성자는 context/T1 구현 참여자이고 원본 영수증의 복사자다. 역할을 지우거나 독립 과학 검증으로 확대하지 않는다.

Peer는 기록된101개 선택 검사 ID·로그, CLI 도움말2개, 참조38개와 단계별 영수증의 대응을 확인했다. source125/protected886 안정성은 캡처된 메타데이터 대조이며 원 보호 본문/설치 소스를 전수 재해시한 결과가 아니다. 전체364개나 현재13/63 assertion을 다시 실행하지 않았고, 모델·CPU 연구·owner 자료를 조회하지 않았다. 합성 transport와 작은 공개 CPU 구성 fixture의 기존 실행 결과를 검토한 공학 자료다.

원 peer manifest/report가 참조하는 metadata-comparison 및 installation-phase-supplement 본문은 복사하지 않았다. 이 최소 capsule만으로 원 peer의 모든 상세 비교를 원격 재현할 수 있다고 주장하지 않는다. 로컬 경로가 원 영수증에 남아 있고 Python hook의 관측 범위는 OS 격리 보증이 아니다.

복사 전 첫 준비 시도는 외부 manifest의 `relative` 키를 `path`로 가정해 실패했다. 새 폴더/복사본 생성 전에 발생한 metadata 처리 오류이며 원 tool 실패와 요약을 보존했다. 키 처리만 바로잡고 세 파일을 복사했다. 후보·검사·설치·연구를 다시 실행하지 않았다.

연구 향상·실제 보고서 완결성·채택·최종평가·Goal 완료는 false다. 원 실패 및 고정20% token CI/10% MSE 기준은 그대로이고 새 실제 연구 등록이나 실행 권한은 이 자료에 없다. 실제 연구 폴더·설정·등록 자료·owner 자료·환경·Git·기존 capsule/root 문서는 읽거나 변경하지 않았다.
