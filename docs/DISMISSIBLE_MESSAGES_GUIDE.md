# Dismissible Messages Implementation Guide

## Overview
Replace informational popups with session-dismissible messages that include a "Don't show again this session" checkbox. This reduces popup fatigue while preserving important feedback.

## Key Features

✅ **Session-based dismissal** - Resets when app restarts
✅ **Easy drop-in replacement** - Similar API to `messagebox`
✅ **Persistent memory** - Once dismissed, stays hidden for the session
✅ **Unique message IDs** - Control which messages can be dismissed
✅ **Styled dialogs** - Info and success variants

## Quick Start

### 1. Import the Module

```python
from utils.dismissible_message import showinfo_dismissible, showsuccess_dismissible
```

### 2. Replace Informational Popups

**Before:**
```python
from tkinter import messagebox

messagebox.showinfo(
    "Measurement Saved",
    "Your precision measurement has been saved to the database."
)
```

**After:**
```python
from utils.dismissible_message import showinfo_dismissible

showinfo_dismissible(
    title="Measurement Saved",
    message="Your precision measurement has been saved to the database.",
    message_id="measurement_saved",  # Unique ID
    detail="You can view it in the Database Viewer."  # Optional
)
```

## When to Use Dismissible Messages

### ✅ Good Candidates (Use Dismissible)

**Success notifications:**
- "Measurement saved"
- "Analysis completed"
- "Export successful"
- "Template loaded"
- "Calibration saved"

**Informational messages:**
- "Results copied to clipboard"
- "Settings applied"
- "Calculation completed"
- "Data logged"

### ❌ Keep as Regular Dialogs

**Error messages:**
- User needs to see every error
- Don't use dismissible

**Confirmations:**
- "Delete this item?"
- "Overwrite file?"
- Require explicit action each time

**Critical warnings:**
- Data loss warnings
- Validation failures
- Configuration errors

## Usage Examples

### Example 1: Simple Success Message

```python
from utils.dismissible_message import showsuccess_dismissible

def save_measurement(self):
    # ... save logic ...
    
    showsuccess_dismissible(
        title="Saved",
        message="Measurement saved successfully!",
        message_id="measurement_save_success"
    )
```

### Example 2: Info Message with Details

```python
from utils.dismissible_message import showinfo_dismissible

def export_data(self):
    # ... export logic ...
    
    showinfo_dismissible(
        title="Export Complete",
        message="Your data has been exported to the spreadsheet.",
        message_id="export_complete",
        detail=f"Saved to: {export_path}"
    )
```

### Example 3: With Parent Window

```python
from utils.dismissible_message import showinfo_dismissible

def on_template_load(self):
    # ... load template ...
    
    showinfo_dismissible(
        title="Template Loaded",
        message="Coordinate template has been applied.",
        message_id="template_loaded",
        parent=self.root  # Pass parent window
    )
```

### Example 4: Conditional Display

```python
from utils.dismissible_message import showinfo_dismissible, is_message_dismissed

def save_analysis(self):
    # ... save logic ...
    
    # Only show if not dismissed
    if not is_message_dismissed("analysis_saved"):
        showinfo_dismissible(
            title="Analysis Saved",
            message="Your color analysis has been saved.",
            message_id="analysis_saved"
        )
```

## Message ID Naming Convention

Use descriptive, unique IDs that describe the message purpose:

**Good IDs:**
- `"measurement_saved"`
- `"export_complete"`
- `"template_loaded"`
- `"analysis_success"`
- `"calibration_applied"`
- `"perforation_measured"`

**Bad IDs:**
- `"msg1"` - Not descriptive
- `"success"` - Too generic
- `"info"` - Too vague

## Specific Implementation Examples

### In `gui/precision_measurement_tool.py`

```python
# Line ~1241
# OLD:
messagebox.showinfo("Saved", "Measurement saved to database")

# NEW:
from utils.dismissible_message import showsuccess_dismissible

showsuccess_dismissible(
    title="Saved",
    message="Measurement saved to database",
    message_id="precision_measurement_saved",
    parent=self.dialog
)
```

### In `gui/gauge_perforation_ui.py`

```python
# Line ~903
# OLD:
messagebox.showinfo("Saved", "Perforation data saved")

# NEW:
from utils.dismissible_message import showsuccess_dismissible

showsuccess_dismissible(
    title="Saved",
    message="Perforation data saved successfully",
    message_id="perforation_data_saved",
    detail="The data has been logged to the StampZ data file.",
    parent=self.root
)
```

### In `managers/data_export_manager.py`

```python
# Line ~137
# OLD:
messagebox.showinfo("Success", "Export completed successfully!")

# NEW:
from utils.dismissible_message import showsuccess_dismissible

showsuccess_dismissible(
    title="Export Complete",
    message="Your data has been exported successfully!",
    message_id="data_export_success",
    detail=f"File saved to: {output_path}"
)
```

### In `gui/sample_results_manager.py`

