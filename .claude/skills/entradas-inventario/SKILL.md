---
name: entradas-inventario
description: Capturar en la caja la mercancía que llegó (del maquilador o de un proveedor con remisión) y corregir existencias contando — sobre todo las tallas en negativo — con los mismos servicios del POS (compra, «Llegó mercancía» del celular, conteo), vista previa en solo lectura y todo en una transacción. Usar cuando Daniel diga "llegaron 30 golpes blancos", "registra esta entrada", "me llegó la remisión de Romanos", "da entrada a…", "hay 7 corbatines dorados", "corrige el stock de…", "¿qué está en negativo?", "¿qué tengo que contar?", "el pants 3pz dice 0 y sí hay", o mande foto de una remisión para darle entrada. No es para dar de alta productos nuevos (alta-productos) ni para registrar ventas (registro-venta-libreta).
---

# Entradas y conteos de inventario

Scripts en `scripts/`, desde la raíz del repo con `$PY` (ver `CLAUDE.md`). Con `--env-file` del env de la caja (ruta en `CLAUDE.md`) leen o escriben la caja; sin él, la base local.

| Script | Qué hace | Escribe |
|---|---|---|
| `buscar.py "golpe blanco"` | SKU, existencia (total, suelto en tienda, dentro de cajas del almacén y del piso), costo, precio, si es conjunto; `--movimientos N` | No |
| `negativos.py` | Tallas en negativo por escuela y prenda, lo más rojo primero, con ventas de 30 días y último conteo. `--escuela`, `--buscar`, `--desfasados` (conjuntos que no cuadran con sus piezas), `--reconciliados` (las que se subieron a 0 en septiembre y nadie contó), `--plantilla <scratchpad>/conteo.json` | No |
| `aplicar_inventario.py plan.json` | Sin flags: **vista previa en solo lectura**. `--aplicar`: guarda todo en una transacción. `--ensayo`: lo hace y lo deshace, solo en una base local | Con `--aplicar` |

El formato del plan está en el docstring de `aplicar_inventario.py`.

## Qué servicio usa cada cosa (lo mismo que la PC y el celular)

| Lo que dice Daniel | En el plan | Servicio del POS | Queda en |
|---|---|---|---|
| «Llegaron 30 golpes blancos» (maquilador, sin remisión) | entrada **sin** `proveedor` | `bodega_movil_service.llego_mercancia` | «Llegadas recientes» del celular, firmada por Daniel. `a_caja` guarda una parte en una caja de bodega |
| «Llegó la remisión de Romanos» (con costos) | entrada **con** `proveedor`, `documento` y `costo` por renglón | `CompraService` (borrador y confirmación) | Una compra con su detalle. **Sube `costo_referencia`** al costo de la remisión |
| «Hay 7 corbatines dorados» | `conteo` con `contado` (la hora real) y `hay` | `conteo_service.registrar_conteo` + `confirmar_ajustes_lote` | Un renglón de conteo, la fecha de último conteo y el ajuste `CONTEO-N`. Los conjuntos de esa pieza se recalculan |
| «El pants 3pz dice 0 y sí hay» | `"recalcular_conjuntos": "todos"` | `conjunto_service.sincronizar_todo` | Movimientos `derivado:`. La vista previa lista cada talla y marca las que **bajan** (también hay conjuntos inflados) |

## Flujo

1. **Ubicar cada prenda** con `buscar.py` (o `negativos.py`). Usar siempre el SKU en el plan. `buscar` sirve solo si resuelve a una única talla; si es ambiguo, el script se detiene y lista las opciones.
   - **Los conjuntos no entran ni se cuentan.** Si llegaron «5 Pants 3pz», entran 5 Pants 2pz y 5 Playeras. Si llegaron chamarras, entran sus piezas. La entrada de un conjunto se reparte por receta: una Chamarra **resta** un Pants Suelto. Ni la vista previa ni el conteo pueden seguir ese reparto, así que el script lo rechaza y dice qué piezas usar.
2. **Llegó mercancía con remisión:** primero `registro-costos-proveedor` (tabla de costos y margen), después la entrada con proveedor. El `documento` es único, en la forma `PROVEEDOR-NOTA-AAAA-MM-DD` (ej. `ROMANOS-NAVLUCES-2026-11-07`). Si una prenda **no existe** en el catálogo, primero `alta-productos`.
3. **Contar:**
   - `hay` = lo **suelto** en tienda (estante y exhibición), **sin nada que esté dentro de una caja**: ni las del almacén ni las cajas que están en el piso (rack PISO). Así mide el conteo del POS (`stock_tienda`). Si `buscar.py` muestra algo en `c.alm` o `c.piso`, decírselo a Daniel para que no lo sume.
   - `contado` = la hora **real** en que se contó, no «ahora». El script suma o resta lo que se vendió desde esa hora hasta que se aplica.
   - Si en el mismo plan hay entradas, `incluye_entradas` es obligatorio: `true` si contó después de acomodarlas, `false` si contó antes.
   - Si la talla tuvo movimientos de cajas (meter a caja, pasar al piso) **después** de la hora del conteo, el script se detiene: la cuenta saldría mal y hay que volver a contar.
   - Si la talla tiene un conteo **viejo sin aplicar** (por ejemplo, uno de junio), la vista previa lo avisa. Al aplicar, queda marcado como superado, para que nadie lo aplique después encima.
   - Los **conjuntos** (Pants 3pz, Chamarra con receta) no se cuentan: se cuentan sus piezas (Pants 2pz, Playera, Pants suelto) y el conjunto se recalcula solo.
