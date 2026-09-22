#!/usr/bin/env python3
"""
Debug script for sphere visibility issues.
Tests sphere data loading and visibility toggles.
"""

import sys
import os
import pandas as pd

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_sphere_manager_data():
    """Test sphere manager data processing."""
    print("=== Testing Sphere Manager Data Processing ===")
    
    try:
        from plot3d.sphere_manager import SphereManager
        import matplotlib.pyplot as plt
        
        # Create a mock DataFrame with 4 clusters and sphere data
        test_data = {
            'DataID': ['Cluster_0', 'Cluster_1', 'Cluster_2', 'Cluster_3', 'Point_1', 'Point_2'],
            'Xnorm': [0.2, 0.4, 0.6, 0.8, 0.3, 0.7],
            'Ynorm': [0.3, 0.5, 0.7, 0.2, 0.4, 0.6], 
            'Znorm': [0.4, 0.6, 0.8, 0.3, 0.5, 0.8],
            'Cluster': [0, 1, 2, 3, 0, 1],
            'Centroid_X': [0.2, 0.4, 0.6, 0.8, 0.2, 0.4],
            'Centroid_Y': [0.3, 0.5, 0.7, 0.2, 0.3, 0.5],
            'Centroid_Z': [0.4, 0.6, 0.8, 0.3, 0.4, 0.6],
            'Sphere': ['red', 'green', 'blue', 'yellow', '', ''],
            'Radius': [0.02, 0.02, 0.02, 0.02, '', '']
        }
        
        df = pd.DataFrame(test_data)
        print(f"Created test DataFrame with {len(df)} rows")
        print("DataFrame contents:")
        print(df.to_string())
        
        # Create sphere manager with mock components
        fig, ax = plt.subplots(subplot_kw={'projection': '3d'})
        canvas = None  # Mock canvas
        
        sphere_manager = SphereManager(ax, canvas, df)
        
        # Test get_active_colors
        active_colors = sphere_manager.get_active_colors()
        print(f"\nActive colors found: {active_colors}")
        
        # Check if all 4 expected colors are found
        expected_colors = ['red', 'green', 'blue', 'yellow']
        found_colors = []
        
        for expected in expected_colors:
            # Check if the color or its mapped version is in active colors
            mapped_color = sphere_manager._get_color(expected)
            if mapped_color in active_colors or expected in active_colors:
                found_colors.append(expected)
                print(f"✅ Found expected color: {expected} (mapped to: {mapped_color})")
            else:
                print(f"❌ Missing expected color: {expected} (would map to: {mapped_color})")
        
        print(f"\nSummary: Found {len(found_colors)}/{len(expected_colors)} expected colors")
        
        if len(found_colors) == len(expected_colors):
            print("✅ All expected sphere colors found!")
            return True
        else:
            print(f"⚠️  Only {len(found_colors)} of {len(expected_colors)} colors found")
            
            # Debug sphere data processing
            print("\nDebugging sphere data processing:")
            sphere_data = df['Sphere'].dropna().unique()
            print(f"Raw sphere data: {list(sphere_data)}")
            
            for sphere_str in sphere_data:
                print(f"Processing sphere string: '{sphere_str}'")
                if '/' in str(sphere_str):
                    color_name = str(sphere_str).split('/')[0].strip()
                else:
                    color_name = str(sphere_str).strip()
                print(f"  Extracted color name: '{color_name}'")
                mapped_color = sphere_manager._get_color(color_name)
                print(f"  Mapped to: '{mapped_color}'")
            
            return False
        
    except Exception as e:
        print(f"❌ Error testing sphere manager: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dataframe_structure():
    """Test DataFrame structure that would come from Plot_3D data loading."""
    print("\n=== Testing DataFrame Structure ===")
    
    try:
        # Test the data structure that comes from ColorDataBridge
        from utils.color_data_bridge import ColorDataBridge
        
        # Check if we can create a bridge
        bridge = ColorDataBridge()
        print("✅ ColorDataBridge created successfully")
        
        # Test sphere data in centroid rows (should be in rows 2-7 of Plot_3D format)
        # This simulates what should happen when Plot_3D loads cluster data
        mock_plot3d_data = []
        
        # Headers (row 0)
        headers = ['Xnorm', 'Ynorm', 'Znorm', 'DataID', 'Cluster', '∆E', 'Marker', 'Color', 
                  'Centroid_X', 'Centroid_Y', 'Centroid_Z', 'Sphere', 'Radius']
        
        # Centroid rows (rows 1-6, display rows 2-7)
        centroid_rows = [
            [0.25, 0.35, 0.45, 'Cluster_0', 0, '', 'x', 'red', 0.25, 0.35, 0.45, 'red', 0.02],
            [0.45, 0.55, 0.65, 'Cluster_1', 1, '', 'x', 'green', 0.45, 0.55, 0.65, 'green', 0.02],
            [0.65, 0.75, 0.85, 'Cluster_2', 2, '', 'x', 'blue', 0.65, 0.75, 0.85, 'blue', 0.02],
            [0.85, 0.25, 0.35, 'Cluster_3', 3, '', 'x', 'yellow', 0.85, 0.25, 0.35, 'yellow', 0.02],
            ['', '', '', '', '', '', '', '', '', '', '', '', ''],  # Empty centroid row
            ['', '', '', '', '', '', '', '', '', '', '', '', '']   # Empty centroid row
        ]
        
        # Data rows (rows 7+, display rows 8+)
        data_rows = [
            [0.30, 0.40, 0.50, 'Point_1', 0, '', '.', 'blue', '', '', '', '', ''],
            [0.50, 0.60, 0.70, 'Point_2', 1, '', 'o', 'red', '', '', '', '', '']
        ]
        
        # Combine all data
        all_data = centroid_rows + data_rows
        df = pd.DataFrame(all_data, columns=headers)
        
        print("Mock Plot_3D DataFrame structure:")
        print(df.to_string())
        
        # Check sphere data in centroid rows
        centroid_mask = df['DataID'].str.contains('Cluster_', na=False)
        centroid_df = df[centroid_mask]
        
        print(f"\nCentroid rows with sphere data:")
        print(centroid_df[['DataID', 'Sphere', 'Radius', 'Centroid_X', 'Centroid_Y', 'Centroid_Z']].to_string())
        
        # Check for valid centroid data (should have all three coordinates)
        valid_centroid_mask = (
            centroid_df['Centroid_X'].notna() & 
            centroid_df['Centroid_Y'].notna() & 
            centroid_df['Centroid_Z'].notna() &
            (centroid_df['Centroid_X'] != '') &
            (centroid_df['Centroid_Y'] != '') &
            (centroid_df['Centroid_Z'] != '')
        )
        
        valid_centroids = centroid_df[valid_centroid_mask]
        print(f"\nValid centroids (have all coordinates): {len(valid_centroids)}")
        
        if len(valid_centroids) > 0:
            print("Valid centroid sphere data:")
            for idx, row in valid_centroids.iterrows():
                print(f"  {row['DataID']}: Sphere='{row['Sphere']}', Coords=({row['Centroid_X']}, {row['Centroid_Y']}, {row['Centroid_Z']})")
        
        expected_spheres = 4
        actual_spheres = len(valid_centroids)
        
        if actual_spheres == expected_spheres:
            print(f"✅ Found all {expected_spheres} expected spheres with valid coordinates")
            return True
        else:
            print(f"⚠️  Expected {expected_spheres} spheres, found {actual_spheres}")
            return False
        
    except Exception as e:
        print(f"❌ Error testing DataFrame structure: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run sphere debugging tests."""
    print("🔍 Debugging Sphere Visibility Issues\n")
    
    results = []
    
    # Run tests
    results.append(test_sphere_manager_data())
    results.append(test_dataframe_structure())
    
    # Summary
    print(f"\n=== Debug Summary ===")
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All sphere debugging tests passed!")
        print("\nIf spheres are still not showing, the issue might be:")
        print("1. Data not being loaded correctly from database")
        print("2. UI initialization failing")
        print("3. Sphere manager update_references not being called")
    else:
        print("⚠️  Some sphere debugging tests failed.")
        print("This indicates issues with sphere data processing or structure.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)