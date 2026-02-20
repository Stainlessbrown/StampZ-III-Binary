import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
import logging
from typing import Dict, List, Optional, Tuple, Any, Union

class SphereManager:
    """
    Manager class for rendering spheres at centroid coordinates in 3D space.
    
    This class manages the creation and visualization of translucent spheres at
    Centroid_X/Y/Z coordinates. Spheres are only rendered if valid coordinate data exists.
    The colors are taken from the "Sphere" column of the dataframe, with a default of gray
    if no color is specified.
    """
    
    def __init__(self, ax, canvas, data_df: pd.DataFrame):
        """
        Initialize the SphereManager.
        
        Args:
            ax: The matplotlib 3D axis object
            canvas: The matplotlib canvas for rendering
            data_df: Pandas DataFrame containing the data to visualize
        """
        self.ax = ax
        self.canvas = canvas
        self.data_df = data_df
        self.sphere_objects = []  # Store references to sphere objects for later removal
        
        # Constants for sphere rendering
        self.ALPHA = 0.15  # Fixed transparency
        self.DEFAULT_RADIUS = 0.02  # Default radius when none specified
        
        # Configure logger
        self.logger = logging.getLogger(__name__)
        
        # Define color mapping (similar to existing color dictionary but with yellow instead of black)
        # Note: For Plotly compatibility, use full color names that work in both matplotlib and Plotly
        self.color_map = {
            'red': 'red',
            'green': 'green', 
            'blue': 'blue',
            'yellow': 'yellow',
            'cyan': 'cyan',
            'magenta': 'magenta',
            'orange': 'orange',
            'purple': 'purple',
            'brown': 'brown',
            'pink': 'hotpink',  # Changed from 'pink' to 'hotpink' for Plotly compatibility
            'lime': 'lime',
            'navy': 'navy',
            'teal': 'teal'
        }
        
        # Initialize visibility states (all spheres visible by default)
        self.visibility_states = {color: True for color in self.color_map.values()}
        
        self.logger.info("SphereManager initialized successfully")
    
    def clear_spheres(self) -> None:
        """Remove all sphere objects from the plot (3D surfaces and 2D patches)."""
        try:
            count = len(self.sphere_objects)
            # Remove all sphere/circle objects from the plot
            for obj in self.sphere_objects:
                try:
                    obj.remove()
                except Exception:
                    pass  # Already removed or axes changed
            
            # Clear the list of sphere objects
            self.sphere_objects = []
            self.logger.info(f"Cleared {count} sphere/circle objects from plot")
        except Exception as e:
            self.logger.error(f"Error clearing spheres: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def update_references(self, ax, canvas, data_df: pd.DataFrame) -> None:
        """
        Update references to the axis, canvas, and dataframe.
        
        Args:
            ax: The matplotlib 3D axis object
            canvas: The matplotlib canvas for rendering
            data_df: Pandas DataFrame containing the data to visualize
        """
        try:
            # Update references
            self.ax = ax
            self.canvas = canvas
            self.data_df = data_df
            
            # Clear existing spheres
            self.clear_spheres()
            
            self.logger.info(f"Updated SphereManager with {len(data_df)} data points")
        except Exception as e:
            self.logger.error(f"Error updating references: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def toggle_visibility(self, color: str) -> None:
        """
        Toggle the visibility state of spheres of the specified color.
        
        Args:
            color: The color code of the spheres to toggle
        """
        try:
            if color in self.visibility_states:
                self.visibility_states[color] = not self.visibility_states[color]
                self.logger.info(f"Toggled visibility of {color} spheres to {self.visibility_states[color]}")
                self.render_spheres()  # Refresh the spheres with updated visibility
        except Exception as e:
            self.logger.error(f"Error toggling sphere visibility: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def get_active_colors(self) -> List[str]:
        """
        Get list of colors currently used in the data.
        
        Returns:
            List of color codes that are actually present in the dataset
        """
        try:
            # Get unique sphere color names from the data
            colors = self.data_df['Sphere'].dropna().unique()
            # Convert to color codes
            active_colors = [self._get_color(str(c)) for c in colors]
            return active_colors
        except Exception as e:
            self.logger.error(f"Error getting active colors: {str(e)}")
            return []
    
    def get_color_data_ids(self) -> Dict[str, List[str]]:
        """
        Get a mapping of sphere color codes to their associated DataIDs.
        
        Only includes rows that have valid centroid coordinates.
        
        Returns:
            Dict mapping color code -> list of DataID strings
        """
        color_to_ids: Dict[str, List[str]] = {}
        try:
            # Filter to rows with valid centroid coordinates
            valid_mask = (
                self.data_df['Centroid_X'].notna() &
                self.data_df['Centroid_Y'].notna() &
                self.data_df['Centroid_Z'].notna()
            )
            centroid_data = self.data_df[valid_mask]
            
            for _, row in centroid_data.iterrows():
                color_name = row.get('Sphere')
                if pd.isna(color_name):
                    continue
                color = self._get_color(str(color_name))
                data_id = row.get('DataID')
                if pd.notna(data_id) and str(data_id).strip():
                    color_to_ids.setdefault(color, []).append(str(data_id).strip())
        except Exception as e:
            self.logger.error(f"Error getting color data IDs: {str(e)}")
        return color_to_ids
    
    def _create_sphere_mesh(self, center: Tuple[float, float, float], radius: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Create a 3D sphere mesh for rendering.
        
        Args:
            center: (x, y, z) coordinates of the sphere center
            radius: Radius of the sphere
            
        Returns:
            Tuple of (x, y, z) mesh grids for the sphere surface
        """
        # Create sphere mesh - use enough points for a smooth sphere but not too many for performance
        u = np.linspace(0, 2 * np.pi, 20)
        v = np.linspace(0, np.pi, 10)
        
        x = radius * np.outer(np.cos(u), np.sin(v)) + center[0]
        y = radius * np.outer(np.sin(u), np.sin(v)) + center[1]
        z = radius * np.outer(np.ones(np.size(u)), np.cos(v)) + center[2]
        
        return x, y, z
    
    def _get_color(self, color_name: str) -> str:
        """
        Get color code from color name.
        
        Args:
            color_name: Name of the color
            
        Returns:
            Matplotlib color code
        """
        # If color_name is in our map, return the corresponding code
        if color_name in self.color_map:
            return self.color_map[color_name]
        
        # If it's not in our map but is a valid color string, return it directly
        try:
            if isinstance(color_name, str):
                # Check if it might be a hex color or other valid color name
                return color_name
        except:
            pass
        
        # Default color is gray
        return 'gray'
    
    def render_spheres(self) -> None:
        """
        Render spheres at centroid coordinates using variable radii.
        
        Spheres are only drawn where Centroid_X/Y/Z coordinates exist.
        Colors are taken from the "Sphere" column with a default of gray.
        Radii are taken from the "Radius" column with a default of DEFAULT_RADIUS.
        All spheres have a fixed alpha value of 0.15.
        """
        try:
            # Clear existing spheres first
            self.clear_spheres()
            
            # Filter data to only include rows with valid Centroid coordinates
            # ALL THREE coordinates must be present - no fallback
            valid_mask = (
                self.data_df['Centroid_X'].notna() & 
                self.data_df['Centroid_Y'].notna() & 
                self.data_df['Centroid_Z'].notna()
            )
            centroid_data = self.data_df[valid_mask].copy()
            
            # Log how many valid centroid points we found
            self.logger.info(f"Found {len(centroid_data)} points with valid centroid coordinates for spheres")
            print(f"DEBUG: Found {len(centroid_data)} points with valid centroid coordinates for spheres")
            
            # SAFE DEBUG: Show what sphere data we're working with (doesn't change logic)
            if len(centroid_data) > 0:
                print(f"DEBUG: Sample centroid rows with sphere data:")
                for i, (idx, row) in enumerate(centroid_data.head(5).iterrows()):
                    sphere_val = row.get('Sphere', 'N/A')
                    radius_val = row.get('Radius', 'N/A') 
                    data_id = row.get('DataID', 'N/A')
                    print(f"  Row {idx}: DataID={data_id}, Sphere='{sphere_val}', Radius='{radius_val}' (type: {type(radius_val)})")
                    # Extra debug for radius conversion
                    if pd.notna(radius_val):
                        print(f"    Radius is NOT NaN - will use: {float(radius_val)}")
                    else:
                        print(f"    Radius IS NaN - will use default: {self.DEFAULT_RADIUS}")
            
            if len(centroid_data) == 0:
                self.logger.info("No valid centroid data found for sphere rendering")
                print("DEBUG: No valid centroid data found for sphere rendering")
                return
            
            # Process each point with valid centroid coordinates
            sphere_count = 0
            for idx, row in centroid_data.iterrows():
                try:
                    # Get color and check visibility
                    color_name = row.get('Sphere')
                    color = self._get_color(str(color_name) if pd.notna(color_name) else 'gray')
                    
                    # Skip if sphere color is not visible
                    if not self.visibility_states.get(color, True):
                        continue
                        
                    # Get radius from Radius column or use default
                    radius = row.get('Radius', self.DEFAULT_RADIUS)
                    try:
                        radius = float(radius)
                        # Ensure radius is positive, use default if not
                        if not (radius > 0):
                            self.logger.warning(f"Invalid radius value {radius} at index {idx}, using default")
                            radius = self.DEFAULT_RADIUS
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid radius value at index {idx}, using default")
                        radius = self.DEFAULT_RADIUS
                    
                    # Get coordinates
                    center = (
                        float(row['Centroid_X']), 
                        float(row['Centroid_Y']), 
                        float(row['Centroid_Z'])
                    )
                    
                    # Create sphere mesh with variable radius
                    x, y, z = self._create_sphere_mesh(center, radius)
                    
                    # Render the sphere
                    sphere = self.ax.plot_surface(
                        x, y, z,
                        color=color,
                        alpha=self.ALPHA,
                        linewidth=0,
                        antialiased=True
                    )
                    
                    # Add to list of objects for later removal
                    self.sphere_objects.append(sphere)
                    sphere_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Error rendering sphere at index {idx}: {str(e)}")
                    continue
            
            self.logger.info(f"Successfully rendered {sphere_count} visible spheres")
            print(f"DEBUG: Successfully rendered {sphere_count} visible spheres")
            
            # Refresh the canvas
            self.canvas.draw()
            
        except Exception as e:
            self.logger.error(f"Error rendering spheres: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def render_spheres_2d(self, ax_2d, plane: str) -> None:
        """Render spheres as 2D circles projected onto the specified plane.
        
        Args:
            ax_2d: A 2D matplotlib Axes to draw circles on
            plane: Which plane to project onto - 'xy', 'xz', or 'yz'
        """
        try:
            # Clear existing sphere objects (2D circles stored in same list)
            self.clear_spheres()
            
            # Filter data to rows with valid centroid coordinates
            valid_mask = (
                self.data_df['Centroid_X'].notna() & 
                self.data_df['Centroid_Y'].notna() & 
                self.data_df['Centroid_Z'].notna()
            )
            centroid_data = self.data_df[valid_mask].copy()
            
            if len(centroid_data) == 0:
                print("DEBUG: No valid centroid data for 2D sphere rendering")
                return
            
            # Coordinate mapping for each plane
            coord_map = {
                'xy': ('Centroid_X', 'Centroid_Y'),
                'xz': ('Centroid_X', 'Centroid_Z'),
                'yz': ('Centroid_Y', 'Centroid_Z'),
            }
            
            if plane not in coord_map:
                print(f"DEBUG: Unknown plane '{plane}' for 2D sphere rendering")
                return
            
            col_h, col_v = coord_map[plane]
            
            circle_count = 0
            for idx, row in centroid_data.iterrows():
                try:
                    color_name = row.get('Sphere')
                    color = self._get_color(str(color_name) if pd.notna(color_name) else 'gray')
                    
                    if not self.visibility_states.get(color, True):
                        continue
                    
                    radius = row.get('Radius', self.DEFAULT_RADIUS)
                    try:
                        radius = float(radius)
                        if not (radius > 0):
                            radius = self.DEFAULT_RADIUS
                    except (ValueError, TypeError):
                        radius = self.DEFAULT_RADIUS
                    
                    cx = float(row[col_h])
                    cy = float(row[col_v])
                    
                    circle = mpatches.Circle(
                        (cx, cy), radius,
                        facecolor=color,
                        edgecolor=color,
                        alpha=self.ALPHA * 2,  # Slightly more opaque in 2D for visibility
                        linewidth=1.0,
                        zorder=5
                    )
                    ax_2d.add_patch(circle)
                    self.sphere_objects.append(circle)
                    circle_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Error rendering 2D circle at index {idx}: {str(e)}")
                    continue
            
            print(f"DEBUG: Rendered {circle_count} 2D circles for plane {plane}")
            
        except Exception as e:
            self.logger.error(f"Error rendering 2D spheres: {str(e)}")
            import traceback
            traceback.print_exc()