4. **Vista previa** (sin flags, aunque sea contra la caja). Enseñarle a Daniel la tabla antes → entra → contó → queda y los avisos `⚠`.
   - Una entrada sobre una talla en negativo sin conteo deja un número que **no es real**. Pedirle que la cuente.
   - Si el margen de una compra baja de 40 %, avisar sin aplicar nada (eso es `cambio-precios-catalogo`).
5. **Esperar el OK de Daniel** y correr el mismo comando con `--aplicar`. Antes de guardar, el script vuelve a validar todo e imprime el resultado real, incluidos los conjuntos que se movieron por arrastre.
6. Verificar con `buscar.py --sku … --movimientos 5`. Ofrecer etiquetas de lo que llegó (POS: Inventario › etiqueta). Anotar con `actualizar-vault` (nota 07 de catálogo e inventario).

Para corregir muchos negativos de una vez: `negativos.py --plantilla <scratchpad>/conteo.json [--escuela …]`, Daniel cuenta, se llena `hay` (las que deje en `null` se omiten) y se sigue desde el paso 4.

## Protecciones (el script se detiene con ERROR)

- Una compra con un `documento` que ya existe (sin importar mayúsculas), o una llegada igual (misma talla, cantidad y referencia en los últimos 3 días). Si de verdad es otra, `"repetir": true` en ese renglón.
- Una clave que el script no conoce (por ejemplo «Proveedor»), o una llegada que trae `documento` o `costo` sin `proveedor`. Antes, eso se volvía en silencio una llegada sin costo.
- Una llegada con `a_caja` sobre una talla cuyo total no alcanza (en negativo, o con cajas que ya pasan del total). Primero se cuenta; la caja va en otro plan.
- Un conteo de una talla que ya tiene un conteo **más nuevo** que `contado` (así no se aplica dos veces el mismo).
- Dar entrada a un conjunto o contarlo, cantidades con decimales o negativas, un nombre ambiguo, una llegada firmada por alguien que no es el dueño, un conteo y entradas en el mismo plan sin `incluye_entradas`, o una hora de conteo «ahora» o en el futuro.
- `--aplicar` bloquea las tallas que toca antes de leerlas. Una venta de la caja en ese momento espera unos segundos y no se pierde.
- `--ensayo` contra la caja: aunque se deshace, bloquea esas tallas un momento. Usar la vista previa, o una copia local hecha con `actualizar-tienda/scripts/ensayo_migracion.py --conservar`. Con el OK de Daniel existe `--ensayo-en-caja`.

## Nunca

- **Nunca subir negativos a cero a ciegas.** El viejo `pos_uniformes/scripts/revisar_stock_negativo.py --aplicar` lo hace y deja tallas en 0 que nadie contó (`negativos.py --reconciliados` las lista). Un negativo se corrige contando.
- **Nunca `--aplicar` contra la caja sin el OK de Daniel** a la vista previa (regla de `CLAUDE.md`).
- **Nunca bajar precios.** Esta skill no toca precios, solo enseña el margen.
- No usar `aplicar_ajuste_masivo` ni ajustes manuales para «cuadrar» un conteo: el conteo deja su renglón, mide solo la tienda y recalcula los conjuntos.

## Antecedentes (2026-11-19)

- Hasta `53f9aecc` (y `89ffae7b` para el ajuste masivo), una entrada sobre una talla en negativo **fallaba** si no la sacaba de rojo (Golpe en −20 y llegan 10 → «deje stock negativo»), en la PC, en el celular y en las compras. Desde esos commits se registra. La tienda no lo tiene hasta que se actualice, pero los scripts corren con el código de la Mac, que ya lo trae.
- Hasta `596d97b7`, aplicar un conteo **no** recalculaba los conjuntos de la pieza. Así quedaron 81 tallas de conjuntos desfasadas en la caja: 67 abajo de lo que sus piezas arman (una Chamarra en 0 con piezas para 4, que el kiosko no ofrece) y 14 arriba (se ofrecen y no hay). Se corrigen con `"recalcular_conjuntos": "todos"`, con OK de Daniel.
- Ese día había 165 tallas en negativo (−614 piezas) y 51 tallas de conjuntos. UVEG sola sumaba −222.

Notas del vault: `POS Uniformes/07 - Servicios - Catálogo e Inventario.md` y `21 - Sesión de Trabajo.md`.
