import json
import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("a2a_handoff", ROOT / "scripts/a2a_handoff.py")
mapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mapper)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((ROOT / "fixtures/source_packet_valid.json").read_text())

    def test_preserves_task_and_source(self):
        self.packet.update(state="evidence", next_action="collect-evidence")
        self.packet["handoff"]["failure_history"] = [{"failure": "fixture"}]
        bundle = mapper.pack(self.packet)
        self.assertEqual(bundle, mapper.pack(self.packet))
        for output in ("handoff_packet", "prompt_packet"):
            self.assertEqual(bundle[output]["source_packet_id"], self.packet["packet_id"])
            for key, value in self.packet.items():
                self.assertEqual(bundle[output][key], value)
        self.assertEqual(bundle["artifact_refs"]["refs"], self.packet["artifact_refs"])

    def test_review_cannot_override(self):
        with self.assertRaises(ValueError):
            mapper.pack(self.packet, {"allowed_actions": ["submit"]})

    def test_unknown_history(self):
        self.packet["handoff"]["history_status"] = "unknown"
        self.assertEqual(mapper.pack(self.packet)["prompt_packet"]["handoff"]["history_status"], "unknown")
        self.packet["next_action"] = "rerun"
        with self.assertRaises(ValueError):
            mapper.pack(self.packet)

    def test_conflicts_and_old_packets(self):
        for key, value in (("schema_version", "2.0"), ("next_action", "evidence"), ("risk_level", "r2-ui-write-test")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                mapper.pack(dict(self.packet, **{key: value}))

    def test_sensitive_refs(self):
        self.packet["artifact_refs"].append("Bear" + "er example")
        with self.assertRaises(ValueError):
            mapper.pack(self.packet)
