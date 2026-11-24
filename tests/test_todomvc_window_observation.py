"""同名 Chromium 窗口须归属于实际启动该浏览器的正式进程。"""
import os
import sys
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/todomvc"
sys.path.insert(0, str(EXAMPLE))


@pytest.mark.skipif(os.name != "nt", reason="Windows 可见桌面证据")
def test_probe_refuses_foreign_browser_when_runner_owns_none():
    from window_observation import read_owned_window

    with pytest.raises(RuntimeError, match="E_VISIBLE_WINDOW_NOT_OBSERVED"):
        read_owned_window(os.getpid(), "TodoMVC")

def _sample_lane(lane, directory):
    import json
    import time
    from playwright.sync_api import sync_playwright
    from window_observation import observe_window

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_content("<title>TodoMVC observation fixture</title><h1>Local window check</h1>")
        cdp = browser.new_browser_cdp_session()  # 使用实际连接的浏览器独立核对原生 PID。
        processes = cdp.send("SystemInfo.getProcessInfo")["processInfo"]
        expected_pid, = [row["id"] for row in processes if row["type"] == "browser"]
        cdp.detach()
        (directory / (lane + ".ready")).touch()
        peer = "B" if lane == "A" else "A"
        def wait_for(suffix):
            deadline = time.monotonic() + 60
            while not (directory / (peer + suffix)).exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("peer did not reach " + suffix)
                time.sleep(0.05)
        wait_for(".ready")
        start = time.monotonic_ns()
        result = observe_window(page)
        elapsed = time.monotonic_ns() - start
        assert result["windows"]["Id"] == expected_pid
        assert result["runner_pid"] == os.getpid()
        assert 0 < elapsed < 8_000_000_000
        (directory / (lane + ".json")).write_text(json.dumps(
            dict(result=result, expected_pid=expected_pid, elapsed_ns=elapsed, page_url=page.url)), encoding="utf-8")
        wait_for(".json")  # 对端完成观察前保留本窗口，两个相同标题必须同时存在。
        browser.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows 可见桌面证据")
def test_two_independent_visible_windows_with_the_same_title(tmp_path):
    import json
    import subprocess

    lanes = [subprocess.Popen([sys.executable, str(Path(__file__).resolve()), name, str(tmp_path)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT) for name in ("A", "B")]
    try:
        for lane in lanes:
            output, _ = lane.communicate(timeout=90)
            assert lane.returncode == 0, output.decode(errors="replace")
    finally:
        for lane in lanes:
            if lane.poll() is None:
                lane.terminate()  # 仅收回测试自己启动的子进程。
                lane.wait(timeout=10)
    docs = [json.loads((tmp_path / (name + ".json")).read_text()) for name in ("A", "B")]
    assert len({d["expected_pid"] for d in docs}) == 2
    assert len({d["result"]["windows"]["MainWindowHandle"]["value"] for d in docs}) == 2
    assert len({d["result"]["windows"]["MainWindowTitle"] for d in docs}) == 1


if __name__ == "__main__":
    _sample_lane(sys.argv[1], Path(sys.argv[2]))
