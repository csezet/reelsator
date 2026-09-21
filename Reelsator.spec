# -*- mode: python ; coding: utf-8 -*-
import os
import cv2

cascade_dir = cv2.data.haarcascades
datas = [
    (os.path.join(cascade_dir, 'haarcascade_frontalface_default.xml'), 'cv2/data'),
    (os.path.join(cascade_dir, 'haarcascade_profileface.xml'), 'cv2/data')
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['cv2', 'PIL', 'piexif', 'numpy', 'PySide6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Reelsator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Reelsator',
)
