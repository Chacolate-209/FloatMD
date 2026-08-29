# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir build — bundles RapidOCR (no external pip for OCR).
# Output: dist/FloatMD/

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

block_cipher = None
root = Path(SPECPATH)

datas = []
binaries = []
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
    "onnxruntime",
]

datas += collect_data_files("floatmd", includes=["resources/**/*"])

# Bundle RapidOCR models + onnxruntime native libs into the app.
for pkg in ("rapidocr_onnxruntime", "onnxruntime"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        try:
            datas += collect_data_files(pkg)
        except Exception:
            pass

try:
    binaries += collect_dynamic_libs("PySide6")
except Exception:
    pass

# Keep green build lean: do not ship Paddle / OpenCV.
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
    console=False,
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
