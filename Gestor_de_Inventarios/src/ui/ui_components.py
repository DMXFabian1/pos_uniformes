import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox
from src.core.utils.tooltips import ToolTip
import json
import os
from src.core.utils.logging_config import setup_logging

logger = setup_logging()

# Lista global para rastrear todas las instancias de CheckComboBox
check_combobox_instances = []

def create_labeled_entry(parent, label_text, placeholder_text="", width=200, row=0, column=0, sticky="w", 
                         omit_var=None, toggle_callback=None, tooltip=None, label_width=None, label_sticky="e", 
                         input_sticky="w", padx=5, pady=5):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.grid(row=row, column=column, sticky=sticky, padx=padx, pady=pady)
    
    frame.grid_columnconfigure(0, weight=0)
    frame.grid_columnconfigure(1, weight=1)
    frame.grid_columnconfigure(2, weight=0)

    label = ctk.CTkLabel(frame, text=label_text, font=("Helvetica", 12), width=label_width or 100, anchor="e")
    label.grid(row=0, column=0, padx=(0, 5), sticky=label_sticky)

    entry = ctk.CTkEntry(frame, placeholder_text=placeholder_text, width=width)
    entry.grid(row=0, column=1, sticky=input_sticky)

    if omit_var is not None and toggle_callback is not None:
        checkbox = ctk.CTkCheckBox(frame, text="Omitir", variable=omit_var, command=lambda: toggle_callback(omit_var, entry))
        checkbox.grid(row=0, column=2, padx=(10, 0), sticky="w")

    if tooltip:
        ToolTip(label, tooltip)
        ToolTip(entry, tooltip)

    return {"entry": entry, "frame": frame}

def create_labeled_combobox(parent, label_text, values, width=200, row=0, column=0, sticky="w", 
                            omit_var=None, toggle_callback=None, tooltip=None, label_width=None, 
                            label_sticky="e", input_sticky="w", padx=5, pady=5):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.grid(row=row, column=column, sticky=sticky, padx=padx, pady=pady)
    
    frame.grid_columnconfigure(0, weight=0)
    frame.grid_columnconfigure(1, weight=1)
    frame.grid_columnconfigure(2, weight=0)

    label = ctk.CTkLabel(frame, text=label_text, font=("Helvetica", 12), width=label_width or 100, anchor="e")
    label.grid(row=0, column=0, padx=(0, 5), sticky=label_sticky)

    combobox = ctk.CTkComboBox(frame, values=values, width=width)
    combobox.grid(row=0, column=1, sticky=input_sticky)

    if omit_var is not None and toggle_callback is not None:
        checkbox = ctk.CTkCheckBox(frame, text="Omitir", variable=omit_var, command=lambda: toggle_callback(omit_var, combobox))
        checkbox.grid(row=0, column=2, padx=(10, 0), sticky="w")

    if tooltip:
        ToolTip(label, tooltip)
        ToolTip(combobox, tooltip)

    return {"combobox": combobox, "frame": frame}

def create_filter_combobox(parent, label_text, values, width=150, command=None):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(side="left", padx=5, pady=2)
    label = ctk.CTkLabel(frame, text=label_text, font=("Helvetica", 10))
    label.pack(side="left", padx=(0, 5))
    combobox = ctk.CTkComboBox(frame, values=[""] + values, width=width, command=command)
    combobox.pack(side="left")
    return combobox

def create_treeview(parent, columns, visible_columns, height=20):
    tree = ttk.Treeview(parent, columns=["checkbox"] + visible_columns, show="headings", height=height)
    tree.heading("checkbox", text="")
    for col in visible_columns:
        tree.heading(col, text=col.capitalize(), command=lambda c=col: parent.sort_by_column(c))
        tree.column(col, width=100, anchor="center")
    tree.column("checkbox", width=30, anchor="center")
    tree.tag_configure("evenrow", background="#F0F0F0")
    tree.tag_configure("oddrow", background="#FFFFFF")
    return tree

