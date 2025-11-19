# RGB-CMY Template Creation & Plot3D Integration Guide

## Overview
This guide explains how to create the new RGB-only and CMY-only templates, and how the Plot3D integration works.

## Template Creation

### What You Need
- Existing file: `RGB-CMY Channel analysis.xlsx` (in `/data/templates/`)
- Excel or LibreOffice Calc

### Step 1: Create RGB-Only Template

1. **Open** `/Users/stanbrown/Desktop/StampZ-III-Binary/data/templates/RGB-CMY Channel analysis.xlsx`

2. **Save As** → `RGB Channel analysis.xlsx` (same directory)

3. **Edit Row 15** (the header row):
   - Cell B15: Change from "R" to "R" (keep as is)
   - Cell C15: "SD" (keep)
   - Cell D15: "1/SD²" (keep)
   - Cell E15: "G" (keep)
   - Cell F15: "SD" (keep)
   - Cell G15: "1/SD²" (keep)
   - Cell H15: "B" (keep)
   - Cell I15: "SD" (keep)
   - Cell J15: "1/SD²" (keep)
   
   This header should say: **Sample# | R | SD | 1/SD² | G | SD | 1/SD² | B | SD | 1/SD²**

4. **Delete CMY Section**:
   - Select and delete rows 27-50 (everything after RGB averages in row 26)
   
