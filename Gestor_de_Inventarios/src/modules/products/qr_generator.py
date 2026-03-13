import logging
import os
import customtkinter as ctk
from PIL import Image, ImageTk
from src.core.utils.utils import sanitize_filename
from src.modules.products.qr_code_generator import generar_qr
from src.modules.products.standard_label_generator import generar_etiqueta
from src.modules.products.split_label_generator import generar_etiqueta_split
import io
import win32clipboard
from tkinter import messagebox

logger = logging.getLogger(__name__)

def validate_string(arg, name, allow_empty=False):
    """
    Valida que el argumento sea una cadena. Si es None, lo convierte a una cadena vacía.

    Args:
        arg (Any): Valor a validar.
        name (str): Nombre del argumento para mensajes de error.
        allow_empty (bool): Si se permiten cadenas vacías.

    Returns:
        str: Cadena validada.

    Raises:
        ValueError: Si el argumento no es una cadena válida o está vacío cuando no se permite.
    """
    if arg is None:
        arg = ""
        logger.debug(f"Argumento '{name}' era None, convertido a cadena vacía")
    if not isinstance(arg, str):
        logger.error("Argumento '%s' no es una cadena: %s", name, type(arg))
        raise ValueError(f"El argumento '{name}' debe ser una cadena")
    if not allow_empty and not arg.strip():
        logger.error("Argumento '%s' está vacío", name)
        raise ValueError(f"El argumento '{name}' no puede estar vacío")
    return arg.strip()

def extract_talla_from_path(output_path):
    """
    Extrae la talla del nombre de la carpeta en la ruta de salida.

    Args:
        output_path (str): Ruta completa del archivo de salida.

    Returns:
        str: Talla extraída, o 'Sin Talla' si no se puede determinar.
    """
    try:
        folder_path = os.path.dirname(output_path)
        talla_from_path = os.path.basename(folder_path)
        if talla_from_path and talla_from_path.lower() != "sin_talla":
            logger.debug(f"Talla extraída de la ruta '{output_path}': '{talla_from_path}'")
            return talla_from_path
        logger.debug(f"No se pudo extraer talla de la ruta '{output_path}', usando 'Sin Talla'")
        return "Sin Talla"
    except Exception as e:
        logger.error(f"Error al extraer talla de la ruta '{output_path}': {str(e)}")
        return "Sin Talla"

