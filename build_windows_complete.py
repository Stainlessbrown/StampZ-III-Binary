#!/usr/bin/env python3
"""
Complete Windows build script that creates a self-contained StampZ executable.
This bundles ALL dependencies including VC++ runtimes.
"""

import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path

def run_command(cmd, description=""):
    """Run command and handle errors."""
    print(f"\n🔧 {description}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            print("Output:", result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stdout:
            print("Stdout:", e.stdout)
        if e.stderr:
            print("Stderr:", e.stderr)
        return False

def install_build_dependencies():
    """Install all required build dependencies."""
    print("📦 Installing build dependencies...")
    
    dependencies = [
        "pyinstaller>=6.0.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0", 
        "matplotlib>=3.7.0",
        "pillow>=10.0.0",
        "scikit-learn>=1.3.0",
        "openpyxl>=3.1.0",
        "odfpy>=1.4.1",
        "colorspacious>=1.1.2",
        "tksheet>=7.5.0"
    ]
    
    for dep in dependencies:
        if not run_command([sys.executable, "-m", "pip", "install", dep], 
                          f"Installing {dep}"):
            print(f"⚠️ Failed to install {dep}, continuing...")
    
    return True

def create_enhanced_spec():
    """Create an enhanced .spec file for complete bundling."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

# Collect ALL dependencies
matplotlib_datas, matplotlib_binaries, matplotlib_hiddenimports = collect_all('matplotlib')
pandas_datas, pandas_binaries, pandas_hiddenimports = collect_all('pandas')
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
PIL_datas, PIL_binaries, PIL_hiddenimports = collect_all('PIL')

try:
    sklearn_datas, sklearn_binaries, sklearn_hiddenimports = collect_all('sklearn')
except:
    sklearn_datas, sklearn_binaries, sklearn_hiddenimports = [], [], []

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        *matplotlib_binaries,
        *pandas_binaries,
        *numpy_binaries,
        *sklearn_binaries, 
        *PIL_binaries,
    ],
    datas=[
        *matplotlib_datas,
        *pandas_datas,
        *numpy_datas,
        *sklearn_datas,
        *PIL_datas,
        ('data', 'data') if os.path.exists('data') else ('dummy', 'data'),
        ('templates', 'templates') if os.path.exists('templates') else ('dummy', 'templates'),
    ],
    hiddenimports=[
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
        *matplotlib_hiddenimports,
        *pandas_hiddenimports,
        *numpy_hiddenimports,
        *sklearn_hiddenimports,
        *PIL_hiddenimports,
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_agg',
        'pandas._libs.tslibs.base',
        'numpy.random.common',
        'openpyxl', 'odfpy', 'colorspacious',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['IPython', 'jupyter', 'notebook', 'sphinx', 'pytest'],
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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
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
    name='StampZ',
)
'''
    
    with open('StampZ-Complete.spec', 'w') as f:
        f.write(spec_content)
    
    print("✅ Created enhanced .spec file")
    return True

def build_executable():
    """Build the executable using PyInstaller."""
    print("🏗️ Building Windows executable...")
    
    # Clean previous builds
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    
    # Build using the spec file
    if not run_command([
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm", 
        "StampZ-Complete.spec"
    ], "Building with PyInstaller"):
        return False
    
    print("✅ Build completed")
    return True

def bundle_vcredist():
    """Download and bundle VC++ Redistributables."""
    print("📥 Bundling Visual C++ Redistributables...")
    
    dist_dir = Path("dist/StampZ")
    if not dist_dir.exists():
        print("❌ Dist directory not found")
        return False
    
    # Create redistributables folder
    redist_dir = dist_dir / "vcredist"
    redist_dir.mkdir(exist_ok=True)
    
    # URLs for VC++ redistributables
    redist_urls = {
        "vc_redist.x64.exe": "https://aka.ms/vs/17/release/vc_redist.x64.exe",
    }
    
    # Try to download redistributables
    for filename, url in redist_urls.items():
        filepath = redist_dir / filename
        try:
            import urllib.request
            print(f"Downloading {filename}...")
            urllib.request.urlretrieve(url, filepath)
            print(f"✅ Downloaded {filename}")
        except Exception as e:
            print(f"⚠️ Could not download {filename}: {e}")
    
    # Create install script
    install_script = redist_dir / "install_prerequisites.bat"
    with open(install_script, 'w') as f:
        f.write('''@echo off
echo Installing Visual C++ Redistributables...
echo This will ensure StampZ can run on your system.
pause

if exist "vc_redist.x64.exe" (
    echo Installing VC++ 2015-2022 x64...
    vc_redist.x64.exe /quiet /norestart
    echo Done!
) else (
    echo VC++ Redistributable not found.
    echo Please download from: https://aka.ms/vs/17/release/vc_redist.x64.exe
)

pause
''')
    
    print("✅ Created VC++ redistributable installer")
    return True

def create_launcher():
    """Create a simple launcher that handles missing dependencies."""
    print("🚀 Creating dependency-aware launcher...")
    
    launcher_content = '''@echo off
title StampZ - Loading...

echo Starting StampZ...

REM Try to run StampZ
StampZ.exe
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo StampZ failed to start. This might be due to missing system components.
    echo.
    echo Would you like to install the required components now? [Y/N]
    set /p choice=
    if /i "%choice%"=="Y" (
        if exist "vcredist\\install_prerequisites.bat" (
            echo Installing prerequisites...
            call vcredist\\install_prerequisites.bat
            echo.
            echo Please try running StampZ again.
        ) else (
            echo Prerequisites installer not found.
            echo Please install Visual C++ Redistributable manually:
            echo https://aka.ms/vs/17/release/vc_redist.x64.exe
        )
    )
    pause
) else (
    echo StampZ started successfully!
)
'''
    
    launcher_path = Path("dist/StampZ/Launch StampZ.bat")
    with open(launcher_path, 'w') as f:
        f.write(launcher_content)
    
    print("✅ Created smart launcher")
    return True

def create_readme():
    """Create a README with installation instructions."""
    readme_content = """# StampZ - Complete Windows Bundle

This is a self-contained version of StampZ that includes all necessary dependencies.

## Quick Start

1. **Easy Way**: Double-click "Launch StampZ.bat"
   - This will automatically handle any missing dependencies

2. **Direct Way**: Double-click "StampZ.exe"
   - If it doesn't start, run the launcher instead

## Troubleshooting

If StampZ doesn't start:

1. Run "Launch StampZ.bat" - it will guide you through installing prerequisites
2. Or manually install Visual C++ Redistributable from: https://aka.ms/vs/17/release/vc_redist.x64.exe
3. Make sure Windows Defender isn't blocking the executable

## What's Included

This bundle includes:
- StampZ application with all features
- Ternary Plot functionality
- Spectral Analysis tools
- All Python dependencies
- Visual C++ Redistributable installer

## File Size Note

This bundle is larger than previous versions because it includes:
- Pandas (data analysis)
- Matplotlib (advanced plotting) 
- Scikit-learn (machine learning features)

These enable the new Ternary Plot and enhanced analysis features.
"""
    
    readme_path = Path("dist/StampZ/README.txt")
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    print("✅ Created README")
    return True

def main():
    """Main build process."""
    print("🏭 StampZ Complete Windows Bundle Builder")
    print("=" * 50)
    
    if sys.platform != 'win32':
        print("❌ This script must be run on Windows")
        sys.exit(1)
    
    steps = [
        ("Installing dependencies", install_build_dependencies),
        ("Creating enhanced spec", create_enhanced_spec), 
        ("Building executable", build_executable),
        ("Bundling VC++ redistributables", bundle_vcredist),
        ("Creating launcher", create_launcher),
        ("Creating README", create_readme),
    ]
    
    for step_name, step_func in steps:
        print(f"\n{'='*20} {step_name.upper()} {'='*20}")
        if not step_func():
            print(f"❌ Failed at step: {step_name}")
            sys.exit(1)
    
    print("\n" + "="*60)
    print("🎉 BUILD COMPLETE!")
    print("="*60)
    print(f"Output location: {os.path.abspath('dist/StampZ/')}")
    print("\nTo distribute:")
    print("1. Zip the entire 'dist/StampZ' folder")
    print("2. Users should extract and run 'Launch StampZ.bat'")
    print("\nThis bundle includes everything needed to run on Windows!")

if __name__ == "__main__":
    main()