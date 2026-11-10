---
name: alta-productos
description: Dar de alta productos nuevos en el catálogo del POS (uniformes de una escuela, piezas generales, accesorios) de forma coherente con los existentes — mismos valores de catálogo, patrón de nombre, tallas, precios por escalera, SKU automático y liga al uniforme. Usar cuando Daniel diga "da de alta…", "agrega el pants de la escuela X", "nueva escuela con su uniforme", "crea estos productos".
---

# Alta de productos coherente con el catálogo

Dos scripts hacen el trabajo pesado, para no explorar la base de datos a mano:
- `scripts/buscar_hermanos.py`: **solo lectura**. Muestra valores de catálogo, casi-duplicados, productos hermanos con su patrón y lo que ya existe en la escuela.
- `scripts/aplicar_alta.py`: crea por `CatalogService`, con bitácora y SKU automático. **Por defecto es ensayo** (hace todo y deshace al final); guarda solo con `--aplicar`.

Correrlos desde la raíz del repo con el Python del proyecto (`$PY`, ver `CLAUDE.md`). Sin `--db-url` usan la configuración del proyecto, que puede ser **la caja**.

## 1. Buscar hermanos (siempre primero)

```bash
"$PY" .claude/skills/alta-productos/scripts/buscar_hermanos.py --pieza "Pants 2pz" --prenda Deportivo --nivel Secundaria --escuela "Nombre escuela"
```
De la salida, tomar:
- **Valores de catálogo:** usar **exactamente** los que existen (con su acento y mayúsculas). Si sale `NO EXISTE` con parecidos, casi siempre es uno de esos: preguntar a Daniel cuál, **nunca crear uno nuevo** por variar la escritura. Si avisa de casi-duplicados (por ejemplo `Basico` y `Básico`), usar el que tienen la mayoría de los hermanos y mencionarlo.
- **Patrón:** el nombre sin escuela más común (por ejemplo «Pants 2pz Deportivo»; **el POS agrega la escuela solo**), además de marca, categoría, atributo, género y escudo dominantes.
- **Tallas:** el juego de tallas más común para ese nivel.
- **Precios:** el más común por talla, confirmado contra `Gestor_de_Inventarios/reglas_precios_v1.md`. Si la escuela tiene excepción en las reglas, gana la excepción. Si el precio pedido no encaja con ninguna regla, señalarlo.
- **Lo que ya existe en la escuela:** si ya hay un producto igual, no duplicarlo. Proponer agregar las tallas que falten.

## 2. Vista previa para Daniel

Mostrar una tabla corta y **esperar su OK**:

| Campo | Valor | De dónde sale |
|---|---|---|
| Nombre | Pants 2pz Deportivo → «Pants 2pz Deportivo <Escuela>» | 6 de 8 hermanos |
| Catálogo | Deportivo · Pants 2pz · Secundaria · Sin marca · atrib Deportivo · Unisex · Con Escudo | patrón dominante |
| Tallas y precio | 10:595 12:595 14:605 16:605 CH:615 MD:615 GD:615 EXG:615 | escalera de secundaria |
| Uniforme | grupo Deportivo | prenda Deportivo |

Grupos válidos para el uniforme: Diario (Oficial o Básico), Deportivo, Escolta, Accesorio y Otro. Un básico que es pants, playera, short o chamarra va a Deportivo.

## 3. Ensayo y alta

Escribir el spec en un JSON temporal (fuera del repo, en el scratchpad). El formato está en el docstring de `aplicar_alta.py`:
```bash
"$PY" .claude/skills/alta-productos/scripts/aplicar_alta.py /ruta/alta.json            # ensayo: valida y muestra los SKU
"$PY" .claude/skills/alta-productos/scripts/aplicar_alta.py /ruta/alta.json --aplicar  # solo con el OK de Daniel
```
- Si el destino es **la caja**, también el ensayo requiere avisar antes, porque abre una transacción en producción aunque la deshaga.
- Si sale el error de migraciones faltantes: la base está atrasada respecto a la rama. No migrar la caja sin permiso. Para probar, usar una copia local (`createdb -T pos_uniformes pos_uniformes_prueba`, más `alembic upgrade head` con `POS_UNIFORMES_DB_NAME` apuntando a la copia) y borrarla al terminar.
- Varios productos (una escuela completa): un JSON por producto, primero todos los ensayos y luego todos los `--aplicar`.
- No se crean escuelas, marcas ni tipos desde aquí. Si hace falta uno nuevo y Daniel lo confirma, se crea en el POS (Catálogo) o con `CatalogService.crear_marca` o `crear_categoria`.

## 4. Después del alta

- Ofrecer etiquetas o QR de los SKU nuevos (desde el POS: Inventario → etiqueta).
- `productos.db` (Gestor) **no** se actualiza en automático y tiene su propio contador de SKU. Solo agregar ahí si Daniel lo pide, y usando el mismo SKU que asignó la caja.
- Los tarifarios `*_db.py` toman el producto nuevo al regenerarlos (ver skill `cambio-precios-catalogo`, paso 5).
- Anotar en el vault con la skill `actualizar-vault`: nota de catálogo y, si hubo excepción de precio, `Gestor de Precios/02`.
