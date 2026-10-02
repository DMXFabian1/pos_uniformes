---
tags: [libreta, satelite, pos-uniformes]
---

# Libreta Digital de Ventas

> [!success] Qué es (2026-09-02)
> Registro digital de operaciones del mostrador que **sustituye la libreta física** y el ticket doble que se imprimía solo para anotar. Cada venta/apartado de venta rápida se registra solo, ligado al gafete de la empleada. Vive en la página **Libreta** del satélite (tomó el lugar de Tarifarios en el sidebar — esa página sigue viva, oculta).

> [!info] v2 (2026-09-04)
> Periodos **Sem. pasada** (verificar comisiones el día de pago) y **rango por calendario** (dueño); **clic en empleada del ranking = filtrar** todo lo suyo; filtros rápidos Ventas/Apartados/Abonos/💳Tarjeta (cuadre vs voucher); **doble clic en operación = detalle completo** (precios solo dueño). Arqueo del cajón del kiosko: definido para después — por terminal (origen), excluyendo abonos del POS principal, para no pisarse con la SesionCaja del POS.

---

## Reglas de negocio (decisiones de Daniel)

| Regla | Valor |
|-------|-------|
| **Privacidad** | Empleadas ven SUS piezas/comisiones — **jamás dinero** (hay test que falla si aparece un "$" en su vista). Montos solo con el gafete del dueño (`VEND-1`) |
| **Comisión de terminal (tarjeta)** | **4.5%** por producto, con la regla de redondeo de la tienda. Única fuente: `libreta_service.TERMINAL_COMMISSION_PERCENT`. Las empleadas NO ven el porcentaje en ningún diálogo |
| **Comisiones por pieza** | Conjunto **3pz = 2** por unidad (corregido 2026-09-06; antes 3 — registros previos recalculados con `scripts/recalcular_comisiones_libreta.py`); TODO lo demás (2pz incluido, prendas sueltas) = **1** por unidad. Detección: regex `3\s*pz` en el nombre |
| **Apartados** | SÍ dan comisiones por sus piezas (un apartado grande le vale completo a la empleada) |
| **Abonos** | NO dan comisión, pero SÍ se registran (satélite: botón "Abono"; POS principal: hook en registrar-abono y liquidar-y-entregar). Cliente **opcional** |
| **Semana** | Calendario, lunes a domingo |

## Cuándo se registra

- **Hasta que la impresión realmente arranca** (callback `on_printed` del diálogo de impresión; en modo estación, al encolar con éxito). Cerrar sin imprimir = no se anota nada.
- **Reimprimir no duplica** (guard por carrito+total+tipo).
- El dueño puede **borrar registros** (🗑 en su vista, con confirmación) — para impresiones por error.

## Flujo de datos (offline-first)

```
Venta rápida → cola local JSON (data/libreta_pendiente.json, nunca bloquea)
            → hilo en background la sube a Postgres (conserva hora original)
            → tabla libreta_venta (192.168.0.10)
```
- Sin conexión: la vista muestra lo pendiente de esa terminal + aviso "N registros sin subir".
- Al reconectar (o al abrir la vista) se drena solo.

## Vistas

**Empleada** (escanea su gafete): saludo con su nombre, 4 tarjetas (COMISIONES destacada, piezas, ventas, apartados), barra de **meta semanal** ("te faltan N" / 🎉), y sus movimientos como lista amigable ("🛍️ 10:32 · Vendiste 2 pieza(s): Pants T:6 x2 (+2 com.)").

**Dueño** (gafete VEND-1): tarjetas EN CAJA / Ventas $ (con neto) / Abonos $ / Piezas; **corte por día** (En caja $ = ventas+abonos en efectivo; lo de tarjeta no está en el cajón); ranking de empleadas 🥇🥈🥉; tabla de movimientos con montos; **Imprimir corte** (ticket térmico); configurar **meta semanal** (local por terminal, `data/libreta_meta.json`).

**Seguridad**: Esc cierra sesión; cambiar de página cierra sesión; sin botón default que un escaneo pueda disparar.

## Venta rápida (cambios ligados)

