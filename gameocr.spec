# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None
project_dir = Path.cwd()
model_dir = project_dir / "models"
assets_dir = project_dir / "assets"
icon_path = assets_dir / "gameocr.ico"

datas = []
if model_dir.exists():
    datas.append((str(model_dir), "models"))
if assets_dir.exists():
    datas.append((str(assets_dir), "assets"))

hiddenimports = [
    "onnxocr",
    "onnxocr.onnx_paddleocr",
    "openvino",
    "onnxruntime",
    "googletrans",
    "pynput",
    "mss",
    "win32con",
    "win32gui",
    "win32process",
    "win32ui",
    "PIL",
    "cv2",
    "numpy",
    "requests",
]

a = Analysis(
    ["gameocr/main.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.zipfiles,
    a.datas,
    [],
    name="GameOCRTranslator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)