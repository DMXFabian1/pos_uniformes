import customtkinter as ctk
from tkinter import ttk, messagebox
import logging
import json
import os
import webbrowser
from src.core.config.config import CONFIG
from src.ui.ui_utils import mostrar_ventana_seleccion

logger = logging.getLogger(__name__)

class ApartadosActions:
    def __init__(self, root, db_manager, logic, ui, data, store_id=1):
        self.root = root
        self.db_manager = db_manager
        self.logic = logic
        self.ui = ui
        self.data = data
        self.store_id = store_id
        logger.info(f"ApartadosActions inicializado para tienda {self.store_id}")

    # --- Métodos de utilidades ---

    def _create_dialog(self, title, geometry):
        """Crea un diálogo CTkToplevel y asegura que se cierre correctamente."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(title)
        dialog.geometry(geometry)
        dialog.transient(self.root)
        dialog.grab_set()

        original_destroy = dialog.destroy
        def custom_destroy():
            dialog.grab_release()
            original_destroy()
        dialog.destroy = custom_destroy

        return dialog

    def _show_success_dialog(self, title, message, receipt_path=None):
        """Muestra un diálogo de éxito estandarizado."""
        success_dialog = self._create_dialog(title, "400x200")
        ctk.CTkLabel(success_dialog, text=message, wraplength=350).pack(pady=10)
        if receipt_path:
            ctk.CTkButton(
                success_dialog,
                text="Abrir Comprobante",
                command=lambda: webbrowser.open(f"file://{os.path.abspath(receipt_path)}")
            ).pack(pady=10)
        ctk.CTkButton(success_dialog, text="Cerrar", command=success_dialog.destroy).pack(pady=10)

    def _get_selected_apartado(self):
        """Obtiene los datos del apartado seleccionado en el Treeview."""
        selected = self.ui.tree.selection()
        if not selected:
            messagebox.showinfo("Selección", "Seleccione un apartado para realizar esta acción.")
            return None
        item = self.ui.tree.item(selected[0])
        return {
            "id": item['values'][0],
            "cliente_nombre": item['values'][1],
            "anticipo": item['values'][3],
            "estado": item['values'][9],
            "saldo_pendiente": float(item['values'][5].replace('$', ''))
        }

    def _build_confirm_dialog(self, title, message, confirm_callback, extra_widgets=None):
        """Construye un diálogo de confirmación genérico."""
        dialog = self._create_dialog(title, "500x400")
        ctk.CTkLabel(dialog, text=message, wraplength=450).pack(pady=10)
        if extra_widgets:
            for widget in extra_widgets:
                widget.pack(pady=10)

        ctk.CTkButton(dialog, text="Confirmar", command=lambda: [confirm_callback(), dialog.destroy()]).pack(pady=10)
        ctk.CTkButton(dialog, text="Cerrar", command=dialog.destroy).pack(pady=10)
        return dialog

    # --- Validaciones ---

    def _validate_apartado_selection(self, apartado_data):
        """Valida que se haya seleccionado un apartado."""
        if not apartado_data:
            return False
        return True

    def _validate_apartado_active(self, apartado_data):
        """Valida que el apartado esté en estado activo."""
        if apartado_data['estado'] != "activo":
            messagebox.showerror("Error", f"El apartado ID {apartado_data['id']} no puede procesarse porque su estado es '{apartado_data['estado']}'.")
            return False
        return True

    # --- Acciones principales ---

    def completar_apartado(self):
        """Completa un apartado seleccionado."""
        apartado_data = self._get_selected_apartado()
        if not self._validate_apartado_selection(apartado_data) or not self._validate_apartado_active(apartado_data):
            return

        try:
            confirm_message, productos, anticipo, total, saldo_pendiente = self._build_completar_confirm_message(apartado_data)
            if not messagebox.askyesno("Confirmar", confirm_message):
                return

            metodo_pago = self._handle_completar_payment(saldo_pendiente)
            result = self.logic.completar_apartado(apartado_data['id'], metodo_pago or "Anticipo Completo", 0)

            if result["success"]:
                msg = f"Apartado ID {apartado_data['id']} completado exitosamente.\n"
                msg += f"Venta registrada con ID: {result['venta_id']}.\nSe generó un comprobante de venta."
                self._show_success_dialog("Completación Exitosa", msg, result.get("receipt_path"))
                self.data.cargar_apartados_paginated(page=1)
                logger.info(f"Apartado completado: ID {apartado_data['id']}, Venta ID: {result['venta_id']}, Comprobante: {result.get('receipt_path')}, Tienda: {self.store_id}")
            else:
                messagebox.showerror("Error", result["message"])
                logger.error(f"Error al completar apartado: {result['message']}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo completar el apartado: {str(e)}")
            logger.error(f"Error al completar apartado: {str(e)}")

    def _build_completar_confirm_message(self, apartado_data):
        """Construye el mensaje de confirmación para completar un apartado."""
        cursor = self.db_manager.get_cursor()
        cursor.execute("SELECT id_cliente, productos, anticipo FROM apartados WHERE id = ? AND estado = 'activo' AND store_id = ?", (apartado_data['id'], self.store_id))
        apartado = cursor.fetchone()
        if not apartado:
            raise ValueError("El apartado no se encuentra o no está activo.")

        productos = json.loads(apartado['productos'])
        anticipo = float(apartado['anticipo'])
        subtotal = sum(item['precio'] * item['cantidad'] for item in productos)
        total = subtotal
        saldo_pendiente = total - anticipo

        confirm_message = f"Confirmar Completar Apartado ID {apartado_data['id']}\n\n"
        confirm_message += f"Cliente: {apartado_data['cliente_nombre']}\n"
        confirm_message += f"Productos:\n"
        for item in productos:
            confirm_message += f"- {item['sku']} (x{item['cantidad']}) - ${item['precio']:.2f}\n"
        confirm_message += f"\nSubtotal: ${subtotal:.2f}\n"
        confirm_message += f"Total: ${total:.2f}\n"
        confirm_message += f"Anticipo: ${anticipo:.2f}\n"
        confirm_message += f"Saldo Pendiente: ${saldo_pendiente:.2f}\n\n"

        if saldo_pendiente <= 0:
            confirm_message += "El anticipo cubre el total. No se requiere método de pago.\n\n"
        confirm_message += "¿Desea completar el apartado?"
        return confirm_message, productos, anticipo, total, saldo_pendiente

    def _handle_completar_payment(self, saldo_pendiente):
        """Maneja la selección del método de pago para completar un apartado."""
        if saldo_pendiente <= 0:
            return None

        dialog = self._create_dialog("Completar Apartado", "300x200")
        ctk.CTkLabel(dialog, text="Método de Pago (Opcional):").pack(pady=5)
        metodo_var = ctk.StringVar()
        metodo_menu = ctk.CTkOptionMenu(dialog, values=CONFIG["METODOS_PAGO"], variable=metodo_var)
        metodo_menu.pack(pady=5)

        metodo_pago = [None]
        def confirmar():
            metodo_pago[0] = metodo_var.get() or "No especificado"
            dialog.destroy()

        ctk.CTkButton(dialog, text="Confirmar", command=confirmar).pack(pady=10)
        dialog.wait_window()
        return metodo_pago[0]

    def cancelar_apartado(self):
        """Cancela un apartado seleccionado."""
        apartado_data = self._get_selected_apartado()
        if not self._validate_apartado_selection(apartado_data) or not self._validate_apartado_active(apartado_data):
            return

        try:
            cancel_data = self.logic.cancelar_apartado(apartado_data['id'])
            reembolsar_var = ctk.BooleanVar(value=False)
            extra_widgets = [ctk.CTkCheckBox(self.root, text="Registrar reembolso del anticipo", variable=reembolsar_var)] if cancel_data["anticipo"] > 0 else []

            def confirmar():
                result = self.logic.confirmar_cancelacion(apartado_data['id'], reembolsar_anticipo=reembolsar_var.get())
                if result["success"]:
                    msg = f"Apartado ID {apartado_data['id']} cancelado exitosamente.\nSe generó un comprobante de cancelación."
                    self._show_success_dialog("Cancelación Exitosa", msg, result.get("receipt_path"))
                    self.data.cargar_apartados_paginated(page=1)
                    logger.info(f"Apartado cancelado: ID {apartado_data['id']}, Comprobante: {result.get('receipt_path')}, Tienda: {self.store_id}")
                else:
                    messagebox.showerror("Error", result["message"])
                    logger.error(f"Error al cancelar apartado: {result['message']}")

            self._build_confirm_dialog(
                f"Cancelar Apartado ID {apartado_data['id']}",
                cancel_data["confirm_message"],
                confirmar,
                extra_widgets
            )
        except (ValueError, Exception) as e:
            messagebox.showerror("Error", f"No se pudo cancelar el apartado: {str(e)}")
            logger.error(f"Error al cancelar apartado: {str(e)}")

    def extender_apartado(self):
        """Extiende la fecha de vencimiento de un apartado."""
        apartado_data = self._get_selected_apartado()
        if not self._validate_apartado_selection(apartado_data) or not self._validate_apartado_active(apartado_data):
            return

        try:
            extension_data = self.logic.extender_apartado(apartado_data['id'])
            def confirmar():
                self.logic.confirmar_extension(
                    apartado_data['id'],
                    extension_data["nueva_fecha_vencimiento"],
                    extension_data["fecha_modificacion"]
                )
                messagebox.showinfo("Éxito", f"Apartado ID {apartado_data['id']} extendido hasta {extension_data['nueva_fecha_vencimiento']}.")
                self.data.cargar_apartados_paginated(page=1)
                logger.info(f"Apartado extendido: ID {apartado_data['id']}, Tienda: {self.store_id}")

            self._build_confirm_dialog(
                f"Extender Apartado ID {apartado_data['id']}",
                extension_data["confirm_message"],
                confirmar
            )
        except (ValueError, Exception) as e:
            messagebox.showerror("Error", f"No se pudo extender el apartado: {str(e)}")
            logger.error(f"Error al extender apartado: {str(e)}")

    def agregar_anticipo(self):
        """Registra un anticipo para un apartado."""
        apartado_data = self._get_selected_apartado()
        if not self._validate_apartado_selection(apartado_data) or not self._validate_apartado_active(apartado_data):
            return

        result = self._prompt_anticipo_amount(apartado_data)
        if result is None:
            return

        monto, metodo_pago = result
        try:
            anticipo_data = self.logic.registrar_anticipo(apartado_data['id'], monto)
            def confirmar():
                receipt_path = self.logic.confirmar_anticipo(
                    apartado_data['id'],
                    anticipo_data["monto"],
                    anticipo_data["nuevo_anticipo"],
                    anticipo_data["fecha_modificacion"],
                    anticipo_data["nueva_fecha_vencimiento"]
                )
                msg = f"Anticipo de ${monto:.2f} registrado para el apartado ID {apartado_data['id']}.\nSe generó un comprobante.\nMétodo de pago: {metodo_pago}"
                self._show_success_dialog("Anticipo Registrado", msg, receipt_path)
                self.data.cargar_apartados_paginated(page=1)
                logger.info(f"Anticipo registrado para apartado: ID {apartado_data['id']}, Comprobante: {receipt_path}, Tienda: {self.store_id}")

            self._build_confirm_dialog(
                f"Confirmar Anticipo para Apartado ID {apartado_data['id']}",
                anticipo_data["confirm_message"],
                confirmar
            )
        except (ValueError, Exception) as e:
            messagebox.showerror("Error", f"No se pudo registrar el anticipo: {str(e)}")
            logger.error(f"Error al registrar anticipo: {str(e)}")

    def _prompt_anticipo_amount(self, apartado_data):
        """Solicita el monto y método de pago del anticipo al usuario con una interfaz mejorada."""
        dialog = self._create_dialog("Agregar Anticipo", "450x450")

        main_frame = ctk.CTkFrame(dialog)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        ctk.CTkLabel(main_frame, text=f"Apartado ID: {apartado_data['id']}", font=("Arial", 14, "bold")).pack(pady=(0, 5))
        ctk.CTkLabel(main_frame, text=f"Cliente: {apartado_data['cliente_nombre']}").pack(pady=(0, 10))

        anticipos = self.logic.obtener_anticipos(apartado_data['id'], store_id=self.store_id)
        ctk.CTkLabel(main_frame, text="Historial de Anticipos (Últimos 3):").pack(pady=(0, 5))
        historial_textbox = ctk.CTkTextbox(main_frame, height=80, width=400, wrap="word")
        historial_textbox.pack(pady=(0, 10))
        if anticipos:
            historial = "\n".join([f"- ${a['monto']:.2f} el {a['fecha']}" for a in anticipos[-3:]])
        else:
            historial = "No hay anticipos registrados."
        historial_textbox.insert("1.0", historial)
        historial_textbox.configure(state="disabled")

        ctk.CTkLabel(main_frame, text=f"Saldo Pendiente: ${apartado_data['saldo_pendiente']:.2f}").pack(pady=(0, 10))

        ctk.CTkLabel(main_frame, text="Monto del Anticipo *:").pack(pady=(0, 5))
        entry_monto = ctk.CTkEntry(main_frame, width=200)
        entry_monto.pack(pady=(0, 5))
        ctk.CTkLabel(main_frame, text="El monto debe ser positivo y no exceder el saldo pendiente.", font=("Arial", 10), text_color="gray").pack(pady=(0, 5))

        ctk.CTkLabel(main_frame, text="Método de Pago *:").pack(pady=(0, 5))
        metodo_var = ctk.StringVar(value="Seleccione un método")
        metodo_menu = ctk.CTkOptionMenu(main_frame, values=CONFIG["METODOS_PAGO"], variable=metodo_var)
        metodo_menu.pack(pady=(0, 10))

        error_label = ctk.CTkLabel(main_frame, text="", text_color="red", wraplength=400)
        error_label.pack(pady=(0, 10))

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=10)
        confirm_button = ctk.CTkButton(button_frame, text="Confirmar", state="disabled")
        confirm_button.pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Limpiar", command=lambda: self._reset_anticipo_form(entry_monto, metodo_var, error_label, confirm_button)).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Cancelar", command=dialog.destroy).pack(side="right", padx=5)

        monto = [None]
        def validate_anticipo_amount(event=None):
            try:
                value = entry_monto.get().strip()
                metodo = metodo_var.get()

                if not value:
                    error_label.configure(text="El monto es obligatorio.")
                    confirm_button.configure(state="disabled")
                    return
                monto[0] = float(value)
                if monto[0] <= 0:
                    error_label.configure(text="El monto debe ser positivo.")
                    confirm_button.configure(state="disabled")
                    return
                if monto[0] > apartado_data['saldo_pendiente']:
                    error_label.configure(text=f"El monto no puede exceder el saldo pendiente (${apartado_data['saldo_pendiente']:.2f}).")
                    confirm_button.configure(state="disabled")
                    return
                if metodo == "Seleccione un método":
                    error_label.configure(text="Seleccione un método de pago.")
                    confirm_button.configure(state="disabled")
                    return

                error_label.configure(text="")
                confirm_button.configure(state="normal")
            except ValueError:
                error_label.configure(text="El monto debe ser un número válido.")
                confirm_button.configure(state="disabled")
                monto[0] = None

        def confirmar():
            if monto[0] is not None and metodo_var.get() != "Seleccione un método":
                dialog.destroy()

        entry_monto.bind("<KeyRelease>", validate_anticipo_amount)
        metodo_var.trace("w", lambda *args: validate_anticipo_amount())
        confirm_button.configure(command=confirmar)
        dialog.wait_window()
        return monto[0], metodo_var.get() if monto[0] is not None else None

    def _reset_anticipo_form(self, entry_monto, metodo_var, error_label, confirm_button):
        """Resetea el formulario de anticipo a su estado inicial."""
        entry_monto.delete(0, "end")
        metodo_var.set("Seleccione un método")
        error_label.configure(text="")
        confirm_button.configure(state="disabled")

    def modificar_productos(self):
        """Modifica los productos de un apartado."""
        apartado_data = self._get_selected_apartado()
        if not self._validate_apartado_selection(apartado_data) or not self._validate_apartado_active(apartado_data):
            return

        dialog, productos_actuales = self._setup_modificar_dialog(apartado_data['id'])
        if not dialog:
            return

        search_frame, productos_frame, productos_container, productos_entries, label_subtotal, label_saldo = self._setup_modificar_widgets(dialog)
        self._populate_productos(productos_actuales, productos_container, productos_entries, label_subtotal, label_saldo)

        self._setup_search_productos(search_frame, productos_container, productos_entries, label_subtotal, label_saldo)
        self._setup_modificar_buttons(productos_frame, apartado_data['id'], productos_entries, productos_actuales, label_subtotal, label_saldo)

        ctk.CTkButton(dialog, text="Confirmar", command=lambda: self._confirmar_modificacion(apartado_data['id'], productos_entries, productos_actuales, dialog)).pack(pady=10)

    def _setup_modificar_dialog(self, apartado_id):
        """Configura el diálogo principal para modificar productos."""
        try:
            cursor = self.db_manager.get_cursor()
            cursor.execute("SELECT productos FROM apartados WHERE id = ? AND estado = 'activo' AND store_id = ?", (apartado_id, self.store_id))
            apartado = cursor.fetchone()
            if not apartado:
                messagebox.showerror("Error", "El apartado no se encuentra o no está activo.")
                return None, None

            productos_actuales = json.loads(apartado['productos'])
            dialog = self._create_dialog("Modificar Productos", "800x600")
            return dialog, productos_actuales
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar los productos: {str(e)}")
            logger.error(f"Error al configurar diálogo de modificación: {str(e)}")
            return None, None

    def _setup_modificar_widgets(self, dialog):
        """Configura los widgets principales del diálogo de modificación."""
        search_frame = ctk.CTkFrame(dialog)
        search_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(search_frame, text="Buscar Producto (SKU/Nombre):").pack(side="left", padx=5)
        entry_search = ctk.CTkEntry(search_frame, width=200)
        entry_search.pack(side="left", padx=5)

        productos_frame = ctk.CTkFrame(dialog)
        productos_frame.pack(fill="both", expand=True, padx=10, pady=5)
        ctk.CTkLabel(productos_frame, text="Productos:", font=("Arial", 14)).pack(anchor="w", padx=5)

        productos_container = ctk.CTkFrame(productos_frame)
        productos_container.pack(fill="both", expand=True, padx=5, pady=5)
        productos_entries = []

        vista_previa_frame = ctk.CTkFrame(productos_frame)
        vista_previa_frame.pack(fill="x", padx=5, pady=5)
        label_subtotal = ctk.CTkLabel(vista_previa_frame, text="Subtotal: $0.00")
        label_subtotal.pack(side="left", padx=5)
        label_saldo = ctk.CTkLabel(vista_previa_frame, text="Saldo Pendiente: $0.00")
        label_saldo.pack(side="left", padx=5)

        return search_frame, productos_frame, productos_container, productos_entries, label_subtotal, label_saldo

    def _populate_productos(self, productos_actuales, productos_container, productos_entries, label_subtotal, label_saldo):
        """Carga los productos actuales en el diálogo de modificación."""
        for producto in productos_actuales:
            self._add_producto_row(productos_container, productos_entries, label_subtotal, label_saldo, producto['sku'], producto['cantidad'])

    def _add_producto_row(self, productos_container, productos_entries, label_subtotal, label_saldo, sku="", cantidad=1):
        """Agrega una fila de producto al diálogo de modificación."""
        frame = ctk.CTkFrame(productos_container)
        frame.pack(fill="x", pady=2)
        ctk.CTkLabel(frame, text="SKU:").pack(side="left", padx=5)
        entry_sku = ctk.CTkEntry(frame, width=100)
        entry_sku.pack(side="left", padx=5)
        if sku:
            entry_sku.insert(0, sku)
        ctk.CTkLabel(frame, text="Nombre:").pack(side="left", padx=5)
        label_nombre = ctk.CTkLabel(frame, text="N/A", width=150, anchor="w")
        label_nombre.pack(side="left", padx=5)
        ctk.CTkLabel(frame, text="Precio:").pack(side="left", padx=5)
        label_precio = ctk.CTkLabel(frame, text="$0.00", width=80, anchor="w")
        label_precio.pack(side="left", padx=5)
        ctk.CTkLabel(frame, text="Cantidad:").pack(side="left", padx=5)
        entry_cantidad = ctk.CTkEntry(frame, width=50)
        entry_cantidad.pack(side="left", padx=5)
        entry_cantidad.insert(0, str(cantidad))

        stock_label = ctk.CTkLabel(frame, text="Stock: N/A", text_color="gray")
        stock_label.pack(side="left", padx=5)

        def validar_producto(event=None):
            sku_val = entry_sku.get().strip()
            try:
                cantidad_val = int(entry_cantidad.get())
                if sku_val:
                    cursor = self.db_manager.get_cursor()
                    cursor.execute("SELECT nombre, precio, inventario FROM productos WHERE sku = ? AND store_id = ?", (sku_val, self.store_id))
                    producto = cursor.fetchone()
                    if producto:
                        cursor.execute("SELECT productos FROM apartados WHERE id = ? AND store_id = ?", (self._get_selected_apartado()['id'], self.store_id))
                        productos_actuales = json.loads(cursor.fetchone()['productos'])
                        stock_base = producto['inventario']
                        cantidad_apartada = next((item['cantidad'] for item in productos_actuales if item['sku'] == sku_val), 0)
                        stock_disponible = stock_base + cantidad_apartada
                        nombre = producto['nombre']
                        precio = producto['precio']
                        label_nombre.configure(text=nombre)
                        label_precio.configure(text=f"${precio:.2f}")
                        stock_label.configure(text=f"Stock: {stock_disponible}", text_color="green" if stock_disponible >= cantidad_val else "red")
                    else:
                        label_nombre.configure(text="N/A")
                        label_precio.configure(text="$0.00")
                        stock_label.configure(text="Stock: SKU no encontrado", text_color="red")
                else:
                    label_nombre.configure(text="N/A")
                    label_precio.configure(text="$0.00")
                    stock_label.configure(text="Stock: N/A", text_color="gray")
            except ValueError:
                stock_label.configure(text="Stock: Cantidad inválida", text_color="red")
            self._update_vista_previa(productos_entries, label_subtotal, label_saldo)

        entry_sku.bind("<KeyRelease>", validar_producto)
        entry_cantidad.bind("<KeyRelease>", validar_producto)

        ctk.CTkButton(frame, text="Eliminar", command=lambda: frame.destroy(), fg_color="#F44336").pack(side="right", padx=5)
        productos_entries.append((frame, entry_sku, entry_cantidad, label_precio))
        validar_producto()

    def _update_vista_previa(self, productos_entries, label_subtotal, label_saldo):
        """Actualiza la vista previa del subtotal y saldo pendiente."""
        productos_nuevos = []
        cursor = self.db_manager.get_cursor()
        for frame, entry_sku, entry_cantidad, label_precio in productos_entries:
            sku = entry_sku.get().strip()
            try:
                cantidad = int(entry_cantidad.get())
                if not sku:
                    continue
                cursor.execute("SELECT precio FROM productos WHERE sku = ? AND store_id = ?", (sku, self.store_id))
                producto = cursor.fetchone()
                if not producto:
                    continue
                cursor.execute("SELECT productos FROM apartados WHERE id = ? AND store_id = ?", (self._get_selected_apartado()['id'], self.store_id))
                productos_actuales = json.loads(cursor.fetchone()['productos'])
                precio = next((p['precio'] for p in productos_actuales if p['sku'] == sku), producto['precio'])
                productos_nuevos.append({
                    "sku": sku,
                    "cantidad": cantidad,
                    "precio": precio
                })
            except ValueError:
                continue
        subtotal = sum(item['precio'] * item['cantidad'] for item in productos_nuevos)
        cursor.execute("SELECT anticipo FROM apartados WHERE id = ? AND store_id = ?", (self._get_selected_apartado()['id'], self.store_id))
        anticipo = cursor.fetchone()['anticipo']
        saldo_pendiente = subtotal - anticipo
        label_subtotal.configure(text=f"Subtotal: ${subtotal:.2f}")
        label_saldo.configure(text=f"Saldo Pendiente: ${saldo_pendiente:.2f}")

    def _setup_search_productos(self, search_frame, productos_container, productos_entries, label_subtotal, label_saldo):
        """Configura la funcionalidad de búsqueda de productos."""
        def buscar_productos():
            query = search_frame.winfo_children()[1].get().strip()
            if not query:
                messagebox.showinfo("Información", "Por favor, ingrese un SKU o nombre para buscar.")
                return
            cursor = self.db_manager.get_cursor()
            cursor.execute("""
                SELECT sku, nombre, precio, inventario
                FROM productos
                WHERE (sku LIKE ? OR nombre LIKE ?) AND store_id = ?
                LIMIT 10
            """, (f"%{query}%", f"%{query}%", self.store_id))
            productos_encontrados = [dict(row) for row in cursor.fetchall()]
            if not productos_encontrados:
                messagebox.showinfo("Información", f"No se encontraron productos para la búsqueda: '{query}' en tienda {self.store_id}")
                return

            dialog_select = self._create_dialog("Seleccionar Producto", "600x400")
            columns = ["SKU", "Nombre", "Precio", "Stock"]
            column_widths = {"SKU": 100, "Nombre": 200, "Precio": 100, "Stock": 100}

            formatted_productos = [
                {
                    "SKU": prod['sku'],
                    "Nombre": prod['nombre'],
                    "Precio": f"${prod['precio']:.2f}",
                    "Stock": prod['inventario']
                }
                for prod in productos_encontrados
            ]

            def on_select(prod):
                self._add_producto_row(productos_container, productos_entries, label_subtotal, label_saldo, prod['SKU'], 1)
                dialog_select.destroy()

            mostrar_ventana_seleccion(
                parent=dialog_select,
                title="Seleccionar Producto",
                items=formatted_productos,
                columns=columns,
                column_widths=column_widths,
                on_select_callback=on_select
            )

        ctk.CTkButton(search_frame, text="Buscar Producto", command=buscar_productos).pack(side="left", padx=5)

    def _setup_modificar_buttons(self, productos_frame, apartado_id, productos_entries, productos_actuales, label_subtotal, label_saldo):
        """Configura los botones adicionales del diálogo de modificación."""
        ctk.CTkButton(productos_frame, text="Agregar Producto", command=lambda: self._add_producto_row(productos_frame, productos_entries, label_subtotal, label_saldo)).pack(pady=5)
        ctk.CTkButton(productos_frame, text="Ver Historial de Modificaciones", command=lambda: self.ver_historial_modificaciones(apartado_id)).pack(pady=5)

    def _confirmar_modificacion(self, apartado_id, productos_entries, productos_actuales, dialog):
        """Confirma la modificación de productos en un apartado."""
        productos_nuevos = []
        cursor = self.db_manager.get_cursor()
        for frame, entry_sku, entry_cantidad, label_precio in productos_entries:
            sku = entry_sku.get().strip()
            try:
                cantidad = int(entry_cantidad.get())
                if not sku:
                    messagebox.showerror("Error", "El SKU no puede estar vacío.")
                    return
                if cantidad <= 0:
                    messagebox.showerror("Error", f"La cantidad para el SKU {sku} debe ser mayor a 0.")
                    return
                cursor.execute("SELECT nombre, precio, inventario FROM productos WHERE sku = ? AND store_id = ?", (sku, self.store_id))
                producto = cursor.fetchone()
                if not producto:
                    messagebox.showerror("Error", f"SKU {sku} no existe en tienda {self.store_id}.")
                    return
                stock_base = producto['inventario']
                cantidad_apartada = next((item['cantidad'] for item in productos_actuales if item['sku'] == sku), 0)
                stock_disponible = stock_base + cantidad_apartada
                if cantidad > stock_disponible:
                    messagebox.showerror("Error", f"No hay suficiente inventario para SKU {sku} (disponible: {stock_disponible}) en tienda {self.store_id}.")
                    return

                precio = next((p['precio'] for p in productos_actuales if p['sku'] == sku), producto['precio'])
                productos_nuevos.append({
                    "sku": sku,
                    "nombre": producto['nombre'],
                    "cantidad": cantidad,
                    "precio": precio,
                    "descuento": 0
                })
            except ValueError:
                messagebox.showerror("Error", f"La cantidad para el SKU {sku} debe ser un número entero positivo.")
                return

        if not productos_nuevos:
            messagebox.showerror("Error", "Debe haber al menos un producto en la lista.")
            return

        try:
            mod_data = self.logic.modificar_productos_apartado(apartado_id, productos_nuevos)
            dialog.destroy()

            def confirmar():
                receipt_path = self.logic.confirmar_modificacion_productos(
                    apartado_id,
                    mod_data["productos_antiguos"],
                    mod_data["productos_nuevos"],
                    mod_data["cliente_nombre"],
                    mod_data["subtotal_antiguo"],
                    mod_data["subtotal_nuevo"],
                    mod_data["anticipo"],
                    mod_data["cantidades_antiguas"],
                    mod_data["cantidades_nuevas"]
                )
                msg = f"Productos del apartado ID {apartado_id} modificados exitosamente.\nSe generó un comprobante de modificación."
                self._show_success_dialog("Modificación Exitosa", msg, receipt_path)
                self.data.cargar_apartados_paginated(page=1)
                logger.info(f"Productos modificados para apartado: ID {apartado_id}, Comprobante: {receipt_path}, Tienda: {self.store_id}")

            self._build_confirm_dialog(
                f"Confirmar Modificación de Productos - Apartado ID {apartado_id}",
                mod_data["confirm_message"],
                confirmar
            )
        except (ValueError, Exception) as e:
            messagebox.showerror("Error", f"No se pudo modificar los productos: {str(e)}")
            logger.error(f"Error al modificar productos: {str(e)}")

    def ver_historial_modificaciones(self, apartado_id):
        """Muestra el historial de modificaciones de un apartado."""
        try:
            cursor = self.db_manager.get_cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modificaciones_apartados'")
            if not cursor.fetchone():
                messagebox.showinfo("Información", "No hay historial de modificaciones disponible.")
                return

            cursor.execute("SELECT * FROM modificaciones_apartados WHERE apartado_id = ? AND store_id = ? ORDER BY fecha DESC", (apartado_id, self.store_id))
            modificaciones = [dict(row) for row in cursor.fetchall()]
            if not modificaciones:
                messagebox.showinfo("Información", f"No hay modificaciones registradas para este apartado en tienda {self.store_id}.")
                return

            dialog = self._create_dialog(f"Historial de Modificaciones - Apartado ID {apartado_id}", "500x400")
            text_frame = ctk.CTkFrame(dialog)
            text_frame.pack(fill="both", expand=True, padx=10, pady=10)

            historial = f"Historial de Modificaciones - Apartado ID {apartado_id}\n\n"
            for mod in modificaciones:
                historial += f"- {mod['fecha']}: {mod['descripcion']}\n"

            textbox = ctk.CTkTextbox(text_frame, wrap="word", height=300, width=450)
            textbox.pack(side="left", fill="both", expand=True)
            textbox.insert("1.0", historial)
            textbox.configure(state="disabled")

            scrollbar = ctk.CTkScrollbar(text_frame, command=textbox.yview)
            scrollbar.pack(side="right", fill="y")
            textbox.configure(yscrollcommand=scrollbar.set)

            ctk.CTkButton(dialog, text="Cerrar", command=dialog.destroy).pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el historial: {str(e)}")
            logger.error(f"Error al cargar historial de modificaciones: {str(e)}")

    def ver_detalles(self):
        """Muestra los detalles de un apartado seleccionado."""
        apartado_data = self._get_selected_apartado()
        if not self._validate_apartado_selection(apartado_data):
            return

        try:
            cursor = self.db_manager.get_cursor()
            cursor.execute("""
                SELECT a.*, c.nombre_completo, c.numero
                FROM apartados a
                JOIN clientes c ON a.id_cliente = c.id
                WHERE a.id = ? AND a.store_id = ?
            """, (apartado_data['id'], self.store_id))
            apartado = cursor.fetchone()
            if not apartado:
                messagebox.showerror("Error", "El apartado no se encuentra.")
                return

            dialog = self._create_dialog(f"Detalles del Apartado ID {apartado_data['id']}", "500x500")
            text_frame = ctk.CTkFrame(dialog)
            text_frame.pack(fill="both", expand=True, padx=10, pady=10)

            detalles = f"Detalles del Apartado ID {apartado_data['id']}\n\n"
            detalles += f"Cliente: {apartado['nombre_completo']}\n"
            detalles += f"Teléfono: {apartado['numero'] if apartado['numero'] else 'N/A'}\n"
            detalles += f"Estado: {apartado['estado']}\n"
            detalles += f"Fecha Creación: {apartado['fecha_creacion']}\n"
            detalles += f"Fecha Modificación: {apartado['fecha_modificacion']}\n"
            detalles += f"Fecha Vencimiento: {apartado['fecha_vencimiento']}\n\n"
            detalles += "Productos:\n"
            productos = json.loads(apartado['productos'])
            for item in productos:
                subtotal_item = item['cantidad'] * item['precio']
                detalles += f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${item['precio']:.2f} = ${subtotal_item:.2f}\n"
            detalles += f"\nAnticipo: ${apartado['anticipo']:.2f}\n"
            detalles += f"Total: ${sum(item['precio'] * item['cantidad'] for item in productos):.2f}\n"
            detalles += f"Saldo Pendiente: ${sum(item['precio'] * item['cantidad'] for item in productos) - apartado['anticipo']:.2f}\n\n"

            anticipos = self.logic.obtener_anticipos(apartado_data['id'], store_id=self.store_id)
            if anticipos:
                detalles += "Anticipos Registrados:\n"
                for anticipo in anticipos:
                    detalles += f"- ${anticipo['monto']:.2f} el {anticipo['fecha']}\n"

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modificaciones_apartados'")
            if cursor.fetchone():
                cursor.execute("SELECT * FROM modificaciones_apartados WHERE apartado_id = ? AND store_id = ? ORDER BY fecha DESC", (apartado_data['id'], self.store_id))
                modificaciones = [dict(row) for row in cursor.fetchall()]
                if modificaciones:
                    detalles += "\nHistorial de Modificaciones:\n"
                    for mod in modificaciones:
                        detalles += f"- {mod['fecha']}: {mod['descripcion']}\n"

            textbox = ctk.CTkTextbox(text_frame, wrap="word", height=400, width=450)
            textbox.pack(side="left", fill="both", expand=True)
            textbox.insert("1.0", detalles)
            textbox.configure(state="disabled")

            scrollbar = ctk.CTkScrollbar(text_frame, command=textbox.yview)
            scrollbar.pack(side="right", fill="y")
            textbox.configure(yscrollcommand=scrollbar.set)

            ctk.CTkButton(dialog, text="Cerrar", command=dialog.destroy).pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar los detalles: {str(e)}")
            logger.error(f"Error al cargar detalles del apartado: {str(e)}")

    def enviar_recordatorio(self):
        """Envía un recordatorio para un apartado."""
        apartado_data = self._get_selected_apartado()
        if not self._validate_apartado_selection(apartado_data):
            return

        try:
            cursor = self.db_manager.get_cursor()
            cursor.execute("SELECT numero FROM clientes WHERE nombre_completo = ?", (apartado_data['cliente_nombre'],))
            cliente = cursor.fetchone()
            if not cliente or not cliente['numero']:
                messagebox.showerror("Error", f"No se encontró un número de teléfono para el cliente {apartado_data['cliente_nombre']}.")
                return

            dialog = self._create_dialog(f"Enviar Recordatorio - Apartado ID {apartado_data['id']}", "400x300")
            mensaje = f"Estimado(a) {apartado_data['cliente_nombre']},\n\n"
            mensaje += f"Le recordamos que su apartado con ID {apartado_data['id']} tiene un saldo pendiente de ${apartado_data['saldo_pendiente']:.2f}. "
            mensaje += f"Por favor, acérquese a la tienda para completar el pago.\n\nGracias por su atención."

            ctk.CTkLabel(dialog, text="Mensaje de Recordatorio:", font=("Arial", 14)).pack(pady=5)
            textbox = ctk.CTkTextbox(dialog, wrap="word", height=150, width=350)
            textbox.pack(pady=5)
            textbox.insert("1.0", mensaje)
            textbox.configure(state="disabled")

            def enviar():
                logger.info(f"Recordatorio enviado para apartado ID {apartado_data['id']} al cliente {apartado_data['cliente_nombre']} (Número: {cliente['numero']}), Tienda: {self.store_id}")
                messagebox.showinfo("Éxito", "Recordatorio enviado exitosamente.")
                dialog.destroy()

            ctk.CTkButton(dialog, text="Enviar", command=enviar).pack(pady=10)
            ctk.CTkButton(dialog, text="Cerrar", command=dialog.destroy).pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo enviar el recordatorio: {str(e)}")
            logger.error(f"Error al enviar recordatorio: {str(e)}")