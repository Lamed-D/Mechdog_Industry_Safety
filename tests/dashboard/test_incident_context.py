from pathlib import Path
import tempfile
import unittest

from dashboard.core import EventLog
from dashboard.web.run import build_sim
from tools.export_incidents import export_rows


class IncidentContextTests(unittest.TestCase):
    def test_incident_keeps_evidence_and_both_robot_states_without_image_bytes(self):
        core, links = build_sim()
        self.addCleanup(core.log.close)
        for link in links.values():
            link.step()
        core.update()
        core.detection({"robot": "B", "status": "needs_check", "source": "synthetic", "confidence": .9,
                        "frame": {"seq": 7, "width": 640, "height": 480, "jpeg": b"synthetic", "sha256": "a" * 64}})
        context = core.log.recent(1)[0]
        self.assertEqual(context["kind"], "incident_context")
        self.assertEqual(set(context["detail"]["robots"]), {"A", "B"})
        self.assertEqual(context["detail"]["robots"]["A"]["reason"], "boot")
        self.assertNotIn("jpeg", context["detail"]["detection"]["frame"])

    def test_read_only_export_preserves_database_and_evidence_source(self):
        root = Path(__file__).resolve().parents[2] / "build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            path = Path(directory) / "events.db"
            log = EventLog(path, wall=lambda: 42)
            log.record("incident_context", "A", {"v": 1, "detection": {"source": "synthetic"}})
            log.close()
            original = path.read_bytes()
            rows = list(export_rows(path))
            self.assertEqual(rows[0]["evidence_source"], "synthetic")
            self.assertEqual(rows[0]["time_utc"], "1970-01-01T00:00:42+00:00")
            self.assertEqual(path.read_bytes(), original)

    def test_ui_alert_history_is_bounded_and_current_incident_is_kept(self):
        core, _ = build_sim()
        self.addCleanup(core.log.close)
        for i in range(105):
            core.detection({"robot": "A", "status": "needs_check", "source": "synthetic"})
            core.operator("resolved")
        core.detection({"robot": "B", "status": "needs_check", "source": "synthetic"})
        self.assertEqual(len(core.alerts), 100)
        self.assertEqual(core.alerts[-1]["id"], 106)
        self.assertEqual(core.alerts[-1]["state"], "open")
