# YTMP3 Pro Suite

<p align="center">
  <img src="app_icon.ico" alt="Application Icon" width="128" height="128">
  <br>
  <b>An advanced, asynchronous PyQt6 desktop suite for high-fidelity YouTube audio and video extraction.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Framework-PyQt6-00D2B4?style=for-the-badge&logo=qt&logoColor=white">
  <img src="https://img.shields.io/badge/Engine-yt--dlp-FF0000?style=for-the-badge&logo=youtube&logoColor=white">
  <img src="https://img.shields.io/badge/OS-Windows%2010%20%2F%2011-0078D4?style=for-the-badge&logo=windows&logoColor=white">
</p>

---

## 🚀 Key Features

### 🎵 MP3 Downloader
* **High-Fidelity Audio Extraction** – Converts YouTube audio streams into pure 320kbps MP3 format.
* **Live Audio Preview Engine** – Built-in VLC-based asynchronous preview before download.
* **Advanced Playlist Processing** – Handles full playlists with sequential queue management.
* **Dynamic Audio Boost** – FFmpeg-powered real-time gain control (100%–200% safe amplification).
* **Smart Metadata Tagging** – Auto-fetches thumbnails and embeds them into MP3 ID3 tags.

### 🎬 MP4 Downloader
* **High-Quality Video Download** – Supports Best Available, 1080p, 720p, 480p, 360p, 240p, 144p.
* **Video Trim Panel** – Dual-handle range slider to trim video before downloading via FFmpeg.
* **Thumbnail Preview** – Live seek-based thumbnail preview from the video timeline.
* **Silent FFmpeg Processing** – No terminal window pops up during processing.
* **YouTube Authentication** – Bundled cookies support for accessing all available quality streams.

### 💎 General
* **Tabbed Interface** – Single window launcher switching between MP3 and MP4 tools.
* **Modern UI/UX** – Neon animated interface with drag & drop URL support and live progress tracking.
* **Thread-Safe Cancellation** – Instantly stops downloads without freezing the UI.
* **Zero Configuration** – Bundled FFmpeg, VLC, Deno, and cookies; no system setup required for end users.

---

## 🛠️ System Requirements

* **OS:** Windows 10 / 11 (64-bit)
* **Python:** 3.11 or 3.12
* **Internet:** Required for YouTube access

> ⚠️ **Warning:** Python 3.13+ is not recommended due to potential compatibility issues with PyQt6 and PyInstaller.

---

## 📁 Repository Structure

```text
YT-MP3/
│
├── main.py                 # App launcher — tabbed MP3 + MP4 interface
├── youtube_to_mp3_pro.py   # MP3 downloader UI & logic
├── youtube_to_mp4_pro.py   # MP4 downloader UI & logic
├── ffmpeg.exe              # Local media processing engine
├── deno.exe                # JavaScript runtime for YouTube challenge solving
├── cookies.txt             # YouTube authentication cookies (Netscape format)
├── VLC/                    # Bundled VLC engine (libvlc.dll + plugins/)
├── YTMP3-Pro.spec          # PyInstaller build configuration
├── requirements.txt        # Python dependencies
├── app_icon.ico            # App icon asset
├── .gitignore              # Git exclusions
└── README.md               # Documentation
```

---

## 🔧 Installation & Setup (Development)

### 1. Clone Repository

```bash
git clone https://github.com/raja5667/YT-MP3.git
cd YT-MP3
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### 3. Activate Environment

```bash
venv\Scripts\activate
```

### 4. Install Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
pip install "yt-dlp[default]"
pip install yt-dlp-ejs==0.8.0
```

### 5. Add Required Files

Before running or building, make sure these files are in the project root:

* **`deno.exe`** — Download from [deno.land/releases](https://github.com/denoland/deno/releases) (`deno-x86_64-pc-windows-msvc.zip`)
* **`cookies.txt`** — Export from YouTube while logged in using the [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) Chrome extension

### 6. Run Application

```bash
python main.py
```

---

## 📦 Build Standalone EXE (PyInstaller)

This project uses a `.spec` file to bundle VLC, FFmpeg, Deno, EJS scripts, cookies, and all dependencies into a **single portable `.exe`** — no installation required for end users.

### Prerequisites

```bash
pip install pyinstaller
pip install "yt-dlp[default]"
pip install yt-dlp-ejs==0.8.0
```

### Build Executable

```bash
pyinstaller YTMP3-Pro.spec
```

📁 Output will be at:

```
dist/YTMP3-Pro.exe
```

> ✅ The output `.exe` is fully self-contained. Share only `dist/YTMP3-Pro.exe` — users do **not** need Python, VLC, FFmpeg, or Deno installed.

> ⚠️ Expected file size is **150–250 MB** due to bundled VLC plugins and Deno runtime. This is normal.

> 🍪 **Cookies Notice:** The bundled `cookies.txt` is your personal YouTube session. It expires over time (typically months). When quality degrades or errors appear, re-export a fresh `cookies.txt` and rebuild the EXE.

---

## ⚙️ Internal Processing Overview

### 🔐 YouTube Authentication

The app bundles a `cookies.txt` file (Netscape format) exported from a logged-in YouTube session. This allows yt-dlp to access all available quality streams (up to 1080p). Without valid cookies, YouTube may limit formats or block requests.

### ⚡ JavaScript Challenge Solving

YouTube uses JavaScript-based obfuscation challenges (n-challenge and signature) to protect video streams. The app bundles:
- **Deno** — a secure JavaScript runtime
- **yt-dlp-ejs** — the official EJS challenge solver scripts

Together these solve YouTube's JS challenges at runtime, unlocking all available formats.

### 🧹 Workspace Sanitization Engine

Automatically removes temporary `.part`, `.ytdl`, and cache files after download completion or cancellation.

### 🔊 Post-Processing Audio Pipeline

Audio boost is applied via FFmpeg on a duplicated output stream to prevent corruption of original media headers.

### 🧵 Thread Safety System

All downloads run asynchronously with safe interruption handling to prevent UI freezing or crashes.

### 📦 VLC Bundling

VLC is bundled inside the exe via `YTMP3-Pro.spec`. The app detects whether it is running frozen (compiled) or from source and resolves VLC paths accordingly using `sys._MEIPASS`. The VLC setup runs once in `main.py` before either module is imported.

### 🔇 Silent FFmpeg

All FFmpeg subprocess calls use `CREATE_NO_WINDOW` and `STARTUPINFO` flags to suppress terminal windows during video trimming and thumbnail extraction.

---

## 🍪 Refreshing Cookies (When Quality Degrades)

YouTube cookies expire. If the app starts returning fewer quality options or errors:

1. Open Chrome and go to [youtube.com](https://youtube.com) while logged in
2. Click the **Get cookies.txt LOCALLY** extension
3. Export cookies for `youtube.com`
4. Replace `cookies.txt` in the project folder
5. Rebuild: `pyinstaller YTMP3-Pro.spec`

---

## 📄 License

This project is licensed under the **MIT License**.

---

## 👨‍💻 Author

**Dhrubajyoti Das**
GitHub: [@raja5667](https://github.com/raja5667)
