import logging
import re

logger = logging.getLogger(__name__)

def _normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def clean_label_name(nombre_clean, escuela="", nivel_educativo=""):
    """
    Limpia el nombre mostrado en la etiqueta para evitar datos repetidos o tallas incrustadas.
    """
    raw_text = re.sub(r"\s+", " ", str(nombre_clean or "").replace("\n", " ")).strip(" |-_")
    if not raw_text:
        return ""

    parts = [part.strip(" |-_") for part in raw_text.split("|")]
    ignore_values = {
        _normalize_text(escuela),
        _normalize_text(nivel_educativo),
        _normalize_text(f"{nivel_educativo} - {escuela}") if escuela and nivel_educativo else "",
    }

    filtered_parts = [
        part for part in parts
        if part and _normalize_text(part) not in ignore_values
    ]
    cleaned_text = " | ".join(filtered_parts or parts)
    cleaned_text = re.sub(r"(?i)\b(?:talla|t)\s*[:#-]?\s*[^|]+$", "", cleaned_text).strip(" |,-")
    cleaned_text = re.sub(r"\s+", " ", cleaned_text)
    cleaned_text = re.sub(r"\s*\|\s*", " | ", cleaned_text)
    logger.debug("Nombre limpio para etiqueta: '%s' -> '%s'", nombre_clean, cleaned_text)
    return cleaned_text


def build_label_text(nombre_clean, talla, escuela="", nivel_educativo=""):
    """
    Construye el texto de la etiqueta combinando el nombre limpio y la talla.

    Args:
        nombre_clean (str): Nombre limpio del producto.
        talla (str): Talla del producto.
        escuela (str): Escuela del producto para eliminar duplicados.
        nivel_educativo (str): Nivel educativo del producto para eliminar duplicados.

    Returns:
        str: Texto completo de la etiqueta (por ejemplo, "Falda Cuatro tablas T: 30").
    """
    try:
        cleaned_name = clean_label_name(nombre_clean, escuela=escuela, nivel_educativo=nivel_educativo)
        if talla and talla.lower() not in ["", "sin talla", "sin_talla"]:
            label_text = f"{cleaned_name} T: {talla}"
            logger.debug(f"Texto de etiqueta construido: '{label_text}' con talla: '{talla}'")
        else:
            label_text = f"{cleaned_name} T: Sin Talla"
            logger.debug(f"Texto de etiqueta construido: '{label_text}' (sin talla válida)")
        return label_text
    except Exception as e:
        logger.error("Error al construir el texto de la etiqueta: %s", str(e))
        raise
