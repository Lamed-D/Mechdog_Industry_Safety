# 비차단 소켓 공용 도구 (통신 전용 예외, docs/dev/mechdog-api.md 9절).

import errno

_NO_DATA = [errno.EAGAIN, errno.ETIMEDOUT]
if hasattr(errno, "EWOULDBLOCK"):
    _NO_DATA.append(errno.EWOULDBLOCK)


def no_data(error):
    """비차단 소켓에서 '지금은 받을 것 없음'인지. MicroPython 은 args[0] 이 오류 번호."""
    code = getattr(error, "errno", None)
    if code is None and error.args:
        code = error.args[0]
    return code in _NO_DATA


def close(sock):
    if sock is None:
        return
    try:
        sock.close()
    except Exception:
        pass
