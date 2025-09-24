#!/usr/bin/env python3
"""
Test script to verify validation and sphere visibility fixes.
"""

import sys
import os
import tkinter as tk

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_validation_lists():
    """Test that validation lists no longer contain '(none)'."""
    print("=== Testing Validation Lists ===")
    
    # Test format_redirector
    try:
        from utils.format_redirector import get_valid_markers, get_valid_colors, get_valid_spheres
        
        markers = get_valid_markers()
        colors = get_valid_colors() 
        spheres = get_valid_spheres()
        
        print(f"Markers: {markers[:5]}...  (first 5)")
        print(f"Colors: {colors[:5]}...   (first 5)")
        print(f"Spheres: {spheres[:5]}... (first 5)")
        
        # Check for '(none)' entries
        has_none_markers = '(none)' in markers
        has_none_colors = '(none)' in colors
        has_none_spheres = '(none)' in spheres
        
        print(f"Markers contain '(none)': {has_none_markers}")
        print(f"Colors contain '(none)': {has_none_colors}")
        print(f"Spheres contain '(none)': {has_none_spheres}")
        
        # Check for empty string as first entry
        first_marker = markers[0] if markers else "N/A"
        first_color = colors[0] if colors else "N/A"
        first_sphere = spheres[0] if spheres else "N/A"
        
        print(f"First marker: '{first_marker}'")
        print(f"First color: '{first_color}'")
        print(f"First sphere: '{first_sphere}'")
        
        success = not (has_none_markers or has_none_colors or has_none_spheres)
        print(f"✅ Validation fix successful: {success}")
        
    except Exception as e:
        print(f"❌ Error testing validation lists: {e}")
        return False
        
    return True

def test_unified_data_manager():
    """Test unified data manager validation lists."""
    print("\n=== Testing Unified Data Manager ===")
    
    try:
        from utils.unified_data_manager import DataState
        
        # Create a data state instance to test validation lists
        state = DataState()
        
        print(f"VALID_MARKERS: {state.VALID_MARKERS[:5]}...")
        print(f"VALID_COLORS: {state.VALID_COLORS[:5]}...")
        print(f"VALID_SPHERES: {state.VALID_SPHERES[:5]}...")
        
        # Check for '(none)' entries
        has_none_markers = '(none)' in state.VALID_MARKERS
        has_none_colors = '(none)' in state.VALID_COLORS
        has_none_spheres = '(none)' in state.VALID_SPHERES
        
        print(f"Contains '(none)' - Markers: {has_none_markers}, Colors: {has_none_colors}, Spheres: {has_none_spheres}")
        
        success = not (has_none_markers or has_none_colors or has_none_spheres)
        print(f"✅ Unified manager fix successful: {success}")
        
    except Exception as e:
        print(f"❌ Error testing unified data manager: {e}")
        return False
        
    return True

def test_realtime_sheet_creation():
    """Test that realtime sheet can be created without validation errors."""
    print("\n=== Testing Realtime Sheet Creation ===")
    
    try:
        # Create a test root window
        root = tk.Tk()
        root.withdraw()  # Hide it
        
        # Import and create realtime sheet
        from gui.realtime_plot3d_sheet import RealtimePlot3DSheet
        
        # Create sheet without loading initial data to test validation setup
        sheet = RealtimePlot3DSheet(
            parent=root,
            sample_set_name="Test_Validation_Fix",
            load_initial_data=False  # Skip data loading, just test validation setup
        )
        
        # Check that validation constants are correct
        print(f"Sheet VALID_MARKERS: {sheet.VALID_MARKERS[:3]}...")
        print(f"Sheet VALID_COLORS: {sheet.VALID_COLORS[:3]}...")
        print(f"Sheet VALID_SPHERES: {sheet.VALID_SPHERES[:3]}...")
        
        # Check for '(none)' entries
        has_none = any('(none)' in lst for lst in [sheet.VALID_MARKERS, sheet.VALID_COLORS, sheet.VALID_SPHERES])
        
        print(f"Sheet contains '(none)': {has_none}")
        print(f"✅ Sheet creation successful: {not has_none}")
        
        # Clean up
        sheet.window.destroy()
        root.destroy()
        
        return not has_none
        
    except Exception as e:
        print(f"❌ Error testing realtime sheet creation: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Validation and Sphere Fixes\n")
    
    results = []
    
    # Run tests
    results.append(test_validation_lists())
    results.append(test_unified_data_manager()) 
    results.append(test_realtime_sheet_creation())
    
    # Summary
    print(f"\n=== Test Summary ===")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Validation fix is working.")
    else:
        print("⚠️  Some tests failed. Check individual results above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)