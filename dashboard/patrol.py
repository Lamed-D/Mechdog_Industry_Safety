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
            for number, box in zip(ids.flatten(), corners):
                # 작은 기본 번호 대신 굵은 초록 윤곽 + 태그 위쪽에 검은 바탕 노란 글씨 큰 번호
                points = box.reshape(4, 2).astype(int)
                cv.polylines(image, [points], True, (0, 255, 0), 4)
                label = f"{int(number)}"
                (w, h), _ = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 2, 5)
                x = max(0, min(int(points[:, 0].mean()) - w // 2 - 8, width - w - 16))
                y = max(h + 16, int(points[:, 1].min()) - 8)
                cv.rectangle(image, (x, y - h - 16), (x + w + 16, y), (0, 0, 0), -1)
                cv.putText(image, label, (x + 8, y - 8), cv.FONT_HERSHEY_SIMPLEX, 2, (0, 230, 255), 5)
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

    def __init__(self, vision, calibration_path, arrive_mm=None):
        self.vision = vision
        self.calibration_path = calibration_path
        # 임시 시험: 값이 있으면 태그 접근 모드의 도착을 태그 크기 대신 전방 초음파 거리(mm)로 판단
        self.arrive_mm = arrive_mm
        self.frame_jpeg = None
        self.log, self.photos, self.serial, self.found = [], {}, 0, None
        self.sizes = {}
        if calibration_path.exists():
            with closing(sqlite3.connect(calibration_path)) as db:
                self.sizes.update(db.execute("SELECT tag, width FROM calibration"))
        self.owner = None
        self.route = []
        self.visits = []
        self.index = 0
        self.reason = "대기 중 (아직 시작 안 함)"

    def fresh_frame(self):
        frame, jpeg = self.vision.snapshot()
        if not frame or not 0 <= monotonic() - frame[1] < 1:
            raise ValueError("최신 카메라 영상 없음")
        self.frame_jpeg = jpeg
        return frame

    def note(self, ok, text, expected, tags, distance):
        """임시 시험: 도착 확인 칸 기록(ok: True 도착, False 중단, None 발견, "start"). 사진은 메모리에만 둠.
        --patrol-arrive-mm 이 없으면 아무것도 남기지 않음(기존 동작 그대로)."""
        if not self.arrive_mm:
            return
        self.serial += 1
        self.log.append({"n": self.serial, "ok": ok, "text": text,
                         "expected": expected, "seen": [t[0] for t in tags], "sonar_mm": distance,
                         "size": round(max((t[2] for t in tags if t[0] == expected), default=0), 3),
                         "offset": round(next((t[1] - .5 for t in tags if t[0] == expected), 0), 3)})
        self.photos[self.serial] = self.frame_jpeg
        while len(self.log) > 30:
            self.photos.pop(self.log.pop(0)["n"], None)

    def photo(self, n):
        return self.photos.get(n)

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
        if mode == "tag" and not self.arrive_mm and any(n not in self.sizes for n in route):
            raise ValueError("각 지점의 도착 기준을 먼저 저장하세요")
        seq = self.fresh_frame()[0]
        self.turn = 12 if body["turn"] == "left" else -12
        # 임시 시험: 같은 방식·순서로 다시 시작하면 멈췄던 태그부터 이어서 감(기록도 유지)
        resume = (self.arrive_mm and not body.get("fresh") and getattr(self, "mode", None) == mode
                  and self.route == route and 0 < self.index < len(route))
        self.mode, self.route, self.owner = mode, route, owner
        if not resume:
            self.visits, self.index = [], 0
        self.seq = seq
        self.seen_at, self.drive = 0, (0, 0)
        self.found = None
        if not self.arrive_mm or body.get("fresh"):
            self.log, self.photos = [], {}  # "처음부터 다시 시작"은 진행·기록을 모두 비움
        self.sonar_ok_at = monotonic()
        self.phase = "search" if mode == "tag" else "follow"
        # 임시 시험 모드는 태그를 찾을 때까지 계속 회전(시간 제한 없음). 멈추려면 정지·비상 정지
        self.until = float("inf") if self.arrive_mm and mode == "tag" else monotonic() + 5
        self.lease = monotonic() + .9
        self.reason = f"순찰 중 (태그 {route[self.index]}부터 이어서)" if resume else "순찰 중"
        if self.arrive_mm:
            self.note("start", ("이어서 시작 · " if resume else "순찰 시작 · ") + " → ".join(map(str, route)),
                      route[self.index], [], None)

    def stop(self, link, reason):
        if self.owner:
            self.owner = None
            self.reason = reason
            link.stop()
            if self.arrive_mm and not (self.log and reason in self.log[-1]["text"]):
                # 임시 시험: tick 밖(배터리·화면 연결·운영자 정지 등)에서 끝난 이유도 기록
                expected = self.route[self.index] if self.index < len(self.route) else None
                tags = self.vision.snapshot()[0][4] if self.vision.snapshot()[0] else []
                self.note(reason.startswith("순찰 완료") or False, reason, expected, tags,
                          link.latest.sonar_mm if link.latest else None)

    def tick(self, link):
        now = monotonic()
        if now >= self.lease:
            raise ValueError("조종 화면 연결 만료")
        seq, captured, line, stripe, tags = self.fresh_frame()
        if self.phase == "search" and now >= self.until:
            raise ValueError("목표 태그 탐색 시간 초과")
        if link.latest.sonar_mm:
            self.sonar_ok_at = now
        if self.arrive_mm and self.mode == "tag" and self.phase == "follow":
            # 임시 시험: 직진 중에는 프레임을 기다리지 않고 매 주기 초음파로 도착을 보고 이동을 이어감
            expected = self.route[self.index]
            distance = link.latest.sonar_mm  # 값이 없으면(None) 멈추지 않고 직진 유지(사용자 결정, 임시 시험)
            if distance and distance <= self.arrive_mm:
                self.confirm(link, now)  # 태그는 완전히 멈춘 뒤 confirm 단계에서 확인
                return
            if now - self.seen_at > 2:
                message = f"목표 태그 {expected}를 2초 넘게 놓침"
                self.note(False, message, expected, tags, distance)
                raise ValueError(message)
            link.move(*self.drive)
        if self.seq == seq:
            return
        self.seq = seq
        expected = self.route[self.index]
        target = [t for t in tags if t[0] == expected]
        if self.phase == "confirm":
            if link.latest.state != "idle" or link.latest.last_seq <= self.stop_seq:
                self.stopped_at = now
                return
            # 임시 시험 모드는 멈춘 뒤 0.8초 흔들림이 가라앉은 다음 찍힌 프레임으로만 확인
            if captured <= self.stopped_at + (.8 if self.arrive_mm else 0):
                return
            if len(tags) != 1 or len(target) != 1:
                message = f"예상 ID {expected} · 검출 {[t[0] for t in tags]}"
                self.note(False, "멈춘 뒤 확인 실패 · " + message, expected, tags, link.latest.sonar_mm)
                raise ValueError(message)
            self.note(True, f"태그 {expected} 도착 확인", expected, tags, link.latest.sonar_mm)
            self.visits.append(expected)
            self.index += 1
            if self.index == len(self.route):
                self.stop(link, "순찰 완료 (방문 순서의 마지막 태그 도착)")
                return
            self.phase = "depart" if self.mode == "line" else "search"
            self.until = float("inf") if self.arrive_mm and self.mode == "tag" else now + 5
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
            if self.arrive_mm:
                # 임시 시험: 태그가 보이면 방향만 갱신. 걷는 중 흔들려 잠깐 놓쳐도 1초까지는 직진 유지
                if len(target) > 1:
                    message = f"목표 태그 {expected}가 여러 개 보임"
                    self.note(False, message, expected, tags, link.latest.sonar_mm)
                    raise ValueError(message)
                if target:
                    distance = link.latest.sonar_mm
                    if self.found != self.index:
                        # 이번 구간에서 목표 태그를 처음 본 순간: 회전을 멈추고 직진으로 바뀌는 시점
                        self.found = self.index
                        self.note(None, f"태그 {expected} 발견 · 회전 멈추고 직진", expected, tags, distance)
                    if distance and distance <= self.arrive_mm:
                        self.confirm(link, now)  # 태그가 보이는데 이미 도착 거리 안: 전진 없이 멈추고 번호 확인
                        return
                    self.phase = "follow"
                    self.seen_at = now
                    self.drive = (50, max(-10, min(10, round((.5 - target[0][1]) * 40))))
                    link.move(*self.drive)
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
        frame, _ = self.vision.snapshot()
        visible = sorted(t[0] for t in frame[4]) if frame and 0 <= monotonic() - frame[1] < 1 else None
        nxt = self.index + 1
        return {"visible": visible, "active": bool(self.owner), "reason": self.reason, "visits": self.visits[:],
                "target": self.route[self.index] if self.index < len(self.route) else None,
                # 네비 안내용: 지금 단계, 그다음 태그, 도는 방향
                "phase": getattr(self, "phase", None) if self.owner else None,
                "mode": getattr(self, "mode", None),
                "next": self.route[nxt] if nxt < len(self.route) else None,
                "turn": ("left" if getattr(self, "turn", 12) > 0 else "right"),
                "calibrated": sorted(self.sizes), "arrive_mm": self.arrive_mm, "log": self.log[:]}
