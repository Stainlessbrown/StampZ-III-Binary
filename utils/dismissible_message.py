#!/usr/bin/env python3
"""
Dismissible message dialog with "Don't show again" option.
Messages can be suppressed for the current session only (resets on app restart).
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional, Set


class SessionMessageManager:
    """Manages which messages have been dismissed for the current session."""
    
    def __init__(self):
        # Track dismissed message IDs for this session
        self._dismissed_messages: Set[str] = set()
    
    def is_dismissed(self, message_id: str) -> bool:
        """Check if a message has been dismissed this session."""
        return message_id in self._dismissed_messages
    
    def dismiss(self, message_id: str):
        """Mark a message as dismissed for this session."""
        self._dismissed_messages.add(message_id)
    
    def reset(self):
        """Reset all dismissed messages (typically not needed - auto-resets on restart)."""
        self._dismissed_messages.clear()
    
    def get_dismissed_count(self) -> int:
        """Get the number of dismissed messages this session."""
        return len(self._dismissed_messages)


# Global session manager
_session_manager = SessionMessageManager()


def get_session_manager() -> SessionMessageManager:
    """Get the global session message manager."""
    return _session_manager


class DismissibleMessageBox:
    """Custom message box with 'Don't show again' checkbox."""
    
    @staticmethod
    def show_info(
        title: str,
        message: str,
        message_id: str,
        parent: Optional[tk.Tk] = None,
        detail: Optional[str] = None
    ) -> bool:
        """
        Show an informational message with 'Don't show again' option.
        
        Args:
            title: Dialog title
            message: Main message text
            message_id: Unique identifier for this message type
            parent: Parent window (optional)
            detail: Additional detail text (optional)
        
        Returns:
            True if shown, False if dismissed
        """
        # Check if message was already dismissed this session
        if _session_manager.is_dismissed(message_id):
            return False
        
        # Create custom dialog
        dialog = tk.Toplevel(parent) if parent else tk.Toplevel()
        dialog.title(title)
        dialog.resizable(False, False)
        
        # Make modal
        dialog.transient(parent if parent else dialog.master)
        dialog.grab_set()
        
        # Main content frame
        content_frame = ttk.Frame(dialog, padding="20")
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Icon and message frame
        top_frame = ttk.Frame(content_frame)
        top_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Info icon (using Unicode character)
        icon_label = ttk.Label(
            top_frame,
            text="ℹ️",
            font=("Helvetica", 32)
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 15))
        
        # Message text
        message_frame = ttk.Frame(top_frame)
        message_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        message_label = ttk.Label(
            message_frame,
            text=message,
            wraplength=400,
            justify=tk.LEFT
        )
        message_label.pack(anchor='w')
        
        # Detail text (if provided)
        if detail:
            detail_label = ttk.Label(
                message_frame,
                text=detail,
                wraplength=400,
                justify=tk.LEFT,
                font=("Helvetica", 9),
                foreground="gray"
            )
            detail_label.pack(anchor='w', pady=(10, 0))
        
        # Separator
        separator = ttk.Separator(content_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(0, 15))
        
        # Checkbox frame
        checkbox_frame = ttk.Frame(content_frame)
        checkbox_frame.pack(fill=tk.X, pady=(0, 15))
        
        dont_show_var = tk.BooleanVar(value=False)
        checkbox = ttk.Checkbutton(
            checkbox_frame,
            text="Don't show this message again this session",
            variable=dont_show_var
        )
        checkbox.pack(anchor='w')
        
        # Button frame
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X)
        
        def on_ok():
            if dont_show_var.get():
                _session_manager.dismiss(message_id)
            dialog.destroy()
        
        ok_button = ttk.Button(
            button_frame,
            text="OK",
            command=on_ok,
            width=10
        )
        ok_button.pack(side=tk.RIGHT)
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_reqwidth() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_reqheight() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Focus OK button
        ok_button.focus_set()
        
        # Bind Enter key to OK
        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_ok())
        
        # Wait for dialog
        dialog.wait_window()
        
        return True
    
    @staticmethod
    def show_success(
        title: str,
        message: str,
        message_id: str,
        parent: Optional[tk.Tk] = None,
        detail: Optional[str] = None
    ) -> bool:
        """
        Show a success message with 'Don't show again' option.
        
        Similar to show_info but with success styling.
        """
        if _session_manager.is_dismissed(message_id):
            return False
        
        dialog = tk.Toplevel(parent) if parent else tk.Toplevel()
        dialog.title(title)
        dialog.resizable(False, False)
        
        dialog.transient(parent if parent else dialog.master)
        dialog.grab_set()
        
        content_frame = ttk.Frame(dialog, padding="20")
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        top_frame = ttk.Frame(content_frame)
        top_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Success icon
        icon_label = ttk.Label(
            top_frame,
            text="✓",
            font=("Helvetica", 32),
            foreground="#2E7D32"
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 15))
        
        message_frame = ttk.Frame(top_frame)
        message_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        message_label = ttk.Label(
            message_frame,
            text=message,
            wraplength=400,
            justify=tk.LEFT
        )
        message_label.pack(anchor='w')
        
        if detail:
            detail_label = ttk.Label(
                message_frame,
                text=detail,
                wraplength=400,
                justify=tk.LEFT,
                font=("Helvetica", 9),
                foreground="gray"
            )
            detail_label.pack(anchor='w', pady=(10, 0))
        
        separator = ttk.Separator(content_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(0, 15))
        
        checkbox_frame = ttk.Frame(content_frame)
        checkbox_frame.pack(fill=tk.X, pady=(0, 15))
        
        dont_show_var = tk.BooleanVar(value=False)
        checkbox = ttk.Checkbutton(
            checkbox_frame,
            text="Don't show this message again this session",
            variable=dont_show_var
        )
        checkbox.pack(anchor='w')
        
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X)
        
        def on_ok():
            if dont_show_var.get():
                _session_manager.dismiss(message_id)
            dialog.destroy()
        
        ok_button = ttk.Button(
            button_frame,
            text="OK",
            command=on_ok,
            width=10
        )
        ok_button.pack(side=tk.RIGHT)
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_reqwidth() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_reqheight() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        ok_button.focus_set()
        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_ok())
        
        dialog.wait_window()
        
        return True


