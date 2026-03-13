import sqlite3
import win32clipboard
import customtkinter as ctk
from tkinter import messagebox
import logging
import time
from src.core.utils.treeview_utils import apply_treeview_styles
from src.modules.products.product_service import ProductService
from src.modules.products.product_validator import ProductValidator
from src.modules.products.product_edit_form import ProductEditForm
from src.core.utils.tooltips import ToolTip
from src.core.utils.filter_cache import FilterCache
from src.core.utils.logging_config import setup_logging

logger = setup_logging()

class ProductManagerLogic:
    """
    Clase que maneja la lógica de negocio para la gestión de productos.
    """
    def __init__(self, manager, store_id=1):
        """
        Inicializa la lógica de gestión de productos.

        Args:
            manager (ProductManagerWindow): Instancia del administrador de ventana.
            store_id (int): ID de la tienda.
        """
        logger.info(f"Inicializando ProductManagerLogic para tienda {store_id}")
        self.manager = manager
        self.store_id = store_id
        self.root_folder = manager.root_folder
        self.service = ProductService(store_id, self.root_folder)
        self.validator = ProductValidator()
        self.edit_form = ProductEditForm(self.manager.root, self.service, self.validator, self.store_id)
        self.filter_cache = FilterCache()
        self.selection_state = manager.selection_state
        self.first_selected_item = manager.first_selected_item
        self.selection_anchor = manager.selection_anchor
        self.last_selected_sku = manager.last_selected_sku
        self.page_size = manager.page_size
        self.current_filters = manager.current_filters
        self.sort_column = manager.sort_column
        self.sort_direction = manager.sort_direction
        self.columns = manager.columns
        self.visible_columns = manager.visible_columns
        self.is_deleting = manager.is_deleting
        self.current_label_path = manager.current_label_path
        self.search_after_id = None
        self.cached_total_items = None
        self.cached_total_pages = None
        self.cached_filters = None

    def get_unique_values(self, column):
        """
        Obtiene los valores únicos para una columna, usando caché.

        Args:
            column (str): Columna de la cual obtener valores únicos.

        Returns:
            list: Lista de valores únicos.
        """
        try:
            start_time = time.time()
            values = self.filter_cache.get(
                column,
                lambda: self.service.get_unique_values(
                    column,
                    custom_tallas=getattr(self.manager, 'tallas_personalizadas', [])
                )
            )
            logger.debug(f"Obtenidos {len(values)} valores únicos para {column} en {time.time() - start_time:.3f}s")
            return values
        except Exception as e:
            logger.error(f"Error al obtener valores únicos para {column}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo cargar los valores de {column}: {str(e)}")
            return []

    def update_filters(self):
        """
        Actualiza los filtros basados en los valores seleccionados en la interfaz.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            self.current_filters = {
                "search": self.manager.ui.search_entry.get().strip().upper(),
                "escuela": self.manager.ui.get_selected_filters("escuela"),
                "nivel_educativo": self.manager.ui.get_selected_filters("nivel_educativo"),
                "color": self.manager.ui.get_selected_filters("color"),
                "tipo_prenda": self.manager.ui.get_selected_filters("tipo_prenda"),
                "tipo_pieza": self.manager.ui.get_selected_filters("tipo_pieza"),
                "genero": self.manager.ui.get_selected_filters("genero"),
                "atributo": self.manager.ui.get_selected_filters("atributo"),
                "marca": self.manager.ui.get_selected_filters("marca"),
                "talla": self.manager.ui.get_selected_filters("talla")
            }
        except AttributeError as e:
            logger.error(f"Error al actualizar filtros: {str(e)}")
            messagebox.showerror("Error", "No se pudieron actualizar los filtros")
        except Exception as e:
            logger.error(f"Error inesperado al actualizar filtros: {str(e)}")
            messagebox.showerror("Error", f"Error al actualizar filtros: {str(e)}")

    def apply_quick_search(self, event=None):
        """
        Aplica la búsqueda rápida con un retraso para evitar múltiples consultas.

        Args:
            event (tk.Event, optional): Evento que desencadena la acción.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            if self.search_after_id is not None:
                self.manager.root.after_cancel(self.search_after_id)
            self.search_after_id = self.manager.root.after(300, self._perform_quick_search)
        except Exception as e:
            logger.error(f"Error al programar búsqueda rápida: {str(e)}")
            messagebox.showerror("Error", f"No se pudo programar la búsqueda rápida: {str(e)}")

    def _perform_quick_search(self):
        """
        Realiza la búsqueda rápida y carga los productos correspondientes.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            self.manager.current_page = 0
            self.selection_anchor = None
            self.update_filters()
            search_text = self.current_filters.get("search", "").strip()
            if len(search_text) >= 6:
                product = self.service.repository.get_product(search_text.upper())
                if product:
                    self.current_filters["exact_sku"] = search_text
                    self.cargar_productos()
                    for item in self.manager.ui.tree.get_children():
                        if self.manager.ui.tree.item(item)["values"][0].upper() == search_text.upper():
                            self.manager.ui.tree.selection_set(item)
                            self.manager.ui.tree.focus(item)
                            self.manager.ui.tree.see(item)
                            self.manager.ui.update_selection_count()
                            self.manager.ui.mostrar_detalle(None)
                            return
            self.cargar_productos()
        except Exception as e:
            logger.error(f"Error en búsqueda rápida: {str(e)}")
            messagebox.showerror("Error", f"No se pudo realizar la búsqueda: {str(e)}")

    def apply_filters(self, event=None):
        """
        Aplica los filtros seleccionados y carga los productos.

        Args:
            event (tk.Event, optional): Evento que desencadena la acción.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            self.manager.current_page = 0
            self.current_filters.pop("exact_sku", None)
            self.update_filters()
            self.selection_anchor = None
            self.cargar_productos()
        except Exception as e:
            logger.error(f"Error al aplicar filtros: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron aplicar los filtros: {str(e)}")

    def clear_filters(self):
        """
        Limpia los filtros y recarga los productos.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            self.manager.current_page = 0
            self.current_filters = {
                "search": "",
                "escuela": [], "nivel_educativo": [], "color": [], "tipo_prenda": [],
                "tipo_pieza": [], "genero": [], "atributo": [], "marca": [], "talla": []
            }
            self.sort_column = None
            self.sort_direction = "asc"
            self.selection_anchor = None
            self.cached_total_items = None
            self.cached_total_pages = None
            self.cached_filters = None
            self.cargar_productos()
            logger.info("Filtros limpiados y productos recargados")
        except Exception as e:
            logger.error(f"Error al limpiar filtros: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron limpiar los filtros: {str(e)}")

    def cancel_pending_search(self):
        """
        Cancela una búsqueda rápida pendiente.
        """
        try:
            if self.search_after_id is not None:
                self.manager.root.after_cancel(self.search_after_id)
                self.search_after_id = None
        except Exception as e:
            logger.error(f"Error al cancelar búsqueda pendiente: {str(e)}")

    def prev_page(self):
        """
        Navega a la página anterior de productos.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            if self.manager.current_page > 0:
                self.manager.current_page -= 1
                self.selection_anchor = None
                self.cargar_productos()
        except Exception as e:
            logger.error(f"Error al navegar a página anterior: {str(e)}")
            messagebox.showerror("Error", f"No se pudo navegar a la página anterior: {str(e)}")

    def next_page(self):
        """
        Navega a la página siguiente de productos.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            if self.manager.total_pages > 0 and self.manager.current_page < self.manager.total_pages - 1:
                self.manager.current_page += 1
                self.selection_anchor = None
                self.cargar_productos()
        except Exception as e:
            logger.error(f"Error al navegar a página siguiente: {str(e)}")
            messagebox.showerror("Error", f"No se pudo navegar a la página siguiente: {str(e)}")

    def sort_by_column(self, column):
        """
        Ordena los productos por la columna especificada.

        Args:
            column (str): Columna por la cual ordenar.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            if self.sort_column == column:
                self.sort_direction = "desc" if self.sort_direction == "asc" else "asc"
            else:
                self.sort_column = column
                self.sort_direction = "asc"
            self.selection_anchor = None
            self.cargar_productos()
        except Exception as e:
            logger.error(f"Error al ordenar por columna {column}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo ordenar por {column}: {str(e)}")

    def cargar_productos(self, batch_size=None):
        """
        Carga los productos en la interfaz con paginación, filtros y ordenamiento.

        Args:
            batch_size (int, optional): Número de productos a cargar por lote.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            start_time = time.time()
            self.manager.ui.lock_interface(True)
            selected_skus = [sku for sku, selected in self.selection_state.items() if selected]
            effective_batch_size = batch_size if batch_size is not None else self.page_size

            logger.debug(f"Cargando productos para página {self.manager.current_page + 1}, batch_size={effective_batch_size}")

            if batch_size is None:
                self.manager.ui.tree.delete(*self.manager.ui.tree.get_children())

            productos, total_items, total_pages, page = self.service.load_products(
                self.manager.current_page, effective_batch_size, self.current_filters,
                self.sort_column, self.sort_direction
            )
            self.manager.current_page = page
            self.cached_total_items = total_items
            self.cached_filters = self.current_filters.copy()
            self.manager.total_pages = total_pages

            if total_items == 0:
                self.manager.ui.tree.insert("", "end", values=[""] * len(self.manager.ui.tree["columns"]))
                self.manager.total_pages = 0
                self.manager.current_page = 0
                self.manager.update_pagination_text(total_items, self.manager.current_page, self.manager.total_pages)
                self.manager.ui.prev_ten_button.configure(state="disabled")
                self.manager.ui.prev_button.configure(state="disabled")
                self.manager.ui.next_button.configure(state="disabled")
                self.manager.ui.next_ten_button.configure(state="disabled")
                self.manager.ui.update_selection_count()
                logger.info(f"No se encontraron productos, tiempo: {time.time() - start_time:.3f}s")
                return

            self.manager.total_pages = total_pages
            self.manager.current_page = min(max(0, self.manager.current_page), self.manager.total_pages - 1)
            self.cached_total_pages = self.manager.total_pages
            self.manager.update_pagination_text(total_items, self.manager.current_page, self.manager.total_pages)

            if not productos:
                self.manager.ui.tree.insert("", "end", values=[""] * len(self.manager.ui.tree["columns"]))
            else:
                items_to_insert = []
                for idx, producto in enumerate(productos):
                    sku = producto[0]
                    values = [
                        producto[0], producto[1], producto[2], producto[3] or "", producto[4],
                        producto[5], producto[6], producto[7], producto[8], producto[9],
                        producto[10], producto[11], producto[12], producto[13], producto[14],
                        f"{producto[15]:.2f}" if producto[15] is not None else "0.00"
                    ]
                    filtered_values = [values[self.columns.index(col)] for col in self.visible_columns]
                    items_to_insert.append(filtered_values)
                    if sku not in self.selection_state:
                        self.selection_state[sku] = False

                apply_treeview_styles(self.manager.ui.tree, items_to_insert, inventory_column="inventario", low_inventory_threshold=5)

                item_map = {self.manager.ui.tree.item(item)["values"][0]: item for item in self.manager.ui.tree.get_children()}
                for sku in selected_skus:
                    if sku in item_map:
                        self.manager.ui.tree.selection_add(item_map[sku])
                        self.selection_state[sku] = True
                        if sku == selected_skus[0]:
                            self.manager.ui.tree.see(item_map[sku])
                            self.manager.ui.tree.focus(item_map[sku])

            self.manager.ui.update_selection_count()
            logger.info(f"Cargados {len(productos)} productos, página {self.manager.current_page + 1}, total páginas: {self.manager.total_pages}, tiempo: {time.time() - start_time:.3f}s")
        except Exception as e:
            logger.error(f"Error al cargar productos: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron cargar los productos: {str(e)}")
        finally:
            if hasattr(self.manager, 'ui') and self.manager.ui is not None:
                self.manager.ui.lock_interface(False)

    def copy_sku(self):
        """
        Copia los SKUs seleccionados al portapapeles.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            selected_items = self.manager.ui.tree.selection()
            if not selected_items:
                messagebox.showwarning("Advertencia", "Selecciona al menos un producto")
                return
            skus = [self.manager.ui.tree.item(item)["values"][0].upper() for item in selected_items]
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(", ".join(skus))
            win32clipboard.CloseClipboard()
            logger.info(f"Copiados {len(skus)} SKUs al portapapeles")
            messagebox.showinfo("Éxito", "SKU(s) copiados al portapapeles")
        except Exception as e:
            logger.error(f"Error al copiar SKUs: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron copiar los SKUs: {str(e)}")

    def eliminar_seleccion(self):
        """
        Elimina los productos seleccionados.
        """
        if self.is_deleting:
            return
        self.is_deleting = True

        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            selected_items = self.manager.ui.tree.selection()
            if not selected_items:
                messagebox.showwarning("Advertencia", "Selecciona al menos un producto para eliminar")
                return
            skus = [self.manager.ui.tree.item(item)["values"][0].upper() for item in selected_items]
            if not messagebox.askyesno("Confirmar", f"¿Estás seguro de eliminar {len(skus)} producto(s)?"):
                return

            self.manager.ui.delete_button.configure(state="disabled")
            self.manager.ui.tree.unbind("<<TreeviewSelect>>")
            self.manager.ui.tree.unbind("<Double-1>")

            deleted_count = self.service.delete_products(skus)
            for sku in skus:
                self.selection_state.pop(sku, None)

            self.selection_anchor = None
            for column in ["escuela", "color", "talla", "tipo_prenda", "tipo_pieza", "genero", "atributo", "marca"]:
                self.filter_cache.invalidate(column=column)
            self.cached_filters = None
            self.cached_total_items = None
            self.cached_total_pages = None
            self.cargar_productos()
            logger.info(f"Eliminados {deleted_count} producto(s)")
            messagebox.showinfo("Éxito", f"{deleted_count} producto(s) eliminado(s)")
        except sqlite3.IntegrityError as e:
            logger.error(f"Error de integridad al eliminar productos: {str(e)}")
            messagebox.showerror("Error", "No se pueden eliminar productos porque están referenciados en otras tablas")
        except Exception as e:
            logger.error(f"Error al eliminar productos: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron eliminar los productos: {str(e)}")
        finally:
            self.is_deleting = False
            if hasattr(self.manager, 'ui') and self.manager.ui is not None:
                self.manager.ui.delete_button.configure(state="normal")
                self.manager.ui.tree.bind("<<TreeviewSelect>>", lambda event: [self.manager.ui.update_selection_count(), self.manager.mostrar_detalle(event)])
                self.manager.ui.tree.bind("<Double-1>", lambda event: self.manager.edit_product())

    def duplicar_producto(self):
        """
        Duplica el producto seleccionado.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            selected_items = self.manager.ui.tree.selection()
            if not selected_items:
                messagebox.showwarning("Advertencia", "Selecciona un producto para duplicar")
                return
            if len(selected_items) > 1:
                messagebox.showwarning("Advertencia", "Selecciona solo un producto para duplicar")
                return

            item = selected_items[0]
            sku = self.manager.ui.tree.item(item, "values")[0]
            if not messagebox.askyesno("Confirmar", f"¿Estás seguro de duplicar el producto con SKU {sku}?"):
                return

            new_sku = self.service.duplicate_product(sku)
            self.selection_anchor = None
            for column in ["escuela", "color", "talla", "tipo_prenda", "tipo_pieza", "genero", "atributo", "marca"]:
                self.filter_cache.invalidate(column=column)
            self.cached_filters = None
            self.cached_total_items = None
            self.cached_total_pages = None
            self.cargar_productos()
            logger.info(f"Producto duplicado con nuevo SKU: {new_sku}")
            messagebox.showinfo("Éxito", f"Producto duplicado con nuevo SKU: {new_sku}")
        except ValueError as e:
            messagebox.showwarning("Advertencia", str(e))
        except Exception as e:
            logger.error(f"Error al duplicar producto con SKU {sku}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo duplicar el producto: {str(e)}")

    def edit_product(self):
        """
        Abre la ventana de edición para el producto seleccionado.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            selected_items = self.manager.ui.tree.selection()
            if not selected_items:
                messagebox.showwarning("Advertencia", "Selecciona un producto para editar")
                return
            if len(selected_items) > 1:
                messagebox.showwarning("Advertencia", "Selecciona solo un producto para editar")
                return

            sku = self.manager.ui.tree.item(selected_items[0])["values"][0].upper()
            self.edit_form.edit_product(
                sku,
                getattr(self.manager, 'tallas_personalizadas', []),
                self.manager.label_manager,
                lambda: self._on_save_callback()
            )
        except Exception as e:
            logger.error(f"Error al abrir edición de producto: {str(e)}")
            messagebox.showerror("Error", f"No se pudo abrir la ventana de edición: {str(e)}")

    def _on_save_callback(self):
        """
        Callback para recargar productos después de guardar.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            for column in ["escuela", "color", "talla", "tipo_prenda", "tipo_pieza", "genero", "atributo", "marca"]:
                self.filter_cache.invalidate(column=column)
            self.cached_filters = None
            self.cached_total_items = None
            self.cached_total_pages = None
            self.selection_anchor = None
            self.cargar_productos()
            logger.info("Productos recargados tras guardar cambios")
        except Exception as e:
            logger.error(f"Error en callback de guardado: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron recargar los productos: {str(e)}")

    def update_multiple_inventories(self):
        """
        Abre la ventana para actualizar los inventarios de los productos seleccionados.
        """
        try:
            if not hasattr(self.manager, 'ui') or self.manager.ui is None:
                raise AttributeError("Interfaz 'manager.ui' no disponible")
            selected_items = self.manager.ui.tree.selection()
            if not selected_items:
                messagebox.showwarning("Advertencia", "Selecciona al menos un producto para actualizar el inventario")
                return

            skus = [self.manager.ui.tree.item(item)["values"][0].upper() for item in selected_items]
            update_window = ctk.CTkToplevel(self.manager.root)
            update_window.title("Actualizar Inventarios")
            update_window.geometry("600x500")
            update_window.configure(fg_color="#F5F7FA")
            update_window.transient(self.manager.root)
            update_window.grab_set()

            def on_window_close():
                update_window.destroy()

            update_window.protocol("WM_DELETE_WINDOW", on_window_close)

            canvas = ctk.CTkCanvas(update_window, bg="#F5F7FA", highlightthickness=0)
            scrollbar = ctk.CTkScrollbar(update_window, orientation="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=15, pady=15)
            scrollbar.pack(side="right", fill="y")

            content_frame = ctk.CTkFrame(canvas, fg_color="#FFFFFF", corner_radius=10, border_width=1, border_color="#A3BFFA")
            canvas.create_window((0, 0), window=content_frame, anchor="nw")

            ctk.CTkLabel(content_frame, text=f"Actualizar Inventarios ({len(skus)} Productos)",
                         font=("Helvetica", 16, "bold"), text_color="#1A2E5A").grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="w")

            summary_frame = ctk.CTkFrame(content_frame, fg_color="#E6F0FA", corner_radius=5)
            summary_frame.grid(row=1, column=0, columnspan=2, padx=15, pady=5, sticky="ew")
            ctk.CTkLabel(summary_frame, text="Productos Seleccionados:", font=("Helvetica", 12, "bold"),
                         text_color="#1A2E5A").grid(row=0, column=0, padx=10, pady=5, sticky="w")
            summary_text = ", ".join(skus[:5]) + ("..." if len(skus) > 5 else "")
            ctk.CTkLabel(summary_frame, text=summary_text, font=("Helvetica", 11), text_color="#333333",
                         wraplength=550).grid(row=1, column=0, padx=10, pady=2, sticky="w")

            mode_var = ctk.StringVar(value="unique")
            mode_frame = ctk.CTkFrame(content_frame, fg_color="#E6F0FA", corner_radius=5)
            mode_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=5, sticky="ew")
            ctk.CTkLabel(mode_frame, text="Modo de Actualización:", font=("Helvetica", 12, "bold"),
                         text_color="#1A2E5A").grid(row=0, column=0, padx=10, pady=5, sticky="w")
            ctk.CTkRadioButton(mode_frame, text="Valor Único (mismo inventario para todos)", variable=mode_var,
                               value="unique", font=("Helvetica", 12)).grid(row=1, column=0, padx=10, pady=5, sticky="w")
            ctk.CTkRadioButton(mode_frame, text="Valores Individuales (diferente inventario por producto)",
                               variable=mode_var, value="individual", font=("Helvetica", 12)).grid(row=2, column=0, padx=10, pady=5, sticky="w")

            input_frame = ctk.CTkFrame(content_frame, fg_color="#E6F0FA", corner_radius=5, border_width=1, border_color="#A3BFFA")
            input_frame.grid(row=3, column=0, columnspan=2, padx=15, pady=10, sticky="ew")
            input_frame.grid_columnconfigure(0, weight=0)
            input_frame.grid_columnconfigure(1, weight=1)

            entries = {}
            validation_status = {}

            def update_input_fields():
                for widget in input_frame.winfo_children():
                    widget.destroy()
                entries.clear()
                validation_status.clear()

                if mode_var.get() == "unique":
                    ctk.CTkLabel(input_frame, text="Inventario Único:", font=("Helvetica", 12)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
                    single_entry = ctk.CTkEntry(input_frame, placeholder_text="Ej: 10", width=200)
                    single_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
                    ToolTip(single_entry, "Ingresa el valor de inventario para todos los productos seleccionados")
                    entries["single"] = single_entry
                    validation_status["single"] = True
                    single_entry.bind("<KeyRelease>", lambda e: validate_entry(single_entry, "Inventario Único", "single"))
                else:
                    ctk.CTkLabel(input_frame, text="Inventarios Individuales:", font=("Helvetica", 12, "bold"),
                                 text_color="#1A2E5A").grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="w")
                    for i, sku in enumerate(skus):
                        ctk.CTkLabel(input_frame, text=f"SKU {sku}:", font=("Helvetica", 12)).grid(row=i+1, column=0, padx=5, pady=5, sticky="e")
                        entry = ctk.CTkEntry(input_frame, placeholder_text="Ej: 10", width=200)
                        entry.grid(row=i+1, column=1, padx=5, pady=5, sticky="w")
                        ToolTip(entry, f"Ingresa el nuevo inventario para el producto {sku}")
                        entries[sku] = entry
                        validation_status[sku] = True
                        entry.bind("<KeyRelease>", lambda e, ent=entry, s=sku: validate_entry(ent, f"Inventario SKU {s}", s))

                update_save_button_state()

            def validate_entry(entry, field_name, key):
                value = entry.get().strip()
                is_valid, error_msg = self.validator.validate_numeric(value, field_name, entry, allow_negative=False)
                validation_status[key] = is_valid
                if not is_valid and value:
                    messagebox.showwarning("Advertencia", error_msg)
                update_save_button_state()

            def update_save_button_state():
                all_valid = all(validation_status.values())
                save_button.configure(state="normal" if all_valid else "disabled")

            mode_var.trace("w", lambda *args: update_input_fields())
            update_input_fields()

            def save_multiple_inventories():
                try:
                    inventory_updates = {}
                    if mode_var.get() == "unique":
                        is_valid, num = self.validator.validate_numeric(entries["single"].get(), "Inventario Único", allow_negative=False)
                        if not is_valid:
                            messagebox.showwarning("Advertencia", num)
                            return
                        single_value = int(num) if num is not None else 0
                        for sku in skus:
                            inventory_updates[sku] = single_value
                    else:
                        for sku in skus:
                            is_valid, num = self.validator.validate_numeric(entries[sku].get(), f"Inventario SKU {sku}", allow_negative=False)
                            if not is_valid:
                                messagebox.showwarning("Advertencia", num)
                                return
                            inventory_updates[sku] = int(num) if num is not None else 0

                    updated_count = self.service.update_inventories(inventory_updates)
                    self.filter_cache.invalidate(column="inventario")
                    self.cached_filters = None
                    self.cached_total_items = None
                    self.cached_total_pages = None
                    self.cargar_productos()
                    logger.info(f"Actualizado inventario para {updated_count} producto(s)")
                    messagebox.showinfo("Éxito", f"Inventario actualizado para {updated_count} producto(s)")
                    update_window.destroy()
                except Exception as e:
                    logger.error(f"Error al actualizar inventarios: {str(e)}")
                    messagebox.showerror("Error", f"No se pudo actualizar el inventario: {str(e)}")

            button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            button_frame.grid(row=4, column=0, columnspan=2, pady=15, sticky="ew")
            button_frame.grid_columnconfigure(0, weight=1)
            button_frame.grid_columnconfigure(1, weight=1)

            save_button = ctk.CTkButton(button_frame, text="Actualizar", command=save_multiple_inventories,
                                        fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
                                        font=("Helvetica", 12), width=120, state="normal")
            save_button.grid(row=0, column=0, padx=15)
            ToolTip(save_button, "Actualiza el inventario de los productos seleccionados")

            cancel_button = ctk.CTkButton(button_frame, text="Cancelar", command=on_window_close,
                                          fg_color="#A9A9A9", hover_color="#8B8B8B", corner_radius=8,
                                          font=("Helvetica", 12), width=120)
            cancel_button.grid(row=0, column=1, padx=15)
            ToolTip(cancel_button, "Cancela y cierra la ventana")

            content_frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

            def on_mouse_scroll(event):
                if canvas.winfo_exists() and canvas.winfo_containing(event.x_root, event.y_root) == canvas:
                    canvas.yview_scroll(int(-event.delta / 120), "units")

            canvas.bind_all("<MouseWheel>", on_mouse_scroll)
        except Exception as e:
            logger.error(f"Error al abrir ventana de actualización de inventarios: {str(e)}")
            messagebox.showerror("Error", f"No se pudo abrir la ventana de inventarios: {str(e)}")