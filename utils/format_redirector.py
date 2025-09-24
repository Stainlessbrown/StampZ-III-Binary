#!/usr/bin/env python3
"""
Format Redirector

This module provides redirects for all formatting logic that exists outside of data_file_manager.py.
Instead of having duplicate column definitions, validation lists, and normalization logic scattered
across multiple files, this module redirects all such calls to the centralized data_file_manager.py.

Key Functions:
1. Replace all PLOT3D_COLUMNS definitions with get_plot3d_columns()
2. Replace all TERNARY_COLUMNS definitions with get_ternary_columns()
3. Replace all VALID_MARKERS/COLORS/SPHERES with get_validation_lists()
4. Replace all normalization functions with unified normalize_*() functions
5. Provide compatibility functions for existing code

This eliminates inconsistencies and ensures all formatting comes from one source.
"""

import logging
from typing import List, Dict, Any, Optional, Union
import pandas as pd
import numpy as np

# Import the unified data file manager
from utils.data_file_manager import get_data_file_manager, DataFormat

logger = logging.getLogger(__name__)

# Global manager instance
_manager = None

def _get_manager():
    """Get the global data file manager instance."""
    global _manager
    if _manager is None:
        _manager = get_data_file_manager()
    return _manager


# === Column Structure Redirects ===

def get_plot3d_columns() -> List[str]:
    """
    Get Plot_3D column structure.
    
    REPLACES: All hardcoded PLOT3D_COLUMNS definitions
    
    Returns:
        List of column names for Plot_3D format
    """
    return _get_manager().get_columns(DataFormat.PLOT3D)


def get_ternary_columns() -> List[str]:
    """
    Get Ternary column structure.
    
    REPLACES: All hardcoded TERNARY_COLUMNS definitions
    
    Returns:
        List of column names for Ternary format
    """
    return _get_manager().get_columns(DataFormat.TERNARY)


# === Validation Lists Redirects ===

def get_valid_markers() -> List[str]:
    """
    Get valid marker list.
    
    REPLACES: All hardcoded VALID_MARKERS definitions
    
    Returns:
        List of valid marker options
    """
    validation_lists = _get_manager().get_validation_lists(DataFormat.PLOT3D)
    return validation_lists.get('Marker', ['', '.', 'o', '*', '^', '<', '>', 'v', 's', 'D', '+', 'x'])


def get_valid_colors() -> List[str]:
    """
    Get valid color list.
    
    REPLACES: All hardcoded VALID_COLORS definitions
    
    Returns:
        List of valid color options
    """
    validation_lists = _get_manager().get_validation_lists(DataFormat.PLOT3D)
    return validation_lists.get('Color', ['', 'red', 'blue', 'green', 'orange', 'purple', 'yellow', 
                                          'cyan', 'magenta', 'brown', 'pink', 'lime', 'navy', 'teal', 'gray'])


def get_valid_spheres() -> List[str]:
    """
    Get valid sphere list.
    
    REPLACES: All hardcoded VALID_SPHERES definitions
    
    Returns:
        List of valid sphere options
    """
    validation_lists = _get_manager().get_validation_lists(DataFormat.PLOT3D)
    return validation_lists.get('Sphere', ['', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta',
                                           'orange', 'purple', 'brown', 'pink', 'lime', 'navy', 'teal', 'gray'])


def get_all_validation_lists(format_type: str = 'plot3d') -> Dict[str, List[str]]:
    """
    Get all validation lists for a format.
    
    REPLACES: Multiple separate validation list definitions
    
    Args:
        format_type: 'plot3d' or 'ternary'
        
    Returns:
        Dictionary of validation lists
    """
    data_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
    return _get_manager().get_validation_lists(data_format)


# === Normalization Function Redirects ===

def normalize_lab_l(l_value: float) -> float:
    """
    Normalize L* value (0-100) to 0-1 range.
    
    REPLACES: All scattered L* normalization logic
    
    Args:
        l_value: L* value in 0-100 range
        
    Returns:
        Normalized value in 0-1 range
    """
    return max(0.0, min(1.0, l_value / 100.0))


