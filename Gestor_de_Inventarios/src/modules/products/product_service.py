import sqlite3
import os
import shutil
import logging
from src.modules.products.product_repository import ProductRepository
from src.core.config.config import CONFIG

logger = logging.getLogger(__name__)

class ProductService:
    """
    Clase que proporciona servicios de alto nivel para la gestión de productos.
    Interactúa con el repositorio de productos y el sistema de archivos.
    """
    def __init__(self, store_id, root_folder):
        """
        Inicializa el servicio de productos.

        Args:
            store_id (int): ID de la tienda.
            root_folder (str): Carpeta raíz para el almacenamiento de archivos.
        """
        self.store_id = store_id
        self.root_folder = root_folder
        self.repository = ProductRepository(store_id)
        logger.debug(f"ProductService inicializado para tienda {self.store_id}")

    def load_products(self, page, page_size, filters, sort_column, sort_direction):
        """
        Carga productos con paginación, filtros y ordenamiento.

        Args:
            page (int): Número de página actual.
            page_size (int): Tamaño de la página.
            filters (dict): Filtros para aplicar a la consulta.
            sort_column (str): Columna por la cual ordenar.
            sort_direction (str): Dirección del ordenamiento ("asc" o "desc").

        Returns:
            tuple: (productos, total_items, total_pages, page)
        """
        try:
            logger.debug(f"Filtros recibidos en load_products: {filters}")
            logger.debug(f"Tallas específicas en filtros: {filters.get('talla', [])}")
            total_items = self.repository.count_products(filters)
            total_pages = max(1, (total_items + page_size - 1) // page_size)
            page = min(max(0, page), total_pages - 1)
            products = self.repository.find_products(page, page_size, filters, sort_column, sort_direction)
            logger.debug("Cargados %d productos, página %d de %d", len(products), page + 1, total_pages)
            return products, total_items, total_pages, page
        except sqlite3.Error as e:
            logger.error("Error en la base de datos al cargar productos: %s", str(e))
            raise ValueError(f"No se pudieron cargar los productos: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al cargar productos: %s", str(e))
            raise

    def get_unique_values(self, column, custom_tallas=None):
        """
        Obtiene valores únicos para una columna, con soporte para tallas personalizadas.

        Args:
            column (str): Columna de la cual obtener valores únicos.
            custom_tallas (list, optional): Lista de tallas personalizadas adicionales.

        Returns:
            list: Lista de valores únicos.
        """
        try:
            values = self.repository.get_unique_values(column)
            logger.debug(f"Valores obtenidos desde repository para {column}: {values}")
            if column == "talla" and custom_tallas:
                values.extend(talla for talla in custom_tallas if talla and talla.strip() and len(talla.strip()) > 0 and talla not in values)
                logger.debug(f"Tallas personalizadas añadidas: {custom_tallas}")
            logger.debug(f"Valores únicos obtenidos para %s: %d valores: {values}", column, len(values))
            return values
        except sqlite3.Error as e:
            logger.error("Error en la base de datos al obtener valores únicos para %s: %s", column, str(e))
            raise ValueError(f"No se pudieron obtener valores únicos: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al obtener valores únicos para %s: %s", column, str(e))
            raise

    def duplicate_product(self, sku):
        """
        Duplica un producto existente y genera un nuevo SKU.

        Args:
            sku (str): SKU del producto a duplicar.

        Returns:
            str: Nuevo SKU generado.

        Raises:
            ValueError: Si el producto no existe o ya existe uno con las mismas características.
        """
        try:
            product = self.repository.get_product(sku)
            if not product:
                logger.error("Producto no encontrado con SKU %s", sku)
                raise ValueError(f"No se encontró el producto con SKU {sku}")

            with self.repository.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM productos 
                    WHERE UPPER(nombre) = UPPER(?) 
                    AND UPPER(COALESCE(nivel_educativo, '')) = UPPER(COALESCE(?, '')) 
                    AND escuela_id = ? 
                    AND UPPER(COALESCE(tipo_prenda, '')) = UPPER(COALESCE(?, '')) 
                    AND UPPER(COALESCE(tipo_pieza, '')) = UPPER(COALESCE(?, '')) 
                    AND UPPER(COALESCE(genero, '')) = UPPER(COALESCE(?, '')) 
                    AND UPPER(COALESCE(talla, '')) = UPPER(COALESCE(?, '')) 
                    AND UPPER(COALESCE(color, '')) = UPPER(COALESCE(?, '')) 
                    AND UPPER(COALESCE(escudo, '')) = UPPER(COALESCE(?, '')) 
                    AND UPPER(COALESCE(marca, '')) = UPPER(COALESCE(?, '')) 
                    AND sku != ? 
                    AND store_id = ?
                """, (
                    product["nombre"], product["nivel_educativo"], product["escuela_id"],
                    product["tipo_prenda"], product["tipo_pieza"], product["genero"],
                    product["talla"], product["color"], product["escudo"],
                    product["marca"], sku, self.store_id
                ))
                count = cursor.fetchone()[0]
                if count > 0:
                    logger.warning("Producto con características idénticas ya existe para SKU %s", sku)
                    raise ValueError("Ya existe un producto con las mismas características")

                new_sku = self.repository.generate_new_sku()
                cursor.execute("""
                    INSERT INTO productos (
                        sku, nombre, nivel_educativo, escuela_id, color, tipo_prenda, tipo_pieza, 
                        genero, atributo, ubicacion, escudo, marca, talla, qr_path, 
                        inventario, ventas, precio, image_path, store_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_sku, product["nombre"], product["nivel_educativo"], product["escuela_id"],
                    product["color"], product["tipo_prenda"], product["tipo_pieza"],
                    product["genero"], product["atributo"], product["ubicacion"],
                    product["escudo"], product["marca"], product["talla"], product["qr_path"],
                    product["inventario"], product["ventas"], product["precio"],
                    product["image_path"], self.store_id
                ))
                self.repository.db_manager.commit()
                logger.info(f"Producto duplicado con nuevo SKU: {new_sku} en tienda {self.store_id}")
                return new_sku
        except sqlite3.Error as e:
            logger.error("Error en la base de datos al duplicar producto con SKU %s: %s", sku, str(e))
            raise ValueError(f"No se pudo duplicar el producto: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al duplicar producto con SKU %s: %s", sku, str(e))
            raise

    def delete_products(self, skus):
        """
        Elimina los productos seleccionados y sus carpetas asociadas.

        Args:
            skus (list): Lista de SKUs a eliminar.

        Returns:
            int: Número de productos eliminados.

        Raises:
            ValueError: Si ocurre un error durante la eliminación.
        """
        try:
            if not skus:
                logger.warning("Lista de SKUs vacía para eliminación")
                return 0

            with self.repository.db_manager as db:
                cursor = db.get_cursor()
                talla_folders_to_delete = set()
                base_folders = set()

                for sku in skus:
                    cursor.execute("SELECT qr_path FROM productos WHERE sku = ? AND store_id = ?", (sku, self.store_id))
                    result = cursor.fetchone()
                    if result and result[0]:
                        qr_path = result[0]
                        talla_folder_relative = os.path.dirname(qr_path)
                        base_folder_relative = os.path.dirname(talla_folder_relative)
                        talla_folder_absolute = os.path.join(self.root_folder, talla_folder_relative)
                        base_folder_absolute = os.path.join(self.root_folder, base_folder_relative)
                        talla_folders_to_delete.add(talla_folder_absolute)
                        base_folders.add(base_folder_absolute)

                deleted_count = 0
                for sku in skus:
                    cursor.execute("DELETE FROM productos WHERE sku = ? AND store_id = ?", (sku, self.store_id))
                    if cursor.rowcount > 0:
                        deleted_count += 1
                        logger.info(f"Producto eliminado: SKU {sku} en tienda {self.store_id}")

                for talla_folder_absolute in talla_folders_to_delete:
                    if os.path.exists(talla_folder_absolute):
                        shutil.rmtree(talla_folder_absolute, ignore_errors=True)
                        logger.info(f"Subcarpeta de talla eliminada: {talla_folder_absolute}")
                    else:
                        logger.warning(f"Subcarpeta de talla no encontrada: {talla_folder_absolute}")

                for base_folder_absolute in base_folders:
                    if os.path.exists(base_folder_absolute) and not os.listdir(base_folder_absolute):
                        shutil.rmtree(base_folder_absolute, ignore_errors=True)
                        logger.info(f"Carpeta base vacía eliminada: {base_folder_absolute}")

                self.repository.db_manager.commit()
                logger.debug("Eliminados %d productos", deleted_count)
                return deleted_count
        except sqlite3.Error as e:
            logger.error("Error en la base de datos al eliminar productos: %s", str(e))
            raise ValueError(f"No se pudieron eliminar los productos: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al eliminar productos: %s", str(e))
            raise

    def update_inventories(self, inventory_updates):
        """
        Actualiza los inventarios de los productos seleccionados.

        Args:
            inventory_updates (dict): Diccionario con SKUs y nuevos valores de inventario.

        Returns:
            int: Número de inventarios actualizados.

        Raises:
            ValueError: Si ocurre un error durante la actualización.
        """
        try:
            if not inventory_updates:
                logger.warning("Diccionario de actualizaciones de inventario vacío")
                return 0

            with self.repository.db_manager as db:
                cursor = db.get_cursor()
                updated_count = 0
                for sku, new_inventory in inventory_updates.items():
                    cursor.execute("UPDATE productos SET inventario = ? WHERE sku = ? AND store_id = ?",
                                   (new_inventory, sku, self.store_id))
                    if cursor.rowcount > 0:
                        updated_count += 1
                        logger.debug(f"Inventario actualizado para SKU %s: %d", sku, new_inventory)
                self.repository.db_manager.commit()
                logger.debug("Actualizados %d inventarios", updated_count)
                return updated_count
        except sqlite3.Error as e:
            logger.error("Error en la base de datos al actualizar inventarios: %s", str(e))
            raise ValueError(f"No se pudieron actualizar los inventarios: {str(e)}")
        except Exception as e:
            logger.error("Error inesperado al actualizar inventarios: %s", str(e))
            raise