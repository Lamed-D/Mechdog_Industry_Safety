import unittest

from dashboard.core import DashboardCore, EventLog
from dashboard.web.robot_adapter import RobotAdapter
from host.robot_hub import RobotHub
from scenario.machine import Command, Scenario


class Socket:
    def __init__(self, *args):
        self.incoming, self.sent = [], []
        self.closed = False

    def bind(self, address):
        self.bound = address

    def setblocking(self, value):
        self.blocking = value

    def recvfrom(self, size):
        if not self.incoming:
            raise BlockingIOError
        return self.incoming.pop(0)

    def sendto(self, data, peer):
        self.sent.append((data, peer))
        return len(data)

    def close(self):
        self.closed = True


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.hub = RobotHub({"A": "127.0.0.1", "B": "127.0.0.2"}, socket_factory=Socket)
        self.adapter = RobotAdapter(self.hub, clock=lambda: 0)
        self.log = EventLog()
        self.addCleanup(self.log.close)
        self.core = DashboardCore(Scenario(), self.adapter.links, self.log)

    def feed(self, robot, peer=None, seq=1):
        boot = self.adapter.links[robot].boot_id
        payload = ("TEL|%s|%d|0|stopped|1|boot|7800|0.0|0.0|100|%s|none|$" % (robot, seq, boot)).encode()
        self.hub.socket.incoming.append((payload, peer or self.hub.peers[robot]))

    def test_one_socket_routes_both_robots_and_rejects_wrong_source(self):
        self.feed("A", self.hub.peers["B"])
        self.feed("B")
        self.feed("A")
        self.adapter.step(self.core)
        self.assertEqual(self.hub.rejected, 1)
        self.assertTrue(all(link.fresh() for link in self.adapter.links.values()))
        self.assertEqual(len(self.hub.socket.sent), 2)

    def test_stationary_adapter_never_sends_motion_or_action(self):
        for kind, arg in (("patrol", None), ("goto", "manager"), ("guide", "site"),
                          ("action", "nodding_motion"), ("pose", "sit")):
            self.core.commands.append(Command("A", kind, arg))
        self.adapter.step(self.core)
        self.assertTrue(all(b"MOVE" not in data and b"ACTION" not in data and b"POSE" not in data
                            for data, _ in self.hub.socket.sent))
        self.assertEqual(sum(n["kind"] == "command_blocked" for n in self.core.notices), 5)

    def test_estop_and_exit_attempt_both_robots(self):
        self.core.commands.append(Command("A", "action", "nodding_motion"))
        self.core.estop_all()
        self.assertFalse(self.core.commands)
        self.adapter.close()
        self.assertTrue(self.hub.socket.closed)
        self.assertEqual({peer for data, peer in self.hub.socket.sent if b"ESTOP" in data},
                         set(self.hub.peers.values()))

    def test_send_failure_does_not_skip_second_robot(self):
        original = self.hub.socket.sendto

        def fail_a(data, peer):
            if peer == self.hub.peers["A"]:
                raise OSError("injected")
            return original(data, peer)

        self.hub.socket.sendto = fail_a
        self.adapter.step(self.core)
        self.assertEqual(self.adapter.failures, 1)
        self.assertEqual(self.hub.socket.sent[-1][1], self.hub.peers["B"])

    def test_address_validation_precedes_socket_creation(self):
        for hosts in ({"A": "127.0.0.1", "B": "127.0.0.1"},
                      {"A": "192.168.1.1", "B": "192.168.1.2"},
                      {"A": "0.0.0.0", "B": "127.0.0.2"}):
            with self.assertRaises(ValueError):
                RobotHub(hosts, socket_factory=lambda *a: self.fail("socket opened"))
