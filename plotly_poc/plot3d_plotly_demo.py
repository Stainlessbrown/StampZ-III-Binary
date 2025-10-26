#!/usr/bin/env python3
"""
Plotly 3D Color Space Visualization - Proof of Concept

This demonstrates how Plotly handles 3D scatter plots with:
- Interactive rotation (drag to rotate)
- Better camera control
- Hover tooltips
- Easy customization

Compare this interaction to matplotlib to decide if migration is worth it.
"""

import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

def load_ods_file(file_path):
    """Load ODS file and prepare data for plotting."""
    print(f"Loading file: {file_path}")
    df = pd.read_excel(file_path, engine='odf')
    
    # Show what columns we have
    print(f"Columns: {df.columns.tolist()}")
    print(f"Loaded {len(df)} rows")
    
    # Filter to rows with valid normalized coordinates
    required_cols = ['Xnorm', 'Ynorm', 'Znorm']
    if all(col in df.columns for col in required_cols):
        valid_df = df.dropna(subset=required_cols)
        print(f"Found {len(valid_df)} rows with valid X/Y/Z coordinates")
        return valid_df
    else:
        print(f"ERROR: Missing required columns. Need: {required_cols}")
        return None

def create_plotly_3d_scatter(df):
    """Create an interactive 3D scatter plot using Plotly."""
    
    # Create the figure
    fig = go.Figure()
    
    # Get unique colors if they exist, otherwise use a default
    if 'Color' in df.columns:
        colors = df['Color'].fillna('blue')
    else:
        colors = ['blue'] * len(df)
    
    # Get markers if they exist
    if 'Marker' in df.columns:
        # Plotly uses different marker symbols than matplotlib
        # Map common matplotlib markers to plotly symbols
        marker_map = {
            'o': 'circle',
            '.': 'circle',
            '*': 'diamond',
            '^': 'triangle-up',
            'v': 'triangle-down',
            's': 'square',
            '+': 'cross',
            'x': 'x',
            'D': 'diamond'
        }
        markers = df['Marker'].fillna('o').map(lambda m: marker_map.get(m, 'circle'))
    else:
        markers = ['circle'] * len(df)
    
    # Get data IDs for hover text
    if 'DataID' in df.columns:
        hover_text = df['DataID'].fillna('Unknown')
    else:
        hover_text = [f'Point {i}' for i in range(len(df))]
    
    # Add cluster info to hover if available
    if 'Cluster' in df.columns:
        hover_text = [f"{text}<br>Cluster: {cluster}" 
                     for text, cluster in zip(hover_text, df['Cluster'].fillna('None'))]
    
    # Add Delta E info if available
    if '∆E' in df.columns or 'DeltaE' in df.columns:
        delta_col = '∆E' if '∆E' in df.columns else 'DeltaE'
        hover_text = [f"{text}<br>ΔE: {de:.4f}" if pd.notna(de) else text
                     for text, de in zip(hover_text, df[delta_col])]
    
    # Create scatter plot
    fig.add_trace(go.Scatter3d(
        x=df['Xnorm'],
        y=df['Ynorm'],
        z=df['Znorm'],
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
    
    # Add trendline if we can calculate it
    if len(df) >= 3:
        try:
            import numpy as np
            from sklearn.decomposition import PCA
            
            # Simple linear regression for trendline: z = ax + by + c
            X = df[['Xnorm', 'Ynorm']].values
            z = df['Znorm'].values
            
            # Add intercept term
            X_with_intercept = np.column_stack([X, np.ones(len(X))])
            
            # Solve for coefficients
            coeffs, _, _, _ = np.linalg.lstsq(X_with_intercept, z, rcond=None)
            a, b, c = coeffs
            
            print(f"Trendline equation: z = {a:.4f}x + {b:.4f}y + {c:.4f}")
            
            # Use PCA to find principal direction
            pca = PCA(n_components=1)
            pca.fit(X)
            direction = pca.components_[0]
            
            # Create line along principal direction
            x_mean, y_mean = X.mean(axis=0)
            x_range = X[:, 0].max() - X[:, 0].min()
            y_range = X[:, 1].max() - X[:, 1].min()
            scale = max(x_range, y_range) * 1.5
            
            t = np.linspace(-scale, scale, 100)
            line_x = x_mean + direction[0] * t
            line_y = y_mean + direction[1] * t
            line_z = a * line_x + b * line_y + c
            
            # Add trendline to plot
            fig.add_trace(go.Scatter3d(
                x=line_x,
                y=line_y,
                z=line_z,
                mode='lines',
                line=dict(color='black', width=2),
                name='Trendline',
                hoverinfo='skip'
            ))
            
        except Exception as e:
            print(f"Could not add trendline: {e}")
    
    # Update layout for better 3D viewing
    fig.update_layout(
        title='3D Color Space Visualization (Plotly POC)',
        scene=dict(
            xaxis_title='a* (X)',
            yaxis_title='b* (Y)',
            zaxis_title='L* (Z)',
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.5),  # Initial camera position
                up=dict(x=0, y=0, z=1)  # Z-axis points up
            ),
            aspectmode='data'  # Keep aspect ratio realistic
        ),
        hovermode='closest',
        width=1200,
        height=800,
        showlegend=True
    )
    
    return fig

def main():
    """Main entry point."""
    print("=" * 60)
    print("Plotly 3D Color Space Visualization - Proof of Concept")
    print("=" * 60)
    
    # Check for command line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Try to find a test file
        test_file = Path("/Users/stanbrown/Desktop/Marianne de Muller/15 Fr/Mar_Mul_15_AVG_averages.ods")
        if test_file.exists():
            file_path = str(test_file)
            print(f"\nUsing test file: {file_path}")
        else:
            print("\nUsage: python3 plot3d_plotly_demo.py <path_to_ods_file>")
            print("\nOr provide a file path as argument")
            return
    
    # Load data
    df = load_ods_file(file_path)
    if df is None:
        return
    
    # Create plot
    print("\nCreating interactive 3D plot...")
    fig = create_plotly_3d_scatter(df)
    
    # Show the plot (opens in browser)
    print("\nOpening plot in browser...")
    print("\nInteraction tips:")
    print("- DRAG to rotate the 3D view")
    print("- SCROLL to zoom in/out")
    print("- HOVER over points to see details")
    print("- Try rotating to see how smooth it is!")
    print("\nClose the browser tab when done.")
    
    fig.show()

if __name__ == '__main__':
    main()
