#!/usr/bin/env python3
"""
Hue-Based Color Sorting for StampZ
Provides functions to sort colors by hue with special handling for philatelic colors.
Handles browns, grays, blacks, and whites appropriately for stamp analysis.
"""

import numpy as np
from typing import List, Tuple, Optional, Union, Dict
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
    BROWN = 3  # Browns - low saturation chromatic colors
    CHROMATIC = 4  # Saturated colors with distinct hues
    
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
        # 2. Gray: Low saturation (s < 0.2) but not black or white
        # 3. White: High lightness (l > 0.85) and low saturation (s < 0.2)  
        # 4. Brown: Low saturation AND low lightness (visually distinct from chromatic)
        # 5. Chromatic: All other colors sorted by hue
        
        if l < 0.15:  # Black - very dark colors
            sort_key = (0, l, s)  # Group 0: blacks, then by lightness
        elif s < 0.2 and not (l > 0.85):  # Gray - low saturation, not white
            sort_key = (1, l, s)  # Group 1: grays, then by lightness
        elif l > 0.85 and s < 0.2:  # White - bright and unsaturated
            sort_key = (2, -l, s)  # Group 2: whites, brightest first
        elif s < 0.65 and l < 0.5:  # Browns - low-medium saturation AND low lightness
            sort_key = (3, h, l, s)  # Group 3: browns by hue, then lightness
        else:  # Chromatic colors - bright, saturated colors
            sort_key = (4, h, s, l)  # Group 4: by hue, then saturation, then lightness
        
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
    elif s < 0.65 and l < 0.5:  # Browns: low-medium saturation AND low lightness
        return HueGroup.BROWN
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

def filter_by_hue_range(colors_rgb: List[Tuple[int, int, int]], 
                       center_hue: float, 
                       hue_range: float = 30.0) -> List[Tuple[int, int, int]]:
    """
    Filter colors to only include those within a specific hue range.
    Perfect for stamp varieties that span similar hues (e.g., pink→red→red-orange).
    
    Args:
        colors_rgb: List of RGB color tuples
        center_hue: Center hue in degrees (0-360)
        hue_range: Total range in degrees (±range/2 around center)
        
    Returns:
        Filtered list of RGB colors within the hue range
    """
    filtered_colors = []
    half_range = hue_range / 2.0
    
    for rgb in colors_rgb:
        group = get_hue_group(*rgb)
        
        # Only filter chromatic colors by hue
        if group not in [HueGroup.CHROMATIC, HueGroup.BROWN]:
            continue
            
        h, s, l = rgb_to_hsl(*rgb)
        
        # Handle hue wrapping around 0/360 degrees
        min_hue = (center_hue - half_range) % 360
        max_hue = (center_hue + half_range) % 360
        
        if min_hue <= max_hue:
            # Normal range (doesn't wrap around)
            if min_hue <= h <= max_hue:
                filtered_colors.append(rgb)
        else:
            # Range wraps around 0/360 (e.g., 350-10 degrees)
            if h >= min_hue or h <= max_hue:
                filtered_colors.append(rgb)
    
    return filtered_colors

def get_variety_hue_ranges(variety_type: str) -> List[Tuple[str, float, float]]:
    """
    Get predefined hue ranges for common stamp color varieties.
    
    Args:
        variety_type: Type of variety (e.g., 'red_varieties', 'blue_varieties')
        
    Returns:
        List of (name, center_hue, range) tuples
    """
    varieties = {
        'red_varieties': [
            ('Pink to Red-Orange', 15, 45),  # Covers pink→red→red-orange
            ('Deep Red Varieties', 0, 20),   # Pure reds and crimsons
        ],
        'blue_varieties': [
            ('Blue to Blue-Green', 210, 60),  # Blue→cyan varieties
            ('Deep Blue Varieties', 240, 40), # Pure blues
        ],
        'green_varieties': [
            ('Yellow-Green to Blue-Green', 120, 60),  # Full green spectrum
            ('Pure Green Varieties', 120, 30),        # True greens
        ],
        'brown_varieties': [
            ('Orange-Brown Varieties', 30, 40),   # Orange to brown transition
            ('Red-Brown Varieties', 15, 30),      # Red to brown transition
        ]
    }
    
    return varieties.get(variety_type, [])

