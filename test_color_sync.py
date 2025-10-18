#!/usr/bin/env python3
"""
Test script to verify line color synchronization between control panel and canvas
"""

import tkinter as tk
from tkinter import ttk
from gui.canvas import CropCanvas
import sys
import os

def test_color_sync():
    """Test that line color changes are properly synchronized"""
    
    print("Testing line color synchronization...")
    
    # Create a simple test app
    root = tk.Tk()
    root.title("Color Sync Test")
    root.geometry("800x600")
    
    try:
        # Create canvas and control panel
        canvas = CropCanvas(root, bg='white')
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create a simple control panel for testing
        control_frame = tk.Frame(root)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add color selection
        color_var = tk.StringVar(value="white")
        tk.Label(control_frame, text="Line Color:").pack()
        color_combo = ttk.Combobox(control_frame, textvariable=color_var, 
                                 values=["white", "red", "green", "blue", "yellow", "magenta", "cyan", "black"],
                                 state='readonly')
        color_combo.pack()
        
        def on_color_change(*args):
            color = color_var.get()
            print(f"Color changed to: {color}")
            canvas.set_line_color(color)
            # Print current shape manager color for verification
            if hasattr(canvas, 'shape_manager'):
                print(f"Shape manager current_color: {canvas.shape_manager.current_color}")
        
        color_var.trace('w', on_color_change)
        color_combo.bind('<<ComboboxSelected>>', on_color_change)
        
        # Initialize with default color
        on_color_change()
        
        # Add some test info
        info_label = tk.Label(control_frame, text="Change color and check\nif it synchronizes with\nthe canvas markers", 
                             justify=tk.LEFT, wraplength=150)
        info_label.pack(pady=10)
        
        # Add close button
        tk.Button(control_frame, text="Close", command=root.quit).pack(pady=10)
        
        print("Test app created. Change colors to verify synchronization.")
        print("Initial control panel color:", color_var.get())
        print("Initial canvas color:", canvas.shape_manager.current_color)
        
        root.mainloop()
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_color_sync()
    sys.exit(0 if success else 1)