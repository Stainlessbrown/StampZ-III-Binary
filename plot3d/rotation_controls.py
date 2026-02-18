import tkinter as tk
from tkinter import ttk
from .rotary_knob import RotaryKnob

class RotationControls(tk.LabelFrame):
    """Widget providing controls for 3D plot rotation using rotary knobs"""
    
    def __init__(self, master, on_rotation_change=None, trendline_manager=None, plotly_callback=None, hue_wheel_callback=None):
        """Initialize rotation controls
        
        Args:
            master: Parent widget
            on_rotation_change: Callback function to be called when rotation changes
            trendline_manager: TrendlineManager instance for trendline-based views
            plotly_callback: Callback to open Plotly viewer
            hue_wheel_callback: Callback to open Hue Wheel viewer
        """
        super().__init__(master, text="◎ Rotation Controls - CLICK & DRAG KNOBS ◎", 
                       font=('Arial', 10, 'bold'), foreground='blue', borderwidth=2)
        
        # Initialize default values for the 3D plot (in plot coordinate system)
        self._elevation = 30  # Plot angles are in -180 to 180 range
        self._azimuth = -60
        self._roll = 0
        
        # Set callback function
        self.on_rotation_change = on_rotation_change
        
        # Store trendline manager for trendline-based views
        self.trendline_manager = trendline_manager
        
        # Store Plotly viewer callback
        self.plotly_callback = plotly_callback
        
        # Store Hue Wheel viewer callback
        self.hue_wheel_callback = hue_wheel_callback
        
        # Flag to prevent recursive callbacks
        self._updating_programmatically = False
        
        # 2D view mode flag
        self.use_2d_view = tk.BooleanVar(value=False)
        
        # Store current plane view ('xy', 'xz', 'yz', or None for 3D perspective)
        self.current_plane = None
        
        # Create Tkinter variables for spinboxes - show actual plot angles
        self.elevation_var = tk.DoubleVar(value=self._elevation)
        self.azimuth_var = tk.DoubleVar(value=self._azimuth)
        self.roll_var = tk.DoubleVar(value=self._roll)
        
        # Knob references
        self.elevation_knob = None
        self.azimuth_knob = None
        self.roll_knob = None
        
        # Create controls
        self._create_controls()
        
        # Connect variable trace callbacks for spinboxes with write and read monitoring
        # This ensures updates are detected from both programmatic and user changes
        self.elevation_var.trace_add("write", self._on_elevation_change)
        self.azimuth_var.trace_add("write", self._on_azimuth_change)
        self.roll_var.trace_add("write", self._on_roll_change)
    
    def _plot_to_knob_elevation(self, elevation):
        """Convert from plot elevation (-180 to 180) to knob angle (0-360)"""
        # Same mapping as azimuth and roll: -180 maps to 0, 180 maps to 360
        return (elevation + 180) % 360
    
    def _knob_to_plot_elevation(self, knob_angle):
        """Convert from knob angle (0-360) to plot elevation (-180 to 180)"""
        # Same mapping as azimuth and roll
        normalized = knob_angle % 360
        return normalized - 180 if normalized <= 180 else normalized - 540
    
    def _plot_to_knob_azimuth(self, azimuth):
        """Convert from plot azimuth (-180 to 180) to knob angle (0-360)"""
        # Simple offset: -180 maps to 0, 180 maps to 360
        return (azimuth + 180) % 360
    
    def _knob_to_plot_azimuth(self, knob_angle):
        """Convert from knob angle (0-360) to plot azimuth (-180 to 180)"""
        # Map 0-360 to -180 to 180
        normalized = knob_angle % 360
        return normalized - 180 if normalized <= 180 else normalized - 540
    
    def _plot_to_knob_roll(self, roll):
        """Convert from plot roll (-180 to 180) to knob angle (0-360)"""
        # Same mapping as azimuth
        return (roll + 180) % 360
    
    def _knob_to_plot_roll(self, knob_angle):
        """Convert from knob angle (0-360) to plot roll (-180 to 180)"""
        # Same mapping as azimuth
        normalized = knob_angle % 360
        return normalized - 180 if normalized <= 180 else normalized - 540
        
    def _create_controls(self):
        """Create rotation control UI elements using rotary knobs"""
        # Container frame with more horizontal room
        main_frame = tk.Frame(self)
        main_frame.grid(padx=6, pady=5)  # Minimal padding to maximize internal space
        
        # Create a frame for the knobs (horizontal layout)
        knobs_frame = tk.Frame(main_frame)
        knobs_frame.grid(row=0, column=0, padx=2, pady=3)  # Minimal horizontal padding
        
        # Configure column weights to ensure even spacing
        knobs_frame.columnconfigure(0, weight=1)
        knobs_frame.columnconfigure(1, weight=1)
        knobs_frame.columnconfigure(2, weight=1)
        
        # Create each knob with labels (convert plot angles to knob angles)
        self._create_knob_column(knobs_frame, 0, "Elevation", 
                                self._plot_to_knob_elevation(self._elevation), self._on_elevation_knob_change)
        self._create_knob_column(knobs_frame, 1, "Azimuth", 
                                self._plot_to_knob_azimuth(self._azimuth), self._on_azimuth_knob_change)
        self._create_knob_column(knobs_frame, 2, "Roll", 
                                self._plot_to_knob_roll(self._roll), self._on_roll_knob_change)
        
        # Spinbox frame below the knobs with more space
        spinbox_frame = tk.Frame(main_frame)
        spinbox_frame.grid(row=1, column=0, padx=3, pady=(3, 5))  # Minimal padding to save space
        
        # Configure column weights for spinbox frame too
        spinbox_frame.columnconfigure(0, weight=1)
        spinbox_frame.columnconfigure(1, weight=1)
        spinbox_frame.columnconfigure(2, weight=1)
        
        # Add spinboxes for precise control
        self._create_spinbox_row(spinbox_frame, 0, self.elevation_var)
        self._create_spinbox_row(spinbox_frame, 1, self.azimuth_var)
        self._create_spinbox_row(spinbox_frame, 2, self.roll_var)
        
        # Reset button
        reset_btn = ttk.Button(
            main_frame,
            text="Reset Rotation",
            command=self._reset_rotation
        )
        reset_btn.grid(row=2, column=0, sticky='ew', padx=5, pady=3)
        
        # Add plane view buttons frame
        self._create_plane_view_buttons(main_frame)
        
    def _create_knob_column(self, parent, column, label_text, initial_angle, callback):
        """Create a column containing a labeled rotary knob
        
        Args:
            parent: Parent widget
            column: Grid column
            label_text: Text for the control label
            initial_angle: Initial angle for the knob (0-360)
            callback: Function to call when knob value changes
        """
        # Frame for this knob column
        frame = tk.Frame(parent)
        # Use progressively narrower padding for columns from left to right
        # This ensures the rightmost column (Roll) fits properly
        col_padx = [6, 4, 2]  # Paddings for columns 0, 1, 2
        frame.grid(row=0, column=column, padx=col_padx[column], pady=2)
        
        # Label above the knob
        label = ttk.Label(frame, text=label_text, font=('Arial', 9, 'bold'))
        label.grid(row=0, column=0, pady=(0, 2))  # Minimal vertical padding
        
        # Create a frame with visible border for the knob to make it more obvious
        knob_frame = tk.Frame(frame, borderwidth=3, relief="raised", bg="#c0c0ff", 
                           highlightbackground="blue", highlightthickness=2)
        knob_frame.grid(row=1, column=0, padx=2, pady=2)
        
        # Rotary knob with slightly adjusted size (smaller size to fit better)
        knob = RotaryKnob(knob_frame, callback=callback, width=58, height=58)
        knob.pack(padx=1, pady=1)
        knob.set_angle(initial_angle)
        
        # Add active state visual feedback for knob interaction
        def on_knob_enter(e):
            knob_frame.config(bg="#a0a0ff", relief="sunken")  # Brighter blue, sunken appearance
            
        def on_knob_leave(e):
            knob_frame.config(bg="#c0c0ff", relief="raised")  # Back to normal
            
        # Add hover effect to knob and frame
        knob.bind("<Enter>", on_knob_enter)
        knob.bind("<Leave>", on_knob_leave)
        knob_frame.bind("<Enter>", on_knob_enter)
        knob_frame.bind("<Leave>", on_knob_leave)
        
        # Store reference to the knob
        if label_text == "Elevation":
            self.elevation_knob = knob
        elif label_text == "Azimuth":
            self.azimuth_knob = knob
        else:  # Roll
            self.roll_knob = knob
        
        return knob
    
    def _create_spinbox_row(self, parent, column, variable):
        """Create a spinbox for precise input
        
        Args:
            parent: Parent widget
            column: Grid column
            variable: Tkinter variable to bind to
        """
        # Spinbox showing actual plot angles (-180 to 180)
        spinbox = ttk.Spinbox(
            parent,
            from_=-180,
            to=180,
            width=6,
            increment=1.0,
            textvariable=variable,  # Bind to variable for immediate updating
            command=lambda: self._immediate_update(variable)  # Direct update on spinbox change
        )
        spinbox.grid(row=0, column=column, padx=4)  # Add padding around the spinbox
        
        # Bind direct update to all relevant events for immediate responsiveness
        spinbox.bind("<Return>", lambda e: self._immediate_update(variable))
        spinbox.bind("<FocusOut>", lambda e: self._immediate_update(variable))
        spinbox.bind("<KeyRelease>", lambda e: self._immediate_update(variable))
        
        # Handle button click/release events to trigger updates
        spinbox.bind("<ButtonRelease-1>", lambda e: self._immediate_update(variable))
        
        # Add up/down keys with direct updates
        spinbox.bind("<Up>", lambda e: (self._increment_spinbox(variable, 1.0), self._immediate_update(variable)))
        spinbox.bind("<Down>", lambda e: (self._increment_spinbox(variable, -1.0), self._immediate_update(variable)))
        spinbox.bind("<MouseWheel>", lambda e: (self._increment_spinbox(variable, 1.0 if e.delta > 0 else -1.0), self._immediate_update(variable)))
        
        return spinbox
    
    def _on_elevation_knob_change(self, angle):
        """Handle elevation knob rotation"""
        if self._updating_programmatically:
            return
        
        try:
            # Convert the knob angle (0-360) to plot elevation (-180 to 180)
            self._elevation = self._knob_to_plot_elevation(angle)
            
            # Update the spinbox value (showing plot angle -180 to 180)
            self._updating_programmatically = True
            self.elevation_var.set(round(self._elevation))
            self._updating_programmatically = False
            
            # Trigger the callback to update the plot
            self._trigger_callback()
        except Exception as e:
            print(f"Error in elevation knob update: {e}")
    
    def _on_azimuth_knob_change(self, angle):
        """Handle azimuth knob rotation"""
        if self._updating_programmatically:
            return
        
        try:
            # Convert the knob angle (0-360) to plot azimuth (-180 to 180)
            self._azimuth = self._knob_to_plot_azimuth(angle)
            
            # Update the spinbox value (showing plot angle -180 to 180)
            self._updating_programmatically = True
            self.azimuth_var.set(round(self._azimuth))
            self._updating_programmatically = False
            
            # Trigger the callback to update the plot
            self._trigger_callback()
        except Exception as e:
            print(f"Error in azimuth knob update: {e}")
    
    def _on_roll_knob_change(self, angle):
        """Handle roll knob rotation"""
        if self._updating_programmatically:
            return
        
        try:
            # Convert the knob angle (0-360) to plot roll (-180 to 180)
            self._roll = self._knob_to_plot_roll(angle)
            
            # Update the spinbox value (showing plot angle -180 to 180)
            self._updating_programmatically = True
            self.roll_var.set(round(self._roll))
            self._updating_programmatically = False
            
            # Trigger the callback to update the plot
            self._trigger_callback()
        except Exception as e:
            print(f"Error in roll knob update: {e}")

    def _on_elevation_change(self, *args):
        """Handle elevation variable changes from spinbox"""
        if self._updating_programmatically:
            return
            
        try:
            # Get the spinbox value (plot angle -180 to 180)
            plot_angle = self.elevation_var.get()
            self._elevation = plot_angle
            
            # Convert plot angle to knob angle and update knob UI
            knob_angle = self._plot_to_knob_elevation(plot_angle)
            if self.elevation_knob:
                self.elevation_knob.set_angle(knob_angle)
            
            # Trigger the callback
            self._trigger_callback()
        except Exception as e:
            print(f"Error updating elevation: {e}")
    
    def _on_azimuth_change(self, *args):
        """Handle azimuth variable changes from spinbox"""
        if self._updating_programmatically:
            return
            
        try:
            # Get the spinbox value (plot angle -180 to 180)
            plot_angle = self.azimuth_var.get()
            self._azimuth = plot_angle
            
            # Convert plot angle to knob angle and update knob UI
            knob_angle = self._plot_to_knob_azimuth(plot_angle)
            if self.azimuth_knob:
                self.azimuth_knob.set_angle(knob_angle)
            
            # Trigger the callback
            self._trigger_callback()
        except Exception as e:
            print(f"Error updating azimuth: {e}")
    
    def _on_roll_change(self, *args):
        """Handle roll variable changes from spinbox"""
        if self._updating_programmatically:
            return
            
        try:
            # Get the spinbox value (plot angle -180 to 180)
            plot_angle = self.roll_var.get()
            self._roll = plot_angle
            
            # Convert plot angle to knob angle and update knob UI
            knob_angle = self._plot_to_knob_roll(plot_angle)
            if self.roll_knob:
                self.roll_knob.set_angle(knob_angle)
            
            # Trigger the callback
            self._trigger_callback()
        except Exception as e:
            print(f"Error updating roll: {e}")
    
    def _trigger_callback(self):
        """Trigger the rotation change callback"""
        if self.on_rotation_change:
            try:
                self.on_rotation_change()
            except Exception as e:
                print(f"Error in rotation callback: {e}")
    
    def _validate_values(self, event=None):
        """Validate rotation values and ensure they are in valid ranges"""
        try:
            # Set flag to prevent recursive callbacks (only once)
            self._updating_programmatically = True
            
            # Get current values from spinboxes (plot angles -180 to 180)
            try:
                self._elevation = float(self.elevation_var.get())
                self._azimuth = float(self.azimuth_var.get())
                self._roll = float(self.roll_var.get())
                
                # Normalize to -180 to 180 range
                self._elevation = ((self._elevation + 180) % 360) - 180
                self._azimuth = ((self._azimuth + 180) % 360) - 180
                self._roll = ((self._roll + 180) % 360) - 180
            except (ValueError, tk.TclError):
                # Keep current values if conversion fails
                pass
            
            # Update spinbox variables with normalized plot angles
            # Only update if values have changed to prevent recursive updates
            if round(self.elevation_var.get()) != round(self._elevation):
                self.elevation_var.set(round(self._elevation))
            if round(self.azimuth_var.get()) != round(self._azimuth):
                self.azimuth_var.set(round(self._azimuth))
            if round(self.roll_var.get()) != round(self._roll):
                self.roll_var.set(round(self._roll))
            
            # Update knob positions (convert plot angles to knob angles)
            if self.elevation_knob:
                self.elevation_knob.set_angle(self._plot_to_knob_elevation(self._elevation))
            if self.azimuth_knob:
                self.azimuth_knob.set_angle(self._plot_to_knob_azimuth(self._azimuth))
            if self.roll_knob:
                self.roll_knob.set_angle(self._plot_to_knob_roll(self._roll))
            
            # Ensure UI updates
            self.update_idletasks()
            
            # Reset flag before triggering callback
            self._updating_programmatically = False
            
            # Trigger the plot update
            self._trigger_callback()

        except Exception as e:
            print(f"Error validating values: {e}")
            self._updating_programmatically = False

    def _reset_rotation(self):
        """Reset rotation to default values"""
        # Set flag to prevent recursive callbacks
        self._updating_programmatically = True
        
        try:
            # Default plot values
            default_elev = 30
            default_azim = -60
            default_roll = 0
            
            # Update internal state
            self._elevation = default_elev
            self._azimuth = default_azim
            self._roll = default_roll
            
            # Update spinbox variables with plot angles
            self.elevation_var.set(round(default_elev))
            self.azimuth_var.set(round(default_azim))
            self.roll_var.set(round(default_roll))
            
            # Update knob positions (convert plot angles to knob angles)
            if self.elevation_knob:
                self.elevation_knob.set_angle(self._plot_to_knob_elevation(default_elev))
            if self.azimuth_knob:
                self.azimuth_knob.set_angle(self._plot_to_knob_azimuth(default_azim))
            if self.roll_knob:
                self.roll_knob.set_angle(self._plot_to_knob_roll(default_roll))
            
            # Ensure UI updates
            self.update_idletasks()
            
        except Exception as e:
            print(f"Error resetting rotation: {e}")
            
        finally:
            # Always reset the flag and trigger callback
            self._updating_programmatically = False
            self._trigger_callback()
    def update_values(self, elev, azim, roll=0):
        """Update rotation values without triggering callbacks
        
        This is used when the plot updates the controls, rather than
        the controls updating the plot.
        
        Args:
            elev: Elevation angle in plot coordinates (may be outside -180 to 180)
            azim: Azimuth angle in plot coordinates (may be outside -180 to 180)
            roll: Roll angle in plot coordinates (may be outside -180 to 180)
        """
        try:
            # Set flag to prevent recursive callbacks
            self._updating_programmatically = True
            
            # Update internal plot angles and normalize to -180 to 180
            self._elevation = float(elev)
            self._azimuth = float(azim)
            self._roll = float(roll)
            
            # Normalize to -180 to 180 range
            self._elevation = ((self._elevation + 180) % 360) - 180
            self._azimuth = ((self._azimuth + 180) % 360) - 180
            self._roll = ((self._roll + 180) % 360) - 180
            
            # Update spinbox variables with plot angles
            self.elevation_var.set(round(self._elevation))
            self.azimuth_var.set(round(self._azimuth))
            self.roll_var.set(round(self._roll))
            
            # Update knob positions (convert plot angles to knob angles)
            if self.elevation_knob:
                self.elevation_knob.set_angle(self._plot_to_knob_elevation(self._elevation))
            if self.azimuth_knob:
                self.azimuth_knob.set_angle(self._plot_to_knob_azimuth(self._azimuth))
            if self.roll_knob:
                self.roll_knob.set_angle(self._plot_to_knob_roll(self._roll))
            
            # Ensure UI updates
            self.update_idletasks()
            
        except Exception as e:
            print(f"Error updating values: {e}")
        finally:
            self._updating_programmatically = False
    def _increment_spinbox(self, variable, amount):
        """Increment or decrement a spinbox value
        
        Args:
            variable: The Tkinter variable to modify
            amount: The amount to add (can be negative)
        """
        try:
            current_value = variable.get()
            # Calculate new value and normalize to -180 to 180
            new_value = current_value + amount
            new_value = ((new_value + 180) % 360) - 180
            new_value = round(new_value)
            # Set flag to prevent recursive callbacks that could interfere with the update
            self._updating_programmatically = True
            variable.set(new_value)
            self._updating_programmatically = False
            
            # This will trigger the appropriate change handler through the variable trace
        except Exception as e:
            print(f"Error incrementing value: {e}")
            self._updating_programmatically = False
    
    def _immediate_update(self, variable):
        """Force immediate update from spinbox changes
        
        Args:
            variable: The Tkinter variable to update from
        """
        try:
            # Normalize and round the value to -180 to 180 range
            value = float(variable.get())
            value = ((value + 180) % 360) - 180
            value = round(value)
            
            # Set the normalized value back to ensure consistency
            if variable.get() != value:
                variable.set(value)
            
            # Validate and update the plot
            self._validate_values()
        except (ValueError, tk.TclError):
            # Ignore invalid values, they'll be fixed by _validate_values later
            pass
            
    def _validate_and_update(self, event=None):
        """Validate values and explicitly trigger rotation update"""
        # Just call validate values which already triggers the callback
        self._validate_values(event)
    
    @property
    def elevation(self):
        """Get the current elevation value"""
        return self._elevation
    
    @property
    def azimuth(self):
        """Get the current azimuth value"""
        return self._azimuth
    
    @property
    def roll(self):
        """Get the current roll value"""
        return self._roll
        
    def _create_plane_view_buttons(self, parent):
        """Create buttons for preset plane views
        
        Args:
            parent: Parent widget
        """
        # Create a labeled frame for the plane view buttons
        plane_frame = ttk.LabelFrame(parent, text="Plane Views")
        plane_frame.grid(row=3, column=0, sticky='ew', padx=5, pady=5)
        
        # Add 2D/3D mode toggle at the top
        mode_frame = ttk.Frame(plane_frame)
        mode_frame.grid(row=0, column=0, padx=5, pady=(5,2), sticky='ew')
        
        ttk.Checkbutton(
            mode_frame,
            text="📊 Use 2D Plot (fills window better)",
            variable=self.use_2d_view,
            command=self._on_view_mode_change
        ).pack(side=tk.LEFT)
        
        # Create a frame for the buttons
        button_frame = ttk.Frame(plane_frame)
        button_frame.grid(row=1, column=0, padx=5, pady=5, sticky='ew')
        
        # Configure grid weights to distribute buttons evenly
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)
        
        # Create X/Y plane button
        xy_btn = ttk.Button(
            button_frame,
            text="X/Y Plane",
            command=lambda: self._set_plane_view('xy')
        )
        xy_btn.grid(row=0, column=0, padx=2, pady=2, sticky='ew')
        
        # Create X/Z plane button
        xz_btn = ttk.Button(
            button_frame,
            text="X/Z Plane",
            command=lambda: self._set_plane_view('xz')
        )
        xz_btn.grid(row=0, column=1, padx=2, pady=2, sticky='ew')
        
        # Create Y/Z plane button
        yz_btn = ttk.Button(
            button_frame,
            text="Y/Z Plane",
            command=lambda: self._set_plane_view('yz')
        )
        yz_btn.grid(row=0, column=2, padx=2, pady=2, sticky='ew')
        
        # Add Plotly interactive viewer button if callback is available
        if self.plotly_callback is not None:
            plotly_btn = ttk.Button(
                button_frame,
                text="🌐 Interactive View (Browser)",
                command=self.plotly_callback
            )
            plotly_btn.grid(row=2, column=0, columnspan=3, padx=2, pady=(5,2), sticky='ew')
            
            # Add note about features
            note_label = ttk.Label(
                button_frame,
                text="Includes: Linear trendline & visible spheres\n(Opens new browser tab each time)\n(Spheres may block hover - toggle off to inspect points)\n(Polynomial trendline: matplotlib only)",
                font=('Arial', 9),
                foreground='gray',
                justify='center'
            )
            note_label.grid(row=3, column=0, columnspan=3, padx=2, pady=(0,5), sticky='ew')
        
        # Add Hue Wheel viewer button if callback is available
        if self.hue_wheel_callback is not None:
            hue_wheel_btn = ttk.Button(
                button_frame,
                text="🎨 Hue Wheel (Polar Plot)",
                command=self.hue_wheel_callback
            )
            # Position below Plotly button if it exists, otherwise at row 2
            row_pos = 4 if self.plotly_callback is not None else 2
            hue_wheel_btn.grid(row=row_pos, column=0, columnspan=3, padx=2, pady=(2,2), sticky='ew')
            
            # Add note about hue wheel
            hue_note_label = ttk.Label(
                button_frame,
                text="Visualizes L*C*h data: Angle=Hue, Radius=Chroma\n(Requires L*C*h columns in template)",
                font=('Arial', 9),
                foreground='gray',
                justify='center'
            )
            hue_note_label.grid(row=row_pos+1, column=0, columnspan=3, padx=2, pady=(0,5), sticky='ew')
        
        return plane_frame
    
    def _on_view_mode_change(self):
        """Handle 2D/3D view mode toggle change."""
        # Just trigger a callback - the plot will check the mode and render accordingly
        print(f"View mode changed to: {'2D' if self.use_2d_view.get() else '3D'}")
        self._trigger_callback()
        
    def _set_plane_view(self, plane):
        """Set the view angles for a specific plane view
        
        Args:
            plane: String indicating which plane view to set ('xy', 'xz', or 'yz')
        """
        try:
            # Set flag to prevent recursive callbacks
            self._updating_programmatically = True
            
            # Define the angles for each plane view (in plot coordinates -180 to 180)
            views = {
                'xy': {'elev': 90, 'azim': 0, 'roll': 0},       # X/Y plane (top view)
                'xz': {'elev': 0, 'azim': 0, 'roll': 0},        # X/Z plane (front view)
                'yz': {'elev': 0, 'azim': 90, 'roll': 0}        # Y/Z plane (side view)
            }
            
            if plane in views:
                view = views[plane]
                
                # Store the current plane for 2D rendering
                self.current_plane = plane
                
                # Update internal state
                self._elevation = view['elev']
                self._azimuth = view['azim']
                self._roll = view['roll']
                
                # Convert to knob angles (0-360)
                elev_knob = self._plot_to_knob_elevation(self._elevation)
                azim_knob = self._plot_to_knob_azimuth(self._azimuth)
                roll_knob = self._plot_to_knob_roll(self._roll)
                
                # Update spinbox variables
                self.elevation_var.set(round(elev_knob))
                self.azimuth_var.set(round(azim_knob))
                self.roll_var.set(round(roll_knob))
                
                # Update knob positions
                if self.elevation_knob:
                    self.elevation_knob.set_angle(elev_knob)
                if self.azimuth_knob:
                    self.azimuth_knob.set_angle(azim_knob)
                if self.roll_knob:
                    self.roll_knob.set_angle(roll_knob)
                
                print(f"Set {plane.upper()} plane view: elev={self._elevation}, azim={self._azimuth}, roll={self._roll}")
                
        except Exception as e:
            print(f"Error setting plane view: {e}")
        finally:
            # Reset flag and trigger callback
            self._updating_programmatically = False
            self._trigger_callback()
