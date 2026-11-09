"""가짜 `HW_MechDog` 모듈 (docs/dev/mechdog-api.md 3·4절).

실제 로봇과 다르게 동작 그룹은 시간이 흘러도 저절로 끝나지 않습니다. 테스트가 `fake_finish_action()`으로 끝냅니다.
`move(0, 0)`이 실행 중인 동작 그룹을 끊는지는 실물 확인 전이므로(docs/protocol.md 3.3절) 끊지 않는 쪽으로 흉내 냅니다.
"""

from tests.fakes._base import FakeHardwareError, check_int_range, check_vec3

# mechdog-api.md 4.1절, 문서 철자 그대로(`sit_dowm`)
ACTION_NAMES = (
    "stand_four_legs",
    "normal_attitude",
    "sit_dowm",
    "go_prone",
    "nodding_motion",
    "scrape_a_bow",
    "handshake",
    "stretch_oneself",
    "rotation_pitch",
    "rotation_roll",
    "stand_two_legs",
    "press_up",
    "boxing",
    "left_foot_kick",
    "right_foot_kick",
    "pee",
)

STEP_MIN, STEP_MAX = -100, 100
ANGLE_MIN, ANGLE_MAX = -30, 30

instances = []


def fake_reset():
    del instances[:]


class MechDog:
    def __init__(self, duration=None):
        # duration 키워드는 제조사 예제 한 곳에서만 보임. 의미 미기재라 기록만 합니다.
        self.calls = [("__init__", (duration,))]
        self.last_move = (0, 0)
        self.action_running = None  # 실행 중인 동작 그룹 이름
        self.homeostasis_on = False
        instances.append(self)

    # --- 이동 ---
    def move(self, step, angle):
        check_int_range("move step", step, STEP_MIN, STEP_MAX)
        check_int_range("move angle", angle, ANGLE_MIN, ANGLE_MAX)
        self.calls.append(("move", (step, angle)))
        self.last_move = (step, angle)

    def set_gait_params(self, lift_time, contact_time, lift_height):
        # 범위가 문서에 없으므로 양수인지만 봅니다(상한 10000은 오타 잡기용).
        for name, value in (("lift_time", lift_time), ("contact_time", contact_time),
                            ("lift_height", lift_height)):
            check_int_range("set_gait_params " + name, value, 1, 10000)
        self.calls.append(("set_gait_params", (lift_time, contact_time, lift_height)))

    # --- 자세 ---
    def transform(self, xyz, rpy, time_ms):
        check_vec3("transform xyz", xyz)
        check_vec3("transform rpy", rpy)
        check_int_range("transform time_ms", time_ms, 0, 60000)
        self.calls.append(("transform", (list(xyz), list(rpy), time_ms)))

    def set_pose(self, xyz, abc, time_ms):
        check_vec3("set_pose xyz", xyz)
        check_vec3("set_pose abc", abc)
        check_int_range("set_pose time", time_ms, 0, 60000)
        self.calls.append(("set_pose", (list(xyz), list(abc), time_ms)))

    def set_default_pose(self):
        self.calls.append(("set_default_pose", ()))

    # --- 동작 그룹 ---
    def action_run(self, name):
        if name not in ACTION_NAMES:
            raise FakeHardwareError("action_run: 문서에 없는 이름 %r" % (name,))
        self.calls.append(("action_run", (name,)))
        self.action_running = name

    def action_is_over(self):
        # 제조사 예제에서 action_run 뒤에 끝났는지 확인할 때 씀. 사용은 이슈 #12에서 승인됨.
        self.calls.append(("action_is_over", ()))
        return self.action_running is None

    def stop_action(self):
        # 제조사 예제에서 실행 중인 동작 그룹을 멈출 때 씀. 사용은 이슈 #12에서 승인됨.
        self.calls.append(("stop_action", ()))
        self.action_running = None

    # --- 자기 균형 ---
    def homeostasis(self, enable):
        if not isinstance(enable, bool):
            raise FakeHardwareError("homeostasis: True/False 가 아님 %r" % (enable,))
        self.calls.append(("homeostasis", (enable,)))
        self.homeostasis_on = enable

    def read_homeostasis_status(self):
        self.calls.append(("read_homeostasis_status", ()))
        return self.homeostasis_on

    # --- 우리 로봇에 없는 장치 ---
    def set_servo(self, *args, **kwargs):
        raise FakeHardwareError("set_servo: 우리 로봇에는 부가 서보 장치가 없음 (mechdog-api.md 0절)")

    # --- 테스트 도우미 (실제 API 아님) ---
    def fake_finish_action(self):
        self.action_running = None

    def fake_tip_over(self):
        """기울기 20° 초과로 균형 모드가 풀린 상황."""
        self.homeostasis_on = False

    def fake_calls(self, name):
        return [args for call, args in self.calls if call == name]
