// 코어(안전 로직)가 하드웨어를 만지는 유일한 통로. 실제 구현은 motion_mechdog.*(벤더 공식 API)와
// 배터리·기울기 읽기입니다. 코어는 이 추상 인터페이스에만 의존해 벤더·Arduino 와 분리됩니다.
#ifndef MECH_BACKEND_H
#define MECH_BACKEND_H
#include <stdint.h>

namespace mech {

// 로봇을 움직이는 호출은 모두 여기로 모읍니다. 공식 MechDog API 만 씁니다(docs/dev/mechdog-api.md 3절).
class MotionBackend {
 public:
  virtual ~MotionBackend() {}
  virtual void stop() = 0;                    // move(0, 0). 전용 정지 함수 없음
  virtual void move(long step, long angle) = 0;
  virtual void action(const char* name) = 0;  // 동작 그룹 시작(비동기). 벤더 action_run 은 블로킹이라 별도 태스크에서 돌림
  virtual void stop_action() = 0;             // 최선 노력. 벤더에 중단 API 가 없으면 아무것도 안 함
  virtual bool action_over() = 0;             // 동작 그룹이 끝났으면 true (벤더 run_status 기반)
  virtual void default_pose() = 0;            // set_default_pose()
};

// 추가 센서 읽기(공식 외). 실패·모르는 값은 false 로 돌려줘 코어가 NA 로 다룹니다.
class Sensors {
 public:
  virtual ~Sensors() {}
  virtual bool read_battery(int32_t& mv) = 0;         // true=유효(mv>0)
  virtual bool read_tilt(float& x, float& y) = 0;     // true=유효(유한값)
};

}  // namespace mech
#endif
