---
tags: [pos-uniformes, caja, nomina, corte, libreta, encargado]
---

# Caja con reactivo, nómina y corte (2026-09-08 → 2026-09-10)

> [!success] Qué resuelve
> "Que los cortes y los pagos se calculen solos, y que le diga al encargado cuándo descansan y a quién se le paga." Todo vive en la Libreta del kiosko y en la app del celular; el POS principal conserva su `SesionCaja` aparte (`caja_service.py` ≠ `corte_caja_service.py`).

## Reglas de negocio (decisiones de Daniel)

| Regla | Valor |
|-------|-------|
| **Reactivo** | Fondo que se queda en el cajón entre cortes. Arrancó en **$11,160**. Se llama *reactivo*, no "fondo", en los tickets |
| **Corte por momento** | Cubre desde el corte anterior (`libreta_corte.hasta`) hasta ahora; lo vendido después cae en el siguiente aunque sea el mismo día |
| **Sueldo** | **$1,300** por ciclo de 7 días + **$2 por comisión** − **$216.67 por falta** (1/6 del sueldo; cantidad supuesta). Editable en Libreta → ⚙ Caja y nómina (`caja_parametros`) |
| **Quién** | Solo el dueño (VEND-1) y el encargado (ENC-1) hacen cortes, pagos y retiros. `AUTO` es la tarea programada |
| **Empleadas por días** | Modo `por_dia`: cobra sueldo/6 por día trabajado (patrón + días extra apuntados como "vino a trabajar"), sin faltas, **al terminar sus días** |
| **Horario** | Cierra 18:00; **jueves y domingo 17:00**. El corte se propone 30 min antes (17:30 / 16:30); el resumen de Telegram 15 min antes (17:45 / 16:45) |
| **Papel** | Los tickets NO imprimen esperado ni diferencia |

## Oficial y real

> [!important] Vocabulario firme (Daniel, 2026-09-10)
> **OFICIAL** = la cifra del dueño **con** sus ajustes. Es la que se presenta, la que ve el encargado y la que se audita. **Se muestra sin ninguna marca que la delate.**
> **REAL** = lo que de verdad se vendió, **sin** ajustes (`libreta_corte.monto_esperado`). Solo la ve el dueño, y solo al pedirla con **Ctrl+Shift+R**.

| Dónde | Qué se ve |
|-------|-----------|
| Ticket, "Ver cortes" del encargado, PWA | **Solo lo oficial**. Con ajuste, la venta impresa es la que cuadra con la cifra (venta = cifra − reactivo + pagos + gastos): el papel siempre suma y nada delata |
| Libreta del dueño | La tarjeta EN EL CAJÓN aplica los ajustes del periodo (`corte_caja_service.ajustes_en_rango`, solo cortes de VEND-1) y conserva el pie de siempre. **Ctrl+Shift+R** enseña lo real ("REAL · lo que se vendió, sin tus ajustes (±N)") |
| 🧾 Cortes | Columnas *Venta real* y *Ajuste* **escondidas**; **Ctrl+Shift+R** las asoma y el título pasa a "· con lo real" |
| Telegram del dueño (canal privado) | "Ajuste: real $X → oficial $Y"; el resumen de la noche dice "ajustado (real $X)" |

**Ejemplo real (09/09/2026):** venta real $16,640 · se reporta $13,640 · se entrega **$12,042** · **$3,000 sin reportar**. Todo cuadra con $13,640 en el papel, en la Libreta, en la app y para el encargado.

## El ticket

> [!important] Un solo formato para todos (2026-09-10)
> El **ticket simple** (`CORTE`) es el default en **todos** los caminos: Libreta → Imprimir corte, el botón del encargado, `/corte` de Telegram y las reimpresiones. El **completo** (`CORTE DE CAJA`, con operaciones por empleada) es opcional: casilla "Ticket completo" en 🧾 Cortes (al cambiar de corte vuelve al simple).

Estructura (`_bloque_cuenta` + `_bloque_pagos` en `corte_caja_dialog.py`), pedida por Daniel el 2026-09-09 ("más simple"):

```
Reactivo en caja          ← primera línea
Venta en efectivo
Con tarjeta (N) · VENTA TOTAL · "(la tarjeta no esta en el cajon)"   ← solo si hubo
─────
Venta en efectivo
  − Pago a X / − Gasto (motivo)                ← una línea por resta
═════
SACAR DE LA VENTA
"El reactivo de la caja se queda igual"        ← u OJO si bajó
─────
PAGAR A X (desglose) / YA PAGADO A X (hora)    ← sueldo + comisiones − faltas
COMISIONES por empleada
```

Sin "EN CAJA" ni "Se retira". Los cortes viejos sin reactivo imprimen `Total del dia`.

## Los dos caminos del corte