def get_user_friendly_hue_ranges() -> Dict[str, Tuple[float, float]]:
    """
    Get user-friendly hue range names with their corresponding hue ranges.
    Perfect for UI dropdowns and user selection.
    
    Returns:
        Dictionary mapping friendly names to (center_hue, range) tuples
        Special keys for achromatic colors: 'BLACK', 'GRAY', 'WHITE', 'BROWN'
    """
    return {
        # Achromatic colors (special handling)
        'Black': 'BLACK',
        'Gray': 'GRAY', 
        'White': 'WHITE',
        'Brown': 'BROWN',
        
        # Primary colors and adjacent ranges
        'Red': (0, 30),
        'Red-Orange': (15, 30),
        'Orange': (45, 30),
        'Orange-Yellow': (75, 30),
        'Yellow': (75, 30),
        'Yellow-Green': (105, 30),
        'Green': (120, 30),
        'Green-Blue': (135, 30),
        'Blue': (240, 30),
        'Blue-Violet': (255, 30),
        'Violet': (285, 30),
        'Violet-Red': (315, 30),
        
        # Broader ranges
        'All Reds': (0, 60),        # Red + Red-Orange
        'All Oranges': (30, 60),    # Red-Orange + Orange + Orange-Yellow
        'All Yellows': (60, 60),    # Orange-Yellow + Yellow + Yellow-Green
        'All Greens': (120, 60),    # Yellow-Green + Green + Green-Blue
        'All Blues': (210, 120),    # Green-Blue + Blue + Blue-Violet
        'All Violets': (300, 60),   # Blue-Violet + Violet + Violet-Red
        
        # Combined achromatic
        'All Achromatic': 'ALL_ACHROMATIC',  # Black + Gray + White
        'All Neutrals': 'ALL_NEUTRALS',      # Black + Gray + White + Brown
        
        # Stamp-specific ranges
        'Pink to Red-Orange': (15, 45),   # Common stamp variety
        'Brown Tones': 'BROWN',           # All browns
        'Deep Blues': (240, 40),          # Navy, royal blue range
    }

def filter_by_friendly_name(colors_rgb: List[Tuple[int, int, int]], 
                           friendly_name: str) -> List[Tuple[int, int, int]]:
    """
    Filter colors using user-friendly hue range names.
    
    Args:
        colors_rgb: List of RGB color tuples
        friendly_name: User-friendly name like 'Green-Blue', 'Green', 'Black', 'White'
        
    Returns:
        Filtered list of RGB colors in that hue range
    """
    ranges = get_user_friendly_hue_ranges()
    
    if friendly_name not in ranges:
        available = ', '.join(ranges.keys())
        raise ValueError(f"Unknown hue range '{friendly_name}'. Available: {available}")
    
    range_value = ranges[friendly_name]
    
    # Handle special achromatic cases
    if isinstance(range_value, str):
        if range_value == 'BLACK':
            return filter_by_hue_groups(colors_rgb, [HueGroup.BLACK])
        elif range_value == 'GRAY':
            return filter_by_hue_groups(colors_rgb, [HueGroup.GRAY])
        elif range_value == 'WHITE':
            return filter_by_hue_groups(colors_rgb, [HueGroup.WHITE])
        elif range_value == 'BROWN':
            return filter_by_hue_groups(colors_rgb, [HueGroup.BROWN])
        elif range_value == 'ALL_ACHROMATIC':
            return filter_by_hue_groups(colors_rgb, [HueGroup.BLACK, HueGroup.GRAY, HueGroup.WHITE])
        elif range_value == 'ALL_NEUTRALS':
            return filter_by_hue_groups(colors_rgb, [HueGroup.BLACK, HueGroup.GRAY, HueGroup.WHITE, HueGroup.BROWN])
        else:
            raise ValueError(f"Unknown special range value: {range_value}")
    else:
        # Handle chromatic hue ranges
        center_hue, hue_range = range_value
        return filter_by_hue_range(colors_rgb, center_hue, hue_range)

