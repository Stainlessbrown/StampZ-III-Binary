"""
Plotly Interactive 3D Viewer

Provides an interactive Plotly visualization as a complement to the matplotlib plot.
Opens in browser for smooth rotation and hover tooltips.
"""

import pandas as pd
import plotly.graph_objects as go
import numpy as np


def create_plotly_visualization(df, show_trendline=False, show_polynomial=False, show_cubic=False,
                                show_exponential=False, show_red_trendline=False, 
                                show_green_trendline=False, show_blue_trendline=False,
                                trendline_manager=None, show_spheres=False, 
                                sphere_data=None, initial_elev=30, initial_azim=-60, initial_roll=0, 
                                axis_ranges=None):
    """Create an interactive Plotly 3D scatter plot from DataFrame.
    
    Args:
        df: DataFrame with Xnorm, Ynorm, Znorm columns and optional Color, Marker, etc.
        show_trendline: Whether to show the linear trendline
        show_polynomial: Whether to show the polynomial (degree 2) surface
        show_cubic: Whether to show the cubic (degree 3) surface
        show_exponential: Whether to show the exponential curved line
        show_red_trendline: Whether to show red color-filtered trendline
        show_green_trendline: Whether to show green color-filtered trendline
        show_blue_trendline: Whether to show blue color-filtered trendline
        trendline_manager: TrendlineManager instance with fitted trendlines
        show_spheres: Whether to show spheres
        sphere_data: Optional DataFrame with sphere definitions (Centroid_X/Y/Z, Sphere, Radius)
        initial_elev: Initial elevation angle from matplotlib (degrees)
        initial_azim: Initial azimuth angle from matplotlib (degrees)  
        initial_roll: Initial roll angle from matplotlib (degrees)
        axis_ranges: Optional dict with 'x', 'y', 'z' keys containing (min, max) tuples for axis limits
    
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    # Filter to valid data points
    required_cols = ['Xnorm', 'Ynorm', 'Znorm']
    if not all(col in df.columns for col in required_cols):
        raise ValueError(f"DataFrame missing required columns: {required_cols}")
    
    valid_df = df.dropna(subset=required_cols).copy()
    
    if len(valid_df) == 0:
        raise ValueError("No valid data points to plot")
    
    # Get colors
    if 'Color' in valid_df.columns:
        colors = valid_df['Color'].fillna('blue')
    else:
        colors = ['blue'] * len(valid_df)
    
    # Get markers - Plotly 3D only supports limited symbols
    # Map matplotlib markers to Plotly-compatible ones
    marker_map = {
        'o': 'circle',
        '.': 'circle', 
        '*': 'diamond',
        '^': 'diamond',  # triangle-up not supported, use diamond
        'v': 'diamond-open',  # triangle-down not supported, use open diamond
        '<': 'square',  # triangle-left not supported, use square
        '>': 'square-open',  # triangle-right not supported, use open square
        's': 'square',
        '+': 'cross',
        'x': 'x',
        'D': 'diamond',
        'p': 'square',  # pentagon not supported, use square
        'h': 'diamond',  # hexagon not supported, use diamond
        'H': 'diamond-open',  # hexagon2 not supported, use open diamond
    }
    if 'Marker' in valid_df.columns:
        markers = valid_df['Marker'].fillna('o').map(lambda m: marker_map.get(m, 'circle'))
    else:
        markers = ['circle'] * len(valid_df)
    
    # Build hover text
    hover_text = []
    for idx, row in valid_df.iterrows():
        text = row.get('DataID', f'Point {idx}')
        if 'Cluster' in row and pd.notna(row['Cluster']) and str(row['Cluster']).strip() != '':
            text += f"<br>Cluster: {int(row['Cluster'])}"
        if 'DeltaE' in row and pd.notna(row['DeltaE']):
            text += f"<br>ΔE: {row['DeltaE']:.4f}"
        elif '∆E' in row and pd.notna(row['∆E']):
            text += f"<br>ΔE: {row['∆E']:.4f}"
        hover_text.append(text)
    
    # Add scatter plot
    fig.add_trace(go.Scatter3d(
        x=valid_df['Xnorm'],
        y=valid_df['Ynorm'],
        z=valid_df['Znorm'],
        mode='markers',
        marker=dict(
            size=6,
            color=colors,
            symbol=markers,
            line=dict(width=0)
        ),
        text=hover_text,
        hovertemplate='<b>%{text}</b><br>X: %{x:.4f}<br>Y: %{y:.4f}<br>Z: %{z:.4f}<extra></extra>',
        name='Data Points'
    ))
    
    # Add linear trendline if requested
    if show_trendline and len(valid_df) >= 3:
        try:
            from sklearn.decomposition import PCA
            
            # Linear regression: z = ax + by + c
            X = valid_df[['Xnorm', 'Ynorm']].values
            z = valid_df['Znorm'].values
            X_with_intercept = np.column_stack([X, np.ones(len(X))])
            coeffs, _, _, _ = np.linalg.lstsq(X_with_intercept, z, rcond=None)
            a, b, c = coeffs
            
            # Use PCA for line direction
            pca = PCA(n_components=1)
            pca.fit(X)
            direction = pca.components_[0]
            
            # Create line
            x_mean, y_mean = X.mean(axis=0)
            x_range = X[:, 0].max() - X[:, 0].min()
            y_range = X[:, 1].max() - X[:, 1].min()
            scale = max(x_range, y_range) * 1.5
            
            t = np.linspace(-scale, scale, 100)
            line_x = x_mean + direction[0] * t
            line_y = y_mean + direction[1] * t
            line_z = a * line_x + b * line_y + c
            
            fig.add_trace(go.Scatter3d(
                x=line_x, y=line_y, z=line_z,
                mode='lines',
                line=dict(color='black', width=2),
                name='Linear Trendline',
                hoverinfo='skip'
            ))
        except Exception as e:
            print(f"Could not add linear trendline: {e}")
    
    # Add polynomial surface if requested
    if show_polynomial and trendline_manager is not None and len(valid_df) >= 6:
        try:
            points = trendline_manager.get_polynomial_points(valid_df, num_points=20)
            fig.add_trace(go.Surface(
                x=points['x'], y=points['y'], z=points['z'],
                colorscale=[[0, 'cyan'], [1, 'cyan']],
                opacity=0.3,
                showscale=False,
                name='Polynomial (deg 2)',
                hoverinfo='skip'
            ))
        except Exception as e:
            print(f"Could not add polynomial surface: {e}")
    
    # Add cubic surface if requested
    if show_cubic and trendline_manager is not None and len(valid_df) >= 10:
        try:
            points = trendline_manager.get_cubic_points(valid_df, num_points=20)
            fig.add_trace(go.Surface(
                x=points['x'], y=points['y'], z=points['z'],
                colorscale=[[0, 'orange'], [1, 'orange']],
                opacity=0.3,
                showscale=False,
                name='Cubic (deg 3)',
                hoverinfo='skip'
            ))
        except Exception as e:
            print(f"Could not add cubic surface: {e}")
    
    # Add exponential curve if requested
    if show_exponential and trendline_manager is not None and len(valid_df) >= 4:
        try:
            curve_points = trendline_manager.get_exponential_curve_points(valid_df, num_points=100)
            if curve_points is not None:
                fig.add_trace(go.Scatter3d(
                    x=curve_points['x'],
                    y=curve_points['y'],
                    z=curve_points['z'],
                    mode='lines',
                    line=dict(color='red', width=4),
                    name='Exponential Curve',
                    hoverinfo='skip'
                ))
        except Exception as e:
            print(f"Could not add exponential curve: {e}")
    
    # Add color-filtered trendlines if requested
    color_trendlines = [
        (show_red_trendline, 'red', 'Red Trendline', 'dash'),
        (show_green_trendline, 'green', 'Green Trendline', 'dashdot'),
        (show_blue_trendline, 'blue', 'Blue Trendline', 'dot')
    ]
    
    for show_color, color_name, label, dash_style in color_trendlines:
        if show_color and trendline_manager is not None:
            try:
                # Calculate color-filtered regression if not already done
                trendline_manager.calculate_color_filtered_regression(valid_df, color_name)
                equation = trendline_manager.get_color_line_equation(color_name)
                
                if equation is not None:
                    a, b, c = equation
                    
                    # Use PCA for line direction (similar to main trendline)
                    try:
                        from sklearn.decomposition import PCA
                    except ImportError:
                        continue
                    
                    # Filter to color-specific points
                    color_df = valid_df[valid_df['Color'].str.lower() == color_name.lower()]
                    if len(color_df) < 3:
                        continue
                    
                    X = color_df[['Xnorm', 'Ynorm']].values
                    pca = PCA(n_components=1)
                    pca.fit(X)
                    direction = pca.components_[0]
                    
                    # Use ALL data range for consistent line length
                    x_mean, y_mean = X.mean(axis=0)
                    x_range = valid_df['Xnorm'].max() - valid_df['Xnorm'].min()
                    y_range = valid_df['Ynorm'].max() - valid_df['Ynorm'].min()
                    scale = max(x_range, y_range) * 1.5
                    
                    t = np.linspace(-scale, scale, 100)
                    line_x = x_mean + direction[0] * t
                    line_y = y_mean + direction[1] * t
                    line_z = a * line_x + b * line_y + c
                    
                    fig.add_trace(go.Scatter3d(
                        x=line_x, y=line_y, z=line_z,
                        mode='lines',
                        line=dict(color=color_name, width=2, dash=dash_style),
                        name=label,
                        hoverinfo='skip'
                    ))
            except Exception as e:
                print(f"Could not add {color_name} trendline: {e}")
    
    # Add spheres if requested
    if show_spheres and sphere_data is not None:
        _add_spheres_to_plot(fig, sphere_data)
    
    # Convert matplotlib angles to Plotly camera position
    # Matplotlib: elev (elevation), azim (azimuth), roll
    # Plotly: camera eye position in spherical coordinates
    # Note: matplotlib azimuth is 90° offset from standard spherical coords
    import math
    
    # Convert angles to radians
    # Matplotlib azimuth: 0° = -Y axis, 90° = +X axis, -90° = -X axis
    # Add 90° to align with standard spherical coordinates
    elev_rad = math.radians(initial_elev)
    azim_rad = math.radians(initial_azim + 90)
    
    # Calculate camera position (distance = 2.5 for good view)
    distance = 2.5
    cam_x = distance * math.cos(elev_rad) * math.cos(azim_rad)
    cam_y = distance * math.cos(elev_rad) * math.sin(azim_rad)
    cam_z = distance * math.sin(elev_rad)
    
    # Create title - note: started from matplotlib view but angles won't match exactly
    title_text = 'Interactive 3D Color Space Visualization<br><sub>Drag to rotate • Scroll to zoom • Shift+drag for box zoom</sub>'
    
    # Configure layout with improved hover label styling
    # Build axis configuration - show all data but inform user about matplotlib zoom
    xaxis_config = dict(showbackground=True, showgrid=True, showline=True)
    yaxis_config = dict(showbackground=True, showgrid=True, showline=True)
    zaxis_config = dict(showbackground=True, showgrid=True, showline=True)
    
    # Adjust title to show zoom info if matplotlib was zoomed
    zoom_info = ""
    if axis_ranges:
        zoom_info = f"<br><sub style='color:#666;'>Matplotlib view: X={axis_ranges.get('x', 'N/A')}, Y={axis_ranges.get('y', 'N/A')}, Z={axis_ranges.get('z', 'N/A')}</sub>"
        print(f"Matplotlib was zoomed to: X={axis_ranges.get('x')}, Y={axis_ranges.get('y')}, Z={axis_ranges.get('z')}")
        print("Note: Plotly shows full data range - use scroll to zoom to match matplotlib view")
    
    fig.update_layout(
        title=title_text + zoom_info,
        scene=dict(
            xaxis_title='a* (X)',
            yaxis_title='b* (Y)',
            zaxis_title='L* (Z)',
            camera=dict(
                eye=dict(x=cam_x, y=cam_y, z=cam_z),
                up=dict(x=0, y=0, z=1)
            ),
            aspectmode='data',  # Use 'data' to preserve true proportions and sphere shapes
            xaxis=xaxis_config,
            yaxis=yaxis_config,
            zaxis=zaxis_config,
            # Use turntable mode for better hover compatibility
            dragmode='turntable'  # Allows rotation with hover, use scroll to zoom
        ),
        hovermode='closest',
        width=1200,
        height=800,
        showlegend=True,
        # Enable modebar buttons for better control
        modebar=dict(
            orientation='v',  # Vertical toolbar
            bgcolor='rgba(255,255,255,0.7)'
        ),
        # Improve hover label appearance
        hoverlabel=dict(
            bgcolor="rgba(255, 255, 255, 0.85)",  # Semi-transparent white background
            font_size=11,
            font_family="Arial",
            font_color="#000000",  # Solid black text for readability
            bordercolor="rgba(100, 100, 100, 0.5)",  # Subtle border
            align="left"
        )
    )
    
    return fig


def _add_spheres_to_plot(fig, df):
    """Add spheres to the Plotly figure.
    
    Args:
        fig: Plotly Figure object
        df: DataFrame with Sphere, Centroid_X/Y/Z, Radius columns
    """
    print(f"DEBUG: Attempting to add spheres. DataFrame columns: {df.columns.tolist()}")
    print(f"DEBUG: Total rows in DataFrame: {len(df)}")
    
    # Check if required centroid columns exist (Sphere column is optional for color)
    required_cols = ['Centroid_X', 'Centroid_Y', 'Centroid_Z']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"DEBUG: Missing required centroid columns: {missing_cols}")
        return
    
    # Check what's in the centroid columns
    print(f"DEBUG: Centroid_X non-null count: {df['Centroid_X'].notna().sum()} / {len(df)}")
    print(f"DEBUG: Centroid_Y non-null count: {df['Centroid_Y'].notna().sum()} / {len(df)}")
    print(f"DEBUG: Centroid_Z non-null count: {df['Centroid_Z'].notna().sum()} / {len(df)}")
    print(f"DEBUG: Sample Centroid_X values: {df['Centroid_X'].head(10).tolist()}")
    print(f"DEBUG: Sample Centroid_Y values: {df['Centroid_Y'].head(10).tolist()}")
    print(f"DEBUG: Sample Centroid_Z values: {df['Centroid_Z'].head(10).tolist()}")
    
    # Match matplotlib logic: Filter for rows with valid centroid data
    # Sphere column is only used for color (gray if NaN)
    sphere_data = df.dropna(subset=['Centroid_X', 'Centroid_Y', 'Centroid_Z']).copy()
    print(f"DEBUG: Found {len(sphere_data)} rows with valid centroid coordinates")
    
    if len(sphere_data) == 0:
        print("DEBUG: No valid centroid data found")
        return
    
    # Get unique spheres based on centroid coordinates AND radius
    # This allows concentric spheres (same center, different radii) to display
    unique_spheres = sphere_data.drop_duplicates(subset=['Centroid_X', 'Centroid_Y', 'Centroid_Z', 'Radius'])
    print(f"DEBUG: Unique spheres to plot: {len(unique_spheres)} (including concentric spheres)")
    
    for _, row in unique_spheres.iterrows():
        center_x = row['Centroid_X']
        center_y = row['Centroid_Y']
        center_z = row['Centroid_Z']
        radius = row.get('Radius', 0.02)
        # Handle NaN radius values
        if pd.isna(radius):
            radius = 0.02
        else:
            radius = float(radius)
        # Match matplotlib logic: use Sphere column for color, default to gray if NaN
        color = row.get('Sphere', 'gray')
        if pd.isna(color):
            color = 'gray'
        
        print(f"DEBUG: Rendering sphere at ({center_x}, {center_y}, {center_z}) with radius {radius}, color={color}")
        
        # Create sphere mesh with enough points for smooth appearance
        u = np.linspace(0, 2 * np.pi, 15)
        v = np.linspace(0, np.pi, 15)
        x = center_x + radius * np.outer(np.cos(u), np.sin(v))
        y = center_y + radius * np.outer(np.sin(u), np.sin(v))
        z = center_z + radius * np.outer(np.ones(np.size(u)), np.cos(v))
        
        # Use Surface trace with color parameter directly (no surfacecolor array)
        fig.add_trace(go.Surface(
            x=x, y=y, z=z,
            colorscale=[[0, color], [1, color]],  # Map color directly
            showscale=False,
            opacity=0.25,  # Slightly transparent
            name=f'Sphere ({color})',
            hoverinfo='skip',
            showlegend=True
        ))


def open_interactive_view(df, show_trendline=True, show_polynomial=False, show_cubic=False,
                         show_exponential=False, show_red_trendline=False, 
                         show_green_trendline=False, show_blue_trendline=False,
                         trendline_manager=None, show_spheres=True, 
                         sphere_data=None, initial_elev=30, initial_azim=-60, initial_roll=0, 
                         axis_ranges=None):
    """Open an interactive Plotly view of the data in the browser.
    
    Args:
        df: DataFrame to visualize
        show_trendline: Whether to show linear trendline
        show_polynomial: Whether to show polynomial surface
        show_cubic: Whether to show cubic surface
        show_exponential: Whether to show exponential curve
        show_red_trendline: Whether to show red color-filtered trendline
        show_green_trendline: Whether to show green color-filtered trendline
        show_blue_trendline: Whether to show blue color-filtered trendline
        trendline_manager: TrendlineManager instance
        show_spheres: Whether to show spheres
        sphere_data: Optional DataFrame with sphere definitions
        initial_elev: Initial elevation angle from matplotlib
        initial_azim: Initial azimuth angle from matplotlib
        initial_roll: Initial roll angle from matplotlib
        axis_ranges: Optional dict with axis range limits from matplotlib
    """
    try:
        fig = create_plotly_visualization(df, show_trendline, show_polynomial, show_cubic,
                                         show_exponential, show_red_trendline, 
                                         show_green_trendline, show_blue_trendline,
                                         trendline_manager, show_spheres, 
                                         sphere_data, initial_elev, initial_azim, initial_roll, 
                                         axis_ranges)
        fig.show()
        print("Opened interactive Plotly view in browser")
    except Exception as e:
        print(f"Error opening Plotly view: {e}")
        import traceback
        traceback.print_exc()
