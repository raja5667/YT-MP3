import os
import sys
import logging
import subprocess
import threading
import time
import urllib.request
import urllib.error
import json
import pathlib

# ===== VLC Setup (must happen before importing vlc) =====
if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

vlc_path     = os.path.join(base_path, "vlc")
plugins_path = os.path.join(vlc_path, "plugins")

os.environ["PYTHON_VLC_LIB_PATH"]    = os.path.join(vlc_path, "libvlc.dll")
os.environ["PYTHON_VLC_MODULE_PATH"] = plugins_path
os.environ["VLC_PLUGIN_PATH"]        = plugins_path

if hasattr(os, "add_dll_directory") and os.path.isdir(vlc_path):
    os.add_dll_directory(vlc_path)
# ========================================================

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

# Import both windows (VLC setup already done above)
from youtube_to_mp3_pro import AppWindow as MP3Window, resource_path, ICON_PATH
from youtube_to_mp4_pro  import VideoAppWindow as MP4Window

# ── App version ──────────────────────────────────────────────────────────────
APP_VERSION      = "v2.0.1"
GITHUB_API_URL   = "https://api.github.com/repos/raja5667/YT-MP3/releases/latest"
DOWNLOAD_PAGE    = "https://www.youtubemp3proh.dpdns.org/download.html"
GITHUB_REPO_URL  = "https://github.com/raja5667/YT-MP3"

# TODO: replace with your real Firebase Realtime Database URL once created
# (Firebase console -> Build -> Realtime Database -> copy the URL shown at
# the top, looks like "https://ytmp3-pro-xxxxx-default-rtdb.firebaseio.com").
# Must match the RATINGS_DB_URL used in download.js on the website exactly.
RATINGS_DB_URL   = "https://ytmp3-pro-default-rtdb.asia-southeast1.firebasedatabase.app"
# ─────────────────────────────────────────────────────────────────────────────


