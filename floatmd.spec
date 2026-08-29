# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir (green folder) build for FloatMD.
# Usage:
#   pyinstaller floatmd.spec
# Output: dist/FloatMD/

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None
root = Path(SPECPATH)

datas = []
datas += collect_data_files("floatmd", includes=["resources/**/*"])

# Optional OCR models shipped with rapidocr (if installed)
try:
    datas += collect_data_files("rapidocr_onnxruntime")
except Exception:
    pass

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtPrintSupport",
    "httpx",
    "httpcore",
    "anyio",
    "appdirs",
    "keyring",
    "keyring.backends",
    "mss",
    "PIL",
    "markdown",
    "pymdownx",
    "rapidocr_onnxruntime",
]

binaries = []
# Qt WebEngine / platform plugins
try:
    binaries += collect_dynamic_libs("PySide6")
except Exception:
    pass

# Keep default green build lean: RapidOCR only (Paddle is optional / huge).
excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
    "pandas",
    "paddle",
    "paddleocr",
    "paddlex",
    "cv2",
    "torch",
    "tensorflow",
]

a = Analysis(
    [str(root / "scripts" / "run_floatmd.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name="FloatMD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed
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
    name="FloatMD",
)
