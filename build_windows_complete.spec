# -*- mode: python ; coding: utf-8 -*-
"""
Enhanced PyInstaller spec for Windows that bundles ALL dependencies.
This creates a completely self-contained executable.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

# Collect all data and binaries for heavy dependencies
matplotlib_datas, matplotlib_binaries, matplotlib_hiddenimports = collect_all('matplotlib')
pandas_datas, pandas_binaries, pandas_hiddenimports = collect_all('pandas')
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
sklearn_datas, sklearn_binaries, sklearn_hiddenimports = collect_all('sklearn')
PIL_datas, PIL_binaries, PIL_hiddenimports = collect_all('PIL')

# Additional data files
extra_datas = []
if os.path.exists('data'):
    extra_datas.extend(collect_data_files('data', include_py_files=True))
if os.path.exists('templates'):
    extra_datas.extend(collect_data_files('templates', include_py_files=True))

# Collect dynamic libraries for matplotlib backends
mpl_backends = collect_dynamic_libs('matplotlib')

a = Analysis(
    ['stampz.py'],
    pathex=['.'],
    binaries=[
        *matplotlib_binaries,
        *pandas_binaries, 
        *numpy_binaries,
        *sklearn_binaries,
        *PIL_binaries,
        *mpl_backends,
    ],
    datas=[
        *matplotlib_datas,
        *pandas_datas,
        *numpy_datas,
        *sklearn_datas,
        *PIL_datas,
        *extra_datas,
        ('data', 'data'),
        ('templates', 'templates'),
    ],
    hiddenimports=[
        # Core app imports
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        
        # Heavy dependency imports
        *matplotlib_hiddenimports,
        *pandas_hiddenimports,
        *numpy_hiddenimports,
        *sklearn_hiddenimports,
        *PIL_hiddenimports,
        
        # Matplotlib backends - critical for Windows
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_agg', 
        'matplotlib.backends._backend_agg',
        'matplotlib.figure',
        'matplotlib.pyplot',
        
        # Pandas engines
        'pandas._libs.tslibs.base',
        'pandas._libs.tslibs.nattype',
        'pandas._libs.tslibs.np_datetime',
        'pandas._libs.tslibs.timedeltas',
        'pandas._libs.tslibs.timestamps',
        'pandas._libs.parsers',
        'pandas._libs.writers',
        
        # NumPy
        'numpy.random.common',
        'numpy.random.bounded_integers',
        'numpy.random.entropy',
        
        # File format support
        'openpyxl',
        'odfpy',
        'ezodf',
        'lxml',
        'xlrd',
        
        # Our modules
        'utils.spectral_analyzer',
        'utils.color_analyzer',
        'utils.color_analysis_db',
        'plot3d.ternary_plot_app',
        'plot3d.Plot_3D',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused modules to reduce size
        'IPython',
        'jupyter',
        'notebook',
        'sphinx',
        'pytest',
        'setuptools',
        'distutils',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='StampZ',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Don't compress - can cause issues with matplotlib
    console=False,  # Windows GUI app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='StampZ',
)

# Optional: Create a single-file executable (larger but more portable)
# Uncomment the following to create a single .exe instead of a folder:
"""
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='StampZ-Standalone',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
"""