def _submit_rating_async(stars: int):
    """
    Fire-and-forget POST of the star rating to Firebase Realtime Database.

    Runs on a background thread so a slow or offline connection never blocks
    the rating dialog from closing. Any failure (no internet, DNS lookup
    failure, Firebase down) is silently swallowed -- losing one submission
    isn't worth interrupting the user over, and there's nothing useful to
    show them if it fails anyway.
    """
    def _send():
        try:
            payload = json.dumps({"stars": stars, "ts": int(time.time())}).encode("utf-8")
            req = urllib.request.Request(
                f"{RATINGS_DB_URL}/ratings.json",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # offline or Firebase unreachable -- drop silently

    threading.Thread(target=_send, daemon=True).start()

TAB_ACTIVE = """
    QPushButton {
        background: transparent;
        color: white; font-size: 13px; font-weight: 600;
        border: none; border-bottom: 2px solid #4285F4;
        border-radius: 0px; padding: 0px 20px;
    }
"""
TAB_INACTIVE = """
    QPushButton {
        background: transparent;
        color: rgba(255,255,255,0.38); font-size: 13px; font-weight: 500;
        border: none; border-bottom: 2px solid transparent;
        border-radius: 0px; padding: 0px 20px;
    }
    QPushButton:hover { color: rgba(255,255,255,0.75); border-bottom: 2px solid rgba(255,255,255,0.18); }
"""

TAB_BAR_H  = 42
MP3_H      = 500
MP4_H      = 500


# ── yt-dlp auto-updater ──────────────────────────────────────────────────────
class YtdlpUpdater(QtCore.QThread):
    finished = QtCore.pyqtSignal(str)

    def run(self):
        try:
            if getattr(sys, "frozen", False):
                exe = os.path.join(os.path.dirname(sys.executable), "yt-dlp.exe")
            else:
                exe = "yt-dlp"

            result = subprocess.run(
                [exe, "-U"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            output = (result.stdout + result.stderr).strip()

            if "up to date" in output.lower():
                self.finished.emit("")
            elif result.returncode == 0:
                self.finished.emit("yt-dlp updated ✓")
            else:
                self.finished.emit("")
        except Exception:
            self.finished.emit("")
# ─────────────────────────────────────────────────────────────────────────────


# ── App update checker ───────────────────────────────────────────────────────
class AppUpdateChecker(QtCore.QThread):
    """Checks GitHub releases API for a newer version. Emits (latest_version, download_url)
    if an update is found, or ("", "") if already up to date or no internet."""

    update_available = QtCore.pyqtSignal(str, str)  # (latest_version, exe_download_url)

    def run(self):
        try:
            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={"User-Agent": "YTMP3-Pro-App"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            latest_tag = data.get("tag_name", "")
            if not latest_tag:
                return

            # Find the .exe asset download URL
            exe_url = ""
            for asset in data.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    exe_url = asset.get("browser_download_url", "")
                    break

            # Compare versions — emit only if newer
            def parse(v):
                return [int(x) for x in v.lstrip("v").split(".")]

            if parse(latest_tag) > parse(APP_VERSION):
                self.update_available.emit(latest_tag, exe_url)

        except Exception:
            pass  # No internet or API error — silent
# ─────────────────────────────────────────────────────────────────────────────


# ── Download worker ──────────────────────────────────────────────────────────
class DownloadWorker(QtCore.QThread):
    """Downloads the new .exe to the user's Downloads folder."""

    progress   = QtCore.pyqtSignal(int)   # 0-100
    finished   = QtCore.pyqtSignal(str)   # save path on success
    error      = QtCore.pyqtSignal(str)   # error message on failure

    def __init__(self, url: str, save_path: str):
        super().__init__()
        self.url       = url
        self.save_path = save_path

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "YTMP3-Pro-App"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536  # 64 KB chunks

                with open(self.save_path, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self.progress.emit(int(downloaded / total * 100))

            self.finished.emit(self.save_path)
        except Exception as e:
            self.error.emit(str(e))
# ─────────────────────────────────────────────────────────────────────────────


# ── Update dialog ────────────────────────────────────────────────────────────
class UpdateDialog(QtWidgets.QDialog):
    def __init__(self, latest_version: str, exe_url: str, parent=None):
        super().__init__(parent)
        self.latest_version = latest_version
        self.exe_url        = exe_url
        self._worker        = None

        self.setWindowTitle("Update Available")
        self.setFixedWidth(420)
        self.setStyleSheet("""
            QDialog { background: #0f1117; color: white; }
            QLabel  { color: white; }
            QPushButton {
                background: #4285F4; color: white; border: none;
                border-radius: 6px; padding: 9px 22px;
                font-size: 13px; font-weight: 600;
            }
            QPushButton:hover   { background: #5a9cf5; }
            QPushButton:disabled { background: #2a3a5c; color: #6b7a99; }
            QPushButton#btnSkip {
                background: transparent; color: rgba(255,255,255,0.45);
                border: 1px solid rgba(255,255,255,0.15);
            }
            QPushButton#btnSkip:hover { color: white; border-color: rgba(255,255,255,0.4); }
            QProgressBar {
                background: #1e2130; border: none; border-radius: 4px; height: 6px;
            }
            QProgressBar::chunk { background: #4285F4; border-radius: 4px; }
        """)

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(14)

        # Icon + title row
        title_row = QtWidgets.QHBoxLayout()
        icon_lbl = QtWidgets.QLabel("🚀")
        icon_lbl.setStyleSheet("font-size: 28px;")
        title_lbl = QtWidgets.QLabel("New Update Available!")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
        title_row.addWidget(icon_lbl)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Version info
        ver_lbl = QtWidgets.QLabel(
            f"<span style='color:rgba(255,255,255,0.5)'>Current version:</span> "
            f"<b>{APP_VERSION}</b>&nbsp;&nbsp;"
            f"<span style='color:rgba(255,255,255,0.5)'>New version:</span> "
            f"<b style='color:#4ade80'>{self.latest_version}</b>"
        )
        ver_lbl.setTextFormat(Qt.TextFormat.RichText)
        ver_lbl.setStyleSheet("font-size: 12px;")
        layout.addWidget(ver_lbl)

        # Info text
        info = QtWidgets.QLabel(
            "A new version is ready. Click <b>Download Update</b> to save it "
            "to your Downloads folder, then replace the old YTMP3-Pro.exe with the new one."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.65); line-height: 1.5;")
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)

        # Progress bar (hidden until download starts)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_lbl = QtWidgets.QLabel("")
        self.status_lbl.setStyleSheet("font-size: 11px; color: rgba(255,255,255,0.5);")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)

        layout.addSpacing(4)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_skip = QtWidgets.QPushButton("Later")
        self.btn_skip.setObjectName("btnSkip")
        self.btn_skip.clicked.connect(self.reject)

        self.btn_download = QtWidgets.QPushButton("Download Update")
        self.btn_download.clicked.connect(self._start_download)

        btn_row.addWidget(self.btn_skip)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_download)
        layout.addLayout(btn_row)

    def _start_download(self):
        # If no direct exe URL, fall back to website
        if not self.exe_url:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(DOWNLOAD_PAGE))
            self.accept()
            return

        # Save to Downloads folder
        downloads = pathlib.Path.home() / "Downloads"
        downloads.mkdir(exist_ok=True)
        exe_name  = f"YTMP3-Pro-{self.latest_version}.exe"
        save_path = str(downloads / exe_name)

        self.btn_download.setEnabled(False)
        self.btn_download.setText("Downloading…")
        self.btn_skip.setEnabled(False)
        self.progress_bar.show()
        self.status_lbl.show()
        self.status_lbl.setText("Starting download…")

        self._worker = DownloadWorker(self.exe_url, save_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, pct: int):
        self.progress_bar.setValue(pct)
        self.status_lbl.setText(f"Downloading… {pct}%")

    def _on_finished(self, save_path: str):
        self.progress_bar.setValue(100)
        self.status_lbl.setText("")

        # Show success message
        QtWidgets.QMessageBox.information(
            self,
            "Download Complete",
            f"✅  New version saved to:\n{save_path}\n\n"
            f"Close YTMP3-Pro and replace the old .exe with this new file to complete the update."
        )
        self.accept()

    def _on_error(self, err: str):
        self.btn_download.setEnabled(True)
        self.btn_download.setText("Download Update")
        self.btn_skip.setEnabled(True)
        self.progress_bar.hide()
        self.status_lbl.hide()
        # Fall back to website on error
        QtWidgets.QMessageBox.warning(
            self, "Download Failed",
            f"Could not download the update automatically.\n\nOpening your browser to the download page instead."
        )
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(DOWNLOAD_PAGE))
# ─────────────────────────────────────────────────────────────────────────────


