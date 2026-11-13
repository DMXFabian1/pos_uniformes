---
name: alta-productos
description: Dar de alta productos nuevos en el catálogo del POS (uniformes de una escuela, piezas generales, accesorios), copiar el uniforme de una escuela a otra (con otros colores), o cambiar color/nombre de productos existentes — de forma coherente con el catálogo: mismos valores, patrón de nombre, tallas, precios por escalera, SKU automático, bitácora y liga al uniforme. Usar cuando Daniel diga "da de alta…", "agrega el pants de la escuela X", "nueva escuela igual a Y", "copia el uniforme de…", "cambia el color de…", "crea estos productos".
---

# Alta de productos coherente con el catálogo

Scripts en `scripts/`, todos desde la raíz del repo con el Python del proyecto (`$PY`, ver `CLAUDE.md`):

| Script | Qué hace | Escribe |
|---|---|---|
| `buscar_hermanos.py` | Valores de catálogo, casi-duplicados, productos hermanos con su patrón, lo que ya tiene la escuela y (§4) lo que elige el motor del alta: modelo, precio por talla con su origen y «Ya tiene / Le falta» | No (solo lectura) |
| `copiar_escuela.py` | Compara escuela origen con destino y **genera el plan**: altas, ediciones de color o nombre, piezas del uniforme | No (solo lectura) |
| `aplicar_alta.py` | Ejecuta uno o varios planes **en una sola transacción**. Las altas van por el **motor del alta del POS** (`services/alta_prenda_service.py`, el mismo de la pantalla «Nueva prenda»); `editar` y `ligar_al_uniforme` por `CatalogService` y `uniforme_service`. Ensayo por defecto; guarda solo con `--aplicar` | Sí |

**El motor del alta** (tanda 2, 2026-11-13) hace que Claude y la pantalla den de alta igual: revisa los valores (nada se crea sin confirmar), arma el nombre sin repetir la escuela, crea prenda y tallas, **liga la prenda a su uniforme**, **propone la receta** del Pants 3pz o la Chamarra (o completa la de los conjuntos de la escuela que no tenían; una receta que ya existe no se toca), da entrada a lo que llegó como **ENTRADA normal** por talla (`ALTA-ENTRADA`, corregible; la talla se puede borrar) y deja en la bitácora **el origen**: «Claude (skill alta-productos) · modelo: …» o «Copia de escuela: A → B · modelo: …». Todo junto o nada. Servicios: `hermanos_service` (modelo, «igual en N escuelas», «Ya tiene / Le falta»), `precio_sugerido_service` (precio por talla «como las demás» / «del modelo» / «a mano», 5/9 solo sugerido) y `alta_prenda_service` (plan → ensayo → aplicar).

**Conexión:** sin opciones, usan la configuración del proyecto (en la Mac suele ser la base local). Para la caja, `--env-file` con el env que indica `CLAUDE.md`. El script imprime `⚠ PRODUCCIÓN / RED` cuando no es local. Nunca escribir en la caja sin el OK de Daniel. Para probar la skill sin base, `--db-url sqlite:///ruta/mini.db` (por ejemplo, una caja en miniatura hecha con `pos_uniformes/tests/_ayuda_mini_caja.py`).

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
   - **Precios:** los que da el motor en la sección 4 (el más común en la caja para esa pieza, nivel y talla; si no hay, el del modelo), confirmados contra `Gestor_de_Inventarios/reglas_precios_v1.md` (gana la excepción de la escuela si la hay). La regla 5/9 **solo se sugiere** («¿$289?»); un precio que ya es el de las demás escuelas no se discute (corbata $70, camiseta $52). Nunca bajar precios. $0 no pasa.
   - **Ya tiene / Le falta:** la sección 4 dice qué piezas tienen las demás escuelas del nivel y esta no («lo tienen 41 de 44»).
   - **Lo que ya existe en la escuela:** no duplicar.
2. Escribir el spec JSON en el scratchpad. El formato está en el docstring de `aplicar_alta.py`. Cambios del motor:
   - Sin `"uniforme"`, una prenda de escuela **se liga sola** a su uniforme con el grupo que le toca; `"uniforme": false` para no ligarla.
   - `"llegan"` por talla (o `"stock"`, igual) entra como ENTRADA normal. Un Pants 3pz o una Chamarra no llevan existencia (se arman de sus piezas).
   - `"modelo"` (nombre de la prenda copiada) y `"origen"` van a la bitácora. `--origen` cambia el origen general y `--usuario` el ADMIN que firma.
   - Tallas y colores nuevos se guardan en una sola forma (Uni → Unitalla, Blanca → Blanco) y el ensayo lo avisa.
   - Un valor de catálogo que no existe solo se crea si viene en `"confirmados"`, y eso solo después de que Daniel lo apruebe. Una escuela nueva, solo con un usuario ADMIN.

## Editar color o nombre de productos existentes

Bloque `editar` del plan: `{"editar": [{"producto_id": 596, "color": "Azul", "nombre": "Chaleco Azul"}]}`. Conserva SKU, precio, costo, stock mínimo y todos los campos del producto. El nombre va **sin** escuela (si la trae, el script la quita para que el POS no la duplique). Si el nombre lleva el color viejo, cambiar los dos.

## 3. Vista previa, ensayo y aplicar

1. Mostrar a Daniel la tabla de lo que cambia (altas con tallas y precios, ediciones antes → después, piezas del uniforme) y **esperar su OK**.
2. Ensayo: `aplicar_alta.py plan.json [--env-file …]`. Primero se planean todas las altas: si alguna trae errores (valor que no existe, precio en $0, ya existe) no se toca nada y se listan. Después todo va en una transacción: los SKU que se ven son los reales, se ve el grupo del uniforme y la receta que queda, y si algo falla no se guarda nada. En la caja, avisar antes de ensayar.
3. Con el OK: el mismo comando con `--aplicar`. Verificar después con `buscar_hermanos.py --escuela …` o con `copiar_escuela.py`, que debe dar 0 cambios.

Si sale "faltan migraciones": no migrar la caja sin permiso. Para probar, usar una copia local (`createdb -T pos_uniformes pos_uniformes_prueba`, `alembic upgrade head` con `POS_UNIFORMES_DB_NAME` apuntando a la copia, un `--env-file` hacia ella) y borrarla al terminar.

## 4. Después

- Ofrecer etiquetas o QR de los SKU nuevos (POS: Inventario → etiqueta). Si se cambió el color de productos con stock, avisar que las etiquetas físicas quedan con el color viejo.
- `productos.db` (Gestor) **no** se actualiza solo y tiene su propio contador de SKU. Solo agregar ahí si Daniel lo pide, con el mismo SKU de la caja.
- Los tarifarios `*_db.py` toman los cambios al regenerarse (skill `cambio-precios-catalogo`, paso 5).
- Anotar con la skill `actualizar-vault`. Los cambios de escuelas van en `07 - Servicios - Catálogo e Inventario` y en `Gestor de Precios/02`.
