#!/usr/bin/env python3
"""
Batch Bit Depth Checker for TIFF Files

Scans a folder (and optionally subfolders) to identify the bit depth 
of all TIFF files. Useful for screening which files need re-leveling
after the 16-bit preservation fix.

Usage:
    python3 batch_check_bit_depth.py /path/to/folder
    python3 batch_check_bit_depth.py /path/to/folder --recursive
    python3 batch_check_bit_depth.py /path/to/folder --filter "_aligned"
"""

import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict

try:
    import tifffile
    HAS_TIFFFILE = True
except ImportError:
    HAS_TIFFFILE = False
    print("⚠️  Warning: tifffile not available. Install with: pip install tifffile")

from PIL import Image
import numpy as np


def get_bit_depth_tifffile(filepath):
    """Get bit depth using tifffile (accurate)."""
    try:
        img_array = tifffile.imread(filepath)
        if img_array.dtype == np.uint16:
            return 16
        elif img_array.dtype == np.uint8:
            return 8
        elif img_array.dtype == np.uint32:
            return 32
        else:
            return f"Unknown ({img_array.dtype})"
    except Exception as e:
        return f"Error: {e}"


def get_bit_depth_pil(filepath):
    """Get bit depth using PIL (less accurate for 16-bit)."""
    try:
        with Image.open(filepath) as img:
            # Check mode
            if img.mode in ('I;16', 'I;16B', 'I;16L'):
                return "16 (PIL)"
            elif img.mode in ('I', 'F'):
                return "32 (PIL)"
            else:
                return "8 (PIL)"
    except Exception as e:
        return f"Error: {e}"


def get_bit_depth(filepath):
    """Get bit depth of a TIFF file."""
    if HAS_TIFFFILE:
        return get_bit_depth_tifffile(filepath)
    else:
        return get_bit_depth_pil(filepath)


def scan_folder(folder_path, recursive=False, filter_pattern=None, extensions=None):
    """
    Scan folder for image files and check their bit depth.
    
    Args:
        folder_path: Path to folder to scan
        recursive: If True, scan subfolders recursively
        filter_pattern: Optional string that must be in filename (e.g., "_aligned", "_leveled")
        extensions: List of file extensions to check (default: ['.tif', '.tiff'])
    
    Returns:
        Dictionary with bit depth as key and list of files as value
    """
    if extensions is None:
        extensions = ['.tif', '.tiff']
    
    results = defaultdict(list)
    total_files = 0
    
    folder_path = Path(folder_path)
    
    # Get list of files
    if recursive:
        files = []
        for ext in extensions:
            files.extend(folder_path.rglob(f'*{ext}'))
    else:
        files = []
        for ext in extensions:
            files.extend(folder_path.glob(f'*{ext}'))
    
    # Filter by pattern if specified
    if filter_pattern:
        files = [f for f in files if filter_pattern in f.name]
    
    # Sort files for consistent output
    files = sorted(files)
    
    print(f"\nScanning {len(files)} files...")
    if filter_pattern:
        print(f"Filter: files containing '{filter_pattern}'")
    print()
    
    for filepath in files:
        total_files += 1
        bit_depth = get_bit_depth(str(filepath))
        
        # Normalize bit depth for grouping
        if isinstance(bit_depth, int):
            key = f"{bit_depth}-bit"
        else:
            key = str(bit_depth)
        
        results[key].append(filepath)
        
        # Show progress every 10 files
        if total_files % 10 == 0:
            print(f"  Processed {total_files} files...", end='\r')
    
    if total_files > 0:
        print(f"  Processed {total_files} files... Done!    ")
    
    return results


