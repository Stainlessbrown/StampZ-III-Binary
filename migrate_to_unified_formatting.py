#!/usr/bin/env python3
"""
Migration Script for Unified Formatting

This script helps migrate existing files to use the format_redirector.py instead
of scattered hardcoded formatting logic.

USAGE:
1. Run this script to see which files need updating
2. Apply the suggested changes to each file
3. Test that everything works consistently

This provides a clear migration path from the current scattered approach
to the unified formatting system.
"""

import os
import re
import logging
from typing import List, Dict, Set, Tuple

logger = logging.getLogger(__name__)

# Files that contain formatting logic to be migrated
TARGET_FILES = [
    "gui/realtime_plot3d_sheet.py",
    "gui/ternary_export.py", 
    "gui/ternary_datasheet.py",
    "utils/ods_exporter.py",
    "utils/rigid_plot3d_templates.py",
    "plot3d/Plot_3D.py",
    "utils/worksheet_manager.py",
    "utils/plot3d_integration.py"
]

# Patterns to find and replace
MIGRATION_PATTERNS = {
    # Column definitions
    'PLOT3D_COLUMNS': {
        'pattern': r'PLOT3D_COLUMNS\s*=\s*\[[\s\S]*?\]',
        'replacement': 'from utils.format_redirector import get_plot3d_columns\n    # PLOT3D_COLUMNS = get_plot3d_columns()  # Use this instead of hardcoded list',
        'import_needed': 'from utils.format_redirector import get_plot3d_columns'
    },
    
    'TERNARY_COLUMNS': {
        'pattern': r'TERNARY_COLUMNS\s*=\s*\[[\s\S]*?\]',
        'replacement': 'from utils.format_redirector import get_ternary_columns\n    # TERNARY_COLUMNS = get_ternary_columns()  # Use this instead of hardcoded list',
        'import_needed': 'from utils.format_redirector import get_ternary_columns'
    },
    
    # Validation lists
    'VALID_MARKERS': {
        'pattern': r'VALID_MARKERS\s*=\s*\[[\s\S]*?\]',
        'replacement': 'from utils.format_redirector import get_valid_markers\n    # VALID_MARKERS = get_valid_markers()  # Use this instead of hardcoded list',
        'import_needed': 'from utils.format_redirector import get_valid_markers'
    },
    
    'VALID_COLORS': {
        'pattern': r'VALID_COLORS\s*=\s*\[[\s\S]*?\]',
        'replacement': 'from utils.format_redirector import get_valid_colors\n    # VALID_COLORS = get_valid_colors()  # Use this instead of hardcoded list',
        'import_needed': 'from utils.format_redirector import get_valid_colors'
    },
    
    'VALID_SPHERES': {
        'pattern': r'VALID_SPHERES\s*=\s*\[[\s\S]*?\]',
        'replacement': 'from utils.format_redirector import get_valid_spheres\n    # VALID_SPHERES = get_valid_spheres()  # Use this instead of hardcoded list',
        'import_needed': 'from utils.format_redirector import get_valid_spheres'
    },
    
    # Normalization functions
    'lab_l_normalization': {
        'pattern': r'(\w+)\s*/\s*100\.0',
        'replacement': 'normalize_lab_l(\\1)',
        'import_needed': 'from utils.format_redirector import normalize_lab_l'
    },
    
    'lab_a_normalization': {
        'pattern': r'\(\s*(\w+)\s*\+\s*128\.0\s*\)\s*/\s*255\.0',
        'replacement': 'normalize_lab_a(\\1, "plot3d")',
        'import_needed': 'from utils.format_redirector import normalize_lab_a'
    },
    
    'lab_b_normalization': {
        'pattern': r'\(\s*(\w+)\s*\+\s*128\.0\s*\)\s*/\s*255\.0',
        'replacement': 'normalize_lab_b(\\1, "plot3d")',
        'import_needed': 'from utils.format_redirector import normalize_lab_b'
    }
}


