# Color Library Import Format Guide

## Overview

StampZ can import color libraries from CSV files in **three different color space formats**: LAB, RGB, or HEX. The import function automatically detects which format is used.

## Required Columns

### Minimum Requirements

All import formats require:
- **Name column** (required): The name/identifier for each color

Plus **ONE** of the following color formats:

#### Option 1: L\*a\*b\* Format (Recommended)
- `lab_l` (or `L*`, `L`, `lightness`)
- `lab_a` (or `a*`, `a`, `green_red`)
- `lab_b` (or `b*`, `b`, `blue_yellow`)

#### Option 2: RGB Format
- `rgb_r` (or `r`, `red`)
- `rgb_g` (or `g`, `green`)
- `rgb_b` (or `b`, `blue`)

#### Option 3: HEX Format
- `hex` (or `hex_code`, `hexcode`, `hex_color`, `color_hex`, `#hex`, `html`)

## Important: Color Format Rules

### If Using HEX:
✅ **Only HEX column needed** - No RGB, Lab, or CMY columns required  
✅ StampZ automatically converts HEX → RGB → Lab for storage

### If Using RGB:
✅ **All three RGB values required** (R, G, B)  
✅ StampZ automatically converts RGB → Lab for storage  
❌ No HEX column needed

### If Using L\*a\*b\*:
✅ **All three Lab values required** (L\*, a\*, b\*)  
✅ StampZ automatically converts Lab → RGB for display  
❌ No HEX or RGB columns needed

### Summary Table:

| Format | Required Columns | Auto-Generated | Notes |
|--------|------------------|----------------|-------|
| **HEX** | `name`, `hex` | RGB, Lab | HEX → RGB → Lab |
| **RGB** | `name`, `rgb_r`, `rgb_g`, `rgb_b` | Lab | RGB → Lab |
| **Lab** | `name`, `lab_l`, `lab_a`, `lab_b` | RGB | Lab → RGB |

**Key Point:** You only need ONE color format. StampZ converts between them automatically!

## Optional Columns

These columns are recognized but not required:
- `description` (or `desc`, `comment`)
- `category` (or `type`, `group`)
- `source` (or `origin`, `reference`)
- `notes` (or `note`, `remarks`)

## CSV Format Examples

### Example 1: L\*a\*b\* Format (Recommended for Color Science)
```csv
name,description,lab_l,lab_a,lab_b,category,source,notes
Red,Bright red,53.24,80.09,67.20,Primary,Scott Catalog,
Blue,Deep blue,32.30,-10.24,-47.57,Primary,Stanley Gibbons,
Yellow,Chrome yellow,97.14,-21.55,94.48,Primary,Pantone,
```

### Example 2: RGB Format (Common for Digital Colors)
```csv
name,description,rgb_r,rgb_g,rgb_b,category,source,notes
Red,Bright red,255,0,0,Primary,,
Blue,Deep blue,0,0,255,Primary,,
Yellow,Chrome yellow,255,255,0,Primary,,
```

### Example 3: HEX Format (Web/HTML Colors)
```csv
name,description,hex,category,source,notes
Red,Bright red,#FF0000,Primary,,
Blue,Deep blue,#0000FF,Primary,,
Yellow,Chrome yellow,#FFFF00,Primary,,
```

### Example 4: Minimal Format (Just Name and HEX)
```csv
name,hex
Red,#FF0000
Blue,#0000FF
Yellow,#FFFF00
Green,#00FF00
```

## Flexible Column Names

StampZ recognizes many variations of column names (case-insensitive):

### Name Column:
- `name`, `color_name`, `color`

### L\*a\*b\* Columns:
- **L\*:** `lab_l`, `L*`, `L_star`, `L`, `lightness`
- **a\*:** `lab_a`, `a*`, `a_star`, `a`, `green_red`
- **b\*:** `lab_b`, `b*`, `b_star`, `b`, `blue_yellow`

### RGB Columns:
- **R:** `rgb_r`, `r`, `red`
- **G:** `rgb_g`, `g`, `green`
- **B:** `rgb_b`, `b`, `blue`

### HEX Column:
- `hex`, `hex_code`, `hexcode`, `hex_color`, `color_hex`, `#hex`, `html`

### Optional Columns:
- **Description:** `description`, `desc`, `comment`
- **Category:** `category`, `type`, `group`
- **Source:** `source`, `origin`, `reference`
- **Notes:** `notes`, `note`, `remarks`

## Data Validation

StampZ validates color values during import:

### L\*a\*b\* Ranges:
- **L\*:** 0 to 100 (warnings if outside)
- **a\*:** -128 to +127 (warnings if outside)
- **b\*:** -128 to +127 (warnings if outside)

### RGB Ranges:
- **R, G, B:** 0 to 255

### HEX Format:
- Standard 6-digit hex codes: `#RRGGBB`
- With or without `#` symbol

## Import Priority

If a CSV file contains **multiple color formats**, StampZ uses this priority:

1. **L\*a\*b\*** (preferred - most accurate)
2. **HEX** (common - web colors)
3. **RGB** (fallback)

## Common Questions

### Q: 
## Example Workflows

### Workflow 1: Creating from Scratch (Minimal)
```csv
name,hex
Scott #1,#C71585
Scott #2,#4169E1
Scott #3,#FFD700
```
Simple! Just name and hex code.

### Workflow 2: Detailed Catalog
```csv
name,description,lab_l,lab_a,lab_b,category,source,notes
Scott 1c Rose,1851 Franklin rose,48.50,65.20,23.10,Definitive,Scott Catalog,Unused
Scott 2 Blue,1851 Washington blue,32.30,-10.24,-47.57,Definitive,Scott Catalog,Plate 1
```
Full details with Lab values for maximum accuracy.

### Workflow 3: Web Colors Import
```csv
name,hex,category
Royal Red,#DC143C,Primary
Sky Blue,#87CEEB,Secondary
Forest Green,#228B22,Accent
```
Mix of name, hex, and organization category.

## Export Formats

StampZ can **export** libraries in three formats:
- L\*a\*b\* format (recommended)
- RGB format
- CMY format (calculated from RGB: C=255-R, M=255-G, Y=255-B)

**Note:** CMY export is for reference only. Use Lab, RGB, or HEX for re-importing.

## Tips for Best Results

1. ✅ **Use Lab format** when possible for color accuracy
2. ✅ **Use HEX format** for convenience (web colors)
3. ✅ **Include descriptions** for better organization
4. ✅ **Use categories** to group related colors
5. ✅ **Keep names unique** within a library
6. ⚠️ **Avoid CMYK** - not a supported import format
7. ⚠️ **Don't mix formats** - use one color space per file

## File Requirements

- **Format:** CSV (comma-separated values)
- **Encoding:** UTF-8 (recommended)
- **Line Endings:** Any (Unix, Windows, Mac)
- **Header Row:** Required (column names)
- **Extension:** `.csv`

---

**Summary:** Import with **name** + **one of** (HEX, RGB, or Lab). StampZ handles all conversions automatically!
