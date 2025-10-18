#!/usr/bin/env python3
"""
Test RGB-CMY Integration with StampZ Workflow

Tests the RGB-CMY analyzer integration with existing coordinate marker system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.rgb_cmy_color_analyzer import RGBCMYColorAnalyzer
from PIL import Image, ImageDraw
import numpy as np


class MockCoordinateMarker:
    """Mock coordinate marker for testing."""
    
    def __init__(self, x, y, width=20, height=20, shape='rectangle', anchor='center'):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.shape = shape
        self.anchor = anchor


def test_rgb_cmy_integration():
    """Test RGB-CMY analysis integration with coordinate markers."""
    print("🧪 Testing RGB-CMY Integration with StampZ Workflow")
    print("=" * 55)
    
    # Create test image similar to what StampZ would load
    print("1️⃣ Creating test image...")
    test_image = Image.new('RGB', (800, 600), (240, 240, 240))
    draw = ImageDraw.Draw(test_image)
    
    # Add colored regions for testing
    regions = [
        ((100, 100, 150, 150), (200, 50, 50)),    # Red
        ((300, 100, 150, 150), (50, 200, 50)),    # Green  
        ((500, 100, 150, 150), (50, 50, 200)),    # Blue
        ((100, 300, 150, 150), (200, 200, 50)),   # Yellow
        ((300, 300, 150, 150), (200, 50, 200)),   # Magenta
        ((500, 300, 150, 150), (50, 200, 200))    # Cyan
    ]
    
    for (x, y, w, h), color in regions:
        draw.rectangle([x, y, x+w, y+h], fill=color)
    
    # Save test image
    test_image_path = "test_integration_image.png"
    test_image.save(test_image_path)
    print(f"   📸 Saved test image: {test_image_path}")
    
    # Create mock coordinate markers (similar to what StampZ Sample tool creates)
    print("2️⃣ Creating coordinate markers...")
    coord_markers = []
    
    # Create markers at the center of each colored region
    marker_positions = [
        (175, 175),  # Red region center
        (375, 175),  # Green region center
        (575, 175),  # Blue region center
        (175, 375),  # Yellow region center
        (375, 375),  # Magenta region center
        (575, 375)   # Cyan region center
    ]
    
    for i, (x, y) in enumerate(marker_positions):
        marker = MockCoordinateMarker(x, y, width=50, height=50, shape='rectangle', anchor='center')
        coord_markers.append(marker)
        print(f"   🎯 Created marker {i+1} at ({x}, {y})")
    
    print(f"   📍 Created {len(coord_markers)} coordinate markers")
    
    # Test RGB-CMY analysis using the integration module
    print("3️⃣ Running RGB-CMY analysis through integration...")
    
    analyzer = RGBCMYColorAnalyzer()
    
    results = analyzer.analyze_image_rgb_cmy_from_canvas(
        test_image_path,
        "Integration_Test_Set",
        coord_markers
    )
    
    if not results:
        print("❌ RGB-CMY analysis failed!")
        return False
    
    print(f"   ✅ Analysis successful: {results['num_samples']} samples")
    
    # Display results
    print("4️⃣ Analysis Results:")
    print("-" * 80)
    print(f"{'Sample':<12} {'Pixels':<8} {'R':<6} {'G':<6} {'B':<6} | {'C':<6} {'Y':<6} {'M':<6}")
    print("-" * 80)
    
    sample_results = results['results']
    expected_colors = ['Red', 'Green', 'Blue', 'Yellow', 'Magenta', 'Cyan']
    
    for i, result in enumerate(sample_results):
        color_name = expected_colors[i] if i < len(expected_colors) else f"Sample_{i+1}"
        print(f"{color_name:<12} "
              f"{result['pixel_count']:<8} "
              f"{result['R_mean']:<6.1f} "
              f"{result['G_mean']:<6.1f} "
              f"{result['B_mean']:<6.1f} | "
              f"{result['C_mean']:<6.1f} "
              f"{result['Y_mean']:<6.1f} "
              f"{result['M_mean']:<6.1f}")
    
    # Test export functionality
    print("\n5️⃣ Testing export functionality...")
    
    try:
        # Export to CSV (since we may not have the Excel template)
        csv_path = "Integration_Test_RGB_CMY_Results.csv"
        rgb_cmy_analyzer = results['analyzer']
        rgb_cmy_analyzer._export_to_csv(csv_path)
        
        print(f"   📊 Exported results to: {csv_path}")
        
        # Verify CSV contains expected data
        with open(csv_path, 'r') as f:
            csv_content = f.read()
            if "Colour Space Analysis" in csv_content and "Sample#" in csv_content:
                print("   ✅ CSV export format validated")
            else:
                print("   ⚠️  CSV format may be incorrect")
    
    except Exception as e:
        print(f"   ❌ Export test failed: {e}")
    
    # Validate results make sense
    print("\n6️⃣ Validating results...")
    
    validation_passed = True
    
    for i, result in enumerate(sample_results):
        expected_color = expected_colors[i]
        r, g, b = result['R_mean'], result['G_mean'], result['B_mean']
        c, y, m = result['C_mean'], result['Y_mean'], result['M_mean']
        
        # Basic validation: CMY should be approximately 255 - RGB
        expected_c = 255 - r
        expected_y = 255 - g
        expected_m = 255 - b
        
        c_diff = abs(c - expected_c)
        y_diff = abs(y - expected_y)
        m_diff = abs(m - expected_m)
        
        if c_diff > 5 or y_diff > 5 or m_diff > 5:
            print(f"   ⚠️  Color conversion issue for {expected_color}: CMY calculation may be off")
            validation_passed = False
        
        # Validate that primary colors have expected high/low values
        if expected_color == "Red" and r < 150:
            print(f"   ⚠️  Red sample should have high R value, got {r:.1f}")
            validation_passed = False
        elif expected_color == "Green" and g < 150:
            print(f"   ⚠️  Green sample should have high G value, got {g:.1f}")
            validation_passed = False
        elif expected_color == "Blue" and b < 150:
            print(f"   ⚠️  Blue sample should have high B value, got {b:.1f}")
            validation_passed = False
    
    if validation_passed:
        print("   ✅ All results validated successfully")
    
    print(f"\n🎉 RGB-CMY Integration Test {'Passed' if validation_passed else 'Completed with Warnings'}!")
    print(f"\n📁 Files Created:")
    print(f"  • Test image: {test_image_path}")
    print(f"  • Results CSV: {csv_path}")
    
    print(f"\n📝 Integration Summary:")
    print(f"  • Successfully created {len(coord_markers)} mock coordinate markers")
    print(f"  • Analyzed {results['num_samples']} samples using RGB-CMY system")
    print(f"  • Generated template-compatible export")
    print(f"  • Validated RGB-CMY conversion accuracy")
    
    return validation_passed


if __name__ == "__main__":
    test_rgb_cmy_integration()