#!/usr/bin/env python3
"""
Hue-Based Color Sorting for StampZ
Provides functions to sort colors by hue with special handling for philatelic colors.
Handles browns, grays, blacks, and whites appropriately for stamp analysis.
"""

import numpy as np
from typing import List, Tuple, Optional, Union
from enum import Enum

try:
    from skimage import color
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False
    print("Warning: scikit-image not available. Install with: pip install scikit-image")

class HueGroup(Enum):
    """Predefined hue groups for philatelic color organization."""
    BLACK = 0
    GRAY = 1  
    WHITE = 2
    CHROMATIC = 3  # All colors with distinct hues
    
    # Specific hue ranges for chromatic colors
    RED = (0, 30)
    ORANGE = (30, 60)
    YELLOW = (60, 90)
    GREEN = (90, 150)
    CYAN = (150, 210)
    BLUE = (210, 270)
    MAGENTA = (270, 330)
    RED_VIOLET = (330, 360)

def rgb_to_hsl(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """
    Convert RGB to HSL color space.
    
    Args:
        r, g, b: RGB values (0-255)
        
    Returns:
        Tuple of (hue, saturation, lightness) where:
        - hue: 0-360 degrees
        - saturation: 0-1
        - lightness: 0-1
    """
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    diff = max_val - min_val
    
    # Lightness
    l = (max_val + min_val) / 2.0
    
    if diff == 0:
        h = s = 0  # achromatic
    else:
        # Saturation
        s = diff / (2 - max_val - min_val) if l > 0.5 else diff / (max_val + min_val)
        
        # Hue
        if max_val == r:
            h = (60 * ((g - b) / diff) + 360) % 360
        elif max_val == g:
            h = (60 * ((b - r) / diff) + 120) % 360
        else:  # max_val == b
            h = (60 * ((r - g) / diff) + 240) % 360
    
    return h, s, l

def sort_lab_by_hue(lab_colors: List[Union[Tuple[float, float, float], List[float]]]) -> List[Tuple[float, float, float]]:
    """
    Sorts a list of L*a*b* colors by their hue using scikit-image.
    
    Args:
        lab_colors: List of L*a*b* color tuples/arrays
                   Each color should be in the range L: [0, 100], a,b: [-128, 127]
    
    Returns:
        List of L*a*b* colors sorted by hue
    """
    if not HAS_SKIMAGE:
        raise ImportError("scikit-image is required for lab_to_rgb conversion. Install with: pip install scikit-image")
    
    if not lab_colors:
        return []
    
    # Convert L*a*b* colors to RGB then HSV
    rgb_colors = color.lab2rgb(np.array(lab_colors))
    hsv_colors = color.rgb2hsv(rgb_colors)
    
    # Extract hue (the first component of HSV)
    hues = hsv_colors[:, 0] * 360  # Convert from 0-1 to 0-360 degrees
    
    # Create a list of (hue, original_lab_color) tuples
    indexed_colors = list(zip(hues, lab_colors))
    
    # Sort based on hue
    sorted_indexed_colors = sorted(indexed_colors, key=lambda item: item[0])
    
    # Extract the sorted L*a*b* colors
    sorted_lab_colors = [item[1] for item in sorted_indexed_colors]
    
    return sorted_lab_colors

def sort_colors_philatelic(colors_rgb: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int]]:
    """
    Sort colors with philatelic considerations.
    Groups colors as: Black -> Gray -> White -> Hue-sorted chromatic colors
    Browns are treated as dark oranges and sorted with chromatic colors.
    
    Args:
        colors_rgb: List of RGB color tuples (0-255 each)
        
    Returns:
        List of RGB colors sorted philatelically
    """
    if not colors_rgb:
        return []
    
    processed_colors = []
    
    for r, g, b in colors_rgb:
        h, s, l = rgb_to_hsl(r, g, b)
        
        # Define sorting logic with philatelic considerations:
        # 1. Black: Low lightness (l < 0.15) regardless of saturation
        # 2. White: High lightness (l > 0.85) and low saturation (s < 0.2)  
        # 3. Gray: Low saturation (s < 0.2) but not black or white
        # 4. All other colors (including brown): Sort by hue
        
        if l < 0.15:  # Black - very dark colors
            sort_key = (0, l, s)  # Group 0: blacks, then by lightness
        elif l > 0.85 and s < 0.2:  # White - bright and unsaturated
            sort_key = (2, -l, s)  # Group 2: whites, brightest first  
        elif s < 0.2:  # Gray - low saturation, not black/white
            sort_key = (1, l, s)  # Group 1: grays, then by lightness
        else:  # Chromatic colors (including browns as dark oranges)
            sort_key = (3, h, s, l)  # Group 3: by hue, then saturation, then lightness
        
        processed_colors.append((sort_key, (r, g, b)))
    
    # Sort and extract original RGB tuples
    processed_colors.sort(key=lambda x: x[0])
    return [color for key, color in processed_colors]

