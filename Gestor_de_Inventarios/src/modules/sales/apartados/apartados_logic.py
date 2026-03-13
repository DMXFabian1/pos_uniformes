import logging
import json
import os
from datetime import datetime, timedelta
from src.core.config.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

class ApartadosLogic:
    def __init__(self, db_manager=None, user_id=None, store_id=1):
        self.db_manager = db_manager or DatabaseManager()
        self.user_id = user_id
        self.store_id = store_id
        self.initialize_modificaciones_apartados_table()
        self.db_manager.get_cursor().execute("CREATE INDEX IF NOT EXISTS idx_apartados_id_cliente ON apartados(id_cliente)")
        self.db_manager.conn.commit()
        logger.info(f"ApartadosLogic inicializado para tienda {self.store_id}")

    def initialize_modificaciones_apartados_table(self):
        """Crea la tabla modificaciones_apartados si no existe."""
        try:
            cursor = self.db_manager.get_cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS modificaciones_apartados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    apartado_id INTEGER NOT NULL,
                    user_id TEXT,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    productos_antiguos TEXT NOT NULL,
                    productos_nuevos TEXT NOT NULL,
                    descripcion TEXT,
                    store_id INTEGER,
                    FOREIGN KEY (apartado_id) REFERENCES apartados(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )
            """)
            self.db_manager.conn.commit()
            logger.info(f"Tabla 'modificaciones_apartados' verificada/creada con store_id para tienda {self.store_id}.")
        except Exception as e:
            logger.error(f"Error al crear tabla modificaciones_apartados para tienda {self.store_id}: {str(e)}")
            raise

    def generate_cancellation_receipt(self, apartado_id, cliente_nombre, usuario_nombre, productos, anticipo, subtotal, reembolso_info=None):
        """Genera un comprobante de cancelación y devuelve la ruta del archivo."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        receipt_dir = os.path.join("sales_reports", "cancelaciones")
        os.makedirs(receipt_dir, exist_ok=True)
        receipt_path = os.path.join(receipt_dir, f"cancelacion_{apartado_id}_{timestamp}.txt")

        with open(receipt_path, "w", encoding="utf-8") as f:
            f.write("===== Comprobante de Cancelación =====\n\n")
            f.write(f"ID Apartado: {apartado_id}\n")
            f.write(f"Cliente: {cliente_nombre}\n")
            f.write(f"Usuario: {usuario_nombre}\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("Productos:\n")
            for item in productos:
                f.write(f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${float(item['precio']):.2f}\n")
            f.write(f"\nSubtotal: ${subtotal:.2f}\n")
            f.write(f"Anticipo: ${float(anticipo):.2f}\n")
            f.write(f"Saldo Pendiente: ${(subtotal - float(anticipo)):.2f}\n")
            if reembolso_info:
                f.write(f"Estado de Reembolso: Reembolsado (${reembolso_info['monto']:.2f})\n")
            else:
                f.write("Estado de Reembolso: No aplica\n")
            f.write("\n=====================================\n")
        
        logger.info(f"Comprobante de cancelación generado: {receipt_path} para tienda {self.store_id}")
        return receipt_path

    def generate_completion_receipt(self, apartado_id, venta_id, cliente_nombre, usuario_nombre, productos, subtotal, anticipo, total_final, metodo_pago):
        """Genera un comprobante de completación de apartado y devuelve la ruta del archivo."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        receipt_dir = os.path.join("sales_reports", "ventas")
        os.makedirs(receipt_dir, exist_ok=True)
        receipt_path = os.path.join(receipt_dir, f"venta_apartado_{apartado_id}_{timestamp}.txt")

        with open(receipt_path, "w", encoding="utf-8") as f:
            f.write("===== Comprobante de Venta (Apartado Completado) =====\n\n")
            f.write(f"ID Apartado: {apartado_id}\n")
            f.write(f"ID Venta: {venta_id}\n")
            f.write(f"Cliente: {cliente_nombre}\n")
            f.write(f"Usuario: {usuario_nombre}\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("Productos:\n")
            for item in productos:
                f.write(f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${float(item['precio']):.2f}\n")
            f.write(f"\nSubtotal: ${subtotal:.2f}\n")
            f.write(f"Anticipo: ${float(anticipo):.2f}\n")
            f.write(f"Total (con IVA): ${total_final:.2f}\n")
            f.write(f"Método de Pago: {metodo_pago}\n")
            f.write(f"Saldo Pendiente: ${(total_final - float(anticipo)):.2f}\n")
            f.write("\n=====================================\n")
        
        logger.info(f"Comprobante de completación generado: {receipt_path} para tienda {self.store_id}")
        return receipt_path

    def generate_creation_receipt(self, apartado_id, cliente_nombre, usuario_nombre, productos, anticipo, subtotal, fecha_vencimiento):
        """Genera un comprobante de creación de apartado y devuelve la ruta del archivo."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        receipt_dir = os.path.join("sales_reports", "apartados")
        os.makedirs(receipt_dir, exist_ok=True)
        receipt_path = os.path.join(receipt_dir, f"apartado_{apartado_id}_{timestamp}.txt")

        with open(receipt_path, "w", encoding="utf-8") as f:
            f.write("===== Comprobante de Creación de Apartado =====\n\n")
            f.write(f"ID Apartado: {apartado_id}\n")
            f.write(f"Cliente: {cliente_nombre}\n")
            f.write(f"Usuario: {usuario_nombre}\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Fecha de Vencimiento: {fecha_vencimiento}\n\n")
            f.write("Productos:\n")
            for item in productos:
                f.write(f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${float(item['precio']):.2f}\n")
            f.write(f"\nSubtotal: ${subtotal:.2f}\n")
            f.write(f"Anticipo Inicial: ${float(anticipo):.2f}\n")
            f.write(f"Saldo Pendiente: ${(subtotal - float(anticipo)):.2f}\n")
            f.write("\n=====================================\n")
        
        logger.info(f"Comprobante de creación generado: {receipt_path} para tienda {self.store_id}")
        return receipt_path

    def generate_modification_receipt(self, apartado_id, cliente_nombre, usuario_nombre, productos_antiguos, productos_nuevos, anticipo, subtotal_antiguo, subtotal_nuevo):
        """Genera un comprobante de modificación de productos del apartado y devuelve la ruta del archivo."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        receipt_dir = os.path.join("sales_reports", "modificaciones")
        os.makedirs(receipt_dir, exist_ok=True)
        receipt_path = os.path.join(receipt_dir, f"modificacion_{apartado_id}_{timestamp}.txt")

        with open(receipt_path, "w", encoding="utf-8") as f:
            f.write("===== Comprobante de Modificación de Apartado =====\n\n")
            f.write(f"ID Apartado: {apartado_id}\n")
            f.write(f"Cliente: {cliente_nombre}\n")
            f.write(f"Usuario: {usuario_nombre}\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("Productos Antiguos:\n")
            for item in productos_antiguos:
                f.write(f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${float(item['precio']):.2f}\n")
            f.write(f"\nSubtotal Antiguo: ${subtotal_antiguo:.2f}\n\n")
            f.write("Productos Nuevos:\n")
            for item in productos_nuevos:
                f.write(f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${float(item['precio']):.2f}\n")
            f.write(f"\nSubtotal Nuevo: ${subtotal_nuevo:.2f}\n")
            f.write(f"Anticipo: ${float(anticipo):.2f}\n")
            f.write(f"Saldo Pendiente: ${(subtotal_nuevo - float(anticipo)):.2f}\n")
            f.write("\n=====================================\n")
        
        logger.info(f"Comprobante de modificación generado: {receipt_path} para tienda {self.store_id}")
        return receipt_path

    def cancelar_apartado(self, apartado_id):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("""
                SELECT a.id_cliente, a.productos, a.anticipo, a.estado, c.nombre_completo
                FROM apartados a
                JOIN clientes c ON a.id_cliente = c.id
                WHERE a.id = ? AND a.estado = 'activo' AND a.store_id = ?
            """, (apartado_id, self.store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError("Apartado no encontrado o ya procesado")

            id_cliente, productos_json, anticipo, estado, cliente_nombre = apartado
            productos = json.loads(productos_json)

            subtotal = sum(float(item['precio']) * int(item['cantidad']) for item in productos)
            saldo_pendiente = subtotal - float(anticipo)

            confirm_message = f"Cancelar Apartado ID {apartado_id}\n\n"
            confirm_message += f"Cliente: {cliente_nombre}\n"
            confirm_message += "Productos:\n"
            for item in productos:
                confirm_message += f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${float(item['precio']):.2f}\n"
            confirm_message += f"\nSubtotal: ${subtotal:.2f}\n"
            confirm_message += f"Anticipo: ${float(anticipo):.2f}\n"
            confirm_message += f"Saldo Pendiente: ${saldo_pendiente:.2f}\n"
            confirm_message += "Advertencia: Esta acción no se puede deshacer.\n"
            if anticipo > 0:
                confirm_message += "El anticipo podría requerir reembolso.\n"
            confirm_message += "¿Desea cancelar el apartado?"

            logger.info(f"Preparando cancelación de apartado ID {apartado_id} por usuario {self.user_id} en tienda {self.store_id}")

            return {
                "confirm_message": confirm_message,
                "anticipo": float(anticipo),
                "productos": productos
            }

        except ValueError as e:
            logger.error(f"Error de validación al preparar cancelación de apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al preparar cancelación de apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise Exception(f"No se pudo preparar la cancelación: {str(e)}")

    def confirmar_cancelacion(self, apartado_id, reembolsar_anticipo=False):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("""
                SELECT a.id_cliente, a.productos, a.anticipo, a.estado, c.nombre_completo
                FROM apartados a
                JOIN clientes c ON a.id_cliente = c.id
                WHERE a.id = ? AND a.estado = 'activo' AND a.store_id = ?
            """, (apartado_id, self.store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError("Apartado no encontrado o ya procesado")

            id_cliente, productos_json, anticipo, estado, cliente_nombre = apartado
            productos = json.loads(productos_json)

            subtotal = sum(float(item['precio']) * int(item['cantidad']) for item in productos)

            cursor.execute("""
                UPDATE apartados
                SET estado = 'cancelado',
                    fecha_modificacion = ?
                WHERE id = ? AND store_id = ?
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), apartado_id, self.store_id))

            for item in productos:
                cursor.execute("""
                    UPDATE productos
                    SET inventario = inventario + ?
                    WHERE sku = ? AND store_id = ?
                """, (int(item['cantidad']), item['sku'], self.store_id))

            reembolso_info = None
            if reembolsar_anticipo and anticipo > 0:
                cursor.execute("""
                    INSERT INTO reembolsos (id_apartado, monto, fecha, user_id, store_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (apartado_id, float(anticipo), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.user_id, self.store_id))
                reembolso_info = {"monto": float(anticipo)}

            cursor.execute("SELECT username FROM users WHERE id = ?", (self.user_id,))
            user = cursor.fetchone()
            usuario_nombre = user['username'] if user else "Desconocido"

            receipt_path = self.generate_cancellation_receipt(
                apartado_id, cliente_nombre, usuario_nombre, productos, anticipo, subtotal, reembolso_info
            )

            self.db_manager.conn.commit()
            logger.info(f"Apartado ID {apartado_id} cancelado por usuario {self.user_id} en tienda {self.store_id}. Reembolso: {reembolsar_anticipo}")

            return {
                "success": True,
                "message": "Apartado cancelado exitosamente",
                "receipt_path": receipt_path
            }

        except ValueError as e:
            logger.error(f"Error de validación al cancelar apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise
        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Error inesperado al cancelar apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise Exception(f"No se pudo cancelar el apartado: {str(e)}")

    def extender_apartado(self, apartado_id):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("""
                SELECT a.id_cliente, a.productos, a.anticipo, a.estado, a.fecha_vencimiento, c.nombre_completo
                FROM apartados a
                JOIN clientes c ON a.id_cliente = c.id
                WHERE a.id = ? AND a.estado = 'activo' AND a.store_id = ?
            """, (apartado_id, self.store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError("Apartado no encontrado o ya procesado")

            id_cliente, productos_json, anticipo, estado, fecha_vencimiento, cliente_nombre = apartado
            productos = json.loads(productos_json)

            subtotal = sum(float(item['precio']) * int(item['cantidad']) for item in productos)
            saldo_pendiente = subtotal - float(anticipo)

            fecha_modificacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            nueva_fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

            confirm_message = f"Extender Apartado ID {apartado_id}\n\n"
            confirm_message += f"Cliente: {cliente_nombre}\n"
            confirm_message += "Productos:\n"
            for item in productos:
                confirm_message += f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${float(item['precio']):.2f}\n"
            confirm_message += f"\nSubtotal: ${subtotal:.2f}\n"
            confirm_message += f"Anticipo: ${float(anticipo):.2f}\n"
            confirm_message += f"Saldo Pendiente: ${saldo_pendiente:.2f}\n"
            confirm_message += f"Fecha de Vencimiento Actual: {fecha_vencimiento}\n"
            confirm_message += f"Nueva Fecha de Vencimiento: {nueva_fecha_vencimiento}\n"
            confirm_message += "¿Desea extender el apartado?"

            logger.info(f"Preparando extensión de apartado ID {apartado_id} por usuario {self.user_id} en tienda {self.store_id}")

            return {
                "confirm_message": confirm_message,
                "nueva_fecha_vencimiento": nueva_fecha_vencimiento,
                "fecha_modificacion": fecha_modificacion
            }

        except ValueError as e:
            logger.error(f"Error de validación al preparar extensión de apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al preparar extensión de apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise Exception(f"No se pudo preparar la extensión: {str(e)}")

    def confirmar_extension(self, apartado_id, nueva_fecha_vencimiento, fecha_modificacion):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("UPDATE apartados SET fecha_vencimiento = ?, fecha_modificacion = ? WHERE id = ? AND store_id = ?",
                          (nueva_fecha_vencimiento, fecha_modificacion, apartado_id, self.store_id))
            self.db_manager.conn.commit()
            logger.info(f"Apartado {apartado_id} extendido hasta {nueva_fecha_vencimiento} por usuario {self.user_id} en tienda {self.store_id}")
        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Error al extender apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise Exception(f"No se pudo extender el apartado: {str(e)}")

    def registrar_anticipo(self, apartado_id, monto):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            if monto is None:
                raise ValueError("El monto del anticipo no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("""
                SELECT a.id_cliente, a.productos, a.anticipo, a.estado, a.fecha_vencimiento, c.nombre_completo
                FROM apartados a
                JOIN clientes c ON a.id_cliente = c.id
                WHERE a.id = ? AND a.estado = 'activo' AND a.store_id = ?
            """, (apartado_id, self.store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError("Apartado no encontrado o no activo")

            id_cliente, productos_json, anticipo_actual, estado, fecha_vencimiento, cliente_nombre = apartado
            productos = json.loads(productos_json)

            if monto <= 0:
                raise ValueError("El monto del anticipo debe ser positivo")

            if anticipo_actual is None:
                anticipo_actual = 0.0
            subtotal = sum(float(item['precio']) * int(item['cantidad']) for item in productos)
            nuevo_anticipo = float(anticipo_actual) + float(monto)
            saldo_pendiente = subtotal - nuevo_anticipo

            if saldo_pendiente < 0:
                raise ValueError(f"El anticipo total (${nuevo_anticipo:.2f}) no puede exceder el saldo pendiente (${subtotal - float(anticipo_actual):.2f}).")

            fecha_modificacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            nueva_fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

            confirm_message = f"Registrar Anticipo para Apartado ID {apartado_id}\n\n"
            confirm_message += f"Cliente: {cliente_nombre}\n"
            confirm_message += "Productos:\n"
            for item in productos:
                confirm_message += f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${float(item['precio']):.2f}\n"
            confirm_message += f"\nSubtotal: ${subtotal:.2f}\n"
            confirm_message += f"Anticipo Actual: ${float(anticipo_actual):.2f}\n"
            confirm_message += f"Nuevo Anticipo: ${monto:.2f}\n"
            confirm_message += f"Anticipo Total: ${nuevo_anticipo:.2f}\n"
            confirm_message += f"Saldo Pendiente: ${saldo_pendiente:.2f}\n"
            confirm_message += f"Fecha de Vencimiento Actual: {fecha_vencimiento}\n"
            confirm_message += f"Nueva Fecha de Vencimiento: {nueva_fecha_vencimiento}\n"
            confirm_message += "¿Desea registrar el anticipo?"

            logger.info(f"Preparando registro de anticipo de {monto} para apartado ID {apartado_id} por usuario {self.user_id} en tienda {self.store_id}")

            return {
                "confirm_message": confirm_message,
                "monto": monto,
                "nuevo_anticipo": nuevo_anticipo,
                "fecha_modificacion": fecha_modificacion,
                "nueva_fecha_vencimiento": nueva_fecha_vencimiento
            }

        except ValueError as e:
            logger.error(f"Error de validación al preparar registro de anticipo para apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al preparar registro de anticipo para apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise Exception(f"No se pudo preparar el registro del anticipo: {str(e)}")

    def confirmar_anticipo(self, apartado_id, monto, nuevo_anticipo, fecha_modificacion, nueva_fecha_vencimiento):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            if monto is None:
                raise ValueError("El monto del anticipo no puede ser None")
            if self.user_id is None:
                raise ValueError("El ID del usuario no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("SELECT estado FROM apartados WHERE id = ? AND estado = 'activo' AND store_id = ?", (apartado_id, self.store_id))
            result = cursor.fetchone()
            if not result:
                raise ValueError("Apartado no encontrado o no activo")

            cursor.execute("""
                UPDATE apartados
                SET anticipo = ?,
                    fecha_modificacion = ?,
                    fecha_vencimiento = ?
                WHERE id = ? AND store_id = ?
            """, (nuevo_anticipo, fecha_modificacion, nueva_fecha_vencimiento, apartado_id, self.store_id))

            cursor.execute("INSERT INTO anticipos (apartado_id, monto, fecha, store_id) VALUES (?, ?, ?, ?)",
                          (apartado_id, monto, fecha_modificacion, self.store_id))

            cursor.execute("""
                SELECT a.id_cliente, a.productos, a.anticipo, c.nombre_completo
                FROM apartados a
                JOIN clientes c ON a.id_cliente = c.id
                WHERE a.id = ? AND a.store_id = ?
            """, (apartado_id, self.store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError("Apartado no encontrado después de la actualización")
            cliente_nombre = apartado['nombre_completo']
            productos = json.loads(apartado['productos'])
            subtotal = sum(float(item['precio']) * int(item['cantidad']) for item in productos)

            cursor.execute("SELECT username FROM users WHERE id = ? AND store_id = ?", (self.user_id, self.store_id))
            user = cursor.fetchone()
            usuario_nombre = user['username'] if user else "Desconocido"

            comprobantes_dir = os.path.join("sales_reports", "abonos")
            os.makedirs(comprobantes_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            comprobante_filename = f"comprobante_abono_{apartado_id}_{timestamp}.txt"
            comprobante_path = os.path.join(comprobantes_dir, comprobante_filename)

            with open(comprobante_path, "w", encoding="utf-8") as f:
                f.write("===== Comprobante de Abono =====\n\n")
                f.write(f"Apartado ID: {apartado_id}\n")
                f.write(f"Cliente: {cliente_nombre}\n")
                f.write(f"Registrado por: {usuario_nombre}\n")
                f.write(f"Fecha: {fecha_modificacion}\n\n")
                f.write("Productos:\n")
                for item in productos:
                    f.write(f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${float(item['precio']):.2f}\n")
                f.write(f"\nSubtotal: ${subtotal:.2f}\n")
                f.write(f"Anticipo Anterior: ${(nuevo_anticipo - monto):.2f}\n")
                f.write(f"Monto del Abono: ${monto:.2f}\n")
                f.write(f"Anticipo Total: ${nuevo_anticipo:.2f}\n")
                f.write(f"Saldo Pendiente: ${(subtotal - nuevo_anticipo):.2f}\n")
                f.write("\n=============================\n")

            self.db_manager.conn.commit()
            logger.info(f"Anticipo de {monto} registrado para apartado {apartado_id} por usuario {self.user_id} en tienda {self.store_id}")
            logger.info(f"Comprobante generado: {comprobante_path} para tienda {self.store_id}")

            return comprobante_path

        except ValueError as e:
            self.db_manager.conn.rollback()
            logger.error(f"Error de validación al registrar anticipo para apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise Exception(f"No se pudo registrar el anticipo: {str(e)}")
        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Error inesperado al registrar anticipo para apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise Exception(f"No se pudo registrar el anticipo: {str(e)}")

    def buscar_apartados_por_cliente(self, id_cliente, estado="activo", limit=None, offset=0):
        try:
            if id_cliente is None:
                raise ValueError("El ID del cliente no puede ser None")
            cursor = self.db_manager.get_cursor()
            query = """
                SELECT a.id, c.nombre_completo, a.productos, a.anticipo, a.fecha_creacion, a.fecha_vencimiento, a.estado
                FROM apartados a
                LEFT JOIN clientes c ON a.id_cliente = c.id
                WHERE a.id_cliente = ? AND a.estado = ? AND a.store_id = ?
            """
            params = [id_cliente, estado, self.store_id]
            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error al buscar apartados para cliente {id_cliente} en tienda {self.store_id}: {str(e)}")
            raise

    def buscar_clientes(self, query="", limit=None, offset=0):
        try:
            return self.db_manager.buscar_clientes(query=query, store_id=self.store_id, limit=limit, offset=offset)
        except Exception as e:
            logger.error(f"Error al buscar clientes con query '{query}' en tienda {self.store_id}: {str(e)}")
            raise

    def crear_apartado(self, id_cliente, user_id, productos, anticipo, store_id=1):
        try:
            if id_cliente is None:
                raise ValueError("El ID del cliente no puede ser None")
            if user_id is None:
                raise ValueError("El ID del usuario no puede ser None")
            cursor = self.db_manager.get_cursor()
            if anticipo < 0:
                raise ValueError("El anticipo no puede ser negativo")
            
            for item in productos:
                cursor.execute("SELECT nombre, precio, inventario FROM productos WHERE sku = ? AND store_id = ?", (item['sku'], store_id))
                producto = cursor.fetchone()
                if not producto:
                    raise ValueError(f"SKU {item['sku']} no existe en tienda {store_id}")
                if item['cantidad'] > producto['inventario']:
                    raise ValueError(f"No hay suficiente inventario para SKU {item['sku']} (disponible: {producto['inventario']}) en tienda {store_id}")
                item['nombre'] = producto['nombre']
                item['precio'] = producto['precio']
            
            cursor.execute("SELECT nombre_completo FROM clientes WHERE id = ? AND store_id = ?", (id_cliente, store_id))
            cliente = cursor.fetchone()
            if not cliente:
                raise ValueError(f"Cliente con ID {id_cliente} no existe en tienda {store_id}")
            cliente_nombre = cliente['nombre_completo']
            
            fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                INSERT INTO apartados (id_cliente, user_id, productos, anticipo, fecha_creacion, fecha_vencimiento, estado, store_id)
                VALUES (?, ?, ?, ?, ?, ?, 'activo', ?)
            """, (id_cliente, user_id, json.dumps(productos), anticipo, fecha_creacion, fecha_vencimiento, store_id))
            apartado_id = cursor.lastrowid

            cursor.execute("SELECT username FROM users WHERE id = ? AND store_id = ?", (user_id, store_id))
            user = cursor.fetchone()
            usuario_nombre = user['username'] if user else "Desconocido"

            subtotal = sum(float(item['precio']) * int(item['cantidad']) for item in productos)

            receipt_path = self.generate_creation_receipt(
                apartado_id, cliente_nombre, usuario_nombre, productos, anticipo, subtotal, fecha_vencimiento
            )

            self.db_manager.conn.commit()
            logger.info(f"Apartado creado con ID {apartado_id} para cliente {id_cliente} en tienda {store_id}, Comprobante: {receipt_path}")

            return {
                "success": True,
                "message": "Apartado creado exitosamente",
                "apartado_id": apartado_id,
                "receipt_path": receipt_path
            }

        except ValueError as e:
            logger.error(f"Error de validación al crear apartado para cliente {id_cliente} en tienda {store_id}: {str(e)}")
            raise
        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Error inesperado al crear apartado para cliente {id_cliente} en tienda {store_id}: {str(e)}")
            raise Exception(f"No se pudo crear el apartado: {str(e)}")

    def completar_apartado(self, apartado_id, metodo_pago, tasa_iva):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("""
                SELECT a.id_cliente, a.productos, a.anticipo, c.nombre_completo
                FROM apartados a
                JOIN clientes c ON a.id_cliente = c.id
                WHERE a.id = ? AND a.estado = 'activo' AND a.store_id = ?
            """, (apartado_id, self.store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError("Apartado no encontrado o ya completado")

            id_cliente, productos_json, anticipo, cliente_nombre = apartado
            productos = json.loads(productos_json)

            for item in productos:
                item['precio'] = float(item['precio'])
                item['cantidad'] = int(item['cantidad'])
                item['descuento'] = float(item.get('descuento', 0))

            subtotal = sum(item['precio'] * item['cantidad'] for item in productos)
            total_final = float(subtotal * (1 + tasa_iva))

            cursor.execute("""
                INSERT INTO ventas (user_id, id_cliente, metodo_pago, fecha, total, items, store_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.user_id, id_cliente, metodo_pago, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total_final, json.dumps(productos), self.store_id))
            venta_id = cursor.lastrowid

            cursor.execute("""
                UPDATE apartados
                SET estado = 'completado',
                    fecha_modificacion = ?
                WHERE id = ? AND store_id = ?
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), apartado_id, self.store_id))

            cursor.execute("SELECT username FROM users WHERE id = ?", (self.user_id,))
            user = cursor.fetchone()
            usuario_nombre = user['username'] if user else "Desconocido"

            receipt_path = self.generate_completion_receipt(
                apartado_id, venta_id, cliente_nombre, usuario_nombre, productos, subtotal, anticipo, total_final, metodo_pago
            )

            self.db_manager.conn.commit()
            logger.info(f"Apartado {apartado_id} completado, venta registrada con ID {venta_id} en tienda {self.store_id}, Comprobante: {receipt_path}")

            return {
                "success": True,
                "message": "Apartado completado exitosamente",
                "venta_id": venta_id,
                "receipt_path": receipt_path
            }

        except ValueError as e:
            logger.error(f"Error de validación al completar apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise
        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Error inesperado al completar apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise Exception(f"No se pudo completar el apartado: {str(e)}")

    def modificar_productos_apartado(self, apartado_id, productos_nuevos):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("""
                SELECT a.id, a.productos, a.anticipo, a.estado, c.nombre_completo
                FROM apartados a
                JOIN clientes c ON a.id_cliente = c.id
                WHERE a.id = ? AND a.store_id = ?
            """, (apartado_id, self.store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError("Apartado no encontrado")
            if apartado['estado'] != 'activo':
                raise ValueError(f"El apartado ID {apartado_id} no está activo")

            productos_antiguos = json.loads(apartado['productos'])
            cliente_nombre = apartado['nombre_completo']
            anticipo = float(apartado['anticipo'])

            if not productos_nuevos:
                raise ValueError("El apartado debe contener al menos un producto.")

            subtotal_antiguo = sum(float(item['precio']) * int(item['cantidad']) for item in productos_antiguos)

            cantidades_antiguas = {item['sku']: int(item['cantidad']) for item in productos_antiguos}
            cantidades_nuevas = {}
            productos_nuevos_ajustados = []

            for item in productos_nuevos:
                cursor.execute("SELECT nombre, precio, inventario FROM productos WHERE sku = ? AND store_id = ?", (item['sku'], self.store_id))
                producto = cursor.fetchone()
                if not producto:
                    raise ValueError(f"SKU {item['sku']} no existe en tienda {self.store_id}")
                if item['cantidad'] <= 0:
                    raise ValueError(f"La cantidad del producto {item['sku']} debe ser mayor a 0")

                cantidad_antigua = cantidades_antiguas.get(item['sku'], 0)
                cantidad_nueva = int(item['cantidad'])
                cantidades_nuevas[item['sku']] = cantidad_nueva
                diferencia = cantidad_nueva - cantidad_antigua

                logger.debug(f"SKU: {item['sku']}, Cantidad Antigua: {cantidad_antigua}, Cantidad Nueva: {cantidad_nueva}, Diferencia: {diferencia}, Stock Disponible: {producto['inventario']} en tienda {self.store_id}")

                if diferencia > 0:
                    if diferencia > producto['inventario']:
                        raise ValueError(f"No hay suficiente inventario para SKU {item['sku']} (disponible: {producto['inventario']}, solicitado adicional: {diferencia}) en tienda {self.store_id}")

                precio = next((p['precio'] for p in productos_antiguos if p['sku'] == item['sku']), producto['precio'])
                item['nombre'] = producto['nombre']
                item['precio'] = precio
                item['diferencia_inventario'] = diferencia
                productos_nuevos_ajustados.append(item)

            subtotal_nuevo = sum(float(item['precio']) * int(item['cantidad']) for item in productos_nuevos_ajustados)

            confirm_message = f"Modificar Productos del Apartado ID {apartado_id}\n\n"
            confirm_message += f"Cliente: {cliente_nombre}\n\n"
            confirm_message += "Productos Actuales:\n"
            for item in productos_antiguos:
                confirm_message += f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - ${float(item['precio']):.2f}\n"
            confirm_message += f"\nSubtotal Actual: ${subtotal_antiguo:.2f}\n\n"
            confirm_message += "Productos Propuestos:\n"
            for item in productos_nuevos_ajustados:
                precio_actual = cursor.execute("SELECT precio FROM productos WHERE sku = ? AND store_id = ?", (item['sku'], self.store_id)).fetchone()['precio']
                precio_texto = f"${float(item['precio']):.2f}"
                if float(item['precio']) != precio_actual:
                    precio_texto += f" (Precio original, actual: ${precio_actual:.2f})"
                confirm_message += f"- {item['sku']} ({item['nombre']}) (x{item['cantidad']}) - {precio_texto}\n"
            confirm_message += f"\nSubtotal Propuesto: ${subtotal_nuevo:.2f}\n"
            confirm_message += f"Anticipo: ${anticipo:.2f}\n"
            confirm_message += f"Saldo Pendiente Actual: ${(subtotal_antiguo - anticipo):.2f}\n"
            confirm_message += f"Saldo Pendiente Propuesto: ${(subtotal_nuevo - anticipo):.2f}\n\n"
            confirm_message += "¿Desea modificar los productos del apartado?"

            logger.info(f"Preparando modificación de productos para apartado ID {apartado_id} por usuario {self.user_id} en tienda {self.store_id}")

            return {
                "confirm_message": confirm_message,
                "productos_antiguos": productos_antiguos,
                "productos_nuevos": productos_nuevos_ajustados,
                "subtotal_antiguo": subtotal_antiguo,
                "subtotal_nuevo": subtotal_nuevo,
                "anticipo": anticipo,
                "cliente_nombre": cliente_nombre,
                "cantidades_antiguas": cantidades_antiguas,
                "cantidades_nuevas": cantidades_nuevas
            }

        except ValueError as e:
            logger.error(f"Error de validación al preparar modificación de productos para apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al preparar modificación de productos para apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise Exception(f"No se pudo preparar la modificación: {str(e)}")

    def confirmar_modificacion_productos(self, apartado_id, productos_antiguos, productos_nuevos, cliente_nombre, subtotal_antiguo, subtotal_nuevo, anticipo, cantidades_antiguas, cantidades_nuevas):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("SELECT estado FROM apartados WHERE id = ? AND estado = 'activo' AND store_id = ?", (apartado_id, self.store_id))
            result = cursor.fetchone()
            if not result:
                raise ValueError("Apartado no encontrado o no activo")

            for item in productos_nuevos:
                sku = item['sku']
                diferencia = item['diferencia_inventario']
                logger.debug(f"Ajustando inventario para SKU {sku}, Diferencia: {diferencia} en tienda {self.store_id}")
                if diferencia != 0:
                    cursor.execute("""
                        UPDATE productos
                        SET inventario = inventario - ?
                        WHERE sku = ? AND store_id = ?
                    """, (diferencia, sku, self.store_id))
                    cursor.execute("SELECT inventario FROM productos WHERE sku = ? AND store_id = ?", (sku, self.store_id))
                    nuevo_inventario = cursor.fetchone()['inventario']
                    logger.debug(f"Inventario actualizado para SKU {sku}: {nuevo_inventario} en tienda {self.store_id}")
                    if nuevo_inventario < 0:
                        raise ValueError(f"El inventario para SKU {sku} no puede ser negativo: {nuevo_inventario} en tienda {self.store_id}")

            fecha_modificacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                UPDATE apartados
                SET productos = ?,
                    fecha_modificacion = ?
                WHERE id = ? AND store_id = ?
            """, (json.dumps(productos_nuevos), fecha_modificacion, apartado_id, self.store_id))

            cursor.execute("SELECT username FROM users WHERE id = ?", (self.user_id,))
            user = cursor.fetchone()
            usuario_nombre = user['username'] if user else "Desconocido"

            descripcion = "Modificación de productos:\n"
            for sku, cantidad_nueva in cantidades_nuevas.items():
                cantidad_antigua = cantidades_antiguas.get(sku, 0)
                if cantidad_antigua == 0:
                    descripcion += f"- Añadido: {sku} (x{cantidad_nueva})\n"
                elif cantidad_nueva > cantidad_antigua:
                    descripcion += f"- Aumentado: {sku} de {cantidad_antigua} a {cantidad_nueva}\n"
                elif cantidad_nueva < cantidad_antigua:
                    descripcion += f"- Reducido: {sku} de {cantidad_antigua} a {cantidad_nueva}\n"
            for sku, cantidad_antigua in cantidades_antiguas.items():
                if sku not in cantidades_nuevas:
                    descripcion += f"- Eliminado: {sku} (x{cantidad_antigua})\n"

            cursor.execute("""
                INSERT INTO modificaciones_apartados (apartado_id, user_id, fecha, productos_antiguos, productos_nuevos, descripcion, store_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                apartado_id,
                self.user_id,
                fecha_modificacion,
                json.dumps(productos_antiguos),
                json.dumps(productos_nuevos),
                descripcion,
                self.store_id
            ))

            receipt_path = self.generate_modification_receipt(
                apartado_id, cliente_nombre, usuario_nombre, productos_antiguos, productos_nuevos, anticipo, subtotal_antiguo, subtotal_nuevo
            )

            self.db_manager.conn.commit()
            logger.info(f"Productos modificados para apartado {apartado_id} en tienda {self.store_id}, Comprobante: {receipt_path}")

            return receipt_path

        except Exception as e:
            self.db_manager.conn.rollback()
            logger.error(f"Error al modificar productos para apartado {apartado_id} en tienda {self.store_id}: {str(e)}")
            raise Exception(f"No se pudo modificar los productos: {str(e)}")

    def obtener_anticipos(self, apartado_id, store_id=1):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("SELECT monto, fecha FROM anticipos WHERE apartado_id = ? AND store_id = ? ORDER BY fecha", (apartado_id, store_id))
            anticipos = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Se obtuvieron {len(anticipos)} anticipos para el apartado {apartado_id} en tienda {store_id}")
            return anticipos
        except Exception as e:
            logger.error(f"Error al obtener anticipos para apartado {apartado_id} en tienda {store_id}: {str(e)}")
            return []

    def obtener_modificaciones(self, apartado_id, store_id=1):
        try:
            if apartado_id is None:
                raise ValueError("El ID del apartado no puede ser None")
            cursor = self.db_manager.get_cursor()
            cursor.execute("SELECT * FROM modificaciones_apartados WHERE apartado_id = ? AND store_id = ? ORDER BY fecha DESC", (apartado_id, store_id))
            modificaciones = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Se obtuvieron {len(modificaciones)} modificaciones para el apartado {apartado_id} en tienda {store_id}")
            return modificaciones
        except Exception as e:
            logger.error(f"Error al obtener modificaciones para apartado {apartado_id} en tienda {store_id}: {str(e)}")
            return []

    def agregar_cliente(self, nombre_completo, numero):
       """Añade un nuevo cliente usando DatabaseManager."""
       try:
           if not nombre_completo:
               raise ValueError("El nombre completo es obligatorio")
           cliente_id = self.db_manager.registrar_cliente(nombre_completo, numero, store_id=self.store_id)
           logger.info(f"Cliente agregado con ID {cliente_id} en tienda {self.store_id}")
           return cliente_id
       except Exception as e:
           logger.error(f"Error al agregar cliente en tienda {self.store_id}: {str(e)}")
           raise
    
    def editar_cliente(self, cliente_id, nombre_completo, numero):
       """Edita un cliente existente usando DatabaseManager."""
       try:
           if not nombre_completo:
               raise ValueError("El nombre completo es obligatorio")
           if not self.db_manager.actualizar_cliente(cliente_id, nombre_completo, numero, store_id=self.store_id):
               raise ValueError(f"Cliente con ID {cliente_id} no encontrado en tienda {self.store_id}")
           logger.info(f"Cliente {cliente_id} actualizado en tienda {self.store_id}")
       except Exception as e:
           logger.error(f"Error al editar cliente {cliente_id} en tienda {self.store_id}: {str(e)}")
           raise
       
    def eliminar_cliente(self, cliente_id):
       """Elimina un cliente usando DatabaseManager."""
       try:
           cursor = self.db_manager.get_cursor()
           cursor.execute("SELECT COUNT(*) FROM apartados WHERE id_cliente = ? AND store_id = ?", (cliente_id, self.store_id))
           if cursor.fetchone()[0] > 0:
               raise ValueError("No se puede eliminar: el cliente tiene apartados asociados")
           if not self.db_manager.eliminar_cliente(cliente_id, store_id=self.store_id):
               raise ValueError(f"Cliente con ID {cliente_id} no encontrado en tienda {self.store_id}")
           logger.info(f"Cliente {cliente_id} eliminado en tienda {self.store_id}")
       except Exception as e:
           logger.error(f"Error al eliminar cliente {cliente_id} en tienda {self.store_id}: {str(e)}")
           raise