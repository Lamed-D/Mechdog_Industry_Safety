# MechDog 시작 파일. 장치에 robot/ 와 custom_sensors/ 의 .py 파일을 모두 맨 위 폴더로 올립니다.
# 업로드·실행은 사용자 확인 후에만 합니다. 시작하면 boot 래치 상태로 서 있고, Pi 5 의 HELLO·RESET 뒤에만 움직입니다.

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
