import sqlite3
import logging
import os
import bcrypt
import json
from datetime import datetime, timedelta
from src.core.config.config import CONFIG

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.db_path = os.path.join(CONFIG['ROOT_FOLDER'], CONFIG['DB_NAME'])
            cls._instance.conn = None
            cls._instance.connect()
            cls._instance.ensure_tables()  # Añadido para asegurar que las tablas se creen
        return cls._instance

    def connect(self):
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
                logger.info(f"Directorio creado: {db_dir}")

            if not os.path.exists(self.db_path):
                logger.warning(f"El archivo de base de datos {self.db_path} no existe. Se creará uno nuevo.")

            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Conexión a {self.db_path} establecida.")
        except sqlite3.Error as e:
            logger.error(f"Error al conectar a la base de datos {self.db_path}: {str(e)}")
            self.conn = None
            raise

    def ensure_connection(self):
        if self.conn is None:
            logger.warning("Conexión a la base de datos no está activa. Intentando reconectar...")
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    self.connect()
                    logger.debug(f"Reconexión exitosa en intento {attempt}")
                    break
                except sqlite3.Error as e:
                    if attempt == max_attempts:
                        logger.error(f"No se pudo reconectar después de {max_attempts} intentos: {str(e)}")
                        raise sqlite3.Error(f"No se pudo establecer la conexión a la base de datos después de {max_attempts} intentos: {str(e)}")
                    logger.warning(f"Intento {attempt} fallido. Reintentando...")

    def get_escuelas(self, store_id=1):
        """Obtiene todas las escuelas para una tienda específica."""
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT id, nombre FROM escuelas WHERE store_id = ? ORDER BY nombre", (store_id,))
            escuelas = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"Obtenidas {len(escuelas)} escuelas para tienda {store_id}")
            return escuelas
        except sqlite3.Error as e:
            logger.error(f"Error al obtener escuelas para tienda {store_id}: {str(e)}")
            return []

    def add_escuela(self, nombre, store_id=1):
        """Añade una nueva escuela y devuelve su ID."""
        try:
            cursor = self.get_cursor()
            cursor.execute("INSERT INTO escuelas (nombre, store_id) VALUES (?, ?)", (nombre, store_id))
            self.commit()
            cursor.execute("SELECT last_insert_rowid()")
            escuela_id = cursor.fetchone()[0]
            logger.info(f"Escuela '{nombre}' añadida con ID {escuela_id} para tienda {store_id}")
            return escuela_id
        except sqlite3.Error as e:
            logger.error(f"Error al añadir escuela '{nombre}' para tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def migrate_dates(self):
        """Migra las fechas en las tablas apartados, anticipos y reembolsos al formato %Y-%m-%d %H:%M:%S."""
        try:
            cursor = self.get_cursor()

            # Verificar primero si store_id existe en apartados y añadirlo si no
            cursor.execute("PRAGMA table_info(apartados)")
            columns = [col[1] for col in cursor.fetchall()]
            if "store_id" not in columns:
                logger.warning("Añadiendo columna 'store_id' a la tabla 'apartados' antes de migrar fechas...")
                cursor.execute("ALTER TABLE apartados ADD COLUMN store_id INTEGER")
                cursor.execute("UPDATE apartados SET store_id = 1 WHERE store_id IS NULL")
                self.commit()
                logger.info("Columna 'store_id' añadida a apartados antes de migrar fechas.")

            cursor.execute("SELECT id, fecha_creacion, fecha_modificacion, fecha_vencimiento, store_id FROM apartados")
            apartados = cursor.fetchall()
            for apartado in apartados:
                apartado_id = apartado['id']
                store_id = apartado['store_id']
                updates = []
                params = []

                fecha_creacion = apartado['fecha_creacion']
                if fecha_creacion is None:
                    fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    updates.append("fecha_creacion = ?")
                    params.append(fecha_creacion)
                else:
                    try:
                        datetime.strptime(fecha_creacion, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        fecha_creacion = f"{fecha_creacion} 00:00:00"
                        updates.append("fecha_creacion = ?")
                        params.append(fecha_creacion)

                fecha_modificacion = apartado['fecha_modificacion']
                if fecha_modificacion is None:
                    fecha_modificacion = fecha_creacion  # Usar fecha_creacion como fallback
                    updates.append("fecha_modificacion = ?")
                    params.append(fecha_modificacion)
                else:
                    try:
                        datetime.strptime(fecha_modificacion, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        fecha_modificacion = f"{fecha_modificacion} 00:00:00"
                        updates.append("fecha_modificacion = ?")
                        params.append(fecha_modificacion)

                fecha_vencimiento = apartado['fecha_vencimiento']
                if fecha_vencimiento is None:
                    fecha_vencimiento = (datetime.strptime(fecha_creacion, "%Y-%m-%d %H:%M:%S") + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
                    updates.append("fecha_vencimiento = ?")
                    params.append(fecha_vencimiento)
                else:
                    try:
                        datetime.strptime(fecha_vencimiento, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        fecha_vencimiento = f"{fecha_vencimiento} 00:00:00"
                        updates.append("fecha_vencimiento = ?")
                        params.append(fecha_vencimiento)

                if updates:
                    params.append(apartado_id)
                    update_query = f"UPDATE apartados SET {', '.join(updates)} WHERE id = ? AND store_id = ?"
                    params.append(store_id)
                    cursor.execute(update_query, params)

            cursor.execute("SELECT id, fecha, store_id FROM anticipos")
            anticipos = cursor.fetchall()
            for anticipo in anticipos:
                anticipo_id = anticipo['id']
                store_id = anticipo['store_id']
                fecha = anticipo['fecha']
                if fecha is None:
                    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("UPDATE anticipos SET fecha = ? WHERE id = ? AND store_id = ?", (fecha, anticipo_id, store_id))
                else:
                    try:
                        datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        fecha = f"{fecha} 00:00:00"
                        cursor.execute("UPDATE anticipos SET fecha = ? WHERE id = ? AND store_id = ?", (fecha, anticipo_id, store_id))

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reembolsos'")
            if cursor.fetchone():
                cursor.execute("SELECT id_reembolso, fecha, store_id FROM reembolsos")
                reembolsos = cursor.fetchall()
                for reembolso in reembolsos:
                    reembolso_id = reembolso['id_reembolso']
                    store_id = reembolso['store_id']
                    fecha = reembolso['fecha']
                    if fecha is None:
                        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cursor.execute("UPDATE reembolsos SET fecha = ? WHERE id_reembolso = ? AND store_id = ?", (fecha, reembolso_id, store_id))
                    else:
                        try:
                            datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            fecha = f"{fecha} 00:00:00"
                            cursor.execute("UPDATE reembolsos SET fecha = ? WHERE id_reembolso = ? AND store_id = ?", (fecha, reembolso_id, store_id))

            self.commit()
            logger.info("Migración de fechas completada.")
        except sqlite3.Error as e:
            logger.error(f"Error al migrar fechas: {str(e)}")
            self.rollback()
            raise

    def initialize_default_user(self, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE store_id = ?", (store_id,))
            user_count = cursor.fetchone()[0]
            if user_count == 0:
                password = "admin123"
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute(
                    "INSERT INTO users (username, password, role, store_id) VALUES (?, ?, ?, ?)",
                    ("admin", hashed_password, "admin", store_id)
                )
                self.commit()
                logger.info(f"Usuario predeterminado 'admin' creado con contraseña 'admin123' para tienda {store_id}.")
        except sqlite3.Error as e:
            logger.error(f"Error al crear usuario predeterminado para tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def ensure_tables(self):
        try:
            cursor = self.get_cursor()

            # Migrar todas las tablas para asegurar que tengan store_id al inicio
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(users)")
                columns = [col[1] for col in cursor.fetchall()]
                if "store_id" not in columns:
                    logger.warning("Añadiendo columna 'store_id' a la tabla 'users'...")
                    cursor.execute("ALTER TABLE users ADD COLUMN store_id INTEGER")
                    cursor.execute("UPDATE users SET store_id = 1 WHERE store_id IS NULL")
                    self.commit()
                    logger.info("Columna 'store_id' añadida a users.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='productos'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(productos)")
                columns = [col[1] for col in cursor.fetchall()]
                if "store_id" not in columns:
                    logger.warning("Añadiendo columna 'store_id' a la tabla 'productos'...")
                    cursor.execute("ALTER TABLE productos ADD COLUMN store_id INTEGER")
                    cursor.execute("UPDATE productos SET store_id = 1 WHERE store_id IS NULL")
                    self.commit()
                    logger.info("Columna 'store_id' añadida a productos.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contador_sku'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(contador_sku)")
                columns = [col[1] for col in cursor.fetchall()]
                if "store_id" not in columns:
                    logger.warning("Añadiendo columna 'store_id' a la tabla 'contador_sku'...")
                    cursor.execute("ALTER TABLE contador_sku ADD COLUMN store_id INTEGER")
                    cursor.execute("UPDATE contador_sku SET store_id = 1 WHERE store_id IS NULL")
                    self.commit()
                    logger.info("Columna 'store_id' añadida a contador_sku.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clientes'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(clientes)")
                columns = [col[1] for col in cursor.fetchall()]
                if "store_id" not in columns:
                    logger.warning("Añadiendo columna 'store_id' a la tabla 'clientes'...")
                    cursor.execute("ALTER TABLE clientes ADD COLUMN store_id INTEGER")
                    cursor.execute("UPDATE clientes SET store_id = 1 WHERE store_id IS NULL")
                    self.commit()
                    logger.info("Columna 'store_id' añadida a clientes.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ventas'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(ventas)")
                columns = [col[1] for col in cursor.fetchall()]
                if "store_id" not in columns:
                    logger.warning("Añadiendo columna 'store_id' a la tabla 'ventas'...")
                    cursor.execute("ALTER TABLE ventas ADD COLUMN store_id INTEGER")
                    cursor.execute("UPDATE ventas SET store_id = 1 WHERE store_id IS NULL")
                    self.commit()
                    logger.info("Columna 'store_id' añadida a ventas.")

                if "id_cliente" not in columns:
                    logger.warning("Añadiendo columna 'id_cliente' a la tabla 'ventas'...")
                    cursor.execute("ALTER TABLE ventas ADD COLUMN id_cliente INTEGER")
                    self.commit()
                    logger.info("Columna 'id_cliente' añadida a ventas.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='venta_items'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(venta_items)")
                columns = [col[1] for col in cursor.fetchall()]
                if "store_id" not in columns:
                    logger.warning("Añadiendo columna 'store_id' a la tabla 'venta_items'...")
                    cursor.execute("ALTER TABLE venta_items ADD COLUMN store_id INTEGER")
                    cursor.execute("UPDATE venta_items SET store_id = 1 WHERE store_id IS NULL")
                    self.commit()
                    logger.info("Columna 'store_id' añadida a venta_items.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='apartados'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(apartados)")
                columns = [col[1] for col in cursor.fetchall()]
                if "store_id" not in columns:
                    logger.warning("Añadiendo columna 'store_id' a la tabla 'apartados'...")
                    cursor.execute("ALTER TABLE apartados ADD COLUMN store_id INTEGER")
                    cursor.execute("UPDATE apartados SET store_id = 1 WHERE store_id IS NULL")
                    self.commit()
                    logger.info("Columna 'store_id' añadida a apartados.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='anticipos'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(anticipos)")
                columns = [col[1] for col in cursor.fetchall()]
                if "store_id" not in columns:
                    logger.warning("Añadiendo columna 'store_id' a la tabla 'anticipos'...")
                    cursor.execute("ALTER TABLE anticipos ADD COLUMN store_id INTEGER")
                    cursor.execute("UPDATE anticipos SET store_id = 1 WHERE store_id IS NULL")
                    self.commit()
                    logger.info("Columna 'store_id' añadida a anticipos.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reembolsos'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(reembolsos)")
                columns = [col[1] for col in cursor.fetchall()]
                if "store_id" not in columns:
                    logger.warning("Añadiendo columna 'store_id' a la tabla 'reembolsos'...")
                    cursor.execute("ALTER TABLE reembolsos ADD COLUMN store_id INTEGER")
                    cursor.execute("UPDATE reembolsos SET store_id = 1 WHERE store_id IS NULL")
                    self.commit()
                    logger.info("Columna 'store_id' añadida a reembolsos.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kits'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE kits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    precio REAL NOT NULL,
                    store_id INTEGER,
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                self.commit()
                logger.info("Tabla 'kits' creada con store_id.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kit_components'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE kit_components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kit_id INTEGER NOT NULL,
                    tipo_prenda TEXT NOT NULL,
                    tipo_pieza TEXT NOT NULL,
                    cantidad INTEGER NOT NULL,
                    sku_start TEXT,
                    sku_end TEXT,
                    store_id INTEGER,
                    FOREIGN KEY (kit_id) REFERENCES kits(id),
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                self.commit()
                logger.info("Tabla 'kit_components' creada con store_id.")
            else:
                # Migrar kit_components para añadir sku_start y sku_end si no existen
                cursor.execute("PRAGMA table_info(kit_components)")
                columns = [col[1] for col in cursor.fetchall()]
                if "sku_start" not in columns:
                    cursor.execute("ALTER TABLE kit_components ADD COLUMN sku_start TEXT")
                    logger.info("Columna 'sku_start' añadida a kit_components.")
                if "sku_end" not in columns:
                    cursor.execute("ALTER TABLE kit_components ADD COLUMN sku_end TEXT")
                    logger.info("Columna 'sku_end' añadida a kit_components.")
                self.commit()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stores'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE stores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    ubicacion TEXT
                )''')
                cursor.execute("INSERT INTO stores (id, nombre, ubicacion) VALUES (1, 'Tienda Principal', 'San Felipe')")
                self.commit()
                logger.info("Tabla 'stores' creada con tienda por defecto.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='escuelas'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE escuelas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL UNIQUE,
                    store_id INTEGER,
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                self.commit()
                logger.info("Tabla 'escuelas' creada con store_id.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='productos'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE productos (
                    sku TEXT PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    nivel_educativo TEXT,
                    escuela_id INTEGER,
                    color TEXT,
                    tipo_prenda TEXT,
                    tipo_pieza TEXT,
                    genero TEXT,
                    atributo TEXT,
                    ubicacion TEXT,
                    escudo TEXT,
                    marca TEXT,
                    talla TEXT,
                    qr_path TEXT,
                    inventario INTEGER DEFAULT 0,
                    ventas INTEGER DEFAULT 0,
                    precio REAL DEFAULT 0,
                    image_path TEXT,
                    store_id INTEGER,
                    FOREIGN KEY (store_id) REFERENCES stores(id),
                    FOREIGN KEY (escuela_id) REFERENCES escuelas(id)
                )''')
                self.commit()
                logger.info("Tabla 'productos' creada con store_id y escuela_id.")
            else:
                cursor.execute("PRAGMA table_info(productos)")
                columns = [col[1] for col in cursor.fetchall()]
                expected_columns = [
                    "sku", "nombre", "nivel_educativo", "escuela_id", "color", "tipo_prenda", "tipo_pieza",
                    "genero", "atributo", "ubicacion", "escudo", "marca", "talla", "qr_path", "inventario",
                    "ventas", "precio", "image_path", "store_id"
                ]
                for col in expected_columns:
                    if col not in columns and col != "store_id" and col != "escuela_id":
                        logger.error(f"La tabla 'productos' no tiene la columna esperada: {col}")
                        raise sqlite3.Error(f"Esquema incorrecto en la tabla 'productos': falta la columna {col}")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contador_sku'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE contador_sku (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ultimo_sku TEXT NOT NULL,
                    store_id INTEGER,
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                cursor.execute("INSERT INTO contador_sku (ultimo_sku, store_id) VALUES ('000000', 1)")
                self.commit()
                logger.info("Tabla 'contador_sku' creada con store_id.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    store_id INTEGER,
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                self.commit()
                logger.info("Tabla 'users' creada con store_id.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clientes'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_completo TEXT NOT NULL,
                    numero TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    store_id INTEGER,
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                self.commit()
                logger.info("Tabla 'clientes' creada con store_id.")
            else:
                expected_columns = ["id", "nombre_completo", "numero", "created_at", "store_id"]
                cursor.execute("PRAGMA table_info(clientes)")
                actual_columns = [col[1] for col in cursor.fetchall()]
                for col in expected_columns:
                    if col not in actual_columns and col != "store_id":
                        logger.error(f"La tabla 'clientes' no tiene la columna esperada: {col}")
                        raise sqlite3.Error(f"Esquema incorrecto en la tabla 'clientes': falta la columna {col}")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ventas'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE ventas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    id_cliente INTEGER,
                    metodo_pago TEXT,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total REAL,
                    store_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (id_cliente) REFERENCES clientes(id),
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                self.commit()
                logger.info("Tabla 'ventas' creada con store_id.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='venta_items'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE venta_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venta_id INTEGER,
                    sku TEXT,
                    cantidad INTEGER,
                    precio REAL,
                    descuento REAL,
                    store_id INTEGER,
                    FOREIGN KEY (venta_id) REFERENCES ventas(id),
                    FOREIGN KEY (sku) REFERENCES productos(sku),
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                self.commit()
                logger.info("Tabla 'venta_items' creada con store_id.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='apartados'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE apartados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_cliente INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    productos TEXT NOT NULL,
                    anticipo REAL DEFAULT 0,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_vencimiento TIMESTAMP NOT NULL,
                    estado TEXT DEFAULT 'activo',
                    store_id INTEGER,
                    FOREIGN KEY (id_cliente) REFERENCES clientes(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                self.commit()
                logger.info("Tabla 'apartados' creada con store_id.")
            else:
                cursor.execute("PRAGMA table_info(apartados)")
                columns = [col[1] for col in cursor.fetchall()]
                if "fecha_modificacion" not in columns:
                    logger.warning("Añadiendo columna 'fecha_modificacion' a la tabla 'apartados'...")
                    cursor.execute("ALTER TABLE apartados ADD COLUMN fecha_modificacion TIMESTAMP")
                    cursor.execute("UPDATE apartados SET fecha_modificacion = fecha_creacion WHERE fecha_modificacion IS NULL")
                    self.commit()
                    logger.info("Columna 'fecha_modificacion' añadida.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='anticipos'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE anticipos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    apartado_id INTEGER NOT NULL,
                    monto REAL NOT NULL,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    store_id INTEGER,
                    FOREIGN KEY (apartado_id) REFERENCES apartados(id),
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                self.commit()
                logger.info("Tabla 'anticipos' creada con store_id.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reembolsos'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE reembolsos (
                    id_reembolso INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_apartado INTEGER NOT NULL,
                    monto REAL NOT NULL,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id TEXT NOT NULL,
                    store_id INTEGER,
                    FOREIGN KEY (id_apartado) REFERENCES apartados(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (store_id) REFERENCES stores(id)
                )''')
                self.commit()
                logger.info("Tabla 'reembolsos' creada con store_id.")

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modificaciones_apartados'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE modificaciones_apartados (
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
                )''')
                self.commit()
                logger.info("Tabla 'modificaciones_apartados' creada con store_id.")

            self.initialize_default_user()
            self.migrate_dates()

        except sqlite3.Error as e:
            logger.error(f"Error al verificar tablas: {str(e)}")
            raise

    def validate_user(self, username, password, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT password, role FROM users WHERE username = ? AND store_id = ?", (username, store_id))
            result = cursor.fetchone()
            if result:
                if isinstance(password, bytes):
                    password = password.decode('utf-8')
                if bcrypt.checkpw(password.encode('utf-8'), result['password']):
                    logger.info(f"Usuario {username} validado exitosamente para tienda {store_id}")
                    return result['role']
            logger.warning(f"Validación fallida para usuario {username} en tienda {store_id}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Error al validar usuario {username} en tienda {store_id}: {str(e)}")
            return None

    def buscar_productos(self, query, store_id=1, limit=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("""
                SELECT p.sku, p.nombre, p.precio, p.inventario, e.nombre AS escuela
                FROM productos p
                LEFT JOIN escuelas e ON p.escuela_id = e.id
                WHERE (p.sku LIKE ? OR p.nombre LIKE ?) AND p.store_id = ?
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", store_id, limit))
            result = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"Productos encontrados para query '{query}' en tienda {store_id}: {len(result)} registros")
            return result
        except sqlite3.Error as e:
            logger.error(f"Error al buscar productos en tienda {store_id}: {str(e)}")
            return []

    def validar_stock(self, sku, cantidad, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT inventario FROM productos WHERE sku = ? AND store_id = ?", (sku, store_id))
            result = cursor.fetchone()
            is_valid = result and result['inventario'] >= cantidad
            logger.debug(f"Validación de stock para SKU {sku} en tienda {store_id}: {is_valid}")
            return is_valid
        except sqlite3.Error as e:
            logger.error(f"Error al validar stock para SKU {sku} en tiendafrak {store_id}: {str(e)}")
            return False

    def buscar_clientes(self, query, store_id=1, limit=1, offset=0):
        logging.debug(f"Buscando clientes con query: '{query}', tienda: {store_id}, limit: {limit}, offset: {offset}")
        try:
            cursor = self.get_cursor()
            query = f"%{query}%"
            if limit is None:
                cursor.execute("""
                    SELECT id, nombre_completo, numero, created_at
                    FROM clientes
                    WHERE (nombre_completo LIKE ? OR numero LIKE ?) AND store_id = ?
                """, (query, query, store_id))
            else:
                cursor.execute("""
                    SELECT id, nombre_completo, numero, created_at
                    FROM clientes
                    WHERE (nombre_completo LIKE ? OR numero LIKE ?) AND store_id = ?
                    LIMIT ? OFFSET ?
                """, (query, query, store_id, limit, offset))
            clientes = [dict(row) for row in cursor.fetchall()]
            logging.debug(f"Clientes encontrados en tienda {store_id}: {len(clientes)} registros")
            return clientes
        except sqlite3.Error as e:
            logger.error(f"Error al buscar clientes en tienda {store_id}: {str(e)}")
            return []

    def registrar_cliente(self, nombre_completo, numero, store_id=1):
        logging.debug(f"Registrando cliente: {nombre_completo}, {numero}, tienda: {store_id}")
        try:
            cursor = self.get_cursor()
            cursor.execute("""
                INSERT INTO clientes (nombre_completo, numero, store_id)
                VALUES (?, ?, ?)
            """, (nombre_completo, numero, store_id))
            self.commit()
            cursor.execute("SELECT last_insert_rowid()")
            cliente_id = cursor.fetchone()[0]
            logging.debug(f"Cliente registrado con ID: {cliente_id} en tienda {store_id}")
            return cliente_id
        except sqlite3.Error as e:
            logger.error(f"Error al registrar cliente en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def actualizar_cliente(self, cliente_id, nombre_completo, numero, store_id=1):
        logging.debug(f"Actualizando cliente: ID {cliente_id}, Nombre: {nombre_completo}, Número: {numero}, tienda: {store_id}")
        try:
            cursor = self.get_cursor()
            cursor.execute(
                "UPDATE clientes SET nombre_completo = ?, numero = ? WHERE id = ? AND store_id = ?",
                (nombre_completo, numero, cliente_id, store_id)
            )
            if cursor.rowcount == 0:
                logger.warning(f"No se encontró el cliente con ID {cliente_id} en tienda {store_id} para actualizar.")
                return False
            self.commit()
            logging.debug(f"Cliente actualizado con éxito: ID {cliente_id} en tienda {store_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error al actualizar cliente en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def eliminar_cliente(self, cliente_id, store_id=1):
        logging.debug(f"Eliminando cliente: ID {cliente_id}, tienda: {store_id}")
        try:
            cursor = self.get_cursor()
            cursor.execute("DELETE FROM clientes WHERE id = ? AND store_id = ?", (cliente_id, store_id))
            if cursor.rowcount == 0:
                logger.warning(f"No se encontró el cliente con ID {cliente_id} en tienda {store_id} para eliminar.")
                return False
            self.commit()
            logging.debug(f"Cliente eliminado con éxito: ID {cliente_id} en tienda {store_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error al eliminar cliente en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def registrar_venta(self, user_id, items, metodo_pago, id_cliente, tasa_iva, store_id=1, reducir_inventario=True):
        try:
            cursor = self.get_cursor()
            subtotal = sum(item['cantidad'] * item['precio'] for item in items)
            total_descuento = sum(item['descuento'] for item in items)
            iva = (subtotal - total_descuento) * tasa_iva
            total = subtotal - total_descuento + iva
            fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                INSERT INTO ventas (user_id, id_cliente, metodo_pago, fecha, total, store_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, id_cliente, metodo_pago, fecha, total, store_id))
            venta_id = cursor.lastrowid

            # Insertar ítems en la tabla venta_items
            for item in items:
                cursor.execute("""
                    INSERT INTO venta_items (venta_id, sku, cantidad, precio, descuento, store_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (venta_id, item['sku'], item['cantidad'], item['precio'], item['descuento'], store_id))

            if reducir_inventario:
                for item in items:
                    cursor.execute("""
                        UPDATE productos SET inventario = inventario - ?, ventas = ventas + ?
                        WHERE sku = ? AND store_id = ?
                    """, (item['cantidad'], item['cantidad'], item['sku'], store_id))

            self.commit()
            logger.info(f"Venta registrada con ID: {venta_id} en tienda {store_id}")
            return venta_id
        except sqlite3.Error as e:
            logger.error(f"Error al registrar venta en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def get_last_sale_id(self, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT MAX(id) FROM ventas WHERE store_id = ?", (store_id,))
            result = cursor.fetchone()
            last_id = result[0] or 0
            logger.debug(f"Último ID de venta obtenido para tienda {store_id}: {last_id}")
            return last_id
        except sqlite3.Error as e:
            logger.error(f"Error al obtener último ID de venta en tienda {store_id}: {str(e)}")
            return 0

    def get_cliente(self, id_cliente, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT id, nombre_completo, numero, created_at FROM clientes WHERE id = ? AND store_id = ?", (id_cliente, store_id))
            row = cursor.fetchone()
            cliente = dict(row) if row else None
            if cliente:
                logger.debug(f"Cliente con ID {id_cliente} obtenido para tienda {store_id}")
            else:
                logger.warning(f"No se encontró cliente con ID {id_cliente} en tienda {store_id}")
            return cliente
        except sqlite3.Error as e:
            logger.error(f"Error al obtener cliente con ID {id_cliente} en tienda {store_id}: {str(e)}")
            return None

    def actualizar_inventario(self, sku, cantidad, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("UPDATE productos SET inventario = inventario + ? WHERE sku = ? AND store_id = ?", (cantidad, sku, store_id))
            if cursor.rowcount > 0:
                self.commit()
                logger.info(f"Inventario actualizado para SKU {sku} en tienda {store_id}: {cantidad}")
                return True
            logger.warning(f"No se encontró el producto con SKU {sku} en tienda {store_id} para actualizar inventario")
            return False
        except sqlite3.Error as e:
            logger.error(f"Error al actualizar inventario para SKU {sku} en tienda {store_id}: {str(e)}")
            self.rollback()
            return False

    def registrar_apartado(self, id_cliente, user_id, productos, anticipo=0, store_id=1):
        logging.debug(f"Registrando apartado para cliente {id_cliente}, usuario {user_id}, tienda {store_id}")
        try:
            cursor = self.get_cursor()
            for item in productos:
                if not self.validar_stock(item['sku'], item['cantidad'], store_id):
                    raise ValueError(f"No hay suficiente stock para el producto {item['sku']} en tienda {store_id}")
            
            fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            
            for item in productos:
                cursor.execute("""
                    UPDATE productos SET inventario = inventario - ?
                    WHERE sku = ? AND store_id = ?
                """, (item['cantidad'], item['sku'], store_id))
            
            cursor.execute("""
                INSERT INTO apartados (id_cliente, user_id, productos, anticipo, fecha_vencimiento, estado, store_id)
                VALUES (?, ?, ?, ?, ?, 'activo', ?)
            """, (id_cliente, user_id, json.dumps(productos), anticipo, fecha_vencimiento, store_id))
            
            apartado_id = cursor.lastrowid
            
            if anticipo > 0:
                cursor.execute("""
                    INSERT INTO anticipos (apartado_id, monto, store_id)
                    VALUES (?, ?, ?)
                """, (apartado_id, anticipo, store_id))
            
            self.commit()
            logger.info(f"Apartado registrado con ID: {apartado_id} en tienda {store_id}")
            return apartado_id
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"Error al registrar apartado en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def buscar_apartados(self, query="", estado="activo", store_id=1, limit=None, offset=0):
        logging.debug(f"Buscando apartados con query: '{query}', estado: {estado}, tienda: {store_id}, limit: {limit}, offset: {offset}")
        try:
            cursor = self.get_cursor()
            query = f"%{query}%"
            if limit is None:
                cursor.execute("""
                    SELECT a.*, c.nombre_completo
                    FROM apartados a
                    JOIN clientes c ON a.id_cliente = c.id
                    WHERE (c.nombre_completo LIKE ? OR c.numero LIKE ?)
                    AND a.estado = ? AND a.store_id = ?
                """, (query, query, estado, store_id))
            else:
                cursor.execute("""
                    SELECT a.*, c.nombre_completo
                    FROM apartados a
                    JOIN clientes c ON a.id_cliente = c.id
                    WHERE (c.nombre_completo LIKE ? OR c.numero LIKE ?)
                    AND a.estado = ? AND a.store_id = ?
                    LIMIT ? OFFSET ?
                """, (query, query, estado, store_id, limit, offset))
            apartados = [dict(row) for row in cursor.fetchall()]
            logging.debug(f"Apartados encontrados en tienda {store_id}: {len(apartados)} registros")
            return apartados
        except sqlite3.Error as e:
            logger.error(f"Error al buscar apartados en tienda {store_id}: {str(e)}")
            return []

    def apartados_por_vencer(self, dias=2, store_id=1):
        try:
            cursor = self.get_cursor()
            fecha_limite = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                SELECT a.*, c.nombre_completo, c.numero
                FROM apartados a
                JOIN clientes c ON a.id_cliente = c.id
                WHERE a.estado = 'activo'
                AND a.fecha_vencimiento <= ?
                AND a.fecha_vencimiento >= ?
                AND a.store_id = ?
            """, (fecha_limite, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), store_id))
            apartados = [dict(row) for row in cursor.fetchall()]
            logging.debug(f"Apartados por vencer en tienda {store_id}: {len(apartados)} registros")
            return apartados
        except sqlite3.Error as e:
            logger.error(f"Error al buscar apartados por vencer en tienda {store_id}: {str(e)}")
            return []

    def verificar_apartados_vencidos(self, store_id=1):
        try:
            cursor = self.get_cursor()
            fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                SELECT * FROM apartados
                WHERE estado = 'activo'
                AND fecha_vencimiento < ?
                AND store_id = ?
            """, (fecha_actual, store_id))
            apartados_vencidos = [dict(row) for row in cursor.fetchall()]
            
            for apartado in apartados_vencidos:
                productos = json.loads(apartado['productos'])
                for item in productos:
                    cursor.execute("""
                        UPDATE productos SET inventario = inventario + ?
                        WHERE sku = ? AND store_id = ?
                    """, (item['cantidad'], item['sku'], store_id))
                cursor.execute("UPDATE apartados SET estado = 'vencido' WHERE id = ? AND store_id = ?", (apartado['id'], store_id))
            
            self.commit()
            logger.info(f"Se marcaron {len(apartados_vencidos)} apartados como vencidos en tienda {store_id}")
            return len(apartados_vencidos)
        except sqlite3.Error as e:
            logger.error(f"Error al verificar apartados vencidos en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def extender_apartado(self, apartado_id, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM apartados WHERE id = ? AND store_id = ?", (apartado_id, store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError(f"No se encontró el apartado con ID {apartado_id} en tienda {store_id}")
            
            if apartado['estado'] != 'activo':
                raise ValueError(f"El apartado con ID {apartado_id} no está activo")
            
            nueva_fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE apartados SET fecha_vencimiento = ? WHERE id = ? AND store_id = ?", (nueva_fecha_vencimiento, apartado_id, store_id))
            self.commit()
            logger.info(f"Apartado {apartado_id} extendido hasta {nueva_fecha_vencimiento} en tienda {store_id}")
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"Error al extender apartado en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def registrar_anticipo(self, apartado_id, monto, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM apartados WHERE id = ? AND store_id = ?", (apartado_id, store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError(f"No se encontró el apartado con ID {apartado_id} en tienda {store_id}")
            
            if apartado['estado'] != 'activo':
                raise ValueError(f"El apartado con ID {apartado_id} no está activo")
            
            cursor.execute("""
                INSERT INTO anticipos (apartado_id, monto, store_id)
                VALUES (?, ?, ?)
            """, (apartado_id, monto, store_id))
            
            nuevo_anticipo = apartado['anticipo'] + monto
            nueva_fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                UPDATE apartados SET anticipo = ?, fecha_vencimiento = ?
                WHERE id = ? AND store_id = ?
            """, (nuevo_anticipo, nueva_fecha_vencimiento, apartado_id, store_id))
            
            self.commit()
            logger.info(f"Anticipo de {monto} registrado para apartado {apartado_id} en tienda {store_id}")
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"Error al registrar anticipo en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def obtener_anticipos(self, apartado_id, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM anticipos WHERE apartado_id = ? AND store_id = ? ORDER BY fecha", (apartado_id, store_id))
            anticipos = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"Anticipos obtenidos para apartado {apartado_id} en tienda {store_id}: {len(anticipos)} registros")
            return anticipos
        except sqlite3.Error as e:
            logger.error(f"Error al obtener anticipos en tienda {store_id}: {str(e)}")
            return []

    def modificar_productos_apartado(self, apartado_id, nuevos_productos, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM apartados WHERE id = ? AND store_id = ?", (apartado_id, store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError(f"No se encontró el apartado con ID {apartado_id} en tienda {store_id}")
            
            if apartado['estado'] != 'activo':
                raise ValueError(f"El apartado con ID {apartado_id} no está activo")
            
            productos_viejos = json.loads(apartado['productos'])
            
            for item in productos_viejos:
                cursor.execute("""
                    UPDATE productos SET inventario = inventario + ?
                    WHERE sku = ? AND store_id = ?
                """, (item['cantidad'], item['sku'], store_id))
            
            for item in nuevos_productos:
                if not self.validar_stock(item['sku'], item['cantidad'], store_id):
                    raise ValueError(f"No hay suficiente stock para el producto {item['sku']} en tienda {store_id}")
                cursor.execute("""
                    UPDATE productos SET inventario = inventario - ?
                    WHERE sku = ? AND store_id = ?
                """, (item['cantidad'], item['sku'], store_id))
            
            cursor.execute("UPDATE apartados SET productos = ? WHERE id = ? AND store_id = ?", (json.dumps(nuevos_productos), apartado_id, store_id))
            self.commit()
            logger.info(f"Productos del apartado {apartado_id} actualizados en tienda {store_id}")
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"Error al modificar productos del apartado en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def completar_apartado(self, apartado_id, metodo_pago, tasa_iva, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM apartados WHERE id = ? AND store_id = ?", (apartado_id, store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError(f"No se encontró el apartado con ID {apartado_id} en tienda {store_id}")
            
            if apartado['estado'] != 'activo':
                raise ValueError(f"El apartado con ID {apartado_id} no está activo")
            
            productos = json.loads(apartado['productos'])
            venta_id = self.registrar_venta(
                user_id=apartado['user_id'],
                items=productos,
                metodo_pago=metodo_pago,
                id_cliente=apartado['id_cliente'],
                tasa_iva=tasa_iva,
                store_id=store_id,
                reducir_inventario=False
            )
            
            cursor.execute("UPDATE apartados SET estado = 'completado' WHERE id = ? AND store_id = ?", (apartado_id, store_id))
            self.commit()
            logger.info(f"Apartado {apartado_id} completado y convertido en venta {venta_id} en tienda {store_id}")
            return venta_id
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"Error al completar apartado en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def cancelar_apartado(self, apartado_id, store_id=1):
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM apartados WHERE id = ? AND store_id = ?", (apartado_id, store_id))
            apartado = cursor.fetchone()
            if not apartado:
                raise ValueError(f"No se encontró el apartado con ID {apartado_id} en tienda {store_id}")
            
            if apartado['estado'] != 'activo':
                raise ValueError(f"El apartado con ID {apartado_id} no está activo")
            
            productos = json.loads(apartado['productos'])
            for item in productos:
                cursor.execute("""
                    UPDATE productos SET inventario = inventario + ?
                    WHERE sku = ? AND store_id = ?
                """, (item['cantidad'], item['sku'], store_id))
            
            cursor.execute("UPDATE apartados SET estado = 'cancelado' WHERE id = ? AND store_id = ?", (apartado_id, store_id))
            self.commit()
            logger.info(f"Apartado {apartado_id} cancelado y productos devueltos al inventario en tienda {store_id}")
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"Error al cancelar apartado en tienda {store_id}: {str(e)}")
            self.rollback()
            raise

    def buscar_apartados_por_cliente(self, id_cliente, estado="activo", store_id=1, limit=None, offset=0):
        """Busca apartados por ID de cliente."""
        try:
            cursor = self.get_cursor()
            sql = """
                SELECT a.*, c.nombre_completo
                FROM apartados a
                JOIN clientes c ON a.id_cliente = c.id
                WHERE a.id_cliente = ? AND a.estado = ? AND a.store_id = ?
            """
            params = [id_cliente, estado, store_id]
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            cursor.execute(sql, params)
            apartados = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"Apartados encontrados para cliente {id_cliente} en tienda {store_id}: {len(apartados)} registros")
            return apartados
        except sqlite3.Error as e:
            logger.error(f"Error al buscar apartados por cliente {id_cliente} en tienda {store_id}: {str(e)}")
            return []

    def obtener_modificaciones(self, apartado_id, store_id=1):
        """Obtiene el historial de modificaciones de un apartado."""
        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT * FROM modificaciones_apartados WHERE apartado_id = ? AND store_id = ? ORDER BY fecha DESC", (apartado_id, store_id))
            modificaciones = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"Modificaciones obtenidas para apartado {apartado_id} en tienda {store_id}: {len(modificaciones)} registros")
            return modificaciones
        except sqlite3.Error as e:
            logger.error(f"Error al obtener modificaciones para apartado {apartado_id} en tienda {store_id}: {str(e)}")
            return []

    def get_cursor(self):
        self.ensure_connection()
        if self.conn is None:
            raise sqlite3.Error("No se pudo establecer la conexión a la base de datos.")
        try:
            return self.conn.cursor()
        except sqlite3.Error as e:
            logger.error(f"Error al obtener cursor: {str(e)}")
            raise

    def commit(self):
        if self.conn is None:
            logger.error("No hay conexión activa para realizar commit.")
            raise sqlite3.Error("No hay conexión activa.")
        try:
            self.conn.commit()
            logger.debug("Commit realizado con éxito.")
        except sqlite3.Error as e:
            logger.error(f"Error al hacer commit: {str(e)}")
            raise

    def rollback(self):
        if self.conn is None:
            logger.error("No hay conexión activa para realizar rollback.")
            raise sqlite3.Error("No hay conexión activa.")
        try:
            self.conn.rollback()
            logger.debug("Rollback realizado con éxito.")
        except sqlite3.Error as e:
            logger.error(f"Error al hacer rollback: {str(e)}")
            raise

    def close(self):
        if self.conn:
            try:
                self.conn.commit()
                self.conn.close()
                logger.info(f"Conexión a {self.db_path} cerrada.")
            except sqlite3.Error as e:
                logger.error(f"Error al cerrar la conexión: {str(e)}")
            finally:
                self.conn = None

    def __enter__(self):
        self.ensure_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
            logger.error(f"Excepción en contexto 'with': {exc_type}, {exc_val}")
        else:
            self.commit()

    def __del__(self):
        self.close()