def get_hue_group(r: int, g: int, b: int) -> HueGroup:
    """
    Determine which hue group an RGB color belongs to.
    
    Args:
        r, g, b: RGB values (0-255)
        
    Returns:
        HueGroup enum value
    """
    h, s, l = rgb_to_hsl(r, g, b)
    
    if l < 0.15:
        return HueGroup.BLACK
    elif l > 0.85 and s < 0.2:
        return HueGroup.WHITE  
    elif s < 0.2:
        return HueGroup.GRAY
    else:
        return HueGroup.CHROMATIC

def filter_by_hue_groups(colors_rgb: List[Tuple[int, int, int]], 
                        selected_groups: List[HueGroup]) -> List[Tuple[int, int, int]]:
    """
    Filter colors to only include specified hue groups.
    Useful for the Compare function to select specific color types.
    
    Args:
        colors_rgb: List of RGB color tuples
        selected_groups: List of HueGroup enums to include
        
    Returns:
        Filtered list of RGB colors
    """
    filtered_colors = []
    
    for rgb in colors_rgb:
        group = get_hue_group(*rgb)
        if group in selected_groups:
            filtered_colors.append(rgb)
    
    return filtered_colors

def get_chromatic_hue_range(h: float) -> Optional[Tuple[str, Tuple[float, float]]]:
    """
    Get the named hue range for a chromatic color.
    
    Args:
        h: Hue value in degrees (0-360)
        
    Returns:
        Tuple of (name, (min_hue, max_hue)) or None if not chromatic
    """
    # Define hue ranges with some overlap at boundaries
    hue_ranges = [
        ("Red", (0, 30)),
        ("Orange", (30, 60)), 
        ("Yellow", (60, 90)),
        ("Green", (90, 150)),
        ("Cyan", (150, 210)),
        ("Blue", (210, 270)),
        ("Magenta", (270, 330)),
        ("Red-Violet", (330, 360))
    ]
    
    for name, (min_h, max_h) in hue_ranges:
        if min_h <= h < max_h:
            return (name, (min_h, max_h))
    
    return None

# Example usage and testing
if __name__ == "__main__":
    # Example L*a*b* colors for testing hue sorting
    lab_colors_unsorted = [
        [50, 70, 50],   # Orange-red
        [50, -50, 50],  # Green-yellow
        [50, 0, -50],   # Blue
        [50, 50, -50],  # Magenta
        [50, -70, -50]  # Cyan
    ]
    
    if HAS_SKIMAGE:
        print("Testing L*a*b* hue sorting:")
        sorted_lab = sort_lab_by_hue(lab_colors_unsorted)
        
        print("Unsorted L*a*b* colors:")
        for c in lab_colors_unsorted:
            print(f"L={c[0]:.2f}, a={c[1]:.2f}, b={c[2]:.2f}")
        
        print("\nSorted L*a*b* colors by hue:")
        for c in sorted_lab:
            print(f"L={c[0]:.2f}, a={c[1]:.2f}, b={c[2]:.2f}")
    
    # Example RGB colors for philatelic sorting
    colors_to_sort = [
        (255, 255, 255),  # White
        (0, 0, 0),        # Black
        (150, 75, 0),     # Brown
        (128, 128, 128),  # Gray
        (255, 0, 0),      # Red
        (255, 165, 0),    # Orange
        (0, 128, 0)       # Green
    ]
    
    print("\n" + "="*50)
    print("Testing philatelic color sorting:")
    print("="*50)
    
    sorted_colors = sort_colors_philatelic(colors_to_sort)
    
    print("Original colors:")
    for i, (r, g, b) in enumerate(colors_to_sort):
        group = get_hue_group(r, g, b)
        print(f"{i+1}. RGB({r:3d}, {g:3d}, {b:3d}) - Group: {group.name}")
    
    print("\nSorted colors (philatelic order):")
    for i, (r, g, b) in enumerate(sorted_colors):
        group = get_hue_group(r, g, b)
        h, s, l = rgb_to_hsl(r, g, b)
        hue_info = ""
        if group == HueGroup.CHROMATIC:
            hue_range = get_chromatic_hue_range(h)
            if hue_range:
                hue_info = f" - {hue_range[0]} (H:{h:.1f}°)"
        print(f"{i+1}. RGB({r:3d}, {g:3d}, {b:3d}) - Group: {group.name}{hue_info}")
    
    # Test filtering by hue groups
    print("\n" + "="*50)
    print("Testing hue group filtering:")
    print("="*50)
    
    # Filter to only show chromatic colors (excluding black, white, gray)
    chromatic_only = filter_by_hue_groups(colors_to_sort, [HueGroup.CHROMATIC])
    print("Chromatic colors only:")
    for r, g, b in chromatic_only:
        h, s, l = rgb_to_hsl(r, g, b)
        hue_range = get_chromatic_hue_range(h)
        hue_name = hue_range[0] if hue_range else "Unknown"
        print(f"RGB({r:3d}, {g:3d}, {b:3d}) - {hue_name} (H:{h:.1f}°)")
    
    # Filter to only show achromatic colors
    achromatic_only = filter_by_hue_groups(colors_to_sort, [HueGroup.BLACK, HueGroup.GRAY, HueGroup.WHITE])
    print("\nAchromatic colors only:")
    for r, g, b in achromatic_only:
        group = get_hue_group(r, g, b)
        print(f"RGB({r:3d}, {g:3d}, {b:3d}) - {group.name}")