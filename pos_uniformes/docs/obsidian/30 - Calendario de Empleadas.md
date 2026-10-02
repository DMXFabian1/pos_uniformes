---
tags: [pos-uniformes, calendario, empleadas, libreta]
---

# Calendario de Empleadas (2026-09-04)

> Descansos, faltas y pagos dentro de la Libreta del satélite. Objetivo cumplido:
> **Daniel ya no está en medio negociando descansos** — las reglas deciden solas.

## Reglas de negocio (decididas por Daniel)

| Regla | Valor |
|-------|-------|
| Pago | Cada **7 días de CALENDARIO** desde el último pago → cobran siempre el mismo día de la semana |
| Falta | **NO mueve** la fecha de pago (se descuenta al pagar); queda registrada y los días trabajados se cuentan para control |
| Descanso | Un día **FIJO** semanal por empleada; excepciones por evento (movido/extra) |
| Cupo | Máximo **1 empleada descansando por día** |
| Anticipación | Descansos y cambios se piden con **7 días** |
| Cuota | **2 movimientos al mes** por empleada (pedidos + intercambios juntos); las marcas del dueño/encargado no gastan cuota |
| Intercambios | Entre compañeras con **doble gafete** (A propone, B acepta escaneando) — **sin aprobación de Daniel** (suma cero) |

## Vistas por rol

- **Empleada** (📅 en Libreta): mes pintado (descanso azul, falta rojo, pago verde), banner "⭐ Comisiones desde tu último pago + 🛌 siguiente descanso + 💵 próximo pago". Autoservicio: **Pedir descanso este día** (la app aprueba/rechaza sola y sugiere días libres) y **Cambiar con compañera**.
- **Dueño VEND-1**: selector de empleada, marcar falta/descanso/trabajó/quitar, **💵 Le pagué este día** (reinicia ciclo y banner), configurar horario. Historial de pagos no se pisa.
- **Encargado ENC-1 (León Fabian)**: modo ultra-simple de 3 preguntas — ¿De quién? → Faltó / Le doy descanso → Hoy / Mañana / Otro día — con "Me equivoqué (borrar)". Sin dinero, sin config. Además: **Ver cortes** (fecha y cifra) y **Hacer corte de hoy** (cifra calculada, SIN poder editarla, firmado ENC-1). Gafete = Empleada `ENC-1` (QR EMP:ENC-1, tarjeta en `generated/employee_cards/`).

## Sincronía con el calendario del kiosko

La página "Calendario" (conteos) pinta solos los chips 🛌 descansos y 💵 pagos (hechos + próximo proyectado) de las empleadas. **Faltas NO salen ahí** (privadas de la Libreta). Los recordatorios manuales de ese calendario se **retiraron** (redundantes; código vivo con nota para revivir).

## Infraestructura

| Pieza | Archivo |
|-------|---------|
| Modelos | `EmpleadaHorario` + `EmpleadaEvento` — migración `q0e1f2a3b4c5` |
| Servicio | `services/calendario_empleadas_service.py` (estado del día, próximo pago, autoservicio, cuota, chips) |
| Diálogos | `ui/dialogs/calendario_empleadas_dialog.py` (`CalendarioEmpleadasDialog` + `CalendarioEncargadoDialog`) |
| Gate ENC-1 | `_on_libreta_gate_scan` → `_abrir_calendario_encargado` en `quote_satellite_window.py` |
| Tests | `tests/test_calendario_empleadas.py` (~28) + gate/encargado en `test_libreta.py` |

> [!note] Datos en producción (2026-09-08)
> Al 2026-09-08 siguen **7 activas sin descanso fijo** (Cristal, Evelyn, Fanny, Katherine, Lupita, Nayeli, Stayce). Se capturan desde Libreta → 👥 Equipo → ✏️ Horario (o desde Pendientes → Configurar). Lupita ya no trabaja → dar de baja. Naye → tipo "por días" sáb/dom.

## v2 (2026-09-08) — nómina, por días y León

- **Pago con monto**: "💵 Le pagué este día" calcula 1,300 + 2/comisión − 216.67/falta, muestra el desglose y guarda `empleada_pago`; usa la **fecha seleccionada** (adelantos o pagos olvidados). Ver [[33 - Caja, Nómina y Corte Automático]].
- **Modo por días** (`modo_pago="por_dia"`, `dias_trabajo`): estado del día = trabajo solo en sus días (o evento "trabajo"); pago al terminar sus días (último weekday del patrón); cobra sueldo/6 por día; no hay faltas. `quienes_descansan` las ignora (un lunes no "descansa", no le toca). Naye.
- **León**: su menú muestra quién descansa hoy/mañana y pagos de la semana; tercera opción **✅ Vino a trabajar (día extra)**; su corte ya es de un botón y registra los pagos solo; **💸 Saqué dinero del cajón**. Ya no registra pagos a mano.
- `guardar_horario` acepta `modo_pago`, `dias_trabajo`, `fecha_ultimo_pago` (con `actualizar_ultimo_pago=True`).

