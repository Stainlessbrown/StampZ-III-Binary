#!/usr/bin/env python3
"""
Complete RGB-CMY Channel Analysis Test

Demonstrates the complete workflow including:
- Image loading
- Interactive mask generation (rectangles and circles)
- RGB-CMY channel analysis
- Results export to template format
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.rgb_cmy_analyzer import RGBCMYAnalyzer
from PIL import Image, ImageDraw
import numpy as np


def create_test_stamp_image(width=1200, height=800):
    """Create a realistic stamp image with multiple colored regions."""
    image = Image.new('RGB', (width, height), (240, 235, 220))  # Off-white background
    draw = ImageDraw.Draw(image)
    
    # Simulate stamp design with various colored elements
    
    # Border (dark blue frame)
    border_width = 20
    draw.rectangle([0, 0, width-1, height-1], outline=(20, 40, 100), width=border_width)
    
    # Central design elements with different colors
    regions = [
        # Red region (stamp subject)
        ((200, 150, 400, 250), (180, 40, 40)),
        # Blue region (sky/background) 
        ((500, 150, 700, 250), (40, 80, 160)),
        # Green region (foliage/landscape)
        ((200, 300, 400, 400), (60, 120, 40)),
        # Yellow region (sun/highlights)
        ((500, 300, 600, 400), (200, 180, 40)),
        # Purple region (decorative element)
        ((750, 150, 950, 250), (120, 60, 140)),
        # Orange region (accent color)
        ((750, 300, 950, 400), (200, 120, 40))
    ]
    
    sample_coordinates = []
    for i, ((x, y, x2, y2), color) in enumerate(regions):
        # Add some texture/noise to make it more realistic
        for py in range(y, y2, 2):
            for px in range(x, x2, 2):
                noise_r = np.random.randint(-20, 20)
                noise_g = np.random.randint(-20, 20) 
                noise_b = np.random.randint(-20, 20)
                
                final_color = (
                    max(0, min(255, color[0] + noise_r)),
                    max(0, min(255, color[1] + noise_g)),
                    max(0, min(255, color[2] + noise_b))
                )
                draw.point((px, py), fill=final_color)
        
        # Store center coordinates for mask generation
        center_x = (x + x2) // 2
        center_y = (y + y2) // 2
        sample_coordinates.append((center_x, center_y, min(x2-x, y2-y)//2))
    
    return image, sample_coordinates


def create_masks_from_coordinates(image, coordinates):
    """Create circular masks centered on the sample coordinates."""
    masks = {}
    
    for i, (cx, cy, radius) in enumerate(coordinates):
        # Create circular mask
        mask = Image.new('L', image.size, 0)  # Black background
        draw = ImageDraw.Draw(mask)
        
        # Adjust radius to ensure good coverage
        mask_radius = max(50, radius - 10)  # At least 50px radius, slightly smaller than region
        
        # Draw white circle on black background
        left = cx - mask_radius
        top = cy - mask_radius
        right = cx + mask_radius
        bottom = cy + mask_radius
        
        draw.ellipse([left, top, right, bottom], fill=255)
        
        # Name masks descriptively
        color_names = ['Red_Subject', 'Blue_Sky', 'Green_Foliage', 'Yellow_Sun', 'Purple_Decorative', 'Orange_Accent']
        mask_name = f"Sample_{i+1:02d}_{color_names[i] if i < len(color_names) else f'Region_{i+1}'}"
        masks[mask_name] = mask
        
        print(f"Created mask '{mask_name}' at ({cx}, {cy}) with radius {mask_radius}")
    
    return masks


def demonstrate_complete_workflow():
    """Demonstrate the complete RGB-CMY analysis workflow."""
    print("🎨 RGB-CMY Complete Analysis Workflow Demonstration")
    print("=" * 60)
    
    # Step 1: Create realistic test image
    print("1️⃣ Creating realistic stamp test image...")
    stamp_image, sample_coords = create_test_stamp_image()
    
    # Save test image
    test_image_path = "test_stamp_rgb_cmy.png"
    stamp_image.save(test_image_path)
    print(f"   📸 Saved test stamp: {test_image_path}")
    print(f"   📏 Image size: {stamp_image.size[0]} x {stamp_image.size[1]} pixels")
    
    # Step 2: Generate masks programmatically
    print("\n2️⃣ Generating analysis masks...")
    masks = create_masks_from_coordinates(stamp_image, sample_coords)
    print(f"   🎭 Created {len(masks)} masks for analysis")
    
    # Step 3: Initialize analyzer
    print("\n3️⃣ Setting up RGB-CMY analyzer...")
    analyzer = RGBCMYAnalyzer()
    
    # Set realistic metadata
    analyzer.set_metadata({
        'date_measured': '10/17/2025',
        'plate': 'Test Stamp Plate A',
        'die': 'Commemorative Die #47',
        'date_registered': '10/17/2025',
        'described_colour': 'Multi-color commemorative stamp design',
        'total_pixels': str(stamp_image.size[0] * stamp_image.size[1])
    })
    print("   📋 Set analysis metadata")
    
    # Load test image
    analyzer.load_image(test_image_path)
    print("   🔍 Loaded source image")
    
    # Step 4: Run analysis
    print("\n4️⃣ Analyzing RGB and CMY channels...")
    results = analyzer.analyze_multiple_masks(masks)
    
    # Step 5: Display detailed results
    print("\n5️⃣ Analysis Results:")
    print("-" * 100)
    print(f"{'Sample':<20} {'Pixels':<8} {'R':<6} {'G':<6} {'B':<6} | {'C':<6} {'Y':<6} {'M':<6}")
    print("-" * 100)
    
    for result in results:
        print(f"{result['sample_name']:<20} "
              f"{result['pixel_count']:<8} "
              f"{result['R_mean']:<6.1f} "
              f"{result['G_mean']:<6.1f} "
              f"{result['B_mean']:<6.1f} | "
              f"{result['C_mean']:<6.1f} "
              f"{result['Y_mean']:<6.1f} "
              f"{result['M_mean']:<6.1f}")
    
    # Calculate and show statistics
    print("-" * 100)
    if len(results) > 1:
        avg_r = np.mean([r['R_mean'] for r in results])
        avg_g = np.mean([r['G_mean'] for r in results])
        avg_b = np.mean([r['B_mean'] for r in results])
        avg_c = np.mean([r['C_mean'] for r in results])
        avg_y = np.mean([r['Y_mean'] for r in results])
        avg_m = np.mean([r['M_mean'] for r in results])
        
        print(f"{'AVERAGES':<20} {'':<8} "
              f"{avg_r:<6.1f} {avg_g:<6.1f} {avg_b:<6.1f} | "
              f"{avg_c:<6.1f} {avg_y:<6.1f} {avg_m:<6.1f}")
        
        # Show standard deviations
        std_r = np.std([r['R_mean'] for r in results], ddof=1)
        std_g = np.std([r['G_mean'] for r in results], ddof=1)
        std_b = np.std([r['B_mean'] for r in results], ddof=1)
        
        print(f"{'STD DEV (RGB)':<20} {'':<8} "
              f"{std_r:<6.2f} {std_g:<6.2f} {std_b:<6.2f}")
    
    # Step 6: Save individual masks
    print("\n6️⃣ Saving analysis masks...")
    mask_dir = "rgb_cmy_analysis_masks"
    saved_masks = analyzer.save_masks(mask_dir, "stamp_mask")
    print(f"   💾 Saved {len(saved_masks)} mask files to {mask_dir}/")
    
    # Step 7: Export results
    print("\n7️⃣ Exporting results to template...")
    template_path = "/Users/stanbrown/Desktop/SG 19 Measures/RGB-CMY Channel analysis.xlsx"
    output_path = "Stamp_RGB_CMY_Analysis.xlsx"
    
    if os.path.exists(template_path):
        success = analyzer.export_to_template(template_path, output_path)
        if success:
            print(f"   ✅ Results exported to {output_path}")
            csv_path = output_path.replace('.xlsx', '.csv')
            print(f"   📊 CSV version: {csv_path}")
        else:
            print("   ❌ Template export failed")
    else:
        print(f"   ⚠️  Template not found, creating CSV output...")
        csv_path = "Stamp_RGB_CMY_Analysis.csv"
        analyzer._export_to_csv(csv_path)
        print(f"   📊 CSV results: {csv_path}")
    
    # Step 8: Summary
    print(f"\n🎉 Complete RGB-CMY Analysis Workflow Finished!")
    print(f"\n📁 Files Created:")
    print(f"  • Source image: {test_image_path}")
    print(f"  • Mask directory: {mask_dir}/ ({len(saved_masks)} files)")
    if os.path.exists(template_path):
        print(f"  • Analysis results: {output_path}")
    else:
        print(f"  • Analysis results: {csv_path}")
    
    print(f"\n📈 Analysis Summary:")
    print(f"  • Analyzed {len(results)} sample regions")
    print(f"  • Total pixels analyzed: {sum(r['pixel_count'] for r in results):,}")
    print(f"  • Average RGB values: R={avg_r:.1f}, G={avg_g:.1f}, B={avg_b:.1f}")
    print(f"  • Average CMY values: C={avg_c:.1f}, Y={avg_y:.1f}, M={avg_m:.1f}")
    
    return True


if __name__ == "__main__":
    demonstrate_complete_workflow()