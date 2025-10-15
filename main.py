#!/usr/bin/env python3
"""StampZ-III - Main Application Entry Point
A image analysis application optimized for philatelic images
"""

# Import initialize_env first to set up data preservation system
# Handle module loading for both development and bundled PyInstaller environments
import sys
import os

# For bundled PyInstaller apps, ensure current directory is in Python path
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # Running in a PyInstaller bundle
    if '.' not in sys.path:
        sys.path.insert(0, '.')

import initialize_env

import tkinter as tk
import logging

logger = logging.getLogger(__name__)


def launch_full_stampz():
    """Launch the full StampZ-III application."""
    # Import the refactored application
    from app import StampZApp
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting full StampZ-III application...")
    
    # Create main window
    root = tk.Tk()
    
    try:
        # Create and run the application
        app = StampZApp(root)
        logger.info("StampZ-III application initialized successfully")
        
        # Start the main event loop
        root.mainloop()
        
    except Exception as e:
        logger.error(f"Failed to start StampZ-III: {e}")
        import traceback
        traceback.print_exc()
        
        # Show error to user
        try:
            tk.messagebox.showerror(
                "Startup Error",
                f"Failed to start StampZ-III:\n\n{str(e)}\n\n"
                f"Please check the console for detailed error information."
            )
        except:
            print(f"CRITICAL ERROR: {e}")
    
    finally:
        try:
            root.destroy()
        except:
            pass


def launch_plot3d_only():
    """Launch Plot_3D only mode."""
    try:
        from plot3d.standalone_plot3d import main as plot3d_main
        plot3d_main()
    except Exception as e:
        logger.error(f"Failed to start Plot_3D mode: {e}")
        try:
            tk.messagebox.showerror(
                "Plot_3D Launch Error",
                f"Failed to start Plot_3D mode:\n\n{str(e)}\n\n"
                f"Please check the console for detailed error information."
            )
        except:
            print(f"CRITICAL ERROR: {e}")


def main():
    """Main entry point - launches full StampZ application."""
    try:
        launch_full_stampz()
    except Exception as e:
        print(f"Error during launch: {e}")
        logging.error(f"Launch error: {e}")
    finally:
        # Ensure complete process termination
        sys.exit(0)


if __name__ == "__main__":
    main()