# ── Rating prompt: persistence + UI ──────────────────────────────────────────
class RatingManager:
    """
    Tracks how many successful downloads a user has made (persisted across app
    restarts via QSettings — on Windows this lives in the registry, so it
    survives even for a onefile PyInstaller exe with no writable install folder).

    Rules:
      - Every successful (non-cancelled) MP3 or MP4 download counts toward the total.
      - Counts accumulate across separate app sessions (open app, download 2,
        close, reopen later, download 3 more -> total is 5 -> prompt fires).
      - If the user taps "Maybe Later", the prompt is pushed back by
        RE_PROMPT_INTERVAL more downloads instead of disappearing forever.
      - Once the user gives ANY rating (1-5 stars), we never ask again.
    """

    ORG  = "YTMP3Pro"
    APP  = "YTMP3Pro"
    INITIAL_THRESHOLD  = 5   # ask after this many downloads, first time
    RE_PROMPT_INTERVAL = 5   # if they say "later", ask again after this many more

    def __init__(self):
        self.settings = QtCore.QSettings(self.ORG, self.APP)

    def has_rated(self) -> bool:
        return bool(self.settings.value("rating_given", False, type=bool))

    def record_download(self) -> bool:
        """
        Call this once per successful download. Returns True if the rating
        dialog should be shown right now.
        """
        if self.has_rated():
            return False

        count = self.settings.value("download_count", 0, type=int) + 1
        self.settings.setValue("download_count", count)

        next_prompt_at = self.settings.value(
            "next_prompt_at", self.INITIAL_THRESHOLD, type=int
        )
        self.settings.sync()

        return count >= next_prompt_at

    def mark_rated(self):
        self.settings.setValue("rating_given", True)
        self.settings.sync()

    def remind_later(self):
        """Push the next prompt out by RE_PROMPT_INTERVAL more downloads."""
        count = self.settings.value("download_count", 0, type=int)
        self.settings.setValue("next_prompt_at", count + self.RE_PROMPT_INTERVAL)
        self.settings.sync()


