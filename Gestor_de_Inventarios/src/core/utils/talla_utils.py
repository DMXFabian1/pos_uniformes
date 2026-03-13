import logging

logger = logging.getLogger(__name__)

def sort_tallas(tallas, orden_tallas=None):
    """
    Ordena una lista de tallas en categorías: numéricas, americanas, españolas, especiales y otras.
    Si se proporciona orden_tallas, usa ese orden para las tallas presentes.

    Args:
        tallas (list): Lista de tallas a ordenar.
        orden_tallas (list, optional): Lista de tallas en el orden deseado (por ejemplo, desde config.json).

    Returns:
        list: Lista de tallas ordenadas.
    """
    if orden_tallas:
        logger.debug(f"Ordenando tallas con orden_tallas personalizado: {orden_tallas}")
        # Ordenar según orden_tallas, colocando tallas no definidas al final
        def get_talla_index(talla):
            try:
                return orden_tallas.index(talla)
            except ValueError:
                return len(orden_tallas)
        return sorted(tallas, key=get_talla_index)

    logger.debug("Ordenando tallas con lógica por defecto")
    # Definir categorías de tallas
    americanas = ["XS", "S", "M", "L", "XL", "XXL", "XXXL", "XXXXL"]
    españolas = ["CH", "MD", "GD", "EXG"]
    especiales = [
        "Uni", "ESP", "NT", "0-0", "0-2", "3-5", "6-8", "9-12", "13-18",
        "CH-MD", "GD-EXG", "Dama"
    ]

    # Separar tallas por categoría
    numericas = sorted([t for t in tallas if t.isdigit()], key=int)
    americanas_presentes = [t for t in americanas if t in tallas]
    españolas_presentes = [t for t in españolas if t in tallas]
    especiales_presentes = [t for t in especiales if t in tallas]
    otras = sorted([t for t in tallas if t not in numericas + americanas_presentes + españolas_presentes + especiales_presentes])

    # Combinar todas las categorías en el orden deseado
    ordenadas = numericas + americanas_presentes + españolas_presentes + especiales_presentes + otras
    logger.debug(f"Tallas ordenadas: {ordenadas}")
    return ordenadas