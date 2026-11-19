import json
import unittest
from pathlib import Path
from scripts.checkpoint_schema import capture_snapshot, build_checkpoint_bundle

class ExecutionSnapshotTests(unittest.TestCase):
    def test_captured_task_round_trips(self):
        root = Path(__file__).resolve().parents[1]
        packet = json.loads((root / "fixtures/current_task.json").read_text())
        definition = json.loads((root / "fixtures/definition.json").read_text())
        facts = json.loads((root / "fixtures/facts.json").read_text())
        snapshot = capture_snapshot(definition, packet, facts)
        bundle = build_checkpoint_bundle(snapshot)
        self.assertEqual(bundle, build_checkpoint_bundle(snapshot))
        self.assertEqual(bundle["ui_test_packet"]["lineage"]["parent_packet_id"], packet["packet_id"])
        self.assertEqual(bundle["prompt_packet"]["source_packet_id"],bundle["ui_test_packet"]["packet_id"])

        packet["run"]["run_id"] = "run-b"
        with self.assertRaisesRegex(ValueError, "another run"):
            capture_snapshot(definition, packet, facts)
        del packet["packet_id"]
        facts.update(run_id="run-b", session_id="session-b", snapshot_id="snap-b")
        for result in facts["step_results"]:
            result["evidence_refs"] = ["run-b/" + result["step_id"]]
        second = build_checkpoint_bundle(capture_snapshot(definition, packet, facts))
        second_packet = second["ui_test_packet"]
        self.assertNotEqual(bundle["ui_test_packet"]["packet_id"], second_packet["packet_id"])
        self.assertNotIn("local/S01", second_packet["artifact_refs"])
        self.assertNotIn("parent_packet_id", second_packet["lineage"])
        self.assertEqual(second_packet["steps"][1]["postcondition"], definition["steps"][1]["verification"])
        self.assertEqual(second_packet["steps"][0]["evidence_refs"], ["run-b/S01"])
        definition["applies_to"]["environment"] = "other"
        with self.assertRaisesRegex(ValueError, "applicability"):
            capture_snapshot(definition, packet, facts)
