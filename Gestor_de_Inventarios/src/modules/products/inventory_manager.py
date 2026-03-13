import sqlite3
import logging
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from src.core.utils.tooltips import ToolTip

logger = logging.getLogger(__name__)

class InventoryManager:
    """
    Clase para gestionar la modificación de inventarios y precios de productos.
    """
    def __init__(self, root_folder, db_manager, manager, store_id=1):
        """
        Inicializa el administrador de inventario.

        Args:
            root_folder (str): Carpeta raíz para archivos.
            db_manager (DatabaseManager): Administrador de base de datos.
            manager (ProductManagerWindow): Administrador de la ventana de productos.
            store_id (int): ID de la tienda.
        """
        self.root_folder = root_folder
        self.db_manager = db_manager
        self.manager = manager
        self.store_id = store_id
        logger.info("InventoryManager inicializado para tienda %d", store_id)

    def validate_numeric_input(self, value, field_name, widget=None, allow_negative=False):
        """
        Valida una entrada numérica y actualiza el estilo del widget.

        Args:
            value (str): Valor a validar.
            field_name (str): Nombre del campo para mensajes de error.
            widget (ctk.CTkEntry, optional): Widget a actualizar.
            allow_negative (bool): Si se permiten valores negativos.

        Returns:
            tuple: (bool, float or None) - (Éxito de la validación, Valor numérico o mensaje de error).
        """
        try:
            if not value.strip():
                if widget:
                    widget.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
                return True, None
            num = float(value)
            if not allow_negative and num < 0:
                if widget:
                    widget.configure(fg_color="#FFE6E6", border_color="#FF5555")
                logger.warning("Valor negativo no permitido para %s: %s", field_name, value)
                return False, f"El campo {field_name} no puede ser negativo"
            if widget:
                widget.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
            logger.debug("Validación numérica exitosa para %s: %s", field_name, num)
            return True, num
        except ValueError:
            if widget:
                widget.configure(fg_color="#FFE6E6", border_color="#FF5555")
            logger.warning("Valor inválido para %s: %s", field_name, value)
            return False, f"El campo {field_name} debe ser un número válido"

    def open_inventory_modification_window(self):
        """
        Abre una ventana modal para modificar el inventario de los productos seleccionados.
        """
        try:
            selected_items = self.manager.ui.tree.selection()
            if not selected_items:
                logger.warning("No se seleccionaron productos para modificar inventario")
                messagebox.showwarning("Advertencia", "Selecciona al menos un producto para modificar el inventario")
                return

            selected_skus = [self.manager.ui.tree.item(item)["values"][0].upper() for item in selected_items]
            inventory_window = ctk.CTkToplevel(self.manager.root)
            inventory_window.title("Modificar Inventario")
            inventory_window.geometry("500x400")
            inventory_window.configure(fg_color="#F5F7FA")
            inventory_window.transient(self.manager.root)
            inventory_window.grab_set()
            logger.debug("Ventana de modificación de inventario creada")

            def on_window_close():
                inventory_window.destroy()
                logger.debug("Ventana de inventario cerrada")

            inventory_window.protocol("WM_DELETE_WINDOW", on_window_close)

            ctk.CTkLabel(inventory_window, text=f"Modificar Inventario ({len(selected_skus)} Productos)",
                         font=("Helvetica", 16, "bold"), text_color="#1A2E5A").pack(pady=10)

            summary_frame = ctk.CTkFrame(inventory_window, fg_color="#E6F0FA", corner_radius=5)
            summary_frame.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(summary_frame, text="Productos Seleccionados:", font=("Helvetica", 12, "bold"),
                         text_color="#1A2E5A").pack(anchor="w", padx=10, pady=5)
            summary_text = ", ".join(selected_skus[:5]) + ("..." if len(selected_skus) > 5 else "")
            ctk.CTkLabel(summary_frame, text=summary_text, font=("Helvetica", 11), text_color="#333333",
                         wraplength=450).pack(anchor="w", padx=10, pady=2)

            value_frame = ctk.CTkFrame(inventory_window, fg_color="transparent")
            value_frame.pack(fill="x", padx=20, pady=10)
            ctk.CTkLabel(value_frame, text="Nuevo Inventario:", font=("Helvetica", 12)).pack(side="left", padx=5)
            value_entry = ctk.CTkEntry(value_frame, placeholder_text="Ej: 10", width=150)
            value_entry.pack(side="left", padx=5)
            # Forzar el foco después de que la ventana esté renderizada
            inventory_window.after(100, lambda: value_entry.focus_set())
            ToolTip(value_entry, "Ingresa el nuevo valor de inventario para los productos seleccionados")

            def on_value_change(event):
                is_valid, _ = self.validate_numeric_input(value_entry.get(), "Inventario", value_entry, allow_negative=False)
                apply_button.configure(state="normal" if is_valid else "disabled")

            value_entry.bind("<KeyRelease>", on_value_change)

            button_frame = ctk.CTkFrame(inventory_window, fg_color="transparent")
            button_frame.pack(fill="x", padx=20, pady=20)
            apply_button = ctk.CTkButton(button_frame, text="Aplicar",
                                         command=lambda: self.update_selected_inventory(value_entry.get(), selected_skus),
                                         fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
                                         font=("Helvetica", 12), width=120, state="disabled")
            apply_button.pack(side="left", padx=10)
            ToolTip(apply_button, "Aplica el nuevo inventario a los productos seleccionados")
            ctk.CTkButton(button_frame, text="Cancelar", command=on_window_close,
                          fg_color="#FF6F61", hover_color="#E55B50", corner_radius=8,
                          font=("Helvetica", 12), width=120).pack(side="left", padx=10)
            ToolTip(button_frame.winfo_children()[-1], "Cancela y cierra la ventana")
        except Exception as e:
            logger.error("Error al abrir ventana de modificación de inventario: %s", str(e))
            messagebox.showerror("Error", f"No se pudo abrir la ventana: {str(e)}")

    def update_selected_inventory(self, value, selected_skus):
        """
        Actualiza el inventario de los productos seleccionados.

        Args:
            value (str): Nuevo valor de inventario.
            selected_skus (list): Lista de SKUs seleccionados.
        """
        try:
            is_valid, num = self.validate_numeric_input(value, "Inventario", allow_negative=False)
            if not is_valid:
                logger.warning("Inventario inválido: %s", value)
                messagebox.showwarning("Advertencia", num)
                return
            new_inventory = int(num) if num is not None else 0

            with self.db_manager as db:
                cursor = db.get_cursor()
                updated_count = 0
                for sku in selected_skus:
                    cursor.execute("SELECT inventario FROM productos WHERE sku = ? AND store_id = ?",
                                  (sku, self.store_id))
                    result = cursor.fetchone()
                    if not result:
                        logger.warning("No se encontró el producto con SKU %s", sku)
                        continue
                    old_inventory = result[0] or 0
                    cursor.execute("UPDATE productos SET inventario = ? WHERE sku = ? AND store_id = ?",
                                  (new_inventory, sku, self.store_id))
                    updated_count += cursor.rowcount
                    logger.info("Inventario actualizado para SKU %s: %s -> %s", sku, old_inventory, new_inventory)

                self.db_manager.commit()
                logger.debug("Actualizados %d productos", updated_count)

            if hasattr(self.manager.product_manager, 'cached_filters'):
                self.manager.product_manager.cached_filters = None
                self.manager.product_manager.cached_total_items = None
                self.manager.product_manager.cached_total_pages = None
            self.manager.cargar_productos()
            messagebox.showinfo("Éxito", f"Inventario actualizado para {updated_count} producto(s)")
        except sqlite3.Error as e:
            logger.error("Error al actualizar inventario: %s", str(e))
            messagebox.showerror("Error", f"No se pudo actualizar el inventario: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al actualizar inventario: %s", str(e))
            messagebox.showerror("Error", f"No se pudo actualizar el inventario: {str(e)}")

    def open_price_modification_window(self):
        """
        Abre una ventana modal para modificar los precios de los productos seleccionados.
        """
        try:
            selected_items = self.manager.ui.tree.selection()
            if not selected_items:
                logger.warning("No se seleccionaron productos para modificar precios")
                messagebox.showwarning("Advertencia", "Selecciona al menos un producto para modificar el precio")
                return

            selected_skus = [self.manager.ui.tree.item(item)["values"][0].upper() for item in selected_items]
            price_window = ctk.CTkToplevel(self.manager.root)
            price_window.title("Modificar Precios")
            price_window.geometry("500x400")
            price_window.configure(fg_color="#F5F7FA")
            price_window.transient(self.manager.root)
            price_window.grab_set()
            logger.debug("Ventana de modificación de precios creada")

            def on_window_close():
                price_window.destroy()
                logger.debug("Ventana de precios cerrada")

            price_window.protocol("WM_DELETE_WINDOW", on_window_close)

            ctk.CTkLabel(price_window, text=f"Modificar Precios ({len(selected_skus)} Productos)",
                         font=("Helvetica", 16, "bold"), text_color="#1A2E5A").pack(pady=10)

            summary_frame = ctk.CTkFrame(price_window, fg_color="#E6F0FA", corner_radius=5)
            summary_frame.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(summary_frame, text="Productos Seleccionados:", font=("Helvetica", 12, "bold"),
                         text_color="#1A2E5A").pack(anchor="w", padx=10, pady=5)
            summary_text = ", ".join(selected_skus[:5]) + ("..." if len(selected_skus) > 5 else "")
            ctk.CTkLabel(summary_frame, text=summary_text, font=("Helvetica", 11), text_color="#333333",
                         wraplength=450).pack(anchor="w", padx=10, pady=2)

            mode_frame = ctk.CTkFrame(price_window, fg_color="transparent")
            mode_frame.pack(fill="x", padx=20, pady=5)
            mode_var = tk.StringVar(value="set")
            ctk.CTkRadioButton(mode_frame, text="Establecer Precio", variable=mode_var, value="set",
                               font=("Helvetica", 12)).pack(side="left", padx=10)
            ctk.CTkRadioButton(mode_frame, text="Aumentar/Disminuir", variable=mode_var, value="adjust",
                               font=("Helvetica", 12)).pack(side="left", padx=10)

            value_frame = ctk.CTkFrame(price_window, fg_color="transparent")
            value_frame.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(value_frame, text="Valor:", font=("Helvetica", 12)).pack(side="left", padx=5)
            value_entry = ctk.CTkEntry(value_frame, placeholder_text="Ej: 100.00 o -10.00", width=150)
            value_entry.pack(side="left", padx=5)
            # Forzar el foco después de que la ventana esté renderizada
            price_window.after(100, lambda: value_entry.focus_set())
            ToolTip(value_entry, "Ingresa el valor del precio (positivo para establecer/aumentar, negativo para disminuir)")

            def on_value_change(event):
                allow_negative = mode_var.get() == "adjust"
                is_valid, _ = self.validate_numeric_input(value_entry.get(), "Valor", value_entry, allow_negative=allow_negative)
                apply_button.configure(state="normal" if is_valid else "disabled")

            value_entry.bind("<KeyRelease>", on_value_change)

            button_frame = ctk.CTkFrame(price_window, fg_color="transparent")
            button_frame.pack(fill="x", padx=20, pady=20)
            apply_button = ctk.CTkButton(button_frame, text="Aplicar",
                                         command=lambda: self.update_selected_prices(value_entry.get(), selected_skus, mode_var.get()),
                                         fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
                                         font=("Helvetica", 12), width=120, state="disabled")
            apply_button.pack(side="left", padx=10)
            ToolTip(apply_button, "Aplica los cambios de precio a los productos seleccionados")
            ctk.CTkButton(button_frame, text="Cancelar", command=on_window_close,
                          fg_color="#FF6F61", hover_color="#E55B50", corner_radius=8,
                          font=("Helvetica", 12), width=120).pack(side="left", padx=10)
            ToolTip(button_frame.winfo_children()[-1], "Cancela y cierra la ventana")
        except Exception as e:
            logger.error("Error al abrir ventana de modificación de precios: %s", str(e))
            messagebox.showerror("Error", f"No se pudo abrir la ventana: {str(e)}")

    def update_selected_prices(self, value, selected_skus, mode="set"):
        """
        Actualiza los precios de los productos seleccionados.

        Args:
            value (str): Valor para establecer o ajustar el precio.
            selected_skus (list): Lista de SKUs seleccionados.
            mode (str): Modo de actualización ("set" o "adjust").
        """
        try:
            is_valid, num = self.validate_numeric_input(value, "Precio", allow_negative=(mode == "adjust"))
            if not is_valid:
                logger.warning("Precio inválido: %s", value)
                messagebox.showwarning("Advertencia", num)
                return
            value = num if num is not None else 0.0

            with self.db_manager as db:
                cursor = db.get_cursor()
                updated_count = 0
                for sku in selected_skus:
                    cursor.execute("SELECT precio FROM productos WHERE sku = ? AND store_id = ?",
                                  (sku, self.store_id))
                    result = cursor.fetchone()
                    if not result:
                        logger.warning("No se encontró el producto con SKU %s", sku)
                        continue
                    current_price = result[0] or 0.0
                    new_price = value if mode == "set" else current_price + value
                    if new_price < 0:
                        new_price = 0
                    cursor.execute("UPDATE productos SET precio = ? WHERE sku = ? AND store_id = ?",
                                  (new_price, sku, self.store_id))
                    updated_count += cursor.rowcount
                    logger.info("Precio actualizado para SKU %s: %s -> %s", sku, current_price, new_price)

                self.db_manager.commit()
                logger.debug("Actualizados %d productos", updated_count)

            if hasattr(self.manager.product_manager, 'cached_filters'):
                self.manager.product_manager.cached_filters = None
                self.manager.product_manager.cached_total_items = None
                self.manager.product_manager.cached_total_pages = None
            self.manager.cargar_productos()
            messagebox.showinfo("Éxito", f"Precios actualizados para {updated_count} producto(s)")
        except sqlite3.Error as e:
            logger.error("Error al actualizar precios: %s", str(e))
            messagebox.showerror("Error", f"No se pudo actualizar los precios: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al actualizar precios: %s", str(e))
            messagebox.showerror("Error", f"No se pudo actualizar los precios: {str(e)}")

    def update_mass_prices(self, increment):
        """
        Actualiza los precios de todos los productos aplicando un incremento.

        Args:
            increment (str): Valor del incremento.
        """
        try:
            increment = float(increment)
            with self.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute("UPDATE productos SET precio = CASE WHEN precio + ? < 0 THEN 0 ELSE precio + ? END WHERE store_id = ?",
                              (increment, increment, self.store_id))
                updated_count = cursor.rowcount
                self.db_manager.commit()
                logger.info("Precios ajustados masivamente: incremento de %s, %d productos afectados", increment, updated_count)

            if hasattr(self.manager.product_manager, 'cached_filters'):
                self.manager.product_manager.cached_filters = None
                self.manager.product_manager.cached_total_items = None
                self.manager.product_manager.cached_total_pages = None
            self.manager.cargar_productos()
            messagebox.showinfo("Éxito", f"Precios ajustados masivamente para {updated_count} producto(s)")
        except ValueError:
            logger.warning("Incremento inválido: %s", increment)
            messagebox.showerror("Error", "Ingresa un valor numérico válido para el incremento")
        except sqlite3.Error as e:
            logger.error("Error al ajustar precios masivamente: %s", str(e))
            messagebox.showerror("Error", f"No se pudo ajustar los precios masivamente: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al ajustar precios masivamente: %s", str(e))
            messagebox.showerror("Error", f"No se pudo ajustar los precios masivamente: {str(e)}")