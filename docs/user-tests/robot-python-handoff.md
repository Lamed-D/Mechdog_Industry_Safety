# 본체 Python 시험 업로드 담당자 인계

이 문서는 다른 작업자가 현재 테스트 코드를 본체에 올리고 결과를 남기기 위한 실행 안내입니다.
**본체 코드 백업은 사용자 보고로 완료됐습니다. 지금 올릴 대상은 시험 파일이며 통합 main이 아닙니다.**
장치 작업은 사용자가 지정한 담당자가 대상 A/B와 시험 항목을 확인한 뒤 직접 수행합니다.

## 전달 파일 준비: PC에서만

저장소 루트에서 `python tools/package_robot_checks.py`를 실행하면 `build/robot_checks/`에 시험 파일·안내·빈 결과 양식·해시 명세가 생성됩니다.
담당자에게 이 폴더를 전달합니다. `python tools/package_robot_checks.py --verify`로 파일 누락·변경을 먼저 검사합니다.
에이전트가 생성·검증한 폴더이며 실제 장치 시험을 마쳤다는 뜻은 아닙니다.

## 담당자가 올릴 파일

| 파일 | 목적 | import 후 실행 |
| --- | --- | --- |
| mechdog_only.py | 공식 API 존재·배터리 읽기 | `import mechdog_only; mechdog_only.main()` |
| api_candidates.py | 후보 API 존재만 확인 | `import api_candidates; api_candidates.main()` |
| robot_imu_check.py | 공식 I2C IMU 읽기 | `import robot_imu_check; print(robot_imu_check.run())` |
| robot_loop_check.py | 본체 main에 필요한 4개 루프 지원 확인 | 아래 루프 명령 |
| vision_probe.py | 공식 카메라 I2C 응답 | `import vision_probe; vision_probe.main()` |
| robot_motion_check.py | 정지·짧은 동작 1개씩 | 아래 동작 명령 |

README·명세·체크리스트·결과 양식은 PC에서 읽습니다. 보드에는 위 `.py` 6개만 원래 이름 그대로 올립니다.
`tests/fakes/`, 호스트 코드, 생성한 통합 main, secrets 예시는 시험 업로드 대상이 아닙니다.

## 업로드와 실행 순서

1. 기존 백업이 대상 본체의 것인지 확인하고 복구 위치를 담당자가 알아 둡니다. 카메라 보드와 본체 COM을 구분합니다.
2. 기존 main의 자동 실행을 중단하고 대상 로봇을 지지합니다. 제조사 동작 파일과 공식 라이브러리는 덮어쓰지 않습니다.
3. Hiwonder Python Editor에서 전달 폴더를 로컬 프로젝트로 엽니다. 이는 PC 파일 표시 단계이며 아직 보드 업로드가 아닙니다.
4. 위 시험 `.py`를 **Download만** 선택해 본체 최상위에 올립니다. 파일명을 main.py로 바꾸지 않습니다.
   Download and Run은 재시작/실행을 동반하므로 시험 준비 전에 사용하지 않습니다.
5. REPL에서 표의 읽기 항목을 먼저 하나씩 실행합니다. 후보 API는 존재만 기록하며 보정/서보 후보 호출은 하지 않습니다.
6. 루프 시험을 실행하고 약 1초 뒤 상태를 확인합니다.

```python
import robot_loop_check as loops
import time
state = loops.run(allow_background=True)
time.sleep_ms(1000)
print(state)
```

counts가 네 개 모두 50, done이 모두 True, errors와 registration_error에 오류가 없어야 합니다.
등록 시간이 루프 완료까지 기다린 것인지, REPL이 계속 응답하는지도 기록합니다. 하나라도 불명확하면 main 적용 보류입니다.

7. 사용자가 승인한 동작 항목만 하나씩 실행합니다. 첫 항목은 stop입니다.

```python
import robot_motion_check as checks
print(checks.run("stop", allow_motion=True))
```

stop의 실제 정지를 확인한 뒤 `forward`, `backward`, `left`, `right`, `action`을 각각 별도로 승인·실행합니다.
한 번에 여섯 항목을 연속 실행하는 코드를 만들지 않습니다. left/right는 작은 전진을 포함합니다.
`calls_completed`는 호출 완료일 뿐 합격이 아닙니다. 실제 방향·쏠림·정지 지연을 담당자가 관측합니다.
이상 시 다음 항목을 진행하지 말고 현장 전원을 차단하고 기존 백업으로 복구합니다.

8. [체크리스트](robot-python-checklist.md)와 [결과 양식](results-template.md)을 A/B별로 채워 개발 담당자에게 전달합니다.
   전원·단위·API 반환·루프·정지 결과를 검토한 뒤에만 통합 main 적용 여부를 판단합니다.

현재 실물 결과는 모두 미실행입니다. 백업 완료와 원본 라이브러리 구현 직접 검토 완료는 별개이며, 구현 원본 대조는 아직 미완료입니다.
공식 Python 문서·제조사 예제의 호출/인자를 우선 확인하고 보조 자료를 대조했습니다. 일부 시험값·시간 한계는 실측 전 가정입니다.
[공식 편집기·Python 안내](https://docs.hiwonder.com/projects/MechDog/en/latest/docs/4.Python_Programming_Projects.html).
개인정보·비밀번호·기기 고유번호·원본 참고 소스·실제 얼굴 영상은 결과에 넣지 않습니다.
