# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],                        # ← entry point is main.py
    pathex=[],
    binaries=[],
    datas=[
        ('VLC', 'vlc'),                 # Bundle VLC folder
        ('ffmpeg.exe', '.'),            # Bundle FFmpeg
        ('app_icon.ico', '.'),          # Bundle icon
        ('youtube_to_mp3_pro.py', '.'), # Bundle MP3 module
        ('youtube_to_mp4_pro.py', '.'), # Bundle MP4 module
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
        'mutagen',
        'mutagen.mp3',
        'mutagen.id3',
        'requests',
        'PIL',
        'PIL.Image',
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
