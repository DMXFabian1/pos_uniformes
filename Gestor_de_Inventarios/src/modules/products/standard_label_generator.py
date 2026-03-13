import logging
import os
from PIL import Image, ImageDraw, ImageFont
from src.modules.products.label_text_builder import build_label_text

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

def clean_nombre(nombre, talla):
    """
    Limpia el campo nombre eliminando 'Talla' y cualquier valor asociado, incluyendo partes posteriores.

    Args:
        nombre (str): Nombre del producto.
        talla (str): Talla del producto.

    Returns:
        str: Nombre limpio sin 'Talla' ni partes posteriores.
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
        
        nombre_clean = " ".join(nombre_clean.split())
        logger.debug("Nombre limpio: %s", nombre_clean)
        return nombre_clean
    except Exception as e:
        logger.error("Error al limpiar nombre '%s': %s", nombre, str(e))
        raise

def adjust_font_size(draw, text, font_path, initial_size, max_width, min_size=24):
    """
    Ajusta el tamaño de la fuente para que el texto quepa en el ancho máximo, pero no se reduce por debajo de min_size.

    Args:
        draw (ImageDraw.Draw): Objeto de dibujo.
        text (str): Texto a medir.
        font_path (str): Ruta de la fuente.
        initial_size (int): Tamaño inicial de la fuente.
        max_width (int): Ancho máximo permitido.
        min_size (int): Tamaño mínimo permitido para la fuente.

    Returns:
        ImageFont: Fuente ajustada.
    """
    font_size = initial_size
    while font_size >= min_size:  # No reducir por debajo de min_size
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

def generar_etiqueta(sku, escuela, nivel_educativo, nombre, talla, genero, tipo_pieza, qr_path, output_path):
    """
    Genera una etiqueta estándar con información del producto y un código QR.
    No incluye el campo 'Tipo' en la etiqueta.

    Args:
        sku (str): SKU del producto.
        escuela (str): Nombre de la escuela.
        nivel_educativo (str): Nivel educativo.
        nombre (str): Nombre del producto.
        talla (str): Talla del producto.
        genero (str): Género del producto (no se incluye en la etiqueta).
        tipo_pieza (str): Tipo de pieza del producto (no se incluye en la etiqueta).
        qr_path (str): Ruta del código QR.
        output_path (str): Ruta donde guardar la etiqueta.

    Returns:
        bool: True si se generó correctamente.

    Raises:
        ValueError: Si los argumentos son inválidos.
        IOError: Si hay un error al acceder a los archivos.
    """
    try:
        logger.debug("Generando etiqueta estándar: sku=%s, escuela=%s, nivel_educativo=%s, nombre=%s, talla=%s, genero=%s, tipo_pieza=%s, qr_path=%s, output_path=%s",
                     sku, escuela, nivel_educativo, nombre, talla, genero, tipo_pieza, qr_path, output_path)

        sku = validate_string(sku, "sku")
        escuela = validate_string(escuela, "escuela", allow_empty=True)
        nivel_educativo = validate_string(nivel_educativo, "nivel_educativo", allow_empty=True)
        nombre = validate_string(nombre, "nombre")
        talla = validate_string(talla, "talla", allow_empty=True)
        genero = validate_string(genero, "genero", allow_empty=True)
        tipo_pieza = validate_string(tipo_pieza, "tipo_pieza", allow_empty=True)
        qr_path = validate_string(qr_path, "qr_path")
        output_path = validate_string(output_path, "output_path")

        if not os.path.exists(qr_path):
            logger.error("Archivo QR no encontrado: %s", qr_path)
            raise IOError(f"El archivo QR no existe: {qr_path}")

        label_width = 992  # Updated to match previous qr_generator.py
        label_height = 271  # Updated to match previous qr_generator.py
        label_image = Image.new("1", (label_width, label_height), 1)
        draw = ImageDraw.Draw(label_image)

        qr_image = Image.open(qr_path)
        qr_size = 231  # Updated to match previous qr_generator.py
        qr_image = qr_image.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        qr_image = qr_image.convert("1")
        qr_x = label_width - qr_size - 20
        qr_y = (label_height - qr_size) // 2
        label_image.paste(qr_image, (qr_x, qr_y))

        font_path = "arial.ttf"
        initial_font_size = 30
        text_x = 20
        line_spacing = 10
        max_text_width = qr_x - 40

        nombre_clean = clean_nombre(nombre, talla)
        label_text = build_label_text(nombre_clean, talla)

        if escuela in ["Sin escuela", "", None]:
            escuela = ""
        if nivel_educativo in ["Sin nivel educativo", "", None]:
            nivel_educativo = ""

        fields = []
        if escuela.strip() and nivel_educativo.strip():
            fields.append(f"{nivel_educativo} - {escuela}")
        fields.append(label_text)
        fields.append(f"Talla: {talla}" if talla else "Sin Talla")
        fields.append(sku)

        line_height = 40
        text_height = len(fields) * line_height + (len(fields) - 1) * line_spacing
        text_y = (label_height - text_height) // 2

        for field in fields:
            font = adjust_font_size(draw, field, font_path, initial_font_size, max_text_width)
            draw.text((text_x, text_y), field, font=font, fill=0)
            text_y += line_height + line_spacing

        label_image.save(output_path, "PNG")
        logger.info("Etiqueta estándar generada y guardada en: %s", output_path)
        return True
    except ValueError as ve:
        logger.error("Error de validación en generar_etiqueta: %s", str(ve))
        raise
    except IOError as ioe:
        logger.error("Error de E/S al generar etiqueta estándar en %s: %s", output_path, str(ioe))
        raise
    except Exception as e:
        logger.error("Error inesperado al generar etiqueta estándar en %s: %s", output_path, str(e))
        raise