class FormattingMigrator:
    """Helps migrate files to use unified formatting."""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.issues_found = []
        self.migration_suggestions = []
    
    def analyze_files(self) -> Dict[str, List[str]]:
        """
        Analyze files to find formatting issues.
        
        Returns:
            Dictionary mapping file paths to lists of issues found
        """
        issues = {}
        
        for file_path in TARGET_FILES:
            full_path = os.path.join(self.project_root, file_path)
            
            if os.path.exists(full_path):
                file_issues = self._analyze_file(full_path, file_path)
                if file_issues:
                    issues[file_path] = file_issues
            else:
                print(f"⚠️ File not found: {file_path}")
        
        return issues
    
    def _analyze_file(self, full_path: str, relative_path: str) -> List[str]:
        """Analyze a single file for formatting issues."""
        issues = []
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for hardcoded column definitions
            if re.search(r'PLOT3D_COLUMNS\s*=\s*\[', content):
                issues.append("❌ Hardcoded PLOT3D_COLUMNS definition found")
            
            if re.search(r'TERNARY_COLUMNS\s*=\s*\[', content):
                issues.append("❌ Hardcoded TERNARY_COLUMNS definition found")
            
            # Check for validation lists
            if re.search(r'VALID_MARKERS\s*=\s*\[', content):
                issues.append("❌ Hardcoded VALID_MARKERS definition found")
            
            if re.search(r'VALID_COLORS\s*=\s*\[', content):
                issues.append("❌ Hardcoded VALID_COLORS definition found")
            
            if re.search(r'VALID_SPHERES\s*=\s*\[', content):
                issues.append("❌ Hardcoded VALID_SPHERES definition found")
            
            # Check for manual normalization
            if re.search(r'\w+\s*/\s*100\.0', content):
                issues.append("❌ Manual L* normalization found (should use normalize_lab_l())")
            
            if re.search(r'\(\s*\w+\s*\+\s*128\.0\s*\)\s*/\s*255\.0', content):
                issues.append("❌ Manual a*/b* normalization found (should use normalize_lab_a/b())")
            
            if re.search(r'\(\s*\w+\s*\+\s*127\.5\s*\)\s*/\s*255\.0', content):
                issues.append("❌ Manual ternary normalization found (should use normalize_lab_a/b(val, 'ternary'))")
            
            # Check for format imports
            if 'from utils.format_redirector import' not in content:
                if issues:  # Only suggest import if there are issues to fix
                    issues.append("✅ Add: from utils.format_redirector import [needed functions]")
        
        except Exception as e:
            issues.append(f"❌ Error reading file: {e}")
        
        return issues
    
    def generate_migration_suggestions(self, issues: Dict[str, List[str]]) -> List[str]:
        """Generate specific migration suggestions."""
        suggestions = []
        
        if not issues:
            suggestions.append("🎉 No formatting issues found! All files are using unified formatting.")
            return suggestions
        
        suggestions.append("📋 MIGRATION PLAN:")
        suggestions.append("=" * 50)
        
        for file_path, file_issues in issues.items():
            suggestions.append(f"\n📁 {file_path}")
            suggestions.append("-" * 30)
            
            for issue in file_issues:
                suggestions.append(f"  {issue}")
            
            # Add specific migration steps for this file
            suggestions.extend(self._get_file_specific_suggestions(file_path, file_issues))
        
        suggestions.append("\n🔧 GENERAL MIGRATION STEPS:")
        suggestions.append("=" * 50)
        suggestions.append("1. Add imports for format_redirector functions")
        suggestions.append("2. Replace hardcoded lists with function calls")
        suggestions.append("3. Replace manual normalization with unified functions")
        suggestions.append("4. Test that the application still works correctly")
        suggestions.append("5. Verify that all plotting schemas show consistent data")
        
        return suggestions
    
    def _get_file_specific_suggestions(self, file_path: str, issues: List[str]) -> List[str]:
        """Get file-specific migration suggestions."""
        suggestions = []
        
        if "realtime_plot3d_sheet.py" in file_path:
            suggestions.extend([
                "  🔧 Specific fixes:",
                "     1. Replace: PLOT3D_COLUMNS = [...] → self.PLOT3D_COLUMNS = get_plot3d_columns()",
                "     2. Replace: VALID_MARKERS = [...] → self.VALID_MARKERS = get_valid_markers()",
                "     3. Replace: VALID_COLORS = [...] → self.VALID_COLORS = get_valid_colors()",
                "     4. Replace: VALID_SPHERES = [...] → self.VALID_SPHERES = get_valid_spheres()",
                "     5. Replace manual normalization with convert_lab_to_normalized()"
            ])
        
        elif "ternary_export.py" in file_path:
            suggestions.extend([
                "  🔧 Specific fixes:",
                "     1. Replace: PLOT3D_COLUMNS = [...] → get_plot3d_columns()",
                "     2. Replace manual normalization with normalize_lab_*() functions"
            ])
        
        elif "ods_exporter.py" in file_path:
            suggestions.extend([
                "  🔧 Specific fixes:",
                "     1. Replace: _normalize_lab_l() → normalize_lab_l()",
                "     2. Replace: _normalize_lab_ab() → normalize_lab_a/b()"
            ])
        
        return suggestions
    
    def create_example_fix(self, file_path: str) -> str:
        """Create an example of how to fix a specific file."""
        if "realtime_plot3d_sheet.py" in file_path:
            return """
# BEFORE (scattered formatting):
class RealtimePlot3DSheet:
    PLOT3D_COLUMNS = [
        'Xnorm', 'Ynorm', 'Znorm', 'DataID', 'Cluster', 
        '∆E', 'Marker', 'Color', 'Centroid_X', 'Centroid_Y', 
        'Centroid_Z', 'Sphere', 'Radius'
    ]
    
    VALID_MARKERS = ['(none)', '.', 'o', '*', '^', '<', '>', 'v', 's', 'D', '+', 'x']
    
    def normalize_data(self, l_val, a_val, b_val):
        x_norm = l_val / 100.0
        y_norm = (a_val + 128.0) / 255.0
        z_norm = (b_val + 128.0) / 255.0
        return (x_norm, y_norm, z_norm)

# AFTER (unified formatting):
from utils.format_redirector import (
    get_plot3d_columns, get_valid_markers, get_valid_colors, get_valid_spheres,
    convert_lab_to_normalized
)

class RealtimePlot3DSheet:
    def __init__(self, parent, sample_set_name="StampZ_Analysis"):
        # Get columns and validation lists from unified source
        self.PLOT3D_COLUMNS = get_plot3d_columns()
        self.VALID_MARKERS = get_valid_markers() 
        self.VALID_COLORS = get_valid_colors()
        self.VALID_SPHERES = get_valid_spheres()
    
    def normalize_data(self, l_val, a_val, b_val):
        return convert_lab_to_normalized(l_val, a_val, b_val, 'plot3d')
"""
        
        return "No specific example available for this file."


