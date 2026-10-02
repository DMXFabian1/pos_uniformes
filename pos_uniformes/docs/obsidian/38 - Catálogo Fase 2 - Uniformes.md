---
tags: [pos, catalogo, uniformes, fase2]
fecha: 2026-09-21
estado: fases 2, 2b y 3 hechas en código (1e3a53ef, 2026-09-21); pendiente migrar producción, armar uniformes y recetas; retirar ligas al final
---

# 38 — Catálogo, fase 2: el uniforme como entidad

> [!abstract] En una frase
> Hoy "el uniforme de la escuela X" no existe en la base: se **adivina** juntando productos con `escuela_id`, ligas manuales y el color de cada talla. La fase 2 lo hace explícito: una tabla `uniforme` (por escuela) con sus `uniforme_pieza` (qué prenda, en qué color, en qué orden, si es obligatoria). **Los SKUs no se tocan**; una prenda general vive una vez y aparece en todos los uniformes que la señalen.

Esta nota es la que hay que leer para **retomar** el trabajo: qué se decidió, qué está hecho, qué falta y en qué orden.

---

## 1. Por qué (lo que se vio el 20–21/09)

- **Camisa Cuello Olan Blanca (#394)** es un solo producto general, ligado a Príncipes y Club Rotario. Eso está bien: un stock, un juego de SKUs, dos escuelas. Así debe ser.
- **Pants sueltos**: 39 productos generales (`Pants Suelto Liso Rojo` #145, `Punto Rojo` #136, …) casi sin ligas (Liso Rojo → solo Justo Sierra; Liso Verde → nadie) **y** ~45 productos por escuela (`Pants Suelto Vicente Guerrero` #574 …). Daniel (21/09): *"es otro pants [con escudo] y sí es una mezcla"* → hay escuelas cuyo pants es el suyo (escudo) y escuelas que usan el general del estante, y hoy eso no está escrito en ningún lado; por eso el guiado no lo muestra.
- El **color** vive en `variante.color` (por talla), no en la prenda → 214 de 322 prendas de escuela "Sin color" ([[project_catalogo_sin_color]]). Daniel decide colores después; **no inventar**.
- Cuatro consumidores reconstruyen la misma lista cada uno a su modo: hoja de conteo (`conteo_service`), tarifario PDF (`school_tariff_service.build_school_tariff`: directos + ligados), flujo guiado (`quote_guided_catalog_helper._inject_linked_products`), mapa de conteos (`conteo_mapa_service`). Y `config_conteo_escuela` (cada cuánto se cuenta) cuelga de la escuela, no del uniforme.

## 2. Modelo (decidido)

```
uniforme
  id, escuela_id (FK, RESTRICT), nivel_educativo_id (FK, null),
  nombre  ("Uniforme" — por si un plantel llega a tener dos: "Diario"/"Deportivo" no van aquí, van en la pieza),
  activo, created_at, updated_at
  UNIQUE (escuela_id, nombre)

uniforme_pieza
  id, uniforme_id (FK, CASCADE), producto_id (FK, RESTRICT),
  grupo   ("Diario" | "Deportivo" | "Escolta" | "Accesorio" | "Otro")  ← por tipo de prenda al armar (Oficial/Básico → Diario, Deportivo → Deportivo, Escolta, Accesorio); un básico que es pants/playera/short/chamarra → Deportivo. Editable.
  orden   (int; por defecto el orden de piezas del tarifario: Pants 3pz, 2pz, Chamarra, Suelto, Playera, Suéter, Camisa…)
  obligatoria (bool, default true)
  color   (str 50, null)  ← "en este uniforme va blanca"; vacío hasta que Daniel lo diga
  nota    (str 200, null)
  activo
  UNIQUE (uniforme_id, producto_id)
```

Decisiones:
- **Un uniforme por escuela** (tras partir Álvaro Obregón y Vicente Guerrero por plantel, ninguna escuela activa tiene dos niveles; `nivel_educativo_id` queda por si vuelve a pasar). Diario/Deportivo son **grupos de piezas**, no uniformes distintos, porque el tarifario y la hoja se imprimen por escuela.
- La pieza **señala** al producto; no lo copia. Pants con escudo = producto de la escuela (`escuela_id`); pants del estante = producto general. Un uniforme puede tener los dos.
- **Transición sin romper nada**: mientras tarifario/guiado/hoja sigan leyendo `catalog_school_product_link`, el servicio de uniformes **mantiene las ligas en espejo**: agregar una pieza general crea la liga; quitarla la borra. Cuando los cuatro consumidores lean de `uniforme_pieza`, las ligas se retiran (fase 2b).
- `color` de la pieza **no** reemplaza `variante.color` todavía; es el dato que después servirá para poblar los "Sin color" cuando Daniel decida.

## 3. Piezas de código

| Qué | Dónde | Estado |
|---|---|---|
| Modelos `Uniforme`, `UniformePieza` | `database/models.py` | ✅ |
| Migración `1c2d3e4f5a6b_uniformes` (revisa `0b1c2d3e4f5a`) | `migrations/versions/` | ✅ (pendiente en producción) |
| Servicio | `services/uniforme_service.py` | ✅ |
| Script armar desde lo que hay (dry-run / `--aplicar`, `--escuela ID`) | `scripts/armar_uniformes.py` | ✅ |
| Pantalla POS "Uniformes por escuela" (Más → Uniformes por escuela) | `ui/dialogs/uniforme_escuela_dialog.py` | ✅ |
| Tests | `tests/test_uniforme_service.py` (servicio + script), `test_uniforme_escuela_dialog.py` (pantalla, sqlite en memoria) | ✅ 16 tests |
| Consumidores leyendo del uniforme (hoja, mapa, tarifario, guiado) | `conteo_service`, `school_tariff_service`, `catalog_school_link_service` | ✅ 2b (47c98bb3), con fallback si la escuela no tiene uniforme |
| Poblar `variante.color` desde `uniforme_pieza.color` | — | ⏳ cuando Daniel dé colores |
| Retirar `catalog_school_product_link` | — | ⏳ al final de 2b |

### Servicio (`uniforme_service.py`)
- `grupo_para(producto)` → grupo por tipo de prenda (Deportivo / Deportivo casual → "Deportivo"; Oficial / Básico → "Diario"; Escolta; Accesorio; resto "Otro").
- `proponer(session, escuela_id)` → lo que el script y el botón "Proponer desde catálogo" arman: productos activos con `escuela_id` + productos generales ligados, ordenados por `_PIEZA_ORDER` del tarifario. No escribe.
- `uniforme_de(session, escuela_id, crear=False)`, `piezas_de(session, uniforme_id)`.
- `agregar_pieza(session, uniforme_id, producto_id, *, grupo=None, color=None, obligatoria=True)` — reactiva si ya existía; espejo de liga si el producto es general.
- `quitar_pieza(session, pieza_id)` — la deja **inactiva** (no borra): `armar` no la regresa si Daniel la quitó a propósito; `agregar_pieza` la reactiva. Espejo de liga.
- `actualizar_pieza(session, pieza_id, **campos)` — grupo, obligatoria, color, nota.
- `mover_pieza(session, pieza_id, delta)` — reordena dentro del uniforme.
- `armar(session, escuela_id)` — crea el uniforme con la propuesta (idempotente: solo agrega lo que nunca estuvo; una prenda nueva de la escuela sí entra al volver a correr).
- `resumen(session)` — filas para el script: escuela, piezas propias, generales, sin uniforme.

### Script
```
python -m pos_uniformes.scripts.armar_uniformes            # dry-run, todas las escuelas activas
python -m pos_uniformes.scripts.armar_uniformes --escuela 53
python -m pos_uniformes.scripts.armar_uniformes --aplicar
```
Imprime por escuela la lista propuesta (grupo · pieza · origen). Idempotente.

### Pantalla POS
`Más → Uniformes por escuela` (solo ADMIN). Izquierda: escuelas con buscador. Derecha: tabla de piezas (Grupo ▾ · Pieza · Tipo · Origen "con escudo"/"general" · Color · Oblig. · ▲ ▼ · Quitar) y abajo "Agregar prenda general del estante" (buscador; lo que ya está en el uniforme no se ofrece; doble clic agrega). Botón **Proponer desde catálogo** (sin uniforme) / **Completar desde catálogo** (ya armado). Todo se guarda al momento. El diálogo de ligas del kiosko (Ctrl+Shift+L) sigue vivo y coherente gracias al espejo; se retira en 2b. Acepta `session_factory` para probarse con sqlite.

Probado en la Mac sobre una copia de producción del 21/09 (dump en scratchpad, restaurado en `pos_uniformes` local, `alembic upgrade head`, `armar_uniformes --aplicar`): Justo Sierra queda con 7 propias + 6 generales (pants rojo liso/punto, camisa manga corta blanca, falda y jumper escocés, pantalón vestir azul marino); Vicente Guerrero 6 + 4.

### Fase 2b — quién lee el uniforme y cómo (hecho 2026-09-21)
Regla común: **si la escuela tiene uniforme armado, manda el uniforme; si no, todo sigue como antes**. Así producción no cambia hasta que se corra `armar_uniformes`.

| Consumidor | Qué toma del uniforme | Qué NO cambia |
|---|---|---|
| **Hoja de conteo y mapa** (`obtener_variantes_para_conteo_varias` → `VarianteParaConteo.orden_uniforme`, `agrupar_variantes_por_producto`) | el **orden** de las prendas; lo que no está en el uniforme va al final | se siguen listando **todas** las prendas activas de la escuela (lo que tiene stock se cuenta). Las generales **no** entran a la hoja de la escuela: se cuentan en Básicos, una sola vez |
| **Tarifario** (`build_school_tariff` → `_piezas_del_uniforme`; fallback `_directos_y_ligados`) | piezas (propias + generales), **sección = grupo** (Deportivo, Diario, Escolta, Accesorio, Otro), orden de Daniel, `opcional` ("(opcional)" en el ticket, "· opcional" en el HTML), **color de la pieza** si Daniel lo puso | precios, fusión de mismo precio (ahora también exige misma sección y mismo opcional). Extra: "Sin color" ya no se imprime |
| **Flujo guiado del kiosko** (`list_all_active_links`) | para las escuelas armadas devuelve sus **piezas generales** en orden (una liga metida por fuera ya no manda); para las demás, las ligas | el formato de las filas y el caché del kiosko; el orden de las tarjetas del guiado sigue siendo el suyo (pendiente si Daniel lo pide) |

Pendiente para cerrar la fase: cuando **todas** las escuelas de producción estén armadas, retirar `catalog_school_product_link` (tabla, `_espejo_liga`, diálogo Ctrl+Shift+L del kiosko, `_links_desde_ligas`).

## 4. Cómo se aplica en producción (cuando Daniel diga)

Producción ya está en `0b1c2d3e4f5a` (Daniel corrió `actualizar_pc_principal.bat` el 20–21/09); falta solo esta migración.

1. `actualizar_pc_principal.bat` (trae las migraciones `1c2d3e4f5a6b` y `2d3e4f5a6b7c`).
2. En la principal: `python -m pos_uniformes.scripts.armar_uniformes` → leer → `--aplicar`. Deja un uniforme por escuela con lo que ya se sabía (productos propios + 8 ligas).
3. `python -m pos_uniformes.scripts.crear_piezas_faltantes` → leer → `--aplicar`.
4. `python -m pos_uniformes.scripts.armar_recetas` → leer → `--aplicar`.

En Windows los tres van en uno: `scripts\catalogo_armar.bat` (en seco) y `scripts\catalogo_armar.bat --aplicar`. **El orden importa**: hasta que los uniformes no están armados, el paso 2 no ve las prendas generales que usa cada escuela y crearía productos de más (22 en vez de 16). Ensayado sobre una copia fresca de producción el 22/09: 50 uniformes, **16 productos nuevos** (117 tallas en 0), **114/114 recetas**, 436 tallas de conjuntos con stock calculado (+3,241 piezas que antes estaban en 0), 67 tallas de conjuntos sin pieza equivalente (se quedan como están). Guarda ~92 recetas y **reescribe el stock de 3pz/chamarra** con el calculado (movimientos `derivado:`). Desde ahí, vender un 3pz baja el 2pz y la playera.
5. Daniel, en Más → Uniformes por escuela, completa lo que falta: qué generales usa cada escuela (pants, short, playera…), grupo Diario/Deportivo, opcionales (suéter, chaleco), color de cada pieza (las recetas ya no necesitan nada: las 114 quedan solas).

## 5. Preguntas abiertas
- ¿Género? Hay productos Hombre/Mujer/Unisex; la pieza hereda el género del producto, no hace falta en el uniforme salvo que una escuela tenga "falda para niña / pantalón para niño" como piezas alternativas → se resuelve con `obligatoria=False` + nota, o con un campo `alternativa_de` en 2b si hace falta.
- ¿Precio del uniforme completo? Suma de piezas obligatorias; se calcula, no se guarda.
- ~~Fase 3 (Pants 3pz / Chamarra como conjunto)~~ → decidido, ver abajo.

## 5b. Fase 3 — decidida con Daniel (2026-09-21): 3pz y Chamarra siguen **artificiales**

Daniel: *"un pants 3pz no es más que un 2pz y una playera, y la chamarra es una que le quito a un pants 2pz"*. **No** son productos con stock propio; son formas de vender lo que ya está en el estante. Conservan su SKU, su precio y su etiqueta (nada se reimprime); lo que cambia es que la venta y el stock lo sepan.

| Se vende | Inventario |
|---|---|
| Pants 3pz | −1 Pants 2pz, −1 Playera (misma escuela y talla) |
| Chamarra | −1 Pants 2pz, **+1 Pants Suelto** (el que quedó) |
| 2pz, Playera, Suelto | como hoy |

- Stock del 3pz = min(2pz, playera); stock de Chamarra = stock del 2pz. **Se calculan, no se cuentan** (ya no entran a la hoja: `_TIPOS_VIRTUALES`).
- **Precios:** por separado todo vale más — es a propósito: así Daniel empuja a llevarse el conjunto completo. 3pz < 2pz + playera; chamarra + suelto > 2pz. El tarifario muestra cada precio tal cual, sin derivar nada.
- La playera del 3pz es **la playera de la escuela** (Playera Deportiva <escuela>); en muy pocas escuelas es una **polo blanca básica** general (Daniel, 21/09). Por eso la receta del 3pz no se adivina por tipo de pieza: la pieza del 3pz apunta a la pieza de playera **del mismo uniforme**, sea propia o general — y si el uniforme tiene dos playeras, Daniel elige cuál.
- ~~Hoy la venta descuenta "1 Pants 3pz" de un stock que no existe~~ → arreglado en la fase 3 (abajo).

### Fase 3 — hecha (2026-09-21, `1e3a53ef`)
- **Receta** en `conjunto_componente` (conjunto_id, componente_id, cantidad: >0 se lleva, <0 deja). Migración `2d3e4f5a6b7c`. Servicio `services/conjunto_service.py`.
- **La venta se descompone en `InventarioService.registrar_movimiento`**: si la variante es de un conjunto con receta, el movimiento se aplica a sus piezas de la **misma talla** (lo que se lleva con el mismo tipo, p. ej. SALIDA_VENTA; lo que deja como AJUSTE_ENTRADA con nota "por Chamarra X talla 10"), y luego el stock del conjunto se recalcula. Vale para Libreta, POS viejo y apartados. Una pieza sin esa talla se anota en el log y la venta sigue.
- **Stock calculado y guardado**: 3pz = min(2pz, playera) de la talla; Chamarra = 2pz. Cada vez que una pieza se mueve (venta, llegada, conteo, ajuste), los conjuntos que la usan se recalculan con un movimiento `derivado:<conjunto_id>` (así kiosko, celular y catálogo lo leen como siempre). Los `derivado:` no se rutean (sin bucle). Sesiones falsas de los tests viejos (no `Session`) no entran al hook.
- **Libreta**: `descontar_stock` no repite si alguna pieza ya trae la referencia; `devolver_stock` regresa todo lo que la operación movió (incluido el suelto que dejó la chamarra).
- **Revisar** (`_ventas_por_sku`): un 3pz vendido cuenta también como 2pz y playera vendidos; la chamarra, como 2pz. Sin eso pedía de menos.
- **Una pieza puede ser "cualquiera de estas"** (columna `grupo` en `conjunto_componente`): las piezas con el mismo grupo son alternativas. Daniel (22/09): *"el SABES puede llevar de hombre o de mujer playera deportiva"* → el 3pz lleva `Playera Deportiva H SABES` **o** `M`; su stock **suma** las dos y al vender se toma **la que más hay**. Se propone solo cuando son la misma prenda en dos géneros (mismo nombre salvo H/M y géneros distintos); dos del mismo género siguen siendo pregunta.
- **Script `crear_piezas_faltantes.py`** (dry-run / `--aplicar`): da de alta la prenda que un conjunto necesita y la escuela no tiene — el `Pants Suelto <escuela>` de las que venden chamarra (15 escuelas) y la `Playera Deportiva <escuela>` de las que venden 3pz sin playera (Vicente Guerrero, decisión de Daniel 22/09). Tallas y color del Pants 2pz de la escuela, stock 0 (sube/baja solo con las ventas del conjunto), SKUs nuevos de la secuencia, y entra al uniforme de su escuela. Precios = el más común de esa prenda en las demás escuelas: suelto $259 numérica / $269 letra; playera $199 (12–18 $209), CH $219, MD $225, GD $235, EXG $239. **No** crea nada donde la escuela ya usa una prenda general (partiría el montón).
- **Script `armar_recetas.py`** (dry-run / `--aplicar`): busca las piezas entre las del uniforme (si está armado) o los productos de la escuela; conjuntos generales ("Chamarra Liso Azul Marino") se arman de generales con el mismo nombre sin la palabra de la pieza; entre Polo y Deportiva, la del 3pz es la deportiva; dos deportivas H/M son alternativas; el suelto que deja la chamarra se elige con la regla de precios de Daniel (chamarra + suelto ≥ 2pz, de ahí el de punto y no el liso); el color va en masculino para emparejar familias ("Chamarra Liso Blanca" = "Pants 2pz Liso Blanco"). Con `--aplicar` guarda y sincroniza el stock de todos los conjuntos. Sobre la copia del 22/09, después de `crear_piezas_faltantes`: **114 de 114 conjuntos con receta, 0 pendientes**.
- **Pantalla**: en Más → Uniformes por escuela, la columna **Se arma de** en los conjuntos ("⚠ sin receta" si no tiene) abre `RecetaDialog`: un combo por pieza (primero las del tipo que pide; el resto por si la escuela lo hace distinto), preseleccionado si solo hay una. Guardar = `definir_receta` + stock recalculado.
- Tests: `tests/test_conjunto_service.py` (receta, propuesta, venta 3pz/chamarra, llegada de 2pz sube el 3pz, talla sin pieza, Libreta descontar/devolver, Revisar, script) y `RecetaDialogTests`.
- **Los conjuntos no se suman a los totales** (`conjunto_service.filtro_sin_conjuntos`, 22/09): un 3pz con receta **es** el 2pz y la playera que ya están contados, así que su existencia no entra a "piezas en tienda", al valor del inventario ni al conteo de stock bajo — en el resumen del POS ni en el panel de uniformes (total, valor y valor por nivel). El stock **por talla** del conjunto no cambia: sigue siendo el bueno para vender y para el kiosko. Sin el filtro, producción pasaría de 16,366 a 19,534 piezas de mentiras.
- No cambia: SKU, precio ni etiqueta de 3pz/chamarra; siguen fuera de la hoja de conteo (`_TIPOS_VIRTUALES`). Apartar una chamarra también "deja" el suelto en ese momento (simplificación aceptada).

Relacionadas: [[07 - Servicios - Catálogo e Inventario]] (fase 1), [[27 - Generador Tarifarios Escuelas]], [[36 - Conteos por Jornada]], [[16 - Flujo de Presupuesto]] (guiado), [[02 - Base de Datos]].

## 6. Bitácora
- **2026-09-21** — Diseño acordado con Daniel (Olan = un producto en dos uniformes ✔; pants con escudo = otro producto, y "sí es una mezcla" con los del estante). Modelo, migración, servicio, script, pantalla POS y 16 tests. Commit `9ba43098`, pusheado a GitHub (`chore/reorganizacion-repo`). Suite 2,409 en verde. Nada en producción todavía. Daniel vio la captura de la pantalla con Vicente Guerrero. Siguiente: que Daniel vea la pantalla; luego 2b empezando por la hoja de conteo y el mapa.
- **2026-09-21 (tarde)** — Fase 3 decidida: 3pz y Chamarra siguen artificiales (§5b); la playera del 3pz es la de la escuela, salvo pocas con polo blanca básica. Precios sueltos más caros a propósito.
- **2026-09-21 (noche)** — **2b hecha** (`47c98bb3`): hoja/mapa (orden), tarifario (sección=grupo, opcional, color de pieza, sin "Sin color"), guiado (generales del uniforme). Todo con fallback. Suite 2,417 en verde. Probado el tarifario de Justo Sierra sobre la copia local.
- **2026-09-21 (noche, 2)** — **Fase 3 hecha** (`1e3a53ef`): receta, venta que descompone, stock calculado, Libreta/Revisar, script y Receta… en la pantalla. Probado sobre la copia local: 92 recetas solas, 22 para Daniel. Suite 2,430 en verde.
- **2026-09-22** — Daniel probó la pantalla en la Mac (copia local). Decisiones: crear el `Pants Suelto <escuela>` para las 15 que no lo tenían; el 3pz del SABES lleva la playera deportiva **de hombre o de mujer**; a Vicente Guerrero **se le crea su propia deportiva**. Con eso: alternativas en la receta (`grupo`), `crear_piezas_faltantes`, y **114/114 recetas** sobre la copia de producción. Commits `c291f1e5`, `cc5baa4d`. Suite 2,436.
- **2026-09-22 (tarde)** — Daniel aplicó en la tienda. Dos cosas que salieron: (1) edité `2d3e4f5a6b7c` **después** de que ya había corrido en la principal → la columna `grupo` quedó fuera allá y el POS tronaba; se arregló con `3e4f5a6b7c8d` (agregar) y `4f5a6b7c8d9e` (reagrupar las recetas viejas, que se leían como "2pz **o** playera"). **Nunca editar una migración ya aplicada.** (2) Los totales contaban los conjuntos dos veces → `filtro_sin_conjuntos` (`90ff5912`).
