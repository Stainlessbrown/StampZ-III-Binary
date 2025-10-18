#!/usr/bin/env python3
"""
RGB-CMY Color Analyzer Extension

Extends the existing ColorAnalyzer to support RGB-CMY channel analysis
using the same coordinate marker system as regular color analysis.
"""

import numpy as np
from PIL import Image
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime
import os
import shutil

from .rgb_cmy_analyzer import RGBCMYAnalyzer
from .coordinate_db import CoordinatePoint, SampleAreaType

logger = logging.getLogger(__name__)


class RGBCMYColorAnalyzer:
    """Extends color analysis to support RGB-CMY channel analysis."""
    
    def __init__(self):
        self.rgb_cmy_analyzer = RGBCMYAnalyzer()
    
    def analyze_image_rgb_cmy_from_canvas(self, image_path: str, sample_set_name: str, 
                                         coord_markers: List) -> Optional[Dict]:
        """
        Analyze RGB-CMY channels from canvas coordinate markers.
        
        Args:
            image_path: Path to the source image
            sample_set_name: Name of the sample set
            coord_markers: List of coordinate markers from canvas
            
        Returns:
            Dictionary with analysis results or None if failed
        """
        try:
            logger.info(f"Starting RGB-CMY analysis for {len(coord_markers)} samples")
            
            # Load the source image
            if not self.rgb_cmy_analyzer.load_image(image_path):
                logger.error(f"Failed to load image: {image_path}")
                return None
            
            # Set metadata
            self.rgb_cmy_analyzer.set_metadata({
                'date_measured': datetime.now().strftime('%m/%d/%Y'),
                'plate': sample_set_name,
                'die': os.path.splitext(os.path.basename(image_path))[0],
                'date_registered': datetime.now().strftime('%m/%d/%Y'),
                'described_colour': f'RGB-CMY analysis of {sample_set_name}',
                'total_pixels': str(self.rgb_cmy_analyzer.source_image.size[0] * self.rgb_cmy_analyzer.source_image.size[1])
            })
            
            # Convert coordinate markers to masks
            masks = self._create_masks_from_markers(coord_markers)
            
            if not masks:
                logger.warning("No valid masks created from coordinate markers")
                return None
            
            # Run analysis
            results = self.rgb_cmy_analyzer.analyze_multiple_masks(masks)
            
            if not results:
                logger.warning("RGB-CMY analysis returned no results")
                return None
            
            # Package results for return
            analysis_results = {
                'sample_set_name': sample_set_name,
                'image_path': image_path,
                'num_samples': len(results),
                'results': results,
                'analyzer': self.rgb_cmy_analyzer  # Include analyzer for export functions
            }
            
            logger.info(f"RGB-CMY analysis completed successfully for {len(results)} samples")
            return analysis_results
            
        except Exception as e:
            logger.error(f"Error in RGB-CMY analysis: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _create_masks_from_markers(self, coord_markers: List) -> Dict[str, Image.Image]:
        """
        Create PIL Image masks from canvas coordinate markers.
        
        Args:
            coord_markers: List of coordinate markers from canvas
            
        Returns:
            Dictionary of {sample_name: mask_image}
        """
        masks = {}
        
        try:
            image_size = self.rgb_cmy_analyzer.source_image.size
            
            for i, marker in enumerate(coord_markers):
                try:
                    # Extract marker information using same method as Color Analysis
                    # Color Analysis uses: x, y = marker['image_pos']
                    if isinstance(marker, dict) and 'image_pos' in marker:
                        x, y = marker['image_pos']
                        logger.debug(f"Extracted coordinates from marker {i}: ({x}, {y})")
                    else:
                        # Fallback methods
                        if hasattr(marker, 'x') and hasattr(marker, 'y'):
                            x, y = marker.x, marker.y
                        elif hasattr(marker, 'coordinate'):
                            x, y = marker.coordinate.x, marker.coordinate.y
                        elif isinstance(marker, dict):
                            x = marker.get('x', marker.get('image_x', None))
                            y = marker.get('y', marker.get('image_y', None))
                            if x is None or y is None:
                                logger.error(f"Marker {i} missing coordinates: {marker.keys()}")
                                continue
                        else:
                            logger.error(f"Cannot extract coordinates from marker {i}: {type(marker)}, {marker}")
                            continue
                    
                    # Validate coordinates are not at (0,0) unless intentional
                    if x == 0 and y == 0:
                        logger.warning(f"Marker {i} at (0,0) - may be using fallback coordinates!")
                    
                    # Get sample area properties using same method as Color Analysis
                    width = marker.get('sample_width', 20) if isinstance(marker, dict) else getattr(marker, 'width', 20)
                    height = marker.get('sample_height', 20) if isinstance(marker, dict) else getattr(marker, 'height', 20)
                    shape = marker.get('sample_type', 'rectangle') if isinstance(marker, dict) else getattr(marker, 'shape', 'rectangle')
                    anchor = marker.get('anchor', 'center') if isinstance(marker, dict) else getattr(marker, 'anchor', 'center')
                    
                    # Apply same coordinate transformation as Color Analysis
                    # Convert from Cartesian coordinates (0,0 at bottom-left) to PIL coordinates (0,0 at top-left)
                    pil_y = image_size[1] - y
                    
                    # Debug logging to track coordinate extraction AND transformation
                    logger.info(f"Marker {i+1}: pos=({x:.1f},{y:.1f}), PIL_y={pil_y:.1f}, size={width}x{height}, shape={shape}, anchor={anchor}")
                    
                    # Create mask using transformed coordinates
                    mask = self._create_single_mask(image_size, x, pil_y, width, height, shape, anchor)
                    
                    if mask is not None:
                        sample_name = f"Sample_{i+1:02d}"
                        masks[sample_name] = mask
                        
                        # DEBUG: Sample a few pixels from this mask to verify location
                        mask_array = np.array(mask)
                        white_pixels = np.where(mask_array > 128)
                        if len(white_pixels[0]) > 0:
                            # Sample first few white pixels to see what colors we're getting
                            source_array = np.array(self.rgb_cmy_analyzer.source_image)
                            sample_rgb_values = []
                            for idx in range(min(5, len(white_pixels[0]))):
                                py, px = white_pixels[0][idx], white_pixels[1][idx]
                                pixel_rgb = source_array[py, px]
                                sample_rgb_values.append(tuple(pixel_rgb))
                            
                            logger.info(f"Created mask for {sample_name} at ({x:.1f}, {y:.1f})")
                            logger.info(f"  Mask covers {len(white_pixels[0])} pixels")
                            logger.info(f"  Sample pixel colors: {sample_rgb_values}")
                            
                            # Check if we're getting unexpected colors
                            if sample_rgb_values:
                                # Convert to int to avoid uint8 overflow
                                avg_r = sum(int(rgb[0]) for rgb in sample_rgb_values) / len(sample_rgb_values)
                                avg_g = sum(int(rgb[1]) for rgb in sample_rgb_values) / len(sample_rgb_values)
                                avg_b = sum(int(rgb[2]) for rgb in sample_rgb_values) / len(sample_rgb_values)
                                logger.info(f"  Average RGB from sample: ({avg_r:.1f}, {avg_g:.1f}, {avg_b:.1f})")
                                
                                if avg_r > 200 and avg_g > 200 and avg_b < 100:
                                    logger.warning(f"  WARNING: Getting YELLOW colors from supposedly RED image!")
                                elif avg_r > 150 and avg_g < 100 and avg_b < 100:
                                    logger.info(f"  Getting RED colors as expected")
                        else:
                            logger.warning(f"  Mask for {sample_name} contains no white pixels!")
                    
                except Exception as e:
                    logger.warning(f"Failed to create mask from marker {i}: {e}")
                    continue
            
            logger.info(f"Created {len(masks)} masks from {len(coord_markers)} markers")
            return masks
            
        except Exception as e:
            logger.error(f"Error creating masks from markers: {e}")
            return {}
    
    def _create_single_mask(self, image_size: Tuple[int, int], x: float, y: float, 
                           width: float, height: float, shape: str, anchor: str) -> Optional[Image.Image]:
        """
        Create a single mask image from marker parameters.
        
        Args:
            image_size: (width, height) of the source image
            x, y: Center coordinates of the marker
            width, height: Dimensions of the sample area
            shape: 'rectangle' or 'circle'
            anchor: Position anchor ('center', 'top_left', etc.)
            
        Returns:
            PIL Image mask or None if failed
        """
        try:
            from PIL import ImageDraw
            
            # Create blank mask (black background)
            mask = Image.new('L', image_size, 0)
            draw = ImageDraw.Draw(mask)
            
            if shape.lower() == 'circle':
                # For circles, use width as diameter
                radius = width / 2
                left = x - radius
                top = y - radius
                right = x + radius
                bottom = y + radius
                
                # Draw white circle on black background
                draw.ellipse([left, top, right, bottom], fill=255)
                
            else:  # Rectangle
                # Calculate rectangle bounds based on anchor position
                if anchor == 'center':
                    left = x - width / 2
                    top = y - height / 2
                    right = x + width / 2
                    bottom = y + height / 2
                elif anchor == 'top_left':
                    left = x
                    top = y
                    right = x + width
                    bottom = y + height
                elif anchor == 'top_right':
                    left = x - width
                    top = y
                    right = x
                    bottom = y + height
                elif anchor == 'bottom_left':
                    left = x
                    top = y - height
                    right = x + width
                    bottom = y
                elif anchor == 'bottom_right':
                    left = x - width
                    top = y - height
                    right = x
                    bottom = y
                else:
                    # Default to center
                    left = x - width / 2
                    top = y - height / 2
                    right = x + width / 2
                    bottom = y + height / 2
                
                # Ensure bounds are within image
                left = max(0, min(left, image_size[0] - 1))
                top = max(0, min(top, image_size[1] - 1))
                right = max(1, min(right, image_size[0]))
                bottom = max(1, min(bottom, image_size[1]))
                
                # Draw white rectangle on black background
                draw.rectangle([left, top, right, bottom], fill=255)
            
            return mask
            
        except Exception as e:
            logger.error(f"Error creating single mask: {e}")
            return None
    
    def export_rgb_cmy_results(self, analysis_results: Dict, template_path: str, output_path: str) -> bool:
        """
        Export RGB-CMY analysis results to template.
        
        Args:
            analysis_results: Results from analyze_image_rgb_cmy_from_canvas
            template_path: Path to RGB-CMY template
            output_path: Output file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            analyzer = analysis_results.get('analyzer')
            if not analyzer:
                logger.error("No analyzer found in analysis results")
                return False
            
            return analyzer.export_to_template(template_path, output_path)
            
        except Exception as e:
            logger.error(f"Error exporting RGB-CMY results: {e}")
            return False


def create_rgb_cmy_analysis_option():
    """
    Create a simple analysis option that can be integrated into the existing
    Color Analysis workflow.
    """
    return {
        'name': 'RGB-CMY Channel Analysis',
        'description': 'Analyze RGB and CMY channel values with statistics',
        'analyzer_class': RGBCMYColorAnalyzer,
        'template_paths': {
            'xlsx': "/Users/stanbrown/Desktop/SG 19 Measures/RGB-CMY Channel analysis.xlsx",
            'ods': "/Users/stanbrown/Desktop/SG 19 Measures/RGB-CMY Channel analysis.ods"
        },
        'export_formats': ['xlsx', 'ods', 'csv']
    }