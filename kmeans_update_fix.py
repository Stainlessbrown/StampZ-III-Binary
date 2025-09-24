#!/usr/bin/env python3
"""
Fix for K-means update callback data type issues.
This patches the DataFrame update process to handle mixed data types safely.
"""

def patch_kmeans_update_callback():
    """Patch the K-means update callback to handle data type issues."""
    
    from plot3d.Plot_3D import Plot3DApp
    import pandas as pd
    import numpy as np
    
    # Store original method
    original_init = Plot3DApp.__init__
    
    def patched_init(self, *args, **kwargs):
        """Patched initialization that includes safe update callback."""
        
        # Call original init up to the callback definition
        original_init(self, *args, **kwargs)
        
        # Override the callback with safer version
        def safe_on_kmeans_update(updated_df):
            """Safe version of K-means update that handles data types properly."""
            try:
                print("🔧 SAFE K-MEANS UPDATE: Processing DataFrame with data type cleaning...")
                
                # Clean up data types before processing
                cleaned_df = updated_df.copy()
                
                # Convert numeric columns properly
                numeric_columns = ['Xnorm', 'Ynorm', 'Znorm', 'Centroid_X', 'Centroid_Y', 'Centroid_Z']
                for col in numeric_columns:
                    if col in cleaned_df.columns:
                        # Convert to numeric, replacing errors with NaN
                        cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')
                
                # Convert Cluster column to integer, replacing NaN with empty string
                if 'Cluster' in cleaned_df.columns:
                    # First convert to numeric, then to integer where possible
                    cluster_numeric = pd.to_numeric(cleaned_df['Cluster'], errors='coerce')
                    # Convert to int where not NaN, leave NaN as empty string
                    cleaned_df['Cluster'] = cluster_numeric.fillna('')
                    # Convert non-empty values to integers
                    mask = cleaned_df['Cluster'] != ''
                    if mask.any():
                        cleaned_df.loc[mask, 'Cluster'] = cleaned_df.loc[mask, 'Cluster'].astype(int)
                
                # Handle other potentially problematic columns
                string_columns = ['DataID', 'Marker', 'Color', 'Sphere']
                for col in string_columns:
                    if col in cleaned_df.columns:
                        # Ensure all values are strings, replace NaN with empty string
                        cleaned_df[col] = cleaned_df[col].fillna('').astype(str)
                        # Replace 'nan' string with empty string
                        cleaned_df[col] = cleaned_df[col].replace('nan', '')
                
                print(f"✅ Data types cleaned: {len(cleaned_df)} rows processed")
                
                # Update internal DataFrame
                self.df = cleaned_df
                
                # Safely refresh plot
                print("🔄 Refreshing plot with cleaned data...")
                self.refresh_plot()
                print("✅ Plot refreshed successfully")
                
                # Handle worksheet callback safely
                if self.worksheet_update_callback:
                    try:
                        # Check if row selection info is available from K-means manager
                        start_row = getattr(safe_on_kmeans_update, '_kmeans_start_row', None)
                        end_row = getattr(safe_on_kmeans_update, '_kmeans_end_row', None)
                        
                        if start_row is not None and end_row is not None:
                            # Pass row selection info to worksheet callback
                            if hasattr(self.worksheet_update_callback, '__code__') and self.worksheet_update_callback.__code__.co_argcount > 2:
                                self.worksheet_update_callback(cleaned_df, start_row, end_row)
                            else:
                                self.worksheet_update_callback(cleaned_df)
                        else:
                            self.worksheet_update_callback(cleaned_df)
                        print(f"✅ Successfully updated parent worksheet with {len(cleaned_df)} rows")
                    except Exception as e:
                        print(f"⚠️ Warning: Failed to update parent worksheet: {e}")
                        # Don't raise - worksheet update is not critical
                        
                elif self.sample_set_name:
                    # Standalone mode - automatically save to database
                    try:
                        print(f"🔄 Standalone mode: Auto-saving analysis results to database {self.sample_set_name}")
                        color_points = self._convert_dataframe_to_color_points(cleaned_df)
                        if color_points:
                            success = self.bridge.save_color_points_to_database(self.sample_set_name, color_points)
                            if success:
                                print(f"✅ Analysis results auto-saved to database: {self.sample_set_name}")
                            else:
                                print(f"⚠️ Failed to auto-save results to database")
                        else:
                            print(f"⚠️ Failed to convert data for database saving")
                    except Exception as db_error:
                        print(f"⚠️ Error auto-saving to database: {db_error}")
                        # Don't raise - auto-save failure is not critical
                        
            except Exception as e:
                print(f"❌ Error in safe K-means update: {e}")
                import traceback
                traceback.print_exc()
                # Don't re-raise to avoid breaking the UI
                
        # Replace the callback in managers
        if hasattr(self, 'kmeans_manager'):
            self.kmeans_manager.on_data_update = safe_on_kmeans_update
        if hasattr(self, 'delta_e_manager'):
            self.delta_e_manager.on_data_update = safe_on_kmeans_update
            
        print("✅ K-means update callback patched for safe data type handling")
    
    # Apply the patch
    Plot3DApp.__init__ = patched_init
    print("✅ K-means update callback patched to handle data type issues")

if __name__ == "__main__":
    patch_kmeans_update_callback()
    print("K-means update patch applied. Now you can run K-means clustering safely.")