- Diálogo único al imprimir: ¿copia tienda? (escanear el **propio gafete** = sí) + ¿pago con tarjeta? Default: sin copia, efectivo.
- Con tarjeta: la copia interna sale con el 4.5% ya descontado, automático.
- Con descuento empleada: COPIA EMPLEADA automática, solo pregunta el pago.
- El gafete releído por el sensor se ignora ("Gafete ignorado"); guard anti-Enter del escáner en diálogos de impresión.

## Infraestructura

| Pieza | Archivo |
|-------|---------|
| Modelo + migraciones | `LibretaVenta` · `o8c9d0e1f2a3` (tabla) + `p9d0e1f2a3b4` (comisiones/tarjeta) — **aplicadas en producción 2026-09-03** |
| Servicio | `services/libreta_service.py` (registrar, ventanas, resúmenes, corte, eliminar) |
| Cola offline | `services/libreta_local_queue_service.py` |
| Meta semanal | `services/libreta_meta_service.py` |
| Ticket de corte | `ui/helpers/libreta_corte_ticket_helper.py` |
| UI | página Libreta en `ui/quote_satellite_window.py` · registro en `ui/views/quick_sale_view.py` |
| Tests | `tests/test_libreta.py` (~27) + hooks en tests de venta rápida |

## Descartado por Daniel (no volver a proponer)

Devoluciones/contra-asientos · corte por WhatsApp · vista mensual · producto estrella/horas pico · constancia de turno imprimible.
> ~~pago de comisiones calculado ($/comisión)~~ — **revertido 2026-09-08**: Daniel pidió la nómina automática (ver [[33 - Caja, Nómina y Corte Automático]]).

---

## v3 (2026-09-04) — ciclos, cortes formales y anti doble conteo

**Regla de pago corregida:** cada **7 días de calendario** (mismo día de la semana), NO por días trabajados. Ver [[30 - Calendario de Empleadas]].

- **Anti doble conteo**: al arrancar la impresión el carrito se **vacía** en el mismo acto en que registra (venta y apartado). Cerrar sin imprimir lo conserva. Adiós al caso "imprimí 3, agregué 1, reimprimí = 7 pzs".
- **Periodos simplificados**: quedan **Hoy** y **Mi ciclo / Su ciclo** (desde el último pago — el respaldo del banner). "Semana" y "Sem. pasada" ocultas (código vivo). El dueño elige empleada en el ranking antes de "Su ciclo". Rango libre sigue.
- **Banner de empleada**: comisiones desde su último pago + **siguiente descanso concreto** ("jueves 10/Sep") + próximo pago.
- **Corte formal**: "Imprimir corte" pregunta la cifra REAL (precargada con la esperada, editable **solo por el dueño**); el ticket imprime **UNA sola cifra — "VENTA DE HOY"** sin esperado/faltante/rastro de edición (ni desglose por día si hubo cambio). Corte **minimalista**: fuera ventas/neto/apartados/abonos y montos por empleada — quedan operaciones, piezas, cifra final y por-empleada con ops/pzas/comisiones.
- **Historial de cortes**: tabla `libreta_corte` (migración `r1f2a3b4c5d6`) guarda SOLO la cifra final (sin columnas de esperado/diferencia — sin rastro también en DB), con `creado_por` (VEND-1 o ENC-1). León lo consulta ("Ver cortes") y puede **hacer el corte de hoy** con la cifra calculada sin editarla.
- UI: banner de título "Libreta" retirado; diálogo de impresión **rediseñado táctil** (botón Imprimir 56px, Cerrar amplio, checkbox 26px, preview solo-lectura); botones estándar de Qt en **español** (Sí/No/Cancelar, `utils/qt_spanish.py`); botones sin estilo con colores explícitos (modo oscuro Windows).

Tests: `test_libreta.py` ~54 · `test_calendario_empleadas.py` ~28 · `test_api_movil.py` 9.


---

## v3.1 (2026-09-05) — blindaje y reimpresión

