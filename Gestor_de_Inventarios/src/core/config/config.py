import json
import os
from typing import Dict, List, Any
import logging
from src.core.paths import BASE_DIR, CONFIG_FILE

logger = logging.getLogger(__name__)

# Constantes para rutas (relativas al BASE_DIR)
LOGS_DIR = "Logs"
DOCS_DIR = "Documentation"
BACKUPS_DIR = "Backups"
DB_NAME = "data/productos.db"  # Actualizado para incluir la carpeta data/
QR_DIR = "Mis codigos"
IMAGES_DIR = "ProductImages"
SALES_REPORTS_DIR = "SalesReports"
INVENTORY_REPORTS_DIR = "InventoryReports"
SYNC_REPORTS_DIR = "SyncReports"  # Nuevo directorio para reportes de sincronización

# Configuración predeterminada para la aplicación
default_config = {
    "TALLAS": [
        "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "16", "18", "20",
        "28", "30", "32", "34", "36", "38", "40", "42", "44", "46", "48",
        "XS", "S", "M", "L", "XL", "XXL", "XXXL", "XXXXL",
        "CH", "MD", "GD", "EXG", "Uni", "ESP", "NT",
        "0-0", "0-2", "3-5", "6-8", "9-12", "13-18", "CH-MD", "GD-EXG", "Dama"
    ],
    "COLORES": [
        "Rojo", "Azul", "Blanco", "Rosa", "Beige", "Amarillo", "Café", "Vino", "Gris",
        "Azul Marino", "Negro", "Verde", "Azul Rey", "Blanca", "Azul cielo",
        "Camuflaje", "Escoces", "Bicolor", "Raya roja", "Doble raya",
        "Gales rojo", "Gales verde", "Gales azul", "Gris claro", "Gris obscuro"
    ],
    "GENEROS": [
        "Mujer", "Hombre", "Unisex"
    ],
    "MARCAS": [
        "Claudia", "Leo", "Prowear", "Lobito"
    ],
    "ULTIMA_MARCA": "Lobito",
    "ULTIMO_COLOR": "Azul Rey",
    "NIVELES_EDUCATIVOS": [
        "Preescolar", "Primaria", "Secundaria", "Bachillerato", "Universidad"
    ],
    "TIPOS_PRENDA": [
        "Accesorio", "Básico", "Deportivo", "Escolta", "Interior", "Oficial"
    ],
    "TIPOS_PIEZA": [
        "Bata", "Boina", "Calceta", "Calcetín", "Camisa", "Chaleco", "Chamarra",
        "Corbata", "Corbatín", "Falda", "Filipina", "Guante", "Jumper", "Malla",
        "Mandil", "Moño", "Pantalón", "Pants Suelto", "Playera", "Saco", "Suéter",
        "Pants 2pz", "Pants 3pz", "Short"
    ],
    "ATRIBUTOS": [
        "4 tablas", "Algodón", "Chazarilla", "Corazón", "Cuello Redondo", "Cuello V",
        "Deportivo", "Electromecánica", "Escoces", "Escolar", "Gales", "Interior",
        "Laboratorio", "Liso", "Manga Corta", "Manga Larga", "Mezclilla", "Pique",
        "Plisada", "Polilana", "Polo", "Popelina", "Pretina", "Punto", "Resorte",
        "Tableado", "Tortuga", "Botones", "Infantil", "Escolta", "Vestir"
    ],
    "UBICACIONES": [
        "San Felipe", "Comunidad", "Sin Información"
    ],
    "ESCUDOS": [
        "Con Escudo", "Sin Escudo"
    ],
    "LOGS_DIR": LOGS_DIR,
    "DOCS_DIR": DOCS_DIR,
    "BACKUPS_DIR": BACKUPS_DIR,
    "DB_NAME": DB_NAME,
    "DB_PATH": os.path.join(BASE_DIR, DB_NAME),  # Actualizado para usar DB_NAME
    "QR_DIR": QR_DIR,
    "IMAGES_DIR": IMAGES_DIR,
    "SALES_REPORTS_DIR": SALES_REPORTS_DIR,
    "INVENTORY_REPORTS_DIR": INVENTORY_REPORTS_DIR,
    "SYNC_REPORTS_DIR": SYNC_REPORTS_DIR,
    "ROOT_FOLDER": BASE_DIR,
    "METODOS_PAGO": ["Efectivo", "Transferencia"],
    "TASA_IVA": 0.16,
    "VENTAS_CONFIG": {"aplicar_iva": True},
    "POS_TITLE": "POS - Boutique",
    "THEME_MODE": "light",
    "THEME_COLOR": "blue"
}

