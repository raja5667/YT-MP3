import os
import sys
import shutil
import traceback
from pathlib import Path
from yt_dlp import YoutubeDL
import socket

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QPainter, QBrush, QColor, QLinearGradient
from PyQt6.QtWidgets import QLabel

# ==========================
# CONFIG & CONSTANTS
# ==========================
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads"
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BITRATE_KBPS = 320
FFMPEG_CMD = "ffmpeg"
ICON_PATH = "/mnt/data/Gemini_Generated_Image_efbieefbieefbiee.jpg"
# Added this constant back for completeness, even if the cropping PostProcessor is removed
SQUARE_THUMBNAIL_SIZE = 500 

# ==========================
# UTILITY FUNCTIONS
# ==========================
def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed and accessible in the system's PATH."""
    return shutil.which(FFMPEG_CMD) is not None

def safe_mkdir(p: Path):
    """Safely create a directory."""
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

def check_internet(timeout=3) -> bool:
    """Return True if online, False if offline."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection(("8.8.8.8", 53))  # Google DNS
        return True
    except OSError:
        return False

# ==========================
# NEON FRAME WIDGET
# ==========================
class NeonFrame(QtWidgets.QFrame):
    """Custom QFrame with an animating, gradient border."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(770, 54)
        self.setLineWidth(3)
        self.setMidLineWidth(0)
        self.setFrameShape(QtWidgets.QFrame.Shape.Box)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        self.setStyleSheet("border-radius: 27px; background: transparent;")
        
        self._border_offset = 0.0
        self.border_anim = QPropertyAnimation(self, b"border_offset")
        self.border_anim.setDuration(3000)
        self.border_anim.setStartValue(0.0)
        self.border_anim.setEndValue(1.0)
        self.border_anim.setLoopCount(-1)
        self.border_anim.start()

    def set_border_offset(self, offset: float):
        self._border_offset = offset
        self.update()

    def get_border_offset(self) -> float:
        return self._border_offset

    border_offset = pyqtProperty(float, get_border_offset, set_border_offset)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bg_rect = self.rect().adjusted(1, 1, -1, -1)
        bg_color = QColor(255, 255, 255, int(255 * 0.02))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(bg_rect, 27, 27)

        offset = self._border_offset
        stops = [
            (0.0 + offset) % 1.0, QColor("#4285F4"),
            (0.3 + offset) % 1.0, QColor("#EA4335"),
            (0.7 + offset) % 1.0, QColor("#FBBC05"),
            (1.0 + offset) % 1.0, QColor("#34A853"),
        ]
        gradient = QLinearGradient(0, 0, self.width(), 0)
        for i in range(0, len(stops), 2):
            stop_pos = stops[i]
            color = stops[i+1]
            gradient.setColorAt(stop_pos, color)
            
        pen = QtGui.QPen()
        pen.setWidth(3)
        pen.setBrush(gradient)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        border_rect = self.rect().adjusted(1, 1, -2, -2)
        painter.drawRoundedRect(border_rect, 27, 27)
        painter.end()

