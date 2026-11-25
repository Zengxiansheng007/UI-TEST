import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "a2a_handoff.py"
FIXTURE = ROOT / "fixtures" / "source_packet_valid.json"


class A2AHandoffCliTests(unittest.TestCase):
    def test_project_bundle_is_owned_by_the_requested_stage(self):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([sys.executable, str(SCRIPT), str(FIXTURE), "--project", td,
                            "--stage", "midscene", "--stage-run-id", "run41"], check=True)
            paths = list((Path(td) / "运行").glob("m*/交接/*.json"))
            self.assertEqual(len(paths), 1)
            self.assertIn("handoff_packet", json.loads(paths[0].read_text("utf8")))

    def test_cli_writes_output(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.json"
            cmd = [sys.executable, str(SCRIPT), str(FIXTURE), "--output", str(out)]
            subprocess.run(cmd, check=True)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("handoff_packet", payload)
            self.assertNotIn("hand_off", payload)
            self.assertIn("prompt_packet", payload)
            self.assertIn("artifact_refs", payload)


if __name__ == "__main__":
    unittest.main()
