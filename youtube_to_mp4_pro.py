import os
import sys
import traceback
import shutil
from pathlib import Path
from yt_dlp import YoutubeDL
import socket
import logging
import subprocess

def _no_window():
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": si}

# ===== Path Setup =====
if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path):
    try:
        bp = sys._MEIPASS
    except Exception:
        bp = os.path.abspath(".")
    return os.path.join(bp, relative_path)

ICON_PATH = resource_path("app_icon.ico")

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QPropertyAnimation, pyqtProperty, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QBrush, QColor, QLinearGradient, QPixmap, QImage
from PyQt6.QtWidgets import QLabel

# ==========================
# CONFIG & CONSTANTS
# ==========================
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads"
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_QUALITIES = ["Best Available", "4K (2160p)", "1440p", "1080p", "720p", "480p", "360p", "240p", "144p"]

# Format strings explained:
#   1. Prefer best video (any codec) + best audio, merged to mp4 via ffmpeg
#   2. Fallback to a pre-merged mp4/webm stream at that height
#   3. Last resort: absolute best single stream
# Including webm/vp9 in the chain is critical — YouTube serves 1080p+ almost
# exclusively as webm. Without it, yt-dlp silently downgrades to 720p mp4.
QUALITY_FORMAT_MAP = {
    # Best Available: grab the absolute best video + best audio and merge.
    "Best Available": (
        "bestvideo+bestaudio/best"
    ),
    # 4K (2160p): YouTube serves 4K only as VP9/AV1 webm — ffmpeg merges to mp4.
    # No height floor so it always falls back gracefully if 4K is not available.
    "4K (2160p)": (
        "bestvideo[height<=2160]+bestaudio"
        "/best[height<=2160]"
        "/bestvideo+bestaudio"
        "/best"
    ),
    # 1440p: VP9 webm only at this tier; always falls back cleanly.
    "1440p": (
        "bestvideo[height<=1440]+bestaudio"
        "/best[height<=1440]"
        "/bestvideo+bestaudio"
        "/best"
    ),
    # 1080p: prefer VP9 webm (higher quality than AVC mp4 at same resolution).
    "1080p": (
        "bestvideo[height<=1080]+bestaudio"
        "/best[height<=1080]"
        "/bestvideo+bestaudio"
        "/best"
    ),
    # 720p and below: AVC mp4 streams exist; prefer mp4+m4a for compatibility.
    "720p": (
        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
        "/bestvideo[height<=720]+bestaudio"
        "/best[height<=720]"
        "/best"
    ),
    "480p": (
        "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]"
        "/bestvideo[height<=480]+bestaudio"
        "/best[height<=480]"
        "/best"
    ),
    "360p": (
        "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]"
        "/bestvideo[height<=360]+bestaudio"
        "/best[height<=360]"
        "/best"
    ),
    "240p": (
        "bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]"
        "/bestvideo[height<=240]+bestaudio"
        "/best[height<=240]"
        "/best"
    ),
    "144p": (
        "bestvideo[height<=144][ext=mp4]+bestaudio[ext=m4a]"
        "/bestvideo[height<=144]+bestaudio"
        "/best[height<=144]"
        "/best"
    ),
}

# Map quality label to expected max height, used to detect fallback situations
QUALITY_HEIGHT_MAP = {
    "4K (2160p)": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
    "240p": 240,
    "144p": 144,
}

def resolve_ffmpeg_path() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    binary_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, binary_name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), binary_name)

FFMPEG_CMD = resolve_ffmpeg_path()

def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None or os.path.exists(FFMPEG_CMD)

def check_internet(timeout=3) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection(("8.8.8.8", 53))
        return True
    except OSError:
        return False

def safe_mkdir(p: Path):
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Failed to create directory {p}: {e}")

def fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

# ==========================
# NEON FRAME
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
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, int(255 * 0.02))))
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
            gradient.setColorAt(stops[i], stops[i + 1])

        pen = QtGui.QPen()
        pen.setWidth(3)
        pen.setBrush(gradient)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 27, 27)
        painter.end()

# ==========================
# THUMBNAIL LOADER THREAD
# ==========================
class ThumbnailLoader(QThread):
    """Fetches video info (duration + thumbnail URL + title + available heights) in background."""
    info_ready = pyqtSignal(int, str, str, list)  # duration, thumbnail_url, title, available_heights
    error      = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            opts = {
                "quiet": True,
                "skip_download": True,
                "no_warnings": True,
                "noplaylist": True,
            }
            with YoutubeDL(opts) as ydl:
                info  = ydl.extract_info(self.url, download=False)
                dur   = int(info.get("duration", 0) or 0)
                thumb = info.get("thumbnail", "")
                title = info.get("title", "")
                # Collect all unique heights available for this video
                heights = set()
                for fmt in info.get("formats", []):
                    h = fmt.get("height")
                    if h:
                        heights.add(int(h))
                self.info_ready.emit(dur, thumb, title, sorted(heights, reverse=True))
        except Exception as e:
            self.error.emit(str(e))


class ThumbnailDownloader(QThread):
    """Downloads the thumbnail image bytes."""
    pixmap_ready = pyqtSignal(QPixmap)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            import urllib.request
            with urllib.request.urlopen(self.url, timeout=8) as r:
                data = r.read()
            img = QImage()
            img.loadFromData(data)
            if not img.isNull():
                self.pixmap_ready.emit(QPixmap.fromImage(img))
        except Exception:
            pass


# ==========================
# STREAM URL FETCHER
# ==========================
class StreamUrlFetcher(QThread):
    """Gets the direct stream URL for frame extraction via ffmpeg."""
    url_ready = pyqtSignal(str, int)   # stream_url, duration

    def __init__(self, page_url: str):
        super().__init__()
        self.page_url = page_url

    def run(self):
        try:
            opts = {
                "quiet": True,
                "skip_download": True,
                "no_warnings": True,
                "noplaylist": True,
                "format": "bestvideo[height<=480][ext=mp4]/bestvideo[height<=480]/best[height<=480]/best",
            }
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.page_url, download=False)
                dur  = int(info.get("duration", 0) or 0)
                url  = info.get("url", "")
                if not url and "requested_formats" in info:
                    url = info["requested_formats"][0].get("url", "")
                self.url_ready.emit(url, dur)
        except Exception:
            self.url_ready.emit("", 0)


