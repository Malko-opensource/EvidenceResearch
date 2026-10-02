# 공개된 완료 실험의 독립 재계산

비공개 owner 원본행과 owner-request가 없는 격리 복사본에서 승인된 네 개발 실험 쌍의 실제 CPU 지표, scalar test MSE와 원본 모델 자원 사용량을 재계산했다. 새 모델·실험 runner를 실행하지 않았다. [실제 재현 결과](result.json), [접근·변조 검사](proof.json), [scalar 계산과 원본 해시](scalar-replay.json)

| 과제 | B test MSE | C test MSE |
|---|---:|---:|
| linear-seed11 | 0.007897013375325187 | 0.007872898389416436 |
| linear-seed19 | 0.006470742533013084 | 0.007097926978190683 |
| quadratic-seed31 | 0.01024605080700476 | 0.010259914892394905 |
| quadratic-seed43 | 0.009640098160702186 | 0.009748852682844445 |

이 표는 완료된 최소 단계 개발 진단의 재계산이다. 선택·개선 여부를 확증 판정하지 않으며, 모델 교체 효과나 원본 권장 구성 대비 우월성을 입증하지 않는다. 원본 독립 보고서 검토의 상태와 bytes를 확인했고, 그 서술을 새로 의미 판정한 것은 아니다.

등록 파일의 외부 해시는 `a8fdd8c5500961350b289b8798a0ee9dde116ed2d07ee0ef13e131701ec0be92`다. 공개 승인된 정확한 파일 목록의 외부 해시는 `b71986a181f3c8359ca14151ce746b3110c33131001b4c225ce977c419c5cfb2`다. reader는 두 해시를 고정 trust anchor로 확인한다. 다른 해시를 전달해 바뀐 등록·manifest를 승인할 수 없다. 공개 manifest에는 과거 승인 대기 문구가 그대로 있으며, 실제 승인 전사는 별도 approval.json에 있다. 과거 파일은 변경하지 않는다.

1. 승인된 manifest의 2791개 원본 파일을 모두 외부 해시·크기로 확인한다.
2. 등록 당시 archived source 18개와 선택한 public input을 등록 해시에 대조한다.
3. 인증된 tasks.py에서 생성 함수와 상수만 추출해 같은 task/seed의 자료를 메모리 안에서 생성한다. 공개 train/validation과 manifest도 생성값에 대조한다.
4. 인증된 study.py의 owner 객체식과 store.py의 실제 직렬화식을 추출한다. 재생성한 원본 owner JSON bytes의 SHA, test value SHA, ID SHA가 등록값과 같아야 한다. 비공개 원본행 파일은 열지 않는다.
5. 인증된 독립 reference-fit 함수와 owner metric 함수로 실제 저장 weights·predictions·공개 MSE·scalar test MSE를 재계산한다. 원본 모델 요청의 해시·완료 이벤트·no-tools·model/effort·CLI 격리 설정·사용량을 대조한다.

등록 source·원본 manifest·public input·reader까지 총2816개 공개 파일만 격리 복사했다. 원본의 bytes는 전후 동일했다. 격리 child에서 원래 프로젝트 접근, 비공개 원본행/request 열기, subprocess/network 시도는 모두0이었다. 원본 model/provider/runner package를 import하지 않았다. 생성한 test 행·예측은 출력·파일·로그에 저장하지 않았고 해시와 승인된 scalar 결과만 남겼다. [접근·계산 범위 증거](proof.json)

11개 음성 검사는 잘못된 외부 등록·manifest pin, archived generator 변조, 예측과 그 자체 해시를 함께 바꾸는 변조, scalar 측정값 변조, 예측 누락, root 밖 원래 절대 경로, parent traversal, drive-relative/rooted-relative 경로 및 alternate stream 경로를 거절했다. 변조된 원본을 별도 자가 재해시해도 승인된 외부 manifest 해시를 바꿀 수 없다. 거절은 생성 함수 실행 전에 발생했다. [변조 검사 결과](proof.json)

새 checkout에서 reader와 공개 증거가 모두 있는 경우 다음을 실행한다. `NEW_RESULT.json`은 아직 존재하지 않는 경로로 지정한다.

```powershell
python -B evaluation/replay_published_units.py --root . --recorded-root "C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch" --units linear-seed11 linear-seed19 quadratic-seed31 quadratic-seed43 --out NEW_RESULT.json
```

격리 복사·guard·변조 검사는 다음 명령으로 다시 실행한다.

```powershell
python -B evaluation/development/published-units-replay-v1/reproduce.py
```

이번 증거는 짧은 Windows 임시 경로의 공개 전용 격리 복사에서 실제로 얻었다. 더 깊은 checkout의 Windows 경로 제한까지 입증하지 않는다. 표준 라이브러리의 생성·부동소수점·직렬화 결과가 달라지면 원본 SHA 비교에서 거절하며 근사 생성 자료로 대체하지 않는다. application 수준의 정합 검사이며 같은 사용자 권한의 임의 프로세스를 막는 OS sandbox는 아니다. 최종 평가 과제와 진행 중인 과제는 reader의 승인 범위에 포함되지 않는다.
