import os
import sys
import traceback
import shutil
import re
from pathlib import Path
from yt_dlp import YoutubeDL
import socket
import logging
import subprocess
import vlc

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

YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.|m\.|music\.)?youtube\.com/'
    r'(watch\?v=|embed/|v/|shorts/|live/|playlist\?list=)'
    r'([a-zA-Z0-9_-]+)', re.IGNORECASE
)

YOUTU_BE_REGEX = re.compile(
    r'(https?://)?youtu\.be/([a-zA-Z0-9_-]+)', re.IGNORECASE
)

def is_valid_youtube_url(url: str) -> bool:
    """Returns True if the string matches any valid YouTube format."""
    url = url.strip()
    return bool(YOUTUBE_REGEX.match(url) or YOUTU_BE_REGEX.match(url))

def resolve_ffmpeg_path() -> str:
    """
    Cross-platform resolution for FFmpeg.
    1. Checks if 'ffmpeg' is available in the system PATH.
    2. Falls back to a local/bundled binary (handling OS-specific extensions).
    """
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    binary_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    
    if getattr(sys, "frozen", False):
        bundled_path = os.path.join(sys._MEIPASS, binary_name)
    else:
        bundled_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), binary_name)
        
    return bundled_path

FFMPEG_CMD = resolve_ffmpeg_path()
ICON_PATH = "/mnt/data/app_icon.ico"
SQUARE_THUMBNAIL_SIZE = 500 

# ==========================
# UTILITY FUNCTIONS
# ==========================
def check_ffmpeg() -> bool:
    """
    Robust verification that checks if ffmpeg is available globally in the system PATH
    or exists explicitly at the fallback path resolved during configuration setup.
    """
    return shutil.which("ffmpeg") is not None or os.path.exists(FFMPEG_CMD)

def safe_mkdir(p: Path):
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Failed to create directory {p}: {e}")

def check_internet(timeout=3) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection(("8.8.8.8", 53))
        return True
    except OSError:
        return False

