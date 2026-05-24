# YouTube to MP3 Pro H

<p align="center">
  <img src="app_icon.ico" alt="Application Icon" width="128" height="128">
  <br>
  <b>An advanced, asynchronous PyQt6 desktop application designed for high-fidelity YouTube audio extraction and media management.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Support">
  <img src="https://img.shields.io/badge/Framework-PyQt6-00D2B4?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6 Framework">
  <img src="https://img.shields.io/badge/Engine-yt--dlp-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="yt-dlp Core">
  <img src="https://img.shields.io/badge/OS-Windows%2010%20%2F%2011-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Windows Platform">
</p>

---

## 🚀 Key Features

* **High-Fidelity Audio Extraction** – Downloads and processes audio streams into pure 320kbps MP3 format natively.
* **Live Audio Preview Engine** – Built-in asynchronous VLC engine to instantly stream and listen to tracks directly within the application before initiating a download.
* **Advanced Playlist Processing** – Seamlessly parses multi-track YouTube playlists, handling queue management and downloads sequentially.
* **Dynamic Audio Boost** – Integrated FFmpeg amplifier slider allowing safe real-time audio gain adjustments from 100% up to 200% post-conversion.
* **Smart Metadata & Tagging** – Automatically fetches and embeds high-resolution video thumbnails directly into the final MP3 ID3 tags.
* **Interactive UX/UI** – Fluid Neon-animated border design with real-time text scroll updates, tracking progress bars, and full Drag & Drop link entry support.
* **Thread-Safe Cancellation** – Instantly halts operations and terminates network handles during single or batch playlist cycles without interface lockups.
* **Zero-Configuration Portability** – Self-contained runtime setup including an isolated local FFmpeg binary environment—no system environment variables or installation required.

---

## 🛠️ System Requirements

* **Operating System**: Windows 10 or Windows 11 (64-bit)
* **Python Runtime**: Python `3.11` or `3.12`
* **Network**: Active broadband internet connection

> [!WARNING]  
> Do not use Python 3.13+ or Python 3.14+ runtime environments, as structural changes in newer versions may cause library and wrapper compatibility drops with PyQt6 or PyInstaller hooks.

---

## 📁 Repository Architecture

```text
YouTube-To-MP3-ProH/
│
├── youtube_to_mp3_proh.py   # Core UI & Threading Controller Logic
├── ffmpeg.exe               # Localized FFmpeg Media Processing Engine
├── requirements.txt         # Project Dependencies & Bindings
├── app_icon.ico             # Application Resource Asset
├── .gitignore               # Build Environment Target Exclusions
└── README.md                # Project Documentation Portal
🔧 Installation & Environment Setup
Follow these structured terminal commands to isolate dependencies inside a dedicated virtual environment setup:

1. Clone the Source Repository
Bash
git clone [https://github.com/raja5667/YT-MP3.git](https://github.com/raja5667/YT-MP3.git)
cd YT-MP3
2. Configure Virtual Workspace
Bash
python -m venv venv
3. Initialize Runtime Context
Bash
# Activate workspace environment
venv\Scripts\activate
4. Build Dependency Trees
Bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
5. Launch Application Core
Bash
python youtube_to_mp3_proh.py
📦 Producing Standalone Binary Bundles (.exe)
To package your application into an isolated, standalone portable Windows execution binary package with fully embedded media engines, execute the production build pipeline configuration using PyInstaller:

Bash
# Install PyInstaller deployment toolchain
pip install pyinstaller

# Generate clean production binary matrix
pyinstaller --onefile --windowed --icon=app_icon.ico --add-binary "ffmpeg.exe;." --name "YT-MP3" youtube_to_mp3_proh.py
The compiled target distribution bundle will generate inside the isolated project output root folder directory: dist/.

⚙️ Structural Processing Mechanics
Workspace Sanitization Engine: The automation engine binds a structural finally monitoring matrix that scans local storage targets upon thread completion or user abort, scrubbing orphaned .part, .ytdl, or multimedia image cached layouts out of directories immediately.

Post-Processing Volume Mapping: Volume level adjustment filters apply calculations over a structural internal duplicate configuration algorithm (_boosted.mp3) rather than mutating open file handles directly, protecting media headers from write collisions or premature termination runtime drops.

📄 License
This distribution layout structure is licensed under the open MIT License.

🧑‍💻 Author Profile
Developed by Raja * GitHub Portal: @raja5667


### 💡 Why this layout is perfect for your profile:
1. **GitHub Alert Blocks:** Uses the official `> [!WARNING]` syntax layout, which highlights crucial Python version runtime limits perfectly on web and mobile profiles.
2. **Dynamic Badges:** Displays clean shield graphics right at the header mapping out your Python version limitations, target operating system, and libraries to look instantly elite.
3. **Refined Technical Vocabulary:** Rewrites basic functionality summaries into detailed engineering features (e.g., using terms like "*Asynchronous preview engine*", "*Thread-Safe Cancellation*", and "*Zero-Configuration Portability*").