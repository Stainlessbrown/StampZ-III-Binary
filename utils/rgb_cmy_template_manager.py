#!/usr/bin/env python3
"""
RGB-CMY Template Manager

Handles RGB-CMY analysis templates, copying them into StampZ, 
and generating appropriate filenames for exports.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class RGBCMYTemplateManager:
    """Manages RGB-CMY analysis templates and exports."""
    
    def __init__(self):
        self.templates_dir = self._get_templates_directory()
        self.ensure_templates_exist()
    
    def _get_templates_directory(self) -> str:
        """Get the StampZ templates directory path."""
        # Get the base directory of StampZ
        base_dir = Path(__file__).parent.parent
        templates_dir = base_dir / "data" / "templates"
        
        # Create directory if it doesn't exist
        templates_dir.mkdir(parents=True, exist_ok=True)
        
        return str(templates_dir)
    
    def ensure_templates_exist(self):
        """Ensure RGB-CMY templates exist in StampZ templates directory."""
        template_files = [
            "RGB-CMY Channel analysis.xlsx",
            "RGB-CMY Channel analysis.ods"
        ]
        
        for template_file in template_files:
            template_path = os.path.join(self.templates_dir, template_file)
            
            if not os.path.exists(template_path):
                logger.warning(f"RGB-CMY template not found: {template_path}")
                # You could add logic here to create a basic template if needed
    
    def get_template_path(self, format_type: str) -> str:
        """
        Get path to RGB-CMY template for specified format.
        
        Args:
            format_type: 'xlsx' or 'ods'
            
        Returns:
            Path to template file
        """
        template_filename = f"RGB-CMY Channel analysis.{format_type}"
        return os.path.join(self.templates_dir, template_filename)
    
    def generate_output_filename(self, image_path: str, sample_set_name: str, 
                                format_type: str = "xlsx") -> str:
        """
        Generate an output filename based on image name and timestamp.
        
        Args:
            image_path: Path to the source image
            sample_set_name: Name of the sample set
            format_type: Output format ('xlsx', 'ods', 'csv')
            
        Returns:
            Generated filename with path
        """
        try:
            # Extract image name without extension
            image_name = Path(image_path).stem
            
            # Get current timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create filename: ImageName_SampleSet_YYYYMMDD_HHMMSS.ext
            filename = f"{image_name}_{sample_set_name}_RGB-CMY_{timestamp}.{format_type}"
            
            # Clean filename (remove invalid characters)
            filename = self._clean_filename(filename)
            
            # Return full path in the same directory as the image
            image_dir = Path(image_path).parent
            output_path = image_dir / filename
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error generating output filename: {e}")
            # Fallback filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"RGB-CMY_Analysis_{timestamp}.{format_type}"
    
    def _clean_filename(self, filename: str) -> str:
        """Clean filename by removing or replacing invalid characters."""
        # Replace problematic characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove multiple consecutive underscores
        while '__' in filename:
            filename = filename.replace('__', '_')
        
        # Remove leading/trailing underscores and spaces
        filename = filename.strip('_ ')
        
        return filename
    
    def export_with_auto_filename(self, analyzer, image_path: str, 
                                 sample_set_name: str, format_type: str = "xlsx") -> tuple[bool, str]:
        """
        Export RGB-CMY analysis results with automatically generated filename.
        
        Args:
            analyzer: RGBCMYAnalyzer instance with results
            image_path: Path to source image
            sample_set_name: Sample set name
            format_type: Export format ('xlsx', 'ods', 'csv')
            
        Returns:
            Tuple of (success, output_path)
        """
        try:
            # Generate output filename
            output_path = self.generate_output_filename(image_path, sample_set_name, format_type)
            
            if format_type in ['xlsx', 'ods']:
                # Get template path
                template_path = self.get_template_path(format_type)
                
                if not os.path.exists(template_path):
                    logger.warning(f"Template not found: {template_path}, falling back to CSV")
                    # Fallback to CSV
                    csv_path = output_path.replace(f'.{format_type}', '.csv')
                    analyzer._export_to_csv(csv_path)
                    return True, csv_path
                
                # Export using template
                success = analyzer.export_to_template(template_path, output_path)
                if success:
                    return True, output_path
                else:
                    # Fallback to CSV
                    csv_path = output_path.replace(f'.{format_type}', '.csv')
                    analyzer._export_to_csv(csv_path)
                    return True, csv_path
            
            else:  # CSV
                analyzer._export_to_csv(output_path)
                return True, output_path
            
        except Exception as e:
            logger.error(f"Error in auto-export: {e}")
            return False, ""
    
    def get_available_formats(self) -> list[str]:
        """Get list of available export formats based on existing templates."""
        formats = []
        
        if os.path.exists(self.get_template_path('xlsx')):
            formats.append('xlsx')  # Prefer xlsx - it works with formulas
        
        if os.path.exists(self.get_template_path('ods')):
            formats.append('ods')  # ODS also supports formulas
        
        # CSV removed - doesn't support formulas, so not useful for RGB-CMY analysis
        
        return formats
    
    def get_template_info(self) -> dict:
        """Get information about available templates."""
        info = {
            'templates_directory': self.templates_dir,
            'available_formats': self.get_available_formats(),
            'templates': {}
        }
        
        for format_type in ['xlsx', 'ods']:
            template_path = self.get_template_path(format_type)
            info['templates'][format_type] = {
                'path': template_path,
                'exists': os.path.exists(template_path),
                'size': os.path.getsize(template_path) if os.path.exists(template_path) else 0
            }
        
        return info


# Global instance
_template_manager = None

def get_template_manager() -> RGBCMYTemplateManager:
    """Get singleton template manager instance."""
    global _template_manager
    if _template_manager is None:
        _template_manager = RGBCMYTemplateManager()
    return _template_manager


if __name__ == "__main__":
    # Test the template manager
    manager = RGBCMYTemplateManager()
    
    print("RGB-CMY Template Manager Test")
    print("=" * 40)
    
    # Show template info
    info = manager.get_template_info()
    print(f"Templates directory: {info['templates_directory']}")
    print(f"Available formats: {info['available_formats']}")
    
    for format_type, template_info in info['templates'].items():
        status = "✅ Available" if template_info['exists'] else "❌ Missing"
        size = f"({template_info['size']} bytes)" if template_info['exists'] else ""
        print(f"  {format_type.upper()}: {status} {size}")
    
    # Test filename generation
    test_image = "/Users/test/Documents/stamp_image.jpg"
    test_sample_set = "Test_Sample_Set"
    
    print(f"\nFilename generation test:")
    print(f"Image: {test_image}")
    print(f"Sample set: {test_sample_set}")
    
    for format_type in ['xlsx', 'ods', 'csv']:
        filename = manager.generate_output_filename(test_image, test_sample_set, format_type)
        print(f"  {format_type.upper()}: {filename}")