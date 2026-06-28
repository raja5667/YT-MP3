# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Collect EVERYTHING from yt_dlp — this is the critical fix.
# yt_dlp uses dynamic imports for its 1700+ extractors (YouTube, etc.)
# and all downloader/postprocessor/networking modules. Without collect_all,
# PyInstaller misses them and yt_dlp silently falls back to lowest quality.
yt_dlp_datas, yt_dlp_binaries, yt_dlp_hiddenimports = collect_all('yt_dlp')

a = Analysis(
    ['main.py'],                        # ← entry point is main.py
    pathex=[],
    binaries=[
        *yt_dlp_binaries,
    ],
    datas=[
        ('VLC', 'vlc'),                 # Bundle VLC folder
        ('ffmpeg.exe', '.'),            # Bundle FFmpeg
        ('app_icon.ico', '.'),          # Bundle icon
        ('youtube_to_mp3_pro.py', '.'), # Bundle MP3 module
        ('youtube_to_mp4_pro.py', '.'), # Bundle MP4 module
        *yt_dlp_datas,                  # All yt_dlp data files (extractors, etc.)
    ],
    hiddenimports=[
        # yt_dlp — full dynamic extractor tree (fixes quality fallback in exe)
        *yt_dlp_hiddenimports,
        *collect_submodules('yt_dlp'),
        *collect_submodules('yt_dlp.extractor'),
        *collect_submodules('yt_dlp.downloader'),
        *collect_submodules('yt_dlp.postprocessor'),
        *collect_submodules('yt_dlp.networking'),
        *collect_submodules('yt_dlp.utils'),

        # UI / media
        'vlc',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',

        # Audio tagging
        'mutagen',
        'mutagen.mp3',
        'mutagen.id3',
        'mutagen.mp4',
        'mutagen.flac',
        'mutagen.ogg',

        # Networking & image
        'requests',
        'certifi',
        'urllib3',
        'PIL',
        'PIL.Image',

        # Stdlib modules yt_dlp uses at runtime
        'http.cookiejar',
        'http.cookies',
        'xml.etree.ElementTree',
        'email.mime.text',
        'email.mime.multipart',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='YTMP3-Pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'libvlc.dll',
        'libvlccore.dll',
    ],
    runtime_tmpdir=None,
    console=False,              # No terminal window for users
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
    onefile=True,               # Single .exe output
)
