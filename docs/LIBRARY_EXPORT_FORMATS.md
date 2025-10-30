# Color Library Export Format Selection

## Overview
Library exports now support selecting which color space format to export: **RGB**, **L\*a\*b\***, or **CMY**.

## Changes Made

### 1. Export Dialog (`gui/color_library_manager.py`)
- Added format selection dialog before file save dialog
- Users can choose one of three formats:
  - **L\*a\*b\*** (CIE Lab color space) - Default
  - **RGB** (Red, Green, Blue values)
  - **CMY** (Cyan, Magenta, Yellow values)

### 2. Export Function (`utils/color_library.py`)
- Updated `export_library()` to accept `format_type` parameter
- Supports three format types: `'lab'`, `'rgb'`, `'cmy'`
- CSV column headers change based on selected format

## CSV Format Examples

### L\*a\*b\* Format
```csv
name,description,lab_l,lab_a,lab_b,category,source,notes
Red,Bright red,53.24,80.09,67.20,Primary,,
```

### RGB Format
```csv
name,description,rgb_r,rgb_g,rgb_b,category,source,notes
Red,Bright red,255.00,0.00,0.00,Primary,,
```

### CMY Format
```csv
name,description,cmy_c,cmy_m,cmy_y,category,source,notes
Red,Bright red,0.00,255.00,255.00,Primary,,
```

## User Workflow

1. Click **Export Library** button in Color Library Manager
2. Select desired color space format from dialog:
   - L\*a\*b\* (recommended for color science)
   - RGB (for digital/screen colors)
   - CMY (for print/ink analysis)
3. Choose file location and name
4. File is exported with selected format

## Import Compatibility

- Import automatically detects which format was used
- All three formats are fully supported for import
- No manual format specification needed when importing

## Notes

- **Display preferences** (what shows in the Library tab) are separate from export format
- Display can show all three color spaces simultaneously
- Export is limited to ONE color space per file for simplicity
- RGB values now display with 2 decimal places (e.g., 255.00, 128.47)