# ==========================
# FRAME EXTRACTOR THREAD
# ==========================
class FrameExtractor(QThread):
    """Extracts frames at specific timestamps; emits each frame as it arrives
    so the filmstrip fills in progressively (important for 50 frames)."""
    frame_ready  = pyqtSignal(list)   # [(timestamp_sec, QPixmap)] — one at a time
    frames_ready = pyqtSignal(list)   # full list at end (compat)

    def __init__(self, stream_url: str, timestamps: list, duration: int):
        super().__init__()
        self.stream_url = stream_url
        self.timestamps = timestamps
        self.duration   = duration
        self._stop      = False

    def stop(self):
        self._stop = True

    def run(self):
        results = []
        for ts in self.timestamps:
            if self._stop:
                break
            try:
                cmd = [
                    FFMPEG_CMD, "-y",
                    "-ss", str(ts),
                    "-i", self.stream_url,
                    "-frames:v", "1",
                    "-q:v", "5",
                    "-f", "image2pipe",
                    "-vcodec", "mjpeg",
                    "pipe:1"
                ]
                proc = subprocess.run(cmd, capture_output=True, timeout=12, **_no_window())
                if proc.returncode == 0 and proc.stdout:
                    img = QImage()
                    img.loadFromData(proc.stdout)
                    if not img.isNull():
                        pair = (ts, QPixmap.fromImage(img))
                        results.append(pair)
                        self.frame_ready.emit([pair])   # progressive update
            except Exception:
                pass
        if results:
            self.frames_ready.emit(results)


# ==========================
# FILMSTRIP RANGE SLIDER
# Frames are drawn as the background of the slider itself.
# ==========================
NUM_FRAMES = 5   # number of preview frames shown in the strip

