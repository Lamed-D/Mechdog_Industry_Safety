# 장착된 비전 모듈의 공식 Python 연결. 로봇 동작이나 영상 저장을 수행하지 않습니다.
# 제조사 예제: IIC(2) + ESP32S3Cam. 버스는 실물에서 확인합니다.


class Vision:
    def __init__(self, api):
        self.camera = None
        self.error = None
        try:
            self.camera = api.ESP32S3Cam(api.IIC(2))
        except Exception:
            self.error = "camera_init_failed"

    def read_face(self):
        """성공 여부와 원시 결과 유형만 반환. 얼굴 검출을 낙상으로 해석하지 않습니다."""
        if self.camera is None:
            return {"status": "unknown", "reason": self.error}
        try:
            result = self.camera.face_recognition()
        except Exception:
            return {"status": "unknown", "reason": "camera_read_failed"}
        if result is None:
            return {"status": "unknown", "reason": "no_result"}
        if not isinstance(result, (bool, int, list, tuple)):
            return {"status": "unknown", "reason": "unexpected_result_type"}
        return {"status": "observed", "result_type": type(result).__name__,
                "has_result": bool(result), "fallen_person": "unknown"}
