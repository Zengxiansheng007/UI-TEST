"""Exercise the exploration archive boundary using only controlled data."""
import base64
import hashlib
import sys
from pathlib import Path

import pytest

PACKAGES = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGES / "ui-test-explore/scripts"))
from publish_observations import deliver

PIXELS = b"GIF89a" + bytes(24)


def batch(step):
    case = dict(node_id="c", case_id="c", attempt_ref="1", run_id="r", status="observed", steps=[step])
    return dict(stage="midscene", run_id="r", cases=[case])


@pytest.mark.parametrize("value", ["Bearer " + "controlled-sample-value", "password" + "=" + "sample-only",
                                  "sk-" + "x" * 24], ids=["header", "assignment", "provider"])
def test_sensitive_nested_observation_never_archived(tmp_path, value):
    output = tmp_path / "r"
    output.mkdir()
    with pytest.raises(ValueError, match="E_STAGE_SENSITIVE_FIELDS"):
        deliver(batch(dict(step_id="s", actual_result=value)), output)
    assert not list(output.iterdir())


@pytest.mark.parametrize("embedded", [True, False])
def test_local_or_embedded_image_cannot_bypass_ownership_and_digest(tmp_path, embedded):
    output = tmp_path / "r"
    output.mkdir()
    shot = output / "x.gif"
    shot.write_bytes(PIXELS)
    image = dict(data_uri="data:image/gif;base64," + base64.b64encode(PIXELS).decode()) if embedded else dict(path=str(shot))
    for metadata in [{}, dict(sha256=hashlib.sha256(PIXELS).hexdigest(), stage="midscene",
                             case_id="c", attempt_ref="1", run_id="r", step_id="s")]:
        with pytest.raises(ValueError, match="E_EXPLORATION_IMAGE"):
            deliver(batch(dict(step_id="s", images=[dict(image, **metadata)])), output)
        assert not (output / "observations.json").exists()


@pytest.mark.parametrize("embedded", [True, False])
def test_original_digest_is_required_even_for_unrecognized_replacement_bytes(tmp_path, embedded):
    import json
    output = tmp_path / "r"
    folder = output / "images"
    folder.mkdir(parents=True)
    capture = "e3b492ab-8b88-4992-b343-e795a038a302"
    shot = folder / (capture + ".png")
    receipt = dict(stage="midscene", case_id="c", attempt_ref="1", run_id="r", step_id="s",
                   path=str(shot), sha256=hashlib.sha256(PIXELS).hexdigest())
    (folder / (capture + ".json")).write_text(json.dumps(receipt))
    shot.write_bytes(b"changed")
    image = dict(receipt, capture_id=capture)
    if embedded:
        del image["path"]
        image["data_uri"] = "data:image/gif;base64," + base64.b64encode(b"changed").decode()
    previous = output / "report.html"
    previous.write_bytes(b"original-report")
    with pytest.raises(ValueError, match="E_UI_IMAGE_HASH_MISMATCH"):
        deliver(batch(dict(step_id="s", images=[image])), output, archived=True)
    assert previous.read_bytes() == b"original-report"
