"""Single-image pose inference on fresh Wi-Fi frames; no robot commands."""
from dataclasses import dataclass
from io import BytesIO
from math import hypot
import os
from pathlib import Path
import sqlite3
from threading import Lock, Thread
from time import monotonic

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from dashboard.fall_events import DATA_DIR


@dataclass
class Track:
    box: tuple
    seen: float
    first: tuple | None = None
    reported: bool = False
    last_event: float = float("-inf")
    upright_frames: int = 0


def assess(points, width, height):
    def visible(index):
        p = points[index]
        return min(p.visibility, p.presence) >= 0.55 and 0 <= p.x <= 1 and 0 <= p.y <= 1

    def center(indices):
        group = [points[i] for i in indices if visible(i)]
        if group:
            return (width * sum(p.x for p in group) / len(group),
                    height * sum(p.y for p in group) / len(group))

    shoulders, hips = center((11, 12)), center((23, 24))
    if not shoulders or not hips or not center((25, 26, 27, 28)):
        return None
    body = [p for i, p in enumerate(points) if visible(i)]
    left, right = min(p.x for p in body), max(p.x for p in body)
    top, bottom = min(p.y for p in body), max(p.y for p in body)
    box = (max(0, int((left - .025) * width)), max(0, int((top - .025) * height)),
           min(width - 1, int((right + .025) * width)), min(height - 1, int((bottom + .025) * height)))
    dx, dy = shoulders[0] - hips[0], shoulders[1] - hips[1]
    if hypot(dx / width, dy / height) < .045:
        return None
    fallen = abs(dx) >= 1.2 * abs(dy) and (right - left) * width >= 1.15 * (bottom - top) * height
    upright = dy < -1.2 * abs(dx)
    return box, fallen, upright


def overlap(a, b):
    shared = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = (a[2]-a[0]) * (a[3]-a[1]) + (b[2]-b[0]) * (b[3]-b[1])
    return shared / max(1, area - shared)


