#!/usr/bin/env python3
"""
Startup Performance Profiler for StampZ-III
Run this to identify startup bottlenecks on different systems
"""

import time
import sys
import os
import platform
import psutil
import traceback
from pathlib import Path

class StartupProfiler:
    def __init__(self):
        self.start_time = time.time()
        self.checkpoints = []
        self.system_info = self._get_system_info()
    
    def checkpoint(self, name: str, details: str = ""):
        """Record a timing checkpoint"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        since_last = elapsed - (self.checkpoints[-1]['elapsed'] if self.checkpoints else 0)
        
        self.checkpoints.append({
            'name': name,
            'details': details,
            'elapsed': elapsed,
            'since_last': since_last,
            'timestamp': current_time
        })
        
        print(f"[{elapsed:6.3f}s] (+{since_last:6.3f}s) {name}: {details}")
    
    def _get_system_info(self):
        """Collect system information"""
        try:
            return {
                'platform': platform.platform(),
                'processor': platform.processor(),
                'python_version': sys.version,
                'memory_gb': round(psutil.virtual_memory().total / (1024**3), 2),
                'cpu_count': psutil.cpu_count(),
                'cpu_freq': psutil.cpu_freq().current if psutil.cpu_freq() else "Unknown",
                'disk_usage': psutil.disk_usage('.').percent,
                'available_memory_gb': round(psutil.virtual_memory().available / (1024**3), 2),
            }
        except Exception as e:
            return {'error': str(e)}
    
    def profile_imports(self):
        """Profile major import statements"""
        self.checkpoint("START", "Beginning import profiling")
        
        # Test critical imports individually
        imports_to_test = [
            ('tkinter', 'import tkinter as tk'),
            ('PIL', 'from PIL import Image, ImageTk'),
            ('numpy', 'import numpy as np'),
            ('matplotlib', 'import matplotlib.pyplot as plt'),
            ('cv2', 'import cv2'),
            ('sqlite3', 'import sqlite3'),
            ('scipy', 'import scipy'),
            ('sklearn', 'import sklearn'),
        ]
        
        for name, import_stmt in imports_to_test:
            start = time.time()
            try:
                exec(import_stmt)
                duration = time.time() - start
                self.checkpoint(f"IMPORT_{name}", f"Success ({duration:.3f}s)")
            except ImportError as e:
                self.checkpoint(f"IMPORT_{name}", f"FAILED: {str(e)}")
            except Exception as e:
                self.checkpoint(f"IMPORT_{name}", f"ERROR: {str(e)}")
    
    def profile_data_directories(self):
        """Profile data directory creation/access"""
        self.checkpoint("DATA_DIRS_START", "Checking data directories")
        
        try:
            from utils.path_utils import ensure_data_directories
            ensure_data_directories()
            self.checkpoint("DATA_DIRS_COMPLETE", "Data directories verified")
        except Exception as e:
            self.checkpoint("DATA_DIRS_ERROR", f"Error: {str(e)}")
    
    def profile_gui_creation(self):
        """Profile GUI initialization"""
        self.checkpoint("GUI_START", "Starting GUI creation")
        
        try:
            import tkinter as tk
            root = tk.Tk()
            self.checkpoint("GUI_ROOT", "Root window created")
            
            # Test basic widget creation
            test_frame = tk.Frame(root)
            test_label = tk.Label(test_frame, text="Test")
            self.checkpoint("GUI_WIDGETS", "Basic widgets created")
            
            root.withdraw()  # Hide the window
            root.destroy()
            self.checkpoint("GUI_CLEANUP", "GUI cleaned up")
            
        except Exception as e:
            self.checkpoint("GUI_ERROR", f"Error: {str(e)}")
    
    def profile_database_access(self):
        """Profile database operations"""
        self.checkpoint("DB_START", "Testing database access")
        
        try:
            from utils.coordinate_db import CoordinateDB
            db = CoordinateDB()
            sets = db.get_all_set_names()
            self.checkpoint("DB_COMPLETE", f"Database accessed, {len(sets)} sets found")
        except Exception as e:
            self.checkpoint("DB_ERROR", f"Error: {str(e)}")
    
    def generate_report(self):
        """Generate a comprehensive startup report"""
        total_time = time.time() - self.start_time
        
        print("\n" + "="*60)
        print("STARTUP PERFORMANCE REPORT")
        print("="*60)
        
        print("\nSYSTEM INFO:")
        for key, value in self.system_info.items():
            print(f"  {key}: {value}")
        
        print(f"\nTOTAL STARTUP TIME: {total_time:.3f} seconds")
        
        print("\nTIMING BREAKDOWN:")
        for checkpoint in self.checkpoints:
            print(f"  {checkpoint['elapsed']:6.3f}s - {checkpoint['name']}: {checkpoint['details']}")
        
        # Identify slow operations
        slow_operations = [cp for cp in self.checkpoints if cp['since_last'] > 0.5]
        if slow_operations:
            print("\nSLOW OPERATIONS (>0.5s):")
            for op in slow_operations:
                print(f"  {op['since_last']:6.3f}s - {op['name']}: {op['details']}")
        
        # Generate recommendations
        print("\nRECOMMENDATIONS:")
        if total_time > 10:
            print("  - Startup time is quite slow. Consider lazy loading of heavy modules.")
        if total_time > 5:
            print("  - Consider showing a splash screen during startup.")
        if any('IMPORT' in cp['name'] and cp['since_last'] > 1 for cp in self.checkpoints):
            print("  - Some imports are slow. Consider lazy importing non-critical modules.")
        
        return {
            'total_time': total_time,
            'system_info': self.system_info,
            'checkpoints': self.checkpoints,
            'slow_operations': slow_operations
        }

def main():
    """Run startup profiling"""
    print("StampZ-III Startup Profiler")
    print("This will test startup performance and identify bottlenecks")
    print("-" * 60)
    
    profiler = StartupProfiler()
    
    try:
        # Profile different startup phases
        profiler.profile_imports()
        profiler.profile_data_directories()
        profiler.profile_database_access()
        profiler.profile_gui_creation()
        
        # Generate and save report
        report = profiler.generate_report()
        
        # Save detailed report to file
        report_file = Path("startup_performance_report.txt")
        with open(report_file, 'w') as f:
            f.write("StampZ-III Startup Performance Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Generated: {time.ctime()}\n\n")
            
            f.write("System Information:\n")
            for key, value in report['system_info'].items():
                f.write(f"  {key}: {value}\n")
            
            f.write(f"\nTotal Startup Time: {report['total_time']:.3f} seconds\n\n")
            
            f.write("Timing Breakdown:\n")
            for cp in report['checkpoints']:
                f.write(f"  {cp['elapsed']:6.3f}s (+{cp['since_last']:6.3f}s) - {cp['name']}: {cp['details']}\n")
        
        print(f"\nDetailed report saved to: {report_file}")
        
    except Exception as e:
        print(f"Profiling failed: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()