- **Cortes nunca se pierden offline**: si la PC principal no responde al confirmar el corte, cae a `libreta_cortes_pendientes.json` y sube solo en el siguiente refresh con base (conserva su fecha). `libreta_local_queue_service.encolar_corte/drenar_cortes`.
- **La puerta de la Libreta valida el gafete** contra `Empleada` activa (mismo criterio que venta rápida); offline o con la DB caída exige formato `VEND-N`. Un código inventado ya no abre nada.
- **Movimientos paginados**: 25 por página con "◀ Anteriores · Página X de Y · N movimientos · Siguientes ▶" (botones 44px); `_libreta_rows_pintadas` es la rebanada visible (borrar/detalle/reimprimir por índice siguen alineados); página 0 al cambiar periodo/filtro/sesión.
- **La página scrollea completa**: la tabla y la lista de empleada crecen con su contenido (sin scroll interno) y el satélite tiene scroll con el dedo (QScroller touch) en todas las páginas.
- **🖨 Reimprimir ticket** (solo dueño, barra del dueño): reconstruye el ticket de la operación seleccionada (venta/apartado) con su fecha original y leyenda `*** REIMPRESION ***`, y lo manda a imprimir **sin on_printed** — jamás re-registra. Abonos no tienen ticket. `QuickSaleWidget.build_reprint_ticket` presta el estado del carrito y lo devuelve intacto.
- **🖨 Reimprimir desde el detalle (2026-09-14)**: en "Detalle de la operación" (doble clic en un movimiento), junto a Ver momento, **para todas** — el cliente que perdió su ticket lo pide en el mostrador. Mismo `_reimprimir_row_libreta`, misma copia, nunca registra. No aparece en abonos. El de MOVIMIENTOS sigue solo dueño.
- **CON TARJETA (LLEGA) (2026-09-14)**: la tarjeta del dueño (satélite y celular) muestra en grande lo que **llega** por la terminal (neto tras 4.5%, `ResumenPeriodo.tarjeta_neto` = suma de `monto_neto`) y en chico "cobrado $X". Los tickets de corte (dueño, encargado, remoto) dicen `Tarjeta, llega (N): $neto` (sin leyenda de lo cobrado, Daniel la quitó) y **VENTA TOTAL = efectivo + lo que llega**. Daniel: *"lo que importa es saber cuánto llega"*.
- **La venta descuenta stock (2026-09-14)**: `registrar_operacion` llama `descontar_stock` (ver [[07 - Servicios - Catálogo e Inventario]]); borrar una operación lo regresa.
- UI: banner de título retirado; periodos solo Hoy + Mi/Su ciclo.
- **💳 Cambiar pago** (solo dueño, `2026.10.26`): alterna tarjeta/efectivo del registro seleccionado con confirmación y **recalcula el neto** con la regla de la venta (`libreta_service.cambiar_pago_tarjeta`: 4.5% por producto sobre el precio cobrado —con descuento de empleada si lo hubo— redondeado; efectivo → neto = total; abonos sobre el monto). Para cuando la empleada olvidó marcar tarjeta.
- **Corte sin piezas** (`2026.10.29`): ni "Piezas:" arriba ni "pzas" por empleada — quedan operaciones, VENTA DE HOY y comisiones por empleada ("4 ops: 15 com.").

## v4 — Solo dinero real + anticipo de apartado (2026-09-06)

