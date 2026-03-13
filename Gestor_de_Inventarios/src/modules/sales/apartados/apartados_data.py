import logging
from datetime import datetime
import json
from tkinter import messagebox
from src.ui.ui_utils import mostrar_ventana_seleccion

logger = logging.getLogger(__name__)

class ApartadosData:
    def __init__(self, db_manager, ui, items_per_page, store_id=1):
        self.db_manager = db_manager
        self.ui = ui
        self.items_per_page = items_per_page
        self.store_id = store_id
        self.apartados_page = 1
        self.total_apartados = 0
        logger.info(f"ApartadosData inicializado para tienda {self.store_id}")

    def parse_date(self, date_str, apartado_id):
        """Parsea una cadena de fecha en un objeto datetime."""
        if date_str is None:
            logger.warning(f"Fecha nula encontrada en apartado ID {apartado_id}. Usando fecha predeterminada.")
            return datetime.now()
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.strptime(date_str, "%Y-%m-%d")

    def format_apartado_row(self, apartado):
        """Formatea los datos de un apartado para el Treeview."""
        productos = json.loads(apartado['productos'])
        productos_str = f"{sum(item['cantidad'] for item in productos)} producto(s)"
        total = sum(item['precio'] * item['cantidad'] for item in productos)
        anticipo = float(apartado['anticipo'])
        saldo_pendiente = total - anticipo

        fecha_creacion_dt = self.parse_date(apartado['fecha_creacion'], apartado['id'])
        fecha_vencimiento_dt = self.parse_date(apartado['fecha_vencimiento'], apartado['id'])
        fecha_modificacion_dt = self.parse_date(apartado['fecha_modificacion'], apartado['id'])

        fecha_creacion = fecha_creacion_dt.strftime("%d/%m/%Y %H:%M:%S")
        fecha_vencimiento = fecha_vencimiento_dt.strftime("%d/%m/%Y %H:%M:%S")
        fecha_modificacion = fecha_modificacion_dt.strftime("%d/%m/%Y %H:%M:%S")

        dias_restantes = (fecha_vencimiento_dt - datetime.now()).days
        tags = ()
        if apartado['estado'] == "activo":
            if dias_restantes <= self.ui.dias_vencimiento_filtro:
                tags = ("venciendo",)
            else:
                tags = ("activo",)

        return {
            "values": (
                apartado['id'], apartado['nombre_completo'], productos_str,
                f"${anticipo:.2f}", f"${total:.2f}", f"${saldo_pendiente:.2f}",
                fecha_creacion, fecha_modificacion, fecha_vencimiento, apartado['estado']
            ),
            "tags": tags,
            "dias_restantes": dias_restantes
        }

    def actualizar_dias_vencimiento(self):
        """Actualiza el filtro de días para apartados por vencer."""
        try:
            dias = int(self.ui.entry_dias_vencimiento.get())
            if dias <= 0:
                raise ValueError("El número de días debe ser positivo.")
            self.ui.dias_vencimiento_filtro = dias
            self.ui.update_notif_label(0)
            self.cargar_apartados_paginated(page=1)
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def cargar_apartados_paginated(self, page):
        """Carga los apartados en la página especificada con paginación."""
        self.apartados_page = page
        logging.debug(f"Cargando apartados, página: {self.apartados_page}, tienda: {self.store_id}")
        try:
            for item in self.ui.tree.get_children():
                self.ui.tree.delete(item)

            self.db_manager.verificar_apartados_vencidos(store_id=self.store_id)
            apartados_all = self.db_manager.buscar_apartados(query="", estado="activo", store_id=self.store_id, limit=None)
            self.total_apartados = len(apartados_all)
            self.ui.apartados_paginator.set_total_items(self.total_apartados)

            offset = self.ui.apartados_paginator.get_offset()
            apartados = self.db_manager.buscar_apartados(query="", estado="activo", store_id=self.store_id, limit=self.items_per_page, offset=offset)
            logging.debug(f"Apartados obtenidos: {len(apartados)} registros")

            if not apartados:
                logger.info(f"No se encontraron apartados activos en tienda {self.store_id}.")
            for apartado in apartados:
                row_data = self.format_apartado_row(apartado)
                self.ui.tree.insert("", "end", values=row_data["values"], tags=row_data["tags"])

            apartados_venciendo = self.db_manager.apartados_por_vencer(dias=self.ui.dias_vencimiento_filtro, store_id=self.store_id)
            self.ui.update_notif_label(len(apartados_venciendo))
            logging.debug("Apartados cargados y notificaciones actualizadas")
        except Exception as e:
            logging.error(f"Error al cargar apartados en tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo cargar los apartados: {str(e)}")

    def buscar_apartados(self):
        """Busca apartados según un query."""
        query = self.ui.entry_busqueda.get().strip()
        logging.debug(f"Buscando apartados con query: {query} en tienda {self.store_id}")
        try:
            apartados = self.db_manager.buscar_apartados(query=query, estado="activo", store_id=self.store_id, limit=50)
            logging.debug(f"Resultados de búsqueda: {len(apartados)} registros")
            if not apartados:
                messagebox.showinfo("Información", f"No se encontraron apartados para la búsqueda: '{query}' en tienda {self.store_id}")
                return

            columns = ["ID", "Cliente", "Productos", "Anticipo", "Total", "Saldo Pendiente", "Fecha Creación", "Fecha Modificación", "Fecha Vencimiento", "Estado"]
            column_widths = {
                "ID": 50,
                "Cliente": 150,
                "Productos": 100,
                "Anticipo": 100,
                "Total": 100,
                "Saldo Pendiente": 100,
                "Fecha Creación": 100,
                "Fecha Modificación": 100,
                "Fecha Vencimiento": 100,
                "Estado": 100
            }

            formatted_apartados = [
                {
                    "ID": apartado['id'],
                    "Cliente": apartado['nombre_completo'],
                    "Productos": ", ".join([f"{item['sku']} (x{item['cantidad']})" for item in json.loads(apartado['productos'])]),
                    "Anticipo": f"${apartado['anticipo']:.2f}",
                    "Total": f"${sum(item['precio'] * item['cantidad'] for item in json.loads(apartado['productos'])):.2f}",
                    "Saldo Pendiente": f"${sum(item['precio'] * item['cantidad'] for item in json.loads(apartado['productos'])) - apartado['anticipo']:.2f}",
                    "Fecha Creación": self.parse_date(apartado['fecha_creacion'], apartado['id']).strftime("%d/%m/%Y %H:%M:%S"),
                    "Fecha Modificación": self.parse_date(apartado['fecha_modificacion'], apartado['id']).strftime("%d/%m/%Y %H:%M:%S"),
                    "Fecha Vencimiento": self.parse_date(apartado['fecha_vencimiento'], apartado['id']).strftime("%d/%m/%Y %H:%M:%S"),
                    "Estado": apartado['estado']
                }
                for apartado in apartados
            ]

            def on_select(apartado):
                for item in self.ui.tree.get_children():
                    self.ui.tree.delete(item)
                self.ui.tree.insert("", "end", values=(
                    apartado['ID'],
                    apartado['Cliente'],
                    f"{len(json.loads(apartado['Productos']))} producto(s)",
                    apartado['Anticipo'],
                    apartado['Total'],
                    apartado['Saldo Pendiente'],
                    apartado['Fecha Creación'],
                    apartado['Fecha Modificación'],
                    apartado['Fecha Vencimiento'],
                    apartado['Estado']
                ))

            mostrar_ventana_seleccion(
                parent=self.ui.root,
                title="Seleccionar Apartado",
                items=formatted_apartados,
                columns=columns,
                column_widths=column_widths,
                on_select_callback=on_select
            )

            logging.debug("Resultados de búsqueda cargados")
        except Exception as e:
            logging.error(f"Error al buscar apartados en tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo buscar apartados: {str(e)}")