# Convenience functions that match messagebox API
def showinfo_dismissible(
    title: str,
    message: str,
    message_id: str,
    parent: Optional[tk.Tk] = None,
    detail: Optional[str] = None
) -> bool:
    """
    Show an informational message that can be dismissed for the session.
    
    Usage:
        from utils.dismissible_message import showinfo_dismissible
        
        showinfo_dismissible(
            title="Analysis Complete",
            message="Your color analysis has been saved successfully.",
            message_id="analysis_save_success",
            detail="The results are now available in the database."
        )
    
    Args:
        title: Dialog title
        message: Main message
        message_id: Unique ID (use descriptive names like "measurement_saved")
        parent: Parent window
        detail: Additional detail text
    
    Returns:
        True if shown, False if dismissed
    """
    return DismissibleMessageBox.show_info(title, message, message_id, parent, detail)


def showsuccess_dismissible(
    title: str,
    message: str,
    message_id: str,
    parent: Optional[tk.Tk] = None,
    detail: Optional[str] = None
) -> bool:
    """
    Show a success message that can be dismissed for the session.
    
    Similar to showinfo_dismissible but with success styling.
    """
    return DismissibleMessageBox.show_success(title, message, message_id, parent, detail)


def is_message_dismissed(message_id: str) -> bool:
    """
    Check if a message has been dismissed this session.
    
    Useful for programmatically checking without showing the dialog.
    """
    return _session_manager.is_dismissed(message_id)


def reset_session_dismissals():
    """
    Reset all dismissed messages (mainly for testing).
    
    Note: This happens automatically when the app restarts.
    """
    _session_manager.reset()


# Example usage and testing
if __name__ == "__main__":
    # Test the dismissible message
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    # First call - will show
    print("Showing message first time...")
    shown = showinfo_dismissible(
        title="Measurement Saved",
        message="Your precision measurement has been saved to the database.",
        message_id="measurement_saved",
        detail="You can view it in the Database Viewer."
    )
    print(f"Message shown: {shown}")
    
    # Second call - will show again (user didn't check the box)
    print("\nShowing message second time...")
    shown = showinfo_dismissible(
        title="Measurement Saved",
        message="Your precision measurement has been saved to the database.",
        message_id="measurement_saved",
        detail="You can view it in the Database Viewer."
    )
    print(f"Message shown: {shown}")
    
    # After checking "Don't show again", subsequent calls return False
    print("\nIf you checked 'Don't show again', this won't appear...")
    shown = showinfo_dismissible(
        title="Measurement Saved",
        message="Your precision measurement has been saved to the database.",
        message_id="measurement_saved"
    )
    print(f"Message shown: {shown}")
    
    print("\nSession dismissal count:", get_session_manager().get_dismissed_count())
    
    root.destroy()
