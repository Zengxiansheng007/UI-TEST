"""Verify both command names against an explicitly relocated suite."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class SelectedCheckpointTests(unittest.TestCase):
    def test_roundtrip_and_missing_identity(self):
        skills = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "selected"
            for name in ("scripts", "schemas", "references"):
                shutil.copytree(skills / "ui-test" / name, main / name)
            layout = {}
            for name in ("checkpoint-schema", "a2a-handoff"):
                owner = root / (name + "-owner")
                shutil.copytree(skills / name, owner)
                layout[name] = str(owner)
            layout_file = main / "references/suite-layout.json"
            layout_file.write_text(json.dumps(layout))
            fixtures = Path(layout["checkpoint-schema"]) / "fixtures"
            entry = main / "scripts/ui_test_suite.py"
            old_script = skills / "ui-test-checkpoint-schema/scripts/checkpoint_schema.py"

            def run(command, *args, ok=True):
                result = subprocess.run([sys.executable, *command, *args], cwd=root,
                                        env=dict(os.environ, UI_TEST_SUITE=str(main)),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, ok, result.stderr)
                return result.stderr

            def read(name):
                return json.loads((root / name).read_text())

            task = json.loads((fixtures / "current_task.json").read_text())
            facts = json.loads((fixtures / "facts.json").read_text())
            definition = fixtures / "definition.json"
            for command in ([entry, "checkpoint-schema"], [entry, "ui-test-checkpoint-schema"], [old_script]):
                run(command, "validate", "--input", definition)
                run(command, "capture", "--definition", definition, "--task", fixtures / "current_task.json",
                    "--facts", fixtures / "facts.json", "--output", "snapshot.json")
                run(command, "packet", "--input", "snapshot.json", "--output", "packet.json")
                run(command, "bundle", "--input", "snapshot.json", "--output", "bundle.json")
                snapshot, packet, bundle = map(read, ("snapshot.json", "packet.json", "bundle.json"))
                self.assertEqual(snapshot, bundle["snapshot"])
                self.assertEqual(packet, bundle["ui_test_packet"])
                self.assertEqual(snapshot["task"], task)
                for key in facts:
                    self.assertEqual(snapshot[key], facts[key])
                for part in (packet, bundle["handoff_packet"], bundle["prompt_packet"]):
                    for key in ("case", "branch", "scope", "run"):
                        self.assertEqual(part[key], task[key])
                    self.assertIn(facts["snapshot_id"], part["lineage"]["source_refs"])
                    self.assertIn("checkbox-definition", part["lineage"]["source_refs"])
                incomplete = dict(facts)
                del incomplete["session_id"]
                (root / "missing.json").write_text(json.dumps(incomplete))
                error = run(command, "capture", "--definition", definition, "--task", fixtures / "current_task.json",
                            "--facts", "missing.json", "--output", "bad.json", ok=False)
                self.assertIn("session_id", error)
                self.assertFalse((root / "bad.json").exists())
            invalid = json.loads(definition.read_text())
            invalid["applies_to"]["unrecognized"] = 1
            (root / "invalid.json").write_text(json.dumps(invalid))
            self.assertIn("applies_to", run([entry, "checkpoint-schema"], "validate", "--input",
                                            "invalid.json", ok=False))
            layout["a2a-handoff"] = str(root / "missing-handoff")
            layout_file.write_text(json.dumps(layout))
            self.assertIn("E_SUITE_CAPABILITY_MISSING", run([entry, "checkpoint-schema"], "bundle",
                          "--input", "snapshot.json", "--output", "bad.json", ok=False))
