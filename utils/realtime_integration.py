#!/usr/bin/env python3
"""
Realtime Sheet Integration with Data File Manager

This module provides simple integration functions to connect the existing
RealtimePlot3DSheet with the new DataFileManager, ensuring consistent
formatting and behavior across all data formats.

Usage:
    # In your existing realtime sheet initialization:
    from utils.realtime_integration import integrate_with_data_file_manager
    integrate_with_data_file_manager(realtime_sheet_instance)
"""

import logging
from typing import Any, List, Optional
from utils.data_file_manager import get_data_file_manager, DataFormat, apply_realtime_formatting

logger = logging.getLogger(__name__)


def integrate_with_data_file_manager(realtime_sheet, format_type: str = 'plot3d'):
    """
    Integrate an existing RealtimePlot3DSheet with the DataFileManager.
    
    This replaces the sheet's formatting methods with centralized ones,
    ensuring consistency across all formats.
    
    Args:
        realtime_sheet: The RealtimePlot3DSheet instance to integrate
        format_type: 'plot3d' or 'ternary' format
    """
    try:
        logger.info(f"Integrating realtime sheet with DataFileManager ({format_type})")
        
        # Store reference to data file manager
        realtime_sheet._data_file_manager = get_data_file_manager()
        realtime_sheet._format_type = format_type
        
        # Replace formatting methods with centralized ones
        original_apply_formatting = getattr(realtime_sheet, '_apply_formatting', None)
        original_setup_validation = getattr(realtime_sheet, '_setup_validation', None)
        
        def unified_apply_formatting():
            """Unified formatting method using DataFileManager."""
            try:
                logger.debug("Applying unified formatting...")
                apply_realtime_formatting(realtime_sheet.sheet, format_type)
                logger.debug("Unified formatting applied successfully")
            except Exception as e:
                logger.error(f"Error in unified formatting: {e}")
                # Fallback to original if available
                if original_apply_formatting:
                    logger.debug("Falling back to original formatting...")
                    original_apply_formatting()
        
        def unified_setup_validation():
            """Unified validation setup using DataFileManager."""
            try:
                logger.debug("Setting up unified validation...")
                # The apply_realtime_formatting already includes validation setup
                # so this can be a no-op or just call the formatting
                pass
            except Exception as e:
                logger.error(f"Error in unified validation setup: {e}")
                # Fallback to original if available
                if original_setup_validation:
                    logger.debug("Falling back to original validation setup...")
                    original_setup_validation()
        
        # Replace the methods
        realtime_sheet._apply_formatting = unified_apply_formatting
        realtime_sheet._setup_validation = unified_setup_validation
        
        # Add helper methods
        def get_unified_validation_lists():
            """Get validation lists from DataFileManager."""
            data_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
            return realtime_sheet._data_file_manager.get_validation_lists(data_format)
        
        def get_unified_columns():
            """Get column list from DataFileManager."""
            data_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
            return realtime_sheet._data_file_manager.get_columns(data_format)
        
        def standardize_sheet_data(data, source_format_name='database'):
            """Standardize data using DataFileManager."""
            source_format = DataFormat.DATABASE if source_format_name == 'database' else DataFormat.PLOT3D
            target_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
            return realtime_sheet._data_file_manager.standardize_data(data, source_format, target_format)
        
        # Add helper methods to the sheet instance
        realtime_sheet.get_unified_validation_lists = get_unified_validation_lists
        realtime_sheet.get_unified_columns = get_unified_columns  
        realtime_sheet.standardize_sheet_data = standardize_sheet_data
        
        # Update the PLOT3D_COLUMNS to match DataFileManager
        if hasattr(realtime_sheet, 'PLOT3D_COLUMNS'):
            unified_columns = get_unified_columns()
            realtime_sheet.PLOT3D_COLUMNS = unified_columns
            logger.debug(f"Updated PLOT3D_COLUMNS to: {unified_columns}")
        
        # Update validation lists to match DataFileManager
        if hasattr(realtime_sheet, 'VALID_MARKERS'):
            validation_lists = get_unified_validation_lists()
            realtime_sheet.VALID_MARKERS = validation_lists.get('Marker', realtime_sheet.VALID_MARKERS)
            realtime_sheet.VALID_COLORS = validation_lists.get('Color', realtime_sheet.VALID_COLORS)
            if hasattr(realtime_sheet, 'VALID_SPHERES'):
                realtime_sheet.VALID_SPHERES = validation_lists.get('Sphere', realtime_sheet.VALID_SPHERES)
            logger.debug("Updated validation lists from DataFileManager")
        
        logger.info("Successfully integrated realtime sheet with DataFileManager")
        return True
        
    except Exception as e:
        logger.error(f"Error integrating realtime sheet with DataFileManager: {e}")
        return False


def create_unified_external_file(file_path: str, realtime_sheet, format_type: str = 'plot3d') -> bool:
    """
    Create an external file using the current realtime sheet data with unified formatting.
    
    Args:
        file_path: Path where to save the external file
        realtime_sheet: The RealtimePlot3DSheet instance
        format_type: 'plot3d' or 'ternary' format
        
    Returns:
        True if successful
    """
    try:
        logger.info(f"Creating unified external file: {file_path}")
        
        # Get current sheet data
        sheet_data = realtime_sheet.sheet.get_sheet_data(get_header=False)
        
        # Convert to DataFrame using unified columns
        if hasattr(realtime_sheet, 'get_unified_columns'):
            columns = realtime_sheet.get_unified_columns()
        else:
            # Fallback to integration
            integrate_with_data_file_manager(realtime_sheet, format_type)
            columns = realtime_sheet.get_unified_columns()
        
        import pandas as pd
        if sheet_data:
            df = pd.DataFrame(sheet_data, columns=columns)
        else:
            df = pd.DataFrame(columns=columns)
        
        # Use DataFileManager to create the file
        manager = get_data_file_manager()
        data_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
        
        success = manager.create_external_file(file_path, df, data_format)
        
        if success:
            logger.info(f"Successfully created unified external file: {file_path}")
        else:
            logger.error(f"Failed to create unified external file: {file_path}")
            
        return success
        
    except Exception as e:
        logger.error(f"Error creating unified external file: {e}")
        return False


