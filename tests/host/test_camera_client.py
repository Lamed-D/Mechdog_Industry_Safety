import io
import time
import unittest

from host.vision.camera_client import (CameraClient, CameraEndpoint, LatestFrameReceiver, is_jpeg,
                                       parse_status, read_mjpeg)
from tools.mock import mock_camera


def part(seq, jpeg=None, length=None, lead=b"\r\n", age=5):
    jpeg = mock_camera.synthetic_jpeg(seq) if jpeg is None else jpeg
    head = b"--b\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\nX-Frame-Seq: %d\r\nX-Frame-Age-Ms: %d\r\n\r\n" % (
        len(jpeg) if length is None else length, seq, age)
    return lead + head + jpeg


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class MjpegParsingTests(unittest.TestCase):
    def test_reads_parts_with_or_without_leading_crlf(self):
        frames = list(read_mjpeg(io.BytesIO(part(1, lead=b"") + part(2)), "A"))
        self.assertEqual([f.seq for f in frames], [1, 2])
        self.assertTrue(all(is_jpeg(f.jpeg) and f.robot == "A" for f in frames))
        self.assertEqual(frames[0].camera_age_ms, 5)

    def test_malformed_stream_raises_instead_of_guessing(self):
        for data in (b"garbage\r\n", part(1, jpeg=b"not a jpeg!"), part(1, length=10 ** 7)):
            with self.assertRaises(ValueError):
                list(read_mjpeg(io.BytesIO(data), "A"))

    def test_truncated_part_ends_quietly(self):
        data = part(1)[:-10]
        self.assertEqual(list(read_mjpeg(io.BytesIO(data), "A")), [])


class StatusTests(unittest.TestCase):
    def test_valid_status(self):
        status = parse_status(mock_camera.CameraState("B").status(), "B")
        self.assertTrue(status["camera_ok"])
        self.assertFalse(status["recognition"])

    def test_wrong_robot_and_bad_fields_rejected(self):
        good = mock_camera.CameraState("A").status()
        with self.assertRaises(ValueError):
            parse_status(good, "B")
        for mutate in (lambda s: s["camera"].pop("ok"), lambda s: s["camera"].update(fps=float("nan")),
                       lambda s: s["camera"].update(ok="yes"), lambda s: s["wifi"].update(mode="x")):
            broken = mock_camera.CameraState("A").status()
            mutate(broken)
            with self.assertRaises(ValueError):
                parse_status(broken, "A")

    def test_endpoint_validation_and_urls(self):
        endpoint = CameraEndpoint("A", "cam.local", key="k y")
        self.assertEqual(endpoint.url("/stream"), "http://cam.local:81/stream?key=k+y")
        self.assertEqual(CameraEndpoint.default_host("B"), "mechdog-b-cam.local")
        for bad in (dict(robot="C", host="x"), dict(robot="A", host="x/y"), dict(robot="A", host="x", http_port=0)):
            with self.assertRaises(ValueError):
                CameraEndpoint(**bad)


class FreshnessTests(unittest.TestCase):
    def test_latest_goes_unknown_when_stale(self):
        clock = FakeClock()
        receiver = LatestFrameReceiver(CameraEndpoint("A", "x"), max_age_s=1.0, clock=clock)
        self.assertIsNone(receiver.latest())
        receiver.feed(io.BytesIO(part(1) + part(2)))
        self.assertEqual(receiver.latest().seq, 2)
        self.assertEqual(receiver.state()["status"], "streaming")
        clock.now += 1.5
        self.assertIsNone(receiver.latest())
        self.assertEqual(receiver.state()["status"], "unknown")

    def test_camera_reported_old_frame_is_not_fresh(self):
        receiver = LatestFrameReceiver(CameraEndpoint("A", "x"), max_camera_age_ms=500, clock=FakeClock())
        receiver.feed(io.BytesIO(part(1, age=900)))
        self.assertIsNone(receiver.latest())


class MockServerTests(unittest.TestCase):
    def setUp(self):
        self.state = mock_camera.CameraState("A", key="secret-key", fps=50)
        self.http = mock_camera.serve(self.state)
        self.stream = mock_camera.serve(self.state)
        for server in (self.http, self.stream):
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
        self.endpoint = CameraEndpoint("A", "127.0.0.1", self.http.server_address[1],
                                       self.stream.server_address[1], key="secret-key")

    def test_status_and_capture(self):
        client = CameraClient(self.endpoint, timeout_s=2)
        self.assertEqual(client.status()["status"], "ok")
        frame = client.capture()
        self.assertTrue(is_jpeg(frame.jpeg))
        self.assertIsNotNone(frame.seq)

    def test_missing_key_is_unknown(self):
        endpoint = CameraEndpoint("A", "127.0.0.1", self.http.server_address[1])
        client = CameraClient(endpoint, timeout_s=2)
        self.assertEqual(client.status(), {"robot": "A", "status": "unknown", "reason": "http_401"})
        self.assertIsNone(client.capture())

    def test_unreachable_camera_is_unknown(self):
        endpoint = CameraEndpoint("A", "127.0.0.1", 9, 9)
        self.assertEqual(CameraClient(endpoint, timeout_s=0.5).status()["status"], "unknown")

    def test_stream_keeps_newest_frame_then_goes_stale_when_camera_stalls(self):
        receiver = LatestFrameReceiver(self.endpoint, max_age_s=0.3, timeout_s=2, retry_s=0.1).start()
        self.addCleanup(receiver.stop)
        deadline = time.monotonic() + 3
        while receiver.frames < 3 and time.monotonic() < deadline:
            time.sleep(0.02)
        first = receiver.latest()
        self.assertIsNotNone(first)
        time.sleep(0.1)
        self.assertGreater(receiver.latest().seq, first.seq)
        self.state.stall.set()
        time.sleep(0.5)
        self.assertIsNone(receiver.latest())
        self.assertEqual(receiver.state()["status"], "unknown")
        self.state.stall.clear()


if __name__ == "__main__":
    unittest.main()
