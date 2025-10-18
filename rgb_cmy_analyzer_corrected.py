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
    
    def analyze_masked_region(self, mask: Image.Image, sample_name: str) -> Dict[str, float]:
        """
        Analyze RGB and CMY values for a masked region.
        
        Args:
            mask: Binary mask image (white = analyze, black = ignore)
            sample_name: Name/identifier for this sample
            
        Returns:
            Dictionary with RGB and CMY statistics
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
            
            # Calculate RGB statistics
            rgb_means = np.mean(masked_rgb, axis=0)
            rgb_stds = np.std(masked_rgb, axis=0, ddof=1)  # Sample standard deviation
            
            # Convert RGB to CMY
            # CMY = 255 - RGB (simple subtractive color model)
            cmy_values = 255 - masked_rgb
            cmy_means = np.mean(cmy_values, axis=0)
            cmy_stds = np.std(cmy_values, axis=0, ddof=1)
            
            # Compile results - CORRECTED: Standard RGB and CMY order
            result = {
                'sample_name': sample_name,
                'pixel_count': int(np.sum(mask_pixels)),
                # RGB data - standard RGB order (Red, Green, Blue)
                'R_mean': float(rgb_means[0]),  # Red = index 0
                'R_std': float(rgb_stds[0]),
                'G_mean': float(rgb_means[1]),  # Green = index 1
                'G_std': float(rgb_stds[1]),
                'B_mean': float(rgb_means[2]),  # Blue = index 2
                'B_std': float(rgb_stds[2]),
                # CMY data - standard CMY order (Cyan, Magenta, Yellow)
                'C_mean': float(cmy_means[0]),  # Cyan = 255 - Red
                'C_std': float(cmy_stds[0]),
                'M_mean': float(cmy_means[1]),  # Magenta = 255 - Green
                'M_std': float(cmy_stds[1]),
                'Y_mean': float(cmy_means[2]),  # Yellow = 255 - Blue
                'Y_std': float(cmy_stds[2])
            }
            
            logger.info(f"Analyzed sample {sample_name}: {result['pixel_count']} pixels")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing masked region for {sample_name}: {e}")
            return self._create_empty_result(sample_name)
    
    def _create_empty_result(self, sample_name: str) -> Dict[str, float]:
        """Create empty result structure for failed analysis."""
        return {
            'sample_name': sample_name,
            'pixel_count': 0,
            'R_mean': 0.0, 'R_std': 0.0,
            'G_mean': 0.0, 'G_std': 0.0,
            'B_mean': 0.0, 'B_std': 0.0,
            'C_mean': 0.0, 'C_std': 0.0,
            'M_mean': 0.0, 'M_std': 0.0,
            'Y_mean': 0.0, 'Y_std': 0.0
        }
    
    def analyze_multiple_masks(self, masks: Dict[str, Image.Image]) -> List[Dict[str, float]]:
        """
        Analyze multiple masked regions in batch.
        
        Args:
            masks: Dictionary of {sample_name: mask_image}
            
        Returns:
            List of analysis results for each sample
        """
        results = []
        
        for sample_name, mask in masks.items():
            result = self.analyze_masked_region(mask, sample_name)
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
    
    def export_to_template(self, template_path: str, output_path: str) -> bool:
        """
        Export analysis results to RGB-CMY template.
        
        Args:
            template_path: Path to the RGB-CMY template file
            output_path: Path for the populated output file
            
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
                return self._export_to_xlsx(template_path, output_path)
            elif file_ext == '.ods':
                return self._export_to_ods(template_path, output_path)
            else:
                # Fallback to CSV
                self._export_to_csv(output_path)
                return True
            
        except Exception as e:
            logger.error(f"Error exporting to template: {e}")
            return False
    
    def _export_to_xlsx(self, template_path: str, output_path: str) -> bool:
        """Export to Excel format using openpyxl."""
        try:
            import openpyxl
            
            # Load template
            workbook = openpyxl.load_workbook(template_path)
            sheet = workbook.active
            
            # Populate metadata
            metadata = self.analysis_data.get('metadata', {})
            sheet['B2'] = metadata.get('plate', '')
            sheet['B3'] = datetime.now().strftime('%m/%d/%Y')
            sheet['B5'] = metadata.get('date_measured', '')
            sheet['B7'] = metadata.get('plate', '')
            sheet['B8'] = metadata.get('die', '')
            sheet['B9'] = metadata.get('date_registered', '')
            sheet['B10'] = metadata.get('described_colour', '')
            sheet['B14'] = metadata.get('total_pixels', '')
            
            # Populate RGB data (rows 16-21, columns B-J) - RGB order
            for i in range(min(6, len(self.results))):  # Only populate up to 6 samples or actual count
                result = self.results[i]
                row = 16 + i
                sheet[f'B{row}'] = result['R_mean']  # Red in first column
                sheet[f'C{row}'] = result['R_std']
                sheet[f'E{row}'] = result['G_mean']  # Green in middle
                sheet[f'F{row}'] = result['G_std']
                sheet[f'H{row}'] = result['B_mean']  # Blue in last column
                sheet[f'I{row}'] = result['B_std']
            
            # Populate CMY data (rows 29-34, columns B-J) - CMY order
            for i in range(min(6, len(self.results))):  # Only populate up to 6 samples or actual count
                result = self.results[i]
                row = 29 + i
                sheet[f'B{row}'] = result['C_mean']  # Cyan first
                sheet[f'C{row}'] = result['C_std']
                sheet[f'E{row}'] = result['M_mean']  # Magenta middle
                sheet[f'F{row}'] = result['M_std']
                sheet[f'H{row}'] = result['Y_mean']  # Yellow last
                sheet[f'I{row}'] = result['Y_std']
            
            # Save populated workbook
            workbook.save(output_path)
            logger.info(f"Excel file exported: {output_path}")
            return True
            
        except ImportError:
            logger.warning("openpyxl not available, falling back to CSV")
            csv_path = output_path.replace('.xlsx', '.csv')
            self._export_to_csv(csv_path)
            return True
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
            return False
    
    def _export_to_ods(self, template_path: str, output_path: str) -> bool:
        """Export to ODS format using proper odfpy library (same as main app)."""
        try:
            # Try to import odfpy like the main ODS exporter does
            try:
                from odf.opendocument import OpenDocumentSpreadsheet
                from odf.table import Table, TableRow, TableCell
                from odf.text import P
                from odf.style import Style, TableColumnProperties
                from odf import number
                
                logger.info("Using odfpy for native ODS export")
                
                # Create new ODS document (we'll populate it from scratch)
                doc = OpenDocumentSpreadsheet()
                
                # Create table
                table = Table()
                table.setAttribute('name', 'RGB-CMY Analysis')
                
                # Helper function to create a cell with value
                def create_cell(value, value_type='string'):
                    cell = TableCell()
                    if value_type == 'float' and value != '':
                        try:
                            numeric_value = float(value)
                            cell.setAttribute('valuetype', 'float')
                            cell.setAttribute('value', str(numeric_value))
                            cell.addElement(P(text=str(value)))
                        except (ValueError, TypeError):
                            cell.addElement(P(text=str(value)))
                    else:
                        cell.addElement(P(text=str(value)))
                    return cell
                
                # Get metadata
                metadata = self.analysis_data.get('metadata', {})
                
                # Create rows matching the template structure
                rows_data = [
                    # Header rows (1-14)
                    ['Colour Space Analysis', '', '', '', '', '', '', '', '', ''],
                    [metadata.get('plate', ''), '', '', '', '', '', '', '', '', ''],
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
                    ['No of Pixels', metadata.get('total_pixels', ''), '', '', '', '', '', '', '', ''],
                    
                    # RGB section header (row 15) - RGB order
                    ['Sample#', 'R', 'SD', '1/SD²', 'G', 'SD', '1/SD²', 'B', 'SD', '1/SD²']
                ]
                
                # RGB data rows (16-21) - only populate rows for actual samples
                for i in range(6):
                    if i < len(self.results):
                        result = self.results[i]
                        r_inv_sd2 = 1 / (result['R_std'] ** 2) if result['R_std'] > 0 else ''
                        g_inv_sd2 = 1 / (result['G_std'] ** 2) if result['G_std'] > 0 else ''
                        b_inv_sd2 = 1 / (result['B_std'] ** 2) if result['B_std'] > 0 else ''
                        
                        rows_data.append([
                            str(i + 1),
                            f"{result['R_mean']:.1f}",  # Red first
                            f"{result['R_std']:.2f}",
                            f"{r_inv_sd2:.6f}" if r_inv_sd2 != '' else '',
                            f"{result['G_mean']:.1f}",  # Green middle
                            f"{result['G_std']:.2f}",
                            f"{g_inv_sd2:.6f}" if g_inv_sd2 != '' else '',
                            f"{result['B_mean']:.1f}",  # Blue last
                            f"{result['B_std']:.2f}",
                            f"{b_inv_sd2:.6f}" if b_inv_sd2 != '' else ''
                        ])
                    else:
                        # Empty row for unused sample slots
                        rows_data.append([str(i + 1), '', '', '', '', '', '', '', '', ''])
                
                # RGB averages and calculations (rows 22-27)
                if self.results:
                    avg_r = np.mean([r['R_mean'] for r in self.results])
                    avg_g = np.mean([r['G_mean'] for r in self.results])
                    avg_b = np.mean([r['B_mean'] for r in self.results])
                    avg_r_std = np.mean([r['R_std'] for r in self.results])
                    avg_g_std = np.mean([r['G_std'] for r in self.results])
                    avg_b_std = np.mean([r['B_std'] for r in self.results])
                    
                    rows_data.extend([
                        ['Ave', f"{avg_r:.1f}", f"{avg_r_std:.2f}", 
                         f"{1/(avg_r_std**2):.6f}" if avg_r_std > 0 else '',
                         f"{avg_g:.1f}", f"{avg_g_std:.2f}",
                         f"{1/(avg_g_std**2):.6f}" if avg_g_std > 0 else '',
                         f"{avg_b:.1f}", f"{avg_b_std:.2f}",
                         f"{1/(avg_b_std**2):.6f}" if avg_b_std > 0 else ''],
                        ['8-bit', f"{avg_r:.0f}", '', '', f"{avg_g:.0f}", '', '', f"{avg_b:.0f}", '', ''],
                        ['R-G', f"{avg_r - avg_g:.1f}", f"{avg_r_std:.2f}", '0.000', '', '', '', '', '', ''],
                        ['G-B', f"{avg_g - avg_b:.1f}", f"{avg_g_std:.2f}", '', '', '', '', '', '', ''],
                        ['R-B', f"{avg_r - avg_b:.1f}", '', '', '', '', '', '', '', ''],
                        ['', '', '', '', '', '', '', '', '', '']
                    ])
                else:
                    rows_data.extend([
                        ['Ave', '', '', '', '', '', '', '', '', ''],
                        ['8-bit', '', '', '', '', '', '', '', '', ''],
                        ['R-G', '', '', '0.000', '', '', '', '', '', ''],
                        ['G-B', '', '', '', '', '', '', '', '', ''],
                        ['R-B', '', '', '', '', '', '', '', '', ''],
                        ['', '', '', '', '', '', '', '', '', '']
                    ])
                
                # CMY section header (row 28) - CMY order
                rows_data.append(['Sample#', 'C', 'SD', '1/SD²', 'M', 'SD', '1/SD²', 'Y', 'SD', '1/SD²'])
                
                # CMY data rows (29-34) - only populate rows for actual samples
                for i in range(6):
                    if i < len(self.results):
                        result = self.results[i]
                        c_inv_sd2 = 1 / (result['C_std'] ** 2) if result['C_std'] > 0 else ''
                        m_inv_sd2 = 1 / (result['M_std'] ** 2) if result['M_std'] > 0 else ''
                        y_inv_sd2 = 1 / (result['Y_std'] ** 2) if result['Y_std'] > 0 else ''
                        
                        rows_data.append([
                            str(i + 1),
                            f"{result['C_mean']:.1f}",  # Cyan first
                            f"{result['C_std']:.2f}",
                            f"{c_inv_sd2:.6f}" if c_inv_sd2 != '' else '',
                            f"{result['M_mean']:.1f}",  # Magenta middle
                            f"{result['M_std']:.2f}",
                            f"{m_inv_sd2:.6f}" if m_inv_sd2 != '' else '',
                            f"{result['Y_mean']:.1f}",  # Yellow last
                            f"{result['Y_std']:.2f}",
                            f"{y_inv_sd2:.6f}" if y_inv_sd2 != '' else ''
                        ])
                    else:
                        # Empty row for unused sample slots
                        rows_data.append([str(i + 1), '', '', '', '', '', '', '', '', ''])
                
                # CMY averages (rows 35-39)
                if self.results:
                    avg_c = np.mean([r['C_mean'] for r in self.results])
                    avg_m = np.mean([r['M_mean'] for r in self.results])
                    avg_y = np.mean([r['Y_mean'] for r in self.results])
                    avg_c_std = np.mean([r['C_std'] for r in self.results])
                    avg_m_std = np.mean([r['M_std'] for r in self.results])
                    avg_y_std = np.mean([r['Y_std'] for r in self.results])
                    
                    rows_data.extend([
                        ['Ave', f"{avg_c:.1f}", f"{avg_c_std:.2f}",
                         f"{1/(avg_c_std**2):.6f}" if avg_c_std > 0 else '',
                         f"{avg_m:.1f}", f"{avg_m_std:.2f}",
                         f"{1/(avg_m_std**2):.6f}" if avg_m_std > 0 else '',
                         f"{avg_y:.1f}", f"{avg_y_std:.2f}",
                         f"{1/(avg_y_std**2):.6f}" if avg_y_std > 0 else ''],
                        ['', '', '', '', '', '', '', '', '', ''],
                        ['C-M', f"{avg_c - avg_m:.1f}", f"{avg_c_std:.2f}", '', '', '', '', '', '', ''],
                        ['M-Y', f"{avg_m - avg_y:.1f}", f"{avg_m_std:.2f}", '', '', '', '', '', '', ''],
                        ['C-Y', f"{avg_c - avg_y:.1f}", '', '', '', '', '', '', '', '']
                    ])
                else:
                    rows_data.extend([
                        ['Ave', '', '', '', '', '', '', '', '', ''],
                        ['', '', '', '', '', '', '', '', '', ''],
                        ['C-M', '', '', '', '', '', '', '', '', ''],
                        ['M-Y', '', '', '', '', '', '', '', '', ''],
                        ['C-Y', '', '', '', '', '', '', '', '', '']
                    ])
                
                # Create table rows
                for row_data in rows_data:
                    row = TableRow()
                    for value in row_data:
                        cell = create_cell(value, 'float' if str(value).replace('.','').replace('-','').isdigit() else 'string')
                        row.addElement(cell)
                    table.addElement(row)
                
                # Add table to document
                doc.spreadsheet.addElement(table)
                
                # Save document
                doc.save(output_path)
                logger.info(f"ODS file exported with data using odfpy: {output_path}")
                return True
                
            except ImportError as import_error:
                logger.warning(f"odfpy not available: {import_error}, falling back to template copy")
                
                # Fallback: just copy the template (better than broken file)
                shutil.copy2(template_path, output_path)
                logger.info(f"ODS template copied (no data population): {output_path}")
                return True
            
        except Exception as e:
            logger.error(f"Error exporting to ODS: {e}")
            return False
    
    def _export_to_csv(self, csv_path: str):
        """Export results to CSV format matching the template structure."""
        try:
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
            data.append(['Sample#', 'R', 'SD', '1/SD²', 'G', 'SD', '1/SD²', 'B', 'SD', '1/SD²'])
            
            # RGB data rows (16-21)
            for i in range(6):
                if i < len(self.results):
                    result = self.results[i]
                    r_inv_sd2 = 1 / (result['R_std'] ** 2) if result['R_std'] > 0 else 0
                    g_inv_sd2 = 1 / (result['G_std'] ** 2) if result['G_std'] > 0 else 0
                    b_inv_sd2 = 1 / (result['B_std'] ** 2) if result['B_std'] > 0 else 0
                    
                    data.append([
                        str(i + 1),
                        f"{result['R_mean']:.1f}",
                        f"{result['R_std']:.2f}",
                        f"{r_inv_sd2:.6f}" if r_inv_sd2 > 0 else "#DIV/0!",
                        f"{result['G_mean']:.1f}",
                        f"{result['G_std']:.2f}",
                        f"{g_inv_sd2:.6f}" if g_inv_sd2 > 0 else "#DIV/0!",
                        f"{result['B_mean']:.1f}",
                        f"{result['B_std']:.2f}",
                        f"{b_inv_sd2:.6f}" if b_inv_sd2 > 0 else "#DIV/0!"
                    ])
                else:
                    data.append([str(i + 1), '', '', '#DIV/0!', '', '', '#DIV/0!', '', '', '#DIV/0!'])
            
            # RGB averages and calculations (rows 22-27)
            if self.results:
                avg_r = np.mean([r['R_mean'] for r in self.results])
                avg_g = np.mean([r['G_mean'] for r in self.results])
                avg_b = np.mean([r['B_mean'] for r in self.results])
                avg_r_std = np.mean([r['R_std'] for r in self.results])
                avg_g_std = np.mean([r['G_std'] for r in self.results])
                avg_b_std = np.mean([r['B_std'] for r in self.results])
                
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
            data.append(['Sample#', 'C', 'SD', '1/SD²', 'M', 'SD', '1/SD²', 'Y', 'SD', '1/SD²'])
            
            # CMY data rows (29-34)
            for i in range(6):
                if i < len(self.results):
                    result = self.results[i]
                    c_inv_sd2 = 1 / (result['C_std'] ** 2) if result['C_std'] > 0 else 0
                    m_inv_sd2 = 1 / (result['M_std'] ** 2) if result['M_std'] > 0 else 0
                    y_inv_sd2 = 1 / (result['Y_std'] ** 2) if result['Y_std'] > 0 else 0
                    
                    data.append([
                        str(i + 1),
                        f"{result['C_mean']:.1f}",
                        f"{result['C_std']:.2f}",
                        f"{c_inv_sd2:.6f}" if c_inv_sd2 > 0 else "#DIV/0!",
                        f"{result['M_mean']:.1f}",
                        f"{result['M_std']:.2f}",
                        f"{m_inv_sd2:.6f}" if m_inv_sd2 > 0 else "#DIV/0!",
                        f"{result['Y_mean']:.1f}",
                        f"{result['Y_std']:.2f}",
                        f"{y_inv_sd2:.6f}" if y_inv_sd2 > 0 else "#DIV/0!"
                    ])
                else:
                    data.append([str(i + 1), '', '', '#DIV/0!', '', '', '#DIV/0!', '', '', '#DIV/0!'])
            
            # CMY averages (row 35)
            if self.results:
                avg_c = np.mean([r['C_mean'] for r in self.results])
                avg_m = np.mean([r['M_mean'] for r in self.results])
                avg_y = np.mean([r['Y_mean'] for r in self.results])
                avg_c_std = np.mean([r['C_std'] for r in self.results])
                avg_m_std = np.mean([r['M_std'] for r in self.results])
                avg_y_std = np.mean([r['Y_std'] for r in self.results])
                
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