def add_size_to_config(new_size, config_path="config.json"):
    """Añade una nueva talla numérica al archivo config.json y devuelve la lista actualizada de tallas."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        try:
            size_num = int(new_size)
            if size_num <= 0:
                raise ValueError("La talla debe ser un número positivo.")
        except ValueError:
            messagebox.showerror("Error", "La talla debe ser un número entero válido.")
            return None
        
        new_size = str(size_num)
        
        current_sizes = config["TALLAS"]
        if new_size in current_sizes:
            messagebox.showwarning("Advertencia", f"La talla {new_size} ya existe.")
            return None
        
        numeric_sizes = [s for s in current_sizes if s.isdigit()]
        non_numeric_sizes = [s for s in current_sizes if not s.isdigit()]
        numeric_sizes.append(new_size)
        numeric_sizes = sorted(numeric_sizes, key=int)
        
        config["TALLAS"] = numeric_sizes + non_numeric_sizes
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return config["TALLAS"]
    
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo añadir la talla: {str(e)}")
        return None

def create_field(parent, label_text, values, row, omit_var, toggle_command, add_command=None, default_value="", 
                 update_callback=None, allow_add_size=False, config_path="config.json", add_value_callback=None):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=3, pady=3)

    ctk.CTkLabel(frame, text=label_text, font=("Helvetica", 12, "bold"), text_color="#1A2E5A", width=120).grid(row=0, column=0, sticky="e", padx=3, pady=3)

    field_frame = ctk.CTkFrame(frame, fg_color="transparent")
    field_frame.grid(row=0, column=1, sticky="w")

    combo = ctk.CTkComboBox(field_frame, values=values, width=300, border_color="#A3BFFA", state="normal", text_color="#4B5EAA")
    combo.set(default_value if default_value else "")
    combo.grid(row=0, column=0, sticky="w", padx=3, pady=3)

    original_values = values.copy()
    filtered_values = original_values.copy()
    current_index = -1

    def on_key_release(event):
        nonlocal filtered_values, current_index
        typed_text = combo.get().strip().lower()
        if not typed_text:
            filtered_values = original_values.copy()
            combo.configure(values=filtered_values)
            current_index = -1
            return
        filtered_values = [item for item in original_values if item.lower().startswith(typed_text)]
        combo.configure(values=filtered_values if filtered_values else original_values)
        current_index = -1

    def on_arrow_key(event):
        nonlocal current_index, filtered_values
        if not filtered_values:
            return
        if current_index == -1:
            if event.keysym == "Down":
                current_index = 0
            elif event.keysym == "Up":
                current_index = len(filtered_values) - 1
        else:
            if event.keysym == "Down":
                current_index = (current_index + 1) % len(filtered_values)
            elif event.keysym == "Up":
                current_index = (current_index - 1) % len(filtered_values)

        if current_index >= 0 and current_index < len(filtered_values):
            combo.set(filtered_values[current_index])

    def confirm_selection(event=None):
        nonlocal current_index
        typed_text = combo.get().strip().lower()
        if not typed_text:
            return
        if current_index >= 0 and current_index < len(filtered_values):
            combo.set(filtered_values[current_index])
        else:
            for item in original_values:
                if item.lower().startswith(typed_text):
                    combo.set(item)
                    break
        if update_callback:
            update_callback()
        current_index = -1

    combo.bind("<KeyRelease>", on_key_release)
    combo.bind("<Up>", on_arrow_key)
    combo.bind("<Down>", on_arrow_key)
    combo.bind("<Return>", confirm_selection)
    combo.bind("<<ComboboxSelected>>", lambda event: [update_callback() if update_callback else None])

    checkbox = ctk.CTkCheckBox(field_frame, text=f"Omitir {label_text.strip(':')}", variable=omit_var, 
                               command=lambda: toggle_command(omit_var, combo), fg_color="#4A90E2", text_color="#4B5EAA")
    checkbox.grid(row=1, column=0, sticky="w", padx=3, pady=3)

    add_button = None
    if add_command:
        add_button = ctk.CTkButton(field_frame, text="+", command=add_command, width=30, 
                                   fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8)
        add_button.grid(row=0, column=1, padx=5)

    new_size_entry = None
    add_size_button = None
    if allow_add_size and label_text.lower().startswith("talla"):
        new_size_frame = ctk.CTkFrame(field_frame, fg_color="transparent")
        new_size_frame.grid(row=2, column=0, sticky="w", pady=3)
        
        new_size_entry = ctk.CTkEntry(new_size_frame, placeholder_text="Nueva talla numérica", width=150)
        new_size_entry.pack(side="left", padx=3)
        
        def add_new_size():
            if validate_numeric_entry(new_size_entry, "Nueva talla", is_int=True):
                new_size = new_size_entry.get().strip()
                updated_sizes = add_size_to_config(new_size, config_path)
                if updated_sizes:
                    combo.configure(values=updated_sizes)
                    nonlocal original_values, filtered_values
                    original_values = updated_sizes.copy()
                    filtered_values = original_values.copy()
                    new_size_entry.delete(0, tk.END)
                    messagebox.showinfo("Éxito", f"Talla {new_size} añadida correctamente.")
        
        add_size_button = ctk.CTkButton(new_size_frame, text="Añadir", command=add_new_size, width=80,
                                        fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8)
        add_size_button.pack(side="left", padx=3)

    new_value_entry = None
    add_value_button = None
    if add_value_callback:
        new_value_frame = ctk.CTkFrame(field_frame, fg_color="transparent")
        new_value_frame.grid(row=2, column=0, sticky="w", pady=3)
        
        new_value_entry = ctk.CTkEntry(new_value_frame, placeholder_text=f"Nueva {label_text.lower().strip(':')}", width=150)
        new_value_entry.pack(side="left", padx=3)
        
        add_value_button = ctk.CTkButton(new_value_frame, text="Añadir", command=lambda: add_value_callback(new_value_entry, combo), 
                                         width=80, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8)
        add_value_button.pack(side="left", padx=3)

    return {
        "combo": combo,
        "checkbox": checkbox,
        "add_button": add_button,
        "new_size_entry": new_size_entry,
        "add_size_button": add_size_button,
        "new_value_entry": new_value_entry,
        "add_value_button": add_value_button
    }

def validate_numeric_entry(entry, field_name, is_int=False):
    value = entry.get().strip()
    try:
        if value:
            if field_name in ["Inventario", "Ventas"]:
                num = int(value)
                if num < 0:
                    entry.configure(fg_color="#FFE6E6", border_color="#FF5555")
                    messagebox.showwarning("Advertencia", f"El campo {field_name} no puede ser negativo.")
                    return False
            else:
                num = int(value) if is_int else float(value)
                if num < 0:
                    entry.configure(fg_color="#FFE6E6", border_color="#FF5555")
                    messagebox.showwarning("Advertencia", f"El campo {field_name} no puede ser negativo.")
                    return False
        entry.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
        return True
    except ValueError:
        entry.configure(fg_color="#FFE6E6", border_color="#FF5555")
        if field_name in ["Inventario", "Ventas"]:
            messagebox.showwarning("Advertencia", f"El campo {field_name} debe ser un número entero válido (sin decimales).")
        else:
            messagebox.showwarning("Advertencia", f"El campo {field_name} debe ser un {'entero' if is_int else 'número'} válido.")
        return False

def validate_string(entry, field_name, allow_empty=False):
    value = entry.get().strip()
    if not value and not allow_empty:
        entry.configure(fg_color="#FFE6E6", border_color="#FF5555")
        return False
    entry.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
    return True

def create_check_combobox(parent, label_text, values, width=100, command=None, row=0, column=0, sticky="w", padx=4, pady=3, check_column=None, 
                         font=("Helvetica", 10, "bold"), label_color="#1A2E5A", bg_color="#E6F0FA"):
    """
    Crea un CheckComboBox para selección múltiple con casillas de verificación, con la etiqueta encima.

    Args:
        parent (tk.Widget): Widget padre.
        label_text (str): Texto de la etiqueta.
        values (list): Lista de valores disponibles.
        width (int): Ancho del componente.
        command (callable): Función a llamar cuando cambian las selecciones.
        row (int): Fila en la cuadrícula (no usado con pack).
        column (int): Columna en la cuadrícula (no usado con pack).
        sticky (str): Alineación (no usado con pack).
        padx (int): Padding horizontal.
        pady (int): Padding vertical.
        check_column (str, optional): Nombre de la columna asociada al combobox.
        font (tuple): Fuente de la etiqueta.
        label_color (str): Color del texto de la etiqueta.
        bg_color (str): Color de fondo del frame.

    Returns:
        CheckComboBox: Instancia del componente.
    """
    frame = ctk.CTkFrame(parent, fg_color=bg_color, corner_radius=8)
    frame.pack(side="left", padx=padx, pady=pady)
    
    label = ctk.CTkLabel(frame, text=label_text, font=font, text_color=label_color)
    label.pack(side="top", pady=(2, 2))
    
    check_combobox = CheckComboBox(frame, values=values, width=width, command=command, column=check_column)
    check_combobox.pack(side="top")
    
    logger.debug(f"CheckComboBox creado con label={label_text}, column={check_column}")
    return check_combobox

class CheckComboBox(ctk.CTkFrame):
    """
    Componente personalizado que simula un ComboBox con selección múltiple mediante casillas de verificación.
    Usa un CTkToplevel para el menú desplegable con diseño mejorado.
    """
    def __init__(self, parent, values, width=100, command=None, column=None):
        super().__init__(parent, fg_color="transparent")
        self.values = values
        self.command = command
        self.width = width
        self.column = column
        self.selected_vars = {value: ctk.BooleanVar(value=False) for value in values}
        self.is_menu_open = False
        self.state = "normal"
        self.menu_window = None
        self.scroll_canvas = None
        self.scrollable_frame = None
        self.search_entry = None
        self.checkboxes = {}
        check_combobox_instances.append(self)
        logger.debug(f"Inicializando CheckComboBox con column={self.column}")
        self.setup_ui()

    def setup_ui(self):
        self.display_entry = ctk.CTkEntry(
            self, 
            width=self.width, 
            state="readonly", 
            font=("Helvetica", 11), 
            fg_color="#FFFFFF", 
            border_color="#A3BFFA", 
            text_color="#333333",
            corner_radius=6
        )
        self.display_entry.pack(side="left")
        self.update_display_text()
        
        self.toggle_button = ctk.CTkButton(
            self, 
            text="▼", 
            width=28, 
            command=self.toggle_menu,
            fg_color="#4A90E2", 
            hover_color="#2A6EBB", 
            corner_radius=6, 
            font=("Helvetica", 10)
        )
        self.toggle_button.pack(side="left", padx=(4, 0))
        
        self.display_entry.bind("<Button-1>", lambda e: self.toggle_menu())
        self.bind("<FocusIn>", lambda e: self.display_entry.configure(border_color="#4A90E2"))
        self.bind("<FocusOut>", lambda e: [self.display_entry.configure(border_color="#A3BFFA"), self.on_focus_out(e)])
        self._update_state()

    def _update_state(self):
        if self.state == "disabled":
            self.display_entry.configure(state="disabled", fg_color="#E0E0E0", text_color="#808080")
            self.toggle_button.configure(state="disabled", fg_color="#A9A9A9", hover_color="#A9A9A9")
        else:
            self.display_entry.configure(state="readonly", fg_color="#FFFFFF", text_color="#333333")
            self.toggle_button.configure(state="normal", fg_color="#4A90E2", hover_color="#2A6EBB")

    def update_display_text(self):
        selected = [value for value, var in self.selected_vars.items() if var.get()]
        if not selected:
            self.display_entry.configure(text_color="#808080")
            self.display_entry.delete(0, tk.END)
            self.display_entry.insert(0, "Selecciona...")
        else:
            display_text = ", ".join(selected[:3]) + ("..." if len(selected) > 3 else "")
            self.display_entry.configure(text_color="#333333")
            self.display_entry.delete(0, tk.END)
            self.display_entry.insert(0, display_text)

    def toggle_menu(self):
        if self.state == "disabled":
            return
        if self.is_menu_open:
            self.close_menu()
        else:
            self.open_menu()

    def open_menu(self):
        if self.is_menu_open or self.state == "disabled":
            return
        
        for instance in check_combobox_instances:
            if instance != self and instance.is_menu_open:
                instance.close_menu()
        
        try:
            self.is_menu_open = True
            self.menu_window = ctk.CTkToplevel(self)
            self.menu_window.title("")
            self.menu_window.configure(fg_color="#FFFFFF")
            self.menu_window.transient(self)
            self.menu_window.overrideredirect(True)
            self.menu_window.attributes('-topmost', True)

            # Crear frame principal con bordes redondeados y sombra
            menu_frame = ctk.CTkFrame(self.menu_window, fg_color="#FFFFFF", corner_radius=8, border_width=1, border_color="#D3D3D3")
            menu_frame.pack(fill="both", expand=True, padx=2, pady=2)

            num_options = len(self.values)
            option_height = 28
            max_height = 400
            min_height = 150
            calculated_height = min(max(num_options * option_height + 100, min_height), max_height)
            menu_width = max(self.width + 40, 220)

            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            self.menu_window.geometry(f"{menu_width}x{int(calculated_height)}+{x}+{y}")

            self.search_entry = ctk.CTkEntry(
                menu_frame, 
                placeholder_text="Buscar...", 
                width=menu_width - 20, 
                fg_color="#F5F7FA", 
                border_color="#A3BFFA", 
                corner_radius=6,
                text_color="#1A2E5A"
            )
            self.search_entry.pack(fill="x", padx=10, pady=8)
            # MODIFICACIÓN: Usar bind_all para <KeyRelease> y establecer el foco
            self.menu_window.bind_all("<KeyRelease>", self.filter_options)
            self.search_entry.focus_set()
            
            self.scroll_canvas = ctk.CTkCanvas(menu_frame, bg="#FFFFFF", highlightthickness=0)
            self.scrollbar = ctk.CTkScrollbar(
                menu_frame, 
                orientation="vertical", 
                command=self.scroll_canvas.yview, 
                width=20,
                fg_color="#FFFFFF", 
                button_color="#4A90E2", 
                button_hover_color="#2A6EBB"
            )
            self.scrollable_frame = ctk.CTkFrame(self.scroll_canvas, fg_color="#FFFFFF")
            
            self.scrollable_frame.bind("<Configure>", lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))
            self.scroll_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=menu_width - 30)
            self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
            
            self.scroll_canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
            self.scrollbar.pack(side="right", fill="y", padx=(0, 10))
            
            self.checkboxes = {}
            for value in self.values:
                var = self.selected_vars[value]
                checkbox = ctk.CTkCheckBox(
                    self.scrollable_frame, 
                    text=value, 
                    variable=var, 
                    command=self.on_selection_change,
                    font=("Helvetica", 11), 
                    fg_color="#4A90E2", 
                    text_color="#1A2E5A",
                    hover_color="#E6F0FA"
                )
                checkbox.pack(fill="x", padx=8, pady=2)
                self.checkboxes[value] = checkbox
            
            button_frame = ctk.CTkFrame(menu_frame, fg_color="transparent")
            button_frame.pack(fill="x", padx=10, pady=8)
            ctk.CTkButton(
                button_frame, 
                text="Seleccionar Todo", 
                command=self.select_all,
                fg_color="#4A90E2", 
                hover_color="#2A6EBB", 
                corner_radius=8, 
                width=100,
                font=("Helvetica", 10)
            ).pack(side="left", padx=5)
            ctk.CTkButton(
                button_frame, 
                text="Deseleccionar", 
                command=self.deselect_all,
                fg_color="#FF6F61", 
                hover_color="#E55B50", 
                corner_radius=8, 
                width=100,
                font=("Helvetica", 10)
            ).pack(side="right", padx=5)
            
            self.menu_window.update_idletasks()
            if self.scroll_canvas.winfo_exists():
                self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
            else:
                logger.error("Canvas no existe después de la inicialización")
            
            def on_mouse_scroll(event):
                if self.menu_window.winfo_exists():
                    widget_under_mouse = self.winfo_containing(event.x_root, event.y_root)
                    if widget_under_mouse in [self.scroll_canvas, self.scrollable_frame] or \
                       widget_under_mouse in self.checkboxes.values() or \
                       self.scroll_canvas.winfo_containing(event.x_root, event.y_root) == self.scroll_canvas:
                        delta = int(-event.delta / 120)
                        self.scroll_canvas.yview_scroll(delta, "units")
            
            self.menu_window.bind_all("<MouseWheel>", on_mouse_scroll)
            self.scroll_canvas.focus_set()
            
            logger.debug("Menú desplegable creado y mostrado")
        except Exception as e:
            logger.error(f"Error al abrir el menú desplegable: {str(e)}")
            self.is_menu_open = False
            if self.menu_window:
                self.menu_window.destroy()
                self.menu_window = None
            raise

    def close_menu(self):
        if self.menu_window:
            # MODIFICACIÓN: Desvincular <KeyRelease> usando unbind_all
            self.menu_window.unbind_all("<KeyRelease>")
            self.menu_window.unbind_all("<MouseWheel>")
            self.menu_window.destroy()
            self.menu_window = None
            self.scroll_canvas = None
            self.scrollable_frame = None
            self.search_entry = None
            self.checkboxes = {}
            self.is_menu_open = False
            logger.debug("Menú desplegable cerrado")

    def on_focus_out(self, event):
        if self.menu_window and not self.winfo_containing(event.x_root, event.y_root) in [self, self.menu_window, self.display_entry, self.toggle_button]:
            self.close_menu()

    def filter_options(self, event=None):
        if not self.menu_window or not self.menu_window.winfo_exists():
            logger.warning("Menú desplegable no existe o fue destruido")
            return
        
        # MODIFICACIÓN: Verificar que el foco esté en search_entry
        if self.search_entry != self.winfo_toplevel().focus_get():
            return
        
        try:
            search_text = self.search_entry.get().strip().lower()
            logger.debug(f"Filtrando opciones para column={self.column}, search_text={search_text}")
            
            for checkbox in self.checkboxes.values():
                checkbox.pack_forget()
            self.checkboxes.clear()
            
            filtered_values = [v for v in self.values if search_text in v.lower()]
            
            for value in filtered_values:
                var = self.selected_vars[value]
                checkbox = ctk.CTkCheckBox(
                    self.scrollable_frame, 
                    text=value, 
                    variable=var, 
                    command=self.on_selection_change,
                    font=("Helvetica", 11), 
                    fg_color="#4A90E2", 
                    text_color="#1A2E5A",
                    hover_color="#E6F0FA"
                )
                checkbox.pack(fill="x", padx=8, pady=2)
                self.checkboxes[value] = checkbox
            
            if self.scroll_canvas and self.scroll_canvas.winfo_exists():
                self.menu_window.update_idletasks()
                self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
            else:
                logger.error("Canvas no existe en filter_options")
        except Exception as e:
            logger.error(f"Error al filtrar opciones: {str(e)}")

    def on_selection_change(self):
        self.update_display_text()
        if self.command:
            selected = self.get_selected()
            logger.debug(f"Ejecutando comando con selecciones: {selected}, column={self.column}")
            self.command(selected)

    def select_all(self):
        for var in self.selected_vars.values():
            var.set(True)
        self.update_display_text()
        if self.command:
            selected = self.get_selected()
            self.command(selected)

    def deselect_all(self):
        for var in self.selected_vars.values():
            var.set(False)
        self.update_display_text()
        if self.command:
            selected = self.get_selected()
            self.command(selected)

    def configure(self, values=None, state=None):
        if values is not None:
            self.values = values
            self.selected_vars = {value: ctk.BooleanVar(value=False) for value in values}
            if self.is_menu_open:
                self.close_menu()
                self.open_menu()
            self.update_display_text()
        if state is not None:
            self.state = state
            self._update_state()

    def get_selected(self):
        selected = [value for value, var in self.selected_vars.items() if var.get()]
        return selected

    def set(self, selected_values, skip_command=False):
        for value, var in self.selected_vars.items():
            var.set(value in selected_values)
        self.update_display_text()
        if self.command and not skip_command:
            selected = self.get_selected()
            self.command(selected)