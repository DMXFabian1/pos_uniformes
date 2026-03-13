import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class FileManager:
    """
    Clase que maneja operaciones de archivos para el sistema de gestión de productos.
    """
    def __init__(self, root_folder):
        """
        Inicializa el administrador de archivos.

        Args:
            root_folder (str): Carpeta raíz para el almacenamiento de archivos.

        Raises:
            ValueError: Si root_folder no es una ruta válida.
        """
        if not root_folder or not os.path.isdir(root_folder):
            logger.error("Carpeta raíz inválida: %s", root_folder)
            raise ValueError("La carpeta raíz no es válida o no existe")
        self.root_folder = os.path.abspath(root_folder)
        logger.debug("FileManager inicializado con root_folder: %s", self.root_folder)

    def save_image(self, source_path, destination_subfolder="ProductImages"):
        """
        Copia una imagen al sistema y retorna la ruta relativa.

        Args:
            source_path (str): Ruta del archivo de imagen fuente.
            destination_subfolder (str): Subcarpeta destino dentro de root_folder.

        Returns:
            str: Ruta relativa de la imagen guardada.

        Raises:
            ValueError: Si la imagen no es válida o no se puede copiar.
            PermissionError: Si no hay permisos para copiar el archivo.
        """
        try:
            if not os.path.isfile(source_path):
                logger.error("Archivo fuente no encontrado: %s", source_path)
                raise ValueError(f"El archivo {source_path} no existe")
            
            file_extension = os.path.splitext(source_path)[1].lower()
            if file_extension not in [".png", ".jpg", ".jpeg", ".gif", ".bmp"]:
                logger.error("Formato de imagen no soportado: %s", file_extension)
                raise ValueError(f"El formato {file_extension} no es soportado")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"product_image_{timestamp}{file_extension}"
            destination_path = os.path.join(self.root_folder, destination_subfolder, new_filename)
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            
            shutil.copy(source_path, destination_path)
            relative_path = os.path.join(destination_subfolder, new_filename).replace("\\", "/")
            logger.info("Imagen guardada: %s", relative_path)
            return relative_path
        except PermissionError as e:
            logger.error("Error de permisos al copiar imagen: %s", str(e))
            raise
        except Exception as e:
            logger.error("Error al guardar imagen: %s", str(e))
            raise ValueError(f"No se pudo guardar la imagen: {str(e)}")

    def delete_product_folders(self, qr_paths):
        """
        Elimina las carpetas asociadas a los productos basadas en los qr_paths.

        Args:
            qr_paths (list): Lista de rutas relativas de etiquetas QR.

        Raises:
            ValueError: Si ocurre un error al eliminar las carpetas.
        """
        try:
            if not qr_paths:
                logger.debug("Lista de qr_paths vacía, no se eliminan carpetas")
                return

            talla_folders_to_delete = set()
            base_folders = set()

            for qr_path in qr_paths:
                if not qr_path:
                    continue
                talla_folder_relative = os.path.dirname(qr_path)
                base_folder_relative = os.path.dirname(talla_folder_relative)
                talla_folder_absolute = os.path.normpath(os.path.join(self.root_folder, talla_folder_relative))
                base_folder_absolute = os.path.normpath(os.path.join(self.root_folder, base_folder_relative))

                # Verificar que las rutas estén dentro de root_folder
                if not talla_folder_absolute.startswith(self.root_folder) or not base_folder_absolute.startswith(self.root_folder):
                    logger.warning("Ruta fuera de root_folder: %s", talla_folder_absolute)
                    continue

                talla_folders_to_delete.add(talla_folder_absolute)
                base_folders.add(base_folder_absolute)

            for talla_folder_absolute in talla_folders_to_delete:
                if os.path.exists(talla_folder_absolute):
                    shutil.rmtree(talla_folder_absolute, ignore_errors=True)
                    logger.info("Subcarpeta de talla eliminada: %s", talla_folder_absolute)
                else:
                    logger.debug("Subcarpeta de talla no encontrada: %s", talla_folder_absolute)

            for base_folder_absolute in base_folders:
                if os.path.exists(base_folder_absolute) and not os.listdir(base_folder_absolute):
                    shutil.rmtree(base_folder_absolute, ignore_errors=True)
                    logger.info("Carpeta base vacía eliminada: %s", base_folder_absolute)

            logger.debug("Eliminación de carpetas completada")
        except Exception as e:
            logger.error("Error al eliminar carpetas de productos: %s", str(e))
            raise ValueError(f"No se pudieron eliminar las carpetas: {str(e)}")

    def get_absolute_path(self, relative_path):
        """
        Convierte una ruta relativa en una ruta absoluta.

        Args:
            relative_path (str): Ruta relativa dentro de root_folder.

        Returns:
            str: Ruta absoluta, o None si la ruta es inválida.

        Raises:
            ValueError: Si la ruta relativa es inválida o está fuera de root_folder.
        """
        try:
            if not relative_path:
                logger.debug("Ruta relativa vacía")
                return None

            absolute_path = os.path.normpath(os.path.join(self.root_folder, relative_path))
            if not absolute_path.startswith(self.root_folder):
                logger.error("Ruta relativa fuera de root_folder: %s", relative_path)
                raise ValueError("La ruta relativa está fuera de la carpeta raíz")
            
            logger.debug("Ruta absoluta generada: %s", absolute_path)
            return absolute_path
        except Exception as e:
            logger.error("Error al convertir ruta relativa %s: %s", relative_path, str(e))
            raise ValueError(f"No se pudo convertir la ruta relativa: {str(e)}")