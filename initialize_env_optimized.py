"""
Optimized initialization with minimal startup overhead
"""

import os
import sys
from pathlib import Path
import logging

# Minimal logging setup - defer detailed configuration
logger = logging.getLogger(__name__)

def get_app_data_dir():
    """Get the appropriate application data directory based on platform."""
    if sys.platform == 'darwin':  # macOS
        return Path.home() / 'Library' / 'Application Support' / 'StampZ-III'
    elif sys.platform == 'win32':  # Windows
        app_data = os.getenv('APPDATA')
        return Path(app_data) / 'StampZ-III' if app_data else Path.home() / '.stampz_iii'
    else:  # Linux and others
        return Path.home() / '.local' / 'share' / 'StampZ-III'

def quick_directory_setup():
    """Minimal directory setup - defer heavy operations"""
    
    # Get directories
    if getattr(sys, 'frozen', False):
        app_bundle_dir = Path(sys._MEIPASS)
    else:
        app_bundle_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    if getattr(sys, 'frozen', False):
        user_data_dir = get_app_data_dir()
    else:
        script_dir = Path(__file__).parent.absolute()
        if (script_dir / 'main.py').exists() and (script_dir / 'gui').exists():
            user_data_dir = script_dir  # Development mode
        else:
            user_data_dir = get_app_data_dir()
    
    # Add to Python path immediately
    for dir_name in ['gui', 'utils']:
        dir_path = app_bundle_dir / dir_name
        if str(dir_path) not in sys.path:
            sys.path.insert(0, str(dir_path))
    
    # Create only essential directories
    essential_dirs = ['data', 'data/color_libraries']
    for dir_name in essential_dirs:
        (user_data_dir / dir_name).mkdir(parents=True, exist_ok=True)
    
    # Set environment variable
    os.environ['STAMPZ_DATA_DIR'] = str(user_data_dir)
    
    return app_bundle_dir, user_data_dir

def lazy_initialization():
    """Defer heavy operations until after GUI is shown"""
    # This will be called after the main window is displayed
    try:
        # Import the full initialization for heavy operations
        from initialize_env import copy_directory_contents, check_and_preserve_data
        
        user_data_dir = Path(os.environ['STAMPZ_DATA_DIR'])
        app_bundle_dir = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).parent
        
        # Complete directory setup
        data_dirs = ['exports', 'recent']
        for dir_name in data_dirs:
            user_dir = user_data_dir / dir_name
            user_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy initial data if needed (deferred)
        bundle_data_dir = app_bundle_dir / 'data'
        user_data_subdir = user_data_dir / 'data'
        
        if bundle_data_dir.exists():
            color_libs_dir = user_data_subdir / 'color_libraries'
            has_existing_data = (
                color_libs_dir.exists() and 
                any(color_libs_dir.glob('*.db')) and
                any(db.stat().st_size > 32768 for db in color_libs_dir.glob('*.db'))
            )
            
            if not has_existing_data:
                copy_directory_contents(bundle_data_dir, user_data_subdir)
        
        return True
        
    except Exception as e:
        logger.error(f"Lazy initialization failed: {e}")
        return False

# Perform minimal initialization immediately
quick_directory_setup()