"""Check the archived entry distribution and the original response spellings."""
import json
from pathlib import Path
import re

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def test_archived_entries_ship_outside_the_capability_catalog():
    catalog = json.loads((SKILLS / "ui-test/references/capabilities.json").read_bytes())
    active = {entry["name"] for entry in catalog["entries"]}
    targets = {"ui-test-system": "ui-test", "ui-test-system-a2a-handoff": "ui-test-a2a-handoff",
               "ui-test-system-checkpoint-schema": "ui-test-checkpoint-schema",
               "checkpoint-runtime-v1": "ui-test-checkpoint-runtime"}
    for name, replacement in targets.items():
        directory = SKILLS / name
        text = (directory / "SKILL.md").read_text(encoding="utf8")
        result = json.loads(re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)[1])
        expected = dict(deprecated=True, archived=True, replacement=replacement, payload_forwarded=False)
        if name == "ui-test-system":
            expected = dict(deprecated=True, replacement=replacement, route=replacement,
                            payloadForwarded=False, statusCode="archived", statusLabelZh="已归档")
        assert result == expected
        assert name not in active and not (directory / "scripts").exists()
        assert "allow_implicit_invocation: false" in (directory / "agents/openai.yaml").read_text(encoding="utf8")