def normalize_lab_a(a_value: float, format_type: str = 'plot3d') -> float:
    """
    Normalize a* value to 0-1 range.
    
    REPLACES: All scattered a* normalization logic
    
    Args:
        a_value: a* value (typically -128 to +127)
        format_type: 'plot3d' or 'ternary' (different ranges)
        
    Returns:
        Normalized value in 0-1 range
    """
    if format_type == 'plot3d':
        # Plot_3D: -128 to +127 → 0-1
        return max(0.0, min(1.0, (a_value + 128.0) / 255.0))
    else:
        # Ternary: -127.5 to +127.5 → 0-1
        return max(0.0, min(1.0, (a_value + 127.5) / 255.0))


def normalize_lab_b(b_value: float, format_type: str = 'plot3d') -> float:
    """
    Normalize b* value to 0-1 range.
    
    REPLACES: All scattered b* normalization logic
    
    Args:
        b_value: b* value (typically -128 to +127)
        format_type: 'plot3d' or 'ternary' (different ranges)
        
    Returns:
        Normalized value in 0-1 range
    """
    if format_type == 'plot3d':
        # Plot_3D: -128 to +127 → 0-1
        return max(0.0, min(1.0, (b_value + 128.0) / 255.0))
    else:
        # Ternary: -127.5 to +127.5 → 0-1
        return max(0.0, min(1.0, (b_value + 127.5) / 255.0))


def denormalize_lab_l(normalized_value: float) -> float:
    """
    Denormalize L* value from 0-1 range back to 0-100.
    
    REPLACES: All scattered L* denormalization logic
    
    Args:
        normalized_value: Value in 0-1 range
        
    Returns:
        L* value in 0-100 range
    """
    return normalized_value * 100.0


def denormalize_lab_a(normalized_value: float, format_type: str = 'plot3d') -> float:
    """
    Denormalize a* value from 0-1 range back to original.
    
    REPLACES: All scattered a* denormalization logic
    
    Args:
        normalized_value: Value in 0-1 range
        format_type: 'plot3d' or 'ternary' (different ranges)
        
    Returns:
        a* value in original range
    """
    if format_type == 'plot3d':
        # 0-1 → -128 to +127
        return (normalized_value * 255.0) - 128.0
    else:
        # 0-1 → -127.5 to +127.5
        return (normalized_value * 255.0) - 127.5


def denormalize_lab_b(normalized_value: float, format_type: str = 'plot3d') -> float:
    """
    Denormalize b* value from 0-1 range back to original.
    
    REPLACES: All scattered b* denormalization logic
    
    Args:
        normalized_value: Value in 0-1 range
        format_type: 'plot3d' or 'ternary' (different ranges)
        
    Returns:
        b* value in original range
    """
    if format_type == 'plot3d':
        # 0-1 → -128 to +127
        return (normalized_value * 255.0) - 128.0
    else:
        # 0-1 → -127.5 to +127.5
        return (normalized_value * 255.0) - 127.5


def normalize_rgb(rgb_value: float) -> float:
    """
    Normalize RGB value (0-255) to 0-1 range.
    
    REPLACES: All scattered RGB normalization logic
    
    Args:
        rgb_value: RGB value in 0-255 range
        
    Returns:
        Normalized value in 0-1 range
    """
    return max(0.0, min(1.0, rgb_value / 255.0))


def denormalize_rgb(normalized_value: float) -> float:
    """
    Denormalize RGB value from 0-1 range back to 0-255.
    
    REPLACES: All scattered RGB denormalization logic
    
    Args:
        normalized_value: Value in 0-1 range
        
    Returns:
        RGB value in 0-255 range
    """
    return normalized_value * 255.0


# === Format Conversion Redirects ===

