# Cubic Polynomial Trendline Feature

## Overview
Added cubic (degree 3) polynomial trendline support to StampZ Plot_3D for more detailed non-linear trend analysis.

## What Was Added

### 1. Trendline Manager (`plot3d/trendline_manager.py`)
Added three new methods to support cubic regression:

- **`calculate_cubic_regression(df)`** - Fits a cubic surface through 3D data points
  - Equation: `z = ax³ + by³ + cx²y + dxy² + ex² + fy² + gxy + hx + iy + j`
  - Requires minimum 10 data points (10 coefficients to solve)
  - Uses least squares regression with numerical stability checks

- **`_fallback_cubic_regression(df)`** - Backup method if cubic fitting fails
  - Falls back to quadratic (degree 2) model
  - Sets cubic terms to zero

- **`get_cubic_points(df, num_points)`** - Generates the cubic surface grid for visualization
  - Returns 2D meshgrid (X, Y, Z) for wireframe plotting

- **`get_cubic_equation()`** - Returns the 10 coefficients
- **`get_cubic_color()`** / **`set_cubic_color()`** - Color management

### 2. Plot_3D UI (`plot3d/Plot_3D.py`)

Added UI checkbox in the "Trend Lines" panel:
- **"Cubic (degree 3)"** checkbox (appears below "Polynomial (degree 2)")
- Checkbox variable: `self.show_cubic`
- Color: Purple wireframe (to distinguish from blue polynomial)

### 3. Plot Rendering (`plot3d/Plot_3D.py`)

Added plotting code in `refresh_plot()` method:
- Calculates cubic regression when checkbox is enabled
- Renders as wireframe surface (similar to quadratic)
- Displays simplified equation on plot (top 4 terms only, due to length)
- Positioned at y=0.85 (below polynomial equation at y=0.90)
- Z-order: 18 (below polynomial but above data points)

## Comparison of Trendline Types

| Type | Equation Terms | Min Points | Use Case |
|------|---------------|------------|----------|
| **Linear** | 3 | 3 | Flat plane, simple trends |
| **Polynomial (Quadratic)** | 6 | 6 | Curved surface, scanner gamma curves |
| **Cubic** | 10 | 10 | Complex curves, S-shapes, inflection points |

## Cubic Surface Equation

The full cubic equation is:

```
z = ax³ + by³ + cx²y + dxy² + ex² + fy² + gxy + hx + iy + j
```

Where:
- **Cubic terms** (ax³, by³): Capture S-shaped curves along each axis
- **Mixed cubic terms** (cx²y, dxy²): Capture interactions between axes
- **Quadratic terms** (ex², fy²): Basic curvature
- **Linear terms** (hx, iy): Base trend direction
- **Constant** (j): Vertical offset

## When to Use Cubic vs Quadratic

**Use Quadratic (degree 2) when:**
- Data shows simple curvature
- Want simpler, more interpretable model
- Have 6-50 data points
- Scanner response curve looks smooth

**Use Cubic (degree 3) when:**
- Data shows complex non-linearities
- Need to capture S-shaped curves or inflection points
- Have 10+ data points (preferably 20+)
- Comparing different scanning conditions
- Scanner shows complex color response (e.g., shadows/highlights behave differently)

## Visual Comparison

- **Linear (black line)**: Straight plane through data
- **Polynomial (blue wireframe)**: Smooth curved surface
- **Cubic (purple wireframe)**: More complex surface with potential S-curves

## Testing

To test the new feature:

1. Load a data file with 10+ points into Plot_3D
2. Enable "Cubic (degree 3)" checkbox in Trend Lines panel
3. Compare with "Polynomial (degree 2)" to see additional curvature
4. Check console output for regression parameters
5. Verify purple wireframe displays correctly

## Technical Notes

- **Grid resolution**: Adaptive (10-20 points per axis based on dataset size)
- **Numerical stability**: Uses `rcond=1e-10` for least squares
- **Fallback behavior**: Degrades to quadratic if cubic fails
- **Color**: Purple (`'purple'`) to distinguish from polynomial (blue)
- **Transparency**: Alpha=0.7 for visibility

## Files Modified

1. `plot3d/trendline_manager.py` - Added cubic regression methods (~190 lines)
2. `plot3d/Plot_3D.py` - Added UI checkbox and plotting code (~140 lines)

## Performance

Cubic regression is computationally similar to quadratic:
- Calculation: O(n) where n = number of data points
- Rendering: O(g²) where g = grid_size (10-20)
- No significant performance impact for typical datasets (<1000 points)

---

**Date Added**: 2025-11-09  
**Author**: Claude (via Stan Brown)  
**Purpose**: Non-linear trend analysis for scanner color characterization