class StarRatingWidget(QtWidgets.QWidget):
    """Row of 5 clickable stars with hover fill preview."""

    rated = QtCore.pyqtSignal(int)  # 1-5

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._buttons = []
        for i in range(1, 6):
            btn = QtWidgets.QPushButton("★")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(42, 42)
            btn.setStyleSheet(self._style(False))
            btn.installEventFilter(self)
            btn.clicked.connect(lambda _checked, n=i: self.rated.emit(n))
            layout.addWidget(btn)
            self._buttons.append(btn)

    def _style(self, filled: bool) -> str:
        color = "#facc15" if filled else "rgba(255,255,255,0.25)"
        return (
            f"QPushButton {{ background: transparent; border: none; "
            f"font-size: 28px; color: {color}; }}"
        )

    def _fill_up_to(self, n: int):
        for i, btn in enumerate(self._buttons, start=1):
            btn.setStyleSheet(self._style(i <= n))

    def eventFilter(self, obj, event):
        if obj in self._buttons:
            idx = self._buttons.index(obj) + 1
            if event.type() == QtCore.QEvent.Type.Enter:
                self._fill_up_to(idx)
            elif event.type() == QtCore.QEvent.Type.Leave:
                self._fill_up_to(0)
        return super().eventFilter(obj, event)


class RatingDialog(QtWidgets.QDialog):
    """
    Rating prompt with a normal close button + a 'Maybe Later' option.
    Tapping any star records the rating (so it never shows again) and opens
    the GitHub repo so the user can drop a star there too. Closing without
    rating (X button, Escape, or 'Maybe Later') just postpones the next ask.
    """

    def __init__(self, rating_manager: "RatingManager", parent=None):
        super().__init__(parent)
        self.rating_manager = rating_manager
        self._rated = False

        self.setWindowTitle("Rate YTMP3 Pro")
        self.setFixedWidth(380)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background: #0f1117; color: white; }
            QLabel  { color: white; }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 20)
        layout.setSpacing(16)

        icon_lbl = QtWidgets.QLabel("⭐")
        icon_lbl.setStyleSheet("font-size: 32px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        title_lbl = QtWidgets.QLabel("Enjoying YTMP3 Pro?")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        msg_lbl = QtWidgets.QLabel(
            "You've downloaded several files with YTMP3 Pro!\nPlease tap a star to rate the app."
        )
        msg_lbl.setStyleSheet("font-size: 12.5px; color: rgba(255,255,255,0.65);")
        msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        self.stars = StarRatingWidget()
        stars_row = QtWidgets.QHBoxLayout()
        stars_row.addStretch()
        stars_row.addWidget(self.stars)
        stars_row.addStretch()
        layout.addLayout(stars_row)

        self.stars.rated.connect(self._on_rated)

        self.btn_later = QtWidgets.QPushButton("Maybe Later")
        self.btn_later.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_later.setStyleSheet("""
            QPushButton {
                background: transparent; color: rgba(255,255,255,0.45);
                border: none; font-size: 12px; padding: 6px;
            }
            QPushButton:hover { color: white; }
        """)
        self.btn_later.clicked.connect(self.close)
        layout.addWidget(self.btn_later, alignment=Qt.AlignmentFlag.AlignCenter)

    def _on_rated(self, stars: int):
        self._rated = True
        self.rating_manager.mark_rated()
        _submit_rating_async(stars)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(GITHUB_REPO_URL))
        self.accept()

    def closeEvent(self, event):
        # Any way of dismissing without rating (X, Escape, Maybe Later) -> postpone, don't block.
        if not self._rated:
            self.rating_manager.remind_later()
        event.accept()
