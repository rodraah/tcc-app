# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for TCC-App (Windows onedir).

Build:  .\\scripts\\build_exe.ps1
Output: dist\\TCC-App\\TCC-App.exe
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Heavy packages that ship binary/data assets PyInstaller misses by default.
_mp_datas, _mp_bins, _mp_hidden = collect_all("mediapipe")
_ctk_datas, _ctk_bins, _ctk_hidden = collect_all("customtkinter")
_cv_datas, _cv_bins, _cv_hidden = collect_all("cv2")
_pw_datas, _pw_bins, _pw_hidden = collect_all("playwright")

datas = [
    *_mp_datas,
    *_ctk_datas,
    *_cv_datas,
    *_pw_datas,
    *collect_data_files("faster_whisper"),
]

binaries = [
    *_mp_bins,
    *_ctk_bins,
    *_cv_bins,
    *_pw_bins,
]

hiddenimports = [
    *_mp_hidden,
    *_ctk_hidden,
    *_cv_hidden,
    *_pw_hidden,
    "pyaudio",
    "sounddevice",
    "vosk",
    "faster_whisper",
    "ctranslate2",
    "onnxruntime",
    "playwright",
    "playwright.sync_api",
    "keyboard",
    "pystray",
    "PIL",
    "PIL._tkinter_finder",
    "win32gui",
    "win32con",
    "win32api",
    "win32process",
    "pywintypes",
    "pythoncom",
    "comtypes",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "tensorflow",
        "pytest",
        "IPython",
    ],
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
    name="TCC-App",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app — no black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TCC-App",
)
