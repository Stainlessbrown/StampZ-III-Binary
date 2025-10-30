# StampZ Bundle Troubleshooting Guide

## Windows Issues

If StampZ downloads but doesn't open when clicked on Windows, follow these steps:

### Quick Fixes (Try These First)

#### 1. Install Visual C++ Redistributable (Most Common Fix)
Download and install the Microsoft Visual C++ Redistributable:
- [VC++ 2015-2022 x64](https://aka.ms/vs/17/release/vc_redist.x64.exe)

This is the **#1 cause** of "nothing happens" on Windows.

#### 2. Run as Administrator
Right-click on `stampz.exe` and select "Run as administrator".

#### 3. Check Windows Defender
- Open Windows Security
- Go to "Virus & threat protection"
- Check if StampZ was quarantined
- Add folder exception if needed

#### 4. Try Running from Command Prompt
1. Open Command Prompt (cmd)
2. Navigate to the StampZ folder
3. Run: `stampz.exe --version`
4. Look for error messages

## macOS Issues

If StampZ downloads but doesn't open when clicked on macOS, follow these steps:

### Quick Fixes (Try These First)

#### 1. Remove Quarantine (Most Common Fix)
Right-click on StampZ.app and select "Open". If you see a security warning, click "Open" anyway.

OR run this in Terminal:
```bash
sudo xattr -rd com.apple.quarantine /path/to/StampZ.app
```

#### 2. Check Your Mac Type
- **M1/M2/M3 Mac (Apple Silicon)**: Download the ARM version
- **Intel Mac (2020 and earlier)**: Download the Intel version
- **M1/M2/M3 with Intel version**: Install Rosetta 2:
  ```bash
  sudo softwareupdate --install-rosetta
  ```

#### 3. Try Running from Terminal
1. Open Terminal
2. Navigate to the app bundle:
   ```bash
   cd /Applications/StampZ.app/Contents/MacOS
   ./stampz
   ```

## Debug Information Needed

If the quick fixes don't work, please run our debug script and send the output:

### For Windows Users:
#### Step 1: Download Debug Script
1. Go to: https://github.com/Stainlessbrown/StampZ-III-Binary
2. Download `debug_bundle_windows.py`

#### Step 2: Run Debug Script
Open Command Prompt and run:
```cmd
python debug_bundle_windows.py > stampz_debug.txt 2>&1
```

#### Step 3: Send Results
Email the `stampz_debug.txt` file to the developer.

### For macOS Users:
#### Step 1: Download Debug Script
1. Go to: https://github.com/Stainlessbrown/StampZ-III-Binary
2. Download `debug_bundle.py`

#### Step 2: Run Debug Script
```bash
python3 debug_bundle.py > stampz_debug.txt 2>&1
```

## Common Issues

### Windows
| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Nothing happens when double-clicking | Missing VC++ Redistributable | Install VC++ 2015-2022 x64 |
| Brief flash then disappears | Missing DLLs | Run debug script |
| "Windows protected your PC" | SmartScreen filter | Click "More info" then "Run anyway" |
| Permission denied | User permissions | Run as Administrator |

### macOS  
| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Nothing happens when double-clicking | macOS quarantine | Remove quarantine attribute |
| "App is damaged" message | Wrong architecture | Download correct version for your Mac |
| Brief flash then disappears | Missing dependencies | Run debug script |
| Permission denied | File permissions | Check bundle permissions |

## Manual Verification Steps

### Windows
1. **Check if executable exists**:
   ```cmd
   dir stampz.exe
   ```

2. **Check file properties**:
   ```cmd
   powershell "Get-ItemProperty stampz.exe | Select-Object Name, Length, LastWriteTime"
   ```

3. **Test direct execution**:
   ```cmd
   stampz.exe --version
   ```

4. **Check for missing DLLs**:
   ```cmd
   dir *.dll
   ```

### macOS
1. **Check bundle structure**:
   ```bash
   ls -la /Applications/StampZ.app/Contents/MacOS/
   ```

2. **Check file type**:
   ```bash
   file /Applications/StampZ.app/Contents/MacOS/stampz
   ```

3. **Check extended attributes**:
   ```bash
   xattr /Applications/StampZ.app
   ```

4. **Test direct execution**:
   ```bash
   /Applications/StampZ.app/Contents/MacOS/stampz --version
   ```

## Need Help?

If none of these steps work, please:
1. Run the debug script (see above)
2. Include your macOS version: `sw_vers`
3. Include your Mac model: `system_profiler SPHardwareDataType | grep "Model Name"`
4. Send all output to the developer

---

**Note**: These instructions help diagnose common macOS app bundle issues. The debug script provides detailed technical information for the developer to identify the specific problem.