import json
import customtkinter as ctk
from tkinter import ttk, messagebox
import logging
from datetime import datetime
from src.ui.ui_utils import mostrar_ventana_seleccion
from src.core.config.config import CONFIG

logger = logging.getLogger(__name__)

class ClientesTab:
    def __init__(self, tab, logic, root, user_id, store_id=1, items_per_page=20):
        self.tab = tab
        self.logic = logic
        self.root = root
        self.user_id = user_id
        self.store_id = store_id
        self.items_per_page = items_per_page
        self.clientes_page = 1
        self.total_clientes = 0
        self.cliente_busqueda_var = ctk.StringVar()
        self.setup_ui()
        logger.info(f"Pestaña Clientes inicializada para usuario con ID '{self.user_id}' en tienda {self.store_id}.")

    def setup_ui(self):
        search_frame = ctk.CTkFrame(self.tab)
        search_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(search_frame, text="Buscar Cliente (Nombre/Número):").pack(side="left", padx=5)
        ctk.CTkEntry(search_frame, textvariable=self.cliente_busqueda_var).pack(side="left", padx=5)
        ctk.CTkButton(search_frame, text="Buscar", command=self.buscar_clientes).pack(side="left", padx=5)
        ctk.CTkButton(search_frame, text="Refrescar", command=lambda: self.cargar_clientes(refresh=True)).pack(side="left", padx=5)
        logging.debug("search_frame clientes configurado")

        self.tree_frame = ctk.CTkFrame(self.tab)
        self.tree_frame.pack(fill="both", expand=True, pady=5)
        self.clientes_tree = ttk.Treeview(
            self.tree_frame,
            columns=("ID", "Nombre", "Número"),
            show="headings"
        )
        self.clientes_tree.heading("ID", text="ID")
        self.clientes_tree.heading("Nombre", text="Nombre")
        self.clientes_tree.heading("Número", text="Número")
        self.clientes_tree.column("ID", width=50)
        self.clientes_tree.column("Nombre", width=250)
        self.clientes_tree.column("Número", width=150)
        self.clientes_tree.pack(side="left", fill="both", expand=True)

        buttons_container = ctk.CTkFrame(self.tree_frame, fg_color="transparent")
        buttons_container.pack(side="right", padx=5)
        buttons = [
            {"text": "Agregar Cliente", "command": self.agregar_cliente, "icon": "➕"},
            {"text": "Editar Cliente", "command": self.editar_cliente, "icon": "✏️"},
            {"text": "Eliminar Cliente", "command": self.eliminar_cliente, "icon": "🗑️"},
            {"text": "Crear Apartado", "command": self.crear_apartado_cliente, "icon": "📝"},
            {"text": "Ver Apartados", "command": self.ver_apartados_cliente, "icon": "🔍"}
        ]

        for btn_info in buttons:
            card_frame = ctk.CTkFrame(
                buttons_container,
                corner_radius=10,
                border_width=2,
                border_color="#1f6aa5",
                fg_color="white" if CONFIG["THEME_MODE"] == "light" else "#2b2b2b"
            )
            card_frame.pack(pady=5)
            button = ctk.CTkButton(
                card_frame,
                text=f"{btn_info['icon']} {btn_info['text']}",
                command=btn_info['command'],
                width=150,
                height=40,
                font=("Arial", 14),
                corner_radius=8,
                hover_color="#4a90e2" if CONFIG["THEME_MODE"] == "light" else "#1f6aa5"
            )
            button.pack(padx=5, pady=5)

        from src.core.utils.pagination import Paginator
        self.clientes_paginator = Paginator(self.tab, self.items_per_page, self.cargar_clientes_paginated)
        self.clientes_paginator.pack(fill="x", pady=5)

        self.cargar_clientes_paginated(page=1)
        logging.debug("clientes_tree y botones configurados")

    def cargar_clientes_paginated(self, page, refresh=False):
        self.clientes_page = page
        if refresh:
            self.cliente_busqueda_var.set("")
        query = self.cliente_busqueda_var.get().strip()
        logging.debug(f"Buscando clientes con query: {query}, página: {self.clientes_page}")
        for item in self.clientes_tree.get_children():
            self.clientes_tree.delete(item)
        try:
            clientes_all = self.logic.buscar_clientes(query=query, limit=None)
            self.total_clientes = len(clientes_all)
            self.clientes_paginator.set_total_items(self.total_clientes)

            offset = self.clientes_paginator.get_offset()
            clientes = self.logic.buscar_clientes(query=query, limit=self.items_per_page, offset=offset)
            logging.debug(f"Clientes obtenidos: {len(clientes)} registros")
            if not clientes:
                messagebox.showinfo("Información", f"No se encontraron clientes para la búsqueda: '{query}'")
            for cliente in clientes:
                self.clientes_tree.insert("", "end", values=(
                    cliente['id'],
                    cliente['nombre_completo'],
                    cliente['numero'] or "N/A"
                ))
            logging.debug("Clientes cargados")
        except Exception as e:
            logging.error(f"Error al cargar clientes: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron cargar los clientes: {str(e)}")

    def cargar_clientes(self, refresh=False):
        self.cargar_clientes_paginated(self.clientes_page, refresh)

    def buscar_clientes(self):
        query = self.cliente_busqueda_var.get().strip()
        logging.debug(f"Buscando clientes con query: {query}")
        try:
            clientes = self.logic.buscar_clientes(query=query, limit=50)
            logging.debug(f"Clientes obtenidos: {len(clientes)} registros")
            if not clientes:
                messagebox.showinfo("Información", f"No se encontraron clientes para la búsqueda: '{query}'")
                return

            columns = ["ID", "Nombre Completo", "Número"]
            column_widths = {"ID": 50, "Nombre Completo": 250, "Número": 150}
            formatted_clientes = [
                {
                    "ID": cliente['id'],
                    "Nombre Completo": cliente['nombre_completo'],
                    "Número": cliente['numero'] or "N/A"
                }
                for cliente in clientes
            ]

            def on_select(cliente):
                for item in self.clientes_tree.get_children():
                    self.clientes_tree.delete(item)
                self.clientes_tree.insert("", "end", values=(
                    cliente['ID'],
                    cliente['Nombre Completo'],
                    cliente['Número']
                ))

            mostrar_ventana_seleccion(
                parent=self.root,
                title="Seleccionar Cliente",
                items=formatted_clientes,
                columns=columns,
                column_widths=column_widths,
                on_select_callback=on_select
            )

            logging.debug("Clientes cargados")
        except Exception as e:
            logging.error(f"Error al buscar clientes: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron cargar los clientes: {str(e)}")

    def agregar_cliente(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Agregar Cliente")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Nombre *:").pack(pady=5)
        nombre_var = ctk.StringVar()
        ctk.CTkEntry(dialog, textvariable=nombre_var).pack(pady=5)
        ctk.CTkLabel(dialog, text="Número:").pack(pady=5)
        numero_var = ctk.StringVar()
        ctk.CTkEntry(dialog, textvariable=numero_var).pack(pady=5)

        def guardar():
            try:
                if not nombre_var.get().strip():
                    raise ValueError("El nombre es obligatorio")
                cliente_id = self.logic.agregar_cliente(
                    nombre_var.get(),
                    numero_var.get()
                )
                self.cargar_clientes()
                dialog.destroy()
                messagebox.showinfo("Éxito", f"Cliente agregado con ID: {cliente_id}")
                logger.info(f"Cliente agregado: ID {cliente_id}")
            except ValueError as e:
                messagebox.showerror("Error", str(e))
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo agregar el cliente: {str(e)}")
                logger.error(f"Error al agregar cliente: {str(e)}")

        ctk.CTkButton(dialog, text="Guardar", command=guardar).pack(pady=20)

    def editar_cliente(self):
        selected = self.clientes_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un cliente")
            return
        cliente_id = self.clientes_tree.item(selected)["values"][0]

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Editar Cliente")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        cliente = self.logic.buscar_clientes(query=f"id:{cliente_id}", limit=1)[0]
        ctk.CTkLabel(dialog, text="Nombre *:").pack(pady=5)
        nombre_var = ctk.StringVar(value=cliente['nombre_completo'])
        ctk.CTkEntry(dialog, textvariable=nombre_var).pack(pady=5)
        ctk.CTkLabel(dialog, text="Número:").pack(pady=5)
        numero_var = ctk.StringVar(value=cliente['numero'] or "")
        ctk.CTkEntry(dialog, textvariable=numero_var).pack(pady=5)

        def guardar():
            try:
                if not nombre_var.get().strip():
                    raise ValueError("El nombre es obligatorio")
                self.logic.editar_cliente(
                    cliente_id,
                    nombre_var.get(),
                    numero_var.get()
                )
                self.cargar_clientes()
                dialog.destroy()
                messagebox.showinfo("Éxito", "Cliente actualizado")
                logger.info(f"Cliente actualizado: ID {cliente_id}")
            except ValueError as e:
                messagebox.showerror("Error", str(e))
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo actualizar el cliente: {str(e)}")
                logger.error(f"Error al actualizar cliente: {str(e)}")

        ctk.CTkButton(dialog, text="Guardar", command=guardar).pack(pady=20)

    def eliminar_cliente(self):
        selected = self.clientes_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un cliente")
            return
        cliente_id = self.clientes_tree.item(selected)["values"][0]

        if not messagebox.askyesno("Confirmar", "¿Eliminar este cliente?"):
            return
        try:
            self.logic.eliminar_cliente(cliente_id)
            self.cargar_clientes()
            messagebox.showinfo("Éxito", "Cliente eliminado")
            logger.info(f"Cliente eliminado: ID {cliente_id}")
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar el cliente: {str(e)}")
            logger.error(f"Error al eliminar cliente: {str(e)}")

    def crear_apartado(self, preselected_cliente_id, preselected_cliente_nombre, callback=None):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Crear Apartado")
        dialog.geometry("900x700")
        dialog.transient(self.root)
        dialog.grab_set()

        cliente_id_var = ctk.StringVar(value=preselected_cliente_id)
        cliente_nombre_var = ctk.StringVar(value=preselected_cliente_nombre)
        productos_list = []
        anticipo_var = ctk.DoubleVar(value=0.0)
        subtotal_var = ctk.DoubleVar(value=0.0)
        total_pendiente_var = ctk.DoubleVar(value=0.0)
        ANTICIPO_MINIMO_PORCENTAJE = 0.2

        cliente_frame = ctk.CTkFrame(dialog)
        cliente_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(cliente_frame, text="Cliente *:", font=("Arial", 14)).pack(side="left", padx=5)
        cliente_label = ctk.CTkLabel(cliente_frame, textvariable=cliente_nombre_var)
        cliente_label.pack(side="left", padx=5)

        productos_frame = ctk.CTkFrame(dialog)
        productos_frame.pack(fill="both", expand=True, padx=10, pady=5)
        ctk.CTkLabel(productos_frame, text="Productos:", font=("Arial", 14)).pack(anchor="w", padx=5)

        productos_container = ctk.CTkFrame(productos_frame)
        productos_container.pack(fill="both", expand=True, padx=5, pady=5)
        productos_entries = []

        def agregar_producto():
            frame = ctk.CTkFrame(productos_container)
            frame.pack(fill="x", pady=2)
            ctk.CTkLabel(frame, text="SKU:").pack(side="left", padx=5)
            entry_sku = ctk.CTkEntry(frame, width=100)
            entry_sku.pack(side="left", padx=5)

            ctk.CTkLabel(frame, text="Nombre:").pack(side="left", padx=5)
            label_nombre = ctk.CTkLabel(frame, text="N/A", width=150)
            label_nombre.pack(side="left", padx=5)

            ctk.CTkLabel(frame, text="Precio:").pack(side="left", padx=5)
            label_precio = ctk.CTkLabel(frame, text="0.0", width=50)
            label_precio.pack(side="left", padx=5)

            ctk.CTkLabel(frame, text="Cantidad:").pack(side="left", padx=5)
            entry_cantidad = ctk.CTkEntry(frame, width=50)
            entry_cantidad.pack(side="left", padx=5)

            ctk.CTkLabel(frame, text="Subtotal:").pack(side="left", padx=5)
            label_subtotal = ctk.CTkLabel(frame, text="0.0", width=70)
            label_subtotal.pack(side="left", padx=5)

            stock_warning_label = ctk.CTkLabel(frame, text="", text_color="red")
            stock_warning_label.pack(side="left", padx=5)

            def actualizar_info_producto(*args):
                sku = entry_sku.get().strip()
                if sku:
                    producto = self.logic.buscar_productos(sku, store_id=self.store_id, limit=1)
                    if producto:
                        label_nombre.configure(text=producto[0]['nombre'])
                        label_precio.configure(text=str(producto[0]['precio']))
                        try:
                            cantidad = int(entry_cantidad.get()) if entry_cantidad.get() else 0
                            if cantidad > 0:
                                if not self.logic.validar_stock(sku, cantidad, store_id=self.store_id):
                                    stock_warning_label.configure(text="Stock insuficiente")
                                else:
                                    stock_warning_label.configure(text="")
                        except ValueError:
                            stock_warning_label.configure(text="")
                    else:
                        label_nombre.configure(text="Producto no encontrado")
                        label_precio.configure(text="0.0")
                        stock_warning_label.configure(text="")
                actualizar_resumen()

            def actualizar_resumen(*args):
                productos_temp = []
                for entry_sku, _, label_precio, entry_cantidad, _, _ in productos_entries:
                    try:
                        sku = entry_sku.get().strip()
                        cantidad = int(entry_cantidad.get()) if entry_cantidad.get() else 0
                        precio = float(label_precio.cget("text"))
                        if sku and cantidad > 0:
                            subtotal_producto = precio * cantidad
                            label_subtotal.configure(text=f"${subtotal_producto:.2f}")
                            productos_temp.append({
                                "sku": sku,
                                "cantidad": cantidad,
                                "precio": precio,
                                "descuento": 0
                            })
                        else:
                            label_subtotal.configure(text="0.0")
                    except ValueError:
                        label_subtotal.configure(text="0.0")
                        continue
                productos_list.clear()
                productos_list.extend(productos_temp)
                subtotal = sum(item['precio'] * item['cantidad'] for item in productos_list)
                subtotal_var.set(subtotal)
                total_pendiente_var.set(subtotal - anticipo_var.get())

            entry_sku.bind("<KeyRelease>", actualizar_info_producto)
            entry_sku.bind("<Return>", actualizar_info_producto)
            entry_cantidad.bind("<KeyRelease>", actualizar_resumen)

            def eliminar_producto():
                frame.destroy()
                productos_entries.remove((entry_sku, label_nombre, label_precio, entry_cantidad, label_subtotal, stock_warning_label))
                actualizar_resumen()

            ctk.CTkButton(frame, text="Eliminar", command=eliminar_producto, fg_color="red").pack(side="left", padx=5)
            productos_entries.append((entry_sku, label_nombre, label_precio, entry_cantidad, label_subtotal, stock_warning_label))
            actualizar_resumen()

        ctk.CTkButton(productos_frame, text="Agregar Producto", command=agregar_producto).pack(anchor="w", padx=5, pady=5)
        agregar_producto()

        anticipo_frame = ctk.CTkFrame(dialog)
        anticipo_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(anticipo_frame, text="Anticipo (mínimo 20% del total):", font=("Arial", 14)).pack(side="left", padx=5)
        entry_anticipo = ctk.CTkEntry(anticipo_frame, width=100, textvariable=anticipo_var)
        entry_anticipo.pack(side="left", padx=5)

        def actualizar_anticipo(*args):
            try:
                anticipo = float(anticipo_var.get()) if anticipo_var.get() else 0
                total_pendiente_var.set(subtotal_var.get() - anticipo)
            except ValueError:
                total_pendiente_var.set(subtotal_var.get())

        anticipo_var.trace("w", actualizar_anticipo)

        resumen_frame = ctk.CTkFrame(dialog)
        resumen_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(resumen_frame, text="Resumen:", font=("Arial", 14)).pack(anchor="w", padx=5)
        ctk.CTkLabel(resumen_frame, text="Subtotal:").pack(anchor="w", padx=5)
        ctk.CTkLabel(resumen_frame, textvariable=subtotal_var).pack(anchor="w", padx=20)
        ctk.CTkLabel(resumen_frame, text="Anticipo:").pack(anchor="w", padx=5)
        ctk.CTkLabel(resumen_frame, textvariable=anticipo_var).pack(anchor="w", padx=20)
        ctk.CTkLabel(resumen_frame, text="Total Pendiente:").pack(anchor="w", padx=5)
        ctk.CTkLabel(resumen_frame, textvariable=total_pendiente_var).pack(anchor="w", padx=20)

        def guardar_apartado():
            if not cliente_id_var.get():
                messagebox.showerror("Error", "Seleccione un cliente.")
                return
            
            productos = []
            for entry_sku, _, label_precio, entry_cantidad, _, _ in productos_entries:
                sku = entry_sku.get().strip()
                cantidad = entry_cantidad.get().strip()
                if not sku or not cantidad:
                    messagebox.showerror("Error", "Complete todos los campos de los productos.")
                    return
                try:
                    cantidad = int(cantidad)
                    if cantidad <= 0:
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Error", f"La cantidad debe ser un número entero positivo.")
                    return
                producto = self.logic.buscar_productos(sku, store_id=self.store_id, limit=1)
                if not producto:
                    messagebox.showerror("Error", f"No se encontró el producto con SKU {sku} en tienda {self.store_id}.")
                    return
                productos.append({
                    "sku": sku,
                    "cantidad": cantidad,
                    "precio": producto[0]['precio'],
                    "descuento": 0
                })
            
            if not productos:
                messagebox.showerror("Error", "Debe agregar al menos un producto.")
                return
            
            try:
                anticipo = float(anticipo_var.get())
                if anticipo < 0:
                    raise ValueError("El anticipo no puede ser negativo.")
                subtotal = sum(item['precio'] * item['cantidad'] for item in productos)
                anticipo_minimo = subtotal * ANTICIPO_MINIMO_PORCENTAJE
                if anticipo < anticipo_minimo:
                    raise ValueError(f"El anticipo debe ser al menos el {ANTICIPO_MINIMO_PORCENTAJE*100}% del subtotal (${anticipo_minimo:.2f}).")

                confirm_message = f"Confirmar Apartado\n\n"
                confirm_message += f"Cliente: {cliente_nombre_var.get()}\n"
                confirm_message += f"Productos:\n"
                for item in productos:
                    confirm_message += f"- {item['sku']} (x{item['cantidad']}) - ${item['precio']:.2f}\n"
                confirm_message += f"\nSubtotal: ${subtotal:.2f}\n"
                confirm_message += f"Anticipo: ${anticipo:.2f}\n"
                confirm_message += f"Total Pendiente: ${subtotal - anticipo:.2f}\n"
                confirm_message += "\n¿Desea confirmar la creación del apartado?"
                if not messagebox.askyesno("Confirmar", confirm_message):
                    return

                cliente_id = int(cliente_id_var.get())
                result = self.logic.crear_apartado(cliente_id, self.user_id, productos, anticipo, store_id=self.store_id)
                dialog.destroy()
                messagebox.showinfo("Éxito", f"Apartado registrado con ID: {result['apartado_id']}.")
                if callback:
                    callback()
                logger.info(f"Nuevo apartado registrado: ID {result['apartado_id']} en tienda {self.store_id}")
            except ValueError as e:
                messagebox.showerror("Error", str(e))
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo registrar el apartado: {str(e)}")
                logger.error(f"Error al registrar apartado: {str(e)}")

        ctk.CTkButton(dialog, text="Guardar", command=guardar_apartado).pack(pady=10)

    def crear_apartado_cliente(self, callback=None):
        selected = self.clientes_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un cliente")
            return
        cliente_id = self.clientes_tree.item(selected)["values"][0]
        cliente_nombre = self.clientes_tree.item(selected)["values"][1]
        self.crear_apartado(preselected_cliente_id=cliente_id, preselected_cliente_nombre=cliente_nombre, callback=callback)

    def ver_apartados_cliente(self):
        selected = self.clientes_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un cliente")
            return
        cliente_id = self.clientes_tree.item(selected)["values"][0]
        cliente_nombre = self.clientes_tree.item(selected)["values"][1]

        try:
            apartados = self.logic.buscar_apartados_por_cliente(cliente_id)
            if not apartados:
                messagebox.showinfo("Información", f"No se encontraron apartados para {cliente_nombre}")
                return

            columns = ["ID", "Productos", "Anticipo", "Fecha Creación", "Fecha Vencimiento", "Estado"]
            column_widths = {
                "ID": 50,
                "Productos": 200,
                "Anticipo": 100,
                "Fecha Creación": 150,
                "Fecha Vencimiento": 150,
                "Estado": 100
            }
            formatted_apartados = [
                {
                    "ID": apartado['id'],
                    "Productos": ", ".join([f"{item['sku']} (x{item['cantidad']})" for item in json.loads(apartado['productos'])]),
                    "Anticipo": f"${apartado['anticipo']:.2f}",
                    "Fecha Creación": apartado['fecha_creacion'],
                    "Fecha Vencimiento": apartado['fecha_vencimiento'],
                    "Estado": apartado['estado']
                }
                for apartado in apartados
            ]

            def on_select(apartado):
                return (apartado['ID'], cliente_nombre, apartado['Productos'], apartado['Anticipo'],
                        apartado['Fecha Creación'], apartado['Fecha Vencimiento'], apartado['Estado'])

            return mostrar_ventana_seleccion(
                parent=self.root,
                title=f"Apartados de {cliente_nombre}",
                items=formatted_apartados,
                columns=columns,
                column_widths=column_widths,
                on_select_callback=on_select
            )

        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los apartados: {str(e)}")
            logger.error(f"Error al cargar apartados de cliente: {str(e)}")
            return None