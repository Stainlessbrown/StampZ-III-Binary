#!/usr/bin/env python3
"""
Script to rename databases with inconsistent average suffixes to standard _AVG.db format.

This script will:
1. Find all databases with various average-related suffixes
2. Rename them to use the standard _AVG.db suffix
3. Create a backup log of all renames
"""

import os
import shutil
from pathlib import Path
from datetime import datetime


def find_averaged_databases(data_dir):
    """Find all databases with average-related suffixes.
    
    Args:
        data_dir: Path to the color_analysis data directory
        
    Returns:
        List of tuples (current_path, suggested_new_name)
    """
    if not os.path.exists(data_dir):
        print(f"Data directory not found: {data_dir}")
        return []
    
    databases_to_rename = []
    
    # Patterns to look for (in priority order - most specific first)
    patterns = [
        ('_AVG_averages.db', '_AVG.db'),
        ('_AVG_average.db', '_AVG.db'),
        ('_AVERAGE_average.db', '_AVG.db'),
        ('_AVERAGES_averages.db', '_AVG.db'),
        ('_AVERAGES_average.db', '_AVG.db'),
        ('_AVERAGE_averages.db', '_AVG.db'),
        ('_averages.db', '_AVG.db'),
        ('_average.db', '_AVG.db'),
        ('_AVERAGES.db', '_AVG.db'),
        ('_AVERAGE.db', '_AVG.db'),
    ]
    
    for filename in os.listdir(data_dir):
        if not filename.endswith('.db'):
            continue
            
        file_path = os.path.join(data_dir, filename)
        
        # Check each pattern
        for old_suffix, new_suffix in patterns:
            if filename.endswith(old_suffix):
                # Extract the base name
                base_name = filename[:-len(old_suffix)]
                new_filename = f"{base_name}{new_suffix}"
                new_path = os.path.join(data_dir, new_filename)
                
                # Only add if the target doesn't already exist
                if not os.path.exists(new_path):
                    databases_to_rename.append((file_path, new_path, filename, new_filename))
                else:
                    print(f"⚠️  Warning: Cannot rename {filename} - target {new_filename} already exists")
                break
    
    return databases_to_rename


def create_backup_log(renames, log_dir):
    """Create a backup log file of all renames.
    
    Args:
        renames: List of tuples (old_path, new_path, old_name, new_name)
        log_dir: Directory to save the log file
        
    Returns:
        Path to the log file
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"database_rename_log_{timestamp}.txt"
    log_path = os.path.join(log_dir, log_filename)
    
    with open(log_path, 'w') as f:
        f.write("Database Rename Log\n")
        f.write("=" * 80 + "\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total renames: {len(renames)}\n")
        f.write("=" * 80 + "\n\n")
        
        for old_path, new_path, old_name, new_name in renames:
            f.write(f"OLD: {old_name}\n")
            f.write(f"NEW: {new_name}\n")
            f.write(f"Path: {old_path}\n")
            f.write("-" * 80 + "\n")
    
    return log_path


def rename_databases(renames, dry_run=True):
    """Rename databases according to the rename list.
    
    Args:
        renames: List of tuples (old_path, new_path, old_name, new_name)
        dry_run: If True, only show what would be renamed without actually renaming
        
    Returns:
        Number of successful renames
    """
    successful = 0
    
    for old_path, new_path, old_name, new_name in renames:
        try:
            if dry_run:
                print(f"[DRY RUN] Would rename: {old_name} → {new_name}")
            else:
                # Actually rename the file
                os.rename(old_path, new_path)
                print(f"✓ Renamed: {old_name} → {new_name}")
                successful += 1
        except Exception as e:
            print(f"✗ Error renaming {old_name}: {e}")
    
    return successful


def main():
    """Main function to run the database renaming."""
    print("=" * 80)
    print("StampZ Database Renaming Tool")
    print("=" * 80)
    print("\nThis tool will standardize averaged database names to use _AVG.db suffix.")
    print("Old patterns like _averages, _AVERAGES_averages, etc. will be renamed.\n")
    
    # Find the data directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data", "color_analysis")
    
    if not os.path.exists(data_dir):
        print(f"❌ Error: Data directory not found at {data_dir}")
        print("Please make sure you're running this script from the StampZ-III-Binary directory.")
        return
    
    print(f"📁 Scanning: {data_dir}\n")
    
    # Find databases to rename
    renames = find_averaged_databases(data_dir)
    
    if not renames:
        print("✅ No databases need renaming. All databases are already using standard naming.")
        return
    
    print(f"Found {len(renames)} database(s) to rename:\n")
    for old_path, new_path, old_name, new_name in renames:
        print(f"  • {old_name}")
        print(f"    → {new_name}\n")
    
    # Ask user for confirmation
    print("\nOptions:")
    print("  1. Dry run (show what would be renamed, but don't actually rename)")
    print("  2. Rename databases")
    print("  3. Cancel")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        print("\n" + "=" * 80)
        print("DRY RUN - No files will be modified")
        print("=" * 80 + "\n")
        rename_databases(renames, dry_run=True)
        print(f"\n✓ Dry run complete. {len(renames)} database(s) would be renamed.")
        
    elif choice == "2":
        # Create backup log
        log_path = create_backup_log(renames, data_dir)
        print(f"\n📝 Created backup log: {log_path}")
        
        print("\n" + "=" * 80)
        print("RENAMING DATABASES")
        print("=" * 80 + "\n")
        
        successful = rename_databases(renames, dry_run=False)
        
        print(f"\n✓ Renaming complete! {successful}/{len(renames)} database(s) renamed successfully.")
        print(f"📝 See log file for details: {log_path}")
        
    else:
        print("\n❌ Operation cancelled.")


if __name__ == "__main__":
    main()
