"""Latest LiDAR revolution for the diagnostic console."""

import math
import threading
import time
from contextlib import closing

from dashboard.lidar.laser_scan import ranges_metres
from dashboard.lidar.scan_assembler import ScanAssembler
from dashboard.lidar.tcp_client import LidarClient
from dashboard.lidar.probe import usb_samples


class LidarFeed:
    def __init__(self, *, usb=None, tcp=None, port=20108, clock=time.monotonic):
        self.usb = usb
        self.client = LidarClient(tcp, port) if tcp else None
        self.source = "USB" if usb else "TCP" if tcp else None
        self.clock = clock
        self.stop_event = threading.Event()
        self.assembler = ScanAssembler()
        self.lock = threading.Lock()
        self.latest = None
        self.error = None

    def accept(self, sample):
        scan = self.assembler.add(sample)
        if scan is not None:
            ranges = [r if math.isfinite(r) else None for r in ranges_metres(scan)]
            with self.lock:
                self.latest = self.clock(), ranges
                self.error = None

    def disconnected(self, error):
        self.assembler.reset()
        with self.lock:
            self.latest = None
            self.error = str(error)

    def run(self):
        if self.client:
            self.client.run(self.accept, self.disconnected, self.stop_event)
        elif self.usb:
            try:
                with closing(usb_samples(self.usb)) as samples:
                    for sample in samples:
                        if self.stop_event.is_set():
                            break
                        if sample is not None:
                            self.accept(sample)
            except (OSError, ValueError, ImportError) as error:
                self.disconnected(error)

    def snapshot(self):
        with self.lock:
            if not self.source:
                return {"status": "disabled", "ranges_m": []}
            if self.error:
                return {"status": "error", "source": self.source, "error": self.error, "ranges_m": []}
            if self.latest is None:
                return {"status": "waiting", "source": self.source, "ranges_m": []}
            stamp, ranges = self.latest
            if self.clock() - stamp >= 1:
                return {"status": "stale", "source": self.source, "ranges_m": []}
            return {"status": "ready", "source": self.source, "ranges_m": ranges}
