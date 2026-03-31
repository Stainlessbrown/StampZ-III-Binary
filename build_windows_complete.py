#!/usr/bin/env python3
"""
Complete Windows build script that creates a StampZ installer.
Builds with PyInstaller (onedir), then packages with Inno Setup.
Output: dist/StampZ-III-<version>-Setup.exe
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


def build_executable():
    """Build the executable using PyInstaller (onedir mode)."""
    print("🏗️ Building Windows executable (onedir mode)...")
    
    # Clean previous builds
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    
    # Build using the main spec file (now uses onedir for Windows)
    if not run_command([
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm", 
        "stampz.spec"
    ], "Building with PyInstaller"):
        return False
    
    print("✅ Build completed")
    return True

def bundle_vcredist():
    """Download and bundle VC++ Redistributables."""
    print("📥 Bundling Visual C++ Redistributables...")
    
    dist_dir = Path("dist/StampZ-III")
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

def build_installer():
    """Compile the Inno Setup installer from the PyInstaller output."""
    print("📦 Building Inno Setup installer...")
    
    iss_file = Path("stampz_installer.iss")
    if not iss_file.exists():
        print("❌ stampz_installer.iss not found")
        return False
    
    # Common Inno Setup compiler locations
    iscc_paths = [
        Path(os.environ.get('PROGRAMFILES(X86)', '')) / 'Inno Setup 6' / 'ISCC.exe',
        Path(os.environ.get('PROGRAMFILES', '')) / 'Inno Setup 6' / 'ISCC.exe',
        Path('C:/Program Files (x86)/Inno Setup 6/ISCC.exe'),
        Path('C:/Program Files/Inno Setup 6/ISCC.exe'),
    ]
    
    iscc = None
    for path in iscc_paths:
        if path.exists():
            iscc = str(path)
            break
    
    if iscc is None:
        # Try finding it on PATH
        iscc = shutil.which('ISCC')
    
    if iscc is None:
        print("❌ Inno Setup compiler (ISCC.exe) not found.")
        print("   Install Inno Setup 6 from: https://jrsoftware.org/isdl.php")
        print("   The PyInstaller build in dist/StampZ-III/ is still valid.")
        print("   You can compile the installer manually after installing Inno Setup:")
        print(f'   ISCC.exe "{iss_file.absolute()}"')
        return False
    
    if not run_command([iscc, str(iss_file)], "Compiling installer with Inno Setup"):
        return False
    
    output = Path("dist/StampZ-III-3.1.7-Setup.exe")
    if output.exists():
        size_mb = output.stat().st_size / (1024 * 1024)
        print(f"✅ Installer created: {output} ({size_mb:.1f} MB)")
    else:
        print("✅ Inno Setup compilation completed")
    
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
        ("Building executable", build_executable),
        ("Bundling VC++ redistributables", bundle_vcredist),
        ("Building installer", build_installer),
    ]
    
    for step_name, step_func in steps:
        print(f"\n{'='*20} {step_name.upper()} {'='*20}")
        if not step_func():
            print(f"❌ Failed at step: {step_name}")
            sys.exit(1)
    
    print("\n" + "="*60)
    print("🎉 BUILD COMPLETE!")
    print("="*60)
    installer = os.path.abspath('dist/StampZ-III-3.1.7-Setup.exe')
    print(f"Installer: {installer}")
    print("\nTo distribute:")
    print("Upload StampZ-III-3.1.7-Setup.exe to GitHub Releases")
    print("Users just download and run the installer.")

if __name__ == "__main__":
    main()