#!/usr/bin/env python3
"""
Color display utility functions for StampZ
Handles conditional display of RGB, CMY, and L*a*b* values based on user preferences.
"""

from typing import Tuple, Optional


def get_conditional_color_info(
    rgb: Tuple[float, float, float], 
    lab: Optional[Tuple[float, float, float]] = None,
    show_hex: bool = False
) -> str:
    """Generate color information string based on user preferences.
    
    Args:
        rgb: RGB color values (0-255)
        lab: L*a*b* color values (optional)
        show_hex: Whether to include HEX code display
        
    Returns:
        Formatted color information string based on user preferences
    """
    try:
        from utils.user_preferences import get_preferences_manager
        prefs = get_preferences_manager()
        
        # Get user preferences for what to display
        show_rgb = prefs.get_export_include_rgb()
        show_lab = prefs.get_export_include_lab()
        show_cmy = prefs.get_export_include_cmy()
        
        # Always show at least one color space to avoid empty display
        if not show_rgb and not show_lab and not show_cmy and not show_hex:
            show_rgb = True
            show_lab = True
            show_hex = True
        
        color_info_parts = []
        
        # Add L*a*b* info if enabled and available
        if show_lab and lab is not None:
            color_info_parts.append(f"L*a*b*: {lab[0]:.3f}, {lab[1]:.3f}, {lab[2]:.3f}")
        
        # Add RGB info if enabled
        if show_rgb:
            color_info_parts.append(f"RGB: {rgb[0]:.2f}, {rgb[1]:.2f}, {rgb[2]:.2f}")
        
        # Add CMY info if enabled (CMY = 255 - RGB)
        if show_cmy:
            cmy = (255 - rgb[0], 255 - rgb[1], 255 - rgb[2])
            color_info_parts.append(f"CMY: {cmy[0]:.2f}, {cmy[1]:.2f}, {cmy[2]:.2f}")
        
        # Add HEX code if enabled
        if show_hex:
            hex_code = f"#{int(rgb[0]):02X}{int(rgb[1]):02X}{int(rgb[2]):02X}"
            color_info_parts.append(f"HEX: {hex_code}")
        
        return "\n".join(color_info_parts)
        
    except Exception as e:
        print(f"Error getting color display preferences: {e}")
        # Fallback to showing all values
        fallback_parts = []
        if lab is not None:
            fallback_parts.append(f"L*a*b*: {lab[0]:.3f}, {lab[1]:.3f}, {lab[2]:.3f}")
        fallback_parts.append(f"RGB: {rgb[0]:.2f}, {rgb[1]:.2f}, {rgb[2]:.2f}")
        if show_hex:
            hex_code = f"#{int(rgb[0]):02X}{int(rgb[1]):02X}{int(rgb[2]):02X}"
            fallback_parts.append(f"HEX: {hex_code}")
        return "\n".join(fallback_parts)


def get_conditional_color_values_text(
    rgb: Tuple[float, float, float], 
    lab: Optional[Tuple[float, float, float]] = None,
    compact: bool = False,
    show_hex: bool = False
) -> str:
    """Generate color values text in a more compact format for comparison views.
    
    Args:
        rgb: RGB color values (0-255)
        lab: L*a*b* color values (optional)
        compact: If True, use compact single-line format
        
    Returns:
        Formatted color values text based on user preferences
    """
    try:
        from utils.user_preferences import get_preferences_manager
        prefs = get_preferences_manager()
        
        # Get user preferences for what to display
        show_rgb = prefs.get_export_include_rgb()
        show_lab = prefs.get_export_include_lab()
        show_cmy = prefs.get_export_include_cmy()
        
        # Always show at least one color space to avoid empty display
        if not show_rgb and not show_lab and not show_cmy:
            show_rgb = True
            show_lab = True
        
        if compact:
            # Single-line compact format for comparison views
            parts = []
            if show_lab and lab is not None:
                parts.append(f"L*: {lab[0]:>8.3f}  a*: {lab[1]:>8.3f}  b*: {lab[2]:>8.3f}")
            if show_rgb:
                parts.append(f"R: {rgb[0]:>6.2f}  G: {rgb[1]:>6.2f}  B: {rgb[2]:>6.2f}")
            if show_cmy:
                cmy = (255 - rgb[0], 255 - rgb[1], 255 - rgb[2])
                parts.append(f"C: {cmy[0]:>6.2f}  M: {cmy[1]:>6.2f}  Y: {cmy[2]:>6.2f}")
            return "\n".join(parts)
        else:
            # Multi-line format for library views
            return get_conditional_color_info(rgb, lab)
            
    except Exception as e:
        print(f"Error getting color display preferences: {e}")
        # Fallback based on format
        if compact:
            fallback_parts = []
            if lab is not None:
                fallback_parts.append(f"L*: {lab[0]:>8.3f}  a*: {lab[1]:>8.3f}  b*: {lab[2]:>8.3f}")
            fallback_parts.append(f"R: {rgb[0]:>6.2f}  G: {rgb[1]:>6.2f}  B: {rgb[2]:>6.2f}")
            return "\n".join(fallback_parts)
        else:
            return get_conditional_color_info(rgb, lab)