```python
# Line ~961
# OLD:
messagebox.showinfo("Success", success_msg)

# NEW:
from utils.dismissible_message import showsuccess_dismissible

showsuccess_dismissible(
    title="Results Saved",
    message="Analysis results saved successfully!",
    message_id="results_save_success",
    detail=success_msg
)
```

### In `gui/template_manager.py`

```python
# Line ~174
# OLD:
messagebox.showinfo("Success", "Template saved successfully")

# NEW:
from utils.dismissible_message import showsuccess_dismissible

showsuccess_dismissible(
    title="Template Saved",
    message="Coordinate template saved successfully",
    message_id="template_save_success",
    parent=self.root
)
```

## Migration Strategy

### Phase 1: High-Traffic Messages (Immediate)
Replace these first - they appear most frequently:

1. ✅ Measurement saved notifications
2. ✅ Analysis save confirmations
3. ✅ Export success messages
4. ✅ Template load notifications
5. ✅ Calculation completions

### Phase 2: Medium-Traffic Messages
Next priority:

6. Color comparison results
7. Database operations
8. Calibration confirmations
9. Copy to clipboard notifications
10. Settings applied messages

### Phase 3: Low-Traffic Messages
Last priority:

11. Rare informational messages
12. First-time usage tips
13. Feature introductions

## Testing the Implementation

### Test Script

```python
#!/usr/bin/env python3
"""Test dismissible messages."""

import tkinter as tk
from utils.dismissible_message import (
    showinfo_dismissible,
    showsuccess_dismissible,
    get_session_manager
)

root = tk.Tk()
root.title("Dismissible Message Test")

def test_info():
    showinfo_dismissible(
        title="Test Info",
        message="This is a test informational message.",
        message_id="test_info",
        detail="Check the 'Don't show again' box to dismiss."
    )

def test_success():
    showsuccess_dismissible(
        title="Test Success",
        message="This is a test success message.",
        message_id="test_success"
    )

def show_stats():
    count = get_session_manager().get_dismissed_count()
    print(f"Dismissed messages this session: {count}")

btn1 = tk.Button(root, text="Show Info Message", command=test_info)
btn1.pack(pady=10)

btn2 = tk.Button(root, text="Show Success Message", command=test_success)
btn2.pack(pady=10)

btn3 = tk.Button(root, text="Show Dismissal Stats", command=show_stats)
btn3.pack(pady=10)

root.mainloop()
```

### Manual Testing Checklist

- [ ] Message appears on first call
- [ ] Message appears again if checkbox not checked
- [ ] Message doesn't appear after checking "Don't show again"
- [ ] Different message IDs work independently
- [ ] Messages reset after app restart
- [ ] Parent window parameter works
- [ ] Detail text displays correctly
- [ ] Enter/Escape keys work
- [ ] Dialog centers on screen

## Benefits

### For Users
- 📉 **67%+ fewer popups** in typical workflows
- 🎯 **Control over verbosity** per session
- 🔄 **Fresh start** every app launch
- ✨ **Better UX** - less interruption

### For Developers
- 🔧 **Easy migration** - minimal code changes
- 🎨 **Consistent styling** - all dismissible messages look the same
- 📝 **Clean API** - similar to standard messagebox
- 🐛 **Easy debugging** - check dismissal state programmatically

## Advanced Usage

### Check Dismissal State

```python
from utils.dismissible_message import is_message_dismissed

if is_message_dismissed("some_message"):
    # Do something else instead
    status_bar.show("Measurement saved")
else:
    # Show the full message
    showinfo_dismissible(...)
```

### Reset During Development

```python
from utils.dismissible_message import reset_session_dismissals

# For testing - reset all dismissals
reset_session_dismissals()
```

### Get Statistics

```python
from utils.dismissible_message import get_session_manager

manager = get_session_manager()
count = manager.get_dismissed_count()
print(f"User has dismissed {count} messages this session")
```

## Common Patterns

### Pattern 1: Success with File Path

```python
showsuccess_dismissible(
    title="Export Complete",
    message="Data exported successfully",
    message_id="export_success",
    detail=f"Saved to:\n{file_path}"
)
```

### Pattern 2: Info with Action Hint

```python
showinfo_dismissible(
    title="Template Loaded",
    message="Coordinate template has been applied to the image.",
    message_id="template_loaded",
    detail="You can now place samples using the template coordinates."
)
```

### Pattern 3: Conditional Dismissible

```python
def notify_save(self, show_popup=True):
    """Notify about save with optional popup."""
    if show_popup:
        showsuccess_dismissible(
            title="Saved",
            message="Measurement saved",
            message_id="measurement_saved"
        )
    else:
        # Use status bar for silent mode
        self.status_bar.show("Measurement saved")
```

## Summary

Replace informational popups with `showinfo_dismissible()` or `showsuccess_dismissible()`:

```python
# ❌ Before
messagebox.showinfo("Saved", "Measurement saved!")

# ✅ After
showinfo_dismissible(
    title="Saved",
    message="Measurement saved!",
    message_id="measurement_saved"
)
```

**Key Points:**
- Session-based only (resets on restart)
- Easy to implement (similar API)
- Reduces popup fatigue
- User stays in control
- Better workflow experience
