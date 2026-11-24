import base64
from types import SimpleNamespace
from playwright.sync_api import sync_playwright

from scripts.ui_test_core.stage_capture import capture_step


def test_existing_file_is_preserved_as_capture_gap(tmp_path):
    source = tmp_path / "existing.png"
    source.write_bytes(b"original")
    step = dict(step_id="assert", status="failed")
    image = capture_step(SimpleNamespace(frames=[], screenshot=lambda **opts: bytes(24)), step,
                         context=dict(run_id="r", case_id="c", attempt_ref="a"), run_root=tmp_path,
                         point="ordinary", object_ref="row", observation="failure scene", ref=source.name)
    assert image["missing_reason"] and "path" not in image and not step.get("evidence_refs")
    assert step["status"] == "failed" and source.read_bytes() == b"original"


def test_live_query_and_author_images_belong_to_current_step(tmp_path):
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 660, "height": 400})
        page.set_content('<body style="height:850px"><p>Record ABC</p><input type=password style="position:absolute;left:10px;top:70px">')
        page.locator("input").fill("synthetic-private")
        assert page.get_by_text("Record ABC").is_visible()
        context = dict(run_id="run",case_id="case",attempt_ref="attempt")
        step = dict(step_id="read",action="Inspect record ABC")
        for point in ("query","author"):
            image = capture_step(page,step,context=context,run_root=tmp_path,point=point,
                                 object_ref="ABC",observation="Record ABC visible",reason="Check row",
                                 full_page=point == "author")
            assert image["width"] == 660 and image["height"] == (866 if point == "author" else 400)
            source = tmp_path / image["path"]
            encoded = base64.b64encode(source.read_bytes()).decode()
            pixel = page.evaluate("""async data => {
              const image = new Image(); image.src='data:image/png;base64,'+data; await image.decode();
              const ctx=document.createElement('canvas').getContext('2d'); ctx.drawImage(image,0,0);
              return [...ctx.getImageData(20,75,1,1).data];
            }""", encoded)
            assert pixel == [0,0,0,255]
        assert step["evidence_refs"] == [image["path"] for image in step["images"]]
        assert step["key_reason"] == "Check row"
        browser.close()
