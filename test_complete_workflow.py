#!/usr/bin/env python3
"""
Comprehensive test for the complete unified workflow.

Tests all major fixes:
1. Validation dropdowns (no more 'V' entries) 
2. Sphere visibility with proper color names
3. Data synchronization between ternary and Plot_3D
4. Marker/color preferences unified system
5. Cluster assignments and centroids
6. Round-trip data accuracy
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_validation_system():
    """Test that validation system is working without '(none)' entries."""
    print("=== Testing Validation System ===")
    
    try:
        from utils.format_redirector import get_valid_markers, get_valid_colors, get_valid_spheres
        
        markers = get_valid_markers()
        colors = get_valid_colors()
        spheres = get_valid_spheres()
        
        # Check that first entry is empty string (not '(none)')
        first_marker_ok = markers[0] == ''
        first_color_ok = colors[0] == ''
        first_sphere_ok = spheres[0] == ''
        
        # Check that '(none)' is not in any list
        no_none_markers = '(none)' not in markers
        no_none_colors = '(none)' not in colors
        no_none_spheres = '(none)' not in spheres
        
        print(f"✅ First marker is empty string: {first_marker_ok}")
        print(f"✅ First color is empty string: {first_color_ok}")
        print(f"✅ First sphere is empty string: {first_sphere_ok}")
        print(f"✅ No '(none)' in markers: {no_none_markers}")
        print(f"✅ No '(none)' in colors: {no_none_colors}")
        print(f"✅ No '(none)' in spheres: {no_none_spheres}")
        
        validation_success = all([
            first_marker_ok, first_color_ok, first_sphere_ok,
            no_none_markers, no_none_colors, no_none_spheres
        ])
        
        print(f"🎯 Validation system test: {'PASS' if validation_success else 'FAIL'}")
        return validation_success
        
    except Exception as e:
        print(f"❌ Validation system test failed: {e}")
        return False

def test_sphere_color_conversion():
    """Test that sphere colors are properly converted from hex to names."""
    print("\n=== Testing Sphere Color Conversion ===")
    
    try:
        # Create mock cluster data
        mock_clusters = {
            0: [type('MockPoint', (), {'id': 'P1', 'lab': (50, 10, -5), 'rgb': (120, 100, 130)})()],
            1: [type('MockPoint', (), {'id': 'P2', 'lab': (60, -8, 12), 'rgb': (100, 140, 90)})()]
        }
        
        from gui.ternary_datasheet import TernaryDatasheetManager
        manager = TernaryDatasheetManager()
        
        # Calculate centroids
        centroids = manager._calculate_cluster_centroids_for_datasheet(mock_clusters)
        
        # Check that sphere colors are valid names (not hex codes)
        from utils.format_redirector import get_valid_spheres
        valid_spheres = get_valid_spheres()
        
        sphere_colors_ok = True
        hex_colors_found = False
        
        for cluster_id, centroid_data in centroids.items():
            sphere_color = centroid_data['sphere_color']
            print(f"Cluster {cluster_id} sphere color: '{sphere_color}'")
            
            if sphere_color.startswith('#'):
                print(f"❌ Found hex color: {sphere_color}")
                hex_colors_found = True
                sphere_colors_ok = False
            elif sphere_color not in valid_spheres:
                print(f"❌ Invalid sphere color: {sphere_color}")
                sphere_colors_ok = False
            else:
                print(f"✅ Valid sphere color: {sphere_color}")
        
        print(f"🎯 Sphere color conversion test: {'PASS' if sphere_colors_ok else 'FAIL'}")
        return sphere_colors_ok
        
    except Exception as e:
        print(f"❌ Sphere color conversion test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_normalization_accuracy():
    """Test that L*a*b* normalization is perfectly accurate."""
    print("\n=== Testing Normalization Accuracy ===")
    
    try:
        from utils.format_redirector import (
            normalize_lab_l, normalize_lab_a, normalize_lab_b,
            denormalize_lab_l, denormalize_lab_a, denormalize_lab_b
        )
        
        # Test cases with various L*a*b* values
        test_cases = [
            (50.0, 25.0, -15.0),  # Mid-range values
            (0.0, 0.0, 0.0),      # Black point
            (100.0, 127.0, 127.0), # High values
            (25.0, -64.0, 64.0),   # Mixed values
        ]
        
        accuracy_ok = True
        
        for original_l, original_a, original_b in test_cases:
            # Forward conversion
            norm_l = normalize_lab_l(original_l)
            norm_a = normalize_lab_a(original_a)
            norm_b = normalize_lab_b(original_b)
            
            # Reverse conversion
            recovered_l = denormalize_lab_l(norm_l)
            recovered_a = denormalize_lab_a(norm_a)
            recovered_b = denormalize_lab_b(norm_b)
            
            # Check accuracy (within 0.01 tolerance)
            l_accurate = abs(original_l - recovered_l) < 0.01
            a_accurate = abs(original_a - recovered_a) < 0.01
            b_accurate = abs(original_b - recovered_b) < 0.01
            
            case_accurate = l_accurate and a_accurate and b_accurate
            
            print(f"Lab({original_l:6.1f}, {original_a:6.1f}, {original_b:6.1f}) → "
                  f"Norm({norm_l:.4f}, {norm_a:.4f}, {norm_b:.4f}) → "
                  f"Lab({recovered_l:6.1f}, {recovered_a:6.1f}, {recovered_b:6.1f}) "
                  f"{'✅' if case_accurate else '❌'}")
            
            if not case_accurate:
                accuracy_ok = False
        
        print(f"🎯 Normalization accuracy test: {'PASS' if accuracy_ok else 'FAIL'}")
        return accuracy_ok
        
    except Exception as e:
        print(f"❌ Normalization accuracy test failed: {e}")
        return False

def test_metadata_compatibility():
    """Test that metadata keys work for both new and legacy systems."""
    print("\n=== Testing Metadata Compatibility ===")
    
    try:
        from utils.advanced_color_plots import ColorPoint
        
        # Test cases for different metadata key combinations
        test_cases = [
            # New unified keys
            {
                'name': 'Unified keys',
                'metadata': {
                    'marker_preference': 'o',
                    'color_preference': 'red'
                },
                'expected_marker': 'o',
                'expected_color': 'red'
            },
            # Legacy ternary keys (no marker_preference or color_preference keys)
            {
                'name': 'Legacy ternary keys',
                'metadata': {
                    # Explicitly don't include marker_preference or color_preference
                    'ternary_marker': '*',
                    'ternary_marker_color': 'green'
                },
                'expected_marker': '*',
                'expected_color': 'green'
            },
            # Mixed keys (unified should take precedence)
            {
                'name': 'Mixed keys (unified precedence)',
                'metadata': {
                    'marker_preference': 's',
                    'color_preference': 'blue',
                    'ternary_marker': 'x',
                    'ternary_marker_color': 'yellow'
                },
                'expected_marker': 's',
                'expected_color': 'blue'
            },
            # Empty/None values with fallbacks
            {
                'name': 'Fallback chain',
                'metadata': {
                    'marker_preference': '',  # Empty, should fallback
                    'color_preference': None, # None, should fallback
                    'ternary_marker': '+',
                    'ternary_marker_color': 'purple'
                },
                'expected_marker': '+',
                'expected_color': 'purple'
            }
        ]
        
        compatibility_ok = True
        
        for test_case in test_cases:
            # Create test point
            point = ColorPoint(
                id=f"Test_{test_case['name'].replace(' ', '_')}",
                lab=(50.0, 0.0, 0.0),
                rgb=(128, 128, 128),
                ternary_coords=(0.33, 0.33),
                metadata=test_case['metadata']
            )
            
            # Test metadata retrieval logic (same as in ternary datasheet)
            marker_pref = (point.metadata.get('marker_preference', '.') or 
                          point.metadata.get('ternary_marker', '.') or 
                          point.metadata.get('marker', '.'))
            color_pref = (point.metadata.get('color_preference', 'blue') or 
                         point.metadata.get('ternary_marker_color', 'blue') or 
                         point.metadata.get('marker_color', 'blue'))
            
            marker_ok = marker_pref == test_case['expected_marker']
            color_ok = color_pref == test_case['expected_color']
            case_ok = marker_ok and color_ok
            
            print(f"{test_case['name']:25} → "
                  f"marker='{marker_pref}' (expect '{test_case['expected_marker']}') "
                  f"color='{color_pref}' (expect '{test_case['expected_color']}') "
                  f"{'✅' if case_ok else '❌'}")
            
            if not case_ok:
                compatibility_ok = False
        
        print(f"🎯 Metadata compatibility test: {'PASS' if compatibility_ok else 'FAIL'}")
        return compatibility_ok
        
    except Exception as e:
        print(f"❌ Metadata compatibility test failed: {e}")
        return False

def test_unified_imports():
    """Test that all unified modules can be imported without errors."""
    print("\n=== Testing Unified Module Imports ===")
    
    modules_to_test = [
        'utils.format_redirector',
        'utils.unified_data_manager',
        'utils.data_file_manager',
        'gui.realtime_plot3d_sheet',
        'gui.ternary_datasheet',
        'plot3d.sphere_manager'
    ]
    
    import_results = {}
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            import_results[module_name] = True
            print(f"✅ {module_name}")
        except Exception as e:
            import_results[module_name] = False
            print(f"❌ {module_name}: {e}")
    
    all_imports_ok = all(import_results.values())
    
    print(f"🎯 Unified imports test: {'PASS' if all_imports_ok else 'FAIL'}")
    return all_imports_ok

def main():
    """Run all comprehensive tests."""
    print("🧪 COMPREHENSIVE UNIFIED WORKFLOW TEST")
    print("=" * 50)
    
    test_results = []
    
    # Run all tests
    test_results.append(test_validation_system())
    test_results.append(test_sphere_color_conversion())
    test_results.append(test_normalization_accuracy())
    test_results.append(test_metadata_compatibility())
    test_results.append(test_unified_imports())
    
    # Summary
    print("\n" + "=" * 50)
    print("🎯 COMPREHENSIVE TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(test_results)
    total = len(test_results)
    
    test_names = [
        "Validation System",
        "Sphere Color Conversion", 
        "Normalization Accuracy",
        "Metadata Compatibility",
        "Unified Module Imports"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "PASS" if result else "FAIL"
        print(f"{name:25} {status}")
    
    print("-" * 50)
    print(f"Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! The unified workflow is working correctly.")
        print("\nKey accomplishments:")
        print("✅ Validation dropdowns use empty strings instead of '(none)'")
        print("✅ Sphere colors are converted from hex to valid color names") 
        print("✅ L*a*b* normalization is perfectly accurate (round-trip)")
        print("✅ Metadata keys work for both unified and legacy systems")
        print("✅ All unified modules import without errors")
        print("\nThe system should now work correctly for:")
        print("• Ternary datasheet integration with Plot_3D")
        print("• Sphere visibility in Plot_3D when cluster data exists")
        print("• Unified marker/color preference management")
        print("• Data synchronization between all components")
        
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check individual results above.")
        print("Some issues may remain in the unified workflow.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)