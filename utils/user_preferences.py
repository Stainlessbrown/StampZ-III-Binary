#!/usr/bin/env python3
"""
User preferences system for StampZ
Manages user-configurable settings like export locations.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class ExportPreferences:
    """Preferences for file exports."""
    ods_export_directory: str = ""  # Empty means use default
    auto_open_after_export: bool = True
    export_filename_format: str = "{sample_set}_{date}"  # Template for filename
    include_timestamp: bool = False  # Whether to include timestamp in filename
    preferred_export_format: str = "ods"  # Preferred export format: 'ods', 'xlsx', or 'csv'
    export_normalized_values: bool = False  # Export color values normalized to 0.0-1.0 range
    export_include_rgb: bool = True  # Include RGB color values in export
    export_include_lab: bool = True  # Include L*a*b* color values in export
    export_include_cmy: bool = False  # Include CMY color values in export


@dataclass
class FileDialogPreferences:
    """Preferences for file dialogs."""
    last_image_directory: str = ""  # Last directory used for image files (open and save)
    remember_directories: bool = True  # Whether to remember last used directories


@dataclass
class ColorLibraryPreferences:
    """Preferences for color library system."""
    default_library: str = "basic_colors"  # Default color library to use
    hide_non_selected_standards: bool = False  # Hide non-selected standard values in Compare and Libraries


@dataclass
class SampleAreaPreferences:
    """Preferences for default sample area settings."""
    default_shape: str = "circle"  # Default shape: "circle" or "rectangle"
    default_width: int = 10  # Default width/diameter in pixels
    default_height: int = 10  # Default height in pixels (same as width for circles)
    default_anchor: str = "center"  # Default anchor position
    max_samples: int = 6  # Maximum number of sample markers (1-6)
    save_individual_default: bool = True  # Save individual samples by default
    save_average_default: bool = True  # Save calculated average by default
    default_database_name: str = "ColorAnalysis"  # Default database name for analysis
    use_averages_suffix: bool = True  # Automatically add _AVG suffix to average database
    enable_quick_save: bool = False  # Skip database selection dialog and use preferences directly
    default_template: str = ""  # Default template file name (empty means no default)


@dataclass
class CompareModePreferences:
    """Preferences for Compare mode behavior."""
    auto_save_averages: bool = False  # Automatically save averages to database


@dataclass
class MeasurementPreferences:
    """Preferences for measurement features (perforation, centering, etc.)."""
    default_dpi: int = 600  # Default DPI for measurements
    perforation_measurement_enabled: bool = True  # Enable perforation measurement feature
    default_background_color: str = 'black'  # Default scan background color


@dataclass
class WorkspaceConfig:
    """Configuration for a single workspace."""
    databases: List[str] = None  # List of active database filenames
    libraries: List[str] = None  # List of active library filenames
    templates: List[str] = None  # List of active template filenames
    
    def __post_init__(self):
        if self.databases is None:
            self.databases = []
        if self.libraries is None:
            self.libraries = []
        if self.templates is None:
            self.templates = []


@dataclass
class WorkspacePreferences:
    """Preferences for workspace management."""
    workspaces: Dict[str, Any] = None  # Named workspace configurations (name -> WorkspaceConfig dict)
    active_workspace: str = ""  # Currently active workspace name (empty = "All Resources")
    
    def __post_init__(self):
        if self.workspaces is None:
            self.workspaces = {}


# InterfacePreferences class removed - complexity levels no longer used
@dataclass 
class UserPreferences:
    """Main user preferences container."""
    export_prefs: ExportPreferences
    file_dialog_prefs: FileDialogPreferences
    color_library_prefs: ColorLibraryPreferences
    sample_area_prefs: SampleAreaPreferences
    compare_mode_prefs: CompareModePreferences
    measurement_prefs: MeasurementPreferences
    workspace_prefs: WorkspacePreferences
    # interface_prefs removed - complexity levels no longer used
    
    def __init__(self):
        self.export_prefs = ExportPreferences()
        self.file_dialog_prefs = FileDialogPreferences()
        self.color_library_prefs = ColorLibraryPreferences()
        self.sample_area_prefs = SampleAreaPreferences()
        self.compare_mode_prefs = CompareModePreferences()
        self.measurement_prefs = MeasurementPreferences()
        self.workspace_prefs = WorkspacePreferences()
        # self.interface_prefs removed - complexity levels no longer used


class PreferencesManager:
    """Manages user preferences with persistent storage."""
    
    def __init__(self):
        self.preferences = UserPreferences()
        self.prefs_file = self._get_preferences_file_path()
        self.load_preferences()
    
    def _get_preferences_file_path(self) -> Path:
        """Get the path to the preferences file."""
        # Use the same user data directory as other app data
        from .path_utils import get_base_data_dir
        
        base_dir = Path(get_base_data_dir()).parent  # Go up one level from /data
        prefs_file = base_dir / "preferences.json"
        
        return prefs_file
    
    def _get_default_export_directory(self) -> str:
        """Get the default export directory."""
        # Default to user's Desktop/StampZ Exports directory
        desktop = Path.home() / "Desktop"
        if desktop.exists():
            default_dir = desktop / "StampZ Exports"
        else:
            # Fallback to Documents if Desktop doesn't exist
            documents = Path.home() / "Documents" 
            default_dir = documents / "StampZ Exports"
        
        return str(default_dir)
    
    def get_export_directory(self) -> str:
        """Get the current export directory, creating it if needed."""
        export_dir = self.preferences.export_prefs.ods_export_directory
        
        if not export_dir:
            # Use default if not set
            export_dir = self._get_default_export_directory()
            
        # Ensure directory exists
        Path(export_dir).mkdir(parents=True, exist_ok=True)
        
        return export_dir
    
    def set_export_directory(self, directory: str) -> bool:
        """Set the export directory."""
        try:
            # Validate that the directory exists or can be created
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
            
            # Update preferences
            self.preferences.export_prefs.ods_export_directory = str(path)
            self.save_preferences()
            
            return True
        except Exception as e:
            print(f"Error setting export directory: {e}")
            return False
    
    def get_last_image_directory(self) -> Optional[str]:
        """Get the last directory used for image files."""
        if not self.preferences.file_dialog_prefs.remember_directories:
            return None
            
        last_dir = self.preferences.file_dialog_prefs.last_image_directory
        if last_dir and Path(last_dir).exists():
            return last_dir
        return None
    
    # Backwards compatibility aliases
    def get_last_open_directory(self) -> Optional[str]:
        """Get the last directory used for opening files (alias for get_last_image_directory)."""
        return self.get_last_image_directory()
    
    def set_last_image_directory(self, directory: str) -> bool:
        """Set the last directory used for image files."""
        if not self.preferences.file_dialog_prefs.remember_directories:
            return True  # Don't save if remembering is disabled
            
        try:
            path = Path(directory)
            if path.is_file():
                # If it's a file, get the parent directory
                directory = str(path.parent)
            
            self.preferences.file_dialog_prefs.last_image_directory = directory
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting last image directory: {e}")
            return False
    
    # Backwards compatibility aliases
    def set_last_open_directory(self, directory: str) -> bool:
        """Set the last directory used for opening files (alias for set_last_image_directory)."""
        return self.set_last_image_directory(directory)
    
    def get_last_save_directory(self) -> Optional[str]:
        """Get the last directory used for saving files (alias for get_last_image_directory)."""
        return self.get_last_image_directory()
    
    def set_last_save_directory(self, directory: str) -> bool:
        """Set the last directory used for saving files (alias for set_last_image_directory)."""
        return self.set_last_image_directory(directory)
    
    def get_remember_directories(self) -> bool:
        """Get whether to remember last used directories."""
        return self.preferences.file_dialog_prefs.remember_directories
    
    def set_remember_directories(self, remember: bool) -> bool:
        """Set whether to remember last used directories."""
        try:
            self.preferences.file_dialog_prefs.remember_directories = remember
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting remember directories preference: {e}")
            return False
    
    def get_preferred_export_format(self) -> str:
        """Get the preferred export format."""
        return self.preferences.export_prefs.preferred_export_format
    
    def set_preferred_export_format(self, format_type: str) -> bool:
        """Set the preferred export format.
        
        Args:
            format_type: Export format ('ods', 'xlsx', or 'csv')
        """
        if format_type not in ['ods', 'xlsx', 'csv']:
            print(f"Error: Invalid export format '{format_type}'. Use 'ods', 'xlsx', or 'csv'.")
            return False
        
        try:
            self.preferences.export_prefs.preferred_export_format = format_type
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting preferred export format: {e}")
            return False
    
    def get_export_normalized_values(self) -> bool:
        """Get whether to export color values normalized to 0.0-1.0 range."""
        return self.preferences.export_prefs.export_normalized_values
    
    def set_export_normalized_values(self, normalized: bool) -> bool:
        """Set whether to export color values normalized to 0.0-1.0 range.
        
        Args:
            normalized: True to export normalized values (0.0-1.0), False for standard ranges
        """
        try:
            self.preferences.export_prefs.export_normalized_values = normalized
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting normalized export preference: {e}")
            return False
    
    def get_export_include_rgb(self) -> bool:
        """Get whether to include RGB color values in exports."""
        return self.preferences.export_prefs.export_include_rgb
    
    def set_export_include_rgb(self, include_rgb: bool) -> bool:
        """Set whether to include RGB color values in exports.
        
        Args:
            include_rgb: True to include RGB values, False to exclude them
        """
        try:
            # Ensure at least one color space is always included
            if not include_rgb and not self.preferences.export_prefs.export_include_lab and not self.preferences.export_prefs.export_include_cmy:
                print("Error: At least one color space (RGB, L*a*b*, or CMY) must be included in exports")
                return False
            
            self.preferences.export_prefs.export_include_rgb = include_rgb
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting RGB export preference: {e}")
            return False
    
    def get_export_include_lab(self) -> bool:
        """Get whether to include L*a*b* color values in exports."""
        return self.preferences.export_prefs.export_include_lab
    
    def set_export_include_lab(self, include_lab: bool) -> bool:
        """Set whether to include L*a*b* color values in exports.
        
        Args:
            include_lab: True to include L*a*b* values, False to exclude them
        """
        try:
            # Ensure at least one color space is always included
            if not include_lab and not self.preferences.export_prefs.export_include_rgb and not self.preferences.export_prefs.export_include_cmy:
                print("Error: At least one color space (RGB, L*a*b*, or CMY) must be included in exports")
                return False
            
            self.preferences.export_prefs.export_include_lab = include_lab
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting L*a*b* export preference: {e}")
            return False
    
    def get_export_include_cmy(self) -> bool:
        """Get whether to include CMY color values in exports."""
        return self.preferences.export_prefs.export_include_cmy
    
    def set_export_include_cmy(self, include_cmy: bool) -> bool:
        """Set whether to include CMY color values in exports.
        
        Args:
            include_cmy: True to include CMY values, False to exclude them
        """
        try:
            # Ensure at least one color space is always included
            if not include_cmy and not self.preferences.export_prefs.export_include_rgb and not self.preferences.export_prefs.export_include_lab:
                print("Error: At least one color space (RGB, L*a*b*, or CMY) must be included in exports")
                return False
            
            self.preferences.export_prefs.export_include_cmy = include_cmy
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting CMY export preference: {e}")
            return False
    
    def get_default_color_library(self) -> str:
        """Get the default color library."""
        return self.preferences.color_library_prefs.default_library
    
    def set_default_color_library(self, library_name: str) -> bool:
        """Set the default color library.
        
        Args:
            library_name: Name of the color library to set as default
        """
        try:
            self.preferences.color_library_prefs.default_library = library_name
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting default color library: {e}")
            return False
    
    def get_hide_non_selected_standards(self) -> bool:
        """Get whether to hide non-selected standard values in Compare and Libraries."""
        return self.preferences.color_library_prefs.hide_non_selected_standards
    
    def set_hide_non_selected_standards(self, hide: bool) -> bool:
        """Set whether to hide non-selected standard values in Compare and Libraries.
        
        Args:
            hide: True to hide non-selected values, False to show all values
        """
        try:
            self.preferences.color_library_prefs.hide_non_selected_standards = hide
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting hide non-selected standards preference: {e}")
            return False
    
    def get_available_color_libraries(self) -> List[str]:
        """Get a list of available color libraries."""
        try:
            from .path_utils import get_color_libraries_dir
            library_dir = get_color_libraries_dir()
            
            # Ensure library directory exists
            os.makedirs(library_dir, exist_ok=True)
            
            # Get all library files
            library_files = [f for f in os.listdir(library_dir) if f.endswith("_library.db")]
            
            # Always include basic_colors if not found
            if "basic_colors_library.db" not in library_files:
                library_files.append("basic_colors_library.db")
            
            # Convert to library names (remove "_library.db" suffix)
            library_names = [f[:-11] for f in library_files]
            
            return sorted(library_names)
        except Exception as e:
            print(f"Error getting available color libraries: {e}")
            return ["basic_colors"]
    
    # Interface mode methods removed - complexity levels no longer used
    
    def get_default_sample_shape(self) -> str:
        """Get the default sample area shape."""
        return self.preferences.sample_area_prefs.default_shape
    
    def set_default_sample_shape(self, shape: str) -> bool:
        """Set the default sample area shape.
        
        Args:
            shape: Shape type ('circle' or 'rectangle')
        """
        if shape not in ['circle', 'rectangle']:
            print(f"Error: Invalid shape '{shape}'. Use 'circle' or 'rectangle'.")
            return False
        
        try:
            self.preferences.sample_area_prefs.default_shape = shape
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting default sample shape: {e}")
            return False
    
    def get_default_sample_width(self) -> int:
        """Get the default sample area width/diameter."""
        return self.preferences.sample_area_prefs.default_width
    
    def set_default_sample_width(self, width: int) -> bool:
        """Set the default sample area width/diameter.
        
        Args:
            width: Width in pixels (must be positive)
        """
        if width <= 0:
            print(f"Error: Width must be positive, got {width}")
            return False
        
        try:
            self.preferences.sample_area_prefs.default_width = width
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting default sample width: {e}")
            return False
    
    def get_default_sample_height(self) -> int:
        """Get the default sample area height."""
        return self.preferences.sample_area_prefs.default_height
    
    def set_default_sample_height(self, height: int) -> bool:
        """Set the default sample area height.
        
        Args:
            height: Height in pixels (must be positive)
        """
        if height <= 0:
            print(f"Error: Height must be positive, got {height}")
            return False
        
        try:
            self.preferences.sample_area_prefs.default_height = height
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting default sample height: {e}")
            return False
    
    def get_default_sample_anchor(self) -> str:
        """Get the default sample area anchor position."""
        return self.preferences.sample_area_prefs.default_anchor
    
    def set_default_sample_anchor(self, anchor: str) -> bool:
        """Set the default sample area anchor position.
        
        Args:
            anchor: Anchor position ('center', 'top_left', 'top_right', 'bottom_left', 'bottom_right')
        """
        valid_anchors = ['center', 'top_left', 'top_right', 'bottom_left', 'bottom_right']
        if anchor not in valid_anchors:
            print(f"Error: Invalid anchor '{anchor}'. Use one of: {', '.join(valid_anchors)}")
            return False
        
        try:
            self.preferences.sample_area_prefs.default_anchor = anchor
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting default sample anchor: {e}")
            return False
    
    def get_max_samples(self) -> int:
        """Get the maximum number of sample markers."""
        return self.preferences.sample_area_prefs.max_samples
    
    def set_max_samples(self, max_samples: int) -> bool:
        """Set the maximum number of sample markers.
        
        Args:
            max_samples: Maximum samples (1-6)
        """
        if not 1 <= max_samples <= 6:
            print(f"Error: Max samples must be between 1 and 6, got {max_samples}")
            return False
        
        try:
            self.preferences.sample_area_prefs.max_samples = max_samples
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting max samples: {e}")
            return False
    
    def get_default_sample_settings(self) -> dict:
        """Get all default sample area settings as a dictionary."""
        return {
            'shape': self.preferences.sample_area_prefs.default_shape,
            'width': self.preferences.sample_area_prefs.default_width,
            'height': self.preferences.sample_area_prefs.default_height,
            'anchor': self.preferences.sample_area_prefs.default_anchor,
            'max_samples': self.preferences.sample_area_prefs.max_samples
        }
    
    def get_save_individual_default(self) -> bool:
        """Get whether to save individual samples by default."""
        return self.preferences.sample_area_prefs.save_individual_default
    
    def set_save_individual_default(self, save_individual: bool) -> bool:
        """Set whether to save individual samples by default.
        
        Args:
            save_individual: True to save individual samples by default
        """
        try:
            self.preferences.sample_area_prefs.save_individual_default = save_individual
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting save individual default: {e}")
            return False
    
    def get_save_average_default(self) -> bool:
        """Get whether to save averaged results by default."""
        return self.preferences.sample_area_prefs.save_average_default
    
    def set_save_average_default(self, save_average: bool) -> bool:
        """Set whether to save averaged results by default.
        
        Args:
            save_average: True to save averaged results by default
        """
        try:
            self.preferences.sample_area_prefs.save_average_default = save_average
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting save average default: {e}")
            return False
    
    def get_default_database_name(self) -> str:
        """Get the default database name for analysis."""
        return self.preferences.sample_area_prefs.default_database_name
    
    def set_default_database_name(self, database_name: str) -> bool:
        """Set the default database name for analysis.
        
        Args:
            database_name: Default database name (without .db extension)
        """
        try:
            # Clean the name (remove .db extension if present)
            if database_name.endswith('.db'):
                database_name = database_name[:-3]
            
            self.preferences.sample_area_prefs.default_database_name = database_name
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting default database name: {e}")
            return False
    
    def get_use_averages_suffix(self) -> bool:
        """Get whether to automatically add _AVG suffix to average database."""
        return self.preferences.sample_area_prefs.use_averages_suffix
    
    def set_use_averages_suffix(self, use_suffix: bool) -> bool:
        """Set whether to automatically add _AVG suffix to average database.
        
        Args:
            use_suffix: True to add _AVG suffix automatically
        """
        try:
            self.preferences.sample_area_prefs.use_averages_suffix = use_suffix
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting averages suffix preference: {e}")
            return False
    
    def get_enable_quick_save(self) -> bool:
        """Get whether to enable quick save (skip database dialog)."""
        return self.preferences.sample_area_prefs.enable_quick_save
    
    def set_enable_quick_save(self, enable: bool) -> bool:
        """Set whether to enable quick save (skip database dialog).
        
        Args:
            enable: True to skip database selection dialog and use preferences
        """
        try:
            self.preferences.sample_area_prefs.enable_quick_save = enable
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting quick save preference: {e}")
            return False
    
    def get_default_template(self) -> str:
        """Get the default template filename.
        
        Returns:
            Default template filename (empty string means no default)
        """
        return self.preferences.sample_area_prefs.default_template
    
    def set_default_template(self, template_name: str) -> bool:
        """Set the default template filename.
        
        Args:
            template_name: Template filename (e.g., '6markers.json') or empty string for no default
        """
        try:
            self.preferences.sample_area_prefs.default_template = template_name
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting default template: {e}")
            return False
    
    def get_auto_save_averages(self) -> bool:
        """Get whether to automatically save averages to database in Compare mode."""
        return self.preferences.compare_mode_prefs.auto_save_averages
    
    def set_auto_save_averages(self, auto_save: bool) -> bool:
        """Set whether to automatically save averages to database in Compare mode.
        
        Args:
            auto_save: True to automatically save averages, False to require manual saving
        """
        try:
            self.preferences.compare_mode_prefs.auto_save_averages = auto_save
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting auto save averages preference: {e}")
            return False
    
    def get_default_dpi(self) -> int:
        """Get the default DPI setting for measurements."""
        return self.preferences.measurement_prefs.default_dpi
    
    def set_default_dpi(self, dpi: int) -> bool:
        """Set the default DPI setting for measurements.
        
        Args:
            dpi: DPI value (typically 400, 600, 800, 1200, etc.)
        """
        try:
            if dpi < 72 or dpi > 2400:
                raise ValueError("DPI must be between 72 and 2400")
            
            self.preferences.measurement_prefs.default_dpi = dpi
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting default DPI: {e}")
            return False
    
    def get_perforation_measurement_enabled(self) -> bool:
        """Get whether perforation measurement is enabled."""
        return self.preferences.measurement_prefs.perforation_measurement_enabled
    
    def set_perforation_measurement_enabled(self, enabled: bool) -> bool:
        """Set whether perforation measurement is enabled."""
        try:
            self.preferences.measurement_prefs.perforation_measurement_enabled = enabled
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting perforation measurement enabled: {e}")
            return False
    
    def get_default_background_color(self) -> str:
        """Get the default background color for measurements."""
        return self.preferences.measurement_prefs.default_background_color
    
    def set_default_background_color(self, bg_color: str) -> bool:
        """Set the default background color for measurements.
        
        Args:
            bg_color: 'black', 'dark_gray', 'white', or 'light_gray'
        """
        try:
            valid_colors = ['black', 'dark_gray', 'white', 'light_gray']
            if bg_color not in valid_colors:
                raise ValueError(f"Background color must be one of: {valid_colors}")
            
            self.preferences.measurement_prefs.default_background_color = bg_color
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting default background color: {e}")
            return False
    
    # ==================== Workspace Management Methods ====================
    
    def get_workspaces(self) -> Dict[str, Any]:
        """Get all workspace configurations.
        
        Returns:
            Dictionary mapping workspace names to their configurations
        """
        return self.preferences.workspace_prefs.workspaces.copy()
    
    def get_active_workspace(self) -> str:
        """Get the currently active workspace name.
        
        Returns:
            Active workspace name, or empty string for 'All Resources' mode
        """
        return self.preferences.workspace_prefs.active_workspace
    
    def set_active_workspace(self, name: str) -> bool:
        """Set the active workspace.
        
        Args:
            name: Workspace name, or empty string for 'All Resources' mode
            
        Returns:
            True if successful
        """
        try:
            # Allow empty string (All Resources mode) or valid workspace name
            if name and name not in self.preferences.workspace_prefs.workspaces:
                print(f"Error: Workspace '{name}' does not exist")
                return False
            
            self.preferences.workspace_prefs.active_workspace = name
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error setting active workspace: {e}")
            return False
    
    def create_workspace(self, name: str, databases: List[str] = None, 
                         libraries: List[str] = None, templates: List[str] = None) -> bool:
        """Create a new workspace.
        
        Args:
            name: Workspace name (must be unique)
            databases: List of database filenames to include
            libraries: List of library filenames to include
            templates: List of template filenames to include
            
        Returns:
            True if successful
        """
        try:
            if not name or not name.strip():
                print("Error: Workspace name cannot be empty")
                return False
            
            name = name.strip()
            if name in self.preferences.workspace_prefs.workspaces:
                print(f"Error: Workspace '{name}' already exists")
                return False
            
            # Create workspace config as a dictionary (for JSON serialization)
            config = {
                'databases': databases or [],
                'libraries': libraries or [],
                'templates': templates or []
            }
            
            self.preferences.workspace_prefs.workspaces[name] = config
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error creating workspace: {e}")
            return False
    
    def delete_workspace(self, name: str) -> bool:
        """Delete a workspace.
        
        Args:
            name: Workspace name to delete
            
        Returns:
            True if successful
        """
        try:
            if name not in self.preferences.workspace_prefs.workspaces:
                print(f"Error: Workspace '{name}' does not exist")
                return False
            
            # If deleting the active workspace, switch to All Resources
            if self.preferences.workspace_prefs.active_workspace == name:
                self.preferences.workspace_prefs.active_workspace = ""
            
            del self.preferences.workspace_prefs.workspaces[name]
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error deleting workspace: {e}")
            return False
    
    def update_workspace(self, name: str, databases: List[str] = None,
                         libraries: List[str] = None, templates: List[str] = None) -> bool:
        """Update a workspace configuration.
        
        Args:
            name: Workspace name to update
            databases: New list of database filenames (None to keep existing)
            libraries: New list of library filenames (None to keep existing)
            templates: New list of template filenames (None to keep existing)
            
        Returns:
            True if successful
        """
        try:
            if name not in self.preferences.workspace_prefs.workspaces:
                print(f"Error: Workspace '{name}' does not exist")
                return False
            
            config = self.preferences.workspace_prefs.workspaces[name]
            
            if databases is not None:
                config['databases'] = databases
            if libraries is not None:
                config['libraries'] = libraries
            if templates is not None:
                config['templates'] = templates
            
            self.save_preferences()
            return True
        except Exception as e:
            print(f"Error updating workspace: {e}")
            return False
    
    def get_workspace_config(self, name: str) -> Optional[Dict[str, List[str]]]:
        """Get configuration for a specific workspace.
        
        Args:
            name: Workspace name
            
        Returns:
            Workspace config dict or None if not found
        """
        return self.preferences.workspace_prefs.workspaces.get(name)
    
    def get_available_databases(self) -> List[str]:
        """Get all available database files from the color_analysis directory.
        
        Returns:
            List of database filenames (without path)
        """
        try:
            from .path_utils import get_color_analysis_dir
            analysis_dir = get_color_analysis_dir()
            
            if not os.path.exists(analysis_dir):
                return []
            
            # Get all .db files, excluding system files
            databases = []
            for f in os.listdir(analysis_dir):
                if f.endswith('.db') and not f.startswith('.'):
                    databases.append(f)
            
            return sorted(databases)
        except Exception as e:
            print(f"Error getting available databases: {e}")
            return []
    
    def get_available_libraries(self) -> List[str]:
        """Get all available library files from the color_libraries directory.
        
        Returns:
            List of library filenames (without path)
        """
        try:
            from .path_utils import get_color_libraries_dir
            library_dir = get_color_libraries_dir()
            
            if not os.path.exists(library_dir):
                return []
            
            # Get all *_library.db files
            libraries = []
            for f in os.listdir(library_dir):
                if f.endswith('_library.db') and not f.startswith('.'):
                    libraries.append(f)
            
            return sorted(libraries)
        except Exception as e:
            print(f"Error getting available libraries: {e}")
            return []
    
    def get_available_templates(self) -> List[str]:
        """Get all available sampling templates from coordinates.db.
        
        Returns:
            List of template names (coordinate sets)
        """
        try:
            import sqlite3
            from .path_utils import get_base_data_dir
            
            db_path = os.path.join(get_base_data_dir(), "coordinates.db")
            
            if not os.path.exists(db_path):
                return []
            
            templates = []
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                # Get template names, excluding temporary/manual mode templates
                cursor.execute("""
                    SELECT DISTINCT cs.name
                    FROM coordinate_sets cs
                    WHERE NOT EXISTS (
                        SELECT 1 FROM coordinates c 
                        WHERE c.set_id = cs.id AND c.temporary = 1
                    )
                    ORDER BY cs.name
                """)
                templates = [row[0] for row in cursor.fetchall() if row[0]]
            
            return sorted(templates)
        except Exception as e:
            print(f"Error getting available templates: {e}")
            return []
    
    def get_active_databases(self) -> List[str]:
        """Get databases active in the current workspace.
        
        Returns:
            List of active database filenames, or all databases if no workspace is active
        """
        active_ws = self.preferences.workspace_prefs.active_workspace
        
        if not active_ws:  # All Resources mode
            return self.get_available_databases()
        
        config = self.preferences.workspace_prefs.workspaces.get(active_ws)
        if config:
            # Return only databases that still exist
            available = set(self.get_available_databases())
            return [db for db in config.get('databases', []) if db in available]
        
        return self.get_available_databases()
    
    def get_active_libraries(self) -> List[str]:
        """Get libraries active in the current workspace.
        
        Returns:
            List of active library filenames, or all libraries if no workspace is active
        """
        active_ws = self.preferences.workspace_prefs.active_workspace
        
        if not active_ws:  # All Resources mode
            return self.get_available_libraries()
        
        config = self.preferences.workspace_prefs.workspaces.get(active_ws)
        if config:
            # Return only libraries that still exist
            available = set(self.get_available_libraries())
            return [lib for lib in config.get('libraries', []) if lib in available]
        
        return self.get_available_libraries()
    
    def get_active_templates(self) -> List[str]:
        """Get templates active in the current workspace.
        
        Returns:
            List of active template filenames, or all templates if no workspace is active
        """
        active_ws = self.preferences.workspace_prefs.active_workspace
        
        if not active_ws:  # All Resources mode
            return self.get_available_templates()
        
        config = self.preferences.workspace_prefs.workspaces.get(active_ws)
        if config:
            # Return only templates that still exist
            available = set(self.get_available_templates())
            return [tpl for tpl in config.get('templates', []) if tpl in available]
        
        return self.get_available_templates()
    
    # ==================== End Workspace Methods ====================
    
    def get_export_filename(self, sample_set_name: str = None, extension: str = ".ods") -> str:
        """Generate export filename based on preferences."""
        from datetime import datetime
        
        # Get template and preferences
        template = self.preferences.export_prefs.export_filename_format
        include_timestamp = self.preferences.export_prefs.include_timestamp
        
        # Prepare template variables
        variables = {
            "sample_set": sample_set_name or "color_analysis",
            "date": datetime.now().strftime("%Y%m%d"),
            "datetime": datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        
        # Format the filename
        try:
            filename = template.format(**variables)
        except (KeyError, ValueError):
            # Fallback to simple format if template fails
            filename = f"{variables['sample_set']}_{variables['date']}"
        
        # Add timestamp if requested
        if include_timestamp:
            timestamp = datetime.now().strftime("_%H%M%S")
            filename += timestamp
            
        return filename + extension
    
    def load_preferences(self) -> bool:
        """Load preferences from file."""
        try:
            if self.prefs_file.exists():
                with open(self.prefs_file, 'r') as f:
                    data = json.load(f)
                
                # Load export preferences
                if 'export_prefs' in data:
                    export_data = data['export_prefs']
                    self.preferences.export_prefs = ExportPreferences(
                        ods_export_directory=export_data.get('ods_export_directory', ''),
                        auto_open_after_export=export_data.get('auto_open_after_export', True),
                        export_filename_format=export_data.get('export_filename_format', '{sample_set}_{date}'),
                        include_timestamp=export_data.get('include_timestamp', False),
                        preferred_export_format=export_data.get('preferred_export_format', 'ods'),
                        export_normalized_values=export_data.get('export_normalized_values', False),
                        export_include_rgb=export_data.get('export_include_rgb', True),
                        export_include_lab=export_data.get('export_include_lab', True),
                        export_include_cmy=export_data.get('export_include_cmy', False)
                    )
                
                # Load file dialog preferences
                if 'file_dialog_prefs' in data:
                    dialog_data = data['file_dialog_prefs']
                    # Handle migration from old dual-directory system
                    last_image_dir = dialog_data.get('last_image_directory', '')
                    if not last_image_dir:
                        # Migrate: prefer last_open_directory if it exists
                        last_image_dir = dialog_data.get('last_open_directory', dialog_data.get('last_save_directory', ''))
                    
                    self.preferences.file_dialog_prefs = FileDialogPreferences(
                        last_image_directory=last_image_dir,
                        remember_directories=dialog_data.get('remember_directories', True)
                    )
                
                # Load color library preferences
                if 'color_library_prefs' in data:
                    library_data = data['color_library_prefs']
                    self.preferences.color_library_prefs = ColorLibraryPreferences(
                        default_library=library_data.get('default_library', 'basic_colors'),
                        hide_non_selected_standards=library_data.get('hide_non_selected_standards', False)
                    )
                
                # Load sample area preferences
                if 'sample_area_prefs' in data:
                    sample_data = data['sample_area_prefs']
                    self.preferences.sample_area_prefs = SampleAreaPreferences(
                        default_shape=sample_data.get('default_shape', 'circle'),
                        default_width=sample_data.get('default_width', 10),
                        default_height=sample_data.get('default_height', 10),
                        default_anchor=sample_data.get('default_anchor', 'center'),
                        max_samples=sample_data.get('max_samples', 6),
                        save_individual_default=sample_data.get('save_individual_default', True),
                        save_average_default=sample_data.get('save_average_default', True),
                        default_database_name=sample_data.get('default_database_name', 'ColorAnalysis'),
                        use_averages_suffix=sample_data.get('use_averages_suffix', True),
                        enable_quick_save=sample_data.get('enable_quick_save', False),
                        default_template=sample_data.get('default_template', '')
                    )
                
                # Load compare mode preferences
                if 'compare_mode_prefs' in data:
                    compare_data = data['compare_mode_prefs']
                    self.preferences.compare_mode_prefs = CompareModePreferences(
                        auto_save_averages=compare_data.get('auto_save_averages', False)
                    )
                
                # Load measurement preferences
                if 'measurement_prefs' in data:
                    measurement_data = data['measurement_prefs']
                    self.preferences.measurement_prefs = MeasurementPreferences(
                        default_dpi=measurement_data.get('default_dpi', 600),
                        perforation_measurement_enabled=measurement_data.get('perforation_measurement_enabled', True),
                        default_background_color=measurement_data.get('default_background_color', 'black')
                    )
                
                # Load workspace preferences
                if 'workspace_prefs' in data:
                    workspace_data = data['workspace_prefs']
                    self.preferences.workspace_prefs = WorkspacePreferences(
                        workspaces=workspace_data.get('workspaces', {}),
                        active_workspace=workspace_data.get('active_workspace', '')
                    )
                
                # Interface preferences removed - complexity levels no longer used
                
                print(f"Loaded preferences from {self.prefs_file}")
                return True
        except Exception as e:
            print(f"Error loading preferences: {e}")
            
        # Use defaults if loading failed
        self.preferences = UserPreferences()
        return False
    
    def save_preferences(self) -> bool:
        """Save preferences to file, preserving any existing data."""
        try:
            # Ensure the preferences directory exists
            self.prefs_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing preferences to preserve other sections
            existing_data = {}
            if self.prefs_file.exists():
                try:
                    with open(self.prefs_file, 'r') as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    # If file is corrupted, start fresh but preserve structure
                    existing_data = {}
            
            # Update only the preferences we manage, preserving everything else
            existing_data.update({
                'export_prefs': asdict(self.preferences.export_prefs),
                'file_dialog_prefs': asdict(self.preferences.file_dialog_prefs),
                'color_library_prefs': asdict(self.preferences.color_library_prefs),
                'sample_area_prefs': asdict(self.preferences.sample_area_prefs),
                'compare_mode_prefs': asdict(self.preferences.compare_mode_prefs),
                'measurement_prefs': asdict(self.preferences.measurement_prefs),
                'workspace_prefs': asdict(self.preferences.workspace_prefs),
                # 'interface_prefs': removed - complexity levels no longer used
            })
            
            with open(self.prefs_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
                
            print(f"Saved preferences to {self.prefs_file}")
            return True
        except Exception as e:
            print(f"Error saving preferences: {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """Reset all preferences to defaults."""
        self.preferences = UserPreferences()
        return self.save_preferences()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a custom preference value.
        
        Args:
            key: Preference key
            default: Default value if key doesn't exist
            
        Returns:
            Preference value or default
        """
        try:
            if self.prefs_file.exists():
                with open(self.prefs_file, 'r') as f:
                    data = json.load(f)
                    return data.get(key, default)
        except Exception as e:
            print(f"Error getting preference '{key}': {e}")
        return default
    
    def set(self, key: str, value: Any) -> bool:
        """Set a custom preference value.
        
        Args:
            key: Preference key
            value: Value to set
            
        Returns:
            True if successful
        """
        try:
            # Load existing data
            existing_data = {}
            if self.prefs_file.exists():
                with open(self.prefs_file, 'r') as f:
                    existing_data = json.load(f)
            
            # Set the custom key
            existing_data[key] = value
            
            # Save back
            self.prefs_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.prefs_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error setting preference '{key}': {e}")
            return False
    
    def get_preferences_summary(self) -> Dict[str, Any]:
        """Get a summary of current preferences."""
        return {
            'Export Directory': self.get_export_directory(),
            'Auto-open after export': self.preferences.export_prefs.auto_open_after_export,
            'Filename format': self.preferences.export_prefs.export_filename_format,
            'Include timestamp': self.preferences.export_prefs.include_timestamp,
            'Preferences file': str(self.prefs_file)
        }


# Global instance for easy access
_prefs_manager = None

def get_preferences_manager() -> PreferencesManager:
    """Get the global preferences manager instance."""
    global _prefs_manager
    if _prefs_manager is None:
        _prefs_manager = PreferencesManager()
    return _prefs_manager


def get_export_directory() -> str:
    """Convenience function to get current export directory."""
    return get_preferences_manager().get_export_directory()


def set_export_directory(directory: str) -> bool:
    """Convenience function to set export directory."""
    return get_preferences_manager().set_export_directory(directory)


# Interface mode convenience functions removed - complexity levels no longer used
