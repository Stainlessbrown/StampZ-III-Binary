#!/usr/bin/env python3
"""
Fix Database Normalization Issue

This script corrects the problem where database L*a*b* values are stored in normalized
format (0-1 range) when they should be stored as whole L*a*b* values (0-100, -128 to +127).

The script "un-normalizes" the values by:
1. L* values: multiply by 100 (0.26 → 26)
2. a* values: multiply by 255 and subtract 128 (0.647 → 37)
3. b* values: multiply by 255 and subtract 128 (0.571 → 18)

This ensures that when the Plot_3D application applies normalization, it gets correct values.
"""

import sqlite3
import sys
import os

def un_normalize_lab(db_path, check_only=False):
    """Un-normalize L*a*b* values in the database to fix double-normalization issue.
    
    Args:
        db_path: Path to database file
        check_only: If True, only check values without modifying
    """
    print(f"🔍 Checking database: {db_path}")
    if not os.path.exists(db_path):
        print(f"❌ Error: Database file not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check first few rows to confirm they're in 0-1 range (normalized)
        cursor.execute('SELECT id, l_value, a_value, b_value FROM color_measurements LIMIT 5')
        rows = cursor.fetchall()
        
        # Check if values are already in the 0-1 range
        normalized_count = 0
        for row in rows:
            row_id, l_val, a_val, b_val = row
            if 0 <= l_val <= 1.0 and 0 <= a_val <= 1.0 and 0 <= b_val <= 1.0:
                normalized_count += 1
                
        is_normalized = normalized_count >= len(rows) / 2
        
        print(f"Database appears to contain {'normalized' if is_normalized else 'whole'} L*a*b* values")
        
        if not is_normalized:
            print(f"⚠️ Database values don't appear to be in normalized range (0-1).")
            print(f"Sample values: {rows}")
            return False
            
        # Show a sample of what will change
        print("\nSample of changes that will be made:")
        print("ID |  Current L*   |   New L*   |  Current a*  |   New a*   |  Current b*  |   New b*")
        print("-" * 85)
        
        for row in rows:
            row_id, l_val, a_val, b_val = row
            new_l = l_val * 100.0
            new_a = (a_val * 255.0) - 128.0
            new_b = (b_val * 255.0) - 128.0
            print(f"{row_id:3d} | {l_val:12.6f} | {new_l:10.2f} | {a_val:12.6f} | {new_a:10.2f} | {b_val:12.6f} | {new_b:10.2f}")
        
        if check_only:
            print("\n✅ Check completed. No changes made.")
            return True
            
        # Get all rows to update
        cursor.execute('SELECT id, l_value, a_value, b_value FROM color_measurements')
        all_rows = cursor.fetchall()
        total_rows = len(all_rows)
        
        print(f"\n🔄 About to update {total_rows} rows in the database.")
        confirm = input("Continue with the update? (y/N): ").strip().lower()
        
        if confirm != 'y':
            print("Operation cancelled.")
            return False
            
        # Update all rows
        updated = 0
        for row in all_rows:
            row_id, l_val, a_val, b_val = row
            
            # Un-normalize values
            new_l = l_val * 100.0
            new_a = (a_val * 255.0) - 128.0
            new_b = (b_val * 255.0) - 128.0
            
            # Update row
            cursor.execute(
                "UPDATE color_measurements SET l_value = ?, a_value = ?, b_value = ? WHERE id = ?",
                (new_l, new_a, new_b, row_id)
            )
            updated += 1
            
            if updated % 100 == 0:
                print(f"  Updated {updated}/{total_rows} rows...")
                
        # Commit changes
        conn.commit()
        print(f"\n✅ Successfully updated {updated} rows in the database")
        
        # Verify changes
        cursor.execute('SELECT id, l_value, a_value, b_value FROM color_measurements LIMIT 5')
        updated_rows = cursor.fetchall()
        
        print("\nVerification of updated values:")
        print("ID |     L*    |    a*    |    b*")
        print("-" * 40)
        for row in updated_rows:
            print(f"{row[0]:3d} | {row[1]:8.2f} | {row[2]:8.2f} | {row[3]:8.2f}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_database_normalization.py <database_name> [check_only]")
        print("  <database_name>: Database name without .db extension (e.g., '138_averages')")
        print("  [check_only]: Optional. If 'check', only check values without modifying")
        sys.exit(1)
        
    db_name = sys.argv[1]
    check_only = len(sys.argv) > 2 and sys.argv[2].lower() == 'check'
    
    # Construct path to database
    db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'color_analysis')
    db_path = os.path.join(db_dir, f"{db_name}.db")
    
    result = un_normalize_lab(db_path, check_only)
    if result and not check_only:
        print("\n✅ Database fix completed successfully!")
        print("Now you should be able to run Plot_3D and perform K-means clustering.")
        print("The values will be properly normalized (not double-normalized) for visualization.")
    else:
        print("\n⚠️ No changes were made to the database.")