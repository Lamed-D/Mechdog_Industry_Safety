# MechDog 시작 파일. 권장 업로드는 tools/bundle_robot.py의 A/B 단일 main입니다.
# 업로드·실행은 사용자 확인 후에만 합니다. boot 래치로 명령 대기하며 생성자의 자세 변화는 실물 미확인입니다.

import machine
import network
import socket
import time

import Hiwonder
import Hiwonder_IIC
from HW_MechDog import MechDog

import config
from app import App
from vision import Vision

try:
    import secrets  # 커밋하지 않는 파일 (secrets.example.py 참고)
    SSID = secrets.WIFI_SSID
    PASSWORD = secrets.WIFI_PASSWORD
except Exception:
    SSID = None  # 없으면 Wi-Fi 에 붙지 않고 정지 상태로 남음
    PASSWORD = None

mechdog = MechDog()
try:
    mechdog.move(0, 0)
    try:
        _imu = Hiwonder_IIC.MPU(Hiwonder_IIC.IIC(1))
        read_tilt = _imu.read_angle
    except Exception:
        def read_tilt():
            raise OSError("imu unavailable")  # 텔레메트리에 NA, imu_unknown

    app = App(config, mechdog, Hiwonder.Battery_power, read_tilt, network, socket, machine, time,
              SSID, PASSWORD, vision=Vision(Hiwonder_IIC, config.VISION_RECOGNITION_ON_CAMERA))
    app.start(Hiwonder.startMain)
except BaseException:
    # 초기화·부분 루프 등록 실패/중단에도 동작 그룹과 이동 정지를 각각 시도합니다.
    try:
        mechdog.stop_action()
    except Exception:
        pass
    try:
        mechdog.move(0, 0)
    except Exception:
        pass
    raise  # 정지 호출 오류로 원래 시작 실패를 숨기지 않음
