import os
import sys
import shutil
import traceback
from pathlib import Path
from yt_dlp import YoutubeDL

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QLineF, QObject, pyqtProperty
from PyQt6.QtGui import QPainter, QBrush, QColor, QPalette, QLinearGradient
from PyQt6.QtWidgets import QWidget, QLabel, QStyle

# ---------------------- Configuration ----------------------
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads"
# Create folder if missing
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BITRATE_KBPS = 320
FFMPEG_CMD = "ffmpeg"
# Note: ICON_PATH is likely a placeholder path that doesn't exist on all systems.
ICON_PATH = "/mnt/data/Gemini_Generated_Image_efbieefbieefbiee.jpg" 

# ---------------------- Utilities ----------------------
def check_ffmpeg() -> bool:
    """Checks if the FFmpeg command is available in the system PATH."""
    return shutil.which(FFMPEG_CMD) is not None

def safe_mkdir(p: Path):
    """Safely creates a directory path."""
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

# ---------------------- Custom Widgets for Efficiency ----------------------

class NeonFrame(QtWidgets.QFrame):
    """
    Custom QFrame to handle the neon border animation efficiently using QPainter 
    and QPropertyAnimation on a custom property, avoiding constant stylesheet updates.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(770, 54) # Match original input frame size
        self.setLineWidth(3)
        self.setMidLineWidth(0)
        self.setFrameShape(QtWidgets.QFrame.Shape.Box)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        self.setStyleSheet("border-radius: 27px; background: transparent;")
        
        self._border_offset = 0.0
        self.border_anim = QPropertyAnimation(self, b"border_offset")
        self.border_anim.setDuration(3000) # 3 seconds per cycle
        self.border_anim.setStartValue(0.0)
        self.border_anim.setEndValue(1.0)
        self.border_anim.setLoopCount(-1)
        self.border_anim.start()

    def set_border_offset(self, offset: float):
        """Setter for the 'border_offset' custom property."""
        self._border_offset = offset
        self.update() # Request repaint

    def get_border_offset(self) -> float:
        """Getter for the 'border_offset' custom property."""
        return self._border_offset

    # Register the custom property
    border_offset = pyqtProperty(float, get_border_offset, set_border_offset)

    def paintEvent(self, event):
        """Custom drawing for the animated border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw the rounded background
        bg_rect = self.rect().adjusted(1, 1, -1, -1)
        bg_color = QColor(255, 255, 255, int(255 * 0.02)) # Original rgba(255,255,255,0.02)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(bg_rect, 27, 27)

        # Draw the neon border
        offset = self._border_offset
        
        # Gradient stops for the sweep effect
        # The offset shifts the entire stop list
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
            # Map the 0.0 to 1.0 offset to actual gradient positions
            gradient.setColorAt(stop_pos, color)

        # Create the pen for the border
        pen = QtGui.QPen()
        pen.setWidth(3)
        pen.setBrush(gradient)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Draw the rounded rectangle border
        border_rect = self.rect().adjusted(1, 1, -2, -2)
        painter.drawRoundedRect(border_rect, 27, 27)
        
        painter.end()


# ---------------------- Downloader Thread ----------------------
# (DownloadWorker is correct and does not require changes)
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

    def run(self):
        try:
            opts = self._make_opts(self.output_dir)
            with YoutubeDL(opts) as ydl:
                self.status.emit("Starting download...")
                ydl.download([self.url])
                if not self._stop:
                    self.finished.emit("Done")
        except Exception as e:
            # Added a check for stop to prevent error on intentional cancellation
            if not self._stop:
                tb = traceback.format_exc()
                self.error.emit(f"An error occurred: {e}\n\n{tb}")

    def stop(self):
        self._stop = True

    def _make_opts(self, output_dir):
        outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")

        def hook(d):
            if self._stop:
                raise Exception("Download cancelled by user.") # Exit download gracefully
                
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
                self.status.emit("Converting to MP3...")

        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "noplaylist": False,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(BITRATE_KBPS),
            }],
            "retries": 3,
            "continuedl": True,
        }
        return opts


