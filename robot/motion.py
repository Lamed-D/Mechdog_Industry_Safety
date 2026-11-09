# 로봇을 움직이는 호출은 모두 여기 모읍니다. 공식 MechDog API만 씁니다(docs/dev/mechdog-api.md 3절).

STEP_MIN, STEP_MAX = -100, 100
ANGLE_MIN, ANGLE_MAX = -30, 30


class Motion:
    def __init__(self, dog):
        self.dog = dog

    def stop(self):
        self.dog.move(0, 0)  # 전용 정지 함수 없음. 정지는 항상 이 호출

    def move(self, step, angle):
        if not (STEP_MIN <= step <= STEP_MAX and ANGLE_MIN <= angle <= ANGLE_MAX):
            raise ValueError("move out of range")
        self.dog.move(step, angle)

    def action(self, name):
        self.dog.action_run(name)

    def stop_action(self):
        # 실행 중인 동작 그룹 멈추기(제조사 예제). 실물 확인 전이므로 항상 stop() 과 함께 부릅니다.
        self.dog.stop_action()

    def action_over(self):
        return self.dog.action_is_over()

    def default_pose(self):
        self.dog.set_default_pose()
