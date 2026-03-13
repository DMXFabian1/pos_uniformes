import sqlite3
import os
import shutil
from PIL import Image
import customtkinter as ctk
from tkinter import messagebox, filedialog
from src.ui.ui_components import create_labeled_entry, create_labeled_combobox
from src.core.utils.tooltips import ToolTip
from src.core.config.config import CONFIG
from datetime import datetime
from uuid import uuid4
from src.core.utils.logging_config import setup_logging

class ProductEditForm:
    """Clase que crea y maneja una ventana para editar los detalles de un producto."""
    def __init__(self, root, product_service, validator, store_id):
        """
        Inicializa el formulario de edición de productos.

        Args:
            root (tk.Tk): Ventana raíz de Tkinter.
            product_service (ProductService): Servicio para interactuar con productos.
            validator (ProductValidator): Validador para entradas.
            store_id (int): ID de la tienda.
        """
        self.logger = setup_logging(store_id=store_id)
        self.root = root
        self.product_service = product_service
        self.validator = validator
        self.store_id = store_id
        self.root_folder = CONFIG.get('ROOT_FOLDER', os.path.abspath(os.path.dirname(__file__)))
        self.omit_vars = {}
        self.image_references = []
        self.edit_image_path = None
        self.edit_qr_path = None
        self.edit_image_label = None
        self.edit_qr_label = None
        self.original_product_data = None
        self.empty_image = ctk.CTkImage(light_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)), size=(1, 1))
        self.logger.debug("ProductEditForm inicializado para tienda %d", store_id)

    def toggle_field(self, omit_var, widget):
        """Habilita o deshabilita un campo según el estado del omit_var."""
        state = "disabled" if omit_var.get() else "normal"
        try:
            widget.configure(state=state)
        except Exception as e:
            self.logger.warning("Error al togglear campo: %s", str(e))

    def create_field(self, parent, field_config, row, col):
        """
        Crea un campo de entrada o combobox según la configuración.

        Args:
            parent (tk.Widget): Widget padre.
            field_config (dict): Configuración del campo.
            row (int): Fila en la cuadrícula.
            col (int): Columna en la cuadrícula.

        Returns:
            tk.Widget: Widget creado (entrada o combobox) o None si falla.
        """
        try:
            field = field_config["field"]
            label = field_config["label"]
            value = field_config.get("value", "") or ""
            required = field_config.get("required", False)
            placeholder = field_config.get("placeholder", f"Ej: {label}")
            values = field_config.get("values", [])

            self.logger.debug(f"Creando campo {field} con valor inicial '{value}', requerido={required}, valores={values}")

            self.omit_vars[field] = ctk.BooleanVar(value=False) if not required else None
            if values:
                widget_field = create_labeled_combobox(
                    parent, f"{label}:", values=values, width=300, row=row, column=col, sticky="w",
                    omit_var=self.omit_vars[field] if not required else None, toggle_callback=self.toggle_field,
                    tooltip=f"Selecciona el {label.lower()} del producto{' (requerido)' if required else ''}",
                    label_width=120, label_sticky="e", input_sticky="w", padx=(5, 10), pady=5
                )
                widget = widget_field["combobox"]
                self.logger.debug(f"Combobox creado para {field}: {widget}")
                widget.set(value if value in values else "")
            else:
                widget_field = create_labeled_entry(
                    parent, f"{label}:", placeholder_text=placeholder, width=300,
                    row=row, column=col, sticky="w", omit_var=self.omit_vars[field] if not required else None,
                    toggle_callback=self.toggle_field, tooltip=f"Ingresa el {label.lower()} del producto{' (requerido)' if required else ''}",
                    label_width=120, label_sticky="e", input_sticky="w", padx=(5, 10), pady=5
                )
                widget = widget_field["entry"]
                self.logger.debug(f"Entry creado para {field}: {widget}")
                widget.insert(0, value)

            if not widget:
                self.logger.error("Widget no creado para campo %s", field)
                return None

            if not required and not value:
                self.omit_vars[field].set(True)
                widget.configure(state="disabled")

            # Bind validations
            if required:
                widget.bind("<KeyRelease>", lambda e: self._validate_field(widget, label, "required"))
            if field == "ubicacion":
                widget.bind("<KeyRelease>", lambda e: self._validate_field(widget, label, "ubicacion"))
            if field in ["precio", "inventario", "ventas"]:
                widget.bind("<KeyRelease>", lambda e: self._validate_field(widget, label, "numeric"))
            if field == "talla":
                widget.bind("<<ComboboxSelected>>", lambda e: self._validate_field(widget, label, "talla"))
                widget.bind("<KeyRelease>", lambda e: self._validate_field(widget, label, "talla"))

            self.logger.debug(f"Campo {field} creado exitosamente")
            return widget
        except Exception as e:
            self.logger.error("Error al crear campo %s: %s", field_config.get("field", "desconocido"), str(e), exc_info=True)
            return None

    def _validate_field(self, widget, label, validation_type):
        """Valida un campo en tiempo real según el tipo de validación."""
        try:
            value = widget.get()
            if validation_type == "required":
                return self.validator.validate_required(value, label, widget)
            elif validation_type == "ubicacion":
                return self.validator.validate_ubicacion(value, label, widget)
            elif validation_type == "numeric":
                return self.validator.validate_numeric(value, label, widget, allow_negative=False)
            elif validation_type == "talla":
                return self.validator.validate_talla(value, label, widget, self.custom_tallas)
            else:
                self.logger.warning("Tipo de validación desconocido: %s para campo %s", validation_type, label)
                return True, ""
        except Exception as e:
            self.logger.error("Error al validar campo %s (%s): %s", label, validation_type, str(e))
            return False, f"Error al validar {label}: {str(e)}"

    def clear_fields(self, entries):
        """Limpia los campos del formulario de edición."""
        try:
            for field, entry in entries.items():
                if entry is None:
                    self.logger.warning(f"Campo {field} es None al limpiar campos")
                    continue
                if field in self.omit_vars:
                    self.omit_vars[field].set(True)
                    entry.configure(state="disabled")
                    if isinstance(entry, ctk.CTkEntry):
                        entry.delete(0, ctk.END)
                    else:
                        entry.set("")
                elif field in ["inventario", "ventas"]:
                    entry.delete(0, ctk.END)
                    entry.insert(0, "0")

            self.edit_image_path = None
            self.edit_qr_path = None
            if self.edit_image_label:
                self.edit_image_label.configure(image=self.empty_image, text="Sin imagen")
                self.edit_image_label.image = self.empty_image
            if self.edit_qr_label:
                self.edit_qr_label.configure(image=self.empty_image, text="Sin etiqueta")
                self.edit_qr_label.image = self.empty_image
            self.logger.debug("Campos de edición limpiados")
        except Exception as e:
            self.logger.error("Error al limpiar campos: %s", str(e))
            messagebox.showerror("Error", "No se pudieron limpiar los campos")

    def restore_original_values(self, entries, sku):
        """Restaura los valores originales del producto."""
        try:
            if not self.original_product_data:
                messagebox.showwarning("Advertencia", "No se pueden restaurar los valores originales")
                return

            product = self.original_product_data
            for field, entry in entries.items():
                if entry is None:
                    self.logger.warning(f"Campo {field} es None al restaurar valores para SKU {sku}")
                    continue
                value = product.get(field, "") or ""
                display_value = (
                    str(int(value)) if value and field in ["inventario", "ventas"] else
                    f"{float(value):.2f}" if value and field == "precio" else
                    str(value)
                )
                if isinstance(entry, ctk.CTkEntry):
                    entry.delete(0, ctk.END)
                    entry.insert(0, display_value)
                else:
                    entry.set(display_value)
                if field in self.omit_vars:
                    self.omit_vars[field].set(not value)
                    entry.configure(state="disabled" if self.omit_vars[field].get() else "normal")
                self.validator.validate_required(display_value, field, entry)

            self.edit_image_path = product.get("image_path")
            self.edit_qr_path = product.get("qr_path")
            self._update_image_label()
            self._update_qr_label()
            self.logger.debug("Valores originales restaurados para SKU %s", sku)
        except Exception as e:
            self.logger.error("Error al restaurar valores originales para SKU %s: %s", sku, str(e))
            messagebox.showerror("Error", "No se pudieron restaurar los valores originales")

    def _update_image_label(self):
        """Actualiza la etiqueta de la imagen del producto."""
        try:
            if self.edit_image_path and os.path.exists(os.path.join(self.root_folder, self.edit_image_path)):
                img = Image.open(os.path.join(self.root_folder, self.edit_image_path))
                img.thumbnail((150, 150), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, size=(150, 150))
                self.edit_image_label.configure(image=ctk_img, text="")
                self.edit_image_label.image = ctk_img
                self.image_references.append(ctk_img)
                self.logger.debug("Imagen cargada: %s", self.edit_image_path)
            else:
                self.edit_image_label.configure(image=self.empty_image, text="Sin imagen")
                self.edit_image_label.image = self.empty_image
                self.logger.debug("Sin imagen para mostrar")
        except Exception as e:
            self.logger.error("Error al actualizar imagen: %s", str(e))
            self.edit_image_label.configure(image=self.empty_image, text="No se pudo cargar la imagen")

    def _update_qr_label(self):
        """Actualiza la etiqueta de la etiqueta QR."""
        try:
            if self.edit_qr_path and os.path.exists(os.path.join(self.root_folder, self.edit_qr_path)):
                img = Image.open(os.path.join(self.root_folder, self.edit_qr_path))
                img.thumbnail((150, 150), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, size=(150, 150))
                self.edit_qr_label.configure(image=ctk_img, text="")
                self.edit_qr_label.image = ctk_img
                self.image_references.append(ctk_img)
                self.logger.debug("Etiqueta QR cargada: %s", self.edit_qr_path)
            else:
                self.edit_qr_label.configure(image=self.empty_image, text="Sin etiqueta")
                self.edit_qr_label.image = self.empty_image
                self.logger.debug("Sin etiqueta QR para mostrar")
        except Exception as e:
            self.logger.error("Error al actualizar etiqueta QR: %s", str(e))
            self.edit_qr_label.configure(image=self.empty_image, text="No se pudo cargar la etiqueta")

    def select_new_image(self):
        """Selecciona una nueva imagen para el producto."""
        try:
            file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")])
            if not file_path:
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(file_path)[1]
            new_filename = f"product_image_{timestamp}{file_extension}"
            new_file_path = os.path.join(self.root_folder, "ProductImages", new_filename)
            os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
            shutil.copy(file_path, new_file_path)
            self.edit_image_path = os.path.join("ProductImages", new_filename)
            self._update_image_label()
            self.logger.info("Nueva imagen seleccionada: %s", self.edit_image_path)
        except PermissionError as e:
            self.logger.error("Error de permisos al copiar imagen: %s", str(e))
            messagebox.showerror("Error", "No se tienen permisos para copiar la imagen")
            self.edit_image_path = None
            self._update_image_label()
        except Exception as e:
            self.logger.error("Error al cargar imagen: %s", str(e))
            messagebox.showerror("Error", f"No se pudo cargar la imagen: {str(e)}")
            self.edit_image_path = None
            self._update_image_label()

    def edit_product(self, sku, custom_tallas, label_manager, on_save_callback):
        """Abre una ventana para editar un producto."""
        try:
            product = self.product_service.repository.get_product(sku)
            if not product:
                self.logger.error("Producto no encontrado con SKU %s", sku)
                messagebox.showerror("Error", "Producto no encontrado")
                return

            self.original_product_data = product
            self.custom_tallas = custom_tallas
            self.label_manager = label_manager  # Almacenar label_manager para usar en save_edited_product

            edit_window = ctk.CTkToplevel(self.root)
            edit_window.title(f"Editar Producto - SKU: {sku}")
            edit_window.geometry("900x700")
            edit_window.configure(fg_color="#F5F7FA")
            edit_window.transient(self.root)
            edit_window.grab_set()
            self.logger.debug("Ventana de edición creada para SKU %s", sku)

            def on_window_close():
                self.image_references = []
                self.original_product_data = None
                edit_window.destroy()
                self.logger.debug("Ventana de edición cerrada")

            edit_window.protocol("WM_DELETE_WINDOW", on_window_close)

            canvas = ctk.CTkCanvas(edit_window, bg="#F5F7FA", highlightthickness=0)
            scrollbar = ctk.CTkScrollbar(edit_window, orientation="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=15, pady=15)
            scrollbar.pack(side="right", fill="y")

            content_frame = ctk.CTkFrame(canvas, fg_color="#FFFFFF", corner_radius=10, border_width=1, border_color="#A3BFFA")
            canvas.create_window((0, 0), window=content_frame, anchor="nw")

            entries = {}
            field_sections = self._define_field_sections(product)
            for section_idx, (section_title, fields) in enumerate(field_sections.items()):
                section_frame = ctk.CTkFrame(content_frame, fg_color="#E6F0FA", corner_radius=5, border_width=1, border_color="#A3BFFA")
                section_frame.grid(row=section_idx, column=0, padx=15, pady=(10 if section_idx == 0 else 0, 10), sticky="ew", columnspan=2)
                section_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
                ctk.CTkLabel(section_frame, text=section_title, font=("Helvetica", 14, "bold"), text_color="#1A2E5A").grid(row=0, column=0, columnspan=4, padx=10, pady=5, sticky="w")

                for i, field_config in enumerate(fields):
                    col = 0 if i % 2 == 0 else 2
                    row = (i // 2) + 1
                    widget = self.create_field(section_frame, field_config, row, col)
                    if widget is None:
                        self.logger.error("No se pudo crear el widget para el campo %s en la sección %s", field_config["field"], section_title)
                        messagebox.showerror("Error", f"No se pudo crear el campo {field_config['label']}")
                        return
                    entries[field_config["field"]] = widget

            self._create_media_section(content_frame, product, entries, label_manager, sku)

            button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            button_frame.grid(row=len(field_sections), column=0, columnspan=2, pady=15, sticky="ew")
            button_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

            buttons = [
                ("Guardar", lambda: self.save_edited_product(sku, entries, edit_window, on_save_callback), "#4A90E2", "#2A6EBB", "Guarda los cambios realizados en el producto"),
                ("Restaurar Original", lambda: self.restore_original_values(entries, sku), "#FFA500", "#CC8400", "Restaura los valores originales del producto"),
                ("Limpiar Campos", lambda: self.clear_fields(entries), "#FF6F61", "#E55B50", "Restaura los campos opcionales a su estado predeterminado"),
                ("Cancelar", on_window_close, "#A9A9A9", "#8B8B8B", "Cancela los cambios y cierra la ventana")
            ]
            for idx, (text, command, fg_color, hover_color, tooltip) in enumerate(buttons):
                btn = ctk.CTkButton(button_frame, text=text, command=command, fg_color=fg_color, hover_color=hover_color,
                                    corner_radius=8, font=("Helvetica", 12), width=120)
                btn.grid(row=0, column=idx, padx=15)
                ToolTip(btn, tooltip)

            content_frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

            def on_mouse_scroll(event):
                if canvas.winfo_exists() and canvas.winfo_containing(event.x_root, event.y_root) == canvas:
                    canvas.yview_scroll(int(-event.delta / 120), "units")

            canvas.bind_all("<MouseWheel>", on_mouse_scroll)
            self.logger.debug("Ventana de edición configurada para SKU %s", sku)
        except Exception as e:
            self.logger.error("Error al abrir ventana de edición para SKU %s: %s", sku, str(e))
            messagebox.showerror("Error", f"No se pudo abrir la ventana de edición: {str(e)}")

    def _define_field_sections(self, product):
        """Define las secciones y campos del formulario."""
        self.logger.debug(f"Datos del producto para SKU {product.get('sku', 'desconocido')}: {product}")
        escuelas = [""] + sorted([esc['nombre'] for esc in self.product_service.repository.db_manager.get_escuelas(self.store_id)])
        fields = {
            "Información General": [
                {"field": "nombre", "label": "Nombre", "value": str(product.get("nombre", "")), "required": True},
                {"field": "escuela", "label": "Escuela", "value": str(product.get("escuela", "")), "values": escuelas},
                {"field": "nivel_educativo", "label": "Nivel Educativo", "value": str(product.get("nivel_educativo", "")),
                 "values": [""] + sorted(CONFIG.get("NIVELES_EDUCATIVOS", []))},
            ],
            "Características Principales": [
                {"field": "tipo_prenda", "label": "Tipo Prenda", "value": str(product.get("tipo_prenda", "")),
                 "values": [""] + sorted(CONFIG.get("TIPOS_PRENDA", []))},
                {"field": "tipo_pieza", "label": "Tipo Pieza", "value": str(product.get("tipo_pieza", "")),
                 "values": [""] + sorted(CONFIG.get("TIPOS_PIEZA", []))},
                {"field": "color", "label": "Color", "value": str(product.get("color", "")),
                 "values": [""] + sorted(CONFIG.get("COLORES", []))},
                {"field": "talla", "label": "Talla", "value": str(product.get("talla", "")),
                 "values": [""] + sorted(CONFIG.get("TALLAS", []) + self.custom_tallas)},
                {"field": "genero", "label": "Género", "value": str(product.get("genero", "")),
                 "values": [""] + sorted(CONFIG.get("GENEROS", []))},
            ],
            "Detalles Adicionales": [
                {"field": "atributo", "label": "Atributo", "value": str(product.get("atributo", "")),
                 "values": [""] + sorted(CONFIG.get("ATRIBUTOS", []))},
                {"field": "marca", "label": "Marca", "value": str(product.get("marca", "")),
                 "values": [""] + sorted(CONFIG.get("MARCAS", []))},
                {"field": "escudo", "label": "Escudo", "value": str(product.get("escudo", "")),
                 "values": [""] + sorted(CONFIG.get("ESCUDOS", []))},
                {"field": "ubicacion", "label": "Ubicación", "value": str(product.get("ubicacion", ""))},
            ],
            "Inventario y Precio": [
                {"field": "precio", "label": "Precio", "value": f"{float(product['precio']):.2f}" if product.get("precio") is not None else "0.00", "required": True},
                {"field": "inventario", "label": "Inventario", "value": str(int(product["inventario"])) if product.get("inventario") is not None else "0", "required": True},
                {"field": "ventas", "label": "Ventas", "value": str(int(product["ventas"])) if product.get("ventas") is not None else "0", "required": True},
            ],
        }
        return fields

    def _create_media_section(self, parent, product, entries, label_manager, sku):
        """Crea la sección de medios (imágenes y QR)."""
        media_frame = ctk.CTkFrame(parent, fg_color="#F5F5F5", corner_radius=8, border_width=1, border_color="#A3BFFA")
        media_frame.grid(row=4, column=0, padx=15, pady=(0, 10), sticky="ew", columnspan=2)
        media_frame.grid_columnconfigure((0, 1), weight=1)

        for col, (title, label_attr, button_text, command, tooltip) in enumerate([
            ("Imagen del Producto", "edit_image_label", "Seleccionar Imagen", self.select_new_image, "Selecciona una nueva imagen (PNG, JPG, JPEG, GIF, BMP)"),
            ("Etiqueta del Producto", "edit_qr_label", "Regenerar Etiqueta", lambda: label_manager.regenerate_label(sku, entries, self.edit_qr_label), "Regenera la etiqueta QR basada en los datos actuales"),
        ]):
            subframe = ctk.CTkFrame(media_frame, fg_color="#F5F5F5", corner_radius=8, width=200)
            subframe.grid(row=0, column=col, padx=10, pady=5, sticky="n")
            subframe.grid_propagate(False)
            subframe.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(subframe, text=title, font=("Helvetica", 12, "bold"), text_color="#1A2E5A").grid(row=0, column=0, padx=10, pady=5, sticky="n")

            setattr(self, label_attr, ctk.CTkLabel(subframe, text="Sin imagen", image=None, width=150, height=150))
            getattr(self, label_attr).grid(row=1, column=0, padx=5, pady=5, sticky="n")
            getattr(self, f"_update_{label_attr.split('_')[1]}_label")()

            btn = ctk.CTkButton(subframe, text=button_text, command=command, fg_color="#4A90E2", hover_color="#2A6EBB",
                                corner_radius=8, font=("Helvetica", 12), width=120)
            btn.grid(row=2, column=0, padx=5, pady=5, sticky="n")
            ToolTip(btn, tooltip)

    def save_edited_product(self, sku, entries, edit_window, on_save_callback):
        """Guarda los cambios realizados en el producto y regenera la etiqueta."""
        try:
            self.logger.debug(f"Campos en entries para SKU {sku}: {list(entries.keys())}")
            for field, widget in entries.items():
                self.logger.debug(f"Campo {field}: {'None' if widget is None else 'Widget existe'}")

            # Define required fields
            required_fields = ["nombre", "precio", "inventario", "ventas"]

            # Validate required fields
            for field in required_fields:
                if field not in entries:
                    self.logger.error(f"Campo requerido '{field}' no está definido en entries para SKU {sku}")
                    messagebox.showerror("Error", f"El campo '{field}' no está definido")
                    return
                if entries[field] is None:
                    self.logger.error(f"Widget para campo requerido '{field}' es None para SKU {sku}")
                    messagebox.showerror("Error", f"El widget para el campo '{field}' no está inicializado")
                    return
                is_valid, error_msg = self.validator.validate_required(entries[field].get(), field.capitalize(), entries[field])
                if not is_valid:
                    messagebox.showerror("Error", error_msg)
                    return

            # Validate numeric fields
            numeric_fields = ["precio", "inventario", "ventas"]
            for field in numeric_fields:
                is_valid, error_msg = self.validator.validate_numeric(entries[field].get(), field.capitalize(), entries[field], allow_negative=False)
                if not is_valid:
                    messagebox.showerror("Error", error_msg)
                    return

            # Validate optional fields
            optional_fields = ["ubicacion", "talla"]
            for field in optional_fields:
                if field in entries and entries[field] is not None and not self.omit_vars.get(field, ctk.BooleanVar(value=False)).get():
                    result = self._validate_field(entries[field], field.capitalize(), field)
                    if result is None:
                        self.logger.error(f"Validación de {field} devolvió None para SKU {sku}")
                        messagebox.showerror("Error", f"Error inesperado al validar {field}")
                        return
                    is_valid, error_msg = result
                    if not is_valid:
                        messagebox.showerror("Error", error_msg)
                        return

            # Gather data
            data = {}
            for field in entries:
                if field not in entries or entries[field] is None:
                    self.logger.warning(f"Campo '{field}' no está definido o es None para SKU {sku}")
                    data[field] = None
                    continue
                if field in required_fields:
                    try:
                        data[field] = entries[field].get().strip()
                    except AttributeError as e:
                        self.logger.error(f"Error al obtener valor del campo requerido '{field}' para SKU {sku}: {str(e)}")
                        messagebox.showerror("Error", f"No se pudo obtener el valor del campo '{field}'")
                        return
                else:
                    omit_var = self.omit_vars.get(field)
                    if omit_var is not None and omit_var.get():
                        data[field] = None
                    else:
                        try:
                            data[field] = entries[field].get().strip()
                        except AttributeError as e:
                            self.logger.error(f"Error al obtener valor del campo opcional '{field}' para SKU {sku}: {str(e)}")
                            messagebox.showerror("Error", f"No se pudo obtener el valor del campo '{field}'")
                            return

            # Process numeric fields
            try:
                data["precio"] = float(data["precio"] or 0.0)
                data["inventario"] = int(data["inventario"] or 0)
                data["ventas"] = int(data["ventas"] or 0)
                data["talla"] = data["talla"].upper() if data["talla"] else None
            except (ValueError, TypeError) as e:
                self.logger.error("Error al procesar campos numéricos para SKU %s: %s", sku, str(e))
                messagebox.showerror("Error", "Valores numéricos inválidos")
                return

            # Get escuela_id
            escuela_id = None
            if data.get("escuela"):
                try:
                    with self.product_service.repository.db_manager as db:
                        cursor = db.get_cursor()
                        cursor.execute("SELECT id FROM escuelas WHERE nombre = ? AND store_id = ?", (data["escuela"], self.store_id))
                        result = cursor.fetchone()
                        if result:
                            escuela_id = result[0]
                        else:
                            self.logger.warning("Escuela no encontrada: %s", data["escuela"])
                            messagebox.showerror("Error", f"La escuela '{data['escuela']}' no existe")
                            return
                except sqlite3.Error as e:
                    self.logger.error("Error al consultar escuela para SKU %s: %s", sku, str(e))
                    messagebox.showerror("Error", f"Error al validar escuela: {str(e)}")
                    return

            # Regenerate label
            try:
                # Mapear datos a los campos esperados por regenerate_label
                label_data = {
                    "nombre": data["nombre"],
                    "escuela": data.get("escuela", ""),
                    "nivel_educativo": data.get("nivel_educativo", ""),
                    "talla": data.get("talla", ""),
                    "genero": data.get("genero", ""),
                    "tipo_prenda": data.get("tipo_prenda", ""),
                    "tipo_pieza": data.get("tipo_pieza", "")
                }
                # Llamar a regenerate_label para generar la etiqueta con el formato de qr_generator.py
                qr_path_relative, label_path_relative = self.label_manager.regenerate_label(sku, label_data, self.edit_qr_label)
                self.edit_qr_path = label_path_relative
                self.logger.info("Etiqueta regenerada para SKU %s: %s", sku, self.edit_qr_path)
            except Exception as e:
                self.logger.error("Error al regenerar etiqueta para SKU %s: %s", sku, str(e))
                messagebox.showerror("Error", f"No se pudo regenerar la etiqueta: {str(e)}")
                return

            # Update product
            try:
                with self.product_service.repository.db_manager as db:
                    cursor = db.get_cursor()
                    query = """
                        UPDATE productos SET 
                            nombre = ?, nivel_educativo = ?, escuela_id = ?, color = ?, tipo_prenda = ?, tipo_pieza = ?, 
                            genero = ?, atributo = ?, ubicacion = ?, escudo = ?, marca = ?, talla = ?, 
                            inventario = ?, ventas = ?, precio = ?, qr_path = ?, image_path = ?
                        WHERE sku = ? AND store_id = ?
                    """
                    params = (
                        data["nombre"],
                        data.get("nivel_educativo"),
                        escuela_id,
                        data.get("color"),
                        data.get("tipo_prenda"),
                        data.get("tipo_pieza"),
                        data.get("genero"),
                        data.get("atributo"),
                        data.get("ubicacion"),
                        data.get("escudo"),
                        data.get("marca"),
                        data["talla"],
                        data["inventario"],
                        data["ventas"],
                        data["precio"],
                        self.edit_qr_path,
                        self.edit_image_path,
                        sku,
                        self.store_id
                    )
                    cursor.execute(query, params)
                    db.commit()
                    self.logger.info("Producto actualizado: SKU %s", sku)
            except sqlite3.Error as e:
                self.logger.error("Error en la base de datos al guardar producto %s: %s", sku, str(e))
                messagebox.showerror("Error", f"No se pudo guardar el producto: {str(e)}")
                return

            on_save_callback()
            messagebox.showinfo("Éxito", f"Producto {sku} actualizado correctamente")
        except Exception as e:
            self.logger.error("Error inesperado al guardar producto %s: %s", sku, str(e), exc_info=True)
            messagebox.showerror("Error", f"No se pudo guardar el producto: {str(e)}")
        finally:
            edit_window.destroy()