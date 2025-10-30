# StampZ-III Binary Version

This repository contains the **binary coordinate system** version of StampZ-III, which uses XYZ coordinates for color analysis.

## Key Differences from Ternary Version

- **Coordinate System**: Uses binary XYZ coordinates (not ternary Lab/Luv)
- **Clustering**: K-means clustering with 5 clusters maximum
- **ΔE Calculations**: Distance calculations between points and cluster centroids
- **Database Schema**: Optimized for XYZ coordinate storage

## Recent Fixes (September 2024)

### Numpy Ufunc Type Errors - RESOLVED ✅
- Fixed `numpy ufunc 'less'` and `'greater'` type mismatch errors
- Resolved mixed int/str cluster ID comparison issues in `delta_e_manager.py`
- Ensured consistent string-based cluster ID handling throughout the codebase
- All K-means clustering and ΔE workflows now function without type errors

### Key Changes Made:
1. **delta_e_manager.py**: Fixed cluster mask operations to use consistent string types
2. **realtime_plot3d_sheet.py**: Enhanced cluster ID type handling  
3. **ΔE Precision**: Added 4-decimal place precision for ΔE calculations
4. **Database Operations**: All save/update operations working correctly

## Usage

```bash
python3 main.py
```

## Current Status

✅ **Fully Functional**
- K-means clustering working without errors
- ΔE calculations with proper precision
- Database persistence working
- Worksheet updates functioning correctly
- No numpy ufunc type conflicts

## Repository Structure

This is the stable binary version, separate from the ternary coordinate system version (StampZ-IIIx).

## Fallback Point

This commit represents a stable working state with all numpy type issues resolved. Safe to use as a fallback point before implementing new features.