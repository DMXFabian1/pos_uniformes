---
tags: [modulo, pos-uniformes, kiosko, inventario, pedidos]
---

# 37 — Revisar y Pedidos

> Revisar un conteo dejó de ser "aplicar o descartar": ahora dice **qué hacer con cada talla** — cuántas hay, cuántas se van por semana, cuánto pedir — y **guarda lo que Daniel decide** para que la siguiente revisión aprenda de ella.

Relacionado: [[36 - Conteos por Jornada]] · [[35 - Demanda No Atendida]] · [[28 - Libreta Digital]] · [[12 - Servicios - Analítica e Historia]]

---

## Por qué (2026-09-13)

Daniel: *"la info es importante y me encanta, pero necesito saber qué hacer con ella, pedir más, menos, ir aprendiendo de ella, ver cómo evoluciona y en el mejor de los casos predecir."*

Antes de prometer, se midió qué datos hay (solo lectura, producción):

| Dato | Estado al 2026-09-13 |
|------|----------------------|
| Ventas con talla | La Libreta guarda `detalle` = `[{sku, talla, cantidad, …}]` por venta. **437 ventas / 882 piezas desde el 02-09** (12 días). 811 de 834 renglones casan con una variante por `sku` (único por variante) |
| Conteos | 2,213 tallas contadas desde mayo; **700 con 2 o más conteos** |
| Pidieron y no había | 29 señales (`demanda_no_atendida`) |
| Compras / entradas | **cero.** El sistema no sabe qué se pidió ni qué llegó — ese era el hueco que impedía aprender |

Conclusión honesta: **predecir no**, con 12 días es inventar. Lo que sí: empezar a guardar hoy lo que hace falta (ventas por talla + pedidos + conteos) para que en 2–3 meses salga "esta talla vende el doble que en septiembre" y en el regreso a clases del año que entra haya un ciclo completo por escuela.

## Paso 1 — El servicio (`services/revision_service.py`)

`revisar(session, jornada, hoy=None) → Revision` con una `LineaRevision` por talla contada:

| Campo | De dónde sale |
|-------|---------------|
| `conto` | lo que capturaron en la jornada |
| `anterior`, `anterior_at` | el conteo previo de esa talla (fuera de esta jornada) |
| `vendidas`, `dias_observados` | Libreta por SKU (`tipo` venta o apartado), **desde el conteo anterior**, nunca antes del 02-09 ni más atrás de 12 semanas (`VENTANA_MAX_DIAS = 84`) |
| `ritmo_semana` | `(vendidas + pidieron) / semanas` — **lo que pidieron y no había cuenta como venta perdida** |
| `semanas_cubiertas` | `conto / ritmo` |
| `pidieron` | `demanda_no_atendida` tipo `talla_agotada` por SKU en la ventana |
| `ellas_sugieren` | el "Pedido: N" que la empleada anotó en la hoja (`notas`) |
| `sugerido`, `estado` | `sugerir()`: cubrir **4 semanas** (`SEMANAS_OBJETIVO`, Daniel: "4 semanas, igual para todas") → `URGENTE` (0 y la piden/vendía) · `PEDIR` · `BIEN` · `NO_SE_MUEVE` · `SIN_DATOS` (menos de 7 días observados o sin Libreta) |
| `pedido_anterior`, `pedido_anterior_at`, `vendidas_desde_pedido` | la última decisión guardada y qué pasó después — **aquí aprende** |
| `pedido` | lo ya decidido en esta jornada |

`guardar_pedidos(session, jornada, {conteo_id: piezas|None}, decidido_por)` — solo `VEND-1`; escribe en el propio renglón de `conteo_inventario`: **`pedido`, `pedido_sugerido`, `pedido_decidido_at`** (migración **`bc2d3e4f5a6b`**). `None` borra la decisión; `0` es una decisión ("no pedir").

Todo se calcula en Python sobre pocas filas para que funcione igual en Postgres y en el SQLite de los tests.

## Paso 2 — El diálogo Revisar (`ConteoRevisionDialog`)

> [!success] Rediseño 2026-09-14: primero la decisión, después la evidencia
> Daniel: *"una tabla enorme con un montón de datos… a alguien fuera de contexto le parecerá abrumador"*. Ahora: **cuatro tarjetas** tipo Libreta (URGENTE · PEDIR · SURTIR DE CAJAS · BIEN/SIN DATOS) con cifra grande que además **filtran** (`_TarjetaFiltro`, arrancan prendidas las de acción); **tabla compacta agrupada por prenda** (fila de prenda con "pedir 28 · surtir 4") con 5 columnas: `Talla · Hay (4 + 24 en cajas) · Qué hacer ("pedir 12" / "surtir 7" / "¡URGENTE! pedir 7" / "bien" / "sin datos") · Pedido`; al tocar una talla, abajo **por qué** en una línea (vendidas, ritmo, alcanza, pidieron, cajas, la vez pasada). **"Ver todas las columnas"** trae la tabla completa de abajo.

