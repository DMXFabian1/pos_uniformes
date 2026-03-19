import sqlite3
import logging
import os
import re
from PIL import Image, ImageDraw, ImageFont, ImageWin
import customtkinter as ctk
from tkinter import messagebox
import win32print
import win32ui
import textwrap
from src.core.config.db_manager import DatabaseManager
from src.modules.products.label_text_builder import build_label_text as build_compact_label_text
from src.modules.products.qr_code_generator import ensure_print_quality_qr, generar_qr

logger = logging.getLogger(__name__)

def validate_string(arg, name, allow_empty=False):
    """
    Valida que el argumento sea una cadena. Si es None, lo convierte a una cadena vacía.
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

def clean_nombre(nombre, talla):
    """
    Limpia el campo nombre eliminando 'Talla' y cualquier valor asociado.
    """
    try:
        nombre_clean = validate_string(nombre, "nombre")
        talla = validate_string(talla, "talla", allow_empty=True)
        
        nombre_lower = nombre_clean.lower()
        if "talla" in nombre_lower:
            talla_idx = nombre_lower.index("talla")
            nombre_clean = nombre_clean[:talla_idx].strip()
        else:
            nombre_clean = nombre_clean.split("_")[0].strip()

        nombre_clean = re.sub(r"(?i)\b(?:talla|t)\s*[:#-]?\s*\S+\s*$", "", nombre_clean).strip(" |,-")
        nombre_clean = " ".join(nombre_clean.split())
        logger.debug("Nombre limpio: %s", nombre_clean)
        return nombre_clean
    except Exception as e:
        logger.error("Error al limpiar nombre '%s': %s", nombre, str(e))
        raise

def adjust_font_size(draw, text, font_path, initial_size, max_width, min_size=24):
    """
    Ajusta el tamaño de la fuente para que el texto quepa en el ancho máximo.
    """
    font_size = initial_size
    while font_size >= min_size:
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            logger.warning("No se pudo cargar la fuente %s, usando fuente por defecto", font_path)
            font = ImageFont.load_default()
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        if text_width <= max_width:
            return font
        font_size -= 2
    try:
        logger.debug(f"Usando tamaño de fuente mínimo: {min_size}")
        return ImageFont.truetype(font_path, min_size)
    except IOError:
        logger.warning("No se pudo cargar la fuente mínima, usando fuente por defecto")
        return ImageFont.load_default()

def extract_talla_from_path(output_path):
    """
    Extrae la talla del nombre de la carpeta en la ruta de salida.
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

def build_label_text(nombre, talla):
    """
    Construye el texto para la etiqueta combinando nombre y talla.
    """
    nombre = validate_string(nombre, "nombre")
    talla = validate_string(talla, "talla", allow_empty=True)
    return build_compact_label_text(nombre, talla).replace(" T: ", "\nT: ")

def generar_etiqueta_split(sku, nombre, qr_path, output_path, talla=None):
    """
    Genera una etiqueta dividida en cuatro partes, cada una de 244x342 píxeles.
    """
    try:
        logger.debug("Generando etiqueta dividida: sku=%s, nombre=%s, qr_path=%s, output_path=%s, talla=%s",
                     sku, nombre, qr_path, output_path, talla)

        sku = validate_string(sku, "sku")
        nombre = validate_string(nombre, "nombre")
        qr_path = validate_string(qr_path, "qr_path")
        output_path = validate_string(output_path, "output_path")
        talla = validate_string(talla, "talla", allow_empty=True)

        if not talla or talla.lower() in ["", "sin talla", "sin_talla"]:
            talla = extract_talla_from_path(output_path)
            logger.debug(f"Talla ajustada después de extracción de la ruta: '{talla}'")

        if not os.path.exists(qr_path):
            logger.error("Archivo QR no encontrado: %s", qr_path)
            raise IOError(f"El archivo QR no existe: {qr_path}")

        label_width = 976
        label_height = 342
        label_image = Image.new("L", (label_width, label_height), 255)
        draw = ImageDraw.Draw(label_image)

        qr_image = Image.open(qr_path)
        qr_size = 231
        qr_image = qr_image.resize((qr_size, qr_size), Image.Resampling.NEAREST)
        qr_image = qr_image.convert("L")

        font_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "fonts", "arial.ttf")
        initial_font_size = 36
        max_text_width = 231
        line_spacing = 8

        nombre_clean = clean_nombre(nombre, talla)
        label_text = build_label_text(nombre_clean, talla)
        label_lines = textwrap.wrap(label_text, width=20)

        section_width = 244
        available_text_height = label_height - (10 + qr_size + 10)  # Espacio disponible debajo del QR (10 = qr_y, 10 = margen inferior)

        for section in range(4):
            section_x = section * section_width
            qr_x = section_x + (section_width - qr_size) // 2
            qr_y = 10  # Movido más arriba (de 20 a 10)
            label_image.paste(qr_image, (qr_x, qr_y))

            text_y = qr_y + qr_size + 3  # Margen inicial reducido (de 5 a 3)
            font = adjust_font_size(draw, label_text, font_path, initial_font_size, max_text_width, min_size=20)

            total_text_height = 0
            for line in label_lines:
                text_bbox = font.getbbox(line)
                line_height = text_bbox[3] - text_bbox[1]
                total_text_height += line_height + line_spacing

            # Verificar si el texto cabe en el espacio disponible
            if total_text_height > available_text_height:
                logger.debug(f"El texto es demasiado alto ({total_text_height}px) para el espacio disponible ({available_text_height}px)")
                font = adjust_font_size(draw, label_text, font_path, initial_font_size - 4, max_text_width, min_size=16)

            for line in label_lines:
                text_bbox = font.getbbox(line)
                text_width = text_bbox[2] - text_bbox[0]
                line_height = text_bbox[3] - text_bbox[1]
                text_x = qr_x + (qr_size - text_width) // 2
                if text_y + line_height <= label_height:  # Asegurarse de no dibujar fuera de la etiqueta
                    draw.text((text_x, text_y), line, font=font, fill=0)
                    text_y += line_height + line_spacing
                else:
                    logger.warning(f"Línea de texto truncada en la sección {section} para SKU {sku}")
                    break

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        label_image.save(output_path, "PNG")
        logger.debug(f"Etiqueta dividida generada y guardada en: {output_path}")
        return True
    except Exception as e:
        logger.error("Error al generar etiqueta dividida: %s", str(e))
        raise

