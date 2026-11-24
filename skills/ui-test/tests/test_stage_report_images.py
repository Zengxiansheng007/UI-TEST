"""A formal stage may embed only evidence bound to the current sealed step."""
from pathlib import Path
import sys

import pytest


def test_legacy_references_show_digest_limit_and_verified_ordinary_image(tmp_path):
    step = dict(step_id="OPEN", evidence_refs=["reports/OPEN.png", "reports/next.png"],
                screenshot_ref="reports/next.png", screenshot_sha256="a" * 64)
    images = formal_step(step, tmp_path, {"evidence_refs": step["evidence_refs"]})["images"]
    assert images[0]["source_ref"] == "reports/OPEN.png" and "摘要" in images[0]["missing_reason"]
    assert images[1]["role"] == "ordinary" and images[1]["sha256"] == "a" * 64

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.ui_test_core.stage_delivery import formal_step


def test_formal_projection_keeps_source_ref_and_resolves_against_case_root(tmp_path):
    ref = "images/lookup.png"
    image = {"role": "key", "path": ref, "sha256": "1" * 64}
    step = {"step_id": "lookup", "evidence_refs": [ref], "images": [image]}
    projected = formal_step(step, tmp_path)
    assert projected["images"] == [{**image, "source_ref": ref, "path": str(tmp_path / ref)}]
    assert step["images"][0]["path"] == ref


@pytest.mark.parametrize("ref,refs,digest", [
    ("../elsewhere.png", ["../elsewhere.png"], "1" * 64),
    ("other.png", [], "1" * 64),
    ("lookup.png", ["lookup.png"], ""),
])
def test_unbound_formal_images_fail_before_report_publication(tmp_path, ref, refs, digest):
    with pytest.raises(ValueError):
        formal_step({"images": [{"path": ref, "sha256": digest}], "evidence_refs": refs}, tmp_path)
