# -*- mode: python ; coding: utf-8 -*-

import sys


# GUI.py is the packaging launcher; it delegates to the single maintained
# implementation in virtual_array.gui. GUI_mod.py is a compatibility alias only.
app_entry_script = 'GUI.py'
app_icon = None
if sys.platform == 'win32':
    app_icon = 'src/virtual_array/assets/mimo_array_logo.ico'
elif sys.platform == 'darwin':
    app_icon = 'src/virtual_array/assets/mimo_array_logo.icns'

a = Analysis(
    [app_entry_script],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/virtual_array/assets/mimo_array_logo_48.png', 'virtual_array/assets'),
        ('src/virtual_array/assets/mimo_array_logo_256.png', 'virtual_array/assets'),
        ('src/virtual_array/assets/mimo_array_logo.ico', 'virtual_array/assets'),
        ('src/virtual_array/assets/mimo_array_logo.icns', 'virtual_array/assets'),
    ],
    hiddenimports=[
        'virtual_array.gui',
        'pyparsing.testing',
        'openpyxl',
        'openpyxl.cell._writer',
        'PySide6',
        'pyqtgraph',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', '_pytest', 'numpy.tests', 'matplotlib.tests'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MIMOArrayVisualizer',
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
    icon=app_icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MIMOArrayVisualizer',
)
