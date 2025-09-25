"""
Optional ternary plot loader to avoid heavy dependencies in main bundle.
Only loads pandas/matplotlib when actually needed.
"""

def open_ternary_plot_window(root):
    """
    Lazy-load ternary plot to avoid loading heavy dependencies unless needed.
    """
    try:
        # Try to import the heavy dependencies
        import pandas as pd
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
        
        # If successful, import and create the ternary plot
        from plot3d.ternary_plot_app import TernaryPlotWindow
        return TernaryPlotWindow(root)
        
    except ImportError as e:
        from tkinter import messagebox
        missing_deps = []
        
        try:
            import pandas
        except ImportError:
            missing_deps.append("pandas")
            
        try:
            import matplotlib
        except ImportError:
            missing_deps.append("matplotlib")
        
        messagebox.showerror(
            "Missing Dependencies",
            f"Ternary Plot requires additional dependencies that are not installed:\n\n"
            f"Missing: {', '.join(missing_deps)}\n\n"
            f"To use this feature, please install:\n"
            f"pip install pandas matplotlib\n\n"
            f"Or download the full version of StampZ with all features included."
        )
        return None
        
    except Exception as e:
        from tkinter import messagebox
        messagebox.showerror(
            "Ternary Plot Error",
            f"Failed to open Ternary Plot:\n\n{str(e)}"
        )
        return None