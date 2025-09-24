#!/usr/bin/env python3
"""
Unified Data State Manager

This module provides the single source of truth for data representation across
all StampZ-III plotting systems (Plot_3D, Ternary, external files, database).

Key Principles:
1. Raw data is stored in database in original L*a*b* format
2. All plotting systems receive data in their expected format via adapters
3. All changes are saved back through unified save logic
4. Format transformations happen only at the adapter layer
5. The data state manager maintains consistency across all views

This eliminates the multiple "sources of truth" problem and ensures that:
- Plot_3D always sees properly normalized (0-1) data
- Ternary always sees data in its expected format
- External files maintain Plot_3D compatibility
- Database preserves original measurement precision
- All views show the same logical data, just transformed appropriately
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class DataFormat(Enum):
    """Supported data formats for transformation."""
    DATABASE = "database"           # Raw L*a*b* values as stored in database
    PLOT3D = "plot3d"              # Normalized 0-1 values for Plot_3D
    TERNARY = "ternary"            # Ternary-specific format
    EXTERNAL_ODS = "external_ods"   # External spreadsheet format
    EXTERNAL_CSV = "external_csv"   # CSV export format


@dataclass
class DataState:
    """Represents the unified data state."""
    # Raw data (as stored in database)
    measurements: List[Dict[str, Any]] = field(default_factory=list)
    centroids: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    sample_set_name: str = ""
    last_updated: datetime = field(default_factory=datetime.now)
    version: int = 1
    
    # Plot preferences (applies to all formats)
    plot_preferences: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Format-specific cached data (for performance)
    _cached_plot3d: Optional[pd.DataFrame] = field(default=None, repr=False)
    _cached_ternary: Optional[pd.DataFrame] = field(default=None, repr=False)
    _cache_valid: bool = field(default=False, repr=False)


class UnifiedDataStateManager:
    """
    Single source of truth for data across all StampZ-III plotting systems.
    
    This manager:
    1. Loads raw data from database
    2. Provides data in any required format via adapters
    3. Handles all save operations consistently
    4. Maintains cache for performance
    5. Ensures all views see the same logical data
    """
    
    def __init__(self, sample_set_name: str):
        self.sample_set_name = sample_set_name
        self.data_state = DataState(sample_set_name=sample_set_name)
        self._lock = threading.RLock()  # Thread safety for concurrent access
        self._change_listeners = []  # Callbacks for data changes
        
        logger.info(f"Initialized UnifiedDataStateManager for '{sample_set_name}'")
    
    # === Core Data Loading ===
    
    def load_from_database(self, force_reload: bool = False) -> bool:
        """
        Load raw data from database into unified state.
        
        Args:
            force_reload: Force reload even if data exists
            
        Returns:
            True if successful
        """
        with self._lock:
            try:
                if self.data_state.measurements and not force_reload:
                    logger.debug("Using cached database data")
                    return True
                
                logger.info(f"Loading raw data from database: {self.sample_set_name}")
                
                from utils.color_analysis_db import ColorAnalysisDB
                db = ColorAnalysisDB(self.sample_set_name)
                
                # Load all measurements (raw L*a*b* values)
                measurements = db.get_all_measurements()
                if not measurements:
                    logger.warning(f"No measurements found in database: {self.sample_set_name}")
                    return False
                
                # Separate regular measurements from centroids
                regular_measurements = [m for m in measurements if m.get('image_name') != 'CENTROIDS']
                centroid_measurements = [m for m in measurements if m.get('image_name') == 'CENTROIDS']
                
                # Store raw data
                self.data_state.measurements = regular_measurements
                self.data_state.centroids = centroid_measurements
                self.data_state.last_updated = datetime.now()
                self.data_state.version += 1
                
                # Load plot preferences
                self._load_plot_preferences(regular_measurements)
                
                # Clear cache to force regeneration
                self._invalidate_cache()
                
                logger.info(f"Loaded {len(regular_measurements)} measurements and {len(centroid_measurements)} centroids")
                return True
                
            except Exception as e:
                logger.error(f"Error loading from database: {e}")
                return False
    
    def _load_plot_preferences(self, measurements: List[Dict[str, Any]]):
        """Load plot preferences (markers, colors, etc.) from measurements."""
        self.data_state.plot_preferences = {}
        
        for measurement in measurements:
            data_id = self._create_data_id(measurement)
            if data_id:
                self.data_state.plot_preferences[data_id] = {
                    'marker': measurement.get('marker_preference', '.'),
                    'color': measurement.get('color_preference', 'blue'),
                    'cluster_id': measurement.get('cluster_id'),
                    'delta_e': measurement.get('delta_e'),
                    'sphere_color': measurement.get('sphere_color'),
                    'sphere_radius': measurement.get('sphere_radius'),
                    'trendline_valid': measurement.get('trendline_valid', True)
                }
    
    # === Format Adapters ===
    
    def get_plot3d_data(self, include_centroids: bool = True) -> pd.DataFrame:
        """
        Get data in Plot_3D format (normalized 0-1 values).
        
        Returns:
            DataFrame with Plot_3D column structure and normalized values
        """
        with self._lock:
            # Use cache if valid
            if self.data_state._cache_valid and self.data_state._cached_plot3d is not None:
                logger.debug("Using cached Plot_3D data")
                return self.data_state._cached_plot3d.copy()
            
            try:
                logger.debug("Generating Plot_3D data from raw measurements")
                
                # Plot_3D column structure
                plot3d_columns = [
                    'Xnorm', 'Ynorm', 'Znorm', 'DataID', 'Cluster', 
                    '∆E', 'Marker', 'Color', 'Centroid_X', 'Centroid_Y', 
                    'Centroid_Z', 'Sphere', 'Radius'
                ]
                
                all_rows = []
                
                # Add centroid rows (rows 1-6 in final structure)
                if include_centroids:
                    centroid_rows = self._generate_centroid_rows()
                    all_rows.extend(centroid_rows)
                
                # Add data rows (rows 7+ in final structure)
                data_rows = self._generate_plot3d_data_rows()
                all_rows.extend(data_rows)
                
                # Create DataFrame
                df = pd.DataFrame(all_rows, columns=plot3d_columns)
                
                # Cache the result
                self.data_state._cached_plot3d = df.copy()
                self.data_state._cache_valid = True
                
                logger.info(f"Generated Plot_3D data: {len(all_rows)} total rows")
                return df.copy()
                
            except Exception as e:
                logger.error(f"Error generating Plot_3D data: {e}")
                return pd.DataFrame()
    
    def get_ternary_data(self) -> pd.DataFrame:
        """
        Get data in Ternary format.
        
        Returns:
            DataFrame with ternary-specific structure
        """
        with self._lock:
            # Use cache if valid
            if self.data_state._cache_valid and self.data_state._cached_ternary is not None:
                logger.debug("Using cached Ternary data")
                return self.data_state._cached_ternary.copy()
            
            try:
                logger.debug("Generating Ternary data from raw measurements")
                
                # Ternary uses same structure as Plot_3D but different normalizations
                ternary_rows = []
                
                for measurement in self.data_state.measurements:
                    if not self._is_measurement_valid(measurement):
                        continue
                    
                    data_id = self._create_data_id(measurement)
                    prefs = self.data_state.plot_preferences.get(data_id, {})
                    
                    # Ternary-specific normalization (different from Plot_3D)
                    l_val = measurement.get('l_value', 0.0)
                    a_val = measurement.get('a_value', 0.0)
                    b_val = measurement.get('b_value', 0.0)
                    
                    # Ternary normalization logic
                    x_norm = max(0.0, min(1.0, l_val / 100.0))
                    y_norm = max(0.0, min(1.0, (a_val + 127.5) / 255.0))
                    z_norm = max(0.0, min(1.0, (b_val + 127.5) / 255.0))
                    
                    row = [
                        round(x_norm, 6),                    # Xnorm
                        round(y_norm, 6),                    # Ynorm  
                        round(z_norm, 6),                    # Znorm
                        data_id,                             # DataID
                        str(prefs.get('cluster_id', '')),    # Cluster
                        str(prefs.get('delta_e', '')),       # ∆E
                        prefs.get('marker', '.'),            # Marker
                        prefs.get('color', 'blue'),          # Color
                        '',                                  # Centroid_X (empty for data rows)
                        '',                                  # Centroid_Y
                        '',                                  # Centroid_Z
                        prefs.get('sphere_color', ''),       # Sphere
                        str(prefs.get('sphere_radius', ''))  # Radius
                    ]
                    ternary_rows.append(row)
                
                # Create DataFrame
                columns = [
                    'Xnorm', 'Ynorm', 'Znorm', 'DataID', 'Cluster', 
                    '∆E', 'Marker', 'Color', 'Centroid_X', 'Centroid_Y', 
                    'Centroid_Z', 'Sphere', 'Radius'
                ]
                df = pd.DataFrame(ternary_rows, columns=columns)
                
                # Cache the result
                self.data_state._cached_ternary = df.copy()
                
                logger.info(f"Generated Ternary data: {len(ternary_rows)} rows")
                return df.copy()
                
            except Exception as e:
                logger.error(f"Error generating Ternary data: {e}")
                return pd.DataFrame()
    
    def get_external_data(self, format_type: DataFormat) -> pd.DataFrame:
        """
        Get data in external file format (ODS, CSV, etc.).
        
        Args:
            format_type: Target format
            
        Returns:
            DataFrame formatted for external files
        """
        with self._lock:
            if format_type in [DataFormat.EXTERNAL_ODS, DataFormat.EXTERNAL_CSV]:
                # External files use Plot_3D format for compatibility
                return self.get_plot3d_data()
            else:
                logger.warning(f"Unsupported external format: {format_type}")
                return pd.DataFrame()
    
    # === Data Generation Helpers ===
    
    def _generate_plot3d_data_rows(self) -> List[List[Any]]:
        """Generate data rows in Plot_3D format."""
        data_rows = []
        
        for measurement in self.data_state.measurements:
            if not self._is_measurement_valid(measurement):
                continue
                
            data_id = self._create_data_id(measurement)
            prefs = self.data_state.plot_preferences.get(data_id, {})
            
            # Plot_3D normalization (0-1 range)
            l_val = measurement.get('l_value', 0.0)
            a_val = measurement.get('a_value', 0.0)
            b_val = measurement.get('b_value', 0.0)
            
            # Normalize L*a*b* to 0-1 for Plot_3D
            x_norm = max(0.0, min(1.0, l_val / 100.0))                      # L*: 0-100 → 0-1
            y_norm = max(0.0, min(1.0, (a_val + 128.0) / 255.0))           # a*: -128 to +127 → 0-1
            z_norm = max(0.0, min(1.0, (b_val + 128.0) / 255.0))           # b*: -128 to +127 → 0-1
            
            row = [
                round(x_norm, 4),                        # Xnorm
                round(y_norm, 4),                        # Ynorm
                round(z_norm, 4),                        # Znorm
                data_id,                                 # DataID
                str(prefs.get('cluster_id', '')),        # Cluster
                str(prefs.get('delta_e', '')),           # ∆E
                prefs.get('marker', '.'),                # Marker
                prefs.get('color', 'blue'),              # Color
                '',                                      # Centroid_X (empty for data rows)
                '',                                      # Centroid_Y
                '',                                      # Centroid_Z
                prefs.get('sphere_color', ''),           # Sphere
                str(prefs.get('sphere_radius', ''))      # Radius
            ]
            data_rows.append(row)
        
        return data_rows
    
    def _generate_centroid_rows(self) -> List[List[Any]]:
        """Generate centroid rows for Plot_3D format."""
        centroid_rows = []
        
        # Create 6 rows (for rows 2-7 in display)
        for i in range(6):
            # Find centroid for this cluster
            centroid = None
            for c in self.data_state.centroids:
                if c.get('cluster_id') == i:
                    centroid = c
                    break
            
            if centroid:
                row = [
                    '',                                      # Xnorm (empty for centroids)
                    '',                                      # Ynorm
                    '',                                      # Znorm
                    '',                                      # DataID (empty for centroids)
                    str(i),                                  # Cluster
                    '',                                      # ∆E (empty)
                    '',                                      # Marker (empty)
                    '',                                      # Color (empty)
                    str(centroid.get('centroid_x', '')),     # Centroid_X
                    str(centroid.get('centroid_y', '')),     # Centroid_Y
                    str(centroid.get('centroid_z', '')),     # Centroid_Z
                    centroid.get('sphere_color', ''),        # Sphere
                    str(centroid.get('sphere_radius', ''))   # Radius
                ]
            else:
                # Empty centroid row
                row = [''] * 13
            
            centroid_rows.append(row)
        
        return centroid_rows
    
    # === Save Operations ===
    
    def save_changes(self, data: pd.DataFrame, source_format: DataFormat) -> bool:
        """
        Save changes back to database through unified logic.
        
        Args:
            data: Modified data in source format
            source_format: Format of the incoming data
            
        Returns:
            True if successful
        """
        with self._lock:
            try:
                logger.info(f"Saving changes from {source_format.value}")
                
                # Convert data back to database format if needed
                normalized_data = self._normalize_incoming_data(data, source_format)
                
                # Update internal state
                self._update_internal_state(normalized_data)
                
                # Save to database
                success = self._save_to_database()
                
                if success:
                    # Invalidate cache to force regeneration
                    self._invalidate_cache()
                    
                    # Notify listeners
                    self._notify_change_listeners()
                    
                    logger.info("Successfully saved changes")
                else:
                    logger.error("Failed to save changes to database")
                
                return success
                
            except Exception as e:
                logger.error(f"Error saving changes: {e}")
                return False
    
    def _normalize_incoming_data(self, data: pd.DataFrame, source_format: DataFormat) -> Dict[str, Any]:
        """Convert incoming data back to database format."""
        normalized = {
            'measurements': [],
            'centroids': [],
            'preferences': {}
        }
        
        for idx, row in data.iterrows():
            data_id = row.get('DataID', '')
            
            if not data_id:
                continue
            
            # Check if this is centroid data
            is_centroid = (row.get('Centroid_X', '') != '' and 
                          row.get('Centroid_Y', '') != '' and 
                          row.get('Centroid_Z', '') != '')
            
            if is_centroid:
                # This is centroid data
                try:
                    cluster_id = int(row.get('Cluster', 0))
                    centroid = {
                        'cluster_id': cluster_id,
                        'centroid_x': float(row.get('Centroid_X', 0)),
                        'centroid_y': float(row.get('Centroid_Y', 0)),
                        'centroid_z': float(row.get('Centroid_Z', 0)),
                        'sphere_color': row.get('Sphere', ''),
                        'sphere_radius': float(row.get('Radius', 0)) if row.get('Radius', '') else None
                    }
                    normalized['centroids'].append(centroid)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing centroid data for cluster {row.get('Cluster')}: {e}")
                    continue
            else:
                # This is measurement data - convert back from normalized values
                try:
                    # Convert normalized values back to L*a*b*
                    if source_format == DataFormat.PLOT3D:
                        l_val = float(row.get('Xnorm', 0)) * 100.0              # 0-1 → 0-100
                        a_val = (float(row.get('Ynorm', 0)) * 255.0) - 128.0    # 0-1 → -128 to +127
                        b_val = (float(row.get('Znorm', 0)) * 255.0) - 128.0    # 0-1 → -128 to +127
                    elif source_format == DataFormat.TERNARY:
                        l_val = float(row.get('Xnorm', 0)) * 100.0              # 0-1 → 0-100
                        a_val = (float(row.get('Ynorm', 0)) * 255.0) - 127.5    # 0-1 → -127.5 to +127.5
                        b_val = (float(row.get('Znorm', 0)) * 255.0) - 127.5    # 0-1 → -127.5 to +127.5
                    else:
                        logger.warning(f"Unsupported source format for conversion: {source_format}")
                        continue
                    
                    # Parse data_id to get image_name and coordinate_point
                    image_name, coord_point = self._parse_data_id(data_id)
                    
                    measurement = {
                        'image_name': image_name,
                        'coordinate_point': coord_point,
                        'l_value': l_val,
                        'a_value': a_val,
                        'b_value': b_val,
                        'data_id': data_id
                    }
                    normalized['measurements'].append(measurement)
                    
                    # Store preferences
                    normalized['preferences'][data_id] = {
                        'marker': row.get('Marker', '.'),
                        'color': row.get('Color', 'blue'),
                        'cluster_id': int(row.get('Cluster')) if row.get('Cluster', '').strip() else None,
                        'delta_e': float(row.get('∆E')) if row.get('∆E', '').strip() else None,
                        'sphere_color': row.get('Sphere', ''),
                        'sphere_radius': float(row.get('Radius')) if row.get('Radius', '').strip() else None
                    }
                    
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing measurement data for {data_id}: {e}")
                    continue
        
        return normalized
    
    def _update_internal_state(self, normalized_data: Dict[str, Any]):
        """Update internal data state with normalized data."""
        # Update measurements and centroids
        # This would involve matching by data_id and updating the corresponding entries
        # in self.data_state.measurements and self.data_state.centroids
        
        # Update plot preferences
        for data_id, prefs in normalized_data.get('preferences', {}).items():
            if data_id not in self.data_state.plot_preferences:
                self.data_state.plot_preferences[data_id] = {}
            self.data_state.plot_preferences[data_id].update(prefs)
        
        # Update version
        self.data_state.version += 1
        self.data_state.last_updated = datetime.now()
    
    def _save_to_database(self) -> bool:
        """Save current state back to database."""
        try:
            from utils.color_analysis_db import ColorAnalysisDB
            db = ColorAnalysisDB(self.sample_set_name)
            
            # Save measurements with updated preferences
            success_count = 0
            for measurement in self.data_state.measurements:
                data_id = self._create_data_id(measurement)
                prefs = self.data_state.plot_preferences.get(data_id, {})
                
                # Update measurement with preferences
                updated_measurement = measurement.copy()
                updated_measurement.update({
                    'marker_preference': prefs.get('marker', '.'),
                    'color_preference': prefs.get('color', 'blue'),
                    'cluster_id': prefs.get('cluster_id'),
                    'delta_e': prefs.get('delta_e'),
                    'sphere_color': prefs.get('sphere_color'),
                    'sphere_radius': prefs.get('sphere_radius'),
                    'trendline_valid': prefs.get('trendline_valid', True)
                })
                
                # Save to database
                success = db.update_measurement_plot_data(
                    image_name=measurement['image_name'],
                    coordinate_point=measurement['coordinate_point'],
                    **{k: v for k, v in updated_measurement.items() 
                       if k not in ['image_name', 'coordinate_point']}
                )
                
                if success:
                    success_count += 1
            
            # Save centroids
            for centroid in self.data_state.centroids:
                success = db.insert_or_update_centroid_data(**centroid)
                if success:
                    success_count += 1
            
            logger.info(f"Saved {success_count} items to database")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            return False
    
    # === Utility Methods ===
    
    def _invalidate_cache(self):
        """Invalidate all cached data."""
        self.data_state._cached_plot3d = None
        self.data_state._cached_ternary = None
        self.data_state._cache_valid = False
    
    def _is_measurement_valid(self, measurement: Dict[str, Any]) -> bool:
        """Check if measurement should be included in output."""
        # Skip measurements that were intentionally deleted
        if measurement.get('trendline_valid') is False:
            return False
        return True
    
    def _create_data_id(self, measurement: Dict[str, Any]) -> str:
        """Create consistent DataID from measurement."""
        image_name = measurement.get('image_name', '')
        coord_point = measurement.get('coordinate_point', 1)
        
        if coord_point > 1 or '_pt' in image_name:
            return f"{image_name}_pt{coord_point}"
        return image_name
    
    def _parse_data_id(self, data_id: str) -> Tuple[str, int]:
        """Parse DataID back to image_name and coordinate_point."""
        if '_pt' in data_id:
            parts = data_id.rsplit('_pt', 1)
            try:
                return parts[0], int(parts[1])
            except (IndexError, ValueError):
                return data_id, 1
        return data_id, 1
    
    def add_change_listener(self, callback):
        """Add listener for data changes."""
        self._change_listeners.append(callback)
    
    def _notify_change_listeners(self):
        """Notify all change listeners."""
        for callback in self._change_listeners:
            try:
                callback(self.data_state)
            except Exception as e:
                logger.warning(f"Error in change listener: {e}")


# === Global Manager Registry ===

_manager_registry = {}

def get_unified_data_manager(sample_set_name: str) -> UnifiedDataStateManager:
    """
    Get or create unified data manager for a sample set.
    
    Args:
        sample_set_name: Name of the sample set
        
    Returns:
        UnifiedDataStateManager instance
    """
    if sample_set_name not in _manager_registry:
        _manager_registry[sample_set_name] = UnifiedDataStateManager(sample_set_name)
    
    return _manager_registry[sample_set_name]


def clear_manager_cache(sample_set_name: str = None):
    """
    Clear manager cache.
    
    Args:
        sample_set_name: Specific sample set to clear, or None for all
    """
    if sample_set_name:
        if sample_set_name in _manager_registry:
            _manager_registry[sample_set_name]._invalidate_cache()
    else:
        for manager in _manager_registry.values():
            manager._invalidate_cache()


# === Usage Examples ===

def example_usage():
    """Example of how to use the unified data state manager."""
    
    # Get manager for a sample set
    manager = get_unified_data_manager("138_averages")
    
    # Load from database
    manager.load_from_database()
    
    # Get data in different formats
    plot3d_data = manager.get_plot3d_data()
    ternary_data = manager.get_ternary_data()
    external_data = manager.get_external_data(DataFormat.EXTERNAL_ODS)
    
    # Make changes to plot3d_data...
    # ... modify DataFrame ...
    
    # Save changes back
    manager.save_changes(plot3d_data, DataFormat.PLOT3D)


if __name__ == "__main__":
    print("Unified Data State Manager loaded successfully")
    print("Use get_unified_data_manager(sample_set_name) to get a manager instance")