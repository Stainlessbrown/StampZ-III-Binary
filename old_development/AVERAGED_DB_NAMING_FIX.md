# Averaged Database Naming Standardization

## Problem
The StampZ app was creating averaged databases with multiple inconsistent naming patterns:
- `_average.db`
- `_averages.db`
- `_AVG.db`
- `_AVERAGE.db`
- `_AVG_averages.db`
- `_AVERAGES_averages.db`
- `_AVG_average.db`
- `_AVERAGE_average.db`

This inconsistency made it difficult to:
1. Locate averaged databases
2. Understand which databases contained averaged data
3. Filter databases programmatically

## Solution
Standardized all averaged database naming to use **`_AVG.db`** suffix only.

### Changes Made

#### 1. Core Database Class (`utils/color_analysis_db.py`)
- Modified `AveragedColorAnalysisDB.__init__()` to:
  - Strip any existing average-related suffixes
  - Apply only the standard `_AVG` suffix
  - Handle all variations of average suffixes

#### 2. Analysis Manager (`app/analysis_manager.py`)
- Updated RGB/CMY channel save to use `_AVG.db` instead of `_AVG_averages.db`
- Fixed info text in dialog to show correct naming pattern
- Updated database filter to recognize all average suffix variations

#### 3. Sample Results Manager (`gui/sample_results_manager.py`)
- Changed `_AVERAGES` suffix to `_AVG` in quick save
- Updated both quick save and dialog save paths
- Fixed file list reporting to show correct `.db` extension

#### 4. Color Analyzer (`utils/color_analyzer.py`)
- Updated comments to reflect `_AVG` suffix instead of `_averages`
- Fixed debug message to show actual database path

#### 5. Preferences Dialog (`gui/preferences_dialog.py`)
- Updated UI text to show `_AVG.db` suffix
- Changed checkbox label from "AVERAGES" to "AVG"

#### 6. User Preferences (`utils/user_preferences.py`)
- Updated comments and docstrings to reflect `_AVG` suffix

### Naming Convention

**Individual Sample Data:**
```
{database_name}.db
```

**Averaged Data:**
```
{database_name}_AVG.db
```

**RGB/CMY Channel Analysis:**
```
{database_name}_RGB.db         (individual channels)
{database_name}_RGB_AVG.db     (averaged channels)
{database_name}_CMY.db         (individual channels)
{database_name}_CMY_AVG.db     (averaged channels)
```

### Migration

#### Existing Databases
Use the provided `rename_averaged_databases.py` script to rename existing databases:

```bash
cd ~/Desktop/StampZ-III-Binary
python3 rename_averaged_databases.py
```

The script will:
1. Scan for all databases with non-standard average suffixes
2. Show what would be renamed (dry run option)
3. Rename databases to standard `_AVG.db` format
4. Create a log file of all renames

#### Manual Rename
If you prefer to rename manually:

```bash
# Example: rename _AVERAGES_averages to _AVG
mv "DatabaseName_AVERAGES_averages.db" "DatabaseName_AVG.db"
```

### Testing
After the fix, all new averaged databases created through:
- Results Manager (Quick Save)
- Results Manager (Save Dialog)
- RGB/CMY Channel Analysis
- Compare Mode (if auto-save enabled)

...will use the standard `_AVG.db` suffix.

### Backward Compatibility
The `AveragedColorAnalysisDB` class now automatically handles any legacy naming:
- When instantiated with any average-related suffix, it strips it and applies `_AVG`
- Existing code that passes database names with old suffixes will still work correctly
- The class normalizes all inputs to the standard format

## Benefits
1. **Consistency**: Single, clear naming pattern
2. **Simplicity**: Shorter, clearer suffix (`_AVG` vs `_AVERAGES_averages`)
3. **Maintainability**: Easier to filter and search for averaged databases
4. **User-Friendly**: Less confusion about which databases contain averaged data

## Date
2026-01-04
