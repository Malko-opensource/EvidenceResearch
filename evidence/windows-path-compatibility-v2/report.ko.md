실제 작업공간의 `versions/v5-development`를 release root로 계산했을 때 짧은 `runs/p5`는 현재 검사 대상 경로 최대 239자이며, 같은 전체 길이를 가진 별도 디렉터리에서 18종 저장 경로 probe와 캡처한 atomic_json 쓰기 검사가 모두 통과했다. 긴 `runs/development/recommended-pilot-v5`는 최대 269자이고 checkpoint cursor·manifest 임시 파일 probe 두 개가 이 환경에서 실제 실패했다. 예정된 등록 출력 디렉터리는 만들거나 변경하지 않았다.

| 예정 출력 | 현재 최대 경로 길이 | 격리 저장 probe | 과거 nested owner-copy 길이 |
| --- | ---: | --- | ---: |
| versions/v5-development/runs/p5 | 239 | 18종 통과 | 267 |
| versions/v5-development/runs/development/recommended-pilot-v5 | 269 | checkpoint 임시 파일 2종 실패 | 297 |

길이는 최장 등록 task ID인 `quadratic-seed179`, 19자리 `time_ns`, 8자리 logical ordinal 및 보수적인 10자리 Windows process ID로 계산했다. 최대 경로는 B의 `attempts/attempt-0776/upstream/transport_checkpoints` 아래 staged cursor 또는 committed manifest의 atomic temporary 파일이다. 짧은 tool reply 이름은 ordinal 8자리와 hash 앞 12자리로 구성되고 전체 SHA·실행 identity는 내용과 ledger에 남는다.

과거 owner-attempt의 전체 상대 트리 복사 방식에서는 짧은 출력에서도 267자 경로가 가능했다. 현재 고정 사본의 study.py는 `original-state/00000000.bin`처럼 짧은 blob을 쓰고 `snapshot-map.json`에 원래 상대 경로·파일 크기·SHA를 보존한다. 과거 위험 계산은 counterfactual이며 현재 파일 경로로 세지 않는다.

검사는 현재 소스 사본의 format string과 사전 설정을 확인하고 실제 동작과 같은 길이의 별도 owned 경로를 만들었다. synthetic byte 쓰기, flush/fsync, replace, copy2, SHA 일치 확인을 수행했다. immutable snapshot의 canonical_json 및 atomic_json 함수 정의도 직접 실행했다. 실제 모델 호출은 0회다. [result.json](result.json)은 모든 계산 경로, proxy 경로, OS 오류와 검증 범위를 포함하며 [source-manifest.json](source-manifest.json)은 당시 소스 사본을 연결한다.

```powershell
python -B evidence/windows-path-compatibility-v2/reproduce.py
```

검사는 공개 저장소의 `source/` 사본을 사용하며 ignored 미래 코드에 의존하지 않는다. 재현 시 새 clone의 절대 root 길이에 따라 계산값과 OS 결과가 달라질 수 있다.

이 결과는 파일 저장 호환성 증거다. 실제 Codex process의 command line·출력 경로 처리, 예정 release root에서 전체 CLI 재개, 모든 향후 task ID나 다른 파일명까지 확인한 것은 아니다. Windows long-path 지원은 OS·runtime·application에 따라 다르므로 260자를 모든 Windows 환경의 보편 실패선으로 주장하지 않는다. 현재 실제 시험에서는 긴 두 파일 경로가 실패했고 짧은 경로들은 성공했다. 공개 clone의 root가 더 길어지면 다시 검사해야 한다.

검사 보조 코드의 최초 실행에서는 불필요하게 추가한 release prefix 없는 세 번째 경로가 proxy root보다 짧아 equal-length padding assertion에 걸렸다. 요청된 두 release 출력만 비교하도록 보조 코드를 정정했다. 모델·등록된 실험은 실행하거나 바꾸지 않았다.
