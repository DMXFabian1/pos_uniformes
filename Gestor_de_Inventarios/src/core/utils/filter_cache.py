import logging

logger = logging.getLogger(__name__)

class FilterCache:
    """
    Clase que gestiona un caché para almacenar valores únicos de filtros,
    reduciendo consultas repetitivas a la base de datos.
    """
    def __init__(self):
        """
        Inicializa el caché como un diccionario vacío.
        """
        self.cache = {}
        logger.debug("FilterCache inicializado")

    def get(self, column, get_values_callback):
        """
        Obtiene valores desde el caché o los carga si no existen.

        Args:
            column (str): Columna para la cual obtener valores.
            get_values_callback (callable): Función para obtener valores si no están en caché.

        Returns:
            list: Valores únicos para la columna.
        """
        if column not in self.cache:
            logger.debug(f"Cargando valores para {column} desde la base de datos")
            self.cache[column] = get_values_callback()
        else:
            logger.debug(f"Valores para {column} obtenidos del caché")
        return self.cache[column]

    def invalidate(self, column=None):
        """
        Invalida el caché para una columna específica o todas.

        Args:
            column (str, optional): Columna a invalidar. Si es None, invalida todo.
        """
        if column:
            self.cache.pop(column, None)
            logger.debug(f"Caché invalidado para {column}")
        else:
            self.cache.clear()
            logger.debug("Caché completo invalidado")