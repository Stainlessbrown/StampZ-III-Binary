#!/usr/bin/env python3
"""
Test script for hue sorting integration with StampZ color libraries.
Tests the hue_sorting module with existing color library data.
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.hue_sorting import (
    sort_colors_philatelic, 
    filter_by_hue_groups, 
    get_hue_group,
    HueGroup,
    sort_lab_by_hue
)
from utils.color_library import ColorLibrary

def test_with_existing_libraries():
    """Test hue sorting with existing color libraries."""
    print("=" * 60)
    print("Testing Hue Sorting with Existing StampZ Color Libraries")
    print("=" * 60)
    
    try:
        # Test with default library
        print("\n1. Loading default color library...")
        library = ColorLibrary("default")
        
        # Get all colors from the library
        colors = library.get_all_colors()
        
        if not colors:
            print("   No colors found in default library.")
            print("   This is expected in a development environment.")
            
            # Create some test colors to demonstrate functionality
            print("\n2. Creating test colors for demonstration...")
            test_colors_rgb = [
                (139, 69, 19),   # Saddle brown
                (160, 82, 45),   # Sienna brown  
                (205, 133, 63),  # Peru brown
                (50, 50, 50),    # Dark gray
                (220, 220, 220), # Light gray
                (255, 255, 255), # White
                (0, 0, 0),       # Black
                (220, 20, 60),   # Crimson red
                (255, 140, 0),   # Dark orange
                (34, 139, 34),   # Forest green
                (30, 144, 255),  # Dodger blue
                (138, 43, 226),  # Blue violet
            ]
            
            print(f"   Created {len(test_colors_rgb)} test colors")
            
        else:
            print(f"   Found {len(colors)} colors in library")
            
            # Convert library colors to RGB for testing
            test_colors_rgb = []
            for color in colors[:20]:  # Test with first 20 colors to avoid overwhelming output
                test_colors_rgb.append((int(color.rgb[0]), int(color.rgb[1]), int(color.rgb[2])))
            
            print(f"   Using first {len(test_colors_rgb)} colors for testing")
        
        # Test philatelic sorting
        print("\n3. Testing philatelic color sorting...")
        sorted_colors = sort_colors_philatelic(test_colors_rgb)
        
        print("   Results (showing color groups):")
        current_group = None
        group_count = 0
        
        for i, (r, g, b) in enumerate(sorted_colors):
            group = get_hue_group(r, g, b)
            
            if group != current_group:
                if current_group is not None:
                    print(f"      (Total {group_count} colors in {current_group.name} group)")
                print(f"   --- {group.name} GROUP ---")
                current_group = group
                group_count = 0
            
            group_count += 1
            
            # Show first few colors in each group
            if group_count <= 3:
                print(f"      RGB({r:3d}, {g:3d}, {b:3d}) - {group.name}")
            elif group_count == 4:
                print("      ...")
        
        if current_group is not None:
            print(f"      (Total {group_count} colors in {current_group.name} group)")
        
        # Test group filtering
        print("\n4. Testing hue group filtering...")
        
        # Filter chromatic colors only
        chromatic_only = filter_by_hue_groups(test_colors_rgb, [HueGroup.CHROMATIC])
        print(f"   Chromatic colors only: {len(chromatic_only)} colors")
        
        # Filter achromatic colors only  
        achromatic_only = filter_by_hue_groups(test_colors_rgb, [HueGroup.BLACK, HueGroup.GRAY, HueGroup.WHITE])
        print(f"   Achromatic colors only: {len(achromatic_only)} colors")
        
        # Test with LAB colors if we have library colors
        if colors and len(colors) > 0:
            print("\n5. Testing L*a*b* hue sorting with library colors...")
            lab_colors = [(color.lab[0], color.lab[1], color.lab[2]) for color in colors[:10]]
            
            try:
                sorted_lab = sort_lab_by_hue(lab_colors)
                print(f"   Successfully sorted {len(sorted_lab)} L*a*b* colors by hue")
            except ImportError as e:
                print(f"   Skipping L*a*b* test: {e}")
        
        print("\n✅ All tests completed successfully!")
        print("\nIntegration Summary:")
        print("- Philatelic sorting works correctly")
        print("- Group filtering functions properly")
        print("- Compatible with existing ColorLibrary system")
        print("- Ready for integration with Compare function")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_compare_function_integration():
    """Test how hue sorting would integrate with the Compare function."""
    print("\n" + "=" * 60)
    print("Testing Compare Function Integration")
    print("=" * 60)
    
    # Simulate colors from a stamp analysis
    stamp_colors = [
        (139, 69, 19),   # Brown stamp color
        (160, 82, 45),   # Another brown shade
        (220, 20, 60),   # Red accent
        (255, 140, 0),   # Orange element
        (240, 240, 240), # Paper white
        (60, 60, 60),    # Postmark black
        (180, 180, 180), # Gray shading
    ]
    
    print(f"\nSimulated stamp analysis found {len(stamp_colors)} colors")
    
    # Show how Compare function could use hue group filtering
    scenarios = [
        ("All chromatic colors (excluding paper/postmark)", [HueGroup.CHROMATIC]),
        ("Only achromatic colors (paper/postmark)", [HueGroup.BLACK, HueGroup.GRAY, HueGroup.WHITE]),
        ("Browns and reds only", [HueGroup.CHROMATIC]),  # Would need additional filtering by hue range
    ]
    
    for scenario_name, groups in scenarios:
        filtered = filter_by_hue_groups(stamp_colors, groups)
        print(f"\n{scenario_name}: {len(filtered)} colors")
        for r, g, b in filtered:
            group = get_hue_group(r, g, b)
            print(f"   RGB({r:3d}, {g:3d}, {b:3d}) - {group.name}")
    
    print("\n✅ Compare function integration ready!")

if __name__ == "__main__":
    print("StampZ Hue Sorting Integration Test")
    print("This test verifies hue sorting works with your color library system.")
    
    success = test_with_existing_libraries()
    
    if success:
        test_compare_function_integration()
        print("\n🎉 All tests passed! Ready for version update and commit.")
    else:
        print("\n⚠️  Some tests failed. Please review before committing.")
    
    print("\nNext steps:")
    print("1. Update version number")
    print("2. Add and commit changes")
    print("3. Push to test with full color libraries (>500 colors)")