Tabla completa, por talla: `Prenda · Talla · A la mano · En cajas · Vendidas (N en M d) · Ritmo/sem · Alcanza · Pidieron · Hoja · Surtir · Sugerido · Pedido · La vez pasada`.

- Por defecto solo lo que pide acción (tarjetas URGENTE/PEDIR/SURTIR prendidas); la tarjeta BIEN trae el resto.
- **Pedido** (fondo amarillo, editable) arranca en lo sugerido; el encabezado suma "tu pedido: N piezas en M tallas" al momento. Si un texto no es número, vuelve al anterior.
- **La vez pasada**: "pediste 10 el 23/08, vendiste 11" / "había 8 el 12/07" / "primer conteo".
- **Guardar pedido** deja la decisión. **Aplicar al inventario** la guarda también en el mismo gesto (y deja stock = lo contado). Descartar igual que antes.
- Las columnas Sistema/Diferencia salieron: mientras el inventario esté congelado son ruido ([[07 - Servicios - Catálogo e Inventario]]).
- **Hoja de pedido** (`PedidoHojaDialog`): `texto_pedido()` agrupado por prenda (color solo si hay más de uno), con **Copiar** (para el WhatsApp del maquilador), **Imprimir** en carta (`html_pedido()` por `imprimir_hoja_carta`) o **Mandar por Telegram** (`enviar_mensaje`).

## Paso 3 — Historia de la talla (`TallaHistoriaDialog`)

Doble clic en cualquier fila (menos Pedido, que ahí edita) o botón "Historia de la talla": `historia_de_talla(session, variante_id)`:

- **Barras de las últimas 12 semanas** (`SemanasWidget`, pintado con QPainter, sin librerías): vendidas en café, y encima en rojo lo que pidieron y no había.
- **Tabla de conteos**: fecha · contó · quién · sugerido · **pediste** · **vendidas después** (hasta el siguiente conteo). Ahí se ve si el pedido se quedó corto o sobró.

## Historia de la escuela (2026-09-13, noche)

Daniel: *"más que historial de talla me viene bien un historial de escuela, para ver cómo se ha vendido esa escuela, qué se pide más o menos"*. Botón **Historia de la escuela** en Revisar → `EscuelaHistoriaDialog` / `historia_de_escuela(escuela_id | tipo_pieza)`: piezas por semana (12, con lo que pidieron y no había en rojo) y tabla **por prenda de mayor a menor venta** (vendidas · % del total · pidieron · a la mano · en cajas), con "Ver tallas" para desplegar las tallas bajo cada prenda. Encabezado: "393 piezas en 12 semanas · 7 pidieron y no había · 3 de 5 prendas hacen el 80 % de lo vendido".

## Comparativo con el conteo anterior (2026-09-14)

Daniel: *"una vez aplicado el conteo no puedo volver a verlo; me gustaría un comparativo de la última vez que contamos, qué se movió más y cuánto"*. `comparativo_de_jornada(session, jornada)` → por talla **había** (conteo anterior de esa talla) · **hay** · **cambio** · **vendidas en medio** (Libreta) · **sin explicar** = había − vendidas − hay (positivo: faltan piezas que ninguna venta explica — merma o venta sin registrar; negativo: sobran — llegó mercancía sin anotar), ordenado por lo que más se movió. `ConteoComparativoDialog`: tarjetas HABÍA · HAY · VENDIDAS EN MEDIO · FALTAN · SOBRAN y "Solo lo que cambió". Se abre con **doble clic en el tablero de escuelas** (última jornada terminada, aplicada o no; `FilaTablero.jornada_id`) y con **"Comparar con el anterior"** en Revisar. Primer conteo = "todavía no hay con qué comparar".

## A la mano / en cajas (2026-09-13, noche)

Daniel: los básicos "se pisan" y son demasiados. Radiografía: **2,362 tallas básicas** en 237 prendas; 258 con venta en 12 días; **674 de 882 piezas vendidas son básicos**; 605 tallas (Chamarra, Pants Suelto, Chaleco) sin venta ni conteo. Y el POS ya tiene **Bodega** por cajas (31 cajas, 3 ubicaciones `PISO-N1/N2/ALMACEN-N1`, 1,495 piezas registradas, sin movimiento desde el 16 de julio).