def generate_product_labels(sku, escuela, nivel_educativo, nombre, talla, genero, base_dir, tipo_prenda, tipo_pieza, db_manager=None, store_id=1):
    """
    Genera códigos QR y etiquetas (estándar y dividida) para un producto, manejando directorios y nombres de archivo.

    Args:
        sku (str): SKU del producto.
        escuela (str): Nombre de la escuela.
        nivel_educativo (str): Nivel educativo.
        nombre (str): Nombre del producto.
        talla (str): Talla del producto.
        genero (str): Género del producto.
        base_dir (str): Directorio base para guardar archivos.
        tipo_prenda (str): Tipo de prenda.
        tipo_pieza (str): Tipo de pieza.
        db_manager (DatabaseManager, optional): Administrador de base de datos para consultar la talla.
        store_id (int): ID de la tienda.

    Returns:
        tuple: Rutas relativas del QR, la etiqueta estándar y la etiqueta dividida.
    """
    try:
        escuela = validate_string(escuela, "escuela", allow_empty=True)
        nivel_educativo = validate_string(nivel_educativo, "nivel_educativo", allow_empty=True)
        nombre = validate_string(nombre, "nombre")
        talla = validate_string(talla, "talla", allow_empty=True)
        genero = validate_string(genero, "genero", allow_empty=True)
        tipo_prenda = validate_string(tipo_prenda, "tipo_prenda", allow_empty=True)
        tipo_pieza = validate_string(tipo_pieza, "tipo_pieza", allow_empty=True)

        # Depuración: Registrar el valor de talla recibido
        logger.debug(f"Valor de talla recibido en generate_product_labels: '{talla}'")

        # Si la talla está vacía y tenemos acceso a la base de datos, intentamos obtenerla
        if (not talla or talla.lower() in ["", "sin talla", "sin_talla"]) and db_manager:
            with db_manager as db:
                cursor = db.get_cursor()
                cursor.execute("SELECT talla FROM productos WHERE sku = ? AND store_id = ?", (sku, store_id))
                result = cursor.fetchone()
                if result and result[0]:
                    talla = result[0]
                    logger.debug(f"Talla obtenida de la base de datos para SKU {sku}: '{talla}'")
                else:
                    logger.debug(f"No se encontró talla en la base de datos para SKU {sku}, usando 'Sin Talla'")
                    talla = "Sin Talla"

        # Usamos clean_nombre desde standard_label_generator para obtener el nombre limpio
        from src.modules.products.standard_label_generator import clean_nombre
        nombre_clean = clean_nombre(nombre, talla)
        folder_name = f"{nombre_clean}_{tipo_prenda}_{tipo_pieza}".strip("_")
        folder_path = os.path.join(base_dir, folder_name.replace("/", "_").replace("\\", "_"))
        os.makedirs(folder_path, exist_ok=True)

        sanitized_talla = sanitize_filename(talla) if talla and talla.lower() not in ["", "sin talla", "sin_talla"] else "Sin_Talla"
        talla_folder = os.path.join(folder_path, sanitized_talla)
        os.makedirs(talla_folder, exist_ok=True)

        qr_filename = f"{sku}_{nombre_clean}_{sanitized_talla}_qr.png"
        label_filename = f"{sku}_{nombre_clean}_{sanitized_talla}_label.png"
        label_split_filename = f"{sku}_{nombre_clean}_{sanitized_talla}_label_split.png"
        qr_path_absolute = os.path.join(talla_folder, qr_filename)
        label_path_absolute = os.path.join(talla_folder, label_filename)
        label_split_path_absolute = os.path.join(talla_folder, label_split_filename)
        qr_path_relative = os.path.join("Mis codigos", folder_name.replace("/", "_").replace("\\", "_"), sanitized_talla, qr_filename).replace("\\", "/")
        label_path_relative = os.path.join("Mis codigos", folder_name.replace("/", "_").replace("\\", "_"), sanitized_talla, label_filename).replace("\\", "/")
        label_split_path_relative = os.path.join("Mis codigos", folder_name.replace("/", "_").replace("\\", "_"), sanitized_talla, label_split_filename).replace("\\", "/")

        # Si la talla sigue siendo vacía, intentar extraerla del nombre de la carpeta
        if not talla or talla.lower() in ["", "sin talla", "sin_talla"]:
            talla = extract_talla_from_path(label_split_path_absolute)
            logger.debug(f"Talla ajustada después de extracción de la ruta: '{talla}'")

        generar_qr(sku, qr_path_absolute, tipo_pieza)
        generar_etiqueta(sku, escuela, nivel_educativo, nombre, talla, genero, tipo_pieza, qr_path_absolute, label_path_absolute)
        generar_etiqueta_split(sku, nombre, qr_path_absolute, label_split_path_absolute, talla=talla)
        logger.info("QR y etiquetas generadas: %s, %s, %s", qr_path_relative, label_path_relative, label_split_path_relative)
        return qr_path_relative, label_path_relative, label_split_path_relative
    except Exception as e:
        logger.error("Error al generar etiquetas para SKU %s: %s", sku, str(e))
        raise

