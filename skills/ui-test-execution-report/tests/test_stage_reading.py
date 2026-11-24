"""Exercise the shared offline reading surface at the published document boundary."""
import base64
import hashlib
import sys
from pathlib import Path
from html.parser import HTMLParser

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stage_report import publish_stage_report


GIF = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
GIF_HASH = hashlib.sha256(base64.b64decode(GIF.split(",", 1)[1])).hexdigest()


class ReadingOrder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []
        self.links = []
        self.toggles = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "a":
            self.links.append(attrs["href"])
        if "id" in attrs:
            self.targets.append(attrs["id"])
        if tag == "details" and attrs.get("class") == "ordinary-images":
            self.toggles.append("open" in attrs)


def test_only_event_bound_failure_scene_is_always_visible(tmp_path):
    images = [dict(point=p, role="ordinary", caption=p, data_uri=GIF, sha256=GIF_HASH) for p in ("ordinary", "failure")]
    case = dict(node_id="c", case_id="c", status="failed", steps=[dict(step_id="s", status="failed", images=images)])
    document = Path(publish_stage_report("midscene", "r", [case], tmp_path)["report_html"]).read_text("utf8")
    key, ordinary = document.split('<details class="ordinary-images">', 1)
    assert 'data-image-title="failure"' in key and 'data-image-title="ordinary"' in ordinary


def test_report_links_to_key_steps_and_keeps_ordinary_pictures_local(tmp_path):
    steps = [dict(step_id=str(i), action="检查", images=[dict(role=role, data_uri=GIF, sha256=GIF_HASH)])
             for i, role in enumerate(["ordinary", "ordinary", "key"])]
    case = dict(case_id="查询 A-17", node_id="query", status="observed", steps=steps)
    delivery = publish_stage_report("midscene", "explore", [case], tmp_path)
    document = Path(delivery["report_html"]).read_text(encoding="utf8")
    order = ReadingOrder()
    order.feed(document)
    assert order.toggles == [False, False]
    assert "#case-1" in order.links and "#case-1-step-3" in order.links
    assert all(link[1:] in order.targets for link in order.links if link.startswith("#"))
    assert document.count('class="ui-image-trigger"') == 3


def test_eligible_representative_and_all_source_refs_survive_publication(tmp_path):
    def receipt(caption, **fields):
        return dict(dict(role="key", data_uri=GIF, sha256=GIF_HASH, point="receipt", object_ref="A-17",
                         observation="已受理", caption=caption), **fields)
    steps = [dict(step_id="submit", images=[
        receipt("overview", preferred=True, support="context"), receipt("first"),
        receipt("choice", preferred=True, final_goal="受理申请"),
        receipt("another request", object_ref="A-18"),
        receipt("failed", point="final", observation="处理失败", object_ref="A-18"),
    ])]
    case = dict(case_id="C", node_id="n", status="observed", steps=steps)
    for stage in ("midscene", "playwright"):
        delivery = publish_stage_report(stage, "r", [dict(case, attempt_ref="a"), dict(case, attempt_ref="b")],
                                        tmp_path / stage)
        document = Path(delivery["report_html"]).read_text(encoding="utf8")
        body, sources = document.split('<details class="sources">')
        assert body.count('<figure') == 6
        for title in ("choice", "another request", "failed"):
            assert body.count(f'data-image-title="{title}"') == 2
        assert body.count("回执同时证明最终目标") == 2
        for title in ("overview", "first"):
            assert sources.count(f'data-image-title="{title}"') == 2
        order = ReadingOrder()
        order.feed(document)
        assert len(order.targets) == len(set(order.targets))
        assert all(link[1:] in order.targets for link in order.links if link.startswith("#"))


def test_unusable_designation_and_separate_observation_times(tmp_path):
    base = dict(role="key", data_uri=GIF, sha256=GIF_HASH, point="query", object_ref="A-17", observation="pending")
    first = dict(step_id="first", images=[
        dict(base, caption="missing", data_uri="", preferred=True),
        dict(base, caption="overview", support="context", preferred=True),
        dict(base, caption="verified"), dict(base, caption="later alternative")])
    second = dict(step_id="after-refresh", images=[dict(base, caption="after refresh")])
    case = dict(case_id="C", node_id="n", status="observed", steps=[first, second])
    delivery = publish_stage_report("midscene", "r", [case], tmp_path)
    document = Path(delivery["report_html"]).read_text(encoding="utf8")
    body, sources = document.split('<details class="sources">')
    assert body.count('<figure') == 2 and '截图缺失' in body
    assert 'data-image-title="verified"' in body and 'data-image-title="after refresh"' in body
    assert 'data-image-title="later alternative"' in sources and 'data-image-title="overview"' in sources