## Descanso movido (2026-09-13)

Daniel: *"una empleada faltó, pero no descansó; tomamos ese día como descanso"*. Darle **descanso en un día que no es el suyo** (`/descanso_Fanny` en Telegram, "Le doy descanso" en el kiosko, encargado, PWA — todos pasan por `marcar_dia`) ahora **mueve el descanso de esa semana**: el fijo queda como `TRABAJO` con nota `descanso movido al dd/mm`. Sin falta, sin descuento, un solo descanso en la semana. Quitar esa marca regresa el fijo. Una `FALTA` no mueve nada; un día fijo que ya tenía marca propia se respeta; las de `por_dia` no tienen fijo. Tests: `DescansoMovidoTests`.

**Y la nómina descuenta por días, no por marcas (2026-09-13):** *"solo se descuentan faltas cuando laboran menos de sus días"*. `faltas_netas_en_rango` = faltas marcadas − días trabajados **de más** (`dias_extra_en_rango`: vino en su descanso fijo **sin** haber descansado otro día de esa semana), dentro del mismo ciclo de pago, nunca negativo. Stayce faltó el martes y vino el sábado → 0 faltas, pago completo; faltó y además descansó su día → 1 falta. **Corrección 2026-09-15:** el sábado que trabaja porque su descanso se movió al martes no es día de más, solo compensa el martes; si además faltó el miércoles, laboró 5 de 6 y se descuenta 1 (antes salía pago completo). Se calcula por semana: `max(0, trabajó el fijo − descansos en otro día)`. Tests en `test_nomina_service`.

## Pendiente

- Fase 2 admin: cuadrícula mensual (empleadas × días), recibo de pago impreso, aviso "mañana le toca pago a X".
- El papá debe capturar en el calendario en vez de recorrer de palabra ("si no está en el calendario, no existe").


## Calendario del kiosko: detalle del día y pago con gafete (2026-09-09)

- **Tocar un día** de la página Calendario abre `DiaCalendarioDialog`: tres tarjetas (🛌 descansa · 💵 día de pago · 📋 conteos) sin truncar, y abajo **"¿Cuánto llevas? Escanea tu gafete"**.
  - Gafete de empleada → SOLO su pago pendiente con desglose (sueldo o días × tarifa, comisiones, faltas, TOTAL HOY, cuándo le toca).
  - Gafete de Daniel (VEND-1) o León (ENC-1) → tabla con el de todas las activas (sin ellos).
  - Cualquier otro código → "no es un gafete activo". Lo mostrado se oculta solo a los 45 s (pantalla compartida) o con "Ocultar pago".
- **Empleadas por días (Naye)** ya no aparecen "descansando" los días que no les tocan; solo su pago proyectado (`chips_calendario_mes`).
- **Faltas a la vista (2026-09-09)**: chip rojo ❌ con el nombre junto a descansos y pagos, y tarjeta **❌ FALTÓ** en el detalle del día. Antes solo vivían en el calendario privado de la Libreta.
- Estética: celdas con hover y cursor de mano, hoy con anillo terracota, fines de semana atenuados, "+N más · toca para ver".
- Código: `services/dia_calendario_service.py` (`resumen_dia`, `vista_de_pagos`, `lineas_pago`) · `ui/dialogs/dia_calendario_dialog.py` · `conteo_calendario_mes_panel.py` · tests `test_dia_calendario`.

**Quitar una marca desde el celular (2026-09-19):** en "¿Qué pasó con X?" (encargado, y ahora también el dueño desde su inicio con *👥 Asistencia*) aparece "Apuntado (últimas dos semanas)" con **Quitar** por marca (`GET /movil/encargado/marcas/{code}` → `{fecha, tipo, texto}` de −14 a +7 días; `POST /encargado/marcar` con `tipo="quitar"`), y el botón *Sí vino (en su descanso)* (`tipo="trabajo"`). Antes solo se podía corregir en el kiosko (Quitar marca) o repitiendo `/falta_X` en Telegram.
