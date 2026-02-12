# YouTube to MP3 Pro H

A PyQt6-based desktop application to download YouTube audio as high-quality 320kbps MP3 with playlist support and automatic thumbnail embedding.

---

## Features

- Download YouTube videos as MP3 (320kbps)
- Playlist support
- Auto thumbnail embedding
- Drag & drop YouTube links
- Custom download directory
- Cancel download support
- Automatic temporary file cleanup
- Portable FFmpeg (no system installation required)

---

## Requirements

- Python 3.12.x (Recommended)
- Windows 10 / 11
- Internet connection
- pip (latest version recommended)

> ⚠️ Avoid Python 3.13 if you face compatibility issues with PyQt6 or PyInstaller.

---

## Project Structure

```
YouTube-To-MP3-ProH/
│
├── youtube_to_mp3_proh.py
├── ffmpeg.exe
├── requirements.txt
├── app_icon.ico
├── .gitignore
└── README.md
```

---

## Setup (Windows)

### 1. Clone Repository

```bash
git clone https://github.com/raja5667/YouTube-To-MP3-ProH.git
cd YouTube-To-MP3-ProH
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### 3. Activate Virtual Environment

```bash
venv\Scripts\activate
```

### 4. Install Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Run the Application

```bash
python youtube_to_mp3_proh.py
```

---

## Build Windows Executable (.exe)

Install PyInstaller:

```bash
pip install pyinstaller
```

Build (portable version including FFmpeg):

```bash
pyinstaller --onefile --windowed --icon=app_icon.ico --add-binary "ffmpeg.exe;." youtube_to_mp3_proh.py
```

The final executable will be inside:

```
dist/
```

---

## Notes

- FFmpeg is bundled locally inside the project.
- No global FFmpeg installation required.
- Downloads are saved to the user's Downloads folder by default.
- Temporary files are automatically cleaned after download or cancellation.

---

## License

MIT License

---

## Author

Developed by Raja  
GitHub: https://github.com/raja5667