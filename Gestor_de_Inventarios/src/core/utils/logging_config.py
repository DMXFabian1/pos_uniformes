import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from src.core.paths import BASE_DIR

def setup_logging(store_id=None):
    """
    Configura el sistema de logging con rotación de archivos y salida en consola.

    Args:
        store_id (int, optional): ID de la tienda para incluir en los logs.
    """
    # Crear directorio para logs si no existe
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Usar un solo archivo de log por día
    log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Configurar logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - StoreID:%(store_id)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            "%(name)s - StoreID:%(store_id)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        class ContextFilter(logging.Filter):
            def filter(self, record):
                record.store_id = store_id if store_id is not None else "N/A"
                return True
        
        logger.addFilter(ContextFilter())
    
    return logger