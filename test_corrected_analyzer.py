#!/usr/bin/env python3
"""
Test the corrected RGB-CMY analyzer with proper channel order
"""

import os
import sys
import numpy as np
from PIL import Image
import tempfile

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from rgb_cmy_analyzer_corrected import RGBCMYAnalyzer

def create_test_image():
    """Create test image with 6 distinct colored regions"""
    image = Image.new('RGB', (300, 200))
    pixels = []
    
    for y in range(200):
        for x in range(300):
            if x < 50:  # Strip 1 - Pure Red
                pixels.append((255, 0, 0))
            elif x < 100:  # Strip 2 - Pure Green 
                pixels.append((0, 255, 0))
            elif x < 150:  # Strip 3 - Pure Blue
                pixels.append((0, 0, 255))
            elif x < 200:  # Strip 4 - Yellow
                pixels.append((255, 255, 0))
            elif x < 250:  # Strip 5 - Magenta
                pixels.append((255, 0, 255))
            else:  # Strip 6 - Cyan
                pixels.append((0, 255, 255))
    
    image.putdata(pixels)
    return image

def create_test_masks(image_size):
    """Create test masks for 6 colored regions"""
    masks = {}
    
    regions = [
        ("Sample_01", (25, 100, 25, 50)),     # Red region
        ("Sample_02", (75, 100, 25, 50)),     # Green region  
        ("Sample_03", (125, 100, 25, 50)),    # Blue region
        ("Sample_04", (175, 100, 25, 50)),    # Yellow region
        ("Sample_05", (225, 100, 25, 50)),    # Magenta region
        ("Sample_06", (275, 100, 25, 50))     # Cyan region
    ]
    
    for sample_name, (x, y, width, height) in regions:
        mask = Image.new('L', image_size, 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.rectangle([x, y, x + width, y + height], fill=255)
        masks[sample_name] = mask
    
    return masks

def test_corrected_analyzer():
    """Test the corrected analyzer with proper RGB order"""
    
    print("Testing CORRECTED RGB-CMY analyzer...")
    
    # Create analyzer
    analyzer = RGBCMYAnalyzer()
    
    # Create test image with pure colors
    test_image = create_test_image()
    
    # Save test image
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        test_image_path = temp_file.name
        test_image.save(test_image_path)
    
    try:
        # Load the test image
        if not analyzer.load_image(test_image_path):
            print("ERROR: Failed to load test image")
            return False
        
        # Set test metadata
        analyzer.set_metadata({
            'date_measured': '10/17/2024',
            'plate': 'Test Plate CORRECTED',
            'die': 'Test Die',
            'date_registered': '10/17/2024',
            'described_colour': 'Corrected RGB Order Test',
            'total_pixels': str(test_image.size[0] * test_image.size[1])
        })
        
        # Create test masks
        test_masks = create_test_masks(test_image.size)
        
        print(f"Created {len(test_masks)} test masks")
        
        # Analyze the masks
        results = analyzer.analyze_multiple_masks(test_masks)
        
        if not results:
            print("ERROR: Analysis returned no results")
            return False
        
        print(f"Analysis completed with {len(results)} samples")
        print("\n=== RGB Analysis Results ===")
        
        expected_colors = [
            ("Red", (255, 0, 0)),
            ("Green", (0, 255, 0)), 
            ("Blue", (0, 0, 255)),
            ("Yellow", (255, 255, 0)),
            ("Magenta", (255, 0, 255)),
            ("Cyan", (0, 255, 255))
        ]
        
        # Verify each sample has correct RGB values
        for i, (result, (color_name, expected_rgb)) in enumerate(zip(results, expected_colors)):
            actual_rgb = (result['R_mean'], result['G_mean'], result['B_mean'])
            actual_cmy = (result['C_mean'], result['M_mean'], result['Y_mean'])
            expected_cmy = (255 - expected_rgb[0], 255 - expected_rgb[1], 255 - expected_rgb[2])
            
            print(f"Sample {i+1} ({color_name}):")
            print(f"  Expected RGB: {expected_rgb}")
            print(f"  Actual RGB:   ({actual_rgb[0]:.0f}, {actual_rgb[1]:.0f}, {actual_rgb[2]:.0f})")
            print(f"  Expected CMY: {expected_cmy}")
            print(f"  Actual CMY:   ({actual_cmy[0]:.0f}, {actual_cmy[1]:.0f}, {actual_cmy[2]:.0f})")
            
            # Check if values are close (within tolerance for pure colors)
            rgb_close = all(abs(a - e) < 5 for a, e in zip(actual_rgb, expected_rgb))
            cmy_close = all(abs(a - e) < 5 for a, e in zip(actual_cmy, expected_cmy))
            
            if rgb_close and cmy_close:
                print(f"  ✅ CORRECT!")
            else:
                print(f"  ❌ MISMATCH!")
                return False
            print()
        
        # Test ODS export
        output_path = "/Users/stanbrown/Desktop/StampZ-III-Binary/test_corrected_rgb_cmy.ods"
        template_path = "/Users/stanbrown/Desktop/SG 19 Measures/RGB-CMY Channel analysis.ods"
        
        success = analyzer.export_to_template(template_path, output_path)
        
        if success:
            print(f"✅ ODS file exported: {output_path}")
            print("Now the exported data should show proper RGB and CMY values!")
            return True
        else:
            print("❌ ODS export failed")
            return False
        
    finally:
        # Cleanup
        try:
            os.unlink(test_image_path)
        except:
            pass

if __name__ == "__main__":
    success = test_corrected_analyzer()
    if success:
        print("\n🎉 CORRECTED RGB-CMY analyzer test passed!")
        print("The channel mapping is now fixed!")
        print("Remember to update your templates to use RGB order instead of BGR")
    else:
        print("\n💥 Test failed!")
    
    sys.exit(0 if success else 1)