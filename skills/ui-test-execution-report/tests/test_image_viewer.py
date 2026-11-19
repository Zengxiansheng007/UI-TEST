"""图片来源、证据保真与生成器集成回归。"""
import base64
import copy
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from image_viewer import install_image_viewer, render_image_evidence
import generate_report
from validate_execution_report_skill import validate_image_viewer

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jM1sAAAAASUVORK5CYII=")


class ImageViewerTests(unittest.TestCase):
    def test_local_png_bytes_and_evidence_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            path.write_bytes(PNG)
            evidence = {"path": str(path), "sha256": hashlib.sha256(PNG).hexdigest()}
            original = copy.deepcopy(evidence)
            markup = render_image_evidence(evidence, "截图")
            source = re.search(r'src="([^"]+)"', markup).group(1)
            self.assertEqual(base64.b64decode(source.partition(",")[2]), PNG)
            self.assertEqual(evidence, original)
            self.assertIn('class="ui-image-trigger"', markup)
            self.assertNotIn("<svg", markup)

    def test_hash_mismatch_fails_closed(self):
        source = "data:image/png;base64," + base64.b64encode(PNG).decode()
        with self.assertRaisesRegex(ValueError, "E_UI_IMAGE_HASH_MISMATCH"):
            render_image_evidence({"data_uri": source, "sha256": "0" * 64})

    def test_missing_file_is_not_replaced_with_illustration(self):
        rendered = generate_report.ui_cell({"step_id": "S", "ui_evidence": {"path": "missing/image.png", "svg_kind": "login"}})
        self.assertIn("data-ui-image-missing", rendered)
        self.assertNotIn("<svg", rendered)
        self.assertNotIn("<img", rendered)

    def test_remote_and_active_image_sources_are_not_loaded(self):
        for source in ({"path": "https://example.invalid/image.png"},
                       {"data_uri": "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="},
                       {"data_uri": "javascript:alert(1)"}):
            rendered = render_image_evidence(source)
            self.assertIn("data-ui-image-missing", rendered)
            self.assertNotIn("<img", rendered)

    def test_untrusted_title_cannot_inject_markup(self):
        source = "data:image/png;base64," + base64.b64encode(PNG).decode()
        rendered = render_image_evidence({"data_uri": source}, '<script>alert("x")</script>')
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_viewer_installation_is_standalone_and_idempotent(self):
        document = "<html><head></head><body>sample</body></html>"
        installed = install_image_viewer(document)
        self.assertEqual(install_image_viewer(installed), installed)
        self.assertIn("showModal()", installed)
        self.assertIn('data-viewer-action="actual"', installed)
        self.assertNotIn('<script src=', installed)

    def test_copied_html_retains_image_after_original_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original.png"
            original.write_bytes(PNG)
            markup = render_image_evidence({"path": str(original)})
            document = install_image_viewer("<html><head></head><body>" + markup + "</body></html>")
            isolated = root / "isolated"
            isolated.mkdir()
            report = isolated / "report.html"
            report.write_text(document, encoding="utf-8")
            original.unlink()
            self.assertEqual(len(list(isolated.iterdir())), 1)
            source = re.search(r'src="([^"]+)"', report.read_text(encoding="utf-8")).group(1)
            self.assertEqual(base64.b64decode(source.partition(",")[2]), PNG)
            self.assertEqual(validate_image_viewer(report), [])

    def test_portability_validator_rejects_sidecar_resources(self):
        for tag in ('<img src="D:/screenshots/a.png">', '<img src="image.png">',
                    '<img src="file:///D:/a.png">', '<script src="viewer.js"></script>',
                    '<link rel="stylesheet" href="style.css">', '<style>@import "theme.css";</style>'):
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as directory:
                report = Path(directory) / "report.html"
                report.write_text(install_image_viewer("<html><head></head><body>" + tag + "</body></html>"), encoding="utf-8")
                self.assertTrue(any(item['rule'] == 'image-viewer-offline' for item in validate_image_viewer(report)))

    def test_document_structure_is_required(self):
        with self.assertRaisesRegex(ValueError, "E_UI_IMAGE_DOCUMENT_STRUCTURE"):
            install_image_viewer("not html")

    def test_report_generator_uses_shared_viewer_without_changing_result(self):
        sample = json.loads((Path(__file__).resolve().parents[1] / "assets/sample-run.json").read_text(encoding="utf-8"))
        original = copy.deepcopy(sample)
        rendered = generate_report.render_html(sample)
        self.assertEqual(sample, original)
        self.assertIn('id="ui-image-viewer-script"', rendered)
        self.assertNotIn("<svg", rendered)


if __name__ == "__main__":
    unittest.main()
