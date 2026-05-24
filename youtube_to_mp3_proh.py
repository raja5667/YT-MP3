import os
import sys
import traceback
from pathlib import Path
from yt_dlp import YoutubeDL
import socket
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

def get_ffmpeg_path():
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "ffmpeg.exe")
    return os.path.join(os.path.dirname(__file__), "ffmpeg.exe")

FFMPEG_CMD = get_ffmpeg_path()
ICON_PATH = "/mnt/data/app_icon.ico"
SQUARE_THUMBNAIL_SIZE = 500 

# ==========================
# UTILITY FUNCTIONS
# ==========================
def check_ffmpeg() -> bool:
    return os.path.exists(FFMPEG_CMD)

def safe_mkdir(p: Path):
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

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

    def run(self):
        try:
            opts = self._make_opts(self.output_dir)
    
            with YoutubeDL(opts) as ydl:
                self._ydl = ydl
    
                self.status.emit("Extracting link metadata...")
                if self._stop:
                    self.finished.emit("Cancelled")
                    return
    
                info = ydl.extract_info(self.url, download=False)
                if not info:
                    raise Exception("Failed to extract video information.")

                # If it's a playlist, explicitly handle individual downloads in a controlled loop
                if "entries" in info:
                    entries = list(info["entries"])
                    total_tracks = len(entries)
                    self.status.emit(f"Found playlist with {total_tracks} tracks. Starting...")
                    
                    for index, entry in enumerate(entries, start=1):
                        if self._stop:
                            self.finished.emit("Cancelled")
                            return
                        
                        if not entry:
                            continue
                            
                        track_url = entry.get("url") or entry.get("webpage_url")
                        if not track_url:
                            continue
                            
                        title = entry.get("title", f"Track_{index}")
                        for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
                            title = title.replace(char, "_")
                            
                        self.status.emit(f"[{index}/{total_tracks}] Processing: {title[:30]}...")
                        
                        # Configure options specifically for this track extraction
                        track_opts = self._make_opts(self.output_dir)
                        with YoutubeDL(track_opts) as single_ydl:
                            if self._stop:
                                self.finished.emit("Cancelled")
                                return
                            single_ydl.download([track_url])
                        
                        # Handle audio volume boost post-conversion
                        final_mp3 = os.path.join(self.output_dir, f"{title}.mp3")
                        if self.boost_enabled and os.path.exists(final_mp3) and not self._stop:
                            self.status.emit(f"[{index}/{total_tracks}] Boosting Audio...")
                            self.boost_mp3_volume(final_mp3, self.boost_value)
                else:
                    title = info.get("title", "audio")
                    for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
                        title = title.replace(char, "_")
                        
                    final_mp3 = os.path.join(self.output_dir, f"{title}.mp3")
    
                    self.status.emit("Starting download...")
                    ydl.download([self.url])
    
                    if self.boost_enabled and os.path.exists(final_mp3) and not self._stop:
                        self.status.emit("Boosting audio...")
                        self.boost_mp3_volume(final_mp3, self.boost_value)
    
                if not self._stop:
                    self.finished.emit("Done")
    
        except Exception as e:
            if self._stop:
                self.finished.emit("Cancelled")
            else:
                tb = traceback.format_exc()
                self.error.emit(f"An error occurred: {e}\n\n{tb}")
    
        finally:
            self.cleanup_partial_files(self.output_dir)

    def stop(self):
        self._stop = True
        try:
            if self._ydl:
                self._ydl.stop_processing()
        except:
            pass
        self.cleanup_partial_files(self.output_dir)

    def cleanup_partial_files(self, folder):
        try:
            for f in os.listdir(folder):
                file_path = os.path.join(folder, f)
                if f.endswith((".part", ".ytdl", ".temp", ".tmp", ".webm", ".mp4", ".m4a", ".wav")):
                    os.remove(file_path)
                elif f.endswith((".webp", ".jpg", ".jpeg", ".png")):
                    os.remove(file_path)
                elif f.endswith(".mp3"):
                    if os.path.getsize(file_path) < 200 * 1024:
                        os.remove(file_path)
        except Exception:
            pass

    def boost_mp3_volume(self, mp3_file, boost_percent):
        try:
            volume_multiplier = boost_percent / 50
            temp_file = mp3_file.replace(".mp3", "_boosted.mp3")
    
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
    
        except Exception as e:
            self.status.emit(f"Boost failed: {e}")     

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
                self.status.emit(f"Downloading: {pct_val:5.1f}% — {short[:30]}")
            elif status == "finished":
                self.status.emit("Converting audio streams...")

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
            "noplaylist": True, # Managed explicitly inside the worker loop
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
        except:
            pass
            
        self.output_dir = DEFAULT_OUTPUT_DIR
        safe_mkdir(self.output_dir)
        self.worker = None
        self._resetting = False
        self.vlc_instance = vlc.Instance("--no-video")
        self.player = self.vlc_instance.media_player_new()
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
        self.input_line.textChanged.connect(self.auto_preview_timer)
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
        valid = "youtube.com/watch?v=" in url or "youtu.be/" in url or "youtube.com/playlist?list=" in url
        self.btn_play_pause.setEnabled(bool(valid))

    def change_path(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select download folder", str(self.output_dir))
        if path:
            self.output_dir = Path(path)
            self.lbl_path_value.setText(str(self.output_dir))

    def auto_preview_timer(self):
        if hasattr(self, "_preview_timer"):
            self._preview_timer.stop()
        else:
            self._preview_timer = QTimer()
            self._preview_timer.setSingleShot(True)
            self._preview_timer.timeout.connect(self.preview_audio)
        self._preview_timer.start(1000)         

    def preview_audio(self):
        if self._resetting:
            return
    
        try:
            url = self.input_line.text().strip()
            if not url:
                self.reset_player_ui()
                self.btn_play_pause.setEnabled(False)
                self.lbl_status.setText("Ready")
                return
    
            if "youtube.com/watch?v=" not in url and "youtu.be/" not in url and "youtube.com/playlist?list=" not in url:
                self.reset_player_ui()
                self.btn_play_pause.setEnabled(False)
                self.lbl_status.setText("Invalid YouTube link.")
                return
    
            self.lbl_status.setText("Loading preview...")
    
            preview_opts = {
                "quiet": True,
                "format": "bestaudio/best",
                "socket_timeout": 3,
                "retries": 0,
                "fragment_retries": 0,
                "skip_download": True,
                "no_warnings": True
            }

            with YoutubeDL(preview_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception:
                    self.reset_player_ui()
                    self.btn_play_pause.setEnabled(False)
                    self.lbl_status.setText("Invalid or broken YouTube link.")
                    return
    
                if not info:
                    self.reset_player_ui()
                    self.btn_play_pause.setEnabled(False)
                    self.lbl_status.setText("Invalid YouTube link.")
                    return
                
                # Dynamic fix: extract the first track URL if link is a playlist
                if "entries" in info:
                    entries = list(info["entries"])
                    if entries and entries[0]:
                        audio_url = entries[0].get("url")
                    else:
                        audio_url = None
                else:
                    audio_url = info.get("url")
    
                if not audio_url:
                    self.reset_player_ui()
                    self.btn_play_pause.setEnabled(False)
                    self.lbl_status.setText("Could not load preview stream.")
                    return
    
            self.btn_play_pause.setEnabled(True)
            self.player.stop()
    
            media = self.vlc_instance.media_new(audio_url)
            self.player.set_media(media)
            self.player.audio_set_volume(self.boost_slider.value())
            self.player.play()
            
            self.lbl_playback_state.setText("[ Playing ]")
            self.lbl_playback_state.setStyleSheet("color: #34A853; font-size: 12px; font-weight: bold;")
    
            def auto_pause():
                self.player.pause()
                self.lbl_playback_state.setText("[ Preview Ready ]")
                self.lbl_playback_state.setStyleSheet("color: #4285F4; font-size: 12px; font-weight: bold;")
                self.lbl_status.setText("Ready to Preview")
            
            QtCore.QTimer.singleShot(400, auto_pause)
    
        except Exception:
            self.reset_player_ui()
            self.btn_play_pause.setEnabled(False)
            self.lbl_status.setText("Invalid or broken YouTube link.")

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
                self.worker.wait(500) 
            except:
                pass
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
            print(e)

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
            print(e)

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
            print(e)

    def set_player_position(self, position):
        try:
            length = self.player.get_length()
            if length > 0:
                self.player.set_time(int((position / 100) * length))
        except Exception as e:
            print(e)

    def reset_player_ui(self):
        try:
            self.player.stop()
            self.player.set_media(None)
        except:
            pass
        self.seek_slider.setValue(0)
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
        if hasattr(self, "_preview_timer"):
            self._preview_timer.stop()
        try:
            self.player.stop()
            self.player.set_media(None)
        except:
            pass
        self.input_line.clear()
        self.progress.setValue(0)
        self.lbl_status.setText("Ready")
        self.boost_toggle.setChecked(False)
        self.boost_slider.setValue(100)
        self.seek_slider.setValue(0)
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

def main(): 
    app = QtWidgets.QApplication(sys.argv) 
    app.setFont(QtGui.QFont("Segoe UI", 10)) 
    win = AppWindow() 
    win.show() 
    sys.exit(app.exec())

if __name__ == "__main__":
    main()