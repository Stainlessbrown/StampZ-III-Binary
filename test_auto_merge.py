#!/usr/bin/env python3
"""Test the auto-merge functionality"""

from pathlib import Path
from datetime import datetime
import os
import tempfile

def test_auto_merge():
    """Test auto-merge logic"""
    
    # Create a temp directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create fake data files
        original_file = tmpdir / "test_image_StampZ_Data.txt"
        cropped_file = tmpdir / "test_image-crp_StampZ_Data.txt"
        
        # Write some content to original
        with open(original_file, 'w') as f:
            f.write("STAMPZ COMPREHENSIVE ANALYSIS DATA\n")
            f.write("Original image data\n")
            f.write("Perforation: 11.5\n")
        
        # Write some content to cropped
        with open(cropped_file, 'w') as f:
            f.write("STAMPZ COMPREHENSIVE ANALYSIS DATA\n")
            f.write("Cropped image data\n")
            f.write("Color analysis: RGB(150,45,32)\n")
        
        print(f"Created test files:")
        print(f"  Original: {original_file.name}")
        print(f"  Cropped: {cropped_file.name}")
        print(f"\nBoth files exist: {original_file.exists() and cropped_file.exists()}")
        
        # Simulate the auto-merge logic for cropped file
        print(f"\n--- Testing merge when saving to CROPPED file ---")
        current_path = cropped_file
        current_stem = current_path.stem
        
        if current_stem.endswith('_StampZ_Data'):
            image_name = current_stem[:-len('_StampZ_Data')]
            print(f"Image name extracted: '{image_name}'")
            print(f"Ends with -crp: {image_name.endswith('-crp')}")
            
            if image_name.endswith('-crp'):
                original_image_name = image_name[:-len('-crp')]
                print(f"Original image name: '{original_image_name}'")
                
                original_data_file = current_path.parent / f"{original_image_name}_StampZ_Data.txt"
                print(f"Looking for: {original_data_file.name}")
                print(f"File exists: {original_data_file.exists()}")
                
                if original_data_file.exists():
                    print("\n✓ MERGE WOULD OCCUR")
                    print(f"  Would merge FROM: {original_data_file.name}")
                    print(f"  Would merge INTO: {current_path.name}")
                    print(f"  Would delete: {original_data_file.name}")
                else:
                    print("\n✗ NO MERGE - Original file not found")
            else:
                print("\n✗ NO MERGE - Not a cropped file")
        
        # Test the opposite direction
        print(f"\n--- Testing merge when saving to ORIGINAL file ---")
        current_path = original_file
        current_stem = current_path.stem
        
        if current_stem.endswith('_StampZ_Data'):
            image_name = current_stem[:-len('_StampZ_Data')]
            print(f"Image name extracted: '{image_name}'")
            print(f"Ends with -crp: {image_name.endswith('-crp')}")
            
            if not image_name.endswith('-crp'):
                cropped_image_name = f"{image_name}-crp"
                print(f"Cropped image name: '{cropped_image_name}'")
                
                cropped_data_file = current_path.parent / f"{cropped_image_name}_StampZ_Data.txt"
                print(f"Looking for: {cropped_data_file.name}")
                print(f"File exists: {cropped_data_file.exists()}")
                
                if cropped_data_file.exists():
                    print("\n✓ MERGE WOULD OCCUR")
                    print(f"  Would merge FROM: {current_path.name}")
                    print(f"  Would merge INTO: {cropped_data_file.name}")
                    print(f"  Would delete: {current_path.name}")
                else:
                    print("\n✗ NO MERGE - Cropped file not found")

if __name__ == "__main__":
    test_auto_merge()
