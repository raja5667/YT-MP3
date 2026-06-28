import os
import sys
import logging

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
MP3_H      = 500   # fixed height of MP3 window
MP4_H      = 500   # MP4 window height (matches MP3 window)


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
        self._switch_to(0)  # start on MP3 tab

        # No resize needed — MP4 trim panel is always visible

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
        root.addWidget(tab_bar)

        # ── Stacked pages ─────────────────────────────────────
        self.stack = QtWidgets.QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)

        self.mp3_window = MP3Window()
        self.mp4_window = MP4Window()

        self.stack.addWidget(self.mp3_window)  # index 0
        self.stack.addWidget(self.mp4_window)  # index 1

        root.addWidget(self.stack)

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