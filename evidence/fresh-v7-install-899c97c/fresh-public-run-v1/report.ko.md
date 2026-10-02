새 공개 v7 설치·재현 결과

공개 커밋 `899c97cdab5d557db8b80a6bf479779ed13282d1`을 부모가 새 `_er7`에 내려받고 고정 upstream 35개를 별도 취득한 뒤, 외부 해시로 고정한 helper와 GO에 따라 새 자체 `.venv`를 만들었다. 공개 소스 71개와 자체 upstream 35개, 총 106개를 확인했고 설치·검사 전후 바이트가 같았다. 선택에서 빠진 두 선택적 구형 example은 사용하지 않았다.

네트워크 없이 editable 설치가 성공했다. 설치 때만 bundled build 도구를 사용하고 실행·검사의 PATH/PYTHONPATH에서는 해당 도구를 제거했다. 자체 환경의 package 버전은 `0.4.0.dev0`, user site는 비활성화였다. CLI help와 고정 reference closure가 통과했다. 모델 인증은 확인하지 않았다.

새 환경에서 전체 263개 검사를 한 번 실행해 모두 통과했다. 공개된 고정 캡처 소스의 38개 사례도 새 공개 체크아웃과 새 짧은 출력 경로에서 한 번 재현해 통과했다. 이 재현은 합성 transport와 작은 공개 배열 CPU 구성 검사 12회이며, 실제 provider 호출과 연구 trial은 없었다. 원시 로그·명령·receipt와 가드 기록을 보존했다.

부모 Python 가드는 기존 프로젝트 접근, 허용 root 밖 접근, 미등록 run 접근, 미허용 process, network 이벤트를 모두 0으로 기록했다. 전체 검사에서 허용된 CPU fixture 자식 1개는 PYTHONPATH를 교체하여 이 부모 hook 밖에서 실행된다. 따라서 이 기록은 OS sandbox나 모든 자식의 파일 접근에 대한 전역 증명이 아니다. 38개 구성 재현에서는 부모 guard count와 고정 driver의 기존 root/provider guard count가 모두 0이었다.

이번 증거는 공개 선택 소스의 설치·구성 재현 가능성에 한정한다. 별도 supplemental 5개 sidecar의 portable 재실행, 실제 모델 인증, 연구 성능 향상, Goal 완료를 주장하지 않는다. 기존 실제 v5/v6/v7 기록, owner 행·private seed, 기존 309개 소스 body는 열지 않았다. 성공한 단계를 반복하지 않았고 Git 변경이나 업로드도 하지 않았다.

공개 후보는 `public-proof-selection-v1.json`의 exact 목록으로 제안한다. helper/가드/외부 pin/부모 취득 receipt와 새 7단계 원시 로그·106개 source metadata·38개 원시 result/tests log만 포함한다. `.venv`, 새 runtime upstream body, 전체 합성 출력 tree, 기존 실제 연구 자료는 제외한다. 38개 raw result의 artifact inventory는 보존하지만 finisher가 그 모든 artifact body를 다시 감사했다는 주장은 하지 않는다.