# ---------------------- Main Application UI ----------------------
class AppWindow(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTubeToMP3 Pro H (Static Dots)")
        self.setFixedSize(850, 500)
        self.setStyleSheet("background-color: #202124;")

        try:
            if os.path.exists(ICON_PATH):
                self.setWindowIcon(QtGui.QIcon(ICON_PATH))
        except:
            pass

        # Use an instance attribute instead of global
        self.output_dir = DEFAULT_OUTPUT_DIR
        safe_mkdir(self.output_dir)
        self.worker = None

        self._build_ui()
        self.setAcceptDrops(True) # Ensure drag and drop is enabled

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(40, 20, 40, 20)
        outer.setSpacing(12)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Title
        title = QtWidgets.QLabel()
        title_text = (
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
        title.setText(title_text)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(title)
        outer.addSpacing(18)

        # Input Frame (Now using the efficient NeonFrame)
        self.input_frame = NeonFrame() # Custom widget
        
        self.input_line = QtWidgets.QLineEdit()
        self.input_line.setPlaceholderText("Paste YouTube link or drag & drop here…")
        self.input_line.setFixedHeight(50)
        self.input_line.setStyleSheet("""
            QLineEdit {
                border: none;
                padding-left: 18px;
                font-size: 18px;
                color: #FFFFFF;
                background-color: transparent; /* No background in QLineEdit, let NeonFrame draw it */
                border-radius: 25px;
            }
        """)

        # Add input line to the custom frame's layout
        f = QtWidgets.QHBoxLayout(self.input_frame)
        f.setContentsMargins(5,2,5,2) # Adjusted margins to fit QLineEdit properly inside NeonFrame
        f.addWidget(self.input_line)
        outer.addWidget(self.input_frame)

        outer.addSpacing(6)

        # PATH ROW
        path_row = QtWidgets.QHBoxLayout()
        lbl_path = QtWidgets.QLabel("Download Path:")
        lbl_path.setStyleSheet("color:#BDC1C6; font-size:13px;")
        path_row.addWidget(lbl_path)

        self.lbl_path_value = QtWidgets.QLabel(str(self.output_dir))
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

        # --- Static 3 Dots (No change needed) ---
        dot_widget = QtWidgets.QWidget()
        dot_widget.setFixedSize(20, 19)
        dot_layout = QtWidgets.QGridLayout(dot_widget)
        dot_layout.setContentsMargins(0,0,0,0)
        dot_layout.setSpacing(0)

        dot_style = "font-size:7px; margin:0; padding:0;"

        dot1 = QLabel("⬤")
        dot1.setStyleSheet(f"color:#EA4335; {dot_style}")  # red
        dot1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot_layout.addWidget(dot1, 0, 1)  # top

        dot2 = QLabel("⬤")
        dot2.setStyleSheet(f"color:#34A853; {dot_style}")  # green
        dot2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot_layout.addWidget(dot2, 1, 0)  # bottom-left

        dot3 = QLabel("⬤")
        dot3.setStyleSheet(f"color:#FBBC05; {dot_style}")  # yellow
        dot3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot_layout.addWidget(dot3, 2, 1)  # bottom-right

        path_row.addWidget(dot_widget)
        outer.addLayout(path_row)
        outer.addSpacing(20)

        # Buttons Row
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        btn_row.setSpacing(22)

        self.btn_download = QtWidgets.QPushButton("Download MP3")
        self.btn_download.setFixedSize(220, 56)
        
        # NOTE: To create the "Gradient Flow" effect on the button, 
        # we need to animate the gradient stops themselves. The original
        # code's QPropertyAnimation on 'geometry' with identical start/end
        # values was incorrect. Here we fix the styling and remove the
        # incorrect animation logic. For a true gradient flow, a custom
        # widget like NeonFrame would be needed here too, but for simplicity
        # we'll keep the static style and remove the broken animation.
        self.btn_download.setStyleSheet("""
            QPushButton {
                font-size:18px; font-weight:600; color:white;
                border:2px solid white;
                border-radius:28px;
                /* Static gradient for a professional look */
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4285F4, stop:0.45 #FF7043,
                    stop:0.75 #FBBC05, stop:1 #EA4335
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
                border: 2px solid #4285F4;
                color:#4285F4;
                font-size:18px;
                border-radius:28px;
                background: transparent;                   
            }
        """)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_download)
        btn_row.addWidget(self.btn_cancel)

        outer.addLayout(btn_row)

        # Status & Progress
        self.lbl_status = QtWidgets.QLabel("Ready")
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

        footer = QtWidgets.QLabel("MP3 - 320kbps • Playlist Support • Drag & Drop Enabled")
        footer.setStyleSheet("color:#BDC1C6; font-size:13px;")
        outer.addWidget(footer)

    # Removed the inefficient update_neon_border method and eventFilter
    # The animation is now handled by the NeonFrame widget's QPropertyAnimation

    # Logic
    def change_path(self):
        # Access instance attribute instead of global
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

        url = self.input_line.text().strip()
        if not url:
            self.lbl_status.setText("Please paste a YouTube link.")
            return

        safe_mkdir(self.output_dir)

        # Pass instance attribute
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
                # The worker's stop method is now used to signal cancellation 
                # which causes the run method to raise an exception and stop gracefully.
                self.worker.stop()
                self.worker.wait(1200) 
            except:
                pass
            self.lbl_status.setText("Cancelled")

        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)

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

    def reset_ui(self):
        self.input_line.clear()
        self.progress.setValue(0)
        self.lbl_status.setText("Ready")

    def _on_error(self, err):
        # Check if the error is due to intentional cancellation before showing a box
        if "Download cancelled by user" not in err:
            QtWidgets.QMessageBox.critical(self, "Error", err)
        
        self.lbl_status.setText("Error")
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    # Drag and Drop handlers
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            url = e.mimeData().urls()[0].toString()
            self.input_line.setText(url)
        elif e.mimeData().hasText():
            self.input_line.setText(e.mimeData().text())


# ---------------------- Entry Point ----------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Segoe UI", 10))
    win = AppWindow()
    win.show()
    # It is standard practice to use app.exec() for PyQt6
    sys.exit(app.exec())

if __name__ == "__main__":
    main()