5. **Result**:
   - Rows 1-14: User input metadata (unchanged)
   - Row 15: Header (Sample#, R, SD, 1/SD², G, SD, 1/SD², B, SD, 1/SD²)
   - Rows 16-21: Sample data (6 samples)
   - Row 22: "Ave" with averages
   - Rows 23-26: Additional calculations (8-bit, R-G, G-B, R-B)
   - **Important**: Averages are in **D22, G22, J22**

6. **Save** the file

### Step 2: Create CMY-Only Template

1. **Open** `/Users/stanbrown/Desktop/StampZ-III-Binary/data/templates/RGB-CMY Channel analysis.xlsx` again

2. **Save As** → `CMY Channel analysis.xlsx` (same directory)

3. **Edit Row 15** (the header row):
   - Cell B15: Change to "C" (Cyan)
   - Cell C15: "SD" (keep)
   - Cell D15: "1/SD²" (keep)
   - Cell E15: Change to "M" (Magenta)
   - Cell F15: "SD" (keep)
   - Cell G15: "1/SD²" (keep)
   - Cell H15: Change to "Y" (Yellow)
   - Cell I15: "SD" (keep)
   - Cell J15: "1/SD²" (keep)
   
   This header should say: **Sample# | C | SD | 1/SD² | M | SD | 1/SD² | Y | SD | 1/SD²**

4. **Copy CMY Formulas to RGB Section**:
   - The formulas in rows 29-39 (CMY section) need to be copied to rows 16-26
   - Select rows 29-39, copy
   - Select row 16, paste
   - This moves the CMY calculations to the standard data position

5. **Delete Old Sections**:
   - Delete rows 27-50 (the old CMY section and unused rows)

6. **Update Labels**:
   - Row 22: Should say "Ave" (average row)
   - Rows 23-26: Update calculation labels to CMY equivalents:
     - Row 23: "8-bit" → keep
     - Row 24: "C-M" (was "R-G")
     - Row 25: "M-Y" (was "G-B")
     - Row 26: "C-Y" (was "R-B")

7. **Result**:
   - Rows 1-14: User input metadata (unchanged)
   - Row 15: Header (Sample#, C, SD, 1/SD², M, SD, 1/SD², Y, SD, 1/SD²)
   - Rows 16-21: Sample data (6 samples)
   - Row 22: "Ave" with averages
   - Rows 23-26: Additional calculations (8-bit, C-M, M-Y, C-Y)
   - **Important**: Averages are in **D22, G22, J22**

8. **Save** the file

### Template Summary

All three templates now have:
- **Rows 1-14**: User metadata input
- **Row 15**: Column headers (R/G/B or C/M/Y)
- **Rows 16-21**: 6 sample data rows
- **Row 22**: Averages row
- **D22, G22, J22**: Average values for channels 1, 2, 3

## How It Works

### Export Behavior

When you run RGB-CMY analysis:

1. **RGB + CMY (Combined)** mode:
   - Uses: `RGB-CMY Channel analysis.xlsx`
   - Populates: RGB data in rows 16-21, CMY data in rows 29-34
   - Result: Both sections filled

2. **RGB Only** mode:
   - Uses: `RGB Channel analysis.xlsx`
   - Populates: RGB data in rows 16-21
   - Result: Clean RGB-only spreadsheet, no empty CMY section

3. **CMY Only** mode:
   - Uses: `CMY Channel analysis.xlsx`
   - Populates: CMY data in rows 16-21
   - Result: Clean CMY-only spreadsheet, no empty RGB section

### Averages Location

**All templates** have averages in the same cells:
- **D22**: Channel 1 average (R or C)
- **G22**: Channel 2 average (G or M)
- **J22**: Channel 3 average (B or Y)

This consistency makes Plot3D integration simple!

## Plot3D Integration

### Future Enhancement

The averages in D22/G22/J22 can be automatically extracted and appended to Plot3D format spreadsheets.

### Planned Function

```python
def export_to_plot3d(analysis_results, output_spreadsheet):
    """
    Extract averages from RGB-CMY analysis and append to Plot3D spreadsheet.
    
    Args:
        analysis_results: Dict containing analyzer and mode
        output_spreadsheet: Path to Plot3D format spreadsheet
    
    Process:
        1. Read averages from D22, G22, J22
        2. Get filename as dataID
        3. Append row to Plot3D spreadsheet:
           dataID | value1 (D22) | value2 (G22) | value3 (J22)
    """
    pass
```

### Manual Process (Until Automated)

For now, you can manually copy:
1. Open your RGB-CMY export (e.g., `MyStamp_RGB_20251024_143000.xlsx`)
2. Note values in D22, G22, J22
3. Open your Plot3D spreadsheet
4. Add new row: `[Filename, D22_value, G22_value, J22_value]`

### Why This Works

- **RGB mode**: D22=R_avg, G22=G_avg, J22=B_avg → Direct Plot3D input
- **CMY mode**: D22=C_avg, G22=M_avg, J22=Y_avg → CMY color space plotting
- **Combined**: Both available, user chooses which to use

## Testing

### Test RGB Template
1. Run RGB-only analysis
2. Export results
3. Check that:
   - File uses "RGB Channel analysis.xlsx"
   - Only rows 16-21 have data
   - No empty CMY section
   - Averages in D22, G22, J22

### Test CMY Template
1. Run CMY-only analysis
2. Export results
3. Check that:
   - File uses "CMY Channel analysis.xlsx"
   - Only rows 16-21 have data
   - No empty RGB section
   - Averages in D22, G22, J22

### Test Combined Template
1. Run RGB+CMY analysis
2. Export results
3. Check that:
   - File uses "RGB-CMY Channel analysis.xlsx"
   - Rows 16-21 have RGB data
   - Rows 29-34 have CMY data
   - Both sections complete

## Troubleshooting

### Template Not Found
If you see "Template not found" error:
- Check template names exactly match:
  - `RGB Channel analysis.xlsx`
  - `CMY Channel analysis.xlsx`
  - `RGB-CMY Channel analysis.xlsx`
- Check they're in: `/Users/stanbrown/Desktop/StampZ-III-Binary/data/templates/`
- System falls back to combined template if mode-specific missing
- System falls back to CSV if no templates found

### Wrong Data in Export
- Verify template formulas reference correct cells
- Check that averages are calculated correctly
- Ensure row 15 labels match your mode (R/G/B or C/M/Y)

### Empty Cells
- Make sure you ran analysis before export
- Check that results contain the expected channel data (RGB or CMY)
- Verify mode matches your analysis type

## Benefits

### Cleaner Data
- No empty sections in exports
- Easier to review and analyze
- Professional appearance

### Simplified Workflow
- Consistent cell locations (D22, G22, J22)
- Easy to automate Plot3D integration
- Can script data extraction

### Better Organization
- RGB data separate from CMY data
- Combined option still available when needed
- Clear templates for different use cases

## Next Steps

1. **Create templates** following steps above
2. **Test each mode** to verify correct export
3. **Verify averages** are in D22, G22, J22
4. **Request Plot3D integration** if you want automatic appending to Plot3D spreadsheets

The templates are the foundation - once they're created, the code will automatically use them based on your selected analysis mode!