def convert_lab_to_normalized(l_val: float, a_val: float, b_val: float, 
                             format_type: str = 'plot3d') -> tuple:
    """
    Convert L*a*b* values to normalized format.
    
    REPLACES: All scattered Lab→normalized conversion logic
    
    Args:
        l_val: L* value (0-100)
        a_val: a* value (typically -128 to +127)
        b_val: b* value (typically -128 to +127)  
        format_type: 'plot3d' or 'ternary'
        
    Returns:
        Tuple of (x_norm, y_norm, z_norm) in 0-1 range
    """
    x_norm = normalize_lab_l(l_val)
    y_norm = normalize_lab_a(a_val, format_type)
    z_norm = normalize_lab_b(b_val, format_type)
    
    return (x_norm, y_norm, z_norm)


def convert_normalized_to_lab(x_norm: float, y_norm: float, z_norm: float, 
                             format_type: str = 'plot3d') -> tuple:
    """
    Convert normalized values back to L*a*b* format.
    
    REPLACES: All scattered normalized→Lab conversion logic
    
    Args:
        x_norm: Normalized X value (0-1)
        y_norm: Normalized Y value (0-1)
        z_norm: Normalized Z value (0-1)
        format_type: 'plot3d' or 'ternary'
        
    Returns:
        Tuple of (l_val, a_val, b_val) in original ranges
    """
    l_val = denormalize_lab_l(x_norm)
    a_val = denormalize_lab_a(y_norm, format_type)
    b_val = denormalize_lab_b(z_norm, format_type)
    
    return (l_val, a_val, b_val)


# === Data Standardization Redirects ===

def standardize_data(data: Union[pd.DataFrame, List[List[Any]]], 
                    source_format: str, target_format: str) -> pd.DataFrame:
    """
    Standardize data between formats.
    
    REPLACES: All scattered data standardization logic
    
    Args:
        data: Data in source format
        source_format: 'database', 'plot3d', 'ternary', 'external_ods', 'external_csv'
        target_format: Target format
        
    Returns:
        Standardized DataFrame
    """
    # Convert format strings to DataFormat enums
    format_map = {
        'database': DataFormat.DATABASE,
        'plot3d': DataFormat.PLOT3D, 
        'ternary': DataFormat.TERNARY,
        'external_ods': DataFormat.EXTERNAL_ODS,
        'external_csv': DataFormat.EXTERNAL_CSV
    }
    
    source_df = DataFormat(source_format) if source_format in format_map else DataFormat.PLOT3D
    target_df = DataFormat(target_format) if target_format in format_map else DataFormat.PLOT3D
    
    # Convert to DataFrame if needed
    if isinstance(data, list):
        columns = get_plot3d_columns() if source_format == 'plot3d' else get_ternary_columns()
        data = pd.DataFrame(data, columns=columns)
    
    return _get_manager().standardize_data(data, source_df, target_df)


# === Formatting Application Redirects ===

def apply_realtime_formatting(sheet_widget, format_type: str = 'plot3d'):
    """
    Apply formatting to realtime sheet.
    
    REPLACES: All scattered sheet formatting logic
    
    Args:
        sheet_widget: TkSheet widget
        format_type: 'plot3d' or 'ternary'
    """
    from utils.data_file_manager import get_data_file_manager, DataFormat
    manager = get_data_file_manager()
    data_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
    manager.apply_realtime_sheet_formatting(sheet_widget, data_format)


def create_external_file(file_path: str, data: pd.DataFrame, 
                        format_type: str = 'plot3d') -> bool:
    """
    Create external file with proper formatting.
    
    REPLACES: All scattered external file creation logic
    
    Args:
        file_path: Path for the output file
        data: Data to export
        format_type: 'plot3d' or 'ternary'
        
    Returns:
        True if successful
    """
    data_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
    return _get_manager().create_external_file(file_path, data, data_format)


def read_external_file(file_path: str, format_type: str = 'plot3d') -> Optional[pd.DataFrame]:
    """
    Read external file with proper standardization.
    
    REPLACES: All scattered external file reading logic
    
    Args:
        file_path: Path of the file to read
        format_type: 'plot3d' or 'ternary'
        
    Returns:
        Standardized DataFrame or None
    """
    data_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
    return _get_manager().read_external_file(file_path, data_format)