# ─────────────────────────────────────────────────────────────────────────────


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YTMP3 Pro")
        self.setStyleSheet("QWidget { background-color: #0f1117; color: white; }")

        try:
            if os.path.exists(ICON_PATH):
                self.setWindowIcon(QtGui.QIcon(ICON_PATH))
        except Exception:
            pass

        self._current_tab = 0
        self._build_ui()
        self._switch_to(0)

        # Kick off yt-dlp auto-update in background
        self._updater = YtdlpUpdater()
        self._updater.finished.connect(self._on_ytdlp_updated)
        self._updater.start()

        # Kick off app update check in background
        self._app_checker = AppUpdateChecker()
        self._app_checker.update_available.connect(self._on_update_available)
        self._app_checker.start()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Tab bar ──────────────────────────────────────────
        tab_bar = QtWidgets.QWidget()
        tab_bar.setFixedHeight(TAB_BAR_H)
        tab_bar.setStyleSheet(
            "background: #0a0c12; border-bottom: 1px solid rgba(255,255,255,0.08);"
        )

        tab_layout = QtWidgets.QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(24, 0, 24, 0)
        tab_layout.setSpacing(0)

        self.btn_mp3 = QtWidgets.QPushButton("MP3 Downloader")
        self.btn_mp4 = QtWidgets.QPushButton("MP4 Downloader")

        for btn in (self.btn_mp3, self.btn_mp4):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(TAB_BAR_H)

        self.btn_mp3.clicked.connect(lambda: self._switch_to(0))
        self.btn_mp4.clicked.connect(lambda: self._switch_to(1))

        tab_layout.addWidget(self.btn_mp3)
        tab_layout.addWidget(self.btn_mp4)
        tab_layout.addStretch()

        # Status label — yt-dlp updated / app update available
        self._status_lbl = QtWidgets.QLabel("")
        self._status_lbl.setStyleSheet(
            "font-size: 11px; padding-right: 8px; cursor: pointer;"
        )
        self._status_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        tab_layout.addWidget(self._status_lbl)

        ver_lbl = QtWidgets.QLabel(APP_VERSION)
        ver_lbl.setStyleSheet("color: rgba(255,255,255,0.25); font-size: 11px; padding-right: 12px;")
        tab_layout.addWidget(ver_lbl)

        root.addWidget(tab_bar)

        # ── Stacked pages ─────────────────────────────────────
        self.stack = QtWidgets.QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)

        self.mp3_window = MP3Window()
        self.mp4_window = MP4Window()

        self.stack.addWidget(self.mp3_window)
        self.stack.addWidget(self.mp4_window)

        root.addWidget(self.stack)

        # ── Rating prompt wiring ───────────────────────────────
        self.rating_manager = RatingManager()
        self.mp3_window.download_succeeded.connect(self._on_download_succeeded)
        self.mp4_window.download_succeeded.connect(self._on_download_succeeded)

    def _on_download_succeeded(self):
        """Called after every successful MP3 or MP4 download."""
        should_prompt = self.rating_manager.record_download()
        if should_prompt:
            # Small delay so the "Done" status message is visible before the popup steals focus.
            QtCore.QTimer.singleShot(600, self._show_rating_dialog)

    def _show_rating_dialog(self):
        dlg = RatingDialog(self.rating_manager, parent=self)
        dlg.exec()

    def _on_ytdlp_updated(self, msg: str):
        if msg:
            self._status_lbl.setStyleSheet("color: #4ade80; font-size: 11px; padding-right: 8px;")
            self._status_lbl.setText(msg)
            QtCore.QTimer.singleShot(4000, lambda: self._status_lbl.setText(""))

    def _on_update_available(self, latest_version: str, exe_url: str):
        """Show a clickable 'Update available' badge in the tab bar."""
        self._pending_version = latest_version
        self._pending_exe_url = exe_url

        self._status_lbl.setStyleSheet(
            "color: #facc15; font-size: 11px; padding-right: 8px; "
            "text-decoration: underline;"
        )
        self._status_lbl.setText(f"Update available: {latest_version}")
        self._status_lbl.mousePressEvent = lambda _: self._show_update_dialog()

    def _show_update_dialog(self):
        dlg = UpdateDialog(self._pending_version, self._pending_exe_url, parent=self)
        dlg.exec()

    def _switch_to(self, index: int):
        self._current_tab = index
        self.stack.setCurrentIndex(index)

        if index == 0:
            self.btn_mp3.setStyleSheet(TAB_ACTIVE)
            self.btn_mp4.setStyleSheet(TAB_INACTIVE)
            self.setWindowTitle("YouTube to MP3 Pro")
            self.setFixedSize(850, MP3_H + TAB_BAR_H)
        else:
            self.btn_mp3.setStyleSheet(TAB_INACTIVE)
            self.btn_mp4.setStyleSheet(TAB_ACTIVE)
            self.setWindowTitle("YouTube to MP4 Pro")
            self.setFixedSize(850, MP4_H + TAB_BAR_H)

    def closeEvent(self, event):
        self.mp3_window.closeEvent(event)
        self.mp4_window.closeEvent(event)
        event.accept()


def main():
    is_frozen = getattr(sys, "frozen", False)

    if not is_frozen:
        logging.basicConfig(
            filename="youtube_to_mp3.log",
            filemode="a",
            format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=logging.ERROR,
        )
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
        logging.getLogger().addHandler(console)
        print("Logging initialized.")
    else:
        logging.getLogger().addHandler(logging.NullHandler())

    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(ICON_PATH))
    app.setFont(QtGui.QFont("Segoe UI", 10))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()