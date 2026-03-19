# -*- mode: python ; coding: utf-8 -*-
import os
ROOT = r'C:\Users\naoki\XROSS-main\XROSS_v2.0.1\xross_project'

a = Analysis(
    [os.path.join(ROOT, 'xross', '__main__.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'favicon.ico'), '.'),
    ],
    hiddenimports=[
        'PIL',
        'PIL._tkinter_finder',
        'matplotlib.backends.backend_tkagg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'matplotlib.backends.backend_qt5agg', 'matplotlib.backends.backend_qt5',
        'matplotlib.backends.backend_qt4agg', 'matplotlib.backends.backend_qt4',
        'matplotlib.backends.backend_webagg', 'matplotlib.backends.backend_webagg_core',
        'matplotlib.backends.backend_gtk3agg', 'matplotlib.backends.backend_gtk3cairo',
        'matplotlib.backends.backend_gtk3', 'matplotlib.backends.backend_gtk4agg',
        'matplotlib.backends.backend_gtk4cairo',
        'matplotlib.backends.backend_wx', 'matplotlib.backends.backend_wxagg',
        'matplotlib.backends.backend_wxcairo',
        'matplotlib.backends.backend_nbagg', 'matplotlib.backends.backend_cairo',
        'matplotlib.backends.backend_macosx',
        'plotly', 'bokeh', 'IPython', 'notebook', 'jupyter',
        'sphinx', 'pytest', 'cv2', 'torch', 'tensorflow',
        'h5py', 'tables', 'sympy', 'docutils',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='XROSS',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=os.path.join(ROOT, 'favicon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='XROSS',
)
