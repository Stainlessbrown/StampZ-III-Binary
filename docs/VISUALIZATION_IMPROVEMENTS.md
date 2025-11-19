# Plot_3D Visualization Improvements

## Changes Made - 2025-11-09

### 1. Better Wireframe Colors
Changed polynomial surface colors for better visual contrast:

- **Polynomial (degree 2)**: `blue` → **`cyan`** (bright blue-green)
- **Cubic (degree 3)**: `purple` → **`orange`**

This makes the two wireframe grids much easier to distinguish visually.

### 2. Added Exponential Curved Line

Added a new **single curved line** option (not a grid/surface):

**What it is:**
- A smooth **red curved line** through your 3D data
- Uses PCA (Principal Component Analysis) to find the main direction through the data
- Fits a power law curve: `z = a * distance^b + c`
- Much cleaner visually than wireframe grids

**When to use it:**
- Want a clean, simple curved trend line
- Scanner gamma/response curve analysis
- Less "busy" than polynomial wireframes
- Good for presentations/publications

**Checkbox:** "Exponential Curve" (red line)

### Summary of All Trendline Options

| Type | Visual | Color | Use Case |
|------|--------|-------|----------|
| **Linear** | Line (plane) | Black | Simple flat trends |
| **Polynomial (deg 2)** | Wireframe grid | Cyan | Curved surface |
| **Cubic (deg 3)** | Wireframe grid | Orange | Complex surface |
| **Exponential Curve** | **Smooth curved line** | **Red** | **Clean curved trend** |
| R/G/B filters | Lines | Red/Green/Blue | Color-specific trends |

## Visual Comparison

### Grid/Surface Options (more detail, more "busy"):
- Polynomial (cyan wireframe)
- Cubic (orange wireframe)

### Line Options (cleaner):
- Linear (black straight line)
- **Exponential (red curved line)** ← NEW!
- R/G/B filtered lines

## Technical Details

**Exponential Curve Fitting:**
1. Uses PCA to find principal direction through data
2. Projects all points onto this direction
3. Fits power law: `z = a * (distance)^b + c`
4. Generates smooth curve along principal axis
5. Requires minimum 4 data points

**Fallback behavior:**
- If power law fails → polynomial curve
- If PCA unavailable → simple linear fallback

**Visualization:**
- Line width: 2.5 (thicker than other lines for visibility)
- Z-order: 35 (above everything else)
- Alpha: 0.9 (slight transparency)

## Files Modified

1. `plot3d/trendline_manager.py`
   - Changed colors (lines 15, 18)
   - Added exponential curve methods (~200 lines)

2. `plot3d/Plot_3D.py`
   - Added exponential checkbox (line ~1547)
   - Added exponential plotting code (~60 lines)

## Usage

1. Load data into Plot_3D
2. Check "Exponential Curve" in Trend Lines panel
3. See red curved line through your data
4. Compare with polynomial wireframes

The exponential curve is perfect when you want to show a trend without the visual complexity of wireframe grids!

---

**Date**: 2025-11-09  
**Purpose**: Reduce visual "busyness" while maintaining analytical options
