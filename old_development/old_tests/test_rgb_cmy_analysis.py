#!/usr/bin/env python3
"""
Test script for RGB-CMY Channel Mask Analysis

Demonstrates the RGB-CMY analyzer functionality with sample data.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.rgb_cmy_analyzer import RGBCMYAnalyzer, create_sample_masks
from PIL import Image, ImageDraw
import numpy as np


def create_test_image(width=800, height=600):
    """Create a test image with colored regions for analysis."""
    image = Image.new('RGB', (width, height), (128, 128, 128))  # Gray background
    draw = ImageDraw.Draw(image)
    
    # Create colored test regions
    regions = [
        # Red region
        ((100, 100, 120, 120), (255, 100, 100)),
        # Green region  
        ((250, 100, 120, 120), (100, 255, 100)),
        # Blue region
        ((400, 100, 120, 120), (100, 100, 255)),
        # Yellow region
        ((100, 250, 120, 120), (255, 255, 100)),
        # Cyan region
        ((250, 250, 120, 120), (100, 255, 255)),
        # Magenta region
        ((400, 250, 120, 120), (255, 100, 255))
    ]
    
    sample_regions = []
    for (x, y, w, h), color in regions:
        draw.rectangle([x, y, x + w, y + h], fill=color)
        sample_regions.append((x, y, w, h))
    
    return image, sample_regions


def test_rgb_cmy_analysis():
    """Test the RGB-CMY analysis functionality."""
    print("🧪 Testing RGB-CMY Channel Mask Analysis")
    print("=" * 50)
    
    # Create test image
    print("📸 Creating test image with colored regions...")
    test_image, regions = create_test_image()
    
    # Save test image for reference
    test_image_path = "test_image_rgb_cmy.png"
    test_image.save(test_image_path)
    print(f"   Saved test image: {test_image_path}")
    
    # Create analyzer
    analyzer = RGBCMYAnalyzer()
    
    # Set metadata
    analyzer.set_metadata({
        'date_measured': '10/17/2025',
        'plate': 'Test Plate RGB-CMY',
        'die': 'Test Die A1',
        'date_registered': '10/17/2025',
        'described_colour': 'Multi-color test pattern',
        'total_pixels': str(test_image.size[0] * test_image.size[1])
    })
    print("📋 Set analysis metadata")
    
    # Load test image
    analyzer.load_image(test_image_path)
    
    # Create masks for the colored regions
    print("🎭 Creating sample masks...")
    masks = create_sample_masks(test_image, regions)
    print(f"   Created {len(masks)} sample masks")
    
    # Analyze all masks
    print("🔬 Analyzing RGB and CMY channels...")
    results = analyzer.analyze_multiple_masks(masks)
    
    # Display results
    print("\n📊 Analysis Results:")
    print("-" * 80)
    print(f"{'Sample':<12} {'Pixels':<8} {'R':<6} {'G':<6} {'B':<6} {'C':<6} {'Y':<6} {'M':<6}")
    print("-" * 80)
    
    for result in results:
        print(f"{result['sample_name']:<12} "
              f"{result['pixel_count']:<8} "
              f"{result['R_mean']:<6.1f} "
              f"{result['G_mean']:<6.1f} "
              f"{result['B_mean']:<6.1f} "
              f"{result['C_mean']:<6.1f} "
              f"{result['Y_mean']:<6.1f} "
              f"{result['M_mean']:<6.1f}")
    
    # Save masks
    print("\n💾 Saving individual masks...")
    mask_dir = "rgb_cmy_masks"
    saved_masks = analyzer.save_masks(mask_dir, "test_mask")
    print(f"   Saved {len(saved_masks)} mask files to {mask_dir}/")
    
    # Export results
    print("\n📤 Exporting results...")
    template_path = "/Users/stanbrown/Desktop/SG 19 Measures/RGB-CMY Channel analysis.xlsx"
    output_path = "RGB_CMY_Analysis_Results.xlsx"
    
    if os.path.exists(template_path):
        success = analyzer.export_to_template(template_path, output_path)
        if success:
            print(f"   ✅ Results exported to {output_path}")
            csv_path = output_path.replace('.xlsx', '.csv')
            print(f"   📊 CSV version created: {csv_path}")
        else:
            print("   ❌ Export failed")
    else:
        print(f"   ⚠️  Template not found at {template_path}")
        csv_path = "RGB_CMY_Analysis_Results.csv"
        analyzer._export_to_csv(csv_path)
        print(f"   📊 Created CSV output: {csv_path}")
    
    print("\n🎉 RGB-CMY Analysis test completed!")
    print(f"Files created:")
    print(f"  • Test image: {test_image_path}")
    print(f"  • Masks directory: {mask_dir}/")
    if os.path.exists(template_path):
        print(f"  • Analysis results: {output_path}")
    else:
        print(f"  • Analysis results: {csv_path}")
    
    return True


if __name__ == "__main__":
    test_rgb_cmy_analysis()