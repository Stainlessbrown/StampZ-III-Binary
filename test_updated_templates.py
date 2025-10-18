#!/usr/bin/env python3
"""
Test RGB-CMY analysis with updated templates that use RGB order
"""

import os
import sys
import tempfile
from PIL import Image, ImageDraw

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

def test_with_updated_templates():
    """Test RGB-CMY export with updated template files"""
    
    print("🧪 Testing RGB-CMY Analysis with Updated Templates")
    print("=" * 55)
    
    # Check if corrected analyzer is in place
    analyzer_path = "utils/rgb_cmy_analyzer.py"
    
    try:
        with open(analyzer_path, 'r') as f:
            content = f.read()
            if "CORRECTED VERSION" in content:
                print("✅ Using corrected RGB-CMY analyzer")
            else:
                print("⚠️  Original analyzer still in use - you need to replace it!")
                print("   Replace utils/rgb_cmy_analyzer.py with utils/rgb_cmy_analyzer_corrected.py")
                return False
    except Exception as e:
        print(f"❌ Cannot read analyzer file: {e}")
        return False
    
    try:
        from rgb_cmy_analyzer import RGBCMYAnalyzer
    except Exception as e:
        print(f"❌ Cannot import RGB-CMY analyzer: {e}")
        return False
    
    # Create test data
    print("\n📊 Creating test image with distinct colors...")
    
    # Create simple test image
    image = Image.new('RGB', (300, 200))
    draw = ImageDraw.Draw(image)
    
    # Draw colored rectangles
    colors_and_regions = [
        ((255, 0, 0), (25, 100, 25, 50), "Red"),      # Red
        ((0, 255, 0), (75, 100, 25, 50), "Green"),    # Green  
        ((0, 0, 255), (125, 100, 25, 50), "Blue"),    # Blue
        ((255, 255, 0), (175, 100, 25, 50), "Yellow"), # Yellow
    ]
    
    # Fill image and draw test rectangles
    draw.rectangle([(0, 0), (300, 200)], fill=(128, 128, 128))  # Gray background
    
    masks = {}
    expected_values = {}
    
    for i, ((r, g, b), (x, y, w, h), color_name) in enumerate(colors_and_regions):
        # Draw colored rectangle
        draw.rectangle([(x, y), (x+w, y+h)], fill=(r, g, b))
        
        # Create corresponding mask
        mask = Image.new('L', image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rectangle([(x, y), (x+w, y+h)], fill=255)
        
        sample_name = f"Sample_{i+1:02d}"
        masks[sample_name] = mask
        expected_values[sample_name] = {
            'color_name': color_name,
            'rgb': (r, g, b),
            'cmy': (255-r, 255-g, 255-b)
        }
    
    # Save test image
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        test_image_path = temp_file.name
        image.save(test_image_path)
    
    try:
        # Create analyzer and run analysis
        analyzer = RGBCMYAnalyzer()
        
        if not analyzer.load_image(test_image_path):
            print("❌ Failed to load test image")
            return False
        
        analyzer.set_metadata({
            'date_measured': '10/17/2024',
            'plate': 'Template Test',
            'die': 'RGB Order Test',
            'date_registered': '10/17/2024', 
            'described_colour': 'Testing Updated Templates',
            'total_pixels': str(image.size[0] * image.size[1])
        })
        
        print(f"📍 Created {len(masks)} test samples with distinct colors")
        
        # Run analysis
        results = analyzer.analyze_multiple_masks(masks)
        
        if not results:
            print("❌ Analysis failed")
            return False
        
        print(f"✅ Analysis completed for {len(results)} samples")
        
        # Verify results make sense
        print("\n🔍 Verifying RGB values are correct:")
        all_correct = True
        
        for i, result in enumerate(results):
            sample_name = f"Sample_{i+1:02d}"
            expected = expected_values[sample_name]
            
            actual_rgb = (round(result['R_mean']), round(result['G_mean']), round(result['B_mean']))
            expected_rgb = expected['rgb']
            
            rgb_match = all(abs(a - e) <= 2 for a, e in zip(actual_rgb, expected_rgb))
            
            print(f"  {sample_name} ({expected['color_name']}): Expected {expected_rgb}, Got {actual_rgb} {'✅' if rgb_match else '❌'}")
            
            if not rgb_match:
                all_correct = False
        
        if not all_correct:
            print("❌ RGB values don't match expected - channel mapping may still be wrong")
            return False
        
        # Test export to updated templates
        print(f"\n📁 Testing export to updated templates...")
        
        # Test ODS export
        template_path = "data/Templates/RGB-CMY Channel analysis.ods"  # Updated template location
        output_path = "/Users/stanbrown/Desktop/StampZ-III-Binary/test_with_updated_template.ods"
        
        if os.path.exists(template_path):
            success = analyzer.export_to_template(template_path, output_path)
            if success:
                print(f"✅ ODS export successful: {output_path}")
                print("📋 Open the file to verify:")
                print("   - RGB values should be in R-G-B order")
                print("   - CMY values should be in C-M-Y order")
                print("   - Each sample should show distinct values")
                return True
            else:
                print("❌ ODS export failed")
                return False
        else:
            print(f"⚠️  Template not found at: {template_path}")
            print("   Please check the template location")
            return False
    
    finally:
        # Cleanup
        try:
            os.unlink(test_image_path)
        except:
            pass

if __name__ == "__main__":
    success = test_with_updated_templates()
    
    if success:
        print("\n🎉 SUCCESS! RGB-CMY analysis is working with updated templates!")
        print("🔧 The channel mapping fix is complete")
        print("📊 Each sample should now show unique, correct RGB and CMY values")
    else:
        print("\n💥 Test failed - check the issues above")
    
    sys.exit(0 if success else 1)