# ==========================
# NEON FRAME WIDGET
# ==========================
class NeonFrame(QtWidgets.QFrame):
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

    def __init__(self, url: str, output_dir: str, boost_enabled=False, boost_value=100):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.boost_enabled = boost_enabled
        self.boost_value = boost_value
        self._stop = False
        self._ydl = None
        self.current_downloaded_files = set()
        
        self.current_index = 1
        self.total_tracks = 1

    def run(self):
        try:
            opts_meta = self._make_opts(self.output_dir)
            with YoutubeDL(opts_meta) as ydl:
                self._ydl = ydl
                self.status.emit("Extracting link metadata...")
                if self._stop:
                    self.finished.emit("Cancelled")
                    return
                
                info = ydl.extract_info(self.url, download=False)
                if not info:
                    raise Exception("Failed to extract video information.")

                if "entries" in info:
                    entries = list(info["entries"])
                    self.total_tracks = len(entries)
                    self.status.emit(f"Found playlist with {self.total_tracks} tracks. Starting...")
                    
                    for index, entry in enumerate(entries, start=1):
                        if self._stop:
                            self.finished.emit("Cancelled")
                            return
                        
                        if not entry:
                            continue
                            
                        self.current_index = index
                        track_url = entry.get("url") or entry.get("webpage_url")
                        if not track_url:
                            continue
                            
                        title = entry.get("title", f"Track_{index}")
                        for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
                            title = title.replace(char, "_")
                            
                        self.status.emit(f"[{index}/{self.total_tracks}] Processing: {title[:30]}...")
                        
                        track_opts = self._make_opts(self.output_dir)
                        with YoutubeDL(track_opts) as single_ydl:
                            if self._stop:
                                self.finished.emit("Cancelled")
                                return
                            single_ydl.download([track_url])
                        
                        final_mp3 = os.path.join(self.output_dir, f"{title}.mp3")
                        if self.boost_enabled and os.path.exists(final_mp3) and not self._stop:
                            self.status.emit(f"[{index}/{self.total_tracks}] Boosting Audio...")
                            self.boost_mp3_volume(final_mp3, self.boost_value)
                else:
                    self.total_tracks = 1
                    self.current_index = 1
                    
                    title = info.get("title", "audio")
                    for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
                        title = title.replace(char, "_")
                        
                    final_mp3 = os.path.join(self.output_dir, f"{title}.mp3")
                    self.status.emit("Starting download...")
                    
                    opts_dl = self._make_opts(self.output_dir)
                    with YoutubeDL(opts_dl) as single_ydl:
                        single_ydl.download([self.url])
    
                    if self.boost_enabled and os.path.exists(final_mp3) and not self._stop:
                        self.status.emit("Boosting audio...")
                        self.boost_mp3_volume(final_mp3, self.boost_value)
    
                if not self._stop:
                    self.finished.emit("Done")
    
        except Exception as e:
            if self._stop or "cancelled" in str(e).lower():
                self._stop = True  
                self.finished.emit("Cancelled")
            else:
                tb = traceback.format_exc()
                self.error.emit(f"An error occurred: {e}\n\n{tb}")
    
        finally:
            self.cleanup_partial_files()

    def stop(self):
        self._stop = True
        try:
            if self._ydl:
                self._ydl.stop_processing()
        except Exception as e:
            print(f"Error stopping yt-dlp processing: {e}")
        self.cleanup_partial_files()

    def cleanup_partial_files(self):
        """
        Scans for tracking arrays and handles wildcard disk queries 
        to ensure no orphan file remnants (including thumbnails) persist post-cancellation.
        """
        try:
            for file_path in list(self.current_downloaded_files):
                if os.path.exists(file_path):
                    if file_path.endswith((".part", ".ytdl", ".temp", ".tmp", ".webm", ".mp4", ".m4a", ".wav", ".webp", ".jpg", ".jpeg", ".png")):
                        os.remove(file_path)
                    elif file_path.endswith(".mp3") and (self._stop or os.path.getsize(file_path) < 200 * 1024):
                        os.remove(file_path)

            if self._stop and os.path.exists(self.output_dir):
                for filename in os.listdir(self.output_dir):
                    if filename.endswith((".part", ".ytdl", ".temp", ".webp", ".jpg", ".jpeg", ".png")):
                        full_bad_path = os.path.join(self.output_dir, filename)
                        try:
                            os.remove(full_bad_path)
                            print(f"Flushed orphan artifact: {filename}")
                        except Exception:
                            pass
        except Exception:
            logging.exception("Cleanup structural pass failed execution")

    def boost_mp3_volume(self, mp3_file, boost_percent):
        try:
            volume_multiplier = boost_percent / 50
            temp_file = mp3_file.replace(".mp3", "_boosted.mp3")
            self.current_downloaded_files.add(temp_file)
    
            cmd = [
                FFMPEG_CMD,
                "-y",
                "-i", mp3_file,
                "-map", "0",
                "-c:v", "copy",
                "-filter:a", f"volume={volume_multiplier}",
                "-id3v2_version", "3",
                temp_file
            ]
    
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(result.stderr)
    
            os.remove(mp3_file)
            os.rename(temp_file, mp3_file)
            
            if temp_file in self.current_downloaded_files:
                self.current_downloaded_files.remove(temp_file)
            self.current_downloaded_files.add(mp3_file)
    
        except Exception:
            logging.exception("Boost failed")
            self.status.emit("Boost failed. Check logs.")  

    def _make_opts(self, output_dir):
        outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")
        
        def hook(d):
            if self._stop:
                raise Exception("Download cancelled by user.")
                
            filename = d.get("filename")
            if filename:
                self.current_downloaded_files.add(os.path.abspath(filename))
                
            status = d.get("status")
            if status == "downloading":
                downloaded = d.get("downloaded_bytes", 0) or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct = (downloaded / total * 100) if total else 0.0
                try:
                    pct_val = max(0.0, min(100.0, float(pct)))
                except Exception:
                    pct_val = 0.0
                
                overall_pct = (((self.current_index - 1) + (pct_val / 100.0)) / self.total_tracks) * 100.0
                self.progress.emit(overall_pct)
                
                short = os.path.basename(filename or "")
                self.status.emit(
                    f"[{self.current_index}/{self.total_tracks}] "
                    f"Downloading: {pct_val:5.1f}% (Overall: {overall_pct:.1f}%) — {short[:25]}"
                )
            elif status == "finished":
                overall_finished_pct = (self.current_index / self.total_tracks) * 100.0
                self.progress.emit(overall_finished_pct)
                self.status.emit(f"[{self.current_index}/{self.total_tracks}] Converting audio streams...")

        postprocessors = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(BITRATE_KBPS),
            },
            {
                "key": "EmbedThumbnail",
            }
        ]
        
        opts = {
            "format": "bestaudio/best",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "outtmpl": outtmpl,
            "noplaylist": True, 
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            "ffmpeg_location": FFMPEG_CMD,
            "writethumbnail": True,  
            "embed_thumbnail": True,
            "keepvideo": False,      
            "postprocessors": postprocessors,
            "retries": 3,
            "continuedl": True,
        }
        return opts

