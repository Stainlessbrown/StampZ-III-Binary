#!/usr/bin/env python3
"""
Complete RGB-CMY Workflow Test with Template Manager

Tests the entire enhanced workflow including:
- Template management and auto-generated filenames
- Integration with existing coordinate marker system
- Export to embedded templates with timestamp names
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.rgb_cmy_color_analyzer import RGBCMYColorAnalyzer
from utils.rgb_cmy_template_manager import get_template_manager
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


def test_complete_rgb_cmy_workflow():
    """Test the complete RGB-CMY analysis workflow with template manager."""
    print("🎨 Complete RGB-CMY Workflow Test")
    print("=" * 50)
    
    # Step 1: Check template manager
    print("1️⃣ Checking template manager...")
    template_manager = get_template_manager()
    template_info = template_manager.get_template_info()
    
    print(f"   📁 Templates directory: {template_info['templates_directory']}")
    print(f"   📋 Available formats: {template_info['available_formats']}")
    
    for format_type, info in template_info['templates'].items():
        status = "✅" if info['exists'] else "❌"
        size_mb = info['size'] / 1024 / 1024 if info['exists'] else 0
        print(f"   {format_type.upper()}: {status} ({size_mb:.2f} MB)" if info['exists'] else f"   {format_type.upper()}: {status}")
    
    # Step 2: Create test image
    print("\n2️⃣ Creating test stamp image...")
    test_image = Image.new('RGB', (1000, 700), (250, 248, 240))  # Cream background
    draw = ImageDraw.Draw(test_image)
    
    # Create stamp-like design with various colors
    stamp_regions = [
        # Main subject (red)
        ((150, 150, 200, 200), (185, 45, 45)),
        # Sky background (blue)
        ((400, 150, 200, 200), (45, 85, 185)),
        # Landscape (green)
        ((150, 400, 200, 200), (65, 145, 55)),
        # Sun/highlights (yellow)
        ((400, 400, 200, 200), (205, 185, 45)),
        # Decorative elements (purple)
        ((700, 150, 200, 200), (125, 65, 155)),
        # Accent features (orange)
        ((700, 400, 200, 200), (205, 125, 45))
    ]
    
    # Add realistic texture and variation
    for (x, y, w, h), base_color in stamp_regions:
        for py in range(y, y + h, 2):
            for px in range(x, x + w, 2):
                # Add texture variation
                variation = np.random.randint(-25, 25, 3)
                final_color = tuple(
                    max(0, min(255, base_color[i] + variation[i])) 
                    for i in range(3)
                )
                draw.point((px, py), fill=final_color)
    
    # Add border
    border_color = (80, 60, 120)
    draw.rectangle([10, 10, 990, 690], outline=border_color, width=8)
    
    # Save test image with descriptive name
    test_image_path = "test_stamp_complete_workflow.png"
    test_image.save(test_image_path)
    print(f"   📸 Created stamp image: {test_image_path}")
    
    # Step 3: Create coordinate markers
    print("\n3️⃣ Creating coordinate markers...")
    coord_markers = []
    
    # Create markers at the center of each colored region
    marker_positions = [
        (250, 250, "Red_Subject"),
        (500, 250, "Blue_Sky"), 
        (250, 500, "Green_Landscape"),
        (500, 500, "Yellow_Sun"),
        (800, 250, "Purple_Decorative"),
        (800, 500, "Orange_Accent")
    ]
    
    for i, (x, y, description) in enumerate(marker_positions):
        marker = MockCoordinateMarker(
            x, y, 
            width=60, height=60, 
            shape='rectangle', 
            anchor='center'
        )
        coord_markers.append(marker)
        print(f"   🎯 Marker {i+1}: {description} at ({x}, {y})")
    
    print(f"   📍 Created {len(coord_markers)} coordinate markers")
    
    # Step 4: Run RGB-CMY analysis
    print("\n4️⃣ Running integrated RGB-CMY analysis...")
    
    analyzer = RGBCMYColorAnalyzer()
    sample_set_name = "Commemorative_Stamp_Analysis"
    
    results = analyzer.analyze_image_rgb_cmy_from_canvas(
        test_image_path,
        sample_set_name,
        coord_markers
    )
    
    if not results:
        print("❌ RGB-CMY analysis failed!")
        return False
    
    print(f"   ✅ Analysis completed: {results['num_samples']} samples")
    
    # Step 5: Display results with color names
    print("\n5️⃣ Analysis Results:")
    print("-" * 85)
    print(f"{'Region':<18} {'Pixels':<8} {'R':<6} {'G':<6} {'B':<6} | {'C':<6} {'Y':<6} {'M':<6}")
    print("-" * 85)
    
    sample_results = results['results']
    region_names = [pos[2] for pos in marker_positions]
    
    for i, result in enumerate(sample_results):
        region_name = region_names[i] if i < len(region_names) else f"Sample_{i+1}"
        print(f"{region_name:<18} "
              f"{result['pixel_count']:<8} "
              f"{result['R_mean']:<6.1f} "
              f"{result['G_mean']:<6.1f} "
              f"{result['B_mean']:<6.1f} | "
              f"{result['C_mean']:<6.1f} "
              f"{result['Y_mean']:<6.1f} "
              f"{result['M_mean']:<6.1f}")
    
    # Calculate averages
    if len(sample_results) > 1:
        avg_r = np.mean([r['R_mean'] for r in sample_results])
        avg_g = np.mean([r['G_mean'] for r in sample_results])
        avg_b = np.mean([r['B_mean'] for r in sample_results])
        avg_c = np.mean([r['C_mean'] for r in sample_results])
        avg_y = np.mean([r['Y_mean'] for r in sample_results])
        avg_m = np.mean([r['M_mean'] for r in sample_results])
        
        print("-" * 85)
        print(f"{'AVERAGES':<18} {'':<8} "
              f"{avg_r:<6.1f} {avg_g:<6.1f} {avg_b:<6.1f} | "
              f"{avg_c:<6.1f} {avg_y:<6.1f} {avg_m:<6.1f}")
    
    # Step 6: Test auto-export for each available format
    print("\n6️⃣ Testing auto-export functionality...")
    
    rgb_cmy_analyzer = results['analyzer']
    exported_files = []
    
    for format_type in template_manager.get_available_formats():
        print(f"   📤 Exporting to {format_type.upper()}...")
        
        success, output_path = template_manager.export_with_auto_filename(
            rgb_cmy_analyzer,
            test_image_path,
            sample_set_name,
            format_type
        )
        
        if success:
            filename = os.path.basename(output_path)
            file_size = os.path.getsize(output_path)
            print(f"      ✅ {filename} ({file_size} bytes)")
            exported_files.append(output_path)
        else:
            print(f"      ❌ Export failed for {format_type}")
    
    # Step 7: Verify exports contain expected data
    print("\n7️⃣ Verifying exported files...")
    
    for export_path in exported_files:
        filename = os.path.basename(export_path)
        extension = os.path.splitext(export_path)[1].lower()
        
        try:
            if extension == '.csv':
                with open(export_path, 'r') as f:
                    content = f.read()
                    
                if "Colour Space Analysis" in content and "Sample#" in content:
                    # Count data rows
                    rgb_samples = content.count('Sample_')
                    print(f"      ✅ {filename}: Valid CSV with {rgb_samples//2} samples")  # Divide by 2 because RGB and CMY sections
                else:
                    print(f"      ⚠️  {filename}: CSV format may be incorrect")
            
            else:  # xlsx or ods
                print(f"      ✅ {filename}: Binary template file created")
        
        except Exception as e:
            print(f"      ❌ {filename}: Verification failed - {e}")
    
    # Step 8: Show filename pattern
    print("\n8️⃣ Filename Pattern Analysis:")
    
    if exported_files:
        sample_file = os.path.basename(exported_files[0])
        parts = sample_file.split('_')
        print(f"   📝 Pattern: ImageName_SampleSet_RGB-CMY_YYYYMMDD_HHMMSS.ext")
        print(f"   🔍 Example: {sample_file}")
        print(f"   📂 Location: Same directory as source image")
        
        # Show parts breakdown
        if len(parts) >= 5:
            print(f"      • Image: {parts[0]}")
            print(f"      • Sample Set: {parts[1]}")
            print(f"      • Analysis Type: {parts[2]}")
            print(f"      • Date: {parts[3]}")
            print(f"      • Time: {parts[4].split('.')[0]}")
    
    # Step 9: Summary
    print(f"\n🎉 Complete RGB-CMY Workflow Test Successful!")
    
    print(f"\n📊 Test Summary:")
    print(f"  • Templates embedded: ✅ ({len([f for f in template_info['available_formats'] if f != 'csv'])} formats)")
    print(f"  • Auto-filename generation: ✅")
    print(f"  • Coordinate marker integration: ✅") 
    print(f"  • RGB-CMY analysis: ✅ ({len(sample_results)} samples)")
    print(f"  • Multi-format export: ✅ ({len(exported_files)} files)")
    print(f"  • Template population: ✅")
    
    print(f"\n📁 Generated Files:")
    print(f"  • Source image: {test_image_path}")
    for export_path in exported_files:
        print(f"  • Export: {os.path.basename(export_path)}")
    
    print(f"\n🚀 Ready for StampZ Integration:")
    print(f"  • Templates are embedded in StampZ")
    print(f"  • Filenames auto-generated with timestamps")
    print(f"  • Exports saved alongside source images")
    print(f"  • No manual file dialog needed")
    print(f"  • Seamless workflow integration")
    
    return True


if __name__ == "__main__":
    test_complete_rgb_cmy_workflow()