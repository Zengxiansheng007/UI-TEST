"""Exercise the published planning CLI with the selected core."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PLAN = Path(__file__).resolve().parents[1]
SUITE = PLAN.parent / "ui-test"
ENTRY = PLAN / "scripts" / "build_plan.py"
SOURCE = PLAN / "assets" / "playground-wizard.json"


class PlanningTests(unittest.TestCase):
    def invoke(self, source, directory):
        request = directory / "source.json"
        request.write_text(json.dumps(source), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(ENTRY), "--input", str(request), "--output", str(directory / "packet.json")],
            env={**os.environ, "PYTHONPATH": str(SUITE / "scripts")},
            capture_output=True, text=True, encoding="utf-8",
        )

    def test_public_plan_preserves_scope_steps_identity_and_expected_result(self):
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            result = self.invoke(source, target)
            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads((target / "packet.json").read_text(encoding="utf-8"))
            self.assertEqual(packet["case"]["case_id"], "AP-34")
            self.assertEqual(packet["scope"]["module_path"], ["section-34"])
            self.assertEqual(sum(s["action"] == "submit" for s in packet["steps"]), 1)
            self.assertIn("Wizard submitted successfully!", packet["steps"][-1]["postcondition"])
            self.assertEqual(packet["next_action"], "explore")

    def test_missing_business_oracle_requests_clarification_and_creates_no_packet(self):
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        del source["steps"][-1]["postcondition"]
        with tempfile.TemporaryDirectory() as tmp:
            result = self.invoke(source, Path(tmp))
            self.assertEqual(result.returncode, 2)
            self.assertIn("result.postcondition", result.stdout)
            self.assertFalse((Path(tmp) / "packet.json").exists())