- **Vista del dueño sin saturar**: tarjetas **EN EL CAJÓN (EFECTIVO)** (la cifra del corte) · **CON TARJETA** (llega por la terminal, neto tras 4.5%) · **ABONOS** (parte del cajón) · **COMISIONES**. Se quitó "Vendido en total": el valor de un apartado no es dinero recibido y creaba falsas expectativas (principio de Daniel: *lo que importa es cuánto hay en el cajón*).
- Arriba solo **Imprimir corte** + **⚙ Más opciones** (rango de fechas y meta semanal plegados). Reimprimir / Cambiar pago / Borrar viven junto a Movimientos ("Con el movimiento seleccionado:"). **Por día** solo aparece en Su ciclo / rango (6 columnas, crece sin scroll interno). Ranking sin piezas.
- **Comisiones: 3pz = 2** (antes 3). Registros previos recalculados en producción con `scripts/recalcular_comisiones_libreta.py` (vista previa por defecto, `--aplicar` guarda).
- **Anticipo de apartado**: el diálogo de apartado en venta rápida pide el anticipo que deja la clienta hoy (mínimo 25%, teclado en pantalla, efectivo/tarjeta). En el ticket va **una sola vez**: primer renglón del registro de abonos (fecha · monto · restante; "(tarjeta)" si aplica) — sin bloque repetido bajo el total. En la Libreta el apartado anota además un **abono** "Cliente · anticipo" (sin comisión) — así el cajón sí incluye ese dinero. Sin columna nueva en la base.
- **Reasignar movimiento** (`2026.11.10`, `020ce72`): botón **👤 Reasignar** junto a Movimientos (solo dueño) → diálogo táctil con un botón por empleada activa → `libreta_service.reasignar_empleada` mueve código/nombre y con ello las comisiones; montos, piezas y hora intactos. Caso real: una puso su gafete y otra hizo la venta.
- VERSION `2026.11.10`.


## v5 — Cámaras, caja con reactivo y nómina (2026-09-08)

La Libreta del dueño se volvió el centro de gestión. Nuevo en su barra "Con el movimiento seleccionado": **📹 Ver momento** (grabación del DVR a esa hora, [[32 - Cámaras y Afluencia]]), **⚙ Caja y nómina**, **💵 Pagos** (historial con desglose), **🧾 Cortes** (historial de cortes con reimpresión, 2026-09-09), **👥 Equipo** (baja/reactivar/horario), **💸 Retiro**. Secciones nuevas en el panel: **AFLUENCIA** (entran · pasan por fuera · ventas · conversión por hora) y **PENDIENTES DE HOY** (pagos que tocan, posibles faltas, descansos, sin horario — con botones de un toque). **Imprimir corte** ahora es el corte por periodo con reactivo: muestra lo que debe haber, captura lo contado y cuánto se queda de reactivo, ve sobra/falta, e imprime `CORTE DE CAJA` con pagos y retiros desglosados. Todo en [[33 - Caja, Nómina y Corte Automático]].

`_pintar_afluencia_libreta`, `_pintar_pendientes_libreta`, `_imprimir_corte_libreta` (→ `hacer_corte_caja`) en `quote_satellite_window.py`. VERSION `2026.11.11`.


## Vista de la empleada — rediseño (2026-09-09)

- La franja naranja "Comisiones desde tu último pago…" (que se estiraba con el espacio sobrante) es ahora una **tarjeta con tres datos**: ⭐ comisiones del ciclo · 💵 próximo pago (fecha + "faltan N días" / "¡hoy!" / "pendiente de registrar") · 🛌 siguiente descanso (no aparece en modo por días). `_datos_ciclo_libreta` + `_tiles_ciclo` (puro) + `_pintar_ciclo_libreta`.
- "Llevas N piezas…" quedó como **subtítulo bajo el saludo** (`libretaSubtitulo`), ya no flota a media página. `view_ly.addStretch(1)` al final: el sobrante va abajo.
- Movimientos en **dos renglones** (hora · Vendiste N piezas (+com) / prendas) con **word-wrap**; alto exacto con `_ajustar_alto_lista` (`doItemsLayout` + `visualItemRect`) y se recalcula al cambiar el ancho (`resizeEvent`). Estilos en `satellite_styles.py` (`libretaCicloCard`, `cicloValor`, `cicloCaption`).

## Vista del dueño — dinámica (2026-09-09)

- **Ya no se desborda a la derecha**: los subtítulos de las tarjetas envuelven (`setWordWrap`), antes forzaban el ancho y la página cortaba botones.
- **Secciones plegables** (`_libreta_secciones`, `_seccion_libreta`, `_aplicar_seccion_libreta`): POR DÍA · AFLUENCIA · PENDIENTES DE HOY · EQUIPO · MOVIMIENTOS, cada encabezado es un botón ▾/▸. **Afluencia sin datos de cámaras** se pliega sola a un renglón "sin datos de cámaras · N venta(s)" en vez de una tabla de ceros.
- **Gestión** (Retiro, Cortes, Pagos, Equipo, Caja y nómina) va en la barra junto a **Imprimir corte**; las **correcciones** (Reimprimir, Cambiar pago, Reasignar, Borrar, Ver momento) solo aparecen al seleccionar un movimiento (`libreta_acciones_bar`, `_on_libreta_seleccion`).
- Tablas por día/afluencia con renglones de 36 px.