class RangeSlider(QtWidgets.QWidget):
    """
    Dual-handle range slider with a filmstrip background.
    The frames fill the full height of the widget; handles sit on top.
    """
    range_changed = QtCore.pyqtSignal(int, int)

    STRIP_H   = 50   # total widget height (filmstrip height)
    HANDLE_R  = 10   # handle circle radius
    LABEL_H   = 18   # timestamp label strip at bottom of each frame

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.STRIP_H)
        self._duration   = 0
        self._start      = 0
        self._end        = 0
        self._drag       = None
        self._pixmaps    = {}      # {timestamp_sec: QPixmap}
        self._timestamps = []      # ordered list of timestamp keys
        self._loading    = False
        self._placeholder       = "Paste a URL above to load video preview"
        self._placeholder_color = QColor(255, 255, 255, 45)   # default: dim white
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ── public API ──────────────────────────────────────────────────────
    def set_duration(self, seconds: int):
        self._duration = max(1, seconds)
        self._start    = 0
        self._end      = self._duration
        self.update()
        self.range_changed.emit(self._start, self._end)

    def set_loading(self, timestamps: list):
        self._timestamps = timestamps
        self._pixmaps    = {}
        self._loading    = True
        self.update()

    def set_frames(self, frames: list):
        """frames = [(timestamp_sec, QPixmap), ...]  — merges into existing dict."""
        self._loading = False
        for ts, px in frames:
            self._pixmaps[ts] = px
        self.update()

    def set_placeholder(self, text: str = "", color: QColor = None):
        self._loading    = False
        self._pixmaps    = {}
        self._timestamps = []
        self._placeholder       = text or "Paste a URL above to load video preview"
        self._placeholder_color = color if color is not None else QColor(255, 255, 255, 45)
        self.update()

    def get_start(self) -> int:
        return self._start

    def get_end(self) -> int:
        return self._end

    # ── geometry helpers ────────────────────────────────────────────────
    def _usable_rect(self) -> QtCore.QRect:
        """The full filmstrip area (inset slightly for border)."""
        r = self.HANDLE_R
        return self.rect().adjusted(r, 0, -r, 0)

    def _x_for(self, val: int) -> int:
        ur = self._usable_rect()
        if self._duration == 0:
            return ur.left()
        return ur.left() + int((val / self._duration) * ur.width())

    def _val_for(self, x: int) -> int:
        ur    = self._usable_rect()
        ratio = max(0.0, min(1.0, (x - ur.left()) / max(1, ur.width())))
        return int(ratio * self._duration)

    # ── painting ────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p  = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w  = self.width()
        h  = self.STRIP_H
        ur = self._usable_rect()

        # ── 1. filmstrip background ──────────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(20, 22, 32)))
        p.drawRoundedRect(ur, 6, 6)

        if not self._timestamps:
            # placeholder text
            p.setPen(self._placeholder_color)
            p.setFont(QtGui.QFont("Segoe UI", 9))
            p.drawText(ur, Qt.AlignmentFlag.AlignCenter, self._placeholder)
        else:
            n          = len(self._timestamps)
            cell_w     = ur.width() // n
            frame_h    = h

            for i, ts in enumerate(self._timestamps):
                fx         = ur.left() + i * cell_w
                frame_rect = QtCore.QRect(fx, 0, cell_w, frame_h)

                if ts in self._pixmaps:
                    px = self._pixmaps[ts].scaled(
                        cell_w, frame_h,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    src_x = max(0, (px.width()  - cell_w)  // 2)
                    src_y = max(0, (px.height() - frame_h) // 2)
                    p.setClipRect(frame_rect)
                    p.drawPixmap(
                        frame_rect, px,
                        QtCore.QRect(src_x, src_y, cell_w, frame_h)
                    )
                    p.setClipping(False)

                    # timestamp label at bottom of cell
                    lbl_rect = QtCore.QRect(fx, frame_h - self.LABEL_H, cell_w, self.LABEL_H)
                    p.setBrush(QBrush(QColor(0, 0, 0, 160)))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawRect(lbl_rect)
                    p.setPen(QColor(255, 255, 255, 210))
                    p.setFont(QtGui.QFont("Segoe UI", 7, QtGui.QFont.Weight.Bold))
                    p.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, fmt_time(ts))
                else:
                    # loading slot
                    p.setBrush(QBrush(QColor(28, 31, 45)))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawRect(frame_rect)
                    if self._loading:
                        p.setPen(QColor(255, 255, 255, 35))
                        p.setFont(QtGui.QFont("Segoe UI", 13))
                        p.drawText(frame_rect, Qt.AlignmentFlag.AlignCenter, "⏳")

                # cell divider
                if i > 0:
                    p.setPen(QtGui.QPen(QColor(0, 0, 0, 80), 1))
                    p.drawLine(fx, 0, fx, frame_h)

        # ── 2. strip border ──────────────────────────────────────────────
        p.setPen(QtGui.QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(ur.adjusted(0, 0, -1, -1), 6, 6)

        # ── 3. darkened sides outside the selected range ─────────────────
        x1 = self._x_for(self._start)
        x2 = self._x_for(self._end)

        # left dimmed zone
        if x1 > ur.left():
            p.setBrush(QBrush(QColor(0, 0, 0, 130)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setClipRect(QtCore.QRect(ur.left(), 0, x1 - ur.left(), h))
            p.drawRoundedRect(ur, 6, 6)
            p.setClipping(False)

        # right dimmed zone
        if x2 < ur.right():
            p.setBrush(QBrush(QColor(0, 0, 0, 130)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setClipRect(QtCore.QRect(x2, 0, ur.right() - x2, h))
            p.drawRoundedRect(ur, 6, 6)
            p.setClipping(False)

        # ── 4. selection border (bright outline over selected area) ───────
        sel_rect = QtCore.QRect(x1, 0, x2 - x1, h)
        grad = QLinearGradient(x1, 0, x2, 0)
        grad.setColorAt(0, QColor(66, 133, 244, 200))
        grad.setColorAt(1, QColor(52, 168, 83, 200))
        p.setPen(QtGui.QPen(QBrush(grad), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(sel_rect)

        cy = h // 2

        # ── 5. start handle ──────────────────────────────────────────────
        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.setPen(QtGui.QPen(QColor("#4285F4"), 2))
        p.drawEllipse(QtCore.QPoint(x1, cy), self.HANDLE_R, self.HANDLE_R)

        # ── 6. end handle ────────────────────────────────────────────────
        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.setPen(QtGui.QPen(QColor("#34A853"), 2))
        p.drawEllipse(QtCore.QPoint(x2, cy), self.HANDLE_R, self.HANDLE_R)

        p.end()

    # ── mouse events ────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        x  = e.position().x()
        x1 = self._x_for(self._start)
        x2 = self._x_for(self._end)
        self._drag = "start" if abs(x - x1) <= abs(x - x2) else "end"
        self._move_drag(x)

    def mouseMoveEvent(self, e):
        if self._drag:
            self._move_drag(e.position().x())
        else:
            x  = e.position().x()
            x1 = self._x_for(self._start)
            x2 = self._x_for(self._end)
            near = abs(x - x1) <= self.HANDLE_R + 4 or abs(x - x2) <= self.HANDLE_R + 4
            self.setCursor(
                Qt.CursorShape.SizeHorCursor if near else Qt.CursorShape.ArrowCursor
            )

    def mouseReleaseEvent(self, e):
        self._drag = None

    def _move_drag(self, x: float):
        val = self._val_for(int(x))
        if self._drag == "start":
            self._start = max(0, min(val, self._end - 1))
        elif self._drag == "end":
            self._end = min(self._duration, max(val, self._start + 1))
        self.update()
        self.range_changed.emit(self._start, self._end)


# ==========================
# VIDEO DOWNLOAD WORKER
# ==========================
class VideoDownloadWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(float)
    status   = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(str)
    error    = QtCore.pyqtSignal(str)

    def __init__(self, url: str, output_dir: str,
                 quality: str = "Best Available",
                 trim_start: int = None, trim_end: int = None):
        super().__init__()
        self.url        = url
        self.output_dir = output_dir
        self.quality    = quality
        self.trim_start = trim_start
        self.trim_end   = trim_end
        self._stop      = False
        self._ydl       = None
        self.current_downloaded_files = set()
        self.current_index = 1
        self.total_tracks  = 1

    def run(self):
        try:
            self.total_tracks  = 1
            self.current_index = 1

            self.status.emit("Starting download...")
            opts = self._make_opts(self.output_dir)
            with YoutubeDL(opts) as single_ydl:
                self._ydl = single_ydl
                if self._stop:
                    self.finished.emit("Cancelled")
                    return
                single_ydl.download([self.url])

            if not self._stop:
                self.finished.emit("Done")

        except Exception as e:
            err_str = str(e).lower()
            if self._stop or "cancelled" in err_str:
                self._stop = True
                self.finished.emit("Cancelled")
            else:
                self.error.emit(self._classify_error(str(e)))
        finally:
            self._cleanup()

    def stop(self):
        self._stop = True
        try:
            if self._ydl:
                self._ydl.stop_processing()
        except Exception as e:
            print(f"Error stopping yt-dlp: {e}")
        self._cleanup()

    def _classify_error(self, err: str) -> str:
        e = err.lower()

        # Instagram / login-walled platforms
        if any(k in e for k in ("empty media response", "check if this post is accessible",
                                 "cookies-from-browser", "cookies for the authentication")):
            return ("🔒  Login required.\n\n"
                    "This post is private or requires you to be logged in.\n\n"
                    "Only public posts can be downloaded without authentication.")

        if any(k in e for k in ("sign in", "login required", "private video",
                                 "members only", "age-restricted", "age restricted",
                                 "requires authentication")):
            return ("🔒  Login required.\n\n"
                    "This video is private or age-restricted and requires a login to access.\n\n"
                    "Try a different, publicly available video.")

        if any(k in e for k in ("copyright", "not available in your country",
                                 "geo", "geo-restricted", "geoblocked")):
            return ("🌍  Not available in your region.\n\n"
                    "This video is geo-blocked or has been restricted due to copyright.")

        if any(k in e for k in ("video unavailable", "has been removed",
                                 "no longer available", "this video is unavailable")):
            return ("🗑️  Video unavailable.\n\n"
                    "This video may have been deleted or taken down by the uploader.")

        if any(k in e for k in ("unsupported url", "ie_key", "no suitable extractor")):
            return ("🔗  Unsupported URL.\n\n"
                    "This link doesn't appear to point to a supported video.\n"
                    "Please check the URL and try again.")

        if any(k in e for k in ("http error 429", "too many requests", "rate limit")):
            return ("⏳  Rate limited.\n\n"
                    "Too many requests were made. Please wait a few minutes and try again.")

        if any(k in e for k in ("http error 403", "403 forbidden", "forbidden")):
            return ("⛔  Access denied (403).\n\n"
                    "The server refused the request. The video may be restricted "
                    "or the link may have expired.")

        if any(k in e for k in ("http error 404", "not found")):
            return ("❓  Video not found (404).\n\n"
                    "The video could not be found. The link may be broken or the video deleted.")

        if any(k in e for k in ("network", "connection", "timed out", "timeout",
                                 "errno", "socket", "ssl", "certificate verify")):
            return ("🌐  Network error.\n\n"
                    "Could not reach the server. Check your internet connection and try again.")

        if any(k in e for k in ("ffmpeg", "merger", "postprocessor")):
            return ("🎞️  FFmpeg error.\n\n"
                    "FFmpeg failed while processing the video.\n"
                    "Make sure FFmpeg is properly installed and in your PATH.")

        if any(k in e for k in ("no space", "disk full", "permission denied", "read-only",
                                 "winerror 5", "access is denied")):
            return ("💾  Storage error.\n\n"
                    "Could not write to the download folder. Check that you have "
                    "enough disk space and write permissions.")

        # Fallback — strip raw yt-dlp ERROR: prefix and GitHub noise, keep it readable
        cleaned = err
        for noise in ("see  https://github.com", "filling out the appropriate",
                      "confirm you are on the latest", "yt-dlp -u", "yt-dlp -U"):
            if noise.lower() in cleaned.lower():
                cleaned = cleaned[:cleaned.lower().index(noise.lower())].strip(" .\n")
        cleaned = cleaned.replace("ERROR: ", "").strip()
        return f"❌  Download failed.\n\n{cleaned}"

    def _cleanup(self):
        try:
            for file_path in list(self.current_downloaded_files):
                if os.path.exists(file_path):
                    if file_path.endswith((".part", ".ytdl", ".temp", ".tmp", ".webp", ".jpg", ".jpeg", ".png")):
                        os.remove(file_path)
                    elif file_path.endswith((".mp4", ".webm", ".mkv")) and self._stop \
                            and os.path.getsize(file_path) < 200 * 1024:
                        os.remove(file_path)
            if self._stop and os.path.exists(self.output_dir):
                for filename in os.listdir(self.output_dir):
                    if filename.endswith((".part", ".ytdl", ".temp", ".webp")):
                        try:
                            os.remove(os.path.join(self.output_dir, filename))
                        except Exception:
                            pass
        except Exception:
            logging.exception("Video cleanup failed")

    def _make_opts(self, output_dir):
        outtmpl    = os.path.join(output_dir, "%(title)s.%(ext)s")
        fmt        = QUALITY_FORMAT_MAP.get(self.quality, QUALITY_FORMAT_MAP["Best Available"])

        class YtdlpLogger:
            def debug(self, msg): pass
            def warning(self, msg): pass
            def error(self, msg): pass

        # Track whether we already showed the fallback warning this download
        _fallback_warned = {"shown": False}

        def hook(d):
            if self._stop:
                raise Exception("Download cancelled by user.")
            filename = d.get("filename")
            if filename:
                self.current_downloaded_files.add(os.path.abspath(filename))
            if d.get("status") == "downloading":
                downloaded = d.get("downloaded_bytes", 0) or 0
                total      = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                # Show actual resolution being downloaded
                height = d.get("info_dict", {}).get("height") or 0
                res_tag = f" [{height}p]" if height else ""

                # Warn once if actual quality is lower than what was requested
                requested_h = QUALITY_HEIGHT_MAP.get(self.quality, 0)
                if (not _fallback_warned["shown"]
                        and requested_h > 0
                        and height
                        and int(height) < requested_h):
                    _fallback_warned["shown"] = True
                    self.status.emit(
                        f"⚠️  {self.quality} not available for this video. "
                        f"Downloading best available [{height}p] instead..."
                    )
                    return  # let user read the message before progress overwrites it

                if total > 0:
                    pct = (downloaded / total) * 100
                    speed = d.get("speed") or 0
                    speed_str = f" — {speed/1024/1024:.1f} MB/s" if speed > 0 else ""
                    self.progress.emit(pct)
                    self.status.emit(
                        f"[{self.current_index}/{self.total_tracks}] "
                        f"Downloading{res_tag}... {pct:.1f}%{speed_str}"
                    )
            elif d.get("status") == "finished":
                height = d.get("info_dict", {}).get("height") or ""
                res_tag = f" [{height}p]" if height else ""
                self.status.emit(
                    f"[{self.current_index}/{self.total_tracks}] Processing video{res_tag}..."
                )
                self.progress.emit(99.0)
                # Run trim after the file is fully written
                if self.trim_start is not None and self.trim_end is not None:
                    fname = d.get("filename", "")
                    if fname and os.path.exists(fname):
                        self.status.emit(
                            f"[{self.current_index}/{self.total_tracks}] Trimming..."
                        )
                        self._do_trim(fname)

        opts = {
            "format": fmt,
            # Sort candidates: prefer higher resolution, then higher bitrate,
            # then vp9/av1 codec (better quality per bit than avc on YouTube).
            # This ensures yt-dlp picks the best quality stream when multiple
            # formats match the height filter.
            "format_sort": ["res", "br", "vcodec:vp9", "vcodec:av01", "vcodec:avc1"],
            "merge_output_format": "mp4",
            # Explicitly invoke the FFmpeg merger so the video+audio streams are
            # always combined into a single mp4 — without this, yt-dlp can silently
            # skip the merge step and produce a video-only file.
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            ],
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "logger": YtdlpLogger(),
            "progress_hooks": [hook],
            "ffmpeg_location": FFMPEG_CMD,
            "retries": 3,
            "continuedl": True,
            "ignoreerrors": False,
        }

        if self.trim_start is not None and self.trim_end is not None:
            # Store trim info; actual cutting is done in _do_trim() after download
            opts["postprocessors"] = []  # no yt-dlp postprocessor needed

        return opts

    def _do_trim(self, input_path: str) -> str:
        """Cut the downloaded file using ffmpeg. Returns path of trimmed file."""
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_trimmed{ext}"
        cmd = [
            FFMPEG_CMD, "-y",
            "-i", input_path,
            "-ss", str(self.trim_start),
            "-to", str(self.trim_end),
            "-c", "copy",          # stream copy — fast, no re-encode
            output_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=300, check=True, **_no_window())
            os.remove(input_path)
            os.rename(output_path, input_path)
        except Exception as e:
            logging.error(f"Trim failed: {e}")
        return input_path


# ==========================
# VIDEO APP WINDOW
# ==========================
class VideoAppWindow(QtWidgets.QWidget):
    """Main window – trim panel is always visible; preview strip shows real frames."""

    class _AlwaysTrueToggle(QtCore.QObject):
        """Dummy so main.py's trim_toggle references don't break."""
        toggled = QtCore.pyqtSignal(bool)
        def isChecked(self): return True

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube to MP4 Pro")
        self.setFixedSize(850, 500)
        self.setStyleSheet("QWidget { background-color: #0f1117; color: white; }")

        # Dummy trim_toggle keeps main.py happy
        self.trim_toggle = self._AlwaysTrueToggle(self)

        try:
            if os.path.exists(ICON_PATH):
                self.setWindowIcon(QtGui.QIcon(ICON_PATH))
        except Exception as e:
            print(f"Could not load icon: {e}")

        self.output_dir      = DEFAULT_OUTPUT_DIR
        self.worker          = None
        self._info_thread    = None
        self._thumb_thread   = None
        self._stream_thread  = None
        self._frame_thread   = None
        self._video_duration = 0
        self._start_sec      = 0
        self._end_sec        = 0

        # Debounce timer – wait 800ms after typing before fetching
        self._url_timer = QtCore.QTimer()
        self._url_timer.setSingleShot(True)
        self._url_timer.timeout.connect(self._on_url_settled)

        safe_mkdir(self.output_dir)
        self._build_ui()
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(40, 16, 40, 14)
        outer.setSpacing(7)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Title ──────────────────────────────────────────────────────
        title = QLabel(
            "<span style='font-size:36px; font-weight:600; letter-spacing:6px;'>"
            "<span style='color:#4285F4'>Y</span><span style='color:#EA4335'>O</span>"
            "<span style='color:#FBBC05'>U</span><span style='color:#34A853'>T</span>"
            "<span style='color:#4285F4'>U</span><span style='color:#EA4335'>B</span>"
            "<span style='color:#FBBC05'>E</span><span style='color:#34A853'>&nbsp;</span>"
            "<span style='color:#4285F4'>T</span><span style='color:#EA4335'>O</span>&nbsp;"
            "<span style='color:#FBBC05'>M</span><span style='color:#34A853'>P</span>"
            "<span style='color:#4285F4'>4</span><span style='color:#EA4335'>&nbsp;</span>"
            "<span style='color:#FBBC05'>P</span><span style='color:#34A853'>R</span>"
            "<span style='color:#4285F4'>O</span>"
            "</span>"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(title)
        outer.addSpacing(6)

        # ── URL input ──────────────────────────────────────────────────
        self.input_frame = NeonFrame()
        self.input_line  = QtWidgets.QLineEdit()
        self.input_line.setPlaceholderText("🔗 Paste any URL or drag & drop here…")
        self.input_line.setFixedHeight(50)
        self.input_line.setStyleSheet("""
            QLineEdit {
                border: none; padding-left: 18px; font-size: 18px;
                color: #FFFFFF; background-color: transparent; border-radius: 25px;
            }
        """)
        self.input_line.textChanged.connect(self._on_text_changed)
        f = QtWidgets.QHBoxLayout(self.input_frame)
        f.setContentsMargins(5, 2, 5, 2)
        f.addWidget(self.input_line)
        outer.addWidget(self.input_frame)

        # ── Video title label ──────────────────────────────────────────
        self.lbl_video_title = QLabel("")
        self.lbl_video_title.setStyleSheet(
            "color: rgba(255,255,255,0.50); font-size: 11px; padding-left: 2px;"
        )
        self.lbl_video_title.setWordWrap(False)
        outer.addWidget(self.lbl_video_title)

        # ── Quality row ────────────────────────────────────────────────
        options_row = QtWidgets.QHBoxLayout()

        lbl_quality = QLabel("Quality:")
        lbl_quality.setStyleSheet("color:#BDC1C6; font-size:13px;")
        options_row.addWidget(lbl_quality)

        self.quality_combo = QtWidgets.QComboBox()
        self.quality_combo.addItems(VIDEO_QUALITIES)
        self.quality_combo.setCurrentIndex(0)  # default: Best Available
        self.quality_combo.setFixedWidth(160)
        self.quality_combo.setStyleSheet("""
            QComboBox {
                background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.15);
                border-radius: 8px; color: white; padding: 4px 10px; font-size: 13px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #1e2130; color: white;
                selection-background-color: #4285F4;
            }
        """)
        options_row.addWidget(self.quality_combo)
        options_row.addStretch()

        lbl_trim = QLabel("✂  Trim Clip")
        lbl_trim.setStyleSheet("color: rgba(255,255,255,0.55); font-size: 13px;")
        options_row.addWidget(lbl_trim)
        outer.addLayout(options_row)

        # ── Trim panel (always shown) ──────────────────────────────────
        trim_panel = QtWidgets.QWidget()
        trim_inner = QtWidgets.QVBoxLayout(trim_panel)
        trim_inner.setContentsMargins(0, 2, 0, 0)
        trim_inner.setSpacing(4)

        self.range_slider = RangeSlider()
        self.range_slider.range_changed.connect(self._on_range_changed)
        trim_inner.addWidget(self.range_slider)

        time_row = QtWidgets.QHBoxLayout()

        self.lbl_start_time = QLabel("00:00:00")
        self.lbl_start_time.setStyleSheet("""
            color: white; font-size: 12px; font-weight: bold;
            background: rgba(66,133,244,0.15); border: 1px solid rgba(66,133,244,0.3);
            padding: 4px 12px; border-radius: 6px;
        """)

        self.lbl_end_time = QLabel("00:00:00")
        self.lbl_end_time.setStyleSheet("""
            color: white; font-size: 12px; font-weight: bold;
            background: rgba(52,168,83,0.15); border: 1px solid rgba(52,168,83,0.3);
            padding: 4px 12px; border-radius: 6px;
        """)

        self.lbl_dur_status = QLabel("Paste a URL above to load duration")
        self.lbl_dur_status.setStyleSheet("color: rgba(255,255,255,0.30); font-size: 11px;")
        self.lbl_dur_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        time_row.addWidget(self.lbl_start_time)
        time_row.addStretch()
        time_row.addWidget(self.lbl_dur_status)
        time_row.addStretch()
        time_row.addWidget(self.lbl_end_time)
        trim_inner.addLayout(time_row)
        outer.addWidget(trim_panel)

        # ── Download path row ──────────────────────────────────────────
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
            QPushButton { color:#4285F4; background:transparent; border:none; font-size:14px; }
            QPushButton:hover { color:#34A853; }
        """)
        self.btn_change.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_change.clicked.connect(self.change_path)
        path_row.addWidget(self.btn_change)
        outer.addLayout(path_row)
        outer.addSpacing(8)

        # ── Buttons ────────────────────────────────────────────────────
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        btn_row.setSpacing(22)

        self.btn_download = QtWidgets.QPushButton("Download MP4")
        self.btn_download.setFixedSize(220, 52)
        self.btn_download.setStyleSheet("""
            QPushButton {
                font-size:17px; font-weight:500; border:2px solid transparent;
                border-radius:26px; padding:10px; color:white;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4285F4,stop:1 #34A853);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #5a95f5,stop:1 #46b863);
            }
            QPushButton:disabled {
                background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.25);
            }
        """)
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self.start_download)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(66, 133, 244, 140))
        self.btn_download.setGraphicsEffect(shadow)
        btn_row.addWidget(self.btn_download)

        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.setFixedSize(160, 52)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                font-size:17px; font-weight:500; border:2px solid #4285F4;
                color:#4285F4; border-radius:26px; padding:10px; background:transparent;
            }
            QPushButton:hover { background:rgba(66,133,244,40%); border:2px solid #34A853; color:#34A853; }
            QPushButton:pressed { background:rgba(52,168,83,60%); border:2px solid #0F9D58; color:#0F9D58; }
            QPushButton:disabled { border-color:rgba(255,255,255,0.15); color:rgba(255,255,255,0.2); }
        """)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_download)
        btn_row.addWidget(self.btn_cancel)
        outer.addLayout(btn_row)

        # ── Status row ─────────────────────────────────────────────────
        status_row = QtWidgets.QHBoxLayout()
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color:rgba(255,255,255,0.85); font-size:14px; padding-left:4px;")
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()
        self.lbl_skipped = QLabel("")
        self.lbl_skipped.setStyleSheet("color:#FBBC05; font-size:13px; font-weight:bold; padding-right:4px;")
        self.lbl_skipped.setVisible(False)
        status_row.addWidget(self.lbl_skipped)
        outer.addLayout(status_row)
        outer.addSpacing(4)

        # ── Progress bar ───────────────────────────────────────────────
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet("""
            QProgressBar { background:rgba(255,255,255,0.08); border:none; border-radius:3px; }
            QProgressBar::chunk { border-radius:3px;
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4285F4,stop:1 #34A853); }
        """)
        outer.addWidget(self.progress)
        outer.addSpacing(8)

        # ── Footer ─────────────────────────────────────────────────────
        footer_container = QtWidgets.QWidget()
        footer_layout    = QtWidgets.QVBoxLayout(footer_container)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(2)

        footer = QLabel(
            "YouTube Only <span style='color:#FBBC05;'>•</span> "
            "MP4 - Best Quality <span style='color:#FBBC05;'>•</span> "
            "Trim Support <span style='color:#FBBC05;'>•</span> "
            "Drag & Drop Enabled"
        )
        footer.setStyleSheet("color:#BDC1C6; font-size:12px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        contact_label = QLabel(
            'If you face any error, <a href="https://raja5667.github.io/MONO/contact.html" '
            'style="color:#4285F4; text-decoration:none;">contact us</a>.'
        )
        contact_label.setStyleSheet("color:#BDC1C6; font-size:11px;")
        contact_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contact_label.setOpenExternalLinks(True)

        footer_layout.addWidget(footer)
        footer_layout.addWidget(contact_label)
        outer.addWidget(footer_container)

    # ------------------------------------------------------------------
    # URL debounce
    # ------------------------------------------------------------------
    def _on_text_changed(self, text: str):
        self._url_timer.stop()
        if text.strip():
            self._url_timer.start(800)
        else:
            self._reset_preview()

    def _is_youtube_url(self, url: str) -> bool:
        import re
        return bool(re.search(r'(youtube\.com|youtu\.be)', url, re.IGNORECASE))

    def _on_url_settled(self):
        url = self.input_line.text().strip()
        if not url:
            return
        if not self._is_youtube_url(url):
            self._stop_bg_threads()
            self._video_duration = 0
            self._start_sec = None
            self._end_sec   = None
            self.lbl_video_title.setText("")
            self.lbl_dur_status.setText("Only YouTube URLs are supported")
            self.lbl_dur_status.setStyleSheet("color: #FF6B6B; font-size: 11px;")  # red
            self.lbl_start_time.setText("--:--:--")
            self.lbl_end_time.setText("--:--:--")
            self.range_slider.set_placeholder(
                "⚠️  Only YouTube URLs are supported",
                QColor(255, 107, 107, 220)   # red
            )
        else:
            self._fetch_video_info(url)

    # ------------------------------------------------------------------
    # Video info / preview fetching
    # ------------------------------------------------------------------
    def _stop_bg_threads(self):
        # Signal the frame extractor to stop cleanly first
        if self._frame_thread and self._frame_thread.isRunning():
            self._frame_thread.stop()
        for t in (self._info_thread, self._thumb_thread,
                  self._stream_thread, self._frame_thread):
            if t:
                try:
                    t.disconnect()   # detach all signals to prevent stale callbacks
                except Exception:
                    pass
                if t.isRunning():
                    t.terminate()
                    t.wait(300)

    def _fetch_video_info(self, url: str):
        self._stop_bg_threads()
        self.lbl_dur_status.setText("Loading…")
        self.lbl_dur_status.setStyleSheet("color: #4285F4; font-size: 11px;")   # blue
        self.lbl_video_title.setText("")
        self.range_slider.set_placeholder(
            "Loading video info…",
            QColor(66, 133, 244, 200)   # blue
        )

        self._info_thread = ThumbnailLoader(url)
        self._info_thread.info_ready.connect(self._on_info_ready)
        self._info_thread.error.connect(self._on_info_error)
        self._info_thread.start()

    def _on_info_ready(self, duration: int, thumb_url: str, title: str, available_heights: list):
        # Duration
        if duration > 0:
            self._video_duration = duration
            self.range_slider.set_duration(duration)
            self._start_sec = 0
            self._end_sec   = duration
            self.lbl_dur_status.setText(f"Total: {fmt_time(duration)}")
            self.lbl_dur_status.setStyleSheet("color: #34A853; font-size: 11px;")  # green
            self.lbl_start_time.setText(fmt_time(0))
            self.lbl_end_time.setText(fmt_time(duration))
        else:
            self.lbl_dur_status.setText("Could not fetch duration")
            self.lbl_dur_status.setStyleSheet("color: #FF6B6B; font-size: 11px;")  # red

        # Title
        if title:
            display = title if len(title) <= 62 else title[:59] + "…"
            self.lbl_video_title.setText(display)

        # Enable / disable quality options based on what the video actually has.
        # A quality tier is enabled if at least one format matches its max height.
        # "Best Available" is always enabled.
        if available_heights:
            max_available = max(available_heights)
            model = self.quality_combo.model()
            for i in range(self.quality_combo.count()):
                label = self.quality_combo.itemText(i)
                if label == "Best Available":
                    item_enabled = True
                else:
                    req_h = QUALITY_HEIGHT_MAP.get(label, 0)
                    # Enable the tier if the video has a stream at or above that height,
                    # meaning the video can fulfil this quality level.
                    item_enabled = max_available >= req_h
                item = model.item(i)
                if item:
                    item.setEnabled(item_enabled)
                    # Dim disabled items visually
                    item.setForeground(
                        QtGui.QColor("#FFFFFF") if item_enabled else QtGui.QColor("#555870")
                    )
            # If currently selected quality is now disabled, switch to Best Available
            current_label = self.quality_combo.currentText()
            if current_label != "Best Available":
                req_h = QUALITY_HEIGHT_MAP.get(current_label, 0)
                if max_available < req_h:
                    self.quality_combo.setCurrentIndex(0)  # Best Available

        # Build timestamps for filmstrip inside the slider
        if duration > 0:
            n          = NUM_FRAMES
            step       = duration / (n + 1)
            timestamps = [int(step * (i + 1)) for i in range(n)]
        else:
            timestamps = []

        self.range_slider.set_loading(timestamps)

        # Step 1: quickly fill strip with thumbnail while real frames load
        if thumb_url and timestamps:
            self._thumb_thread = ThumbnailDownloader(thumb_url)
            self._thumb_thread.pixmap_ready.connect(
                lambda px: self._apply_thumbnail_placeholder(px, timestamps)
            )
            self._thumb_thread.start()
        elif timestamps:
            # No thumbnail – go straight to frame extraction
            self._start_frame_extraction(timestamps, duration)

    def _apply_thumbnail_placeholder(self, thumb_px: QPixmap, timestamps: list):
        """Fill filmstrip slots with thumbnail as a placeholder, then fetch real frames."""
        if not thumb_px.isNull():
            self.range_slider.set_frames([(ts, thumb_px) for ts in timestamps])

        # Step 2: fetch real frames via ffmpeg
        url = self.input_line.text().strip()
        if url and check_ffmpeg():
            self._start_frame_extraction(timestamps, self._video_duration)

    def _start_frame_extraction(self, timestamps: list, duration: int):
        url = self.input_line.text().strip()
        if not url:
            return
        self._stream_thread = StreamUrlFetcher(url)
        self._stream_thread.url_ready.connect(
            lambda su, _: self._on_stream_ready(su, timestamps, duration)
        )
        self._stream_thread.start()

    def _on_stream_ready(self, stream_url: str, timestamps: list, duration: int):
        if not stream_url or not timestamps:
            return
        self._frame_thread = FrameExtractor(stream_url, timestamps, duration)
        # Progressive: each frame updates the slider as it arrives
        self._frame_thread.frame_ready.connect(self.range_slider.set_frames)
        self._frame_thread.frames_ready.connect(self.range_slider.set_frames)
        self._frame_thread.start()

    def _on_info_error(self, _err: str):
        self.lbl_dur_status.setText("⚠️  Could not fetch video info")
        self.lbl_dur_status.setStyleSheet("color: #FF6B6B; font-size: 11px;")   # red
        self.range_slider.set_placeholder(
            "Could not load preview — URL may be invalid or video unavailable",
            QColor(255, 107, 107, 200)   # red
        )

    def _reset_preview(self):
        self._stop_bg_threads()
        self._video_duration = 0
        self._start_sec = 0
        self._end_sec   = 0
        self.lbl_video_title.setText("")
        self.lbl_dur_status.setText("Paste a URL above to load duration")
        self.lbl_dur_status.setStyleSheet("color: rgba(255,255,255,0.30); font-size: 11px;")
        self.lbl_start_time.setText("00:00:00")
        self.lbl_end_time.setText("00:00:00")
        self.range_slider.set_duration(1)
        self.range_slider.set_placeholder()
        # Re-enable all quality options when URL is cleared
        model = self.quality_combo.model()
        for i in range(self.quality_combo.count()):
            item = model.item(i)
            if item:
                item.setEnabled(True)
                item.setForeground(QtGui.QColor("#FFFFFF"))

    # ------------------------------------------------------------------
    # Range slider callback
    # ------------------------------------------------------------------
    def _on_range_changed(self, start: int, end: int):
        self._start_sec = start
        self._end_sec   = end
        self.lbl_start_time.setText(fmt_time(start))
        self.lbl_end_time.setText(fmt_time(end))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def change_path(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select download folder", str(self.output_dir)
        )
        if path:
            self.output_dir = Path(path)
            self.lbl_path_value.setText(str(self.output_dir))

    def start_download(self):
        if not check_ffmpeg():
            QtWidgets.QMessageBox.critical(
                self, "FFmpeg Missing",
                "🎞️  FFmpeg was not found.\n\n"
                "FFmpeg is required to merge video and audio streams.\n"
                "Please install FFmpeg and make sure it's in your system PATH."
            )
            return
        if not check_internet():
            QtWidgets.QMessageBox.critical(
                self, "No Internet Connection",
                "🌐  You appear to be offline.\n\n"
                "Please check your internet connection and try again."
            )
            self.lbl_status.setText("❌  No internet connection")
            return

        url = self.input_line.text().strip()
        if not url:
            self.lbl_status.setText("⚠️  Please paste a YouTube URL first.")
            return
        if not url.startswith(("http://", "https://")):
            self.lbl_status.setText("⚠️  URL must start with http:// or https://")
            return
        if not self._is_youtube_url(url):
            self.lbl_status.setText("⚠️  Only YouTube URLs are supported.")
            return

        safe_mkdir(self.output_dir)
        quality = self.quality_combo.currentText()

        # Apply trim only if YouTube video and user actually moved the handles
        trim_start = None
        trim_end   = None
        if (self._video_duration > 0
                and self._start_sec is not None
                and self._end_sec is not None):
            if self._start_sec > 0 or self._end_sec < self._video_duration:
                trim_start = self._start_sec
                trim_end   = self._end_sec

        self.worker = VideoDownloadWorker(url, str(self.output_dir), quality, trim_start, trim_end)
        self.worker.progress.connect(lambda pct: self.progress.setValue(int(pct)))
        self.worker.status.connect(self.lbl_status.setText)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)

        self.lbl_skipped.setText("")
        self.lbl_skipped.setVisible(False)
        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.lbl_status.setText("Queued")
        self.progress.setValue(0)
        self.worker.start()

    def cancel_download(self):
        if self.worker and self.worker.isRunning():
            try:
                self.worker.stop()
                self.worker.wait(3000)
            except Exception as e:
                print(f"Error stopping worker: {e}")
        self.lbl_status.setText("Cancelled")
        self.lbl_skipped.setVisible(False)
        self.progress.setValue(0)
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    def _on_finished(self, msg):
        self.progress.setValue(100)
        self.lbl_status.setText(f"✅  {msg}")
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        QtCore.QTimer.singleShot(6000, self._reset_ui)

    def _on_error(self, err):
        cancelled_keywords = ("cancelled by user", "cancelled", "stopped")
        is_cancel = any(k in err.lower() for k in cancelled_keywords)
        if not is_cancel:
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Download Failed")
            msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            msg.setText(err)
            msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            msg.setStyleSheet("""
                QMessageBox { background-color: #1a1d2e; color: white; }
                QMessageBox QLabel { color: white; font-size: 13px; min-width: 340px; }
                QPushButton {
                    background: #4285F4; color: white; border: none;
                    border-radius: 6px; padding: 6px 22px; font-size: 13px;
                }
                QPushButton:hover { background: #5a95f5; }
            """)
            msg.exec()
            self.lbl_status.setText("❌  Download failed")
        else:
            self.lbl_status.setText("⏹  Cancelled")
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    def _reset_ui(self):
        # Only clear if the URL is the same one that was just downloaded
        # (user may have already pasted a new URL)
        self.progress.setValue(0)
        self.lbl_status.setText("Ready")
        self.lbl_skipped.setVisible(False)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        url = ""
        if e.mimeData().hasUrls():
            url = e.mimeData().urls()[0].toString()
        elif e.mimeData().hasText():
            url = e.mimeData().text()
        self.input_line.setText(url)

    def closeEvent(self, event):
        self._url_timer.stop()
        self._stop_bg_threads()
        if self.worker and self.worker.isRunning():
            try:
                self.worker.stop()
                self.worker.wait(500)
            except Exception:
                pass
        event.accept()