class ScanAndPrintApp:
    def __init__(self, parent, root_folder, db_manager, store_id=1):
        self.parent = parent
        self.root_folder = root_folder
        self.db_manager = db_manager
        self.store_id = store_id
        self.window = ctk.CTkToplevel(parent)
        self.window.title("Escanear e Imprimir Etiqueta")
        self.window.geometry("400x200")
        self.window.configure(fg_color="#F5F7FA")
        self.window.transient(parent)
        self.window.grab_set()
        self.setup_ui()
        logger.info("ScanAndPrintApp inicializada")
        # Asegurar que el campo de entrada tenga el foco al abrir
        self.window.after(100, self.sku_entry.focus_set)

    def setup_ui(self):
        main_frame = ctk.CTkFrame(self.window, fg_color="#E6F0FA")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            main_frame,
            text="Escanear SKU",
            font=("Helvetica", 16, "bold"),
            text_color="#1A2E5A"
        ).pack(pady=10)

        self.sku_entry = ctk.CTkEntry(
            main_frame,
            placeholder_text="Ingresa o escanea el SKU",
            width=300,
            font=("Helvetica", 14)
        )
        self.sku_entry.pack(pady=10)
        self.sku_entry.bind("<Return>", lambda event: self.scan_and_print())
        # No necesitamos focus_set aquí porque lo manejamos en __init__

        print_button = ctk.CTkButton(
            main_frame,
            text="Imprimir Etiqueta",
            command=self.scan_and_print,
            fg_color="#4A90E2",
            hover_color="#2A6EBB",
            font=("Helvetica", 14),
            width=200
        )
        print_button.pack(pady=10)

    def generate_qr_code(self, sku):
        """
        Genera un código QR para el SKU y lo guarda en el directorio de QRs.
        """
        try:
            qr_path = os.path.join(self.root_folder, f"labels/qr/{sku}_qr.png")
            os.makedirs(os.path.dirname(qr_path), exist_ok=True)
            generar_qr(sku, qr_path)
            logger.debug(f"Código QR generado y guardado en: {qr_path}")

            # Actualizar la base de datos con la nueva ruta del QR
            with self.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute(
                    "UPDATE productos SET qr_path = ? WHERE sku = ? AND store_id = ?",
                    (f"labels/qr/{sku}_qr.png", sku.upper(), self.store_id)
                )
                db.commit()
                logger.debug(f"Base de datos actualizada con qr_path para SKU {sku}")
            return qr_path
        except Exception as e:
            logger.error(f"Error al generar código QR para SKU {sku}: {str(e)}")
            raise

    def get_product_info(self, sku):
        """
        Obtiene la información del producto desde la base de datos.
        """
        try:
            with self.db_manager as db:
                cursor = db.get_cursor()
                cursor.execute(
                    "SELECT sku, nombre, talla, tipo_pieza, qr_path, label_split_path FROM productos WHERE sku = ? AND store_id = ?",
                    (sku.upper(), self.store_id)
                )
                result = cursor.fetchone()
                if result:
                    return {
                        "sku": result["sku"],
                        "nombre": result["nombre"],
                        "talla": result["talla"],
                        "tipo_pieza": result["tipo_pieza"],
                        "qr_path": result["qr_path"],
                        "label_split_path": result["label_split_path"]
                    }
                logger.warning(f"No se encontró producto con SKU {sku}")
                return None
        except sqlite3.Error as e:
            logger.error(f"Error al consultar base de datos: {str(e)}")
            raise

    def scan_and_print(self):
        """
        Procesa el SKU escaneado y genera e imprime la etiqueta dividida.
        """
        try:
            sku = validate_string(self.sku_entry.get(), "sku")
            logger.debug(f"Procesando SKU: {sku}")

            product = self.get_product_info(sku)
            if not product:
                messagebox.showerror("Error", f"No se encontró el producto con SKU {sku}")
                return

            qr_path = product["qr_path"]
            # Si no hay qr_path o el archivo no existe, generar un nuevo QR
            if not qr_path or not os.path.exists(os.path.join(self.root_folder, qr_path)):
                logger.info(f"Archivo QR no encontrado para SKU {sku}, generando uno nuevo")
                qr_path = self.generate_qr_code(sku)
                qr_regenerated = True
            else:
                qr_path = os.path.join(self.root_folder, qr_path)
                qr_regenerated = ensure_print_quality_qr(
                    product["sku"],
                    qr_path,
                    product.get("tipo_pieza"),
                )

            # Generar o recuperar la etiqueta dividida
            label_split_path = product["label_split_path"]
            if qr_regenerated or not label_split_path or not os.path.exists(os.path.join(self.root_folder, label_split_path)):
                output_path = os.path.join(self.root_folder, f"labels/split/{sku}_split.png")
                generar_etiqueta_split(
                    sku=product["sku"],
                    nombre=product["nombre"],
                    qr_path=qr_path,
                    output_path=output_path,
                    talla=product["talla"]
                )
                label_split_path = output_path

                # Actualizar la base de datos con la nueva ruta de la etiqueta dividida
                with self.db_manager as db:
                    cursor = db.get_cursor()
                    cursor.execute(
                        "UPDATE productos SET label_split_path = ? WHERE sku = ? AND store_id = ?",
                        (f"labels/split/{sku}_split.png", sku.upper(), self.store_id)
                    )
                    db.commit()
                    logger.debug(f"Base de datos actualizada con label_split_path para SKU {sku}")
            else:
                label_split_path = os.path.join(self.root_folder, label_split_path)

            # Imprimir la etiqueta
            self.print_label(label_split_path, sku)
            messagebox.showinfo("Éxito", f"Etiqueta dividida para SKU {sku} impresa correctamente")
            self.sku_entry.delete(0, "end")
            self.sku_entry.focus_set()

        except ValueError as ve:
            logger.error(f"Error de validación: {str(ve)}")
            messagebox.showerror("Error", str(ve))
            self.sku_entry.delete(0, "end")
            self.sku_entry.focus_set()
        except Exception as e:
            logger.error(f"Error al procesar e imprimir: {str(e)}")
            messagebox.showerror("Error", f"No se pudo imprimir la etiqueta: {str(e)}")
            self.sku_entry.delete(0, "end")
            self.sku_entry.focus_set()

    def print_label(self, label_path, sku):
        """
        Imprime la etiqueta dividida usando la impresora Brother QL-800.
        """
        hprinter = None
        hdc = None
        try:
            printer_name = "Brother QL-800"
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
            if not any(printer_name in printer[2] for printer in printers):
                raise ValueError(f"La impresora {printer_name} no está disponible")

            hprinter = win32print.OpenPrinter(printer_name)
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(printer_name)
            image = Image.open(label_path).convert("L").point(lambda x: 0 if x < 128 else 255, "1")
            label_width, label_height = image.size
            logger.debug(f"Tamaño de la etiqueta: {label_width}x{label_height}")

            hdc.StartDoc(f"Label Print Job - {sku}")
            hdc.StartPage()
            dib = ImageWin.Dib(image)
            dib.draw(hdc.GetHandleOutput(), (0, 0, label_width, label_height))
            hdc.EndPage()
            hdc.EndDoc()
            logger.info(f"Etiqueta impresa para SKU {sku}")

        except Exception as e:
            logger.error(f"Error al imprimir etiqueta para SKU {sku}: {str(e)}")
            raise
        finally:
            if hdc:
                try:
                    hdc.DeleteDC()
                    logger.debug("Contexto de dispositivo de impresora liberado")
                except Exception as e:
                    logger.warning(f"Error al liberar contexto de dispositivo: {str(e)}")
            if hprinter:
                try:
                    win32print.ClosePrinter(hprinter)
                    logger.debug("Manejador de impresora cerrado")
                except Exception as e:
                    logger.warning(f"Error al cerrar manejador de impresora: {str(e)}")

    def destroy(self):
        """
        Cierra la ventana y libera recursos.
        """
        if self.window.winfo_exists():
            self.window.destroy()
            logger.debug("Ventana ScanAndPrintApp cerrada")
