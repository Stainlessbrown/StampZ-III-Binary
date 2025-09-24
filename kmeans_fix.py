#!/usr/bin/env python3
"""
Quick fix for K-means data type error.
This patches the validate_row_range method to handle mixed data types properly.
"""

def patch_kmeans_validation():
    """Patch the K-means manager validation to handle mixed data types."""
    
    # Import the original method
    from plot3d.k_means_manager import KmeansManager
    import numpy as np
    import pandas as pd
    
    # Store original method
    original_validate = KmeansManager.validate_row_range
    
    def patched_validate_row_range(self, start_row: int, end_row: int):
        """Patched version that handles mixed data types safely."""
        if self.data is None:
            self.logger.error("No data loaded. Call load_data() first.")
            raise ValueError("No data loaded. Call load_data() first.")
        
        # SAFE METHOD: Find last non-empty row by checking coordinate columns directly
        coordinate_cols = ['Xnorm', 'Ynorm', 'Znorm']
        last_valid_rows = []
        
        for col in coordinate_cols:
            if col in self.data.columns:
                try:
                    # Convert to numeric first, then check for valid values
                    numeric_series = pd.to_numeric(self.data[col], errors='coerce')
                    valid_indices = numeric_series.notna().values.nonzero()[0]
                    if len(valid_indices) > 0:
                        last_valid_rows.append(valid_indices[-1])
                except Exception as e:
                    print(f"Warning: Could not process column {col}: {e}")
                    continue
        
        if not last_valid_rows:
            raise ValueError("No valid coordinate data found in the file")
        
        last_valid_row = max(last_valid_rows) + 1  # Add 1 for 1-based indexing
        
        # Validate start_row - row 8 is the first valid data row 
        min_valid_row = 8  # Data starts at row 8 (display row)
        if start_row < min_valid_row:
            self.logger.warning(f"Invalid start_row {start_row}, adjusting to minimum value {min_valid_row}")
            start_row = min_valid_row
        
        # Validate end_row
        max_row = min(999, last_valid_row)
        
        print(f"\n🔧 PATCHED ROW VALIDATION:")
        print(f"  - Input end_row: {end_row}")
        print(f"  - last_valid_row: {last_valid_row}")
        print(f"  - max_row: {max_row}")
        print(f"  - DataFrame has {len(self.data)} rows")
        
        if end_row > max_row:
            print(f"  - ⚠️ TRUNCATING: end_row {end_row} > max_row {max_row}")
            self.logger.warning(f"Invalid end_row {end_row}, adjusting to last non-empty row {max_row}")
            end_row = max_row
        else:
            print(f"  - ✅ end_row {end_row} <= max_row {max_row}, no truncation")
        
        # Ensure start_row <= end_row
        if start_row > end_row:
            self.logger.error(f"Start row {start_row} is greater than end row {end_row}")
            raise ValueError("Start row must be less than or equal to end row")
        
        self.logger.info(f"Validated row range: {start_row} to {end_row}")
        return start_row, end_row
    
    # Apply the patch
    KmeansManager.validate_row_range = patched_validate_row_range
    print("✅ K-means validation patched to handle mixed data types")

if __name__ == "__main__":
    patch_kmeans_validation()
    print("K-means patch applied. Now you can run K-means clustering safely.")