# Comentarios para incluir en config.json
CONFIG_COMMENTS = {
    "__COMENTARIOS__": {
        "TALLAS": "Lista de tallas disponibles para los productos (números, estándares como XS-XXL, y categorías especiales).",
        "COLORES": "Lista de colores disponibles para los productos.",
        "GENEROS": "Lista de géneros para los productos (Mujer, Hombre, Unisex).",
        "MARCAS": "Lista de marcas de los productos.",
        "ULTIMA_MARCA": "Última marca seleccionada por el usuario.",
        "ULTIMO_COLOR": "Último color seleccionado por el usuario.",
        "NIVELES_EDUCATIVOS": "Lista de niveles educativos asociados a los productos (por ejemplo, uniformes escolares).",
        "TIPOS_PRENDA": "Lista de tipos de prenda (categorías generales).",
        "TIPOS_PIEZA": "Lista de tipos específicos de piezas de ropa.",
        "ATRIBUTOS": "Lista de atributos o características de los productos.",
        "UBICACIONES": "Lista de ubicaciones (por ejemplo, sucursales o regiones).",
        "ESCUDOS": "Opciones para incluir o no un escudo en los productos.",
        "LOGS_DIR": "Directorio donde se guardan los logs de la aplicación.",
        "DOCS_DIR": "Directorio donde se guarda la documentación.",
        "BACKUPS_DIR": "Directorio donde se guardan las copias de seguridad.",
        "DB_NAME": "Nombre del archivo de la base de datos, incluyendo la carpeta data/.",
        "DB_PATH": "Ruta completa al archivo de la base de datos.",
        "QR_DIR": "Directorio donde se guardan los códigos QR generados.",
        "IMAGES_DIR": "Directorio donde se guardan las imágenes de los productos.",
        "SALES_REPORTS_DIR": "Directorio donde se guardan los reportes de ventas.",
        "INVENTORY_REPORTS_DIR": "Directorio donde se guardan los reportes de inventario.",
        "SYNC_REPORTS_DIR": "Directorio donde se guardan los reportes de sincronización con ELEventas.",
        "ROOT_FOLDER": "Carpeta raíz donde se almacenan todos los datos de la aplicación.",
        "METODOS_PAGO": "Métodos de pago aceptados (Efectivo, Transferencia).",
        "TASA_IVA": "Tasa de IVA aplicada a las ventas (por defecto 16%).",
        "VENTAS_CONFIG": "Configuración adicional para las ventas (por ejemplo, aplicar IVA).",
        "POS_TITLE": "Título de la ventana del POS.",
        "THEME_MODE": "Modo de tema para la interfaz gráfica (light/dark).",
        "THEME_COLOR": "Tema de color para la interfaz gráfica (por ejemplo, blue)."
    }
}

def clean_config(config: Dict, source: str) -> Dict:
    cleaned_config = config.copy()
    if "__COMENTARIOS__" in cleaned_config:
        del cleaned_config["__COMENTARIOS__"]
    for key in default_config:
        if key not in cleaned_config:
            cleaned_config[key] = default_config[key]
    for key in ["COLORES", "GENEROS", "MARCAS", "NIVELES_EDUCATIVOS", "TIPOS_PRENDA", "TIPOS_PIEZA", "ATRIBUTOS", "UBICACIONES", "ESCUDOS", "METODOS_PAGO"]:
        if key in cleaned_config:
            if isinstance(cleaned_config[key], dict):
                cleaned_config[key] = list(cleaned_config[key].keys())
            elif not isinstance(cleaned_config[key], list):
                logger.warning(f"Formato inválido para {key} en {source}. Usando valor predeterminado.")
                cleaned_config[key] = default_config[key]
    for key in ["LOGS_DIR", "DOCS_DIR", "BACKUPS_DIR", "DB_NAME", "DB_PATH", "QR_DIR", "IMAGES_DIR", "SALES_REPORTS_DIR", "INVENTORY_REPORTS_DIR", "SYNC_REPORTS_DIR"]:
        if key in cleaned_config and cleaned_config[key] != default_config[key]:
            logger.warning(f"Valor de {key} en {source} no coincide con el predeterminado. Usando valor predeterminado.")
            cleaned_config[key] = default_config[key]
    if "ROOT_FOLDER" in cleaned_config and cleaned_config["ROOT_FOLDER"] != BASE_DIR:
        logger.warning(f"Valor de ROOT_FOLDER en {source} no coincide con el predeterminado. Usando valor dinámico.")
        cleaned_config["ROOT_FOLDER"] = BASE_DIR
    for obsolete_key in ["TALLAS_CALZADO", "CATEGORIAS", "gestion_productos"]:
        if obsolete_key in cleaned_config:
            del cleaned_config[obsolete_key]
    return cleaned_config

