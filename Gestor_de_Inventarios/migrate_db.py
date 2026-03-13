import sqlite3
from datetime import datetime

db_path = "C:/Users/Daniel/Downloads/Gestor_de_Inventarios/data/productos.db"
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(productos)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'last_modified' not in columns:
        cursor.execute("ALTER TABLE productos ADD COLUMN last_modified TIMESTAMP")
        current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("UPDATE productos SET last_modified = ? WHERE last_modified IS NULL", (current_timestamp,))
        print(f"Migración completada: columna 'last_modified' añadida y actualizada con {current_timestamp}.")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_last_modified ON productos (last_modified)")
    print("Índice creado en last_modified.")
    
    conn.commit()
except sqlite3.Error as e:
    print(f"Error durante la migración: {e}")
finally:
    conn.close()