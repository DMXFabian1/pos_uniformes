import customtkinter as ctk
from src.modules.products.product_manager_window import ProductManagerWindow
from src.core.config.config import CONFIG
from src.core.config.db_manager import DatabaseManager
from src.core.paths import BASE_DIR, ICONS_DIR
import logging
import os
from PIL import Image, ImageTk
from tkinter import messagebox
import sys

logger = logging.getLogger(__name__)

class ProductManager:
    """
    Clase principal para la gestión de productos.
    Inicializa la interfaz y coordina la lógica de gestión.
    """
    def __init__(self, app, parent_frame, store_id=1):
        """
        Inicializa el módulo de gestión de productos.

        Args:
            app (App): Instancia de la aplicación principal.
            parent_frame (tk.Widget): Frame padre donde se incrustará la ventana.
            store_id (int): ID de la tienda.
        """
        logger.debug("Iniciando ProductManager")
        self.app = app
        self.parent_frame = parent_frame
        self.store_id = store_id
        self.root = self._validate_root(app)
        self.db_manager = self._validate_db_manager(app)
        self.root_folder = self._get_root_folder(app)
        self.icons = self.load_icons()
        self.tallas_personalizadas = getattr(app, 'tallas_personalizadas', [])
        self.user_id = getattr(app, 'user_id', "unknown_user")
        self.role = getattr(app, 'role', "unknown_role")
        logger.info(f"ProductManager inicializado para usuario {self.user_id} con rol {self.role} en tienda {self.store_id}")

        self.window = ProductManagerWindow(self, parent_frame, self.root, self.icons, store_id=store_id)
        self.setup_ui()

    def _validate_root(self, app):
        """
        Valida que la ventana raíz de Tkinter esté definida.

        Args:
            app (App): Instancia de la aplicación.

        Returns:
            tk.Tk: Ventana raíz.

        Raises:
            ValueError: Si root no está definido.
        """
        if not hasattr(app, 'root') or app.root is None:
            logger.error("Ventana raíz (root) no está definida en app")
            raise ValueError("La ventana raíz no está definida")
        return app.root

    def _validate_db_manager(self, app):
        """
        Valida que el administrador de base de datos esté definido.

        Args:
            app (App): Instancia de la aplicación.

        Returns:
            DatabaseManager: Instancia del administrador de base de datos.

        Raises:
            ValueError: Si db_manager no está definido.
        """
        if not hasattr(app, 'db_manager') or app.db_manager is None:
            logger.error("db_manager no está definido en app")
            raise ValueError("El administrador de base de datos no está definido")
        return app.db_manager

    def _get_root_folder(self, app):
        """
        Obtiene la carpeta raíz, usando la configuración por defecto si no está definida.

        Args:
            app (App): Instancia de la aplicación.

        Returns:
            str: Ruta de la carpeta raíz.
        """
        return getattr(app, 'root_folder', CONFIG.get('ROOT_FOLDER', BASE_DIR))

    def load_icons(self):
        """
        Carga los íconos para la interfaz.

        Returns:
            dict: Diccionario con los íconos cargados (clave: nombre, valor: ImageTk.PhotoImage).
        """
        icons = {}
        icon_files = {
            "edit": "edit.png",
            "copy": "copy.png",
            "delete": "delete.png",
            "duplicate": "duplicate.png",
            "price": "price.png",
            "print": "print.png",
            "inventory": "inventory.png"
        }

        for key, file_name in icon_files.items():
            try:
                icon_path = os.path.join(ICONS_DIR, file_name)
                logger.debug(f"Intentando cargar ícono: {icon_path}")
                if not os.path.exists(icon_path):
                    logger.warning(f"Archivo de ícono no encontrado: {icon_path}")
                    continue
                img = Image.open(icon_path)
                img = img.resize((24, 24), Image.Resampling.LANCZOS)
                icons[key] = ImageTk.PhotoImage(img)
                logger.debug(f"Ícono cargado: {key}")
            except Exception as e:
                logger.error(f"Error al cargar ícono {key}: {str(e)}")

        if not icons:
            logger.warning("No se cargaron íconos, inicializando diccionario vacío")
        return icons

    def setup_ui(self):
        """
        Configura la interfaz inicial del módulo de gestión de productos.
        """
        try:
            logger.debug("Configurando UI de ProductManager")
            self.window.ui.initialize_comboboxes()
            self.window.cargar_productos()
            logger.debug("UI configurada y datos iniciales cargados")
        except Exception as e:
            logger.error(f"Error al configurar UI: {str(e)}")
            messagebox.showerror("Error", f"No se pudo configurar la interfaz: {str(e)}")

    def on_closing(self):
        """
        Realiza la limpieza al cerrar el módulo.
        """
        logger.debug("Cerrando ProductManager")
        try:
            if self.window:
                self.window.on_closing()
                self.window = None
            logger.debug("ProductManager cerrado y recursos limpiados")
        except Exception as e:
            logger.error(f"Error al cerrar ProductManager: {str(e)}")
            messagebox.showerror("Error", f"Error al cerrar la gestión de productos: {str(e)}")

def abrir_gestion_productos(app, parent_frame, store_id=1):
    """
    Crea y devuelve una instancia de ProductManager.

    Args:
        app (App): Instancia de la aplicación principal.
        parent_frame (tk.Widget): Frame padre donde se incrustará la ventana.
        store_id (int): ID de la tienda.

    Returns:
        ProductManager: Instancia del módulo de gestión de productos.
    """
    try:
        return ProductManager(app, parent_frame, store_id=store_id)
    except Exception as e:
        logger.error(f"Error al abrir Gestión de Productos para tienda {store_id}: {str(e)}")
        raise