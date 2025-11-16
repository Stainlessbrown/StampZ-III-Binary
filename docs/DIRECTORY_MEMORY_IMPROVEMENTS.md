# Directory Memory Improvements

## Overview
The Preferences system has been updated to simplify directory management and better support the data logger workflow.

## Changes Made

### 1. Unified Image Directory Memory

**Before:**
- Separate `last_open_directory` and `last_save_directory` settings
- Could result in opening images from one location and saving to another
- Caused data files to be separated from their images

**After:**
- Single `last_image_directory` setting for both Open and Save operations
- Ensures cropped images are saved in the same directory as originals
- Keeps data files (`*_StampZ_Data.txt`) with their corresponding images

### 2. Clear Separation of Concerns

The preferences now have a clearer distinction between:

**Image Directory (File Dialogs tab):**
- For working with image files (`.tif`, `.png`, `.jpg`)
- Tracks where you open and save stamp images
- Data logger creates measurement files here

**Export Directory (Export Settings tab):**
- For exporting analysis results to spreadsheets (`.ods`, `.xlsx`, `.csv`)
- Separate location, typically `~/Desktop/StampZ Exports`
- Not affected by image directory changes

### 3. Data Logger Integration

The unified directory system ensures proper data logging:

```
project_folder/
├── stamp_original.tif
├── stamp_original-crp.tif          (cropped version)
├── stamp_original_StampZ_Data.txt  (includes all measurements)
└── stamp_original-crp_StampZ_Data.txt (includes perforation data)
```

**Why this matters:**
- The data logger (`UnifiedDataLogger`) creates text files in the same directory as images
- For perforation measurements and color analysis to be properly linked, images must share a directory
- Unified directory memory makes this workflow automatic

### 4. Backwards Compatibility

The old API methods still work:
```python
# These are now aliases to the unified method
prefs_manager.get_last_open_directory()
prefs_manager.set_last_open_directory(path)
prefs_manager.get_last_save_directory()
prefs_manager.set_last_save_directory(path)

# New unified methods (recommended)
prefs_manager.get_last_image_directory()
prefs_manager.set_last_image_directory(path)
```

### 5. Automatic Migration

When loading preferences from an older version:
- If `last_image_directory` doesn't exist, it migrates from `last_open_directory`
- Fallback to `last_save_directory` if needed
- No user action required

## User Experience

### Preferences Dialog Updates

**File Dialogs Tab:**
- Renamed "Directory Memory" → "Directory Memory (Images Only)"
- Shows single "Last image directory" instead of separate Open/Save
- Added explanation about data file integration
- Updated info text to explain the workflow

**Key Benefits:**
1. **Simpler UI** - One directory to track instead of two
2. **Better workflow** - Keeps related files together
3. **Clear guidance** - Explains why unified directory matters
4. **Prevents data loss** - Reduces risk of separated data files

## Technical Details

### Data Structures

```python
@dataclass
class FileDialogPreferences:
    """Preferences for file dialogs."""
    last_image_directory: str = ""  # Unified for open and save
    remember_directories: bool = True
```

### Preference File Format

```json
{
  "file_dialog_prefs": {
    "last_image_directory": "/Users/username/StampProject",
    "remember_directories": true
  },
  "export_prefs": {
    "ods_export_directory": "/Users/username/Desktop/StampZ Exports",
    ...
  }
}
```

## Best Practices

### For Users
1. Keep all images for a project in one directory
2. This directory will contain:
   - Original images
   - Cropped images
   - Data logger files (`*_StampZ_Data.txt`)
3. Export spreadsheets go to a separate Export Directory

### For Developers
1. Always use `set_last_image_directory()` when opening or saving images
2. The unified directory is specifically for image operations
3. Export operations use the separate `export_prefs.ods_export_directory`
4. Data logger automatically uses the image's directory

## Files Modified

- `utils/user_preferences.py` - Unified directory methods, migration logic
- `gui/preferences_dialog.py` - Updated UI to show single directory
- `docs/DIRECTORY_MEMORY_IMPROVEMENTS.md` - This documentation

## Testing Recommendations

1. Test with fresh install (no existing preferences)
2. Test migration from older preferences file
3. Verify Open dialog uses last image directory
4. Verify Save dialog uses last image directory
5. Verify data logger creates files in correct location
6. Verify Export directory remains independent
