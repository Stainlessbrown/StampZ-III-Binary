# CMY Color Space Export Preference

## Overview
CMY (Cyan, Magenta, Yellow) color space has been added to the Export Settings preferences, allowing users to control whether CMY values are included in their exports.

## Location
**Preferences → Export Settings → Color Space Selection**

## Available Color Spaces
Users can now select any combination of three color spaces for export:

1. **RGB** (Red, Green, Blue)
   - Native scanned image format
   - Range: 0-255 per channel
   - Additive color model

2. **L\*a\*b\*** (CIE L\*a\*b\*)
   - Perceptually uniform color space
   - Better for color analysis and comparisons
   - Device-independent

3. **CMY** (Cyan, Magenta, Yellow) — NEW
   - Subtractive color model
   - Calculated as 255 - RGB
   - Range: 0-255 per channel
   - Useful for print and ink analysis

## Usage

### Enabling CMY Export
1. Open **Preferences** (Gear icon or menu)
2. Navigate to **Export Settings** tab
3. In the **Color Space Selection** section, check:
   - ☑ **Include CMY color values (Cyan, Magenta, Yellow)**
4. Click **OK** or **Apply**

### Use Cases for CMY

#### Print Analysis
- CMY represents subtractive color mixing (used in printing)
- Higher CMY values = more ink/pigment
- Useful for analyzing ink coverage and density

#### Stamp Color Studies
- Traditional printing uses subtractive color model
- CMY values can reveal printing techniques
- Helps identify ink formulations and variations

#### Color Comparison
- Some reference standards use CMY notation
- Easier to compare with historical print data
- Complements RGB analysis for complete picture

### Export Behavior
When CMY is enabled:
- CMY columns (C, M, Y) added to exported spreadsheets
- Works with ODS, XLSX, and CSV formats
- Can be combined with RGB and/or L\*a\*b\*
- Values calculated automatically from RGB data

## Relationship to RGB-CMY Analysis
This preference is **separate** from the RGB-CMY Channel Analysis feature:

### RGB-CMY Channel Analysis (in GUI)
- Standalone tool for detailed channel analysis
- Provides channel-separated statistics
- Exports specialized analysis spreadsheets
- Includes L\*a\*b\* conversion for plotting
- Has its own analysis mode selector (RGB/CMY/Both)

### Export Settings Preference
- Applies to **all regular color analysis exports**
- Controls which color spaces appear in standard spreadsheets
- Works with normal color sampling workflow
- Affects coordinate-based color measurements

## Technical Details

### CMY Calculation
```
C (Cyan)    = 255 - R (Red)
M (Magenta) = 255 - G (Green)  
Y (Yellow)  = 255 - B (Blue)
```

This is the **simple subtractive model**, representing ink absorption rather than light emission.

### Data Storage
- Stored in user preferences: `preferences.json`
- Default value: `False` (CMY not included by default)
- Persists across application sessions
- Can be reset to defaults in Preferences dialog

### Validation
- At least one color space must always be selected
- System prevents unchecking all color spaces
- If attempt to disable all, RGB is automatically re-enabled

## Compatibility

### Existing Exports
- Enabling CMY adds new columns to existing export format
- Does not affect previously exported files
- Backward compatible with older StampZ versions (they ignore CMY columns)

### File Formats
- **ODS**: Full support with formulas
- **XLSX**: Full support with formulas
- **CSV**: Plain values, no formulas

### Normalized Exports
When "Export normalized values" is enabled:
- CMY values normalized to 0.0-1.0 range (divided by 255)
- Consistent with RGB and L\*a\*b\* normalization
- Useful for machine learning and statistical analysis

## Benefits

### For Philatelists
- Matches traditional color terminology used in stamp catalogues
- Easier to describe ink colors and variations
- Historical printing context (subtractive mixing)

### For Researchers
- Complete color representation (both additive and subtractive)
- Additional data points for statistical analysis
- Correlation studies between RGB and CMY

### For Print Professionals
- Natural color space for CMYK printing systems
- Easier to relate to ink formulations
- Useful for reproduction and restoration work

## Examples

### Basic Color Analysis with CMY
1. Load stamp image
2. Place color sample markers
3. Enable CMY in preferences
4. Export results → CMY columns included

### Selective Export
Want only CMY and L\*a\*b\*, not RGB?
1. Preferences → Export Settings
2. ☐ Uncheck RGB
3. ☑ Check L\*a\*b\*
4. ☑ Check CMY
5. Export contains only L\*a\*b\* and CMY columns

### Combining with RGB-CMY Analysis
For comprehensive analysis:
1. Use RGB-CMY Channel Analysis tool for detailed statistics
2. Enable CMY in Export Settings for regular measurements
3. Get both specialized channel analysis AND CMY in coordinate samples
4. Complete color characterization of your stamps

## Notes

- CMY is calculated from RGB, not measured separately
- Assumes simple subtractive color model (not full CMYK with black)
- Values represent color **absorption** rather than **emission**
- For CMYK printing, K (black) channel would need separate measurement

## Related Features
- RGB-CMY Channel Analysis (standalone tool)
- L\*a\*b\* color space export
- Normalized value export
- Plot3D visualization (can plot in any color space)
