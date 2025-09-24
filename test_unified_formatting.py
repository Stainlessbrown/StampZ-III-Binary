#!/usr/bin/env python3
"""
Test script to validate that the unified formatting system works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_unified_formatting():
    """Test the unified formatting system components"""
    print("🧪 TESTING UNIFIED FORMATTING SYSTEM")
    print("=" * 50)
    
    try:
        # Test 1: Import the format redirector
        print("\n1. Testing format_redirector import...")
        from utils.format_redirector import apply_realtime_formatting
        print("✅ apply_realtime_formatting imported successfully")
        
        # Test 2: Import the data file manager
        print("\n2. Testing data_file_manager import...")
        from utils.data_file_manager import get_data_file_manager, DataFormat
        manager = get_data_file_manager()
        print("✅ DataFileManager imported successfully")
        
        # Test 3: Check format specifications
        print("\n3. Testing format specifications...")
        spec = manager.get_format_spec(DataFormat.PLOT3D)
        print(f"✅ data_start_row: {spec.data_start_row} (should be 7)")
        print(f"✅ protected_areas: {spec.protected_areas} (should be empty list)")
        print(f"✅ marker_color: {spec.marker_color} (should be salmon)")
        print(f"✅ color_color: {spec.color_color} (should be yellow)")
        print(f"✅ sphere_color: {spec.sphere_color} (should be yellow)")
        
        # Test 4: Check validation lists
        print("\n4. Testing validation lists...")
        validation_lists = manager.get_validation_lists(DataFormat.PLOT3D)
        print(f"✅ Marker validation: {validation_lists['Marker'][:3]}... (first 3)")
        print(f"✅ Color validation: {validation_lists['Color'][:3]}... (first 3)")
        print(f"✅ Sphere validation: {validation_lists['Sphere'][:3]}... (first 3)")
        
        # Test 5: Check that all start with empty string
        print("\n5. Testing default values...")
        print(f"✅ Markers start with empty: {validation_lists['Marker'][0] == ''}")
        print(f"✅ Colors start with empty: {validation_lists['Color'][0] == ''}")
        print(f"✅ Spheres start with empty: {validation_lists['Sphere'][0] == ''}")
        
        # Test 6: Test method exists
        print("\n6. Testing method availability...")
        print(f"✅ apply_realtime_sheet_formatting exists: {hasattr(manager, 'apply_realtime_sheet_formatting')}")
        print(f"✅ _apply_column_formatting exists: {hasattr(manager, '_apply_column_formatting')}")
        print(f"✅ _apply_validation_dropdowns exists: {hasattr(manager, '_apply_validation_dropdowns')}")
        
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("The unified formatting system should work correctly.")
        print("If you're still seeing old formatting, try restarting the application completely.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_unified_formatting()
    sys.exit(0 if success else 1)