def print_results(results, show_filenames=False, folder_path=None):
    """Print scan results in a formatted way."""
    print("\n" + "="*70)
    print("BIT DEPTH SCAN RESULTS")
    print("="*70)
    
    # Sort by bit depth
    sorted_keys = sorted(results.keys(), 
                        key=lambda x: int(x.split('-')[0]) if x[0].isdigit() else 999)
    
    total_files = sum(len(files) for files in results.values())
    
    for bit_depth in sorted_keys:
        files = results[bit_depth]
        count = len(files)
        percentage = (count / total_files * 100) if total_files > 0 else 0
        
        # Use emoji to highlight 8-bit vs 16-bit
        if bit_depth == "8-bit":
            icon = "⚠️ "
        elif bit_depth == "16-bit":
            icon = "✅"
        else:
            icon = "ℹ️ "
        
        print(f"\n{icon} {bit_depth}: {count} files ({percentage:.1f}%)")
        
        if show_filenames and files:
            for filepath in files[:10]:  # Show first 10
                # Show relative path if folder_path provided
                if folder_path:
                    try:
                        rel_path = filepath.relative_to(folder_path)
                        print(f"     {rel_path}")
                    except:
                        print(f"     {filepath.name}")
                else:
                    print(f"     {filepath.name}")
            
            if len(files) > 10:
                print(f"     ... and {len(files) - 10} more")
    
    print("\n" + "="*70)
    print(f"Total files scanned: {total_files}")
    
    # Show warning if 8-bit files found
    if "8-bit" in results:
        print("\n⚠️  WARNING: Found 8-bit TIFF files!")
        print("   These may have been converted from 16-bit during leveling.")
        print("   Consider re-leveling these files with the fixed version.")
    
    print("="*70 + "\n")


def save_report(results, output_file, folder_path):
    """Save detailed report to a text file."""
    with open(output_file, 'w') as f:
        f.write("BIT DEPTH SCAN REPORT\n")
        f.write("="*70 + "\n")
        f.write(f"Scanned folder: {folder_path}\n")
        f.write("="*70 + "\n\n")
        
        sorted_keys = sorted(results.keys(), 
                            key=lambda x: int(x.split('-')[0]) if x[0].isdigit() else 999)
        
        for bit_depth in sorted_keys:
            files = results[bit_depth]
            f.write(f"\n{bit_depth}: {len(files)} files\n")
            f.write("-" * 40 + "\n")
            
            for filepath in files:
                try:
                    rel_path = filepath.relative_to(folder_path)
                    f.write(f"  {rel_path}\n")
                except:
                    f.write(f"  {filepath}\n")
    
    print(f"📄 Detailed report saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Batch check bit depth of TIFF files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Desktop/stamps
  %(prog)s ~/Desktop/stamps --recursive
  %(prog)s ~/Desktop/stamps --filter "_aligned" --show-files
  %(prog)s ~/Desktop/stamps --recursive --save-report report.txt
        """
    )
    
    parser.add_argument('folder', help='Folder to scan for TIFF files')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Scan subfolders recursively')
    parser.add_argument('-f', '--filter', type=str,
                       help='Filter files by pattern (e.g., "_aligned", "_leveled")')
    parser.add_argument('-s', '--show-files', action='store_true',
                       help='Show filenames in output (first 10 per group)')
    parser.add_argument('-o', '--save-report', type=str,
                       help='Save detailed report to file')
    parser.add_argument('-e', '--extensions', nargs='+', 
                       default=['.tif', '.tiff'],
                       help='File extensions to check (default: .tif .tiff)')
    
    args = parser.parse_args()
    
    # Validate folder exists
    folder_path = Path(args.folder).expanduser().resolve()
    if not folder_path.exists():
        print(f"❌ Error: Folder not found: {folder_path}")
        sys.exit(1)
    
    if not folder_path.is_dir():
        print(f"❌ Error: Not a directory: {folder_path}")
        sys.exit(1)
    
    # Scan folder
    results = scan_folder(
        folder_path,
        recursive=args.recursive,
        filter_pattern=args.filter,
        extensions=args.extensions
    )
    
    # Print results
    if not results:
        print("\n⚠️  No TIFF files found matching criteria.")
        sys.exit(0)
    
    print_results(results, show_filenames=args.show_files, folder_path=folder_path)
    
    # Save report if requested
    if args.save_report:
        save_report(results, args.save_report, folder_path)


if __name__ == '__main__':
    main()
