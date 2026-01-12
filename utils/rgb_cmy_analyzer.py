#!/usr/bin/env python3
"""
RGB-CMY Channel Mask Analysis Module - CORRECTED VERSION

Analyzes masked regions of images for RGB and CMY channel values,
calculates statistics, and populates analysis templates.

FIXED: Now uses standard RGB order (Red, Green, Blue) instead of BGR
FIXED: Uses standard CMY order (Cyan, Magenta, Yellow)

Compatible with existing StampZ mask generation and color analysis workflows.
"""

import numpy as np
from PIL import Image, ImageDraw
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union
import os
import logging
from datetime import datetime
import shutil

logger = logging.getLogger(__name__)

# Color space conversion
try:
    from colorspacious import cspace_convert
    HAS_COLORSPACIOUS = True
except ImportError:
    HAS_COLORSPACIOUS = False
    logger.warning("colorspacious not installed. L*a*b* conversion will use approximation.")


class RGBCMYAnalyzer:
    """Analyzes RGB and CMY channel values from masked image regions."""
    
    def __init__(self):
        self.results = []
        self.masks = {}
        self.source_image = None
        self.analysis_data = {
            'metadata': {},
            'rgb_data': [],
            'cmy_data': [],
            'statistics': {}
        }
    
    def rgb_to_lab(self, rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Convert RGB to CIE L*a*b* color space.
        
        Args:
            rgb: RGB values as (r, g, b) floats 0-255
            
        Returns:
            L*a*b* values as (L, a, b) floats
        """
        if HAS_COLORSPACIOUS:
            # Use precise conversion via colorspacious
            rgb_float = [c/255.0 for c in rgb]
            lab = cspace_convert(rgb_float, "sRGB1", "CIELab")
            return tuple(lab)
        else:
            # Use approximation if colorspacious not available
            return self._rgb_to_lab_approximation(rgb)
    
    def _rgb_to_lab_approximation(self, rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Approximate RGB to L*a*b* conversion.
        
        This is a simplified conversion that's reasonably accurate for most colors.
        For precise color analysis, install colorspacious: pip install colorspacious
        """
        r, g, b = [c/255.0 for c in rgb]
        
        # Convert to linear RGB
        def gamma_correct(c):
            return c/12.92 if c <= 0.04045 else ((c + 0.055)/1.055) ** 2.4
        
        r_lin = gamma_correct(r)
        g_lin = gamma_correct(g)
        b_lin = gamma_correct(b)
        
        # Convert to XYZ (using sRGB matrix)
        x = 0.4124564 * r_lin + 0.3575761 * g_lin + 0.1804375 * b_lin
        y = 0.2126729 * r_lin + 0.7151522 * g_lin + 0.0721750 * b_lin
        z = 0.0193339 * r_lin + 0.1191920 * g_lin + 0.9503041 * b_lin
        
        # Normalize by D65 white point
        xn, yn, zn = 0.95047, 1.0, 1.08883
        x, y, z = x/xn, y/yn, z/zn
        
        # Convert to Lab
        def f(t):
            return t**(1/3) if t > 0.008856 else (7.787 * t + 16/116)
        
        fx, fy, fz = f(x), f(y), f(z)
        
        L = 116 * fy - 16
        a = 500 * (fx - fy)
        b = 200 * (fy - fz)
        
        return (L, a, b)
    
    def load_image(self, image_path: str) -> bool:
        """Load the source image for analysis."""
        try:
            self.source_image = Image.open(image_path).convert('RGB')
            logger.info(f"Loaded image: {image_path} ({self.source_image.size})")
            return True
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return False
    
    def set_metadata(self, metadata: Dict[str, str]):
        """Set analysis metadata (date, plate, die, etc.)."""
        self.analysis_data['metadata'] = metadata
        logger.info(f"Set metadata: {metadata}")
    
    def analyze_masked_region(self, mask: Image.Image, sample_name: str, mode: str = 'rgb') -> Dict[str, float]:
        """
        Analyze RGB or CMY values for a masked region.
        
        Args:
            mask: Binary mask image (white = analyze, black = ignore)
            sample_name: Name/identifier for this sample
            mode: 'rgb' or 'cmy' - which channels to analyze
            
        Returns:
            Dictionary with RGB or CMY statistics
        """
        if self.source_image is None:
            raise ValueError("No source image loaded. Call load_image() first.")
        
        try:
            # Ensure mask is same size as source image
            if mask.size != self.source_image.size:
                mask = mask.resize(self.source_image.size, Image.LANCZOS)
            
            # Convert mask to grayscale and then to array
            mask_array = np.array(mask.convert('L'))
            
            # Convert source image to array
            image_array = np.array(self.source_image)
            
            # Apply mask - only analyze pixels where mask is white (> 128)
            mask_pixels = mask_array > 128
            
            if not np.any(mask_pixels):
                logger.warning(f"No pixels found in mask for sample {sample_name}")
                return self._create_empty_result(sample_name)
            
            # Extract RGB values for masked pixels
            masked_rgb = image_array[mask_pixels]  # Shape: (n_pixels, 3)
            
            # Compile results based on mode
            result = {
                'sample_name': sample_name,
                'pixel_count': int(np.sum(mask_pixels)),
                'mode': mode
            }
            
            # Calculate RGB statistics if requested
            if mode == 'rgb':
                rgb_means = np.mean(masked_rgb, axis=0)
                rgb_stds = np.std(masked_rgb, axis=0, ddof=1)  # Sample standard deviation
                
                # RGB data - standard RGB order (Red, Green, Blue)
                result.update({
                    'R_mean': float(rgb_means[0]),  # Red = index 0
                    'R_std': float(rgb_stds[0]),
                    'G_mean': float(rgb_means[1]),  # Green = index 1
                    'G_std': float(rgb_stds[1]),
                    'B_mean': float(rgb_means[2]),  # Blue = index 2
                    'B_std': float(rgb_stds[2]),
                })
                
                # Convert RGB mean to L*a*b* for better visualization
                lab = self.rgb_to_lab((rgb_means[0], rgb_means[1], rgb_means[2]))
                result.update({
                    'L_mean': float(lab[0]),
                    'a_mean': float(lab[1]),
                    'b_mean': float(lab[2])
                })
            
            # Calculate CMY statistics if requested
            if mode == 'cmy':
                # Convert RGB to CMY (CMY = 255 - RGB, simple subtractive color model)
                cmy_values = 255 - masked_rgb
                cmy_means = np.mean(cmy_values, axis=0)
                cmy_stds = np.std(cmy_values, axis=0, ddof=1)
                
                # CMY data - standard CMY order (Cyan, Magenta, Yellow)
                result.update({
                    'C_mean': float(cmy_means[0]),  # Cyan = 255 - Red
                    'C_std': float(cmy_stds[0]),
                    'M_mean': float(cmy_means[1]),  # Magenta = 255 - Green
                    'M_std': float(cmy_stds[1]),
                    'Y_mean': float(cmy_means[2]),  # Yellow = 255 - Blue
                    'Y_std': float(cmy_stds[2])
                })
            
            logger.info(f"Analyzed sample {sample_name}: {result['pixel_count']} pixels")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing masked region for {sample_name}: {e}")
            return self._create_empty_result(sample_name, mode=mode)
    
    def _create_empty_result(self, sample_name: str, mode: str = 'rgb') -> Dict[str, float]:
        """Create empty result structure for failed analysis."""
        result = {
            'sample_name': sample_name,
            'pixel_count': 0,
            'mode': mode
        }
        
        if mode == 'rgb':
            result.update({
                'R_mean': 0.0, 'R_std': 0.0,
                'G_mean': 0.0, 'G_std': 0.0,
                'B_mean': 0.0, 'B_std': 0.0,
                'L_mean': 0.0, 'a_mean': 0.0, 'b_mean': 0.0
            })
        else:  # cmy
            result.update({
                'C_mean': 0.0, 'C_std': 0.0,
                'M_mean': 0.0, 'M_std': 0.0,
                'Y_mean': 0.0, 'Y_std': 0.0
            })
        
        return result
    
    def analyze_multiple_masks(self, masks: Dict[str, Image.Image], mode: str = 'rgb') -> List[Dict[str, float]]:
        """
        Analyze multiple masked regions in batch.
        
        Args:
            masks: Dictionary of {sample_name: mask_image}
            mode: 'rgb' or 'cmy' - which channels to analyze
            
        Returns:
            List of analysis results for each sample
        """
        results = []
        
        for sample_name, mask in masks.items():
            result = self.analyze_masked_region(mask, sample_name, mode=mode)
            results.append(result)
            
            # Store mask for potential saving
            self.masks[sample_name] = mask
        
        self.results = results
        logger.info(f"Analyzed {len(results)} samples")
        return results
    
    def save_masks(self, output_directory: str, prefix: str = "mask") -> List[str]:
        """
        Save individual masks as image files.
        
        Args:
            output_directory: Directory to save masks
            prefix: Filename prefix for mask files
            
        Returns:
            List of saved file paths
        """
        saved_files = []
        
        try:
            os.makedirs(output_directory, exist_ok=True)
            
            for sample_name, mask in self.masks.items():
                # Create safe filename
                safe_name = "".join(c for c in sample_name if c.isalnum() or c in ('-', '_'))
                filename = f"{prefix}_{safe_name}.png"
                filepath = os.path.join(output_directory, filename)
                
                # Save mask
                mask.save(filepath)
                saved_files.append(filepath)
                logger.info(f"Saved mask: {filepath}")
                
        except Exception as e:
            logger.error(f"Error saving masks: {e}")
        
        return saved_files
    
    def export_lab_csv(self, output_path: str) -> bool:
        """Export RGB data as L*a*b* values to CSV for plotting.
        
        Args:
            output_path: Path for the output CSV file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.results:
                logger.error("No analysis results available. Run analysis first.")
                return False
            
            # Check if results contain RGB data
            if not any('L_mean' in r for r in self.results):
                logger.error("No L*a*b* data available. Run RGB analysis first.")
                return False
            
            # Create CSV data
            csv_data = []
            csv_data.append(['Sample', 'Pixels', 'L*', 'a*', 'b*', 'R', 'G', 'B'])
            
            for result in self.results:
                if 'L_mean' in result:
                    csv_data.append([
                        result['sample_name'],
                        result['pixel_count'],
                        f"{result['L_mean']:.2f}",
                        f"{result['a_mean']:.2f}",
                        f"{result['b_mean']:.2f}",
                        f"{result.get('R_mean', 0):.1f}",
                        f"{result.get('G_mean', 0):.1f}",
                        f"{result.get('B_mean', 0):.1f}"
                    ])
            
            # Write to CSV
            df = pd.DataFrame(csv_data[1:], columns=csv_data[0])
            df.to_csv(output_path, index=False)
            logger.info(f"Exported L*a*b* data to CSV: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting L*a*b* CSV: {e}")
            return False
    
    def save_channel_masks(self, output_directory: str, prefix: str = "channel") -> Dict[str, List[str]]:
        """
        Save RGB and CMY channel masks as grayscale images.
        
        Args:
            output_directory: Directory to save channel masks
            prefix: Filename prefix for channel mask files
            
        Returns:
            Dictionary with lists of saved file paths for each channel type
        """
        if self.source_image is None:
            logger.error("No source image loaded. Cannot create channel masks.")
            return {}
        
        saved_files = {
            'rgb': [],
            'cmy': []
        }
        
        try:
            os.makedirs(output_directory, exist_ok=True)
            
            # Convert source image to array for channel extraction
            image_array = np.array(self.source_image)
            
            # Extract RGB channels
            r_channel = image_array[:, :, 0]  # Red channel
            g_channel = image_array[:, :, 1]  # Green channel 
            b_channel = image_array[:, :, 2]  # Blue channel
            
            # Calculate CMY channels (255 - RGB)
            c_channel = 255 - r_channel  # Cyan = 255 - Red
            m_channel = 255 - g_channel  # Magenta = 255 - Green
            y_channel = 255 - b_channel  # Yellow = 255 - Blue
            
            # Save RGB channel masks
            rgb_channels = [('R', r_channel), ('G', g_channel), ('B', b_channel)]
            for channel_name, channel_data in rgb_channels:
                channel_image = Image.fromarray(channel_data.astype(np.uint8), mode='L')
                filename = f"{prefix}_RGB_{channel_name}.png"
                filepath = os.path.join(output_directory, filename)
                channel_image.save(filepath)
                saved_files['rgb'].append(filepath)
                logger.info(f"Saved RGB {channel_name} channel: {filepath}")
            
            # Save CMY channel masks
            cmy_channels = [('C', c_channel), ('M', m_channel), ('Y', y_channel)]
            for channel_name, channel_data in cmy_channels:
                channel_image = Image.fromarray(channel_data.astype(np.uint8), mode='L')
                filename = f"{prefix}_CMY_{channel_name}.png"
                filepath = os.path.join(output_directory, filename)
                channel_image.save(filepath)
                saved_files['cmy'].append(filepath)
                logger.info(f"Saved CMY {channel_name} channel: {filepath}")
            
            # Optionally save composite RGB and CMY visualizations
            self._save_composite_channel_masks(output_directory, prefix, image_array, saved_files)
            
        except Exception as e:
            logger.error(f"Error saving channel masks: {e}")
        
        return saved_files
    
    def _save_composite_channel_masks(self, output_directory: str, prefix: str, 
                                     image_array: np.ndarray, saved_files: Dict[str, List[str]]):
        """
        Save composite visualizations of RGB and CMY channels.
        
        Args:
            output_directory: Directory to save files
            prefix: Filename prefix
            image_array: Source image array
            saved_files: Dictionary to append new file paths to
        """
        try:
            # Create RGB composite (original image)
            rgb_composite = Image.fromarray(image_array.astype(np.uint8), mode='RGB')
            rgb_filename = f"{prefix}_RGB_composite.png"
            rgb_filepath = os.path.join(output_directory, rgb_filename)
            rgb_composite.save(rgb_filepath)
            saved_files['rgb'].append(rgb_filepath)
            logger.info(f"Saved RGB composite: {rgb_filepath}")
            
            # Create CMY composite visualization
            # CMY channels as RGB for visualization
            cmy_array = 255 - image_array  # Convert RGB to CMY
            cmy_composite = Image.fromarray(cmy_array.astype(np.uint8), mode='RGB')
            cmy_filename = f"{prefix}_CMY_composite.png"
            cmy_filepath = os.path.join(output_directory, cmy_filename)
            cmy_composite.save(cmy_filepath)
            saved_files['cmy'].append(cmy_filepath)
            logger.info(f"Saved CMY composite: {cmy_filepath}")
            
        except Exception as e:
            logger.error(f"Error saving composite channel masks: {e}")
    
    def export_to_template(self, template_path: str, output_path: str, mode: str = 'rgb') -> bool:
        """
        Export analysis results to channel analysis template.
        
        Args:
            template_path: Path to the channel analysis template file
            output_path: Path for the populated output file
            mode: 'rgb' or 'cmy' - which channels to export
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.results:
                logger.error("No analysis results available. Run analysis first.")
                return False
            
            # Determine file extension
            file_ext = os.path.splitext(output_path)[1].lower()
            
            if file_ext == '.xlsx':
                return self._export_to_xlsx(template_path, output_path, mode=mode)
            else:
                # Fallback to CSV
                self._export_to_csv(output_path, mode=mode)
                return True
            
        except Exception as e:
            logger.error(f"Error exporting to template: {e}")
            return False
    
    def _export_to_xlsx(self, template_path: str, output_path: str, mode: str = 'rgb') -> bool:
        """Export to Excel format using openpyxl."""
        try:
            import openpyxl
            from utils.user_preferences import get_preferences_manager
            
            # Check user normalization preference
            try:
                prefs = get_preferences_manager()
                use_normalized = prefs.get_export_normalized_values()
            except:
                use_normalized = False  # Default to raw values if preferences unavailable
            
            # Load template
            workbook = openpyxl.load_workbook(template_path)
            sheet = workbook.active
            
            # Skip metadata population - rows 1-14 are for user input
            # Only populate analysis data in rows 15+ to preserve user's manual entries
            
            # All templates now use rows 16-21 for data
            # RGB template: RGB data in rows 16-21
            # CMY template: CMY data in rows 16-21
            
            if mode == 'rgb':
                # RGB-only template: RGB data in rows 16-21
                for i in range(min(6, len(self.results))):
                    result = self.results[i]
                    row = 16 + i
                    
                    if use_normalized:
                        # Normalize RGB values: 0-255 → 0-1 for Plot_3D compatibility
                        sheet[f'B{row}'] = result.get('R_mean', 0) / 255.0 if result.get('R_mean', '') != '' else ''
                        sheet[f'C{row}'] = result.get('R_std', 0) / 255.0 if result.get('R_std', '') != '' else ''
                        sheet[f'E{row}'] = result.get('G_mean', 0) / 255.0 if result.get('G_mean', '') != '' else ''
                        sheet[f'F{row}'] = result.get('G_std', 0) / 255.0 if result.get('G_std', '') != '' else ''
                        sheet[f'H{row}'] = result.get('B_mean', 0) / 255.0 if result.get('B_mean', '') != '' else ''
                        sheet[f'I{row}'] = result.get('B_std', 0) / 255.0 if result.get('B_std', '') != '' else ''
                    else:
                        # Export raw 0-255 values
                        sheet[f'B{row}'] = result.get('R_mean', '')
                        sheet[f'C{row}'] = result.get('R_std', '')
                        sheet[f'E{row}'] = result.get('G_mean', '')
                        sheet[f'F{row}'] = result.get('G_std', '')
                        sheet[f'H{row}'] = result.get('B_mean', '')
                        sheet[f'I{row}'] = result.get('B_std', '')
            
            else:  # cmy
                # CMY-only template: CMY data in rows 16-21
                for i in range(min(6, len(self.results))):
                    result = self.results[i]
                    row = 16 + i
                    
                    if use_normalized:
                        # Normalize CMY values: 0-255 → 0-1 for Plot_3D compatibility
                        sheet[f'B{row}'] = result.get('C_mean', 0) / 255.0 if result.get('C_mean', '') != '' else ''
                        sheet[f'C{row}'] = result.get('C_std', 0) / 255.0 if result.get('C_std', '') != '' else ''
                        sheet[f'E{row}'] = result.get('M_mean', 0) / 255.0 if result.get('M_mean', '') != '' else ''
                        sheet[f'F{row}'] = result.get('M_std', 0) / 255.0 if result.get('M_std', '') != '' else ''
                        sheet[f'H{row}'] = result.get('Y_mean', 0) / 255.0 if result.get('Y_mean', '') != '' else ''
                        sheet[f'I{row}'] = result.get('Y_std', 0) / 255.0 if result.get('Y_std', '') != '' else ''
                    else:
                        # Export raw 0-255 values
                        sheet[f'B{row}'] = result.get('C_mean', '')
                        sheet[f'C{row}'] = result.get('C_std', '')
                        sheet[f'E{row}'] = result.get('M_mean', '')
                        sheet[f'F{row}'] = result.get('M_std', '')
                        sheet[f'H{row}'] = result.get('Y_mean', '')
                        sheet[f'I{row}'] = result.get('Y_std', '')
            
            # Save populated workbook
            workbook.save(output_path)
            logger.info(f"Excel file exported: {output_path}")
            return True
            
        except ImportError:
            logger.warning("openpyxl not available, falling back to CSV")
            csv_path = output_path.replace('.xlsx', '.csv')
            self._export_to_csv(csv_path, mode=mode)
            return True
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
            return False
    
    
    def _export_to_csv(self, csv_path: str, mode: str = 'rgb'):
        """Export results to CSV format matching the template structure."""
        try:
            from utils.user_preferences import get_preferences_manager
            
            # Check user normalization preference
            try:
                prefs = get_preferences_manager()
                use_normalized = prefs.get_export_normalized_values()
            except:
                use_normalized = False  # Default to raw values if preferences unavailable
            
            # Create data structure matching the template format
            data = []
            
            # Header and metadata (rows 1-14)
            metadata = self.analysis_data.get('metadata', {})
            data.extend([
                ['Colour Space Analysis', '', '', '', '', '', '', '', '', ''],
                ['', '', '', '', '', '', '', '', '', ''],
                [datetime.now().strftime('%m/%d/%Y'), '', '', '', '', '', '', '', '', ''],
                ['', '', '', '', '', '', '', '', '', ''],
                ['Date Measured', metadata.get('date_measured', ''), '', '', '', '', '', '', '', ''],
                ['', '', '', '', '', '', '', '', '', ''],
                ['Plate', metadata.get('plate', ''), '', '', '', '', '', '', '', ''],
                ['Die', metadata.get('die', ''), '', '', '', '', '', '', '', ''],
                ['Date Registered', metadata.get('date_registered', ''), '', '', '', '', '', '', '', ''],
                ['Described Colour', metadata.get('described_colour', ''), '', '', '', '', '', '', '', ''],
                ['', '', '', '', '', '', '', '', '', ''],
                ['', '', '', '', '', '', '', '', '', ''],
                ['', 'W x H', 'Area', '', '', '', '', '', '', ''],
                ['No of Pixels', metadata.get('total_pixels', ''), '', '', '', '', '', '', '', '']
            ])
            
            # RGB section header (row 15) - CORRECTED: RGB order
            if mode == 'rgb':
                data.append(['Sample#', 'R', 'SD', '1/SD²', 'G', 'SD', '1/SD²', 'B', 'SD', '1/SD²'])
                
                # RGB data rows (16-21)
                for i in range(6):
                    if i < len(self.results):
                        result = self.results[i]
                        r_inv_sd2 = 1 / (result.get('R_std', 0) ** 2) if result.get('R_std', 0) > 0 else 0
                        g_inv_sd2 = 1 / (result.get('G_std', 0) ** 2) if result.get('G_std', 0) > 0 else 0
                        b_inv_sd2 = 1 / (result.get('B_std', 0) ** 2) if result.get('B_std', 0) > 0 else 0
                        
                        data.append([
                            str(i + 1),
                            f"{result.get('R_mean', 0):.1f}",
                            f"{result.get('R_std', 0):.2f}",
                            f"{r_inv_sd2:.6f}" if r_inv_sd2 > 0 else "#DIV/0!",
                            f"{result.get('G_mean', 0):.1f}",
                            f"{result.get('G_std', 0):.2f}",
                            f"{g_inv_sd2:.6f}" if g_inv_sd2 > 0 else "#DIV/0!",
                            f"{result.get('B_mean', 0):.1f}",
                            f"{result.get('B_std', 0):.2f}",
                            f"{b_inv_sd2:.6f}" if b_inv_sd2 > 0 else "#DIV/0!"
                        ])
                    else:
                        data.append([str(i + 1), '', '', '#DIV/0!', '', '', '#DIV/0!', '', '', '#DIV/0!'])
            
                # RGB averages and calculations (rows 22-27)
                if self.results:
                    avg_r = np.mean([r.get('R_mean', 0) for r in self.results if 'R_mean' in r])
                    avg_g = np.mean([r.get('G_mean', 0) for r in self.results if 'G_mean' in r])
                    avg_b = np.mean([r.get('B_mean', 0) for r in self.results if 'B_mean' in r])
                    avg_r_std = np.mean([r.get('R_std', 0) for r in self.results if 'R_std' in r])
                    avg_g_std = np.mean([r.get('G_std', 0) for r in self.results if 'G_std' in r])
                    avg_b_std = np.mean([r.get('B_std', 0) for r in self.results if 'B_std' in r])
                    
                    data.extend([
                        ['Ave', f"{avg_r:.1f}", f"{avg_r_std:.2f}", 
                         f"{1/(avg_r_std**2):.6f}" if avg_r_std > 0 else "#DIV/0!",
                         f"{avg_g:.1f}", f"{avg_g_std:.2f}",
                         f"{1/(avg_g_std**2):.6f}" if avg_g_std > 0 else "#DIV/0!",
                         f"{avg_b:.1f}", f"{avg_b_std:.2f}",
                         f"{1/(avg_b_std**2):.6f}" if avg_b_std > 0 else "#DIV/0!"],
                        ['8-bit', f"{avg_r:.0f}", '', '', f"{avg_g:.0f}", '', '', f"{avg_b:.0f}", '', ''],
                        ['R-G', f"{avg_r - avg_g:.1f}", f"{avg_r_std:.2f}", '0.000', '', '', '', '', '', ''],
                        ['G-B', f"{avg_g - avg_b:.1f}", f"{avg_g_std:.2f}", '', '', '', '', '', '', ''],
                        ['R-B', f"{avg_r - avg_b:.1f}", '', '', '', '', '', '', '', ''],
                        ['', '', '', '', '', '', '', '', '', '']
                    ])
                else:
                    data.extend([
                        ['Ave', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!'],
                        ['8-bit', '#DIV/0!', '', '', '#DIV/0!', '', '', '#DIV/0!', '', ''],
                        ['R-G', '#DIV/0!', '#DIV/0!', '0.000', '', '', '', '', '', ''],
                        ['G-B', '#DIV/0!', '#DIV/0!', '', '', '', '', '', '', ''],
                        ['R-B', '#DIV/0!', '', '', '', '', '', '', '', ''],
                        ['', '', '', '', '', '', '', '', '', '']
                    ])
            
            # CMY section header (row 28) - CORRECTED: CMY order
            if mode == 'cmy':
                data.append(['Sample#', 'C', 'SD', '1/SD²', 'M', 'SD', '1/SD²', 'Y', 'SD', '1/SD²'])
                
                # CMY data rows (29-34)
                for i in range(6):
                    if i < len(self.results):
                        result = self.results[i]
                        c_inv_sd2 = 1 / (result.get('C_std', 0) ** 2) if result.get('C_std', 0) > 0 else 0
                        m_inv_sd2 = 1 / (result.get('M_std', 0) ** 2) if result.get('M_std', 0) > 0 else 0
                        y_inv_sd2 = 1 / (result.get('Y_std', 0) ** 2) if result.get('Y_std', 0) > 0 else 0
                        
                        data.append([
                            str(i + 1),
                            f"{result.get('C_mean', 0):.1f}",
                            f"{result.get('C_std', 0):.2f}",
                            f"{c_inv_sd2:.6f}" if c_inv_sd2 > 0 else "#DIV/0!",
                            f"{result.get('M_mean', 0):.1f}",
                            f"{result.get('M_std', 0):.2f}",
                            f"{m_inv_sd2:.6f}" if m_inv_sd2 > 0 else "#DIV/0!",
                            f"{result.get('Y_mean', 0):.1f}",
                            f"{result.get('Y_std', 0):.2f}",
                            f"{y_inv_sd2:.6f}" if y_inv_sd2 > 0 else "#DIV/0!"
                        ])
                    else:
                        data.append([str(i + 1), '', '', '#DIV/0!', '', '', '#DIV/0!', '', '', '#DIV/0!'])
            
                # CMY averages (row 35)
                if self.results:
                    avg_c = np.mean([r.get('C_mean', 0) for r in self.results if 'C_mean' in r])
                    avg_m = np.mean([r.get('M_mean', 0) for r in self.results if 'M_mean' in r])
                    avg_y = np.mean([r.get('Y_mean', 0) for r in self.results if 'Y_mean' in r])
                    avg_c_std = np.mean([r.get('C_std', 0) for r in self.results if 'C_std' in r])
                    avg_m_std = np.mean([r.get('M_std', 0) for r in self.results if 'M_std' in r])
                    avg_y_std = np.mean([r.get('Y_std', 0) for r in self.results if 'Y_std' in r])
                    
                    data.extend([
                        ['Ave', f"{avg_c:.1f}", f"{avg_c_std:.2f}",
                         f"{1/(avg_c_std**2):.6f}" if avg_c_std > 0 else "#DIV/0!",
                         f"{avg_m:.1f}", f"{avg_m_std:.2f}",
                         f"{1/(avg_m_std**2):.6f}" if avg_m_std > 0 else "#DIV/0!",
                         f"{avg_y:.1f}", f"{avg_y_std:.2f}",
                         f"{1/(avg_y_std**2):.6f}" if avg_y_std > 0 else "#DIV/0!"],
                        ['', '', '', '', '', '', '', '', '', ''],
                        ['C-M', f"{avg_c - avg_m:.1f}", f"{avg_c_std:.2f}", '', '', '', '', '', '', ''],
                        ['M-Y', f"{avg_m - avg_y:.1f}", f"{avg_m_std:.2f}", '', '', '', '', '', '', ''],
                        ['C-Y', f"{avg_c - avg_y:.1f}", '', '', '', '', '', '', '', '']
                    ])
                else:
                    data.extend([
                        ['Ave', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!', '#DIV/0!'],
                        ['', '', '', '', '', '', '', '', '', ''],
                        ['C-M', '#DIV/0!', '#DIV/0!', '', '', '', '', '', '', ''],
                        ['M-Y', '#DIV/0!', '#DIV/0!', '', '', '', '', '', '', ''],
                        ['C-Y', '#DIV/0!', '', '', '', '', '', '', '', '']
                    ])
            
            # Write to CSV
            df = pd.DataFrame(data)
            df.to_csv(csv_path, index=False, header=False)
            logger.info(f"Exported CSV: {csv_path}")
            
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")


def create_sample_masks(image: Image.Image, regions: List[Tuple[int, int, int, int]]) -> Dict[str, Image.Image]:
    """
    Create sample masks from rectangular regions.
    
    Args:
        image: Source image
        regions: List of (x, y, width, height) tuples defining rectangular regions
        
    Returns:
        Dictionary of {sample_name: mask_image}
    """
    masks = {}
    
    for i, (x, y, width, height) in enumerate(regions):
        # Create mask
        mask = Image.new('L', image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle([x, y, x + width, y + height], fill=255)
        
        sample_name = f"Sample_{i+1:02d}"
        masks[sample_name] = mask
        
    return masks


if __name__ == "__main__":
    # Example usage
    analyzer = RGBCMYAnalyzer()
    
    # Set metadata
    analyzer.set_metadata({
        'date_measured': '10/17/2025',
        'plate': 'Test Plate',
        'die': 'Test Die',
        'date_registered': '10/17/2025',
        'described_colour': 'Test Color'
    })
    
    print("RGB-CMY Analyzer module created successfully!")
    print("CORRECTED: Now uses standard RGB and CMY order!")