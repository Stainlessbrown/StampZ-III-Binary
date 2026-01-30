"""
K-means File Handler

Handles saving cluster assignments to both ODS (LibreOffice) and XLSX (Excel) files.
Includes file locking, backup creation, verification, and detailed error handling.
"""

import os
import shutil
import fcntl
import errno
import time
import pandas as pd
from tkinter import messagebox
import logging


class KMeansFileHandler:
    """Handles saving K-means cluster assignments to spreadsheet files."""
    
    def __init__(self, data, file_path, logger=None):
        """
        Initialize the file handler.
        
        Args:
            data: pandas DataFrame containing cluster assignments
            file_path: Path to the spreadsheet file (.ods or .xlsx)
            logger: Logger instance for debugging
        """
        self.data = data
        self.file_path = file_path
        self.logger = logger or logging.getLogger(__name__)
    
    def save_clusters(self, start: int, end: int, row_indices) -> bool:
        """
        Save cluster assignments to the appropriate file format.
        
        Args:
            start: Start row for clustering
            end: End row for clustering
            row_indices: List of row indices to update
            
        Returns:
            True if save was successful
        """
        try:
            if self.file_path.endswith('.xlsx'):
                self.logger.info(f"Saving clusters to Excel file: {self.file_path}")
                return self._save_to_xlsx(start, end, row_indices)
            elif self.file_path.endswith('.ods'):
                self.logger.info(f"Saving clusters to ODS file: {self.file_path}")
                return self._save_to_ods(start, end, row_indices)
            else:
                raise ValueError(f"Unsupported file format: {self.file_path}")
        except Exception as e:
            self.logger.error(f"Error saving clusters: {str(e)}")
            raise
    
    def _save_to_xlsx(self, start: int, end: int, row_indices) -> bool:
        """Save cluster assignments to an Excel (.xlsx) file."""
        try:
            from openpyxl import load_workbook
            
            # Inform user of the process
            msg = (f"Saving cluster assignments for rows {start}-{end}:\\n\\n"
                  "1. Your original .xlsx file will be updated directly\\n"
                  "2. Cluster and Centroid columns will be modified\\n\\n"
                  "Continue?")
            
            if not messagebox.askokcancel("Save Clusters", msg):
                return False
            
            # Create backup
            backup_path = f"{self.file_path}.bak"
            self.logger.info(f"Creating backup at: {backup_path}")
            shutil.copy2(self.file_path, backup_path)
            
            try:
                # Load the Excel file
                wb = load_workbook(self.file_path)
                ws = wb.active
                self.logger.info(f"Opened Excel sheet: {ws.title}")
                
                # Get cluster assignments
                clusters = self.data.iloc[row_indices]['Cluster']
                valid_clusters = clusters[clusters.notna()]
                
                if not valid_clusters.empty:
                    # Find column indices
                    cluster_col = None
                    centroid_x_col = None
                    centroid_y_col = None
                    centroid_z_col = None
                    
                    for col_idx, cell in enumerate(ws[1], 1):
                        if cell.value == 'Cluster':
                            cluster_col = col_idx
                        elif cell.value == 'Centroid_X':
                            centroid_x_col = col_idx
                        elif cell.value == 'Centroid_Y':
                            centroid_y_col = col_idx
                        elif cell.value == 'Centroid_Z':
                            centroid_z_col = col_idx
                    
                    if not all([cluster_col, centroid_x_col, centroid_y_col, centroid_z_col]):
                        missing = []
                        if not cluster_col: missing.append('Cluster')
                        if not centroid_x_col: missing.append('Centroid_X')
                        if not centroid_y_col: missing.append('Centroid_Y')
                        if not centroid_z_col: missing.append('Centroid_Z')
                        raise ValueError(f"Required columns not found: {', '.join(missing)}")
                    
                    self.logger.info(f"Found columns - Cluster: {cluster_col}, Centroid_X: {centroid_x_col}, Centroid_Y: {centroid_y_col}, Centroid_Z: {centroid_z_col}")
                    
                    # Calculate centroids
                    cluster_centroids = self._calculate_centroids()
                    
                    # Write cluster assignments to data rows
                    # Note: row_indices are 0-based DataFrame indices
                    # Sheet rows: row 1 = header, row 2+ = data (DataFrame indices 0+)
                    cluster_write_count = 0
                    for i, idx in enumerate(row_indices):
                        cluster_value = clusters.iloc[i]
                        if pd.notna(cluster_value):
                            # Map DataFrame index to sheet row: index 0 -> row 2, index 1 -> row 3, etc.
                            sheet_row = idx + 2
                            cell = ws.cell(row=sheet_row, column=cluster_col)
                            cell.value = int(cluster_value)
                            cluster_write_count += 1
                            self.logger.info(f"Wrote cluster {int(cluster_value)} to data point at sheet row {sheet_row} (DataFrame index {idx})")
                    self.logger.info(f"Total cluster assignments written to data rows: {cluster_write_count}")
                    
                    # Write centroid data to fixed rows
                    # Row 2-7 are reserved for cluster 0-5 centroid data
                    for cluster_num, centroid in cluster_centroids.items():
                        excel_row = int(cluster_num) + 2  # Row 2 for cluster 0, row 3 for cluster 1, etc.
                        # Always write the cluster number for identification
                        ws.cell(row=excel_row, column=cluster_col, value=int(cluster_num))
                        # Write centroid coordinates
                        ws.cell(row=excel_row, column=centroid_x_col, value=round(centroid[0], 4))
                        ws.cell(row=excel_row, column=centroid_y_col, value=round(centroid[1], 4))
                        ws.cell(row=excel_row, column=centroid_z_col, value=round(centroid[2], 4))
                        self.logger.info(f"Updated Excel row {excel_row} with cluster {int(cluster_num)} and centroid coordinates")
                    
                    # Save the workbook
                    wb.save(self.file_path)
                    self.logger.info("Excel file saved successfully")
                    
                    # Display success message
                    cluster_counts = valid_clusters.value_counts().to_dict()
                    cluster_info = "\\n".join(f"Cluster {k}: {v} points" for k, v in sorted(cluster_counts.items()))
                    
                    success_msg = (
                        f"Clusters and centroid coordinates saved for rows {start}-{end}!\\n\\n"
                        f"Cluster summary:\\n{cluster_info}\\n\\n"
                        f"Excel file has been updated with:\\n"
                        f"- Cluster assignments\\n"
                        f"- Centroid_X, Centroid_Y, Centroid_Z coordinates\\n\\n"
                        f"NEXT STEP: You can now calculate ΔE values by clicking the 'Calculate' button in the ΔE CIE2000 panel."
                    )
                    
                    messagebox.showinfo("Clusters Saved", success_msg)
                    return True
                else:
                    messagebox.showwarning("Warning", 
                        f"No cluster assignments found for rows {start}-{end}")
                    return False
                    
            finally:
                # Clean up backup if save was successful
                try:
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                except Exception:
                    self.logger.warning(f"Could not remove backup file: {backup_path}")
                    
        except Exception as e:
            self.logger.error(f"Error saving to Excel: {str(e)}")
            messagebox.showerror("Error", 
                f"Failed to save cluster assignments to Excel file.\\n\\n"
                f"Error: {str(e)}\\n\\n"
                f"Please check that the file isn't open in another program.")
            raise
    
    def _save_to_ods(self, start: int, end: int, row_indices) -> bool:
        """Save cluster assignments to an ODS (.ods) file."""
        import ezodf
        
        lockfile = None
        lock_path = f"{self.file_path}.lock"
        
        try:
            # Inform user of the process
            msg = (f"Saving cluster assignments for rows {start}-{end}:\\n\\n"
                  "1. Your original .ods file will be updated directly\\n"
                  "2. Only the Cluster column will be modified\\n\\n"
                  "Continue?")
            
            if not messagebox.askokcancel("Save Clusters", msg):
                return False
            
            # Try to acquire the lock with timeout
            max_attempts = 3
            attempt = 0
            lock_acquired = False
            
            while attempt < max_attempts and not lock_acquired:
                try:
                    lockfile = open(lock_path, 'w+')
                    fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_acquired = True
                    self.logger.info("Lock acquired successfully")
                except IOError as e:
                    if e.errno == errno.EACCES or e.errno == errno.EAGAIN:
                        attempt += 1
                        self.logger.warning(f"File is locked, attempt {attempt}/{max_attempts}")
                        
                        if attempt < max_attempts:
                            if not messagebox.askretrycancel("File Locked", 
                                f"The file appears to be in use by another program.\\n\\n"
                                f"Attempt {attempt} of {max_attempts}.\\n\\n"
                                "Would you like to try again?"):
                                if lockfile:
                                    lockfile.close()
                                return False
                            time.sleep(1)
                        else:
                            if lockfile:
                                lockfile.close()
                            messagebox.showerror("File Locked", 
                                "The file is locked by another program and cannot be accessed.\\n\\n"
                                "Please close any applications that might be using this file and try again.")
                            return False
                    else:
                        if lockfile:
                            lockfile.close()
                        raise
            
            if not lock_acquired:
                messagebox.showerror("File Locked", 
                    "Could not acquire file lock after multiple attempts.")
                return False
            
            # Get cluster assignments
            clusters = self.data.iloc[row_indices]['Cluster']
            valid_clusters = clusters[clusters.notna()]
            
            if not valid_clusters.empty:
                try:
                    # Create backup
                    backup_path = f"{self.file_path}.bak"
                    self.logger.info(f"Creating backup at: {backup_path}")
                    shutil.copy2(self.file_path, backup_path)
                    
                    # Read file structure
                    self.logger.info("Reading file structure")
                    df = pd.read_excel(self.file_path, engine='odf')
                    
                    # Verify required columns
                    required_columns = ['Cluster', 'Centroid_X', 'Centroid_Y', 'Centroid_Z']
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    if missing_columns:
                        raise ValueError(f"Required columns missing: {missing_columns}")
                    
                    # Get column indices
                    cluster_col_idx = df.columns.get_loc('Cluster')
                    centroid_x_col_idx = df.columns.get_loc('Centroid_X')
                    centroid_y_col_idx = df.columns.get_loc('Centroid_Y')
                    centroid_z_col_idx = df.columns.get_loc('Centroid_Z')
                    
                    centroid_col_indices = {
                        'Centroid_X': centroid_x_col_idx,
                        'Centroid_Y': centroid_y_col_idx,
                        'Centroid_Z': centroid_z_col_idx
                    }
                    
                    # Calculate centroids
                    cluster_centroids = self._calculate_centroids()
                    
                    # Prepare updates
                    # CRITICAL: ezodf uses 0-based row indexing, unlike openpyxl
                    # ezodf row 0 = first row (header), row 1 = first data row
                    # openpyxl row 1 = first row (header), row 2 = first data row
                    # DataFrame index 0 = first data row
                    data_point_updates = []
                    for i, idx in enumerate(row_indices):
                        # For ODS with ezodf: DataFrame index X = ezodf row (X + 1)
                        # +1 accounts for header row at ezodf row 0
                        sheet_row_idx = idx + 1  # DataFrame index to ezodf row (0-based)
                        cluster_value = clusters.iloc[i]
                        if pd.notna(cluster_value):
                            data_point_updates.append({
                                'row': sheet_row_idx,
                                'cluster': int(cluster_value)
                            })
                            self.logger.info(f"Prepared update: DataFrame idx {idx} → ezodf row {sheet_row_idx} = cluster {int(cluster_value)}")
                    
                    # Prepare centroid updates
                    centroid_row_mapping = {}
                    unique_clusters = sorted(self.data['Cluster'].dropna().unique())
                    for i, cluster_id in enumerate(unique_clusters):
                        centroid_row_mapping[int(cluster_id)] = i + 1
                    
                    centroid_updates = []
                    for cluster_num, centroid in cluster_centroids.items():
                        fixed_row = centroid_row_mapping.get(cluster_num)
                        centroid_updates.append({
                            'row': fixed_row,
                            'cluster': cluster_num,
                            'centroid': centroid
                        })
                    
                    # Open and update file
                    ods_doc = ezodf.opendoc(self.file_path)
                    sheet = ods_doc.sheets[0]
                    
                    # Clear existing centroid data
                    for row_idx in range(2, len(centroid_row_mapping) + 1):
                        for col_name, col_idx in centroid_col_indices.items():
                            try:
                                cell = sheet[row_idx, col_idx]
                                if cell is not None:
                                    cell.set_value("")
                            except Exception:
                                pass
                    
                    # Update data points
                    successful_writes = 0
                    failed_writes = 0
                    for update in data_point_updates:
                        try:
                            row_idx = update['row']
                            cluster_value = update['cluster']
                            cluster_cell = sheet[row_idx, cluster_col_idx]
                            if cluster_cell is None:
                                self.logger.error(f"Cell at row {row_idx}, col {cluster_col_idx} is None!")
                                failed_writes += 1
                                continue
                            cluster_cell.set_value(cluster_value)
                            successful_writes += 1
                            self.logger.info(f"✓ Updated row {row_idx} with cluster {cluster_value}")
                        except Exception as e:
                            failed_writes += 1
                            self.logger.error(f"✗ Failed to update cluster at row {row_idx}: {str(e)}")
                    
                    self.logger.info(f"Cluster assignment write summary: {successful_writes} successful, {failed_writes} failed")
                    
                    if failed_writes > 0 and successful_writes == 0:
                        raise ValueError(f"Failed to write any cluster assignments! All {failed_writes} writes failed.")
                    
                    # Update centroid rows
                    for update in centroid_updates:
                        try:
                            row_idx = update['row']
                            cluster_value = update['cluster']
                            centroid = update['centroid']
                            
                            cluster_cell = sheet[row_idx, cluster_col_idx]
                            cluster_cell.set_value(cluster_value)
                            
                            sheet[row_idx, centroid_col_indices['Centroid_X']].set_value(format(centroid[0], '.4f'))
                            sheet[row_idx, centroid_col_indices['Centroid_Y']].set_value(format(centroid[1], '.4f'))
                            sheet[row_idx, centroid_col_indices['Centroid_Z']].set_value(format(centroid[2], '.4f'))
                            
                            self.logger.info(f"Updated centroid for cluster {cluster_value} at row {row_idx}")
                        except Exception as e:
                            self.logger.error(f"Failed to update centroid at row {row_idx}: {str(e)}")
                            raise
                    
                    # Save to temporary file and verify
                    temp_path = f"{self.file_path}.new"
                    self.logger.info(f"Saving to temporary file: {temp_path}")
                    
                    try:
                        ods_doc.saveas(temp_path)
                        del ods_doc
                        
                        # Verify the save
                        verify_doc = ezodf.opendoc(temp_path)
                        self._verify_centroid_data(verify_doc, centroid_updates, cluster_col_idx, centroid_col_indices)
                        del verify_doc
                        
                        # Replace original with new file
                        os.replace(temp_path, self.file_path)
                        self.logger.info("File saved and verified successfully")
                        
                    finally:
                        try:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        except Exception as cleanup_error:
                            self.logger.warning(f"Could not clean up temporary file: {str(cleanup_error)}")
                    
                    # Clean up backup
                    try:
                        if os.path.exists(backup_path):
                            os.remove(backup_path)
                    except Exception:
                        self.logger.warning(f"Could not remove backup file: {backup_path}")
                    
                    # Display success message
                    cluster_counts = valid_clusters.value_counts().to_dict()
                    cluster_info = "\\n".join(f"Cluster {k}: {v} points" for k, v in sorted(cluster_counts.items()))
                    
                    success_msg = (
                        f"Clusters and centroid coordinates saved for rows {start}-{end}!\\n\\n"
                        f"Cluster summary:\\n{cluster_info}\\n\\n"
                        f"Original .ods file has been updated with:\\n"
                        f"- Cluster assignments\\n"
                        f"- Centroid_X, Centroid_Y, Centroid_Z coordinates\\n\\n"
                        f"NEXT STEP: You can now calculate ΔE values by clicking the 'Calculate' button in the ΔE CIE2000 panel."
                    )
                    
                    messagebox.showinfo("Clusters Saved", success_msg)
                    return True
                    
                except Exception as e:
                    self.logger.error(f"Error updating spreadsheet: {str(e)}")
                    raise
            else:
                messagebox.showwarning("Warning", 
                    f"No cluster assignments found for rows {start}-{end}")
                return False
                
        except Exception as e:
            messagebox.showerror("Error", 
                "Failed to save cluster assignments.\\n\\n"
                "Please check file permissions and make sure the file isn't open in another program.")
            raise
        finally:
            if lockfile:
                self.logger.info("Releasing file lock")
                fcntl.flock(lockfile, fcntl.LOCK_UN)
                lockfile.close()
                try:
                    os.remove(lock_path)
                    self.logger.info("Lock file removed")
                except Exception as e:
                    self.logger.warning(f"Could not remove lock file: {str(e)}")
    
    def _calculate_centroids(self):
        """Calculate centroids for each cluster."""
        cluster_centroids = {}
        for cluster_num in self.data['Cluster'].dropna().unique():
            cluster_mask = self.data['Cluster'] == cluster_num
            centroid = [
                self.data.loc[cluster_mask, 'Xnorm'].mean(),
                self.data.loc[cluster_mask, 'Ynorm'].mean(),
                self.data.loc[cluster_mask, 'Znorm'].mean()
            ]
            cluster_centroids[int(cluster_num)] = centroid
            self.logger.info(f"Calculated centroid for cluster {int(cluster_num)}: {centroid}")
        return cluster_centroids
    
    def _verify_centroid_data(self, verify_doc, rows_to_verify, cluster_col_idx, centroid_col_indices):
        """Verify that centroid data was saved correctly."""
        verify_sheet = verify_doc.sheets[0]
        verification_count = min(5, len(rows_to_verify))
        self.logger.info(f"Verifying {verification_count} sample updates")
        
        for update in rows_to_verify[:verification_count]:
            cluster_value = update['cluster']
            row_idx = int(cluster_value) + 1
            centroid = update['centroid']
            
            # Verify cluster value
            cluster_cell = verify_sheet[row_idx, cluster_col_idx]
            if cluster_cell.value != cluster_value:
                self.logger.error(f"Cluster value mismatch at row {row_idx}")
                raise ValueError(f"Cluster save verification failed at row {row_idx}")
            
            # Verify centroid coordinates
            if centroid is not None:
                centroid_x_cell = verify_sheet[row_idx, centroid_col_indices['Centroid_X']]
                centroid_y_cell = verify_sheet[row_idx, centroid_col_indices['Centroid_Y']]
                centroid_z_cell = verify_sheet[row_idx, centroid_col_indices['Centroid_Z']]
                
                tolerance = 0.0001
                x_diff = abs(float(centroid_x_cell.value) - centroid[0])
                y_diff = abs(float(centroid_y_cell.value) - centroid[1])
                z_diff = abs(float(centroid_z_cell.value) - centroid[2])
                
                if x_diff > tolerance or y_diff > tolerance or z_diff > tolerance:
                    self.logger.error(f"Centroid coordinate mismatch at row {row_idx}")
                    raise ValueError(f"Centroid save verification failed at row {row_idx}")
        
        centroid_cols = ", ".join([f"{col}:{idx}" for col, idx in centroid_col_indices.items()])
        self.logger.info(f"Centroid columns successfully verified: {centroid_cols}")
