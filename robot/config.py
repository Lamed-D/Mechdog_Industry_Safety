# 로봇 설정값 (docs/protocol.md 8절). [가정] 표시 값은 실측 전 초기값.
# 로봇 B에 올릴 때는 ROBOT_ID 를 "B" 로 바꿉니다.
# Wi-Fi 이름·비밀번호는 secrets.py (커밋 금지, secrets.example.py 참고).

ROBOT_ID = "A"

CMD_PORT = 9100
TEL_PORT = 9101
LIDAR_TCP_PORT = 20108
PI_HOST = None          # None 이면 마지막으로 받아들인 HELLO 를 보낸 주소로 텔레메트리 전송

TEL_PERIOD_MS = 100
WATCHDOG_PERIOD_MS = 20  # 감시 주기, 50 ms 이하 (5.1절)
WIFI_RETRY_MS = 3000     # Wi-Fi 재접속 시도 간격 [가정]

LINK_TIMEOUT_MS = 600    # [가정]
MOVE_HOLD_MS = 600       # [가정]

LOW_BATT_WARN_MV = 7000   # [가정] 셀당 3.5 V
LOW_BATT_LATCH_MV = 6600  # [가정] 셀당 3.3 V
LOW_BATT_RESET_MV = 6800  # [가정]
LOW_BATT_HOLD_MS = 2000   # [가정]
BATT_UNKNOWN_HOLD_MS = 3000  # [가정]
BATT_READ_PERIOD_MS = 200

# 동작 그룹 소요 시간 [가정]. 허용 목록(3.3절)에 있는 이름만.
ACTION_DURATION_MS = {
    "stand_four_legs": 2000,
    "normal_attitude": 2000,
    "sit_dowm": 3000,
    "go_prone": 3000,
    "nodding_motion": 3000,
    "scrape_a_bow": 4000,
}
DEFAULT_POSE_SETTLE_MS = 600  # [가정]
ACTION_MIN_MS = 200           # 동작 시작 뒤 이 시간이 지나야 action_is_over() 를 믿음 [가정]

LIDAR_UART_ID = 1
LIDAR_RX_PIN = 32
LIDAR_TX_PIN = 33
LIDAR_BAUD = 115200
LIDAR_RXBUF = 4096       # [가정]