| | **Dueño** (Libreta → Imprimir corte) | **Encargado / automático** |
|---|---|---|
| Quién | VEND-1 | ENC-1 (botón "Hacer corte") · `AUTO` · el dueño por Telegram `/corte` |
| Captura | **¿Cuánto se vendió? (efectivo)** — la cifra con la que se razona el corte (2026-09-10; antes pedía el total del cajón) — más el reactivo que se queda, otros retiros y nota. Debajo, en vivo: si es la venta registrada o cuánto difiere, y **cuánto queda en el cajón** (`contado_desde_venta`) | **Nada**: cifra calculada, mismo reactivo (baja solo si los pagos superaron la venta) |
| Pagos | Los que ya se registraron en el periodo (salen como YA PAGADO) | **Registra solos** los que tocan hoy o están atrasados (`pagos_que_tocan_hoy`) |
| Función | `hacer_corte_caja()` | `cerrar_corte_automatico()` / `hacer_corte_y_avisar()` |

**La casilla "Ocultar los cobros con tarjeta"** (solo dueño) hace dos cosas: quita la línea del papel **y** marca esos movimientos como privados en la base ([[28 - Libreta Digital]]). Desde el 2026-09-10 **se recuerda**: llega como la dejaste la última vez, igual en el kiosko y en la app (`caja_parametros.ocultar_tarjeta`).

**El corte pregunta antes de imprimir** (2026-09-09): a la hora del corte el sistema propone por Telegram y espera `/corte` o `/nocorte`; recuerda una vez y si no, la caja se queda sin corte. Ver [[34 - Telegram y Resumen Diario]].

## Pantalla del encargado (kiosko y PWA)

Tarjetas 🛌 HOY DESCANSA / 🛌 MAÑANA DESCANSA (nombre de pila) y 💵 PAGOS con **una línea por persona** `Fanny · HOY · $1,588` (HOY/ATRASADO en terracota; fechas en español vía `nomina_service.cuando_pago`), más "Hora del corte: 17:30 (jueves y domingo 16:30)". Botones en orden de uso: **🧾 Hacer corte** (acento), Apuntar falta o descanso (con **✅ Vino a trabajar**), **💸 Saqué dinero del cajón** (monto + motivo), Ver cortes. Nunca cuenta ni captura nada.

## Herramientas del dueño en la Libreta

| Botón | Hace |
|-------|------|
| 🧾 Imprimir corte | El corte del dueño (arriba) |
| ⚙ Caja y nómina | Reactivo vigente, sueldo, $/comisión, descuento por falta |
| 💵 Pagos | Historial por mes × empleada con desglose y quién lo registró. **↩ Deshacer pago** (VEND-1): quita un pago registrado por error, borra la marca 💵 del calendario y regresa `fecha_ultimo_pago` para que el ciclo cuente completo |
| 🧾 Cortes | **Historial por mes**. Columnas con las mismas palabras que el ticket: Fecha · Hora · Periodo · Por · **Reactivo · Venta · Pagos · Gastos** · Nota (`venta_oficial` = cifra − reactivo + pagos + gastos). *Venta real* y *Ajuste* solo con Ctrl+Shift+R. Al seleccionar: ticket reconstruido, **🖨 Reimprimir** (marcado `* REIMPRESION *`), **✏️ Ajustar la venta**, **↩ Quitar el ajuste**, **🗑 Borrar corte** |
| 👥 Equipo | Empleadas con estado, horario, último pago; **⛔ Dar de baja / ✅ Reactivar** y **✏️ Horario** |
| 💸 Retiro | Saqué dinero con motivo |
| 📹 Ver momento | Grabación del DVR ([[32 - Cámaras y Afluencia]]) |
| **PENDIENTES DE HOY** | Pagos que tocan/atrasados, posibles faltas, descansos, sin horario configurar |
| Calendario → 💵 Le pagué este día | Usa la fecha seleccionada: pagar adelantado o registrar un pago de otro día |

### Corregir cortes (solo VEND-1)

| Acción | Qué hace |
|--------|----------|
| **✏️ Ajustar la venta** | Cambia lo que se **reporta** de un corte ya hecho. Se captura la venta oficial y el diálogo enseña en vivo cuánto se entrega y cuánto queda **sin reportar**. La cifra se recalcula con la cuenta del ticket, así "se retira" cuadra con lo entregado. No deja bajar de lo que necesita el reactivo (`ajustar_corte`) |
| **↩ Quitar el ajuste** | Deja la cifra oficial igual a la real (ajustes de prueba). El reactivo no se toca (`quitar_ajuste`) |
| **🗑 Borrar corte** | Quita un corte doble o equivocado. Si era el último, el periodo abierto vuelve a arrancar en el anterior y el reactivo regresa a `reactivo_inicial`; si era de en medio, el siguiente hereda su `desde`. **Los pagos NO se borran** (son dinero entregado): para deshacerlos, 💵 Pagos → ↩ Deshacer pago (`borrar_corte`) |

## Infraestructura