def load_from_unified_external_file(file_path: str, realtime_sheet, format_type: str = 'plot3d') -> bool:
    """
    Load data from an external file into the realtime sheet using unified formatting.
    
    Args:
        file_path: Path of the file to load
        realtime_sheet: The RealtimePlot3DSheet instance
        format_type: 'plot3d' or 'ternary' format
        
    Returns:
        True if successful
    """
    try:
        logger.info(f"Loading data from unified external file: {file_path}")
        
        # Use DataFileManager to read the file
        manager = get_data_file_manager()
        data_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
        
        df = manager.read_external_file(file_path, data_format)
        
        if df is not None:
            # Convert DataFrame to sheet format
            sheet_data = df.values.tolist()
            
            # Clear existing data
            current_rows = realtime_sheet.sheet.get_total_rows()
            if current_rows > 0:
                realtime_sheet.sheet.delete_rows(0, current_rows)
            
            # Insert new data
            if sheet_data:
                realtime_sheet.sheet.insert_rows(rows=sheet_data, idx=0)
            
            # Apply unified formatting
            if hasattr(realtime_sheet, '_apply_formatting'):
                realtime_sheet._apply_formatting()
            
            logger.info(f"Successfully loaded {len(sheet_data)} rows from unified external file")
            return True
        else:
            logger.error("Failed to read data from external file")
            return False
            
    except Exception as e:
        logger.error(f"Error loading from unified external file: {e}")
        return False


def validate_realtime_sheet_data(realtime_sheet, format_type: str = 'plot3d') -> dict:
    """
    Validate the current realtime sheet data using unified validation rules.
    
    Args:
        realtime_sheet: The RealtimePlot3DSheet instance  
        format_type: 'plot3d' or 'ternary' format
        
    Returns:
        Dictionary of validation errors
    """
    try:
        # Get current sheet data
        sheet_data = realtime_sheet.sheet.get_sheet_data(get_header=False)
        
        # Convert to DataFrame
        if hasattr(realtime_sheet, 'get_unified_columns'):
            columns = realtime_sheet.get_unified_columns()
        else:
            integrate_with_data_file_manager(realtime_sheet, format_type)
            columns = realtime_sheet.get_unified_columns()
        
        import pandas as pd
        if sheet_data:
            df = pd.DataFrame(sheet_data, columns=columns)
        else:
            df = pd.DataFrame(columns=columns)
        
        # Use DataFileManager to validate
        manager = get_data_file_manager()
        data_format = DataFormat.PLOT3D if format_type == 'plot3d' else DataFormat.TERNARY
        
        errors = manager.validate_data(df, data_format)
        
        logger.info(f"Validated realtime sheet data: {len(errors)} error types found")
        return errors
        
    except Exception as e:
        logger.error(f"Error validating realtime sheet data: {e}")
        return {'validation_error': [str(e)]}


# === Convenience Functions for Easy Integration ===

def fix_realtime_sheet_formatting(realtime_sheet):
    """
    Quick fix for realtime sheet formatting issues.
    
    Call this if you're having formatting problems with an existing sheet.
    """
    try:
        logger.info("Applying quick formatting fix...")
        integrate_with_data_file_manager(realtime_sheet)
        realtime_sheet._apply_formatting()
        logger.info("Quick formatting fix applied successfully")
        return True
    except Exception as e:
        logger.error(f"Error in quick formatting fix: {e}")
        return False


def sync_validation_lists(realtime_sheet):
    """
    Sync validation lists to ensure consistency.
    
    Call this if dropdowns are showing incorrect values.
    """
    try:
        logger.info("Syncing validation lists...")
        integrate_with_data_file_manager(realtime_sheet)
        
        validation_lists = realtime_sheet.get_unified_validation_lists()
        logger.info(f"Synced validation lists: {list(validation_lists.keys())}")
        
        return validation_lists
    except Exception as e:
        logger.error(f"Error syncing validation lists: {e}")
        return {}


# === Usage Examples ===

def example_integration():
    """Example of how to integrate with existing code."""
    
    # Example 1: Integrate existing realtime sheet
    # realtime_sheet = RealtimePlot3DSheet(parent, "sample_set_name")
    # integrate_with_data_file_manager(realtime_sheet, 'plot3d')
    
    # Example 2: Quick formatting fix
    # fix_realtime_sheet_formatting(realtime_sheet)
    
    # Example 3: Create external file with unified formatting  
    # create_unified_external_file("/path/to/output.ods", realtime_sheet, 'plot3d')
    
    # Example 4: Load from external file
    # load_from_unified_external_file("/path/to/input.ods", realtime_sheet, 'plot3d')
    
    # Example 5: Validate current data
    # errors = validate_realtime_sheet_data(realtime_sheet, 'plot3d')
    # if errors:
    #     print("Validation errors found:", errors)
    
    pass


if __name__ == "__main__":
    # Test the integration functions
    print("Realtime Integration module loaded successfully")
    print("Use integrate_with_data_file_manager(realtime_sheet) to enable unified formatting")