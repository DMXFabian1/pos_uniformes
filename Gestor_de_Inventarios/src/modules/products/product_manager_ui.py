import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox
from src.core.utils.tooltips import ToolTip
from PIL import Image, ImageTk
import logging
import sqlite3
from src.core.utils.utils import sanitize_filename
from src.modules.products import generar_qr, generar_etiqueta
from src.modules.products.standard_label_generator import clean_nombre
import os
from src.core.paths import BASE_DIR, ICONS_DIR
from src.ui.ui_components import create_check_combobox
from src.core.utils.logging_config import setup_logging
from src.core.utils.treeview_utils import apply_treeview_styles
from src.modules.products.qr_code_generator import ensure_print_quality_qr
import math

logger = setup_logging()

class PrintPreviewWindow(ctk.CTkToplevel):
    def __init__(self, parent, label_path, print_callback, manager):
        super().__init__(parent)
        self.title("Vista Previa e Impresión")
        self.geometry("600x700")
        self.configure(fg_color="#E6F0FA")
        self.transient(parent)
        self.grab_set()
        self.label_path = label_path
        self.print_callback = print_callback
        self.manager = manager
        self.tree = manager.ui.tree
        self.add_to_inventory_var = tk.BooleanVar(value=False)
        self.items = []
        self.current_index = 0
        self.current_sku = None
        # Vincular label_type a self.manager.ui.selected_label_type
        self.label_type = self.manager.ui.selected_label_type
        selected_items = self.tree.selection()
        if selected_items:
            self.current_sku = self.tree.item(selected_items[0])["values"][0].upper()
            logger.debug(f"SKU seleccionado al abrir PrintPreviewWindow: {self.current_sku}")
        self.setup_ui()
        self.initialize_navigation()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def initialize_navigation(self):
        self.items = list(self.tree.get_children())
        self.current_index = 0
        if self.items and self.current_sku:
            for i, item in enumerate(self.items):
                try:
                    if self.tree.item(item)["values"][0].upper() == self.current_sku:
                        self.current_index = i
                        break
                except tk.TclError:
                    logger.warning(f"Item {item} no encontrado en el Treeview al inicializar navegación")
                    continue
        self.update_label()
        self.update_button_states()

    def update_button_states(self):
        if not self.items:
            self.prev_button.configure(state="disabled")
            self.next_button.configure(state="disabled")
            return
        self.prev_button.configure(state="normal" if self.current_index > 0 else "disabled")
        self.next_button.configure(state="normal" if self.current_index < len(self.items) - 1 else "disabled")

    def refresh_items(self):
        old_items = set(self.items)
        self.items = list(self.tree.get_children())
        new_items = set(self.items)
        if old_items != new_items:
            logger.debug("Lista de items del Treeview actualizada")
            if self.current_sku:
                for i, item in enumerate(self.items):
                    try:
                        if self.tree.item(item)["values"][0].upper() == self.current_sku:
                            self.current_index = i
                            break
                    except tk.TclError:
                        logger.warning(f"Item {item} no encontrado al refrescar items")
                        continue
                else:
                    self.current_index = 0
                    self.current_sku = None if not self.items else self.tree.item(self.items[0])["values"][0].upper()
            else:
                self.current_index = 0
                self.current_sku = None if not self.items else self.tree.item(self.items[0])["values"][0].upper()
            self.update_label()
            self.update_button_states()

    def previous_product(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_label()
            self.update_button_states()
            self.update_selection()

    def next_product(self):
        if self.current_index < len(self.items) - 1:
            self.current_index += 1
            self.update_label()
            self.update_button_states()
            self.update_selection()

    def update_selection(self):
        if self.items and self.current_index < len(self.items):
            try:
                current_item = self.items[self.current_index]
                self.current_sku = self.tree.item(current_item)["values"][0].upper()
                self.tree.selection_remove(self.tree.selection())
                self.tree.selection_set(current_item)
                self.tree.focus(current_item)
                self.manager.ui.last_selected_sku = self.current_sku
                self.tree.event_generate("<<TreeviewSelect>>")
                logger.debug(f"Selección del Treeview actualizada al item {current_item} (SKU: {self.current_sku}, índice: {self.current_index})")
            except tk.TclError:
                logger.warning(f"Item {current_item} no encontrado al actualizar selección")
                self.refresh_items()
                self.update_label()

    def update_label(self):
        if not self.items or self.current_index >= len(self.items):
            self.label_image.configure(image=self.manager.ui.empty_image_photo, text="Sin producto")
            self.label_image.image = self.manager.ui.empty_image_photo
            self.label_path = None
            self.current_sku = None
            self.update_label_info()
            return

        try:
            current_item = self.items[self.current_index]
            self.current_sku = self.tree.item(current_item, "values")[0].upper()
        except tk.TclError:
            logger.warning(f"Item {current_item} no encontrado en update_label, refrescando items")
            self.refresh_items()
            if not self.items or self.current_index >= len(self.items):
                self.label_image.configure(image=self.manager.ui.empty_image_photo, text="Sin producto")
                self.label_image.image = self.manager.ui.empty_image_photo
                self.label_path = None
                self.current_sku = None
                self.update_label_info()
                return
            current_item = self.items[self.current_index]
            self.current_sku = self.tree.item(current_item, "values")[0].upper()

        try:
            with self.manager.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute("SELECT qr_path, label_split_path FROM productos WHERE sku = ? AND store_id = ?", (self.current_sku, self.manager.store_id))
                result = cursor.fetchone()
                if result:
                    label_type = self.label_type.get()
                    qr_path = result[0] if label_type == "standard" else result[1] if result[1] else result[0]
                    if qr_path:
                        qr_path_absolute = os.path.join(BASE_DIR, qr_path)
                        if os.path.exists(qr_path_absolute):
                            img = Image.open(qr_path_absolute)
                            img_width, img_height = img.size
                            max_size = 400
                            if img_width > img_height:
                                new_width = max_size
                                new_height = int(max_size * img_height / img_width)
                            else:
                                new_height = max_size
                                new_width = int(max_size * img_width / img_height)
                            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            photo = ImageTk.PhotoImage(img)
                            self.label_image.configure(image=photo, text="")
                            self.label_image.image = photo
                            self.label_path = qr_path_absolute
                            logger.debug(f"Etiqueta cargada para SKU {self.current_sku}: {qr_path_absolute}")
                        else:
                            logger.warning(f"Etiqueta no encontrada para SKU {self.current_sku}: {qr_path_absolute}")
                            self.label_image.configure(image=self.manager.ui.empty_image_photo, text="Etiqueta no encontrada")
                            self.label_image.image = self.manager.ui.empty_image_photo
                            self.label_path = None
                    else:
                        logger.warning(f"No se encontró qr_path o label_split_path para SKU {self.current_sku}")
                        self.label_image.configure(image=self.manager.ui.empty_image_photo, text="Sin etiqueta")
                        self.label_image.image = self.manager.ui.empty_image_photo
                        self.label_path = None
                else:
                    logger.warning(f"No se encontró registro para SKU {self.current_sku}")
                    self.label_image.configure(image=self.manager.ui.empty_image_photo, text="Sin etiqueta")
                    self.label_image.image = self.manager.ui.empty_image_photo
                    self.label_path = None
            self.update_label_info()
        except Exception as e:
            logger.error(f"Error al cargar etiqueta para SKU {self.current_sku}: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"No se pudo cargar la etiqueta: {str(e)}")
            self.label_image.configure(image=self.manager.ui.empty_image_photo, text="Error al cargar")
            self.label_image.image = self.manager.ui.empty_image_photo
            self.label_path = None
            self.update_label_info()

    def update_label_info(self):
        try:
            copies_text = self.copies_entry.get().strip()
            copies = int(copies_text) if copies_text.isdigit() else 0
            label_type = self.label_type.get()
            if label_type == "split" and copies > 0:
                effective_copies = math.ceil(copies / 4)
                self.label_info.configure(text=f"Se imprimirán {effective_copies} etiquetas divididas ({copies} copias)")
            else:
                self.label_info.configure(text=f"Se imprimirán {copies} etiquetas estándar")
        except ValueError:
            self.label_info.configure(text="Por favor, ingresa un número válido de copias")

    def setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color="#F5F7FA", corner_radius=10, border_width=1, border_color="#A3BFFA")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        main_frame.grid_rowconfigure(0, weight=0)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_rowconfigure(2, weight=0)
        main_frame.grid_rowconfigure(3, weight=0)
        main_frame.grid_rowconfigure(4, weight=0)  # Nueva fila para label_info
        main_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(main_frame, text="Vista Previa de la Etiqueta", font=("Helvetica", 16, "bold"), text_color="#1A2E5A", wraplength=500)
        title_label.grid(row=0, column=0, pady=(10, 20))

        label_frame = ctk.CTkFrame(main_frame, fg_color="#F5F5F5", corner_radius=8, width=400, height=400)
        label_frame.grid(row=1, column=0, pady=10)
        label_frame.grid_propagate(False)

        if self.label_path and os.path.exists(self.label_path):
            img = Image.open(self.label_path)
            img_width, img_height = img.size
            max_size = 400
            if img_width > img_height:
                new_width = max_size
                new_height = int(max_size * img_height / img_width)
            else:
                new_height = max_size
                new_width = int(max_size * img_width / img_height)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.label_image = tk.Label(label_frame, image=photo, bg="#F5F5F5")
            self.label_image.image = photo
            self.label_image.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.label_image = tk.Label(label_frame, image=self.manager.ui.empty_image_photo, text="No se pudo cargar la etiqueta", bg="#F5F5F5")
            self.label_image.image = self.manager.ui.empty_image_photo
            self.label_image.place(relx=0.5, rely=0.5, anchor="center")

        copies_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        copies_frame.grid(row=2, column=0, pady=10)
        ctk.CTkLabel(copies_frame, text="Número de copias:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A").pack(side="left", padx=5)
        self.copies_entry = ctk.CTkEntry(copies_frame, width=60, border_color="#A3BFFA", fg_color="#FFFFFF")
        self.copies_entry.pack(side="left", padx=5)
        self.copies_entry.insert(0, "1")
        self.copies_entry.bind("<KeyRelease>", lambda e: self.update_label_info())
        self.after(100, lambda: self.copies_entry.focus_set())
        ToolTip(self.copies_entry, "Especifica cuántas copias de la etiqueta deseas imprimir")

        self.add_to_inventory_check = ctk.CTkCheckBox(
            copies_frame,
            text="Añadir al inventario",
            variable=self.add_to_inventory_var,
            font=("Helvetica", 12),
            text_color="#1A2E5A"
        )
        self.add_to_inventory_check.pack(side="left", padx=10)
        ToolTip(self.add_to_inventory_check, "Si está marcado, se añadirán al inventario tantas unidades como copias se impriman")

        ctk.CTkLabel(copies_frame, text="Tipo de etiqueta:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A").pack(side="left", padx=5)
        self.label_type_menu = ctk.CTkOptionMenu(
            copies_frame,
            variable=self.label_type,
            values=["standard", "split"],
            command=lambda _: [self.update_label(), self.update_label_info()],
            fg_color="#4A90E2",
            button_color="#2A6EBB",
            button_hover_color="#1A5A9A",
            font=("Helvetica", 12)
        )
        self.label_type_menu.pack(side="left", padx=5)
        ToolTip(self.label_type_menu, "Selecciona entre etiqueta estándar o dividida (cuatro partes)")

        # Añadir label para información de etiquetas a imprimir
        self.label_info = ctk.CTkLabel(main_frame, text="Se imprimirán 1 etiqueta estándar", font=("Helvetica", 12), text_color="#333333")
        self.label_info.grid(row=3, column=0, pady=5)

        buttons_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        buttons_frame.grid(row=4, column=0, pady=20)
        self.prev_button = ctk.CTkButton(buttons_frame, text="← Producto Anterior", command=self.previous_product, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=150, font=("Helvetica", 12))
        self.prev_button.pack(side="left", padx=5)
        ToolTip(self.prev_button, "Navega al producto anterior en la lista")
        ctk.CTkButton(buttons_frame, text="Imprimir", command=self.print_labels, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=150, font=("Helvetica", 12)).pack(side="left", padx=5)
        self.next_button = ctk.CTkButton(buttons_frame, text="Producto Siguiente →", command=self.next_product, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=150, font=("Helvetica", 12))
        self.next_button.pack(side="left", padx=5)
        ToolTip(self.next_button, "Navega al producto siguiente en la lista")
        ctk.CTkButton(buttons_frame, text="Cerrar", command=self.destroy, fg_color="#A9A9A9", hover_color="#8B8B8B", corner_radius=8, width=150, font=("Helvetica", 12)).pack(side="left", padx=5)

    def print_labels(self):
        try:
            copies = int(self.copies_entry.get().strip())
            if copies <= 0:
                messagebox.showwarning("Advertencia", "El número de copias debe ser mayor que 0.")
                return
            if not self.label_path:
                messagebox.showwarning("Advertencia", "No hay una etiqueta válida para imprimir.")
                return
            self.print_callback(copies, self.add_to_inventory_var.get(), self.label_type.get())
            self.refresh_items()
            self.update_selection()
            messagebox.showinfo("Éxito", f"Se enviaron {copies} etiquetas a la impresora.")
            self.copies_entry.delete(0, tk.END)
            self.copies_entry.insert(0, "1")
        except ValueError:
            messagebox.showwarning("Advertencia", "Por favor, ingresa un número válido de copias.")

    def on_closing(self):
        if self.items and self.current_index < len(self.items):
            try:
                current_item = self.items[self.current_index]
                self.current_sku = self.tree.item(current_item)["values"][0].upper()
                self.tree.selection_remove(self.tree.selection())
                self.tree.selection_set(current_item)
                self.tree.focus(current_item)
                self.manager.ui.last_selected_sku = self.current_sku
                logger.debug(f"Manteniendo selección para SKU: {self.current_sku} al cerrar PrintPreviewWindow")
            except tk.TclError:
                logger.warning(f"Item {current_item} no encontrado al cerrar, intentando restaurar selección por SKU")
                if self.current_sku:
                    for item in self.tree.get_children():
                        try:
                            if self.tree.item(item)["values"][0].upper() == self.current_sku:
                                self.tree.selection_remove(self.tree.selection())
                                self.tree.selection_set(item)
                                self.tree.focus(item)
                                self.manager.ui.last_selected_sku = self.current_sku
                                logger.debug(f"Selección restaurada para SKU: {self.current_sku} al cerrar PrintPreviewWindow")
                                break
                        except tk.TclError:
                            continue
                    else:
                        self.manager.ui.last_selected_sku = None
                        logger.debug("No se encontró el SKU actual en el Treeview al cerrar PrintPreviewWindow")
                else:
                    self.manager.ui.last_selected_sku = None
                    logger.debug("No hay SKU actual al cerrar PrintPreviewWindow")
        else:
            self.manager.ui.last_selected_sku = None
            logger.debug("No hay selección en el Treeview al cerrar PrintPreviewWindow")
        self.destroy()

class ProductManagerUI:
    def __init__(self, manager, store_id=1):
        self.manager = manager
        self.root = manager.root
        self.store_id = store_id
        self.selection_state = manager.selection_state
        self.first_selected_item = manager.first_selected_item
        self.selection_anchor = manager.selection_anchor
        self.last_selected_sku = manager.last_selected_sku
        self.current_page = manager.current_page
        self.page_size = manager.page_size
        self.total_pages = manager.total_pages
        self.current_filters = manager.current_filters
        self.sort_column = manager.sort_column
        self.sort_direction = manager.sort_direction
        self.columns = manager.columns
        self.visible_columns = manager.visible_columns
        self.is_deleting = manager.is_deleting
        self.current_label_path = manager.current_label_path
        self.empty_image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        self.empty_image_photo = ImageTk.PhotoImage(self.empty_image)
        self.filter_combos = {}
        # Añadir variable para rastrear el tipo de etiqueta seleccionado
        self.selected_label_type = tk.StringVar(value="standard")
        logger.info(f"Inicializando ProductManagerUI para tienda {self.store_id}")
        print("Iniciando ProductManagerUI")
        self.icons = self.load_icons()
        self.setup_ui()
        print("setup_ui completado")

    def load_icons(self):
        icons = {}
        icon_files = {
            "edit": "edit.png",
            "copy": "copy.png",
            "delete": "delete.png",
            "duplicate": "duplicate.png",
            "price": "price.png",
            "print": "print.png",
            "inventory": "inventory.png"
        }

        for key, file_name in icon_files.items():
            try:
                icon_path = os.path.join(ICONS_DIR, file_name)
                if not os.path.exists(icon_path):
                    logger.warning("Archivo de ícono no encontrado: %s", icon_path)
                    continue
                img = Image.open(icon_path)
                img = img.resize((24, 24), Image.Resampling.LANCZOS)
                icons[key] = ImageTk.PhotoImage(img)
                logger.debug("Ícono cargado: %s", key)
            except Exception as e:
                logger.error("Error al cargar ícono %s: %s", key, str(e))

        if not icons:
            logger.warning("No se cargaron íconos, inicializando diccionario vacío")
        return icons

    def update_active_filters_label(self):
        active_filters = []
        for column, combo in self.filter_combos.items():
            selected = combo.get_selected()
            if selected:
                label = next((config["label"] for config in self.filter_configs if config["column"] == column), column.capitalize())
                active_filters.append(f"{label}: {', '.join(selected)}")
        
        if active_filters:
            self.active_filters_label.configure(text="Filtros: " + "; ".join(active_filters))
        else:
            self.active_filters_label.configure(text="Sin filtros activos")
        logger.debug(f"Label de filtros actualizado: {self.active_filters_label.cget('text')}")

    def update_filters_and_ui(self, *args):
        try:
            self.manager.apply_filters()
            self.update_active_filters_label()
        except Exception as e:
            logger.error(f"Error al actualizar filtros y UI: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron actualizar los filtros: {str(e)}")

    def setup_ui(self):
        print("Iniciando setup_ui")
        self.manager.main_frame.grid_rowconfigure(0, weight=1)
        self.manager.main_frame.grid_rowconfigure(1, weight=0)
        self.manager.main_frame.grid_columnconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self.manager.main_frame, fg_color="#FFFFFF", corner_radius=10, border_width=2, border_color="#D3D3D3")
        self.main_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=0)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        print("main_frame configurado")

        top_bar = ctk.CTkFrame(self.main_frame, fg_color="#F5F7FA", corner_radius=0)
        top_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        top_bar.grid_columnconfigure(0, weight=0)
        top_bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top_bar, text="Gestión de Productos", font=("Helvetica", 18, "bold"), text_color="#1A2E5A").grid(row=0, column=0, padx=15, pady=10, sticky="w")

        search_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        search_frame.grid(row=0, column=1, padx=15, sticky="e")
        ctk.CTkLabel(search_frame, text="🔍 Buscar:", font=("Helvetica", 12)).grid(row=0, column=0, padx=5, sticky="w")
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Buscar por SKU o Nombre", width=200)
        self.search_entry.grid(row=0, column=1, padx=5, sticky="w")
        self.search_entry.bind("<KeyRelease>", self.manager.apply_quick_search)
        self.search_entry.bind("<Return>", self.manager.apply_quick_search)

        content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=3, minsize=500)
        content_frame.grid_columnconfigure(1, weight=1, minsize=350)
        print(f"content_frame configurado: {content_frame.winfo_width()}x{content_frame.winfo_height()}")

        left_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_frame.grid_rowconfigure(0, weight=0)
        left_frame.grid_rowconfigure(1, weight=0)
        left_frame.grid_rowconfigure(2, weight=1)
        left_frame.grid_rowconfigure(3, weight=0)
        left_frame.grid_columnconfigure(0, weight=1)

        filter_frame = ctk.CTkFrame(left_frame, fg_color="#F5F7FA", corner_radius=8, border_width=1, border_color="#D3D3D3")
        filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        filter_frame.grid_columnconfigure(0, weight=1)

        self.filter_configs = [
            {"column": "color", "label": "Color", "group": "Características"},
            {"column": "tipo_prenda", "label": "Tipo Prenda", "group": "Características"},
            {"column": "tipo_pieza", "label": "Tipo Pieza", "group": "Características"},
            {"column": "atributo", "label": "Atributo", "group": "Características"},
            {"column": "escuela", "label": "Escuela", "group": "Otros"},
            {"column": "nivel_educativo", "label": "Nivel Educativo", "group": "Otros"},
            {"column": "genero", "label": "Género", "group": "Otros"},
            {"column": "marca", "label": "Marca", "group": "Otros"},
            {"column": "talla", "label": "Talla", "group": "Otros"},
        ]

        characteristics_frame = ctk.CTkFrame(filter_frame, fg_color="#E6F0FA", corner_radius=6, border_width=1, border_color="#A3BFFA")
        characteristics_frame.pack(side="left", padx=5, pady=5)
        ctk.CTkLabel(characteristics_frame, text="Características", font=("Helvetica", 12, "bold"), text_color="#1A2E5A").pack(pady=3)

        separator = ctk.CTkFrame(filter_frame, width=2, height=50, fg_color="#A3BFFA")
        separator.pack(side="left", padx=8)

        other_frame = ctk.CTkFrame(filter_frame, fg_color="#E6F0FA", corner_radius=6, border_width=1, border_color="#A3BFFA")
        other_frame.pack(side="left", padx=5, pady=5)
        ctk.CTkLabel(other_frame, text="Otros Filtros", font=("Helvetica", 12, "bold"), text_color="#1A2E5A").pack(pady=3)

        for config in self.filter_configs:
            frame = characteristics_frame if config["group"] == "Características" else other_frame
            combo = create_check_combobox(
                frame,
                config["label"],
                values=["Cargando..."],
                width=100,
                command=self.update_filters_and_ui,
                padx=3,
                pady=3,
                check_column=config["column"],
                font=("Helvetica", 10, "bold"),
                label_color="#1A2E5A",
                bg_color="#E6F0FA"
            )
            combo.pack(side="left", padx=4)
            self.filter_combos[config["column"]] = combo
            ToolTip(combo, f"Selecciona {config['label'].lower()} para filtrar")

        control_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        control_frame.grid(row=1, column=0, sticky="ew", pady=5)
        control_frame.grid_columnconfigure(0, weight=0)
        control_frame.grid_columnconfigure(1, weight=0)
        control_frame.grid_columnconfigure(2, weight=0)
        control_frame.grid_columnconfigure(3, weight=0)
        control_frame.grid_columnconfigure(4, weight=1)
        self.filter_button = ctk.CTkButton(control_frame, text="Aplicar Filtros", command=self.update_filters_and_ui, fg_color="#4A90E2", hover_color="#2A6EBB", width=120, corner_radius=8, font=("Helvetica", 12))
        self.filter_button.grid(row=0, column=0, padx=5, sticky="w")
        ctk.CTkButton(control_frame, text="🗑 Limpiar Filtros", command=self.clear_filters, fg_color="#FF6F61", hover_color="#E55B50", width=120, corner_radius=8, font=("Helvetica", 12)).grid(row=0, column=1, padx=5, sticky="w")
        ctk.CTkButton(control_frame, text="🔄 Refrescar", command=self.manager.cargar_productos, fg_color="#4A90E2", hover_color="#2A6EBB", width=120, corner_radius=8, font=("Helvetica", 12)).grid(row=0, column=2, padx=5, sticky="w")
        self.active_filters_label = ctk.CTkLabel(control_frame, text="Sin filtros activos", font=("Helvetica", 12), text_color="#333333", wraplength=300)
        self.active_filters_label.grid(row=0, column=3, padx=10, sticky="w")
        self.selection_count_label = ctk.CTkLabel(control_frame, text="Seleccionados: 0/0", font=("Helvetica", 12))
        self.selection_count_label.grid(row=0, column=4, padx=10, sticky="w")

        tree_and_pagination_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        tree_and_pagination_frame.grid(row=2, column=0, sticky="nsew")
        tree_and_pagination_frame.grid_rowconfigure(0, weight=1)
        tree_and_pagination_frame.grid_rowconfigure(1, weight=0)
        tree_and_pagination_frame.grid_columnconfigure(0, weight=1)

        tree_frame = ctk.CTkFrame(tree_and_pagination_frame, fg_color="#FFFFFF", corner_radius=8, border_width=1, border_color="#D3D3D3")
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(1, weight=0)
        columns_to_show = self.visible_columns
        self.tree = ttk.Treeview(tree_frame, columns=columns_to_show, show="headings", height=12)
        self.tree.grid(row=0, column=0, sticky="nsew")

        style = ttk.Style()
        style.configure("Custom.Treeview", 
                        background="#FFFFFF", 
                        foreground="#1A2E5A", 
                        rowheight=28, 
                        font=("Helvetica", 11),
                        fieldbackground="#FFFFFF")
        style.configure("Custom.Treeview.Heading", 
                        font=("Helvetica", 12, "bold"), 
                        background="#E6F0FA", 
                        foreground="#1A2E5A",
                        padding=5)
        style.map("Custom.Treeview", 
                  background=[('selected', '#4A90E2'), ('!selected', '#FFFFFF')],
                  foreground=[('selected', '#FFFFFF'), ('!selected', '#1A2E5A')])
        style.map("Custom.Treeview.Heading",
                  background=[('active', '#2A6EBB')])

        scrollbar_y = ctk.CTkScrollbar(tree_frame, command=self.tree.yview, fg_color="#FFFFFF")
        scrollbar_y.grid(row=0, column=1, sticky="ns", padx=(0, 5))
        self.tree.configure(yscrollcommand=scrollbar_y.set, style="Custom.Treeview")

        column_widths = {
            "sku": 120, "nombre": 220, "escuela": 100, "nivel_educativo": 80, "marca": 80,
            "color": 70, "tipo_prenda": 90, "tipo_pieza": 90, "ubicacion": 90, "escudo": 90,
            "talla": 60, "inventario": 60, "ventas": 60, "precio": 65
        }
        for col in self.visible_columns:
            self.tree.heading(col, 
                             text=col.capitalize(), 
                             command=lambda c=col: self.manager.sort_by_column(c))
            self.tree.column(col, 
                            width=column_widths.get(col, 100), 
                            anchor="center",
                            stretch=True)

        self.tree.bind("<<TreeviewSelect>>", lambda event: [self.update_selection_count(), self.manager.mostrar_detalle(event)])
        self.tree.bind("<Double-1>", lambda event: self.manager.edit_product())
        self.root.bind("<Control-a>", lambda event: self.select_all_with_shortcut(event))
        self.root.bind("<Control-Shift-A>", lambda event: self.deselect_all_with_shortcut(event))
        self.root.bind("<Escape>", lambda event: self.clear_window())
        ToolTip(self.tree, "Clic para seleccionar, Shift+Clic para rangos, Ctrl+Clic para múltiples, Ctrl+A para seleccionar todo")

        pagination_frame = ctk.CTkFrame(tree_and_pagination_frame, fg_color="transparent")
        pagination_frame.grid(row=1, column=0, sticky="ew", pady=5)
        pagination_frame.grid_columnconfigure(0, weight=0)
        pagination_frame.grid_columnconfigure(1, weight=0)
        pagination_frame.grid_columnconfigure(2, weight=0)
        pagination_frame.grid_columnconfigure(3, weight=0)
        pagination_frame.grid_columnconfigure(4, weight=0)
        pagination_frame.grid_columnconfigure(5, weight=1)
        pagination_frame.grid_columnconfigure(6, weight=0)
        pagination_frame.grid_columnconfigure(7, weight=0)

        def debug_prev_ten():
            logger.debug(f"Botón 'Retrocede 10 páginas' presionado, página actual: {self.current_page}, total páginas: {self.total_pages}")
            self.manager.prev_ten_pages()

        def debug_next_ten():
            logger.debug(f"Botón 'Avanza 10 páginas' presionado, página actual: {self.current_page}, total páginas: {self.total_pages}")
            self.manager.next_ten_pages()

        self.prev_ten_button = ctk.CTkButton(pagination_frame, text="≪", command=debug_prev_ten, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, font=("Helvetica", 12), width=40)
        self.prev_ten_button.grid(row=0, column=0, padx=5, sticky="w")
        ToolTip(self.prev_ten_button, "Retrocede 10 páginas")
        self.prev_button = ctk.CTkButton(pagination_frame, text="◄", command=self.manager.prev_page, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, font=("Helvetica", 12), width=40)
        self.prev_button.grid(row=0, column=1, padx=5, sticky="w")
        self.page_label = ctk.CTkLabel(pagination_frame, text="Página 1 de 1", font=("Helvetica", 12))
        self.page_label.grid(row=0, column=2, padx=5, sticky="w")
        self.next_button = ctk.CTkButton(pagination_frame, text="►", command=self.manager.next_page, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, font=("Helvetica", 12), width=40)
        self.next_button.grid(row=0, column=3, padx=5, sticky="w")
        self.next_ten_button = ctk.CTkButton(pagination_frame, text="≫", command=debug_next_ten, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, font=("Helvetica", 12), width=40)
        self.next_ten_button.grid(row=0, column=4, padx=5, sticky="w")
        ToolTip(self.next_ten_button, "Avanza 10 páginas")
        self.select_all_button = ctk.CTkButton(pagination_frame, text="✓ Todo", command=self.select_all, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, font=("Helvetica", 12))
        self.select_all_button.grid(row=0, column=6, padx=5, sticky="e")
        self.deselect_all_button = ctk.CTkButton(pagination_frame, text="✗ Ninguno", command=self.deselect_all, fg_color="#FF6F61", hover_color="#E55B50", corner_radius=8, font=("Helvetica", 12))
        self.deselect_all_button.grid(row=0, column=7, padx=5, sticky="e")

        detail_frame = ctk.CTkFrame(content_frame, fg_color="#FFFFFF", corner_radius=10, border_width=2, border_color="#D3D3D3", width=350)
        detail_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        detail_frame.grid_propagate(False)
        detail_frame.grid_rowconfigure(0, weight=0)
        detail_frame.grid_rowconfigure(1, weight=0)
        detail_frame.grid_rowconfigure(2, weight=1)
        detail_frame.grid_rowconfigure(3, weight=0)
        detail_frame.grid_rowconfigure(4, weight=0)
        detail_frame.grid_columnconfigure(0, weight=1)
        print(f"detail_frame colocado en grid: row=0, column=1, dimensions={detail_frame.winfo_width()}x{detail_frame.winfo_height()}")

        title_frame = ctk.CTkFrame(detail_frame, fg_color="#1A2E5A", corner_radius=0)
        title_frame.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(title_frame, text="Detalles del Producto", font=("Helvetica", 16, "bold"), text_color="#FFFFFF").grid(row=0, column=0, pady=5, padx=10, sticky="w")
        print("title_frame creado y colocado")

        details_content = ctk.CTkFrame(detail_frame, fg_color="#FFFFFF", corner_radius=5, width=350)
        details_content.grid(row=1, column=0, sticky="nsew", padx=5, pady=(5, 5))
        details_content.grid_propagate(False)
        details_content.grid_columnconfigure(0, weight=0)
        details_content.grid_columnconfigure(1, weight=1)
        details_content.grid_columnconfigure(2, weight=0)
        details_content.grid_columnconfigure(3, weight=1)

        self.detail_labels = {}
        fields = ["sku", "nombre", "nivel_educativo", "escuela", "color", "tipo_prenda", "tipo_pieza", "genero", "atributo", "ubicacion", "escudo", "marca", "talla", "inventario", "ventas", "precio"]

        for i, field in enumerate(fields):
            if i < 8:
                col_label = 0
                col_value = 1
                row = i
            else:
                col_label = 2
                col_value = 3
                row = i - 8
            ctk.CTkLabel(details_content, text=f"{field.capitalize()}:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A").grid(row=row, column=col_label, padx=(0, 3), pady=2, sticky="e")
            self.detail_labels[field] = ctk.CTkLabel(details_content, text="", font=("Helvetica", 11), text_color="#333333", wraplength=150, anchor="w", justify="left")
            self.detail_labels[field].grid(row=row, column=col_value, padx=(3, 5), pady=2, sticky="w")
        print("details_content creado y colocado, detail_labels inicializado")

        media_frame = ctk.CTkFrame(detail_frame, fg_color="transparent", width=350)
        media_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(2, 2))
        media_frame.grid_propagate(False)
        media_frame.grid_columnconfigure(0, weight=1)
        media_frame.grid_columnconfigure(1, weight=1)

        image_frame = ctk.CTkFrame(media_frame, fg_color="#F5F5F5", corner_radius=8, width=150)
        image_frame.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        image_frame.grid_propagate(False)
        image_frame.grid_columnconfigure(0, weight=1)
        image_frame.grid_rowconfigure(0, weight=0)
        image_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(image_frame, text="Imagen del Producto:", font=("Helvetica", 10, "bold"), text_color="#1A2E5A").grid(row=0, column=0, pady=(2, 1), sticky="n")
        self.image_container = tk.Frame(image_frame, width=140, height=140, bg="#F5F5F5")
        self.image_container.grid(row=1, column=0, pady=(0, 2), sticky="n")
        self.image_container.grid_propagate(False)
        self.image_label = tk.Label(self.image_container, text="Sin imagen", width=140, height=140, bg="#F5F5F5")
        self.image_label.pack()
        print("image_frame creado y colocado, image_label inicializado")

        qr_frame = ctk.CTkFrame(media_frame, fg_color="#F5F5F5", corner_radius=8, width=150)
        qr_frame.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        qr_frame.grid_propagate(False)
        qr_frame.grid_columnconfigure(0, weight=1)
        qr_frame.grid_rowconfigure(0, weight=0)
        qr_frame.grid_rowconfigure(1, weight=1)
        qr_frame.grid_rowconfigure(2, weight=0)
        ctk.CTkLabel(qr_frame, text="Etiqueta del Producto:", font=("Helvetica", 10, "bold"), text_color="#1A2E5A").grid(row=0, column=0, pady=(2, 1), sticky="n")
        self.qr_container = tk.Frame(qr_frame, width=140, height=140, bg="#F5F5F5")
        self.qr_container.grid(row=1, column=0, pady=(0, 2), sticky="n")
        self.qr_container.grid_propagate(False)
        self.qr_label = tk.Label(self.qr_container, text="Selecciona un producto", width=140, height=140, bg="#F5F5F5")
        self.qr_label.pack()
        self.copy_label_button = ctk.CTkButton(qr_frame, text="Copiar Etiqueta", command=self.manager.copy_image_to_clipboard, 
                                               fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, font=("Helvetica", 10), width=120)
        self.copy_label_button.grid(row=2, column=0, pady=2)
        ToolTip(self.copy_label_button, "Copiar la etiqueta (QR) al portapapeles (Ctrl+Q)")
        print("qr_frame creado y colocado, qr_label inicializado")

        self.create_action_buttons(detail_frame)
        print("action_buttons_frame creado y colocado")

        self.manager.main_frame.bind("<Configure>", self.on_resize)

        self.manager.main_frame.update()
        print(f"Main frame actualizado: {self.manager.main_frame.winfo_width()}x{self.manager.main_frame.winfo_height()}")
        print(f"content_frame dimensions después de update: {content_frame.winfo_width()}x{content_frame.winfo_height()}")
        print(f"left_frame dimensions después de update: {left_frame.winfo_width()}x{left_frame.winfo_height()}")
        print(f"detail_frame dimensions después de update: {detail_frame.winfo_width()}x{detail_frame.winfo_height()}")

        self.initialize_comboboxes()

    def create_action_buttons(self, parent_frame):
        action_buttons_frame = ctk.CTkFrame(parent_frame, fg_color="transparent", width=350)
        action_buttons_frame.grid(row=4, column=0, sticky="s", padx=5, pady=(0, 5))
        action_buttons_frame.grid_propagate(False)
        for i in range(7):
            action_buttons_frame.grid_columnconfigure(i, weight=1, minsize=50)
        action_buttons_frame.grid_rowconfigure(0, weight=0)

        buttons = [
            ("edit", self.manager.edit_product, "Editar el producto seleccionado", 0),
            ("copy", self.manager.copy_sku, "Copiar el SKU del producto seleccionado", 1),
            ("delete", self.manager.eliminar_seleccion, "Eliminar los productos seleccionados", 2),
            ("duplicate", self.manager.duplicar_producto, "Duplicar el producto seleccionado", 3),
            ("price", self.manager.open_price_modification_window, "Modificar precios de productos", 4),
            ("print", self.open_print_preview, "Vista previa e impresión de etiquetas (Ctrl+P)", 5),
            ("inventory", self.manager.update_multiple_inventories, "Actualizar inventarios de productos seleccionados", 6),
        ]

        for icon_key, command, tooltip, column in buttons:
            icon = self.icons.get(icon_key)
            if icon is None:
                logger.warning(f"Icono '{icon_key}' no encontrado")
                button = ctk.CTkButton(
                    action_buttons_frame,
                    text=icon_key.capitalize(),
                    command=command,
                    fg_color="#32CD32" if icon_key == "inventory" else "#4A90E2" if icon_key != "delete" else "#FF5555",
                    hover_color="#228B22" if icon_key == "inventory" else "#2A6EBB" if icon_key != "delete" else "#CC4444",
                    corner_radius=8,
                    width=32,
                    height=32
                )
            else:
                button = ctk.CTkButton(
                    action_buttons_frame,
                    image=icon,
                    text="",
                    command=command,
                    fg_color="#32CD32" if icon_key == "inventory" else "#4A90E2" if icon_key != "delete" else "#FF5555",
                    hover_color="#228B22" if icon_key == "inventory" else "#2A6EBB" if icon_key != "delete" else "#CC4444",
                    corner_radius=8,
                    width=32,
                    height=32
                )
            button.grid(row=0, column=column, padx=2, pady=2)
            ToolTip(button, tooltip)
            setattr(self, f"{icon_key}_button", button)

        return action_buttons_frame

    def on_resize(self, event):
        total_width = self.manager.main_frame.winfo_width()
        if total_width < 800:
            minsize_right = 300
        elif total_width < 1200:
            minsize_right = 350
        else:
            minsize_right = 400
        
        content_frame = self.main_frame.winfo_children()[1]
        content_frame.grid_columnconfigure(1, minsize=minsize_right)
        detail_frame = content_frame.winfo_children()[1]
        detail_frame.configure(width=minsize_right)
        self.adjust_column_widths()

    def open_print_preview(self):
        logger.debug(f"Abriendo vista previa de impresión con label_path: {self.current_label_path}")
        if not self.current_label_path:
            messagebox.showwarning("Advertencia", "Por favor, selecciona un producto con una etiqueta para imprimir.")
            return
        print_window = PrintPreviewWindow(self.root, self.current_label_path, self.manager.print_labels, self.manager)
        self.root.wait_window(print_window)
        if self.last_selected_sku:
            for item in self.tree.get_children():
                try:
                    if self.tree.item(item)["values"][0].upper() == self.last_selected_sku:
                        self.tree.selection_remove(self.tree.selection())
                        self.tree.selection_set(item)
                        self.tree.focus(item)
                        logger.debug(f"Selección restaurada para SKU: {self.last_selected_sku} después de cerrar PrintPreviewWindow")
                        break
                except tk.TclError:
                    logger.warning(f"Item {item} no encontrado al restaurar selección después de cerrar PrintPreviewWindow")
                    continue
            else:
                self.last_selected_sku = None
                logger.debug("No se encontró el SKU seleccionado en el Treeview después de cerrar PrintPreviewWindow")
        else:
            self.last_selected_sku = None
            logger.debug("No hay selección en el Treeview después de cerrar PrintPreviewWindow")

    def split_text(self, text, max_length=20):
        text = str(text)
        if len(text) <= max_length:
            return text
        words = text.split()
        if len(words) <= 1:
            return "\n".join([text[i:i+max_length] for i in range(0, len(text), max_length)])
        lines = []
        current_line = []
        current_length = 0
        for word in words:
            if current_length + len(word) + 1 <= max_length:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word) + 1
        if current_line:
            lines.append(" ".join(current_line))
        return "\n".join(lines)

    def clear_window(self):
        self.clear_filters()
        self.deselect_all()
        for field, label in self.detail_labels.items():
            label.configure(text="")
        self.image_label.configure(image=self.empty_image_photo, text="Sin imagen")
        self.image_label.image = self.empty_image_photo
        self.qr_label.configure(image=self.empty_image_photo, text="Selecciona un producto")
        self.qr_label.image = self.empty_image_photo
        self.current_label_path = None
        self.last_selected_sku = None
        logger.debug("Ventana limpiada con éxito")

    def on_closing(self):
        logger.debug("Cerrando ProductManagerUI")
        if hasattr(self, 'tree') and self.tree.winfo_exists():
            self.tree.unbind("<<TreeviewSelect>>")
            self.tree.unbind("<Double-1>")
        self.manager.main_frame.pack_forget()

    def mostrar_detalle(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            self.clear_details()
            return

        item = selected_items[0]
        values = self.tree.item(item, "values")
        sku = values[0].upper()
        logger.debug(f"Mostrando detalles para SKU: {sku}")
        if sku == self.last_selected_sku and not event:
            return

        self.last_selected_sku = sku
        try:
            with self.manager.db_manager as db:
                cursor = db.get_cursor()
                query = """
                    SELECT productos.sku, productos.nombre, productos.nivel_educativo, escuelas.nombre AS escuela, productos.color, 
                        productos.tipo_prenda, productos.tipo_pieza, productos.genero, productos.marca, productos.talla, 
                        productos.atributo, productos.ubicacion, productos.escudo, productos.qr_path, productos.inventario, 
                        productos.ventas, productos.precio, productos.image_path, productos.label_split_path
                    FROM productos 
                    LEFT JOIN escuelas ON productos.escuela_id = escuelas.id 
                    WHERE productos.sku = ? AND productos.store_id = ?
                """
                cursor.execute(query, (sku, self.store_id))
                producto = cursor.fetchone()
                if not producto:
                    logger.error(f"Producto no encontrado con SKU {sku} en tienda {self.store_id}.")
                    messagebox.showerror("Error", "Producto no encontrado.")
                    self.clear_details()
                    return

                required_fields = {"sku": producto[0], "nombre": producto[1]}
                for field, value in required_fields.items():
                    if value is None:
                        logger.error(f"Campo requerido '{field}' es None para SKU {sku}.")
                        messagebox.showerror("Error", f"Datos incompletos: el campo '{field}' no puede estar vacío.")
                        self.clear_details()
                        return

                fields_mapping = {
                    "sku": producto[0],
                    "nombre": producto[1],
                    "nivel_educativo": producto[2],
                    "escuela": producto[3],
                    "color": producto[4],
                    "tipo_prenda": producto[5],
                    "tipo_pieza": producto[6],
                    "genero": producto[7],
                    "marca": producto[8],
                    "talla": producto[9],
                    "atributo": producto[10],
                    "ubicacion": producto[11],
                    "escudo": producto[12],
                    "inventario": producto[14],
                    "ventas": producto[15],
                    "precio": producto[16],
                }

                for field, value in fields_mapping.items():
                    display_value = str(value if value is not None else "No especificado")
                    display_value = self.split_text(display_value, max_length=20)
                    if field == "precio" and value is not None:
                        try:
                            display_value = f"{float(value):.2f}"
                        except (ValueError, TypeError):
                            display_value = "No especificado"
                    if field == "escuela" and display_value and display_value != "No especificado":
                        nivel_educativo = fields_mapping.get("nivel_educativo", "No especificado")
                        if nivel_educativo and nivel_educativo != "No especificado":
                            display_value = self.split_text(f"{display_value} ({nivel_educativo})", max_length=20)
                    if field == "genero" and display_value and display_value != "No especificado":
                        if display_value == "Mujer":
                            symbol = "♀"
                            color = "#800080"
                        elif display_value == "Hombre":
                            symbol = "♂"
                            color = "#008000"
                        elif display_value == "Unisex":
                            symbol = "⚥"
                            color = "#808080"
                        else:
                            symbol = ""
                            color = "#333333"
                        display_value = self.split_text(f"{symbol} {display_value}" if symbol else display_value, max_length=20)
                        self.detail_labels[field].configure(text=display_value, text_color=color)
                        continue
                    if field == "ubicacion":
                        display_value = display_value if display_value != "No especificado" else "No especificado"
                    self.detail_labels[field].configure(text=display_value, text_color="#4B5EAA")

                image_path = producto[17]
                logger.debug(f"Intentando cargar imagen desde: {image_path}")
                if image_path:
                    image_path_absolute = os.path.join(BASE_DIR, image_path)
                    if os.path.exists(image_path_absolute):
                        try:
                            img = Image.open(image_path_absolute)
                            img.thumbnail((140, 140), Image.Resampling.LANCZOS)
                            photo = ImageTk.PhotoImage(img)
                            self.image_label.configure(image=photo, text="")
                            self.image_label.image = photo
                            logger.debug("Imagen del producto cargada exitosamente.")
                        except Exception as e:
                            logger.error(f"Error al abrir la imagen {image_path_absolute}: {str(e)}")
                            self.image_label.configure(image=self.empty_image_photo, text="Error al cargar imagen")
                            self.image_label.image = self.empty_image_photo
                    else:
                        logger.warning(f"Archivo de imagen no encontrado: {image_path_absolute}")
                        self.image_label.configure(image=self.empty_image_photo, text="Archivo de imagen no encontrado")
                        self.image_label.image = self.empty_image_photo
                else:
                    self.image_label.configure(image=self.empty_image_photo, text="Sin imagen")
                    self.image_label.image = self.empty_image_photo

                qr_path = producto[13]
                label_split_path = producto[18]
                nombre = producto[1]
                nivel_educativo = producto[2]
                escuela = producto[3]
                talla = producto[9]
                genero = producto[7]
                tipo_prenda = producto[5]
                tipo_pieza = producto[6]

                if not all([sku, nombre, tipo_prenda, tipo_pieza]):
                    logger.error(f"Datos incompletos para generar etiqueta para SKU {sku}: sku={sku}, nombre={nombre}, tipo_prenda={tipo_prenda}, tipo_pieza={tipo_pieza}")
                    messagebox.showerror("Error", "Faltan datos requeridos (SKU, nombre, tipo de prenda o tipo de pieza) para generar la etiqueta.")
                    self.qr_label.configure(image=self.empty_image_photo, text="Datos incompletos")
                    self.qr_label.image = self.empty_image_photo
                    self.current_label_path = None
                    return

                nombre_base = clean_nombre(nombre, talla)
                talla = talla if talla else "Sin talla"
                escuela = escuela if escuela else "Sin escuela"
                nivel_educativo = nivel_educativo if nivel_educativo else "Sin nivel educativo"
                genero = genero if genero else "Sin género"

                folder_name = f"{sanitize_filename(nombre_base)}_{sanitize_filename(tipo_prenda)}_{sanitize_filename(tipo_pieza)}"
                talla_folder = os.path.join(BASE_DIR, "Mis codigos", folder_name, sanitize_filename(talla))
                try:
                    os.makedirs(talla_folder, exist_ok=True)
                    logger.debug(f"Carpeta creada o existente: {talla_folder}")
                except OSError as e:
                    logger.error(f"Error al crear carpeta {talla_folder} para SKU {sku}: {str(e)}")
                    messagebox.showerror("Error", f"No se pudo crear la carpeta para la etiqueta: {str(e)}")
                    self.qr_label.configure(image=self.empty_image_photo, text="Error al crear carpeta")
                    self.qr_label.image = self.empty_image_photo
                    self.current_label_path = None
                    return

                qr_file_path = os.path.join(talla_folder, f"{sanitize_filename(sku)}.png")
                label_file_path = os.path.join(talla_folder, f"label_{sanitize_filename(sku)}.png")
                label_split_file_path = os.path.join(talla_folder, f"label_split_{sanitize_filename(sku)}.png")

                if qr_path and "Mis codigos" in qr_path:
                    qr_path_absolute = os.path.join(BASE_DIR, qr_path)
                    if not os.path.exists(qr_path_absolute):
                        logger.warning(f"qr_path existente no encontrado: {qr_path_absolute}. Generando nueva etiqueta.")
                        qr_path = None

                qr_regenerated = False
                if not os.path.exists(qr_file_path):
                    try:
                        generar_qr(sku, qr_file_path, tipo_pieza)
                        qr_regenerated = True
                        logger.debug(f"QR generado en: {qr_file_path}")
                    except Exception as e:
                        logger.error(f"Error al generar QR para SKU {sku}: {str(e)}", exc_info=True)
                        messagebox.showerror("Error", f"No se pudo generar el QR: {str(e)}")
                        self.qr_label.configure(image=self.empty_image_photo, text="Error al generar QR")
                        self.qr_label.image = self.empty_image_photo
                        self.current_label_path = None
                        return
                else:
                    try:
                        qr_regenerated = ensure_print_quality_qr(sku, qr_file_path, tipo_pieza)
                    except Exception as e:
                        logger.error(f"Error al regenerar QR de alta resolución para SKU {sku}: {str(e)}", exc_info=True)
                        messagebox.showerror("Error", f"No se pudo preparar el QR para impresión: {str(e)}")
                        self.qr_label.configure(image=self.empty_image_photo, text="Error al preparar QR")
                        self.qr_label.image = self.empty_image_photo
                        self.current_label_path = None
                        return

                if qr_regenerated or not qr_path or qr_path == "" or not os.path.exists(label_file_path) or qr_path != os.path.relpath(label_file_path, self.manager.root_folder):
                    try:
                        generar_etiqueta(sku, escuela, nivel_educativo, nombre_base, talla, genero, tipo_pieza, qr_file_path, label_file_path)
                        new_qr_path = os.path.relpath(label_file_path, self.manager.root_folder)
                        cursor.execute("UPDATE productos SET qr_path = ? WHERE sku = ? AND store_id = ?", 
                                    (new_qr_path, sku, self.store_id))
                        self.manager.db_manager.commit()
                        qr_path = new_qr_path
                        logger.debug(f"Etiqueta estándar generada y guardada en: {label_file_path}, qr_path actualizado: {qr_path}")
                    except sqlite3.Error as e:
                        logger.error(f"Error al actualizar qr_path en la base de datos para SKU {sku}: {str(e)}", exc_info=True)
                        messagebox.showerror("Error", f"No se pudo actualizar la base de datos: {str(e)}")
                        self.qr_label.configure(image=self.empty_image_photo, text="Error en la base de datos")
                        self.qr_label.image = self.empty_image_photo
                        self.current_label_path = None
                        return
                    except Exception as e:
                        logger.error(f"Error al generar etiqueta para SKU {sku}: {str(e)}", exc_info=True)
                        messagebox.showerror("Error", f"No se pudo generar la etiqueta: {str(e)}")
                        self.qr_label.configure(image=self.empty_image_photo, text="Error al generar etiqueta")
                        self.qr_label.image = self.empty_image_photo
                        self.current_label_path = None
                        return

                if qr_regenerated or not label_split_path or label_split_path == "" or not os.path.exists(label_split_file_path) or label_split_path != os.path.relpath(label_split_file_path, self.manager.root_folder):
                    try:
                        from src.modules.products.qr_generator import generar_etiqueta_split
                        generar_etiqueta_split(sku, nombre_base, qr_file_path, label_split_file_path)
                        new_label_split_path = os.path.relpath(label_split_file_path, self.manager.root_folder)
                        cursor.execute("UPDATE productos SET label_split_path = ? WHERE sku = ? AND store_id = ?", 
                                    (new_label_split_path, sku, self.store_id))
                        self.manager.db_manager.commit()
                        label_split_path = new_label_split_path
                        logger.debug(f"Etiqueta dividida generada y guardada en: {label_split_file_path}, label_split_path actualizado: {label_split_path}")
                    except ImportError:
                        logger.warning(f"Función generar_etiqueta_split no encontrada, omitiendo generación de etiqueta dividida para SKU {sku}")
                        label_split_path = None
                    except sqlite3.Error as e:
                        logger.error(f"Error al actualizar label_split_path en la base de datos para SKU {sku}: {str(e)}", exc_info=True)
                        messagebox.showerror("Error", f"No se pudo actualizar la base de datos: {str(e)}")
                        self.qr_label.configure(image=self.empty_image_photo, text="Error en la base de datos")
                        self.qr_label.image = self.empty_image_photo
                        self.current_label_path = None
                        return
                    except Exception as e:
                        logger.error(f"Error al generar etiqueta dividida para SKU {sku}: {str(e)}", exc_info=True)
                        messagebox.showerror("Error", f"No se pudo generar la etiqueta dividida: {str(e)}")
                        self.qr_label.configure(image=self.empty_image_photo, text="Error al generar etiqueta dividida")
                        self.qr_label.image = self.empty_image_photo
                        self.current_label_path = None
                        return

                # Usar selected_label_type para determinar qué etiqueta mostrar
                label_type = self.selected_label_type.get()
                selected_path = qr_path if label_type == "standard" else label_split_path if label_split_path else qr_path
                if selected_path:
                    qr_path_absolute = os.path.join(BASE_DIR, selected_path)
                    if os.path.exists(qr_path_absolute):
                        try:
                            img = Image.open(qr_path_absolute)
                            img.thumbnail((140, 140), Image.Resampling.LANCZOS)
                            photo = ImageTk.PhotoImage(img)
                            self.qr_label.configure(image=photo, text="")
                            self.qr_label.image = photo
                            self.current_label_path = qr_path_absolute
                            logger.debug(f"Etiqueta cargada exitosamente: {qr_path_absolute}")
                        except Exception as e:
                            logger.error(f"Error al abrir la etiqueta {qr_path_absolute} para SKU {sku}: {str(e)}", exc_info=True)
                            messagebox.showerror("Error", f"No se pudo cargar la etiqueta: {str(e)}")
                            self.qr_label.configure(image=self.empty_image_photo, text="Error al cargar etiqueta")
                            self.qr_label.image = self.empty_image_photo
                            self.current_label_path = None
                    else:
                        logger.error(f"Archivo de etiqueta no encontrado: {qr_path_absolute} para SKU {sku}")
                        messagebox.showerror("Error", f"El archivo de la etiqueta no existe: {qr_path_absolute}")
                        self.qr_label.configure(image=self.empty_image_photo, text="Etiqueta no encontrada")
                        self.qr_label.image = self.empty_image_photo
                        self.current_label_path = None
                else:
                    logger.error(f"No se pudo generar o encontrar etiqueta para SKU: {sku}")
                    messagebox.showerror("Error", "No se pudo generar o encontrar la etiqueta para el producto.")
                    self.qr_label.configure(image=self.empty_image_photo, text="Sin etiqueta")
                    self.qr_label.image = self.empty_image_photo
                    self.current_label_path = None

        except sqlite3.Error as e:
            logger.error(f"Error al consultar la base de datos para SKU {sku}: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"No se pudo consultar la base de datos: {str(e)}")
            self.clear_details()
        except Exception as e:
            logger.error(f"Error inesperado al mostrar detalles para SKU {sku}: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Error inesperado: {str(e)}")
            self.clear_details()

    def clear_details(self):
        for field, label in self.detail_labels.items():
            label.configure(text="")
        self.image_label.configure(image=self.empty_image_photo, text="Sin imagen")
        self.image_label.image = self.empty_image_photo
        self.qr_label.configure(image=self.empty_image_photo, text="Selecciona un producto")
        self.qr_label.image = self.empty_image_photo
        self.current_label_path = None

    def initialize_comboboxes(self):
        print("Inicializando comboboxes")
        logger.debug("Inicializando comboboxes para filtros")
        try:
            for column, combo in self.filter_combos.items():
                if not combo.winfo_exists():
                    logger.warning(f"Combobox para {column} no existe, omitiendo inicialización")
                    continue
                values = self.manager.get_unique_values(column)
                if column == "escuela":
                    values = [esc["nombre"] for esc in self.manager.db_manager.get_escuelas(self.store_id)]
                values = sorted(values) if column != "talla" else values
                logger.debug(f"Valores para {column}: {values}")
                if values:
                    combo.configure(values=values)
                else:
                    logger.warning(f"No se encontraron valores para {column}")
                    combo.configure(values=["Sin valores disponibles"])
            
            print("Comboboxes inicializados")
            logger.info("Comboboxes inicializados correctamente")
            self.update_active_filters_label()
        except Exception as e:
            print(f"Error al inicializar comboboxes: {str(e)}")
            logger.error(f"Error al inicializar comboboxes: %s", str(e), exc_info=True)
            messagebox.showerror("Error", f"No se pudieron inicializar los filtros: {str(e)}")

    def update_filter_comboboxes(self):
        print("Actualizando comboboxes de filtros")
        logger.debug("Actualizando comboboxes de filtros")
        try:
            self.initialize_comboboxes()
            print("Comboboxes de filtros actualizados")
            logger.info("Comboboxes de filtros actualizados correctamente")
        except Exception as e:
            print(f"Error al actualizar comboboxes de filtros: {str(e)}")
            logger.error(f"Error al actualizar comboboxes de filtros: %s", str(e), exc_info=True)
            messagebox.showerror("Error", f"No se pudieron actualizar los filtros: {str(e)}")

    def update_pagination_text(self, total_items, current_page, total_pages):
        try:
            logger.debug(f"Actualizando paginación: total_items={total_items}, current_page={current_page}, total_pages={total_pages}")
            if total_items == 0:
                self.page_label.configure(text="No hay productos")
                self.prev_ten_button.configure(state="disabled")
                self.prev_button.configure(state="disabled")
                self.next_button.configure(state="disabled")
                self.next_ten_button.configure(state="disabled")
            else:
                self.page_label.configure(text=f"Página {current_page + 1} de {total_pages}")
                self.prev_ten_button.configure(state="normal" if current_page >= 10 else "disabled")
                self.prev_button.configure(state="normal" if current_page > 0 else "disabled")
                self.next_button.configure(state="normal" if current_page < total_pages - 1 else "disabled")
                self.next_ten_button.configure(state="normal" if current_page + 10 < total_pages else "disabled")
            self.apply_row_styles()
            logger.debug(f"Texto de paginación actualizado: {self.page_label.cget('text')}")
        except Exception as e:
            logger.error(f"Error al actualizar texto de paginación: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"No se pudo actualizar la paginación: {str(e)}")

    def apply_row_styles(self):
        items_data = [self.tree.item(item, "values") for item in self.tree.get_children()]
        apply_treeview_styles(self.tree, items_data, inventory_column="inventario", low_inventory_threshold=5)

    def adjust_column_widths(self):
        available_width = self.manager.main_frame.winfo_width() - 800
        if available_width < 600:
            available_width = 600
        
        column_widths = {
            "sku": 120, "nombre": 220, "escuela": 100, "nivel_educativo": 80, "marca": 80,
            "color": 70, "tipo_prenda": 90, "tipo_pieza": 90, "ubicacion": 90, "escudo": 90,
            "talla": 60, "inventario": 60, "ventas": 60, "precio": 65
        }
        total_default_width = sum(column_widths.get(col, 100) for col in self.tree["columns"])
        
        if available_width > total_default_width:
            stretch_factor = available_width / total_default_width
            for col in self.tree["columns"]:
                new_width = max(int(column_widths.get(col, 100) * stretch_factor), 60)
                self.tree.column(col, width=new_width)
        else:
            for col in self.tree["columns"]:
                self.tree.column(col, width=column_widths.get(col, 100))

    def lock_interface(self, lock=True):
        state = "disabled" if lock else "normal"
        logger.debug(f"Lock interface called with lock={lock}, tree exists={hasattr(self, 'tree') and self.tree.winfo_exists()}")

        try:
            if hasattr(self, 'prev_ten_button') and self.prev_ten_button.winfo_exists():
                self.prev_ten_button.configure(state=state)
            if hasattr(self, 'prev_button') and self.prev_button.winfo_exists():
                self.prev_button.configure(state=state)
            if hasattr(self, 'next_button') and self.next_button.winfo_exists():
                self.next_button.configure(state=state)
            if hasattr(self, 'next_ten_button') and self.next_ten_button.winfo_exists():
                self.next_ten_button.configure(state=state)
            for combo in self.filter_combos.values():
                if combo.winfo_exists():
                    combo.configure(state=state)
            if hasattr(self, 'search_entry') and self.search_entry.winfo_exists():
                self.search_entry.configure(state=state)
            if hasattr(self, 'filter_button') and self.filter_button.winfo_exists():
                self.filter_button.configure(state=state)
            if hasattr(self, 'select_all_button') and self.select_all_button.winfo_exists():
                self.select_all_button.configure(state=state)
            if hasattr(self, 'deselect_all_button') and self.deselect_all_button.winfo_exists():
                self.deselect_all_button.configure(state=state)
            if hasattr(self, 'edit_button') and self.edit_button.winfo_exists():
                self.edit_button.configure(state=state)
            if hasattr(self, 'copy_button') and self.copy_button.winfo_exists():
                self.copy_button.configure(state=state)
            if hasattr(self, 'delete_button') and self.delete_button.winfo_exists():
                self.delete_button.configure(state=state)
            if hasattr(self, 'duplicate_button') and self.duplicate_button.winfo_exists():
                self.duplicate_button.configure(state=state)
            if hasattr(self, 'price_button') and self.price_button.winfo_exists():
                self.price_button.configure(state=state)
            if hasattr(self, 'print_button') and self.print_button.winfo_exists():
                self.print_button.configure(state=state)
            if hasattr(self, 'inventory_button') and self.inventory_button.winfo_exists():
                self.inventory_button.configure(state=state)
            if hasattr(self, 'copy_label_button') and self.copy_label_button.winfo_exists():
                self.copy_label_button.configure(state=state)

            if hasattr(self, 'tree') and self.tree.winfo_exists():
                if lock:
                    self.tree.unbind("<<TreeviewSelect>>")
                    self.tree.unbind("<Double-1>")
                else:
                    self.tree.bind("<<TreeviewSelect>>", lambda event: [self.update_selection_count(), self.manager.mostrar_detalle(event)])
                    self.tree.bind("<Double-1>", lambda event: self.manager.edit_product())
            else:
                logger.warning("El widget self.tree no existe o ha sido destruido. No se pueden vincular/desvincular eventos.")
        except tk.TclError as e:
            logger.warning(f"Error al configurar widgets en lock_interface: {str(e)}")

    def update_selection_count(self):
        selected_items = self.tree.selection()
        selected_count = len(selected_items)
        total_count = len(self.tree.get_children())
        self.selection_count_label.configure(text=f"Seleccionados: {selected_count}/{total_count}")
        visible_skus = [self.tree.item(item, "values")[0] for item in self.tree.get_children()]
        for sku in list(self.selection_state.keys()):
            if sku not in visible_skus:
                self.selection_state[sku] = False
        for item in selected_items:
            sku = self.tree.item(item, "values")[0]
            self.selection_state[sku] = True
        logger.debug(f"Conteo de selección actualizado: {selected_count}/{total_count}")

    def select_all(self):
        for item in self.tree.get_children():
            self.tree.selection_add(item)
            sku = self.tree.item(item, "values")[0]
            self.selection_state[sku] = True
        self.update_selection_count()

    def deselect_all(self):
        for item in self.tree.get_children():
            self.tree.selection_remove(item)
            sku = self.tree.item(item, "values")[0]
            self.selection_state[sku] = False
        self.tree.focus("")
        self.clear_filters()
        self.update_selection_count()

    def select_all_with_shortcut(self, event):
        self.select_all()
        return "break"

    def deselect_all_with_shortcut(self, event):
        self.deselect_all()
        return "break"

    def clear_filters(self):
        try:
            self.search_entry.delete(0, tk.END)
            cleared_columns = []
            for column, combo in self.filter_combos.items():
                if combo.winfo_exists():
                    combo.set([], skip_command=True)
                    combo.update_display_text()
                    cleared_columns.append(column)
            logger.info(f"Filtros limpiados para columnas: {', '.join(cleared_columns)}")
            self.manager.clear_filters()
            self.update_active_filters_label()
            self.manager.apply_filters()
        except Exception as e:
            logger.error("Error al limpiar filtros en la UI: %s", str(e), exc_info=True)
            messagebox.showerror("Error", f"No se pudieron limpiar los filtros en la interfaz: {str(e)}")

    def get_selected_filters(self, filter_name):
        combo = self.filter_combos.get(filter_name)
        if combo:
            return combo.get_selected()
        return []
