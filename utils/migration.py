#!/usr/bin/env python3
"""
Migration utility for upgrading from StampZ, StampZ_II to StampZ-III
Handles one-time data migration for existing users.
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class StampZMigration:
    """Handles migration from StampZ, StampZ_II to StampZ-III data directories."""
    
    def __init__(self):
        """Initialize migration utility."""
        self.old_base_dir = self._get_old_stampz_dir()
        self.old_base_dir_ii = self._get_old_stampz_ii_dir()
        self.new_base_dir = self._get_new_stampz_dir()
        
    def _get_old_stampz_dir(self) -> Optional[Path]:
        """Get the old StampZ directory path."""
        if sys.platform == 'darwin':
            return Path.home() / 'Library' / 'Application Support' / 'StampZ'
        elif sys.platform.startswith('linux'):
            return Path.home() / '.local' / 'share' / 'StampZ'
        elif sys.platform.startswith('win'):
            return Path.home() / 'AppData' / 'Roaming' / 'StampZ'
        return None
    
    def _get_old_stampz_ii_dir(self) -> Optional[Path]:
        """Get the old StampZ_II directory path."""
        if sys.platform == 'darwin':
            return Path.home() / 'Library' / 'Application Support' / 'StampZ_II'
        elif sys.platform.startswith('linux'):
            return Path.home() / '.local' / 'share' / 'StampZ_II'
        elif sys.platform.startswith('win'):
            return Path.home() / 'AppData' / 'Roaming' / 'StampZ_II'
        return None
    
    def _get_new_stampz_dir(self) -> Optional[Path]:
        """Get the new StampZ-III directory path using same logic as main app."""
        try:
            # Import here to avoid circular imports
            from utils.path_utils import get_base_data_dir
            # Get the base data directory and go up one level to get the main StampZ-III dir
            base_data_dir = Path(get_base_data_dir())
            return base_data_dir.parent
        except ImportError:
            # Fallback to original logic if path_utils not available
            if sys.platform == 'darwin':
                return Path.home() / 'Library' / 'Application Support' / 'StampZ-III'
            elif sys.platform.startswith('linux'):
                return Path.home() / '.local' / 'share' / 'StampZ-III'
            elif sys.platform.startswith('win'):
                return Path.home() / 'AppData' / 'Roaming' / 'StampZ-III'
            return None
    
    def is_migration_needed(self) -> bool:
        """Check if migration is needed (old directories exist but migration hasn't been done)."""
        # Check if either old directory exists
        has_old_data = (self.old_base_dir and self.old_base_dir.exists()) or (self.old_base_dir_ii and self.old_base_dir_ii.exists())
        if not has_old_data:
            return False
            
        # Check if migration has already been completed
        migration_marker = self.new_base_dir / '.migration_completed' if self.new_base_dir else None
        if migration_marker and migration_marker.exists():
            return False
            
        # Check if there's actually data to migrate
        return self._has_data_to_migrate()
    
    def _has_data_to_migrate(self) -> bool:
        """Check if there's actually data worth migrating in the old directories."""
        # Check both old StampZ and StampZ_II directories
        for old_dir in [self.old_base_dir, self.old_base_dir_ii]:
            if not old_dir or not old_dir.exists():
                continue
                
            # Look for database files that indicate actual usage
            data_indicators = [
                old_dir / 'coordinates.db',
                old_dir / 'data' / 'coordinates.db',
                old_dir / 'data' / 'color_analysis',
                old_dir / 'data' / 'color_libraries'
            ]
            
            for indicator in data_indicators:
                if indicator.exists():
                    if indicator.is_file():
                        return True
                    elif indicator.is_dir() and any(indicator.iterdir()):
                        return True
        return False
    
    def get_migration_summary(self) -> Dict[str, any]:
        """Get a summary of what would be migrated."""
        summary = {
            'color_libraries': [],
            'color_analysis': [],
            'coordinates': [],
            'total_files': 0,
            'total_size_mb': 0
        }
        
        # Check both old directories for migration data
        old_dirs = []
        if self.old_base_dir and self.old_base_dir.exists():
            old_dirs.append(self.old_base_dir)
        if self.old_base_dir_ii and self.old_base_dir_ii.exists():
            old_dirs.append(self.old_base_dir_ii)
            
        if not old_dirs:
            return summary
            
        # Process each old directory
        for old_dir in old_dirs:
            # Find color libraries
            color_lib_dir = old_dir / 'data' / 'color_libraries'
            if color_lib_dir.exists():
                for lib_file in color_lib_dir.glob('*_library.db'):
                    lib_name = lib_file.stem.replace('_library', '')
                    size_mb = lib_file.stat().st_size / (1024 * 1024)
                    # Check if this library is already in the summary
                    existing = next((lib for lib in summary['color_libraries'] if lib['name'] == lib_name), None)
                    if not existing:
                        summary['color_libraries'].append({
                            'name': lib_name,
                            'size_mb': round(size_mb, 2)
                        })
                        summary['total_files'] += 1
                        summary['total_size_mb'] += size_mb
            
            # Find color analysis databases
            color_analysis_dir = old_dir / 'data' / 'color_analysis'
            if color_analysis_dir.exists():
                for analysis_file in color_analysis_dir.glob('*.db'):
                    analysis_name = analysis_file.stem
                    size_mb = analysis_file.stat().st_size / (1024 * 1024)
                    # Check if this analysis is already in the summary
                    existing = next((analysis for analysis in summary['color_analysis'] if analysis['name'] == analysis_name), None)
                    if not existing:
                        summary['color_analysis'].append({
                            'name': analysis_name,
                            'size_mb': round(size_mb, 2)
                        })
                        summary['total_files'] += 1
                        summary['total_size_mb'] += size_mb
            
            # Find coordinate databases
            coord_files = [
                old_dir / 'coordinates.db',
                old_dir / 'data' / 'coordinates.db'
            ]
            for coord_file in coord_files:
                if coord_file.exists():
                    size_mb = coord_file.stat().st_size / (1024 * 1024)
                    rel_path = str(coord_file.relative_to(old_dir))
                    # Check if this coordinate file is already in the summary
                    existing = next((coord for coord in summary['coordinates'] if coord['path'] == rel_path), None)
                    if not existing:
                        summary['coordinates'].append({
                            'path': rel_path,
                            'size_mb': round(size_mb, 2)
                        })
                        summary['total_files'] += 1
                        summary['total_size_mb'] += size_mb
        
        summary['total_size_mb'] = round(summary['total_size_mb'], 2)
        return summary
    
    def perform_migration(self, create_backup: bool = True) -> Tuple[bool, str]:
        """Perform the migration from StampZ, StampZ_II to StampZ-III.
        
        Args:
            create_backup: Whether to create a backup of the old directories
            
        Returns:
            Tuple of (success, message)
        """
        if not self.new_base_dir:
            return False, "Cannot determine system directories"
            
        # Check if we have at least one old directory
        old_dirs = []
        if self.old_base_dir and self.old_base_dir.exists():
            old_dirs.append(self.old_base_dir)
        if self.old_base_dir_ii and self.old_base_dir_ii.exists():
            old_dirs.append(self.old_base_dir_ii)
            
        if not old_dirs:
            return False, "No old StampZ directories exist"
            
        try:
            # Create backups if requested
            backup_paths = []
            if create_backup:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                for i, old_dir in enumerate(old_dirs):
                    backup_name = f'StampZ_backup_{timestamp}' if i == 0 else f'StampZ_II_backup_{timestamp}'
                    backup_path = old_dir.parent / backup_name
                    logger.info(f"Creating backup at: {backup_path}")
                    shutil.copytree(old_dir, backup_path)
                    backup_paths.append(backup_path)
            
            # Ensure new directory structure exists
            self.new_base_dir.mkdir(parents=True, exist_ok=True)
            (self.new_base_dir / 'data').mkdir(exist_ok=True)
            (self.new_base_dir / 'data' / 'color_libraries').mkdir(exist_ok=True)
            (self.new_base_dir / 'data' / 'color_analysis').mkdir(exist_ok=True)
            
            migrated_files = []
            
            # Process each old directory for migration
            for old_dir in old_dirs:
                # Migrate color libraries
                old_lib_dir = old_dir / 'data' / 'color_libraries'
                new_lib_dir = self.new_base_dir / 'data' / 'color_libraries'
                if old_lib_dir.exists():
                    for lib_file in old_lib_dir.glob('*_library.db'):
                        dest_file = new_lib_dir / lib_file.name
                        should_copy = False
                        
                        if not dest_file.exists():
                            # File doesn't exist, copy it
                            should_copy = True
                        else:
                            # File exists, but check if current source has more data
                            try:
                                import sqlite3
                                # Check source library color count
                                source_count = 0
                                with sqlite3.connect(lib_file) as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT COUNT(*) FROM library_colors")
                                    source_count = cursor.fetchone()[0]
                                
                                # Check destination library color count
                                dest_count = 0
                                with sqlite3.connect(dest_file) as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT COUNT(*) FROM library_colors")
                                    dest_count = cursor.fetchone()[0]
                                
                                # Copy if source has more colors than destination
                                if source_count > dest_count:
                                    should_copy = True
                                    logger.info(f"Replacing {lib_file.name}: source has {source_count} colors vs existing {dest_count}")
                                    
                            except Exception as e:
                                logger.warning(f"Could not compare library sizes for {lib_file.name}: {e}")
                                # If we can't compare, don't overwrite existing file
                                should_copy = False
                        
                        if should_copy:
                            shutil.copy2(lib_file, dest_file)
                            migrated_files.append(f"Library: {lib_file.stem.replace('_library', '')}")
                            logger.info(f"Migrated library: {lib_file.name}")
                
                # Migrate color analysis
                old_analysis_dir = old_dir / 'data' / 'color_analysis'
                new_analysis_dir = self.new_base_dir / 'data' / 'color_analysis'
                if old_analysis_dir.exists():
                    for analysis_file in old_analysis_dir.glob('*.db'):
                        dest_file = new_analysis_dir / analysis_file.name
                        if not dest_file.exists():  # Don't overwrite existing files
                            shutil.copy2(analysis_file, dest_file)
                            migrated_files.append(f"Analysis: {analysis_file.stem}")
                            logger.info(f"Migrated analysis: {analysis_file.name}")
                
                # Migrate coordinate databases (only if new one doesn't exist)
                new_coord_file = self.new_base_dir / 'coordinates.db'
                if not new_coord_file.exists():
                    # Try both possible locations for old coordinates
                    old_coord_files = [
                        old_dir / 'coordinates.db',
                        old_dir / 'data' / 'coordinates.db'
                    ]
                    
                    for old_coord_file in old_coord_files:
                        if old_coord_file.exists():
                            shutil.copy2(old_coord_file, new_coord_file)
                            migrated_files.append("Coordinate templates")
                            logger.info(f"Migrated coordinates: {old_coord_file}")
                            break  # Only migrate the first one found
                
                # Migrate recent files
                old_recent_dir = old_dir / 'recent'
                new_recent_dir = self.new_base_dir / 'recent'
                if old_recent_dir.exists():
                    new_recent_dir.mkdir(exist_ok=True)
                    recent_files_migrated = 0
                    for recent_file in old_recent_dir.glob('*'):
                        if recent_file.is_file():
                            dest_file = new_recent_dir / recent_file.name
                            if not dest_file.exists():  # Don't overwrite existing files
                                shutil.copy2(recent_file, dest_file)
                                recent_files_migrated += 1
                                logger.info(f"Migrated recent file: {recent_file.name}")
                    if recent_files_migrated > 0:
                        migrated_files.append(f"Recent files ({recent_files_migrated} files)")
                
                # Migrate exports directory
                old_exports_dir = old_dir / 'exports'
                new_exports_dir = self.new_base_dir / 'exports'
                if old_exports_dir.exists():
                    new_exports_dir.mkdir(exist_ok=True)
                    exported_files_migrated = 0
                    for export_file in old_exports_dir.glob('*'):
                        if export_file.is_file():
                            dest_file = new_exports_dir / export_file.name
                            if not dest_file.exists():  # Don't overwrite existing files
                                shutil.copy2(export_file, dest_file)
                                exported_files_migrated += 1
                                logger.info(f"Migrated export file: {export_file.name}")
                    if exported_files_migrated > 0:
                        migrated_files.append(f"Export files ({exported_files_migrated} files)")
                
                # Migrate preferences.json
                old_prefs_file = old_dir / 'preferences.json'
                new_prefs_file = self.new_base_dir / 'preferences.json'
                if old_prefs_file.exists() and not new_prefs_file.exists():
                    shutil.copy2(old_prefs_file, new_prefs_file)
                    migrated_files.append("User preferences")
                    logger.info(f"Migrated preferences: {old_prefs_file}")
            
            # Create migration completion marker
            marker_file = self.new_base_dir / '.migration_completed'
            with marker_file.open('w') as f:
                f.write(f"Migration completed: {datetime.now().isoformat()}\n")
                f.write(f"Migrated files: {len(migrated_files)}\n")
                f.write(f"Backup created: {'Yes' if backup_path else 'No'}\n")
                if backup_path:
                    f.write(f"Backup location: {backup_path}\n")
                for item in migrated_files:
                    f.write(f"- {item}\n")
            
            # Create success message
            message_parts = [f"Successfully migrated {len(migrated_files)} items to StampZ-III:"]
            message_parts.extend([f"• {item}" for item in migrated_files])
            
            if backup_paths:
                message_parts.append(f"\nBackups created at:")
                for backup_path in backup_paths:
                    message_parts.append(f"• {backup_path}")
            
            message_parts.append(f"\nYour old StampZ directories remain unchanged.")
            message_parts.append(f"StampZ-III will now use the migrated data exclusively.")
            
            return True, '\n'.join(message_parts)
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False, f"Migration failed: {str(e)}"
    
    def is_migration_completed(self) -> bool:
        """Check if migration has already been completed."""
        if not self.new_base_dir:
            return False
        marker_file = self.new_base_dir / '.migration_completed'
        return marker_file.exists()
    
    def get_migration_info(self) -> Optional[Dict[str, str]]:
        """Get information about a completed migration."""
        if not self.is_migration_completed():
            return None
            
        marker_file = self.new_base_dir / '.migration_completed'
        info = {}
        
        try:
            with marker_file.open('r') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.strip().split(':', 1)
                        info[key.strip()] = value.strip()
        except Exception as e:
            logger.error(f"Error reading migration info: {e}")
            
        return info
