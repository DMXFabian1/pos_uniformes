import sqlite3
import os
import sys
import shutil
from datetime import datetime

DB_PATH = r"C:/Users/Daniel/Downloads/Gestor_de_Inventarios/data/productos.db"


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def abort(msg, conn=None):
    log(f"ERROR: {msg}")
    if conn:
        try:
            conn.rollback()
            log("Rollback aplicado — base de datos sin cambios")
        except Exception as e:
            log(f"Rollback falló: {e}")
        conn.close()
    sys.exit(1)


def main():
    db_path = DB_PATH

    if not os.path.exists(db_path):
        abort(
            f"No se encontró la base de datos en:\n  {db_path}\n"
            "  Verifica la ruta y vuelve a intentar."
        )

    bak_path = db_path.replace(".db", f"_bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    try:
        shutil.copy2(db_path, bak_path)
        log(f"Backup creado: {bak_path}")
    except Exception as e:
        abort(f"No se pudo crear el backup: {e}")

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(productos)")
        cols = [r[1] for r in cur.fetchall()]
        for col in ("sku", "precio", "nombre", "atributo", "tipo_pieza", "tipo_prenda"):
            if col not in cols:
                abort(f"Columna faltante en la tabla productos: '{col}'", conn)
        log("Estructura de tabla verificada")

        cur.execute("SELECT COUNT(*) FROM productos")
        log(f"Productos en DB: {cur.fetchone()[0]}")

        cur.execute("UPDATE productos SET atributo = 'Cuello Olan' WHERE atributo = 'Cuello olan'")
        log(f"  atributo normalizado: {cur.rowcount} filas")

        cur.execute("UPDATE productos SET nombre = REPLACE(nombre, 'Cuello olan', 'Cuello Olan') WHERE nombre LIKE '%Cuello olan%'")
        log(f"  nombre normalizado: {cur.rowcount} filas")

        cur.execute("UPDATE productos SET tipo_prenda = 'Accesorio' WHERE tipo_pieza = 'Boina' AND tipo_prenda != 'Accesorio'")
        log(f"  Boina normalizado: {cur.rowcount} filas")

        cur.execute("DELETE FROM productos WHERE sku IN ('12345', '67890')")
        log(f"  Registros de prueba eliminados: {cur.rowcount}")

        log("Aplicando actualizacion de precios...")
        updates = [
            ("SKU000001", 439.0),  # Bata Manga Larga Blanca Talla 12
            ("SKU000002", 439.0),  # Bata Manga Larga Blanca Talla 14
            ("SKU000003", 439.0),  # Bata Manga Larga Blanca Talla 16
            ("SKU000004", 439.0),  # Bata Manga Larga Blanca Talla 18
            ("SKU000005", 439.0),  # Bata Manga Larga Blanca Talla 20
            ("SKU000006", 439.0),  # Bata Manga Larga Blanca Talla 28
            ("SKU000007", 439.0),  # Bata Manga Larga Blanca Talla 32
            ("SKU000008", 439.0),  # Bata Manga Larga Blanca Talla 34
            ("SKU000009", 439.0),  # Bata Manga Larga Blanca Talla 36
            ("SKU000010", 439.0),  # Bata Manga Larga Blanca Talla 38
            ("SKU000011", 439.0),  # Bata Manga Larga Blanca Talla 40
            ("SKU000012", 439.0),  # Bata Manga Larga Blanca Talla 42
            ("SKU000013", 439.0),  # Bata Manga Larga Blanca Talla 44
            ("SKU000014", 439.0),  # Bata Manga Larga Blanca Talla 46
            ("SKU000015", 395.0),  # Bata Manga Corta Blanca Talla 12
            ("SKU000016", 395.0),  # Bata Manga Corta Blanca Talla 14
            ("SKU000017", 395.0),  # Bata Manga Corta Blanca Talla 16
            ("SKU000018", 395.0),  # Bata Manga Corta Blanca Talla 18
            ("SKU000019", 395.0),  # Bata Manga Corta Blanca Talla 20
            ("SKU000020", 395.0),  # Bata Manga Corta Blanca Talla 28
            ("SKU000021", 395.0),  # Bata Manga Corta Blanca Talla 32
            ("SKU000022", 395.0),  # Bata Manga Corta Blanca Talla 34
            ("SKU000023", 395.0),  # Bata Manga Corta Blanca Talla 36
            ("SKU000024", 395.0),  # Bata Manga Corta Blanca Talla 38
            ("SKU000025", 395.0),  # Bata Manga Corta Blanca Talla 40
            ("SKU000026", 395.0),  # Bata Manga Corta Blanca Talla 42
            ("SKU000027", 395.0),  # Bata Manga Corta Blanca Talla 44
            ("SKU000028", 395.0),  # Bata Manga Corta Blanca Talla 46
            ("SKU000029", 75.0),  # Playera Tortuga Blanca Talla 2
            ("SKU000030", 75.0),  # Playera Tortuga Blanca Talla 3
            ("SKU000031", 75.0),  # Playera Tortuga Blanca Talla 4
            ("SKU000032", 75.0),  # Playera Tortuga Blanca Talla 5
            ("SKU000033", 75.0),  # Playera Tortuga Blanca Talla 6
            ("SKU000034", 75.0),  # Playera Tortuga Blanca Talla 8
            ("SKU000035", 85.0),  # Playera Tortuga Blanca Talla 10
            ("SKU000036", 85.0),  # Playera Tortuga Blanca Talla 12
            ("SKU000037", 95.0),  # Playera Tortuga Blanca Talla 14
            ("SKU000038", 95.0),  # Playera Tortuga Blanca Talla 16
            ("SKU000039", 49.0),  # Calceta Escolar Rojo Talla 0-0
            ("SKU000040", 49.0),  # Calceta Escolar Beige Talla 0-0
            ("SKU000041", 49.0),  # Calceta Escolar Vino Talla 0-0
            ("SKU000042", 49.0),  # Calceta Escolar Azul Marino Talla 0-0
            ("SKU000043", 49.0),  # Calceta Escolar Negro Talla 0-0
            ("SKU000044", 49.0),  # Calceta Escolar Verde Talla 0-0
            ("SKU000045", 49.0),  # Calceta Escolar Blanca Talla 0-0
            ("SKU000046", 49.0),  # Calceta Escolar Rojo Talla 0-2
            ("SKU000047", 49.0),  # Calceta Escolar Beige Talla 0-2
            ("SKU000048", 49.0),  # Calceta Escolar Vino Talla 0-2
            ("SKU000049", 49.0),  # Calceta Escolar Azul Marino Talla 0-2
            ("SKU000050", 49.0),  # Calceta Escolar Negro Talla 0-2
            ("SKU000051", 49.0),  # Calceta Escolar Verde Talla 0-2
            ("SKU000052", 49.0),  # Calceta Escolar Blanca Talla 0-2
            ("SKU000053", 49.0),  # Calceta Escolar Rojo Talla 3-5
            ("SKU000054", 49.0),  # Calceta Escolar Beige Talla 3-5
            ("SKU000055", 49.0),  # Calceta Escolar Vino Talla 3-5
            ("SKU000056", 49.0),  # Calceta Escolar Azul Marino Talla 3-5
            ("SKU000057", 49.0),  # Calceta Escolar Negro Talla 3-5
            ("SKU000058", 49.0),  # Calceta Escolar Verde Talla 3-5
            ("SKU000059", 49.0),  # Calceta Escolar Blanca Talla 3-5
            ("SKU000060", 49.0),  # Calceta Escolar Rojo Talla 6-8
            ("SKU000061", 49.0),  # Calceta Escolar Beige Talla 6-8
            ("SKU000062", 49.0),  # Calceta Escolar Vino Talla 6-8
            ("SKU000063", 49.0),  # Calceta Escolar Azul Marino Talla 6-8
            ("SKU000064", 49.0),  # Calceta Escolar Negro Talla 6-8
            ("SKU000065", 49.0),  # Calceta Escolar Verde Talla 6-8
            ("SKU000066", 49.0),  # Calceta Escolar Blanca Talla 6-8
            ("SKU000067", 49.0),  # Calceta Escolar Rojo Talla 9-12
            ("SKU000068", 49.0),  # Calceta Escolar Beige Talla 9-12
            ("SKU000069", 49.0),  # Calceta Escolar Vino Talla 9-12
            ("SKU000070", 49.0),  # Calceta Escolar Azul Marino Talla 9-12
            ("SKU000071", 49.0),  # Calceta Escolar Negro Talla 9-12
            ("SKU000072", 49.0),  # Calceta Escolar Verde Talla 9-12
            ("SKU000073", 49.0),  # Calceta Escolar Blanca Talla 9-12
            ("SKU000074", 49.0),  # Calceta Escolar Rojo Talla 13-18
            ("SKU000075", 49.0),  # Calceta Escolar Beige Talla 13-18
            ("SKU000076", 49.0),  # Calceta Escolar Vino Talla 13-18
            ("SKU000077", 49.0),  # Calceta Escolar Azul Marino Talla 13-18
            ("SKU000078", 49.0),  # Calceta Escolar Negro Talla 13-18
            ("SKU000079", 49.0),  # Calceta Escolar Verde Talla 13-18
            ("SKU000080", 49.0),  # Calceta Escolar Blanca Talla 13-18
            ("SKU000081", 109.0),  # Malla Escolar Rojo Talla 0-0
            ("SKU000082", 109.0),  # Malla Escolar Beige Talla 0-0
            ("SKU000083", 109.0),  # Malla Escolar Vino Talla 0-0
            ("SKU000084", 109.0),  # Malla Escolar Azul Marino Talla 0-0
            ("SKU000085", 109.0),  # Malla Escolar Negro Talla 0-0
            ("SKU000086", 109.0),  # Malla Escolar Verde Talla 0-0
            ("SKU000087", 109.0),  # Malla Escolar Blanca Talla 0-0
            ("SKU000088", 109.0),  # Malla Escolar Rojo Talla 0-2
            ("SKU000089", 109.0),  # Malla Escolar Beige Talla 0-2
            ("SKU000090", 109.0),  # Malla Escolar Vino Talla 0-2
            ("SKU000091", 109.0),  # Malla Escolar Azul Marino Talla 0-2
            ("SKU000092", 109.0),  # Malla Escolar Negro Talla 0-2
            ("SKU000093", 109.0),  # Malla Escolar Verde Talla 0-2
            ("SKU000094", 109.0),  # Malla Escolar Blanca Talla 0-2
            ("SKU000095", 109.0),  # Malla Escolar Rojo Talla 3-5
            ("SKU000096", 109.0),  # Malla Escolar Beige Talla 3-5
            ("SKU000097", 109.0),  # Malla Escolar Vino Talla 3-5
            ("SKU000098", 109.0),  # Malla Escolar Azul Marino Talla 3-5
            ("SKU000099", 109.0),  # Malla Escolar Negro Talla 3-5
            ("SKU000100", 109.0),  # Malla Escolar Verde Talla 3-5
            ("SKU000101", 109.0),  # Malla Escolar Blanca Talla 3-5
            ("SKU000102", 109.0),  # Malla Escolar Rojo Talla 6-8
            ("SKU000103", 109.0),  # Malla Escolar Beige Talla 6-8
            ("SKU000104", 109.0),  # Malla Escolar Vino Talla 6-8
            ("SKU000105", 109.0),  # Malla Escolar Azul Marino Talla 6-8
            ("SKU000106", 109.0),  # Malla Escolar Negro Talla 6-8
            ("SKU000107", 109.0),  # Malla Escolar Verde Talla 6-8
            ("SKU000108", 109.0),  # Malla Escolar Blanca Talla 6-8
            ("SKU000109", 129.0),  # Malla Escolar Rojo Talla 9-12
            ("SKU000110", 129.0),  # Malla Escolar Beige Talla 9-12
            ("SKU000111", 129.0),  # Malla Escolar Vino Talla 9-12
            ("SKU000112", 129.0),  # Malla Escolar Azul Marino Talla 9-12
            ("SKU000113", 129.0),  # Malla Escolar Negro Talla 9-12
            ("SKU000114", 129.0),  # Malla Escolar Verde Talla 9-12
            ("SKU000115", 129.0),  # Malla Escolar Blanca Talla 9-12
            ("SKU000116", 139.0),  # Malla Escolar Rojo Talla 13-18
            ("SKU000117", 139.0),  # Malla Escolar Beige Talla 13-18
            ("SKU000118", 139.0),  # Malla Escolar Vino Talla 13-18
            ("SKU000119", 139.0),  # Malla Escolar Azul Marino Talla 13-18
            ("SKU000120", 139.0),  # Malla Escolar Negro Talla 13-18
            ("SKU000121", 139.0),  # Malla Escolar Verde Talla 13-18
            ("SKU000122", 139.0),  # Malla Escolar Blanca Talla 13-18
            ("SKU000123", 139.0),  # Malla Escolar Rojo Talla CH-MD
            ("SKU000124", 139.0),  # Malla Escolar Beige Talla CH-MD
            ("SKU000125", 139.0),  # Malla Escolar Vino Talla CH-MD
            ("SKU000126", 139.0),  # Malla Escolar Azul Marino Talla CH-MD
            ("SKU000127", 139.0),  # Malla Escolar Negro Talla CH-MD
            ("SKU000128", 139.0),  # Malla Escolar Verde Talla CH-MD
            ("SKU000129", 139.0),  # Malla Escolar Blanca Talla CH-MD
            ("SKU000130", 139.0),  # Malla Escolar Rojo Talla GD-EXG
            ("SKU000131", 139.0),  # Malla Escolar Beige Talla GD-EXG
            ("SKU000132", 139.0),  # Malla Escolar Vino Talla GD-EXG
            ("SKU000133", 139.0),  # Malla Escolar Azul Marino Talla GD-EXG
            ("SKU000134", 139.0),  # Malla Escolar Negro Talla GD-EXG
            ("SKU000135", 139.0),  # Malla Escolar Verde Talla GD-EXG
            ("SKU000136", 139.0),  # Malla Escolar Blanca Talla GD-EXG
            ("SKU000137", 139.0),  # Malla Escolar Rojo Talla Dama
            ("SKU000138", 139.0),  # Malla Escolar Beige Talla Dama
            ("SKU000139", 139.0),  # Malla Escolar Vino Talla Dama
            ("SKU000140", 139.0),  # Malla Escolar Azul Marino Talla Dama
            ("SKU000141", 139.0),  # Malla Escolar Negro Talla Dama
            ("SKU000142", 139.0),  # Malla Escolar Verde Talla Dama
            ("SKU000143", 139.0),  # Malla Escolar Blanca Talla Dama
            ("SKU000144", 70.0),  # Corbata Rojo Talla Uni
            ("SKU000145", 70.0),  # Corbata Rosa Talla Uni
            ("SKU000146", 70.0),  # Corbata Beige Talla Uni
            ("SKU000147", 70.0),  # Corbata Vino Talla Uni
            ("SKU000148", 70.0),  # Corbata Gris Talla Uni
            ("SKU000149", 70.0),  # Corbata Azul Marino Talla Uni
            ("SKU000150", 70.0),  # Corbata Negro Talla Uni
            ("SKU000151", 70.0),  # Corbata Verde Talla Uni
            ("SKU000152", 70.0),  # Corbata Azul Rey Talla Uni
            ("SKU000153", 70.0),  # Corbata Blanca Talla Uni
            ("SKU000154", 70.0),  # Corbatín Rojo Talla Uni
            ("SKU000155", 70.0),  # Corbatín Rosa Talla Uni
            ("SKU000156", 70.0),  # Corbatín Beige Talla Uni
            ("SKU000157", 70.0),  # Corbatín Vino Talla Uni
            ("SKU000158", 70.0),  # Corbatín Gris Talla Uni
            ("SKU000159", 70.0),  # Corbatín Azul Marino Talla Uni
            ("SKU000160", 70.0),  # Corbatín Negro Talla Uni
            ("SKU000161", 70.0),  # Corbatín Verde Talla Uni
            ("SKU000162", 70.0),  # Corbatín Azul Rey Talla Uni
            ("SKU000163", 70.0),  # Corbatín Blanca Talla Uni
            ("SKU000164", 70.0),  # Corbatín Azul cielo Talla Uni
            ("SKU000165", 70.0),  # Moño Rojo Talla Uni
            ("SKU000166", 70.0),  # Moño Blanco Talla Uni
            ("SKU000167", 70.0),  # Moño Rosa Talla Uni
            ("SKU000168", 70.0),  # Moño Beige Talla Uni
            ("SKU000169", 70.0),  # Moño Vino Talla Uni
            ("SKU000170", 70.0),  # Moño Gris Talla Uni
            ("SKU000171", 70.0),  # Moño Azul Marino Talla Uni
            ("SKU000172", 70.0),  # Moño Negro Talla Uni
            ("SKU000173", 70.0),  # Moño Verde Talla Uni
            ("SKU000174", 70.0),  # Moño Azul Rey Talla Uni
            ("SKU000175", 70.0),  # Moño Blanca Talla Uni
            ("SKU000176", 70.0),  # Moño Azul cielo Talla Uni
            ("SKU000177", 65.0),  # Bata Infantil Rojo Talla Uni
            ("SKU000178", 65.0),  # Bata Infantil Rosa Talla Uni
            ("SKU000179", 65.0),  # Bata Infantil Amarillo Talla Uni
            ("SKU000180", 65.0),  # Bata Infantil Vino Talla Uni
            ("SKU000181", 65.0),  # Bata Infantil Azul Marino Talla Uni
            ("SKU000182", 65.0),  # Bata Infantil Verde Talla Uni
            ("SKU000183", 65.0),  # Bata Infantil Blanca Talla Uni
            ("SKU000184", 65.0),  # Bata Infantil Azul cielo Talla Uni
            ("SKU000185", 80.0),  # Boina Escolta Rojo Talla Uni
            ("SKU000186", 80.0),  # Boina Escolta Blanco Talla Uni
            ("SKU000187", 80.0),  # Boina Escolta Rosa Talla Uni
            ("SKU000188", 80.0),  # Boina Escolta Beige Talla Uni
            ("SKU000189", 80.0),  # Boina Escolta Café Talla Uni
            ("SKU000190", 80.0),  # Boina Escolta Vino Talla Uni
            ("SKU000191", 80.0),  # Boina Escolta Gris Talla Uni
            ("SKU000192", 80.0),  # Boina Escolta Azul Marino Talla Uni
            ("SKU000193", 80.0),  # Boina Escolta Negro Talla Uni
            ("SKU000194", 80.0),  # Boina Escolta Verde Talla Uni
            ("SKU000195", 80.0),  # Boina Escolta Azul Rey Talla Uni
            ("SKU000196", 80.0),  # Boina Escolta Blanca Talla Uni
            ("SKU000197", 80.0),  # Boina Escolta Azul cielo Talla Uni
            ("SKU000198", 80.0),  # Boina Escolta Camuflaje Talla Uni
            ("SKU000199", 49.0),  # Guante Escolta Blanco Talla 2
            ("SKU000200", 49.0),  # Guante Escolta Blanco Talla 3
            ("SKU000201", 49.0),  # Guante Escolta Blanco Talla 4
            ("SKU000202", 49.0),  # Guante Escolta Blanco Talla 5
            ("SKU000203", 49.0),  # Guante Escolta Blanco Talla 6
            ("SKU000204", 49.0),  # Guante Escolta Blanco Talla 7
            ("SKU000205", 49.0),  # Guante Escolta Blanco Talla 8
            ("SKU000206", 49.0),  # Guante Escolta Blanco Talla 9
            ("SKU000207", 49.0),  # Guante Escolta Blanco Talla 10
            ("SKU000208", 49.0),  # Guante Escolta Blanco Talla 11
            ("SKU000209", 49.0),  # Guante Escolta Blanco Talla 12
            ("SKU000210", 49.0),  # Guante Escolta Blanco Talla 13
            ("SKU000211", 49.0),  # Guante Escolta Blanco Talla 14
            ("SKU000212", 75.0),  # Playera Tortuga Blanca Talla 2
            ("SKU000213", 75.0),  # Playera Tortuga Blanca Talla 3
            ("SKU000214", 75.0),  # Playera Tortuga Blanca Talla 4
            ("SKU000215", 75.0),  # Playera Tortuga Blanca Talla 5
            ("SKU000216", 75.0),  # Playera Tortuga Blanca Talla 6
            ("SKU000217", 75.0),  # Playera Tortuga Blanca Talla 7
            ("SKU000218", 75.0),  # Playera Tortuga Blanca Talla 8
            ("SKU000219", 75.0),  # Playera Tortuga Blanca Talla 9
            ("SKU000220", 75.0),  # Playera Tortuga Blanca Talla 10
            ("SKU000221", 75.0),  # Playera Tortuga Blanca Talla 11
            ("SKU000222", 75.0),  # Playera Tortuga Blanca Talla 12
            ("SKU000223", 75.0),  # Playera Tortuga Blanca Talla 13
            ("SKU000224", 75.0),  # Playera Tortuga Blanca Talla 14
            ("SKU000225", 75.0),  # Playera Tortuga Blanca Talla 16
            ("SKU000226", 89.0),  # Camisa Manga Corta Blanca Talla 4
            ("SKU000227", 89.0),  # Camisa Manga Corta Blanca Talla 6
            ("SKU000228", 89.0),  # Camisa Manga Corta Blanca Talla 8
            ("SKU000229", 99.0),  # Camisa Manga Corta Blanca Talla 10
            ("SKU000230", 99.0),  # Camisa Manga Corta Blanca Talla 12
            ("SKU000231", 99.0),  # Camisa Manga Corta Blanca Talla 14
            ("SKU000232", 99.0),  # Camisa Manga Corta Blanca Talla 16
            ("SKU000233", 115.0),  # Camisa Manga Corta Blanca Talla 28
            ("SKU000234", 135.0),  # Camisa Manga Corta Blanca Talla 32
            ("SKU000235", 135.0),  # Camisa Manga Corta Blanca Talla 34
            ("SKU000236", 145.0),  # Camisa Manga Corta Blanca Talla 36
            ("SKU000237", 145.0),  # Camisa Manga Corta Blanca Talla 38
            ("SKU000238", 165.0),  # Camisa Manga Corta Blanca Talla 40
            ("SKU000239", 165.0),  # Camisa Manga Corta Blanca Talla 42
            ("SKU000240", 115.0),  # Camisa Manga Corta Blanca Talla 30
            ("SKU000241", 125.0),  # Camisa Prowear Manga Corta Blanca Talla 4
            ("SKU000242", 125.0),  # Camisa Prowear Manga Corta Blanca Talla 6
            ("SKU000243", 125.0),  # Camisa Prowear Manga Corta Blanca Talla 8
            ("SKU000244", 145.0),  # Camisa Prowear Manga Corta Blanca Talla 10
            ("SKU000245", 145.0),  # Camisa Prowear Manga Corta Blanca Talla 12
            ("SKU000246", 155.0),  # Camisa Prowear Manga Corta Blanca Talla 14
            ("SKU000247", 155.0),  # Camisa Prowear Manga Corta Blanca Talla 16
            ("SKU000248", 165.0),  # Camisa Prowear Manga Corta Blanca Talla 28
            ("SKU000249", 165.0),  # Camisa Prowear Manga Corta Blanca Talla 32
            ("SKU000250", 165.0),  # Camisa Prowear Manga Corta Blanca Talla 34
            ("SKU000251", 165.0),  # Camisa Prowear Manga Corta Blanca Talla 36
            ("SKU000252", 165.0),  # Camisa Prowear Manga Corta Blanca Talla 38
            ("SKU000253", 185.0),  # Camisa Prowear Manga Corta Blanca Talla 40
            ("SKU000254", 185.0),  # Camisa Prowear Manga Corta Blanca Talla 42
            ("SKU000255", 165.0),  # Camisa Prowear Manga Corta Blanca Talla 30
            ("SKU000336", 195.0),  # Falda Cuatro tablas Café Talla 2
            ("SKU000338", 195.0),  # Falda Cuatro tablas Verde Talla 2
            ("SKU000339", 195.0),  # Falda Cuatro tablas Azul Rey Talla 2
            ("SKU000340", 195.0),  # Falda Cuatro tablas Blanca Talla 2
            ("SKU000341", 195.0),  # Falda Cuatro tablas Café Talla 4
            ("SKU000343", 195.0),  # Falda Cuatro tablas Verde Talla 4
            ("SKU000344", 195.0),  # Falda Cuatro tablas Azul Rey Talla 4
            ("SKU000345", 195.0),  # Falda Cuatro tablas Blanca Talla 4
            ("SKU000346", 195.0),  # Falda Cuatro tablas Café Talla 6
            ("SKU000348", 195.0),  # Falda Cuatro tablas Verde Talla 6
            ("SKU000349", 195.0),  # Falda Cuatro tablas Azul Rey Talla 6
            ("SKU000350", 195.0),  # Falda Cuatro tablas Blanca Talla 6
            ("SKU000351", 195.0),  # Falda Cuatro tablas Café Talla 8
            ("SKU000353", 195.0),  # Falda Cuatro tablas Verde Talla 8
            ("SKU000354", 195.0),  # Falda Cuatro tablas Azul Rey Talla 8
            ("SKU000355", 195.0),  # Falda Cuatro tablas Blanca Talla 8
            ("SKU000356", 195.0),  # Falda Cuatro tablas Café Talla 10
            ("SKU000358", 195.0),  # Falda Cuatro tablas Verde Talla 10
            ("SKU000359", 195.0),  # Falda Cuatro tablas Azul Rey Talla 10
            ("SKU000360", 195.0),  # Falda Cuatro tablas Blanca Talla 10
            ("SKU000361", 195.0),  # Falda Cuatro tablas Café Talla 12
            ("SKU000363", 195.0),  # Falda Cuatro tablas Verde Talla 12
            ("SKU000364", 195.0),  # Falda Cuatro tablas Azul Rey Talla 12
            ("SKU000365", 195.0),  # Falda Cuatro tablas Blanca Talla 12
            ("SKU000366", 195.0),  # Falda Cuatro tablas Café Talla 14
            ("SKU000368", 195.0),  # Falda Cuatro tablas Verde Talla 14
            ("SKU000369", 195.0),  # Falda Cuatro tablas Azul Rey Talla 14
            ("SKU000370", 195.0),  # Falda Cuatro tablas Blanca Talla 14
            ("SKU000371", 195.0),  # Falda Cuatro tablas Café Talla 16
            ("SKU000373", 195.0),  # Falda Cuatro tablas Verde Talla 16
            ("SKU000374", 195.0),  # Falda Cuatro tablas Azul Rey Talla 16
            ("SKU000375", 195.0),  # Falda Cuatro tablas Blanca Talla 16
            ("SKU000376", 215.0),  # Falda Cuatro tablas Café Talla 28
            ("SKU000378", 215.0),  # Falda Cuatro tablas Verde Talla 28
            ("SKU000379", 215.0),  # Falda Cuatro tablas Azul Rey Talla 28
            ("SKU000380", 215.0),  # Falda Cuatro tablas Blanca Talla 28
            ("SKU000381", 215.0),  # Falda Cuatro tablas Café Talla 32
            ("SKU000383", 215.0),  # Falda Cuatro tablas Verde Talla 32
            ("SKU000384", 215.0),  # Falda Cuatro tablas Azul Rey Talla 32
            ("SKU000385", 215.0),  # Falda Cuatro tablas Blanca Talla 32
            ("SKU000386", 215.0),  # Falda Cuatro tablas Café Talla 34
            ("SKU000388", 215.0),  # Falda Cuatro tablas Verde Talla 34
            ("SKU000389", 215.0),  # Falda Cuatro tablas Azul Rey Talla 34
            ("SKU000390", 215.0),  # Falda Cuatro tablas Blanca Talla 34
            ("SKU000391", 225.0),  # Falda Cuatro tablas Café Talla 36
            ("SKU000393", 225.0),  # Falda Cuatro tablas Verde Talla 36
            ("SKU000394", 225.0),  # Falda Cuatro tablas Azul Rey Talla 36
            ("SKU000395", 225.0),  # Falda Cuatro tablas Blanca Talla 36
            ("SKU000396", 225.0),  # Falda Cuatro tablas Café Talla 38
            ("SKU000398", 225.0),  # Falda Cuatro tablas Verde Talla 38
            ("SKU000399", 225.0),  # Falda Cuatro tablas Azul Rey Talla 38
            ("SKU000400", 225.0),  # Falda Cuatro tablas Blanca Talla 38
            ("SKU000401", 235.0),  # Falda Cuatro tablas Café Talla 40
            ("SKU000403", 235.0),  # Falda Cuatro tablas Verde Talla 40
            ("SKU000404", 235.0),  # Falda Cuatro tablas Azul Rey Talla 40
            ("SKU000405", 235.0),  # Falda Cuatro tablas Blanca Talla 40
            ("SKU000406", 235.0),  # Falda Cuatro tablas Café Talla 42
            ("SKU000408", 235.0),  # Falda Cuatro tablas Verde Talla 42
            ("SKU000409", 235.0),  # Falda Cuatro tablas Azul Rey Talla 42
            ("SKU000410", 235.0),  # Falda Cuatro tablas Blanca Talla 42
            ("SKU000411", 215.0),  # Falda Cuatro tablas Café Talla 30
            ("SKU000413", 215.0),  # Falda Cuatro tablas Verde Talla 30
            ("SKU000414", 215.0),  # Falda Cuatro tablas Azul Rey Talla 30
            ("SKU000415", 215.0),  # Falda Cuatro tablas Blanca Talla 30
            ("SKU000416", 205.0),  # Falda Escoces Talla 2
            ("SKU000417", 205.0),  # Falda Escoces Talla 4
            ("SKU000418", 205.0),  # Falda Escoces Talla 6
            ("SKU000419", 205.0),  # Falda Escoces Talla 8
            ("SKU000420", 215.0),  # Falda Escoces Talla 10
            ("SKU000421", 215.0),  # Falda Escoces Talla 12
            ("SKU000422", 215.0),  # Falda Escoces Talla 14
            ("SKU000423", 215.0),  # Falda Escoces Talla 16
            ("SKU000424", 245.0),  # Falda Escoces Talla 28
            ("SKU000425", 245.0),  # Falda Escoces Talla 32
            ("SKU000426", 245.0),  # Falda Escoces Talla 34
            ("SKU000427", 255.0),  # Falda Escoces Talla 36
            ("SKU000428", 255.0),  # Falda Escoces Talla 38
            ("SKU000429", 265.0),  # Falda Escoces Talla 40
            ("SKU000430", 265.0),  # Falda Escoces Talla 42
            ("SKU000431", 245.0),  # Falda Escoces Talla 30
            ("SKU000432", 249.0),  # Jumper Beige Talla 2
            ("SKU000433", 249.0),  # Jumper Azul Marino Talla 2
            ("SKU000434", 249.0),  # Jumper Escoces Talla 2
            ("SKU000435", 249.0),  # Jumper Beige Talla 4
            ("SKU000436", 249.0),  # Jumper Azul Marino Talla 4
            ("SKU000437", 249.0),  # Jumper Escoces Talla 4
            ("SKU000438", 249.0),  # Jumper Beige Talla 6
            ("SKU000439", 249.0),  # Jumper Azul Marino Talla 6
            ("SKU000440", 249.0),  # Jumper Escoces Talla 6
            ("SKU000441", 249.0),  # Jumper Beige Talla 8
            ("SKU000442", 249.0),  # Jumper Azul Marino Talla 8
            ("SKU000443", 249.0),  # Jumper Escoces Talla 8
            ("SKU000444", 269.0),  # Jumper Beige Talla 10
            ("SKU000445", 269.0),  # Jumper Azul Marino Talla 10
            ("SKU000446", 269.0),  # Jumper Escoces Talla 10
            ("SKU000447", 269.0),  # Jumper Beige Talla 12
            ("SKU000448", 269.0),  # Jumper Azul Marino Talla 12
            ("SKU000449", 269.0),  # Jumper Escoces Talla 12
            ("SKU000450", 269.0),  # Jumper Beige Talla 14
            ("SKU000451", 269.0),  # Jumper Azul Marino Talla 14
            ("SKU000452", 269.0),  # Jumper Escoces Talla 14
            ("SKU000453", 269.0),  # Jumper Beige Talla 16
            ("SKU000454", 269.0),  # Jumper Azul Marino Talla 16
            ("SKU000455", 269.0),  # Jumper Escoces Talla 16
            ("SKU000456", 289.0),  # Jumper Beige Talla 28
            ("SKU000457", 289.0),  # Jumper Azul Marino Talla 28
            ("SKU000458", 289.0),  # Jumper Escoces Talla 28
            ("SKU000459", 309.0),  # Jumper Beige Talla 32
            ("SKU000460", 309.0),  # Jumper Azul Marino Talla 32
            ("SKU000461", 309.0),  # Jumper Escoces Talla 32
            ("SKU000462", 309.0),  # Jumper Beige Talla 34
            ("SKU000463", 309.0),  # Jumper Azul Marino Talla 34
            ("SKU000464", 309.0),  # Jumper Escoces Talla 34
            ("SKU000465", 319.0),  # Jumper Beige Talla 36
            ("SKU000466", 319.0),  # Jumper Azul Marino Talla 36
            ("SKU000467", 319.0),  # Jumper Escoces Talla 36
            ("SKU000468", 319.0),  # Jumper Beige Talla 38
            ("SKU000469", 319.0),  # Jumper Azul Marino Talla 38
            ("SKU000470", 319.0),  # Jumper Escoces Talla 38
            ("SKU000471", 329.0),  # Jumper Beige Talla 40
            ("SKU000472", 329.0),  # Jumper Azul Marino Talla 40
            ("SKU000473", 329.0),  # Jumper Escoces Talla 40
            ("SKU000474", 329.0),  # Jumper Beige Talla 42
            ("SKU000475", 329.0),  # Jumper Azul Marino Talla 42
            ("SKU000476", 329.0),  # Jumper Escoces Talla 42
            ("SKU000477", 289.0),  # Jumper Beige Talla 30
            ("SKU000478", 289.0),  # Jumper Azul Marino Talla 30
            ("SKU000479", 289.0),  # Jumper Escoces Talla 30
            ("SKU000480", 475.0),  # Pants 2pz Punto Rojo Talla 2
            ("SKU000481", 475.0),  # Pants 2pz Punto Vino Talla 2
            ("SKU000482", 475.0),  # Pants 2pz Punto Gris Talla 2
            ("SKU000483", 475.0),  # Pants 2pz Punto Azul Marino Talla 2
            ("SKU000484", 475.0),  # Pants 2pz Punto Verde Talla 2
            ("SKU000485", 475.0),  # Pants 2pz Punto Azul Rey Talla 2
            ("SKU000486", 475.0),  # Pants 2pz Punto Bicolor Talla 2
            ("SKU000487", 475.0),  # Pants 2pz Punto Raya roja Talla 2
            ("SKU000488", 475.0),  # Pants 2pz Punto Doble raya Talla 2
            ("SKU000489", 475.0),  # Pants 2pz Punto Rojo Talla 4
            ("SKU000490", 475.0),  # Pants 2pz Punto Vino Talla 4
            ("SKU000491", 475.0),  # Pants 2pz Punto Gris Talla 4
            ("SKU000492", 475.0),  # Pants 2pz Punto Azul Marino Talla 4
            ("SKU000493", 475.0),  # Pants 2pz Punto Verde Talla 4
            ("SKU000494", 475.0),  # Pants 2pz Punto Azul Rey Talla 4
            ("SKU000495", 475.0),  # Pants 2pz Punto Bicolor Talla 4
            ("SKU000496", 475.0),  # Pants 2pz Punto Raya roja Talla 4
            ("SKU000497", 475.0),  # Pants 2pz Punto Doble raya Talla 4
            ("SKU000498", 475.0),  # Pants 2pz Punto Rojo Talla 6
            ("SKU000499", 475.0),  # Pants 2pz Punto Vino Talla 6
            ("SKU000500", 475.0),  # Pants 2pz Punto Gris Talla 6
            ("SKU000501", 475.0),  # Pants 2pz Punto Azul Marino Talla 6
            ("SKU000502", 475.0),  # Pants 2pz Punto Verde Talla 6
            ("SKU000503", 475.0),  # Pants 2pz Punto Azul Rey Talla 6
            ("SKU000504", 475.0),  # Pants 2pz Punto Bicolor Talla 6
            ("SKU000505", 475.0),  # Pants 2pz Punto Raya roja Talla 6
            ("SKU000506", 475.0),  # Pants 2pz Punto Doble raya Talla 6
            ("SKU000507", 475.0),  # Pants 2pz Punto Rojo Talla 8
            ("SKU000508", 475.0),  # Pants 2pz Punto Vino Talla 8
            ("SKU000509", 475.0),  # Pants 2pz Punto Gris Talla 8
            ("SKU000510", 475.0),  # Pants 2pz Punto Azul Marino Talla 8
            ("SKU000511", 475.0),  # Pants 2pz Punto Verde Talla 8
            ("SKU000512", 475.0),  # Pants 2pz Punto Azul Rey Talla 8
            ("SKU000513", 475.0),  # Pants 2pz Punto Bicolor Talla 8
            ("SKU000514", 475.0),  # Pants 2pz Punto Raya roja Talla 8
            ("SKU000515", 475.0),  # Pants 2pz Punto Doble raya Talla 8
            ("SKU000516", 495.0),  # Pants 2pz Punto Rojo Talla 10
            ("SKU000517", 495.0),  # Pants 2pz Punto Vino Talla 10
            ("SKU000518", 495.0),  # Pants 2pz Punto Gris Talla 10
            ("SKU000519", 495.0),  # Pants 2pz Punto Azul Marino Talla 10
            ("SKU000520", 495.0),  # Pants 2pz Punto Verde Talla 10
            ("SKU000521", 495.0),  # Pants 2pz Punto Azul Rey Talla 10
            ("SKU000522", 495.0),  # Pants 2pz Punto Bicolor Talla 10
            ("SKU000523", 495.0),  # Pants 2pz Punto Raya roja Talla 10
            ("SKU000524", 495.0),  # Pants 2pz Punto Doble raya Talla 10
            ("SKU000525", 495.0),  # Pants 2pz Punto Rojo Talla 12
            ("SKU000526", 495.0),  # Pants 2pz Punto Vino Talla 12
            ("SKU000527", 495.0),  # Pants 2pz Punto Gris Talla 12
            ("SKU000528", 495.0),  # Pants 2pz Punto Azul Marino Talla 12
            ("SKU000529", 495.0),  # Pants 2pz Punto Verde Talla 12
            ("SKU000530", 495.0),  # Pants 2pz Punto Azul Rey Talla 12
            ("SKU000531", 495.0),  # Pants 2pz Punto Bicolor Talla 12
            ("SKU000532", 495.0),  # Pants 2pz Punto Raya roja Talla 12
            ("SKU000533", 495.0),  # Pants 2pz Punto Doble raya Talla 12
            ("SKU000534", 495.0),  # Pants 2pz Punto Rojo Talla 14
            ("SKU000535", 495.0),  # Pants 2pz Punto Vino Talla 14
            ("SKU000536", 495.0),  # Pants 2pz Punto Gris Talla 14
            ("SKU000537", 495.0),  # Pants 2pz Punto Azul Marino Talla 14
            ("SKU000538", 495.0),  # Pants 2pz Punto Verde Talla 14
            ("SKU000539", 495.0),  # Pants 2pz Punto Azul Rey Talla 14
            ("SKU000540", 495.0),  # Pants 2pz Punto Bicolor Talla 14
            ("SKU000541", 495.0),  # Pants 2pz Punto Raya roja Talla 14
            ("SKU000542", 495.0),  # Pants 2pz Punto Doble raya Talla 14
            ("SKU000543", 495.0),  # Pants 2pz Punto Rojo Talla 16
            ("SKU000544", 495.0),  # Pants 2pz Punto Vino Talla 16
            ("SKU000545", 495.0),  # Pants 2pz Punto Gris Talla 16
            ("SKU000546", 495.0),  # Pants 2pz Punto Azul Marino Talla 16
            ("SKU000547", 495.0),  # Pants 2pz Punto Verde Talla 16
            ("SKU000548", 495.0),  # Pants 2pz Punto Azul Rey Talla 16
            ("SKU000549", 495.0),  # Pants 2pz Punto Bicolor Talla 16
            ("SKU000550", 495.0),  # Pants 2pz Punto Raya roja Talla 16
            ("SKU000551", 495.0),  # Pants 2pz Punto Doble raya Talla 16
            ("SKU000552", 525.0),  # Pants 2pz Punto Rojo Talla 28
            ("SKU000553", 525.0),  # Pants 2pz Punto Vino Talla 28
            ("SKU000554", 525.0),  # Pants 2pz Punto Gris Talla 28
            ("SKU000555", 525.0),  # Pants 2pz Punto Azul Marino Talla 28
            ("SKU000556", 525.0),  # Pants 2pz Punto Verde Talla 28
            ("SKU000557", 525.0),  # Pants 2pz Punto Azul Rey Talla 28
            ("SKU000558", 525.0),  # Pants 2pz Punto Bicolor Talla 28
            ("SKU000559", 525.0),  # Pants 2pz Punto Raya roja Talla 28
            ("SKU000560", 525.0),  # Pants 2pz Punto Doble raya Talla 28
            ("SKU000561", 525.0),  # Pants 2pz Punto Rojo Talla CH
            ("SKU000562", 525.0),  # Pants 2pz Punto Vino Talla CH
            ("SKU000563", 525.0),  # Pants 2pz Punto Gris Talla CH
            ("SKU000564", 525.0),  # Pants 2pz Punto Azul Marino Talla CH
            ("SKU000565", 525.0),  # Pants 2pz Punto Verde Talla CH
            ("SKU000566", 525.0),  # Pants 2pz Punto Azul Rey Talla CH
            ("SKU000567", 525.0),  # Pants 2pz Punto Bicolor Talla CH
            ("SKU000568", 525.0),  # Pants 2pz Punto Raya roja Talla CH
            ("SKU000569", 525.0),  # Pants 2pz Punto Doble raya Talla CH
            ("SKU000570", 535.0),  # Pants 2pz Punto Rojo Talla MD
            ("SKU000571", 535.0),  # Pants 2pz Punto Vino Talla MD
            ("SKU000572", 535.0),  # Pants 2pz Punto Gris Talla MD
            ("SKU000573", 535.0),  # Pants 2pz Punto Azul Marino Talla MD
            ("SKU000574", 535.0),  # Pants 2pz Punto Verde Talla MD
            ("SKU000575", 535.0),  # Pants 2pz Punto Azul Rey Talla MD
            ("SKU000576", 535.0),  # Pants 2pz Punto Bicolor Talla MD
            ("SKU000577", 535.0),  # Pants 2pz Punto Raya roja Talla MD
            ("SKU000578", 535.0),  # Pants 2pz Punto Doble raya Talla MD
            ("SKU000579", 545.0),  # Pants 2pz Punto Rojo Talla GD
            ("SKU000580", 545.0),  # Pants 2pz Punto Vino Talla GD
            ("SKU000581", 545.0),  # Pants 2pz Punto Gris Talla GD
            ("SKU000582", 545.0),  # Pants 2pz Punto Azul Marino Talla GD
            ("SKU000583", 545.0),  # Pants 2pz Punto Verde Talla GD
            ("SKU000584", 545.0),  # Pants 2pz Punto Azul Rey Talla GD
            ("SKU000585", 545.0),  # Pants 2pz Punto Bicolor Talla GD
            ("SKU000586", 545.0),  # Pants 2pz Punto Raya roja Talla GD
            ("SKU000587", 545.0),  # Pants 2pz Punto Doble raya Talla GD
            ("SKU000588", 555.0),  # Pants 2pz Punto Rojo Talla EXG
            ("SKU000589", 555.0),  # Pants 2pz Punto Vino Talla EXG
            ("SKU000590", 555.0),  # Pants 2pz Punto Gris Talla EXG
            ("SKU000591", 555.0),  # Pants 2pz Punto Azul Marino Talla EXG
            ("SKU000592", 555.0),  # Pants 2pz Punto Verde Talla EXG
            ("SKU000593", 555.0),  # Pants 2pz Punto Azul Rey Talla EXG
            ("SKU000594", 555.0),  # Pants 2pz Punto Bicolor Talla EXG
            ("SKU000595", 555.0),  # Pants 2pz Punto Raya roja Talla EXG
            ("SKU000596", 555.0),  # Pants 2pz Punto Doble raya Talla EXG
            ("SKU000597", 250.0),  # Pants 2pz Liso Rojo Talla 2
            ("SKU000598", 250.0),  # Pants 2pz Liso Blanco Talla 2
            ("SKU000599", 250.0),  # Pants 2pz Liso Vino Talla 2
            ("SKU000600", 250.0),  # Pants 2pz Liso Gris Talla 2
            ("SKU000601", 250.0),  # Pants 2pz Liso Azul Marino Talla 2
            ("SKU000602", 250.0),  # Pants 2pz Liso Verde Talla 2
            ("SKU000603", 250.0),  # Pants 2pz Liso Azul Rey Talla 2
            ("SKU000604", 250.0),  # Pants 2pz Liso Bicolor Talla 2
            ("SKU000605", 250.0),  # Pants 2pz Liso Raya roja Talla 2
            ("SKU000606", 250.0),  # Pants 2pz Liso Doble raya Talla 2
            ("SKU000607", 250.0),  # Pants 2pz Liso Rojo Talla 4
            ("SKU000608", 250.0),  # Pants 2pz Liso Blanco Talla 4
            ("SKU000609", 250.0),  # Pants 2pz Liso Vino Talla 4
            ("SKU000610", 250.0),  # Pants 2pz Liso Gris Talla 4
            ("SKU000611", 250.0),  # Pants 2pz Liso Azul Marino Talla 4
            ("SKU000612", 250.0),  # Pants 2pz Liso Verde Talla 4
            ("SKU000613", 250.0),  # Pants 2pz Liso Azul Rey Talla 4
            ("SKU000614", 250.0),  # Pants 2pz Liso Bicolor Talla 4
            ("SKU000615", 250.0),  # Pants 2pz Liso Raya roja Talla 4
            ("SKU000616", 250.0),  # Pants 2pz Liso Doble raya Talla 4
            ("SKU000617", 250.0),  # Pants 2pz Liso Rojo Talla 6
            ("SKU000618", 250.0),  # Pants 2pz Liso Blanco Talla 6
            ("SKU000619", 250.0),  # Pants 2pz Liso Vino Talla 6
            ("SKU000620", 250.0),  # Pants 2pz Liso Gris Talla 6
            ("SKU000621", 250.0),  # Pants 2pz Liso Azul Marino Talla 6
            ("SKU000622", 250.0),  # Pants 2pz Liso Verde Talla 6
            ("SKU000623", 250.0),  # Pants 2pz Liso Azul Rey Talla 6
            ("SKU000624", 250.0),  # Pants 2pz Liso Bicolor Talla 6
            ("SKU000625", 250.0),  # Pants 2pz Liso Raya roja Talla 6
            ("SKU000626", 250.0),  # Pants 2pz Liso Doble raya Talla 6
            ("SKU000627", 250.0),  # Pants 2pz Liso Rojo Talla 8
            ("SKU000628", 250.0),  # Pants 2pz Liso Blanco Talla 8
            ("SKU000629", 250.0),  # Pants 2pz Liso Vino Talla 8
            ("SKU000630", 250.0),  # Pants 2pz Liso Gris Talla 8
            ("SKU000631", 250.0),  # Pants 2pz Liso Azul Marino Talla 8
            ("SKU000632", 250.0),  # Pants 2pz Liso Verde Talla 8
            ("SKU000633", 250.0),  # Pants 2pz Liso Azul Rey Talla 8
            ("SKU000634", 250.0),  # Pants 2pz Liso Bicolor Talla 8
            ("SKU000635", 250.0),  # Pants 2pz Liso Raya roja Talla 8
            ("SKU000636", 250.0),  # Pants 2pz Liso Doble raya Talla 8
            ("SKU000637", 265.0),  # Pants 2pz Liso Rojo Talla 10
            ("SKU000638", 265.0),  # Pants 2pz Liso Blanco Talla 10
            ("SKU000639", 265.0),  # Pants 2pz Liso Vino Talla 10
            ("SKU000640", 265.0),  # Pants 2pz Liso Gris Talla 10
            ("SKU000641", 265.0),  # Pants 2pz Liso Azul Marino Talla 10
            ("SKU000642", 265.0),  # Pants 2pz Liso Verde Talla 10
            ("SKU000643", 265.0),  # Pants 2pz Liso Azul Rey Talla 10
            ("SKU000644", 265.0),  # Pants 2pz Liso Bicolor Talla 10
            ("SKU000645", 265.0),  # Pants 2pz Liso Raya roja Talla 10
            ("SKU000646", 265.0),  # Pants 2pz Liso Doble raya Talla 10
            ("SKU000647", 265.0),  # Pants 2pz Liso Rojo Talla 12
            ("SKU000648", 265.0),  # Pants 2pz Liso Blanco Talla 12
            ("SKU000649", 265.0),  # Pants 2pz Liso Vino Talla 12
            ("SKU000650", 265.0),  # Pants 2pz Liso Gris Talla 12
            ("SKU000651", 265.0),  # Pants 2pz Liso Azul Marino Talla 12
            ("SKU000652", 265.0),  # Pants 2pz Liso Verde Talla 12
            ("SKU000653", 265.0),  # Pants 2pz Liso Azul Rey Talla 12
            ("SKU000654", 265.0),  # Pants 2pz Liso Bicolor Talla 12
            ("SKU000655", 265.0),  # Pants 2pz Liso Raya roja Talla 12
            ("SKU000656", 265.0),  # Pants 2pz Liso Doble raya Talla 12
            ("SKU000657", 265.0),  # Pants 2pz Liso Rojo Talla 14
            ("SKU000658", 265.0),  # Pants 2pz Liso Blanco Talla 14
            ("SKU000659", 265.0),  # Pants 2pz Liso Vino Talla 14
            ("SKU000660", 265.0),  # Pants 2pz Liso Gris Talla 14
            ("SKU000661", 265.0),  # Pants 2pz Liso Azul Marino Talla 14
            ("SKU000662", 265.0),  # Pants 2pz Liso Verde Talla 14
            ("SKU000663", 265.0),  # Pants 2pz Liso Azul Rey Talla 14
            ("SKU000664", 265.0),  # Pants 2pz Liso Bicolor Talla 14
            ("SKU000665", 265.0),  # Pants 2pz Liso Raya roja Talla 14
            ("SKU000666", 265.0),  # Pants 2pz Liso Doble raya Talla 14
            ("SKU000667", 265.0),  # Pants 2pz Liso Rojo Talla 16
            ("SKU000668", 265.0),  # Pants 2pz Liso Blanco Talla 16
            ("SKU000669", 265.0),  # Pants 2pz Liso Vino Talla 16
            ("SKU000670", 265.0),  # Pants 2pz Liso Gris Talla 16
            ("SKU000671", 265.0),  # Pants 2pz Liso Azul Marino Talla 16
            ("SKU000672", 265.0),  # Pants 2pz Liso Verde Talla 16
            ("SKU000673", 265.0),  # Pants 2pz Liso Azul Rey Talla 16
            ("SKU000674", 265.0),  # Pants 2pz Liso Bicolor Talla 16
            ("SKU000675", 265.0),  # Pants 2pz Liso Raya roja Talla 16
            ("SKU000676", 265.0),  # Pants 2pz Liso Doble raya Talla 16
            ("SKU000677", 315.0),  # Pants 2pz Liso Rojo Talla 28
            ("SKU000678", 315.0),  # Pants 2pz Liso Blanco Talla 28
            ("SKU000679", 315.0),  # Pants 2pz Liso Vino Talla 28
            ("SKU000680", 315.0),  # Pants 2pz Liso Gris Talla 28
            ("SKU000681", 315.0),  # Pants 2pz Liso Azul Marino Talla 28
            ("SKU000682", 315.0),  # Pants 2pz Liso Verde Talla 28
            ("SKU000683", 315.0),  # Pants 2pz Liso Azul Rey Talla 28
            ("SKU000684", 315.0),  # Pants 2pz Liso Bicolor Talla 28
            ("SKU000685", 315.0),  # Pants 2pz Liso Raya roja Talla 28
            ("SKU000686", 315.0),  # Pants 2pz Liso Doble raya Talla 28
            ("SKU000687", 315.0),  # Pants 2pz Liso Rojo Talla CH
            ("SKU000688", 315.0),  # Pants 2pz Liso Blanco Talla CH
            ("SKU000689", 315.0),  # Pants 2pz Liso Vino Talla CH
            ("SKU000690", 315.0),  # Pants 2pz Liso Gris Talla CH
            ("SKU000691", 315.0),  # Pants 2pz Liso Azul Marino Talla CH
            ("SKU000692", 315.0),  # Pants 2pz Liso Verde Talla CH
            ("SKU000693", 315.0),  # Pants 2pz Liso Azul Rey Talla CH
            ("SKU000694", 315.0),  # Pants 2pz Liso Bicolor Talla CH
            ("SKU000695", 315.0),  # Pants 2pz Liso Raya roja Talla CH
            ("SKU000696", 315.0),  # Pants 2pz Liso Doble raya Talla CH
            ("SKU000697", 325.0),  # Pants 2pz Liso Rojo Talla MD
            ("SKU000698", 325.0),  # Pants 2pz Liso Blanco Talla MD
            ("SKU000699", 325.0),  # Pants 2pz Liso Vino Talla MD
            ("SKU000700", 325.0),  # Pants 2pz Liso Gris Talla MD
            ("SKU000701", 325.0),  # Pants 2pz Liso Azul Marino Talla MD
            ("SKU000702", 325.0),  # Pants 2pz Liso Verde Talla MD
            ("SKU000703", 325.0),  # Pants 2pz Liso Azul Rey Talla MD
            ("SKU000704", 325.0),  # Pants 2pz Liso Bicolor Talla MD
            ("SKU000705", 325.0),  # Pants 2pz Liso Raya roja Talla MD
            ("SKU000706", 325.0),  # Pants 2pz Liso Doble raya Talla MD
            ("SKU000707", 335.0),  # Pants 2pz Liso Rojo Talla GD
            ("SKU000708", 335.0),  # Pants 2pz Liso Blanco Talla GD
            ("SKU000709", 335.0),  # Pants 2pz Liso Vino Talla GD
            ("SKU000710", 335.0),  # Pants 2pz Liso Gris Talla GD
            ("SKU000711", 335.0),  # Pants 2pz Liso Azul Marino Talla GD
            ("SKU000712", 335.0),  # Pants 2pz Liso Verde Talla GD
            ("SKU000713", 335.0),  # Pants 2pz Liso Azul Rey Talla GD
            ("SKU000714", 335.0),  # Pants 2pz Liso Bicolor Talla GD
            ("SKU000715", 335.0),  # Pants 2pz Liso Raya roja Talla GD
            ("SKU000716", 335.0),  # Pants 2pz Liso Doble raya Talla GD
            ("SKU000717", 345.0),  # Pants 2pz Liso Rojo Talla EXG
            ("SKU000718", 345.0),  # Pants 2pz Liso Blanco Talla EXG
            ("SKU000719", 345.0),  # Pants 2pz Liso Vino Talla EXG
            ("SKU000720", 345.0),  # Pants 2pz Liso Gris Talla EXG
            ("SKU000721", 345.0),  # Pants 2pz Liso Azul Marino Talla EXG
            ("SKU000722", 345.0),  # Pants 2pz Liso Verde Talla EXG
            ("SKU000723", 345.0),  # Pants 2pz Liso Azul Rey Talla EXG
            ("SKU000724", 345.0),  # Pants 2pz Liso Bicolor Talla EXG
            ("SKU000725", 345.0),  # Pants 2pz Liso Raya roja Talla EXG
            ("SKU000726", 345.0),  # Pants 2pz Liso Doble raya Talla EXG
            ("SKU000727", 275.0),  # Chamarra Punto Rojo Talla 2
            ("SKU000728", 275.0),  # Chamarra Punto Vino Talla 2
            ("SKU000729", 275.0),  # Chamarra Punto Gris Talla 2
            ("SKU000730", 275.0),  # Chamarra Punto Azul Marino Talla 2
            ("SKU000731", 275.0),  # Chamarra Punto Verde Talla 2
            ("SKU000732", 275.0),  # Chamarra Punto Azul Rey Talla 2
            ("SKU000733", 275.0),  # Chamarra Punto Bicolor Talla 2
            ("SKU000734", 275.0),  # Chamarra Punto Raya roja Talla 2
            ("SKU000735", 275.0),  # Chamarra Punto Doble raya Talla 2
            ("SKU000736", 275.0),  # Chamarra Punto Rojo Talla 4
            ("SKU000737", 275.0),  # Chamarra Punto Vino Talla 4
            ("SKU000738", 275.0),  # Chamarra Punto Gris Talla 4
            ("SKU000739", 275.0),  # Chamarra Punto Azul Marino Talla 4
            ("SKU000740", 275.0),  # Chamarra Punto Verde Talla 4
            ("SKU000741", 275.0),  # Chamarra Punto Azul Rey Talla 4
            ("SKU000742", 275.0),  # Chamarra Punto Bicolor Talla 4
            ("SKU000743", 275.0),  # Chamarra Punto Raya roja Talla 4
            ("SKU000744", 275.0),  # Chamarra Punto Doble raya Talla 4
            ("SKU000745", 275.0),  # Chamarra Punto Rojo Talla 6
            ("SKU000746", 275.0),  # Chamarra Punto Vino Talla 6
            ("SKU000747", 275.0),  # Chamarra Punto Gris Talla 6
            ("SKU000748", 275.0),  # Chamarra Punto Azul Marino Talla 6
            ("SKU000749", 275.0),  # Chamarra Punto Verde Talla 6
            ("SKU000750", 275.0),  # Chamarra Punto Azul Rey Talla 6
            ("SKU000751", 275.0),  # Chamarra Punto Bicolor Talla 6
            ("SKU000752", 275.0),  # Chamarra Punto Raya roja Talla 6
            ("SKU000753", 275.0),  # Chamarra Punto Doble raya Talla 6
            ("SKU000754", 275.0),  # Chamarra Punto Rojo Talla 8
            ("SKU000755", 275.0),  # Chamarra Punto Vino Talla 8
            ("SKU000756", 275.0),  # Chamarra Punto Gris Talla 8
            ("SKU000757", 275.0),  # Chamarra Punto Azul Marino Talla 8
            ("SKU000758", 275.0),  # Chamarra Punto Verde Talla 8
            ("SKU000759", 275.0),  # Chamarra Punto Azul Rey Talla 8
            ("SKU000760", 275.0),  # Chamarra Punto Bicolor Talla 8
            ("SKU000761", 275.0),  # Chamarra Punto Raya roja Talla 8
            ("SKU000762", 275.0),  # Chamarra Punto Doble raya Talla 8
            ("SKU000763", 295.0),  # Chamarra Punto Rojo Talla 10
            ("SKU000764", 295.0),  # Chamarra Punto Vino Talla 10
            ("SKU000765", 295.0),  # Chamarra Punto Gris Talla 10
            ("SKU000766", 295.0),  # Chamarra Punto Azul Marino Talla 10
            ("SKU000767", 295.0),  # Chamarra Punto Verde Talla 10
            ("SKU000768", 295.0),  # Chamarra Punto Azul Rey Talla 10
            ("SKU000769", 295.0),  # Chamarra Punto Bicolor Talla 10
            ("SKU000770", 295.0),  # Chamarra Punto Raya roja Talla 10
            ("SKU000771", 295.0),  # Chamarra Punto Doble raya Talla 10
            ("SKU000772", 295.0),  # Chamarra Punto Rojo Talla 12
            ("SKU000773", 295.0),  # Chamarra Punto Vino Talla 12
            ("SKU000774", 295.0),  # Chamarra Punto Gris Talla 12
            ("SKU000775", 295.0),  # Chamarra Punto Azul Marino Talla 12
            ("SKU000776", 295.0),  # Chamarra Punto Verde Talla 12
            ("SKU000777", 295.0),  # Chamarra Punto Azul Rey Talla 12
            ("SKU000778", 295.0),  # Chamarra Punto Bicolor Talla 12
            ("SKU000779", 295.0),  # Chamarra Punto Raya roja Talla 12
            ("SKU000780", 295.0),  # Chamarra Punto Doble raya Talla 12
            ("SKU000781", 295.0),  # Chamarra Punto Rojo Talla 14
            ("SKU000782", 295.0),  # Chamarra Punto Vino Talla 14
            ("SKU000783", 295.0),  # Chamarra Punto Gris Talla 14
            ("SKU000784", 295.0),  # Chamarra Punto Azul Marino Talla 14
            ("SKU000785", 295.0),  # Chamarra Punto Verde Talla 14
            ("SKU000786", 295.0),  # Chamarra Punto Azul Rey Talla 14
            ("SKU000787", 295.0),  # Chamarra Punto Bicolor Talla 14
            ("SKU000788", 295.0),  # Chamarra Punto Raya roja Talla 14
            ("SKU000789", 295.0),  # Chamarra Punto Doble raya Talla 14
            ("SKU000790", 295.0),  # Chamarra Punto Rojo Talla 16
            ("SKU000791", 295.0),  # Chamarra Punto Vino Talla 16
            ("SKU000792", 295.0),  # Chamarra Punto Gris Talla 16
            ("SKU000793", 295.0),  # Chamarra Punto Azul Marino Talla 16
            ("SKU000794", 295.0),  # Chamarra Punto Verde Talla 16
            ("SKU000795", 295.0),  # Chamarra Punto Azul Rey Talla 16
            ("SKU000796", 295.0),  # Chamarra Punto Bicolor Talla 16
            ("SKU000797", 295.0),  # Chamarra Punto Raya roja Talla 16
            ("SKU000798", 295.0),  # Chamarra Punto Doble raya Talla 16
            ("SKU000799", 385.0),  # Chamarra Punto Rojo Talla 28
            ("SKU000800", 385.0),  # Chamarra Punto Vino Talla 28
            ("SKU000801", 385.0),  # Chamarra Punto Gris Talla 28
            ("SKU000802", 385.0),  # Chamarra Punto Azul Marino Talla 28
            ("SKU000803", 385.0),  # Chamarra Punto Verde Talla 28
            ("SKU000804", 385.0),  # Chamarra Punto Azul Rey Talla 28
            ("SKU000805", 385.0),  # Chamarra Punto Bicolor Talla 28
            ("SKU000806", 385.0),  # Chamarra Punto Raya roja Talla 28
            ("SKU000807", 385.0),  # Chamarra Punto Doble raya Talla 28
            ("SKU000808", 385.0),  # Chamarra Punto Rojo Talla CH
            ("SKU000809", 385.0),  # Chamarra Punto Vino Talla CH
            ("SKU000810", 385.0),  # Chamarra Punto Gris Talla CH
            ("SKU000811", 385.0),  # Chamarra Punto Azul Marino Talla CH
            ("SKU000812", 385.0),  # Chamarra Punto Verde Talla CH
            ("SKU000813", 385.0),  # Chamarra Punto Azul Rey Talla CH
            ("SKU000814", 385.0),  # Chamarra Punto Bicolor Talla CH
            ("SKU000815", 385.0),  # Chamarra Punto Raya roja Talla CH
            ("SKU000816", 385.0),  # Chamarra Punto Doble raya Talla CH
            ("SKU000817", 395.0),  # Chamarra Punto Rojo Talla MD
            ("SKU000818", 395.0),  # Chamarra Punto Vino Talla MD
            ("SKU000819", 395.0),  # Chamarra Punto Gris Talla MD
            ("SKU000820", 395.0),  # Chamarra Punto Azul Marino Talla MD
            ("SKU000821", 395.0),  # Chamarra Punto Verde Talla MD
            ("SKU000822", 395.0),  # Chamarra Punto Azul Rey Talla MD
            ("SKU000823", 395.0),  # Chamarra Punto Bicolor Talla MD
            ("SKU000824", 395.0),  # Chamarra Punto Raya roja Talla MD
            ("SKU000825", 395.0),  # Chamarra Punto Doble raya Talla MD
            ("SKU000826", 405.0),  # Chamarra Punto Rojo Talla GD
            ("SKU000827", 405.0),  # Chamarra Punto Vino Talla GD
            ("SKU000828", 405.0),  # Chamarra Punto Gris Talla GD
            ("SKU000829", 405.0),  # Chamarra Punto Azul Marino Talla GD
            ("SKU000830", 405.0),  # Chamarra Punto Verde Talla GD
            ("SKU000831", 405.0),  # Chamarra Punto Azul Rey Talla GD
            ("SKU000832", 405.0),  # Chamarra Punto Bicolor Talla GD
            ("SKU000833", 405.0),  # Chamarra Punto Raya roja Talla GD
            ("SKU000834", 405.0),  # Chamarra Punto Doble raya Talla GD
            ("SKU000835", 415.0),  # Chamarra Punto Rojo Talla EXG
            ("SKU000836", 415.0),  # Chamarra Punto Vino Talla EXG
            ("SKU000837", 415.0),  # Chamarra Punto Gris Talla EXG
            ("SKU000838", 415.0),  # Chamarra Punto Azul Marino Talla EXG
            ("SKU000839", 415.0),  # Chamarra Punto Verde Talla EXG
            ("SKU000840", 415.0),  # Chamarra Punto Azul Rey Talla EXG
            ("SKU000841", 415.0),  # Chamarra Punto Bicolor Talla EXG
            ("SKU000842", 415.0),  # Chamarra Punto Raya roja Talla EXG
            ("SKU000843", 415.0),  # Chamarra Punto Doble raya Talla EXG
            ("SKU000844", 175.0),  # Chamarra Liso Rojo Talla 2
            ("SKU000845", 175.0),  # Chamarra Liso Vino Talla 2
            ("SKU000846", 175.0),  # Chamarra Liso Gris Talla 2
            ("SKU000847", 175.0),  # Chamarra Liso Azul Marino Talla 2
            ("SKU000848", 175.0),  # Chamarra Liso Verde Talla 2
            ("SKU000849", 175.0),  # Chamarra Liso Azul Rey Talla 2
            ("SKU000850", 175.0),  # Chamarra Liso Blanca Talla 2
            ("SKU000851", 175.0),  # Chamarra Liso Bicolor Talla 2
            ("SKU000852", 175.0),  # Chamarra Liso Raya roja Talla 2
            ("SKU000853", 175.0),  # Chamarra Liso Doble raya Talla 2
            ("SKU000854", 175.0),  # Chamarra Liso Rojo Talla 4
            ("SKU000855", 175.0),  # Chamarra Liso Vino Talla 4
            ("SKU000856", 175.0),  # Chamarra Liso Gris Talla 4
            ("SKU000857", 175.0),  # Chamarra Liso Azul Marino Talla 4
            ("SKU000858", 175.0),  # Chamarra Liso Verde Talla 4
            ("SKU000859", 175.0),  # Chamarra Liso Azul Rey Talla 4
            ("SKU000860", 175.0),  # Chamarra Liso Blanca Talla 4
            ("SKU000861", 175.0),  # Chamarra Liso Bicolor Talla 4
            ("SKU000862", 175.0),  # Chamarra Liso Raya roja Talla 4
            ("SKU000863", 175.0),  # Chamarra Liso Doble raya Talla 4
            ("SKU000864", 175.0),  # Chamarra Liso Rojo Talla 6
            ("SKU000865", 175.0),  # Chamarra Liso Vino Talla 6
            ("SKU000866", 175.0),  # Chamarra Liso Gris Talla 6
            ("SKU000867", 175.0),  # Chamarra Liso Azul Marino Talla 6
            ("SKU000868", 175.0),  # Chamarra Liso Verde Talla 6
            ("SKU000869", 175.0),  # Chamarra Liso Azul Rey Talla 6
            ("SKU000870", 175.0),  # Chamarra Liso Blanca Talla 6
            ("SKU000871", 175.0),  # Chamarra Liso Bicolor Talla 6
            ("SKU000872", 175.0),  # Chamarra Liso Raya roja Talla 6
            ("SKU000873", 175.0),  # Chamarra Liso Doble raya Talla 6
            ("SKU000874", 175.0),  # Chamarra Liso Rojo Talla 8
            ("SKU000875", 175.0),  # Chamarra Liso Vino Talla 8
            ("SKU000876", 175.0),  # Chamarra Liso Gris Talla 8
            ("SKU000877", 175.0),  # Chamarra Liso Azul Marino Talla 8
            ("SKU000878", 175.0),  # Chamarra Liso Verde Talla 8
            ("SKU000879", 175.0),  # Chamarra Liso Azul Rey Talla 8
            ("SKU000880", 175.0),  # Chamarra Liso Blanca Talla 8
            ("SKU000881", 175.0),  # Chamarra Liso Bicolor Talla 8
            ("SKU000882", 175.0),  # Chamarra Liso Raya roja Talla 8
            ("SKU000883", 175.0),  # Chamarra Liso Doble raya Talla 8
            ("SKU000884", 195.0),  # Chamarra Liso Rojo Talla 10
            ("SKU000885", 195.0),  # Chamarra Liso Vino Talla 10
            ("SKU000886", 195.0),  # Chamarra Liso Gris Talla 10
            ("SKU000887", 195.0),  # Chamarra Liso Azul Marino Talla 10
            ("SKU000888", 195.0),  # Chamarra Liso Verde Talla 10
            ("SKU000889", 195.0),  # Chamarra Liso Azul Rey Talla 10
            ("SKU000890", 195.0),  # Chamarra Liso Blanca Talla 10
            ("SKU000891", 195.0),  # Chamarra Liso Bicolor Talla 10
            ("SKU000892", 195.0),  # Chamarra Liso Raya roja Talla 10
            ("SKU000893", 195.0),  # Chamarra Liso Doble raya Talla 10
            ("SKU000894", 195.0),  # Chamarra Liso Rojo Talla 12
            ("SKU000895", 195.0),  # Chamarra Liso Vino Talla 12
            ("SKU000896", 195.0),  # Chamarra Liso Gris Talla 12
            ("SKU000897", 195.0),  # Chamarra Liso Azul Marino Talla 12
            ("SKU000898", 195.0),  # Chamarra Liso Verde Talla 12
            ("SKU000899", 195.0),  # Chamarra Liso Azul Rey Talla 12
            ("SKU000900", 195.0),  # Chamarra Liso Blanca Talla 12
            ("SKU000901", 195.0),  # Chamarra Liso Bicolor Talla 12
            ("SKU000902", 195.0),  # Chamarra Liso Raya roja Talla 12
            ("SKU000903", 195.0),  # Chamarra Liso Doble raya Talla 12
            ("SKU000904", 225.0),  # Chamarra Liso Rojo Talla 14
            ("SKU000905", 215.0),  # Chamarra Liso Vino Talla 14
            ("SKU000906", 215.0),  # Chamarra Liso Gris Talla 14
            ("SKU000907", 215.0),  # Chamarra Liso Azul Marino Talla 14
            ("SKU000908", 215.0),  # Chamarra Liso Verde Talla 14
            ("SKU000909", 215.0),  # Chamarra Liso Azul Rey Talla 14
            ("SKU000910", 215.0),  # Chamarra Liso Blanca Talla 14
            ("SKU000911", 215.0),  # Chamarra Liso Bicolor Talla 14
            ("SKU000912", 215.0),  # Chamarra Liso Raya roja Talla 14
            ("SKU000913", 215.0),  # Chamarra Liso Doble raya Talla 14
            ("SKU000914", 215.0),  # Chamarra Liso Rojo Talla 16
            ("SKU000915", 215.0),  # Chamarra Liso Vino Talla 16
            ("SKU000916", 215.0),  # Chamarra Liso Gris Talla 16
            ("SKU000917", 215.0),  # Chamarra Liso Azul Marino Talla 16
            ("SKU000918", 215.0),  # Chamarra Liso Verde Talla 16
            ("SKU000919", 215.0),  # Chamarra Liso Azul Rey Talla 16
            ("SKU000920", 215.0),  # Chamarra Liso Blanca Talla 16
            ("SKU000921", 215.0),  # Chamarra Liso Bicolor Talla 16
            ("SKU000922", 215.0),  # Chamarra Liso Raya roja Talla 16
            ("SKU000923", 215.0),  # Chamarra Liso Doble raya Talla 16
            ("SKU000924", 235.0),  # Chamarra Liso Rojo Talla 28
            ("SKU000925", 235.0),  # Chamarra Liso Vino Talla 28
            ("SKU000926", 235.0),  # Chamarra Liso Gris Talla 28
            ("SKU000927", 235.0),  # Chamarra Liso Azul Marino Talla 28
            ("SKU000928", 235.0),  # Chamarra Liso Verde Talla 28
            ("SKU000929", 235.0),  # Chamarra Liso Azul Rey Talla 28
            ("SKU000930", 235.0),  # Chamarra Liso Blanca Talla 28
            ("SKU000931", 235.0),  # Chamarra Liso Bicolor Talla 28
            ("SKU000932", 235.0),  # Chamarra Liso Raya roja Talla 28
            ("SKU000933", 235.0),  # Chamarra Liso Doble raya Talla 28
            ("SKU000934", 235.0),  # Chamarra Liso Rojo Talla CH
            ("SKU000935", 235.0),  # Chamarra Liso Vino Talla CH
            ("SKU000936", 235.0),  # Chamarra Liso Gris Talla CH
            ("SKU000937", 235.0),  # Chamarra Liso Azul Marino Talla CH
            ("SKU000938", 235.0),  # Chamarra Liso Verde Talla CH
            ("SKU000939", 235.0),  # Chamarra Liso Azul Rey Talla CH
            ("SKU000940", 235.0),  # Chamarra Liso Blanca Talla CH
            ("SKU000941", 235.0),  # Chamarra Liso Bicolor Talla CH
            ("SKU000942", 235.0),  # Chamarra Liso Raya roja Talla CH
            ("SKU000943", 235.0),  # Chamarra Liso Doble raya Talla CH
            ("SKU000944", 235.0),  # Chamarra Liso Rojo Talla MD
            ("SKU000945", 235.0),  # Chamarra Liso Vino Talla MD
            ("SKU000946", 235.0),  # Chamarra Liso Gris Talla MD
            ("SKU000947", 235.0),  # Chamarra Liso Azul Marino Talla MD
            ("SKU000948", 235.0),  # Chamarra Liso Verde Talla MD
            ("SKU000949", 235.0),  # Chamarra Liso Azul Rey Talla MD
            ("SKU000950", 235.0),  # Chamarra Liso Blanca Talla MD
            ("SKU000951", 235.0),  # Chamarra Liso Bicolor Talla MD
            ("SKU000952", 235.0),  # Chamarra Liso Raya roja Talla MD
            ("SKU000953", 235.0),  # Chamarra Liso Doble raya Talla MD
            ("SKU000954", 235.0),  # Chamarra Liso Rojo Talla GD
            ("SKU000955", 235.0),  # Chamarra Liso Vino Talla GD
            ("SKU000956", 235.0),  # Chamarra Liso Gris Talla GD
            ("SKU000957", 235.0),  # Chamarra Liso Azul Marino Talla GD
            ("SKU000958", 235.0),  # Chamarra Liso Verde Talla GD
            ("SKU000959", 235.0),  # Chamarra Liso Azul Rey Talla GD
            ("SKU000960", 235.0),  # Chamarra Liso Blanca Talla GD
            ("SKU000961", 235.0),  # Chamarra Liso Bicolor Talla GD
            ("SKU000962", 235.0),  # Chamarra Liso Raya roja Talla GD
            ("SKU000963", 235.0),  # Chamarra Liso Doble raya Talla GD
            ("SKU000964", 235.0),  # Chamarra Liso Rojo Talla EXG
            ("SKU000965", 235.0),  # Chamarra Liso Vino Talla EXG
            ("SKU000966", 235.0),  # Chamarra Liso Gris Talla EXG
            ("SKU000967", 235.0),  # Chamarra Liso Azul Marino Talla EXG
            ("SKU000968", 235.0),  # Chamarra Liso Verde Talla EXG
            ("SKU000969", 235.0),  # Chamarra Liso Azul Rey Talla EXG
            ("SKU000970", 235.0),  # Chamarra Liso Blanca Talla EXG
            ("SKU000971", 235.0),  # Chamarra Liso Bicolor Talla EXG
            ("SKU000972", 235.0),  # Chamarra Liso Raya roja Talla EXG
            ("SKU000973", 235.0),  # Chamarra Liso Doble raya Talla EXG
            ("SKU000974", 249.0),  # Pants Suelto Punto Rojo Talla 2
            ("SKU000975", 249.0),  # Pants Suelto Punto Vino Talla 2
            ("SKU000976", 249.0),  # Pants Suelto Punto Gris Talla 2
            ("SKU000977", 249.0),  # Pants Suelto Punto Azul Marino Talla 2
            ("SKU000978", 249.0),  # Pants Suelto Punto Verde Talla 2
            ("SKU000979", 249.0),  # Pants Suelto Punto Azul Rey Talla 2
            ("SKU000980", 249.0),  # Pants Suelto Punto Bicolor Talla 2
            ("SKU000981", 249.0),  # Pants Suelto Punto Raya roja Talla 2
            ("SKU000982", 249.0),  # Pants Suelto Punto Doble raya Talla 2
            ("SKU000983", 249.0),  # Pants Suelto Punto Rojo Talla 4
            ("SKU000984", 249.0),  # Pants Suelto Punto Vino Talla 4
            ("SKU000985", 249.0),  # Pants Suelto Punto Gris Talla 4
            ("SKU000986", 249.0),  # Pants Suelto Punto Azul Marino Talla 4
            ("SKU000987", 249.0),  # Pants Suelto Punto Verde Talla 4
            ("SKU000988", 249.0),  # Pants Suelto Punto Azul Rey Talla 4
            ("SKU000989", 249.0),  # Pants Suelto Punto Bicolor Talla 4
            ("SKU000990", 249.0),  # Pants Suelto Punto Raya roja Talla 4
            ("SKU000991", 249.0),  # Pants Suelto Punto Doble raya Talla 4
            ("SKU000992", 249.0),  # Pants Suelto Punto Rojo Talla 6
            ("SKU000993", 249.0),  # Pants Suelto Punto Vino Talla 6
            ("SKU000994", 249.0),  # Pants Suelto Punto Gris Talla 6
            ("SKU000995", 249.0),  # Pants Suelto Punto Azul Marino Talla 6
            ("SKU000996", 249.0),  # Pants Suelto Punto Verde Talla 6
            ("SKU000997", 249.0),  # Pants Suelto Punto Azul Rey Talla 6
            ("SKU000998", 249.0),  # Pants Suelto Punto Bicolor Talla 6
            ("SKU000999", 249.0),  # Pants Suelto Punto Raya roja Talla 6
            ("SKU001000", 249.0),  # Pants Suelto Punto Doble raya Talla 6
            ("SKU001001", 249.0),  # Pants Suelto Punto Rojo Talla 8
            ("SKU001002", 249.0),  # Pants Suelto Punto Vino Talla 8
            ("SKU001003", 249.0),  # Pants Suelto Punto Gris Talla 8
            ("SKU001004", 249.0),  # Pants Suelto Punto Azul Marino Talla 8
            ("SKU001005", 249.0),  # Pants Suelto Punto Verde Talla 8
            ("SKU001006", 249.0),  # Pants Suelto Punto Azul Rey Talla 8
            ("SKU001007", 249.0),  # Pants Suelto Punto Bicolor Talla 8
            ("SKU001008", 249.0),  # Pants Suelto Punto Raya roja Talla 8
            ("SKU001009", 249.0),  # Pants Suelto Punto Doble raya Talla 8
            ("SKU001010", 269.0),  # Pants Suelto Punto Rojo Talla 10
            ("SKU001011", 269.0),  # Pants Suelto Punto Vino Talla 10
            ("SKU001012", 269.0),  # Pants Suelto Punto Gris Talla 10
            ("SKU001013", 269.0),  # Pants Suelto Punto Azul Marino Talla 10
            ("SKU001014", 269.0),  # Pants Suelto Punto Verde Talla 10
            ("SKU001015", 269.0),  # Pants Suelto Punto Azul Rey Talla 10
            ("SKU001016", 269.0),  # Pants Suelto Punto Bicolor Talla 10
            ("SKU001017", 269.0),  # Pants Suelto Punto Raya roja Talla 10
            ("SKU001018", 269.0),  # Pants Suelto Punto Doble raya Talla 10
            ("SKU001019", 269.0),  # Pants Suelto Punto Rojo Talla 12
            ("SKU001020", 269.0),  # Pants Suelto Punto Vino Talla 12
            ("SKU001021", 269.0),  # Pants Suelto Punto Gris Talla 12
            ("SKU001022", 269.0),  # Pants Suelto Punto Azul Marino Talla 12
            ("SKU001023", 269.0),  # Pants Suelto Punto Verde Talla 12
            ("SKU001024", 269.0),  # Pants Suelto Punto Azul Rey Talla 12
            ("SKU001025", 269.0),  # Pants Suelto Punto Bicolor Talla 12
            ("SKU001026", 269.0),  # Pants Suelto Punto Raya roja Talla 12
            ("SKU001027", 269.0),  # Pants Suelto Punto Doble raya Talla 12
            ("SKU001028", 269.0),  # Pants Suelto Punto Rojo Talla 14
            ("SKU001029", 269.0),  # Pants Suelto Punto Vino Talla 14
            ("SKU001030", 269.0),  # Pants Suelto Punto Gris Talla 14
            ("SKU001031", 269.0),  # Pants Suelto Punto Azul Marino Talla 14
            ("SKU001032", 269.0),  # Pants Suelto Punto Verde Talla 14
            ("SKU001033", 269.0),  # Pants Suelto Punto Azul Rey Talla 14
            ("SKU001034", 269.0),  # Pants Suelto Punto Bicolor Talla 14
            ("SKU001035", 269.0),  # Pants Suelto Punto Raya roja Talla 14
            ("SKU001036", 269.0),  # Pants Suelto Punto Doble raya Talla 14
            ("SKU001037", 269.0),  # Pants Suelto Punto Rojo Talla 16
            ("SKU001038", 269.0),  # Pants Suelto Punto Vino Talla 16
            ("SKU001039", 269.0),  # Pants Suelto Punto Gris Talla 16
            ("SKU001040", 269.0),  # Pants Suelto Punto Azul Marino Talla 16
            ("SKU001041", 269.0),  # Pants Suelto Punto Verde Talla 16
            ("SKU001042", 269.0),  # Pants Suelto Punto Azul Rey Talla 16
            ("SKU001043", 269.0),  # Pants Suelto Punto Bicolor Talla 16
            ("SKU001044", 269.0),  # Pants Suelto Punto Raya roja Talla 16
            ("SKU001045", 269.0),  # Pants Suelto Punto Doble raya Talla 16
            ("SKU001046", 309.0),  # Pants Suelto Punto Rojo Talla 28
            ("SKU001047", 309.0),  # Pants Suelto Punto Vino Talla 28
            ("SKU001048", 309.0),  # Pants Suelto Punto Gris Talla 28
            ("SKU001049", 309.0),  # Pants Suelto Punto Azul Marino Talla 28
            ("SKU001050", 309.0),  # Pants Suelto Punto Verde Talla 28
            ("SKU001051", 309.0),  # Pants Suelto Punto Azul Rey Talla 28
            ("SKU001052", 309.0),  # Pants Suelto Punto Bicolor Talla 28
            ("SKU001053", 309.0),  # Pants Suelto Punto Raya roja Talla 28
            ("SKU001054", 309.0),  # Pants Suelto Punto Doble raya Talla 28
            ("SKU001055", 309.0),  # Pants Suelto Punto Rojo Talla CH
            ("SKU001056", 309.0),  # Pants Suelto Punto Vino Talla CH
            ("SKU001057", 309.0),  # Pants Suelto Punto Gris Talla CH
            ("SKU001058", 309.0),  # Pants Suelto Punto Azul Marino Talla CH
            ("SKU001059", 309.0),  # Pants Suelto Punto Verde Talla CH
            ("SKU001060", 309.0),  # Pants Suelto Punto Azul Rey Talla CH
            ("SKU001061", 309.0),  # Pants Suelto Punto Bicolor Talla CH
            ("SKU001062", 309.0),  # Pants Suelto Punto Raya roja Talla CH
            ("SKU001063", 309.0),  # Pants Suelto Punto Doble raya Talla CH
            ("SKU001064", 319.0),  # Pants Suelto Punto Rojo Talla MD
            ("SKU001065", 319.0),  # Pants Suelto Punto Vino Talla MD
            ("SKU001066", 319.0),  # Pants Suelto Punto Gris Talla MD
            ("SKU001067", 319.0),  # Pants Suelto Punto Azul Marino Talla MD
            ("SKU001068", 319.0),  # Pants Suelto Punto Verde Talla MD
            ("SKU001069", 319.0),  # Pants Suelto Punto Azul Rey Talla MD
            ("SKU001070", 319.0),  # Pants Suelto Punto Bicolor Talla MD
            ("SKU001071", 319.0),  # Pants Suelto Punto Raya roja Talla MD
            ("SKU001072", 319.0),  # Pants Suelto Punto Doble raya Talla MD
            ("SKU001073", 319.0),  # Pants Suelto Punto Rojo Talla GD
            ("SKU001074", 319.0),  # Pants Suelto Punto Vino Talla GD
            ("SKU001075", 319.0),  # Pants Suelto Punto Gris Talla GD
            ("SKU001076", 319.0),  # Pants Suelto Punto Azul Marino Talla GD
            ("SKU001077", 319.0),  # Pants Suelto Punto Verde Talla GD
            ("SKU001078", 319.0),  # Pants Suelto Punto Azul Rey Talla GD
            ("SKU001079", 319.0),  # Pants Suelto Punto Bicolor Talla GD
            ("SKU001080", 319.0),  # Pants Suelto Punto Raya roja Talla GD
            ("SKU001081", 319.0),  # Pants Suelto Punto Doble raya Talla GD
            ("SKU001082", 339.0),  # Pants Suelto Punto Rojo Talla EXG
            ("SKU001083", 339.0),  # Pants Suelto Punto Vino Talla EXG
            ("SKU001084", 339.0),  # Pants Suelto Punto Gris Talla EXG
            ("SKU001085", 339.0),  # Pants Suelto Punto Azul Marino Talla EXG
            ("SKU001086", 339.0),  # Pants Suelto Punto Verde Talla EXG
            ("SKU001087", 339.0),  # Pants Suelto Punto Azul Rey Talla EXG
            ("SKU001088", 339.0),  # Pants Suelto Punto Bicolor Talla EXG
            ("SKU001089", 339.0),  # Pants Suelto Punto Raya roja Talla EXG
            ("SKU001090", 339.0),  # Pants Suelto Punto Doble raya Talla EXG
            ("SKU001091", 165.0),  # Pants Suelto Liso Rojo Talla 2
            ("SKU001092", 165.0),  # Pants Suelto Liso Vino Talla 2
            ("SKU001093", 165.0),  # Pants Suelto Liso Gris Talla 2
            ("SKU001094", 165.0),  # Pants Suelto Liso Azul Marino Talla 2
            ("SKU001095", 165.0),  # Pants Suelto Liso Verde Talla 2
            ("SKU001096", 165.0),  # Pants Suelto Liso Azul Rey Talla 2
            ("SKU001097", 165.0),  # Pants Suelto Liso Blanca Talla 2
            ("SKU001098", 165.0),  # Pants Suelto Liso Bicolor Talla 2
            ("SKU001099", 165.0),  # Pants Suelto Liso Raya roja Talla 2
            ("SKU001100", 165.0),  # Pants Suelto Liso Doble raya Talla 2
            ("SKU001101", 165.0),  # Pants Suelto Liso Rojo Talla 4
            ("SKU001102", 165.0),  # Pants Suelto Liso Vino Talla 4
            ("SKU001103", 165.0),  # Pants Suelto Liso Gris Talla 4
            ("SKU001104", 165.0),  # Pants Suelto Liso Azul Marino Talla 4
            ("SKU001105", 165.0),  # Pants Suelto Liso Verde Talla 4
            ("SKU001106", 165.0),  # Pants Suelto Liso Azul Rey Talla 4
            ("SKU001107", 165.0),  # Pants Suelto Liso Blanca Talla 4
            ("SKU001108", 165.0),  # Pants Suelto Liso Bicolor Talla 4
            ("SKU001109", 165.0),  # Pants Suelto Liso Raya roja Talla 4
            ("SKU001110", 165.0),  # Pants Suelto Liso Doble raya Talla 4
            ("SKU001111", 165.0),  # Pants Suelto Liso Rojo Talla 6
            ("SKU001112", 165.0),  # Pants Suelto Liso Vino Talla 6
            ("SKU001113", 165.0),  # Pants Suelto Liso Gris Talla 6
            ("SKU001114", 165.0),  # Pants Suelto Liso Azul Marino Talla 6
            ("SKU001115", 165.0),  # Pants Suelto Liso Verde Talla 6
            ("SKU001116", 165.0),  # Pants Suelto Liso Azul Rey Talla 6
            ("SKU001117", 165.0),  # Pants Suelto Liso Blanca Talla 6
            ("SKU001118", 165.0),  # Pants Suelto Liso Bicolor Talla 6
            ("SKU001119", 165.0),  # Pants Suelto Liso Raya roja Talla 6
            ("SKU001120", 165.0),  # Pants Suelto Liso Doble raya Talla 6
            ("SKU001121", 165.0),  # Pants Suelto Liso Rojo Talla 8
            ("SKU001122", 165.0),  # Pants Suelto Liso Vino Talla 8
            ("SKU001123", 165.0),  # Pants Suelto Liso Gris Talla 8
            ("SKU001124", 165.0),  # Pants Suelto Liso Azul Marino Talla 8
            ("SKU001125", 165.0),  # Pants Suelto Liso Verde Talla 8
            ("SKU001126", 165.0),  # Pants Suelto Liso Azul Rey Talla 8
            ("SKU001127", 165.0),  # Pants Suelto Liso Blanca Talla 8
            ("SKU001128", 165.0),  # Pants Suelto Liso Bicolor Talla 8
            ("SKU001129", 165.0),  # Pants Suelto Liso Raya roja Talla 8
            ("SKU001130", 165.0),  # Pants Suelto Liso Doble raya Talla 8
            ("SKU001131", 180.0),  # Pants Suelto Liso Rojo Talla 10
            ("SKU001132", 180.0),  # Pants Suelto Liso Vino Talla 10
            ("SKU001133", 180.0),  # Pants Suelto Liso Gris Talla 10
            ("SKU001134", 180.0),  # Pants Suelto Liso Azul Marino Talla 10
            ("SKU001135", 180.0),  # Pants Suelto Liso Verde Talla 10
            ("SKU001136", 180.0),  # Pants Suelto Liso Azul Rey Talla 10
            ("SKU001137", 180.0),  # Pants Suelto Liso Blanca Talla 10
            ("SKU001138", 180.0),  # Pants Suelto Liso Bicolor Talla 10
            ("SKU001139", 180.0),  # Pants Suelto Liso Raya roja Talla 10
            ("SKU001140", 180.0),  # Pants Suelto Liso Doble raya Talla 10
            ("SKU001141", 180.0),  # Pants Suelto Liso Rojo Talla 12
            ("SKU001142", 180.0),  # Pants Suelto Liso Vino Talla 12
            ("SKU001143", 180.0),  # Pants Suelto Liso Gris Talla 12
            ("SKU001144", 180.0),  # Pants Suelto Liso Azul Marino Talla 12
            ("SKU001145", 180.0),  # Pants Suelto Liso Verde Talla 12
            ("SKU001146", 180.0),  # Pants Suelto Liso Azul Rey Talla 12
            ("SKU001147", 180.0),  # Pants Suelto Liso Blanca Talla 12
            ("SKU001148", 180.0),  # Pants Suelto Liso Bicolor Talla 12
            ("SKU001149", 180.0),  # Pants Suelto Liso Raya roja Talla 12
            ("SKU001150", 180.0),  # Pants Suelto Liso Doble raya Talla 12
            ("SKU001151", 180.0),  # Pants Suelto Liso Rojo Talla 14
            ("SKU001152", 180.0),  # Pants Suelto Liso Vino Talla 14
            ("SKU001153", 180.0),  # Pants Suelto Liso Gris Talla 14
            ("SKU001154", 180.0),  # Pants Suelto Liso Azul Marino Talla 14
            ("SKU001155", 180.0),  # Pants Suelto Liso Verde Talla 14
            ("SKU001156", 180.0),  # Pants Suelto Liso Azul Rey Talla 14
            ("SKU001157", 180.0),  # Pants Suelto Liso Blanca Talla 14
            ("SKU001158", 180.0),  # Pants Suelto Liso Bicolor Talla 14
            ("SKU001159", 180.0),  # Pants Suelto Liso Raya roja Talla 14
            ("SKU001160", 180.0),  # Pants Suelto Liso Doble raya Talla 14
            ("SKU001161", 180.0),  # Pants Suelto Liso Rojo Talla 16
            ("SKU001162", 180.0),  # Pants Suelto Liso Vino Talla 16
            ("SKU001163", 180.0),  # Pants Suelto Liso Gris Talla 16
            ("SKU001164", 180.0),  # Pants Suelto Liso Azul Marino Talla 16
            ("SKU001165", 180.0),  # Pants Suelto Liso Verde Talla 16
            ("SKU001166", 180.0),  # Pants Suelto Liso Azul Rey Talla 16
            ("SKU001167", 180.0),  # Pants Suelto Liso Blanca Talla 16
            ("SKU001168", 180.0),  # Pants Suelto Liso Bicolor Talla 16
            ("SKU001169", 180.0),  # Pants Suelto Liso Raya roja Talla 16
            ("SKU001170", 180.0),  # Pants Suelto Liso Doble raya Talla 16
            ("SKU001171", 205.0),  # Pants Suelto Liso Rojo Talla 28
            ("SKU001172", 205.0),  # Pants Suelto Liso Vino Talla 28
            ("SKU001173", 205.0),  # Pants Suelto Liso Gris Talla 28
            ("SKU001174", 205.0),  # Pants Suelto Liso Azul Marino Talla 28
            ("SKU001175", 205.0),  # Pants Suelto Liso Verde Talla 28
            ("SKU001176", 205.0),  # Pants Suelto Liso Azul Rey Talla 28
            ("SKU001177", 205.0),  # Pants Suelto Liso Blanca Talla 28
            ("SKU001178", 205.0),  # Pants Suelto Liso Bicolor Talla 28
            ("SKU001179", 205.0),  # Pants Suelto Liso Raya roja Talla 28
            ("SKU001180", 205.0),  # Pants Suelto Liso Doble raya Talla 28
            ("SKU001181", 205.0),  # Pants Suelto Liso Rojo Talla CH
            ("SKU001182", 205.0),  # Pants Suelto Liso Vino Talla CH
            ("SKU001183", 205.0),  # Pants Suelto Liso Gris Talla CH
            ("SKU001184", 205.0),  # Pants Suelto Liso Azul Marino Talla CH
            ("SKU001185", 205.0),  # Pants Suelto Liso Verde Talla CH
            ("SKU001186", 205.0),  # Pants Suelto Liso Azul Rey Talla CH
            ("SKU001187", 205.0),  # Pants Suelto Liso Blanca Talla CH
            ("SKU001188", 205.0),  # Pants Suelto Liso Bicolor Talla CH
            ("SKU001189", 205.0),  # Pants Suelto Liso Raya roja Talla CH
            ("SKU001190", 205.0),  # Pants Suelto Liso Doble raya Talla CH
            ("SKU001191", 215.0),  # Pants Suelto Liso Rojo Talla MD
            ("SKU001192", 215.0),  # Pants Suelto Liso Vino Talla MD
            ("SKU001193", 215.0),  # Pants Suelto Liso Gris Talla MD
            ("SKU001194", 215.0),  # Pants Suelto Liso Azul Marino Talla MD
            ("SKU001195", 215.0),  # Pants Suelto Liso Verde Talla MD
            ("SKU001196", 215.0),  # Pants Suelto Liso Azul Rey Talla MD
            ("SKU001197", 215.0),  # Pants Suelto Liso Blanca Talla MD
            ("SKU001198", 215.0),  # Pants Suelto Liso Bicolor Talla MD
            ("SKU001199", 215.0),  # Pants Suelto Liso Raya roja Talla MD
            ("SKU001200", 215.0),  # Pants Suelto Liso Doble raya Talla MD
            ("SKU001201", 225.0),  # Pants Suelto Liso Rojo Talla GD
            ("SKU001202", 225.0),  # Pants Suelto Liso Vino Talla GD
            ("SKU001203", 225.0),  # Pants Suelto Liso Gris Talla GD
            ("SKU001204", 225.0),  # Pants Suelto Liso Azul Marino Talla GD
            ("SKU001205", 225.0),  # Pants Suelto Liso Verde Talla GD
            ("SKU001206", 225.0),  # Pants Suelto Liso Azul Rey Talla GD
            ("SKU001207", 225.0),  # Pants Suelto Liso Blanca Talla GD
            ("SKU001208", 225.0),  # Pants Suelto Liso Bicolor Talla GD
            ("SKU001209", 225.0),  # Pants Suelto Liso Raya roja Talla GD
            ("SKU001210", 225.0),  # Pants Suelto Liso Doble raya Talla GD
            ("SKU001211", 235.0),  # Pants Suelto Liso Rojo Talla EXG
            ("SKU001212", 235.0),  # Pants Suelto Liso Vino Talla EXG
            ("SKU001213", 235.0),  # Pants Suelto Liso Gris Talla EXG
            ("SKU001214", 235.0),  # Pants Suelto Liso Azul Marino Talla EXG
            ("SKU001215", 235.0),  # Pants Suelto Liso Verde Talla EXG
            ("SKU001216", 235.0),  # Pants Suelto Liso Azul Rey Talla EXG
            ("SKU001217", 235.0),  # Pants Suelto Liso Blanca Talla EXG
            ("SKU001218", 235.0),  # Pants Suelto Liso Bicolor Talla EXG
            ("SKU001219", 235.0),  # Pants Suelto Liso Raya roja Talla EXG
            ("SKU001220", 235.0),  # Pants Suelto Liso Doble raya Talla EXG
            ("SKU001221", 195.0),  # Falda Gales rojo Talla 2
            ("SKU001222", 195.0),  # Falda Gales verde Talla 2
            ("SKU001223", 195.0),  # Falda Gales azul Talla 2
            ("SKU001224", 195.0),  # Falda Gales rojo Talla 4
            ("SKU001225", 195.0),  # Falda Gales verde Talla 4
            ("SKU001226", 195.0),  # Falda Gales azul Talla 4
            ("SKU001227", 195.0),  # Falda Gales rojo Talla 6
            ("SKU001228", 195.0),  # Falda Gales verde Talla 6
            ("SKU001229", 195.0),  # Falda Gales azul Talla 6
            ("SKU001230", 195.0),  # Falda Gales rojo Talla 8
            ("SKU001231", 195.0),  # Falda Gales verde Talla 8
            ("SKU001232", 195.0),  # Falda Gales azul Talla 8
            ("SKU001233", 205.0),  # Falda Gales rojo Talla 10
            ("SKU001234", 205.0),  # Falda Gales verde Talla 10
            ("SKU001235", 205.0),  # Falda Gales azul Talla 10
            ("SKU001236", 205.0),  # Falda Gales rojo Talla 12
            ("SKU001237", 205.0),  # Falda Gales verde Talla 12
            ("SKU001238", 205.0),  # Falda Gales azul Talla 12
            ("SKU001239", 215.0),  # Falda Gales rojo Talla 14
            ("SKU001240", 215.0),  # Falda Gales verde Talla 14
            ("SKU001241", 215.0),  # Falda Gales azul Talla 14
            ("SKU001242", 215.0),  # Falda Gales rojo Talla 16
            ("SKU001243", 215.0),  # Falda Gales verde Talla 16
            ("SKU001244", 215.0),  # Falda Gales azul Talla 16
            ("SKU001245", 225.0),  # Falda Gales rojo Talla 28
            ("SKU001246", 225.0),  # Falda Gales verde Talla 28
            ("SKU001247", 225.0),  # Falda Gales azul Talla 28
            ("SKU001248", 225.0),  # Falda Gales rojo Talla 32
            ("SKU001249", 225.0),  # Falda Gales verde Talla 32
            ("SKU001250", 225.0),  # Falda Gales azul Talla 32
            ("SKU001251", 225.0),  # Falda Gales rojo Talla 34
            ("SKU001252", 225.0),  # Falda Gales verde Talla 34
            ("SKU001253", 225.0),  # Falda Gales azul Talla 34
            ("SKU001254", 235.0),  # Falda Gales rojo Talla 36
            ("SKU001255", 235.0),  # Falda Gales verde Talla 36
            ("SKU001256", 235.0),  # Falda Gales azul Talla 36
            ("SKU001257", 235.0),  # Falda Gales rojo Talla 38
            ("SKU001258", 235.0),  # Falda Gales verde Talla 38
            ("SKU001259", 235.0),  # Falda Gales azul Talla 38
            ("SKU001260", 235.0),  # Falda Gales rojo Talla 40
            ("SKU001261", 235.0),  # Falda Gales verde Talla 40
            ("SKU001262", 235.0),  # Falda Gales azul Talla 40
            ("SKU001263", 235.0),  # Falda Gales rojo Talla 42
            ("SKU001264", 235.0),  # Falda Gales verde Talla 42
            ("SKU001265", 235.0),  # Falda Gales azul Talla 42
            ("SKU001266", 245.0),  # Falda Gales rojo Talla 44
            ("SKU001267", 245.0),  # Falda Gales verde Talla 44
            ("SKU001268", 245.0),  # Falda Gales azul Talla 44
            ("SKU001269", 225.0),  # Falda Gales rojo Talla 30
            ("SKU001270", 225.0),  # Falda Gales verde Talla 30
            ("SKU001271", 225.0),  # Falda Gales azul Talla 30
            ("SKU001571", 135.0),  # Playera Polo Blanca Talla 2
            ("SKU001572", 135.0),  # Playera Polo Blanca Talla 4
            ("SKU001573", 135.0),  # Playera Polo Blanca Talla 6
            ("SKU001574", 135.0),  # Playera Polo Blanca Talla 8
            ("SKU001575", 145.0),  # Playera Polo Blanca Talla 10
            ("SKU001576", 145.0),  # Playera Polo Blanca Talla 12
            ("SKU001577", 155.0),  # Playera Polo Blanca Talla 14
            ("SKU001578", 155.0),  # Playera Polo Blanca Talla 16
            ("SKU001579", 155.0),  # Playera Polo Blanca Talla 18
            ("SKU001580", 170.0),  # Playera Polo Blanca Talla 28
            ("SKU001581", 170.0),  # Playera Polo Blanca Talla 32
            ("SKU001582", 170.0),  # Playera Polo Blanca Talla 34
            ("SKU001583", 170.0),  # Playera Polo Blanca Talla 36
            ("SKU001584", 170.0),  # Playera Polo Blanca Talla 38
            ("SKU001585", 180.0),  # Playera Polo Blanca Talla 40
            ("SKU001586", 180.0),  # Playera Polo Blanca Talla 42
            ("SKU001587", 170.0),  # Playera Polo Blanca Talla 30
            ("SKU001588", 229.0),  # Chaleco Claudia U Rojo Talla 4
            ("SKU001589", 229.0),  # Chaleco Claudia U Blanco Talla 4
            ("SKU001590", 229.0),  # Chaleco Claudia U Vino Talla 4
            ("SKU001591", 229.0),  # Chaleco Claudia U Azul Marino Talla 4
            ("SKU001592", 229.0),  # Chaleco Claudia U Negro Talla 4
            ("SKU001593", 229.0),  # Chaleco Claudia U Verde Talla 4
            ("SKU001594", 229.0),  # Chaleco Claudia U Rojo Talla 6
            ("SKU001595", 229.0),  # Chaleco Claudia U Blanco Talla 6
            ("SKU001596", 229.0),  # Chaleco Claudia U Vino Talla 6
            ("SKU001597", 229.0),  # Chaleco Claudia U Azul Marino Talla 6
            ("SKU001598", 229.0),  # Chaleco Claudia U Negro Talla 6
            ("SKU001599", 229.0),  # Chaleco Claudia U Verde Talla 6
            ("SKU001600", 229.0),  # Chaleco Claudia U Rojo Talla 8
            ("SKU001601", 229.0),  # Chaleco Claudia U Blanco Talla 8
            ("SKU001602", 229.0),  # Chaleco Claudia U Vino Talla 8
            ("SKU001603", 229.0),  # Chaleco Claudia U Azul Marino Talla 8
            ("SKU001604", 229.0),  # Chaleco Claudia U Negro Talla 8
            ("SKU001605", 229.0),  # Chaleco Claudia U Verde Talla 8
            ("SKU001606", 239.0),  # Chaleco Claudia U Rojo Talla 10
            ("SKU001607", 239.0),  # Chaleco Claudia U Blanco Talla 10
            ("SKU001608", 239.0),  # Chaleco Claudia U Vino Talla 10
            ("SKU001609", 239.0),  # Chaleco Claudia U Azul Marino Talla 10
            ("SKU001610", 239.0),  # Chaleco Claudia U Negro Talla 10
            ("SKU001611", 239.0),  # Chaleco Claudia U Verde Talla 10
            ("SKU001612", 239.0),  # Chaleco Claudia U Rojo Talla 12
            ("SKU001613", 239.0),  # Chaleco Claudia U Blanco Talla 12
            ("SKU001614", 239.0),  # Chaleco Claudia U Vino Talla 12
            ("SKU001615", 239.0),  # Chaleco Claudia U Azul Marino Talla 12
            ("SKU001616", 239.0),  # Chaleco Claudia U Negro Talla 12
            ("SKU001617", 239.0),  # Chaleco Claudia U Verde Talla 12
            ("SKU001618", 239.0),  # Chaleco Claudia U Rojo Talla 14
            ("SKU001619", 239.0),  # Chaleco Claudia U Blanco Talla 14
            ("SKU001620", 239.0),  # Chaleco Claudia U Vino Talla 14
            ("SKU001621", 239.0),  # Chaleco Claudia U Azul Marino Talla 14
            ("SKU001622", 239.0),  # Chaleco Claudia U Negro Talla 14
            ("SKU001623", 239.0),  # Chaleco Claudia U Verde Talla 14
            ("SKU001624", 239.0),  # Chaleco Claudia U Rojo Talla 16
            ("SKU001625", 239.0),  # Chaleco Claudia U Blanco Talla 16
            ("SKU001626", 239.0),  # Chaleco Claudia U Vino Talla 16
            ("SKU001627", 239.0),  # Chaleco Claudia U Azul Marino Talla 16
            ("SKU001628", 239.0),  # Chaleco Claudia U Negro Talla 16
            ("SKU001629", 239.0),  # Chaleco Claudia U Verde Talla 16
            ("SKU001630", 259.0),  # Chaleco Claudia U Rojo Talla 28
            ("SKU001631", 259.0),  # Chaleco Claudia U Blanco Talla 28
            ("SKU001632", 259.0),  # Chaleco Claudia U Vino Talla 28
            ("SKU001633", 259.0),  # Chaleco Claudia U Azul Marino Talla 28
            ("SKU001634", 259.0),  # Chaleco Claudia U Negro Talla 28
            ("SKU001635", 259.0),  # Chaleco Claudia U Verde Talla 28
            ("SKU001636", 259.0),  # Chaleco Claudia U Rojo Talla 32
            ("SKU001637", 259.0),  # Chaleco Claudia U Blanco Talla 32
            ("SKU001638", 259.0),  # Chaleco Claudia U Vino Talla 32
            ("SKU001639", 259.0),  # Chaleco Claudia U Azul Marino Talla 32
            ("SKU001640", 259.0),  # Chaleco Claudia U Negro Talla 32
            ("SKU001641", 259.0),  # Chaleco Claudia U Verde Talla 32
            ("SKU001642", 259.0),  # Chaleco Claudia U Rojo Talla 34
            ("SKU001643", 259.0),  # Chaleco Claudia U Blanco Talla 34
            ("SKU001644", 259.0),  # Chaleco Claudia U Vino Talla 34
            ("SKU001645", 259.0),  # Chaleco Claudia U Azul Marino Talla 34
            ("SKU001646", 259.0),  # Chaleco Claudia U Negro Talla 34
            ("SKU001647", 259.0),  # Chaleco Claudia U Verde Talla 34
            ("SKU001648", 269.0),  # Chaleco Claudia U Rojo Talla 36
            ("SKU001649", 269.0),  # Chaleco Claudia U Blanco Talla 36
            ("SKU001650", 269.0),  # Chaleco Claudia U Vino Talla 36
            ("SKU001651", 269.0),  # Chaleco Claudia U Azul Marino Talla 36
            ("SKU001652", 269.0),  # Chaleco Claudia U Negro Talla 36
            ("SKU001653", 269.0),  # Chaleco Claudia U Verde Talla 36
            ("SKU001654", 269.0),  # Chaleco Claudia U Rojo Talla 38
            ("SKU001655", 269.0),  # Chaleco Claudia U Blanco Talla 38
            ("SKU001656", 269.0),  # Chaleco Claudia U Vino Talla 38
            ("SKU001657", 269.0),  # Chaleco Claudia U Azul Marino Talla 38
            ("SKU001658", 269.0),  # Chaleco Claudia U Negro Talla 38
            ("SKU001659", 269.0),  # Chaleco Claudia U Verde Talla 38
            ("SKU001660", 269.0),  # Chaleco Claudia U Rojo Talla 40
            ("SKU001661", 269.0),  # Chaleco Claudia U Blanco Talla 40
            ("SKU001662", 269.0),  # Chaleco Claudia U Vino Talla 40
            ("SKU001663", 269.0),  # Chaleco Claudia U Azul Marino Talla 40
            ("SKU001664", 269.0),  # Chaleco Claudia U Negro Talla 40
            ("SKU001665", 269.0),  # Chaleco Claudia U Verde Talla 40
            ("SKU001666", 269.0),  # Chaleco Claudia U Rojo Talla 42
            ("SKU001667", 269.0),  # Chaleco Claudia U Blanco Talla 42
            ("SKU001668", 269.0),  # Chaleco Claudia U Vino Talla 42
            ("SKU001669", 269.0),  # Chaleco Claudia U Azul Marino Talla 42
            ("SKU001670", 269.0),  # Chaleco Claudia U Negro Talla 42
            ("SKU001671", 269.0),  # Chaleco Claudia U Verde Talla 42
            ("SKU001672", 269.0),  # Chaleco Claudia U Rojo Talla 44
            ("SKU001673", 269.0),  # Chaleco Claudia U Blanco Talla 44
            ("SKU001674", 269.0),  # Chaleco Claudia U Vino Talla 44
            ("SKU001675", 269.0),  # Chaleco Claudia U Azul Marino Talla 44
            ("SKU001676", 269.0),  # Chaleco Claudia U Negro Talla 44
            ("SKU001677", 269.0),  # Chaleco Claudia U Verde Talla 44
            ("SKU001678", 269.0),  # Chaleco Claudia U Rojo Talla 46
            ("SKU001679", 269.0),  # Chaleco Claudia U Blanco Talla 46
            ("SKU001680", 269.0),  # Chaleco Claudia U Vino Talla 46
            ("SKU001681", 269.0),  # Chaleco Claudia U Azul Marino Talla 46
            ("SKU001682", 269.0),  # Chaleco Claudia U Negro Talla 46
            ("SKU001683", 269.0),  # Chaleco Claudia U Verde Talla 46
            ("SKU001684", 259.0),  # Chaleco Claudia U Rojo Talla 30
            ("SKU001685", 259.0),  # Chaleco Claudia U Blanco Talla 30
            ("SKU001686", 259.0),  # Chaleco Claudia U Vino Talla 30
            ("SKU001687", 259.0),  # Chaleco Claudia U Azul Marino Talla 30
            ("SKU001688", 259.0),  # Chaleco Claudia U Negro Talla 30
            ("SKU001689", 259.0),  # Chaleco Claudia U Verde Talla 30
            ("SKU001690", 289.0),  # Suéter Claudia Botones M Rojo Talla 4
            ("SKU001691", 289.0),  # Suéter Claudia Botones M Blanco Talla 4
            ("SKU001692", 289.0),  # Suéter Claudia Botones M Vino Talla 4
            ("SKU001693", 289.0),  # Suéter Claudia Botones M Azul Marino Talla 4
            ("SKU001694", 289.0),  # Suéter Claudia Botones M Negro Talla 4
            ("SKU001695", 289.0),  # Suéter Claudia Botones M Verde Talla 4
            ("SKU001696", 289.0),  # Suéter Claudia Botones M Azul Rey Talla 4
            ("SKU001697", 289.0),  # Suéter Claudia Botones M Rojo Talla 6
            ("SKU001698", 289.0),  # Suéter Claudia Botones M Blanco Talla 6
            ("SKU001699", 289.0),  # Suéter Claudia Botones M Vino Talla 6
            ("SKU001700", 289.0),  # Suéter Claudia Botones M Azul Marino Talla 6
            ("SKU001701", 289.0),  # Suéter Claudia Botones M Negro Talla 6
            ("SKU001702", 289.0),  # Suéter Claudia Botones M Verde Talla 6
            ("SKU001703", 289.0),  # Suéter Claudia Botones M Azul Rey Talla 6
            ("SKU001704", 289.0),  # Suéter Claudia Botones M Rojo Talla 8
            ("SKU001705", 289.0),  # Suéter Claudia Botones M Blanco Talla 8
            ("SKU001706", 289.0),  # Suéter Claudia Botones M Vino Talla 8
            ("SKU001707", 289.0),  # Suéter Claudia Botones M Azul Marino Talla 8
            ("SKU001708", 289.0),  # Suéter Claudia Botones M Negro Talla 8
            ("SKU001709", 289.0),  # Suéter Claudia Botones M Verde Talla 8
            ("SKU001710", 289.0),  # Suéter Claudia Botones M Azul Rey Talla 8
            ("SKU001711", 299.0),  # Suéter Claudia Botones M Rojo Talla 10
            ("SKU001712", 299.0),  # Suéter Claudia Botones M Blanco Talla 10
            ("SKU001713", 299.0),  # Suéter Claudia Botones M Vino Talla 10
            ("SKU001714", 299.0),  # Suéter Claudia Botones M Azul Marino Talla 10
            ("SKU001715", 299.0),  # Suéter Claudia Botones M Negro Talla 10
            ("SKU001716", 299.0),  # Suéter Claudia Botones M Verde Talla 10
            ("SKU001717", 299.0),  # Suéter Claudia Botones M Azul Rey Talla 10
            ("SKU001718", 299.0),  # Suéter Claudia Botones M Rojo Talla 12
            ("SKU001719", 299.0),  # Suéter Claudia Botones M Blanco Talla 12
            ("SKU001720", 299.0),  # Suéter Claudia Botones M Vino Talla 12
            ("SKU001721", 299.0),  # Suéter Claudia Botones M Azul Marino Talla 12
            ("SKU001722", 299.0),  # Suéter Claudia Botones M Negro Talla 12
            ("SKU001723", 299.0),  # Suéter Claudia Botones M Verde Talla 12
            ("SKU001724", 299.0),  # Suéter Claudia Botones M Azul Rey Talla 12
            ("SKU001725", 299.0),  # Suéter Claudia Botones M Rojo Talla 14
            ("SKU001726", 299.0),  # Suéter Claudia Botones M Blanco Talla 14
            ("SKU001727", 299.0),  # Suéter Claudia Botones M Vino Talla 14
            ("SKU001728", 299.0),  # Suéter Claudia Botones M Azul Marino Talla 14
            ("SKU001729", 299.0),  # Suéter Claudia Botones M Negro Talla 14
            ("SKU001730", 299.0),  # Suéter Claudia Botones M Verde Talla 14
            ("SKU001731", 299.0),  # Suéter Claudia Botones M Azul Rey Talla 14
            ("SKU001732", 299.0),  # Suéter Claudia Botones M Rojo Talla 16
            ("SKU001733", 299.0),  # Suéter Claudia Botones M Blanco Talla 16
            ("SKU001734", 299.0),  # Suéter Claudia Botones M Vino Talla 16
            ("SKU001735", 299.0),  # Suéter Claudia Botones M Azul Marino Talla 16
            ("SKU001736", 299.0),  # Suéter Claudia Botones M Negro Talla 16
            ("SKU001737", 299.0),  # Suéter Claudia Botones M Verde Talla 16
            ("SKU001738", 299.0),  # Suéter Claudia Botones M Azul Rey Talla 16
            ("SKU001739", 309.0),  # Suéter Claudia Botones M Rojo Talla 28
            ("SKU001740", 309.0),  # Suéter Claudia Botones M Blanco Talla 28
            ("SKU001741", 309.0),  # Suéter Claudia Botones M Vino Talla 28
            ("SKU001743", 309.0),  # Suéter Claudia Botones M Negro Talla 28
            ("SKU001744", 309.0),  # Suéter Claudia Botones M Verde Talla 28
            ("SKU001746", 309.0),  # Suéter Claudia Botones M Rojo Talla 32
            ("SKU001747", 309.0),  # Suéter Claudia Botones M Blanco Talla 32
            ("SKU001748", 309.0),  # Suéter Claudia Botones M Vino Talla 32
            ("SKU001749", 309.0),  # Suéter Claudia Botones M Azul Marino Talla 32
            ("SKU001750", 309.0),  # Suéter Claudia Botones M Negro Talla 32
            ("SKU001751", 309.0),  # Suéter Claudia Botones M Verde Talla 32
            ("SKU001753", 309.0),  # Suéter Claudia Botones M Rojo Talla 34
            ("SKU001754", 309.0),  # Suéter Claudia Botones M Blanco Talla 34
            ("SKU001755", 309.0),  # Suéter Claudia Botones M Vino Talla 34
            ("SKU001756", 309.0),  # Suéter Claudia Botones M Azul Marino Talla 34
            ("SKU001757", 309.0),  # Suéter Claudia Botones M Negro Talla 34
            ("SKU001758", 309.0),  # Suéter Claudia Botones M Verde Talla 34
            ("SKU001759", 309.0),  # Suéter Claudia Botones M Azul Rey Talla 34
            ("SKU001760", 309.0),  # Suéter Claudia Botones M Rojo Talla 36
            ("SKU001761", 309.0),  # Suéter Claudia Botones M Blanco Talla 36
            ("SKU001762", 309.0),  # Suéter Claudia Botones M Vino Talla 36
            ("SKU001763", 309.0),  # Suéter Claudia Botones M Azul Marino Talla 36
            ("SKU001764", 309.0),  # Suéter Claudia Botones M Negro Talla 36
            ("SKU001765", 309.0),  # Suéter Claudia Botones M Verde Talla 36
            ("SKU001766", 309.0),  # Suéter Claudia Botones M Azul Rey Talla 36
            ("SKU001767", 315.0),  # Suéter Claudia Botones M Rojo Talla 38
            ("SKU001768", 315.0),  # Suéter Claudia Botones M Blanco Talla 38
            ("SKU001769", 315.0),  # Suéter Claudia Botones M Vino Talla 38
            ("SKU001770", 315.0),  # Suéter Claudia Botones M Azul Marino Talla 38
            ("SKU001771", 315.0),  # Suéter Claudia Botones M Negro Talla 38
            ("SKU001772", 315.0),  # Suéter Claudia Botones M Verde Talla 38
            ("SKU001774", 315.0),  # Suéter Claudia Botones M Rojo Talla 40
            ("SKU001775", 315.0),  # Suéter Claudia Botones M Blanco Talla 40
            ("SKU001776", 315.0),  # Suéter Claudia Botones M Vino Talla 40
            ("SKU001777", 315.0),  # Suéter Claudia Botones M Azul Marino Talla 40
            ("SKU001778", 315.0),  # Suéter Claudia Botones M Negro Talla 40
            ("SKU001779", 315.0),  # Suéter Claudia Botones M Verde Talla 40
            ("SKU001781", 315.0),  # Suéter Claudia Botones M Rojo Talla 42
            ("SKU001782", 315.0),  # Suéter Claudia Botones M Blanco Talla 42
            ("SKU001783", 315.0),  # Suéter Claudia Botones M Vino Talla 42
            ("SKU001784", 315.0),  # Suéter Claudia Botones M Azul Marino Talla 42
            ("SKU001785", 315.0),  # Suéter Claudia Botones M Negro Talla 42
            ("SKU001786", 315.0),  # Suéter Claudia Botones M Verde Talla 42
            ("SKU001788", 325.0),  # Suéter Claudia Botones M Rojo Talla 44
            ("SKU001789", 325.0),  # Suéter Claudia Botones M Blanco Talla 44
            ("SKU001790", 325.0),  # Suéter Claudia Botones M Vino Talla 44
            ("SKU001791", 325.0),  # Suéter Claudia Botones M Azul Marino Talla 44
            ("SKU001792", 325.0),  # Suéter Claudia Botones M Negro Talla 44
            ("SKU001793", 325.0),  # Suéter Claudia Botones M Verde Talla 44
            ("SKU001795", 325.0),  # Suéter Claudia Botones M Rojo Talla 46
            ("SKU001796", 325.0),  # Suéter Claudia Botones M Blanco Talla 46
            ("SKU001797", 325.0),  # Suéter Claudia Botones M Vino Talla 46
            ("SKU001798", 325.0),  # Suéter Claudia Botones M Azul Marino Talla 46
            ("SKU001799", 325.0),  # Suéter Claudia Botones M Negro Talla 46
            ("SKU001800", 325.0),  # Suéter Claudia Botones M Verde Talla 46
            ("SKU001802", 309.0),  # Suéter Claudia Botones M Rojo Talla 30
            ("SKU001803", 309.0),  # Suéter Claudia Botones M Blanco Talla 30
            ("SKU001804", 309.0),  # Suéter Claudia Botones M Vino Talla 30
            ("SKU001806", 309.0),  # Suéter Claudia Botones M Negro Talla 30
            ("SKU001807", 309.0),  # Suéter Claudia Botones M Verde Talla 30
            ("SKU001809", 289.0),  # Suéter Claudia Cuello V H Rojo Talla 4
            ("SKU001810", 289.0),  # Suéter Claudia Cuello V H Blanco Talla 4
            ("SKU001811", 289.0),  # Suéter Claudia Cuello V H Vino Talla 4
            ("SKU001812", 289.0),  # Suéter Claudia Cuello V H Azul Marino Talla 4
            ("SKU001813", 289.0),  # Suéter Claudia Cuello V H Negro Talla 4
            ("SKU001814", 289.0),  # Suéter Claudia Cuello V H Verde Talla 4
            ("SKU001815", 289.0),  # Suéter Claudia Cuello V H Azul Rey Talla 4
            ("SKU001816", 289.0),  # Suéter Claudia Cuello V H Rojo Talla 6
            ("SKU001817", 289.0),  # Suéter Claudia Cuello V H Blanco Talla 6
            ("SKU001818", 289.0),  # Suéter Claudia Cuello V H Vino Talla 6
            ("SKU001819", 289.0),  # Suéter Claudia Cuello V H Azul Marino Talla 6
            ("SKU001820", 289.0),  # Suéter Claudia Cuello V H Negro Talla 6
            ("SKU001821", 289.0),  # Suéter Claudia Cuello V H Verde Talla 6
            ("SKU001822", 289.0),  # Suéter Claudia Cuello V H Azul Rey Talla 6
            ("SKU001823", 289.0),  # Suéter Claudia Cuello V H Rojo Talla 8
            ("SKU001824", 289.0),  # Suéter Claudia Cuello V H Blanco Talla 8
            ("SKU001825", 289.0),  # Suéter Claudia Cuello V H Vino Talla 8
            ("SKU001826", 289.0),  # Suéter Claudia Cuello V H Azul Marino Talla 8
            ("SKU001827", 289.0),  # Suéter Claudia Cuello V H Negro Talla 8
            ("SKU001828", 289.0),  # Suéter Claudia Cuello V H Verde Talla 8
            ("SKU001829", 289.0),  # Suéter Claudia Cuello V H Azul Rey Talla 8
            ("SKU001830", 299.0),  # Suéter Claudia Cuello V H Rojo Talla 10
            ("SKU001831", 299.0),  # Suéter Claudia Cuello V H Blanco Talla 10
            ("SKU001832", 299.0),  # Suéter Claudia Cuello V H Vino Talla 10
            ("SKU001833", 299.0),  # Suéter Claudia Cuello V H Azul Marino Talla 10
            ("SKU001834", 299.0),  # Suéter Claudia Cuello V H Negro Talla 10
            ("SKU001835", 299.0),  # Suéter Claudia Cuello V H Verde Talla 10
            ("SKU001836", 299.0),  # Suéter Claudia Cuello V H Azul Rey Talla 10
            ("SKU001837", 299.0),  # Suéter Claudia Cuello V H Rojo Talla 12
            ("SKU001838", 299.0),  # Suéter Claudia Cuello V H Blanco Talla 12
            ("SKU001839", 299.0),  # Suéter Claudia Cuello V H Vino Talla 12
            ("SKU001840", 299.0),  # Suéter Claudia Cuello V H Azul Marino Talla 12
            ("SKU001841", 299.0),  # Suéter Claudia Cuello V H Negro Talla 12
            ("SKU001842", 299.0),  # Suéter Claudia Cuello V H Verde Talla 12
            ("SKU001843", 299.0),  # Suéter Claudia Cuello V H Azul Rey Talla 12
            ("SKU001844", 299.0),  # Suéter Claudia Cuello V H Rojo Talla 14
            ("SKU001845", 299.0),  # Suéter Claudia Cuello V H Blanco Talla 14
            ("SKU001846", 299.0),  # Suéter Claudia Cuello V H Vino Talla 14
            ("SKU001847", 299.0),  # Suéter Claudia Cuello V H Azul Marino Talla 14
            ("SKU001848", 299.0),  # Suéter Claudia Cuello V H Negro Talla 14
            ("SKU001849", 299.0),  # Suéter Claudia Cuello V H Verde Talla 14
            ("SKU001850", 299.0),  # Suéter Claudia Cuello V H Azul Rey Talla 14
            ("SKU001851", 299.0),  # Suéter Claudia Cuello V H Rojo Talla 16
            ("SKU001852", 299.0),  # Suéter Claudia Cuello V H Blanco Talla 16
            ("SKU001853", 299.0),  # Suéter Claudia Cuello V H Vino Talla 16
            ("SKU001854", 299.0),  # Suéter Claudia Cuello V H Azul Marino Talla 16
            ("SKU001855", 299.0),  # Suéter Claudia Cuello V H Negro Talla 16
            ("SKU001856", 299.0),  # Suéter Claudia Cuello V H Verde Talla 16
            ("SKU001857", 299.0),  # Suéter Claudia Cuello V H Azul Rey Talla 16
            ("SKU001858", 309.0),  # Suéter Claudia Cuello V H Rojo Talla 28
            ("SKU001859", 309.0),  # Suéter Claudia Cuello V H Blanco Talla 28
            ("SKU001860", 309.0),  # Suéter Claudia Cuello V H Vino Talla 28
            ("SKU001861", 309.0),  # Suéter Claudia Cuello V H Azul Marino Talla 28
            ("SKU001862", 309.0),  # Suéter Claudia Cuello V H Negro Talla 28
            ("SKU001863", 309.0),  # Suéter Claudia Cuello V H Verde Talla 28
            ("SKU001864", 309.0),  # Suéter Claudia Cuello V H Azul Rey Talla 28
            ("SKU001865", 309.0),  # Suéter Claudia Cuello V H Rojo Talla 32
            ("SKU001866", 309.0),  # Suéter Claudia Cuello V H Blanco Talla 32
            ("SKU001867", 309.0),  # Suéter Claudia Cuello V H Vino Talla 32
            ("SKU001868", 309.0),  # Suéter Claudia Cuello V H Azul Marino Talla 32
            ("SKU001869", 309.0),  # Suéter Claudia Cuello V H Negro Talla 32
            ("SKU001870", 309.0),  # Suéter Claudia Cuello V H Verde Talla 32
            ("SKU001871", 309.0),  # Suéter Claudia Cuello V H Azul Rey Talla 32
            ("SKU001872", 309.0),  # Suéter Claudia Cuello V H Rojo Talla 34
            ("SKU001873", 309.0),  # Suéter Claudia Cuello V H Blanco Talla 34
            ("SKU001874", 309.0),  # Suéter Claudia Cuello V H Vino Talla 34
            ("SKU001875", 309.0),  # Suéter Claudia Cuello V H Azul Marino Talla 34
            ("SKU001876", 309.0),  # Suéter Claudia Cuello V H Negro Talla 34
            ("SKU001877", 309.0),  # Suéter Claudia Cuello V H Verde Talla 34
            ("SKU001878", 309.0),  # Suéter Claudia Cuello V H Azul Rey Talla 34
            ("SKU001879", 309.0),  # Suéter Claudia Cuello V H Rojo Talla 36
            ("SKU001880", 309.0),  # Suéter Claudia Cuello V H Blanco Talla 36
            ("SKU001881", 309.0),  # Suéter Claudia Cuello V H Vino Talla 36
            ("SKU001882", 309.0),  # Suéter Claudia Cuello V H Azul Marino Talla 36
            ("SKU001883", 309.0),  # Suéter Claudia Cuello V H Negro Talla 36
            ("SKU001884", 309.0),  # Suéter Claudia Cuello V H Verde Talla 36
            ("SKU001886", 315.0),  # Suéter Claudia Cuello V H Rojo Talla 38
            ("SKU001887", 315.0),  # Suéter Claudia Cuello V H Blanco Talla 38
            ("SKU001888", 315.0),  # Suéter Claudia Cuello V H Vino Talla 38
            ("SKU001889", 315.0),  # Suéter Claudia Cuello V H Azul Marino Talla 38
            ("SKU001890", 315.0),  # Suéter Claudia Cuello V H Negro Talla 38
            ("SKU001891", 315.0),  # Suéter Claudia Cuello V H Verde Talla 38
            ("SKU001893", 315.0),  # Suéter Claudia Cuello V H Rojo Talla 40
            ("SKU001894", 315.0),  # Suéter Claudia Cuello V H Blanco Talla 40
            ("SKU001895", 315.0),  # Suéter Claudia Cuello V H Vino Talla 40
            ("SKU001896", 315.0),  # Suéter Claudia Cuello V H Azul Marino Talla 40
            ("SKU001897", 315.0),  # Suéter Claudia Cuello V H Negro Talla 40
            ("SKU001898", 315.0),  # Suéter Claudia Cuello V H Verde Talla 40
            ("SKU001900", 315.0),  # Suéter Claudia Cuello V H Rojo Talla 42
            ("SKU001901", 315.0),  # Suéter Claudia Cuello V H Blanco Talla 42
            ("SKU001902", 315.0),  # Suéter Claudia Cuello V H Vino Talla 42
            ("SKU001903", 315.0),  # Suéter Claudia Cuello V H Azul Marino Talla 42
            ("SKU001904", 315.0),  # Suéter Claudia Cuello V H Negro Talla 42
            ("SKU001905", 315.0),  # Suéter Claudia Cuello V H Verde Talla 42
            ("SKU001907", 325.0),  # Suéter Claudia Cuello V H Rojo Talla 44
            ("SKU001908", 325.0),  # Suéter Claudia Cuello V H Blanco Talla 44
            ("SKU001909", 325.0),  # Suéter Claudia Cuello V H Vino Talla 44
            ("SKU001910", 325.0),  # Suéter Claudia Cuello V H Azul Marino Talla 44
            ("SKU001911", 325.0),  # Suéter Claudia Cuello V H Negro Talla 44
            ("SKU001912", 325.0),  # Suéter Claudia Cuello V H Verde Talla 44
            ("SKU001914", 325.0),  # Suéter Claudia Cuello V H Rojo Talla 46
            ("SKU001915", 325.0),  # Suéter Claudia Cuello V H Blanco Talla 46
            ("SKU001916", 325.0),  # Suéter Claudia Cuello V H Vino Talla 46
            ("SKU001917", 325.0),  # Suéter Claudia Cuello V H Azul Marino Talla 46
            ("SKU001918", 325.0),  # Suéter Claudia Cuello V H Negro Talla 46
            ("SKU001919", 325.0),  # Suéter Claudia Cuello V H Verde Talla 46
            ("SKU001921", 309.0),  # Suéter Claudia Cuello V H Rojo Talla 30
            ("SKU001922", 309.0),  # Suéter Claudia Cuello V H Blanco Talla 30
            ("SKU001923", 309.0),  # Suéter Claudia Cuello V H Vino Talla 30
            ("SKU001924", 309.0),  # Suéter Claudia Cuello V H Azul Marino Talla 30
            ("SKU001925", 309.0),  # Suéter Claudia Cuello V H Negro Talla 30
            ("SKU001926", 309.0),  # Suéter Claudia Cuello V H Verde Talla 30
            ("SKU001927", 309.0),  # Suéter Claudia Cuello V H Azul Rey Talla 30
            ("SKU001928", 185.0),  # Playera Chazarilla Rojo Talla 4
            ("SKU001929", 185.0),  # Playera Chazarilla Azul Marino Talla 4
            ("SKU001930", 185.0),  # Playera Chazarilla Verde Talla 4
            ("SKU001931", 185.0),  # Playera Chazarilla Rojo Talla 6
            ("SKU001932", 185.0),  # Playera Chazarilla Azul Marino Talla 6
            ("SKU001933", 185.0),  # Playera Chazarilla Verde Talla 6
            ("SKU001934", 185.0),  # Playera Chazarilla Rojo Talla 8
            ("SKU001935", 185.0),  # Playera Chazarilla Azul Marino Talla 8
            ("SKU001936", 185.0),  # Playera Chazarilla Verde Talla 8
            ("SKU001937", 185.0),  # Playera Chazarilla Rojo Talla 10
            ("SKU001938", 185.0),  # Playera Chazarilla Azul Marino Talla 10
            ("SKU001939", 185.0),  # Playera Chazarilla Verde Talla 10
            ("SKU001940", 185.0),  # Playera Chazarilla Rojo Talla 12
            ("SKU001941", 185.0),  # Playera Chazarilla Azul Marino Talla 12
            ("SKU001942", 185.0),  # Playera Chazarilla Verde Talla 12
            ("SKU001943", 190.0),  # Playera Chazarilla Rojo Talla 14
            ("SKU001944", 190.0),  # Playera Chazarilla Azul Marino Talla 14
            ("SKU001945", 190.0),  # Playera Chazarilla Verde Talla 14
            ("SKU001946", 190.0),  # Playera Chazarilla Rojo Talla 16
            ("SKU001947", 190.0),  # Playera Chazarilla Azul Marino Talla 16
            ("SKU001948", 190.0),  # Playera Chazarilla Verde Talla 16
            ("SKU001949", 199.0),  # Playera Chazarilla Rojo Talla 32
            ("SKU001950", 199.0),  # Playera Chazarilla Azul Marino Talla 32
            ("SKU001951", 199.0),  # Playera Chazarilla Verde Talla 32
            ("SKU001952", 199.0),  # Playera Chazarilla Rojo Talla 34
            ("SKU001953", 199.0),  # Playera Chazarilla Azul Marino Talla 34
            ("SKU001954", 199.0),  # Playera Chazarilla Verde Talla 34
            ("SKU001955", 205.0),  # Playera Chazarilla Rojo Talla 36
            ("SKU001956", 205.0),  # Playera Chazarilla Azul Marino Talla 36
            ("SKU001957", 205.0),  # Playera Chazarilla Verde Talla 36
            ("SKU001958", 205.0),  # Playera Chazarilla Rojo Talla 38
            ("SKU001959", 205.0),  # Playera Chazarilla Azul Marino Talla 38
            ("SKU001960", 205.0),  # Playera Chazarilla Verde Talla 38
            ("SKU001961", 209.0),  # Playera Chazarilla Rojo Talla 40
            ("SKU001962", 209.0),  # Playera Chazarilla Azul Marino Talla 40
            ("SKU001963", 209.0),  # Playera Chazarilla Verde Talla 40
            ("SKU001964", 209.0),  # Playera Chazarilla Rojo Talla 42
            ("SKU001965", 209.0),  # Playera Chazarilla Azul Marino Talla 42
            ("SKU001966", 209.0),  # Playera Chazarilla Verde Talla 42
            ("SKU001987", 545.0),  # Pants 3pz Deportivo Blanca Verónica Soto Martínez Príncipes Talla 2
            ("SKU001988", 545.0),  # Pants 3pz Deportivo Frida Kahlo Talla 2
            ("SKU001989", 545.0),  # Pants 3pz Deportivo Jean Piaget Talla 2
            ("SKU001990", 545.0),  # Pants 3pz Deportivo Jorge Cantor Talla 2
            ("SKU001991", 545.0),  # Pants 3pz Deportivo Patria Talla 2
            ("SKU001992", 545.0),  # Pants 3pz Deportivo Álvaro Obregón Talla 2
            ("SKU001993", 545.0),  # Pants 3pz Deportivo Blanca Verónica Soto Martínez Príncipes Talla 4
            ("SKU001994", 545.0),  # Pants 3pz Deportivo Frida Kahlo Talla 4
            ("SKU001995", 545.0),  # Pants 3pz Deportivo Jean Piaget Talla 4
            ("SKU001996", 545.0),  # Pants 3pz Deportivo Jorge Cantor Talla 4
            ("SKU001997", 545.0),  # Pants 3pz Deportivo Patria Talla 4
            ("SKU001998", 545.0),  # Pants 3pz Deportivo Álvaro Obregón Talla 4
            ("SKU001999", 545.0),  # Pants 3pz Deportivo Blanca Verónica Soto Martínez Príncipes Talla 6
            ("SKU002000", 545.0),  # Pants 3pz Deportivo Frida Kahlo Talla 6
            ("SKU002001", 545.0),  # Pants 3pz Deportivo Jean Piaget Talla 6
            ("SKU002002", 545.0),  # Pants 3pz Deportivo Jorge Cantor Talla 6
            ("SKU002003", 545.0),  # Pants 3pz Deportivo Patria Talla 6
            ("SKU002004", 545.0),  # Pants 3pz Deportivo Álvaro Obregón Talla 6
            ("SKU002005", 545.0),  # Pants 3pz Deportivo Blanca Verónica Soto Martínez Príncipes Talla 8
            ("SKU002006", 545.0),  # Pants 3pz Deportivo Frida Kahlo Talla 8
            ("SKU002007", 545.0),  # Pants 3pz Deportivo Jean Piaget Talla 8
            ("SKU002008", 545.0),  # Pants 3pz Deportivo Jorge Cantor Talla 8
            ("SKU002009", 545.0),  # Pants 3pz Deportivo Patria Talla 8
            ("SKU002010", 545.0),  # Pants 3pz Deportivo Álvaro Obregón Talla 8
            ("SKU002011", 445.0),  # Pants 2pz Deportivo Blanca Verónica Soto Martínez Príncipes Talla 2
            ("SKU002012", 445.0),  # Pants 2pz Deportivo Frida Kahlo Talla 2
            ("SKU002013", 445.0),  # Pants 2pz Deportivo Jean Piaget Talla 2
            ("SKU002014", 445.0),  # Pants 2pz Deportivo Jorge Cantor Talla 2
            ("SKU002015", 445.0),  # Pants 2pz Deportivo Patria Talla 2
            ("SKU002016", 445.0),  # Pants 2pz Deportivo Álvaro Obregón Talla 2
            ("SKU002017", 445.0),  # Pants 2pz Deportivo Blanca Verónica Soto Martínez Príncipes Talla 4
            ("SKU002018", 445.0),  # Pants 2pz Deportivo Frida Kahlo Talla 4
            ("SKU002019", 445.0),  # Pants 2pz Deportivo Jean Piaget Talla 4
            ("SKU002020", 445.0),  # Pants 2pz Deportivo Jorge Cantor Talla 4
            ("SKU002021", 445.0),  # Pants 2pz Deportivo Patria Talla 4
            ("SKU002022", 445.0),  # Pants 2pz Deportivo Álvaro Obregón Talla 4
            ("SKU002023", 445.0),  # Pants 2pz Deportivo Blanca Verónica Soto Martínez Príncipes Talla 6
            ("SKU002024", 445.0),  # Pants 2pz Deportivo Frida Kahlo Talla 6
            ("SKU002025", 445.0),  # Pants 2pz Deportivo Jean Piaget Talla 6
            ("SKU002026", 445.0),  # Pants 2pz Deportivo Jorge Cantor Talla 6
            ("SKU002027", 445.0),  # Pants 2pz Deportivo Patria Talla 6
            ("SKU002028", 445.0),  # Pants 2pz Deportivo Álvaro Obregón Talla 6
            ("SKU002029", 445.0),  # Pants 2pz Deportivo Blanca Verónica Soto Martínez Príncipes Talla 8
            ("SKU002030", 445.0),  # Pants 2pz Deportivo Frida Kahlo Talla 8
            ("SKU002031", 445.0),  # Pants 2pz Deportivo Jean Piaget Talla 8
            ("SKU002032", 445.0),  # Pants 2pz Deportivo Jorge Cantor Talla 8
            ("SKU002033", 445.0),  # Pants 2pz Deportivo Patria Talla 8
            ("SKU002034", 445.0),  # Pants 2pz Deportivo Álvaro Obregón Talla 8
            ("SKU002035", 585.0),  # Pants 3pz Deportivo Albino García Ramos Talla 4
            ("SKU002036", 585.0),  # Pants 3pz Deportivo Benito Juárez Talla 4
            ("SKU002037", 585.0),  # Pants 3pz Deportivo Club Rotario Talla 4
            ("SKU002038", 585.0),  # Pants 3pz Deportivo Emiliano Zapata Talla 4
            ("SKU002039", 585.0),  # Pants 3pz Deportivo Francisco Villa Talla 4
            ("SKU002040", 585.0),  # Pants 3pz Deportivo Himno Nacional Talla 4
            ("SKU002041", 585.0),  # Pants 3pz Deportivo Ignacio Allende Talla 4
            ("SKU002042", 585.0),  # Pants 3pz Deportivo J. Guadalupe Victoria Talla 4
            ("SKU002043", 585.0),  # Pants 3pz Deportivo José María Morelos Talla 4
            ("SKU002044", 585.0),  # Pants 3pz Deportivo José María Morelos y Pavón Talla 4
            ("SKU002045", 585.0),  # Pants 3pz Deportivo Justo Sierra Talla 4
            ("SKU002047", 585.0),  # Pants 3pz Deportivo Niños Héroes Talla 4
            ("SKU002048", 585.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 4
            ("SKU002049", 585.0),  # Pants 3pz Deportivo Albino García Ramos Talla 6
            ("SKU002050", 585.0),  # Pants 3pz Deportivo Benito Juárez Talla 6
            ("SKU002051", 585.0),  # Pants 3pz Deportivo Club Rotario Talla 6
            ("SKU002052", 585.0),  # Pants 3pz Deportivo Emiliano Zapata Talla 6
            ("SKU002053", 585.0),  # Pants 3pz Deportivo Francisco Villa Talla 6
            ("SKU002054", 585.0),  # Pants 3pz Deportivo Himno Nacional Talla 6
            ("SKU002055", 585.0),  # Pants 3pz Deportivo Ignacio Allende Talla 6
            ("SKU002056", 585.0),  # Pants 3pz Deportivo J. Guadalupe Victoria Talla 6
            ("SKU002057", 585.0),  # Pants 3pz Deportivo José María Morelos Talla 6
            ("SKU002058", 585.0),  # Pants 3pz Deportivo José María Morelos y Pavón Talla 6
            ("SKU002059", 585.0),  # Pants 3pz Deportivo Justo Sierra Talla 6
            ("SKU002061", 585.0),  # Pants 3pz Deportivo Niños Héroes Talla 6
            ("SKU002062", 585.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 6
            ("SKU002063", 585.0),  # Pants 3pz Deportivo Albino García Ramos Talla 8
            ("SKU002064", 585.0),  # Pants 3pz Deportivo Benito Juárez Talla 8
            ("SKU002065", 585.0),  # Pants 3pz Deportivo Club Rotario Talla 8
            ("SKU002066", 585.0),  # Pants 3pz Deportivo Emiliano Zapata Talla 8
            ("SKU002067", 585.0),  # Pants 3pz Deportivo Francisco Villa Talla 8
            ("SKU002068", 585.0),  # Pants 3pz Deportivo Himno Nacional Talla 8
            ("SKU002069", 585.0),  # Pants 3pz Deportivo Ignacio Allende Talla 8
            ("SKU002070", 585.0),  # Pants 3pz Deportivo J. Guadalupe Victoria Talla 8
            ("SKU002071", 585.0),  # Pants 3pz Deportivo José María Morelos Talla 8
            ("SKU002072", 585.0),  # Pants 3pz Deportivo José María Morelos y Pavón Talla 8
            ("SKU002073", 585.0),  # Pants 3pz Deportivo Justo Sierra Talla 8
            ("SKU002075", 585.0),  # Pants 3pz Deportivo Niños Héroes Talla 8
            ("SKU002076", 585.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 8
            ("SKU002077", 585.0),  # Pants 3pz Deportivo Miguel Campuzano Talla 4
            ("SKU002078", 585.0),  # Pants 3pz Deportivo Miguel Hidalgo Talla 4
            ("SKU002079", 585.0),  # Pants 3pz Deportivo Miguel Campuzano Talla 6
            ("SKU002080", 585.0),  # Pants 3pz Deportivo Miguel Hidalgo Talla 6
            ("SKU002081", 585.0),  # Pants 3pz Deportivo Miguel Campuzano Talla 8
            ("SKU002082", 585.0),  # Pants 3pz Deportivo Miguel Hidalgo Talla 8
            ("SKU002083", 585.0),  # Pants 3pz Deportivo Albino García Ramos Talla 10
            ("SKU002084", 585.0),  # Pants 3pz Deportivo Benito Juárez Talla 10
            ("SKU002085", 585.0),  # Pants 3pz Deportivo Club Rotario Talla 10
            ("SKU002086", 585.0),  # Pants 3pz Deportivo Emiliano Zapata Talla 10
            ("SKU002087", 585.0),  # Pants 3pz Deportivo Francisco Villa Talla 10
            ("SKU002088", 585.0),  # Pants 3pz Deportivo Himno Nacional Talla 10
            ("SKU002089", 585.0),  # Pants 3pz Deportivo Ignacio Allende Talla 10
            ("SKU002090", 585.0),  # Pants 3pz Deportivo J. Guadalupe Victoria Talla 10
            ("SKU002091", 585.0),  # Pants 3pz Deportivo José María Morelos Talla 10
            ("SKU002092", 585.0),  # Pants 3pz Deportivo José María Morelos y Pavón Talla 10
            ("SKU002093", 585.0),  # Pants 3pz Deportivo Justo Sierra Talla 10
            ("SKU002094", 585.0),  # Pants 3pz Deportivo Miguel Campuzano Talla 10
            ("SKU002095", 585.0),  # Pants 3pz Deportivo Miguel Hidalgo Talla 10
            ("SKU002096", 585.0),  # Pants 3pz Deportivo Niños Héroes Talla 10
            ("SKU002097", 585.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 10
            ("SKU002098", 585.0),  # Pants 3pz Deportivo Albino García Ramos Talla 12
            ("SKU002099", 585.0),  # Pants 3pz Deportivo Benito Juárez Talla 12
            ("SKU002100", 585.0),  # Pants 3pz Deportivo Club Rotario Talla 12
            ("SKU002101", 585.0),  # Pants 3pz Deportivo Emiliano Zapata Talla 12
            ("SKU002102", 585.0),  # Pants 3pz Deportivo Francisco Villa Talla 12
            ("SKU002103", 585.0),  # Pants 3pz Deportivo Himno Nacional Talla 12
            ("SKU002104", 585.0),  # Pants 3pz Deportivo Ignacio Allende Talla 12
            ("SKU002105", 585.0),  # Pants 3pz Deportivo J. Guadalupe Victoria Talla 12
            ("SKU002106", 585.0),  # Pants 3pz Deportivo José María Morelos Talla 12
            ("SKU002107", 585.0),  # Pants 3pz Deportivo José María Morelos y Pavón Talla 12
            ("SKU002108", 585.0),  # Pants 3pz Deportivo Justo Sierra Talla 12
            ("SKU002109", 585.0),  # Pants 3pz Deportivo Miguel Campuzano Talla 12
            ("SKU002110", 585.0),  # Pants 3pz Deportivo Miguel Hidalgo Talla 12
            ("SKU002111", 585.0),  # Pants 3pz Deportivo Niños Héroes Talla 12
            ("SKU002112", 585.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 12
            ("SKU002113", 595.0),  # Pants 3pz Deportivo Albino García Ramos Talla 14
            ("SKU002114", 595.0),  # Pants 3pz Deportivo Benito Juárez Talla 14
            ("SKU002115", 595.0),  # Pants 3pz Deportivo Club Rotario Talla 14
            ("SKU002116", 595.0),  # Pants 3pz Deportivo Emiliano Zapata Talla 14
            ("SKU002117", 595.0),  # Pants 3pz Deportivo Francisco Villa Talla 14
            ("SKU002118", 595.0),  # Pants 3pz Deportivo Himno Nacional Talla 14
            ("SKU002119", 595.0),  # Pants 3pz Deportivo Ignacio Allende Talla 14
            ("SKU002120", 595.0),  # Pants 3pz Deportivo J. Guadalupe Victoria Talla 14
            ("SKU002121", 595.0),  # Pants 3pz Deportivo José María Morelos Talla 14
            ("SKU002122", 595.0),  # Pants 3pz Deportivo José María Morelos y Pavón Talla 14
            ("SKU002123", 595.0),  # Pants 3pz Deportivo Justo Sierra Talla 14
            ("SKU002124", 595.0),  # Pants 3pz Deportivo Miguel Campuzano Talla 14
            ("SKU002125", 595.0),  # Pants 3pz Deportivo Miguel Hidalgo Talla 14
            ("SKU002126", 595.0),  # Pants 3pz Deportivo Niños Héroes Talla 14
            ("SKU002127", 595.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 14
            ("SKU002128", 595.0),  # Pants 3pz Deportivo Albino García Ramos Talla 16
            ("SKU002129", 595.0),  # Pants 3pz Deportivo Benito Juárez Talla 16
            ("SKU002130", 595.0),  # Pants 3pz Deportivo Club Rotario Talla 16
            ("SKU002131", 595.0),  # Pants 3pz Deportivo Emiliano Zapata Talla 16
            ("SKU002132", 595.0),  # Pants 3pz Deportivo Francisco Villa Talla 16
            ("SKU002133", 595.0),  # Pants 3pz Deportivo Himno Nacional Talla 16
            ("SKU002134", 595.0),  # Pants 3pz Deportivo Ignacio Allende Talla 16
            ("SKU002135", 595.0),  # Pants 3pz Deportivo J. Guadalupe Victoria Talla 16
            ("SKU002136", 595.0),  # Pants 3pz Deportivo José María Morelos Talla 16
            ("SKU002137", 595.0),  # Pants 3pz Deportivo José María Morelos y Pavón Talla 16
            ("SKU002138", 595.0),  # Pants 3pz Deportivo Justo Sierra Talla 16
            ("SKU002139", 595.0),  # Pants 3pz Deportivo Miguel Campuzano Talla 16
            ("SKU002140", 595.0),  # Pants 3pz Deportivo Miguel Hidalgo Talla 16
            ("SKU002141", 595.0),  # Pants 3pz Deportivo Niños Héroes Talla 16
            ("SKU002142", 595.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 16
            ("SKU002143", 685.0),  # Pants 3pz Deportivo Albino García Ramos Talla CH
            ("SKU002144", 685.0),  # Pants 3pz Deportivo Benito Juárez Talla CH
            ("SKU002145", 685.0),  # Pants 3pz Deportivo Club Rotario Talla CH
            ("SKU002146", 685.0),  # Pants 3pz Deportivo Emiliano Zapata Talla CH
            ("SKU002147", 685.0),  # Pants 3pz Deportivo Francisco Villa Talla CH
            ("SKU002148", 685.0),  # Pants 3pz Deportivo Himno Nacional Talla CH
            ("SKU002149", 685.0),  # Pants 3pz Deportivo Ignacio Allende Talla CH
            ("SKU002150", 685.0),  # Pants 3pz Deportivo J. Guadalupe Victoria Talla CH
            ("SKU002151", 685.0),  # Pants 3pz Deportivo José María Morelos Talla CH
            ("SKU002152", 685.0),  # Pants 3pz Deportivo José María Morelos y Pavón Talla CH
            ("SKU002153", 685.0),  # Pants 3pz Deportivo Justo Sierra Talla CH
            ("SKU002154", 685.0),  # Pants 3pz Deportivo Miguel Campuzano Talla CH
            ("SKU002155", 685.0),  # Pants 3pz Deportivo Miguel Hidalgo Talla CH
            ("SKU002156", 685.0),  # Pants 3pz Deportivo Niños Héroes Talla CH
            ("SKU002157", 685.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla CH
            ("SKU002158", 685.0),  # Pants 3pz Deportivo Albino García Ramos Talla MD
            ("SKU002159", 685.0),  # Pants 3pz Deportivo Benito Juárez Talla MD
            ("SKU002160", 685.0),  # Pants 3pz Deportivo Club Rotario Talla MD
            ("SKU002161", 685.0),  # Pants 3pz Deportivo Emiliano Zapata Talla MD
            ("SKU002162", 685.0),  # Pants 3pz Deportivo Francisco Villa Talla MD
            ("SKU002163", 685.0),  # Pants 3pz Deportivo Himno Nacional Talla MD
            ("SKU002164", 685.0),  # Pants 3pz Deportivo Ignacio Allende Talla MD
            ("SKU002165", 685.0),  # Pants 3pz Deportivo J. Guadalupe Victoria Talla MD
            ("SKU002166", 685.0),  # Pants 3pz Deportivo José María Morelos Talla MD
            ("SKU002167", 685.0),  # Pants 3pz Deportivo José María Morelos y Pavón Talla MD
            ("SKU002168", 685.0),  # Pants 3pz Deportivo Justo Sierra Talla MD
            ("SKU002169", 685.0),  # Pants 3pz Deportivo Miguel Campuzano Talla MD
            ("SKU002170", 685.0),  # Pants 3pz Deportivo Miguel Hidalgo Talla MD
            ("SKU002171", 685.0),  # Pants 3pz Deportivo Niños Héroes Talla MD
            ("SKU002172", 685.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla MD
            ("SKU002173", 695.0),  # Pants 3pz Deportivo Albino García Ramos Talla GD
            ("SKU002174", 695.0),  # Pants 3pz Deportivo Benito Juárez Talla GD
            ("SKU002175", 695.0),  # Pants 3pz Deportivo Club Rotario Talla GD
            ("SKU002176", 695.0),  # Pants 3pz Deportivo Emiliano Zapata Talla GD
            ("SKU002177", 695.0),  # Pants 3pz Deportivo Francisco Villa Talla GD
            ("SKU002178", 695.0),  # Pants 3pz Deportivo Himno Nacional Talla GD
            ("SKU002179", 695.0),  # Pants 3pz Deportivo Ignacio Allende Talla GD
            ("SKU002180", 695.0),  # Pants 3pz Deportivo J. Guadalupe Victoria Talla GD
            ("SKU002181", 695.0),  # Pants 3pz Deportivo José María Morelos Talla GD
            ("SKU002182", 695.0),  # Pants 3pz Deportivo José María Morelos y Pavón Talla GD
            ("SKU002183", 695.0),  # Pants 3pz Deportivo Justo Sierra Talla GD
            ("SKU002184", 695.0),  # Pants 3pz Deportivo Miguel Campuzano Talla GD
            ("SKU002185", 695.0),  # Pants 3pz Deportivo Miguel Hidalgo Talla GD
            ("SKU002186", 695.0),  # Pants 3pz Deportivo Niños Héroes Talla GD
            ("SKU002187", 695.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla GD
            ("SKU002188", 695.0),  # Pants 3pz Deportivo Colegio Motolinea Talla 4
            ("SKU002189", 695.0),  # Pants 3pz Deportivo Colegio Motolinea Talla 6
            ("SKU002190", 695.0),  # Pants 3pz Deportivo Colegio Motolinea Talla 8
            ("SKU002191", 695.0),  # Pants 3pz Deportivo Colegio Motolinea Talla 10
            ("SKU002192", 695.0),  # Pants 3pz Deportivo Colegio Motolinea Talla 12
            ("SKU002193", 695.0),  # Pants 3pz Deportivo Colegio Motolinea Talla 14
            ("SKU002194", 695.0),  # Pants 3pz Deportivo Colegio Motolinea Talla 16
            ("SKU002195", 730.0),  # Pants 3pz Deportivo Colegio Motolinea Talla CH
            ("SKU002196", 740.0),  # Pants 3pz Deportivo Colegio Motolinea Talla MD
            ("SKU002197", 750.0),  # Pants 3pz Deportivo Colegio Motolinea Talla GD
            ("SKU002198", 485.0),  # Pants 2pz Deportivo Albino García Ramos Talla 4
            ("SKU002199", 485.0),  # Pants 2pz Deportivo Benito Juárez Talla 4
            ("SKU002200", 485.0),  # Pants 2pz Deportivo Club Rotario Talla 4
            ("SKU002201", 485.0),  # Pants 2pz Deportivo Emiliano Zapata Talla 4
            ("SKU002202", 485.0),  # Pants 2pz Deportivo Francisco Villa Talla 4
            ("SKU002203", 485.0),  # Pants 2pz Deportivo Himno Nacional Talla 4
            ("SKU002204", 485.0),  # Pants 2pz Deportivo Ignacio Allende Talla 4
            ("SKU002205", 485.0),  # Pants 2pz Deportivo J. Guadalupe Victoria Talla 4
            ("SKU002206", 485.0),  # Pants 2pz Deportivo José María Morelos Talla 4
            ("SKU002207", 485.0),  # Pants 2pz Deportivo José María Morelos y Pavón Talla 4
            ("SKU002208", 485.0),  # Pants 2pz Deportivo Justo Sierra Talla 4
            ("SKU002209", 485.0),  # Pants 2pz Deportivo Miguel Campuzano Talla 4
            ("SKU002210", 485.0),  # Pants 2pz Deportivo Miguel Hidalgo Talla 4
            ("SKU002211", 485.0),  # Pants 2pz Deportivo Niños Héroes Talla 4
            ("SKU002212", 485.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 4
            ("SKU002213", 485.0),  # Pants 2pz Deportivo Albino García Ramos Talla 6
            ("SKU002214", 485.0),  # Pants 2pz Deportivo Benito Juárez Talla 6
            ("SKU002215", 485.0),  # Pants 2pz Deportivo Club Rotario Talla 6
            ("SKU002216", 485.0),  # Pants 2pz Deportivo Emiliano Zapata Talla 6
            ("SKU002217", 485.0),  # Pants 2pz Deportivo Francisco Villa Talla 6
            ("SKU002218", 485.0),  # Pants 2pz Deportivo Himno Nacional Talla 6
            ("SKU002219", 485.0),  # Pants 2pz Deportivo Ignacio Allende Talla 6
            ("SKU002220", 485.0),  # Pants 2pz Deportivo J. Guadalupe Victoria Talla 6
            ("SKU002221", 485.0),  # Pants 2pz Deportivo José María Morelos Talla 6
            ("SKU002222", 485.0),  # Pants 2pz Deportivo José María Morelos y Pavón Talla 6
            ("SKU002223", 485.0),  # Pants 2pz Deportivo Justo Sierra Talla 6
            ("SKU002224", 485.0),  # Pants 2pz Deportivo Miguel Campuzano Talla 6
            ("SKU002225", 485.0),  # Pants 2pz Deportivo Miguel Hidalgo Talla 6
            ("SKU002226", 485.0),  # Pants 2pz Deportivo Niños Héroes Talla 6
            ("SKU002227", 485.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 6
            ("SKU002228", 485.0),  # Pants 2pz Deportivo Albino García Ramos Talla 8
            ("SKU002229", 485.0),  # Pants 2pz Deportivo Benito Juárez Talla 8
            ("SKU002230", 485.0),  # Pants 2pz Deportivo Club Rotario Talla 8
            ("SKU002231", 485.0),  # Pants 2pz Deportivo Emiliano Zapata Talla 8
            ("SKU002232", 485.0),  # Pants 2pz Deportivo Francisco Villa Talla 8
            ("SKU002233", 485.0),  # Pants 2pz Deportivo Himno Nacional Talla 8
            ("SKU002234", 485.0),  # Pants 2pz Deportivo Ignacio Allende Talla 8
            ("SKU002235", 485.0),  # Pants 2pz Deportivo J. Guadalupe Victoria Talla 8
            ("SKU002236", 485.0),  # Pants 2pz Deportivo José María Morelos Talla 8
            ("SKU002237", 485.0),  # Pants 2pz Deportivo José María Morelos y Pavón Talla 8
            ("SKU002238", 485.0),  # Pants 2pz Deportivo Justo Sierra Talla 8
            ("SKU002239", 485.0),  # Pants 2pz Deportivo Miguel Campuzano Talla 8
            ("SKU002240", 485.0),  # Pants 2pz Deportivo Miguel Hidalgo Talla 8
            ("SKU002241", 485.0),  # Pants 2pz Deportivo Niños Héroes Talla 8
            ("SKU002242", 485.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 8
            ("SKU002243", 485.0),  # Pants 2pz Deportivo Albino García Ramos Talla 10
            ("SKU002244", 485.0),  # Pants 2pz Deportivo Benito Juárez Talla 10
            ("SKU002245", 485.0),  # Pants 2pz Deportivo Club Rotario Talla 10
            ("SKU002246", 485.0),  # Pants 2pz Deportivo Emiliano Zapata Talla 10
            ("SKU002247", 485.0),  # Pants 2pz Deportivo Francisco Villa Talla 10
            ("SKU002248", 485.0),  # Pants 2pz Deportivo Himno Nacional Talla 10
            ("SKU002249", 485.0),  # Pants 2pz Deportivo Ignacio Allende Talla 10
            ("SKU002250", 485.0),  # Pants 2pz Deportivo J. Guadalupe Victoria Talla 10
            ("SKU002251", 485.0),  # Pants 2pz Deportivo José María Morelos Talla 10
            ("SKU002252", 485.0),  # Pants 2pz Deportivo José María Morelos y Pavón Talla 10
            ("SKU002253", 485.0),  # Pants 2pz Deportivo Justo Sierra Talla 10
            ("SKU002254", 485.0),  # Pants 2pz Deportivo Miguel Campuzano Talla 10
            ("SKU002255", 485.0),  # Pants 2pz Deportivo Miguel Hidalgo Talla 10
            ("SKU002256", 485.0),  # Pants 2pz Deportivo Niños Héroes Talla 10
            ("SKU002257", 485.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 10
            ("SKU002258", 485.0),  # Pants 2pz Deportivo Albino García Ramos Talla 12
            ("SKU002259", 485.0),  # Pants 2pz Deportivo Benito Juárez Talla 12
            ("SKU002260", 485.0),  # Pants 2pz Deportivo Club Rotario Talla 12
            ("SKU002261", 485.0),  # Pants 2pz Deportivo Emiliano Zapata Talla 12
            ("SKU002262", 485.0),  # Pants 2pz Deportivo Francisco Villa Talla 12
            ("SKU002263", 485.0),  # Pants 2pz Deportivo Himno Nacional Talla 12
            ("SKU002264", 485.0),  # Pants 2pz Deportivo Ignacio Allende Talla 12
            ("SKU002265", 485.0),  # Pants 2pz Deportivo J. Guadalupe Victoria Talla 12
            ("SKU002266", 485.0),  # Pants 2pz Deportivo José María Morelos Talla 12
            ("SKU002267", 485.0),  # Pants 2pz Deportivo José María Morelos y Pavón Talla 12
            ("SKU002268", 485.0),  # Pants 2pz Deportivo Justo Sierra Talla 12
            ("SKU002269", 485.0),  # Pants 2pz Deportivo Miguel Campuzano Talla 12
            ("SKU002270", 485.0),  # Pants 2pz Deportivo Miguel Hidalgo Talla 12
            ("SKU002271", 485.0),  # Pants 2pz Deportivo Niños Héroes Talla 12
            ("SKU002272", 485.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 12
            ("SKU002273", 495.0),  # Pants 2pz Deportivo Albino García Ramos Talla 14
            ("SKU002274", 495.0),  # Pants 2pz Deportivo Benito Juárez Talla 14
            ("SKU002275", 495.0),  # Pants 2pz Deportivo Club Rotario Talla 14
            ("SKU002276", 495.0),  # Pants 2pz Deportivo Emiliano Zapata Talla 14
            ("SKU002277", 495.0),  # Pants 2pz Deportivo Francisco Villa Talla 14
            ("SKU002278", 495.0),  # Pants 2pz Deportivo Himno Nacional Talla 14
            ("SKU002279", 495.0),  # Pants 2pz Deportivo Ignacio Allende Talla 14
            ("SKU002280", 495.0),  # Pants 2pz Deportivo J. Guadalupe Victoria Talla 14
            ("SKU002281", 495.0),  # Pants 2pz Deportivo José María Morelos Talla 14
            ("SKU002282", 495.0),  # Pants 2pz Deportivo José María Morelos y Pavón Talla 14
            ("SKU002283", 495.0),  # Pants 2pz Deportivo Justo Sierra Talla 14
            ("SKU002284", 495.0),  # Pants 2pz Deportivo Miguel Campuzano Talla 14
            ("SKU002285", 495.0),  # Pants 2pz Deportivo Miguel Hidalgo Talla 14
            ("SKU002286", 495.0),  # Pants 2pz Deportivo Niños Héroes Talla 14
            ("SKU002287", 495.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 14
            ("SKU002288", 495.0),  # Pants 2pz Deportivo Albino García Ramos Talla 16
            ("SKU002289", 495.0),  # Pants 2pz Deportivo Benito Juárez Talla 16
            ("SKU002290", 495.0),  # Pants 2pz Deportivo Club Rotario Talla 16
            ("SKU002291", 495.0),  # Pants 2pz Deportivo Emiliano Zapata Talla 16
            ("SKU002292", 495.0),  # Pants 2pz Deportivo Francisco Villa Talla 16
            ("SKU002293", 495.0),  # Pants 2pz Deportivo Himno Nacional Talla 16
            ("SKU002294", 495.0),  # Pants 2pz Deportivo Ignacio Allende Talla 16
            ("SKU002295", 495.0),  # Pants 2pz Deportivo J. Guadalupe Victoria Talla 16
            ("SKU002296", 495.0),  # Pants 2pz Deportivo José María Morelos Talla 16
            ("SKU002297", 495.0),  # Pants 2pz Deportivo José María Morelos y Pavón Talla 16
            ("SKU002298", 495.0),  # Pants 2pz Deportivo Justo Sierra Talla 16
            ("SKU002299", 495.0),  # Pants 2pz Deportivo Miguel Campuzano Talla 16
            ("SKU002300", 495.0),  # Pants 2pz Deportivo Miguel Hidalgo Talla 16
            ("SKU002301", 495.0),  # Pants 2pz Deportivo Niños Héroes Talla 16
            ("SKU002302", 495.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 16
            ("SKU002303", 585.0),  # Pants 2pz Deportivo Albino García Ramos Talla CH
            ("SKU002304", 585.0),  # Pants 2pz Deportivo Benito Juárez Talla CH
            ("SKU002305", 585.0),  # Pants 2pz Deportivo Club Rotario Talla CH
            ("SKU002306", 585.0),  # Pants 2pz Deportivo Emiliano Zapata Talla CH
            ("SKU002307", 585.0),  # Pants 2pz Deportivo Francisco Villa Talla CH
            ("SKU002308", 585.0),  # Pants 2pz Deportivo Himno Nacional Talla CH
            ("SKU002309", 585.0),  # Pants 2pz Deportivo Ignacio Allende Talla CH
            ("SKU002310", 585.0),  # Pants 2pz Deportivo J. Guadalupe Victoria Talla CH
            ("SKU002311", 585.0),  # Pants 2pz Deportivo José María Morelos Talla CH
            ("SKU002312", 585.0),  # Pants 2pz Deportivo José María Morelos y Pavón Talla CH
            ("SKU002313", 585.0),  # Pants 2pz Deportivo Justo Sierra Talla CH
            ("SKU002314", 585.0),  # Pants 2pz Deportivo Miguel Campuzano Talla CH
            ("SKU002315", 585.0),  # Pants 2pz Deportivo Miguel Hidalgo Talla CH
            ("SKU002316", 585.0),  # Pants 2pz Deportivo Niños Héroes Talla CH
            ("SKU002317", 585.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla CH
            ("SKU002318", 585.0),  # Pants 2pz Deportivo Albino García Ramos Talla MD
            ("SKU002319", 585.0),  # Pants 2pz Deportivo Benito Juárez Talla MD
            ("SKU002320", 585.0),  # Pants 2pz Deportivo Club Rotario Talla MD
            ("SKU002321", 585.0),  # Pants 2pz Deportivo Emiliano Zapata Talla MD
            ("SKU002322", 585.0),  # Pants 2pz Deportivo Francisco Villa Talla MD
            ("SKU002323", 585.0),  # Pants 2pz Deportivo Himno Nacional Talla MD
            ("SKU002324", 585.0),  # Pants 2pz Deportivo Ignacio Allende Talla MD
            ("SKU002325", 585.0),  # Pants 2pz Deportivo J. Guadalupe Victoria Talla MD
            ("SKU002326", 585.0),  # Pants 2pz Deportivo José María Morelos Talla MD
            ("SKU002327", 585.0),  # Pants 2pz Deportivo José María Morelos y Pavón Talla MD
            ("SKU002328", 585.0),  # Pants 2pz Deportivo Justo Sierra Talla MD
            ("SKU002329", 585.0),  # Pants 2pz Deportivo Miguel Campuzano Talla MD
            ("SKU002330", 585.0),  # Pants 2pz Deportivo Miguel Hidalgo Talla MD
            ("SKU002331", 585.0),  # Pants 2pz Deportivo Niños Héroes Talla MD
            ("SKU002332", 585.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla MD
            ("SKU002333", 595.0),  # Pants 2pz Deportivo Albino García Ramos Talla GD
            ("SKU002334", 595.0),  # Pants 2pz Deportivo Benito Juárez Talla GD
            ("SKU002335", 595.0),  # Pants 2pz Deportivo Club Rotario Talla GD
            ("SKU002336", 595.0),  # Pants 2pz Deportivo Emiliano Zapata Talla GD
            ("SKU002337", 595.0),  # Pants 2pz Deportivo Francisco Villa Talla GD
            ("SKU002338", 595.0),  # Pants 2pz Deportivo Himno Nacional Talla GD
            ("SKU002339", 595.0),  # Pants 2pz Deportivo Ignacio Allende Talla GD
            ("SKU002340", 595.0),  # Pants 2pz Deportivo J. Guadalupe Victoria Talla GD
            ("SKU002341", 595.0),  # Pants 2pz Deportivo José María Morelos Talla GD
            ("SKU002342", 595.0),  # Pants 2pz Deportivo José María Morelos y Pavón Talla GD
            ("SKU002343", 595.0),  # Pants 2pz Deportivo Justo Sierra Talla GD
            ("SKU002344", 595.0),  # Pants 2pz Deportivo Miguel Campuzano Talla GD
            ("SKU002345", 595.0),  # Pants 2pz Deportivo Miguel Hidalgo Talla GD
            ("SKU002346", 595.0),  # Pants 2pz Deportivo Niños Héroes Talla GD
            ("SKU002347", 595.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla GD
            ("SKU002348", 595.0),  # Pants 2pz Deportivo Colegio Motolinea Talla 4
            ("SKU002349", 595.0),  # Pants 2pz Deportivo Colegio Motolinea Talla 6
            ("SKU002350", 595.0),  # Pants 2pz Deportivo Colegio Motolinea Talla 8
            ("SKU002351", 595.0),  # Pants 2pz Deportivo Colegio Motolinea Talla 10
            ("SKU002352", 595.0),  # Pants 2pz Deportivo Colegio Motolinea Talla 12
            ("SKU002353", 595.0),  # Pants 2pz Deportivo Colegio Motolinea Talla 14
            ("SKU002354", 595.0),  # Pants 2pz Deportivo Colegio Motolinea Talla 16
            ("SKU002355", 630.0),  # Pants 2pz Deportivo Colegio Motolinea Talla CH
            ("SKU002356", 640.0),  # Pants 2pz Deportivo Colegio Motolinea Talla MD
            ("SKU002357", 650.0),  # Pants 2pz Deportivo Colegio Motolinea Talla GD
            ("SKU002358", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002359", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002360", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002361", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002362", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002363", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002364", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002365", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002366", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002367", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002368", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002369", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002370", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002371", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002372", 199.0),  # Playera Deportiva Ad hoc Talla 4
            ("SKU002373", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002374", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002375", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002376", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002377", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002378", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002379", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002380", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002381", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002382", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002383", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002384", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002385", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002386", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002387", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU002388", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002389", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002390", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002391", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002392", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002393", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002394", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002395", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002396", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002397", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002398", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002399", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002400", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002401", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002402", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU002403", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002404", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002405", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002406", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002407", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002408", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002409", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002410", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002411", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002412", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002413", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002414", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002415", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002416", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002417", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002418", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002419", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002420", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002421", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002422", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002423", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002424", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002425", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002426", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002427", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002428", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002429", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002430", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002431", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002432", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002433", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002434", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002435", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002436", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002437", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002438", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002439", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002440", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002441", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002442", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002443", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002444", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002445", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002446", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002447", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002448", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002449", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002450", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002451", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002452", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002453", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002454", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002455", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002456", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002457", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002458", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002459", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002460", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002461", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002462", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002463", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002464", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002465", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002466", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002467", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002468", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002469", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002470", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002471", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002472", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002473", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002474", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002475", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002476", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002477", 219.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002478", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002479", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002480", 219.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002481", 219.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002482", 219.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002483", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002484", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002485", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002486", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002487", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002488", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002489", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002490", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002491", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002492", 225.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002493", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002494", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002495", 219.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002496", 219.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002497", 219.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002498", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002499", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002500", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002501", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002502", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002503", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002504", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002505", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002506", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002507", 235.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002508", 199.0),  # Playera Deportivo Ad hoc Talla 2
            ("SKU002509", 199.0),  # Playera Deportivo Ad hoc Talla 4
            ("SKU002510", 199.0),  # Playera Deportivo Ad hoc Talla 6
            ("SKU002511", 199.0),  # Playera Deportivo Ad hoc Talla 8
            ("SKU002512", 199.0),  # Playera Deportivo Ad hoc Talla 10
            ("SKU002513", 199.0),  # Playera Deportivo Ad hoc Talla 12
            ("SKU002514", 199.0),  # Playera Deportivo Ad hoc Talla 14
            ("SKU002515", 199.0),  # Playera Deportivo Ad hoc Talla 16
            ("SKU002516", 215.0),  # Playera Deportivo Ad hoc Talla CH
            ("SKU002517", 225.0),  # Playera Deportivo Ad hoc Talla MD
            ("SKU002518", 235.0),  # Playera Deportivo Ad hoc Talla GD
            ("SKU002519", 695.0),  # Pants 3pz Deportivo Bicentenario Talla 10
            ("SKU002520", 695.0),  # Pants 3pz Deportivo EsTv 154 Talla 10
            ("SKU002521", 695.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 10
            ("SKU002522", 695.0),  # Pants 3pz Deportivo Técnica de San Bartolo Talla 10
            ("SKU002523", 695.0),  # Pants 3pz Deportivo Bicentenario Talla 12
            ("SKU002524", 695.0),  # Pants 3pz Deportivo EsTv 154 Talla 12
            ("SKU002525", 695.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 12
            ("SKU002526", 695.0),  # Pants 3pz Deportivo Técnica de San Bartolo Talla 12
            ("SKU002527", 705.0),  # Pants 3pz Deportivo Bicentenario Talla 14
            ("SKU002528", 705.0),  # Pants 3pz Deportivo EsTv 154 Talla 14
            ("SKU002529", 705.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 14
            ("SKU002530", 705.0),  # Pants 3pz Deportivo Técnica de San Bartolo Talla 14
            ("SKU002531", 705.0),  # Pants 3pz Deportivo Bicentenario Talla 16
            ("SKU002532", 705.0),  # Pants 3pz Deportivo EsTv 154 Talla 16
            ("SKU002533", 705.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla 16
            ("SKU002534", 705.0),  # Pants 3pz Deportivo Técnica de San Bartolo Talla 16
            ("SKU002535", 715.0),  # Pants 3pz Deportivo Bicentenario Talla CH
            ("SKU002536", 715.0),  # Pants 3pz Deportivo EsTv 154 Talla CH
            ("SKU002537", 715.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla CH
            ("SKU002538", 715.0),  # Pants 3pz Deportivo Técnica de San Bartolo Talla CH
            ("SKU002539", 715.0),  # Pants 3pz Deportivo Bicentenario Talla MD
            ("SKU002540", 715.0),  # Pants 3pz Deportivo EsTv 154 Talla MD
            ("SKU002541", 715.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla MD
            ("SKU002542", 715.0),  # Pants 3pz Deportivo Técnica de San Bartolo Talla MD
            ("SKU002543", 715.0),  # Pants 3pz Deportivo Bicentenario Talla GD
            ("SKU002544", 715.0),  # Pants 3pz Deportivo EsTv 154 Talla GD
            ("SKU002545", 715.0),  # Pants 3pz Deportivo Práxedis Guerrero Talla GD
            ("SKU002546", 715.0),  # Pants 3pz Deportivo Técnica de San Bartolo Talla GD
            ("SKU002547", 595.0),  # Pants 2pz Deportivo Bicentenario Talla 10
            ("SKU002548", 595.0),  # Pants 2pz Deportivo EsTv 154 Talla 10
            ("SKU002549", 595.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 10
            ("SKU002550", 595.0),  # Pants 2pz Deportivo Técnica de San Bartolo Talla 10
            ("SKU002551", 595.0),  # Pants 2pz Deportivo Bicentenario Talla 12
            ("SKU002552", 595.0),  # Pants 2pz Deportivo EsTv 154 Talla 12
            ("SKU002553", 595.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 12
            ("SKU002554", 595.0),  # Pants 2pz Deportivo Técnica de San Bartolo Talla 12
            ("SKU002555", 605.0),  # Pants 2pz Deportivo Bicentenario Talla 14
            ("SKU002556", 605.0),  # Pants 2pz Deportivo EsTv 154 Talla 14
            ("SKU002557", 605.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 14
            ("SKU002558", 605.0),  # Pants 2pz Deportivo Técnica de San Bartolo Talla 14
            ("SKU002559", 605.0),  # Pants 2pz Deportivo Bicentenario Talla 16
            ("SKU002560", 605.0),  # Pants 2pz Deportivo EsTv 154 Talla 16
            ("SKU002561", 605.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla 16
            ("SKU002562", 605.0),  # Pants 2pz Deportivo Técnica de San Bartolo Talla 16
            ("SKU002563", 615.0),  # Pants 2pz Deportivo Bicentenario Talla CH
            ("SKU002564", 615.0),  # Pants 2pz Deportivo EsTv 154 Talla CH
            ("SKU002565", 615.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla CH
            ("SKU002566", 615.0),  # Pants 2pz Deportivo Técnica de San Bartolo Talla CH
            ("SKU002567", 615.0),  # Pants 2pz Deportivo Bicentenario Talla MD
            ("SKU002568", 615.0),  # Pants 2pz Deportivo EsTv 154 Talla MD
            ("SKU002569", 615.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla MD
            ("SKU002570", 615.0),  # Pants 2pz Deportivo Técnica de San Bartolo Talla MD
            ("SKU002571", 615.0),  # Pants 2pz Deportivo Bicentenario Talla GD
            ("SKU002572", 615.0),  # Pants 2pz Deportivo EsTv 154 Talla GD
            ("SKU002573", 615.0),  # Pants 2pz Deportivo Práxedis Guerrero Talla GD
            ("SKU002574", 615.0),  # Pants 2pz Deportivo Técnica de San Bartolo Talla GD
            ("SKU002575", 750.0),  # Pants 3pz Deportivo Telesecundaria 454 Talla 10
            ("SKU002576", 750.0),  # Pants 3pz Deportivo Telesecundaria 512 Talla 10
            ("SKU002577", 750.0),  # Pants 3pz Deportivo Telesecundaria 454 Talla 12
            ("SKU002578", 750.0),  # Pants 3pz Deportivo Telesecundaria 512 Talla 12
            ("SKU002579", 750.0),  # Pants 3pz Deportivo Telesecundaria 454 Talla 14
            ("SKU002580", 750.0),  # Pants 3pz Deportivo Telesecundaria 512 Talla 14
            ("SKU002581", 750.0),  # Pants 3pz Deportivo Telesecundaria 454 Talla 16
            ("SKU002582", 750.0),  # Pants 3pz Deportivo Telesecundaria 512 Talla 16
            ("SKU002583", 750.0),  # Pants 3pz Deportivo Telesecundaria 454 Talla CH
            ("SKU002584", 750.0),  # Pants 3pz Deportivo Telesecundaria 512 Talla CH
            ("SKU002585", 750.0),  # Pants 3pz Deportivo Telesecundaria 454 Talla MD
            ("SKU002586", 750.0),  # Pants 3pz Deportivo Telesecundaria 512 Talla MD
            ("SKU002587", 750.0),  # Pants 3pz Deportivo Telesecundaria 454 Talla GD
            ("SKU002588", 750.0),  # Pants 3pz Deportivo Telesecundaria 512 Talla GD
            ("SKU002589", 650.0),  # Pants 2pz Deportivo Telesecundaria 454 Talla 10
            ("SKU002590", 650.0),  # Pants 2pz Deportivo Telesecundaria 512 Talla 10
            ("SKU002591", 650.0),  # Pants 2pz Deportivo Telesecundaria 454 Talla 12
            ("SKU002592", 650.0),  # Pants 2pz Deportivo Telesecundaria 512 Talla 12
            ("SKU002593", 650.0),  # Pants 2pz Deportivo Telesecundaria 454 Talla 14
            ("SKU002594", 650.0),  # Pants 2pz Deportivo Telesecundaria 512 Talla 14
            ("SKU002595", 650.0),  # Pants 2pz Deportivo Telesecundaria 454 Talla 16
            ("SKU002596", 650.0),  # Pants 2pz Deportivo Telesecundaria 512 Talla 16
            ("SKU002597", 650.0),  # Pants 2pz Deportivo Telesecundaria 454 Talla CH
            ("SKU002598", 650.0),  # Pants 2pz Deportivo Telesecundaria 512 Talla CH
            ("SKU002599", 650.0),  # Pants 2pz Deportivo Telesecundaria 454 Talla MD
            ("SKU002600", 650.0),  # Pants 2pz Deportivo Telesecundaria 512 Talla MD
            ("SKU002601", 650.0),  # Pants 2pz Deportivo Telesecundaria 454 Talla GD
            ("SKU002602", 650.0),  # Pants 2pz Deportivo Telesecundaria 512 Talla GD
            ("SKU002603", 229.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002604", 229.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002605", 229.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002606", 229.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002607", 229.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002608", 229.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU002609", 229.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002610", 229.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002611", 229.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002612", 229.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002613", 229.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002614", 229.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002615", 229.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002616", 229.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002617", 229.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002618", 229.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002619", 229.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002620", 229.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002621", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002622", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002623", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002624", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002625", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002626", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002627", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002628", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002629", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002630", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002631", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002632", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002633", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002634", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002635", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002636", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002637", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002638", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002639", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002640", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002641", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002642", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002643", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002644", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002645", 239.0),  # Playera Deportiva Ad hoc Talla EXG
            ("SKU002646", 239.0),  # Playera Deportiva Ad hoc Talla EXG
            ("SKU002647", 239.0),  # Playera Deportiva Ad hoc Talla EXG
            ("SKU002648", 239.0),  # Playera Deportiva Ad hoc Talla EXG
            ("SKU002649", 239.0),  # Playera Deportiva Ad hoc Talla EXG
            ("SKU002650", 239.0),  # Playera Deportiva Ad hoc Talla EXG
            ("SKU002651", 715.0),  # Pants 3pz Deportivo CBTIS 148 Talla 16
            ("SKU002652", 715.0),  # Pants 3pz Deportivo SABES Talla 16
            ("SKU002653", 715.0),  # Pants 3pz Deportivo CBTIS 148 Talla CH
            ("SKU002654", 715.0),  # Pants 3pz Deportivo SABES Talla CH
            ("SKU002655", 715.0),  # Pants 3pz Deportivo CBTIS 148 Talla MD
            ("SKU002656", 715.0),  # Pants 3pz Deportivo SABES Talla MD
            ("SKU002657", 715.0),  # Pants 3pz Deportivo CBTIS 148 Talla GD
            ("SKU002658", 715.0),  # Pants 3pz Deportivo SABES Talla GD
            ("SKU002659", 715.0),  # Pants 3pz Deportivo CBTIS 148 Talla EXG
            ("SKU002660", 715.0),  # Pants 3pz Deportivo SABES Talla EXG
            ("SKU002661", 615.0),  # Pants 2pz Deportivo CBTIS 148 Talla 16
            ("SKU002662", 615.0),  # Pants 2pz Deportivo SABES Talla 16
            ("SKU002663", 615.0),  # Pants 2pz Deportivo CBTIS 148 Talla CH
            ("SKU002664", 615.0),  # Pants 2pz Deportivo SABES Talla CH
            ("SKU002665", 615.0),  # Pants 2pz Deportivo CBTIS 148 Talla MD
            ("SKU002666", 615.0),  # Pants 2pz Deportivo SABES Talla MD
            ("SKU002667", 615.0),  # Pants 2pz Deportivo CBTIS 148 Talla GD
            ("SKU002668", 615.0),  # Pants 2pz Deportivo SABES Talla GD
            ("SKU002669", 615.0),  # Pants 2pz Deportivo CBTIS 148 Talla EXG
            ("SKU002670", 615.0),  # Pants 2pz Deportivo SABES Talla EXG
            ("SKU002671", 750.0),  # Pants 3pz Deportivo CECYTE Talla 16
            ("SKU002672", 750.0),  # Pants 3pz Deportivo Conalep Talla 16
            ("SKU002673", 750.0),  # Pants 3pz Deportivo UVEG Talla 16
            ("SKU002674", 750.0),  # Pants 3pz Deportivo CECYTE Talla CH
            ("SKU002675", 750.0),  # Pants 3pz Deportivo Conalep Talla CH
            ("SKU002676", 750.0),  # Pants 3pz Deportivo UVEG Talla CH
            ("SKU002677", 750.0),  # Pants 3pz Deportivo CECYTE Talla MD
            ("SKU002678", 750.0),  # Pants 3pz Deportivo Conalep Talla MD
            ("SKU002679", 750.0),  # Pants 3pz Deportivo UVEG Talla MD
            ("SKU002680", 750.0),  # Pants 3pz Deportivo CECYTE Talla GD
            ("SKU002681", 750.0),  # Pants 3pz Deportivo Conalep Talla GD
            ("SKU002682", 750.0),  # Pants 3pz Deportivo UVEG Talla GD
            ("SKU002683", 750.0),  # Pants 3pz Deportivo CECYTE Talla EXG
            ("SKU002684", 750.0),  # Pants 3pz Deportivo Conalep Talla EXG
            ("SKU002685", 750.0),  # Pants 3pz Deportivo UVEG Talla EXG
            ("SKU002686", 650.0),  # Pants 2pz Deportivo CECYTE Talla 16
            ("SKU002687", 650.0),  # Pants 2pz Deportivo Conalep Talla 16
            ("SKU002688", 650.0),  # Pants 2pz Deportivo UVEG Talla 16
            ("SKU002689", 650.0),  # Pants 2pz Deportivo CECYTE Talla CH
            ("SKU002690", 650.0),  # Pants 2pz Deportivo Conalep Talla CH
            ("SKU002691", 650.0),  # Pants 2pz Deportivo UVEG Talla CH
            ("SKU002692", 650.0),  # Pants 2pz Deportivo CECYTE Talla MD
            ("SKU002693", 650.0),  # Pants 2pz Deportivo Conalep Talla MD
            ("SKU002694", 650.0),  # Pants 2pz Deportivo UVEG Talla MD
            ("SKU002695", 650.0),  # Pants 2pz Deportivo CECYTE Talla GD
            ("SKU002696", 650.0),  # Pants 2pz Deportivo Conalep Talla GD
            ("SKU002697", 650.0),  # Pants 2pz Deportivo UVEG Talla GD
            ("SKU002698", 650.0),  # Pants 2pz Deportivo CECYTE Talla EXG
            ("SKU002699", 650.0),  # Pants 2pz Deportivo Conalep Talla EXG
            ("SKU002700", 650.0),  # Pants 2pz Deportivo UVEG Talla EXG
            ("SKU002702", 229.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002704", 229.0),  # Playera Deportiva H Ad hoc Talla 12
            ("SKU002705", 229.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU002706", 229.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002707", 229.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002709", 229.0),  # Playera Deportiva H Ad hoc Talla 14
            ("SKU002710", 229.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU002711", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002712", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002714", 229.0),  # Playera Deportiva H Ad hoc Talla 16
            ("SKU002715", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002716", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002717", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002719", 239.0),  # Playera Deportiva H Ad hoc Talla CH
            ("SKU002720", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002721", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002722", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002724", 239.0),  # Playera Deportiva H Ad hoc Talla MD
            ("SKU002725", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002726", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002727", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002729", 239.0),  # Playera Deportiva H Ad hoc Talla GD
            ("SKU002730", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002731", 239.0),  # Playera Deportiva Ad hoc Talla EXG
            ("SKU002732", 239.0),  # Playera Deportiva Ad hoc Talla EXG
            ("SKU002733", 235.0),  # Playera Polo Ad hoc Talla 16
            ("SKU002734", 235.0),  # Playera Polo Ad hoc Talla CH
            ("SKU002735", 235.0),  # Playera Polo Ad hoc Talla MD
            ("SKU002736", 235.0),  # Playera Polo Ad hoc Talla GD
            ("SKU002737", 235.0),  # Playera Polo Ad hoc Talla EXG
            ("SKU002738", 229.0),  # Playera Deportiva M Ad hoc Talla 12
            ("SKU002739", 229.0),  # Playera Deportiva M Ad hoc Talla 14
            ("SKU002740", 229.0),  # Playera Deportiva M Ad hoc Talla 16
            ("SKU002741", 239.0),  # Playera Deportiva M Ad hoc Talla CH
            ("SKU002742", 239.0),  # Playera Deportiva M Ad hoc Talla MD
            ("SKU002743", 239.0),  # Playera Deportiva M Ad hoc Talla GD
            ("SKU002744", 239.0),  # Playera Deportiva M Ad hoc Talla EXG
            ("SKU002745", 239.0),  # Playera Deportiva H Ad hoc Talla EXG
            ("SKU002749", 235.0),  # Pantalón Vestir Pata de gallo Talla 4
            ("SKU002750", 235.0),  # Pantalón Vestir Pata de gallo Talla 6
            ("SKU002751", 235.0),  # Pantalón Vestir Pata de gallo Talla 8
            ("SKU002752", 245.0),  # Pantalón Vestir Pata de gallo Talla 10
            ("SKU002753", 245.0),  # Pantalón Vestir Pata de gallo Talla 12
            ("SKU002754", 245.0),  # Pantalón Vestir Pata de gallo Talla 14
            ("SKU002755", 245.0),  # Pantalón Vestir Pata de gallo Talla 16
            ("SKU002756", 245.0),  # Pantalón Vestir Pata de gallo Talla 28
            ("SKU002757", 245.0),  # Pantalón Vestir Pata de gallo Talla 30
            ("SKU002758", 285.0),  # Pantalón Vestir Pata de gallo Talla 32
            ("SKU002759", 255.0),  # Pantalón Vestir Pata de gallo Talla 34
            ("SKU002760", 295.0),  # Pantalón Vestir Pata de gallo Talla 36
            ("SKU002761", 295.0),  # Pantalón Vestir Pata de gallo Talla 38
            ("SKU002762", 255.0),  # Pantalón Vestir Pata de gallo Talla 40
            ("SKU002763", 255.0),  # Pantalón Vestir Pata de gallo Talla 42
            ("SKU002764", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU002765", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU002766", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU002767", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU002768", 239.0),  # Playera Deportiva Ad hoc Talla EXG
            ("SKU002769", 80.0),  # Boina Escolta Verde limon Talla Uni
            ("SKU002770", 585.0),  # Pants 3pz Deportivo Ignacio Ramirez Lopez Talla 6
            ("SKU002771", 585.0),  # Pants 3pz Deportivo Ignacio Ramirez Lopez Talla 8
            ("SKU002772", 585.0),  # Pants 3pz Deportivo Ignacio Ramirez Lopez Talla 10
            ("SKU002773", 585.0),  # Pants 3pz Deportivo Ignacio Ramirez Lopez Talla 12
            ("SKU002774", 595.0),  # Pants 3pz Deportivo Ignacio Ramirez Lopez Talla 14
            ("SKU002775", 595.0),  # Pants 3pz Deportivo Ignacio Ramirez Lopez Talla 16
            ("SKU002777", 335.0),  # Chamarra Deportiva Talla 4
            ("SKU002778", 335.0),  # Chamarra Deportiva Talla 4
            ("SKU002780", 335.0),  # Chamarra Deportiva Talla 4
            ("SKU002782", 335.0),  # Chamarra Deportiva Talla 4
            ("SKU002785", 335.0),  # Chamarra Deportiva Talla 4
            ("SKU002786", 335.0),  # Chamarra Deportiva Talla 4
            ("SKU002788", 335.0),  # Chamarra Deportiva Talla 4
            ("SKU002789", 335.0),  # Chamarra Deportiva Talla 4
            ("SKU002791", 335.0),  # Chamarra Deportiva Talla 4
            ("SKU002794", 335.0),  # Chamarra Deportiva Talla 6
            ("SKU002795", 335.0),  # Chamarra Deportiva Talla 6
            ("SKU002797", 335.0),  # Chamarra Deportiva Talla 6
            ("SKU002799", 335.0),  # Chamarra Deportiva Talla 6
            ("SKU002802", 335.0),  # Chamarra Deportiva Talla 6
            ("SKU002803", 335.0),  # Chamarra Deportiva Talla 6
            ("SKU002805", 335.0),  # Chamarra Deportiva Talla 6
            ("SKU002806", 335.0),  # Chamarra Deportiva Talla 6
            ("SKU002808", 335.0),  # Chamarra Deportiva Talla 6
            ("SKU002811", 335.0),  # Chamarra Deportiva Talla 8
            ("SKU002812", 335.0),  # Chamarra Deportiva Talla 8
            ("SKU002814", 335.0),  # Chamarra Deportiva Talla 8
            ("SKU002816", 335.0),  # Chamarra Deportiva Talla 8
            ("SKU002819", 335.0),  # Chamarra Deportiva Talla 8
            ("SKU002820", 335.0),  # Chamarra Deportiva Talla 8
            ("SKU002822", 335.0),  # Chamarra Deportiva Talla 8
            ("SKU002823", 335.0),  # Chamarra Deportiva Talla 8
            ("SKU002825", 335.0),  # Chamarra Deportiva Talla 8
            ("SKU002827", 199.0),  # Camisa Manga Larga H Blanca Talla 2
            ("SKU002828", 199.0),  # Camisa Manga Larga H Blanca Talla 4
            ("SKU002829", 199.0),  # Camisa Manga Larga H Blanca Talla 8
            ("SKU002830", 199.0),  # Camisa Manga Larga H Blanca Talla 6
            ("SKU002831", 219.0),  # Camisa Manga Larga H Blanca Talla 10
            ("SKU002832", 219.0),  # Camisa Manga Larga H Blanca Talla 12
            ("SKU002833", 219.0),  # Camisa Manga Larga H Blanca Talla 14
            ("SKU002834", 219.0),  # Camisa Manga Larga H Blanca Talla 16
            ("SKU002835", 239.0),  # Camisa Manga Larga H Blanca Talla 32
            ("SKU002836", 239.0),  # Camisa Manga Larga H Blanca Talla 34
            ("SKU002837", 249.0),  # Camisa Manga Larga H Blanca Talla 36
            ("SKU002838", 249.0),  # Camisa Manga Larga H Blanca Talla 38
            ("SKU002839", 259.0),  # Camisa Manga Larga H Blanca Talla 40
            ("SKU002840", 259.0),  # Camisa Manga Larga H Blanca Talla 42
            ("SKU002841", 259.0),  # Camisa Manga Larga H Blanca Talla 44
            ("SKU002842", 259.0),  # Camisa Manga Larga H Blanca Talla CH
            ("SKU002843", 269.0),  # Camisa Manga Larga H Blanca Talla MD
            ("SKU002844", 279.0),  # Camisa Manga Larga H Blanca Talla GD
            ("SKU002845", 289.0),  # Camisa Manga Larga H Blanca Talla EXG
            ("SKU002846", 219.0),  # Camisa Manga Larga H Blanca Talla 18
            ("SKU002847", 269.0),  # Camisa Manga Larga M Blanca Talla 30
            ("SKU002848", 269.0),  # Camisa Manga Larga M Blanca Talla CH
            ("SKU002849", 289.0),  # Camisa Manga Larga M Blanca Talla MD
            ("SKU002850", 289.0),  # Camisa Manga Larga M Blanca Talla GD
            ("SKU002851", 309.0),  # Camisa Manga Larga M Blanca Talla EXG
            ("SKU002852", 315.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002853", 315.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002854", 315.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002855", 315.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002856", 315.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002857", 315.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002858", 315.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002859", 315.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002860", 315.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002861", 315.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002862", 315.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002863", 315.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002864", 315.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002865", 315.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002866", 315.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002867", 315.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002868", 315.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002869", 315.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002870", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002871", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002872", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002873", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002874", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002875", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002876", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002877", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002878", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002879", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002880", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002881", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002882", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002883", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002884", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002885", 335.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU002886", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002887", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002888", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002889", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002890", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002891", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002892", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002893", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002894", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002895", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002896", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002897", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002898", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002899", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002900", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002901", 335.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU002902", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002903", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002904", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002905", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002906", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002907", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002908", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002909", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002910", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002911", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002912", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002913", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002914", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002915", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002916", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002917", 335.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU002918", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002919", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002920", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002921", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002922", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002923", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002924", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002925", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002926", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002927", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002928", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002929", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002930", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002931", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002932", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002933", 335.0),  # Chamarra Deportiva Ad hoc Talla 10
            ("SKU002934", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002935", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002936", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002937", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002938", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002939", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002940", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002941", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002942", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002943", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002944", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002945", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002946", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002947", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002948", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002949", 335.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU002950", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002951", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002952", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002953", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002954", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002955", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002956", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002957", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002958", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002959", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002960", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002961", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002962", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002963", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002964", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002965", 335.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU002966", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002967", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002968", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002969", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002970", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002971", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002972", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002973", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002974", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002975", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002976", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002977", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002978", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002979", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002980", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002981", 335.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU002982", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002983", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002984", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002985", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002986", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002987", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002988", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002989", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002990", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002991", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002992", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002993", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002994", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002995", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002996", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002997", 335.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU002998", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU002999", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003000", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003001", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003002", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003003", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003004", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003005", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003006", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003007", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003008", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003009", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003010", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003011", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003012", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003013", 335.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003014", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003015", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003016", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003017", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003018", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003019", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003020", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003021", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003022", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003023", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003024", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003025", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003026", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003027", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003028", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003029", 335.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003030", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003031", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003032", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003033", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003034", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003035", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003036", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003037", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003038", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003039", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003040", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003041", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003042", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003043", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003044", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003045", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003046", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003047", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003048", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003049", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003050", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003051", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003052", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003053", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003054", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003055", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003056", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003057", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003058", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003059", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003060", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003061", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003062", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003063", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003064", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003065", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003066", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003067", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003068", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003069", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003070", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003071", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003072", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003073", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003074", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003075", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003076", 385.0),  # Chamarra Deportiva Ad hoc Talla 12
            ("SKU003077", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003078", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003079", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003080", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003081", 385.0),  # Chamarra Deportiva Ad hoc Talla 14
            ("SKU003082", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003083", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003084", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003085", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003086", 385.0),  # Chamarra Deportiva Ad hoc Talla 16
            ("SKU003087", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003088", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003089", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003090", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003091", 385.0),  # Chamarra Deportiva Ad hoc Talla CH
            ("SKU003092", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003093", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003094", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003095", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003096", 385.0),  # Chamarra Deportiva Ad hoc Talla MD
            ("SKU003097", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003098", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003099", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003100", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003101", 385.0),  # Chamarra Deportiva Ad hoc Talla GD
            ("SKU003102", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003103", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003104", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003105", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003106", 385.0),  # Chamarra Deportiva Ad hoc Talla EXG
            ("SKU003107", 135.0),  # Playera Deportiva Bicolor Talla 4
            ("SKU003108", 135.0),  # Playera Deportiva Bicolor Talla 6
            ("SKU003109", 135.0),  # Playera Deportiva Bicolor Talla 8
            ("SKU003110", 135.0),  # Playera Deportiva Bicolor Talla 10
            ("SKU003111", 135.0),  # Playera Deportiva Bicolor Talla 12
            ("SKU003112", 135.0),  # Playera Deportiva Bicolor Talla 13
            ("SKU003113", 135.0),  # Playera Deportiva Bicolor Talla 16
            ("SKU003114", 135.0),  # Playera Deportiva Bicolor Talla CH
            ("SKU003115", 135.0),  # Playera Deportiva Bicolor Talla MD
            ("SKU003116", 135.0),  # Playera Deportiva Bicolor Talla GD
            ("SKU003117", 185.0),  # Playera Polo Blanca Talla CH
            ("SKU003118", 185.0),  # Playera Polo Blanca Talla MD
            ("SKU003119", 195.0),  # Playera Polo Blanca Talla GD
            ("SKU003120", 195.0),  # Playera Polo Blanca Talla EXG
            ("SKU003121", 205.0),  # Falda Escolar Pata de gallo Talla 4
            ("SKU003122", 205.0),  # Falda Escolar Pata de gallo Talla 6
            ("SKU003123", 205.0),  # Falda Escolar Pata de gallo Talla 8
            ("SKU003124", 215.0),  # Falda Escolar Pata de gallo Talla 10
            ("SKU003125", 215.0),  # Falda Escolar Pata de gallo Talla 12
            ("SKU003126", 225.0),  # Falda Escolar Pata de gallo Talla 14
            ("SKU003127", 225.0),  # Falda Escolar Pata de gallo Talla 16
            ("SKU003128", 245.0),  # Falda Escolar Pata de gallo Talla 28
            ("SKU003129", 245.0),  # Falda Escolar Pata de gallo Talla 30
            ("SKU003130", 205.0),  # Falda Escolar Pgallo cafe Talla 12
            ("SKU003131", 215.0),  # Falda Escolar Pgallo cafe Talla 14
            ("SKU003132", 215.0),  # Falda Escolar Pgallo cafe Talla 16
            ("SKU003133", 245.0),  # Falda Escolar Pgallo cafe Talla 28
            ("SKU003134", 245.0),  # Falda Escolar Pgallo cafe Talla 30
            ("SKU003135", 245.0),  # Falda Escolar Pgallo cafe Talla 32
            ("SKU003136", 245.0),  # Falda Escolar Pgallo cafe Talla 34
            ("SKU003137", 255.0),  # Falda Escolar Pgallo cafe Talla 36
            ("SKU003138", 255.0),  # Falda Escolar Pgallo cafe Talla 38
            ("SKU003139", 255.0),  # Falda Escolar Pgallo cafe Talla 40
            ("SKU003140", 255.0),  # Falda Escolar Pgallo cafe Talla 42
            ("SKU003144", 265.0),  # Pantalón Vestir Pata de gallo Talla 20
            ("SKU003145", 235.0),  # Pantalón Vestir Azul Marino Talla 2
            ("SKU003146", 235.0),  # Pantalón Vestir Azul Rey Talla 2
            ("SKU003147", 235.0),  # Pantalón Vestir Blanco Talla 2
            ("SKU003148", 235.0),  # Pantalón Vestir Café Talla 2
            ("SKU003149", 235.0),  # Pantalón Vestir Gris Talla 2
            ("SKU003150", 235.0),  # Pantalón Vestir Negro Talla 2
            ("SKU003151", 235.0),  # Pantalón Vestir Verde Talla 2
            ("SKU003152", 235.0),  # Pantalón Vestir Vino Talla 2
            ("SKU003153", 235.0),  # Pantalón Vestir Caqui Talla 2
            ("SKU003154", 235.0),  # Pantalón Vestir Verde olivo Talla 2
            ("SKU003155", 235.0),  # Pantalón Vestir Azul Marino Talla 4
            ("SKU003156", 235.0),  # Pantalón Vestir Azul Rey Talla 4
            ("SKU003157", 235.0),  # Pantalón Vestir Blanco Talla 4
            ("SKU003158", 235.0),  # Pantalón Vestir Café Talla 4
            ("SKU003159", 235.0),  # Pantalón Vestir Gris Talla 4
            ("SKU003160", 235.0),  # Pantalón Vestir Negro Talla 4
            ("SKU003161", 235.0),  # Pantalón Vestir Verde Talla 4
            ("SKU003162", 235.0),  # Pantalón Vestir Vino Talla 4
            ("SKU003163", 235.0),  # Pantalón Vestir Caqui Talla 4
            ("SKU003164", 235.0),  # Pantalón Vestir Verde olivo Talla 4
            ("SKU003165", 235.0),  # Pantalón Vestir Azul Marino Talla 6
            ("SKU003166", 235.0),  # Pantalón Vestir Azul Rey Talla 6
            ("SKU003167", 235.0),  # Pantalón Vestir Blanco Talla 6
            ("SKU003168", 235.0),  # Pantalón Vestir Café Talla 6
            ("SKU003169", 235.0),  # Pantalón Vestir Gris Talla 6
            ("SKU003170", 235.0),  # Pantalón Vestir Negro Talla 6
            ("SKU003171", 235.0),  # Pantalón Vestir Verde Talla 6
            ("SKU003172", 235.0),  # Pantalón Vestir Vino Talla 6
            ("SKU003173", 235.0),  # Pantalón Vestir Caqui Talla 6
            ("SKU003174", 235.0),  # Pantalón Vestir Verde olivo Talla 6
            ("SKU003175", 235.0),  # Pantalón Vestir Azul Marino Talla 8
            ("SKU003176", 235.0),  # Pantalón Vestir Azul Rey Talla 8
            ("SKU003177", 235.0),  # Pantalón Vestir Blanco Talla 8
            ("SKU003178", 235.0),  # Pantalón Vestir Café Talla 8
            ("SKU003179", 235.0),  # Pantalón Vestir Gris Talla 8
            ("SKU003180", 235.0),  # Pantalón Vestir Negro Talla 8
            ("SKU003181", 235.0),  # Pantalón Vestir Verde Talla 8
            ("SKU003182", 235.0),  # Pantalón Vestir Vino Talla 8
            ("SKU003183", 235.0),  # Pantalón Vestir Caqui Talla 8
            ("SKU003184", 235.0),  # Pantalón Vestir Verde olivo Talla 8
            ("SKU003185", 245.0),  # Pantalón Vestir Azul Marino Talla 10
            ("SKU003186", 245.0),  # Pantalón Vestir Azul Rey Talla 10
            ("SKU003187", 245.0),  # Pantalón Vestir Blanco Talla 10
            ("SKU003188", 245.0),  # Pantalón Vestir Café Talla 10
            ("SKU003189", 245.0),  # Pantalón Vestir Gris Talla 10
            ("SKU003190", 245.0),  # Pantalón Vestir Negro Talla 10
            ("SKU003191", 245.0),  # Pantalón Vestir Verde Talla 10
            ("SKU003192", 245.0),  # Pantalón Vestir Vino Talla 10
            ("SKU003193", 245.0),  # Pantalón Vestir Caqui Talla 10
            ("SKU003194", 245.0),  # Pantalón Vestir Verde olivo Talla 10
            ("SKU003195", 245.0),  # Pantalón Vestir Azul Marino Talla 12
            ("SKU003196", 245.0),  # Pantalón Vestir Azul Rey Talla 12
            ("SKU003197", 245.0),  # Pantalón Vestir Blanco Talla 12
            ("SKU003198", 245.0),  # Pantalón Vestir Café Talla 12
            ("SKU003199", 245.0),  # Pantalón Vestir Gris Talla 12
            ("SKU003200", 245.0),  # Pantalón Vestir Negro Talla 12
            ("SKU003201", 245.0),  # Pantalón Vestir Verde Talla 12
            ("SKU003202", 245.0),  # Pantalón Vestir Vino Talla 12
            ("SKU003203", 245.0),  # Pantalón Vestir Caqui Talla 12
            ("SKU003204", 245.0),  # Pantalón Vestir Verde olivo Talla 12
            ("SKU003205", 245.0),  # Pantalón Vestir Azul Marino Talla 14
            ("SKU003206", 245.0),  # Pantalón Vestir Azul Rey Talla 14
            ("SKU003207", 245.0),  # Pantalón Vestir Blanco Talla 14
            ("SKU003208", 245.0),  # Pantalón Vestir Café Talla 14
            ("SKU003209", 245.0),  # Pantalón Vestir Gris Talla 14
            ("SKU003210", 245.0),  # Pantalón Vestir Negro Talla 14
            ("SKU003211", 245.0),  # Pantalón Vestir Verde Talla 14
            ("SKU003212", 245.0),  # Pantalón Vestir Vino Talla 14
            ("SKU003213", 245.0),  # Pantalón Vestir Caqui Talla 14
            ("SKU003214", 245.0),  # Pantalón Vestir Verde olivo Talla 14
            ("SKU003215", 245.0),  # Pantalón Vestir Azul Marino Talla 16
            ("SKU003216", 245.0),  # Pantalón Vestir Azul Rey Talla 16
            ("SKU003217", 245.0),  # Pantalón Vestir Blanco Talla 16
            ("SKU003218", 245.0),  # Pantalón Vestir Café Talla 16
            ("SKU003219", 245.0),  # Pantalón Vestir Gris Talla 16
            ("SKU003220", 245.0),  # Pantalón Vestir Negro Talla 16
            ("SKU003221", 245.0),  # Pantalón Vestir Verde Talla 16
            ("SKU003222", 245.0),  # Pantalón Vestir Vino Talla 16
            ("SKU003223", 245.0),  # Pantalón Vestir Caqui Talla 16
            ("SKU003224", 245.0),  # Pantalón Vestir Verde olivo Talla 16
            ("SKU003225", 265.0),  # Pantalón Vestir Azul Marino Talla 18
            ("SKU003226", 265.0),  # Pantalón Vestir Azul Rey Talla 18
            ("SKU003227", 265.0),  # Pantalón Vestir Blanco Talla 18
            ("SKU003228", 265.0),  # Pantalón Vestir Café Talla 18
            ("SKU003229", 265.0),  # Pantalón Vestir Gris Talla 18
            ("SKU003230", 265.0),  # Pantalón Vestir Negro Talla 18
            ("SKU003231", 265.0),  # Pantalón Vestir Verde Talla 18
            ("SKU003232", 265.0),  # Pantalón Vestir Vino Talla 18
            ("SKU003233", 265.0),  # Pantalón Vestir Caqui Talla 18
            ("SKU003234", 265.0),  # Pantalón Vestir Verde olivo Talla 18
            ("SKU003235", 265.0),  # Pantalón Vestir Azul Marino Talla 20
            ("SKU003236", 265.0),  # Pantalón Vestir Azul Rey Talla 20
            ("SKU003237", 265.0),  # Pantalón Vestir Blanco Talla 20
            ("SKU003238", 265.0),  # Pantalón Vestir Café Talla 20
            ("SKU003239", 265.0),  # Pantalón Vestir Gris Talla 20
            ("SKU003240", 265.0),  # Pantalón Vestir Negro Talla 20
            ("SKU003241", 265.0),  # Pantalón Vestir Verde Talla 20
            ("SKU003242", 265.0),  # Pantalón Vestir Vino Talla 20
            ("SKU003243", 265.0),  # Pantalón Vestir Caqui Talla 20
            ("SKU003244", 265.0),  # Pantalón Vestir Verde olivo Talla 20
            ("SKU003245", 265.0),  # Pantalón Vestir Azul Marino Talla 28
            ("SKU003246", 265.0),  # Pantalón Vestir Azul Rey Talla 28
            ("SKU003247", 265.0),  # Pantalón Vestir Blanco Talla 28
            ("SKU003248", 265.0),  # Pantalón Vestir Café Talla 28
            ("SKU003249", 265.0),  # Pantalón Vestir Gris Talla 28
            ("SKU003250", 265.0),  # Pantalón Vestir Negro Talla 28
            ("SKU003251", 265.0),  # Pantalón Vestir Verde Talla 28
            ("SKU003252", 265.0),  # Pantalón Vestir Vino Talla 28
            ("SKU003253", 265.0),  # Pantalón Vestir Caqui Talla 28
            ("SKU003254", 265.0),  # Pantalón Vestir Verde olivo Talla 28
            ("SKU003255", 265.0),  # Pantalón Vestir Azul Marino Talla 30
            ("SKU003256", 265.0),  # Pantalón Vestir Azul Rey Talla 30
            ("SKU003257", 265.0),  # Pantalón Vestir Blanco Talla 30
            ("SKU003258", 265.0),  # Pantalón Vestir Café Talla 30
            ("SKU003259", 265.0),  # Pantalón Vestir Gris Talla 30
            ("SKU003260", 265.0),  # Pantalón Vestir Negro Talla 30
            ("SKU003261", 265.0),  # Pantalón Vestir Verde Talla 30
            ("SKU003262", 265.0),  # Pantalón Vestir Vino Talla 30
            ("SKU003263", 265.0),  # Pantalón Vestir Caqui Talla 30
            ("SKU003264", 265.0),  # Pantalón Vestir Verde olivo Talla 30
            ("SKU003265", 285.0),  # Pantalón Vestir Azul Marino Talla 32
            ("SKU003266", 285.0),  # Pantalón Vestir Azul Rey Talla 32
            ("SKU003267", 285.0),  # Pantalón Vestir Blanco Talla 32
            ("SKU003268", 285.0),  # Pantalón Vestir Café Talla 32
            ("SKU003269", 285.0),  # Pantalón Vestir Gris Talla 32
            ("SKU003270", 285.0),  # Pantalón Vestir Negro Talla 32
            ("SKU003271", 285.0),  # Pantalón Vestir Verde Talla 32
            ("SKU003272", 285.0),  # Pantalón Vestir Vino Talla 32
            ("SKU003273", 285.0),  # Pantalón Vestir Caqui Talla 32
            ("SKU003274", 285.0),  # Pantalón Vestir Verde olivo Talla 32
            ("SKU003275", 285.0),  # Pantalón Vestir Azul Marino Talla 34
            ("SKU003276", 285.0),  # Pantalón Vestir Azul Rey Talla 34
            ("SKU003277", 285.0),  # Pantalón Vestir Blanco Talla 34
            ("SKU003278", 285.0),  # Pantalón Vestir Café Talla 34
            ("SKU003279", 285.0),  # Pantalón Vestir Gris Talla 34
            ("SKU003280", 285.0),  # Pantalón Vestir Negro Talla 34
            ("SKU003281", 285.0),  # Pantalón Vestir Verde Talla 34
            ("SKU003282", 285.0),  # Pantalón Vestir Vino Talla 34
            ("SKU003283", 285.0),  # Pantalón Vestir Caqui Talla 34
            ("SKU003284", 285.0),  # Pantalón Vestir Verde olivo Talla 34
            ("SKU003285", 295.0),  # Pantalón Vestir Azul Marino Talla 36
            ("SKU003286", 295.0),  # Pantalón Vestir Azul Rey Talla 36
            ("SKU003287", 295.0),  # Pantalón Vestir Blanco Talla 36
            ("SKU003288", 295.0),  # Pantalón Vestir Café Talla 36
            ("SKU003289", 295.0),  # Pantalón Vestir Gris Talla 36
            ("SKU003290", 295.0),  # Pantalón Vestir Negro Talla 36
            ("SKU003291", 295.0),  # Pantalón Vestir Verde Talla 36
            ("SKU003292", 295.0),  # Pantalón Vestir Vino Talla 36
            ("SKU003293", 295.0),  # Pantalón Vestir Caqui Talla 36
            ("SKU003294", 295.0),  # Pantalón Vestir Verde olivo Talla 36
            ("SKU003295", 295.0),  # Pantalón Vestir Azul Marino Talla 38
            ("SKU003296", 295.0),  # Pantalón Vestir Azul Rey Talla 38
            ("SKU003297", 295.0),  # Pantalón Vestir Blanco Talla 38
            ("SKU003298", 295.0),  # Pantalón Vestir Café Talla 38
            ("SKU003299", 295.0),  # Pantalón Vestir Gris Talla 38
            ("SKU003300", 295.0),  # Pantalón Vestir Negro Talla 38
            ("SKU003301", 295.0),  # Pantalón Vestir Verde Talla 38
            ("SKU003302", 295.0),  # Pantalón Vestir Vino Talla 38
            ("SKU003303", 295.0),  # Pantalón Vestir Caqui Talla 38
            ("SKU003304", 295.0),  # Pantalón Vestir Verde olivo Talla 38
            ("SKU003305", 295.0),  # Pantalón Vestir Azul Marino Talla 40
            ("SKU003306", 295.0),  # Pantalón Vestir Azul Rey Talla 40
            ("SKU003307", 295.0),  # Pantalón Vestir Blanco Talla 40
            ("SKU003308", 295.0),  # Pantalón Vestir Café Talla 40
            ("SKU003309", 295.0),  # Pantalón Vestir Gris Talla 40
            ("SKU003310", 295.0),  # Pantalón Vestir Negro Talla 40
            ("SKU003311", 295.0),  # Pantalón Vestir Verde Talla 40
            ("SKU003312", 295.0),  # Pantalón Vestir Vino Talla 40
            ("SKU003313", 295.0),  # Pantalón Vestir Caqui Talla 40
            ("SKU003314", 295.0),  # Pantalón Vestir Verde olivo Talla 40
            ("SKU003315", 219.0),  # Pantalón Gabardina Negro Talla 2
            ("SKU003316", 219.0),  # Pantalón Gabardina Negro Talla 4
            ("SKU003317", 219.0),  # Pantalón Gabardina Negro Talla 6
            ("SKU003318", 219.0),  # Pantalón Gabardina Negro Talla 8
            ("SKU003319", 219.0),  # Pantalón Gabardina Negro Talla 10
            ("SKU003320", 219.0),  # Pantalón Gabardina Negro Talla 12
            ("SKU003321", 219.0),  # Pantalón Gabardina Negro Talla 14
            ("SKU003322", 219.0),  # Pantalón Gabardina Negro Talla 16
            ("SKU003323", 235.0),  # Pantalón Vestir Gris claro Talla 4
            ("SKU003324", 235.0),  # Pantalón Vestir Gris claro Talla 6
            ("SKU003325", 235.0),  # Pantalón Vestir Gris claro Talla 8
            ("SKU003326", 245.0),  # Pantalón Vestir Gris claro Talla 10
            ("SKU003327", 245.0),  # Pantalón Vestir Gris claro Talla 12
            ("SKU003328", 255.0),  # Pantalón Vestir Gris claro Talla 14
            ("SKU003329", 255.0),  # Pantalón Vestir Gris claro Talla 16
            ("SKU003330", 265.0),  # Pantalón Vestir Gris claro Talla 18
            ("SKU003331", 265.0),  # Pantalón Vestir Gris claro Talla 20
            ("SKU003332", 275.0),  # Pantalón Vestir Gris claro Talla 28
            ("SKU003333", 275.0),  # Pantalón Vestir Gris claro Talla 30
            ("SKU003334", 285.0),  # Pantalón Vestir Gris claro Talla 32
            ("SKU003335", 285.0),  # Pantalón Vestir Gris claro Talla 34
            ("SKU003336", 295.0),  # Pantalón Vestir Gris claro Talla 36
            ("SKU003337", 295.0),  # Pantalón Vestir Gris claro Talla 38
            ("SKU003338", 315.0),  # Pantalón Vestir Gris claro Talla 40
            ("SKU003339", 315.0),  # Pantalón Vestir Gris claro Talla 42
            ("SKU003340", 235.0),  # Pantalón Vestir Gris obscuro Talla 4
            ("SKU003341", 235.0),  # Pantalón Vestir Gris obscuro Talla 6
            ("SKU003342", 235.0),  # Pantalón Vestir Gris obscuro Talla 8
            ("SKU003343", 245.0),  # Pantalón Vestir Gris obscuro Talla 10
            ("SKU003344", 245.0),  # Pantalón Vestir Gris obscuro Talla 12
            ("SKU003345", 255.0),  # Pantalón Vestir Gris obscuro Talla 14
            ("SKU003346", 255.0),  # Pantalón Vestir Gris obscuro Talla 16
            ("SKU003347", 265.0),  # Pantalón Vestir Gris obscuro Talla 18
            ("SKU003348", 265.0),  # Pantalón Vestir Gris obscuro Talla 20
            ("SKU003349", 275.0),  # Pantalón Vestir Gris obscuro Talla 28
            ("SKU003350", 275.0),  # Pantalón Vestir Gris obscuro Talla 30
            ("SKU003351", 285.0),  # Pantalón Vestir Gris obscuro Talla 32
            ("SKU003352", 285.0),  # Pantalón Vestir Gris obscuro Talla 34
            ("SKU003353", 295.0),  # Pantalón Vestir Gris obscuro Talla 36
            ("SKU003354", 295.0),  # Pantalón Vestir Gris obscuro Talla 38
            ("SKU003355", 315.0),  # Pantalón Vestir Gris obscuro Talla 40
            ("SKU003356", 315.0),  # Pantalón Vestir Gris obscuro Talla 42
            ("SKU003357", 315.0),  # Pantalón Vestir Gris obscuro Talla 44
            ("SKU003358", 315.0),  # Pantalón Vestir Azul Marino Talla 42
            ("SKU003359", 315.0),  # Pantalón Vestir Azul Marino Talla 44
            ("SKU003420", 235.0),  # Pantalón Gales azul Talla 2
            ("SKU003421", 235.0),  # Pantalón Gales rojo Talla 2
            ("SKU003422", 235.0),  # Pantalón Gales verde Talla 2
            ("SKU003423", 235.0),  # Pantalón Gales azul Talla 4
            ("SKU003424", 235.0),  # Pantalón Gales rojo Talla 4
            ("SKU003425", 235.0),  # Pantalón Gales verde Talla 4
            ("SKU003426", 235.0),  # Pantalón Gales azul Talla 5
            ("SKU003427", 235.0),  # Pantalón Gales rojo Talla 5
            ("SKU003428", 235.0),  # Pantalón Gales verde Talla 5
            ("SKU003429", 235.0),  # Pantalón Gales azul Talla 6
            ("SKU003430", 235.0),  # Pantalón Gales rojo Talla 6
            ("SKU003431", 235.0),  # Pantalón Gales verde Talla 6
            ("SKU003432", 235.0),  # Pantalón Gales azul Talla 8
            ("SKU003433", 235.0),  # Pantalón Gales rojo Talla 8
            ("SKU003434", 235.0),  # Pantalón Gales verde Talla 8
            ("SKU003435", 245.0),  # Pantalón Gales azul Talla 10
            ("SKU003436", 245.0),  # Pantalón Gales rojo Talla 10
            ("SKU003437", 245.0),  # Pantalón Gales verde Talla 10
            ("SKU003438", 245.0),  # Pantalón Gales azul Talla 12
            ("SKU003439", 245.0),  # Pantalón Gales rojo Talla 12
            ("SKU003440", 245.0),  # Pantalón Gales verde Talla 12
            ("SKU003441", 245.0),  # Pantalón Gales azul Talla 14
            ("SKU003442", 245.0),  # Pantalón Gales rojo Talla 14
            ("SKU003443", 245.0),  # Pantalón Gales verde Talla 14
            ("SKU003444", 245.0),  # Pantalón Gales azul Talla 16
            ("SKU003445", 245.0),  # Pantalón Gales rojo Talla 16
            ("SKU003446", 245.0),  # Pantalón Gales verde Talla 16
            ("SKU003447", 265.0),  # Pantalón Gales azul Talla 18
            ("SKU003448", 265.0),  # Pantalón Gales rojo Talla 18
            ("SKU003449", 265.0),  # Pantalón Gales verde Talla 18
            ("SKU003450", 265.0),  # Pantalón Gales azul Talla 20
            ("SKU003451", 265.0),  # Pantalón Gales rojo Talla 20
            ("SKU003452", 265.0),  # Pantalón Gales verde Talla 20
            ("SKU003453", 265.0),  # Pantalón Gales azul Talla 28
            ("SKU003454", 265.0),  # Pantalón Gales rojo Talla 28
            ("SKU003455", 265.0),  # Pantalón Gales verde Talla 28
            ("SKU003456", 265.0),  # Pantalón Gales azul Talla 30
            ("SKU003457", 265.0),  # Pantalón Gales rojo Talla 30
            ("SKU003458", 265.0),  # Pantalón Gales verde Talla 30
            ("SKU003459", 285.0),  # Pantalón Gales azul Talla 32
            ("SKU003460", 285.0),  # Pantalón Gales rojo Talla 32
            ("SKU003461", 285.0),  # Pantalón Gales verde Talla 32
            ("SKU003462", 285.0),  # Pantalón Gales azul Talla 34
            ("SKU003463", 285.0),  # Pantalón Gales rojo Talla 34
            ("SKU003464", 285.0),  # Pantalón Gales verde Talla 34
            ("SKU003465", 295.0),  # Pantalón Gales azul Talla 36
            ("SKU003466", 295.0),  # Pantalón Gales rojo Talla 36
            ("SKU003467", 295.0),  # Pantalón Gales verde Talla 36
            ("SKU003468", 295.0),  # Pantalón Gales azul Talla 38
            ("SKU003469", 295.0),  # Pantalón Gales rojo Talla 38
            ("SKU003470", 295.0),  # Pantalón Gales verde Talla 38
            ("SKU003471", 295.0),  # Pantalón Gales azul Talla 40
            ("SKU003472", 295.0),  # Pantalón Gales rojo Talla 40
            ("SKU003473", 295.0),  # Pantalón Gales verde Talla 40
            ("SKU003474", 295.0),  # Pantalón Gales azul Talla 42
            ("SKU003475", 295.0),  # Pantalón Gales rojo Talla 42
            ("SKU003476", 295.0),  # Pantalón Gales verde Talla 42
            ("SKU003477", 315.0),  # Pantalón Gales azul Talla 44
            ("SKU003478", 315.0),  # Pantalón Gales rojo Talla 44
            ("SKU003479", 315.0),  # Pantalón Gales verde Talla 44
            ("SKU003480", 199.0),  # Pantalón Escoces Talla 2
            ("SKU003481", 199.0),  # Pantalón Escoces Talla 3
            ("SKU003482", 199.0),  # Pantalón Escoces Talla 4
            ("SKU003483", 199.0),  # Pantalón Escoces Talla 6
            ("SKU003484", 199.0),  # Pantalón Escoces Talla 8
            ("SKU003485", 235.0),  # Pantalón Escoces Talla 10
            ("SKU003486", 235.0),  # Pantalón Escoces Talla 12
            ("SKU003487", 235.0),  # Pantalón Escoces Talla 14
            ("SKU003488", 235.0),  # Pantalón Escoces Talla 16
            ("SKU003489", 265.0),  # Pantalón Escoces Talla 28
            ("SKU003490", 265.0),  # Pantalón Escoces Talla 30
            ("SKU003491", 265.0),  # Pantalón Escoces Talla 32
            ("SKU003492", 239.0),  # Pantalón Escoces Talla 2
            ("SKU003493", 239.0),  # Pantalón Escoces Talla 4
            ("SKU003494", 239.0),  # Pantalón Escoces Talla 6
            ("SKU003495", 239.0),  # Pantalón Escoces Talla 8
            ("SKU003496", 195.0),  # Falda Escolar Azul Marino Talla 2
            ("SKU003497", 195.0),  # Falda Escolar Azul Marino Talla 4
            ("SKU003498", 195.0),  # Falda Escolar Azul Marino Talla 6
            ("SKU003499", 195.0),  # Falda Escolar Azul Marino Talla 8
            ("SKU003500", 195.0),  # Falda Escolar Azul Marino Talla 10
            ("SKU003501", 195.0),  # Falda Escolar Azul Marino Talla 12
            ("SKU003502", 195.0),  # Falda Escolar Azul Marino Talla 14
            ("SKU003503", 195.0),  # Falda Escolar Azul Marino Talla 16
            ("SKU003504", 205.0),  # Falda Escolar Azul Marino Talla 18
            ("SKU003505", 205.0),  # Falda Escolar Azul Marino Talla 20
            ("SKU003506", 205.0),  # Falda Escolar Azul Marino Talla 28
            ("SKU003507", 205.0),  # Falda Escolar Azul Marino Talla 30
            ("SKU003508", 215.0),  # Falda Escolar Azul Marino Talla 32
            ("SKU003509", 215.0),  # Falda Escolar Azul Marino Talla 34
            ("SKU003510", 225.0),  # Falda Escolar Azul Marino Talla 36
            ("SKU003511", 225.0),  # Falda Escolar Azul Marino Talla 38
            ("SKU003512", 235.0),  # Falda Escolar Azul Marino Talla 40
            ("SKU003513", 235.0),  # Falda Escolar Azul Marino Talla 42
            ("SKU003514", 650.0),  # Pants 2pz Deportivo Telesecundaria 512 Talla EXG
            ("SKU003515", 265.0),  # Falda Gris claro Talla 4
            ("SKU003516", 265.0),  # Falda Gris obscuro Talla 4
            ("SKU003517", 265.0),  # Falda Gris claro Talla 6
            ("SKU003518", 265.0),  # Falda Gris obscuro Talla 6
            ("SKU003519", 265.0),  # Falda Gris claro Talla 8
            ("SKU003520", 265.0),  # Falda Gris obscuro Talla 8
            ("SKU003521", 265.0),  # Falda Gris claro Talla 10
            ("SKU003522", 265.0),  # Falda Gris obscuro Talla 10
            ("SKU003523", 265.0),  # Falda Gris claro Talla 12
            ("SKU003524", 265.0),  # Falda Gris obscuro Talla 12
            ("SKU003525", 265.0),  # Falda Gris claro Talla 14
            ("SKU003526", 265.0),  # Falda Gris obscuro Talla 14
            ("SKU003527", 265.0),  # Falda Gris claro Talla 16
            ("SKU003528", 265.0),  # Falda Gris obscuro Talla 16
            ("SKU003529", 275.0),  # Falda Gris claro Talla 28
            ("SKU003530", 275.0),  # Falda Gris obscuro Talla 28
            ("SKU003531", 275.0),  # Falda Gris claro Talla 30
            ("SKU003532", 275.0),  # Falda Gris obscuro Talla 30
            ("SKU003533", 275.0),  # Falda Gris claro Talla 32
            ("SKU003534", 275.0),  # Falda Gris obscuro Talla 32
            ("SKU003535", 275.0),  # Falda Gris claro Talla 34
            ("SKU003536", 275.0),  # Falda Gris obscuro Talla 34
            ("SKU003537", 285.0),  # Falda Gris claro Talla 36
            ("SKU003538", 285.0),  # Falda Gris obscuro Talla 36
            ("SKU003539", 285.0),  # Falda Gris claro Talla 38
            ("SKU003540", 285.0),  # Falda Gris obscuro Talla 38
            ("SKU003541", 295.0),  # Falda Gris claro Talla 40
            ("SKU003542", 295.0),  # Falda Gris obscuro Talla 40
            ("SKU003543", 295.0),  # Falda Gris claro Talla 42
            ("SKU003544", 295.0),  # Falda Gris obscuro Talla 42
            ("SKU003545", 199.0),  # Falda Vino Talla 4
            ("SKU003546", 199.0),  # Falda Vino Talla 6
            ("SKU003547", 199.0),  # Falda Vino Talla 8
            ("SKU003548", 205.0),  # Falda Vino Talla 10
            ("SKU003549", 205.0),  # Falda Vino Talla 12
            ("SKU003550", 215.0),  # Falda Vino Talla 14
            ("SKU003551", 215.0),  # Falda Vino Talla 16
            ("SKU003552", 225.0),  # Falda Vino Talla 28
            ("SKU003553", 225.0),  # Falda Vino Talla 30
            ("SKU003554", 225.0),  # Falda Vino Talla 32
            ("SKU003555", 225.0),  # Falda Vino Talla 34
            ("SKU003556", 235.0),  # Falda Vino Talla 36
            ("SKU003572", 325.0),  # Suéter Cuello V H Rojo Talla 14
            ("SKU003573", 325.0),  # Suéter Cuello V H Rojo Talla 16
            ("SKU003574", 335.0),  # Suéter Cuello V H Rojo Talla 32
            ("SKU003575", 335.0),  # Suéter Cuello V H Rojo Talla 34
            ("SKU003576", 345.0),  # Suéter Cuello V H Rojo Talla 36
            ("SKU003577", 345.0),  # Suéter Cuello V H Rojo Talla 38
            ("SKU003578", 355.0),  # Suéter Cuello V H Rojo Talla 40
            ("SKU003579", 355.0),  # Suéter Cuello V H Rojo Talla 42
            ("SKU003580", 355.0),  # Suéter Cuello V H Rojo Talla 44
            ("SKU003581", 325.0),  # Suéter Botones M Rojo Talla 14
            ("SKU003582", 325.0),  # Suéter Botones M Rojo Talla 16
            ("SKU003583", 335.0),  # Suéter Botones M Rojo Talla 32
            ("SKU003584", 335.0),  # Suéter Botones M Rojo Talla 34
            ("SKU003585", 345.0),  # Suéter Botones M Rojo Talla 36
            ("SKU003586", 345.0),  # Suéter Botones M Rojo Talla 38
            ("SKU003587", 355.0),  # Suéter Botones M Rojo Talla 40
            ("SKU003588", 355.0),  # Suéter Botones M Rojo Talla 42
            ("SKU003589", 355.0),  # Suéter Botones M Rojo Talla 44
            ("SKU003590", 265.0),  # Camisa Manga Corta Blanca Talla 16
            ("SKU003591", 265.0),  # Camisa Manga Corta Blanca Talla 32
            ("SKU003592", 265.0),  # Camisa Manga Corta Blanca Talla 34
            ("SKU003593", 265.0),  # Camisa Manga Corta Blanca Talla 36
            ("SKU003594", 265.0),  # Camisa Manga Corta Blanca Talla 38
            ("SKU003595", 265.0),  # Camisa Manga Corta Blanca Talla 40
            ("SKU003596", 265.0),  # Camisa Manga Corta Blanca Talla 42
            ("SKU003597", 265.0),  # Camisa Manga Corta Blanca Talla 44
            ("SKU003598", 325.0),  # Suéter Cuello V Azul Marino Talla 14
            ("SKU003599", 325.0),  # Suéter Cuello V Azul Marino Talla 16
            ("SKU003600", 335.0),  # Suéter Cuello V Azul Marino Talla 32
            ("SKU003601", 335.0),  # Suéter Cuello V Azul Marino Talla 34
            ("SKU003602", 345.0),  # Suéter Cuello V Azul Marino Talla 36
            ("SKU003603", 345.0),  # Suéter Cuello V Azul Marino Talla 38
            ("SKU003604", 355.0),  # Suéter Cuello V Azul Marino Talla 40
            ("SKU003605", 355.0),  # Suéter Cuello V Azul Marino Talla 42
            ("SKU003606", 355.0),  # Suéter Cuello V Azul Marino Talla 44
            ("SKU003607", 265.0),  # Chaleco Azul Marino Talla 14
            ("SKU003608", 265.0),  # Chaleco Azul Marino Talla 16
            ("SKU003609", 275.0),  # Chaleco Azul Marino Talla 32
            ("SKU003610", 275.0),  # Chaleco Azul Marino Talla 34
            ("SKU003611", 285.0),  # Chaleco Azul Marino Talla 36
            ("SKU003612", 285.0),  # Chaleco Azul Marino Talla 38
            ("SKU003613", 285.0),  # Chaleco Azul Marino Talla 40
            ("SKU003614", 285.0),  # Chaleco Azul Marino Talla 42
            ("SKU003615", 295.0),  # Chaleco Azul Marino Talla 44
            ("SKU003616", 219.0),  # Playera Blanca Talla 14
            ("SKU003617", 219.0),  # Playera Blanca Talla 16
            ("SKU003618", 219.0),  # Playera Blanca Talla CH
            ("SKU003619", 219.0),  # Playera Blanca Talla MD
            ("SKU003620", 219.0),  # Playera Blanca Talla GD
            ("SKU003621", 219.0),  # Playera Blanca Talla EXG
            ("SKU003622", 285.0),  # Pants Suelto Rojo Talla 14
            ("SKU003623", 285.0),  # Pants Suelto Rojo Talla 16
            ("SKU003624", 285.0),  # Pants Suelto Rojo Talla CH
            ("SKU003625", 285.0),  # Pants Suelto Rojo Talla MD
            ("SKU003626", 285.0),  # Pants Suelto Rojo Talla GD
            ("SKU003627", 285.0),  # Pants Suelto Rojo Talla EXG
            ("SKU003628", 270.0),  # Falda SABES Talla 10
            ("SKU003629", 270.0),  # Falda SABES Talla 12
            ("SKU003630", 270.0),  # Falda SABES Talla 14
            ("SKU003631", 270.0),  # Falda SABES Talla 16
            ("SKU003632", 275.0),  # Falda SABES Talla 28
            ("SKU003633", 275.0),  # Falda SABES Talla 30
            ("SKU003634", 275.0),  # Falda SABES Talla 32
            ("SKU003635", 275.0),  # Falda SABES Talla 34
            ("SKU003636", 285.0),  # Falda SABES Talla 36
            ("SKU003637", 285.0),  # Falda SABES Talla 38
            ("SKU003638", 295.0),  # Falda SABES Talla 40
            ("SKU003639", 295.0),  # Falda SABES Talla 42
            ("SKU003640", 265.0),  # Camisa Manga Larga Blanca Talla 14
            ("SKU003641", 265.0),  # Camisa Manga Larga Blanca Talla 16
            ("SKU003642", 265.0),  # Camisa Manga Larga Blanca Talla 18
            ("SKU003643", 265.0),  # Camisa Manga Larga Blanca Talla 30
            ("SKU003644", 265.0),  # Camisa Manga Larga Blanca Talla 32
            ("SKU003645", 265.0),  # Camisa Manga Larga Blanca Talla 34
            ("SKU003646", 265.0),  # Camisa Manga Larga Blanca Talla 36
            ("SKU003647", 265.0),  # Camisa Manga Larga Blanca Talla 38
            ("SKU003648", 265.0),  # Camisa Manga Larga Blanca Talla 40
            ("SKU003649", 265.0),  # Camisa Manga Larga Blanca Talla 42
            ("SKU003650", 280.0),  # Falda Conalep Escoces Talla 14
            ("SKU003651", 280.0),  # Falda Conalep Escoces Talla 16
            ("SKU003652", 285.0),  # Falda Conalep Escoces Talla 28
            ("SKU003653", 285.0),  # Falda Conalep Escoces Talla 30
            ("SKU003654", 285.0),  # Falda Conalep Escoces Talla 32
            ("SKU003655", 285.0),  # Falda Conalep Escoces Talla 34
            ("SKU003656", 295.0),  # Falda Conalep Escoces Talla 36
            ("SKU003657", 295.0),  # Falda Conalep Escoces Talla 38
            ("SKU003658", 295.0),  # Falda Conalep Escoces Talla 40
            ("SKU003659", 295.0),  # Falda Conalep Escoces Talla 42
            ("SKU003660", 325.0),  # Suéter Botones M Verde Talla 14
            ("SKU003661", 325.0),  # Suéter Botones M Verde Talla 16
            ("SKU003662", 335.0),  # Suéter Botones M Verde Talla 32
            ("SKU003663", 345.0),  # Suéter Botones M Verde Talla 34
            ("SKU003664", 345.0),  # Suéter Botones M Verde Talla 36
            ("SKU003665", 345.0),  # Suéter Botones M Verde Talla 38
            ("SKU003666", 355.0),  # Suéter Botones M Verde Talla 40
            ("SKU003667", 355.0),  # Suéter Botones M Verde Talla 42
            ("SKU003668", 355.0),  # Suéter Botones M Verde Talla 44
            ("SKU003669", 325.0),  # Suéter Cuello V H Verde Talla 14
            ("SKU003670", 325.0),  # Suéter Cuello V H Verde Talla 16
            ("SKU003671", 335.0),  # Suéter Cuello V H Verde Talla 32
            ("SKU003672", 335.0),  # Suéter Cuello V H Verde Talla 34
            ("SKU003673", 345.0),  # Suéter Cuello V H Verde Talla 36
            ("SKU003674", 345.0),  # Suéter Cuello V H Verde Talla 38
            ("SKU003675", 355.0),  # Suéter Cuello V H Verde Talla 40
            ("SKU003676", 355.0),  # Suéter Cuello V H Verde Talla 42
            ("SKU003677", 355.0),  # Suéter Cuello V H Verde Talla 44
            ("SKU003684", 125.0),  # Corbata Verde Talla Uni
            ("SKU003685", 125.0),  # Corbatín Verde Talla Uni
            ("SKU003686", 125.0),  # Mascada Verde Talla Uni
            ("SKU003687", 235.0),  # Pants Suelto Talla 2
            ("SKU003688", 235.0),  # Pants Suelto Talla 2
            ("SKU003689", 235.0),  # Pants Suelto Talla 2
            ("SKU003690", 235.0),  # Pants Suelto Talla 2
            ("SKU003691", 235.0),  # Pants Suelto Talla 4
            ("SKU003692", 235.0),  # Pants Suelto Talla 4
            ("SKU003693", 235.0),  # Pants Suelto Talla 4
            ("SKU003694", 235.0),  # Pants Suelto Talla 4
            ("SKU003695", 235.0),  # Pants Suelto Talla 6
            ("SKU003696", 235.0),  # Pants Suelto Talla 6
            ("SKU003697", 235.0),  # Pants Suelto Talla 6
            ("SKU003698", 235.0),  # Pants Suelto Talla 6
            ("SKU003699", 235.0),  # Pants Suelto Talla 8
            ("SKU003700", 235.0),  # Pants Suelto Talla 8
            ("SKU003701", 235.0),  # Pants Suelto Talla 8
            ("SKU003702", 235.0),  # Pants Suelto Talla 8
            ("SKU003703", 175.0),  # Playera Deportiva Talla 4
            ("SKU003704", 175.0),  # Playera Deportiva Talla 4
            ("SKU003705", 175.0),  # Playera Deportiva Talla 4
            ("SKU003706", 175.0),  # Playera Deportiva Talla 4
            ("SKU003707", 175.0),  # Playera Deportiva Talla 4
            ("SKU003708", 175.0),  # Playera Deportiva Talla 6
            ("SKU003709", 175.0),  # Playera Deportiva Talla 6
            ("SKU003710", 175.0),  # Playera Deportiva Talla 6
            ("SKU003711", 175.0),  # Playera Deportiva Talla 6
            ("SKU003712", 175.0),  # Playera Deportiva Talla 6
            ("SKU003713", 175.0),  # Playera Deportiva Talla 8
            ("SKU003714", 175.0),  # Playera Deportiva Talla 8
            ("SKU003715", 175.0),  # Playera Deportiva Talla 8
            ("SKU003716", 175.0),  # Playera Deportiva Talla 8
            ("SKU003717", 175.0),  # Playera Deportiva Talla 8
            ("SKU003718", 175.0),  # Playera Deportiva Talla 10
            ("SKU003719", 175.0),  # Playera Deportiva Talla 10
            ("SKU003720", 175.0),  # Playera Deportiva Talla 10
            ("SKU003721", 175.0),  # Playera Deportiva Talla 10
            ("SKU003722", 175.0),  # Playera Deportiva Talla 10
            ("SKU003723", 290.0),  # Suéter Botones M Talla 4
            ("SKU003724", 290.0),  # Suéter Botones M Talla 4
            ("SKU003725", 290.0),  # Suéter Botones M Talla 4
            ("SKU003726", 290.0),  # Suéter Botones M Talla 4
            ("SKU003727", 290.0),  # Suéter Botones M Talla 4
            ("SKU003729", 290.0),  # Suéter Botones M Talla 6
            ("SKU003730", 290.0),  # Suéter Botones M Talla 6
            ("SKU003731", 290.0),  # Suéter Botones M Talla 6
            ("SKU003732", 290.0),  # Suéter Botones M Talla 6
            ("SKU003733", 290.0),  # Suéter Botones M Talla 6
            ("SKU003735", 290.0),  # Suéter Botones M Talla 8
            ("SKU003736", 290.0),  # Suéter Botones M Talla 8
            ("SKU003737", 290.0),  # Suéter Botones M Talla 8
            ("SKU003738", 290.0),  # Suéter Botones M Talla 8
            ("SKU003739", 290.0),  # Suéter Botones M Talla 8
            ("SKU003741", 290.0),  # Suéter Botones M Talla 10
            ("SKU003742", 290.0),  # Suéter Botones M Talla 10
            ("SKU003743", 290.0),  # Suéter Botones M Talla 10
            ("SKU003744", 290.0),  # Suéter Botones M Talla 10
            ("SKU003745", 290.0),  # Suéter Botones M Talla 10
            ("SKU003747", 290.0),  # Suéter Cuello V H Talla 4
            ("SKU003748", 290.0),  # Suéter Cuello V H Talla 4
            ("SKU003749", 290.0),  # Suéter Cuello V H Talla 4
            ("SKU003750", 290.0),  # Suéter Cuello V H Talla 4
            ("SKU003751", 290.0),  # Suéter Cuello V H Talla 4
            ("SKU003753", 290.0),  # Suéter Cuello V H Talla 6
            ("SKU003754", 290.0),  # Suéter Cuello V H Talla 6
            ("SKU003755", 290.0),  # Suéter Cuello V H Talla 6
            ("SKU003756", 290.0),  # Suéter Cuello V H Talla 6
            ("SKU003757", 290.0),  # Suéter Cuello V H Talla 6
            ("SKU003759", 290.0),  # Suéter Cuello V H Talla 8
            ("SKU003760", 290.0),  # Suéter Cuello V H Talla 8
            ("SKU003761", 290.0),  # Suéter Cuello V H Talla 8
            ("SKU003762", 290.0),  # Suéter Cuello V H Talla 8
            ("SKU003763", 290.0),  # Suéter Cuello V H Talla 8
            ("SKU003765", 290.0),  # Suéter Cuello V H Talla 10
            ("SKU003766", 290.0),  # Suéter Cuello V H Talla 10
            ("SKU003767", 290.0),  # Suéter Cuello V H Talla 10
            ("SKU003768", 290.0),  # Suéter Cuello V H Talla 10
            ("SKU003769", 290.0),  # Suéter Cuello V H Talla 10
            ("SKU003771", 315.0),  # Suéter Botones Talla 4
            ("SKU003772", 315.0),  # Suéter Botones Talla 6
            ("SKU003773", 315.0),  # Suéter Botones Talla 8
            ("SKU003774", 315.0),  # Suéter Botones Talla 10
            ("SKU003775", 139.0),  # Camisa Cuello Olan Blanca Talla 2
            ("SKU003776", 139.0),  # Camisa Cuello Olan Blanca Talla 4
            ("SKU003777", 139.0),  # Camisa Cuello Olan Blanca Talla 6
            ("SKU003778", 139.0),  # Camisa Cuello Olan Blanca Talla 8
            ("SKU003779", 139.0),  # Camisa Cuello Olan Blanca Talla 10
            ("SKU003780", 545.0),  # Pants 3pz Margarita Paz Paredes Talla 2
            ("SKU003781", 545.0),  # Pants 3pz Margarita Paz Paredes Talla 4
            ("SKU003782", 545.0),  # Pants 3pz Margarita Paz Paredes Talla 6
            ("SKU003783", 545.0),  # Pants 3pz Margarita Paz Paredes Talla 8
            ("SKU003784", 545.0),  # Pants 3pz Margarita Paz Paredes Talla 10
            ("SKU003785", 445.0),  # Pants 2pz Margarita Paz Paredes Talla 2
            ("SKU003786", 445.0),  # Pants 2pz Margarita Paz Paredes Talla 4
            ("SKU003787", 445.0),  # Pants 2pz Margarita Paz Paredes Talla 6
            ("SKU003788", 445.0),  # Pants 2pz Margarita Paz Paredes Talla 8
            ("SKU003789", 445.0),  # Pants 2pz Margarita Paz Paredes Talla 10
            ("SKU003794", 315.0),  # Chamarra Deportiva Ad hoc Talla 4
            ("SKU003795", 315.0),  # Chamarra Deportiva Ad hoc Talla 6
            ("SKU003796", 315.0),  # Chamarra Deportiva Ad hoc Talla 8
            ("SKU003797", 485.0),  # Pants 2pz Ignacio Ramirez Lopez Talla 4
            ("SKU003798", 485.0),  # Pants 2pz Ignacio Ramirez Lopez Talla 6
            ("SKU003799", 485.0),  # Pants 2pz Ignacio Ramirez Lopez Talla 8
            ("SKU003800", 485.0),  # Pants 2pz Ignacio Ramirez Lopez Talla 10
            ("SKU003801", 485.0),  # Pants 2pz Ignacio Ramirez Lopez Talla 12
            ("SKU003802", 495.0),  # Pants 2pz Ignacio Ramirez Lopez Talla 14
            ("SKU003803", 495.0),  # Pants 2pz Ignacio Ramirez Lopez Talla 16
            ("SKU003804", 285.0),  # Pants Suelto Azul Marino Talla 16
            ("SKU003805", 285.0),  # Pants Suelto Azul Marino Talla CH
            ("SKU003806", 285.0),  # Pants Suelto Azul Marino Talla MD
            ("SKU003807", 285.0),  # Pants Suelto Azul Marino Talla GD
            ("SKU003808", 285.0),  # Pants Suelto Azul Marino Talla EXG
            ("SKU003809", 199.0),  # Suéter Oferta Ad hoc Talla Uni
            ("SKU003810", 285.0),  # Pants Suelto Azul Marino Talla 14
            ("SKU003811", 285.0),  # Pants Suelto Azul Marino Talla 16
            ("SKU003812", 285.0),  # Pants Suelto Azul Marino Talla CH
            ("SKU003813", 285.0),  # Pants Suelto Azul Marino Talla MD
            ("SKU003814", 285.0),  # Pants Suelto Azul Marino Talla GD
            ("SKU003815", 285.0),  # Pants Suelto Azul Marino Talla EXG
            ("SKU003816", 285.0),  # Pants Suelto Azul Marino Talla 16
            ("SKU003817", 285.0),  # Pants Suelto Azul Marino Talla CH
            ("SKU003818", 285.0),  # Pants Suelto Azul Marino Talla MD
            ("SKU003819", 285.0),  # Pants Suelto Azul Marino Talla GD
            ("SKU003820", 285.0),  # Pants Suelto Azul Marino Talla EXG
            ("SKU003821", 285.0),  # Pants Suelto Azul Marino Talla 14
            ("SKU003822", 199.0),  # Playera Deportiva Ad hoc Talla 6
            ("SKU003823", 199.0),  # Playera Deportiva Ad hoc Talla 8
            ("SKU003824", 199.0),  # Playera Deportiva Ad hoc Talla 10
            ("SKU003825", 209.0),  # Playera Deportiva Ad hoc Talla 12
            ("SKU003826", 209.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU003827", 209.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU003828", 100.0),  # Playera Conjunto Ad hoc Talla ESP
            ("SKU003829", 279.0),  # Pants Suelto Verde Talla 12
            ("SKU003830", 279.0),  # Pants Suelto Verde Talla 14
            ("SKU003831", 279.0),  # Pants Suelto Verde Talla 16
            ("SKU003832", 279.0),  # Pants Suelto Verde Talla CH
            ("SKU003833", 279.0),  # Pants Suelto Verde Talla MD
            ("SKU003834", 279.0),  # Pants Suelto Verde Talla GD
            ("SKU003835", 279.0),  # Pants Suelto Verde Talla EXG
            ("SKU003836", 229.0),  # Playera Polo Blanca Talla 14
            ("SKU003837", 219.0),  # Playera Polo Ad hoc Talla 14
            ("SKU003838", 219.0),  # Playera Polo Ad hoc Talla 16
            ("SKU003839", 219.0),  # Playera Polo Ad hoc Talla CH
            ("SKU003840", 219.0),  # Playera Polo Ad hoc Talla MD
            ("SKU003841", 219.0),  # Playera Polo Ad hoc Talla GD
            ("SKU003842", 219.0),  # Playera Polo Ad hoc Talla EXG
            ("SKU003843", 239.0),  # Playera Deportiva Ad hoc Talla EXG
            ("SKU003844", 260.0),  # Pants 2pz Algodón Azul Marino Talla 4
            ("SKU003845", 260.0),  # Pants 2pz Algodón Azul Marino Talla 6
            ("SKU003846", 260.0),  # Pants 2pz Algodón Azul Marino Talla 8
            ("SKU003847", 265.0),  # Pants 2pz Algodón Azul Marino Talla 10
            ("SKU003848", 265.0),  # Pants 2pz Algodón Azul Marino Talla 12
            ("SKU003849", 275.0),  # Pants 2pz Algodón Azul Marino Talla 14
            ("SKU003850", 275.0),  # Pants 2pz Algodón Azul Marino Talla 16
            ("SKU003851", 290.0),  # Suéter Cuello V H Rojo Talla 6
            ("SKU003852", 290.0),  # Suéter Cuello V H Rojo Talla 8
            ("SKU003853", 295.0),  # Suéter Cuello V H Rojo Talla 10
            ("SKU003854", 315.0),  # Suéter Cuello V H Rojo Talla 12
            ("SKU003855", 315.0),  # Suéter Cuello V H Rojo Talla 14
            ("SKU003856", 315.0),  # Suéter Cuello V H Rojo Talla 16
            ("SKU003857", 325.0),  # Suéter Cuello V H Rojo Talla 34
            ("SKU003858", 325.0),  # Suéter Cuello V H Rojo Talla 36
            ("SKU003859", 325.0),  # Suéter Cuello V H Rojo Talla 38
            ("SKU003860", 290.0),  # Suéter Botones M Rojo Talla 6
            ("SKU003861", 290.0),  # Suéter Botones M Rojo Talla 8
            ("SKU003862", 295.0),  # Suéter Botones M Rojo Talla 10
            ("SKU003863", 315.0),  # Suéter Botones M Rojo Talla 12
            ("SKU003864", 315.0),  # Suéter Botones M Rojo Talla 14
            ("SKU003865", 315.0),  # Suéter Botones M Rojo Talla 16
            ("SKU003866", 325.0),  # Suéter Botones M Rojo Talla 34
            ("SKU003867", 325.0),  # Suéter Botones M Rojo Talla 36
            ("SKU003868", 325.0),  # Suéter Botones M Rojo Talla 38
            ("SKU003869", 240.0),  # Chaleco Rojo Talla 4
            ("SKU003870", 240.0),  # Chaleco Rojo Talla 6
            ("SKU003871", 240.0),  # Chaleco Rojo Talla 8
            ("SKU003872", 250.0),  # Chaleco Rojo Talla 10
            ("SKU003873", 250.0),  # Chaleco Rojo Talla 12
            ("SKU003874", 260.0),  # Chaleco Rojo Talla 14
            ("SKU003875", 260.0),  # Chaleco Rojo Talla 16
            ("SKU003876", 290.0),  # Chaleco Rojo Talla 34
            ("SKU003877", 290.0),  # Chaleco Rojo Talla 36
            ("SKU003878", 300.0),  # Chaleco Rojo Talla 38
            ("SKU003879", 290.0),  # Suéter Cuello V H Azul Marino Talla 4
            ("SKU003880", 290.0),  # Suéter Cuello V H Azul Marino Talla 6
            ("SKU003881", 290.0),  # Suéter Cuello V H Azul Marino Talla 8
            ("SKU003882", 295.0),  # Suéter Cuello V H Azul Marino Talla 10
            ("SKU003883", 315.0),  # Suéter Cuello V H Azul Marino Talla 12
            ("SKU003884", 315.0),  # Suéter Cuello V H Azul Marino Talla 14
            ("SKU003885", 315.0),  # Suéter Cuello V H Azul Marino Talla 16
            ("SKU003886", 325.0),  # Suéter Cuello V H Azul Marino Talla 34
            ("SKU003887", 325.0),  # Suéter Cuello V H Azul Marino Talla 36
            ("SKU003888", 290.0),  # Suéter Botones M Azul Marino Talla 4
            ("SKU003889", 290.0),  # Suéter Botones M Azul Marino Talla 6
            ("SKU003890", 290.0),  # Suéter Botones M Azul Marino Talla 8
            ("SKU003891", 295.0),  # Suéter Botones M Azul Marino Talla 10
            ("SKU003892", 315.0),  # Suéter Botones M Azul Marino Talla 12
            ("SKU003893", 315.0),  # Suéter Botones M Azul Marino Talla 14
            ("SKU003894", 315.0),  # Suéter Botones M Azul Marino Talla 16
            ("SKU003895", 325.0),  # Suéter Botones M Azul Marino Talla 34
            ("SKU003896", 325.0),  # Suéter Botones M Azul Marino Talla 36
            ("SKU003897", 240.0),  # Chaleco Azul Marino Talla 6
            ("SKU003898", 240.0),  # Chaleco Azul Marino Talla 8
            ("SKU003899", 250.0),  # Chaleco Azul Marino Talla 10
            ("SKU003900", 250.0),  # Chaleco Azul Marino Talla 12
            ("SKU003901", 260.0),  # Chaleco Azul Marino Talla 14
            ("SKU003902", 260.0),  # Chaleco Azul Marino Talla 16
            ("SKU003903", 270.0),  # Chaleco Azul Marino Talla 32
            ("SKU003904", 290.0),  # Chaleco Azul Marino Talla 34
            ("SKU003905", 345.0),  # Suéter Azul Marino Talla 14
            ("SKU003906", 345.0),  # Suéter Azul Marino Talla 16
            ("SKU003907", 345.0),  # Suéter Azul Marino Talla 32
            ("SKU003908", 345.0),  # Suéter Azul Marino Talla 34
            ("SKU003909", 345.0),  # Suéter Azul Marino Talla 36
            ("SKU003910", 345.0),  # Suéter Azul Marino Talla 38
            ("SKU003911", 355.0),  # Suéter Azul Marino Talla 40
            ("SKU003912", 355.0),  # Suéter Azul Marino Talla 42
            ("SKU003913", 290.0),  # Suéter Botones M Azul Marino Talla 4
            ("SKU003914", 290.0),  # Suéter Botones M Azul Marino Talla 6
            ("SKU003915", 290.0),  # Suéter Botones M Azul Marino Talla 8
            ("SKU003916", 295.0),  # Suéter Botones M Azul Marino Talla 10
            ("SKU003917", 315.0),  # Suéter Botones M Azul Marino Talla 12
            ("SKU003918", 315.0),  # Suéter Botones M Azul Marino Talla 14
            ("SKU003919", 315.0),  # Suéter Botones M Azul Marino Talla 16
            ("SKU003920", 325.0),  # Suéter Botones M Azul Marino Talla 32
            ("SKU003921", 325.0),  # Suéter Botones M Azul Marino Talla 34
            ("SKU003922", 325.0),  # Suéter Botones M Azul Marino Talla 36
            ("SKU003923", 325.0),  # Suéter Botones M Azul Marino Talla 38
            ("SKU003924", 290.0),  # Suéter Cuello V H Azul Marino Talla 4
            ("SKU003925", 290.0),  # Suéter Cuello V H Azul Marino Talla 6
            ("SKU003926", 290.0),  # Suéter Cuello V H Azul Marino Talla 8
            ("SKU003927", 295.0),  # Suéter Cuello V H Azul Marino Talla 10
            ("SKU003928", 315.0),  # Suéter Cuello V H Azul Marino Talla 12
            ("SKU003929", 315.0),  # Suéter Cuello V H Azul Marino Talla 14
            ("SKU003930", 315.0),  # Suéter Cuello V H Azul Marino Talla 16
            ("SKU003931", 325.0),  # Suéter Cuello V H Azul Marino Talla 34
            ("SKU003932", 325.0),  # Suéter Cuello V H Azul Marino Talla 36
            ("SKU003933", 325.0),  # Suéter Cuello V H Azul Marino Talla 38
            ("SKU003934", 239.0),  # Falda Azul Talla 4
            ("SKU003935", 239.0),  # Falda Azul Talla 6
            ("SKU003936", 239.0),  # Falda Azul Talla 8
            ("SKU003937", 445.0),  # Pants 2pz Vicente Guerrero Talla 4
            ("SKU003938", 445.0),  # Pants 2pz Vicente Guerrero Talla 6
            ("SKU003939", 445.0),  # Pants 2pz Vicente Guerrero Talla 8
            ("SKU003940", 175.0),  # Playera Blanca Talla 4
            ("SKU003941", 175.0),  # Playera Blanca Talla 6
            ("SKU003942", 175.0),  # Playera Blanca Talla 8
            ("SKU003943", 199.0),  # Playera Polo Gris Talla 4
            ("SKU003944", 199.0),  # Playera Polo Gris Talla 6
            ("SKU003945", 199.0),  # Playera Polo Gris Talla 8
            ("SKU003946", 199.0),  # Playera Polo Gris Talla 10
            ("SKU003947", 199.0),  # Playera Polo Gris Talla 12
            ("SKU003948", 199.0),  # Playera Polo Gris Talla 14
            ("SKU003949", 199.0),  # Playera Polo Gris Talla 16
            ("SKU003950", 215.0),  # Playera Polo Gris Talla CH
            ("SKU003951", 225.0),  # Playera Polo Gris Talla MD
            ("SKU003952", 235.0),  # Playera Polo Gris Talla GD
            ("SKU003953", 615.0),  # Pants 2pz Deportivo Bicentenario Talla EXG
            ("SKU003954", 290.0),  # Suéter Cuello V Azul Marino Talla 6
            ("SKU003955", 290.0),  # Suéter Cuello V Azul Marino Talla 8
            ("SKU003956", 295.0),  # Suéter Cuello V Azul Marino Talla 10
            ("SKU003957", 315.0),  # Suéter Cuello V Azul Marino Talla 12
            ("SKU003958", 315.0),  # Suéter Cuello V Azul Marino Talla 14
            ("SKU003959", 315.0),  # Suéter Cuello V Azul Marino Talla 16
            ("SKU003960", 290.0),  # Suéter Botones Azul Marino Talla 6
            ("SKU003961", 290.0),  # Suéter Botones Azul Marino Talla 8
            ("SKU003962", 295.0),  # Suéter Botones Azul Marino Talla 10
            ("SKU003963", 315.0),  # Suéter Botones Azul Marino Talla 12
            ("SKU003964", 315.0),  # Suéter Botones Azul Marino Talla 14
            ("SKU003965", 315.0),  # Suéter Botones Azul Marino Talla 16
            ("SKU003966", 195.0),  # Playera Chazarilla Azul Marino Talla 18
            ("SKU003967", 195.0),  # Playera Chazarilla Verde Talla 18
            ("SKU003968", 195.0),  # Playera Chazarilla Azul Marino Talla 20
            ("SKU003969", 195.0),  # Playera Chazarilla Verde Talla 20
            ("SKU003970", 295.0),  # Pantalón Vestir Caqui Talla 42
            ("SKU003977", 139.0),  # Camisa Cuello Olan Blanca Talla 12
            ("SKU003978", 139.0),  # Camisa Cuello Olan Blanca Talla 14
            ("SKU003979", 139.0),  # Camisa Cuello Olan Blanca Talla 16
            ("SKU003980", 139.0),  # Camisa Cuello Olan Blanca Talla CH
            ("SKU003981", 139.0),  # Camisa Cuello Olan Blanca Talla MD
            ("SKU003982", 139.0),  # Camisa Cuello Olan Blanca Talla GD
            ("SKU003983", 139.0),  # Camisa Cuello Olan Azul Talla 2
            ("SKU003984", 139.0),  # Camisa Cuello Olan Rojo Talla 2
            ("SKU003985", 139.0),  # Camisa Cuello Olan Vino Talla 2
            ("SKU003986", 139.0),  # Camisa Cuello Olan Azul Talla 4
            ("SKU003987", 139.0),  # Camisa Cuello Olan Rojo Talla 4
            ("SKU003988", 139.0),  # Camisa Cuello Olan Vino Talla 4
            ("SKU003989", 139.0),  # Camisa Cuello Olan Azul Talla 6
            ("SKU003990", 139.0),  # Camisa Cuello Olan Rojo Talla 6
            ("SKU003991", 139.0),  # Camisa Cuello Olan Vino Talla 6
            ("SKU003992", 139.0),  # Camisa Cuello Olan Azul Talla 8
            ("SKU003993", 139.0),  # Camisa Cuello Olan Rojo Talla 8
            ("SKU003994", 139.0),  # Camisa Cuello Olan Vino Talla 8
            ("SKU003995", 139.0),  # Camisa Cuello Olan Azul Talla 10
            ("SKU003996", 139.0),  # Camisa Cuello Olan Rojo Talla 10
            ("SKU003997", 139.0),  # Camisa Cuello Olan Vino Talla 10
            ("SKU003998", 199.0),  # Playera Polo Gris Talla 4
            ("SKU003999", 199.0),  # Playera Polo Gris Talla 6
            ("SKU004000", 199.0),  # Playera Polo Gris Talla 8
            ("SKU004001", 199.0),  # Playera Polo Gris Talla 10
            ("SKU004002", 199.0),  # Playera Polo Gris Talla 12
            ("SKU004003", 199.0),  # Playera Polo Gris Talla 14
            ("SKU004004", 199.0),  # Playera Polo Gris Talla 16
            ("SKU004005", 215.0),  # Playera Polo Gris Talla CH
            ("SKU004006", 225.0),  # Playera Polo Gris Talla MD
            ("SKU004007", 235.0),  # Playera Polo Gris Talla GD
            ("SKU004008", 290.0),  # Suéter Cuello V H Azul Marino Talla 4
            ("SKU004009", 290.0),  # Suéter Cuello V H Azul Marino Talla 6
            ("SKU004010", 290.0),  # Suéter Cuello V H Azul Marino Talla 8
            ("SKU004011", 295.0),  # Suéter Cuello V H Azul Marino Talla 10
            ("SKU004012", 315.0),  # Suéter Cuello V H Azul Marino Talla 12
            ("SKU004013", 315.0),  # Suéter Cuello V H Azul Marino Talla 14
            ("SKU004014", 315.0),  # Suéter Cuello V H Azul Marino Talla 16
            ("SKU004015", 325.0),  # Suéter Cuello V H Azul Marino Talla 34
            ("SKU004016", 325.0),  # Suéter Cuello V H Azul Marino Talla 36
            ("SKU004017", 325.0),  # Suéter Cuello V H Azul Marino Talla 38
            ("SKU004018", 335.0),  # Suéter Cuello V H Azul Marino Talla 40
            ("SKU004019", 290.0),  # Suéter Botones M Azul Marino Talla 4
            ("SKU004020", 290.0),  # Suéter Botones M Azul Marino Talla 6
            ("SKU004021", 290.0),  # Suéter Botones M Azul Marino Talla 8
            ("SKU004022", 295.0),  # Suéter Botones M Azul Marino Talla 10
            ("SKU004023", 315.0),  # Suéter Botones M Azul Marino Talla 12
            ("SKU004024", 315.0),  # Suéter Botones M Azul Marino Talla 14
            ("SKU004025", 315.0),  # Suéter Botones M Azul Marino Talla 16
            ("SKU004026", 325.0),  # Suéter Botones M Azul Marino Talla 34
            ("SKU004027", 325.0),  # Suéter Botones M Azul Marino Talla 36
            ("SKU004028", 325.0),  # Suéter Botones M Azul Marino Talla 38
            ("SKU004029", 335.0),  # Suéter Botones M Azul Marino Talla 40
            ("SKU004030", 240.0),  # Chaleco Azul Marino Talla 4
            ("SKU004031", 240.0),  # Chaleco Azul Marino Talla 6
            ("SKU004032", 240.0),  # Chaleco Azul Marino Talla 8
            ("SKU004033", 250.0),  # Chaleco Azul Marino Talla 10
            ("SKU004034", 250.0),  # Chaleco Azul Marino Talla 12
            ("SKU004035", 260.0),  # Chaleco Azul Marino Talla 14
            ("SKU004036", 260.0),  # Chaleco Azul Marino Talla 16
            ("SKU004037", 290.0),  # Chaleco Azul Marino Talla 34
            ("SKU004038", 290.0),  # Chaleco Azul Marino Talla 36
            ("SKU004039", 300.0),  # Chaleco Azul Marino Talla 38
            ("SKU004040", 300.0),  # Chaleco Azul Marino Talla 40
            ("SKU004041", 245.0),  # Falda Escolar Pata de gallo Talla 32
            ("SKU004042", 245.0),  # Falda Escolar Pata de gallo Talla 34
            ("SKU004043", 255.0),  # Falda Escolar Pata de gallo Talla 36
            ("SKU004044", 255.0),  # Falda Escolar Pata de gallo Talla 38
            ("SKU004045", 325.0),  # Suéter Cuello V H Azul Marino Talla 14
            ("SKU004046", 325.0),  # Suéter Cuello V H Azul Marino Talla 16
            ("SKU004047", 345.0),  # Suéter Cuello V H Azul Marino Talla 32
            ("SKU004048", 345.0),  # Suéter Cuello V H Azul Marino Talla 34
            ("SKU004049", 345.0),  # Suéter Cuello V H Azul Marino Talla 36
            ("SKU004050", 345.0),  # Suéter Cuello V H Azul Marino Talla 38
            ("SKU004051", 345.0),  # Suéter Cuello V H Azul Marino Talla 40
            ("SKU004052", 345.0),  # Suéter Cuello V H Azul Marino Talla 42
            ("SKU004053", 355.0),  # Suéter Cuello V H Azul Marino Talla 44
            ("SKU004054", 325.0),  # Suéter Botones M Azul Marino Talla 14
            ("SKU004055", 325.0),  # Suéter Botones M Azul Marino Talla 16
            ("SKU004056", 345.0),  # Suéter Botones M Azul Marino Talla 32
            ("SKU004057", 345.0),  # Suéter Botones M Azul Marino Talla 34
            ("SKU004058", 345.0),  # Suéter Botones M Azul Marino Talla 36
            ("SKU004059", 345.0),  # Suéter Botones M Azul Marino Talla 38
            ("SKU004060", 345.0),  # Suéter Botones M Azul Marino Talla 40
            ("SKU004061", 345.0),  # Suéter Botones M Azul Marino Talla 42
            ("SKU004062", 355.0),  # Suéter Botones M Azul Marino Talla 44
            ("SKU004063", 325.0),  # Suéter Cuello V H Azul Marino Talla 12
            ("SKU004064", 325.0),  # Suéter Botones M Azul Marino Talla 12
            ("SKU004065", 325.0),  # Suéter Cuello V H Verde Talla 12
            ("SKU004066", 325.0),  # Suéter Cuello V H Verde Talla 14
            ("SKU004067", 325.0),  # Suéter Cuello V H Verde Talla 16
            ("SKU004068", 345.0),  # Suéter Cuello V H Verde Talla 32
            ("SKU004069", 345.0),  # Suéter Cuello V H Verde Talla 34
            ("SKU004070", 345.0),  # Suéter Cuello V H Verde Talla 36
            ("SKU004071", 345.0),  # Suéter Cuello V H Verde Talla 38
            ("SKU004072", 345.0),  # Suéter Cuello V H Verde Talla 40
            ("SKU004073", 345.0),  # Suéter Cuello V H Verde Talla 42
            ("SKU004074", 355.0),  # Suéter Cuello V H Verde Talla 44
            ("SKU004075", 325.0),  # Suéter Botones M Verde Talla 12
            ("SKU004076", 325.0),  # Suéter Botones M Verde Talla 14
            ("SKU004077", 325.0),  # Suéter Botones M Verde Talla 16
            ("SKU004078", 345.0),  # Suéter Botones M Verde Talla 32
            ("SKU004079", 345.0),  # Suéter Botones M Verde Talla 34
            ("SKU004080", 345.0),  # Suéter Botones M Verde Talla 36
            ("SKU004081", 345.0),  # Suéter Botones M Verde Talla 38
            ("SKU004082", 345.0),  # Suéter Botones M Verde Talla 40
            ("SKU004083", 345.0),  # Suéter Botones M Verde Talla 42
            ("SKU004084", 355.0),  # Suéter Botones M Verde Talla 44
            ("SKU004085", 290.0),  # Suéter Cuello V H Azul Marino Talla 4
            ("SKU004086", 290.0),  # Suéter Cuello V H Azul Marino Talla 6
            ("SKU004087", 290.0),  # Suéter Cuello V H Azul Marino Talla 8
            ("SKU004088", 295.0),  # Suéter Cuello V H Azul Marino Talla 10
            ("SKU004089", 315.0),  # Suéter Cuello V H Azul Marino Talla 12
            ("SKU004090", 315.0),  # Suéter Cuello V H Azul Marino Talla 14
            ("SKU004091", 315.0),  # Suéter Cuello V H Azul Marino Talla 16
            ("SKU004092", 325.0),  # Suéter Cuello V H Azul Marino Talla 32
            ("SKU004093", 325.0),  # Suéter Cuello V H Azul Marino Talla 34
            ("SKU004094", 325.0),  # Suéter Cuello V H Azul Marino Talla 36
            ("SKU004095", 325.0),  # Suéter Cuello V H Azul Marino Talla 38
            ("SKU004096", 335.0),  # Suéter Cuello V H Azul Marino Talla 40
            ("SKU004097", 335.0),  # Suéter Cuello V H Azul Marino Talla 42
            ("SKU004098", 290.0),  # Suéter Botones M Azul Marino Talla 4
            ("SKU004099", 290.0),  # Suéter Botones M Azul Marino Talla 6
            ("SKU004100", 290.0),  # Suéter Botones M Azul Marino Talla 8
            ("SKU004101", 295.0),  # Suéter Botones M Azul Marino Talla 10
            ("SKU004102", 315.0),  # Suéter Botones M Azul Marino Talla 12
            ("SKU004103", 315.0),  # Suéter Botones M Azul Marino Talla 14
            ("SKU004104", 315.0),  # Suéter Botones M Azul Marino Talla 16
            ("SKU004105", 325.0),  # Suéter Botones M Azul Marino Talla 32
            ("SKU004106", 325.0),  # Suéter Botones M Azul Marino Talla 34
            ("SKU004107", 325.0),  # Suéter Botones M Azul Marino Talla 36
            ("SKU004108", 325.0),  # Suéter Botones M Azul Marino Talla 38
            ("SKU004109", 335.0),  # Suéter Botones M Azul Marino Talla 40
            ("SKU004110", 335.0),  # Suéter Botones M Azul Marino Talla 42
            ("SKU004111", 240.0),  # Chaleco Azul Marino Talla 4
            ("SKU004112", 240.0),  # Chaleco Azul Marino Talla 6
            ("SKU004113", 240.0),  # Chaleco Azul Marino Talla 8
            ("SKU004114", 250.0),  # Chaleco Azul Marino Talla 10
            ("SKU004115", 250.0),  # Chaleco Azul Marino Talla 12
            ("SKU004116", 260.0),  # Chaleco Azul Marino Talla 14
            ("SKU004117", 260.0),  # Chaleco Azul Marino Talla 16
            ("SKU004118", 270.0),  # Chaleco Azul Marino Talla 32
            ("SKU004119", 290.0),  # Chaleco Azul Marino Talla 34
            ("SKU004120", 290.0),  # Chaleco Azul Marino Talla 36
            ("SKU004121", 300.0),  # Chaleco Azul Marino Talla 38
            ("SKU004122", 300.0),  # Chaleco Azul Marino Talla 40
            ("SKU004123", 290.0),  # Chaleco Azul Marino Talla 42
            ("SKU004124", 290.0),  # Suéter Cuello V H Rojo Talla 4
            ("SKU004125", 290.0),  # Suéter Cuello V H Rojo Talla 6
            ("SKU004126", 290.0),  # Suéter Cuello V H Rojo Talla 8
            ("SKU004127", 295.0),  # Suéter Cuello V H Rojo Talla 10
            ("SKU004128", 315.0),  # Suéter Cuello V H Rojo Talla 12
            ("SKU004129", 315.0),  # Suéter Cuello V H Rojo Talla 14
            ("SKU004130", 315.0),  # Suéter Cuello V H Rojo Talla 16
            ("SKU004131", 325.0),  # Suéter Cuello V H Rojo Talla 32
            ("SKU004132", 325.0),  # Suéter Cuello V H Rojo Talla 34
            ("SKU004133", 325.0),  # Suéter Cuello V H Rojo Talla 36
            ("SKU004134", 325.0),  # Suéter Cuello V H Rojo Talla 38
            ("SKU004135", 335.0),  # Suéter Cuello V H Rojo Talla 40
            ("SKU004136", 290.0),  # Suéter Botones M Rojo Talla 4
            ("SKU004137", 290.0),  # Suéter Botones M Rojo Talla 6
            ("SKU004138", 290.0),  # Suéter Botones M Rojo Talla 8
            ("SKU004139", 295.0),  # Suéter Botones M Rojo Talla 10
            ("SKU004140", 315.0),  # Suéter Botones M Rojo Talla 12
            ("SKU004141", 315.0),  # Suéter Botones M Rojo Talla 14
            ("SKU004142", 315.0),  # Suéter Botones M Rojo Talla 16
            ("SKU004143", 325.0),  # Suéter Botones M Rojo Talla 32
            ("SKU004144", 325.0),  # Suéter Botones M Rojo Talla 34
            ("SKU004145", 325.0),  # Suéter Botones M Rojo Talla 36
            ("SKU004146", 325.0),  # Suéter Botones M Rojo Talla 38
            ("SKU004147", 335.0),  # Suéter Botones M Rojo Talla 40
            ("SKU004148", 240.0),  # Chaleco Rojo Talla 4
            ("SKU004149", 240.0),  # Chaleco Rojo Talla 6
            ("SKU004150", 240.0),  # Chaleco Rojo Talla 8
            ("SKU004151", 250.0),  # Chaleco Rojo Talla 10
            ("SKU004152", 250.0),  # Chaleco Rojo Talla 12
            ("SKU004153", 260.0),  # Chaleco Rojo Talla 14
            ("SKU004154", 260.0),  # Chaleco Rojo Talla 16
            ("SKU004155", 270.0),  # Chaleco Rojo Talla 32
            ("SKU004156", 290.0),  # Chaleco Rojo Talla 34
            ("SKU004157", 290.0),  # Chaleco Rojo Talla 36
            ("SKU004158", 300.0),  # Chaleco Rojo Talla 38
            ("SKU004159", 300.0),  # Chaleco Rojo Talla 40
            ("SKU004160", 245.0),  # Chaleco Azul Marino Talla 12
            ("SKU004161", 245.0),  # Chaleco Azul Marino Talla 14
            ("SKU004162", 245.0),  # Chaleco Azul Marino Talla 16
            ("SKU004163", 265.0),  # Chaleco Azul Marino Talla 32
            ("SKU004164", 265.0),  # Chaleco Azul Marino Talla 34
            ("SKU004165", 275.0),  # Chaleco Azul Marino Talla 36
            ("SKU004166", 275.0),  # Chaleco Azul Marino Talla 38
            ("SKU004167", 275.0),  # Chaleco Azul Marino Talla 40
            ("SKU004168", 275.0),  # Chaleco Azul Marino Talla 42
            ("SKU004169", 290.0),  # Suéter Cuello V H Rojo Talla 4
            ("SKU004170", 290.0),  # Suéter Cuello V H Rojo Talla 6
            ("SKU004171", 290.0),  # Suéter Cuello V H Rojo Talla 8
            ("SKU004172", 295.0),  # Suéter Cuello V H Rojo Talla 10
            ("SKU004173", 315.0),  # Suéter Cuello V H Rojo Talla 12
            ("SKU004174", 315.0),  # Suéter Cuello V H Rojo Talla 14
            ("SKU004175", 315.0),  # Suéter Cuello V H Rojo Talla 16
            ("SKU004176", 325.0),  # Suéter Cuello V H Rojo Talla 32
            ("SKU004177", 325.0),  # Suéter Cuello V H Rojo Talla 34
            ("SKU004178", 325.0),  # Suéter Cuello V H Rojo Talla 36
            ("SKU004179", 325.0),  # Suéter Cuello V H Rojo Talla 38
            ("SKU004180", 335.0),  # Suéter Cuello V H Rojo Talla 40
            ("SKU004181", 335.0),  # Suéter Cuello V H Rojo Talla 42
            ("SKU004182", 290.0),  # Suéter Botones M Rojo Talla 4
            ("SKU004183", 290.0),  # Suéter Botones M Rojo Talla 6
            ("SKU004184", 290.0),  # Suéter Botones M Rojo Talla 8
            ("SKU004185", 295.0),  # Suéter Botones M Rojo Talla 10
            ("SKU004186", 315.0),  # Suéter Botones M Rojo Talla 12
            ("SKU004187", 315.0),  # Suéter Botones M Rojo Talla 14
            ("SKU004188", 315.0),  # Suéter Botones M Rojo Talla 16
            ("SKU004189", 325.0),  # Suéter Botones M Rojo Talla 32
            ("SKU004190", 325.0),  # Suéter Botones M Rojo Talla 34
            ("SKU004191", 325.0),  # Suéter Botones M Rojo Talla 36
            ("SKU004192", 325.0),  # Suéter Botones M Rojo Talla 38
            ("SKU004193", 335.0),  # Suéter Botones M Rojo Talla 40
            ("SKU004194", 335.0),  # Suéter Botones M Rojo Talla 42
            ("SKU004195", 325.0),  # Suéter Cuello V H Verde Talla 12
            ("SKU004196", 325.0),  # Suéter Cuello V H Verde Talla 14
            ("SKU004197", 325.0),  # Suéter Cuello V H Verde Talla 16
            ("SKU004198", 345.0),  # Suéter Cuello V H Verde Talla 30
            ("SKU004199", 345.0),  # Suéter Cuello V H Verde Talla 32
            ("SKU004200", 345.0),  # Suéter Cuello V H Verde Talla 34
            ("SKU004201", 345.0),  # Suéter Cuello V H Verde Talla 36
            ("SKU004202", 345.0),  # Suéter Cuello V H Verde Talla 38
            ("SKU004203", 345.0),  # Suéter Cuello V H Verde Talla 40
            ("SKU004204", 345.0),  # Suéter Cuello V H Verde Talla 42
            ("SKU004205", 345.0),  # Suéter Cuello V H Verde Talla 44
            ("SKU004206", 325.0),  # Suéter Botones M Verde Talla 12
            ("SKU004207", 325.0),  # Suéter Botones M Verde Talla 14
            ("SKU004208", 325.0),  # Suéter Botones M Verde Talla 16
            ("SKU004209", 345.0),  # Suéter Botones M Verde Talla 30
            ("SKU004210", 345.0),  # Suéter Botones M Verde Talla 32
            ("SKU004211", 345.0),  # Suéter Botones M Verde Talla 34
            ("SKU004212", 345.0),  # Suéter Botones M Verde Talla 36
            ("SKU004213", 345.0),  # Suéter Botones M Verde Talla 38
            ("SKU004214", 345.0),  # Suéter Botones M Verde Talla 40
            ("SKU004215", 345.0),  # Suéter Botones M Verde Talla 42
            ("SKU004216", 355.0),  # Suéter Botones M Verde Talla 44
            ("SKU004217", 245.0),  # Chaleco Verde Talla 12
            ("SKU004218", 245.0),  # Chaleco Verde Talla 14
            ("SKU004219", 245.0),  # Chaleco Verde Talla 16
            ("SKU004220", 265.0),  # Chaleco Verde Talla 30
            ("SKU004221", 265.0),  # Chaleco Verde Talla 32
            ("SKU004222", 265.0),  # Chaleco Verde Talla 34
            ("SKU004223", 275.0),  # Chaleco Verde Talla 36
            ("SKU004224", 275.0),  # Chaleco Verde Talla 38
            ("SKU004225", 275.0),  # Chaleco Verde Talla 40
            ("SKU004226", 275.0),  # Chaleco Verde Talla 42
            ("SKU004227", 275.0),  # Chaleco Verde Talla 44
            ("SKU004228", 240.0),  # Chaleco Azul Marino Talla 4
            ("SKU004229", 240.0),  # Chaleco Azul Marino Talla 6
            ("SKU004230", 240.0),  # Chaleco Azul Marino Talla 8
            ("SKU004231", 250.0),  # Chaleco Azul Marino Talla 10
            ("SKU004232", 250.0),  # Chaleco Azul Marino Talla 12
            ("SKU004233", 260.0),  # Chaleco Azul Marino Talla 14
            ("SKU004234", 260.0),  # Chaleco Azul Marino Talla 16
            ("SKU004235", 270.0),  # Chaleco Azul Marino Talla CH
            ("SKU004236", 270.0),  # Chaleco Azul Marino Talla MD
            ("SKU004237", 270.0),  # Chaleco Azul Marino Talla GD
            ("SKU004238", 270.0),  # Chaleco Azul Marino Talla EXG
            ("SKU004239", 290.0),  # Suéter Azul Marino Talla 4
            ("SKU004240", 290.0),  # Suéter Azul Marino Talla 6
            ("SKU004241", 290.0),  # Suéter Azul Marino Talla 8
            ("SKU004242", 295.0),  # Suéter Azul Marino Talla 10
            ("SKU004243", 315.0),  # Suéter Azul Marino Talla 12
            ("SKU004244", 315.0),  # Suéter Azul Marino Talla 14
            ("SKU004245", 315.0),  # Suéter Azul Marino Talla 16
            ("SKU004250", 325.0),  # Suéter Azul Marino Talla 32
            ("SKU004251", 325.0),  # Suéter Azul Marino Talla 34
            ("SKU004252", 325.0),  # Suéter Azul Marino Talla 36
            ("SKU004253", 325.0),  # Suéter Azul Marino Talla 38
            ("SKU004254", 335.0),  # Suéter Azul Marino Talla 40
            ("SKU004255", 175.0),  # Playera Deportiva Blanca Talla 2
            ("SKU004256", 175.0),  # Playera Deportiva Blanca Talla 4
            ("SKU004257", 175.0),  # Playera Deportiva Blanca Talla 6
            ("SKU004258", 175.0),  # Playera Deportiva Blanca Talla 8
            ("SKU004270", 290.0),  # Suéter Cuello V H Azul Talla 4
            ("SKU004271", 290.0),  # Suéter Cuello V H Azul Talla 6
            ("SKU004272", 290.0),  # Suéter Cuello V H Azul Talla 8
            ("SKU004273", 295.0),  # Suéter Cuello V H Azul Talla 10
            ("SKU004274", 315.0),  # Suéter Cuello V H Azul Talla 12
            ("SKU004275", 315.0),  # Suéter Cuello V H Azul Talla 14
            ("SKU004276", 315.0),  # Suéter Cuello V H Azul Talla 16
            ("SKU004277", 325.0),  # Suéter Cuello V H Azul Talla 32
            ("SKU004278", 325.0),  # Suéter Cuello V H Azul Talla 34
            ("SKU004279", 325.0),  # Suéter Cuello V H Azul Talla 36
            ("SKU004280", 325.0),  # Suéter Cuello V H Azul Talla 38
            ("SKU004281", 290.0),  # Suéter Botones M Azul Talla 4
            ("SKU004282", 290.0),  # Suéter Botones M Azul Talla 6
            ("SKU004283", 290.0),  # Suéter Botones M Azul Talla 8
            ("SKU004284", 295.0),  # Suéter Botones M Azul Talla 10
            ("SKU004285", 315.0),  # Suéter Botones M Azul Talla 12
            ("SKU004286", 315.0),  # Suéter Botones M Azul Talla 14
            ("SKU004287", 315.0),  # Suéter Botones M Azul Talla 16
            ("SKU004288", 325.0),  # Suéter Botones M Azul Talla 32
            ("SKU004289", 325.0),  # Suéter Botones M Azul Talla 34
            ("SKU004290", 325.0),  # Suéter Botones M Azul Talla 36
            ("SKU004291", 325.0),  # Suéter Botones M Azul Talla 38
            ("SKU004292", 240.0),  # Chaleco Azul Talla 4
            ("SKU004293", 240.0),  # Chaleco Azul Talla 6
            ("SKU004294", 240.0),  # Chaleco Azul Talla 8
            ("SKU004295", 250.0),  # Chaleco Azul Talla 10
            ("SKU004296", 250.0),  # Chaleco Azul Talla 12
            ("SKU004297", 260.0),  # Chaleco Azul Talla 14
            ("SKU004298", 260.0),  # Chaleco Azul Talla 16
            ("SKU004299", 270.0),  # Chaleco Azul Talla 32
            ("SKU004300", 290.0),  # Chaleco Azul Talla 34
            ("SKU004301", 290.0),  # Chaleco Azul Talla 36
            ("SKU004302", 300.0),  # Chaleco Azul Talla 38
            ("SKU004303", 300.0),  # Chaleco Azul Talla 40
            ("SKU004304", 290.0),  # Chaleco Azul Talla 42
            ("SKU004305", 515.0),  # Pants 2pz Deportivo Sor Juana Inés de la Cruz Talla 4
            ("SKU004306", 515.0),  # Pants 2pz Deportivo Sor Juana Inés de la Cruz Talla 6
            ("SKU004307", 515.0),  # Pants 2pz Deportivo Sor Juana Inés de la Cruz Talla 8
            ("SKU004308", 515.0),  # Pants 2pz Deportivo Sor Juana Inés de la Cruz Talla 10
            ("SKU004309", 290.0),  # Suéter Cuello V H Vino Talla 4
            ("SKU004310", 290.0),  # Suéter Cuello V H Vino Talla 6
            ("SKU004311", 290.0),  # Suéter Cuello V H Vino Talla 8
            ("SKU004312", 295.0),  # Suéter Cuello V H Vino Talla 10
            ("SKU004313", 315.0),  # Suéter Cuello V H Vino Talla 12
            ("SKU004314", 315.0),  # Suéter Cuello V H Vino Talla 14
            ("SKU004315", 315.0),  # Suéter Cuello V H Vino Talla 16
            ("SKU004316", 325.0),  # Suéter Cuello V H Vino Talla 34
            ("SKU004317", 325.0),  # Suéter Cuello V H Vino Talla 36
            ("SKU004318", 325.0),  # Suéter Cuello V H Vino Talla 38
            ("SKU004319", 290.0),  # Suéter Botones M Vino Talla 4
            ("SKU004320", 290.0),  # Suéter Botones M Vino Talla 6
            ("SKU004321", 290.0),  # Suéter Botones M Vino Talla 8
            ("SKU004322", 295.0),  # Suéter Botones M Vino Talla 10
            ("SKU004323", 315.0),  # Suéter Botones M Vino Talla 12
            ("SKU004324", 315.0),  # Suéter Botones M Vino Talla 14
            ("SKU004325", 315.0),  # Suéter Botones M Vino Talla 16
            ("SKU004326", 325.0),  # Suéter Botones M Vino Talla 34
            ("SKU004327", 325.0),  # Suéter Botones M Vino Talla 36
            ("SKU004328", 325.0),  # Suéter Botones M Vino Talla 38
            ("SKU004329", 240.0),  # Chaleco Beige Talla 4
            ("SKU004330", 240.0),  # Chaleco Beige Talla 6
            ("SKU004331", 240.0),  # Chaleco Beige Talla 8
            ("SKU004332", 250.0),  # Chaleco Beige Talla 10
            ("SKU004333", 250.0),  # Chaleco Beige Talla 12
            ("SKU004334", 260.0),  # Chaleco Beige Talla 14
            ("SKU004335", 260.0),  # Chaleco Beige Talla 16
            ("SKU004336", 290.0),  # Chaleco Beige Talla 34
            ("SKU004337", 290.0),  # Chaleco Beige Talla 36
            ("SKU004338", 300.0),  # Chaleco Beige Talla 38
            ("SKU004339", 485.0),  # Pants 2pz Deportivo Narciso Mendoza Talla 4
            ("SKU004340", 485.0),  # Pants 2pz Deportivo Narciso Mendoza Talla 6
            ("SKU004341", 485.0),  # Pants 2pz Deportivo Narciso Mendoza Talla 8
            ("SKU004342", 485.0),  # Pants 2pz Deportivo Narciso Mendoza Talla 10
            ("SKU004343", 485.0),  # Pants 2pz Deportivo Narciso Mendoza Talla 12
            ("SKU004344", 495.0),  # Pants 2pz Deportivo Narciso Mendoza Talla 14
            ("SKU004345", 495.0),  # Pants 2pz Deportivo Narciso Mendoza Talla 16
            ("SKU004346", 495.0),  # Pants 2pz Deportivo Narciso Mendoza Talla 18
            ("SKU004347", 199.0),  # Playera Deportivo Ad hoc Talla 4
            ("SKU004348", 199.0),  # Playera Deportivo Ad hoc Talla 6
            ("SKU004349", 199.0),  # Playera Deportivo Ad hoc Talla 8
            ("SKU004350", 199.0),  # Playera Deportivo Ad hoc Talla 10
            ("SKU004351", 209.0),  # Playera Deportivo Ad hoc Talla 12
            ("SKU004352", 209.0),  # Playera Deportivo Ad hoc Talla 14
            ("SKU004353", 209.0),  # Playera Deportivo Ad hoc Talla 16
            ("SKU004354", 215.0),  # Playera Deportivo Ad hoc Talla 30
            ("SKU004355", 219.0),  # Playera Deportivo Ad hoc Talla CH
            ("SKU004364", 575.0),  # Pants 2pz Deportivo Adolfo Lopez Mateo Talla 4
            ("SKU004365", 575.0),  # Pants 2pz Deportivo Adolfo Lopez Mateo Talla 6
            ("SKU004366", 575.0),  # Pants 2pz Deportivo Adolfo Lopez Mateo Talla 8
            ("SKU004367", 585.0),  # Pants 2pz Deportivo Adolfo Lopez Mateo Talla 10
            ("SKU004368", 585.0),  # Pants 2pz Deportivo Adolfo Lopez Mateo Talla 12
            ("SKU004369", 595.0),  # Pants 2pz Deportivo Adolfo Lopez Mateo Talla 14
            ("SKU004370", 595.0),  # Pants 2pz Deportivo Adolfo Lopez Mateo Talla 16
            ("SKU004371", 595.0),  # Pants 2pz Deportivo Adolfo Lopez Mateo Talla 18
            ("SKU004372", 199.0),  # Playera Deportivo Ad hoc Talla 4
            ("SKU004373", 199.0),  # Playera Deportivo Ad hoc Talla 6
            ("SKU004374", 199.0),  # Playera Deportivo Ad hoc Talla 8
            ("SKU004375", 199.0),  # Playera Deportivo Ad hoc Talla 10
            ("SKU004376", 209.0),  # Playera Deportivo Ad hoc Talla 12
            ("SKU004377", 209.0),  # Playera Deportivo Ad hoc Talla 14
            ("SKU004378", 209.0),  # Playera Deportivo Ad hoc Talla 16
            ("SKU004379", 199.0),  # Playera Deportivo Ad hoc Talla 18
            ("SKU004380", 240.0),  # Chaleco Negro Talla 6
            ("SKU004381", 240.0),  # Chaleco Negro Talla 8
            ("SKU004382", 245.0),  # Chaleco Negro Talla 10
            ("SKU004383", 245.0),  # Chaleco Negro Talla 12
            ("SKU004384", 250.0),  # Chaleco Negro Talla 14
            ("SKU004385", 250.0),  # Chaleco Negro Talla 16
            ("SKU004386", 270.0),  # Chaleco Negro Talla 34
            ("SKU004387", 270.0),  # Chaleco Negro Talla 36
            ("SKU004388", 295.0),  # Suéter Cuello V H Negro Talla 10
            ("SKU004389", 315.0),  # Suéter Cuello V H Negro Talla 12
            ("SKU004390", 315.0),  # Suéter Cuello V H Negro Talla 14
            ("SKU004391", 315.0),  # Suéter Cuello V H Negro Talla 16
            ("SKU004392", 325.0),  # Suéter Cuello V H Negro Talla 34
            ("SKU004393", 325.0),  # Suéter Cuello V H Negro Talla 36
            ("SKU004394", 325.0),  # Suéter Cuello V H Negro Talla 38
            ("SKU004395", 295.0),  # Suéter Botones M Negro Talla 10
            ("SKU004396", 315.0),  # Suéter Botones M Negro Talla 12
            ("SKU004397", 315.0),  # Suéter Botones M Negro Talla 14
            ("SKU004398", 315.0),  # Suéter Botones M Negro Talla 16
            ("SKU004399", 325.0),  # Suéter Botones M Negro Talla 34
            ("SKU004400", 325.0),  # Suéter Botones M Negro Talla 36
            ("SKU004401", 325.0),  # Suéter Botones M Negro Talla 38
            ("SKU004402", 485.0),  # Pants 2pz Deportivo Palacio Talla 4
            ("SKU004403", 485.0),  # Pants 2pz Deportivo Palacio Talla 6
            ("SKU004404", 485.0),  # Pants 2pz Deportivo Palacio Talla 8
            ("SKU004405", 485.0),  # Pants 2pz Deportivo Palacio Talla 10
            ("SKU004406", 485.0),  # Pants 2pz Deportivo Palacio Talla 12
            ("SKU004407", 495.0),  # Pants 2pz Deportivo Palacio Talla 14
            ("SKU004408", 495.0),  # Pants 2pz Deportivo Palacio Talla 16
            ("SKU004409", 229.0),  # Playera Deportiva Ad hoc Talla 14
            ("SKU004410", 229.0),  # Playera Deportiva Ad hoc Talla 16
            ("SKU004411", 229.0),  # Playera Deportiva Ad hoc Talla 18
            ("SKU004412", 239.0),  # Playera Deportiva Ad hoc Talla CH
            ("SKU004413", 239.0),  # Playera Deportiva Ad hoc Talla MD
            ("SKU004414", 239.0),  # Playera Deportiva Ad hoc Talla GD
            ("SKU004415", 325.0),  # Suéter Botones M Ad hoc Talla 14
            ("SKU004416", 325.0),  # Suéter Botones M Ad hoc Talla 16
            ("SKU004417", 290.0),  # Suéter Botones M Ad hoc Talla 18
            ("SKU004418", 345.0),  # Suéter Botones M Ad hoc Talla 32
            ("SKU004419", 345.0),  # Suéter Botones M Ad hoc Talla 34
            ("SKU004420", 345.0),  # Suéter Botones M Ad hoc Talla 36
            ("SKU004421", 345.0),  # Suéter Botones M Ad hoc Talla 38
            ("SKU004422", 345.0),  # Suéter Botones M Ad hoc Talla 40
            ("SKU004423", 325.0),  # Suéter Cuello V H Ad hoc Talla 14
            ("SKU004424", 325.0),  # Suéter Cuello V H Ad hoc Talla 16
            ("SKU004425", 290.0),  # Suéter Cuello V H Ad hoc Talla 18
            ("SKU004426", 345.0),  # Suéter Cuello V H Ad hoc Talla 32
            ("SKU004427", 345.0),  # Suéter Cuello V H Ad hoc Talla 34
            ("SKU004428", 345.0),  # Suéter Cuello V H Ad hoc Talla 36
            ("SKU004429", 345.0),  # Suéter Cuello V H Ad hoc Talla 38
            ("SKU004430", 345.0),  # Suéter Cuello V H Ad hoc Talla 40
            ("SKU004431", 199.0),  # Playera Deportivo Ad hoc Talla Uni
            ("SKU004440", 229.0),  # Chaleco Negro Talla 4
            ("SKU004441", 229.0),  # Chaleco Negro Talla 6
            ("SKU004442", 229.0),  # Chaleco Negro Talla 8
            ("SKU004443", 239.0),  # Chaleco Negro Talla 10
            ("SKU004444", 239.0),  # Chaleco Negro Talla 12
            ("SKU004445", 239.0),  # Chaleco Negro Talla 14
            ("SKU004446", 239.0),  # Chaleco Negro Talla 16
            ("SKU004447", 259.0),  # Chaleco Negro Talla 32
            ("SKU004448", 259.0),  # Chaleco Negro Talla 34
            ("SKU004449", 290.0),  # Suéter Botones M Azul Marino Talla 4
            ("SKU004450", 290.0),  # Suéter Botones M Azul Marino Talla 6
            ("SKU004451", 290.0),  # Suéter Botones M Azul Marino Talla 8
            ("SKU004452", 295.0),  # Suéter Botones M Azul Marino Talla 10
            ("SKU004453", 315.0),  # Suéter Botones M Azul Marino Talla 12
            ("SKU004454", 315.0),  # Suéter Botones M Azul Marino Talla 14
            ("SKU004455", 315.0),  # Suéter Botones M Azul Marino Talla 16
            ("SKU004456", 300.0),  # Suéter Botones M Azul Marino Talla 18
            ("SKU004457", 290.0),  # Suéter Cuello V H Azul Marino Talla 4
            ("SKU004458", 290.0),  # Suéter Cuello V H Azul Marino Talla 6
            ("SKU004459", 290.0),  # Suéter Cuello V H Azul Marino Talla 8
            ("SKU004460", 295.0),  # Suéter Cuello V H Azul Marino Talla 10
            ("SKU004461", 315.0),  # Suéter Cuello V H Azul Marino Talla 12
            ("SKU004462", 315.0),  # Suéter Cuello V H Azul Marino Talla 14
            ("SKU004463", 315.0),  # Suéter Cuello V H Azul Marino Talla 16
            ("SKU004464", 300.0),  # Suéter Cuello V H Azul Marino Talla 18
            ("SKU004465", 199.0),  # Playera Polo Ad hoc Talla 4
            ("SKU004466", 199.0),  # Playera Polo Ad hoc Talla 6
            ("SKU004467", 199.0),  # Playera Polo Ad hoc Talla 8
            ("SKU004468", 199.0),  # Playera Polo Ad hoc Talla 10
            ("SKU004469", 199.0),  # Playera Polo Ad hoc Talla 12
            ("SKU004470", 199.0),  # Playera Polo Ad hoc Talla 14
            ("SKU004471", 199.0),  # Playera Polo Ad hoc Talla 16
            ("SKU004472", 199.0),  # Playera Polo Ad hoc Talla 18
            ("SKU004473", 595.0),  # Pants 2pz Deportivo Santa Rosa 238 Talla 12
            ("SKU004474", 605.0),  # Pants 2pz Deportivo Santa Rosa 238 Talla 14
            ("SKU004475", 605.0),  # Pants 2pz Deportivo Santa Rosa 238 Talla 16
            ("SKU004476", 595.0),  # Pants 2pz Deportivo Santa Rosa 238 Talla 18
            ("SKU004477", 615.0),  # Pants 2pz Deportivo Santa Rosa 238 Talla CH
            ("SKU004478", 615.0),  # Pants 2pz Deportivo Santa Rosa 238 Talla MD
            ("SKU004479", 615.0),  # Pants 2pz Deportivo Santa Rosa 238 Talla GD
            ("SKU004480", 229.0),  # Playera Deportivo Ad hoc Talla 14
            ("SKU004481", 229.0),  # Playera Deportivo Ad hoc Talla 16
            ("SKU004482", 229.0),  # Playera Deportivo Ad hoc Talla 18
            ("SKU004483", 239.0),  # Playera Deportivo Ad hoc Talla CH
            ("SKU004484", 239.0),  # Playera Deportivo Ad hoc Talla MD
            ("SKU004485", 239.0),  # Playera Deportivo Ad hoc Talla GD
            ("SKU004486", 290.0),  # Suéter Botones M Azul Talla 6
            ("SKU004487", 290.0),  # Suéter Botones M Azul Talla 8
            ("SKU004488", 295.0),  # Suéter Botones M Azul Talla 10
            ("SKU004489", 315.0),  # Suéter Botones M Azul Talla 12
            ("SKU004490", 315.0),  # Suéter Botones M Azul Talla 14
            ("SKU004491", 315.0),  # Suéter Botones M Azul Talla 16
            ("SKU004492", 325.0),  # Suéter Botones M Azul Talla 30
            ("SKU004493", 325.0),  # Suéter Botones M Azul Talla 32
            ("SKU004494", 325.0),  # Suéter Botones M Azul Talla 34
            ("SKU004495", 325.0),  # Suéter Botones M Azul Talla 36
            ("SKU004496", 325.0),  # Suéter Botones M Azul Talla 38
            ("SKU004497", 290.0),  # Suéter Cuello V H Azul Talla 6
            ("SKU004498", 290.0),  # Suéter Cuello V H Azul Talla 8
            ("SKU004499", 295.0),  # Suéter Cuello V H Azul Talla 10
            ("SKU004500", 315.0),  # Suéter Cuello V H Azul Talla 12
            ("SKU004501", 315.0),  # Suéter Cuello V H Azul Talla 14
            ("SKU004502", 315.0),  # Suéter Cuello V H Azul Talla 16
            ("SKU004503", 325.0),  # Suéter Cuello V H Azul Talla 30
            ("SKU004504", 325.0),  # Suéter Cuello V H Azul Talla 32
            ("SKU004505", 325.0),  # Suéter Cuello V H Azul Talla 34
            ("SKU004506", 325.0),  # Suéter Cuello V H Azul Talla 36
            ("SKU004507", 325.0),  # Suéter Cuello V H Azul Talla 38
            ("SKU004508", 445.0),  # Pants 2pz Vidal Acolcer Talla 4
            ("SKU004509", 445.0),  # Pants 2pz Vidal Acolcer Talla 6
            ("SKU004510", 445.0),  # Pants 2pz Vidal Acolcer Talla 8
            ("SKU004511", 445.0),  # Pants 2pz Vidal Acolcer Talla 10
            ("SKU004512", 175.0),  # Playera Deportiva Blanca Talla 4
            ("SKU004513", 175.0),  # Playera Deportiva Blanca Talla 6
            ("SKU004514", 175.0),  # Playera Deportiva Blanca Talla 8
            ("SKU004515", 175.0),  # Playera Deportiva Blanca Talla 10
            ("SKU004516", 445.0),  # Pants 2pz Deportivo Alvaro Obregon Talla 4
            ("SKU004517", 445.0),  # Pants 2pz Deportivo Alvaro Obregon Talla 6
            ("SKU004518", 445.0),  # Pants 2pz Deportivo Alvaro Obregon Talla 8
            ("SKU004519", 445.0),  # Pants 2pz Deportivo Alvaro Obregon Talla 10
            ("SKU004520", 290.0),  # Suéter Cuello V H Rojo Talla 4
            ("SKU004521", 290.0),  # Suéter Cuello V H Rojo Talla 6
            ("SKU004522", 290.0),  # Suéter Cuello V H Rojo Talla 8
            ("SKU004523", 295.0),  # Suéter Cuello V H Rojo Talla 10
            ("SKU004524", 315.0),  # Suéter Cuello V H Rojo Talla 12
            ("SKU004525", 315.0),  # Suéter Cuello V H Rojo Talla 14
            ("SKU004526", 315.0),  # Suéter Cuello V H Rojo Talla 16
            ("SKU004527", 325.0),  # Suéter Cuello V H Rojo Talla 34
            ("SKU004528", 325.0),  # Suéter Cuello V H Rojo Talla 36
            ("SKU004529", 290.0),  # Suéter Botones M Rojo Talla 4
            ("SKU004530", 290.0),  # Suéter Botones M Rojo Talla 6
            ("SKU004531", 290.0),  # Suéter Botones M Rojo Talla 8
            ("SKU004532", 295.0),  # Suéter Botones M Rojo Talla 10
            ("SKU004533", 315.0),  # Suéter Botones M Rojo Talla 12
            ("SKU004534", 315.0),  # Suéter Botones M Rojo Talla 14
            ("SKU004535", 315.0),  # Suéter Botones M Rojo Talla 16
            ("SKU004536", 325.0),  # Suéter Botones M Rojo Talla 34
            ("SKU004537", 325.0),  # Suéter Botones M Rojo Talla 36
            ("SKU004538", 290.0),  # Suéter Cuello V H Vino Talla 4
            ("SKU004539", 290.0),  # Suéter Cuello V H Vino Talla 6
            ("SKU004540", 290.0),  # Suéter Cuello V H Vino Talla 8
            ("SKU004541", 295.0),  # Suéter Cuello V H Vino Talla 10
            ("SKU004542", 315.0),  # Suéter Cuello V H Vino Talla 12
            ("SKU004543", 315.0),  # Suéter Cuello V H Vino Talla 14
            ("SKU004544", 315.0),  # Suéter Cuello V H Vino Talla 16
            ("SKU004545", 325.0),  # Suéter Cuello V H Vino Talla 34
            ("SKU004546", 325.0),  # Suéter Cuello V H Vino Talla 36
            ("SKU004547", 290.0),  # Suéter Botones M Vino Talla 4
            ("SKU004548", 290.0),  # Suéter Botones M Vino Talla 6
            ("SKU004549", 290.0),  # Suéter Botones M Vino Talla 8
            ("SKU004550", 295.0),  # Suéter Botones M Vino Talla 10
            ("SKU004551", 315.0),  # Suéter Botones M Vino Talla 12
            ("SKU004552", 315.0),  # Suéter Botones M Vino Talla 14
            ("SKU004553", 315.0),  # Suéter Botones M Vino Talla 16
            ("SKU004554", 325.0),  # Suéter Botones M Vino Talla 34
            ("SKU004555", 325.0),  # Suéter Botones M Vino Talla 36
            ("SKU004556", 240.0),  # Chaleco Blanco Talla 2
            ("SKU004557", 240.0),  # Chaleco Blanco Talla 4
            ("SKU004558", 240.0),  # Chaleco Blanco Talla 6
            ("SKU004559", 240.0),  # Chaleco Blanco Talla 8
            ("SKU004560", 250.0),  # Chaleco Blanco Talla 10
            ("SKU004561", 250.0),  # Chaleco Blanco Talla 12
            ("SKU004562", 260.0),  # Chaleco Blanco Talla 14
            ("SKU004563", 260.0),  # Chaleco Blanco Talla 16
            ("SKU004564", 290.0),  # Chaleco Blanco Talla 34
            ("SKU004565", 215.0),  # Camisa Manga Larga Blanca Talla 4
            ("SKU004566", 215.0),  # Camisa Manga Larga Blanca Talla 6
            ("SKU004567", 215.0),  # Camisa Manga Larga Blanca Talla 8
            ("SKU004568", 215.0),  # Camisa Manga Larga Blanca Talla 10
            ("SKU004569", 225.0),  # Camisa Manga Larga Blanca Talla 12
            ("SKU004570", 225.0),  # Camisa Manga Larga Blanca Talla 14
            ("SKU004571", 225.0),  # Camisa Manga Larga Blanca Talla 16
            ("SKU004572", 245.0),  # Camisa Manga Larga Blanca Talla 18
            ("SKU004573", 245.0),  # Camisa Manga Larga Blanca Talla 32
            ("SKU004574", 245.0),  # Camisa Manga Larga Blanca Talla 34
            ("SKU004575", 245.0),  # Camisa Manga Larga Blanca Talla 36
            ("SKU004576", 245.0),  # Camisa Manga Larga Blanca Talla 38
            ("SKU004577", 265.0),  # Camisa Manga Larga Blanca Talla 12
            ("SKU004578", 265.0),  # Camisa Manga Larga Blanca Talla 14
            ("SKU004579", 265.0),  # Camisa Manga Larga Blanca Talla 16
            ("SKU004580", 265.0),  # Camisa Manga Larga Blanca Talla 18
            ("SKU004581", 265.0),  # Camisa Manga Larga Blanca Talla 30
            ("SKU004582", 265.0),  # Camisa Manga Larga Blanca Talla 32
            ("SKU004583", 265.0),  # Camisa Manga Larga Blanca Talla 34
            ("SKU004584", 265.0),  # Camisa Manga Larga Blanca Talla 36
            ("SKU004585", 265.0),  # Camisa Manga Larga Blanca Talla 38
            ("SKU004586", 265.0),  # Camisa Manga Larga Blanca Talla 40
            ("SKU004587", 485.0),  # Pants 2pz Alvaro Obregon Talla 6
            ("SKU004588", 485.0),  # Pants 2pz Alvaro Obregon Talla 8
            ("SKU004589", 485.0),  # Pants 2pz Alvaro Obregon Talla 10
            ("SKU004590", 485.0),  # Pants 2pz Alvaro Obregon Talla 12
            ("SKU004591", 485.0),  # Pants 2pz Alvaro Obregon Talla 14
            ("SKU004592", 485.0),  # Pants 2pz Alvaro Obregon Talla 16
            ("SKU004593", 585.0),  # Pants 2pz Alvaro Obregon Talla CH
            ("SKU004594", 585.0),  # Pants 2pz Alvaro Obregon Talla MD
            ("SKU004595", 585.0),  # Pants 2pz Alvaro Obregon Talla GD
            ("SKU004596", 199.0),  # Playera Blanca Talla 6
            ("SKU004597", 199.0),  # Playera Blanca Talla 8
            ("SKU004598", 199.0),  # Playera Blanca Talla 10
            ("SKU004599", 209.0),  # Playera Blanca Talla 12
            ("SKU004600", 209.0),  # Playera Blanca Talla 14
            ("SKU004601", 209.0),  # Playera Blanca Talla 16
            ("SKU004602", 219.0),  # Playera Blanca Talla CH
            ("SKU004603", 219.0),  # Playera Blanca Talla MD
            ("SKU004604", 219.0),  # Playera Blanca Talla GD
            ("SKU004605", 209.0),  # Playera Chazarilla Café Talla 10
            ("SKU004606", 209.0),  # Playera Chazarilla Café Talla 12
            ("SKU004607", 209.0),  # Playera Chazarilla Café Talla 14
            ("SKU004608", 209.0),  # Playera Chazarilla Café Talla 16
            ("SKU004609", 209.0),  # Playera Chazarilla Café Talla 32
            ("SKU004610", 209.0),  # Playera Chazarilla Café Talla 34
            ("SKU004611", 209.0),  # Playera Chazarilla Café Talla 36
            ("SKU004612", 209.0),  # Playera Chazarilla Café Talla 38
            ("SKU004613", 605.0),  # Pants 2pz Lobito Liso ESTV 663 Talla 16
            ("SKU004614", 615.0),  # Pants 2pz Lobito Liso ESTV 663 Talla CH
            ("SKU004615", 615.0),  # Pants 2pz Lobito Liso ESTV 663 Talla MD
            ("SKU004616", 615.0),  # Pants 2pz Lobito Liso ESTV 663 Talla GD
            ("SKU004617", 615.0),  # Pants 2pz Lobito Liso ESTV 663 Talla EXG
            ("SKU004618", 229.0),  # Playera Deportivo Blanca Talla 12
            ("SKU004619", 229.0),  # Playera Deportivo Blanca Talla 14
            ("SKU004620", 229.0),  # Playera Deportivo Blanca Talla 16
            ("SKU004621", 229.0),  # Playera Deportivo Blanca Talla 32
            ("SKU004622", 239.0),  # Playera Deportivo Blanca Talla CH
            ("SKU004623", 239.0),  # Playera Deportivo Blanca Talla MD
            ("SKU004624", 239.0),  # Playera Deportivo Blanca Talla GD
            ("SKU004625", 239.0),  # Playera Deportivo Blanca Talla EXG
            ("SKU004626", 219.0),  # Playera Polo Blanca Talla 12
            ("SKU004627", 219.0),  # Playera Polo Blanca Talla 14
            ("SKU004628", 219.0),  # Playera Polo Blanca Talla 16
            ("SKU004629", 219.0),  # Playera Polo Blanca Talla 32
            ("SKU004630", 219.0),  # Playera Polo Blanca Talla CH
            ("SKU004631", 219.0),  # Playera Polo Blanca Talla MD
            ("SKU004632", 219.0),  # Playera Polo Blanca Talla GD
            ("SKU004633", 219.0),  # Playera Polo Blanca Talla EXG
        ]

        actualizados = 0
        no_encontrados = []

        for sku, precio in updates:
            cur.execute("UPDATE productos SET precio = ? WHERE sku = ?", (precio, sku))
            if cur.rowcount > 0:
                actualizados += 1
            else:
                no_encontrados.append(sku)

        log(f"  Precios actualizados: {actualizados}/{len(updates)}")

        if no_encontrados:
            log(f"  ADVERTENCIA — SKUs no encontrados ({len(no_encontrados)}): {no_encontrados[:20]}")
            if len(no_encontrados) > len(updates) * 0.1:
                abort(
                    f"Mas del 10% de SKUs no encontrados ({len(no_encontrados)}/{len(updates)}). "
                    "Verifica que esta DB corresponde al mismo sistema.",
                    conn,
                )

        cur.execute("PRAGMA integrity_check")
        result = cur.fetchone()[0]
        if result != "ok":
            abort(f"Fallo en integrity_check: {result}", conn)
        log("Integridad de DB verificada")

        conn.commit()
        conn.close()

        log("=" * 50)
        log("ACTUALIZACION COMPLETADA EXITOSAMENTE")
        log(f"  Precios aplicados : {actualizados}")
        log(f"  SKUs no hallados  : {len(no_encontrados)}")
        log(f"  Backup en         : {bak_path}")
        log("=" * 50)

    except sqlite3.Error as e:
        abort(f"Error de SQLite: {e}", conn)
    except Exception as e:
        abort(f"Error inesperado: {e}", conn)


if __name__ == "__main__":
    main()