def cargar_config(archivo: str = CONFIG_FILE) -> Dict:
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            loaded_config = json.load(f)
            logger.debug(f"Contenido de {archivo}: {loaded_config}")
            cleaned_config = clean_config(loaded_config, archivo)
            exportar_configuraciones(cleaned_config, archivo)
            return cleaned_config
    except FileNotFoundError:
        logger.warning(f"No se encontró el archivo {archivo}. Usando configuración predeterminada.")
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        exportar_configuraciones(default_config, archivo)
        return default_config.copy()
    except json.JSONDecodeError as e:
        logger.error(f"Formato inválido en {archivo}: {str(e)}. Usando configuración predeterminada.")
        return default_config.copy()
    except Exception as e:
        logger.error(f"Error al cargar {archivo}: {str(e)}. Usando configuración predeterminada.")
        return default_config.copy()

def guardar_datos_personalizados(categoria: str, predeterminados: List[str], config: Dict) -> None:
    try:
        if not isinstance(predeterminados, list) or not all(isinstance(item, str) for item in predeterminados):
            raise ValueError("predeterminados debe ser una lista de strings")
        if not isinstance(categoria, str):
            raise ValueError("categoria debe ser un string")
        for item in predeterminados:
            if len(item.strip()) < 2:
                raise ValueError(f"Los valores deben tener al menos 2 caracteres (encontrado: '{item}')")

        logger.debug(f"Guardando datos para categoría '{categoria}' con predeterminados: {predeterminados}")

        if categoria not in config:
            logger.warning(f"Categoría {categoria} no encontrada en CONFIG. Creándola vacía.")
            config[categoria] = []

        current_data = config.get(categoria, [])
        if not isinstance(current_data, list):
            logger.warning(f"Datos actuales de {categoria} no son una lista. Inicializando como vacía.")
            current_data = []

        new_data = [item for item in predeterminados if item not in current_data]
        final_data = current_data + new_data
        config[categoria] = final_data

        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            logger.debug(f"Datos a guardar en {CONFIG_FILE} para {categoria}: {config[categoria]}")
            json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f"Datos personalizados guardados en {CONFIG_FILE} para {categoria}")
    except IOError as e:
        logger.error(f"Error de I/O al guardar {CONFIG_FILE}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error al guardar {CONFIG_FILE}: {str(e)}")
        raise

def exportar_configuraciones(config: Dict, archivo: str) -> None:
    if not isinstance(config, dict):
        raise ValueError("config debe ser un diccionario")
    try:
        config_with_comments = CONFIG_COMMENTS.copy()
        config_with_comments.update(config)
        os.makedirs(os.path.dirname(archivo), exist_ok=True)
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(config_with_comments, f, ensure_ascii=False, indent=2)
            logger.info(f"Configuraciones exportadas a {archivo}")
    except IOError as e:
        logger.error(f"Error al exportar configuraciones a {archivo}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error inesperado al exportar configuraciones a {archivo}: {e}")
        raise

def importar_configuraciones(archivo: str) -> Dict:
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            nuevas_config = json.load(f)
            logger.info(f"Configuraciones leídas desde {archivo}: {nuevas_config}")
            return clean_config(nuevas_config, archivo)
    except FileNotFoundError:
        logger.error(f"Archivo {archivo} no encontrado")
        raise FileNotFoundError(f"No se encontró el archivo {archivo}")
    except json.JSONDecodeError as e:
        logger.error(f"Formato inválido en {archivo}: {str(e)}")
        raise ValueError(f"Formato inválido en {archivo}")
    except Exception as e:
        logger.error(f"Error al importar configuraciones desde {archivo}: {e}")
        raise

CONFIG = cargar_config()
logger.info("Configuraciones iniciales cargadas dinámicas")