class FallDetection:
    def __init__(self, feed, events, robot):
        self.feed, self.events, self.robot = feed, events, robot
        model = DATA_DIR / "pose_landmarker_lite.task"
        if not model.is_file():
            raise ValueError(f"먼저 README 설치 절차로 모델을 내려받으세요: {model}")
        self.label = "쓰러짐 의심"
        try:
            self.font = ImageFont.truetype(str(Path(os.environ.get("WINDIR", "C:/Windows"))
                                               / "Fonts/malgun.ttf"), 14)
        except OSError:
            self.label, self.font = "Suspected fall", ImageFont.load_default()
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=model.read_bytes()), num_poses=4)
        self.model = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        person_model = DATA_DIR / "efficientdet_lite0.tflite"
        if not person_model.is_file():
            self.model.close()
            raise ValueError("README 설치 절차로 EfficientDet Lite0 사람 모델을 내려받으세요.")
        person_options = mp.tasks.vision.ObjectDetectorOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=person_model.read_bytes()),
            category_allowlist=["person"], score_threshold=0.55, max_results=4)
        self.people = mp.tasks.vision.ObjectDetector.create_from_options(person_options)
        self.tracks = []
        self.on_fall = None
        self.lock = Lock()
        self.latest = (0, "감지 불가", None)
        self.worker = Thread(target=self.run, daemon=True)

    def annotated(self, rgb, boxes):
        image = Image.fromarray(rgb)
        draw = ImageDraw.Draw(image)
        for box in boxes:
            draw.rectangle(box, outline="orange", width=3)
            x, y = box[:2]
            x = min(x, max(0, image.width - 100))
            y = max(0, y - 22)
            draw.rectangle((x, y, x + 99, y + 21), fill="black")
            draw.text((x + 3, y + 1), self.label, fill="orange", font=self.font)
        output = BytesIO()
        image.save(output, format="JPEG", quality=88)
        return output.getvalue()

    def person_pose(self, rgb, box):
        height, width = rgb.shape[:2]
        pad = round(max(box.width, box.height) * .12)
        x = max(0, box.origin_x - pad)
        y = max(0, box.origin_y - pad)
        crop = rgb[y:min(height, box.origin_y + box.height + pad),
                   x:min(width, box.origin_x + box.width + pad)]
        h, w = crop.shape[:2]
        if min(w, h) < 16:
            return None
        # A wide person may be easier to landmark when rotated upright.
        for turns in ((0, 1, -1) if box.width > box.height else (0,)):
            oriented = np.ascontiguousarray(np.rot90(crop, turns))
            result = self.model.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=oriented))
            for points in result.pose_landmarks:
                for point in points:
                    u, v = point.x, point.y
                    if turns == 1:
                        u, v = 1-v, u
                    elif turns == -1:
                        u, v = v, 1-u
                    point.x, point.y = (x + u*w)/width, (y + v*h)/height
                pose = assess(points, width, height)
                if pose:
                    person_box = (max(0, box.origin_x), max(0, box.origin_y),
                                  min(width-1, box.origin_x+box.width), min(height-1, box.origin_y+box.height))
                    if overlap(person_box, pose[0]) >= .25:
                        return person_box, pose[1], pose[2]
        return None

    def process(self, received, wall_time, jpeg):
        image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        people = self.people.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)).detections
        poses = [pose for person in people if (pose := self.person_pose(rgb, person.bounding_box))]
        self.tracks = [t for t in self.tracks if received - t.seen <= 2 or received - t.last_event < 30]
        # Assign strongest overlaps first so two people cannot claim the same track.
        pairs = sorted(((overlap(p[0], t.box), i, j) for i, p in enumerate(poses)
                        for j, t in enumerate(self.tracks)), reverse=True)
        matched, used = {}, set()
        for score, i, j in pairs:
            if score >= .15 and i not in matched and j not in used:
                matched[i] = self.tracks[j]
                used.add(j)
        for j, track in enumerate(self.tracks):
            if j not in used:
                track.first = None
                track.upright_frames = 0
        fallen_boxes = []
        marked = None
        for i, (box, fallen, upright) in enumerate(poses):
            track = matched.get(i)
            if track is None:
                track = Track(box, received)
                self.tracks.append(track)
            if received - track.seen > 1:
                track.first = None
                track.upright_frames = 0
            track.box, track.seen = box, received
            track.upright_frames = track.upright_frames + 1 if upright else 0
            if track.upright_frames >= 2:
                track.reported = False
            if not fallen:
                track.first = None
                continue
            if track.reported or received - track.last_event < 30:
                if track.reported:
                    fallen_boxes.append(box)
                continue
            marked = self.annotated(rgb, [box])
            photo = (wall_time, width, height, box, marked)
            if track.first is None:
                track.first = photo
            else:
                if self.on_fall:
                    self.on_fall()
                self.events.record(self.robot, track.first, photo)
                track.reported, track.last_event, track.first = True, received, None
                fallen_boxes.append(box)
        if fallen_boxes:
            preview = self.annotated(rgb, fallen_boxes)
            return "쓰러짐 의심", preview
        if not people:
            return "사람 미검출", jpeg
        return ("사람 확인" if poses else "사람 확인 · 자세 확인 불가"), jpeg

    def run(self):
        previous = 0
        try:
            while not self.feed.stop_event.wait(.03):
                seq, received, wall_time, jpeg = self.feed.latest()
                if seq == previous:
                    continue
                previous = seq
                if monotonic() - received > 1:
                    for track in self.tracks:
                        track.first = None
                        track.upright_frames = 0
                    with self.lock:
                        self.latest = 0, "감지 불가", None
                    continue
                try:
                    status, preview = self.process(received, wall_time, jpeg)
                except (RuntimeError, ValueError, cv2.error, OSError, sqlite3.Error) as error:
                    for track in self.tracks:
                        track.first = None
                    status, preview = f"감지 처리 오류 · {error}", jpeg
                with self.lock:
                    self.latest = received, status, preview
        finally:
            self.close()

    def close(self):
        self.people.close()
        self.model.close()

    def snapshot(self):
        with self.lock:
            received, status, jpeg = self.latest
        if monotonic() - received > 1:
            return "감지 불가", None
        return status, jpeg
