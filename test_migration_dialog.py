#!/usr/bin/env python3
"""
Test script to display migration dialog for screenshot/documentation purposes.
This creates a mock migration scenario to show what users would see.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
from pathlib import Path

class MockMigration:
    """Mock migration object for testing the UI."""
    
    def __init__(self, scenario="needed"):
        """
        Args:
            scenario: "needed" or "completed" to show different states
        """
        self.scenario = scenario
    
    def is_migration_needed(self):
        return self.scenario == "needed"
    
    def is_migration_completed(self):
        return self.scenario == "completed"
    
    def get_migration_summary(self):
        """Return mock migration summary data."""
        return {
            'color_libraries': [
                {'name': 'Stanley_Gibbons', 'size_mb': 2.45},
                {'name': 'Scott_Catalog', 'size_mb': 1.89},
                {'name': 'Custom_Colors', 'size_mb': 0.67}
            ],
            'color_analysis': [
                {'name': 'US_Stamps_Analysis', 'size_mb': 3.21},
                {'name': 'UK_Definitives', 'size_mb': 1.54}
            ],
            'coordinates': [
                {'path': 'coordinates.db', 'size_mb': 0.45}
            ],
            'total_files': 6,
            'total_size_mb': 10.21
        }
    
    def get_migration_info(self):
        """Return mock migration info for completed scenario."""
        return {
            'Migration completed': '2024-11-15 14:30:22',
            'Migrated files': '6',
            'Backup created': 'Yes'
        }
    
    def perform_migration(self, create_backup=True):
        """Mock migration - just return success."""
        return True, "Mock migration successful"


def create_migration_needed_section(parent, migration):
    """Create section for needed migration."""
    # Warning
    warning_frame = ttk.LabelFrame(parent, text="Migration Available", padding="10")
    warning_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(
        warning_frame,
        text="⚠️ StampZ data found that can be migrated to StampZ-III",
        font=("TkDefaultFont", 11, "bold"),
        foreground="orange"
    ).pack(anchor=tk.W, pady=(0, 10))
    
    # Get migration summary
    summary = migration.get_migration_summary()
    
    # Summary of what will be migrated
    summary_frame = ttk.LabelFrame(parent, text="Migration Summary", padding="10")
    summary_frame.pack(fill=tk.X, pady=(0, 10))
    
    summary_text = f"The following data from your old StampZ installation can be migrated:\n\n"
    
    if summary['color_libraries']:
        summary_text += f"📚 Color Libraries ({len(summary['color_libraries'])}):"
        for lib in summary['color_libraries']:
            summary_text += f"\n  • {lib['name']} ({lib['size_mb']} MB)"
        summary_text += "\n\n"
    
    if summary['color_analysis']:
        summary_text += f"🔬 Color Analysis ({len(summary['color_analysis'])}):"
        for analysis in summary['color_analysis']:
            summary_text += f"\n  • {analysis['name']} ({analysis['size_mb']} MB)"
        summary_text += "\n\n"
    
    if summary['coordinates']:
        summary_text += f"📍 Coordinate Templates ({len(summary['coordinates'])}):"
        for coord in summary['coordinates']:
            summary_text += f"\n  • {coord['path']} ({coord['size_mb']} MB)"
        summary_text += "\n\n"
    
    summary_text += f"Total: {summary['total_files']} files, {summary['total_size_mb']} MB"
    
    ttk.Label(
        summary_frame,
        text=summary_text,
        font=("TkDefaultFont", 10),
        justify=tk.LEFT
    ).pack(anchor=tk.W)
    
    # Migration options
    options_frame = ttk.LabelFrame(parent, text="Migration Options", padding="10")
    options_frame.pack(fill=tk.X, pady=(0, 10))
    
    create_backup_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        options_frame,
        text="Create backup of original StampZ directory (recommended)",
        variable=create_backup_var
    ).pack(anchor=tk.W, pady=(0, 10))
    
    # Migration button
    button_frame = ttk.Frame(options_frame)
    button_frame.pack(fill=tk.X)
    
    def mock_migrate():
        messagebox.showinfo("Test Mode", "This is a test dialog for screenshots.\nNo actual migration will be performed.")
    
    def mock_skip():
        messagebox.showinfo("Test Mode", "This is a test dialog for screenshots.\nNo action will be taken.")
    
    ttk.Button(
        button_frame,
        text="Migrate Data to StampZ-III",
        command=mock_migrate
    ).pack(side=tk.LEFT, padx=(0, 10))
    
    ttk.Button(
        button_frame,
        text="Skip Migration",
        command=mock_skip
    ).pack(side=tk.LEFT)
    
    # Info about the process
    info_frame = ttk.LabelFrame(parent, text="What happens during migration?", padding="10")
    info_frame.pack(fill=tk.X)
    
    info_text = (
        "1. Your old StampZ directory will be backed up (if selected)\n"
        "2. Data will be copied to the new StampZ-III directory structure\n"
        "3. StampZ-III will use the migrated data going forward\n"
        "4. Your original StampZ directory remains unchanged\n\n"
        "This process is safe and reversible - your original data is never deleted."
    )
    
    ttk.Label(
        info_frame,
        text=info_text,
        font=("TkDefaultFont", 10),
        justify=tk.LEFT
    ).pack(anchor=tk.W)


def create_migration_completed_section(parent, migration):
    """Create section for completed migration."""
    status_frame = ttk.LabelFrame(parent, text="Migration Status", padding="10")
    status_frame.pack(fill=tk.X, pady=(0, 10))
    
    # Success message
    ttk.Label(
        status_frame,
        text="✅ Migration completed successfully!",
        font=("TkDefaultFont", 11, "bold"),
        foreground="green"
    ).pack(anchor=tk.W, pady=(0, 10))
    
    # Get migration info
    info = migration.get_migration_info()
    if info:
        info_text = f"Migration Date: {info.get('Migration completed', 'Unknown')}\n"
        info_text += f"Files Migrated: {info.get('Migrated files', 'Unknown')}\n"
        info_text += f"Backup Created: {info.get('Backup created', 'Unknown')}"
        
        ttk.Label(
            status_frame,
            text=info_text,
            font=("TkDefaultFont", 10)
        ).pack(anchor=tk.W, pady=(0, 10))
    
    # Info about old directory
    info_frame = ttk.LabelFrame(parent, text="Information", padding="10")
    info_frame.pack(fill=tk.X)
    
    info_text = (
        "Your data has been successfully migrated from the old StampZ directory to StampZ-III.\n\n"
        "• All your color libraries, analysis data, and templates are now in StampZ-III\n"
        "• The old StampZ directory has been left unchanged as a backup\n"
        "• StampZ-III now uses the migrated data exclusively\n\n"
        "You can safely delete the old StampZ directory if you no longer need it, "
        "but it's recommended to keep it as a backup until you're sure everything works correctly."
    )
    
    ttk.Label(
        info_frame,
        text=info_text,
        wraplength=600,
        justify=tk.LEFT,
        font=("TkDefaultFont", 10)
    ).pack(anchor=tk.W)


def show_migration_dialog(scenario="needed"):
    """
    Show migration dialog window.
    
    Args:
        scenario: "needed" or "completed"
    """
    root = tk.Tk()
    root.title("StampZ-III Preferences - Migration Tab")
    root.geometry("700x650")
    
    # Create main frame with padding
    main_frame = ttk.Frame(root, padding="15")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title
    title_frame = ttk.Frame(main_frame)
    title_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(
        title_frame,
        text="StampZ to StampZ-III Migration",
        font=("TkDefaultFont", 12, "bold")
    ).pack(anchor=tk.W)
    
    # Create scrollable content area
    canvas = tk.Canvas(main_frame, highlightthickness=0)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Create mock migration object
    migration = MockMigration(scenario=scenario)
    
    # Show appropriate section based on scenario
    if scenario == "completed":
        create_migration_completed_section(scrollable_frame, migration)
    else:
        create_migration_needed_section(scrollable_frame, migration)
    
    # Pack canvas and scrollbar
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Add instruction label at bottom
    instruction_frame = ttk.Frame(root, padding="10")
    instruction_frame.pack(fill=tk.X, side=tk.BOTTOM)
    
    ttk.Label(
        instruction_frame,
        text="📸 This is a test window for screenshots. Take your screenshot now!",
        font=("TkDefaultFont", 9),
        foreground="blue"
    ).pack()
    
    # Center the window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    root.mainloop()


if __name__ == "__main__":
    print("StampZ-III Migration Dialog Test")
    print("=" * 50)
    print("\nThis will show the migration dialog for screenshot purposes.")
    print("\nChoose which scenario to display:")
    print("1. Migration Needed (user has old StampZ data)")
    print("2. Migration Completed (migration already done)")
    print()
    
    choice = input("Enter choice (1 or 2, default=1): ").strip()
    
    if choice == "2":
        show_migration_dialog(scenario="completed")
    else:
        show_migration_dialog(scenario="needed")
