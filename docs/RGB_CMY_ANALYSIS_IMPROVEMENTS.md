# RGB-CMY Channel Analysis Improvements

## Overview
The RGB-CMY channel mask analysis feature has been enhanced to provide separate analysis options and improved data formats for plotting and visualization.

## New Features

### 1. Separate Analysis Modes
You can now choose which color channels to analyze:

- **RGB + CMY** (default): Analyzes both RGB and CMY channels
- **RGB Only**: Analyzes only RGB channels
- **CMY Only**: Analyzes only CMY channels

This provides flexibility to focus on just the channels you need, reducing data complexity and improving clarity.

### 2. L*a*b* Color Space Conversion
For RGB analysis, the system now automatically converts RGB values to **CIE L*a*b*** color space:

- **L*** (Lightness): 0-100
- **a*** (green-red axis): typically -128 to +128
- **b*** (blue-yellow axis): typically -128 to +128

#### Why L*a*b*?
- **Perceptually uniform**: Equal distances in L*a*b* space correspond to roughly equal perceived color differences
- **Better for plotting**: More intuitive visualization of color relationships
- **Delta E calculations**: Enables accurate color difference measurements
- **Device independent**: Unlike RGB, L*a*b* is not tied to a specific display or printer

### 3. New Export Options

#### Standard Export (Excel/CSV)
- Exports raw RGB and/or CMY channel data
- Includes statistics (mean, standard deviation, inverse variance)
- Compatible with existing templates

#### L*a*b* CSV Export
- **New button**: 🌈 Export L*a*b* CSV
- Exports perceptually uniform color data
- Ideal for:
  - Plotting in 3D color space
  - Color difference analysis
  - Scientific visualization
  - Integration with Plot3D features

### 4. Enhanced Results Display
The results view now shows:
- RGB values (R, G, B)
- L*a*b* values (L*, a*, b*) when available
- CMY values (C, M, Y) when requested
- Summary statistics for all measured channels

## Usage Example

### For Plotting RGB Data:
1. Load your stamp image
2. Create/load masks for color regions
3. Select **"RGB Only"** mode
4. Click **"🔬 Run Analysis"**
5. Click **"🌈 Export L*a*b* CSV"**
6. Use the CSV in your plotting software with perceptually uniform axes

### For Complete Analysis:
1. Select **"RGB + CMY"** mode
2. Run analysis to get both color spaces
3. Export to Excel for comprehensive statistics
4. Export L*a*b* CSV for plotting

### For CMY-Only:
1. Select **"CMY Only"** mode
2. Run analysis for subtractive color model data
3. Export results with only CMY statistics

## Database Storage
Results are saved with mode-specific naming:
- `{name}_RGB.db` - RGB-only data
- `{name}_CMY.db` - CMY-only data
- `{name}_RGBCMY.db` - Combined RGB+CMY data
- `{name}_RGB_AVG.db` - Averaged RGB statistics
- `{name}_CMY_AVG.db` - Averaged CMY statistics
- `{name}_RGBCMY_AVG.db` - Averaged combined statistics

## Technical Details

### Color Space Conversion
The RGB to L*a*b* conversion uses:
- **colorspacious** library (if available) for precise conversion
- Fallback to accurate approximation if colorspacious not installed
- sRGB color space with D65 illuminant
- Standard CIE L*a*b* (CIELAB 1976)

### Data Structure
Each analysis result now includes (when RGB mode selected):
```python
{
    'sample_name': str,
    'pixel_count': int,
    'R_mean': float,  # 0-255
    'G_mean': float,  # 0-255
    'B_mean': float,  # 0-255
    'L_mean': float,  # 0-100
    'a_mean': float,  # typically -128 to +128
    'b_mean': float,  # typically -128 to +128
    # ... plus std deviations and CMY if requested
}
```

## Benefits

### For Analysis
- **Focused data**: Only compute and export what you need
- **Cleaner results**: Separate RGB and CMY for easier interpretation
- **Better accuracy**: L*a*b* provides perceptually meaningful measurements

### For Plotting
- **Uniform space**: L*a*b* plots show perceptual color relationships accurately
- **Easy comparison**: Color differences are proportional to visual differences
- **3D visualization**: L*a*b* works excellently in 3D color space plots
- **Simpler normalization**: L*a*b* ranges are more consistent than RGB/CMY

### For Workflow
- **Flexibility**: Choose analysis mode based on your needs
- **Compatibility**: Works with existing StampZ features
- **Integration**: L*a*b* data works with Plot3D for advanced visualization

## Recommendations

- **For color variation studies**: Use RGB+CMY mode
- **For plotting and visualization**: Export L*a*b* CSV
- **For print analysis**: CMY mode focuses on subtractive colors
- **For digital/screen colors**: RGB mode with L*a*b* export
- **For scientific papers**: L*a*b* provides standardized, device-independent data

## Future Enhancements
Potential additions:
- Direct Plot3D integration from RGB-CMY analysis
- Delta E calculations between mask regions
- Color clustering in L*a*b* space
- Gamut visualization
