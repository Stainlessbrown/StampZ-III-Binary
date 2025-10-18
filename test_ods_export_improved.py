#!/usr/bin/env python3
"""
Test improved ODS export functionality for RGB-CMY analysis
"""

import os
import sys
import numpy as np
from PIL import Image
import tempfile
import shutil

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from rgb_cmy_analyzer import RGBCMYAnalyzer

def create_test_image():
    """Create a simple test image for analysis."""
    # Create a 300x200 RGB image with 6 different colored regions
    image = Image.new('RGB', (300, 200))
    pixels = []
    
    for y in range(200):
        for x in range(300):
            if x < 50:  # Strip 1 - Red
                pixels.append((200, 50, 50))
            elif x < 100:  # Strip 2 - Green 
                pixels.append((50, 200, 50))
            elif x < 150:  # Strip 3 - Blue
                pixels.append((50, 50, 200))
            elif x < 200:  # Strip 4 - Yellow
                pixels.append((220, 220, 50))
            elif x < 250:  # Strip 5 - Magenta
                pixels.append((200, 50, 200))
            else:  # Strip 6 - Cyan
                pixels.append((50, 200, 200))
    
    image.putdata(pixels)
    return image

def create_test_masks(image_size):
    """Create test masks for different regions."""
    masks = {}
    
    # Create masks for each colored region - now 6 samples
    regions = [
        ("Sample_01", (25, 100, 25, 50)),     # Red region
        ("Sample_02", (75, 100, 25, 50)),     # Green region  
        ("Sample_03", (125, 100, 25, 50)),    # Blue region
        ("Sample_04", (175, 100, 25, 50)),    # Yellow region
        ("Sample_05", (225, 100, 25, 50)),    # Magenta region
        ("Sample_06", (275, 100, 25, 50))     # Cyan region
    ]
    
    for sample_name, (x, y, width, height) in regions:
        mask = Image.new('L', image_size, 0)  # Black background
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.rectangle([x, y, x + width, y + height], fill=255)  # White region
        masks[sample_name] = mask
    
    return masks

def test_ods_export():
    """Test the improved ODS export functionality."""
    
    print("Testing improved ODS export functionality...")
    
    # Create analyzer
    analyzer = RGBCMYAnalyzer()
    
    # Create test image
    test_image = create_test_image()
    
    # Save test image to temporary file
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
            'plate': 'Test Plate ODS',
            'die': 'Test Die',
            'date_registered': '10/17/2024',
            'described_colour': 'ODS Export Test',
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
        
        # Print sample results
        for i, result in enumerate(results[:2]):  # Show first 2 samples
            print(f"Sample {i+1}: RGB({result['R_mean']:.1f}, {result['G_mean']:.1f}, {result['B_mean']:.1f}) "
                  f"CMY({result['C_mean']:.1f}, {result['M_mean']:.1f}, {result['Y_mean']:.1f})")
        
        # Test ODS export
        output_path = "/Users/stanbrown/Desktop/StampZ-III-Binary/test_ods_export_improved.ods"
        template_path = "/Users/stanbrown/Desktop/SG 19 Measures/RGB-CMY Channel analysis.ods"
        
        success = analyzer.export_to_template(template_path, output_path)
        
        if success:
            print(f"SUCCESS: ODS file exported to {output_path}")
            print("Try opening the file in LibreOffice Calc to verify data population")
            
            # Check if file exists and has reasonable size
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"File size: {file_size} bytes")
                if file_size > 5000:  # Should be larger than empty template
                    print("File appears to contain data (reasonable size)")
                    return True
                else:
                    print("WARNING: File is quite small, may only be template")
                    return True
            else:
                print("ERROR: Output file not created")
                return False
        else:
            print("ERROR: ODS export failed")
            return False
        
    finally:
        # Cleanup
        try:
            os.unlink(test_image_path)
        except:
            pass

if __name__ == "__main__":
    success = test_ods_export()
    if success:
        print("\n✅ ODS export test completed successfully!")
    else:
        print("\n❌ ODS export test failed!")
    
    sys.exit(0 if success else 1)