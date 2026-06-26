# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['youtube_to_mp3_pro.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('VLC', 'vlc'),          # Bundles your VLC folder → inside exe as "vlc"
        ('app_icon.ico', '.'),   # App icon
        ('ffmpeg.exe', '.'),     # FFmpeg binary
    ],
    hiddenimports=[
        'vlc',
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.downloader',
        'yt_dlp.postprocessor',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
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
    name='YT-MP3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,               # Compresses the exe to reduce file size
    upx_exclude=[
        'libvlc.dll',       # Don't compress VLC DLLs (can cause issues)
        'libvlccore.dll',
    ],
    runtime_tmpdir=None,
    console=False,          # No black console window when user opens exe
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',    # Sets the exe icon
    onefile=True,           # Everything in ONE single .exe file
)