def main():
    """Run the migration analysis."""
    project_root = "/Users/stanbrown/Desktop/StampZ-III"
    
    print("🔍 StampZ-III Formatting Migration Analysis")
    print("=" * 60)
    
    migrator = FormattingMigrator(project_root)
    
    # Analyze files
    issues = migrator.analyze_files()
    
    # Generate suggestions
    suggestions = migrator.generate_migration_suggestions(issues)
    
    # Print results
    for suggestion in suggestions:
        print(suggestion)
    
    # Show example fix
    if issues:
        print("\n" + "=" * 60)
        print("💡 EXAMPLE FIX (realtime_plot3d_sheet.py):")
        print("=" * 60)
        print(migrator.create_example_fix("realtime_plot3d_sheet.py"))
    
    print("\n" + "=" * 60)
    print("🎯 NEXT STEPS:")
    print("=" * 60)
    if issues:
        print("1. Review the migration suggestions above")
        print("2. Apply the suggested changes to each file") 
        print("3. Test Plot_3D, Ternary, and external file workflows")
        print("4. Verify that all systems show consistent data")
        print("\n💡 TIP: Start with realtime_plot3d_sheet.py as it's the most critical file")
    else:
        print("✅ All files are already using unified formatting!")
        print("🎉 Your system should have consistent data representation")
    
    return len(issues) == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)