# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec. Run on Windows via build_exe.bat (or manually:
`pyinstaller --noconfirm lifeline_bot.spec`).

Notes:
  - better_profanity ships its word list as package data; PyInstaller's
    static import analysis won't pick that up on its own, so it's added
    explicitly via collect_data_files below. Without this, the built exe
    would run but silently report "profanity filter unavailable".
  - pyttsx3's Windows backend (sapi5) and vgamepad are loaded dynamically
    enough that they need to be listed as hidden imports or PyInstaller
    won't bundle them, and the exe would fail at runtime with a
    ModuleNotFoundError even though `pip install` succeeded at build time.
"""

from PyInstaller.utils.hooks import collect_data_files

datas = []
datas += collect_data_files("better_profanity")

hidden_imports = [
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    "vgamepad",
    "vgamepad.win",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="LifelineVoiceController",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,       # windowed app, no console popup
    icon=None,            # put an .ico path here if you have one
)
