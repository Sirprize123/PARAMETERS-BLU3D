import re
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, Text, Scrollbar, simpledialog, ttk
import os
from datetime import datetime


class SRCModifierApp:
    def __init__(self, root):
        try:
            self.root = root
            self.root.title("SRC File Modifier")
            self.root.geometry("1140x700")
            
            # Create menu bar
            self.menubar = tk.Menu(self.root)
            self.root.config(menu=self.menubar)
            
            # Create File menu
            self.file_menu = tk.Menu(self.menubar, tearoff=0)
            self.menubar.add_cascade(label="File", menu=self.file_menu)
            self.file_menu.add_command(label="Open", command=self.load_file)
            self.file_menu.add_command(label="Save", command=self.modify_file, state='disabled')
            self.file_menu.add_separator()
            self.file_menu.add_command(label="Exit", command=self.root.quit)
            
            # Store reference to save menu item for enabling/disabling
            self.save_menu_item = self.file_menu
            
            # Add collapsible frame for file metadata editing
            self.metadata_frame = ttk.Frame(self.root)
            self.metadata_frame.pack(fill='x', padx=2, pady=2)
            
            # Metadata header with toggle button
            metadata_header = ttk.Frame(self.metadata_frame)
            metadata_header.pack(fill='x')
            
            self.metadata_toggle = ttk.Button(metadata_header, text="▶", width=3)
            self.metadata_toggle.pack(side='left', padx=1)
            ttk.Label(metadata_header, text="Change Name and Start Position").pack(side='left', padx=5)
            
            # Content frame that will be collapsed/expanded
            self.metadata_content = ttk.Frame(self.metadata_frame)
            # Start collapsed - don't pack initially
            
            # DEF name section
            def_frame = ttk.Frame(self.metadata_content) 
            def_frame.pack(fill='x', pady=1)
            ttk.Label(def_frame, text="Display Name:").pack(side='left', padx=5)
            self.def_entry = ttk.Entry(def_frame, width=20)
            self.def_entry.pack(side='left')
            
            # PARKPOS section
            parkpos_frame = ttk.Frame(self.metadata_content)
            parkpos_frame.pack(fill='x', pady=1)
            ttk.Label(parkpos_frame, text="Starting Position:").pack(side='left', padx=5)
            
            # Compact position entries
            positions = ['X', 'Y', 'Z', 'A', 'B', 'C', 'S', 'T']
            self.parkpos_entries = {}
            
            pos_frame = ttk.Frame(parkpos_frame)
            pos_frame.pack(side='left')
            
            for i, pos in enumerate(positions):
                ttk.Label(pos_frame, text=pos).pack(side='left')
                self.parkpos_entries[pos] = ttk.Entry(pos_frame, width=5)
                self.parkpos_entries[pos].pack(side='left', padx=(0,3))
            
            # Update button
            ttk.Button(self.metadata_content, text="Update", width=8,
                      command=self.update_file_settings).pack(pady=1)
            
            # Add toggle_metadata_frame method
            def toggle_metadata_frame(self):
                if self.metadata_content.winfo_viewable():
                    self.metadata_content.pack_forget()
                    self.metadata_toggle.configure(text="▶")
                else:
                    self.metadata_content.pack(fill='x', padx=5, pady=2)
                    self.metadata_toggle.configure(text="▼")
            
            # Make toggle_metadata_frame a method of the class
            self.toggle_metadata_frame = toggle_metadata_frame.__get__(self, SRCModifierApp)
            
            # Configure toggle button command
            self.metadata_toggle.configure(command=self.toggle_metadata_frame)
            
            # Initialize parameters
            self.params = {}
            self.param_line_numbers = {}  # Store line numbers for each parameter
            self.param_groups = {}
            self.step_size = 5.0  # Default step size (%)
            
            self.input_file = None
            self.original_content = None
            self.show_graph = tk.BooleanVar(value=True)
            
            # Create figure and canvas after UI elements
            self.fig = None
            self.ax = None
            self.canvas = None
            
            self.dragging_point = None
            self.preview_text = None
            # Define colors for each parameter type
            self.param_colors = {
                'TOOL_RPM': '#ffb3ff',  # Light Magenta
                '$VEL.CP': '#ffb3b3',   # Light Red
                'LAYER_COOLING': '#87CEEB',      # Light Blue
                'ACT_DRIVE': '#90EE90'  # Light LIGHT GREEN
            }
            
            # Store custom parameters
            self.print_progress_params = {}  # For print progress parameters
            # Store custom Z height parameters
            self.custom_z_params = {}
            self.param_frames = {}
            # Store Z height parameter frames
            self.z_param_frames = {}
            self.print_progress_frames = {}  # New dict to store print progress frames separately
            self.available_params = ['TOOL_RPM', '$VEL.CP', 'LAYER_COOLING', 'ACT_DRIVE']
            
            # Store parameter groups
            self.param_groups = {}
            
            # Store content frames for each parameter type
            self.content_frames = {}
            
            # Store header labels for each parameter type
            self.header_labels = {}

            # Store frame positions
            self.frame_positions = {}
            
            # Store trigger parameters that should be preserved
            self.trigger_params = {}
            
            # Add undo/redo history
            self.undo_history = []
            self.redo_history = []
            self.max_history = 50  # Maximum number of operations to store
            
            # Add search tracking variables
            self.current_search_pos = "1.0"
            self.last_search_term = ""
            
            # Create UI elements
            self.create_ui()
            
            # Initialize save button
            self.save_button = tk.Button(self.root, text="Save", command=self.modify_file, state=tk.DISABLED)
            
            # Initialize undo/redo buttons
            self.undo_button = tk.Button(self.root, text="Undo", command=self.undo_last_action, state=tk.DISABLED)
            self.undo_button.pack(side='bottom', pady=5)
            
            self.redo_button = tk.Button(self.root, text="Redo", command=self.redo_last_action, state=tk.DISABLED)
            self.redo_button.pack(side='bottom', pady=5)

            # Add find text functionality
            self.find_text = lambda: None  # Placeholder for find_text method
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize application: {str(e)}")

    def update_file_settings(self):
        try:
            if not self.original_content:
                messagebox.showerror("Error", "Please load a file first")
                return
            
            # Save current state before modification
            self.save_state()
            
            lines = self.original_content.splitlines()
            modified = False
            
            # Get file name without extension
            file_name = os.path.basename(self.input_file).split('.')[0]
            
            # Update the lines
            if self.def_entry.get().strip():
                lines[0] = f"DEF {self.def_entry.get()}"
                modified = True
            
            # Build PARKPOS string from entries
            parkpos_str = "PARKPOS = {POS:"
            for pos, entry in self.parkpos_entries.items():
                if pos in ['S', 'T']:
                    parkpos_str += f" {pos} 'B{entry.get()}',"
                else:
                    parkpos_str += f" {pos} {entry.get()},"
            parkpos_str = parkpos_str.rstrip(',') + '}'
            
            for i, line in enumerate(lines):
                if line.startswith("PARKPOS = "):  # Modify PARKPOS line
                    lines[i] = parkpos_str
                    modified = True
                elif line.startswith(";generated with "):  # Overwrite generation info
                    lines[i] = ";generated by @BLU3D, experimental prototype 0.1"
                    modified = True
                elif line.startswith(";Source file name: "):  # Overwrite source file name
                    lines[i] = f";Source file name: {file_name}.src"
                    modified = True
            
            if modified:
                self.original_content = '\n'.join(lines) + '\n'
                
                # Force preview update
                if self.preview_text:
                    self.preview_text.delete("1.0", tk.END)
                    self.preview_text.insert("1.0", self.original_content)
                self.update_preview()
                
                self.save_button.config(state=tk.NORMAL)
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update settings: {str(e)}")

    def load_file(self):
        try:
            # Open file dialog to select .src file
            file_path = filedialog.askopenfilename(
                filetypes=[("SRC files", "*.src"), ("All files", "*.*")]
            )
            
            if not file_path:
                return
                
            self.input_file = file_path
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as file:
                self.original_content = file.read()
                
            # After loading file content, extract DEF and PARKPOS values
            lines = self.original_content.splitlines()
            if lines:
                for line in lines:
                    if line.startswith("DEF "):
                        def_value = line.split("DEF  ", 1)[1]
                        self.def_entry.delete(0, tk.END)
                        self.def_entry.insert(0, def_value)
                    elif line.startswith("PARKPOS = "):
                        # Parse PARKPOS values
                        parkpos_str = line.split("PARKPOS = ", 1)[1]
                        # Extract values using regex
                        pos_pattern = re.compile(r'([XYZABCST])\s+(?:\'B)?([^,\s}]+)')
                        matches = pos_pattern.finditer(parkpos_str)
                        
                        for match in matches:
                            pos, value = match.groups()
                            if pos in self.parkpos_entries:
                                self.parkpos_entries[pos].delete(0, tk.END)
                                self.parkpos_entries[pos].insert(0, value.strip("'"))
            
            # Extract parameters and create UI elements
            if self.extract_params_from_file():
                self.create_param_entries()
                
                self.save_button.config(state=tk.NORMAL)  # Enable save button when file is loaded
                self.file_menu.entryconfig("Save", state='normal')  # Enable save menu item
                self.update_preview()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {str(e)}")

    def add_print_progress(self):
        self.add_frame("Add Print Progress", "Print Progress")
        
    def add_frame(self, title,frame_name):
        try:
            # Save current state before adding
            self.save_state()
            
            # Create dialog window
            dialog = tk.Toplevel(self.root)
            dialog.title(title)
            dialog.geometry("150x150")  # Increased height for header
            
            # Create header frame
            header_frame = tk.Frame(dialog)
            header_frame.pack(fill='x', padx=5, pady=5)
            
            # Create and pack entry widget
            value_var = tk.StringVar()
            entry = tk.Entry(dialog, textvariable=value_var)
            entry.pack(padx=5, pady=5)            
            # Focus the entry widget immediately
            entry.focus_set()
            
            # Create a bound method for the button command
            cmd = lambda: self.validate_and_add(value_var, frame_name, dialog)
            
            # Add button
            tk.Button(dialog, text="Add", command=cmd).pack(pady=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add print progress: {str(e)}")
            
    def validate_and_add(self, value_var, frame_name, dialog):
        try:
            if frame_name == "Print Progress":
                percentage = int(value_var.get())
                if percentage < 0 or percentage > 100:
                    messagebox.showerror("Error", "Percentage must be between 0 and 100.")
                    return
                
                if percentage not in self.print_progress_params:
                    self.print_progress_params[percentage] = {}
                
                # Create a frame for the new print progress parameter
                self.create_print_progress_frame(percentage, frame_name, is_z_height=False)
                
            elif frame_name == "Z Height":
                z_height = float(value_var.get())
                max_z = self.get_max_z_value()
                if z_height < 0 or z_height > max_z:
                    messagebox.showerror("Error", f"Z height must be between 0 and {max_z}.")
                    return
                    
                if z_height not in self.custom_z_params:
                    self.custom_z_params[z_height] = {}
                
                # Create a frame for the new Z height parameter
                self.create_print_progress_frame(z_height, frame_name, is_z_height=True)
            
            # Update line numbers and preview
            self.update_line_numbers()
            self.update_preview()
            
            # Get current position in preview text
            current_pos = self.preview_text.index("end-1c")
            
            # Snap preview to the newly added line
            self.preview_text.see(current_pos)
            self.preview_text.tag_add("highlight", current_pos, f"{current_pos} lineend")
            
            # After adding progress/z-height, prompt for parameter
            is_z_height = (frame_name == "Z Height")
            value = float(value_var.get()) if is_z_height else int(value_var.get())
            self.add_param_to_progress(value, is_z_height, dialog)
            
        except ValueError as e:
            if frame_name == "Print Progress":
                messagebox.showerror("Error", "Please enter a valid integer")
            else:
                messagebox.showerror("Error", "Please enter a valid number")
     # Add button
            
    
   
        
    def add_z_height(self):
        self.add_frame("Add Z Height", "Z Height")
       

    def get_max_z_value(self):
        """Extract the maximum Z value from the original content."""
        max_z = 0.0
        z_pattern = re.compile(r'LIN.*?Z\s(\d+\.\d+)')
        for line in self.original_content.splitlines():
            match = z_pattern.search(line)
            
            if match:
                z_value = float(match.group(1))
                
                if z_value > max_z:
                    max_z = z_value
        return max_z
   
    def create_print_progress_frame(self, value, frame_name, is_z_height=False):
        try:
            # Create new frame with appropriate title
            title = f"{frame_name}: {value}"
            if frame_name == "Print Progress":
                title += "%"
                
            progress_frame = tk.LabelFrame(self.param_frame, text=title)
            progress_frame.pack(fill='x', padx=5, pady=2)
            
            # Store the frame in the correct dictionary
            if frame_name == "Print Progress":
                if value not in self.print_progress_frames:
                    self.print_progress_frames[value] = progress_frame
            else:  # Z Height
                if value not in self.z_param_frames:
                    self.z_param_frames[value] = progress_frame

            # Create button frame at the top
            button_frame = tk.Frame(progress_frame)
            button_frame.pack(fill='x', padx=2, pady=1)

            # Get line number for jump button
            content_lines = self.original_content.splitlines()
            line_number = None
            
            if is_z_height:
                z_pattern = re.compile(r'LIN.*?Z\s*([-\d.]+)')
                for i, line in enumerate(content_lines, 1):
                    match = z_pattern.search(line)
                    if match and abs(float(match.group(1)) - value) < 0.0001:
                        line_number = i
                        break
            else:
                search_text = f"PRINT_PROGRESS={value}"
                for i, line in enumerate(content_lines, 1):
                    if search_text in line:
                        line_number = i
                        break

            # Jump to line button
            if line_number:
                jump_btn = tk.Button(button_frame, text="→", 
                                   command=lambda ln=line_number: self.jump_to_line(ln),
                                   bg='light blue')
                jump_btn.pack(side='left', padx=2)

            # Remove button
            remove_btn = tk.Button(button_frame, text="✕",
                                 bg='#ffb3b3', fg='white',
                                 command=lambda v=value, z=is_z_height: self.remove_param(v, z))
            remove_btn.pack(side='left', padx=2)

            # Add parameter button
            add_btn = tk.Button(button_frame, text="+",
                              bg='LIGHT GREEN', fg='white',
                              command=lambda v=value, z=is_z_height: self.add_param_to_progress(v, z))
            add_btn.pack(side='left', padx=2)

            # Add Parameter button at bottom
            add_param_btn = tk.Button(progress_frame, text="Add Parameter", 
                                    command=lambda: self.add_param_to_progress(value, is_z_height))
            add_param_btn.pack(side='bottom', pady=5)

            return progress_frame

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create frame: {str(e)}")

    def add_param_to_progress(self, value, is_z_height=False, parent_dialog=None):
        try:
            # Save current state before adding
            self.save_state()
            
            # Create parameter selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Parameter")
            dialog.geometry("300x200")
            
            # Parameter dropdown
            param_var = tk.StringVar(value='TOOL_RPM')
            param_dropdown = ttk.Combobox(dialog, textvariable=param_var, values=self.available_params)
            param_dropdown.pack(padx=5, pady=5)
            
            # Value entry
            value_frame = tk.Frame(dialog)
            value_frame.pack(padx=5, pady=5)
            value_var = tk.StringVar()
            value_entry = tk.Entry(value_frame, textvariable=value_var)
            value_entry.pack()

            def on_param_select(*args):
                if param_var.get() == 'ACT_DRIVE':
                    # Replace entry with combobox for TRUE/FALSE selection
                    value_entry.pack_forget()
                    value_combo = ttk.Combobox(value_frame, textvariable=value_var, values=['TRUE', 'FALSE'], state='readonly')
                    value_combo.pack()
                    
                else:
                    value_entry.config(state='normal')

            param_var.trace('w', on_param_select)

            def validate_param_value(param_name, value):
                try:
                    if param_name == 'TOOL_RPM':
                        val = float(value)
                        if val > 139.8:
                            messagebox.showerror("Error", "Maximum value for TOOL_RPM is 139.8")
                            return False
                    elif param_name == '$VEL.CP':
                        val = float(value)
                        if val > 2:
                            messagebox.showerror("Error", "Maximum value for $VEL.CP is 2")
                            return False
                        if val > 0.5:
                            return messagebox.askyesno("Warning", 
                                "Values above 0.5 for $VEL.CP could be dangerous.\n\n" +
                                "Do you wish to continue with this value?")
                    elif param_name == 'LAYER_COOLING':
                        val = int(value)
                        if val > 200:
                            messagebox.showerror("Error", "Maximum value for LAYER_COOLING is 200")
                            return False
                    return True
                except ValueError:
                    messagebox.showerror("Error", "Please enter a valid number")
                    return False

            def add_parameter():
                param_name = param_var.get()
                if not param_name:
                    messagebox.showerror("Error", "Please select a parameter")
                    return
                    
                param_value = value_var.get()
                if param_name == 'ACT_DRIVE':
                    if param_value.upper() not in ['TRUE', 'FALSE']:
                        messagebox.showerror("Error", "ACT_DRIVE can only be TRUE or FALSE")
                        return
                    param_value = param_value.upper()
                else:
                    # Validate parameter value before proceeding
                    if not validate_param_value(param_name, param_value):
                        return
                    param_value = float(param_value) if param_name != 'LAYER_COOLING' else int(param_value)

                # Add parameter to appropriate dictionary
                if is_z_height:
                    if value not in self.custom_z_params:
                        self.custom_z_params[value] = {}
                    self.custom_z_params[value][param_name] = param_value
                else:
                    if value not in self.print_progress_params:
                        self.print_progress_params[value] = {}
                    self.print_progress_params[value][param_name] = param_value

                # Find the appropriate position to insert/update the parameter
                content_lines = self.original_content.splitlines()
                insert_index = None
                param_exists = False
                existing_param_index = None

                if param_name == 'TOOL_RPM':
                    # For TOOL_RPM, add trigger command for both Z height and print progress
                    param_line = f"TRIGGER WHEN DISTANCE=0 DELAY=0 DO TOOL_RPM={param_value}"
                    if is_z_height:
                        z_pattern = re.compile(r'LIN.*?Z\s*([-\d.]+)')
                        for i, line in enumerate(content_lines):
                            match = z_pattern.search(line)
                            if match and abs(float(match.group(1)) - value) < 0.0001:
                                content_lines.insert(i + 1, param_line)
                                insert_index = i + 1
                                break
                    else:
                        trigger_pattern = f"TRIGGER WHEN DISTANCE=0 DELAY=0 DO PRINT_PROGRESS={int(value)}"
                        for i, line in enumerate(content_lines):
                            if trigger_pattern in line:
                                content_lines.insert(i + 1, param_line)
                                insert_index = i + 1
                                break
                elif is_z_height:
                    z_pattern = re.compile(r'LIN.*?Z\s*([-\d.]+)')
                    for i, line in enumerate(content_lines):
                        match = z_pattern.search(line)
                        if match and abs(float(match.group(1)) - value) < 0.0001:
                            # Search for existing parameter in this Z height block
                            j = i + 1
                            while j < len(content_lines) and any(param in content_lines[j] for param in self.available_params):
                                if f"{param_name}=" in content_lines[j]:
                                    param_exists = True
                                    existing_param_index = j
                                    break
                                j += 1
                            insert_index = j if not param_exists else None
                            break
                else:
                    trigger_pattern = f"TRIGGER WHEN DISTANCE=0 DELAY=0 DO PRINT_PROGRESS={int(value)}"
                    for i, line in enumerate(content_lines):
                        if trigger_pattern in line:
                            # Search for existing parameter in this print progress block
                            j = i + 1
                            while j < len(content_lines) and any(param in content_lines[j] for param in self.available_params):
                                if f"{param_name}=" in content_lines[j]:
                                    param_exists = True
                                    existing_param_index = j
                                    break
                                j += 1
                            insert_index = j if not param_exists else None
                            break

                if param_exists and param_name != 'TOOL_RPM':
                    # Update existing parameter
                    content_lines[existing_param_index] = f"{param_name}={param_value}"
                elif insert_index is not None:
                    if param_name != 'TOOL_RPM':
                        # Insert new parameter
                        content_lines.insert(insert_index, f"{param_name}={param_value}")
                else:
                    messagebox.showerror("Error", "Could not find appropriate position to insert parameter")
                    return

                # Update content and UI
                self.original_content = '\n'.join(content_lines) + '\n'
                self.update_preview()
                self.jump_to_line(existing_param_index + 1 if param_exists else insert_index + 1)
                self.refresh_progress_params(value, is_z_height)
                
                self.save_button.config(state=tk.NORMAL)
                
                dialog.destroy()
                if parent_dialog:
                    parent_dialog.destroy()

            # Add button
            tk.Button(dialog, text="Add", command=add_parameter).pack(pady=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add parameter: {str(e)}")

    def refresh_progress_params(self, value, is_z_height=False):
        try:
            # Get the correct frame and parameters dictionary based on type
            if is_z_height:
                frame = self.z_param_frames.get(value)
                params_dict = self.custom_z_params.get(value, {})
            else:
                frame = self.print_progress_frames.get(value)
                params_dict = self.print_progress_params.get(value, {})
                
            if frame is None:
                return  # Skip if frame doesn't exist yet
                
            # Clear existing parameter widgets
            for widget in frame.winfo_children():
                widget.destroy()
            
            # Create button frame at the top
            button_frame = tk.Frame(frame)
            button_frame.pack(fill='x', padx=2, pady=1)

            # Get the line number for the jump button
            content_lines = self.original_content.splitlines()
            line_number = None
            
            if is_z_height:
                z_pattern = re.compile(r'LIN.*?Z\s*([-\d.]+)')
                for i, line in enumerate(content_lines, 1):
                    match = z_pattern.search(line)
                    if match and abs(float(match.group(1)) - value) < 0.0001:
                        line_number = i
                        break
            else:
                search_text = f"PRINT_PROGRESS={value}"
                for i, line in enumerate(content_lines, 1):
                    if search_text in line:
                        line_number = i
                        break

            # Jump to line button
            if line_number:
                jump_btn = tk.Button(button_frame, text="→", 
                                   command=lambda ln=line_number: self.jump_to_line(ln),
                                   bg='light blue')
                jump_btn.pack(side='left', padx=2)

            # Add parameter button
            add_btn = tk.Button(button_frame, text="+",
                              bg='LIGHT GREEN', fg='white', 
                              command=lambda v=value, z=is_z_height: self.add_param_to_progress(v, z))
            add_btn.pack(side='left', padx=2)
            
            # Add parameter entries
            for param_name, param_value in params_dict.items():
                param_frame = tk.Frame(frame)
                param_frame.pack(fill='x', padx=2, pady=1)
                
                tk.Label(param_frame, text=param_name).pack(side='left')
                
                # Create entry for value that updates in real-time
                value_var = tk.StringVar(value=str(param_value))
                if param_name == 'ACT_DRIVE':
                    # For ACT_DRIVE, use a readonly Entry instead of Combobox
                    entry = tk.Entry(param_frame, textvariable=value_var, width=10, state='readonly')
                else:
                    entry = tk.Entry(param_frame, textvariable=value_var, width=10)
                entry.pack(side='right')

                # Add jump button for this parameter
                if param_name in self.param_line_numbers:
                    jump_btn = tk.Button(param_frame, text="→", 
                                       command=lambda ln=self.param_line_numbers[param_name]: self.jump_to_line(ln),
                                       bg='light blue')
                    jump_btn.pack(side='right', padx=2)

                # Add remove button for this parameter
                remove_btn = tk.Button(param_frame, text="✕", 
                                     command=lambda p=param_name, v=value: self.remove_param(p, v, is_z_height),
                                     bg='#ffb3b3', fg='white')
                remove_btn.pack(side='right', padx=2)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh parameters: {str(e)}")

    def remove_param(self, param_name, value, is_z_height=False):
        try:
            # Save current state before deletion
            self.save_state()
            
            # Remove parameter from dictionary
            if is_z_height:
                if value in self.custom_z_params and param_name in self.custom_z_params[value]:
                    del self.custom_z_params[value][param_name]
                    # Keep frame even if empty
                    if value in self.z_param_frames:
                        self.refresh_progress_params(value, is_z_height=True)
            else:
                if value in self.print_progress_params and param_name in self.print_progress_params[value]:
                    del self.print_progress_params[value][param_name]
                    # Keep frame even if empty
                    if value in self.print_progress_frames:
                        self.refresh_progress_params(value, is_z_height=False)

            # Remove from content while preserving PRINT_PROGRESS line
            content_lines = self.original_content.splitlines()
            new_content_lines = []
            skip_next = False
            
            for i, line in enumerate(content_lines):
                if skip_next:
                    skip_next = False
                    continue
                    
                if is_z_height:
                    z_pattern = re.compile(r'LIN.*?Z\s*([-\d.]+)')
                    match = z_pattern.search(line)
                    if match and abs(float(match.group(1)) - value) < 0.0001:
                        new_content_lines.append(line)
                        # Skip only the specific parameter line
                        if i + 1 < len(content_lines) and f"{param_name}=" in content_lines[i + 1]:
                            skip_next = True
                        continue
                else:
                    if f"PRINT_PROGRESS={int(value)}" in line:
                        new_content_lines.append(line)  # Keep PRINT_PROGRESS line
                        # Skip only the specific parameter line
                        if i + 1 < len(content_lines) and f"{param_name}=" in content_lines[i + 1]:
                            skip_next = True
                        continue
                
                # Check for $VEL.CP parameter
                if f"$VEL.CP=" in line and param_name == "$VEL.CP":
                    skip_next = True
                    continue
                
                new_content_lines.append(line)

            # Update original content
            self.original_content = '\n'.join(new_content_lines) + '\n'
            
            # Update preview
            self.update_preview()
            
            # Enable save button
            
            self.save_button.config(state=tk.NORMAL)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove parameter: {str(e)}")

    def jump_to_line(self, line_number):
        try:
            if line_number is None:
                messagebox.showerror("Error", "Invalid line number. Cannot jump.")
                return
            
            print(f"Jumping to line: {line_number}")  # Debugging line
            self.preview_text.see(f"{line_number}.0")
            self.preview_text.tag_remove("highlight", "1.0", "end")
            self.preview_text.tag_configure("highlight", background="yellow")
            self.preview_text.tag_add("highlight", f"{line_number}.0", f"{line_number}.end")
            
            # Update line numbers to ensure they're in sync
            self.update_line_numbers()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to jump to line: {str(e)}")

    def accept_param_change(self, percentage, param_name, value_var):
        try:
            if param_name == 'ACT_DRIVE':
                value = value_var.get().upper()
                if value not in ['TRUE', 'FALSE']:
                    messagebox.showerror("Error", "ACT_DRIVE can only be TRUE or FALSE")
                    return
            elif param_name == 'TOOL_RPM':  # Handle TOOL_RPM as int
                value = int(value_var.get())
            elif param_name == 'LAYER_COOLING':  # Handle LAYER_COOLING as int
                value = int(value_var.get())
            else:
                value = float(value_var.get())
                
            self.custom_z_params[percentage][param_name] = value
            
            # Find the line containing Z_HEIGHT=percentage and update the parameter
            content = self.preview_text.get("1.0", tk.END).splitlines()
            param_updated = False
            
            for i, line in enumerate(content):
                if f"Z_HEIGHT={percentage}" in line:
                    # Find and update parameter line after Z_HEIGHT
                    for j in range(i+1, len(content)):
                        if param_name == 'LAYER_COOLING':
                            if 'LAYER_COOLING=' in content[j]:
                                # Keep any text before LAYER_COOLING
                                prefix = content[j].split('LAYER_COOLING=')[0]
                                content[j] = f"{prefix}LAYER_COOLING={value}"
                                param_updated = True
                                break
                        else:
                            if f"{param_name}=" in content[j]:
                                content[j] = f"{param_name}={value}"
                                param_updated = True
                                break
                    break
            
            if not param_updated:
                messagebox.showerror("Error", "Parameter not found in the correct position")
                return
                
            # Update preview
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert("1.0", "\n".join(content))
            
            # Highlight modified line and jump to it
            self.preview_text.see(f"{j+1}.0")
            self.preview_text.tag_remove("highlight", "1.0", "end")
            self.preview_text.tag_configure("highlight", background="yellow")
            self.preview_text.tag_add("highlight", f"{j+1}.0", f"{j+1}.end")
            
            # Enable save button when parameter is changed
            
            self.save_button.config(state=tk.NORMAL)
            
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number")

    def extract_params_from_file(self):
        if not self.original_content:
            return
            
        try:
            # Clear existing params
            self.params.clear()
            self.param_line_numbers.clear()
            self.param_groups.clear()
            self.trigger_params.clear()
            
            # Split content into lines
            lines = self.original_content.splitlines()            
            # Extract all parameters with line numbers
            for line_num, line in enumerate(lines, 1):
                # Look for trigger parameters first
                trigger_match = re.search(r'TRIGGER WHEN DISTANCE=(\d+\.?\d*)\s*DELAY=(\d+\.?\d*)\s*DO\s+ACT_DRIVE=(TRUE|FALSE)', line)
                if trigger_match:
                    distance = float(trigger_match.group(1))
                    delay = float(trigger_match.group(2))
                    act_drive_value = 'TRUE' if trigger_match.group(3) == 'TRUE' else 'FALSE'
                    
                    # Add ACT_DRIVE to params while preserving trigger
                    key = f"Drive (ACT_DRIVE) (Line {line_num})"
                    self.params[key] = act_drive_value
                    self.param_line_numbers[key] = line_num
                    
                    if 'Drive (ACT_DRIVE)' not in self.param_groups:
                        self.param_groups['Drive (ACT_DRIVE)'] = []
                    self.param_groups['Drive (ACT_DRIVE)'].append(key)
                    
                    self.trigger_params[line_num] = {
                        'distance': distance,
                        'delay': delay,
                        'do': 'ACT_DRIVE',
                        'value': act_drive_value
                    }
                    continue
                
                # Look for other parameters
                if 'TOOL_RPM' in line:
                    value = int(re.search(r'TOOL_RPM\s*=\s*(-?\d+)', line).group(1))  # Changed to int
                    key = f"Tool Speed (TOOL_RPM) (Line {line_num})"
                    self.params[key] = value
                    self.param_line_numbers[key] = line_num
                    
                    # Group parameters
                    if 'Tool Speed (TOOL_RPM)' not in self.param_groups:
                        self.param_groups['Tool Speed (TOOL_RPM)'] = []
                    self.param_groups['Tool Speed (TOOL_RPM)'].append(key)
                    
                elif '$VEL.CP' in line:
                    value = float(re.search(r'\$VEL\.CP\s*=\s*(-?\d+\.?\d*)', line).group(1))
                    key = f"Feed Rate ($VEL.CP) (Line {line_num})"
                    self.params[key] = value
                    self.param_line_numbers[key] = line_num
                    
                    if 'Feed Rate ($VEL.CP)' not in self.param_groups:
                        self.param_groups['Feed Rate ($VEL.CP)'] = []
                    self.param_groups['Feed Rate ($VEL.CP)'].append(key)
                    
                elif 'LAYER_COOLING' in line:
                    # Extract everything before LAYER_COOLING
                    prefix = line.split('LAYER_COOLING')[0]
                    value = int(re.search(r'LAYER_COOLING\s*=\s*(-?\d+)', line).group(1))  # Changed to int
                    key = f"Cooling (LAYER_COOLING) (Line {line_num})"
                    self.params[key] = value
                    self.param_line_numbers[key] = line_num
                    
                    # Store the prefix if it exists
                    if prefix:
                        self.params[f"{key}_prefix"] = prefix
                    
                    if 'Cooling (LAYER_COOLING)' not in self.param_groups:
                        self.param_groups['Cooling (LAYER_COOLING)'] = []
                    self.param_groups['Cooling (LAYER_COOLING)'].append(key)
                    
                elif 'ACT_DRIVE' in line:
                    value = 'TRUE' if re.search(r'ACT_DRIVE\s*=\s*(TRUE|FALSE)', line).group(1) == 'TRUE' else 'FALSE'
                    key = f"Drive (ACT_DRIVE) (Line {line_num})"
                    self.params[key] = value
                    self.param_line_numbers[key] = line_num
                    
                    if 'Drive (ACT_DRIVE)' not in self.param_groups:
                        self.param_groups['Drive (ACT_DRIVE)'] = []
                    self.param_groups['Drive (ACT_DRIVE)'].append(key)
                    
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to extract parameters: {str(e)}")
            return False


    def create_ui(self):
        try:
            # Main container
            main_container = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
            main_container.pack(fill=tk.BOTH, expand=True)

            # Left frame setup with fixed width
            left_frame = tk.Frame(main_container, width=500)
            left_frame.pack_propagate(False)  # Prevent frame from shrinking
            main_container.add(left_frame)

            # Add print progress button
            add_print_progress_btn = tk.Button(left_frame, text="Add Print Progress Parameter", command=self.add_print_progress)
            add_print_progress_btn.pack(pady=5)

            # Add Z height button
            add_z_height_btn = tk.Button(left_frame, text="Add Z Height Parameter", command=self.add_z_height)
            add_z_height_btn.pack(pady=5)

            # Load and Save buttons in the same frame
            button_frame = tk.Frame(left_frame)
            button_frame.pack(pady=10)

            # # Load button
            # self.load_button = tk.Button(button_frame, text="Load File", command=self.load_file)
            # self.load_button.pack(side='left', padx=5)

            # # Save button
            # self.save_button = tk.Button(button_frame, text="Save File", command=self.modify_file, state=tk.DISABLED)
            # self.save_button.pack(side='left', padx=5)

            # Create scrollable frame for parameters
            param_canvas = tk.Canvas(left_frame)
            scrollbar = tk.Scrollbar(left_frame, orient="vertical", command=param_canvas.yview)
            self.param_frame = tk.Frame(param_canvas)
            
            # Bind mouse wheel to scroll
            def _on_mousewheel(event):
                param_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            param_canvas.bind_all("<MouseWheel>", _on_mousewheel)
                
            # Configure scrolling
            self.param_frame.bind(
                "<Configure>",
                lambda e: param_canvas.configure(scrollregion=param_canvas.bbox("all"))
            )
            param_canvas.create_window((0, 0), window=self.param_frame, anchor="nw")
            param_canvas.configure(yscrollcommand=scrollbar.set)
            
            # Pack scrollable frame
            param_canvas.pack(side="left", fill="both", expand=True, pady=10)
            scrollbar.pack(side="right", fill="y")

            self.entries = {}

            # Right paned window for preview with fixed width
            preview_frame = tk.Frame(main_container, width=800)
            preview_frame.pack_propagate(False)  # Prevent frame from shrinking
            main_container.add(preview_frame)

            # Create search frame
            search_frame = tk.Frame(preview_frame)
            search_frame.pack(fill='x', padx=5, pady=5)

            # Search entry and buttons
            self.search_var = tk.StringVar()
            search_entry = tk.Entry(search_frame, textvariable=self.search_var)
            search_entry.pack(side='left', fill='x', expand=True)
            
            # Track current search position and last search term
            self.current_search_pos = "1.0"
            self.last_search_term = ""
            
            def find_text(event=None):
                search_term = self.search_var.get()
                if not search_term:
                    return
                    
                # If new search term, reset position
                if search_term != self.last_search_term:
                    self.current_search_pos = "1.0"
                    self.preview_text.tag_remove("search_highlight", "1.0", "end")
                    self.last_search_term = search_term
                
                # Find next occurrence starting from current position
                pos = self.preview_text.search(search_term, self.current_search_pos, stopindex="end", nocase=True)
                
                if pos:
                    # Calculate end position of match
                    end_pos = f"{pos}+{len(search_term)}c"
                    # Highlight the found text with yellow background and black text
                    self.preview_text.tag_add("search_highlight", pos, end_pos)
                    self.preview_text.tag_configure("search_highlight", background="yellow", foreground="black")
                    # See and select the found text
                    self.preview_text.see(pos)
                    self.preview_text.mark_set("insert", pos)
                    self.preview_text.focus_set()
                    # Update position for next search
                    self.current_search_pos = end_pos
                else:
                    # If no match found, show message and reset position
                    messagebox.showinfo("Find", "No more matches found")
                    self.current_search_pos = "1.0"
                
                # Keep focus on the search entry
                search_entry.focus_set()
            
            find_button = tk.Button(search_frame, text="Find", command=find_text)
            find_button.pack(side='right', padx=10)
            
            # Bind the Enter key to the find_text function
            search_entry.bind('<Return>', find_text)
            
            # Create text widget with line numbers
            self.preview_text = Text(preview_frame, wrap="none")
            y_scrollbar = Scrollbar(preview_frame, orient='vertical', command=self.preview_text.yview)
            x_scrollbar = Scrollbar(preview_frame, orient='horizontal', command=self.preview_text.xview)
            
            # Line numbers text widget
            self.line_numbers = Text(preview_frame, width=4, padx=3, takefocus=0, border=0,
                                background='lightgray', state='disabled')
            self.line_numbers.pack(side='left', fill='y')
            
            # Configure text widget
            self.preview_text.pack(side='left', fill='both', expand=True)
            y_scrollbar.pack(side='right', fill='y')
            x_scrollbar.pack(side='bottom', fill='x')
            self.preview_text.configure(yscrollcommand=y_scrollbar.set)
            self.preview_text.configure(xscrollcommand=x_scrollbar.set)
            
            # Bind scrolling events
            self.preview_text.bind('<Key>', lambda e: self.update_line_numbers())
            self.preview_text.bind('<MouseWheel>', lambda e: self.update_line_numbers())
        
            # Configure text tags for parameter highlighting
            self.preview_text.tag_configure("tool_speed", background=self.param_colors['TOOL_RPM'])
            self.preview_text.tag_configure("feed_rate", background=self.param_colors['$VEL.CP'])
            self.preview_text.tag_configure("cooling", background=self.param_colors['LAYER_COOLING'])
            self.preview_text.tag_configure("drive", background=self.param_colors['ACT_DRIVE'])
            self.preview_text.tag_configure("search_highlight", background="yellow")

            # Configure header colors to match parameters
            for header_label in self.header_labels.values():
                param_type = header_label.cget("text").split(" (")[0][2:]  # Remove arrow and get param type
                if "Tool Speed" in param_type:
                    header_label.configure(bg=self.param_colors['TOOL_RPM'])
                elif "Feed Rate" in param_type:
                    header_label.configure(bg=self.param_colors['$VEL.CP'])
                elif "Cooling" in param_type:
                    header_label.configure(bg=self.param_colors['LAYER_COOLING'])
                elif "Drive" in param_type:
                    header_label.configure(bg=self.param_colors['ACT_DRIVE'])
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create UI: {str(e)}")

    def create_param_entries(self):
        try:
            # Store current frame states before clearing
            expanded_sections = {}
            for param_type, content_frame in self.content_frames.items():
                if content_frame.winfo_viewable():
                    expanded_sections[param_type] = True

            # Clear existing entries
            for widget in self.param_frame.winfo_children():
                widget.destroy()
            self.entries.clear()
            self.content_frames.clear()
            self.header_labels.clear()

            if not self.params:
                return
            
            # Create parent header frame
            parent_header_frame = tk.Frame(self.param_frame, relief=tk.RAISED, borderwidth=1)
            parent_header_frame.pack(fill='x')
            
            # Create buttons frame for parent header
            parent_buttons_frame = tk.Frame(parent_header_frame)
            parent_buttons_frame.pack(fill='x', padx=5, pady=2)
            
            # Parent arrow button
            parent_arrow = tk.Label(parent_buttons_frame, text="▶", cursor="hand2", 
                                  font=("Arial", 8, "bold"), width=2,
                                  anchor='w')
            parent_arrow.pack(side='left')
            
            # Parent header label
            parent_label = tk.Label(parent_buttons_frame, text="Initial parameters",
                                  font=("Arial", 8, "bold"), 
                                  anchor='w')
            parent_label.pack(side='left', fill='x', expand=True)
            
            # Create parent content frame
            parent_content_frame = tk.Frame(self.param_frame)
            # Don't pack initially to start closed
            
            def toggle_parent(event=None):
                if parent_content_frame.winfo_viewable():
                    parent_content_frame.pack_forget()
                    parent_arrow.config(text="▶")
                else:
                    parent_content_frame.pack(fill='x')
                    parent_arrow.config(text="▼")
            
            parent_arrow.bind('<Button-1>', toggle_parent)
            parent_label.bind('<Button-1>', toggle_parent)

            for param_type, param_keys in self.param_groups.items():
                # Container frame for parameter type
                container = tk.Frame(parent_content_frame)
                container.pack(fill='x', padx=5, pady=2)
                
                # Header frame
                header_frame = tk.Frame(container, relief=tk.RAISED, borderwidth=1)
                header_frame.pack(fill='x')
                
                # Buttons frame
                buttons_frame = tk.Frame(header_frame)
                buttons_frame.pack(fill='x', padx=5, pady=2)
                
                # Arrow button
                arrow_btn = tk.Label(buttons_frame, text="▶", cursor="hand2",
                                   font=("Arial", 10, "bold"),
                                   width=2,
                                   anchor='w')
                arrow_btn.pack(side='left')
                
                # Header label
                header_label = tk.Label(buttons_frame, 
                                      text=f"{param_type} ({len(param_keys)} occurrences)",
                                      font=("Arial", 10, "bold"),
                                      anchor='w')
                header_label.pack(side='left', fill='x', expand=True)
                self.header_labels[param_type] = header_label
                
                # Content frame
                content_frame = tk.Frame(container)
                content_frame.pack(fill='x')
                self.content_frames[param_type] = content_frame
                
                def make_toggle_function(content_frame, arrow_btn, header_label, param_type):
                    def toggle(event=None):
                        if content_frame.winfo_viewable():
                            content_frame.pack_forget()
                            arrow_btn.config(text="▶")
                        else:
                            content_frame.pack(fill='x', padx=20)
                            arrow_btn.config(text="▼")
                    return toggle
                
                toggle_func = make_toggle_function(content_frame, arrow_btn, header_label, param_type)
                arrow_btn.bind('<Button-1>', toggle_func)
                header_label.bind('<Button-1>', toggle_func)
                
                # Create entries for parameters
                for param_key in param_keys:
                    row = tk.Frame(content_frame)
                    row.pack(fill='x', padx=5, pady=2)
                    
                    # Extract just the variable name and line number
                    param_parts = param_key.split(' (')
                    var_name = param_parts[1].split(')')[0]  # Gets the variable name (e.g., $VEL.CP)
                    line_num = param_parts[-1].split(')')[0]  # Gets the line number
                    simplified_label = f"{var_name} ({line_num})"
                    
                    tk.Label(row, text=simplified_label).pack(side='left')
                    
                    value_var = tk.StringVar(value=str(self.params[param_key]))
                    if "Drive" in param_key:
                        entry = ttk.Combobox(row, textvariable=value_var, values=['TRUE', 'FALSE'],
                                            width=7)
                    else:
                        entry = tk.Entry(row, width=10, textvariable=value_var)
                    entry.pack(side='right')
                    
                    self.entries[param_key] = entry
                    
                    # Accept button
                    accept_btn = tk.Button(row, text="✓", bg='LIGHT GREEN', fg='white',
                                         command=lambda k=param_key, v=value_var, ln=self.param_line_numbers[param_key]:
                                         self.update_line_and_preview(k, v, ln))
                    accept_btn.pack(side='right', padx=2)
                    
                    # Delete button
                    delete_btn = tk.Button(row, text="✕", bg='#ffb3b3', fg='white',
                                         command=lambda k=param_key, ln=self.param_line_numbers[param_key]:
                                         self.delete_parameter(k, ln))
                    delete_btn.pack(side='right', padx=2)
                    
                    # Jump button
                    if param_key in self.param_line_numbers:
                        jump_btn = tk.Button(row, text="→",
                                           command=lambda ln=self.param_line_numbers[param_key]: self.jump_to_line(ln),
                                           bg='light blue')
                        jump_btn.pack(side='right', padx=5)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create parameter entries: {str(e)}")

    def update_line_and_preview(self, key, value_var, line_number):
        try:
            # Save current state before update
            self.save_state()
            
            # Validate and get the value based on parameter type
            if "Feed Rate" in key:  # For $VEL.CP
                value = float(value_var.get())
                if value > 2:
                    messagebox.showerror("Error", "Maximum value for $VEL.CP is 2")
                    return
                if value > 0.5:
                    if not messagebox.askyesno("Warning", 
                        "Values above 0.5 for $VEL.CP could be dangerous.\n\n" +
                        "Do you wish to continue with this value?"):
                        return
            elif "Tool Speed" in key:  # For TOOL_RPM
                value = float(value_var.get())
                if value > 139.8:
                    messagebox.showerror("Error", "Maximum value for TOOL_RPM is 139.8")
                    return
            elif "Cooling" in key:  # For LAYER_COOLING
                value = int(value_var.get())
                if value > 200:
                    messagebox.showerror("Error", "Maximum value for LAYER_COOLING is 200")
                    return
            else:  # For other parameters
                value = value_var.get()
            
            self.params[key] = value
            
            # Get the parameter type from the key
            param_type = key.split(' (')[0]
            
            # Update the specific line in the original content
            content = self.original_content.splitlines()
            line_idx = line_number - 1
            
            if "Tool Speed" in param_type:
                # Check if line contains "TRIGGER WHEN" string
                if "TRIGGER WHEN" in content[line_idx]:
                    aux = re.match("^(.+?)TOOL_RPM=\\d*\\.?\\d*", content[line_idx]).group(1)
                    content[line_idx] = f"{aux}TRIGGER WHEN DISTANCE=0 DELAY=0 DO TOOL_RPM={value}"
                else:
                    content[line_idx] = f"TRIGGER WHEN DISTANCE=0 DELAY=0 DO TOOL_RPM={value}"
                
            elif "Feed Rate" in param_type:
                content[line_idx] = f"$VEL.CP={value}"
            elif "Cooling" in param_type:
                # Check if line contains "TRIGGER WHEN" string
                if "TRIGGER WHEN" in content[line_idx]:
                    aux = re.match("^(.+?)LAYER_COOLING=\\d*\\.?\\d*", content[line_idx]).group(1)
                    content[line_idx] = f"{aux}LAYER_COOLING={value}"
                else:
                    content[line_idx] = f"LAYER_COOLING={value}"
            elif "Drive" in param_type:
                # Check if line contains "TRIGGER WHEN" string
                if "TRIGGER WHEN" in content[line_idx]:
                    aux = re.match("^(.+?)ACT_DRIVE=\\d*\\.?\\d*", content[line_idx]).group(1)
                    content[line_idx] = f"{aux}ACT_DRIVE={value}"
                else:
                    content[line_idx] = f"ACT_DRIVE={value}"
                
            # Update original content
            self.original_content = "\n".join(content) + "\n"
            
            # Update preview using update_preview to maintain highlighting
            self.update_preview()
            
            # Highlight the modified line and jump to it
            self.preview_text.see(f"{line_number}.0")
            self.preview_text.tag_add("highlight", f"{line_number}.0", f"{line_number}.end")
            
            # Enable save button when line is updated
            self.save_button.config(state=tk.NORMAL)
            
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number")

    def update_line_numbers(self):
        try:
            if not self.preview_text:
                return
                
            self.line_numbers.config(state='normal')
            self.line_numbers.delete('1.0', tk.END)
            
            # Get visible lines
            first_line = int(self.preview_text.index("@0,0").split('.')[0])
            last_line = int(self.preview_text.index("@0,%d" % self.preview_text.winfo_height()).split('.')[0])
            
            # Add line numbers for visible lines
            for line_num in range(first_line, last_line + 1):
                self.line_numbers.insert(tk.END, f"{line_num}\n")
                
            self.line_numbers.config(state='disabled')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update line numbers: {str(e)}")

    def update_preview(self):
        try:
            if not self.preview_text or not self.original_content:
                return
                
            self.preview_text.delete(1.0, tk.END)
            modified_lines = self.calculate_new_params()
            
            for line in modified_lines:
                if 'TOOL_RPM=' in line:
                    self.preview_text.insert(tk.END, line, "tool_speed")
                elif '$VEL.CP=' in line:
                    self.preview_text.insert(tk.END, line, "feed_rate")
                elif 'LAYER_COOLING=' in line:
                    self.preview_text.insert(tk.END, line, "cooling")
                elif 'ACT_DRIVE=' in line:
                    self.preview_text.insert(tk.END, line, "drive")
                else:
                    self.preview_text.insert(tk.END, line)
            
            self.update_line_numbers()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update preview: {str(e)}")

    def calculate_new_params(self):
        try:
            if not self.original_content:
                return []
                
            lines = self.original_content.splitlines(True)
            modified_lines = []
            
            # Compile regex patterns
            z_pattern = re.compile(r'LIN\s+X\s*[-\d.]+\s+Y\s*[-\d.]+\s+Z\s*([-\d.]+)')
            
            for line in lines:
                z_match = z_pattern.search(line)
                if z_match:
                    z_height = float(z_match.group(1))
                    
                    # Add original line
                    modified_lines.append(line)
                    
                    # Add custom parameters if they exist for this Z height
                    if z_height in self.custom_z_params:
                        for param_name, param_value in self.custom_z_params[z_height].items():
                            modified_lines.append(f'{param_name}={param_value}\n')
                else:
                    modified_lines.append(line)
                    
            return modified_lines
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate new parameters: {str(e)}")
            return []

    def modify_file(self):
        try:
            if not self.input_file:
                return
                
            for key, entry in self.entries.items():
                try:
                    # Special handling for ACT_DRIVE
                    if "Drive" in key:
                        value = entry.get()
                        if value not in ['TRUE', 'FALSE']:
                            tk.messagebox.showerror("Error", f"Invalid value for {key}. Must be TRUE or FALSE")
                            return
                        self.params[key] = value
                    else:
                        # Convert other parameters to float
                        self.params[key] = float(entry.get())
                except ValueError:
                    tk.messagebox.showerror("Error", f"Invalid value for {key}")
                    return
            
            # Get input file name without extension
            input_name = os.path.splitext(os.path.basename(self.input_file))[0]
            default_output = f"{input_name}_modified.src"
            
            # Open file save dialog
            output_file = filedialog.asksaveasfilename(
                defaultextension=".src",
                initialfile=default_output,
                filetypes=[("SRC files", "*.src"), ("All files", "*.*")]
            )
            
            if not output_file:  # User cancelled
                return
                
            # Create changelog name based on selected output file
            changelog_base = os.path.splitext(output_file)[0]
            default_changelog = f"{changelog_base}_changelog.txt"
                    
            modified_lines = self.calculate_new_params()
            
            # Create changelog entry
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            changelog_entry = f"\n=== {timestamp} ===\n"
            changelog_entry += f"Modified file: {self.input_file}\n"
            changelog_entry += f"Output file: {output_file}\n"
            changelog_entry += "Parameter changes:\n"
            
            # Add parameter changes to changelog
            for key, value in self.params.items():
                changelog_entry += f"- {key}: {value}\n"
            
            # Add custom Z height parameters to changelog
            if self.custom_z_params:
                changelog_entry += "\nCustom Z height parameters:\n"
                for z, params in self.custom_z_params.items():
                    changelog_entry += f"Z = {z}:\n"
                    for param_type, value in params.items():
                        changelog_entry += f"  - {param_type}: {value}\n"
            
            # Write modified file
            with open(output_file, 'w', encoding='utf-8') as file:
                file.writelines(modified_lines)
                
            # Append to changelog
            with open(default_changelog, 'a', encoding='utf-8') as log:
                log.write(changelog_entry)
            
            # Update menu item state
            self.file_menu.entryconfig("Save", state='disabled')
            
            tk.messagebox.showinfo("Success", f"File saved as {output_file}\nChangelog updated in {default_changelog}")
                
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to save file: {str(e)}")

    def delete_parameter(self, key, line_number):
        try:
            # Save current state before deletion
            self.save_state()
            
            # Get the line containing the parameter we want to delete
            content_lines = self.original_content.splitlines()
            param_line = content_lines[line_number - 1]
            
            # Identify parameter type
            param_type = None
            if 'TOOL_RPM=' in param_line:
                param_type = 'TOOL_RPM'
            elif '$VEL.CP=' in param_line:
                param_type = '$VEL.CP'
            elif 'LAYER_COOLING=' in param_line:
                param_type = 'LAYER_COOLING'
            elif 'ACT_DRIVE=' in param_line:
                param_type = 'ACT_DRIVE'

            # Search backwards for position marker
            for i in range(line_number - 2, -1, -1):
                current_line = content_lines[i]
                
                # Found Z height marker
                z_match = re.search(r'LIN.*?Z\s*([-\d.]+)', current_line)
                if z_match:
                    z_value = float(z_match.group(1))
                    if z_value in self.custom_z_params and param_type in self.custom_z_params[z_value]:
                        del self.custom_z_params[z_value][param_type]
                        if not self.custom_z_params[z_value]:
                            del self.custom_z_params[z_value]
                    break
                    
                # Found print progress marker
                progress_match = re.search(r'PRINT_PROGRESS=(\d+)', current_line)
                if progress_match:
                    progress_value = int(progress_match.group(1))
                    if progress_value in self.print_progress_params and param_type in self.print_progress_params[progress_value]:
                        del self.print_progress_params[progress_value][param_type]
                        if not self.print_progress_params[progress_value]:
                            del self.print_progress_params[progress_value]
                    break

            # Remove the line from content
            del content_lines[line_number - 1]
            
            # Remove from tracking dictionaries
            if key in self.params:
                del self.params[key]
            if key in self.param_line_numbers:
                del self.param_line_numbers[key]

            # Remove from param_groups
            for group_name, group_keys in self.param_groups.items():
                if key in group_keys:
                    group_keys.remove(key)
                    if group_name in self.header_labels:
                        header_label = self.header_labels[group_name]
                        header_label.config(text=f"{group_name} ({len(group_keys)} occurrences)")
                    break

            # Update line numbers
            for param_key, line_num in list(self.param_line_numbers.items()):
                if line_num > line_number:
                    self.param_line_numbers[param_key] = line_num - 1
                    if param_key in self.params:
                        value = self.params[param_key]
                        new_key = param_key.replace(f"Line {line_num}", f"Line {line_num - 1}")
                        del self.params[param_key]
                        self.params[new_key] = value
                        for group_keys in self.param_groups.values():
                            if param_key in group_keys:
                                group_keys.remove(param_key)
                                group_keys.append(new_key)

            # Update content and UI
            self.original_content = '\n'.join(content_lines) + '\n'
            self.update_preview()
            self.extract_params_from_file()
            self.create_param_entries()
            
            # Enable save button
            self.save_button.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete parameter: {str(e)}")

    def save_state(self):
        """Save current state for undo"""
        state = {
            'params': self.params.copy(),
            'param_line_numbers': self.param_line_numbers.copy(), 
            'param_groups': {k: v[:] for k, v in self.param_groups.items()},
            'original_content': self.original_content,
            'custom_z_params': {k: v.copy() for k, v in self.custom_z_params.items()},
            'print_progress_params': {k: v.copy() for k, v in self.print_progress_params.items()},
            'z_param_frames': self.z_param_frames.copy(),
            'print_progress_frames': self.print_progress_frames.copy(),
            'header_labels': {k: v.cget("text") for k, v in self.header_labels.items()}  # Save header labels
        }
        self.undo_state = state
        self.undo_button.config(state=tk.NORMAL)
        self.redo_state = None  # Clear redo state when new state is saved
        self.redo_button.config(state=tk.DISABLED)

    def undo_last_action(self):
        try:
            if not self.undo_state:
                self.undo_button.config(state=tk.DISABLED)
                return
            
            # Save current state to redo
            current_state = {
                'params': self.params.copy(),
                'param_line_numbers': self.param_line_numbers.copy(),
                'param_groups': {k: v[:] for k, v in self.param_groups.items()},
                'original_content': self.original_content,
                'custom_z_params': {k: v.copy() for k, v in self.custom_z_params.items()},
                'print_progress_params': {k: v.copy() for k, v in self.print_progress_params.items()},
                'z_param_frames': self.z_param_frames.copy(),
                'print_progress_frames': self.print_progress_frames.copy(),
                'header_labels': {k: v.cget("text") for k, v in self.header_labels.items()}
            }
            self.redo_state = current_state
            
            # Restore undo state
            state = self.undo_state
            self.params = state['params']
            self.param_line_numbers = state['param_line_numbers']
            self.param_groups = state['param_groups']
            self.original_content = state['original_content']
            self.custom_z_params = state['custom_z_params']
            self.print_progress_params = state['print_progress_params']
            self.z_param_frames = state['z_param_frames']
            self.print_progress_frames = state['print_progress_frames']
            
            # Restore header labels
            for k, text in state['header_labels'].items():
                if k in self.header_labels:
                    self.header_labels[k].config(text=text)
            
            # Update UI
            self.update_preview()
            self.create_param_entries()
            
            # Update button states
            self.undo_state = None
            self.undo_button.config(state=tk.DISABLED)
            self.redo_button.config(state=tk.NORMAL)
            
            # Enable save button
            self.save_button.config(state=tk.NORMAL)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to undo: {str(e)}")

    def redo_last_action(self):
        try:
            if not self.redo_state:
                self.redo_button.config(state=tk.DISABLED)
                return
                
            # Save current state to undo
            current_state = {
                'params': self.params.copy(),
                'param_line_numbers': self.param_line_numbers.copy(),
                'param_groups': {k: v[:] for k, v in self.param_groups.items()},
                'original_content': self.original_content,
                'custom_z_params': {k: v.copy() for k, v in self.custom_z_params.items()},
                'print_progress_params': {k: v.copy() for k, v in self.print_progress_params.items()},
                'z_param_frames': self.z_param_frames.copy(),
                'print_progress_frames': self.print_progress_frames.copy(),
                'header_labels': {k: v.cget("text") for k, v in self.header_labels.items()}
            }
            self.undo_state = current_state
            
            # Restore redo state
            state = self.redo_state
            self.params = state['params']
            self.param_line_numbers = state['param_line_numbers']
            self.param_groups = state['param_groups']
            self.original_content = state['original_content']
            self.custom_z_params = state['custom_z_params']
            self.print_progress_params = state['print_progress_params']
            self.z_param_frames = state['z_param_frames']
            self.print_progress_frames = state['print_progress_frames']
            
            # Restore header labels
            for k, text in state['header_labels'].items():
                if k in self.header_labels:
                    self.header_labels[k].config(text=text)
            
            # Update UI
            self.update_preview()
            self.create_param_entries()
            
            # Update button states
            self.redo_state = None
            self.redo_button.config(state=tk.DISABLED)
            self.undo_button.config(state=tk.NORMAL)
            
            # Enable save button
            self.save_button.config(state=tk.NORMAL)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to redo: {str(e)}")

    def create_undo_redo_buttons(self):
        """Create undo and redo buttons with custom styling"""
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5)
        
        # Undo button with counterclockwise arrow (↺)
        self.undo_button = tk.Button(button_frame, text="↺ Undo", 
                                   command=self.undo_last_action,
                                   bg='#FFE4B5',  # Light orange
                                   activebackground='#FFDEAD', # Slightly darker orange on hover
                                   relief='raised',
                                   state=tk.DISABLED)
        self.undo_button.pack(side=tk.LEFT, padx=5)
        # Redo button with clockwise arrow (↻)
        self.redo_button = tk.Button(button_frame, text="↻ Redo",
                                   command=self.redo_last_action,
                                   bg='#D8BFD8',  # Using a different light purple color (Thistle)
                                   activebackground='#E6E6FA',  # Original light purple on hover
                                   relief='raised',
                                   state=tk.DISABLED)
        self.redo_button.pack(side=tk.LEFT, padx=5)

    def jump_to_z_height(self, z_height):
        try:
            content = self.preview_text.get("1.0", tk.END).splitlines()
            z_pattern = re.compile(r'LIN\s+X\s*[-\d.]+\s+Y\s*[-\d.]+\s+Z\s*([-\d.]+)')
            
            for i, line in enumerate(content, 1):
                match = z_pattern.search(line)
                if match and abs(float(match.group(1)) - z_height) < 0.0001:  # Use small epsilon for float comparison
                    self.jump_to_line(i)
                    break
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to jump to Z height: {str(e)}")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = SRCModifierApp(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start application: {str(e)}")
