"""실제 카메라 프레임 분석과 한 바퀴 순찰 제어."""
from contextlib import closing
import sqlite3
from threading import Lock, Thread
from time import monotonic


class PatrolVision:
    def __init__(self, feed, cv):
        self.feed = feed
        self.cv = cv
        self.dictionary = cv.aruco.getPredefinedDictionary(cv.aruco.DICT_APRILTAG_36h11)
        self.detector = cv.aruco.ArucoDetector(self.dictionary)
        self.lock = Lock()
        self.frame = self.jpeg = None

    def start(self):
        Thread(target=self.run, daemon=True).start()

    def snapshot(self):
        with self.lock:
            return self.frame, self.jpeg

    def run(self):
        import numpy as np

        previous = 0
        while not self.feed.stop_event.wait(0.03):
            seq, captured, _, jpeg = self.feed.latest()
            if seq == previous:
                continue
            previous = seq
            frame = preview = None
            if jpeg and 0 <= monotonic() - captured < 1:
                try:
                    image = self.cv.imdecode(np.frombuffer(jpeg, np.uint8), self.cv.IMREAD_COLOR)
                    frame, preview = self.analyze(seq, captured, image)
                except (self.cv.error, ValueError):
                    pass
            with self.lock:
                self.frame, self.jpeg = frame, preview

    def analyze(self, seq, captured, image):
        cv = self.cv
        if image is None:
            raise ValueError("영상 해석 실패")
        height, width = image.shape[:2]
        top = height * 2 // 3
        roi = image[top:]
        dark = cv.inRange(cv.cvtColor(roi, cv.COLOR_BGR2GRAY), 0, 65)
        contours, _ = cv.findContours(dark, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
        lines = [c for c in contours if cv.boundingRect(c)[3] >= roi.shape[0] * .45
                 and cv.boundingRect(c)[2] < width * .55 and cv.contourArea(c) > width * height * .002]
        line = None
        if lines:
            moments = cv.moments(max(lines, key=cv.contourArea))
            line = moments["m10"] / moments["m00"] / width
        blue = cv.inRange(cv.cvtColor(roi, cv.COLOR_BGR2HSV), (95, 85, 45), (135, 255, 255))
        bands, _ = cv.findContours(blue, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
        stripe = any(w >= width * .45 and w > 2 * h and h >= 3
                     for _, _, w, h in map(cv.boundingRect, bands))
        corners, ids, _ = self.detector.detectMarkers(image)
        tags = []
        if ids is not None:
            for number, box in zip(ids.flatten(), corners):
                points = box.reshape(4, 2)
                tags.append((int(number), float(points[:, 0].mean()) / width,
                             cv.arcLength(points, True) / (4 * width)))
            cv.aruco.drawDetectedMarkers(image, corners, ids)
        if line is not None:
            cv.circle(image, (round(line * width), (height + top) // 2), 6, (0, 220, 255), -1)
        if stripe:
            cv.drawContours(image, bands, -1, (255, 180, 0), 2, offset=(0, top))
        ok, result = cv.imencode(".jpg", image)
        if not ok:
            raise ValueError("미리보기 인코딩 실패")
        return (seq, captured, line, stripe, tags), result.tobytes()


class Patrol:
    """Console.lock 안에서만 상태를 변경합니다."""

    def __init__(self, vision, calibration_path):
        self.vision = vision
        self.calibration_path = calibration_path
        self.sizes = {}
        if calibration_path.exists():
            with closing(sqlite3.connect(calibration_path)) as db:
                self.sizes.update(db.execute("SELECT tag, width FROM calibration"))
        self.owner = None
        self.route = []
        self.visits = []
        self.index = 0
        self.reason = "대기"

    def fresh_frame(self):
        frame, _ = self.vision.snapshot()
        if not frame or not 0 <= monotonic() - frame[1] < 1:
            raise ValueError("최신 카메라 영상 없음")
        return frame

    def calibrate(self):
        tags = self.fresh_frame()[4]
        if self.owner or len(tags) != 1:
            raise ValueError("주행을 멈추고 저장할 태그 하나를 화면에 놓으세요")
        number, _, size = tags[0]
        self.calibration_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.calibration_path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS calibration(tag INTEGER PRIMARY KEY, width REAL NOT NULL)")
            db.execute("INSERT OR REPLACE INTO calibration VALUES (?, ?)", (number, size))
        self.sizes[number] = size

    def start(self, body):
        mode, route, owner = (body.get(key) for key in ("mode", "route", "owner"))
        if self.owner or mode not in ("line", "tag") or not isinstance(owner, str) or len(owner) != 36:
            raise ValueError("순찰 시작 상태를 확인하세요")
        if not isinstance(route, list) or not 1 <= len(route) <= 24 or any(
                type(n) is not int or not 0 <= n < 587 for n in route):
            raise ValueError("방문 순서는 0~586 사이의 태그 ID를 최대 24개까지 입력하세요")
        if body.get("turn") not in ("left", "right"):
            raise ValueError("탐색 방향을 선택하세요")
        if mode == "tag" and any(n not in self.sizes for n in route):
            raise ValueError("각 지점의 도착 기준을 먼저 저장하세요")
        seq = self.fresh_frame()[0]
        self.turn = 12 if body["turn"] == "left" else -12
        self.mode, self.route, self.owner = mode, route, owner
        self.visits, self.index, self.seq = [], 0, seq
        self.phase = "search" if mode == "tag" else "follow"
        self.until = monotonic() + 5
        self.lease = monotonic() + .9
        self.reason = "주행 중"

    def stop(self, link, reason):
        if self.owner:
            self.owner = None
            self.reason = reason
            link.stop()

    def tick(self, link):
        now = monotonic()
        if now >= self.lease:
            raise ValueError("조종 화면 연결 만료")
        seq, captured, line, stripe, tags = self.fresh_frame()
        if self.phase == "search" and now >= self.until:
            raise ValueError("목표 태그 탐색 시간 초과")
        if self.seq == seq:
            return
        self.seq = seq
        expected = self.route[self.index]
        target = [t for t in tags if t[0] == expected]
        if self.phase == "confirm":
            if link.latest.state != "idle" or link.latest.last_seq <= self.stop_seq:
                self.stopped_at = now
                return
            if captured <= self.stopped_at:
                return
            if len(tags) != 1 or len(target) != 1:
                raise ValueError(f"예상 ID {expected} · 검출 {[t[0] for t in tags]}")
            self.visits.append(expected)
            self.index += 1
            if self.index == len(self.route):
                self.stop(link, "한 바퀴 완료")
                return
            self.phase = "depart" if self.mode == "line" else "search"
            self.until = now + 5
            return
        if self.mode == "line":
            if self.phase == "depart" and stripe and now >= self.until:
                raise ValueError("정지 띠를 벗어나지 못했습니다")
            if stripe and self.phase == "follow":
                self.confirm(link, now)
                return
            if not stripe:
                self.phase = "follow"
            if line is None:
                raise ValueError("바닥 선을 놓쳤습니다")
            center = line
        else:
            if not target and self.phase == "search":
                link.move(0, self.turn)
                return
            if len(target) != 1:
                raise ValueError(f"목표 태그 {expected} 식별 불가")
            self.phase = "follow"
            _, center, size = target[0]
            if size >= self.sizes[expected] and abs(center - .5) <= .15:
                self.confirm(link, now)
                return
        angle = round((.5 - center) * 40)
        link.move(0 if abs(angle) > 6 else 15, angle)

    def confirm(self, link, now):
        link.stop()
        self.phase = "confirm"
        self.stopped_at = now
        self.stop_seq = link.seq

    def state(self):
        return {"active": bool(self.owner), "reason": self.reason, "visits": self.visits[:],
                "target": self.route[self.index] if self.index < len(self.route) else None,
                "calibrated": sorted(self.sizes)}
