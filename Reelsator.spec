# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/denis/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages/cv2/data/haarcascade_frontalface_default.xml', 'cv2/data'), ('C:/Users/denis/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages/cv2/data/haarcascade_profileface.xml', 'cv2/data')],
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
