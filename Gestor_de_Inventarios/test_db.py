from src.core.config.db_manager import DatabaseManager
import logging

# Configurar logging para ver los mensajes detallados
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Mostrar en consola
        logging.FileHandler('test_db.log')  # Guardar en archivo para referencia
    ]
)

logger = logging.getLogger(__name__)

def test_database():
    db = DatabaseManager()
    try:
        cursor = db.get_cursor()
        logger.info("Conexión a la base de datos establecida")

        # Verificar existencia de tablas
        tables = [
            'clientes', 'apartados', 'ventas', 'anticipos', 'reembolsos',
            'users', 'stores', 'modificaciones_apartados', 'productos'
        ]
        for table in tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if cursor.fetchone():
                logger.info(f"Tabla '{table}' existe")
            else:
                logger.error(f"Tabla '{table}' NO existe")

        # Probar métodos de DatabaseManager
        logger.info("Probando métodos de DatabaseManager...")
        
        # buscar_clientes
        clientes = db.buscar_clientes(query="", store_id=1, limit=5)
        logger.info(f"Clientes encontrados: {len(clientes)}")
        
        # buscar_apartados
        apartados = db.buscar_apartados(query="", estado="activo", store_id=1, limit=5)
        logger.info(f"Apartados encontrados: {len(apartados)}")
        
        # apartados_por_vencer
        apartados_venciendo = db.apartados_por_vencer(dias=2, store_id=1)
        logger.info(f"Apartados por vencer: {len(apartados_venciendo)}")
        
        # verificar_apartados_vencidos
        db.verificar_apartados_vencidos(store_id=1)
        logger.info("Verificación de apartados vencidos ejecutada")
        
        # buscar_productos
        productos = db.buscar_productos(query="test", store_id=1, limit=1)
        logger.info(f"Productos encontrados: {len(productos)}")
        
        # validar_stock
        stock_valido = db.validar_stock(sku="test_sku", cantidad=1, store_id=1)
        logger.info(f"Validación de stock: {stock_valido}")
        
        # buscar_apartados_por_cliente
        apartados_cliente = db.buscar_apartados_por_cliente(id_cliente=1, store_id=1)
        logger.info(f"Apartados por cliente: {len(apartados_cliente)}")
        
        # obtener_modificaciones
        modificaciones = db.obtener_modificaciones(apartado_id=1, store_id=1)
        logger.info(f"Modificaciones encontradas: {len(modificaciones)}")

    except Exception as e:
        logger.error(f"Error durante la prueba: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()
        logger.info("Conexión a la base de datos cerrada")

if __name__ == "__main__":
    test_database()