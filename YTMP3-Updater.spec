# -*- mode: python ; coding: utf-8 -*-
# Separate, lightweight build for the background update watcher.
# Deliberately does NOT bundle yt-dlp / VLC / FFmpeg — this process only
# needs to make a small HTTPS request and show a toast, so it should start
# almost instantly at every Windows login.

block_cipher = None

a = Analysis(
    ['update_watcher.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'win11toast',
        'winsdk',
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
    name='YTMP3-Updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,               # runs silently, no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
