"""只记录当前本地 Playwright runner 的可见 Chromium 窗口。"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


def _owned_browser(runner_pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    entry_args = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = entry_args
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS，仅复制进程关系。
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    drivers, browsers = set(), {}
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        present = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while present:
            image = entry.szExeFile.lower()
            if entry.th32ParentProcessID == runner_pid and image == "node.exe":
                drivers.add(entry.th32ProcessID)
            if image in {"chrome.exe", "chromium.exe", "headless_shell.exe", "chrome-headless-shell.exe"}:
                browsers[entry.th32ProcessID] = (entry.th32ParentProcessID, image)
            present = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES 表示完整快照已读完。
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(snapshot)
    owned = [(pid, parent, image) for pid, (parent, image) in browsers.items() if parent in drivers]
    if len(owned) != 1:
        raise RuntimeError("E_VISIBLE_WINDOW_NOT_OBSERVED: no unique runner-owned browser")
    return owned[0]


def read_owned_window(runner_pid, page_title):
    browser_pid, driver_pid, image = _owned_browser(runner_pid)
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowExW.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.IsWindowVisible.argtypes = user.IsIconic.argtypes = [wintypes.HWND]
    matches = []
    window = None
    while window := user.FindWindowExW(None, window, "Chrome_WidgetWin_1", None):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(window, ctypes.byref(pid))
        if pid.value != browser_pid or not user.IsWindowVisible(window) or user.IsIconic(window):
            continue  # 只对本次浏览器的可见顶层窗口读取标题。
        title = ctypes.create_unicode_buffer(1024)
        if not user.GetWindowTextW(window, title, len(title)):
            continue
        if page_title and (title.value == page_title or title.value.startswith(page_title + " - ")):
            matches.append({"Id": browser_pid, "ProcessName": Path(image).stem,
                            "MainWindowHandle": {"value": window}, "MainWindowTitle": title.value})
    if len(matches) != 1:
        raise RuntimeError("E_VISIBLE_WINDOW_NOT_OBSERVED: no unique visible page window")
    return {"headless": False, "exit_code": 0, "runner_pid": runner_pid,
            "driver_pid": driver_pid, "windows": matches[0]}


def observe_window(page):
    browser = page.context.browser
    if browser is None or [p for ctx in browser.contexts for p in ctx.pages] != [page]:
        raise RuntimeError("E_VISIBLE_WINDOW_NOT_OBSERVED: ambiguous local page")
    title = page.locator("title").first.text_content(timeout=2000)  # 不改动网页标题或置前其他窗口。
    try:
        completed = subprocess.run([sys.executable, "-I", "-S", str(Path(__file__).resolve())],
                                   input=json.dumps(title), capture_output=True, text=True, encoding="utf-8",
                                   timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("E_VISIBLE_WINDOW_NOT_OBSERVED: native observer timed out") from exc
    if completed.returncode:
        raise RuntimeError("E_VISIBLE_WINDOW_NOT_OBSERVED: " + completed.stdout.strip())
    return json.loads(completed.stdout)


if __name__ == "__main__":
    try:
        observation = read_owned_window(os.getppid(), json.load(sys.stdin))
    except (OSError, RuntimeError) as exc:
        print(str(exc))
        sys.exit(1)
    print(json.dumps(observation))
