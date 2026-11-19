import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "checkpoint_schema.py"
FIXTURE = ROOT / "fixtures" / "checkpoint_samples_valid.json"


class CheckpointSchemaCliTests(unittest.TestCase):
    def test_validate_cli_accepts_valid_fixtures(self):
        cmd = [sys.executable, str(SCRIPT), "validate", "--input", str(FIXTURE)]
        subprocess.run(cmd, check=True)

    def test_bundle_cli_writes_output(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "bundle.json"
            snapshot = Path(td) / "snapshot.json"
            subprocess.run([sys.executable, str(SCRIPT), "capture", "--definition", str(ROOT/"fixtures/definition.json"),
                            "--task", str(ROOT/"fixtures/current_task.json"),
                            "--facts", str(ROOT/"fixtures/facts.json"), "--output", str(snapshot)], check=True)
            subprocess.run([sys.executable, str(SCRIPT), "bundle", "--input", str(snapshot), "--output", str(out)], check=True)
            bundle = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(bundle["handoff_packet"]["source_packet_id"], bundle["ui_test_packet"]["packet_id"])
            self.assertEqual(bundle["prompt_packet"]["steps"][1]["evidence_refs"], ["example/S02"])
            self.assertEqual(bundle["ui_test_packet"]["steps"][1]["action"], "assert")
            self.assertIn("example/S02", bundle["prompt_packet"]["artifact_refs"])


if __name__ == "__main__":
    unittest.main()
