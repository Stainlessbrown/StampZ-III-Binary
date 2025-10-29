# Multi-Sheet File Import Feature

## Overview
StampZ now supports importing data from specific sheets in multi-sheet ODS and XLSX files, making it easier to organize different versions or datasets in a single file.

## What's New

### Previous Behavior
- Only the first sheet was imported from ODS/XLSX files
- Users had to maintain separate files for different data versions

### New Behavior
- **Automatic sheet detection** for ODS and XLSX files
- **Sheet selection dialog** appears when multiple sheets are detected
- **Single-sheet files** work automatically (no dialog)
- **CSV files** remain unchanged (no sheet concept)

## User Experience

### When Importing Files

1. **Select your file** (ODS/XLSX with multiple sheets)
2. **Sheet Selection Dialog appears** with:
   - List of all available sheets
   - Scrollable listbox for easy selection
   - Double-click to import
   - "Import" button to confirm
   - "Cancel" button to abort

3. **Single-sheet files** import immediately (no dialog needed)

### Dialog Features
- Shows count of available sheets in the heading
- First sheet is pre-selected by default
- Supports keyboard navigation
- Double-click on a sheet name to import immediately
- Modal dialog (blocks other actions until selection is made)

## Technical Details

### Files Modified

#### 1. `utils/external_data_importer.py`
- Added `get_sheet_names(file_path)` method
  - Returns list of sheet names from ODS/XLSX files
  - Returns empty list for CSV files
  - Handles errors gracefully

- Updated `read_external_file(file_path, sheet_name=None)` method
  - Added optional `sheet_name` parameter
  - Passes sheet name to `pd.read_excel()`
  - Defaults to first sheet (index 0) if not specified

#### 2. `gui/realtime_plot3d_sheet.py`
- Added `_ask_sheet_selection(sheet_names)` method
  - Creates modal dialog with sheet list
  - Returns selected sheet name or None if cancelled
  - Automatically returns single sheet without showing dialog

- Updated `_import_from_plot3d()` method
  - Detects available sheets before import
  - Shows selection dialog for multi-sheet files
  - Passes selected sheet to pandas

- Updated `_merge_with_existing_file()` method
  - Detects sheets when merging with existing files
  - Allows user to select target sheet for merge operation

- Updated export file existence check
  - Uses `sheet_name=0` to read first sheet
  - Ensures compatibility with multi-sheet files

## Usage Examples

### Example 1: Multi-Sheet File
```
File: stamp_analysis.ods
Sheets:
  - Raw_Data
  - Processed_2024
  - Processed_2023
  
User action: Import → selects "Processed_2024" → data imported
```

### Example 2: Single-Sheet File
```
File: single_dataset.ods
Sheets:
  - Sheet1

User action: Import → automatic (no dialog) → data imported
```

### Example 3: CSV File
```
File: data.csv
Sheets: (none - CSV has no sheets)

User action: Import → works as before → data imported
```

## Benefits

1. **Organization**: Keep multiple data versions in one file
2. **Convenience**: No need to split sheets into separate files
3. **Flexibility**: Easy switching between different datasets
4. **Backward Compatible**: Single-sheet files work exactly as before
5. **Error Handling**: Graceful fallback if sheet detection fails

## Error Handling

- If sheet detection fails, defaults to first sheet (index 0)
- If user cancels sheet selection, import is aborted
- Logging captures all sheet operations for debugging
- Sheet selection errors don't crash the application

## Implementation Notes

### Sheet Name Detection
Uses pandas `ExcelFile` class:
- `pd.ExcelFile(path, engine='odf')` for ODS files
- `pd.ExcelFile(path)` for XLSX files
- Returns `xl_file.sheet_names` list

### Sheet Reading
Uses pandas `read_excel()` with `sheet_name` parameter:
- `sheet_name=0` → first sheet (default)
- `sheet_name='SheetName'` → specific sheet by name
- `sheet_name=None` → all sheets (not used in this feature)

### Dialog Implementation
- Uses tkinter `Toplevel` for modal dialog
- `Listbox` widget for sheet selection
- Scrollbar for long sheet lists
- Follows existing dialog patterns in the application

## Testing Checklist

When testing this feature:

- [x] Multi-sheet ODS file import
- [x] Multi-sheet XLSX file import
- [x] Single-sheet file (no dialog expected)
- [x] CSV file (no changes)
- [x] Cancel during sheet selection
- [x] Double-click sheet selection
- [x] Merge operation with multi-sheet file
- [x] Export to existing multi-sheet file
- [x] Error handling with corrupted files

## Future Enhancements

Possible improvements:
1. Show preview of sheet data before importing
2. Import multiple sheets into separate worksheets
3. Remember last selected sheet for a file
4. Sheet name filtering/search for files with many sheets
5. Display row count for each sheet in the dialog

## Related Issues

This feature addresses user feedback about managing multiple data versions and the need to work with consolidated spreadsheet files containing multiple analysis results.

---

**Version**: 1.0  
**Date**: 2025-10-29  
**Author**: Claude (AI Assistant)  
**Status**: Implemented and Ready for Testing
