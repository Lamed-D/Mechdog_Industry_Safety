"""Run from the repo root after sourcing ROS: python -m ros2.scan_node --help."""
import argparse
import math
import queue
import threading
import time

from host.lidar.laser_scan import ranges_metres
from host.lidar.scan_assembler import ScanAssembler
from host.lidar.tcp_client import LidarClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot", choices=("A", "B"), required=True)
    parser.add_argument("--host", default="127.0.0.1")
    from robot.config import LIDAR_TCP_PORT
    parser.add_argument("--port", type=int, default=LIDAR_TCP_PORT)
    parser.add_argument("--direction", type=int, choices=(-1, 1), default=-1)
    parser.add_argument("--offset-deg", type=float, default=0)
    args = parser.parse_args()
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import LaserScan

    class ScanNode(Node):
        def __init__(self):
            super().__init__("scan_" + args.robot.lower())
            self.stop = threading.Event()
            self.inbox = queue.Queue(maxsize=2)
            self.publisher = self.create_publisher(LaserScan, "/robot_%s/scan" % args.robot.lower(),
                                                   qos_profile_sensor_data)
            self.create_timer(0.01, self.publish_pending)
            self.worker = threading.Thread(target=self.receive, daemon=True)
            self.worker.start()

        def enqueue(self, item):
            try:
                self.inbox.put_nowait(item)
            except queue.Full:
                try:
                    self.inbox.get_nowait()
                except queue.Empty:
                    pass
                self.inbox.put_nowait(item)

        def receive(self):
            assembler = ScanAssembler(args.offset_deg, args.direction)
            started = [None]

            def sample(value):
                now = time.monotonic()
                scan = assembler.add(value)
                if value.start:
                    if scan is not None and started[0] is not None:
                        self.enqueue((now, now - started[0], scan))
                    started[0] = now

            def disconnected(error):
                assembler.reset()
                started[0] = None
                self.enqueue((time.monotonic(), 0, str(error)))

            client = LidarClient(args.host, args.port,
                                 on_health=lambda status, code: self.enqueue((time.monotonic(), 0,
                                     "lidar health status=%d code=%d" % (status, code))) if status else None)
            client.run(sample, disconnected, self.stop)

        def publish_pending(self):
            while True:
                try:
                    arrived, duration, scan = self.inbox.get_nowait()
                except queue.Empty:
                    return
                if isinstance(scan, str):
                    self.get_logger().warning(scan)
                    continue
                age = time.monotonic() - arrived
                if age > 0.3 or not 0 < duration <= 1:
                    self.get_logger().warning("discarded stale or incomplete scan")
                    continue
                message = LaserScan()
                # Receive-time estimate, not a hardware timestamp; network latency is unknown.
                ns = self.get_clock().now().nanoseconds - int((duration + age) * 1e9)
                message.header.stamp.sec, message.header.stamp.nanosec = divmod(ns, 1000000000)
                message.header.frame_id = "laser_" + args.robot.lower()
                message.angle_min = 0.0
                message.angle_increment = 2 * math.pi / 360
                message.angle_max = 359 * message.angle_increment
                message.scan_time = duration
                message.time_increment = 0.0  # Binned points have no uniform acquisition order.
                message.range_min, message.range_max = 0.15, 12.0
                message.ranges = ranges_metres(scan)
                self.publisher.publish(message)

    rclpy.init(args=[])
    node = ScanNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop.set()
        node.worker.join(3)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
