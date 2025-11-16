# Preferences Reorganization

## Overview
The Preferences dialog has been reorganized to group related settings more logically and reduce repetitive popup dialogs during analysis workflows.

## Changes Made

### 1. Tab Renaming for Clarity

**Before:**
- "File Dialogs" - ambiguous name
- "Export Settings" - unclear what type of exports

**After:**
- **"Image Dialogs"** - clearly about image file operations
- **"Spreadsheet Exports"** - specifically about ODS/XLSX/CSV exports

This naming makes it immediately clear:
- Image Dialogs = working with `.tif`, `.png`, `.jpg` files
- Spreadsheet Exports = exporting analysis results to `.ods`, `.xlsx`, `.csv`

### 2. Default Color Library Moved to Sampling

**Before:**
- Color Library setting was in "File Dialogs" tab
- Not logically related to file operations

**After:**
- Color Library setting moved to "Sampling" tab
- Makes sense because libraries are used during color sampling/analysis
- Groups all analysis-related defaults together

### 3. Analysis Save Preferences Added

**Problem:**
Every time you saved analysis results, a popup asked:
- ☐ Save individual sample measurements
- ☐ Save calculated average

**Solution:**
New section in Sampling tab: **"Analysis Save Preferences"**
- Set your preferred defaults once
- Checkboxes in save dialog now reflect your preferences
- Still changeable on each save if needed

**Benefits:**
- Fewer clicks during repetitive analysis workflows
- Consistent behavior based on your preferences
- Still flexible when you need to override

### 4. Logical Grouping in Sampling Tab

The Sampling tab now contains all analysis-related settings:

```
Sampling Tab:
├── Color Library Defaults
│   └── Default library for Compare mode
├── Analysis Save Preferences  [NEW]
│   ├── Save individual samples by default
│   └── Save calculated average by default
└── Sample Area Defaults
    ├── Shape, size, anchor
    └── Maximum samples
```

## Technical Details

### New Preferences Added

```python
@dataclass
class SampleAreaPreferences:
    # ... existing fields ...
    save_individual_default: bool = True
    save_average_default: bool = True
```

### New API Methods

```python
# Get/set whether to save individual samples by default
prefs_manager.get_save_individual_default() -> bool
prefs_manager.set_save_individual_default(bool)

# Get/set whether to save averaged results by default
prefs_manager.get_save_average_default() -> bool
prefs_manager.set_save_average_default(bool)
```

### Integration with Save Dialog

The `sample_results_manager.py` now loads preferences when showing the save dialog:

```python
# Load defaults from preferences
save_individual_default = prefs.get_save_individual_default()
save_average_default = prefs.get_save_average_default()

# Apply to checkbox initial states
save_individual = tk.BooleanVar(value=save_individual_default)
save_average = tk.BooleanVar(value=save_average_default)
```

## User Experience Improvements

### Before
1. Analyze samples
2. Click "Save Results"
3. Popup asks: Which database?
4. Popup asks: Save individual? Save average? ✓✓ (every time!)
5. Save

### After
1. Set preferences once (Sampling tab)
2. Analyze samples
3. Click "Save Results"
4. Popup shows pre-checked boxes based on your preferences
5. Save (or adjust if needed)

### Workflow Example

**Typical user doing batch analysis:**
```
Preferences → Sampling:
✓ Save individual sample measurements by default
✓ Save calculated average by default

Now every save dialog opens with both checked.
No need to click them every time!
```

**User only wants averages:**
```
Preferences → Sampling:
☐ Save individual sample measurements by default
✓ Save calculated average by default

Save dialogs now default to only saving averages.
```

## Tab Organization Summary

### Image Dialogs
- Directory memory for images
- Where original and cropped images are stored
- Related to data logger file placement

### Spreadsheet Exports
- Export directory (typically `~/Desktop/StampZ Exports`)
- File formats (ODS, XLSX, CSV)
- Export behavior and options

### Sampling
- **Color Library** defaults
- **Analysis Save** preferences (NEW)
- **Sample Area** defaults
- All analysis-related settings in one place

### Compare Mode
- Auto-save averages option
- Compare mode specific settings

### Measurements
- DPI defaults
- Perforation measurement settings
- Background color defaults

## Files Modified

- `gui/preferences_dialog.py`
  - Renamed `_create_file_dialog_tab()` → `_create_image_dialog_tab()`
  - Renamed `_create_export_tab()` → `_create_spreadsheet_export_tab()`
  - Moved Color Library section to Sampling tab
  - Added Analysis Save Preferences section

- `utils/user_preferences.py`
  - Added `save_individual_default` and `save_average_default` to `SampleAreaPreferences`
  - Added getter/setter methods
  - Updated load/save logic

- `gui/sample_results_manager.py`
  - Modified save dialog to read preferences for default checkbox states

- `docs/PREFERENCES_REORGANIZATION.md`
  - This documentation

## Migration

No migration needed! The new preferences have sensible defaults:
- `save_individual_default: true`
- `save_average_default: true`

This matches the previous hardcoded behavior, so existing workflows continue unchanged.

## Future Considerations

This pattern could be extended to other dialogs:
- Perforation measurement defaults
- Export format preferences
- Plot3D display options

The key benefit: **Set it once in Preferences, use everywhere.**