## Cifras oficiales y cifras reales (2026-09-10)

> [!important] Vocabulario de Daniel
> **OFICIAL** = su cifra **con** sus ajustes. Es la que se presenta, la que ve el encargado y la que se audita. **Se muestra sin ninguna marca que la delate.**
> **REAL** = lo que de verdad se vendió, **sin** ajustes. Solo la ve él, y solo al pedirla.

- La tarjeta **EN EL CAJÓN (EFECTIVO)** aplica los ajustes de los cortes del periodo (`corte_caja_service.ajustes_en_rango`, solo cortes de VEND-1) y conserva el pie de siempre: "ventas + abonos en efectivo · es la cifra del corte".
- **Ctrl+Shift+R** (solo dueño) asoma lo real: la cifra sin ajustes y el pie "REAL · lo que se vendió, sin tus ajustes (±N)". Se repite para volver a lo oficial. El mismo atajo funciona en 🧾 Cortes (columnas *Real (sin ajustes)* y *Ajuste*).
- Código: `_alternar_ver_real_libreta`, `_libreta_ajuste`, `_libreta_ver_real` en `ui/quote_satellite_window.py`. Tests: `test_libreta.AjusteEnLibretaTests`.

## Movimientos privados del dueño (2026-09-09)

Un cobro **con tarjeta** que Daniel marca como privado **desaparece del dinero que ve el encargado**: no sale en su ticket del corte, ni en su pantalla, ni en su modo del celular.

- **Cómo**: MOVIMIENTOS → selecciona el cobro → **🔒 Ocultar del corte** (y **👁 Incluir en el corte** para revertir). En la lista aparece con 🔒. Solo con gafete VEND-1.
- **Solo tarjeta**: el efectivo está físicamente en el cajón; esconderlo descuadraría el corte. El diálogo lo explica y lo impide.
- **La empleada no pierde nada**: las piezas y las **comisiones siguen contando** para su pago (corregido en `1f0ee80b`).
- **De un golpe**: al hacer el corte hay una casilla **"Ocultar los cobros con tarjeta (no salen en el ticket)"** (solo dueño) que oculta todos los del periodo; desde el celular, `/corte sintarjeta`. **Se recuerda** (2026-09-10): llega como la dejaste la última vez, y vale igual en el kiosko y en la app (`caja_parametros.ocultar_tarjeta`, migración `y8a9b0c1d2e3`; `corte_caja_service.recordar_ocultar_tarjeta`).
- Código: `libreta_service.marcar_privado`, `marcar_privadas_del_periodo`, `sin_privados`, `hay_privados`, `comisiones_ocultas`; `nomina_service.ve_privados` decide quién ve el dinero; `corte_caja_service.datos_ticket_encargado` arma lo que va al papel del encargado. Columna `libreta_venta.privado` (migración `x7f8a9b0c1d2`). Tests: `test_libreta_privados`, `test_api_movil`.

> [!warning] La casilla del corte hace DOS cosas
> "Ocultar los cobros con tarjeta" nació (`2b8d6d0d`) como algo **solo del papel**: quitaba la línea "Con tarjeta" del ticket. Con los movimientos privados (`0e433efe`) además **marca los movimientos como privados en la base**, así que ese dinero desaparece de todo lo que ve el encargado, no solo del papel. Hoy conviven las dos capas en `hacer_corte_caja`.

> [!bug] Corregido el 2026-09-09 (`1f0ee80b`)
> La primera versión de "privado" también le escondía al encargado las **piezas y comisiones**, y por eso el pago calculado de la empleada salía **más bajo**. Se revirtió: lo privado esconde el **dinero**, nunca lo ganado. Las comisiones cuentan completas para la nómina, el desglose y el ticket.
