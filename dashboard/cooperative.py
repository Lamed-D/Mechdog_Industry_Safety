"""A/B 한 방향 코스의 순찰, 현장 경보, 도움 요청 및 복귀 안내."""
from ipaddress import IPv4Address
import socket
from threading import Event, Lock, Thread
from time import monotonic, time

from dashboard.camera_monitor import CameraMonitor
from dashboard.fall_events import DATA_DIR
from dashboard.patrol import Patrol, PatrolVision
from dashboard.robot_link import RobotLink
from firmware.robot.python import config


class TeamLink(RobotLink):
    tone = None
    last_tone = None
    first_tone_seq = None
    retry_at = 0

    def stop(self):
        super().stop()
        self.tone = self.first_tone_seq = None

    def observe(self, data):
        accepted = super().observe(data)
        if accepted and self.latest and self.first_tone_seq is not None and self.latest.tone_seq >= self.first_tone_seq:
            self.last_tone = self.tone
            self.tone = self.first_tone_seq = None
        return accepted

    def _idle_command(self):
        if self.tone and self.latest.has_tone and self.latest.state == "idle" and self.clock() >= self.retry_at:
            packet = self._command("TONE", self.tone)
            if self.first_tone_seq is None:
                self.first_tone_seq = self.seq
            self.retry_at = self.clock() + .6
            return packet
        return super()._idle_command()


class Member:
    def __init__(self, robot, send, camera, cv, events, on_fall):
        from dashboard.fall_detection import FallDetection
        self.robot = robot
        self.link = TeamLink(robot, send, require_scan=False)
        self.feed = CameraMonitor(camera, cv, False, robot, require_id=True)
        self.nav = Patrol(PatrolVision(self.feed, cv), DATA_DIR / f"patrol-{robot}.sqlite3")
        self.fall = FallDetection(self.feed, events, robot)
        self.fall.on_fall = lambda: on_fall(robot)
        self.last = None
        self.role = "대기"
        self.blocked = ""
        self.last_event = events.last_detection(robot) or 0

    def ready(self):
        l = self.link
        t = l.latest
        if not l.fresh() or l.emergency or t.latched or t.state not in ("idle", "moving"):
            raise ValueError(f"{self.robot} 본체 연결·잠금 확인")
        if not t.has_tone or not t.battery_mv or t.battery_mv < config.LOW_BATT_WARN_MV or (
                t.warnings & {"batt_unknown", "batt_low", "proto", "lidar_uart", "lidar_backlog"}):
            raise ValueError(f"{self.robot} 협동 펌웨어·배터리 확인")
        self.nav.fresh_frame()
        status, helper_seen = self.fall.scene_status()
        if status == "감지 불가" or status.startswith("감지 처리 오류"):
            raise ValueError(f"{self.robot} 쓰러짐 감지 영상 확인")
        return status, helper_seen

    def stop(self, reason):
        self.nav.stop(self.link, reason)
        self.link.stop()
        self.link.tone = None


