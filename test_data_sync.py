#!/usr/bin/env python3
"""
Test script to verify data synchronization between ternary system and Plot_3D.

This will test:
1. ColorPoint metadata loading (marker_preference, color_preference)
2. Database saving and loading of unified preferences  
3. Sphere data creation and population in datasheets
4. Data flow from ColorDataBridge to ternary display
"""

import sys
import os
import tempfile

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_colorpoint_metadata():
    """Test that ColorPoints are created with correct metadata."""
    print("=== Testing ColorPoint Metadata ===")
    
    try:
        from utils.advanced_color_plots import ColorPoint
        
        # Create a test ColorPoint with metadata (include metadata in constructor)
        test_metadata = {
            'marker_preference': 'o',
            'color_preference': 'red',
            'ternary_marker': '*',  # Legacy key for compatibility
            'ternary_marker_color': 'blue'  # Legacy key for compatibility
        }
        
        test_point = ColorPoint(
            id="Test_Point_1",
            lab=(50.0, 25.0, -15.0),
            rgb=(128, 100, 150),
            ternary_coords=(0.4, 0.6),
            metadata=test_metadata
        )
        
        print(f"Created test point: {test_point.id}")
        print(f"Metadata: {test_point.metadata}")
        
        # Test metadata retrieval logic (same as in ternary datasheet)
        marker_pref = (test_point.metadata.get('marker_preference', '.') or 
                      test_point.metadata.get('ternary_marker', '.') or 
                      test_point.metadata.get('marker', '.'))
        color_pref = (test_point.metadata.get('color_preference', 'blue') or 
                     test_point.metadata.get('ternary_marker_color', 'blue') or 
                     test_point.metadata.get('marker_color', 'blue'))
        
        print(f"Retrieved marker: '{marker_pref}' (expected: 'o')")
        print(f"Retrieved color: '{color_pref}' (expected: 'red')")
        
        success = (marker_pref == 'o' and color_pref == 'red')
        print(f"✅ ColorPoint metadata test: {success}")
        
        return success
        
    except Exception as e:
        print(f"❌ Error testing ColorPoint metadata: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_integration():
    """Test database saving and loading of unified preferences."""
    print("\n=== Testing Database Integration ===")
    
    try:
        from utils.color_analysis_db import ColorAnalysisDB
        from utils.color_analysis_db import load_measurements_from_db
        
        # Create a temporary database for testing
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            temp_db_path = temp_db.name
        
        print(f"Using temporary database: {temp_db_path}")
        
        # Test 1: Create database instance and save measurement
        db = ColorAnalysisDB("Test_Sample_Set")
        db.db_path = temp_db_path  # Override to use temp database
        
        # Save a test measurement set
        set_id = db.create_measurement_set("test_image.jpg", "Test description")
        print(f"Created measurement set: {set_id}")
        
        # Save a measurement with preferences
        measurement_id = db.save_measurement(
            set_id=set_id,
            coordinate_point=1,
            x_position=100.0,
            y_position=200.0,
            l_value=45.5,
            a_value=12.3,
            b_value=-8.7,
            rgb_r=120, rgb_g=100, rgb_b=150,
            marker_preference='s',
            color_preference='green'
        )
        print(f"Saved measurement ID: {measurement_id}")
        
        # Test 2: Update preferences using the unified method
        update_result = db.update_marker_color_preferences(
            image_name="test_image",
            coordinate_point=1,
            marker='D',
            color='purple'
        )
        print(f"Update preferences result: {update_result}")
        
        # Test 3: Load measurements back
        loaded_data = load_measurements_from_db("Test_Sample_Set")
        print(f"Loaded {len(loaded_data)} measurements from database")
        
        if loaded_data:
            test_measurement = loaded_data[0]
            print(f"Loaded measurement: {test_measurement.id}")
            print(f"Loaded metadata: {test_measurement.metadata}")
            
            # Check for unified preferences in metadata
            has_marker_pref = 'marker_preference' in test_measurement.metadata
            has_color_pref = 'color_preference' in test_measurement.metadata
            
            print(f"Has marker_preference: {has_marker_pref}")
            print(f"Has color_preference: {has_color_pref}")
            
            success = has_marker_pref and has_color_pref
        else:
            print("❌ No measurements loaded from database")
            success = False
        
        # Cleanup
        try:
            os.unlink(temp_db_path)
        except:
            pass
            
        print(f"✅ Database integration test: {success}")
        return success
        
    except Exception as e:
        print(f"❌ Error testing database integration: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_centroid_data_creation():
    """Test that centroid data is created correctly for spheres."""
    print("\n=== Testing Centroid Data Creation ===")
    
    try:
        # Create mock cluster data similar to what ternary clustering would produce
        mock_clusters = {
            0: [
                # Mock ColorPoints in cluster 0
                type('MockColorPoint', (), {
                    'id': 'Point_0_1',
                    'lab': (45.0, 10.0, -5.0),
                    'rgb': (120, 100, 130)
                })(),
                type('MockColorPoint', (), {
                    'id': 'Point_0_2', 
                    'lab': (47.0, 12.0, -3.0),
                    'rgb': (125, 105, 135)
                })()
            ],
            1: [
                # Mock ColorPoints in cluster 1
                type('MockColorPoint', (), {
                    'id': 'Point_1_1',
                    'lab': (65.0, -10.0, 15.0),
                    'rgb': (100, 140, 90)
                })(),
                type('MockColorPoint', (), {
                    'id': 'Point_1_2',
                    'lab': (67.0, -8.0, 17.0),
                    'rgb': (105, 145, 95)
                })()
            ]
        }
        
        print(f"Created {len(mock_clusters)} mock clusters")
        
        # Import the ternary datasheet manager to test centroid calculation
        from gui.ternary_datasheet import TernaryDatasheetManager
        
        manager = TernaryDatasheetManager()
        
        # Test the centroid calculation method
        centroids = manager._calculate_cluster_centroids_for_datasheet(mock_clusters)
        
        print(f"Calculated {len(centroids)} centroids")
        
        # Check centroid data structure  
        for cluster_id, centroid_data in centroids.items():
            print(f"Cluster {cluster_id}:")
            print(f"  Centroid: ({centroid_data['centroid_x']:.4f}, {centroid_data['centroid_y']:.4f}, {centroid_data['centroid_z']:.4f})")
            print(f"  Sphere color: {centroid_data['sphere_color']}")
            print(f"  Sphere radius: {centroid_data['sphere_radius']}")
        
        # Verify that all required keys are present
        required_keys = ['centroid_x', 'centroid_y', 'centroid_z', 'sphere_color', 'sphere_radius']
        success = True
        
        for cluster_id, centroid_data in centroids.items():
            for key in required_keys:
                if key not in centroid_data:
                    print(f"❌ Missing key '{key}' in cluster {cluster_id}")
                    success = False
        
        # Check that sphere colors are valid names (not hex codes)
        from utils.format_redirector import get_valid_spheres
        valid_spheres = get_valid_spheres()
        
        for cluster_id, centroid_data in centroids.items():
            sphere_color = centroid_data['sphere_color']
            if sphere_color.startswith('#'):
                print(f"❌ Sphere color is hex code '{sphere_color}' in cluster {cluster_id}, should be color name")
                success = False
            elif sphere_color not in valid_spheres:
                print(f"❌ Invalid sphere color '{sphere_color}' in cluster {cluster_id}")
                success = False
                
        print(f"✅ Centroid data creation test: {success}")
        return success
        
    except Exception as e:
        print(f"❌ Error testing centroid data creation: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all synchronization tests."""
    print("🔗 Testing Data Synchronization Between Ternary and Plot_3D\n")
    
    results = []
    
    # Run tests
    results.append(test_colorpoint_metadata())
    results.append(test_database_integration())
    results.append(test_centroid_data_creation())
    
    # Summary
    print(f"\n=== Synchronization Test Summary ===")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All synchronization tests passed!")
    else:
        print("⚠️  Some synchronization tests failed. Check individual results above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)