def get_available_hue_names() -> List[str]:
    """
    Get list of all available user-friendly hue range names.
    Perfect for populating UI dropdowns.
    
    Returns:
        List of friendly hue range names in logical order
    """
    ranges = get_user_friendly_hue_ranges()
    
    # Group them logically for UI - achromatic first, then chromatic
    achromatic = ['Black', 'Gray', 'White', 'Brown']
    achromatic_groups = ['All Achromatic', 'All Neutrals']
    primary = ['Red', 'Orange', 'Yellow', 'Green', 'Blue', 'Violet']
    adjacent = ['Red-Orange', 'Orange-Yellow', 'Yellow-Green', 'Green-Blue', 'Blue-Violet', 'Violet-Red']
    broad = ['All Reds', 'All Oranges', 'All Yellows', 'All Greens', 'All Blues', 'All Violets']
    special = ['Pink to Red-Orange', 'Brown Tones', 'Deep Blues']
    
    return achromatic + achromatic_groups + primary + adjacent + broad + special

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
    
    # Test user-friendly hue filtering
    print("\n" + "="*50)
    print("Testing User-Friendly Hue Selection:")
    print("="*50)
    
    # Add test colors spanning the green range
    green_test_colors = [
        (173, 255, 47),   # Green-Yellow
        (0, 255, 0),      # Pure Green
        (0, 255, 127),    # Spring Green (Green-Blue)
        (32, 178, 170),   # Light Sea Green (more blue-green)
        (255, 255, 0),    # Yellow (should not appear)
        (0, 0, 255),      # Blue (should not appear)
    ]
    
    print("Available hue range names:")
    available_names = get_available_hue_names()
    for i, name in enumerate(available_names[:12], 1):  # Show first 12
        print(f"  {i:2d}. {name}")
    
    print("\nTesting your specific request - Green-Blue, Green, Green-Yellow:")
    
    for hue_name in ['Green-Blue', 'Green', 'Yellow-Green']:  # Note: Yellow-Green instead of Green-Yellow
        try:
            filtered = filter_by_friendly_name(green_test_colors, hue_name)
            print(f"\n{hue_name} colors: {len(filtered)} found")
            for r, g, b in filtered:
                h, s, l = rgb_to_hsl(r, g, b)
                print(f"  RGB({r:3d}, {g:3d}, {b:3d}) - H:{h:.1f}°")
        except ValueError as e:
            print(f"\n{hue_name}: {e}")
    
    # Filter to only show achromatic colors
    achromatic_only = filter_by_hue_groups(colors_to_sort, [HueGroup.BLACK, HueGroup.GRAY, HueGroup.WHITE])
    print("\nAchromatic colors only:")
    for r, g, b in achromatic_only:
        group = get_hue_group(r, g, b)
        print(f"RGB({r:3d}, {g:3d}, {b:3d}) - {group.name}")
    
    # Test new brown filtering
    brown_only = filter_by_hue_groups(colors_to_sort, [HueGroup.BROWN])
    print("\nBrown colors only:")
    for r, g, b in brown_only:
        group = get_hue_group(r, g, b)
        h, s, l = rgb_to_hsl(r, g, b)
        print(f"RGB({r:3d}, {g:3d}, {b:3d}) - {group.name} (H:{h:.1f}°, S:{s:.2f}, L:{l:.2f})")
    
    # Test hue range filtering for red varieties
    print("\n" + "="*50)
    print("Testing Hue Range Filtering for Stamp Varieties:")
    print("="*50)
    
    # Add more test colors for variety testing
    variety_test_colors = colors_to_sort + [
        (255, 192, 203),  # Pink
        (220, 20, 60),    # Crimson
        (255, 69, 0),     # Red-Orange
        (205, 92, 92),    # Indian Red
        (178, 34, 34),    # Firebrick
    ]
    
    # Filter for pink→red→red-orange varieties (center on red at 15°, ±22.5° range)
    red_varieties = filter_by_hue_range(variety_test_colors, center_hue=15, hue_range=45)
    print(f"\nRed varieties (pink→red→red-orange, 15°±22.5°): {len(red_varieties)} colors")
    for r, g, b in red_varieties:
        h, s, l = rgb_to_hsl(r, g, b)
        hue_range = get_chromatic_hue_range(h)
        hue_name = hue_range[0] if hue_range else "Unknown"
        print(f"RGB({r:3d}, {g:3d}, {b:3d}) - {hue_name} (H:{h:.1f}°)")
