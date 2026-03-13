import sqlite3
import logging
from src.core.config.db_manager import DatabaseManager
from src.core.utils.talla_utils import sort_tallas

logger = logging.getLogger(__name__)

class ProductRepository:
    """
    Clase que maneja las operaciones de bajo nivel con la base de datos para productos.
    """
    def __init__(self, store_id):
        """
        Inicializa el repositorio de productos.

        Args:
            store_id (int): ID de la tienda.
        """
        self.store_id = store_id
        self.db_manager = DatabaseManager()
        logger.debug(f"ProductRepository inicializado para tienda {self.store_id}")

    def find_products(self, page, page_size, filters, sort_column, sort_direction):
        """
        Consulta productos con paginación, filtros y ordenamiento.

        Args:
            page (int): Número de página actual.
            page_size (int): Tamaño de la página.
            filters (dict): Filtros para aplicar a la consulta.
            sort_column (str): Columna por la cual ordenar.
            sort_direction (str): Dirección del ordenamiento ("asc" o "desc").

        Returns:
            list: Lista de productos que coinciden con los filtros.
        """
        try:
            conditions, params = self._build_query_conditions(filters)
            params.insert(0, self.store_id)  # Agregar store_id al inicio

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"""
                SELECT productos.sku, productos.nombre, productos.nivel_educativo, escuelas.nombre AS escuela, 
                       productos.color, productos.tipo_prenda, productos.tipo_pieza, productos.genero, 
                       productos.atributo, productos.ubicacion, productos.escudo, productos.marca, 
                       productos.talla, productos.inventario, productos.ventas, productos.precio
                FROM productos 
                LEFT JOIN escuelas ON productos.escuela_id = escuelas.id 
                {where_clause}
                ORDER BY productos."{sort_column or 'sku'}" {sort_direction.upper()}
                LIMIT ? OFFSET ?
            """
            params.extend([page_size, page * page_size])

            with self.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute(query, params)
                products = cursor.fetchall()
                logger.debug("Cargados %d productos desde la base de datos", len(products))
                return products
        except sqlite3.Error as e:
            logger.error("Error en la base de datos al cargar productos: %s", str(e))
            raise ValueError(f"No se pudieron cargar los productos: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al cargar productos: %s", str(e))
            raise

    def count_products(self, filters):
        """
        Cuenta el número total de productos que coinciden con los filtros.

        Args:
            filters (dict): Filtros para aplicar a la consulta.

        Returns:
            int: Número total de productos.
        """
        try:
            conditions, params = self._build_query_conditions(filters)
            params.insert(0, self.store_id)  # Agregar store_id al inicio

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"""
                SELECT COUNT(*) 
                FROM productos 
                LEFT JOIN escuelas ON productos.escuela_id = escuelas.id 
                {where_clause}
            """

            with self.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute(query, params)
                total = cursor.fetchone()[0] or 0
                logger.debug("Total productos contados: %d", total)
                return total
        except sqlite3.Error as e:
            logger.error("Error en la base de datos al contar productos: %s", str(e))
            raise ValueError(f"No se pudieron contar los productos: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al contar productos: %s", str(e))
            raise

    def _build_query_conditions(self, filters):
        """
        Construye las condiciones y parámetros para las consultas SQL.

        Args:
            filters (dict): Filtros para aplicar.

        Returns:
            tuple: (lista de condiciones, lista de parámetros).
        """
        conditions = ["productos.store_id = ?"]
        params = []

        if filters.get("exact_sku"):
            conditions.append("UPPER(productos.sku) = ?")
            params.append(filters["exact_sku"].upper())
        else:
            if filters.get("search"):
                conditions.append("(UPPER(productos.sku) LIKE ? OR UPPER(productos.nombre) LIKE ?)")
                params.extend([f"%{filters['search']}%", f"%{filters['search']}%"])
            for key in ["escuela", "nivel_educativo", "color", "tipo_prenda", "tipo_pieza", "genero", "atributo", "marca", "talla"]:
                values = filters.get(key, [])
                if values:
                    placeholders = ",".join(["?"] * len(values))
                    if key == "escuela":
                        conditions.append(f"escuelas.nombre IN ({placeholders})")
                        params.extend(values)
                    elif key == "talla":
                        logger.debug(f"Filtro de tallas aplicado: {values}")
                        logger.debug(f"Parámetros de tallas para SQL: {[value.upper() for value in values]}")
                        conditions.append(f"UPPER(productos.talla) IN ({placeholders})")
                        params.extend(value.upper() for value in values)
                    else:
                        conditions.append(f"productos.\"{key}\" IN ({placeholders})")
                        params.extend(values)

        logger.debug(f"Condiciones SQL generadas: {conditions}")
        logger.debug(f"Parámetros SQL generados: {params}")
        return conditions, params

    def get_unique_values(self, column):
        """
        Obtiene valores únicos para una columna dada.

        Args:
            column (str): Columna de la cual obtener valores únicos.

        Returns:
            list: Lista de valores únicos ordenados.
        """
        try:
            with self.db_manager as db:
                cursor = db.get_cursor()
                if column == "escuela":
                    query = "SELECT nombre FROM escuelas WHERE store_id = ? AND nombre IS NOT NULL AND TRIM(nombre) != ''"
                    cursor.execute(query, (self.store_id,))
                else:
                    query = f"""
                        SELECT DISTINCT "{column}"
                        FROM productos
                        WHERE "{column}" IS NOT NULL
                        AND TRIM("{column}") != ''
                        AND LENGTH(TRIM("{column}")) > 0
                        AND store_id = ?
                    """
                    cursor.execute(query, (self.store_id,))
                values = [row[0] for row in cursor.fetchall()]
                logger.debug(f"Valores crudos obtenidos para {column}: {values}")
                values = [str(v).strip() for v in values if v and str(v).strip()]
                logger.debug(f"Valores después de filtrado (eliminando nulos/vacíos): {values}")

                if column == "talla":
                    values = sort_tallas(values)
                    logger.debug(f"Tallas ordenadas para {column}: {values}")
                elif column in ["inventario", "ventas", "precio"]:
                    values.sort(key=lambda x: float(x) if x.replace(".", "").isdigit() else float('inf'))
                else:
                    values.sort()

                logger.debug(f"Valores únicos procesados para {column}: {len(values)} valores: {values}")
                return values
        except sqlite3.Error as e:
            logger.error("Error en la base de datos al obtener valores únicos para %s: %s", column, str(e))
            raise ValueError(f"No se pudieron obtener valores únicos: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al obtener valores únicos para %s: %s", column, str(e))
            raise

    def get_product(self, sku):
        """
        Obtiene los datos completos de un producto por SKU.

        Args:
            sku (str): SKU del producto.

        Returns:
            dict: Diccionario con los datos del producto, o None si no se encuentra.
        """
        try:
            if not sku or not isinstance(sku, str):
                logger.error("SKU inválido: %s", sku)
                return None

            query = """
                SELECT productos.sku, productos.nombre, productos.nivel_educativo, escuelas.nombre AS escuela, 
                       productos.color, productos.tipo_prenda, productos.tipo_pieza, productos.genero, 
                       productos.marca, productos.talla, productos.atributo, productos.ubicacion, 
                       productos.escudo, productos.qr_path, productos.inventario, productos.ventas, 
                       productos.precio, productos.image_path, productos.escuela_id
                FROM productos 
                LEFT JOIN escuelas ON productos.escuela_id = escuelas.id 
                WHERE productos.sku = ? AND productos.store_id = ?
            """
            with self.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute(query, (sku, self.store_id))
                product = cursor.fetchone()
                if product:
                    result = {
                        "sku": product[0], "nombre": product[1], "nivel_educativo": product[2], "escuela": product[3],
                        "color": product[4], "tipo_prenda": product[5], "tipo_pieza": product[6], "genero": product[7],
                        "marca": product[8], "talla": product[9], "atributo": product[10], "ubicacion": product[11],
                        "escudo": product[12], "qr_path": product[13], "inventario": product[14], "ventas": product[15],
                        "precio": product[16], "image_path": product[17], "escuela_id": product[18]
                    }
                    logger.debug("Producto recuperado con SKU %s", sku)
                    return result
                logger.debug("No se encontró producto con SKU %s", sku)
                return None
        except sqlite3.Error as e:
            logger.error("Error en la base de datos al obtener producto %s: %s", sku, str(e))
            raise ValueError(f"No se pudo obtener el producto: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al obtener producto %s: %s", sku, str(e))
            raise

    def generate_new_sku(self):
        """
        Genera un nuevo SKU incrementando el contador.

        Returns:
            str: Nuevo SKU generado.

        Raises:
            ValueError: Si no se puede generar el SKU.
        """
        try:
            with self.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute("SELECT ultimo_sku FROM contador_sku WHERE store_id = ?", (self.store_id,))
                result = cursor.fetchone()
                if not result:
                    logger.error("No se encontró el contador de SKU para tienda %d", self.store_id)
                    raise ValueError("No se encontró el contador de SKU")
                ultimo_sku = int(result[0])
                new_sku = f"{ultimo_sku + 1:06d}"
                cursor.execute("UPDATE contador_sku SET ultimo_sku = ? WHERE store_id = ?", (new_sku, self.store_id))
                self.db_manager.commit()
                logger.debug(f"Nuevo SKU generado: {new_sku}")
                return new_sku
        except sqlite3.Error as e:
            logger.error("Error en la base de datos al generar nuevo SKU: %s", str(e))
            raise ValueError(f"No se pudo generar el SKU: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al generar nuevo SKU: %s", str(e))
            raise