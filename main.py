#!/usr/bin/env python3
# Trigger build - 2025-01-17
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
import time

logger = logging.getLogger(__name__)


def launch_full_stampz():
    """Launch the full StampZ-III application."""
    startup_time = time.time()
    print(f"StampZ-III startup beginning...")
    
    # Import the refactored application  
    import_start = time.time()
    from app import StampZApp
    print(f"App import took {time.time() - import_start:.2f}s")
    
    # Setup logging - both console and file
    import logging.handlers
    from pathlib import Path
    
    # Create log file on Desktop for easy access
    desktop_path = Path.home() / "Desktop"
    log_file = desktop_path / "StampZ_Debug_Log.txt"
    
    # Configure logging with both file and console handlers
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),  # Console output
            logging.FileHandler(log_file, mode='w', encoding='utf-8')  # File output
        ]
    )
    
    # Setup custom stdout/stderr to capture DEBUG statements to log file
    from utils.debug_capture import setup_debug_capture
    setup_debug_capture(log_file)
    
    logger.info(f"StampZ-III Debug Log - Session started")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    
    # Log if running as bundled app
    if getattr(sys, 'frozen', False):
        logger.info(f"Running as PyInstaller bundle")
        logger.info(f"Bundle dir: {sys._MEIPASS}")
    else:
        logger.info(f"Running from source")
    
    logger.info("Starting full StampZ-III application...")
    
    # Create main window
    gui_start = time.time()
    root = tk.Tk()
    print(f"Tkinter root creation took {time.time() - gui_start:.2f}s")
    
    try:
        # Create and run the application
        app_start = time.time()
        app = StampZApp(root)
        print(f"StampZApp initialization took {time.time() - app_start:.2f}s")
        print(f"Total startup time: {time.time() - startup_time:.2f}s")
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
