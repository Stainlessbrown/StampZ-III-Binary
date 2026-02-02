#!/usr/bin/env python3
"""
Fix formulas in Plot3D_Template.ods to handle empty strings instead of ISBLANK.

The issue: ISBLANK() only returns TRUE for cells that have never had a value.
When cells contain empty strings "", ISBLANK returns FALSE, causing #VALUE! errors.

The fix: Replace ISBLANK checks with empty string checks (=""or OR(="";"")).
"""

from odf import opendocument, table
import sys
import shutil
from datetime import datetime

def fix_formulas():
    template_path = '/Users/stanbrown/Desktop/StampZ-III-Binary/data/templates/plot3d/Plot3D_Template.ods'
    
    # Create backup
    backup_path = template_path.replace('.ods', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.ods')
    shutil.copy2(template_path, backup_path)
    print(f"✅ Created backup: {backup_path}")
    
    # Load the template
    doc = opendocument.load(template_path)
    
    # Get the first sheet
    sheets = doc.spreadsheet.getElementsByType(table.Table)
    if not sheets:
        print('❌ No sheets found')
        sys.exit(1)
    
    sheet = sheets[0]
    
    # Track changes
    changes_made = 0
    
    # Process all rows (checking first 1000 should be enough)
    for row_idx, row in enumerate(sheet.getElementsByType(table.TableRow)[:1000]):
        cells = row.getElementsByType(table.TableCell)
        for col_idx, cell in enumerate(cells):
            formula_attr = cell.getAttribute('formula')
            if formula_attr:
                original_formula = formula_attr
                
                # Fix the formulas:
                # For L* (column I): IF([.A8]="";"";...) - already correct, using empty string check
                # For Chroma (column J): Replace ISBLANK checks with empty string checks
                # For Hue (column K): Replace ISBLANK checks with empty string checks
                
                # Replace ISBLANK([.B8]) with [.B8]=""
                # Replace ISBLANK([.C8]) with [.C8]=""
                # Need to handle all possible cell references (B8, B9, B10, etc.)
                
                modified_formula = original_formula
                
                # Replace OR(ISBLANK([.BX]); ISBLANK([.CX])) pattern with OR([.BX]=""; [.CX]="")
                import re
                
                # Pattern: OR(ISBLANK([.BX]); ISBLANK([.CX]))
                pattern = r'OR\(ISBLANK\(\[\.([BC]\d+)\]\);\s*ISBLANK\(\[\.([BC]\d+)\]\)\)'
                replacement = r'OR([.\1]=""; [.\2]="")'
                modified_formula = re.sub(pattern, replacement, modified_formula)
                
                # Also handle single ISBLANK cases if any exist
                pattern_single = r'ISBLANK\(\[\.([A-Z]\d+)\]\)'
                replacement_single = r'[.\1]=""'
                modified_formula = re.sub(pattern_single, replacement_single, modified_formula)
                
                if modified_formula != original_formula:
                    cell.setAttribute('formula', modified_formula)
                    changes_made += 1
                    
                    col_letter = chr(65 + col_idx) if col_idx < 26 else 'Col' + str(col_idx)
                    print(f"\n✏️  Cell {col_letter}{row_idx + 1}:")
                    print(f"   OLD: {original_formula[:100]}...")
                    print(f"   NEW: {modified_formula[:100]}...")
    
    if changes_made > 0:
        # Save the modified template
        doc.save(template_path)
        print(f"\n✅ Successfully updated {changes_made} formulas in {template_path}")
        print(f"✅ Backup saved to: {backup_path}")
    else:
        print("\n⚠️  No formulas needed updating")
    
    return changes_made

if __name__ == '__main__':
    try:
        fix_formulas()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
