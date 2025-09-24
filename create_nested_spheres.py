#!/usr/bin/env python3
"""
Create two spheres at the same centroid with different sizes and distinct colors.
This demonstrates nested spheres where you can see one inside the other due to translucency.
"""

import pandas as pd
from plot3d.sphere_manager import SphereManager
import matplotlib.pyplot as plt
import numpy as np

def create_nested_spheres():
    """Create two spheres at the same location with different sizes and colors."""
    
    # Same centroid coordinates for both spheres
    centroid_x, centroid_y, centroid_z = 0.5, 0.5, 0.5
    
    # Create DataFrame with two rows - same centroid, different colors and sizes
    sphere_data = {
        'DataID': ['Sphere_1', 'Sphere_2'],
        'Xnorm': [centroid_x, centroid_x],  # Same position 
        'Ynorm': [centroid_y, centroid_y],  # Same position
        'Znorm': [centroid_z, centroid_z],  # Same position
        'Cluster': [1, 2],
        'Centroid_X': [centroid_x, centroid_x],  # Required - same centroid
        'Centroid_Y': [centroid_y, centroid_y],  # Required - same centroid  
        'Centroid_Z': [centroid_z, centroid_z],  # Required - same centroid
        'Sphere': ['green/0.03', 'orange/0.06'],  # Different colors and sizes
        'Radius': ['', '']  # Using the Sphere column format instead
    }
    
    df = pd.DataFrame(sphere_data)
    print("Created DataFrame for nested spheres:")
    print(df[['DataID', 'Centroid_X', 'Centroid_Y', 'Centroid_Z', 'Sphere']].to_string())
    
    # Create 3D plot
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Set up the plot appearance
    ax.set_xlabel('X (normalized)')
    ax.set_ylabel('Y (normalized)')
    ax.set_zlabel('Z (normalized)')
    ax.set_title('Nested Spheres: Green (smaller) inside Orange (larger)')
    
    # Set axis limits to better show the spheres
    ax.set_xlim([0.3, 0.7])
    ax.set_ylim([0.3, 0.7])
    ax.set_zlim([0.3, 0.7])
    
    # Create sphere manager
    sphere_manager = SphereManager(ax, None, df)
    
    print(f"\nRendering spheres...")
    print(f"Green sphere radius: 0.03 (smaller, inner)")
    print(f"Orange sphere radius: 0.06 (larger, outer)")
    print(f"Both spheres at centroid: ({centroid_x}, {centroid_y}, {centroid_z})")
    print(f"Transparency: {sphere_manager.ALPHA} (translucent)")
    
    # Render spheres - this should create nested spheres
    sphere_manager.render_spheres()
    
    print(f"Successfully rendered {len(sphere_manager.sphere_objects)} sphere objects")
    
    # Show the plot
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    create_nested_spheres()