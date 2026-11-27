"""Exercise both public command names after installing the owner away from the main suite."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_selected_suite_handoff(tmp_path):
    main = tmp_path / "selected"
    owner = tmp_path / "custom" / "handoff"
    alias = tmp_path / "compat"
    for directory in ("scripts", "schemas", "references"):
        shutil.copytree(ROOT / "ui-test" / directory, main / directory, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "a2a-handoff", owner)
    shutil.copytree(ROOT / "ui-test-a2a-handoff/scripts", alias / "scripts")
    (main / "references/suite-layout.json").write_text(json.dumps({"a2a-handoff": str(owner)}))
    env = dict(os.environ, UI_TEST_SUITE=str(main))
    source = owner / "fixtures/source_packet_valid.json"
    packet = json.loads(source.read_text())
    commands = [[main / "scripts/ui_test_suite.py", name] for name in ("a2a-handoff", "ui-test-a2a-handoff")]
    commands.append([alias / "scripts/a2a_handoff.py"])
    for i, command in enumerate(commands):
        out = tmp_path / f"bundle-{i}.json"
        subprocess.run([sys.executable, *command, source, "--output", out], env=env, check=True)
        bundle = json.loads(out.read_text())
        for name in ("handoff_packet", "prompt_packet"):
            assert bundle[name]["source_packet_id"] == packet["packet_id"]
            assert all(bundle[name][key] == value for key, value in packet.items())
        assert bundle["artifact_refs"]["refs"] == packet["artifact_refs"]
        assert bundle == json.loads((tmp_path / "bundle-0.json").read_text())
    # A schema rule in this installation proves the shared validator used the selected suite.
    schema = main / "schemas/ui-test-packet-v3.schema.json"
    rules = json.loads(schema.read_text())
    rules["required"].append("installation_marker")
    schema.write_text(json.dumps(rules))
    rejected = tmp_path / "rejected.json"
    failure = subprocess.run([sys.executable, *commands[0], source, "--output", rejected], env=env,
                             capture_output=True, text=True)
    assert failure.returncode == 2 and failure.stderr.strip() == "E_PACKET_SCHEMA at $"
    assert not rejected.exists()
