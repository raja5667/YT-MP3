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
* **In-App Rating Prompt** – Asks for a star rating after repeat downloads and feeds it into a live average shown on the [download page](https://www.getdownloadaid.com/download).
* **Windows Installer** – Distributed as a proper Inno Setup installer with Start Menu shortcuts, an "Add or Remove Programs" entry, and clean uninstall support.
* **Single-Instance Enforcement** – Launching the app while it's already running just brings the existing window to the front instead of opening a duplicate.

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
├── YTMP3-Pro.spec          # PyInstaller build configuration (onedir)
├── YTMP3-Pro.iss           # Inno Setup installer script
├── build_release.ps1       # One-command release build (PyInstaller + Inno Setup)
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

### 6. Configure Rating Backend

The in-app rating dialog submits stars to a Firebase Realtime Database so the average can be displayed on the website. In `main.py`, set:

```python
RATINGS_DB_URL = "https://YOUR-PROJECT-default-rtdb.<region>.firebasedatabase.app"
```

to your own Firebase project's database URL (Firebase console → **Build → Realtime Database**). The same URL must also be set as `RATINGS_DB_URL` in the website's `download.js`, or ratings submitted by the app won't show up on the site. See [Rating System](#-in-app-rating-system) below for the required database rules.

### 7. Run Application

```bash
python main.py
```

---

## 📦 Build the App (PyInstaller — onedir)

This project uses a `.spec` file to bundle VLC, FFmpeg, Deno, EJS scripts, cookies, and all dependencies into a **folder build** (`onedir` mode, not `onefile`). Onedir avoids the self-extracting-archive behavior that triggers false-positive malware flags on single-file exes, and it also starts faster since nothing has to be unpacked to a temp folder on every launch.

### Prerequisites

```bash
pip install pyinstaller
pip install "yt-dlp[default]"
pip install yt-dlp-ejs==0.8.0
```

### Build

```bash
pyinstaller YTMP3-Pro.spec
```

📁 Output will be at:

```
dist/YTMP3-Pro/
├── YTMP3-Pro.exe     # launcher — needs the rest of this folder next to it
└── _internal/        # Python runtime, VLC, FFmpeg, Deno, yt-dlp, etc.
```

> ⚠️ This folder is **not** meant to be handed to end users directly — it must be packaged into the installer (next section) before distribution. `YTMP3-Pro.exe` alone will not run without `_internal/` next to it.

> ⚠️ Expected total folder size is **150–250 MB** due to bundled VLC plugins and Deno runtime. This is normal.

> 🍪 **Cookies Notice:** The bundled `cookies.txt` is your personal YouTube session. It expires over time (typically months). When quality degrades or errors appear, re-export a fresh `cookies.txt` and rebuild.

---

## 💿 Build the Installer (Inno Setup)

The onedir build above is packaged into a single Windows installer using [Inno Setup](https://jrsoftware.org/isinfo.php). This is the **only file distributed to end users** — it installs to Program Files (or per-user AppData if installing without admin rights), adds Start Menu / Desktop shortcuts, registers in "Add or Remove Programs," and includes a clean uninstaller.

### Prerequisites

* [Inno Setup](https://jrsoftware.org/isdl.php) installed
* A completed PyInstaller build (`dist/YTMP3-Pro/` must already exist — build that first)

### Build the Installer

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" YTMP3-Pro.iss
```

📁 Output installer will be at:

```
Output/YTMP3-Pro-Setup-<version>.exe
```

### One-Command Release Build

`build_release.ps1` runs both steps above in order (cleans old `build`/`dist`, runs PyInstaller, then ISCC):

```powershell
.\build_release.ps1
```

> ✅ Upload only `Output/YTMP3-Pro-Setup-<version>.exe` as the GitHub release asset — that's the single file users download from getdownloadaid.com. The in-app updater (see below) expects the release's `.exe` asset to be this installer, not a raw portable exe.

> 🔒 **Not code-signed.** Windows SmartScreen may show an "Unknown publisher" warning on first downloads until the file builds enough reputation from download volume over time. This is separate from antivirus detections and isn't fixable without a paid code-signing certificate.

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

### 🪟 Single-Instance Enforcement

On launch, the app checks for an existing instance via a local socket (`QLocalServer`/`QLocalSocket`, socket name `YTMP3Pro-SingleInstance`). If one is already running, the new launch just signals it to come to the front (`showNormal` / `raise_` / `activateWindow`) and exits, so users never end up with two windows open at once — including right after an installer update closes and would otherwise leave a stale window behind.

### 🔄 Auto-Update Flow

The in-app updater checks GitHub Releases for a newer version, and if found, downloads the release's `.exe` asset (the Inno Setup installer, per the build process above) to the user's Downloads folder. It does **not** attempt to self-replace the running exe — the user closes the app and runs the downloaded installer, which detects the existing install (same Inno Setup `AppId`) and updates it in place, preserving shortcuts and the "Add or Remove Programs" entry.

### 📦 VLC Bundling

VLC is bundled inside the exe via `YTMP3-Pro.spec`. The app detects whether it is running frozen (compiled) or from source and resolves VLC paths accordingly using `sys._MEIPASS`. The VLC setup runs once in `main.py` before either module is imported.

### 🔇 Silent FFmpeg

All FFmpeg subprocess calls use `CREATE_NO_WINDOW` and `STARTUPINFO` flags to suppress terminal windows during video trimming and thumbnail extraction.

### ⭐ In-App Rating System

After a set number of successful downloads (default: 5, tracked persistently via `QSettings`), the app shows a 5-star rating dialog. Tapping a star:

1. Submits `{stars, ts}` to Firebase Realtime Database in a background thread — the UI never blocks on it, and a failed submit (e.g. no internet) is dropped silently rather than shown as an error
2. Opens the GitHub repo so the user can also drop a repo star
3. Marks the user as "already rated" locally, so the prompt never shows again on that machine

The website's download page reads all submitted ratings, averages them, and renders a Play-Store-style badge (partial-filled stars + numeric average + rating count). Both sides must point at the same `RATINGS_DB_URL` — see step 6 in Installation & Setup above.

Required Firebase Realtime Database rules (restricts writes to valid 1–5 star values, leaves everything else locked):

```json
{
  "rules": {
    "ratings": {
      ".read": true,
      ".write": true,
      "$rating_id": {
        ".validate": "newData.hasChildren(['stars','ts']) && newData.child('stars').isNumber() && newData.child('stars').val() >= 1 && newData.child('stars').val() <= 5"
      }
    }
  }
}
```

> ⚠️ These rules allow anyone with the database URL to submit a rating directly via REST, not just through the app. That's an accepted tradeoff for a lightweight indie project — if abuse ever becomes a real problem, look into Firebase App Check or adding basic per-device rate limiting.

---

## 🍪 Refreshing Cookies (When Quality Degrades)

YouTube cookies expire. If the app starts returning fewer quality options or errors:

1. Open Chrome and go to [youtube.com](https://youtube.com) while logged in
2. Click the **Get cookies.txt LOCALLY** extension
3. Export cookies for `youtube.com`
4. Replace `cookies.txt` in the project folder
5. Rebuild: `.\build_release.ps1` (or run the PyInstaller + ISCC steps separately — see [Build the App](#-build-the-app-pyinstaller--onedir))

---

## 📄 License

This project is licensed under the **MIT License**.

---

## 👨‍💻 Author

**Dhrubajyoti Das**
GitHub: [@raja5667](https://github.com/raja5667)