# ==========================
# PREVIEW WORKER THREAD
# ==========================
class PreviewWorker(QtCore.QThread):
    preview_ready = QtCore.pyqtSignal(str)
    preview_failed = QtCore.pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self._stop = False  

    def stop(self):
        """Called externally from main UI thread to request safe cessation."""
        self._stop = True

    def run(self):
        try:
            def preview_hook(d):
                if self._stop:
                    raise Exception("Preview generation aborted by user request.")

            preview_opts = {
                "quiet": True,
                "format": "bestaudio/best",
                "socket_timeout": 3,
                "retries": 0,
                "fragment_retries": 0,
                "skip_download": True,
                "no_warnings": True,
                "noplaylist": True,
                "progress_hooks": [preview_hook]
            }

            if self._stop:
                return

            with YoutubeDL(preview_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if self._stop:
                    return
                
                if not info:
                    self.preview_failed.emit("Invalid YouTube link.")
                    return
                
                if "entries" in info:
                    entries = list(info["entries"])
                    if entries and entries[0]:
                        audio_url = entries[0].get("url")
                    else:
                        audio_url = None
                else:
                    audio_url = info.get("url")

                if self._stop:
                    return

                if audio_url:
                    self.preview_ready.emit(audio_url)
                else:
                    self.preview_failed.emit("Could not load preview stream.")
        except Exception as e:
            print(f"Preview extraction thread noted cancellation/failure: {e}")
            if not self._stop:
                self.preview_failed.emit("Invalid or broken YouTube link.")

# ==========================
# MAIN APP WINDOW
# ==========================
class AppWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube to MP3 Pro H")
        self.setFixedSize(850, 500)
        self.setStyleSheet("""
            QWidget {
                background-color: #0f1117;
                color: white;
            }
        """)
        
        try:
            if os.path.exists(ICON_PATH):
                self.setWindowIcon(QtGui.QIcon(ICON_PATH))
        except Exception as e:
            print(f"Optional asset note: Could not load window icon: {e}")
            
        self.output_dir = DEFAULT_OUTPUT_DIR
        safe_mkdir(self.output_dir)
        self.worker = None
        self.preview_worker = None
        self._resetting = False
        
        try:
            self.vlc_instance = vlc.Instance("--no-video")
            self.player = self.vlc_instance.media_player_new()
        except Exception as e:
            print(f"Critical Error: VLC architecture mismatch or not installed: {e}")
            QtWidgets.QMessageBox.critical(self, "VLC Error", "VLC Engine initialization failed. Make sure VLC 64-bit is installed.")
            sys.exit(1)

        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_player_ui)
        self.position_timer.start(100)
        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(40, 20, 40, 20)
        outer.setSpacing(12)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        title = QLabel(
            "<span style='font-size:40px; font-weight:600; letter-spacing:6px;'>"
            "<span style='color:#4285F4'>Y</span><span style='color:#EA4335'>O</span>"
            "<span style='color:#FBBC05'>U</span><span style='color:#34A853'>T</span>"
            "<span style='color:#4285F4'>U</span><span style='color:#EA4335'>B</span>"
            "<span style='color:#FBBC05'>E</span><span style='color:#34A853'>&nbsp;</span>"
            "<span style='color:#4285F4'>T</span><span style='color:#EA4335'>O</span>"
            "<span style='color:#FBBC05'>M</span><span style='color:#34A853'>P</span>"
            "<span style='color:#4285F4'>3</span><span style='color:#EA4335'>&nbsp;</span>"
            "<span style='color:#FBBC05'>P</span><span style='color:#34A853'>R</span>"
            "<span style='color:#4285F4'>O</span><span style='color:#EA4335'>&nbsp;</span>"
            "<span style='color:#FBBC05'>H</span>"
            "</span>"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(title)
        outer.addSpacing(18)

        self.input_frame = NeonFrame()
        self.input_line = QtWidgets.QLineEdit()
        self.input_line.setPlaceholderText("🔗 Paste YouTube link or drag & drop here…")
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
        self.input_line.textChanged.connect(self.preview_audio)
        self.input_line.textChanged.connect(self.update_preview_button_state)
        outer.addWidget(self.input_frame)
        outer.addSpacing(6)

        boost_layout = QtWidgets.QHBoxLayout()
        self.boost_toggle = QtWidgets.QCheckBox("Sound Boost")
        self.boost_toggle.setStyleSheet("QCheckBox { color: white; font-size: 14px; }")
        
        self.boost_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.boost_slider.setRange(100, 200)
        self.boost_slider.setValue(100)
        self.boost_slider.setVisible(False)
        
        self.boost_label = QLabel("150%")
        self.boost_label.setStyleSheet("color:white;")
        self.boost_label.setVisible(False)
        
        self.boost_toggle.toggled.connect(self.toggle_boost)
        self.boost_slider.valueChanged.connect(self.update_boost_ui)
        self.boost_slider.valueChanged.connect(self.delayed_volume_update)
        self.update_boost_ui(self.boost_slider.value())
        
        boost_layout.addWidget(self.boost_toggle)
        boost_layout.addWidget(self.boost_slider)
        boost_layout.addWidget(self.boost_label)
        outer.addLayout(boost_layout)

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
            QPushButton { color: #4285F4; background: transparent; border:none; font-size:14px; }
            QPushButton:hover { color:#34A853; }
        """)
        self.btn_change.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_change.clicked.connect(self.change_path)
        path_row.addWidget(self.btn_change)
        outer.addLayout(path_row)
        outer.addSpacing(20)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        btn_row.setSpacing(22)
        
        self.btn_download = QtWidgets.QPushButton("Download MP3")
        self.btn_download.setFixedSize(220, 56)
        self.btn_download.setStyleSheet("""
            QPushButton {
                font-size:18px; font-weight:500; border:2px solid transparent; border-radius:28px; padding:10px; color:white;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4285F4, stop:1 #EA4335);
            }
        """)
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self.start_download)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(255, 60, 80, 140))
        self.btn_download.setGraphicsEffect(shadow)
        btn_row.addWidget(self.btn_download)

        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.setFixedSize(180, 56)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                font-size:18px; font-weight:500; border:2px solid #4285F4; color:#4285F4; border-radius:28px; padding:10px; background: transparent;
            }
            QPushButton:hover { background: rgba(66,133,244,40%); border:2px solid #34A853; color:#34A853; }
            QPushButton:pressed { background: rgba(52,168,83,60%); border:2px solid #0F9D58; color:#0F9D58; }
        """)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_download)
        btn_row.addWidget(self.btn_cancel)
        outer.addLayout(btn_row)

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 15px; padding-left: 4px;")
        outer.addWidget(self.lbl_status)
        outer.addSpacing(8)
        
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet("""
        QProgressBar { background: rgba(255,255,255,0.08); border: none; border-radius: 3px; }
        QProgressBar::chunk { border-radius: 3px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff2d55, stop:1 #ff0000); }
        """)
        outer.addWidget(self.progress)
        outer.addSpacing(24)
        
        player_row = QtWidgets.QHBoxLayout()
        player_row.setSpacing(14)
        
        self.btn_play_pause = QtWidgets.QPushButton("PREVIEW")
        self.btn_play_pause.setFixedSize(90, 40)
        self.btn_play_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_pause.setEnabled(False)
        self.btn_play_pause.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 20px;
                color: #FFFFFF; font-size: 12px; font-weight: bold; letter-spacing: 1px;
            }
            QPushButton:hover { background-color: #4285F4; border: 1px solid #4285F4; }
            QPushButton:pressed { background-color: #34A853; border: 1px solid #34A853; }
        """)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        player_row.addWidget(self.btn_play_pause)

        self.lbl_playback_state = QLabel("[ Stopped ]")
        self.lbl_playback_state.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 12px; font-weight: bold;")
        player_row.addWidget(self.lbl_playback_state)

        self.seek_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 100)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderMoved.connect(self.set_player_position)
        self.seek_slider.sliderReleased.connect(lambda: self.set_player_position(self.seek_slider.value()))
        self.seek_slider.setStyleSheet("""
        QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,0.25); border-radius: 2px; }
        QSlider::sub-page:horizontal { background: #ff0000; border-radius: 2px; }
        QSlider::handle:horizontal { background: white; width: 10px; height: 10px; margin: -4px 0; border-radius: 5px; }
        """)
        player_row.addWidget(self.seek_slider)
        
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 14px;")
        player_row.addWidget(self.time_label)
        
        outer.addLayout(player_row)
        outer.addStretch()
        footer = QLabel(
            "MP3 - 320kbps <span style='color:#FBBC05;'>•</span> "
            "Playlist Support <span style='color:#FBBC05;'>•</span> "
            "Drag & Drop Enabled"
        )
        footer.setStyleSheet("color:#BDC1C6; font-size:13px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(footer)
        self.update_preview_button_state()

    def toggle_play_pause(self):
        if self.player.is_playing():
            self.player.pause()
            self.lbl_playback_state.setText("[ Paused ]")
            self.lbl_playback_state.setStyleSheet("color: #EA4335; font-size: 12px; font-weight: bold;")
        else:
            self.player.play()
            self.lbl_playback_state.setText("[ Playing ]")
            self.lbl_playback_state.setStyleSheet("color: #34A853; font-size: 12px; font-weight: bold;")

    def update_preview_button_state(self):
        url = self.input_line.text().strip()
        valid = is_valid_youtube_url(url)
        self.btn_play_pause.setEnabled(bool(valid))

    def change_path(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select download folder", str(self.output_dir))
        if path:
            self.output_dir = Path(path)
            self.lbl_path_value.setText(str(self.output_dir))

    def auto_preview_timer(self):
        pass         

    def preview_audio(self):
        if self._resetting:
            return
    
        url = self.input_line.text().strip()
        
        if not url:
            self.reset_player_ui()
            self.btn_play_pause.setEnabled(False)
            self.lbl_status.setText("Ready")
            if hasattr(self, "_current_preview_url"):
                self._current_preview_url = ""
            return
    
        if not is_valid_youtube_url(url):
            self.btn_play_pause.setEnabled(False)
            self.lbl_status.setText("Waiting for valid link...")
            return
            
        if hasattr(self, "_current_preview_url") and self._current_preview_url == url:
            return

        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_worker.stop()
            self.preview_worker.wait()

        self.lbl_status.setText("Loading preview (background)...")
        self.btn_play_pause.setEnabled(False)
        self.seek_slider.setEnabled(False)
        
        self._current_preview_url = url

        self.preview_worker = PreviewWorker(url)
        self.preview_worker.preview_ready.connect(self._on_preview_ready)
        self.preview_worker.preview_failed.connect(self._on_preview_failed)
        self.preview_worker.start()

    def _on_preview_ready(self, audio_url):
        try:
            self.btn_play_pause.setEnabled(True)
            self.seek_slider.setEnabled(True)
            
            self.player.set_media(None) 
            
            media = self.vlc_instance.media_new(audio_url)
            self.player.set_media(media)
            
            self.player.audio_set_volume(self.boost_slider.value() if self.boost_toggle.isChecked() else 100)
            self.player.stop() 
            
            self.lbl_status.setText("Preview is ready")
            self.lbl_playback_state.setText("[ Ready ]")
            self.lbl_playback_state.setStyleSheet("color: #2ecc71; font-size: 12px; font-weight: bold;")
        except Exception as e:
            print(f"Failed loading playback audio into VLC engine: {e}")
            self._on_preview_failed("VLC failed to load stream.")

    def _on_preview_failed(self, error_msg):
        self.reset_player_ui()
        self.btn_play_pause.setEnabled(False)
        self.lbl_status.setText(error_msg)

    def start_download(self):
        if not check_ffmpeg():
            QtWidgets.QMessageBox.critical(self, "FFmpeg Missing", "Install FFmpeg and try again.")
            return

        if not check_internet():
            QtWidgets.QMessageBox.critical(self, "No Internet", "You are offline! Please check your connection.")
            self.lbl_status.setText("Offline")
            return

        url = self.input_line.text().strip()
        if not url or not is_valid_youtube_url(url): 
            self.lbl_status.setText("Please paste a valid YouTube link.")
            return

        safe_mkdir(self.output_dir)
        boost_enabled = self.boost_toggle.isChecked()
        boost_value = self.boost_slider.value()
        
        self.worker = DownloadWorker(url, str(self.output_dir), boost_enabled, boost_value)
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
                self.worker.wait() 
            except Exception as e:
                print(f"Error terminating download execution worker: {e}")
        self.lbl_status.setText("Cancelled")
        self.progress.setValue(0)
        self.input_line.clear()
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QtCore.QTimer.singleShot(5000, self.reset_ui)

    def update_boost_ui(self, value):
        self.boost_label.setText(f"{value}%")
        min_val, max_val = 100, 200
        ratio = max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
        r = int(52 + (234 - 52) * ratio)
        g = int(168 + (67 - 168) * ratio)
        b = int(83 + (53 - 83) * ratio)
        color = f"rgb({r},{g},{b})"
    
        self.boost_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ height: 8px; background: #3c4043; border-radius: 4px; }}
            QSlider::sub-page:horizontal {{ background: {color}; border-radius: 4px; }}
            QSlider::handle:horizontal {{ background: white; width: 18px; margin: -6px 0; border-radius: 9px; }}
        """)
        self.boost_label.setStyleSheet(f"color:{color}; font-weight:bold;")  

    def toggle_boost(self, checked):
        self.boost_slider.setVisible(checked)
        self.boost_label.setVisible(checked)
        try:
            self.player.audio_set_volume(self.boost_slider.value() if checked else 100)
        except Exception as e:
            print(f"Error applying audio toggle volume modification: {e}")

    def delayed_volume_update(self, value):
        if not hasattr(self, "_volume_timer"):
            self._volume_timer = QTimer()
            self._volume_timer.setSingleShot(True)
            self._volume_timer.timeout.connect(lambda: self.apply_volume(self.boost_slider.value()))
        self._volume_timer.start(60)
    
    def apply_volume(self, value):
        try:
            self.player.audio_set_volume(value)
        except Exception as e:
            print(f"Error modifying active VLC audio channel gain: {e}")

    def update_player_ui(self):
        try:
            if not self.player or self.seek_slider.isSliderDown():
                return
            length = self.player.get_length()
            current = self.player.get_time()
            if length <= 0:
                return
            position = int((current / length) * 100)
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(position)
            self.seek_slider.blockSignals(False)
            current_sec = max(0, current // 1000)
            total_sec = max(0, length // 1000)
            self.time_label.setText(f"{current_sec // 60}:{current_sec % 60:02d} / {total_sec // 60}:{total_sec % 60:02d}")
        except Exception as e:
            print(f"Error refreshing player timeline components: {e}")

    def set_player_position(self, position):
        try:
            length = self.player.get_length()
            if length > 0:
                self.player.set_time(int((position / 100) * length))
        except Exception as e:
            print(f"Error resetting media player timeframe playback marker: {e}")

    def reset_player_ui(self):
        try:
            self.player.stop()
            self.player.set_media(None)
        except Exception as e:
            print(f"Error flushing media source contents: {e}")
        self.seek_slider.setValue(0)
        self.seek_slider.setEnabled(False)
        self.time_label.setText("0:00 / 0:00")   
        self.lbl_playback_state.setText("[ Stopped ]")
        self.lbl_playback_state.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 12px; font-weight: bold;")     

    def _on_progress(self, pct):
        self.progress.setValue(int(pct))

    def _on_status(self, msg):
        self.lbl_status.setText(msg)

    def _on_finished(self, msg):
        self.progress.setValue(100)
        self.lbl_status.setText(msg)
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QtCore.QTimer.singleShot(5000, self.reset_ui)

    def _on_error(self, err):
        if "Download cancelled by user" not in err:
            QtWidgets.QMessageBox.critical(self, "Error", err)
        self.lbl_status.setText("Error")
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    def reset_ui(self):
        self._resetting = True

        if hasattr(self, "_current_preview_url"):
            self._current_preview_url = ""

        try:
            self.player.stop()
            self.player.set_media(None)
        except Exception as e:
            print(f"Error resetting audio components: {e}")
        self.input_line.clear()
        self.progress.setValue(0)
        self.lbl_status.setText("Ready")
        self.boost_toggle.setChecked(False)
        self.boost_slider.setValue(100)
        self.seek_slider.setValue(0)
        self.seek_slider.setEnabled(False)
        self.time_label.setText("0:00 / 0:00")
        self.lbl_playback_state.setText("[ Stopped ]")
        self.lbl_playback_state.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 12px; font-weight: bold;")
        self._resetting = False
        
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            self.input_line.setText(e.mimeData().urls()[0].toString())
        elif e.mimeData().hasText():
            self.input_line.setText(e.mimeData().text())

    def closeEvent(self, event):
        """
        Intercepts application window closure to cleanly deallocate resources,
        stopping threads, killing active timers, and releasing unmanaged VLC objects.
        """
        print("Application shutting down... Cleaning up resources.")
        self._resetting = True  
        
        if hasattr(self, "position_timer") and self.position_timer.isActive():
            self.position_timer.stop()
        if hasattr(self, "_volume_timer") and self._volume_timer.isActive():
            self._volume_timer.stop()

        if self.worker and self.worker.isRunning():
            try:
                self.worker.stop()
                self.worker.wait() 
            except Exception as e:
                print(f"Error stopping download worker on exit: {e}")

        if self.preview_worker and self.preview_worker.isRunning():
            try:
                self.preview_worker.stop()
                self.preview_worker.wait()
            except Exception as e:
                print(f"Error stopping preview worker on exit: {e}")

        try:
            if hasattr(self, "player") and self.player is not None:
                self.player.stop()
                self.player.release() 
                self.player = None
                
            if hasattr(self, "vlc_instance") and self.vlc_instance is not None:
                self.vlc_instance.release()  
                self.vlc_instance = None
        except Exception as e:
            print(f"Error releasing native VLC components on exit: {e}")

        event.accept()

def main(): 
    logging.basicConfig(
        filename="youtube_to_mp3.log",
        filemode="a",  
        format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.ERROR  
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
    logging.getLogger().addHandler(console_handler)

    print("Logging initialized. Writing diagnostics to 'youtube_to_mp3.log'")

    app = QtWidgets.QApplication(sys.argv) 
    app.setFont(QtGui.QFont("Segoe UI", 10)) 
    win = AppWindow() 
    win.show() 
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