class QRGenerator:
    """
    Clase para manejar la generación y gestión de etiquetas QR para productos.
    """
    def __init__(self, root_folder, db_manager, manager, store_id=1):
        """
        Inicializa el generador de etiquetas QR.

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
        self.current_label_path = None
        logger.info("QRGenerator inicializado para tienda %d", store_id)

    def copiar_qr(self):
        """
        Copia la etiqueta QR de los productos seleccionados al portapapeles.
        """
        try:
            selected_items = self.manager.ui.tree.selection()
            if not selected_items:
                logger.warning("No se seleccionaron productos para copiar QR")
                messagebox.showwarning("Advertencia", "Selecciona al menos un producto")
                return

            with self.db_manager as db:
                cursor = db.get_cursor()
                for item in selected_items:
                    sku = self.manager.ui.tree.item(item)["values"][0].upper()
                    cursor.execute("SELECT qr_path, label_split_path FROM productos WHERE sku = ? AND store_id = ?", (sku, self.store_id))
                    result = cursor.fetchone()
                    if not result or not result[0]:
                        logger.error("No se encontró la etiqueta para SKU %s", sku)
                        messagebox.showerror("Error", f"No se encontró la etiqueta para {sku}")
                        continue

                    # Usar selected_label_type para determinar qué etiqueta copiar
                    label_type = self.manager.ui.selected_label_type.get()
                    qr_path = os.path.join(self.root_folder, result[0] if label_type == "standard" else result[1] if result[1] else result[0])
                    if not os.path.exists(qr_path):
                        logger.error("Archivo de etiqueta no encontrado: %s", qr_path)
                        messagebox.showerror("Error", f"No se encontró la etiqueta para {sku}")
                        continue

                    img = Image.open(qr_path)
                    output = io.BytesIO()
                    img.convert("RGB").save(output, format="BMP")
                    data = output.getvalue()[14:]
                    output.close()
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                    win32clipboard.CloseClipboard()
                    logger.info("Etiqueta de SKU %s copiada al portapapeles (tipo: %s)", sku, label_type)
                    messagebox.showinfo("Éxito", f"Etiqueta de {sku} copiada al portapapeles")
        except Exception as e:
            logger.error("Error al copiar QR: %s", str(e))
            messagebox.showerror("Error", f"No se pudo copiar la etiqueta: {str(e)}")

    def regenerate_label(self, sku, entries, qr_label):
        """
        Regenera la etiqueta QR para un producto.

        Args:
            sku (str): SKU del producto.
            entries (dict): Diccionario de entradas del formulario.
            qr_label (ctk.CTkLabel): Widget para mostrar la etiqueta.
        """
        try:
            nombre = entries["nombre"].get().strip()
            escuela = entries.get("escuela", ctk.CTkEntry(self.manager.root)).get().strip() if "escuela" in entries else ""
            nivel_educativo = entries.get("nivel_educativo", ctk.CTkEntry(self.manager.root)).get().strip() if "nivel_educativo" in entries else ""
            talla = entries.get("talla", ctk.CTkEntry(self.manager.root)).get().strip() if "talla" in entries else ""
            genero = entries.get("genero", ctk.CTkEntry(self.manager.root)).get().strip() if "genero" in entries else ""
            tipo_prenda = entries.get("tipo_prenda", ctk.CTkEntry(self.manager.root)).get().strip() if "tipo_prenda" in entries else ""
            tipo_pieza = entries.get("tipo_pieza", ctk.CTkEntry(self.manager.root)).get().strip() if "tipo_pieza" in entries else ""

            if not nombre:
                logger.error("Nombre requerido para regenerar etiqueta de SKU %s", sku)
                messagebox.showerror("Error", "El campo Nombre es requerido para generar la etiqueta")
                return

            # Depuración: Registrar el valor de talla desde el formulario
            logger.debug(f"Valor de talla desde el formulario en regenerate_label: '{talla}'")

            # Si la talla está vacía, intentar obtenerla de la base de datos
            if not talla or talla.lower() in ["", "sin talla", "sin_talla"]:
                with self.db_manager as db:
                    cursor = db.get_cursor()
                    cursor.execute("SELECT talla FROM productos WHERE sku = ? AND store_id = ?", (sku, self.store_id))
                    result = cursor.fetchone()
                    if result and result[0]:
                        talla = result[0]
                        logger.debug(f"Talla obtenida de la base de datos para SKU {sku}: '{talla}'")
                    else:
                        logger.debug(f"No se encontró talla en la base de datos para SKU {sku}, usando 'Sin Talla'")
                        talla = "Sin Talla"

            qr_path_relative, label_path_relative, label_split_path_relative = generate_product_labels(
                sku, escuela, nivel_educativo, nombre, talla, genero,
                os.path.join(self.root_folder, "Mis codigos"), tipo_prenda, tipo_pieza,
                db_manager=self.db_manager, store_id=self.store_id
            )

            with self.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute("UPDATE productos SET qr_path = ?, label_split_path = ? WHERE sku = ? AND store_id = ?", 
                              (label_path_relative, label_split_path_relative, sku, self.store_id))
                self.db_manager.commit()

            # Usar selected_label_type para determinar qué etiqueta mostrar
            label_type = self.manager.ui.selected_label_type.get()
            label_path_absolute = os.path.join(self.root_folder, label_path_relative if label_type == "standard" else label_split_path_relative if label_split_path_relative else label_path_relative)
            if not os.path.exists(label_path_absolute):
                logger.error("Etiqueta no encontrada: %s", label_path_absolute)
                messagebox.showerror("Error", "No se pudo encontrar la etiqueta generada")
                return

            img = Image.open(label_path_absolute)
            img.thumbnail((150, 150), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            qr_label.configure(image=photo, text="")
            qr_label.image = photo
            self.current_label_path = label_path_absolute
            logger.info("Etiqueta regenerada para SKU %s: %s (tipo: %s)", sku, label_path_absolute, label_type)
            messagebox.showinfo("Éxito", "Etiqueta regenerada correctamente")
        except Exception as e:
            logger.error("Error al regenerar etiqueta para SKU %s: %s", sku, str(e))
            messagebox.showerror("Error", f"No se pudo regenerar la etiqueta: {str(e)}")

    def copy_image_to_clipboard(self):
        """
        Copia la imagen de la etiqueta actual al portapapeles.
        """
        try:
            if not self.current_label_path or not os.path.exists(self.current_label_path):
                logger.error("No hay imagen de etiqueta para copiar")
                messagebox.showerror("Error", "No hay imagen para copiar")
                return

            img = Image.open(self.current_label_path)
            output = io.BytesIO()
            img.convert("RGB").save(output, format="BMP")
            data = output.getvalue()[14:]
            output.close()
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            logger.info("Imagen de etiqueta copiada al portapapeles: %s", self.current_label_path)
            messagebox.showinfo("Éxito", "Imagen copiada al portapapeles. Puedes pegarla en P-touch Editor")
        except Exception as e:
            logger.error("Error al copiar imagen de etiqueta: %s", str(e))
            messagebox.showerror("Error", f"No se pudo copiar la imagen: {str(e)}")

    def print_labels(self, quantity, add_to_inventory=False):
        """
        Imprime etiquetas para un producto seleccionado.

        Args:
            quantity (int): Número de etiquetas a imprimir.
            add_to_inventory (bool): Si True, incrementa el inventario.
        """
        try:
            selected_items = self.manager.ui.tree.selection()
            if not selected_items:
                logger.warning("No se seleccionaron productos para imprimir etiquetas")
                messagebox.showwarning("Advertencia", "Selecciona un producto para imprimir etiquetas")
                return
            if len(selected_items) > 1:
                logger.warning("Múltiples productos seleccionados para imprimir etiquetas")
                messagebox.showwarning("Advertencia", "Selecciona solo un producto para imprimir etiquetas")
                return
            if quantity is None or quantity < 1:
                logger.error("Cantidad inválida para imprimir etiquetas: %s", quantity)
                messagebox.showwarning("Advertencia", "La cantidad de etiquetas debe ser mayor que 0")
                return

            # Pasar el tipo de etiqueta seleccionado a print_labels
            label_type = self.manager.ui.selected_label_type.get()
            self.manager.print_labels(quantity, add_to_inventory, label_type=label_type)
            logger.info("Enviadas %d etiquetas para imprimir con add_to_inventory=%s (tipo: %s)", quantity, add_to_inventory, label_type)
        except Exception as e:
            logger.error("Error al imprimir etiquetas: %s", str(e))
            messagebox.showerror("Error", f"No se pudo imprimir las etiquetas: {str(e)}")