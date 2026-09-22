# StampZ-III — Project Context for Oz

## What is StampZ-III?
StampZ-III is a Python desktop application for philatelic (postage stamp) image analysis. It is a GUI tool built with tkinter that allows users to load stamp images and perform colour measurement, spectral analysis, perforation gauging, 3D colour-space plotting, and database management. It is targeted at serious philatelists and researchers.

The app is close to completion. Active development is focused on the **calibration target** — testing of the existing calibration target has only recently begun, and changes to it are anticipated.

## Repository
- GitHub: https://github.com/Stainlessbrown/StampZ-III-Binary
- Local: ~/Desktop/StampZ-III-Binary/
- Main branch: `main`

## Application Structure
- `main.py` — entry point; launches `StampZApp` via tkinter
- `app/` — top-level app class (`stampz_app.py`), analysis, file, menu, and settings managers
- `gui/` — all GUI panels and dialogs (canvas, colour display, template manager, scanner calibration, perforation UI, Plot_3D integration, etc.)
- `managers/` — data export, measurement, black ink managers
- `utils/` — colour analysis, image processing, ODS/Excel export, spectral analysis, coordinate management, scanner calibration, RGB/CMY analysis, Plot_3D integration, and more
- `plot3d/` — standalone and integrated 3D colour-space plotting
- `data/` — application data files
- `resources/` — icons and image assets (including `StampZ_256.png`, `StampZ.ico`)
- `templates/` — template files bundled with the app

## Key Technologies
- Python 3.11/3.12, tkinter (GUI)
- PIL/Pillow, OpenCV, numpy (image processing)
- matplotlib, pandas, seaborn, scikit-learn, plotly (analysis/plotting)
- tksheet (spreadsheet widget for Plot_3D data manager)
- colorspacious (colour space conversions)
- ODS/Excel export via odfpy, ezodf, openpyxl

## Build System
- **PyInstaller** with `stampz.spec` — used for all three platforms (onedir mode)
- **Inno Setup** (`stampz_installer.iss`) — wraps Windows build into a signed-style installer (version currently `3.1.7`, publisher "Stainless Brown")
- Windows installer bundles VC++ Redistributable and handles SmartScreen issues

## GitHub Actions Workflows
All workflows are in `.github/workflows/`:

- **`build.yml`** — CI build triggered on every push to `main`. Builds Linux (ubuntu-22.04), Mac-ARM (macos-latest), and Windows. Uploads as temporary artifacts (90-day retention). Does NOT create a release.
- **`build-releases.yml`** — Release build triggered by a `v*` git tag OR manual `workflow_dispatch`. Builds Windows (installer), macOS (zip), and Linux (tar.gz), then creates a **public GitHub Release** at https://github.com/Stainlessbrown/StampZ-III-Binary/releases. This is how builds are distributed to users (replaces the previous Dropbox workflow).
- **`test-bundle.yml`** — Smoke test for Windows bundle on every push.

### Triggering a release
```
git tag v3.x.x
git push origin v3.x.x
```
Or trigger manually from the Actions tab with the desired version string.

## Distribution History
Previously, Linux and Mac-ARM builds were manually downloaded, zipped, and uploaded to Dropbox. Windows builds were similarly distributed but Dropbox does not allow `.exe` files. The new workflow uses GitHub Releases for all three platforms, making them publicly downloadable without a GitHub account.

## Notes
- The app is unsigned on all platforms. On macOS, users must right-click → Open the first time. On Windows, the installer handles SmartScreen ("More info" → "Run anyway").
- `main_optimized.py` and `initialize_env_optimized.py` are alternative/experimental versions; `main.py` and `initialize_env.py` are the active entry points.
- Many loose `.py` files at the root (e.g. `perforation_*.py`, `cancellation_*.py`, `rgb_cmy_*.py`) are development/research utilities, not part of the packaged app.
- A debug log is written to `~/Desktop/StampZ_Debug_Log.txt` on each run.