def validate_data(data: pd.DataFrame, format_type: str = 'plot3d') -> Dict[str, List[str]]:
    """
    Validate data using unified rules.
    
    REPLACES: All scattered data validation logic
    
    Args:
        data: Data to validate
        format_type: 'plot3d' or 'ternary'
        
    Returns:
        Dictionary of validation errors
    """
    data_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
    return _get_manager().validate_data(data, data_format)


# === Backward Compatibility Functions ===

def get_plot3d_template_columns():
    """Backward compatibility for old template code."""
    return get_plot3d_columns()


def get_rigid_template_columns():
    """Backward compatibility for rigid template code."""
    return get_plot3d_columns()


# IMPORTANT: These are the key compatibility functions that replace hardcoded definitions
# Use these in existing code instead of hardcoded lists

# For realtime_plot3d_sheet.py:
PLOT3D_COLUMNS = property(lambda self: get_plot3d_columns())
VALID_MARKERS = property(lambda self: get_valid_markers())
VALID_COLORS = property(lambda self: get_valid_colors())
VALID_SPHERES = property(lambda self: get_valid_spheres())

# For ternary_export.py:
TERNARY_COLUMNS = property(lambda self: get_ternary_columns())

# === Integration Helper Functions ===

def replace_hardcoded_columns(class_instance, format_type: str = 'plot3d'):
    """
    Replace hardcoded column definitions in a class instance.
    
    Use this to retrofit existing classes without changing their code.
    
    Args:
        class_instance: Instance to modify
        format_type: 'plot3d' or 'ternary'
    """
    if format_type == 'plot3d':
        class_instance.PLOT3D_COLUMNS = get_plot3d_columns()
        class_instance.VALID_MARKERS = get_valid_markers()
        class_instance.VALID_COLORS = get_valid_colors()
        class_instance.VALID_SPHERES = get_valid_spheres()
    else:
        class_instance.TERNARY_COLUMNS = get_ternary_columns()
        
    logger.info(f"Replaced hardcoded columns in {class_instance.__class__.__name__} with unified definitions")


def replace_hardcoded_functions(module_instance):
    """
    Replace hardcoded normalization functions in a module.
    
    Use this to retrofit existing modules without changing their code.
    
    Args:
        module_instance: Module to modify
    """
    # Replace normalization functions
    if hasattr(module_instance, '_normalize_lab_l'):
        module_instance._normalize_lab_l = normalize_lab_l
    if hasattr(module_instance, '_normalize_lab_a'):
        module_instance._normalize_lab_a = lambda x: normalize_lab_a(x, 'plot3d')
    if hasattr(module_instance, '_normalize_lab_b'):
        module_instance._normalize_lab_b = lambda x: normalize_lab_b(x, 'plot3d')
    if hasattr(module_instance, '_normalize_rgb'):
        module_instance._normalize_rgb = normalize_rgb
        
    logger.info(f"Replaced hardcoded functions in {module_instance.__name__} with unified functions")


# === Usage Examples ===

def example_usage():
    """Examples of how to use the format redirector."""
    
    # Instead of hardcoded: PLOT3D_COLUMNS = ['Xnorm', 'Ynorm', ...]
    columns = get_plot3d_columns()
    
    # Instead of hardcoded: VALID_MARKERS = ['.', 'o', ...]  
    markers = get_valid_markers()
    
    # Instead of manual normalization: l_norm = l_val / 100.0
    l_norm = normalize_lab_l(l_val)
    
    # Instead of scattered conversion logic
    x_norm, y_norm, z_norm = convert_lab_to_normalized(l_val, a_val, b_val, 'plot3d')
    
    # Instead of separate formatting functions
    apply_realtime_formatting(sheet_widget, 'plot3d')
    
    # Integration with existing classes
    # realtime_sheet = RealtimePlot3DSheet(...)
    # replace_hardcoded_columns(realtime_sheet, 'plot3d')


if __name__ == "__main__":
    print("Format Redirector loaded successfully")
    print("Use the redirect functions instead of hardcoded formatting logic")
    print("Examples:")
    print("  get_plot3d_columns() instead of PLOT3D_COLUMNS = [...]")  
    print("  get_valid_markers() instead of VALID_MARKERS = [...]")
    print("  normalize_lab_l(val) instead of val / 100.0")