class Cooperative:
    def __init__(self, addresses, cameras, cv, events):
        ips = [IPv4Address(addr) for addr in addresses]
        if len(set(ips)) != 2 or any(ip.is_multicast or ip.is_unspecified or ip.is_loopback
                                     or str(ip).endswith(".255") for ip in ips):
            raise ValueError("서로 다른 두 본체의 실제 IPv4 주소가 필요합니다")
        self.lock = Lock()
        self.done = Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.members = {}
        self.peers = {}
        self.owner = self.scene = self.destination = None
        self.generation = 0
        self.phase = "대기"
        self.worker = Thread(target=self.run, daemon=True)
        try:
            self.sock.bind(("", config.TEL_PORT))
            self.sock.setblocking(False)
            for robot, ip, camera in zip("AB", ips, cameras):
                peer = (str(ip), config.CMD_PORT)
                self.peers[peer] = robot
                self.members[robot] = Member(robot, lambda data, p=peer: self.sock.sendto(data, p),
                                             camera, cv, events, self.fallen)
        except BaseException:
            self.close()
            raise

    def launch(self):
        for m in self.members.values():
            m.feed.start()
            m.nav.vision.start()
            m.fall.worker.start()
        self.worker.start()

    def halt(self, reason, emergency=False):
        self.owner = None
        self.generation += 1
        self.phase = reason
        for m in self.members.values():
            m.stop(reason)
            m.role = "정지"
            if emergency:
                m.link.estop()

    def fallen(self, robot):
        with self.lock:
            m = self.members[robot]
            m.last_event = time()
            if not self.owner or self.scene == robot:
                return
            if self.scene:
                self.halt("두 로봇 쓰러짐 감지 · 운영자 확인")
                return
            self.scene, self.destination = robot, m.last
            m.stop("현장 정지")
            m.role = "현장 경보"
            self.next_alarm = 0
            self.phase = "도움 요청 구역 탐색"
            self.searched = set()
            self.helper.role = "사람 탐색"

    @property
    def helper(self):
        return self.members["B" if self.scene == "A" else "A"]

    def next_leg(self, m):
        next_index = (self.course.index(m.last) + 1) % len(self.course)
        m.nav.start(dict(mode=self.mode, route=[self.course[next_index]], turn=self.turn, owner=self.owner))
        if self.mode == "line":
            m.nav.phase = "depart"

    def start(self, body):
        if self.owner or self.scene or body.get("generation") != self.generation:
            raise ValueError("현재 사건을 종료하고 화면을 갱신하세요")
        course, zones = body.get("course"), body.get("zones")
        if (not isinstance(course, list) or not 2 <= len(course) <= 24 or
                any(type(n) is not int or not 0 <= n < 587 for n in course) or len(set(course)) != len(course)
                or not isinstance(zones, list) or not zones or any(type(n) is not int or n not in course for n in zones)):
            raise ValueError("순환 코스와 코스 안의 도움 요청 지점을 입력하세요")
        starts = body.get("starts")
        if (not isinstance(starts, list) or len(starts) != 2 or
                any(type(n) is not int or n not in course for n in starts) or starts[0] == starts[1]):
            raise ValueError("서로 다른 두 시작 지점을 지정하세요")
        for m, tag in zip(self.members.values(), starts):
            if m.ready()[0] == "쓰러짐 의심" or time() - m.last_event < 30:
                raise ValueError(f"{m.robot} 쓰러짐 경고 중")
            if m.link.latest.state != "idle" or (m.link.latest.sonar_mm or 0) <= 300:
                raise ValueError(f"{m.robot} 본체 정지 및 전방 거리 확인")
            if [v[0] for v in m.nav.fresh_frame()[4]] != [tag]:
                raise ValueError(f"{m.robot} 카메라에 시작 태그 {tag} 하나를 표시하세요")
            if body.get("mode") == "tag" and any(n not in m.nav.sizes for n in course):
                raise ValueError(f"{m.robot}에 코스 전체의 도착 기준을 저장하세요")
        self.mode, self.turn = body.get("mode"), body.get("turn")
        owner = body.get("owner")
        if (not isinstance(owner, str) or len(owner) != 36 or self.mode not in ("line", "tag")
                or self.turn not in ("left", "right")):
            raise ValueError("모드·방향·화면 세션을 확인하세요")
        self.course, self.zones, self.owner = course, set(zones), owner
        self.lease = monotonic() + 1
        self.generation += 1
        self.phase = "공동 순찰"
        try:
            for m, tag in zip(self.members.values(), starts):
                m.last, m.role, m.blocked = tag, "순찰", ""
                m.link.last_tone = None
                self.next_leg(m)
        except Exception:
            self.halt("시작 취소")
            raise

    def step_member(self, m, now):
        status, helper_seen = m.ready()
        m.blocked = ""
        if self.scene == m.robot:
            if now >= self.next_alarm:
                m.link.tone = "alarm"
                self.next_alarm = now + 2
            return
        # 사람 판정은 연속 검출 결과를 사용하며 오래된 결과로 출발하지 않습니다.
        person = status != "사람 미검출"
        near = (m.link.latest.sonar_mm or 0) <= 300
        tags = [tag[0] for tag in m.nav.fresh_frame()[4]]
        # 사람 때문에 정지 띠 직전에 멈췄어도 보이는 목표 구역에서 도움을 요청합니다.
        at_zone = (m.role == "사람 탐색" and m.nav.owner and tags == [m.nav.route[m.nav.index]]
                   and tags[0] in self.zones)
        if m.role == "구역 확인" or (at_zone and helper_seen):
            if helper_seen and status != "쓰러짐 의심":
                m.link.stop()
                m.link.tone = "call"
                self.phase = m.role = "호출 후 대기"
                self.depart_at = now + 5
            elif m.role == "구역 확인" and now >= self.inspect_until and not person:
                self.searched.add(m.last)
                if self.zones <= self.searched:
                    self.phase = m.role = "도움 요청 대상 미발견"
                else:
                    m.role = "사람 탐색"
                    self.next_leg(m)
            return
        if m.role == "호출 후 대기":
            if m.link.tone:
                self.depart_at = now + 5
                return
            if now < self.depart_at:
                return
            if near or person:
                m.blocked = "전방 통로 확인 대기"
                return
            if not m.nav.owner and m.last == self.destination:
                self.arrived(m)
                return
            self.phase = m.role = "현장 안내"
            if not m.nav.owner:
                self.next_leg(m)
            else:
                m.nav.until = now + 5
        if not m.nav.owner:
            return
        if near or person:
            m.blocked = "접근 차단"
            if m.link.intent:
                m.link.stop()
            # 정지 지점에서 새 영상과 정지 ACK 확인은 이동이 필요 없습니다.
            if m.nav.phase != "confirm":
                m.nav.until = now + 5
                return
        m.nav.lease = self.lease
        m.nav.tick(m.link)
        if m.nav.owner:
            return
        m.last = m.nav.visits[-1]
        if m.role == "현장 안내" and m.last == self.destination:
            self.arrived(m)
        elif m.role == "사람 탐색" and m.last in self.zones:
            m.role = "구역 확인"
            self.inspect_until = now + 3
        else:
            self.next_leg(m)

    def arrived(self, m):
        self.phase = m.role = "현장 인근 지점 도착"
        m.link.tone = "arrive"

    def run(self):
        while not self.done.wait(.02):
            with self.lock:
                try:
                    for _ in range(32):
                        try:
                            data, peer = self.sock.recvfrom(2048)
                        except (BlockingIOError, ConnectionResetError):
                            break
                        if peer in self.peers:
                            self.members[self.peers[peer]].link.observe(data)
                    if self.owner:
                        now = monotonic()
                        if now >= self.lease:
                            raise ValueError("운영 화면 연결 만료")
                        for m in self.members.values():
                            self.step_member(m, now)
                except Exception as error:
                    self.halt(str(error))
                for m in self.members.values():
                    try:
                        m.link.step()
                    except OSError:
                        self.halt("본체 송신 실패", True)

    def command(self, action, body):
        with self.lock:
            if action == "start":
                self.start(body)
            elif action == "heartbeat":
                if not self.owner or body.get("owner") != self.owner or monotonic() >= self.lease:
                    raise ValueError("시나리오 세션 만료")
                self.lease = monotonic() + 1
            elif action in ("stop", "estop", "finish"):
                self.halt({"stop": "전체 정지", "estop": "전체 비상 정지", "finish": "사건 종료"}[action], action == "estop")
                if action == "finish":
                    self.scene = self.destination = None
            elif action in ("reset", "calibrate") and not self.owner:
                m = self.members[body["robot"]]
                if action == "reset":
                    m.link.request_reset()
                else:
                    m.nav.calibrate()
            else:
                raise ValueError("현재 상태에서 사용할 수 없는 요청")

    def state(self):
        with self.lock:
            robots = {}
            for robot, m in self.members.items():
                link = m.link
                robots[robot] = dict(fresh=link.fresh(), locked=not link.fresh() or link.latest.latched or link.emergency,
                                     role=m.role, last=m.last, target=m.nav.state()["target"] if m.nav.owner else None,
                                     tone=m.link.last_tone, blocked=m.blocked, calibrated=sorted(m.nav.sizes))
            return dict(active=bool(self.owner), phase=self.phase, scene=self.scene, destination=self.destination,
                        generation=self.generation, robots=robots)

    def close(self):
        self.done.set()
        if self.worker.is_alive():
            self.worker.join()
        for m in self.members.values():
            m.feed.stop_event.set()
            try:
                if self.worker.ident is not None:
                    m.link.close()
            except OSError:
                pass
        self.sock.close()
        for m in self.members.values():
            if m.fall.worker.ident is None:
                m.fall.close()
            else:
                m.fall.worker.join()
