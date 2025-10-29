import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import os
import logging
from utils.rigid_plot3d_templates import create_rigid_plot3d_templates, RigidPlot3DTemplate

class TemplateSelector:
    def __init__(self, parent=None):
        self.file_path = None
        self.root = None
        self.parent = parent
        self.create_and_run_dialog()
        
    def create_and_run_dialog(self):
        """Create and run the file selection dialog with proper error handling."""
        try:
            # Create the main window - check if we have a parent (embedded mode)
            if self.parent:
                # Embedded mode - create as Toplevel window
                self.root = tk.Toplevel(self.parent)
                self.root.transient(self.parent)
                self.root.grab_set()  # Modal to parent only, not entire app
            else:
                # Standalone mode - create root window
                self.root = tk.Tk()
                
            self.root.title("Plot_3D File Selector")
            self.root.geometry("400x300")
            self.root.lift()
            self.root.attributes("-topmost", True)
            
            # Add heading
            heading = tk.Label(self.root, text="Plot_3D Template Selector", font=("Arial", 14, "bold"))
            heading.pack(pady=10)
            
            # Open existing .ods file button (most common use case)
            open_button = tk.Button(
                self.root, 
                text="📊 Open Existing .ods File",
                command=self.select_custom_file,
                width=25,
                height=2,
                bg="lightgreen",
                fg="black",
                font=("Arial", 11, "bold")
            )
            open_button.pack(pady=8)
            
            # Add description for open file
            open_desc = tk.Label(
                self.root,
                text="(For StampZ exports and other .ods data files)",
                font=("Arial", 9),
                fg="#666666"
            )
            open_desc.pack(pady=(0, 15))
            
            # Use existing template button
            existing_button = tk.Button(
                self.root, 
                text="📋 Use Built-in Template",
                command=self.select_existing_template,
                width=25,
                height=2,
                bg="lightblue",
                fg="black",
                font=("Arial", 11, "bold")
            )
            existing_button.pack(pady=8)
            
            # Add description for templates
            template_desc = tk.Label(
                self.root,
                text="(Start with pre-made Plot_3D templates)",
                font=("Arial", 9),
                fg="#666666"
            )
            template_desc.pack(pady=(0, 15))
            
            # Create rigid template button
            rigid_button = tk.Button(
                self.root, 
                text="➕ Create New Template",
                command=self.create_rigid_template,
                width=25,
                height=2,
                bg="lightyellow",
                fg="black",
                font=("Arial", 11, "bold")
            )
            rigid_button.pack(pady=8)
            
            # Add description for create template
            create_desc = tk.Label(
                self.root,
                text="(Generate blank template for manual data entry)",
                font=("Arial", 9),
                fg="#666666"
            )
            create_desc.pack(pady=(0, 10))
            
            # Center dialog if we have a parent
            if self.parent:
                self.root.update_idletasks()
                x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (self.root.winfo_width() // 2)
                y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (self.root.winfo_height() // 2)
                self.root.geometry(f"+{x}+{y}")
                
                # Wait for window instead of starting mainloop in embedded mode
                self.parent.wait_window(self.root)
            else:
                # Start the main loop only in standalone mode
                self.root.mainloop()
        except Exception as e:
            logging.error(f"Error creating template selector window: {str(e)}")
            if self.root:
                try:
                    self.root.destroy()
                except:
                    pass
            raise
    
    def select_custom_file(self):
        logging.debug("Select File")
        # Create a new temporary tkinter root for the file dialog
        file_root = tk.Tk()
        file_root.withdraw()
        
        file_types = [
            ('OpenDocument Spreadsheet', '*.ods'),
            ('All files', '*.*')
        ]
        
        selected_file = filedialog.askopenfilename(filetypes=file_types)
        file_root.destroy()
        
        if selected_file:
            # Convert to absolute path
            self.file_path = os.path.abspath(selected_file)
            logging.info(f"Selected file (absolute path): {self.file_path}")
            
            # Detect available sheets and ask user to select one (for multi-sheet files)
            self.sheet_name = None
            if selected_file.endswith(('.ods', '.xlsx')):
                try:
                    from utils.external_data_importer import ExternalDataImporter
                    importer = ExternalDataImporter()
                    sheet_names = importer.get_sheet_names(self.file_path)
                    
                    if sheet_names and len(sheet_names) > 1:
                        self.sheet_name = self._ask_sheet_selection(sheet_names)
                        if not self.sheet_name:
                            logging.info("User cancelled sheet selection")
                            return  # User cancelled
                        logging.info(f"User selected sheet: {self.sheet_name}")
                    elif sheet_names:
                        self.sheet_name = sheet_names[0]
                        logging.info(f"Using single sheet: {self.sheet_name}")
                except Exception as sheet_error:
                    logging.warning(f"Could not detect sheets: {sheet_error}. Using first sheet.")
            
            # Ask user what type of color data the file contains
            self.label_type = self._ask_data_type()
            logging.info(f"User selected data type: {self.label_type}")
            
            self.root.destroy()
        else:
            logging.warning("No file selected")
    
    def _ask_sheet_selection(self, sheet_names):
        """Ask user to select a sheet from a multi-sheet file.
        
        Args:
            sheet_names: List of available sheet names
            
        Returns:
            Selected sheet name, or None if cancelled
        """
        if not sheet_names:
            return None
        
        # If only one sheet, return it automatically
        if len(sheet_names) == 1:
            return sheet_names[0]
        
        logging.debug(f"Creating sheet selection dialog for {len(sheet_names)} sheets")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Sheet")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Add heading
        heading = tk.Label(dialog, 
                          text=f"This file contains {len(sheet_names)} sheets.\nWhich sheet would you like to open?", 
                          font=("Arial", 11, "bold"),
                          justify=tk.LEFT)
        heading.pack(pady=15, padx=10)
        
        # Variable to store selection
        result = tk.StringVar(value="")
        
        # Create scrollable listbox for sheet names
        list_frame = tk.Frame(dialog)
        list_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(list_frame, 
                            font=("Arial", 10),
                            yscrollcommand=scrollbar.set,
                            selectmode=tk.SINGLE,
                            height=8)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate listbox with sheet names
        for sheet in sheet_names:
            listbox.insert(tk.END, sheet)
        
        # Select first item by default
        listbox.selection_set(0)
        listbox.activate(0)
        
        def on_ok():
            selection_idx = listbox.curselection()
            if selection_idx:
                result.set(sheet_names[selection_idx[0]])
            else:
                result.set(sheet_names[0])  # Default to first sheet
            dialog.destroy()
        
        def on_cancel():
            result.set("")  # Empty means cancelled
            dialog.destroy()
        
        def on_double_click(event):
            on_ok()  # Double-click acts as OK
        
        listbox.bind('<Double-Button-1>', on_double_click)
        
        # Button frame
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        ok_btn = tk.Button(btn_frame, text="Open", command=on_ok, width=12, font=("Arial", 10, "bold"))
        ok_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=on_cancel, width=12, font=("Arial", 10))
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Wait for dialog to close
        dialog.wait_window()
        
        final_result = result.get() if result.get() else None
        logging.debug(f"Sheet selection dialog closed, returning: {final_result}")
        return final_result
    
    def _ask_data_type(self):
        """Ask user what type of color data is in the selected file."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Data Type")
        dialog.geometry("450x320")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Add heading
        heading = tk.Label(dialog, text="What type of color data is in this file?", 
                          font=("Arial", 11, "bold"))
        heading.pack(pady=15)
        
        # Variable to store selection
        selection = tk.StringVar(value="LAB")
        
        # Radio buttons
        rb_frame = tk.Frame(dialog)
        rb_frame.pack(pady=10)
        
        tk.Radiobutton(rb_frame, text="L*a*b* (CIE color space)", 
                      variable=selection, value="LAB",
                      font=("Arial", 10)).pack(anchor='w', pady=5)
        
        tk.Radiobutton(rb_frame, text="RGB (Red/Green/Blue, 0-255 normalized)", 
                      variable=selection, value="RGB",
                      font=("Arial", 10)).pack(anchor='w', pady=5)
        
        tk.Radiobutton(rb_frame, text="CMY (Cyan/Magenta/Yellow, 0-255 normalized)", 
                      variable=selection, value="CMY",
                      font=("Arial", 10)).pack(anchor='w', pady=5)
        
        # Separator
        tk.Frame(dialog, height=2, bg="gray").pack(fill='x', padx=20, pady=10)
        
        # Normalized data confirmation
        normalized_var = tk.BooleanVar(value=False)
        check_frame = tk.Frame(dialog)
        check_frame.pack(pady=5)
        
        check = tk.Checkbutton(check_frame, 
                              text="✓ I confirm this data is already normalized (0-1 range)",
                              variable=normalized_var,
                              font=("Arial", 10, "bold"),
                              fg="darkred")
        check.pack()
        
        # Warning note
        warning = tk.Label(dialog, 
                          text="⚠️ Required for Plot_3D compatibility\n(Unnormalized data will not plot correctly)",
                          font=("Arial", 9), fg="#CC0000")
        warning.pack(pady=5)
        
        # Info note
        note = tk.Label(dialog, 
                       text="Axis labels will match your selection.\nData values remain unchanged.",
                       font=("Arial", 9), fg="#666666")
        note.pack(pady=5)
        
        # OK button (disabled until checkbox is checked)
        def on_ok():
            if not normalized_var.get():
                messagebox.showwarning(
                    "Confirmation Required",
                    "Please confirm that your data is normalized (0-1 range).\n\n"
                    "Plot_3D requires normalized data to function correctly."
                )
                return
            dialog.destroy()
        
        ok_btn = tk.Button(dialog, text="OK", command=on_ok, width=10, font=("Arial", 10, "bold"))
        ok_btn.pack(pady=10)
        
        # Wait for dialog to close
        dialog.wait_window()
        
        return selection.get()
    
    def create_rigid_template(self):
        """Create a new rigid Plot_3D template."""
        logging.debug("Create Rigid Template")
        
        # Ask user for template name
        template_name = simpledialog.askstring(
            "Template Name",
            "Enter a name for the rigid template:",
            initialvalue="Plot3D_Rigid"
        )
        
        if not template_name:
            return
            
        # Get save location
        file_root = tk.Tk()
        file_root.withdraw()
        
        file_types = [
            ('OpenDocument Spreadsheet', '*.ods'),
            ('All files', '*.*')
        ]
        
        selected_file = filedialog.asksaveasfilename(
            title="Save Rigid Template",
            filetypes=file_types,
            defaultextension=".ods",
            initialfile=f"{template_name}_Template"
        )
        file_root.destroy()
        
        if selected_file:
            try:
                # Create rigid template
                rigid_creator = RigidPlot3DTemplate()
                success = rigid_creator.create_rigid_template(selected_file, template_name)
                
                if success:
                    self.file_path = os.path.abspath(selected_file)
                    logging.info(f"Created rigid template: {self.file_path}")
                    messagebox.showinfo(
                        "Template Created",
                        f"Rigid Plot_3D template created successfully!\n\n"
                        f"File: {os.path.basename(selected_file)}\n\n"
                        f"Features:\n"
                        f"• Protected column structure\n"
                        f"• Data validation dropdowns\n"
                        f"• Format compliance for K-means & ΔE\n"
                        f"• 'Refresh Data' compatible\n\n"
                        f"Ready for Plot_3D analysis!"
                    )
                    self.root.destroy()
                else:
                    messagebox.showerror(
                        "Creation Failed",
                        "Failed to create rigid template. Please try again."
                    )
            except Exception as e:
                logging.error(f"Error creating rigid template: {e}")
                messagebox.showerror(
                    "Error",
                    f"Error creating rigid template:\n\n{str(e)}"
                )
        else:
            logging.warning("No save location selected")
    
    def select_existing_template(self):
        """Select from existing rigid templates in the templates directory."""
        logging.debug("Select Existing Template")
        
        # Check templates directory
        templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "templates", "plot3d")
        
        if not os.path.exists(templates_dir):
            # Create templates directory and rigid templates
            try:
                os.makedirs(templates_dir, exist_ok=True)
                results = create_rigid_plot3d_templates()
                logging.info(f"Created template directory and templates: {results}")
            except Exception as e:
                logging.error(f"Error creating templates: {e}")
        
        # Look for existing rigid templates
        rigid_templates = []
        if os.path.exists(templates_dir):
            for file in os.listdir(templates_dir):
                if file.endswith('.ods') and 'Rigid' in file:
                    rigid_templates.append(os.path.join(templates_dir, file))
        
        # If no rigid templates found, offer to create them
        if not rigid_templates:
            create_new = messagebox.askyesno(
                "No Rigid Templates",
                "No rigid templates found in the templates directory.\n\n"
                "Would you like to create the standard rigid templates now?"
            )
            
            if create_new:
                try:
                    results = create_rigid_plot3d_templates()
                    if results:
                        messagebox.showinfo(
                            "Templates Created",
                            f"Created rigid templates:\n\n" + "\n".join(results)
                        )
                        # Refresh the list
                        for file in os.listdir(templates_dir):
                            if file.endswith('.ods') and 'Rigid' in file:
                                rigid_templates.append(os.path.join(templates_dir, file))
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create templates: {e}")
                    return
            else:
                return
        
        # Let user select from available templates
        if rigid_templates:
            file_root = tk.Tk()
            file_root.withdraw()
            
            selected_file = filedialog.askopenfilename(
                title="Select Rigid Template",
                initialdir=templates_dir,
                filetypes=[
                    ('OpenDocument Spreadsheet', '*.ods'),
                    ('All files', '*.*')
                ]
            )
            file_root.destroy()
            
            if selected_file:
                self.file_path = os.path.abspath(selected_file)
                logging.info(f"Selected existing rigid template: {self.file_path}")
                self.root.destroy()

