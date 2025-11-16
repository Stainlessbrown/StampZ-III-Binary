# Database Preferences - Quick Guide

## How It Works

The database preferences in **Sampling → Analysis Save Preferences** control what's automatically selected when you click "Save Results".

### Smart Default Behavior

```
┌─────────────────────────────────────────────────────┐
│  When you click "Save Results", the dialog...       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. Checks your preference database name           │
│  2. If it EXISTS → selects "Use existing database" │
│  3. If it DOESN'T exist → selects "Create new"     │
│  4. Pre-fills with your preference name            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Examples

### Scenario 1: First Time (Database Doesn't Exist)

**Preference:** `MyProject`

**What you see:**
```
⦿ Create new database: [MyProject              ]
○ Use existing database: (disabled - none found)
```

**After saving once:**
- `MyProject.db` is created
- Next time, it will be pre-selected!

### Scenario 2: Database Exists

**Preference:** `MyProject`  
**Existing databases:** `MyProject`, `OtherDB`

**What you see:**
```
⦿ Use existing database: [MyProject        ▼]
○ Create new database: [MyProject              ]
```

**Selected automatically** because it exists!

### Scenario 3: Different Preference Database

**Preference:** `NewProject`  
**Existing databases:** `MyProject`, `OtherDB`

**What you see:**
```
○ Use existing database: [MyProject        ▼]
⦿ Create new database: [NewProject             ]
```

**Creates new** because `NewProject` doesn't exist yet.

## Important Points

### ✅ These Settings Control:
- Which database is **pre-selected** in the dialog
- Which checkboxes are **pre-checked**
- What **suffix** is added to averages

### ❌ These Settings DON'T:
- Auto-save without showing the dialog
- Force you to use a specific database
- Prevent you from changing choices in the dialog

### 🎯 The Goal:
**Reduce clicks** by having sensible defaults, while still giving you full control each time.

## Checkbox Meanings

### "Save individual sample measurements by default"
- ✅ Checked → "Save individual" checkbox **starts checked** in dialog
- ❌ Unchecked → "Save individual" checkbox **starts unchecked** in dialog
- You can still toggle it in the dialog!

### "Save calculated average by default"
- ✅ Checked → "Save average" checkbox **starts checked** in dialog
- ❌ Unchecked → "Save average" checkbox **starts unchecked** in dialog
- You can still toggle it in the dialog!

### "Automatically add _AVERAGES suffix"
- ✅ Checked → Average saved to `{name}_AVERAGES_averages.db`
- ❌ Unchecked → Average saved to `{name}_averages.db`
- Applied automatically based on setting

## Workflow

```
1. Set preferences ONCE:
   ├─ Default database name: "MyProject"
   ├─ ☑ Save individual samples
   ├─ ☑ Save calculated average
   └─ ☑ Use _AVERAGES suffix

2. During analysis:
   ├─ Place samples
   ├─ Click "Save Results"
   └─ Dialog opens with everything pre-filled!

3. In the dialog:
   ├─ Already selected: "Use existing: MyProject"
   ├─ Already checked: ☑ Save individual ☑ Save average
   └─ Just click "Save" → Done!
```

## Priority Logic

The dialog chooses the default selection in this order:

1. **If preference database exists** → Select it from "Use existing"
2. **If preference database doesn't exist** → Select "Create new" with that name
3. **Fallback** → Use last used database if available

## Tips

### For Consistent Projects:
```
Set: "MyProject"
Result: All analyses go to MyProject.db automatically
```

### For Per-File Databases:
```
Set: "ColorAnalysis" (generic name)
Result: Uses filename (e.g., "Results_stamp01")
```

### For Simple Workflow:
```
Set: "Analysis"
Check all boxes
Result: One database for everything, minimal clicks
```

## Testing Your Settings

1. Set preference database name to `"TestDB"`
2. Apply and close preferences
3. Go to Results window
4. Click "Save Results"
5. **First time:** Should default to "Create new: TestDB"
6. Save once
7. **Next time:** Should default to "Use existing: TestDB"

## Common Questions

**Q: Why isn't it auto-saving?**  
A: The preferences only set defaults. You still need to click "Save Results" button in the Results window, then "Save" in the dialog. This is intentional - you have control!

**Q: I changed the preference but the dialog still shows the old database?**  
A: Make sure you clicked "Apply" or "OK" in Preferences. The new setting takes effect immediately.

**Q: Can I still use other databases?**  
A: Yes! You can always select a different database from the dropdown or create a new one in the dialog.

**Q: What if I want each image to have its own database?**  
A: Keep the preference as "ColorAnalysis" (generic). The system will automatically use the filename.

## Summary

**Think of preferences as:**
- **Smart defaults** that save you time
- **Starting points** that you can override
- **Workflow optimizations** that reduce repetitive clicking

**NOT as:**
- Automatic saving
- Forced choices
- Rigid constraints