# ==========================
# DOWNLOAD WORKER THREAD
# ==========================
class DownloadWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(float)
    status = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    def __init__(self, url: str, output_dir: str):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self._stop = False
        self._ydl = None

    def run(self):
        try:
            opts = self._make_opts(self.output_dir)

            with YoutubeDL(opts) as ydl:
                self._ydl = ydl

                self.status.emit("Starting download...")

                if self._stop:
                    self.finished.emit("Cancelled")
                    return

                ydl.download([self.url])

                if not self._stop:
                    self.finished.emit("Done")

        except Exception as e:
            if self._stop:
                self.finished.emit("Cancelled")
            else:
                tb = traceback.format_exc()
                self.error.emit(f"An error occurred: {e}\n\n{tb}")

        finally:
            # Clean up on completion or error
            self.cleanup_partial_files(self.output_dir)

    def stop(self):
        """Stop download immediately using new yt-dlp API and manually clean up."""
        self._stop = True
        
        # Attempt to interrupt yt-dlp's network operations (may or may not work immediately)
        try:
            if self._ydl:
                try:
                    # This trick attempts to interrupt network threads
                    s = self._ydl.urlopen("http://0.0.0.0/")
                    s.close()
                except:
                    pass
        except:
            pass
        
        # Perform cleanup immediately on stop request
        self.cleanup_partial_files(self.output_dir)

    def cleanup_partial_files(self, folder):
        """Removes all temporary and partial files, including leftover thumbnails."""
        try:
            for f in os.listdir(folder):
                file_path = os.path.join(folder, f)

                # yt-dlp temp files and video/audio streams
                if f.endswith((".part", ".ytdl", ".temp", ".tmp", ".webm", ".mp4", ".m4a", ".wav")):
                    os.remove(file_path)
                
                # --- NEW: Explicitly remove downloaded thumbnail files ---
                elif f.endswith((".webp", ".jpg", ".jpeg", ".png")):
                    os.remove(file_path)
                # --------------------------------------------------------

                # incomplete mp3 (small files that failed conversion/embedding)
                elif f.endswith(".mp3"):
                    if os.path.getsize(file_path) < 200 * 1024:  # <200 KB
                        os.remove(file_path)

        except Exception:
            pass

    def _make_opts(self, output_dir):
        outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")
        def hook(d):
            if self._stop:
                raise Exception("Download cancelled by user.")
            status = d.get("status")
            if status == "downloading":
                downloaded = d.get("downloaded_bytes", 0) or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct = (downloaded / total * 100) if total else 0.0
                try:
                    pct_val = max(0.0, min(100.0, float(pct)))
                except Exception:
                    pct_val = 0.0
                self.progress.emit(pct_val)
                filename = d.get("filename") or ""
                short = os.path.basename(filename)
                self.status.emit(f"Downloading: {pct_val:5.1f}% — {short}")
            elif status == "finished":
                self.status.emit("Converting/Embedding...")
        
        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "noplaylist": False,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            
            # --- START: Options for Thumbnail Embedding ---
            "writethumbnail": True,  # 1. Download the thumbnail
            "embed_thumbnail": True, # 2. Indicate that we want to embed the thumbnail
            "keepvideo": False,      # Remove temporary video/audio files
            # --- END: Options for Thumbnail Embedding ---
            
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(BITRATE_KBPS),
                },
                {
                    "key": "EmbedThumbnail", # 3. The postprocessor that does the embedding
                },
            ],
            "retries": 3,
            "continuedl": True,
        }
        return opts

