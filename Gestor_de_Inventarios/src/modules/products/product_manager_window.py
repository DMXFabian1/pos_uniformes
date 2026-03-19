import sqlite3
import tkinter as tk
import customtkinter as ctk
from src.modules.products.product_manager_ui import ProductManagerUI
from src.modules.products.product_manager_logic import ProductManagerLogic
from src.modules.products.file_manager import FileManager
from src.modules.products.inventory_manager import InventoryManager
from src.modules.products import QRGenerator
from src.core.config.config import CONFIG
from src.core.utils.tooltips import ToolTip
from tkinter import messagebox
import logging
import os
from PIL import Image, ImageWin
import win32print
import win32ui
import math

logger = logging.getLogger(__name__)

class ProductManagerWindow:
    def __init__(self, app, parent_frame, root, icons, store_id=1):
        self.app = app
        self.parent_frame = parent_frame
        self.root = self._validate_root(root)
        self.icons = self._validate_icons(icons)
        self.store_id = store_id

        self.user_id = getattr(app, 'user_id', "unknown_user")
        self.role = getattr(app, 'role', "unknown_role")
        self.root_folder = getattr(app, 'root_folder', CONFIG.get('ROOT_FOLDER', os.path.abspath(os.path.dirname(__file__))))
        self.tallas_personalizadas = getattr(app, 'tallas_personalizadas', [])
        self.db_manager = self._validate_db_manager(app)
        self.file_manager = FileManager(self.root_folder)
        logger.info(f"Inicializando ProductManagerWindow para usuario {self.user_id} con rol {self.role} en tienda {self.store_id}")

        self.setup_window()
        self.initialize_state()
        self.inventory_manager = InventoryManager(self.root_folder, self.db_manager, self, store_id=self.store_id)
        self.label_manager = QRGenerator(self.root_folder, self.db_manager, self, store_id=self.store_id)
        self.product_manager = ProductManagerLogic(self, store_id=self.store_id)
        self.ui = ProductManagerUI(self, store_id=self.store_id)
        self.setup_keybindings()
        self.setup_buttons()
        self.load_initial_data()
        logger.debug(f"Íconos recibidos: {list(self.icons.keys())}")

    def _validate_root(self, root):
        if not root:
            logger.error("Ventana raíz (root) no está definida")
            raise ValueError("La ventana raíz no está definida")
        return root

    def _validate_icons(self, icons):
        if not isinstance(icons, dict):
            logger.warning("Íconos no válidos, inicializando diccionario vacío")
            return {}
        return icons

    def _validate_db_manager(self, app):
        if not hasattr(app, 'db_manager') or app.db_manager is None:
            logger.error("db_manager no está definido en app")
            raise ValueError("El administrador de base de datos no está definido")
        return app.db_manager

    def setup_window(self):
        try:
            self.main_frame = ctk.CTkFrame(self.parent_frame, fg_color="#E6F0FA")
            self.main_frame.pack(fill="both", expand=True)
            logger.debug("Ventana configurada")
        except Exception as e:
            logger.error("Error al configurar ventana: %s", str(e))
            raise

    def initialize_state(self):
        self.selection_state = {}
        self.first_selected_item = None
        self.selection_anchor = None
        self.last_selected_sku = None
        self.current_page = 0
        self.page_size = 30
        self.total_pages = 0
        self.current_filters = {}
        self.sort_column = None
        self.sort_direction = "asc"
        self.columns = [
            "sku", "nombre", "nivel_educativo", "escuela", "color", "tipo_prenda", "tipo_pieza",
            "genero", "atributo", "ubicacion", "escudo", "marca", "talla", "inventario", "ventas", "precio"
        ]
        self.visible_columns = [
            "sku", "nombre", "escuela", "color", "tipo_prenda", "tipo_pieza", "genero", "talla", "inventario", "ventas", "precio"
        ]
        self.is_deleting = False
        self.current_label_path = None
        logger.debug("Estado inicializado")

    def setup_keybindings(self):
        try:
            self.ui.tree.bind("<Control-a>", self._handle_select_all)
            self.ui.tree.bind("<Control-c>", self._handle_copy_sku)
            self.ui.tree.bind("<Control-p>", self._handle_print_preview)
            self.ui.tree.bind("<Delete>", self._handle_delete_selection)
            logger.debug("Keybindings configurados")
        except AttributeError as e:
            logger.error("Error al configurar keybindings: %s", str(e))
            messagebox.showerror("Error", "No se pudieron configurar los atajos de teclado")

    def _handle_select_all(self, event):
        try:
            self.select_all()
            return "break"
        except Exception as e:
            logger.error("Error en select_all: %s", str(e))
            messagebox.showerror("Error", f"Error al seleccionar todos: {str(e)}")

    def _handle_copy_sku(self, event):
        try:
            self.product_manager.copy_sku()
            return "break"
        except Exception as e:
            logger.error("Error en copy_sku: %s", str(e))
            messagebox.showerror("Error", f"Error al copiar SKU: {str(e)}")

    def _handle_print_preview(self, event):
        try:
            self.ui.open_print_preview()
            return "break"
        except Exception as e:
            logger.error("Error en print_preview: %s", str(e))
            messagebox.showerror("Error", f"Error al abrir vista previa: {str(e)}")

    def _handle_delete_selection(self, event):
        try:
            self.product_manager.eliminar_seleccion()
            return "break"
        except Exception as e:
            logger.error("Error en delete_selection: %s", str(e))
            messagebox.showerror("Error", f"Error al eliminar selección: {str(e)}")

    def setup_buttons(self):
        try:
            button_frame = ctk.CTkFrame(self.main_frame, fg_color="#E6F0FA")
            button_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
            button_frame.grid_columnconfigure(0, weight=0)
            button_frame.grid_columnconfigure(1, weight=0)

            adjust_inventory_button = ctk.CTkButton(
                button_frame,
                text="Ajustar Inventario",
                command=self.inventory_manager.open_inventory_modification_window,
                fg_color="#32CD32",
                hover_color="#228B22",
                width=150,
                height=40,
                font=("Helvetica", 14),
                corner_radius=8
            )
            adjust_inventory_button.grid(row=0, column=0, padx=5, pady=5)
            ToolTip(adjust_inventory_button, "Ajusta el inventario de los productos seleccionados")

            modify_prices_button = ctk.CTkButton(
                button_frame,
                text="Modificar Precios",
                command=self.open_price_modification_window,
                fg_color="#4A90E2",
                hover_color="#2A6EBB",
                width=150,
                height=40,
                font=("Helvetica", 14),
                corner_radius=8
            )
            modify_prices_button.grid(row=0, column=1, padx=5, pady=5)
            ToolTip(modify_prices_button, "Modifica los precios de los productos seleccionados")

            logger.debug("Botones adicionales configurados")
        except Exception as e:
            logger.error("Error al configurar botones: %s", str(e))
            messagebox.showerror("Error", f"No se pudieron configurar los botones: {str(e)}")

    def load_initial_data(self):
        try:
            self.product_manager.cargar_productos()
            logger.debug("Datos iniciales cargados")
        except Exception as e:
            logger.error("Error al cargar datos iniciales: %s", str(e))
            messagebox.showerror("Error", "No se pudieron cargar los datos iniciales")

    def on_closing(self):
        try:
            if hasattr(self.ui, 'tree') and self.ui.tree.winfo_exists():
                self.ui.tree.unbind("<Control-a>")
                self.ui.tree.unbind("<Control-c>")
                self.ui.tree.unbind("<Control-p>")
                self.ui.tree.unbind("<Delete>")
            self.main_frame.pack_forget()
            self.main_frame.destroy()
            self.ui = None
            self.product_manager = None
            self.inventory_manager = None
            self.label_manager = None
            logger.debug("ProductManagerWindow cerrado y recursos limpiados")
        except Exception as e:
            logger.error("Error al cerrar ProductManagerWindow: %s", str(e))

    def select_all(self):
        try:
            for item in self.ui.tree.get_children():
                self.ui.tree.selection_add(item)
            self.ui.update_selection_count()
        except AttributeError as e:
            logger.error("Error al seleccionar todos: %s", str(e))
            messagebox.showerror("Error", "No se pudieron seleccionar los elementos")

    def copy_sku(self):
        self.product_manager.copy_sku()

    def lock_interface(self, lock=True):
        try:
            self.ui.lock_interface(lock)
        except AttributeError as e:
            logger.error("Error al bloquear/desbloquear interfaz: %s", str(e))

    def update_pagination_text(self, total_items, current_page, total_pages):
        try:
            self.ui.update_pagination_text(total_items, current_page, total_pages)
        except AttributeError as e:
            logger.error("Error al actualizar texto de paginación: %s", str(e))

    def get_unique_values(self, column):
        try:
            return self.product_manager.get_unique_values(column)
        except Exception as e:
            logger.error("Error al obtener valores únicos: %s", str(e))
            return []

    def prev_page(self):
        try:
            logger.debug(f"Navegando a la página anterior, página actual: {self.current_page}")
            self.product_manager.prev_page()
        except Exception as e:
            logger.error(f"Error al navegar a la página anterior: {str(e)}")
            messagebox.showerror("Error", f"No se pudo navegar a la página anterior: {str(e)}")

    def next_page(self):
        try:
            logger.debug(f"Navegando a la página siguiente, página actual: {self.current_page}")
            self.product_manager.next_page()
        except Exception as e:
            logger.error(f"Error al navegar a la página siguiente: {str(e)}")
            messagebox.showerror("Error", f"No se pudo navegar a la página siguiente: {str(e)}")

    def prev_ten_pages(self):
        try:
            logger.debug(f"Iniciando navegación a 10 páginas atrás, página actual: {self.current_page}, total páginas: {self.total_pages}")
            if self.current_page >= 10:
                self.current_page -= 10
                self.product_manager.cargar_productos()
                logger.info(f"Navegación exitosa a la página {self.current_page + 1}")
            else:
                self.current_page = 0
                self.product_manager.cargar_productos()
                logger.info(f"Navegación a la primera página (página 1)")
        except Exception as e:
            logger.error(f"Error al navegar a las 10 páginas anteriores: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"No se pudo navegar a las 10 páginas anteriores: {str(e)}")

    def next_ten_pages(self):
        try:
            logger.debug(f"Iniciando navegación a 10 páginas adelante, página actual: {self.current_page}, total páginas: {self.total_pages}")
            if self.current_page + 10 < self.total_pages:
                self.current_page += 10
                self.product_manager.cargar_productos()
                logger.info(f"Navegación exitosa a la página {self.current_page + 1}")
            else:
                self.current_page = self.total_pages - 1
                self.product_manager.cargar_productos()
                logger.info(f"Navegación a la última página (página {self.total_pages})")
        except Exception as e:
            logger.error(f"Error al navegar a las 10 páginas siguientes: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"No se pudo navegar a las 10 páginas siguientes: {str(e)}")

    def sort_by_column(self, column):
        self.product_manager.sort_by_column(column)

    def apply_quick_search(self, event=None):
        self.product_manager.apply_quick_search(event)

    def clear_filters(self):
        self.product_manager.clear_filters()

    def cargar_productos(self):
        try:
            logger.debug(f"Cargando productos para página {self.current_page + 1}")
            selected_items = self.ui.tree.selection()
            current_sku = None
            if selected_items:
                current_sku = self.ui.tree.item(selected_items[0])["values"][0].upper()
                logger.debug(f"SKU seleccionado antes de recargar: {current_sku}")

            self.product_manager.cargar_productos()

            if current_sku:
                for item in self.ui.tree.get_children():
                    if self.ui.tree.item(item)["values"][0].upper() == current_sku:
                        self.ui.tree.selection_set(item)
                        self.ui.tree.focus(item)
                        self.last_selected_sku = current_sku
                        logger.debug(f"Selección restaurada para SKU: {current_sku}")
                        break
                else:
                    logger.debug(f"No se encontró el SKU {current_sku} en la página actual")
                    self.last_selected_sku = None
                self.ui.mostrar_detalle(None)
            else:
                self.ui.tree.selection_remove(self.ui.tree.selection())
                self.last_selected_sku = None
                logger.debug("No había SKU seleccionado, selección limpiada")

        except Exception as e:
            logger.error("Error al cargar productos: %s", str(e))
            messagebox.showerror("Error", "No se pudieron cargar los productos")

    def apply_filters(self, event=None):
        self.product_manager.apply_filters(event)

    def eliminar_seleccion(self):
        self.product_manager.eliminar_seleccion()

    def duplicar_producto(self):
        self.product_manager.duplicar_producto()

    def edit_product(self):
        self.product_manager.edit_product()

    def copy_image_to_clipboard(self):
        self.label_manager.copy_image_to_clipboard()

    def print_labels(self, copies=1, add_to_inventory=False, label_type="standard"):
        selected_items = self.ui.tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "Selecciona un producto para imprimir etiquetas.")
            return
        if len(selected_items) > 1:
            messagebox.showwarning("Advertencia", "Selecciona solo un producto para imprimir etiquetas.")
            return

        sku = self.ui.tree.item(selected_items[0])["values"][0].upper()
        try:
            with self.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute("SELECT qr_path, label_split_path, inventario FROM productos WHERE sku = ? AND store_id = ?", (sku, self.store_id))
                result = cursor.fetchone()
                if not result or not (result[0] or result[1]):
                    messagebox.showerror("Error", f"No se encontró la etiqueta para el producto con SKU {sku}")
                    return

                qr_path = self.file_manager.get_absolute_path(result[0] if label_type == "standard" else result[1] if result[1] else result[0])
                current_inventory = result[2] or 0
                if not os.path.exists(qr_path):
                    messagebox.showerror("Error", f"La etiqueta para el producto con SKU {sku} no existe")
                    return

                printer_name = "Brother QL-800"
                printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
                logger.debug(f"Impresoras disponibles: {[p[2] for p in printers]}")
                if not any(printer_name in printer[2] for printer in printers):
                    messagebox.showerror("Error", f"La impresora {printer_name} no está disponible")
                    return

                # Calcular el número efectivo de etiquetas a imprimir
                effective_copies = copies
                if label_type == "split":
                    effective_copies = math.ceil(copies / 4)  # Cada etiqueta dividida tiene 4 códigos QR

                hprinter = None
                hdc = None
                try:
                    hprinter = win32print.OpenPrinter(printer_name)
                    printer_info = win32print.GetPrinter(hprinter, 2)
                    printer_status = printer_info['Status']
                    logger.debug(f"Estado de la impresora {printer_name}: {printer_status}")

                    hdc = win32ui.CreateDC()
                    hdc.CreatePrinterDC(printer_name)
                    image = Image.open(qr_path).convert("L").point(lambda x: 0 if x < 128 else 255, "1")
                    label_width, label_height = image.size
                    logger.debug(f"Tamaño de la etiqueta: {label_width}x{label_height}")

                    hdc.StartDoc("Label Print Job")
                    for i in range(effective_copies):
                        hdc.StartPage()
                        dib = ImageWin.Dib(image)
                        dib.draw(hdc.GetHandleOutput(), (0, 0, label_width, label_height))
                        hdc.EndPage()
                        logger.debug(f"Imprimiendo copia {i+1} de {effective_copies}")
                    hdc.EndDoc()
                    logger.info("Impresas %d etiquetas para SKU %s (tipo: %s, copias solicitadas: %d)", effective_copies, sku, label_type, copies)

                    if add_to_inventory:
                        # Actualizar inventario con la cantidad de copias solicitadas, no con effective_copies
                        new_inventory = current_inventory + copies
                        cursor.execute(
                            "UPDATE productos SET inventario = ? WHERE sku = ? AND store_id = ?",
                            (new_inventory, sku, self.store_id)
                        )
                        self.db_manager.commit()
                        logger.info("Inventario actualizado para SKU %s: %d -> %d", sku, current_inventory, new_inventory)
                        inventory_column = "inventario"
                        if inventory_column in self.ui.visible_columns:  # Check against visible_columns
                            for item in self.ui.tree.get_children():
                                try:
                                    if self.ui.tree.item(item)["values"][0].upper() == sku:
                                        values = list(self.ui.tree.item(item)["values"])
                                        # Use visible_columns to find the correct index
                                        values[self.ui.visible_columns.index(inventory_column)] = str(new_inventory)
                                        self.ui.tree.item(item, values=values)
                                        logger.debug(f"Treeview actualizado para SKU: {sku} con inventario: {new_inventory}")
                                        break
                                except tk.TclError:
                                    logger.warning(f"Item {item} no encontrado al actualizar Treeview")
                                    continue
                        else:
                            logger.warning(f"Columna 'inventario' no encontrada en self.ui.visible_columns, recargando productos")
                            self.cargar_productos()
                        self.last_selected_sku = sku
                        self.ui.tree.selection_remove(self.ui.tree.selection())
                        for item in self.ui.tree.get_children():
                            try:
                                if self.ui.tree.item(item)["values"][0].upper() == sku:
                                    self.ui.tree.selection_set(item)
                                    self.ui.tree.focus(item)
                                    self.ui.last_selected_sku = sku
                                    logger.debug(f"Selección restaurada después de actualizar inventario para SKU: {sku}")
                                    break
                            except tk.TclError:
                                logger.warning(f"Item {item} no encontrado al restaurar selección")
                                continue
                        else:
                            logger.debug(f"No se encontró el SKU {sku} en la página actual después de actualizar inventario")
                            self.last_selected_sku = None

                except win32ui.error as e:
                    logger.error("Error de win32ui al imprimir etiqueta para SKU %s: %s", sku, str(e))
                    if "no hay conexión activa" in str(e).lower():
                        logger.info("Ignorando error de conexión activa, impresión completada exitosamente")
                    else:
                        raise
                except Exception as e:
                    logger.error("Error inesperado al imprimir etiqueta para SKU %s: %s", sku, str(e), exc_info=True)
                    if isinstance(e, sqlite3.Error) and "No hay conexión activa" in str(e):
                        logger.info("Ignorando error de conexión activa en la base de datos, impresión completada exitosamente")
                    else:
                        raise
                finally:
                    if hdc:
                        try:
                            hdc.DeleteDC()
                            logger.debug("Contexto de dispositivo de impresora liberado")
                        except Exception as e:
                            logger.warning("Error al liberar contexto de dispositivo: %s", str(e))
                    if hprinter:
                        try:
                            win32print.ClosePrinter(hprinter)
                            logger.debug("Manejador de impresora cerrado")
                        except Exception as e:
                            logger.warning("Error al cerrar manejador de impresora: %s", str(e))

        except ImportError:
            logger.error("Librería pywin32 no encontrada")
            messagebox.showerror("Error", "Instala pywin32 con 'pip install pywin32'")
        except Exception as e:
            logger.error("Error al imprimir etiqueta para SKU %s: %s", sku, str(e), exc_info=True)
            if isinstance(e, sqlite3.Error) and "No hay conexión activa" in str(e):
                logger.info("Ignorando error de conexión activa en la base de datos, impresión completada exitosamente")
            else:
                raise

    def update_multiple_inventories(self):
        self.product_manager.update_multiple_inventories()

    def open_price_modification_window(self):
        try:
            selected_items = self.ui.tree.selection()
            current_sku = None
            if selected_items:
                current_sku = self.ui.tree.item(selected_items[0])["values"][0].upper()
                logger.debug(f"SKU seleccionado antes de abrir ventana de precios: {current_sku}")

            self.inventory_manager.open_price_modification_window()

            if current_sku:
                for item in self.ui.tree.get_children():
                    if self.ui.tree.item(item)["values"][0].upper() == current_sku:
                        self.ui.tree.selection_set(item)
                        self.ui.tree.focus(item)
                        self.last_selected_sku = current_sku
                        logger.debug(f"Selección restaurada para SKU: {current_sku} después de cerrar ventana de precios")
                        break
                else:
                    logger.debug(f"No se encontró el SKU {current_sku} en la página actual después de cerrar ventana de precios")
                    self.last_selected_sku = None
                self.ui.mostrar_detalle(None)
        except Exception as e:
            logger.error("Error al abrir ventana de modificación de precios: %s", str(e))
            messagebox.showerror("Error", f"No se pudo abrir la ventana de precios: {str(e)}")

    def update_selected_prices(self, value, selected_skus, mode="set"):
        self.inventory_manager.update_selected_prices(value, selected_skus, mode)

    def update_mass_prices(self, increment):
        self.inventory_manager.update_mass_prices(increment)

    def mostrar_detalle(self, event):
        try:
            self.ui.mostrar_detalle(event)
        except Exception as e:
            logger.error("Error al mostrar detalle: %s", str(e))
            messagebox.showerror("Error", "No se pudieron mostrar los detalles del producto")

def abrir_gestion_productos(app, parent_frame, store_id=1):
    try:
        return ProductManagerWindow(app, parent_frame, app.root, app.icons, store_id=store_id)
    except Exception as e:
        logger.error("Error al abrir ProductManagerWindow para tienda %d: %s", store_id, str(e))
        raise
