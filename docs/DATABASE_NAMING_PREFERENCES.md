# Database Naming Preferences

## Overview
Control how databases are named when saving analysis results through preferences instead of entering names manually each time.

## New Preferences

### In Sampling Tab → Analysis Save Preferences

```
┌─────────────────────────────────────────────────────┐
│  Analysis Save Preferences                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Default database name: [ColorAnalysis          ]  │
│                                                     │
│  Individual samples will save to: {name}.db        │
│  Averages will save to: {name}_AVERAGES_averages.db│
│                                                     │
│  ☑ Save individual sample measurements by default  │
│  ☑ Save calculated average by default              │
│  ☑ Automatically add _AVERAGES suffix to average   │
│     database names                                  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Settings Explained

### 1. Default Database Name
**Setting:** Text field for database name
**Default:** `ColorAnalysis`

**How it works:**
- When creating a new database, this name is suggested
- Can be overridden per-save in the dialog
- Smart logic: uses filename if default is generic

**Examples:**
- Preference set to `"MyProject"` → saves to `MyProject.db`
- Preference set to `"ColorAnalysis"` + file is `stamp01.tif` → saves to `Results_stamp01.db`
- Preference set to `"SG_Analysis"` → always uses `SG_Analysis.db`

### 2. Save Individual/Average Checkboxes
**Settings:** Checkboxes (already implemented)
**Default:** Both enabled

Controls which checkboxes are pre-selected in the save dialog.

### 3. Automatically Add _AVERAGES Suffix
**Setting:** Checkbox
**Default:** Enabled

**How it works:**
- **Enabled:** Average database gets `_AVERAGES` suffix automatically
  - Individual: `ColorAnalysis.db`
  - Average: `ColorAnalysis_AVERAGES_averages.db`

- **Disabled:** Both use the same base name
  - Individual: `ColorAnalysis.db`
  - Average: `ColorAnalysis_averages.db`

## Workflow Examples

### Example 1: Default Behavior (All Enabled)

**Preferences:**
```
Default database name: ColorAnalysis
☑ Save individual samples
☑ Save calculated average  
☑ Automatically add _AVERAGES suffix
```

**Result when saving:**
- Dialog pre-fills: `ColorAnalysis`
- Individual samples → `ColorAnalysis.db`
- Averaged results → `ColorAnalysis_AVERAGES_averages.db`

**File structure:**
```
data/color_analysis/
├── ColorAnalysis.db                    ← All individual measurements
└── ColorAnalysis_AVERAGES_averages.db  ← All averaged results
```

### Example 2: Project-Specific Database

**Preferences:**
```
Default database name: SG_Colors_2025
☑ Save individual samples
☑ Save calculated average
☑ Automatically add _AVERAGES suffix
```

**Result:**
- Individual samples → `SG_Colors_2025.db`
- Averaged results → `SG_Colors_2025_AVERAGES_averages.db`

**Benefit:** All your project data in clearly named databases!

### Example 3: Single Database (No Suffix)

**Preferences:**
```
Default database name: Analysis
☑ Save individual samples
☑ Save calculated average
☐ Automatically add _AVERAGES suffix  ← DISABLED
```

**Result:**
- Individual samples → `Analysis.db`
- Averaged results → `Analysis_averages.db`

**Note:** Both use "Analysis" as base, differentiated only by `_averages.db` extension

### Example 4: Filename-Based (Smart Default)

**Preferences:**
```
Default database name: ColorAnalysis  ← Generic name
☑ Save individual samples
☑ Save calculated average
☑ Automatically add _AVERAGES suffix
```

**When analyzing `stamp_SG_01.tif`:**
- Dialog suggests: `Results_stamp_SG_01`
- Individual → `Results_stamp_SG_01.db`
- Average → `Results_stamp_SG_01_AVERAGES_averages.db`

**Smart behavior:** Generic defaults use filename; specific names are preserved!

## Database Locations

All databases are stored in:
```
~/Library/Application Support/StampZ-III/data/color_analysis/
```

Individual measurements:
- `{name}.db`

Averaged results:
- `{name}_AVERAGES_averages.db` (with suffix)
- `{name}_averages.db` (without suffix)

## Understanding the Suffixes

### Why Two Suffixes?

The system uses two suffixes for average databases:

1. **`_AVERAGES`** - User-configurable prefix (optional)
   - Distinguishes average DB from individual DB
   - Makes it clear which database contains averages
   - Can be turned off in preferences

2. **`_averages.db`** - System suffix (always present)
   - Required by the ColorAnalyzer system
   - Identifies the file as an averages database
   - Cannot be changed

**Full pattern:**
```
{base_name}_AVERAGES_averages.db
│           └─────────┴──────────┘
│           User Pref   System
└─ Your database name
```

**Example:**
- Base: `MyProject`
- With prefix: `MyProject_AVERAGES_averages.db`
- Without prefix: `MyProject_averages.db`

## Technical Details

### New Dataclass Fields

```python
@dataclass
class SampleAreaPreferences:
    # ... existing fields ...
    default_database_name: str = "ColorAnalysis"
    use_averages_suffix: bool = True
