import logging

logger = logging.getLogger(__name__)

def build_label_text(nombre_clean, talla):
    """
    Construye el texto de la etiqueta combinando el nombre limpio y la talla.

    Args:
        nombre_clean (str): Nombre limpio del producto.
        talla (str): Talla del producto.

    Returns:
        str: Texto completo de la etiqueta (por ejemplo, "Falda Cuatro tablas T: 30").
    """
    try:
        if talla and talla.lower() not in ["", "sin talla", "sin_talla"]:
            label_text = f"{nombre_clean} T: {talla}"
            logger.debug(f"Texto de etiqueta construido: '{label_text}' con talla: '{talla}'")
        else:
            label_text = f"{nombre_clean} T: Sin Talla"
            logger.debug(f"Texto de etiqueta construido: '{label_text}' (sin talla válida)")
        return label_text
    except Exception as e:
        logger.error("Error al construir el texto de la etiqueta: %s", str(e))
        raise