# ==========================
# MAIN APP WINDOW
# ==========================
class AppWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTubeToMP3 Pro H (Fixed Cleanup)")
        self.setFixedSize(850, 500)
        self.setStyleSheet("background-color: #202124;")
        
        try:
            if os.path.exists(ICON_PATH):
                self.setWindowIcon(QtGui.QIcon(ICON_PATH))
        except:
            pass
            
        self.output_dir = DEFAULT_OUTPUT_DIR
        safe_mkdir(self.output_dir)
        self.worker = None
        self._build_ui()
        self.setAcceptDrops(True)

    # ------------------------
    # BUILD UI
    # ------------------------
    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(40, 20, 40, 20)
        outer.setSpacing(12)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        title = QLabel(
            "<span style='font-size:40px; font-weight:600; letter-spacing:6px;'>"
            "<span style='color:#4285F4'>Y</span>"
            "<span style='color:#EA4335'>O</span>"
            "<span style='color:#FBBC05'>U</span>"
            "<span style='color:#34A853'>T</span>"
            "<span style='color:#4285F4'>U</span>"
            "<span style='color:#EA4335'>B</span>"
            "<span style='color:#FBBC05'>E</span>"
            "<span style='color:#34A853'>&nbsp;</span>"
            "<span style='color:#4285F4'>T</span>"
            "<span style='color:#EA4335'>O</span>"
            "<span style='color:#FBBC05'>M</span>"
            "<span style='color:#34A853'>P</span>"
            "<span style='color:#4285F4'>3</span>"
            "<span style='color:#EA4335'>&nbsp;</span>"
            "<span style='color:#FBBC05'>P</span>"
            "<span style='color:#34A853'>R</span>"
            "<span style='color:#4285F4'>O</span>"
            "<span style='color:#EA4335'>&nbsp;</span>"
            "<span style='color:#FBBC05'>H</span>"
            "</span>"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(title)
        outer.addSpacing(18)

        # Input Frame
        self.input_frame = NeonFrame()
        self.input_line = QtWidgets.QLineEdit()
        self.input_line.setPlaceholderText("Paste YouTube link or drag & drop here…")
        self.input_line.setFixedHeight(50)
        self.input_line.setStyleSheet("""
            QLineEdit {
                border: none;
                padding-left: 18px;
                font-size: 18px;
                color: #FFFFFF;
                background-color: transparent;
                border-radius: 25px;
            }
        """)
        f = QtWidgets.QHBoxLayout(self.input_frame)
        f.setContentsMargins(5,2,5,2)
        f.addWidget(self.input_line)
        outer.addWidget(self.input_frame)
        outer.addSpacing(6)

        # Download path
        path_row = QtWidgets.QHBoxLayout()
        lbl_path = QLabel("Download Path:")
        lbl_path.setStyleSheet("color:#BDC1C6; font-size:13px;")
        path_row.addWidget(lbl_path)
        self.lbl_path_value = QLabel(str(self.output_dir))
        self.lbl_path_value.setStyleSheet("color:#FFFFFF; font-size:13px;")
        path_row.addWidget(self.lbl_path_value)
        path_row.addStretch()
        self.btn_change = QtWidgets.QPushButton("Change")
        self.btn_change.setStyleSheet("""
            QPushButton {
                color: #4285F4; background: transparent; border:none;
                font-size:14px;
            }
            QPushButton:hover { color:#34A853; }
        """)
        self.btn_change.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_change.clicked.connect(self.change_path)
        path_row.addWidget(self.btn_change)
        outer.addLayout(path_row)
        outer.addSpacing(20)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        btn_row.setSpacing(22)
        self.btn_download = QtWidgets.QPushButton("Download MP3")
        self.btn_download.setFixedSize(220, 56)
        self.btn_download.setStyleSheet("""
            QPushButton {
                font-size:18px;
                border:2px solid transparent;
                border-radius:28px;
                padding:10px;
                color:white;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4285F4, stop:1 #EA4335
                );
            }
        """)
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self.start_download)
        btn_row.addWidget(self.btn_download)

        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.setFixedSize(180, 56)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                font-size:18px;
                border:2px solid #4285F4;
                color:#4285F4;
                border-radius:28px;
                padding:10px;
                background: transparent;
            }
            QPushButton:hover {
                background: rgba(66,133,244,40%);
                border:2px solid #34A853;
                color:#34A853;
            }
            QPushButton:pressed {
                background: rgba(52,168,83,60%);
                border:2px solid #0F9D58;
                color:#0F9D58;
            }
        """)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_download)
        btn_row.addWidget(self.btn_cancel)

        outer.addLayout(btn_row)

        # Status & Progress
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color:white; font-size:15px;")
        outer.addWidget(self.lbl_status)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0,100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(18)
        self.progress.setStyleSheet("""
            QProgressBar { background:#2e2f31; border-radius:9px; }
            QProgressBar::chunk {
                border-radius:9px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #34A853, stop:1 #4285F4
                );
            }
        """)
        outer.addWidget(self.progress)
        outer.addStretch()
        footer = QLabel("MP3 - 320kbps • Playlist Support • Drag & Drop Enabled")
        footer.setStyleSheet("color:#BDC1C6; font-size:13px;")
        outer.addWidget(footer)

    # ------------------------
    # BUTTON ACTIONS
    # ------------------------
    def change_path(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select download folder", str(self.output_dir)
        )
        if path:
            self.output_dir = Path(path)
            self.lbl_path_value.setText(str(self.output_dir))

    def start_download(self):
        if not check_ffmpeg():
            QtWidgets.QMessageBox.critical(self, "FFmpeg Missing", "Install FFmpeg and try again.")
            return

        if not check_internet():
            QtWidgets.QMessageBox.critical(self, "No Internet", "You are offline! Please check your connection.")
            self.lbl_status.setText("Offline")
            return

        url = self.input_line.text().strip()
        if not url:
            self.lbl_status.setText("Please paste a YouTube link.")
            return

        safe_mkdir(self.output_dir)
        self.worker = DownloadWorker(url, str(self.output_dir))
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self._on_status)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)

        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.lbl_status.setText("Queued")
        self.progress.setValue(0)
        self.worker.start()

    def cancel_download(self):
        if self.worker and self.worker.isRunning():
            try:
                self.worker.stop()
                # Wait briefly for the cleanup to potentially finish
                self.worker.wait(500) 
            except:
                pass
        self.lbl_status.setText("Cancelled")
        self.progress.setValue(0)
        self.input_line.clear()
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QtCore.QTimer.singleShot(5000, self.reset_ui)

    # ------------------------
    # SIGNAL HANDLERS
    # ------------------------
    def _on_progress(self, pct):
        self.progress.setValue(int(pct))

    def _on_status(self, msg):
        self.lbl_status.setText(msg)

    def _on_finished(self, msg):
        self.progress.setValue(100)
        self.lbl_status.setText(msg)
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QtCore.QTimer.singleShot(10000, self.reset_ui)

    def _on_error(self, err):
        if "Download cancelled by user" not in err:
            QtWidgets.QMessageBox.critical(self, "Error", err)
        self.lbl_status.setText("Error")
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    def reset_ui(self):
        self.input_line.clear()
        self.progress.setValue(0)
        self.lbl_status.setText("Ready")

    # ------------------------
    # DRAG & DROP
    # ------------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            url = e.mimeData().urls()[0].toString()
            self.input_line.setText(url)
        elif e.mimeData().hasText():
            self.input_line.setText(e.mimeData().text())

# ==========================
# MAIN
# ==========================
def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Segoe UI", 10))
    win = AppWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()