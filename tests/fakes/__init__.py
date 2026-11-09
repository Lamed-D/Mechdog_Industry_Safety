"""PC 테스트용 가짜 MechDog 모듈.

로봇 쪽 코드는 장치에서 `from HW_MechDog import MechDog`, `import Hiwonder`, `import Hiwonder_IIC`,
`import machine`, `import network` 로 공식 모듈을 씁니다. PC에는 이 모듈이 없으므로 테스트에서
`install()`로 같은 이름의 가짜 모듈을 `sys.modules`에 넣고, 끝나면 `uninstall()`로 되돌립니다.

- 이름·인자는 공식 문서(docs/dev/mechdog-api.md)와 제조사 예제에서 확인한 것만 흉내 냅니다.
- 범위 밖 값·없는 동작 이름·`set_servo`는 `FakeHardwareError`(AssertionError)로 테스트를 실패시킵니다.
- 모든 호출은 `calls`에 (이름, 인자) 로 남습니다.
- `fake_` 로 시작하는 함수·메서드는 테스트가 상황을 만들 때만 쓰는 도우미입니다(실제 API 아님).

`time`·`socket`은 CPython 테스트 도구도 쓰므로 `sys.modules`에 넣지 않습니다.
대신 `fake_time.FakeClock`, `fake_socket.FakeNet`을 로봇 코드에 넘겨(주입) 씁니다.
"""

import sys

from tests.fakes import HW_MechDog, Hiwonder, Hiwonder_IIC, machine, network
from tests.fakes._base import FakeHardwareError

MODULES = {
    "HW_MechDog": HW_MechDog,
    "Hiwonder": Hiwonder,
    "Hiwonder_IIC": Hiwonder_IIC,
    "machine": machine,
    "network": network,
}

_saved = {}


def reset():
    """모든 가짜 모듈의 상태(호출 기록, 주입 값)를 처음으로 되돌립니다."""
    for module in MODULES.values():
        module.fake_reset()


def install():
    """가짜 모듈을 공식 이름으로 등록합니다. 상태도 초기화합니다."""
    reset()
    for name, module in MODULES.items():
        if name not in _saved:
            _saved[name] = sys.modules.get(name)
        sys.modules[name] = module


def uninstall():
    """install() 전의 sys.modules 상태로 되돌립니다."""
    for name, previous in _saved.items():
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    _saved.clear()


__all__ = ["FakeHardwareError", "MODULES", "install", "reset", "uninstall"]
