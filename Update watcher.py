"""
update_watcher.py — YTMP3 Pro background update watcher.

A tiny, standalone process (built as its own .exe, separate from the main
YTMP3 Pro app) that:
  1. Runs quietly at Windows login (registered via the registry Run key).
  2. Wakes up periodically and checks the GitHub Releases API.
  3. Shows a native Windows toast notification if a newer version exists,
     even if the main YTMP3 Pro app is closed.

Build this as its own PyInstaller .exe (see build_updater.bat below) and
ship it next to YTMP3-Pro.exe in the same folder. Main.py registers it to
autostart on first launch (see register_startup() added to main.py).

Dependencies:
    pip install win11toast
"""

import sys
import os
import json
import time
import ctypes
import urllib.request

# win11toast wraps the native Windows Runtime toast API — works on Win10/11.
try:
    from win11toast import toast
except Exception:
    toast = None  # graceful no-op on non-Windows / missing dependency


APP_NAME       = "YTMP3 Pro"
GITHUB_API_URL = "https://api.github.com/repos/raja5667/YT-MP3/releases/latest"
DOWNLOAD_PAGE  = "https://www.youtubemp3proh.dpdns.org/download.html"
CHECK_INTERVAL = 6 * 60 * 60  # seconds between checks (6 hours)
MUTEX_NAME     = "YTMP3ProUpdateWatcherMutex"

DATA_DIR        = os.path.join(os.getenv("LOCALAPPDATA", "."), "YTMP3Pro")
INSTALLED_FILE  = os.path.join(DATA_DIR, "installed_version.txt")   # written by main.py on launch
NOTIFIED_FILE   = os.path.join(DATA_DIR, "last_notified.txt")       # written by this watcher


# ── Single instance guard ────────────────────────────────────────────────────
def _ensure_single_instance():
    """Exit immediately if another copy of the watcher is already running."""
    if sys.platform != "win32":
        return None
    ERROR_ALREADY_EXISTS = 183
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        sys.exit(0)
    return mutex  # must stay referenced for the life of the process


# ── Version helpers ───────────────────────────────────────────────────────────
def _read(path, default=""):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return default


def _write(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(value)


def _parse(v):
    return [int(x) for x in v.lstrip("v").split(".")]


# ── Core check ────────────────────────────────────────────────────────────────
def check_for_update():
    try:
        req = urllib.request.Request(
            GITHUB_API_URL, headers={"User-Agent": "YTMP3-Pro-Updater"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        latest_tag = data.get("tag_name", "")
        if not latest_tag:
            return

        installed = _read(INSTALLED_FILE, default="v0.0.0")
        already_notified = _read(NOTIFIED_FILE, default="")

        # Newer than what's installed, and we haven't already pinged for this tag.
        if _parse(latest_tag) > _parse(installed) and latest_tag != already_notified:
            _show_toast(latest_tag)
            _write(NOTIFIED_FILE, latest_tag)

    except Exception:
        pass  # no internet / API hiccup — stay silent, try again next cycle


def _show_toast(latest_tag):
    if toast is None:
        return
    try:
        toast(
            f"{APP_NAME} update available",
            f"Version {latest_tag} is ready to download.",
            on_click=DOWNLOAD_PAGE,
            buttons=[{"activationType": "protocol", "content": "Download now", "arguments": DOWNLOAD_PAGE}],
        )
    except Exception:
        pass


def main():
    if sys.platform != "win32":
        return
    _ensure_single_instance()
    while True:
        check_for_update()
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()