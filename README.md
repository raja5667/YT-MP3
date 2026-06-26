# YouTube to MP3 Pro

<p align="center">
  <img src="app_icon.ico" alt="Application Icon" width="128" height="128">
  <br>
  <b>An advanced, asynchronous PyQt6 desktop application designed for high-fidelity YouTube audio extraction and media management.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Framework-PyQt6-00D2B4?style=for-the-badge&logo=qt&logoColor=white">
  <img src="https://img.shields.io/badge/Engine-yt--dlp-FF0000?style=for-the-badge&logo=youtube&logoColor=white">
  <img src="https://img.shields.io/badge/OS-Windows%2010%20%2F%2011-0078D4?style=for-the-badge&logo=windows&logoColor=white">
</p>

---

## 🚀 Key Features

* 🎵 **High-Fidelity Audio Extraction** – Converts YouTube audio streams into pure 320kbps MP3 format.
* ▶️ **Live Audio Preview Engine** – Built-in VLC-based asynchronous preview before download.
* 📂 **Advanced Playlist Processing** – Handles full playlists with sequential queue management.
* 🔊 **Dynamic Audio Boost** – FFmpeg-powered real-time gain control (100%–200% safe amplification).
* 🏷️ **Smart Metadata Tagging** – Auto-fetches thumbnails and embeds them into MP3 ID3 tags.
* 💎 **Modern UI/UX** – Neon animated interface with drag & drop URL support and live progress tracking.
* 🧵 **Thread-Safe Cancellation** – Instantly stops downloads without freezing the UI.
* 📦 **Zero Configuration Setup** – Bundled FFmpeg and VLC included; no system setup required for end users.

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
├── youtube_to_mp3_pro.py   # Core UI & threading logic
├── ffmpeg.exe              # Local media processing engine
├── VLC/                    # Bundled VLC engine (libvlc.dll + plugins/)
├── YT-MP3.spec             # PyInstaller build configuration
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
```

### 5. Run Application

```bash
python youtube_to_mp3_pro.py
```

---

## 📦 Build Standalone EXE (PyInstaller)

This project uses a `.spec` file to bundle VLC, FFmpeg, and all dependencies into a **single portable `.exe`** — no installation required for end users.

### Prerequisites

```bash
pip install pyinstaller
```

### Build Executable

```bash
pyinstaller YT-MP3.spec
```

📁 Output will be at:

```
dist/YT-MP3.exe
```

> ✅ The output `.exe` is fully self-contained. Share only `dist/YT-MP3.exe` — users do **not** need Python, VLC, or FFmpeg installed.

> ⚠️ Expected file size is **100–200 MB** due to bundled VLC plugins. This is normal.

---

## ⚙️ Internal Processing Overview

### 🧹 Workspace Sanitization Engine

Automatically removes temporary `.part`, `.ytdl`, and cache files after download completion or cancellation.

### 🔊 Post-Processing Audio Pipeline

Audio boost is applied via FFmpeg on a duplicated output stream to prevent corruption of original media headers.

### 🧵 Thread Safety System

All downloads run asynchronously with safe interruption handling to prevent UI freezing or crashes.

### 📦 VLC Bundling

VLC is bundled inside the exe via `YT-MP3.spec`. The app detects whether it is running frozen (compiled) or from source and resolves VLC paths accordingly using `sys._MEIPASS`.

---

## 📄 License

This project is licensed under the **MIT License**.

---

## 👨‍💻 Author

**Raja**
GitHub: [@raja5667](https://github.com/raja5667)
