#!/usr/bin/env python3
"""
Fix RGB channel mapping in RGB-CMY analyzer to use standard RGB order.

This script will update the analyzer to use:
- R, G, B column order (instead of B, G, R) 
- Proper RGB->CMY conversion
"""

import os
import sys

def fix_analyzer_mapping():
    """Apply the RGB channel mapping fix"""
    
    analyzer_path = "utils/rgb_cmy_analyzer.py"
    
    if not os.path.exists(analyzer_path):
        print(f"ERROR: {analyzer_path} not found")
        return False
    
    print("Fixing RGB channel mapping in analyzer...")
    
    # Read the current file
    try:
        with open(analyzer_path, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"ERROR: Cannot read {analyzer_path}: {e}")
        return False
    
    # Define the fixes
    fixes = [
        # Fix RGB channel mapping in result compilation
        {
            'old': """                # RGB data (note: order is B, G, R as per template)
                'B_mean': float(rgb_means[2]),  # Blue = index 2
                'B_std': float(rgb_stds[2]),
                'G_mean': float(rgb_means[1]),  # Green = index 1
                'G_std': float(rgb_stds[1]),
                'R_mean': float(rgb_means[0]),  # Red = index 0
                'R_std': float(rgb_stds[0]),
                # CMY data (C, Y, M order as per template)
                'C_mean': float(cmy_means[0]),  # Cyan = 255 - Red
                'C_std': float(cmy_stds[0]),
                'Y_mean': float(cmy_means[1]),  # Yellow = 255 - Green
                'Y_std': float(cmy_stds[1]),
                'M_mean': float(cmy_means[2]),  # Magenta = 255 - Blue
                'M_std': float(cmy_stds[2])""",
            'new': """                # RGB data - standard RGB order (Red, Green, Blue)
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
                'Y_std': float(cmy_stds[2])"""
        },
        # Fix Excel export to use RGB order
        {
            'old': """            # Populate RGB data (rows 16-21, columns B-J) - only populate actual samples
            for i in range(min(6, len(self.results))):  # Only populate up to 6 samples or actual count
                result = self.results[i]
                row = 16 + i
                sheet[f'B{row}'] = result['B_mean']
                sheet[f'C{row}'] = result['B_std']
                sheet[f'E{row}'] = result['G_mean']
                sheet[f'F{row}'] = result['G_std']
                sheet[f'H{row}'] = result['R_mean']
                sheet[f'I{row}'] = result['R_std']""",
            'new': """            # Populate RGB data (rows 16-21, columns B-J) - RGB order
            for i in range(min(6, len(self.results))):  # Only populate up to 6 samples or actual count
                result = self.results[i]
                row = 16 + i
                sheet[f'B{row}'] = result['R_mean']  # Red in first column
                sheet[f'C{row}'] = result['R_std']
                sheet[f'E{row}'] = result['G_mean']  # Green in middle
                sheet[f'F{row}'] = result['G_std']
                sheet[f'H{row}'] = result['B_mean']  # Blue in last column
                sheet[f'I{row}'] = result['B_std']"""
        },
        # Fix CMY export to use CMY order
        {
            'old': """            # Populate CMY data (rows 29-34, columns B-J) - only populate actual samples
            for i in range(min(6, len(self.results))):  # Only populate up to 6 samples or actual count
                result = self.results[i]
                row = 29 + i
                sheet[f'B{row}'] = result['C_mean']
                sheet[f'C{row}'] = result['C_std']
                sheet[f'E{row}'] = result['Y_mean']
                sheet[f'F{row}'] = result['Y_std']
                sheet[f'H{row}'] = result['M_mean']
                sheet[f'I{row}'] = result['M_std']""",
            'new': """            # Populate CMY data (rows 29-34, columns B-J) - CMY order
            for i in range(min(6, len(self.results))):  # Only populate up to 6 samples or actual count
                result = self.results[i]
                row = 29 + i
                sheet[f'B{row}'] = result['C_mean']  # Cyan first
                sheet[f'C{row}'] = result['C_std']
                sheet[f'E{row}'] = result['M_mean']  # Magenta middle
                sheet[f'F{row}'] = result['M_std']
                sheet[f'H{row}'] = result['Y_mean']  # Yellow last
                sheet[f'I{row}'] = result['Y_std']"""
        },
        # Fix ODS RGB header
        {
            'old': """                    # RGB section header (row 15)
                    ['Sample#', 'B', 'SD', '1/SD²', 'G', 'SD', '1/SD²', 'R', 'SD', '1/SD²']""",
            'new': """                    # RGB section header (row 15) - RGB order
                    ['Sample#', 'R', 'SD', '1/SD²', 'G', 'SD', '1/SD²', 'B', 'SD', '1/SD²']"""
        },
        # Fix ODS RGB data population
        {
            'old': """                        rows_data.append([
                            str(i + 1),
                            f"{result['B_mean']:.1f}",
                            f"{result['B_std']:.2f}",
                            f"{b_inv_sd2:.6f}" if b_inv_sd2 != '' else '',
                            f"{result['G_mean']:.1f}",
                            f"{result['G_std']:.2f}",
                            f"{g_inv_sd2:.6f}" if g_inv_sd2 != '' else '',
                            f"{result['R_mean']:.1f}",
                            f"{result['R_std']:.2f}",
                            f"{r_inv_sd2:.6f}" if r_inv_sd2 != '' else ''
                        ])""",
            'new': """                        rows_data.append([
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
                        ])"""
        },
        # Fix ODS CMY header
        {
            'old': """                # CMY section header (row 28)
                rows_data.append(['Sample#', 'C', 'SD', '1/SD²', 'Y', 'SD', '1/SD²', 'M', 'SD', '1/SD²'])""",
            'new': """                # CMY section header (row 28) - CMY order
                rows_data.append(['Sample#', 'C', 'SD', '1/SD²', 'M', 'SD', '1/SD²', 'Y', 'SD', '1/SD²'])"""
        },
        # Fix ODS CMY data population
        {
            'old': """                        rows_data.append([
                            str(i + 1),
                            f"{result['C_mean']:.1f}",
                            f"{result['C_std']:.2f}",
                            f"{c_inv_sd2:.6f}" if c_inv_sd2 != '' else '',
                            f"{result['Y_mean']:.1f}",
                            f"{result['Y_std']:.2f}",
                            f"{y_inv_sd2:.6f}" if y_inv_sd2 != '' else '',
                            f"{result['M_mean']:.1f}",
                            f"{result['M_std']:.2f}",
                            f"{m_inv_sd2:.6f}" if m_inv_sd2 != '' else ''
                        ])""",
            'new': """                        rows_data.append([
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
                        ])"""
        }
    ]
    
    # Apply the fixes
    fixed_content = content
    fixes_applied = 0
    
    for fix in fixes:
        if fix['old'] in fixed_content:
            fixed_content = fixed_content.replace(fix['old'], fix['new'])
            fixes_applied += 1
            print(f"✓ Applied fix {fixes_applied}")
        else:
            print(f"⚠ Could not find pattern for fix {len([f for f in fixes if fixes.index(f) <= fixes.index(fix)])}")
    
    # Write the fixed content
    try:
        with open(analyzer_path, 'w') as f:
            f.write(fixed_content)
        print(f"✅ Successfully applied {fixes_applied} fixes to {analyzer_path}")
        return True
    except Exception as e:
        print(f"ERROR: Cannot write to {analyzer_path}: {e}")
        return False

def update_csv_export():
    """Also update CSV export to use RGB order"""
    print("\n📋 Note: CSV export will also need header updates:")
    print("   RGB section: Sample# | R | SD | 1/SD² | G | SD | 1/SD² | B | SD | 1/SD²")
    print("   CMY section: Sample# | C | SD | 1/SD² | M | SD | 1/SD² | Y | SD | 1/SD²")

if __name__ == "__main__":
    print("🔧 Fixing RGB-CMY Channel Mapping")
    print("=" * 40)
    
    success = fix_analyzer_mapping()
    
    if success:
        update_csv_export()
        print("\n✅ RGB channel mapping fixed!")
        print("📝 Next steps:")
        print("   1. Test with: python3 test_ods_export_improved.py")
        print("   2. Update your Excel/ODS templates to use RGB order headers")
        print("   3. The exported files will now use standard RGB and CMY order")
    else:
        print("\n❌ Fix failed - manual editing may be required")
    
    sys.exit(0 if success else 1)