Definición acordada: **piso = a la mano** (colgado, lo que la empleada ve y cuenta); **bodega = lo que está en cajas**, esté la caja donde esté. El conteo ya era "solo de tienda" (`registrar_conteo` mide contra `stock_tienda`), así que **las empleadas no cambian nada**.

Revisar ahora:
- `en_cajas` y `cajas` por talla (`_en_cajas`, desde `BodegaContenido`), columna **En cajas** con tooltip "A-12 ×8 · A-3 ×4".
- `sugerir()` devuelve `Sugerencia(sugerido, surtir, …)`: **pedir contra el total** (a la mano + cajas) y **surtir** lo que falte para tener `SEMANAS_A_LA_MANO = 2` colgado, si en cajas hay. Estado nuevo **`SURTIR`**; `URGENTE` solo si no hay en ningún lado. Columna **Surtir** en azul; el encabezado suma "surtir de las cajas N piezas".

**(3) Bodega desde el celular (2026-09-13, noche):** en la vista del dueño de la PWA, botón **📦 Bodega** con dos gestos (`services/bodega_movil_service.py`, API `/api/v1/movil/bodega`, solo `VEND-1`, solo en la tienda):
- **Llegó mercancía**: buscar la prenda → por talla "llegaron" (prellenado con lo que Daniel pidió en los últimos 60 días; debajo, a la mano y en cajas). **Llega al piso**; la casilla *Guardar parte en una caja* destapa la columna "A caja" (talla por talla, ≤ lo que llegó) y el selector de caja (nueva en el almacén, o una existente). Hace `ENTRADA_COMPRA` (sube `stock_actual`) y, solo si algo va a caja, `ingresar_producto`, en una transacción. Daniel: *"no llega a las cajas, por lo general llega a piso y decidimos sacarlo o ponerlo en caja"*.
- **Pasar al piso**: elegir caja → por talla "al piso" (no más de lo que hay) → `retirar_producto`; el total no cambia. Caja en cero → `VACIA`.
- **Corregir caja** (recuento, 2026-09-13 noche): elegir caja → cada talla dice "el sistema dice N" y Daniel escribe lo que hay (en blanco = no la revisé, 0 = ya no hay) → `corregir_caja`: solo cambia la caja (movimiento `AJUSTE` "Recuento: de N a M"); el total no se toca, salvo que la caja diga más de lo que el sistema tiene en total (sube con `AJUSTE_ENTRADA` para no dejar "a la mano" negativo). Es la herramienta para el punto 4.
Probado en el navegador contra la base de pruebas (caja `A-A1-001`).

Plan restante: (4) Daniel recuenta las 31 cajas una vez con *Corregir caja* (llevan dos meses sin moverse); después, "hoy tocan" por movimiento para básicos y desactivar las 605 tallas muertas.

## Reglas que se tomaron (cambiables)

| Regla | Dónde |
|-------|-------|
| Cubrir 4 semanas, igual para todas las escuelas | `SEMANAS_OBJETIVO` |
| Tener 2 semanas a la mano antes de ir a las cajas | `SEMANAS_A_LA_MANO` |
| Demanda no atendida entra al ritmo | `sugerir()` |
| No mirar más de 12 semanas atrás ni antes de que exista la Libreta | `VENTANA_MAX_DIAS`, `_primera_venta` |
| Menos de 7 días observados = "sin datos" | `MIN_DIAS_OBSERVADOS` |
| Ventas = `tipo in ("venta", "apartado")` | `TIPOS_SALIDA` |

## Lo que sigue

- Comparar mes contra mes cuando haya 2–3 meses de Libreta; estacionalidad por escuela cuando haya un año.
- Registrar **entradas** (qué llegó del maquilador) — hoy solo se infiere del siguiente conteo.
- Revisar desde el celular (hoy solo en el kiosko).

## Tests

`test_revision_service.py` (33: `sugerir` con cajas, `revisar`, hoja de pedido, historia de talla y de escuela, comparativo) · `test_conteo_jornada_ui.py` (`RevisionDialogTests`: tarjetas que filtran, fila de prenda, editar y guardar pedido, hoja, aplicar guarda pedido, cajas/surtir, "por qué", ver todas las columnas, historia por doble clic, historia de la escuela, comparativo) · `test_bodega_movil_service.py` (13) · `test_api_bodega_movil.py` (5).
