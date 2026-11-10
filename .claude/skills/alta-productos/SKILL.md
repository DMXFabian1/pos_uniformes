---
name: alta-productos
description: Dar de alta productos nuevos en el catálogo del POS (uniformes de una escuela, piezas generales, accesorios), copiar el uniforme de una escuela a otra (con otros colores), o cambiar color/nombre de productos existentes — de forma coherente con el catálogo: mismos valores, patrón de nombre, tallas, precios por escalera, SKU automático, bitácora y liga al uniforme. Usar cuando Daniel diga "da de alta…", "agrega el pants de la escuela X", "nueva escuela igual a Y", "copia el uniforme de…", "cambia el color de…", "crea estos productos".
---

# Alta de productos coherente con el catálogo

Scripts en `scripts/`, todos desde la raíz del repo con el Python del proyecto (`$PY`, ver `CLAUDE.md`):

| Script | Qué hace | Escribe |
|---|---|---|
| `buscar_hermanos.py` | Valores de catálogo, casi-duplicados, productos hermanos con su patrón y lo que ya tiene la escuela | No (solo lectura) |
| `copiar_escuela.py` | Compara escuela origen con destino y **genera el plan**: altas, ediciones de color o nombre, piezas del uniforme | No (solo lectura) |
| `aplicar_alta.py` | Ejecuta uno o varios planes **en una sola transacción**: altas, `editar` y `ligar_al_uniforme`, por `CatalogService` (bitácora, SKU de la secuencia). Ensayo por defecto; guarda solo con `--aplicar` | Sí |

**Conexión:** sin opciones, usan la configuración del proyecto (en la Mac suele ser la base local). Para la caja, `--env-file` con el env que indica `CLAUDE.md`. El script imprime `⚠ PRODUCCIÓN / RED` cuando no es local. Nunca escribir en la caja sin el OK de Daniel.

## Caso A — Escuela igual a otra (lo más común)

La escuela destino debe existir. Si no existe, se da de alta en el POS; los scripts no crean escuelas.
```bash
"$PY" .claude/skills/alta-productos/scripts/copiar_escuela.py --origen "Ignacio Allende" --destino "Ignacio Allende (Jaral)" \
    --colores Rojo=Azul --color-de "Pants Suelto=Gris" --excluir Boina --salida /scratchpad/plan.json [--env-file …]
```
- `--colores A=B` cambia el color en general; `--color-de PATRÓN=COLOR` fija el color de un producto (gana sobre `--colores`); `--excluir PATRÓN` deja productos fuera. Todos se pueden repetir.
- El color cambia **también en el nombre** ("Suéter Botones M Rojo" → "… Azul"). Lo que el destino ya tiene sale como `YA ESTÁ` o `EDITAR`, nunca duplicado. Las piezas generales del uniforme (falda, pantalón de vestir) se ligan con su grupo y orden.
- Revisar los avisos `⚠` (tallas que faltan en productos que ya existen, que no se agregan solas) y "Solo en el destino".
- Correr el plan en ensayo con `aplicar_alta.py` (paso 3). Volver a correr `copiar_escuela.py` después de aplicar debe dar **0 cambios**.

## Caso B — Producto suelto

1. **Buscar hermanos:**
   ```bash
   "$PY" .claude/skills/alta-productos/scripts/buscar_hermanos.py --pieza "Pants 2pz" --prenda Deportivo --nivel Secundaria --escuela "Nombre escuela"
   ```
   - **Valores de catálogo:** usar **exactamente** los que existen. Si sale `NO EXISTE` con parecidos (escuela incluida), preguntar a Daniel. **Nunca** crear uno nuevo por escribirlo distinto. Ante casi-duplicados (`Basico`/`Básico`), usar el de la mayoría y mencionarlo.
   - **Patrón:** nombre sin escuela más común (el POS agrega la escuela), marca, categoría, atributo, género y escudo dominantes. Juego de tallas más común.
   - **Precios:** el más común por talla, confirmado contra `Gestor_de_Inventarios/reglas_precios_v1.md` (gana la excepción de la escuela si la hay).
   - **Lo que ya existe en la escuela:** no duplicar.
2. Escribir el spec JSON en el scratchpad. El formato está en el docstring de `aplicar_alta.py`.

## Editar color o nombre de productos existentes

Bloque `editar` del plan: `{"editar": [{"producto_id": 596, "color": "Azul", "nombre": "Chaleco Azul"}]}`. Conserva SKU, precio, costo, stock mínimo y todos los campos del producto. El nombre va **sin** escuela (si la trae, el script la quita para que el POS no la duplique). Si el nombre lleva el color viejo, cambiar los dos.

## 3. Vista previa, ensayo y aplicar

1. Mostrar a Daniel la tabla de lo que cambia (altas con tallas y precios, ediciones antes → después, piezas del uniforme) y **esperar su OK**.
2. Ensayo: `aplicar_alta.py plan.json [--env-file …]`. Todo va en una transacción: los SKU que se ven son los reales, y si algo falla no se guarda nada. En la caja, avisar antes de ensayar.
3. Con el OK: el mismo comando con `--aplicar`. Verificar después con `buscar_hermanos.py --escuela …` o con `copiar_escuela.py`, que debe dar 0 cambios.

Si sale "faltan migraciones": no migrar la caja sin permiso. Para probar, usar una copia local (`createdb -T pos_uniformes pos_uniformes_prueba`, `alembic upgrade head` con `POS_UNIFORMES_DB_NAME` apuntando a la copia, un `--env-file` hacia ella) y borrarla al terminar.

## 4. Después

- Ofrecer etiquetas o QR de los SKU nuevos (POS: Inventario → etiqueta). Si se cambió el color de productos con stock, avisar que las etiquetas físicas quedan con el color viejo.
- `productos.db` (Gestor) **no** se actualiza solo y tiene su propio contador de SKU. Solo agregar ahí si Daniel lo pide, con el mismo SKU de la caja.
- Los tarifarios `*_db.py` toman los cambios al regenerarse (skill `cambio-precios-catalogo`, paso 5).
- Anotar con la skill `actualizar-vault`. Los cambios de escuelas van en `07 - Servicios - Catálogo e Inventario` y en `Gestor de Precios/02`.
