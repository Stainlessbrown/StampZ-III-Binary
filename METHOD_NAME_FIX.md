# Quick Fix: ColorAnalysisDB Method Name Error

## Issue
Error message: `'ColorAnalysisDB' object has no attribute 'save_measurement'`

## Root Cause
The ColorAnalysisDB class uses `save_color_measurement()` not `save_measurement()`

## Fix Applied
Changed the method call in `gui/sample_results_manager.py`:

**Before (incorrect):**
```python
saved = individual_db.save_measurement(
    set_id=set_id,
    coordinate_point=measurement['id'],
    # ... wrong parameter names
)
```

**After (correct):**
```python
saved = individual_db.save_color_measurement(
    set_id=set_id,
    coordinate_point=int(measurement['id'].replace('sample_', '')),
    x_pos=measurement['x_position'],
    y_pos=measurement['y_position'],
    l_value=measurement['l_value'],
    a_value=measurement['a_value'],
    b_value=measurement['b_value'],
    rgb_r=measurement['rgb_r'],
    rgb_g=measurement['rgb_g'],
    rgb_b=measurement['rgb_b'],
    sample_type=measurement['sample_type'],
    sample_size=f"{measurement['sample_width']}x{measurement['sample_height']}",
    sample_anchor=measurement['anchor'],
    notes=f"Sample from Results Manager"
)
```

## Additional Fixes
- **Parameter Names**: Updated to match the actual method signature
- **Coordinate Point**: Convert from "sample_1" format to integer (1)
- **Sample Size**: Format as string "WxH" as expected by the database
- **Data Types**: Ensure all parameters match expected types

## Status
✅ **FIXED** - Save Results dialog should now work properly with both individual samples and averages.