```

### New API Methods

```python
# Get/set default database name
prefs.get_default_database_name() -> str
prefs.set_default_database_name(name: str)

# Get/set averages suffix preference
prefs.get_use_averages_suffix() -> bool
prefs.set_use_averages_suffix(use_suffix: bool)
```

### Integration Points

**1. Save Dialog Initialization** (`gui/sample_results_manager.py`):
```python
# Get default from preferences
default_db_name = prefs.get_default_database_name()

# Smart logic: use filename if default is generic
if default_db_name in ["ColorAnalysis", "Results_Analysis"]:
    new_db_var.set(f"Results_{file_base}")
else:
    new_db_var.set(default_db_name)
```

**2. Average Database Naming**:
```python
# Check suffix preference
use_averages_suffix = prefs.get_use_averages_suffix()

# Apply suffix conditionally
if use_averages_suffix:
    avg_db_name = f"{final_db_name}_AVERAGES"
else:
    avg_db_name = final_db_name
```

## Benefits

### For Users
✅ **Set once, use everywhere** - No repetitive typing
✅ **Consistent naming** - All your analyses use the same database
✅ **Clear separation** - `_AVERAGES` suffix makes it obvious
✅ **Flexible** - Can use project names or generic names
✅ **Smart defaults** - Falls back to filename when appropriate

### For Workflows
✅ **Project-based** - Use one database per project
✅ **Stamp-based** - Use one database per stamp
✅ **Session-based** - Use generic name for the session
✅ **Organized** - Easy to find your data

## Common Use Cases

### Use Case 1: Research Project
**Goal:** Keep all project data together

**Setup:**
```
Default database: MyResearchProject_2025
☑ Save individual samples
☑ Save calculated average
☑ Use _AVERAGES suffix
```

**Result:**
- All samples → `MyResearchProject_2025.db`
- All averages → `MyResearchProject_2025_AVERAGES_averages.db`

### Use Case 2: Catalog Analysis
**Goal:** Separate database per catalog

**Setup:**
```
Default database: SG_Catalog
☑ Save individual samples
☑ Save calculated average
☑ Use _AVERAGES suffix
```

**Result:**
- SG catalog samples → `SG_Catalog.db`
- SG catalog averages → `SG_Catalog_AVERAGES_averages.db`

### Use Case 3: Batch Processing
**Goal:** Each stamp gets its own database

**Setup:**
```
Default database: ColorAnalysis  ← Generic
☑ Save individual samples
☑ Save calculated average
☑ Use _AVERAGES suffix
```

**Result (automatic):**
- `stamp01.tif` → `Results_stamp01.db` + `Results_stamp01_AVERAGES_averages.db`
- `stamp02.tif` → `Results_stamp02.db` + `Results_stamp02_AVERAGES_averages.db`

### Use Case 4: Simple Workflow
**Goal:** Just use one database for everything

**Setup:**
```
Default database: Analysis
☑ Save individual samples
☑ Save calculated average
☐ Use _AVERAGES suffix  ← Disabled for simplicity
```

**Result:**
- All samples → `Analysis.db`
- All averages → `Analysis_averages.db`

## Migration

Existing workflows continue to work:
- If preferences don't exist, defaults are used
- `"ColorAnalysis"` is the default database name
- `_AVERAGES` suffix is enabled by default
- Matches previous behavior when manually typing names

## Tips

1. **Project names:** Use descriptive names for long-term projects
2. **Generic default:** Keep "ColorAnalysis" for one-off analyses
3. **Suffix preference:** Keep enabled for clarity, disable for simplicity
4. **Override anytime:** Can always change in the save dialog

## Files Modified

- `utils/user_preferences.py` - New fields and methods
- `gui/preferences_dialog.py` - UI for database preferences
- `gui/sample_results_manager.py` - Uses preferences in save dialog
- `docs/DATABASE_NAMING_PREFERENCES.md` - This documentation
