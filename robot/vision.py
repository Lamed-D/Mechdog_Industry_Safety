# 장착된 비전 모듈의 공식 Python 연결. 로봇 동작이나 영상 저장을 수행하지 않습니다.
# 제조사 예제: IIC(2) + ESP32S3Cam. 버스는 실물에서 확인합니다.
# 맞춤 카메라 펌웨어(firmware/vision_cam)는 카메라에서 인식을 하지 않고 늘 "결과 없음"을 돌려주므로
# (인식은 Pi 5가 영상으로 함), 그때 이 읽기는 "카메라가 I2C에 응답하는지" 확인 용도입니다.


def _has_result(result):
    """공식 결과의 '인식됨' 여부. 형식은 docs/protocol.md 11절."""
    if isinstance(result, bool):
        return result
    if isinstance(result, int):
        return result != 0
    if len(result) >= 4:      # 최신 라이브러리 read_face: [x, y, w, h], w > 0 이면 얼굴
        return result[2] > 0
    return any(result)        # 이전 형식(중심 x, y): 0 이 아니면 결과


def _valid_result(result):
    if isinstance(result, bool):
        return True
    if isinstance(result, int):
        return result >= 0
    if not isinstance(result, (list, tuple)) or len(result) not in (2, 4):
        return False
    return all(isinstance(value, int) and not isinstance(value, bool) and value >= 0
               for value in result)


class Vision:
    def __init__(self, api, recognition_on_camera=False):
        self.camera = None
        self.error = None
        self.recognition = "on_camera" if recognition_on_camera else "off_on_camera"
        try:
            self.camera = api.ESP32S3Cam(api.IIC(2))
        except Exception:
            self.error = "camera_init_failed"

    def read_face(self):
        """성공 여부와 원시 결과 유형만 반환. 얼굴 검출을 낙상으로 해석하지 않습니다."""
        if self.camera is None:
            return {"status": "unknown", "reason": self.error}
        try:
            reader = getattr(self.camera, "read_face", None)
            if not callable(reader):
                reader = self.camera.face_recognition
            result = reader()
        except Exception:
            return {"status": "unknown", "reason": "camera_read_failed"}
        if result is None:
            return {"status": "unknown", "reason": "no_result"}
        if not isinstance(result, (bool, int, list, tuple)):
            return {"status": "unknown", "reason": "unexpected_result_type"}
        if not _valid_result(result):
            return {"status": "unknown", "reason": "invalid_result_shape"}
        return {"status": "observed", "camera_link": "ok", "recognition": self.recognition,
                "result_type": type(result).__name__, "has_result": _has_result(result),
                "fallen_person": "unknown"}