| Pieza | Archivo |
|-------|---------|
| Corte por periodo | `services/corte_caja_service.py` (`estado_caja`, `cerrar_corte`, `cerrar_corte_automatico`, `pagos_que_tocan_hoy`, `ajustes_en_rango`, `recordar_ocultar_tarjeta`) |
| Nómina | `services/nomina_service.py` (`calcular_pago`, `registrar_pago_con_monto`, `deshacer_pago`, `avisos_de_pago`, `cuando_pago`, `resumen_para_encargado`) |
| Historial de cortes | `services/historial_cortes_service.py` (`listar_cortes_mes`, `venta_oficial`, `venta_real`, `ajustar_corte`, `quitar_ajuste`, `borrar_corte`, `es_legacy`, `datos_para_reimprimir`) |
| Propuesta de corte | `services/corte_propuesta_service.py` · `corte_remoto_service.py` |
| Pendientes · Equipo · Retiros · Horario | `pendientes_service` · `equipo_service` · `retiros_service` · `horario_tienda_service` |
| Diálogos | `corte_caja_dialog.py` (corte, parámetros, pagos, retiros, tickets) · `historial_cortes_dialog.py` · `historial_pagos_dialog.py` · `equipo_dialog.py` |
| API móvil | `/encargado*` · `/dueno/corte_estado` · `/dueno/corte` |
| Migraciones | `t3b4c5d6e7f8` (caja_parametros, empleada_pago, periodo) · `u4c5d6e7f8a9` (por día) · `v5d6e7f8a9b0` (caja_retiro) · `w6e7f8a9b0c1` (alerta_telegram) · `x7f8a9b0c1d2` (libreta_venta.privado) · `y8a9b0c1d2e3` (caja_parametros.ocultar_tarjeta) |
| Tests | `test_corte_caja_service`, `test_nomina_service`, `test_corte_caja_dialog`, `test_historial_cortes`, `test_historial_pagos`, `test_corte_propuesta`, `test_corte_remoto`, `test_pendientes_service`, `test_equipo`, `test_empleada_por_dia`, `test_retiros`, `test_horario_tienda`, `test_libreta`, `test_api_movil` |

> [!bug] Errores corregidos
> - **El pago del día no se restaba** en el corte del bot (2026-09-09): se fijaba la hora antes de registrar el pago y quedaba fuera del periodo. Ahora se fecha a la hora del corte.
> - **"Hoy no se paga a nadie" restando en silencio**: los pagos ya hechos en el periodo salen como YA PAGADO A X (hora) y en la cuenta.
> - **Cortes viejos reimpresos con 90 días de ventas**: los de antes del 08/09 (sin `desde`) se reconstruyen con su día completo (`es_legacy`).

Relacionado: [[28 - Libreta Digital]] · [[30 - Calendario de Empleadas]] · [[34 - Telegram y Resumen Diario]] · [[31 - PWA Libreta Móvil]]


> [!info] Faltas netas (2026-09-13)
> La nómina ya no descuenta por cada marca de falta sino por **días de menos**: una falta se compensa si ese ciclo trabajó su día de descanso (`faltas_netas_en_rango`). Ver [[30 - Calendario de Empleadas]].

> [!info] Pagos que tocan hoy en el corte del dueño (2026-09-13)
> `hacer_corte_caja` lista `pagos_que_tocan_hoy` con casilla por empleada (marcadas); lo que queda en el cajón los resta en vivo y al guardar se registran con la hora del corte (dentro del periodo) antes de `cerrar_corte`. Antes solo restaba pagos ya registrados y el corte del domingo no descontó a Stayce, Cristal y Naye. Tests: `test_corte_pagos_de_hoy`.

> [!info] Tarjeta en el ticket: lo que llega (2026-09-14)
> `_bloque_cuenta` recibe `tarjeta_neto` (o lo calcula con `aplicar_comision_terminal`): `Tarjeta, llega (N): $neto` · `VENTA TOTAL = efectivo + neto` (sin leyenda de lo cobrado). Ver [[28 - Libreta Digital]].

## Lo que ya salió del cajón, uno por uno (2026-09-19)

El diálogo del corte (`hacer_corte_caja`) ya no resume "Pagos a empleadas ya hechos: −$X": lista **cada `EmpleadaPago` y cada `CajaRetiro` del periodo** con nombre/motivo, monto y `dd/mm HH:MM`, marcados. Desmarcar = *no salió del cajón en este periodo* (se pagó con otro dinero, o ya se contó antes): el esperado se recalcula en vivo y al guardar `corte_caja_service.marcar_fuera_del_cajon` deja `en_cajon=False` en el registro (columna nueva en `empleada_pago` y `caja_retiro`, migración `0b1c2d3e4f5a`). `pagos_del_periodo` y `total_retiros` suman solo `en_cajon=True`; `pagos_registrados_del_periodo(…, solo_en_cajon=True)` y `retiros_del_periodo(…, solo_en_cajon=True)` filtran por default (el diálogo pide todo con `False`). Volver a marcarlo en un corte siguiente lo revierte. Tests: `LoQueYaSalioDelCajonTests`.
