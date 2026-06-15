# -*- mode: python ; coding: utf-8 -*-
# Build with:  pyinstaller --noconfirm SpaceMusicHubGUI.spec
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

for pkg in ("yt_dlp", "telegram", "dotenv", "PyQt6"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# Bundle the bot script + assets into the EXE folder.
datas += [
    ("telegram_bot_music_youtube.py", "."),
    ("docs/logo_round.png", "."),
    ("docs/logo_round.ico", "."),
    ("docs/bg.jpg",         "."),
]

a = Analysis(
    ["gui_app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Avoid pulling the whole PyQt6 stack we don't use.
        "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtQml", "PyQt6.QtQuick", "PyQt6.Qt3D",
        "PyQt6.QtCharts", "PyQt6.QtDataVisualization",
        "PyQt6.QtPdf", "PyQt6.QtPdfWidgets",
        "tkinter", "test", "unittest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SpaceMusicHub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                    # windowed app — no black console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="docs/logo_round.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SpaceMusicHub",
)
