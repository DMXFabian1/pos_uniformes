---
name: cambio-precios-catalogo
description: Subir o ajustar precios de uniformes, agregar una excepción de precio por escuela, o renombrar una escuela, dejando sincronizados la caja (PostgreSQL), productos.db, las reglas, las guías rápidas y los tarifarios. Usar cuando Daniel diga "sube X a $N", "la escuela Y cambia de nombre", "el pants de Z queda en…", etc.
---

# Cambio de precios o escuelas en el catálogo

La **caja** (PostgreSQL de la PC de la tienda) es la fuente de verdad. Todo lo demás se ajusta a ella.

## 0. Antes de empezar

- Confirmar que la rama tiene las reglas más recientes: `git log -3 --format='%h %cs %s' -- Gestor_de_Inventarios/reglas_precios_v1.md`. Si Daniel menciona un cambio que no aparece ahí, avisar: puede haber quedado en otra rama, como pasó con `docs/costos-proveedores` en noviembre de 2026.
- La copia buena de reglas, guías y generadores es la de **`Gestor_de_Inventarios/`**. Lo que está en `_archivo/` no se toca.

## 1. Entender el cambio y mostrar el "antes"

- Identificar los SKUs afectados: escuela, `tipo_pieza`, `tipo_prenda`, `nivel_educativo` y tallas.
- Consultar los precios actuales en la caja (solo lectura) y en `Gestor_de_Inventarios/data/productos.db`:
  ```bash
  sqlite3 Gestor_de_Inventarios/data/productos.db "select sku,nombre,talla,precio from productos where escuela_id=? and tipo_pieza=?"
  ```
- Revisar la sección de `Gestor_de_Inventarios/reglas_precios_v1.md` que aplica (escalera normal o excepción).
- **Regla de oro:** nunca bajar precios. Si el objetivo es menor al actual, avisar y pedir confirmación explícita.
- Mostrar a Daniel una tabla `SKU | talla | antes | después` y **esperar su OK** antes de escribir en la caja.

## 2. Aplicar en la caja (con bitácora)

Con un script corto que use `get_session()` y `CatalogService.aplicar_cambio_masivo_precio(session, admin, referencia=..., motivo=..., observacion=..., precios_por_variante=[(variante_id, Decimal)])`. Como referencia, ver `_archivo/sincronizar_precios_postgres.py` (busca el admin y mapea SKU a Variante).
- Correr primero en modo dry-run e imprimir el resumen.
- Usar `referencia` con fecha, por ejemplo `PRECIO-2026-11-10`, y un `motivo` legible.
- Para renombrar una escuela: actualizar `escuela.nombre` y el nombre de sus productos, dejando registro en `cambio_catalogo`.

## 3. Igualar productos.db

Hacer `UPDATE productos SET precio=?, last_modified=CURRENT_TIMESTAMP WHERE sku IN (...)`, o actualizar la tabla `escuelas` y los nombres al renombrar. Después correr `sqlite3 … "PRAGMA wal_checkpoint(TRUNCATE)"` para que el `.db` versionado tenga el cambio y no quede en `-wal`.

## 4. Actualizar los textos

| Qué | Dónde |
|---|---|
| Reglas | `Gestor_de_Inventarios/reglas_precios_v1.md`; copiar después a `pos_uniformes/docs/reglas_precios_v1.md` |
| Guía rápida de la familia | `Gestor_de_Inventarios/guia_rapida_<familia>_compacta.md`; copiar a `pos_uniformes/docs/` |
| Generadores con precios escritos en el código | `Gestor_de_Inventarios/generar_tarifarios{,_html}.py` (y su copia en `pos_uniformes/scripts/`), solo si la excepción tiene que aparecer en esos tarifarios |

Al 10-nov-2026 las copias de `pos_uniformes/docs/` y `pos_uniformes/scripts/` **ya diferían** de las de `Gestor_de_Inventarios/`. Al copiar, revisar con `diff` y no pisar algo que solo exista en la copia.
Una excepción se anota con la fecha, por ejemplo: `` - `Escuela` Nivel: 2pz `650` en linea completa (2026-11-10); 3pz sigue la escalera … ``.

## 5. Regenerar los tarifarios

- Los generadores `Gestor_de_Inventarios/generar_tarifarios_db.py` y `generar_tarifario_escuelas_db.py` **leen los precios directo de la caja** (solo lectura, requieren `POS_UNIFORMES_DB_HOST`). Después del paso 2 basta con correrlos:
  ```bash
  cd Gestor_de_Inventarios && python3 generar_tarifarios_db.py
  ```
- Los generadores con precios escritos en el código (`generar_tarifarios.py`, `generar_tarifarios_html.py`) solo se corren si se editaron en el paso 4.
- Los reportes y respaldos viejos no se tocan.

## 6. Cerrar

- Commit con una línea por cambio y la fecha, por ejemplo `precios: Pants 2pz Deportivo Técnica 18 a 650 (10-nov-2026)`. En el cuerpo: tallas, antes y después, y "aplicado en la caja (con bitácora en cambio_catalogo) y en productos.db".
- Proponer la nota para el vault (`Gestor de Precios/02 - Historial de Sesiones de Precios.md`) con la skill `actualizar-vault`.
