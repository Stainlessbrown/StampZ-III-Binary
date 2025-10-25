# Workflow Improvements

## 1. Remember Last Used Database (Results Window)

### Problem
When saving multiple analyses in sequence, users had to re-select their working database each time, even though they were typically working within the same project.

### Solution
The Results window now remembers the last used database and pre-selects it in the "Use Existing Database" dropdown.

**Implementation:**
- Last used database is saved to user preferences on successful save
- When the save dialog opens, it checks preferences for the last used database
- If the last used database still exists, it's pre-selected
- Falls back to first database if last used is not found

**User Experience:**
1. First save: Select your project database (e.g., "Stamp_Analysis_2025")
2. Second save: "Stamp_Analysis_2025" is already selected
3. Continue working with the same database pre-selected each time

---

## 2. Natural Sorting for Numeric Suffixes (Library)

### Problem
Colors with numeric suffixes sorted incorrectly:
- ❌ **Before:** Red_1, Red_10, Red_11, Red_2, Red_3, ...
- ✅ **After:** Red_1, Red_2, Red_3, ..., Red_10, Red_11, ...

### Solution
Implemented **natural sorting** (also called alphanumeric sorting) that treats numbers as numeric values rather than text.

**How it Works:**
- Splits color names into text and number parts
- Text parts sort alphabetically
- Number parts sort numerically
- Example: `"Red_11"` → `["Red_", 11]` → sorts after `["Red_", 10]`

**Applies To:**
- ✅ Alphabetical sorting
- ✅ Category sorting
- ✅ Already worked with Hue (Philatelic) sorting

**Examples:**
```
Sequential colors:     Red_1, Red_2, Red_3, ..., Red_10, Red_11
Version numbers:       Blue_v1, Blue_v2, ..., Blue_v10, Blue_v12
Mixed text/numbers:    Sample_1a, Sample_1b, Sample_2a, Sample_10a
```

---

## Benefits

### For Regular Workflow:
- **Reduced clicks:** No need to find and select the same database repeatedly
- **Fewer errors:** Less chance of accidentally saving to wrong database
- **Better continuity:** Maintains focus on analysis work, not database management

### For Sequential Analysis:
- **Logical order:** Colors appear in the order you expect
- **Easier navigation:** Finding Red_11 after Red_10, not after Red_1
- **Better organization:** Numbered sequences stay together

---

## Technical Details

### Database Preference Storage
- Key: `'last_used_database'`
- Location: User preferences JSON
- Scope: Per user, persistent across sessions
- Fallback: First available database if preference invalid

### Natural Sorting Algorithm
- Uses regex split: `re.split(r'(\d+)', name)`
- Converts digit strings to integers for comparison
- Maintains category as primary sort key
- Case-insensitive text comparison

---

## Testing Recommendations

1. **Database Memory:**
   - Save to database "ProjectA"
   - Close and reopen Results window
   - Verify "ProjectA" is pre-selected

2. **Natural Sorting:**
   - Create colors: Test_1, Test_2, ..., Test_10, Test_11
   - View in Library with Alphabetical sort
   - Verify Test_10 comes before Test_11

3. **Edge Cases:**
   - Database deleted: Should fall back gracefully
   - No numbers in name: Should sort normally
   - Multiple number sequences: Should handle correctly
