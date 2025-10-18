#!/usr/bin/env python3
"""
StampZ-III - Optimized Main Application Entry Point
Focuses on fastest possible startup with lazy loading
"""

import sys
import os
import time
import threading
from pathlib import Path

# For bundled PyInstaller apps, ensure current directory is in Python path
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    if '.' not in sys.path:
        sys.path.insert(0, '.')

# Use optimized initialization for faster startup
try:
    import initialize_env_optimized
    startup_time = time.time()
except ImportError:
    # Fallback to original if optimized version not available
    import initialize_env
    startup_time = time.time()

import tkinter as tk
import logging

# Defer heavy logging setup
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class SplashScreen:
    """Lightweight splash screen for Windows startup performance"""
    
    def __init__(self):
        self.splash = None
        self.should_show_splash = sys.platform == 'win32'  # Only show on Windows
        
    def show(self):
        """Show splash screen - only on Windows or slow systems"""
        if not self.should_show_splash:
            return
            
        try:
            self.splash = tk.Tk()
            self.splash.title("StampZ-III")
            
            # Make it small and centered
            width, height = 300, 100
            x = (self.splash.winfo_screenwidth() // 2) - (width // 2)
            y = (self.splash.winfo_screenheight() // 2) - (height // 2)
            self.splash.geometry(f"{width}x{height}+{x}+{y}")
            
            # Remove window decorations
            self.splash.overrideredirect(True)
            
            # Add content
            frame = tk.Frame(self.splash, bg='white', relief='ridge', bd=2)
            frame.pack(fill='both', expand=True, padx=2, pady=2)
            
            tk.Label(frame, text="StampZ-III", font=('Arial', 16, 'bold'), bg='white').pack(pady=10)
            tk.Label(frame, text="Loading...", font=('Arial', 10), bg='white').pack()
            
            # Progress indicator
            self.progress_var = tk.StringVar()
            self.progress_label = tk.Label(frame, textvariable=self.progress_var, font=('Arial', 9), bg='white', fg='gray')
            self.progress_label.pack()
            
            self.splash.lift()
            self.splash.attributes('-topmost', True)
            self.splash.update()
            
        except Exception as e:
            logger.warning(f"Could not create splash screen: {e}")
            self.splash = None
    
    def update_progress(self, message):
        """Update progress message"""
        if self.splash and hasattr(self, 'progress_var'):
            try:
                self.progress_var.set(message)
                self.splash.update()
            except:
                pass
    
    def hide(self):
        """Hide splash screen"""
        if self.splash:
            try:
                self.splash.destroy()
            except:
                pass
            self.splash = None

def lazy_import_heavy_modules():
    """Import heavy modules in background after GUI is shown"""
    try:
        # These are the heavy imports that slow down startup
        import matplotlib.pyplot as plt
        import numpy as np
        import cv2
        import scipy
        import sklearn
        return True
    except ImportError as e:
        logger.warning(f"Some optional modules not available: {e}")
        return False

def launch_full_stampz():
    """Launch the full StampZ-III application with optimizations"""
    splash = SplashScreen()
    
    try:
        # Show splash screen on Windows
        splash.show()
        splash.update_progress("Initializing...")
        
        # Create main window early but don't show it yet
        root = tk.Tk()
        root.withdraw()  # Hide initially
        
        splash.update_progress("Loading interface...")
        
        # Import and create the application
        from app import StampZApp
        app = StampZApp(root)
        
        splash.update_progress("Finalizing...")
        
        # Show main window and hide splash
        root.deiconify()
        splash.hide()
        
        # Start background initialization of heavy modules
        if hasattr(initialize_env_optimized, 'lazy_initialization'):
            threading.Thread(
                target=initialize_env_optimized.lazy_initialization, 
                daemon=True
            ).start()
        
        # Background loading of heavy modules
        threading.Thread(target=lazy_import_heavy_modules, daemon=True).start()
        
        elapsed = time.time() - startup_time
        logger.info(f"StampZ-III startup completed in {elapsed:.2f}s")
        
        # Start the main event loop
        root.mainloop()
        
    except Exception as e:
        splash.hide()
        logger.error(f"Failed to start StampZ-III: {e}")
        
        try:
            import traceback
            traceback.print_exc()
            
            # Show error to user
            error_root = tk.Tk()
            error_root.withdraw()
            tk.messagebox.showerror(
                "Startup Error",
                f"Failed to start StampZ-III:\n\n{str(e)}\n\n"
                f"Please check the console for detailed error information."
            )
            error_root.destroy()
        except:
            print(f"CRITICAL ERROR: {e}")
    
    finally:
        splash.hide()
        try:
            if 'root' in locals():
                root.destroy()
        except:
            pass

def launch_plot3d_only():
    """Launch Plot_3D only mode"""
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
    """Main entry point - launches full StampZ application"""
    try:
        launch_full_stampz()
    except Exception as e:
        print(f"Error during launch: {e}")
        logging.error(f"Launch error: {e}")
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()