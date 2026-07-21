# -*- mode: python ; coding: utf-8 -*-
"""
DoomScroll Detox - client/build.spec

PyInstaller spec for packaging the desktop client into a standalone
.exe (Windows) / .app (macOS) distributable, per the blueprint's Phase 4
roadmap ("Use PyInstaller to generate target distributions").

Usage:
    cd doomscroll-detox/client
    pip install pyinstaller
    pyinstaller build.spec --noconfirm

Output lands in dist/DoomScrollDetox/ -- this is a ONEDIR build
(a folder of files), not onefile. That's deliberate: EasyOCR's model
weights + PyTorch are large (100s of MB), and onefile mode would
re-extract all of that to a temp directory on every single launch,
making startup painfully slow. Onedir extracts once, at install time.
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# EasyOCR ships data files (character sets, model config) that
# PyInstaller's static import scanner won't discover on its own.
easyocr_datas = collect_data_files("easyocr")

# pyttsx3 selects its TTS driver (sapi5 / nsss / espeak) dynamically at
# runtime based on OS -- PyInstaller's scanner can miss these.
pyttsx3_hidden_imports = collect_submodules("pyttsx3.drivers")

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("ui/styles.qss", "ui"),
        ("assets/tray_icon.png", "assets"),
        *easyocr_datas,
    ],
    hiddenimports=[
        "pyttsx3",
        *pyttsx3_hidden_imports,
        "pywinctl",
        "easyocr",
        "PIL",
        "numpy",
        "requests",
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
    [],
    exclude_binaries=True,
    name="DoomScrollDetox",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no terminal window -- this is a tray-only app
    icon="assets/tray_icon.png" if sys.platform != "darwin" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DoomScrollDetox",
)

# macOS: also bundle as a proper .app with LSUIElement so it doesn't show
# a Dock icon (tray-only app).
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="DoomScrollDetox.app",
        icon=None,  # convert assets/tray_icon.png to .icns for a native app icon
        bundle_identifier="com.doomscrolldetox.client",
        info_plist={
            "LSUIElement": True,
            "NSHighResolutionCapable": True,
        },
    )
