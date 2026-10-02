---
tags: [sesion, pos-uniformes]
---

# Historial de Sesiones

Archivo de archivo. Cada sesión cerrada se mueve aquí desde [[21 - Sesión de Trabajo]].

---

## 2026-09-06

**Rama:** `chore/reorganizacion-repo` · `214e852` → `020ce72` · VERSION `2026.10.31` → `2026.11.10`

1. **Cierre de ayer**: popup "Piezas agregadas" rediseñado (columnas claras, −/+ 44×40, sin "Ticket de venta"/"Guardar borrador" — `2026.11.01`); **copias de etiquetas sin 20 toques**: chips 5·10·20·50, mantener presionado −/+ cuenta solo, vista previa con debounce 250 ms (`2026.11.02`).
2. **Libreta v4 — vista del dueño sin saturar** ([[28 - Libreta Digital]]): tarjetas específicas y **solo dinero real** (EN EL CAJÓN · CON TARJETA · ABONOS · COMISIONES; fuera "Vendido en total" y el valor de apartados — Daniel: *"lo que me importa es cuánto hay en el cajón, no crear falsas expectativas"*); Imprimir corte + "Más opciones" plegable; correcciones junto a Movimientos; POR DÍA solo en ciclo/rango. Diagnosticado en vivo: los $617 "de más" eran el apartado de Blanca, no tarjeta.
3. **3pz = 2 comisiones** (antes 3): `COMISIONES_3PZ`; 18 registros de producción recalculados con `scripts/recalcular_comisiones_libreta.py`.
4. **Anticipo de apartado** ([[17 - App Satélite]]): el diálogo pide el anticipo (mín. 25%, teclado en pantalla, efectivo/tarjeta); va **una sola vez** en el ticket como primer renglón del registro de abonos; la Libreta anota apartado + abono "Cliente · anticipo" → el cajón lo incluye.
5. Test viejo de sidebar alineado (Tarifarios oculto, Libreta visible).
6. **Reasignar movimiento** a otra empleada desde la Libreta (una puso su gafete y otra vendió): las comisiones se van con quien vendió (`2026.11.10`).

**Tests**: libreta 73 · venta rápida 30 · ventana satélite 29 · API móvil 14 — verdes. Capturas con el estilo nativo (macOS) para validar cada pantalla.

---

## 2026-09-05

**Rama:** `chore/reorganizacion-repo` · `1cf3561` → `878bf07` · VERSION `2026.10.04` → `2026.10.25`

1. **Libreta blindada**: cortes con cola offline; el gate valida el gafete (offline: formato VEND-N).
2. **PWA en vivo**: servida desde la Mac contra la base real (Bash, no el preview — sin permiso de Red local); pull-to-refresh; **modo encargado completo** (apuntar, ver cortes, hacer corte con ticket encolado a la tienda, descansos de la semana). Vistas de Daniel/Stayce/León verificadas con datos reales. PINes documentados.
3. **Hardware de casa**: Ryzen ya (gratis, ~$50–130/mes de luz) → N100 (~$15/mes) → Mac mini M4 si entra IA local; Tailscale para HTTPS/cámara.
4. **Ronda táctil del satélite** ([[17 - App Satélite]]): diálogos copia/pago y abono, scroll con el dedo + página completa, paginación 25, carrito −/+/🗑 (5 iteraciones hasta medir con el estilo nativo: el padding del ::item resta 16px al cellWidget), sidebar limpio, Kiosko ignora gafetes.
5. **Reimprimir ticket** desde la Libreta (solo dueño, sin re-registrar).
6. Diagnóstico de "sigue igual": worktrees viejos / proceso viejo / intérprete distinto en VS Code; se abrió el satélite real desde el repo y se capturó la ventana nativa como prueba.

7. **Cambiar pago** tarjeta/efectivo desde la Libreta con neto recalculado (solo dueño).
8. **Cierre nocturno (→ 2026-09-06)**: letra del carrito 16px; **venta de productos sin código** (teclado numérico en pantalla, total en vivo); corte sin piezas; diálogo de etiquetas táctil (toggles, stepper, colores explícitos).

**Tests**: 96 en libreta+venta rápida, 14 en API móvil, 2 del diálogo de etiquetas — todos en verde. **Idea guardada para mañana**: conteos asignados por empleada desde el celular.

---

## 2026-09-04 (sesión maratónica)

**Rama:** `chore/reorganizacion-repo` · `aee1768` → `1cf3561` (~30 commits) · VERSION `2026.09.08` → `2026.10.04`

1. **Updater curado de raíz**: bug `_MEIPASS` (el exe leía mal su versión → "siempre hay actualización"), proceso zombi al actualizar (QApplication.quit + matazombis en lanzador), `instalar_kiosko_aqui.bat`, `forzar_update_satelite.bat`. Kioskos confirmados sanos en `2026.09.11`.
2. **Calendario de empleadas** ([[30 - Calendario de Empleadas]]): tablas + servicio + diálogos; regla de pago corregida con Daniel a **7 días de calendario** (falta no mueve fecha); autoservicio (cupo 1/día, 7 días anticipación, 2 cambios/mes, intercambio doble gafete) — Daniel fuera de la negociación; sincronía con el calendario del kiosko (recordatorios retirados); banner "siguiente descanso". Producción: 6 empleadas migradas a ciclo 7.
3. **León (ENC-1)**: gafete de encargado (Empleada creada en producción + tarjeta impresa), modo ultra-simple 3 preguntas ("Sí trabajó" quitado por confuso), Ver cortes (fecha y cifra), Hacer corte de hoy (sin editar).
4. **Cortes formales**: "VENTA DE HOY" (adiós EN CAJA), cifra final editable solo por el dueño **sin rastro** (ni en ticket ni en DB), corte minimalista, historial `libreta_corte`.
5. **Libreta**: carrito se vacía al imprimir (anti doble conteo), periodos Hoy + Mi/Su ciclo (Semana ocultas), banner de título fuera.
6. **UI parejo**: diálogo de impresión táctil, Sí/No/Cancelar en español (qtbase_es empaquetada), botones legibles en modo oscuro de Windows.
7. **PWA Libreta Móvil** ([[31 - PWA Libreta Móvil]]): Fases 1+B+C desde cero — login PIN, vistas por rol, buscador con escáner de cámara, etiquetas a la Brother vía cola `trabajo`; arquitectura tienda (viva) / casa (snapshot SQLite cada 15 min); verificada completa en navegador. Plática de hardware: Ryzen ya → N100 → Mac mini si IA.

**Tests**: ~46 nuevos entre calendario, libreta, api móvil. **Fixes de paso**: test de conteos con fecha podrida, tests de iconos pisados y restaurados.

---

## 2026-09-02 → 09-03

### ✅ Libreta Digital · Perf (3 rondas) · Code-review · Updates de kioskos sin USB · DESPLEGADO

**La sesión más grande del proyecto — todo quedó en piso el 09-03.** Rama `chore/reorganizacion-repo`, HEAD `c86ab3e`, pusheada.

#### Libreta Digital (ver [[28 - Libreta Digital]])
Registro automático de ventas/apartados/abonos ligado al gafete — sustituye libreta física y ticket doble. Reglas: empleadas sin dinero (test lo garantiza), dueño `VEND-1` ve todo; comisiones 3pz=3/resto 1; tarjeta 4.5% (neto por producto); abonos registran sin comisionar; semana lun-dom. Registra **al imprimir** (cerrar sin imprimir no anota), reimpresión no duplica, dueño puede borrar. Offline-first (cola JSON local + drenado con hora original). Vistas rediseñadas: tarjetas grandes, lista amigable con emojis, ranking 🥇, corte EN CAJA imprimible, meta semanal con barra. Migraciones `o8c9d0e1f2a3` + `p9d0e1f2a3b4` **aplicadas en producción**.

#### Perf (diagnóstico con 2 agentes + 3 rondas)
- WebEngine perezoso (arranque −1.7s) · `refresh_all` una sola vez + refresh dirigido post-caja · reindex Meilisearch fuera del hilo UI · probe TCP en timer de 60s · `statement_timeout` 30s · debounce en búsquedas de Settings (que además tronaban: el texto llegaba como `session`) · batch N+1 de actividad de empleadas · satélite arranca del cache (~35ms) con refresh en background · bodega batch+diferida · QWebEngineView al abrir la pestaña · resumen 11 queries→1 · combos sin doble hidratación.

#### Code-review (8 ángulos, 10 hallazgos, todos corregidos)
Settings congelado antes de exportar host detectado (decía Tienda, conectaba a localhost) · carrera que mataba el watchdog · guards del escáner acumulándose app-wide · doble clic imprimía ambos juegos · repintado del catálogo tras refresh background · CR+LF/auto-repeat en el guard · normalización de escaneo unificada · redondeo delegado a `sale_rounding_service`.

#### Venta rápida
Copia opcional confirmable con el propio gafete · pregunta tarjeta/efectivo (sin mostrar el %) · botón Abono · gafete releído ignorado · guard anti-Enter en diálogos de impresión · "Enviar a preparar" y "Tarifarios" ocultos.

#### Updates + Mensajería (ver [[29 - Updates y Mensajería]])
Share `\\192.168.0.10\pos_updates` + lanzador auto-actualizable en kioskos (usuario `kiosko/pos2026`, vc_redist requisito) · `actualizar_pc_principal.bat` todo-en-uno · reportes de consola por git (`enviar_reporte.bat`) · configs por-máquina destrackeadas de git · scripts PowerShell en ASCII (ANSI rompía comillas) · pywin32 al bundle (etiquetas) · VERSION bumpeada a `2026.09.03` — **bumpear en cada entrega**.

#### Descartado por Daniel
Devoluciones, pago de comisiones calculado, WhatsApp del corte, vista mensual, producto estrella, constancia de turno · Alexa con dictado de producto/talla (riesgo de matching; alternativa propuesta: etiquetas por escáner desde kiosko).

---

## 2026-07-12 → 07-17

### ✅ Conteo (básicos + Subir conteo) · Impresión Servidor/Estación + ESC/POS · Recordatorios · Perf calendario
**Rama:** `feat/despachador-satelite` (NO mergeada a `main`). **Commits:** `1215973` → `27c40fb` (27 commits). **3 migraciones nuevas:** `dias_vigencia_basicos`, tabla `recordatorio`, tabla `recordatorio_completado`.

> [!warning] Deploy pendiente en Windows
> El servidor Windows quedó **sin actualizar** (la Postgres de producción `192.168.0.10` estuvo apagada / fuera de red parte de la sesión). Al retomar, en la PC servidor:
> 1. `git stash` (hay cambios locales en `panel_uniformes.html`) → `git pull origin feat/despachador-satelite`
> 2. **`alembic upgrade head`** — OBLIGATORIO. Dos migraciones nuevas: `dias_vigencia_basicos` y tabla `recordatorio`. Sin esto la app nueva crashea al arrancar.
> 3. Reconstruir bundle: `PyInstaller packaging\windows\presupuestos_satelite_windows.spec --noconfirm`

**1. Productos básicos como entidad del calendario:**
- Los básicos (sin escuela, ligados por catálogo) ahora entran al calendario/pendientes como una entidad más (id-centinela `ESCUELA_ID_BASICOS=0`).
- Frecuencia propia y global: columna `dias_vigencia_basicos` en `configuracion_negocio` (+ migración `j3d4e5f6a7b8`). NULL = default.
- `obtener_estado_conteo_basicos`, `obtener/guardar_dias_vigencia_basicos`.
- UI: aparecen en Imprimir orden (fijados al inicio de la lista) y en Subir conteo; con **filtro de "Tipo de pieza"** (Malla, Playera…). Se registran con escuela NULL.
- Commits: `110f68f`, `2288086`, `1142356`, `0f448a3`

**2. "Subir conteo" (Ctrl+Shift+A → Conteos) — rediseño:**
- Botón "📤 Subir conteo" en la pestaña Calendario del kiosko.
- Tabla agrupada por producto (encabezado por producto), paleta del panel de uniformes.
- **Excluye virtuales** (Pants 3pz, Chamarra) igual que las hojas/panel — usa las funciones agrupadas con flag `virtual`.
- Estilo tipo panel: campo **Físico vacío con el esperado (Tienda) como placeholder gris** + columna **Diferencia** (−N rojo faltante, +N verde sobrante).
- Orden de tallas arreglado para **rangos** ("9-12" antes de "13-18").
- Campo Físico se recortaba en macOS → estilo QLineEdit explícito, más alto.
- Commits: `1215973`, `a692021`, `aae4f3d`, `1084020`

**3. Días sin contar + escuelas al día:**
- Imprimir orden: checkbox "Mostrar también las que están al día" (chips verdes para adelantarse).
- `EstadoCalendarioConteo` gana `dias_sin_contar`; se muestra por entidad en satélite (orden + panel frecuencias) y en el POS (`getEstadoConteo`, ahora soporta básicos).
- Commits: `7a15954`, `1142356`

**4. Impresión — arquitectura Servidor/Estación:**
- Rol explícito por PC en el admin: **🖨 Servidor de impresión** (tiene las impresoras, drena la cola) vs **📡 Estación** (solo encola, NO configura impresoras — se ocultan las cajas de config → fin del autodetect Brother fallido en satélites). En código sigue siendo `MODO_LOCAL` / `MODO_SATELITE`.
- Todo flujo térmico pasa por los helpers de ruteo; `open_printable_text_dialog` (presupuestos/ticket venta) también.
- Aviso si el Servidor no eligió impresora de tickets (si no, va a la predeterminada de Windows y se marca "impreso" sin salir papel).
- Doc nuevo: `docs/arquitectura_impresion.md`.
- Commits: `bb90ded`, `e0a0471`, `37a1b2d`

**5. Impresión — corte y estética (varias iteraciones):**
- Hojas de conteo cortaban mal (página fija de 600 mm). Se separó por documento: **tickets (venta/apartado/presupuesto) = camino histórico intacto (600 mm + drawText)**, **hojas de conteo = alto dinámico / ESC/POS**. Clave: el driver escala el render según el tamaño de página, por eso los tickets deben quedar como antes.
- Se quitó la impresión automática de órdenes (solo banner avisa).
- Commits: `4bf597b`, `62e3bab`, `dd61406`, `9d93878`, `0f25f81`

**6. Impresión — ESC/POS crudo (fix de fondo, detrás de toggle):**
- Las hojas de conteo se imprimen por **ESC/POS crudo** (spooler RAW: Windows pywin32, Mac/Linux `lp -o raw`), sin driver → ancho nativo + corte exacto. Elimina 1ª-hoja-ancha, alto dinámico y corte a destiempo.
- CP850 cubre caja (│─┌) y acentos. Ajustes por máquina (`escpos_settings.json`): toggle, **codepage** (ESC t n, default 2), corte, feed — editables desde el admin con botón **"Imprimir hoja de prueba"**.
- **PENDIENTE:** calibrar el codepage con una impresión de prueba en el servidor (solo aplica a conteos, no a tickets).
- Commits: `760704e`, `fe2a896`

**7. Rendimiento — N+1 del calendario (importante):**
- `obtener_calendario_conteo` hacía ~5 queries × 49 escuelas = **245 queries / ~9 s** en el hilo de UI (banner cada 10 min, diálogos, panel) → congelaba la app = "lento e inestable".
- Nuevo `obtener_estados_conteo_todas_escuelas`: 3 queries agregadas (GROUP BY). Medido: **8743 ms → 722 ms, 245 → 8 queries**, resultado idéntico. Test que cuenta queries para blindar contra reintroducirlo.
- Commit: `da3d5ca`

**8. Kiosko — navegación con Ctrl+←/→:**
- Cambia de sección (Kiosko → Venta rápida → Presupuesto guiado → Tarifarios → Calendario). Se detiene en extremos, salta las secciones ocultas. Ctrl (no flechas peladas) porque el campo de escaneo tiene el foco casi siempre.
- Commit: `1f0bbbe`

**9. Recordatorios en el calendario (nuevo):**
- Tabla `recordatorio` (+ migración `k4e5f6a7b8c9`), compartida entre PCs. Tipos: pago/descanso/nota. Recurrencia: única (fecha), mensual (día del mes), semanal (día de semana; "día 31" cae al último día en meses cortos). Monto opcional para pagos.
- `recordatorio_service`: CRUD + expansión pura (`ocurre_en`, `recordatorios_del_mes`, `proximos_recordatorios`).
- UI: en el calendario mensual del kiosko — botón "➕ Recordatorio" (diálogo administrar), chips de colores por día (pago azul, descanso morado, nota café) y banner de "Próximos".
- Solo en el kiosko satélite por ahora (decisión de Daniel); pendiente evaluar mostrarlos en el POS.
- **Editar** (doble clic / botón ✏️): carga en el formulario, "Guardar cambios" + "Cancelar edición"; `actualizar_recordatorio` reusa la validación y limpia campos de la recurrencia vieja.
- **Limpiar vencidos** (🧹): borra los de fecha específica ya pasada (`eliminar_recordatorios_vencidos`); los recurrentes no se tocan.
- **Clic en un día** del calendario → abre el alta con esa fecha precargada (`RecordatoriosDialog(fecha_inicial=...)`, celdas clicables `_DiaCelda`).
- **Marcar hecho/pagado por ocurrencia** (clic en el chip): tabla `recordatorio_completado` (+ migración `l5f6a7b8c9d0`, `toggle_completado`/`completados_todos`). El chip hecho sale gris, tachado y con ✓. Es por ocurrencia (pagar junio no afecta julio). Los chips consumen el clic (`_ChipRecordatorio`) para no disparar el alta del día.
- **Fixes:** (1) el diálogo arranca en HOY (semanal/mensual) — antes el semanal caía siempre en lunes; (2) el monto ya no se pega a descanso/nota si venía escrito de un pago; (3) el panel actualiza "hoy" en cada refresh (antes quedaba fijo → kiosko 24/7 con el "hoy" de ayer tras medianoche).
- Commits: `dd083ef`, `2dbeb65`, `7230d89`, `d0ae41d`, `2624510`, `27c40fb`

**Infra / entorno:**
- La **Mac ahora apunta a la Postgres de Windows** (`POS_UNIFORMES_DB_HOST=192.168.0.10`, antes localhost) — respaldo en `pos_uniformes.env.bak_localhost`. Motivo: la copia local mostraba 45 escuelas vencidas vs 25 reales. **Cuidado: opera sobre producción.**
- Tests nuevos: básicos, recordatorios, orden de tallas, ESC/POS bytes, N+1 del calendario, navegación de secciones, alto de página tickets/conteos.

---

## 2026-05-19 → 2026-07-08 (bloque archivado el 2026-08-02)

> [!info] Archivado en la reorganización del 2026-08-02
> Este bloque vivió meses en [[21 - Sesión de Trabajo]] sin archivarse. Los checklists de deploy de aquí ya fueron superados por el build `2026.07.11` de la rama `feat/despachador-satelite` (ver [[22 - Referencia Rápida]]).

### Qué toca hacer

> [!note] Pendiente menor
> 1. ~~Reparar los 6 tests desactualizados restantes~~ ✅ 2026-07-08 — suite completa en verde (1,175/0)

> [!check] POS principal — git pull en PC tienda (fixes 2026-07-03)
> 1. `git pull origin main` (trae hasta `7a6a21a`) + reiniciar el POS
> 2. Verificar: imprimir hojas de conteo y **cerrar el diálogo a media impresión** — el POS debe seguir vivo
> 3. Si algo truena, revisar `data/pos_errors.log` junto al código

> [!check] Bundle satélite `2026.07.08` — PRIORITARIO (crash impresión + promo 3pz + etiquetas Ctrl+S + resiliencia de red)
> 1. En la PC Windows: `git pull origin main` (trae `209333b` — VERSION `2026.07.08`, hiddenimports, watchdog de reconexión, pool_pre_ping, impresora de etiquetas por modo)
> 2. Generar bundle: `scripts/build_presupuestos_satelite_windows.ps1` → `2026.07.08`
> 3. Instalar en la PC satélite
> 4. **Prueba de aceptación**: imprimir venta con descuento (2 tickets) y apartado (2 copias), cerrando el diálogo inmediatamente después de imprimir — el programa debe seguir vivo
> 5. Si algo truena, revisar `%APPDATA%\PresupuestosSatelite\data\satellite_errors.log`

> [!check] Desplegar commit `5706df0` (2026-05-31) en Windows — PRIORITARIO
> 1. `git pull origin main` en la PC Windows + reiniciar app
> 2. Correr migración de bodega: `.\.venv\Scripts\python.exe scripts\migrar_codigos_bodega.py`
> 3. Verificar **Bodega**: ALMACEN-N1 aparece en dropdowns, códigos nuevos (A-P1-001)
> 4. Verificar **Ctrl+K** abre consulta de precios desde cualquier parte
> 5. Verificar **Conteo → Productos Basicos** + filtro por tipo de pieza
> 6. Verificar **Disponibilidad → carrito de pedido** + botón Copiar
> 7. Verificar **Label** imprime sin error `cut_between_copies`

> [!check] Bundle satélite `2026.06.11` — verificar tras instalar
> 1. Header muestra `Version 2026.06.11`
> 2. **Venta Rápida**: gate QR empleada → escaneo → tickets venta/apartado
> 3. **Descuento**: solo QR de Daniel (`VEND-1`) lo activa, copia empleada sale
> 4. **Piezas agregadas → Ticket de venta**: QR autoriza en modo offline
> 5. Sin líneas negras en ninguna página
> 6. Ctrl+K funciona en satélite
> 7. Label print funciona (paper_mode fix)

> [!check] Bugs detectados en auditoría 2026-07-03 — TODOS RESUELTOS ✅
> 1. ~~conteo_print_dialog~~ ✅ `a4a0c1a` — delega en `open_tickets_print_dialog` (TicketPrintQueue, −151 líneas duplicadas; botones dicen "hojas" via `unit_label`)
> 2. ~~main.py sin excepthook~~ ✅ `7a6a21a` — `install_gui_excepthook` generalizado; POS principal loguea a `data/pos_errors.log`
> 3. ~~Offline congelamientos 5s~~ ✅ resuelto en `0bb87bb`
> 4. ~~satellite_admin_dialog._restart_app~~ ✅ resuelto en `55b7656` (libera QLockFile antes de execv)
> 5. ~~Menores~~ ✅ resueltos: logs auth QR `7b4a3c5`, int(qty) `448b669`, timer school_link `a96a022`
> 6. ~~5 tests desactualizados del guiado~~ ✅ resueltos en `bcd4408` (expectativas al _PIEZA_ORDER vigente)
> 7. ~~Tallas de letra en diálogo de favoritos~~ ✅ resuelto en `0bb87bb`
>
> **Del satélite solo quedan los del POS principal**: conteo_print_dialog (migrar a TicketPrintQueue) y excepthook en main.py — ver puntos 1 y 2 arriba.

> [!check] Sprint 2 — Integridad de datos (próxima sesión)
> 1. `with_for_update()` en operaciones de stock (`inventario_service.py`)
> 2. Validar fingerprint antes de `sync_remote_to_local` (`db_sync_service.py`)
> 3. Remover `getattr` de campos críticos en `VentaService`
> 4. Reemplazar `except Exception: pass` con logging

### Estado del repo (2026-07-08, fin de jornada)
```
Rama:   main
HEAD:   0844050 feat(satélite): rediseño menú admin en pestañas
Origin: pusheado ✓ (main == origin/main)
Windows: pendiente git pull (POS principal) + generar bundle 2026.07.08 (satélite)
Sin commitear: solo panel_uniformes.html (tema aparte, Panel Uniformes)
```

> [!info] Jornada 2026-07-08 — despliegue + mejoras en piso
> Se desplegó el fix del crash y en piso salieron varias mejoras/bugs, todos resueltos y pusheados:
> promo 3pz (detección por pieza + excluir Tortuga/Chazarilla/Polos), orden de tallas de rango (calcetas), ocultar Presupuesto/Buscar, Meilisearch arranca en offline, **impresora de etiquetas dedicada por modo** (menú admin) y **scroll en el menú admin**. También se reparó tanda de tests desactualizados. Infra: la PC de tienda perdió IPv4 (DHCP), quedó en IP fija; internet de la tienda intermitente.

### Completado 2026-07-08 (2ª parte) — Suite en verde total + bug real del satélite

**Deuda de tests saldada (51 fallas → 0):** 4 frentes en paralelo —
bodega (21: REGEXP portable en SQLite + API de códigos `A-P1-001`), timezone aware (~10),
fixtures con campos nuevos (`ticket_printer`, `variante`, `anulado`, `stock_minimo`,
`stock_bodega/piso`), y expectativas de UI vigentes (hero label HTML, satélite).
**Resultado: 1,175 pasan · 0 fallan · 77 s — primera corrida limpia completa.**
Único cambio de producto por tests: `.op("~")` → `.regexp_match()` en bodega (idéntico en Postgres).

**BUG REAL destapado y reparado — `e188ba1`:** `4d13bea` (2026-06-10) borró la página
**Buscar** del satélite a medias: sin botón ni página en el stack, pero `_reveal_saved_quote`
e "Ir a buscar" seguían navegando a ella → `KeyError` que el except convertía en
**"No se pudo guardar" tras guardar/emitir un presupuesto (aunque SÍ se guardaba)**, y la
lista online de presupuestos guardados llevaba un mes inaccesible. Restaurada al final del
stack (índice 7) con botón, icono y comportamiento offline. ⚠️ **Este fix DEBE entrar al
próximo bundle del satélite** — considerar bump a `2026.07.08`.

Commits: `31625d2` (logout), `0867ec6` (docs), `e188ba1` (fix Buscar), `ea7ba6e` (bodega),
`d729da6` (resto de tests). Todo pusheado.

### Completado 2026-07-08 — Auditoría de documentación + suite completa

**Auditoría vault + docs/ contra HEAD `787be20`:** corregidas cifras y estado en notas
00, 02, 17, 18, 21, 22 (HEAD, versiones, 43 tablas reales, 241 archivos de test / ~1,178 tests,
métricas de módulos). En `docs/` del repo: `diagrama_base_datos_actual.md` (35→43 tablas,
secciones nuevas Bodega/Conteo/Empleadas), `satelite_consulta_y_cache_local.md` (Venta Rápida,
`autostart_and_reindex`, admin Ctrl+Shift+A), `mapa_modulos.md` (views/dialogs/servicios nuevos,
API ya iniciada, contrato real `seller_employee_code` en vez de `seller_employee_id`),
`arquitectura_actual.md` (entry points satélite y api/).

**Fix 2 tests que COLGABAN la suite completa** (`test_main_window_snapshot_cache.py`, tests de
logout): desde `1db1d12` (2026-05-19) `_handle_logout` usa un QDialog custom en vez de
`QMessageBox.question`; los tests seguían mockeando el QMessageBox → el diálogo real esperaba
clic en offscreen para siempre. Fix: mock de `QDialog.exec` (+ `_run_quick_backup_flow` en el
de ADMIN). Con esto la suite corre completa: **1,124 pasan · 51 fallan (todos desactualizados
conocidos, ver [[18 - Cobertura de Tests]]) · 76 s · 0 cuelgues**.

**Hallazgo pendiente:** `meilisearch_service.py` hard-codea `C:\Meilisearch` — en la Mac es ruta
relativa y creó `Playground 2/C:\Meilisearch/` con el exe de Windows (121 MB, basura borrable).
En Mac la búsqueda cae al fallback local; solo Windows arranca Meilisearch de verdad.

### Completado 2026-07-03 — Fix crash al imprimir en Venta Rápida

**Causa raíz diagnosticada** (bundle `2026.06.11` en tienda): el diálogo de tickets
agendaba `QTimer.singleShot(3000, _reset_print_button)` con `WA_DeleteOnClose` —
cerrar el diálogo antes de los 3s → RuntimeError sobre botón destruido → PyQt6
`qFatal()` → el programa aborta (verificado en Mac: exit 134/SIGABRT). Los flujos
de 2 copias lo hacían casi seguro; "tardo en imprimir" = spooler lento → el cierre
cae dentro de la ventana de 3s.

| Commit | Cambio |
|--------|--------|
| `b63fcf5` | **Fix crash + multi-ticket** (trabajo del 2026-06-17, commiteado hoy): `TicketPrintQueue` (cola segura ante cierre), `printable_text_dialog` unificado (1 diálogo, 1 clic para todas las copias), `quick_sale_view` migrado, `business_info_cache_service` (tickets offline sin timeout 5s). 20 tests |
| `74051c9` | **Excepthook global**: `utils/satellite_excepthook.py` + install en `presupuestos_satelite_main.py` — excepciones no manejadas van a stderr + `data/satellite_errors.log` (truncado 512 KB) en vez de abortar. Verificado: sin hook exit 134, con hook sobrevive. 5 tests |
| `6581099` | **Versión `2026.07.03`** para el nuevo bundle |
| `7ee8dc1` | **Ticket de presupuesto muestra mínimo para apartar**: línea "Apartado minimo (25%): $X" debajo del total en el ticket de Piezas agregadas, con `resolve_sale_rounding` (misma regla que apartado de Venta Rápida). 3 tests |
| `fda4ebf` | **Kiosko limpia el cajón en SKU inexistente**: antes solo limpiaba en éxito; un código no encontrado quedaba escrito y el siguiente escaneo se apilaba (`SKU-ASKU-B`). Ahora limpia siempre (éxito o error), con foco listo. 2 tests |
| `0844050` | **Rediseño menú admin en pestañas**: de 5 secciones apiladas (saturado en táctil) a 3 pestañas — Conexión / Impresoras / Búsqueda; cada una con scroll, Cerrar fijo. Ninguna sección se pierde (test) |
| `bdbef8a` | **Etiqueta desde búsqueda → impresora Normal/Split**: `_print_labels_for_skus` pasaba `paper_mode` default "die_cut"; ahora "standard" → sale a la impresora Normal/Split del admin. En Caja ya usaba `impresora_preferida` (Configuración) |
| `ef76ee0` | **Watchdog de reconexión**: el modo online/offline se fijaba al arrancar — apagar la PC principal tumbaba el satélite y encenderla después no se notaba. Timer cada 5 min (1º a 60 s) revisa la DB en 2º plano; si está, refresca catálogo+ligas y banner; si no, degrada sin cerrar. `threading.excepthook` para errores de hilos. Resultado hilo→UI por `pyqtSignal`. 5 tests |
| `b331342` | **Resiliencia ante caída de DB**: `(psycopg.OperationalError) server closed connection` como traceback crudo al escanear (LAN Wi-Fi parpadea). Engine con `pool_pre_ping` + `pool_recycle` 30 min + keepalives TCP; consulta/agregar del kiosko caen al catálogo local si la DB falla; mensaje amigable si el cache tampoco tiene. 5 tests |
| `4714250` | **Scroll en menú admin**: con la sección nueva de etiquetas, Meilisearch quedaba fuera de pantalla en el táctil — todo en `QScrollArea` (touch scroll), botón Cerrar fijo abajo, altura 85% de pantalla |
| `46c2e1b` | **Impresora de etiquetas por modo**: dedicar una impresora a Normal/Split/Continua y otra a Label (troquelada); config en Ctrl+Shift+A persistente por satélite (`label_printer_settings.json`), ruteo `dk1221`→Label / resto→Normal; sin config, autodetección Brother intacta. 7 tests |
| `18da44f` | **Meilisearch arranca en offline**: `autostart_and_reindex()` movido antes del probe de DB — el servicio es local y su índice persiste en disco, así que si el satélite enciende antes que la PC principal la búsqueda con typos funciona con el índice de la última vez online |
| `aec29ac` | **Secciones Presupuesto y Buscar ocultas** (decisión de operación): botones de nav + "Ver presupuesto" del kiosko con `setVisible(False)`; páginas vivas para retomarlas — restaurar = quitar 3 líneas en `quote_satellite_window.py` (buscar "Ocultos temporalmente") |
| `4469d78` | **Tallas de rango ordenan numérico**: calcetas "0-2, 3-5, 6-8, 9-12, 13-18" — como texto "13-18" ganaba a "3-5"; `_size_sort_key` parsea N-N y ordena por inicio del rango (búsqueda, variantes y favoritos) |
| `532c9dd` | **Regla de negocio promo 3pz**: solo la playera deportiva del conjunto entra — Tortuga/Chazarilla/Polos excluidas (señal: "Deportiva/o" en nombre o prenda; verificado 48 candidatas / 15 excluidas en DB real) |
| `e0cd9a4` | **Fix promo 3pz — detección por pieza** (2026-07-05, reportado en piso): "Pants 2pz Punto Verde/Gris" no disparaban la promo porque el detector busca la palabra "deportivo" y esos nombres no la traen. El adaptador reinyecta la señal de taxonomía (pieza ∈ familia deportiva). Verificado: 67/67 pants 2pz reales detectan. Requiere re-build del bundle |
| `d5bbc4a` | **Venta Rápida — etiquetas desde Ctrl+S**: al cerrar la búsqueda con piezas agregadas, confirmación con checkboxes por SKU (Todas/Ninguna, Enter imprime) → tubería de etiquetas del satélite (cache offline + Brother QL). Nuevo `label_print_confirmation_dialog` reutilizable. 8 tests |
| `f5d161d` | **Venta Rápida — promo 3pz**: al agregar pants 2pz deportivo pregunta "¿También lleva playera?" → escanear SKU o elegir de la misma escuela (tallas [Exacta]/[Sugerida]); playera a $100 con "(promo 3pz)"; al quitar el pants regresa a precio original. Reutiliza `resolve_sale_scan_variants` de caja con `CacheRowVariantAdapter` sobre filas del cache (funciona offline). Fix en caja: `_SPORT_PATTERNS` + "deportiva" (femenino no se detectaba). 10 tests |
| `55eb632` | **Meilisearch — auto-arranque + sin botones**: `ensure_running()` arranca el binario si ya está instalado (sin descargar); `autostart_and_reindex()` en los dos entry points; header del guiado solo con indicador pasivo ●/○ (controles completos en menú admin Ctrl+Shift+A). 3 tests |
| `d4b547e` | **Fix 3 tests que COLGABAN la suite de ventana**: ponían `guided_selected_sku`/`guided_mode` (muertos desde el refactor a `GuidedFlowState`) → caían al QMessageBox modal "Sin selección" → offscreen esperaba clic para siempre. Hoy hubo corridas zombis de horas por esto. ⚠️ Quedan **6 tests desactualizados más** en `test_quote_satellite_window.py` (fallan, no cuelgan — preexistentes): filter chips, solo_escuela, status_label layout, 2 de compact cards, reveal_saved_quote |
| `f3a0c33` | **Meilisearch — sinónimos + genero buscable**: `genero` al índice (antes "niña" no matcheaba); sinónimos sec/prim/bach/prepa/kinder, niña↔mujer/niño↔hombre/dama/caballero, marino→azul marino, corbatín↔moño; `index_settings()` extraída y testeable |
| `aa2f5c1` | **Meilisearch — typos y sinónimos vivos**: `matchingStrategy=all` en el motor + eliminado el doble filtrado en los 5 consumidores (Ctrl+S, catálogo satélite, catálogo/inventario POS, bodega). Antes "camisa balnca" daba 0 resultados porque el refinado local exigía substrings literales. 5 tests |
| `7a6a21a` | **Excepthook POS principal**: `install_gui_excepthook(log_path)` generalizado — main.py lo instala con log en `data/pos_errors.log`. Slots con excepción ya no abortan el POS |
| `a4a0c1a` | **Conteo — crash al cerrar a media impresión**: `conteo_print_dialog` ahora delega en `open_tickets_print_dialog` (TicketPrintQueue segura) con `unit_label="hoja"` — se eliminaron 151 líneas duplicadas con el bug del QTimer sin guard |
| `a96a022` | **Timer de status en diálogo de ligas**: `_clear_status` traga el RuntimeError si el diálogo murió antes de los 4s |
| `bcd4408` | **5 tests del guiado reparados**: expectativas actualizadas al `_PIEZA_ORDER` vigente (fallaban desde 2026-05-24); fixture deportivo con `tipo_pieza` reales |
| `448b669` | **add_sku cantidad corrupta**: cae a 1 pieza con warning en vez de ValueError |
| `7b4a3c5` | **Logs en auth QR venta rápida**: errores de DB en gate y autorización de descuento dejan traceback (antes se disfrazaban de "QR no reconocido") |
| `55b7656` | **Reinicio del menú admin**: el arranque registra el QLockFile en la QApplication y `_restart_app` lo libera antes de `os.execv` — en Windows ya no muere con "Ya está abierto" |
| `0bb87bb` | **Guards offline + tallas favoritos**: filtros de presupuestos y escaneo rápido ya no pegan a la DB en offline (congelaban 5s) — re-pintan lista local / van directo a ruta SKU del catálogo local. Diálogo de favoritos: `favorites_variant_sort_key` — tallas de letra por escala en vez de alfabético. 6 tests |
| `e0d7635` | **Fix tallas revueltas en búsqueda del guiado**: los resultados agrupaban por precio pero pintaban tallas en orden de relevancia de Meilisearch. Nueva `build_search_price_groups()` (agrupa por precio ascendente + tallas con `_size_sort_key`: numéricas primero, CH < MD < GD < EXG). 5 tests. ⚠️ Detectado de paso: 5 tests preexistentes de `test_quote_guided_catalog_helper.py` ya fallaban en HEAD (desactualizados) |
| `f1e11fa` | **Fix popup Piezas agregadas**: los botones −/+/✕ borraban/modificaban siempre la PRIMERA línea del carrito — la señal `clicked` de Qt pasa `checked` (bool) como primer arg posicional y pisaba el default `index=original_idx` → `index=False` → fila 0. Fix: las closures absorben `checked`; blindaje `normalize_cart_row_index()` (rechaza bools/fuera de rango) en `_remove_quote_item_at_index` y `_change_sidebar_item_quantity`. 8 tests nuevos |

- Suite del área: **41 tests en verde** (print queue, quick sale, business info, excepthook, startup, filter helper)
- `.gitignore`: agregados `data/business_info.json` y `data/satellite_errors.log`
- Push a origin ✓ — falta bundle en Windows (ver checklist arriba)

### Completado 2026-06-17

(Trabajo escrito el 2026-06-17, commiteado el 2026-07-03 como `b63fcf5` — detalle en la tabla de arriba.)

### Completado 2026-06-10

| Cambio | Detalle |
|--------|---------|
| **Venta Rápida** | Nueva página en satélite — gate QR empleada, escaneo auto-add, tabla editable, total con redondeo |
| **Tickets box-drawing** | Venta y apartado usan `tk_*` helpers + `open_printable_text_dialog` (antes era HTML en browser) |
| **Ticket venta — términos** | 6 puntos: revisión, cambios 15 días con ticket y etiquetas, comprobante, aclaraciones, no devoluciones, factura con datos fiscales |
| **Ticket apartado — abonos** | Cuadro de 5 renglones (Fecha/Monto/Restante) + firma del cliente |
| **Descuento empleada** | Checkbox autorizado solo por admin (Daniel Fabian via QR), 5% con redondeo regla de caja |
| **Copia empleada** | Al aplicar descuento, se genera ticket extra sin términos con precios ya con descuento aplicado |
| **QR empleada** | Restaurado prefijo `EMP:VEND-1` + normalización teclado español (`Ñ`→`:`, `'`→`-`) en gate y caja |
| **Términos en satélite** | `_build_sale_ticket_text` ahora incluye los 6 términos + pie |
| **Scroll en páginas** | Todas las páginas del satélite envueltas en QScrollArea con touch scroll |

### Completado 2026-06-11

| Cambio | Detalle |
|--------|---------|
| **Fix líneas negras** (`f8bdbc3`) | `QScrollArea.setWidget()` activa `autoFillBackground` → pintaba paleta oscura de Windows en huecos entre tarjetas. Fix: `setAutoFillBackground(False)` en página y viewport dentro de `_scrollable()`. Verificado en Windows ✅ |
| **QR auth offline** (`0183829`) | `_authorize_with_employee_qr` (Piezas agregadas → Ticket de venta) siempre consultaba DB y fallaba en modo offline. Ahora acepta formato `VEND-*` offline, igual que el gate de Venta Rápida. Nota: en offline el ticket muestra el código en vez del nombre |
| **Seguridad descuento offline** (`0183829`) | `_authorize_owner` aceptaba cualquier `VEND-*` en offline; ahora solo `VEND-1` (código de Daniel, nueva constante `_OWNER_CODE`) |
| **Versión 2026.06.11** (`60e72f3`) | Bump de `pos_uniformes/VERSION` para el nuevo bundle satélite |
| **Logo transparente** (`b43403a`) | `business-logo.png` (PNG RGBA sin fondo) + fallback PIL aplana alfa sobre blanco antes del multiply. Credencial sin recuadro blanco. POS principal |
| **Popup credencial** (`3877742`) | Quitado el QMessageBox al generar credencial (ya abre Finder); solo status label. POS principal |
| **Ctrl+S en Venta Rápida** (`64a2fa0`) | Búsqueda rápida en modo venta agrega producto al carrito vía `QuickSaleWidget.add_sku`. Con test (4 casos). Satélite |
| **Apartado — 2 copias** (`2cbde0d`) | Al imprimir apartado salen 2 tickets: `- CLIENTE -` (con términos completos) y `- COPIA TIENDA -` (sin términos). Eliminada copia de empleada en apartado. Satélite |
| **Apartado — mínimo sugerido** (`2cbde0d`→`087b872`) | Línea dentro de la caja de totales: `Apartado minimo (25%): $XXX`. 25% del total con regla de redondeo de caja ($515×25%=$128.75→$129). Etiqueta derivada de constante `_MIN_LAYAWAY_PERCENT`. Satélite |
| **ESC cierra sesión** (`5521be9`) | En Venta Rápida con sesión activa, ESC borra piezas/descuento/empleada y vuelve al gate de escaneo QR. Nuevos métodos `logout()`/`is_session_active()`. Fuera de Venta Rápida ESC conserva comportamiento previo. Con test. Satélite |

#### Archivos nuevos
| Archivo | Descripción |
|---------|-------------|
| `pos_uniformes/ui/views/quick_sale_view.py` | Widget completo Venta Rápida (~1000 líneas) |
| `pos_uniformes/tests/test_quick_sale_add_sku.py` | Tests Venta Rápida: add_sku (4), logout (2), apartado (3) = 9 |
| `pos_uniformes/assets/customer_card_template/brand/business-logo.png` | Logo MAXIMODA PNG transparente |

#### Archivos modificados
| Archivo | Cambio |
|---------|--------|
| `pos_uniformes/ui/quote_satellite_window.py` | Sidebar Venta rapida, `_scrollable()`, touch scroll, QR español, términos ticket venta, `page_stack` NoFrame, QR auth offline, Ctrl+S→venta, ESC→logout |
| `pos_uniformes/ui/views/quick_sale_view.py` | `add_sku`, `logout`/`is_session_active`, apartado 2 copias + mínimo 25%, `_OWNER_CODE`, `_MIN_LAYAWAY_PERCENT` |
| `pos_uniformes/utils/qr_generator.py` | QR empleada codifica `EMP:{codigo}` (restaurado) |
| `pos_uniformes/services/employee_card_service.py` | Logo blend multiply (HTML + PIL), aplana alfa sobre blanco. POS principal |
| `pos_uniformes/ui/main_window.py` | Quitado popup al generar credencial. POS principal |
| `pos_uniformes/VERSION` | `2026.06.11` |

### Completado 2026-05-28

| Commit | Cambio |
|--------|--------|
| `bff63b8` | **Generador tarifarios escuelas**: script unificado fpdf2 + psycopg, 91 páginas PDF |
| `d1b22cb` | **Stock por ubicación**: columnas `stock_bodega`, `stock_piso` en Variante + UI |
| `7e239c9` | **Refactor bodega→inventario**: stock_bodega/stock_piso derivados de bodega_contenido (no almacenados) |
| `7e239c9` | **Migración drop columns**: `e7f8a9b0c1d2` elimina columnas + CHECK constraints |
| `7e239c9` | **Ubicaciones fijas**: solo PISO y ALMACÉN, diálogo solo lectura |
| `7e239c9` | **Sync bodega→inventario**: toda operación invalida snapshot cache + refresca tabla inventario |
| `7e239c9` | **Mover Caja mejorado**: muestra ubicación actual, excluye del combo destino |
| `7e239c9` | **Panel Resumen**: "Cobertura de piezas" → "Valor por nivel" (valor monetario por nivel educativo) |

#### Cambios en DB
| Tabla | Cambio |
|-------|--------|
| `variante` | DROP `stock_bodega`, `stock_piso` y sus CHECK constraints |
| Migraciones | `d5e6f7a8b9c0` (add columns) + `e7f8a9b0c1d2` (drop columns) |

#### Archivos nuevos
| Archivo | Descripción |
|---------|-------------|
| `scripts/generar_tarifario_escuelas.py` | Generador PDF tarifarios (~1400 líneas) |
| `migrations/versions/e7f8a9b0c1d2_drop_stock_bodega_piso_from_variante.py` | Drop columnas derivadas |

#### Archivos modificados
| Archivo | Cambio |
|---------|--------|
| `database/models.py` | `stock_bodega/piso/tienda` como @property derivados de bodega_contenidos |
| `services/bodega_service.py` | Eliminados `_ajustar_stock_ubicacion`, `_es_ubicacion_piso`, `crear_ubicacion`, `desactivar_ubicacion` |
| `services/inventory_snapshot_service.py` | Subqueries SQL desde bodega_contenido en vez de columnas |
| `services/conteo_service.py` | joinedload de bodega_contenidos para propiedades derivadas |
| `scripts/generar_panel_uniformes.py` | CTE bodega_stock, "Valor por nivel" reemplaza "Cobertura" |
| `ui/views/bodega_view.py` | `_notify_inventory_changed()`, MoverCajaDialog mejorado |
| `ui/dialogs/bodega_ubicaciones_dialog.py` | Solo lectura, PISO y ALMACÉN fijos |
| `panel_uniformes.html` | Regenerado |

---

### Completado 2026-05-26

| Commit | Cambio |
|--------|--------|
| `2f7e1ce` | **Panel Uniformes embebido**: QWebEngineView + QWebChannel en pestana indice 8 (entre Historial inventarios y Analitica) |
| `2f7e1ce` | **Modulo conteo inventario**: 2 tablas nuevas (conteo_inventario, config_conteo_escuela), servicio completo con registro, ajuste con auditoria via MovimientoInventario |
| `2f7e1ce` | **Bridge JS↔Python**: PanelBridge con 8 @pyqtSlot methods para conteo (getVariantesParaConteo, guardarConteo, confirmarAjuste, etc.) |
| `2f7e1ce` | **Tab Conteo en HTML**: selector escuela, tabla editable con stock fisico, pendientes de ajuste con confirmacion, historial |
| `2f7e1ce` | **N/A automaticos mejorados**: compute_default_na basado en adopcion (<50% → N/A), localStorage migrado a overrides-only |
| `2f7e1ce` | **Fix WebEngine**: early import en main.py (antes de QApplication), version match PyQt6==6.10.x |
| `2f7e1ce` | **Boton eliminado**: "Panel de uniformes" removido de Configuracion (ahora es pestana directa) |
| `2f7e1ce` | **Diagnosticos mejorados**: compute_insights reescrito con 5 diagnosticos accionables (cobertura por nivel, piezas criticas, escuelas con gaps) |

#### Cambios en DB
| Tabla | Cambio |
|-------|--------|
| `conteo_inventario` | Nueva tabla — registro de conteos fisicos por variante |
| `config_conteo_escuela` | Nueva tabla — dias_vigencia configurable por escuela |
| Migracion | `29e11361cabd` (down: `c3d4e5f6a7b8`) |

#### Archivos nuevos
| Archivo | Descripcion |
|---------|-------------|
| `services/conteo_service.py` | Servicio completo de conteo de inventario |
| `ui/views/panel_uniformes_view.py` | Widget QWebEngineView + PanelBridge |
| `migrations/versions/29e11361cabd_...py` | Migracion tablas conteo |

#### Archivos modificados
| Archivo | Cambio |
|---------|--------|
| `main.py` | Early import QtWebEngineWidgets antes de QApplication |
| `requirements.txt` | Agregado PyQt6-WebEngine>=6.7 |
| `database/models.py` | Modelos ConteoInventario + ConfigConteoEscuela |
| `ui/main_window.py` | Tab Panel Uniformes indice 8, boton config eliminado, visible_by_index actualizado |
| `ui/views/settings_view.py` | Entrada de boton Panel de uniformes eliminada |
| `scripts/generar_panel_uniformes.py` | Tab Conteo HTML+JS, compute_default_na reescrito, diagnosticos mejorados, localStorage migrado |

#### Links de productos (BD directa)
- Ignacio Zaragoza: Pants 2pz Liso+Punto Azul Marino, Sueter Claudia Botones M + Cuello V H Azul Marino, Chamarra Liso+Punto Azul Marino
- Justo Sierra: Pants Suelto Liso+Punto Rojo (ya existian, panel mostraba cache viejo)
- Frida Kahlo: Corbatin Vino (reemplazo de Corbata), Jumper Escoces, Falda Escoces, Pantalon Vestir Negro
- Narciso Mendoza: Sueteres Azul Marino
- Vicente Guerrero: Falda Escoces + Jumper Escoces
- Tecnica San Bartolo: Sueter Cafe de Cierre (producto nuevo)
- Ninos Heroes de Miguel Hidalgo: Pants 3pz Deportivo (producto nuevo + 11 variantes)

### Completado 2026-05-25 (sesion continuacion)

| Commit | Cambio |
|--------|--------|
| `c46a001` | **Migración DB**: migración Alembic `tipo_pieza.tipo_uniforme` (oficial/deportivo) + script SQL idempotente `migrate_data_mac_to_windows.sql` (genero, tipo_uniforme, catalog links) |
| `7fa6ddb` | **Meilisearch UI**: barra de progreso indeterminada en Sync ↻ (`_MeilisearchProgressDialog` + `_MeilisearchWorker(QThread)`); botón `○ Meilisearch` para iniciar el servicio; indicador ●/○ con color según estado |
| `67054b2` | **Fix panel uniformes**: reemplaza `import psycopg2` directo por `engine.raw_connection()` via SQLAlchemy (proyecto usa psycopg v3, no psycopg2) |
| `e6cbab1` | **Panel N/A automáticos**: `compute_default_na` extiende a Bachillerato (todas las piezas ausentes = N/A) y Secundaria (Corbatín+Moño); UVEG/SABES/CBTIS/Conalep muestran 100% igual que en Mac |
| `96fa77f` | **Panel N/A Preescolar/Primaria**: Preescolar recibe Corbatín+Moño; Primaria agrega Mascada — denominadores ahora coinciden Mac vs Windows |
| `a8ede7a` | **Auto-detección DB + sync**: `main.py` detecta 192.168.0.10 antes de importar el engine → usa Windows directo si está en LAN; indicador 🟢 Tienda / 🟡 Local en título; nuevo `sync_catalog_to_windows.py` para push de catálogo al regresar a la tienda |

### Completado 2026-05-25 (sesión noche)

| Commit | Cambio |
|--------|--------|
| `6984469` | **Tarifario**: incluye productos ligados + filtro de género al imprimir (diálogo radio buttons original) |
| `8d982f5` | **Fix**: filtro género tarifario equipara Mujer↔Niña y Hombre↔Niño |
| `ee5df80` | **Tarifario**: separa escuelas con múltiples niveles educativos en secciones distintas |
| `eee9316` | **Fix**: Chaleco antes que Falda en `_PIEZA_ORDER` del tarifario |
| `ba903ee` | **Fix**: Chaleco antes que Falda en `_PIEZA_ORDER` del panel y favoritos del satélite |
| `613b51e` | **Tarifario kiosco**: diseño HTML moderno con encabezado visual, columnas responsivas, footer con leyenda |
| `5172042` | **Tarifario**: dividido en secciones Deportivo / Oficial / Básico con headers visuales + `_SECCION_ORDER` en `school_tariff_service` |
| `b68d0cb` | **Fix**: sección Deportivo va primero (antes Oficial aparecía primero) |
| `3d2cca3` | **Diálogo de género**: reemplaza radio buttons con tarjetas táctiles grandes (148×172px) — icono emoji 52px, toque único acepta |
| `5c193cd` | **Presupuesto guiado**: rediseño visual para kiosco táctil — títulos como pills de colores, botones más grandes (14px/12px padding), barra de búsqueda 44px |
| `a75dc98` | **Paleta cálida**: extendida a todo el programa — main_window, analytics, dialogs (inventory_label, inventory_count, school_product_link, bodega_ingreso), tabla row tints warm |

### Completado 2026-05-25 (sesión tarde)

| Commit | Cambio |
|--------|--------|
| `135fb9e` | **Rediseño visual UI**: tema cálido unificado — bodega_view.py reescrito con jerarquía visual, y toda la paleta global migrada de azul-gris a beige/marrón |
| `135fb9e` | **Bodega**: botones con roles visuales (verde=agregar, rojo=retirar, beige=secundario), tarjeta de caja seleccionada, tablas con filas alternas, sin grid |
| `135fb9e` | **`#dataTable`**: encabezados `#f0ebe4`, alternado `#f5f0e9`, selección naranja `#fdeae2` (antes azul-gris) |
| `135fb9e` | **`#cashierTotalsCard`**: marrón oscuro `#2c1810` (antes azul `#324252`) |
| `135fb9e` | **`#cashierCartTable`**: headers beige, alternado beige cálido (antes azul) |
| `135fb9e` | **GroupBoxes/infoCard**: borde `#ddd4c8` cálido |
| `135fb9e` | **Chips, stepButtons, readOnlyField, analyticsLine**: todos en paleta cálida |
| `135fb9e` | **Tab hover**: `#f0ebe4` beige (antes `#e6edf3` azul) |
| `6191d75` | **Fix**: restaurar preview monoespaciado en `printable_text_dialog.py` — `setStyleSheet+setPlainText` (regresión en `381c653`) |
| `bbfa40e` | **Presupuesto POS**: mismo formato box-drawing que satélite (`tk_*` helpers, `tk_top/mid/bot/dbl/field/row`) |
| `1412c88` | **Seguridad Sprint 1**: 5 vulnerabilidades corregidas (ver Deuda Técnica) |

### Completado 2026-05-25 (sesión mañana)

| Commit | Cambio |
|--------|--------|
| `7f1d5f3` | **Panel uniformes v2**: dark/light mode, secciones colapsables por nivel, productos ligados via CTE, PIEZA_ORDER en catálogo, Moño en PIEZA_ORDER |
| `722b8e1` | **Panel**: default NA para Primarias sin Corbata/Corbatín/Moño, Faltantes respeta marcas NA |
| `722b8e1` | **Parser presupuestos**: `scripts/presupuesto_parser.py` — CLI interactivo con fuzzy matching de escuelas |

#### Cambios en DB (Mac local, pendientes en Windows)

| Tabla | Cambio |
|-------|--------|
| `producto.genero` | Falda/Jumper/Blusa/Malla → Mujer; Pantalón → Hombre; resto NULL → Unisex |
| `producto.genero` | Mascada → Mujer |
| `producto.genero` | Suéteres: Ignacio Ramirez Cuello V → Hombre, Botones → Mujer; SABES/UVEG/Motolinea/Oferta/Margarita Paz Botones → Unisex |
| `producto.genero` | 5 camisas olan → Mujer; manga corta blanca → Unisex (parser maneja exclusión, no DB) |
| `tipo_pieza.tipo_uniforme` | Nuevo campo: Pants 3pz/2pz/Suelto/Chamarra/Playera → 'deportivo'; resto → 'oficial' |
| `catalog_school_product_link` | Olan Rojo ligado a Blanca Verónica; Olan Blanca desligada de Blanca Verónica |
| `catalog_school_product_link` | Manga corta reactivada en Blanca Verónica, Frida Kahlo, Margarita Paz (parser excluye para niñas si hay olan) |

### Completado 2026-05-24

| Commit | Cambio |
|--------|--------|
| `51d456b` | **Meilisearch tuning**: sinónimos (género colores, tallas, prendas), stop words, typo tolerance `disableOnAttributes: ["sku"]`, separator tokens `\|`, pagination 5000 hits |
| `51d456b` | **Sync Meilisearch**: botón ↻ ahora arranca el servicio (`ensure_installed()`) antes de re-indexar |
| `5b67416` | **DB sync Mac→Windows**: nuevo `db_sync_service.py` — al arrancar en macOS, clona BD de PC Windows via pg_dump/psql |
| `5b67416` | **Tarifarios offline**: `_refresh_tariff_schools()` soporta modo offline extrayendo escuelas del cache local |
| `1396d8b` | **Fix**: tarifarios no cargaban escuelas al iniciar en modo offline (`_init_offline` no llamaba `_refresh_tariff_schools`) |
| `ebf9f23` | **Fix**: tarifario offline mostraba 1 solo producto — campo `nombre_base` → `producto_nombre_base` |
| `463a886` | **Tarifarios**: orden fijo de piezas con `_PIEZA_ORDER` — Pants 3pz, 2pz, Chamarra, Suelto, Playera, Suéter, Camisa... |
| `edf37d9` | **Rebranding**: fallback nombre negocio de "POS Uniformes" → "MAXIMODA" |
| `f4fb3cf`→`1e7e62d` | **Rename**: "Total estimado" → "Presupuesto estimado" solo en contexto presupuestos (apartados conservan "Total") |
| `bef1119` | **Fix**: tickets presupuesto — "TOTAL ESTIMADO:" → "PRESUPUESTO ESTIMADO:" en builders de texto |
| `39e837a` | **Tickets presupuesto**: ordenar piezas por `_tariff_product_sort_key(tipo_pieza)` |
| `c64fc97` | **Presupuesto guiado**: ordenar piezas con `_PIEZA_ORDER` dentro de cada grupo |
| `a1aabaf` | **Modelos sugeridos**: ordenar tarjetas de producto por `_tariff_product_sort_key` |
| `41423c9` | **Picker colores/tallas**: carga valores distintos de variantes activas en BD — colores y tallas custom persisten entre reinicios |
| `77d6b4a` | **Apartados — anular abono**: elimina último abono registrado, recalcula estado (LIQUIDADO→ACTIVO si aplica) |
| `77d6b4a` | **Apartados — editar apartado**: agregar, quitar o cambiar cantidad de productos en apartados activos; reserva/libera inventario |
| `77d6b4a` | **Apartados — servicios**: `anular_ultimo_abono()`, `agregar_detalle()`, `quitar_detalle()`, `cambiar_cantidad_detalle()`, `_recalcular_totales()` en apartado_service |
| `77d6b4a` | **Apartados — UI**: botones "Anular abono" y "Editar apartado" en pestaña, tooltips, action state helper actualizado |
| `9da2eb8` | **Reporte piezas por escuela**: HTML imprimible seccionado por nivel educativo (Preescolar/Primaria/Secundaria/Bachillerato) con navegación rápida |
| `9da2eb8` | **BD — Álvaro Obregón**: acento corregido, escuela duplicada (id 6) desactivada, productos de id 6 desactivados |

### Completado 2026-05-23

| Commit | Cambio |
|--------|--------|
| `cc21062` | **Inventario UX**: toolbar limpio, etiquetas con precio toggle, split optimizado, caja mejorada, QR masivo |
| `cc21062` | **Etiquetas — precio toggle**: checkbox "Mostrar precio" en todos los diálogos (individual, lote, satélite) |
| `cc21062` | **Etiquetas — uniformes**: override solo puede quitar precio, nunca forzar (profile.show_price AND show_price) |
| `cc21062` | **Etiquetas split**: QR 231→160px, gap 8→2px, texto pegado al QR sin centrado vertical |
| `cc21062` | **Caja**: diálogo HTML con pill estado + tiempo transcurrido, status label con colores |
| `cc21062` | **QR masivo**: BulkQrWorker (QThread) con progreso, cancelación, modo faltantes/regenerar |
| `cc21062` | **Meilisearch dialog**: rediseño cross-platform Windows/macOS |
| `cc21062` | **Fixes**: print_ → print (PyQt6), context menu etiqueta para todos los roles, orden refresh, warning QR sync |
| `2013cf5` | **Fix**: tickets térmicos con texto gigante (HighResolution → ScreenResolution) |
| `9091ee5` | **Fix**: ticket usa ancho real del printer |
| `381c653` | **Fix**: restaurar impresión tickets con QPainter + ScreenResolution (método probado) |
| `bf7f46e` | **Satélite**: botón ↻ Sync junto a Favoritos para re-indexar Meilisearch |
| `701780b` | **Fix**: tarifario — tallas MD, GD, EXG en _TALLA_ORDER para orden correcto y rangos completos |

### Completado 2026-05-22 → 2026-05-23 (committed)

| Commit | Cambio |
|--------|--------|
| `254db13` | **Carrito**: mostrar precio normal vs promo 3pz debajo del producto |
| `dea2b1d` | **Carrito**: precio original tachado Unicode (̶$̶1̶9̶9̶ → $100) cuando aplica promo 3pz |
| `4af6f36` | **Ticket venta**: mostrar precio normal vs promo cuando difieren |
| `1793e72` | **Ticket**: precio normal tachado + precio promo 3pz en línea separada |
| `3219cab` | **Fix**: alinear línea tachado en ticket compensando combining chars Unicode |
| `d44aaeb` | **Ticket**: línea promo simplificada a solo "promo 3pz" sin repetir cantidad/precio |
| `d44aaeb` | **Historial inventarios**: registro muestra `SKU \| Producto \| Talla` en vez de solo SKU |
| prev. commits | **Nombres producto cortos**: `build_ticket_product_name()` usa nombre_base + escuela (sin tipo prenda/pieza/Ad hoc) |
| prev. commits | **Box-drawing tickets**: estilo `┌─┐│└─┘╞═╡` aplicado a todos los tickets (venta, apartado, presupuesto) |
| prev. commits | **Tarifario por escuela**: nueva página en satélite — selector de escuela, vista previa, impresión |
| prev. commits | **Tarifario**: tallas compactas ("4 a 12"), leyenda pares, merge productos mismo precio |
| prev. commits | **DB constraints**: stock_actual y stock_posterior relajados de >= 0 a >= -1 |
| `a19654f` | **Productos virtuales** (stock_minimo=-1): excluir de alertas de inventario |
| `c2cd25a` | **Chamarra preescolar**: agregar talla 10 a tarifarios y guías rápidas |

### Completado sprint anterior (2026-05-19 → 2026-05-21)

| Commit | Cambio |
|--------|--------|
| `94ab06a`→`799c31b` | **Meilisearch en satélite catálogo**: búsqueda typo-tolerant pre-filtra + filtro local refina |
| `b4558b7` | **Meilisearch en catálogo POS**: misma estrategia pre-filtro + filtro local |
| `6c27540` | **Catálogo**: default combo a "Escuela + extras generales" |
| `d0e1cc8` | **Fix impresión volteada**: `ScreenResolution` + `Portrait` explícito + `QPainter` con `try/finally` |
| `f1ed421` | **Meilisearch LaunchAgent**: auto-arranque macOS + logging en indexación |
| `8032488` | **Cart popup rediseño**: resumen, cantidad editable +/−, agrupado por producto, acciones (Imprimir/WhatsApp/Guardar borrador) |
| `e946791`→`c051147` | **Cart popup fixes**: símbolos +/− visibles, fix crash al cerrar (`WA_DeleteOnClose` → `_post_action` pattern) |
| `a696842` | **Fix crash `_DoubleClickFrame`**: proteger `super().mouseDoubleClickEvent` con try/except RuntimeError |
| `593e10b` | **Cmd+S rediseño**: de 7 pasos guiados a buscador Meilisearch + tabla de resultados |
| `8a733ac` | **Cmd+S filtro local**: refina después de Meilisearch ("gales verde" → solo verde) |
| `112430e`→`aec4248` | **Auto-imprimir etiqueta**: al agregar desde Cmd+S, confirmación con checkboxes + Enter = imprimir |
| `86f5a0e` | **Meilisearch en inventario POS**: pre-filtra + filtros locales refinan |
| `faaf98f` | **Meilisearch en catálogo POS (tabla)**: pre-filtra + filtros locales refinan |
| `90b6f82` | **Presentación dialog mejorado**: 4 QGroupBox (Producto, Identificación, Precios, Stock), campos lado a lado |
| `df5bcc9` | **Meilisearch en bodega ingreso**: búsqueda + autocompletado predictivo |
| `e5f4e98` | **Bodega ingreso**: tabla no editable + Ctrl+P imprime etiqueta de fila seleccionada |
| prev. commits | **Bodega view fixes**: retirar producto usa `variante_id` de UserRole (no buscar por SKU), null checks en items tabla, botón "✕" cierra panel de búsqueda, limpiar detalle al deseleccionar caja |
| prev. commits | **Bodega ingreso fix doble-fire Enter**: flag `_completer_just_activated` + `QTimer.singleShot(0)` deferred clear |
| prev. commits | **Bodega ingreso fix filtro local**: `filtered or variantes` era demasiado permisivo — ahora muestra "No encontrado" si filtro vacío |
| prev. commits | **Bodega ingreso fix SKU vacío**: ignorar match de SKU vacío para evitar duplicados |
| prev. commits | **Bodega ingreso UX**: botón "Quitar fila" rojo, "∞" en Disponible/Restante cuando mercancía nueva |
| prev. commits | **Bodega service**: `joinedload` en historial_caja para prevenir N+1 queries |
| `6f3c611` | **Bodega etiqueta PDF**: genera PDF nativo (QPrinter) vertical carta con QR embebido, abre en Vista Previa sin popup |
| `6f3c611` | **Bodega tallas ordenadas**: `_size_sort_key` en desglose_contenido_caja y búsqueda agrupada |
| `6f3c611` | **Bodega ingreso autocomplete**: `UnfilteredPopupCompletion` — Meilisearch filtra, QCompleter muestra todo |
| `6f3c611` | **Fix crash satélite búsqueda**: limpiar `_selected_search_btn = None` antes de `deleteLater()` en resultados |
| `6f3c611` | **Catálogo producto tallas agrupadas**: `group_values_by_format=True` (Numéricas / Letras / Especiales) |
| `6f3c611` | **Catálogo producto valores custom**: `allow_custom=True` en pickers de tallas y colores — campo "+ Agregar" |
| — | **Normalización colores DB**: "Pgallo cafe" → "Pgallo Café", COMMON_COLORS "Cafe" → "Café" |

### Áreas con Meilisearch integrado

| Área | Archivo | Patrón |
|------|---------|--------|
| Satélite — catálogo | `quote_satellite_window.py` | Pre-filtro snapshot rows + filtro local + combos |
| Satélite — guiado | `quote_satellite_window.py` | Pre-filtro snapshot rows + filtro local |
| Cmd+S búsqueda rápida | `quick_product_search_dialog.py` | Meilisearch → local refinement, QCompleter predictivo |
| Inventario POS | `main_window.py` | Pre-filtro inventory_snapshot_rows |
| Catálogo POS | `main_window.py` | Pre-filtro catalog_snapshot_rows |
| Bodega — ingreso a caja | `bodega_ingreso_dialog.py` | Meilisearch → variante IDs → DB lookup, QCompleter |

### Patrón Meilisearch (consistente en todas las áreas)
```python
# 1. Meilisearch pre-filtra por relevancia
hits = meilisearch_service.search(query, limit=500)
hit_skus = {h["sku"] for h in hits}
source_rows = [r for r in all_rows if r["sku"] in hit_skus]

# 2. Filtro local refina con términos exactos
terms = query.lower().split()
for row in source_rows:
    searchable = " ".join([row["sku"], row["nombre"], ...]).lower()
    if all(t in searchable for t in terms):
        hits.append(row)

# 3. Fallback: si Meilisearch no disponible, solo filtro local
```

### Fixes importantes

| Bug | Causa raíz | Fix |
|-----|-----------|-----|
| Impresión volteada en primer print | `HighResolution` en térmicas reporta viewport incorrecto | `ScreenResolution` + `Portrait` explícito |
| Crash al cerrar cart popup | `WA_DeleteOnClose` destruía dialog mientras callbacks referenciaban widgets | `_post_action` pattern: almacenar acción → close → ejecutar después de `exec()` |
| Crash `_DoubleClickFrame` deleted | Double-click en sidebar abre popup → rebuilds sidebar destruyendo frame → `super()` falla | try/except RuntimeError |
| "gales verde" mostraba azul | Meilisearch retorna todos "gales" por relevancia, filtro local desactivado | Mantener filtro local activo después de pre-filtro Meilisearch |
| Tabla bodega ingreso editable | Sin `NoEditTriggers`, celdas de texto eran editables | Agregar `NoEditTriggers` |
| Bodega: doble-fire Enter al seleccionar del autocomplete | QCompleter emite `activated` + Enter propaga al eventFilter → `_handle_scan` x2 | Flag `_completer_just_activated` + `QTimer.singleShot(0)` deferred clear |
| Bodega: `filtered or variantes` mostraba productos incorrectos | Si filtro local no matcheaba nada, fallback devolvía TODOS los resultados crudos de Meilisearch | Mostrar "No encontrado" en vez de fallback |
| Bodega: retirar producto fallaba si SKU ambiguo | Buscaba por SKU en tabla en vez de usar ID | Guardar `variante_id` en UserRole, usar directo |
| Bodega: SKU vacío causaba duplicados | Match de SKU vacío (`""`) coincidía con cualquier variante sin SKU | Ignorar match si SKU es vacío |
| Bodega: N+1 queries en historial | `historial_caja` cargaba variante/producto con lazy loading fuera de sesión | `joinedload(BodegaMovimiento.variante).joinedload(Variante.producto)` |
| Satélite: crash al buscar después de imprimir | `_selected_search_btn` apunta a widget destruido por `deleteLater()` | `_selected_search_btn = None` antes de limpiar resultados |
| Bodega: "calceta verde" no encontraba en autocomplete | QCompleter con `MatchContains` re-filtra resultados de Meilisearch por substring continua | `UnfilteredPopupCompletion` — Meilisearch ya filtró |
| Colores duplicados "Cafe" / "Café" | COMMON_COLORS tenía "Cafe" sin acento, DB tenía "Café" | Corregir constante a "Café" |

### Archivos nuevos

| Archivo | Descripción |
|---------|-------------|
| `~/.local/share/LaunchAgents/com.danielfabian.meilisearch.plist` | LaunchAgent macOS para auto-arranque Meilisearch |
| `services/db_sync_service.py` | Sync remoto Windows DB → Mac local via pg_dump/psql |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `ui/quote_satellite_window.py` | Meilisearch en catálogo, cart popup, fix `_DoubleClickFrame`, tarifarios offline, _PIEZA_ORDER en tickets/guiado, Sync arranca servicio, MAXIMODA fallback |
| `ui/dialogs/quick_product_search_dialog.py` | Reescrito: Meilisearch + tabla (de 800 a 253 líneas) |
| `ui/dialogs/printable_text_dialog.py` | `ScreenResolution` + `Portrait` + `QPainter` con try/finally |
| `ui/dialogs/catalog_variant_dialog.py` | Layout con QGroupBox agrupados, campos lado a lado |
| `ui/dialogs/bodega_ingreso_dialog.py` | Meilisearch + QCompleter + NoEditTriggers + Ctrl+P etiqueta |
| `ui/main_window.py` | Meilisearch en inventario y catálogo, auto-print etiquetas desde Cmd+S, picker colores/tallas desde BD, "Presupuesto estimado", apartados: anular abono + editar apartado |
| `services/meilisearch_service.py` | Logging en indexación, sinónimos, stop words, typo tuning, separator tokens |
| `services/bodega_label_service.py` | PDF nativo con QPrinter, QR embebido, vertical carta, sin popup |
| `services/apartado_service.py` | Anular último abono, agregar/quitar/cambiar cantidad de detalles, recalcular totales |
| `services/layaway_closure_service.py` | Funciones high-level: `void_last_payment`, `add_layaway_item`, `remove_layaway_item`, `update_layaway_item_quantity` |
| `ui/helpers/layaway_action_helper.py` | Campos `void_payment_enabled` y `edit_enabled` en `LayawayActionState` |
| `ui/views/layaway_view.py` | Botones "Anular abono" y "Editar apartado" en layout de acciones |
| `services/bodega_service.py` | Tallas ordenadas con `_talla_sort_key` en desglose y búsqueda agrupada |
| `ui/dialogs/bodega_ingreso_dialog.py` | Fix doble-fire Enter, `UnfilteredPopupCompletion`, botón rojo "Quitar fila" |
| `ui/views/bodega_view.py` | Quitar popup "La etiqueta se abrió en el navegador" |
| `ui/quote_satellite_window.py` | Fix crash `_selected_search_btn` deleteLater |
| `ui/dialogs/catalog_product_dialog.py` | `group_values_by_format=True` + `allow_custom=True` en tallas y colores |
| `ui/main_window.py` | `MultiSelectPickerButton`: `allow_custom` con input "+ Agregar"; COMMON_COLORS "Cafe" → "Café" |
| `utils/qr_generator.py` | (sin cambios, ya existía `generate_for_caja`) |

---

---

## 2026-05-31

### ✅ Nomenclatura bodega + Kiosko rápido Ctrl+K + mejoras panel
**Commits:** `834266d` → `5706df0`

**1. Fix satélite — label print:**
- `quote_satellite_window.py` pasaba `cut_between_copies` (removido) en vez de `paper_mode`
- 3 ocurrencias: `_print_satellite_label` + 2 lambdas (offline y online)
- Commits: `759a88e`, `8393440`

**2. Nomenclatura de cajas de bodega:**
- Formato anterior: `A-001` (solo categoría + secuencia)
- Formato nuevo: `A-P1-001` (categoría + ubicación + secuencia)
  - P1=Piso N1, P2=Piso N2, A1=Almacén N1, XX=sin ubicación
- `_siguiente_codigo()` y `_abrev_ubicacion()` generan el nuevo formato
- `_regenerar_codigo()` actualiza código + QR en reclasificar y mover
- `reclasificar_caja()` y `mover_caja()` regeneran código automáticamente
- Script `migrar_codigos_bodega.py` (idempotente) migra cajas existentes + crea ALMACEN-N1
- ALMACEN-N1 creada en ambas BDs (Mac y Windows)
- Preview de nueva caja actualiza al cambiar ubicación O categoría
- Commit: `b941760`, `caa93af`

**3. Botón Copiar pedido (clipboard):**
- Nuevo botón "📋 Copiar" en barra flotante de Disponibilidad
- `build_pedido_texto()` genera formato WhatsApp con emojis por escuela
- Bridge: `copiarPedido(json)` → `QApplication.clipboard().setText()`
- Commit: `834266d`

**4. Panel en modo claro por defecto:**
- Eliminado `prefers-color-scheme: dark` como fallback — siempre arranca en `light`
- Botón de tema sigue disponible; preferencia manual en localStorage
- Commit: `834266d`

**5. Consulta rápida de precios (Ctrl+K):**
- Nuevo `QuickKioskDialog` — ventana ligera no-modal, siempre al frente
- Escanea SKU → muestra escuela, producto, talla, color y precio (sin stock)
- Tabla de consultas recientes (últimas 20)
- Registrado en POS (`main_window.py`) y satélite (`quote_satellite_window.py`)
- Event filter global en `QApplication` — funciona desde cualquier diálogo modal
- `WindowStaysOnTopHint` para mantenerse al frente
- Archivo: `ui/dialogs/quick_kiosk_dialog.py`
- Commits: `b6ac94f` → `5706df0`

---

## 2026-05-30

### ✅ Conteo de basicos + pedido desde disponibilidad + fix salud inventario
**Commits:** `0e1a2d6`, `834266d`

**1. Fix tarjeta "Salud del inventario" (Resumen):**
- Usaba `stock_actual = 0` → ahora usa `stock_tienda <= 0` (alineado con Disponibilidad)
- Contaba TODAS las variantes activas (4,792) → ahora solo las vinculadas a escuela (3,115)
- Fix redondeo: ultimo segmento = `100 - sum(otros)` (siempre suman 100%)

**2. Conteo de Productos Basicos:**
- Nueva opcion "📦 Productos Basicos" en el selector de escuela del modulo Conteo
- Segundo dropdown de tipo de pieza (Pants, Playera, etc.) que filtra tarjetas y hojas
- 681 variantes / 56 productos / 54 hojas de conteo
- Funciones: `obtener_variantes_basicos_para_conteo()`, `build_conteo_sheets_basicos(tipo_pieza)`
- JS: `_conteoParseSelection()` maneja `isBasicos`, salta estado/config/pendientes

**3. Carrito de pedido en Disponibilidad:**
- Click en talla para agregar al carrito (check marron con outline)
- Barra flotante sticky: "🛒 N tallas · M productos" + Limpiar + Imprimir
- Hojas termicas agrupadas por escuela, con columnas Talla / Stock / Pedir
- Boton "📋 Copiar": genera texto con emojis para WhatsApp → clipboard
- Nuevo servicio: `services/pedido_sheet_service.py` (`build_pedido_sheets` + `build_pedido_texto`)
- Bridge: `imprimirPedido(json)` + `copiarPedido(json)`

**4. Panel en modo claro por defecto:**
- Eliminado `prefers-color-scheme: dark` como fallback — siempre arranca en `light`
- Boton de tema sigue disponible; la preferencia manual se guarda en localStorage

---

### ✅ Hojas de conteo con nivel + modo Label DK-1221 + revisión de bugs de conteo
**Commits:** `71c03f0` → `2f1f376`

**1. Hojas de conteo (impresora térmica):**
- Header ahora muestra **nivel educativo** y posición de escuela (ej. `(3/25)` = escuela 3 de 25 del mismo nivel)
- `build_conteo_sheets()` acepta `nivel_nombre` y `escuela_num`; el JS calcula la posición desde el `<option data-nivel>`

**2. Nuevo modo de impresión "Label" — DK-1221 (23×23 mm die-cut):**
- Etiqueta cuadrada con QR + **nombre del producto** (no el SKU)
- Camino final: `brother_ql` genera el raster nativo (incluye autocut) → **spooler de Windows en modo RAW**. Evita GDI/DEVMODE (frágil con Brother) y no necesita libusb.
- Descartado antes: win32print con paper ID (no aplicaba el tamaño por usar `SetPrinter` nivel 8 + `CreatePrinterDC`) y pyusb (falta libusb en Windows)
- **Lección:** el error final "el rollo no coincide" era **físico** — había que cargar bien el rollo DK-1221 (23 mm) para que el sensor lo detectara. Detalle en [[22 - Referencia Rápida]]

**3. Revisión exhaustiva del módulo de conteo (1 crítico + 2 medios + 3 menores):**
- 🔴 **CRÍTICO** — el conteo medía la diferencia contra `stock_actual` (total) en vez de `stock_tienda`; al confirmar ajustes **destruía el inventario de bodega**. Regresión del 27-may perdida en un revert. Fix + 6 tests (`test_conteo_service.py`).
- 🟠 Conteos pendientes envenenados → script `scripts/revisar_conteos_pendientes.py`
- 🟠 `"ADMIN"` hardcodeado como autor del ajuste → usa usuario logueado
- 🟡 Badge/pendientes ignoraban el nivel → `obtener_conteos_pendientes(nivel_id)` + bridge `(eid, nid)`
- 🟡 Ajuste negativo reventaba el lote completo → se omite ese conteo
- 🟡 Entrada inválida se guardaba como 0 → valida e ignora
- **Bonus:** arreglados 3 tests de etiquetas pre-existentes (mocks sin `show_price`); uno colgaba la suite entera

**Detalle completo:** [[25 - Panel de Uniformes]] · deuda de tests en [[19 - Deuda Técnica]]

**4. Reconciliación de catálogo Mac ↔ Windows (192.168.0.10):**
Comparación directa de ambas BD (psycopg a las dos en paralelo). El catálogo maestro
estaba idéntico (48 escuelas, 548 productos, 4820 variantes, 5710 assets), pero
divergían **links** y **precios**. Stock NO se tocó (Windows = fuente de verdad operacional).

- **Links (3):** Pants Suelto Liso/Punto Rojo estaban en José María Morelos (16) en Windows
  pero en Justo Sierra (17) en Mac → corregido a **Justo Sierra** en Windows (validado por
  obs 540). Camisa olan Blanca → agregada a **Club Rotario** en Windows. Ahora 136 = 136.
- **Precios/activo (64 variantes):**
  - **UVEG Playera Polo** → $259 a **$239** en Windows (Mac era correcto)
  - **Sor Juana** Pants 2pz/3pz → Windows ($415/$515) correcto, bajado en Mac
  - **Chalecos, Suéteres, Pants Adolfo López** → Windows correcto (precios actualizados en
    tienda); alineados en Mac. Cotejado con escaleras de `product_templates.py`:
    Pants Adolfo López Windows ($485/$585) coincide con la escalera vigente
  - **2 variantes** (Pants 2pz Deportivo T4, Francisco Villa + Himno Nacional) → desactivadas
    en Mac (Windows ya las tenía inactivas)
- **Verificado:** 0 diferencias de catálogo (links + precio + activo) entre ambas BD.
- **Backups:** `/tmp/backup_links_windows_20260530.csv`, `/tmp/backup_precios_20260530.csv`
- **Método de comparación** (reutilizable): `psycopg.connect` a `localhost` y `192.168.0.10`,
  comparar conteos por tabla y luego contenido por SKU/clave. Útil para auditar divergencias.

> ⚠️ Hallazgo: las escaleras de precio en `product_templates.py` (Chaleco 239/259/269,
> Suéter T40-42=315) están **desactualizadas** vs los precios reales de la tienda. Solo
> sirven de plantilla inicial, no de referencia de precios vigentes.

**Pendiente en Windows:**
- `git pull` + reiniciar app (toma el código nuevo y el precio actualizado de UVEG)
- Regenerar el panel (se hace solo al abrirlo) para que tarifarios reflejen los precios
- Correr `scripts/revisar_conteos_pendientes.py` (reporte → `--descartar` si lista alguno)

---

## 2026-05-22

### ✅ Normalización de catálogo deportivo + plantillas de presentación
**Commits:** `a4f490f` → `4dc166c`

**Cambios en DB (aplicados en local y Windows `192.168.0.10`):**
- 136 productos → género `Unisex` (playeras, pants 2pz/3pz, pants suelto deportivo/básico que tenían NULL)
- Corrección typo: "Vidal Acolcer" → "Vidal Alcocer" (1 escuela + 2 productos + nombre_base)
- 6 productos Pants 3pz creados (Alvaro Obregon ×2, ESTV 663, Narciso Mendoza, Santa Rosa 238, Vidal Alcocer) + 37 variantes (precio = Pants 2pz + $100)
- 11 chamarras deportivas creadas (10 escuelas) + 85 variantes (precio flat por nivel: $315 preesc, $335 prim, $385 sec)
- Palacio: Playera deportiva + Pants 3pz creados + 20 variantes

**Cambios en código:**
- `product_templates.py`: PRESENTATION_STEP_TEMPLATES expandido de 14 a 38 entradas con precios reales de la DB
- `product_templates.py`: `suggest_presentation_template()` reescrito para labels por pieza (secundaria/bachillerato desglosados)
- `product_templates.py`: BASE_STEP_TEMPLATES — `gender: "Unisex"` en 8 plantillas (4 deportivas + 4 pants básicos)
- Eliminado sistema legacy de plantillas (`load_legacy_product_templates`, `_OMIT_LABELS`)
- `apply_selected_template()` cambia a modo "Ropa Normal" al aplicar plantilla global

**Commits detallados:**
- `a4f490f` — Catálogo: 3 bug fixes en diálogo + plantillas alineadas con datos reales
- `fd78725` — Quitar plantillas legacy de plantillas_productos.json
- `e865ff8` — Plantilla global cambia modo a Ropa Normal al aplicar
- `0786abd` — Plantillas de presentación con precios pre-llenados por escalera
- `30757c5` — Plantillas presentación: 38 entradas con precios reales + suggest actualizado
- `4dc166c` — Plantillas base: género Unisex en deportivos y pants básicos

**Pendiente:**
- Pants suelto deportivo falta en 26 escuelas (dejado para después)
- git push + git pull en Windows del código

---

## 2026-05-21 / 2026-05-22

### ✅ UX Bodega + Catálogo — mejoras y fixes
**Commit:** `6f3c611`

Commit consolidado con mejoras de UX pendientes del sprint Meilisearch/Bodega.

**Cambios:**
- Etiqueta de caja: migrar de HTML/browser a PDF nativo (QPrinter + QrGenerator), vertical carta, se abre en Vista Previa sin popup
- MultiSelectPickerButton: nuevo parámetro `allow_custom` con campo "+ Agregar" para valores nuevos
- Catálogo producto: tallas agrupadas por formato (Numéricas/Letras/Especiales) con `group_values_by_format`
- Catálogo producto: `allow_custom=True` en pickers de tallas y colores
- Bodega ingreso: `UnfilteredPopupCompletion` para que Meilisearch filtre, no el QCompleter
- Bodega service: ordenar tallas con `_talla_sort_key` (orden natural) en desglose y búsqueda agrupada
- Satélite: fix crash `_selected_search_btn` en widget destruido por `deleteLater()`

### ✅ Admin satélite — diagnóstico Meilisearch multiplataforma
**Commit:** `1ba92b7`

### ✅ Deploy parcial a Windows
- `git pull origin main` hasta `1ba92b7` exitoso
- Falta pull de `6f3c611` y build de satélite (spec file path por resolver)

**Estado al cerrar:**
```
Rama:   main
HEAD:   6f3c611
Origin: pushed ✅ 2026-05-22
Pendiente: git pull 6f3c611 en Windows, build satélite, instalar Meilisearch en Windows
```

---

## 2026-05-19 / 2026-05-20

### ✅ Meilisearch — Búsqueda typo-tolerant integrada en todo el POS
**Commits:** `94ab06a` → `e5f4e98`

Motor de búsqueda tolerante a errores de escritura integrado en 6 áreas del sistema. Patrón consistente: Meilisearch pre-filtra por relevancia (limit=500), luego filtro local refina con términos exactos y combos activos. Fallback automático a búsqueda local si Meilisearch no está disponible.

**Áreas integradas:**
- Satélite catálogo y presupuesto guiado (`quote_satellite_window.py`)
- Búsqueda rápida Cmd+S (`quick_product_search_dialog.py`) — reescrito de 7 pasos guiados a buscador + tabla
- Inventario POS (`main_window.py`)
- Catálogo POS (`main_window.py`)
- Bodega ingreso a caja (`bodega_ingreso_dialog.py`) — con QCompleter predictivo

**Infraestructura:**
- LaunchAgent macOS (`com.danielfabian.meilisearch`) con `KeepAlive=true` para auto-arranque
- `meilisearch_service.py`: `search()`, `search_as_families()`, `is_available()`, `index_from_db()`
- Indexa variantes activas con: SKU, nombre, talla, color, escuela, tipo pieza/prenda, marca, categoría

### ✅ Cmd+S — Rediseño completo de búsqueda rápida
**Commits:** `593e10b` → `aec4248`

- De 7 pasos guiados a un buscador simple con tabla de resultados
- Meilisearch + filtro local refinado (ej. "gales verde" → solo verde)
- QCompleter con sugerencias predictivas
- Al cerrar, ofrece imprimir etiquetas de productos agregados (checkboxes + Enter = imprimir)

### ✅ Cart popup ("Piezas agregadas") — Rediseño completo
**Commits:** `8032488` → `a696842`

- Resumen con total de piezas y monto
- Tabla agrupada con cantidad editable +/− inline
- Botones de acción: Imprimir ticket, WhatsApp, Guardar borrador, Cerrar
- Fix crash al cerrar: patrón `_post_action` (almacenar acción → close → ejecutar después de `exec()`)
- Fix crash `_DoubleClickFrame`: try/except RuntimeError al acceder a widget destruido

### ✅ Fix impresión volteada en primer print
**Commit:** `d0e1cc8`

- `QPrinter.HighResolution` en térmicas reporta viewport incorrecto → primera impresión rotada
- Fix: `ScreenResolution` + `QPageLayout.Orientation.Portrait` explícito
- `QPainter` protegido con `painter.begin()` / `try/finally painter.end()` (previene crash raro al cerrar)

### ✅ Presentación dialog — Layout visual mejorado
**Commit:** `90b6f82`

- QFormLayout plano → 4 QGroupBox (Producto, Identificación, Precios, Stock)
- Talla/Color lado a lado, Precio venta/Costo ref. lado a lado
- Estilos consistentes con el resto del POS

### ✅ Bodega ingreso — Meilisearch + mejoras UX
**Commits:** `df5bcc9` → `e5f4e98`

- Búsqueda Meilisearch con filtro local refinado + QCompleter predictivo
- Tabla no editable (solo spin de cantidad es editable)
- Ctrl+P imprime etiqueta de la fila seleccionada

**Estado al cerrar:**
```
Rama:   main
HEAD:   e5f4e98
Origin: pendiente push
Pendiente: git pull en PC Windows, instalar Meilisearch en Windows, reempaquetar bundle satélite
```

---

## 2026-05-17 / 2026-05-18

### ✅ Módulo Bodega (mini-WMS) — diseño e implementación completa
**Commits:** `bc94cc8` → `ab83132`

Módulo de gestión física de inventario integrado con el POS existente. Permite saber exactamente en qué caja y rack está cada talla, sin duplicar ni romper el inventario global.

**Diseño:**
- `stock_actual` sigue siendo el total global (no se toca)
- `stock_en_tienda = stock_actual - sum(bodega_contenido)`
- Sin SKUs nuevos: bodega referencia `variante_id` directamente
- Log append-only de movimientos para auditoría

**Schema (migración `a1b3c5d7e9f0`):**
- `bodega_ubicacion` — rack + nivel (ej. "A1-N2"), campo activo
- `bodega_caja` — caja con código único, FK ubicación, estado ACTIVA/VACIA/CERRADA
- `bodega_contenido` — variante en caja con cantidad, UNIQUE(caja, variante)
- `bodega_movimiento` — log: INGRESO, RETIRO, TRANSFERENCIA, MOVER_CAJA, CREAR_CAJA, AJUSTE

**Service layer (`bodega_service.py`):**
- Ubicaciones: crear, listar, desactivar
- Cajas: crear, mover, cambiar estado, listar con filtros, detalle
- Contenido: ingresar (con validación stock), retirar, transferir entre cajas, ingreso masivo
- Búsqueda: por variante, por texto (nombre/SKU/código caja)
- Historial: por caja, totales
- QR: generación por caja

**UI PyQt6:**
- `bodega_view.py` — vista con splitter: lista de cajas + filtros (izq), detalle con contenido e historial (der)
- `bodega_ingreso_dialog.py` — ingreso masivo con matriz de tallas: buscar producto → SpinBox por variante → max = stock disponible
- `bodega_ubicaciones_dialog.py` — CRUD simple de racks y niveles
- Tab "Bodega" agregado en MainWindow entre Inventario e Historial

**Tests:** 15 unit tests con SQLite in-memory en `test_bodega_service.py`

### ✅ Fix — catálogo e inventario vacíos después de restaurar DB
**Commit:** `7b224f4`

- `build_analytics_operational_alerts` restaba `datetime.now(tz=utc)` (aware) menos `backup_status.last_success_at` (naive, leído del JSON de estado de backup)
- La excepción `TypeError: can't subtract offset-naive and offset-aware datetimes` era capturada por el catch-all de `refresh_all`, causando un `return` antes de ejecutar `_refresh_catalog` y `_refresh_inventory`
- Fix: normalizar naive→aware antes de restar en `analytics_summary_helper.py` y `settings_backup_helper.py`
- `backup_service.py` ahora escribe timestamps con `timezone.utc`

### ✅ Fix — migración Alembic "multiple heads"
**Commit:** `2a41405`

- `down_revision` de la migración bodega apuntaba a `f7c9e12ab430` (mitad de cadena) en vez de `b3c4d5e6f7a8` (head real)
- Causaba error "multiple heads" al hacer `alembic upgrade head`

### ✅ Fix — botón "Siguiente" en inventario no funcionaba con item seleccionado
**Commit:** `ab83132`

- `_refresh_inventory_table` veía `inventory_variant_combo.currentData()` != None y forzaba `page_index` de vuelta a la página del item seleccionado
- Fix: los handlers de paginación (Anterior/Siguiente) limpian el combo antes de refrescar

### Deploy a Windows
- `git pull` + `alembic upgrade head` exitoso en PC Windows
- DB restaurada desde dump `pos_uniformes_20260515_174509.dump` (tuvo que dropear tablas bodega primero por FK dependencies, luego re-aplicar migración)
- App abre correctamente mostrando pestaña Bodega

**Estado al cerrar:**
```
Rama:   main
HEAD:   ab83132
Origin: pendiente push
Pendiente: validar bodega en producción, reempaquetar bundle satélite
```

---

## 2026-05-01

### ✅ Satélite — Buscar y Compartir funcionan en modo offline
**Commits:** `ec4de99`

- `_refresh_offline_quotes()` — pobla `quote_table` desde `offline_quotes.json`; estado "LOCAL", folio como UserRole
- `_refresh_offline_quote_detail(folio)` — carga detalle del presupuesto local y actualiza paneles Buscar y Compartir
- `_handle_quote_selection()` — en offline ruta a `_refresh_offline_quote_detail` en lugar de DB
- `_apply_action_state()` — en offline habilita Imprimir y WhatsApp para el presupuesto local seleccionado; deshabilita Reanudar/Emitir/Cancelar
- `_handle_print_quote()` y `_handle_open_quote_whatsapp()` — en offline leen `_offline_selected_quote` directamente
- `_selected_quote_id()` — ya no falla con folios string; `_selected_offline_folio()` nuevo helper
- Botones nav Buscar y Compartir habilitados en modo local con tooltip descriptivo

### ✅ Fix — impresora del satélite ignoraba el menú admin si había conexión con DB
**Commit:** `ec4de99`

- `printable_text_dialog._load_print_preferences()` leía la DB primero y sobreescribía el cache local
- Fix: cache local (`ticket_print_settings.json`) tiene prioridad siempre; la DB es fallback solo si el cache está vacío
- Resultado: lo que se guarda en `Ctrl+Shift+A` → impresora persiste en todos los contextos

### ✅ Ticket — talla por producto
**Commits:** `b43ca53` (satélite) · `99b7279` (POS principal)

- `_build_snapshot_ticket_text`, `_build_cart_ticket_text`, `_build_offline_whatsapp_message` — añaden `Talla: X` debajo del nombre si la talla existe y no es `-`
- `quote_text_service.py` (POS principal) — mismo cambio usando `detail.talla_snapshot`

### ✅ Ticket — leyenda de no comprobante fiscal
**Commit:** `ec74358`

- Bloque centrado en el encabezado de todos los tickets:
  ```
  ESTE NO ES UN COMPROBANTE
     FISCAL NI DE COMPRA
   Precios solo de referencia
  ```
- Aplica en `quote_text_service.py`, `_build_snapshot_ticket_text` y `_build_cart_ticket_text`

### ✅ Ticket — términos y condiciones corregidos
**Commits:** `779288f` · `4e05fcd` · `ab52785` · `106f70c`

- Oraciones almacenadas completas en `DEFAULT_QUOTE_TERMS_LINES`; `textwrap.wrap` hace el corte — elimina fragmentos sueltos como "contraria." o "indicacion" solos
- "Los precios no aseguran" → "Este ticket no asegura"
- Promoción actualizada: "recibiran un descuento **al registrarse en Maximoda**"
- Nueva promoción: sistema de apartado con 25% del valor total
- Eliminado emoji `:)` del texto

**Estado al cerrar:**
```
Rama:   main
HEAD:   106f70c
Origin: sincronizado ✓
Pendiente: reempaquetar bundle en PC Windows con los cambios de hoy
```

---

## 2026-04-29 (sesión tarde)

### ✅ Bug: impresión de etiquetas crasheaba en satélite
**Commit:** `c44bba3`

- `_open_label_dialog_for_row` — los dos lambdas de `print_label` solo aceptaban 4 args pero `build_inventory_label_dialog` pasa 5 (`image_path, copies, sku, parent, mode`)
- Fix: lambdas ahora aceptan `mode` y lo convierten a `cut_between_copies=(mode == "continuous")`
- `_print_satellite_label` recibe y pasa `cut_between_copies` al helper de Windows

### ✅ Bug: ligas producto-escuela ignoraban escuelas con nombre duplicado (Praxedis Guerrero)
**Commit:** `c44bba3`

- `_inject_linked_products` usaba `escuela_nombre` como clave → dos escuelas con el mismo nombre se mezclaban
- Fix: ahora usa `escuela_id` como clave en `links_by_id`, `id_to_nivel` y `already_in_school`
- Los rows sintéticos también reciben `escuela_id` correcto
- `school_product_link_dialog`: muestra `"Nombre (id N)"` cuando hay duplicados de nombre
- Tests actualizados: `_row()` incluye `escuela_id`; los 3 tests de ligas incluyen `escuela_id` en `school_links`

### ✅ Nuevo: botón "Imprimir" en carrito (funciona offline)
**Commit:** `c44bba3`

- `quote_print_cart_button` → `_handle_print_cart` — imprime el carrito actual sin guardar en DB
- `_build_cart_ticket_text` — genera texto estilo ticket (mismo ancho 38 chars, mismos términos y condiciones)
- Funciona online y offline — no requiere que la PC principal esté encendida

### ✅ Fix: encoding de `setup_satelite.ps1`
**Commit:** `c44bba3`

- Em dashes `—` reemplazados por guiones ASCII `-`
- Archivo guardado con BOM UTF-8 — PowerShell en Windows lo lee correctamente

### ✅ Mac — entorno de desarrollo local sin depender del Windows
- DB volcada desde Windows (4228 variantes) y restaurada en `localhost:5432`
- `.env` apunta a `localhost` para trabajar en casa
- Al volver a la tienda: cambiar `.env` a `192.168.0.10`

### ✅ Bug (sesión anterior): impresión de etiquetas en modo offline colgaba 30s
**Commits:** `01a590b`

- `_print_satellite_label` consultaba `preferred_printer` a la DB aunque estuviera en modo offline
- Fix: query envuelto en `if not self.offline_mode`
- `connect_args={"connect_timeout": 5}` en el engine para cortar pérdidas de conexión en 5s

**Estado al cerrar:**
```
Rama:   main
HEAD:   c44bba3
Origin: sincronizado ✓
Bundle: PresupuestosSatelite-2026.04.24 generado en Windows, listo para instalar en satélite
```

---

## 2026-04-29 (sesión mañana)

### ✅ Tickets de venta — rediseño y talla en detalle
**Commits:** `86c62eb` → `06256da` (9 commits)

- Rediseño de ticket: texto plano con separadores, negritas y precios alineados a la derecha
- Talla incluida en la línea de detalle del artículo (color descartado tras prueba)
- Ancho reducido de 42 → 38 chars para evitar corte derecho en papel de 80mm
- Satélite: mismo estilo que ticket de venta
- `QPainter.drawContents()` reemplaza `doc.print_()` para compatibilidad Windows

### ✅ Conteo físico — scroll area
**Commit:** `46d5199`
- `QScrollArea` alrededor del contenido del diálogo — el diálogo ya no se corta en pantallas pequeñas

### ✅ Modo "Continua" en impresión de etiquetas
**Commits:** `ba9e4a6` → `fd4e32a` (9 commits)

- `LabelGenerator._render_continuous()` — QR 200px centrado + texto debajo, altura dinámica según contenido
- `_normalize_mode()` mapea "continuous" como tercer modo canónico
- Opción "Continua" en `inventory_label_batch_dialog.py` e `inventory_label_dialog.py`
- `print_inventory_label_via_windows`: `cut_between_copies=True` envía cada copia como job independiente (garantiza corte automático)
- `_build_continuous_devmode`, `_find_continuous_roll_paper_id`, `_query_printer_dpi` — intento de configurar DEVMODE para rollo continuo Brother QL-800
- **Pendiente sin resolver:** espacio en blanco de ~9cm en la impresora — driver Brother ignora el cambio de `PaperLength` programáticamente vía DEVMODE + SetPrinter nivel 8. Requiere configurar el driver manualmente o investigar protocolo raster Brother.

### ✅ Modo "Agregar mercancía" en conteo físico
**Commits:** `2e05925` → `f12da54` (5 commits)

**Servicio (`inventory_count_service.py`):**
- `accumulate_inventory_count_scan` recibe `add_to_system: bool = False`
- En modo add: la primera lectura arranca desde `stock_actual + 1` (no desde 0)
- Las siguientes lecturas siguen acumulando sobre el contado

**Diálogo (`inventory_count_dialog.py`):**
- Card de modo con `QRadioButton` + `QButtonGroup` (Conteo físico / Agregar mercancía)
- `_handle_mode_changed` pide confirmación y limpia la tabla si hay datos capturados; usa `blockSignals` para revertir el radio sin loop
- `eventFilter` bloquea scroll de ratón en todos los `QSpinBox` del diálogo
- `counted_spin.setMinimum(stock_sistema)` en modo Agregar — no puede bajar del sistema
- "Restar 1" respeta `stock_sistema` como piso en modo Agregar
- Spinboxes de la tabla: `minimum = stock_sistema` al crearse en modo Agregar
- Mensaje de estado y diálogo de confirmación muestran el modo activo

**Tests (`test_inventory_count_service.py`):**
- `test_accumulate_inventory_count_scan_add_to_system_starts_from_system_stock`
- `test_accumulate_inventory_count_scan_add_to_system_continues_accumulating`

**Estado al cerrar:**
```
Rama:   main
HEAD:   f12da54
Origin: sincronizado ✓
Commits esta sesión: 27 (b0df74c → f12da54)
```

---

## 2026-04-23

### ✅ Consolidación 1 — `_normalize_text` en `utils/text_normalization.py`
Dos variantes duplicadas de `_normalize_text` (simple y NFKD) extraídas a módulo compartido.
- `normalize_text()` — lowercase + strip, None-safe
- `normalize_text_unicode()` — NFKD, elimina diacríticos
- 5 archivos actualizados: `catalog_filter_helper.py`, `inventory_filter_helper.py`, `catalog_product_form_mode_helper.py`, `quote_guided_catalog_helper.py`, `sale_sports_uniform_helper.py`

### ✅ Consolidación 2 — `resolve_selected_settings_row_id` genérico
3 funciones idénticas de resolución de ID en `settings_crm_selection_helper.py` colapsadas a 1 genérica. Las 3 específicas quedan como thin wrappers para compatibilidad.

### ✅ Consolidación 3 — `resolve_stock_tone` en `utils/stock_tone_helper.py`
Umbral `_LOW_STOCK_THRESHOLD = 3` y lógica de semáforo en un solo lugar.
- `resolve_stock_tone(stock, stock_minimo=None)` — danger/warning/positive
- `resolve_row_tone_from_stock(stock)` — danger/warning/None para row_tone
- 4 archivos actualizados: `catalog_table_row_helper.py`, `inventory_table_row_helper.py`, `analytics_stock_helper.py`, `inventory_overview_helper.py`

### ✅ Fix mypy — 6 errores estructurales reales
Corridos `mypy` sobre el source (exc. tests y venv): 687 errores totales, ~500 ruido de `dict[str, object]`. Los 6 errores estructurales corregidos:
- `dashboard_summary_helper.py` — tuple de longitud variable anotada como `tuple[str, ...]`
- `product_templates.py:395` — `.get()` sobre `object` con `isinstance` guard
- `analytics_payment_helper.py` — `sales: list[Any]` en lugar de `list[object]`
- `inventory_table_row_helper.py` — `_format_ultimo_conteo` recibe `datetime | None` con cast en caller
- `scanned_client_flow_service.py` — `int(str(current_client_id))` para evitar `int(None)`
- `config.py` — `getenv` default con `str(... or "")` en lugar de `None`

### ✅ Presupuestos — VENCIDO como estado visual
- `quote_history_helper.py` detecta EMITIDO con vigencia pasada → muestra "VENCIDO" (tono danger)
- Filtro por estado agrega opción "Vencidos" en POS principal y satélite
- `QuoteSnapshotRow` lleva nuevo campo `vigencia_hasta_raw: datetime | None`
- El filtro "EMITIDO" excluye vencidos (filtro aplica sobre estado display, no DB)
- 3 nuevos tests en `test_quote_history_helper.py`

### ✅ Presupuestos — cliente solo por QR
- `quote_client_combo` deshabilitado (solo display), etiqueta cambia a "Cliente (QR)"
- Botón "Nuevo cliente" conservado para creación rápida
- Señal del combo manual eliminada — asignación solo vía escaneo QR
- Aplica en POS principal (`quotes_view.py`) y satélite (`quote_satellite_window.py`)

### ✅ Migración Alembic aplicada en Mac
- `alembic upgrade heads` corrida localmente para sincronizar `a3c7e9f1b204`

### ✅ Bug 1 — Rechazar emitir presupuesto con vigencia vencida
- `presupuesto_service.emitir_presupuesto()` valida `vigencia_hasta < now()` antes de cambiar estado
- Lanzar `ValueError` con mensaje claro
- 4 tests en `test_presupuesto_service.py`: sin vigencia, futura, vencida, mensaje

### ✅ Bug 1b — Mismo fix en `_apply_quote_payload` (todos los caminos)
- `crear_presupuesto` y `actualizar_presupuesto` llamaban `_apply_quote_payload` sin validar vigencia
- El check ahora vive en el método base, cubriendo el editor del satélite también
- **Commit:** `5b3efb4`

### ✅ Bug 3 — Flujo CONVERTIDO implementado
Estado existía en el modelo pero era inalcanzable desde la UI.

- `presupuesto_service.convertir_presupuesto()` — valida EMITIDO → CONVERTIDO + `convertido_at`
- `quote_action_service.convert_quote_to_cart()` — marca CONVERTIDO, devuelve items para carrito
- `QuoteActionState.convert_enabled` — activo solo en EMITIDO
- Botón "Cobrar presupuesto" en panel de presupuestos del POS principal
  - Avisa si el carrito ya tiene items (confirmación reemplazar)
  - Carga items al `sale_cart`, navega al tab Caja (índice 1)
- 4 tests: `convert_enabled` por estado, items del carrito, quote not found
- **Commits:** `21270da`, `64342ec`, `5b3efb4`

**Estado al cerrar:**
```
Rama:   main
HEAD:   5b3efb4
Tests:  32 tests de presupuestos pasando
Commits nuevos desde sesión anterior: 66749aa, 6d9aaba, 64342ec, 21270da, 5b3efb4
```

---

## 2026-04-22

### ✅ Fix migración — DuplicateTable en `a3c7e9f1b204`
**Commit:** `1ce745e`

Al hacer `git pull` en Windows, Alembic fallaba porque dos migraciones partían del mismo padre (dos heads). La migración `a3c7e9f1b204` ya creaba el índice con `add_column(index=True)` y el `create_index` explícito posterior tiraba `DuplicateTable`.

- Fix: `if_not_exists=True` en los tres `op.create_index` de `a3c7e9f1b204_add_seller_employee_id.py`
- Comando correcto para múltiples heads: `python -m alembic upgrade heads` (plural)

### ✅ Fix impresión ticket 80mm — EC-PM-80320
**Commits:** `b7208cd` → `375ce7b` → `8113ce3` → `8cfe9bd` → `1a2be9c` → `8f6ec1b` → `52178ae`

El texto del ticket salía en una franja angosta porque el código estaba configurado para 58mm y `QTextDocument` usaba coordenadas de pantalla (96 DPI) en lugar de las del driver.

**Solución final** — `QPainter.drawText()` con `painter.viewport()`:
- `painter.viewport()` devuelve el rect imprimible en coordenadas nativas del driver → word-wrap al ancho físico real
- Archivos: `printable_text_dialog.py`, `ticket_print_layout_helper.py` (`TICKET_PAPER_WIDTH_MM = 80`), `quote_text_service.py`

**Estado al cerrar:**
```
Rama:   claude/review-pos-uniforme-hr1JL
HEAD:   8682b1d (docs: checkpoints 2026-04-22)
```

---

## 2026-04-21

### ✅ Filtros de precio en inventario
- Combo "Precio" con rangos: <$100 / $100-199 / $200-499 / $500+
- Input "$ exacto" en la barra de búsqueda (±$0.005 de tolerancia)
- Nuevos campos en `InventoryVisibleFilterState`: `precio_filter`, `precio_text_filter`
- Archivos: `inventory_filter_helper.py`, `inventory_view.py`, `main_window.py`
- Tests actualizados en `test_inventory_filter_helper.py`

### ✅ Duplicar presentación
- Nuevo ítem en menú Nuevo → "Duplicar presentación"
- Precarga producto (bloqueado), color, precio y costo de la variante origen
- SKU autoasignado según la nueva talla elegida (campo de solo lectura)
- Archivos: `catalog_variant_dialog.py` (param `prefill`), `inventory_view.py`, `main_window.py`

### ✅ Auditoría completa pestaña Inventario — 11 riesgos, todos resueltos

| Riesgo | Severidad | Fix |
|--------|-----------|-----|
| 1 | Alta | `_selected_catalog_row` no cae a catalog_table cuando hay selección de inventario activa |
| 2 | Media | `_set_combo_value` limpia combo a -1 cuando el valor no se encuentra |
| 3 | Media | Duplicar presentación valida selección en `inventory_table` antes de abrir diálogo |
| 4/8 | Media | Guard que impide `initial+prefill` simultáneos; `_dialog_prefill_variant_id()` extraído |
| 6 | Media | Paginación salta a la página de la variante seleccionada al cambiar filtros |
| 7 | Media | Ajuste masivo muestra advertencia cuando filas seleccionadas no coinciden con filtros |
| 9 | Baja | `_sync_inventory_table_selection(None)` ahora bloquea señales al limpiar |
| 10 | Baja | Confirmación de eliminar muestra producto/talla/color/stock/precio (no solo SKU) |
| 11 | Baja | Menú contextual sincroniza combo al hacer clic derecho |

**Tests agregados:** ~34 nuevos tests en `test_main_window_snapshot_cache.py` (de ~46 → 80)

### ✅ Merge claude/elegant-pike → main
- 52 commits integrados + 5 archivos con conflictos resueltos manualmente
- Conflictos: `inventory_filter_helper.py`, `inventory_view.py`, `main_window.py`, `test_inventory_filter_helper.py`, `config.py`
- Commit de merge: `ffb513d`

**Estado al cerrar:**
```
Rama:   main
HEAD:   ffb513d (merge: claude/elegant-pike → main)
Origin: pendiente push
```

---

## 2026-04-18

### ✅ Redondeo en corte de caja
- `ResumenCaja` suma `total_descuentos` y `total_ajuste_redondeo`
- El detalle del corte en Configuración muestra "Descuentos aplicados" y "Ajuste por redondeo"
- Archivos: `caja_service.py`, `settings_cash_history_detail_helper.py`, `main_window.py`
- Tests actualizados y en verde ✓

### ✅ Calculadora con teclado físico — verificada
- Ya estaba implementada desde `fc5f0bb` (2026-03-12) vía `install_keypad_shortcuts`

### ✅ Corte de caja — cerrar y reabrir en un paso
- `close_and_reopen_cash_session_action` en una sola transacción
- Campo "Reactivo nueva sesión" + botón "Cerrar y reabrir caja"
- Fix: `session.flush()` antes de `abrir_sesion`
- Commits: `3a9d45b` / `e0ccc9b`

### ✅ Conteo por SKU con recordatorios + Stock mínimo por presentación
**Commits:** `626b492` (main) → fixes `a5b69d7`, `1ae8a29`

- `ultimo_conteo_at` — columna en inventario, filtro por conteo
- `stock_minimo` — checkbox + spinner en diálogo de presentación, alerta visual y filtro "Bajo mínimo"
- Tests actualizados: `test_inventory_filter_helper.py`, `test_inventory_table_row_helper.py`, `test_inventory_snapshot_service.py`

---

## 2026-04-14

### ✅ Documentación completa del proyecto en Obsidian
- Mapeado todo el proyecto con agente explorador
- Creadas 20 notas (00 a 20) cubriendo arquitectura, BD, servicios, flujos, deuda técnica y pendientes
- No hubo cambios de código — solo lectura y documentación

---

### ✅ Paso 1 — Consolidar archivos sin commitear
**Commits:**
- `8aebff9` — Consolidar documentacion de satelite, conteo por SKU y handoff
- `e8afd0f` — Agregar scripts de Windows para build y arranque del satelite

**Qué se consolidó:**
- `docs/hoja_ruta_mejoras.md` — anotaciones de producto 2026-04-11/12
- `docs/satelite_consulta_y_cache_local.md` — decisión técnica del satélite
- `docs/conteo_por_sku_y_recordatorios.md` — decisión de conteo por SKU
- `docs/handoff_claude_code_2026-04-13.md` — documento de traspaso
- `scripts/build_presupuestos_satelite_hoy_windows.bat` — build satélite Windows
- `scripts/windows_launch_presupuestos_satelite.ps1` — launcher Windows

---

### ✅ Paso 2 — Tests para `loyalty_service` y `auth_service`
**Commit:** `0d9ecb8`

- `test_loyalty_service.py`: 32 tests
- `test_auth_service.py`: 17 tests
- `test_venta_service.py`: corregidos 4 stubs rotos

**Total tests nuevos:** 49 | **Suite completa:** verde ✓

---

### ✅ Paso 3 — Tests para servicios restantes críticos
**Commits:** `08816c1`, `4a51e80`

- `test_user_service.py`: 20 tests
- `test_compra_service.py`: 14 tests
- `test_sale_discount_service.py`: 22 tests
- `test_sale_stock_policy.py`: 3 tests
- `test_marketing_audit_service.py`: 7 tests

**Total acumulado sesión:** ~120 tests nuevos | **Suite completa:** verde ✓

---

### ✅ Paso 4 — Task Scheduler para respaldos automáticos en Windows
**Commit:** `8628072`
- Sección `9.1` completa en `WINDOWS_SETUP.md` con instrucciones PowerShell

---

### ✅ Paso 5 — Modo offline para el satélite (V1 cache local)
**Commits:** `657c675`, `3e14a42`, `af9fd09`, `0f3d2cb`

- `catalog_local_cache_service.py` — snapshot JSON local
- `satellite_startup_service.py` — probe TCP 3s
- Arranque con fallback elegante (online / offline / error amigable)
- `setup_satelite.ps1` — instalación en un paso
- 15 tests nuevos

**Validado en piso** — PC satélite: `C:\Users\Daniel\Desktop\PresupuestosSatelite-2026.04.07-windows\`

---

### ✅ Paso 6 — Estabilización y mejoras de kiosko
**Commits:** `325ed45`, `88845b5`, `6f46fd9`, `2e27b3f`

- Arranque automático (`-AutoStart` en setup)
- Pantalla completa + botón Salir discreto
- Scroll táctil (`QScroller`) en 9 widgets
- Foco automático en campo de escaneo al cambiar a kiosko

---

### ✅ Paso 7 — Impresión de etiquetas y botón prominente
**Commits:** `8cc6c98`, `7ad09fa`, `0d83469`, `a7b38f9`

- Botón "Imprimir etiqueta" en catálogo plano y guiado
- Ctrl+P en tabla del catálogo
- PIN: admin `634700` / empleadas `12345`
- Online: desde DB; offline: desde cache JSON (`render_inventory_label_from_cache_row`)
- Botón "Agregar" promovido a `primaryButton` + `minHeight 38px`

---

### ✅ Merge a main + Obsidian al día
**Commit de merge:** `9977105`
- Rama `codex/etiquetas-windows` → `main`
- Notas 17, 18, 19, 20 actualizadas con estado real

---

## 2026-04-15 (parte 1)

### ✅ Fixes de bugs (build anterior)

| Commit | Fix |
|--------|-----|
| `4f6f510` | NameError al emitir presupuesto (`_state_value` no importado) |
| `df3705a` | Freeze al dar Refrescar — `_correct_guided_state` era recursivo |
| `81f46a3` | Botones Reanudar/Emitir seleccionado: normalizar `.strip().upper()` igual que el helper |

### ✅ AppData y config persistente

| Commit | Cambio |
|--------|--------|
| `130f922` | `satellite_data_dir()` guarda config en `%APPDATA%\PresupuestosSatelite\` |
| `7109386` | Cache del catálogo también en AppData (sobrevive updates del bundle) |

### ✅ Features nuevas

| Commit | Feature |
|--------|---------|
| `c23f89c` | Niveles guiados ordenados: Preescolar → Primaria → Secundaria → Bachillerato |
| `c52ef95` | **Presupuestos en modo local**: tab Presupuesto habilitado offline, Emitir genera folio local y abre WhatsApp |
| `8e21a5d` | **Crear cliente**: teléfono obligatorio, solo dígitos, exactamente 10 |

### ✅ Sistema de Favoritos

| Commit | Feature |
|--------|---------|
| `d54017a` | **Favoritos en flujo guiado**: botón ♥ en cada tarjeta, favoritos ordenados primero, persistidos en `satellite_data_dir/data/favorites.json` |
| `bd6f6ac` | **Ventana ♥ Favoritos**: botón en header del flujo guiado; `seed_favorites_from_bundle` copia seed al AppData en primer arranque Windows |
| `b121c80` | **Rediseño dialog**: layout master-detail (lista izquierda / detalle derecho), grupos por tipo de pieza, header degradado rojo, 820×580 |
| `8dbea86` | Título "Los favoritos de Maximoda", tallas agrupadas por precio, dialog 960×660 |
| `4c43cb4` | Fix orden grupos: normalizar acentos con `unicodedata.NFD` → Pantalón/Suéter matchean correctamente |
| `3bfe1f5` | `data/favorites.json` commiteado como seed (35 favoritos actuales de Maximoda) |

---

## 2026-04-15 (parte 2) / 2026-04-16

### ✅ UX improvements + pulido de favoritos
**Commit:** `0a1ab42`

| Cambio | Detalle |
|--------|---------|
| **Hint label en Buscar** | Aparece bajo los botones de acción; explica por qué Reanudar/Emitir están inactivos según el estado del presupuesto seleccionado. Se oculta cuando no hay selección activa. |
| **Imprimir etiqueta sin PIN** | Eliminado el dialog de contraseña que bloqueaba la impresión de etiquetas en el satélite |
| **Anterior/Siguiente en etiqueta** | El dialog de impresión ahora recibe todas las variantes del mismo producto (mismo `producto_nombre_base` + escuela + nivel), permitiendo navegar entre tallas con los botones Anterior/Siguiente. Funciona en modo online y offline. |
| **Dialog favoritos limpiado** | Eliminados los botones "Quitar de favoritos", "Imprimir etiqueta" y el spinner de Cantidad del panel derecho. Ctrl+P sigue disponible para imprimir. |
| **Agrupación por escuela en favoritos** | Cuando un producto tiene variantes a distintos precios por escuela, se muestran secciones "Precio general" y "Precio {escuela}" en lugar de agrupar solo por precio — deja claro el origen de cada precio. |
| **Tallas ordenadas numéricamente** | Las tallas se ordenan como números (2, 3, 4, 6, 8, 10, 12…) en lugar de alfabéticamente (10, 12, 14, 2, 28…) |
| **Protección de favoritos** | Quitar un favorito (♥ → ♡ en el flujo guiado) ahora pide contraseña `12345`. Agregar favoritos sigue siendo libre. |

---

## 2026-04-16

### ✅ Splash screen + instancia única + kiosko + bug fixes
**Commit:** `b2e0798`

| Cambio | Detalle |
|--------|---------|
| **Splash screen** | Pantalla de carga al arrancar con nombre de la app, colores de la marca y mensajes de progreso por paso: "Verificando conexión", "Preparando base de datos", "Cargando catálogo", "Listo." |
| **Instancia única** | `QLockFile` en `%TEMP%` impide abrir segunda ventana — muestra mensaje "Ya está abierto, busca la ventana en la barra de tareas". Si la app se cuelga, el lock expira automáticamente (comportamiento por defecto Qt). |
| **Protección favoritos bilateral** | Agregar y quitar favoritos piden contraseña `12345`. Mensaje contextual diferente para cada acción. |
| **Kiosko zona central más grande** | SKU: 26→30px. Nombre producto: 22→28px. Nuevo label "Talla X · Color Y" en gris suave debajo del nombre. Precio: 48→56px, color cambiado a rojo `#c0392b`. |
| **Bug fix: Imprimir cierra la app** | `printable_text_dialog.py` usaba `QPrinter.setPageMargins(float, float, float, float, Unit)` — API de Qt5 que no existe en PyQt6. El `TypeError` en el slot mataba el proceso. Corregido a `QMarginsF(...)`. Afectaba también tickets de venta y apartados en main_window. |

---

## 2026-04-16 (parte 2)

### ✅ Optimización de consultas en `main_window.py`
**Commit:** `da69a03`

| Cambio                                  | Detalle                                                                                                                                                                                                                                                            |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Sesiones compartidas en refresh_all** | `_refresh_settings_users`, `_refresh_settings_suppliers` y `_refresh_settings_clients` ahora aceptan un `session` opcional. `refresh_all` les pasa una sola sesión compartida en vez de abrir 3 sesiones separadas.                                                |
| **Cache de snapshots de empleadas**     | `_refresh_settings_employees` guarda los snapshots en `self._employee_activity_snapshots_cache`. `_refresh_settings_employee_detail` reutiliza ese cache cuando `summary_days=1`, eliminando la segunda carga innecesaria al seleccionar una empleada en la lista. |

### ✅ Refrescos de UI costosos eliminados
**Commit:** `243115c`

`_refresh_sale_cart_table` y `_refresh_quote_cart_table` llamaban a `_refresh_permissions()` (~150 `setEnabled`/`setVisible`) en cada escaneo, cambio de cantidad o descuento. Como el rol y la sesión de caja no cambian con el carrito, se reemplazó por las actualizaciones mínimas:
- `sale_layaway_button` — único botón sale-cart-dependiente no cubierto ya por el panel_view
- `quote_qty_down/up/remove/clear_button` — dependían del quote_cart

### ✅ Tests `quote_action_service` — bloqueador de Fase 5
**Commit:** `e3b6b7f`

14 tests en dos clases (`EmitQuoteTests`, `CancelQuoteTests`):
- Happy path: `emit_quote` y `cancel_quote` llaman a los métodos correctos del servicio
- Verificación de kwargs: `session`, `presupuesto`, `usuario`, `observacion` pasados correctamente
- `observacion` contiene el username del operador
- `ValueError` cuando quote no existe, cuando usuario no existe, o cuando ambos faltan
- El servicio no se llama si falta alguno de los dos objetos

## 2026-05-22

### ✅ Catálogo deportivo: productos faltantes + productos virtuales

#### Cambios en base de datos (local + producción 192.168.0.10)
| Cambio | Detalle |
|--------|---------|
| **Género Unisex** | 136 productos deportivos (pants, playeras) marcados como `genero = 'Unisex'` |
| **Typo Alcocer** | Corregido "Acolcer" → "Alcocer" en escuela y productos |
| **Pants 3pz** | 6 productos + 37 variantes creados para 5 escuelas (precio = Pants 2pz + $100) |
| **Chamarra deportiva** | 11 productos + 85 variantes para 10 escuelas (precios flat por nivel) |
| **Palacio completo** | Playera + Pants 3pz creados (2 productos + 20 variantes) |
| **Productos virtuales** | 674 variantes de Pants 3pz y Chamarra marcadas con `stock_minimo = -1` |

#### Cambios en código
| Archivo | Cambio |
|---------|--------|
| `inventory_filter_helper.py` | `stock_minimo < 0` excluye variante de filtros "zero" y "below_min" |
| `stock_tone_helper.py` | `stock_minimo < 0` retorna tono "neutral" en vez de "danger" |
| `inventory_overview_helper.py` | Badge muestra "Virtual" en vez de "Agotado" para productos virtuales |
| `inventory_overview_service.py` | `stock_minimo` agregado al `InventoryOverviewSnapshot` |
| `main_window.py` | Se pasa `stock_minimo` al builder de overview |
| `product_templates.py` | 38 plantillas de presentación + `gender=Unisex` en 8 plantillas base |

#### Rollback (si productos virtuales causan problemas)

**Base de datos** (ejecutar en ambas DBs):
```sql
UPDATE variante SET stock_minimo = NULL WHERE stock_minimo = -1;
```

**Código** — revertir estos commits:
```bash
git revert <commit-hash>  # commit de productos virtuales
```

---

## 2026-09-07 → 2026-09-08 — Cámaras, caja con reactivo, nómina y Telegram (maratón)

### ✅ Suite de tests saneada (2026-09-07/08)

| Commit | Cambio |
|--------|--------|
| `2405106a` | Ticket con recuadro del TOTAL arriba a la derecha del diálogo de impresión (VERSION `2026.11.11`) |
| `5fad9f02` `befff3c3` `53b13633` | `pytest --fast` (580 tests en 4 s); los tests ya no tocan producción (`conftest.py` fuerza `pos_uniformes_test`) |
| `2217bf70` `10ca1980` `3ca8623b` `d93e008b` `6c912695` | Sin hilos de Postgres ni clics colgados; semilla mínima (62 fallos → 0); navegación del kiosko derivada; reloj congelado; watchdog y recordatorios |
| `430cf04e` `2bca1f20` | `_KioskKeyFilter` a nivel de módulo (adiós al segfault); suite completa 1,681 en ~74 s |

### ✅ Red: impresora y DVR al Deco

HP Smart Tank 750 reconectada al WiFi (sin pantalla: modo config + red DIRECT) → `192.168.0.9`; 50 trabajos atorados cancelados; página de prueba OK. DVR Dahua por cable, IP fija `192.168.0.11`, hora corregida (GMT-6, sin DST, NTP), P2P + DMSS con usuario `dany`. Ver [[32 - Cámaras y Afluencia]].

### ✅ Cámaras en el kiosko

| Commit | Feature |
|--------|---------|
| `aa4dfa91` | **Visor de cámaras** (Ctrl+Shift+C / botón): empleadas = entradas, admin PIN = todas; pestaña 📹 Cámaras en admin; `dvr_settings_cache_service` |
| `49ff470d` | **Ver momento** en la Libreta: grabación del DVR a la hora del movimiento (`cam/playback`) |
| `ccb820e4` `0fd5a1cb` | Pestaña Cámaras: lista de canales con colores fijos, aviso de qué campo falta |
| `b48e5389` `654fc580` `076dae1e` `fae5691b` | **Afluencia**: contador YOLO + ByteTrack (proceso aparte), tabla `afluencia_hora`, sección en Libreta, línea diagonal en ENTRADA2.2, instalador de un paso, lee el DVR de AppData |

### ✅ Updater

| Commit | Fix |
|--------|-----|
| `3ae534d7` | `VERSION.txt` publicado = versión+commit → los kioskos actualizan en cada build |
| `3dbbcbd7` | La app lee `VERSION.txt` junto al exe como versión instalada (antes avisaba "versión nueva" siempre) |

### ✅ Caja con reactivo, nómina y León de un botón

| Commit | Feature |
|--------|---------|
| `223546b4` | **Corte por periodo con reactivo** ($11,160), **nómina** 1,300 + 2/com − 216.67/falta, `caja_parametros`, `empleada_pago`, diálogos de corte/pago/parámetros, API móvil |
| `e8a9d196` | **Resumen diario por Telegram** (`resumen_diario_telegram.py`, `telegram_service`) |
| `96728483` | **Historial de pagos** (💵 Pagos) |
| `3a74d002` `93145510` `e7052a0e` `06488ebe` `bf8a204c` `7052c3e9` | **Corte de un botón para León** (pagos del día automáticos) y tickets: el suyo simple (SE VENDIO · PAGAR A con desglose · SACAR DE LA VENTA · "reactivo"), el del dueño con venta, reactivo y pagos desglosados |
| `80c65040` | **Pendientes de hoy** (pagos, posibles faltas, descansos, sin horario) + pago con fecha elegida + recordatorio 13:30 |
| `c87ccd49` | **Equipo**: dar de baja por temporada / reactivar (Lupita) |
| `d44cee32` | **Empleadas por días** (Naye sáb/dom): `modo_pago`/`dias_trabajo`, cobra por día al terminar sus días, "Vino a trabajar" para León, ✏️ Horario en Equipo |
| `28de5783` | **Retiros con motivo** (`caja_retiro`): botón para León y Daniel, kiosko + PWA, el corte los descuenta y los tickets los listan |
| `99993374` | **Horario de la tienda** (18:00; jue/dom 17:00) y corte automático 30 min antes (`corte_automatico.py`, tareas 16:30/17:30) |
| `3c69b5b9` | **Bot de Telegram**: `/corte` desde el celular (imprime en la tienda), `/estado`, `/resumen`, `/pendientes`; el corte por hora queda apagado por default |

### Decisiones de Daniel en la sesión

- Solo él (VEND-1) y su papá León (ENC-1) hacen cortes, pagos y retiros; León **no captura ni cuenta**: un botón y un ticket claro.
- Nómina calculada (revierte el "descartado" de la Libreta v1); faltas se descuentan (1/6 del sueldo, por confirmar).
- Naye trabaja fines de semana y a veces la semana completa → modo por días.
- Prefiere **ordenar el corte desde el celular** (`/corte`) a que se haga solo por hora.
- Servidor futuro: mini PC Linux (Lenovo Tiny i5 usada) + Coral para Frigate; IA de lenguaje por API de Claude; la MacBook Air 2017 sirve con Linux.

### Estado al cerrar

```
Rama:  chore/reorganizacion-repo @ af8aa262 (pusheada) · VERSION 2026.11.11 (+commit en builds)
Tests: 1,811 en verde (completa) · --fast 670
Windows: PENDIENTE actualizar_pc_principal.bat (4 migraciones: s2a3, t3b4, u4c5, v5d6)
Mac: base de pruebas local migrada a v5d6e7f8a9b0; token de Telegram en el env local (falta chat id)
```


## 2026-09-09 — Historial de cortes con reimpresión (dueño)

- Libreta → **🧾 Cortes**: cortes por mes con hora, periodo, quién, en caja, reactivo, se retiró, pagos y sobró/faltó (solo pantalla). Ticket reconstruido del periodo guardado y **reimpresión** marcada `* REIMPRESION *` con la hora del corte original, en formato dueño o encargado.
- `services/historial_cortes_service.py` + `ui/dialogs/historial_cortes_dialog.py` + `test_historial_cortes` (ver [[33 - Caja, Nómina y Corte Automático]]).
- Telegram en la PC principal: el antivirus intercepta HTTPS → `truststore` + reintento sin verificar con aviso (af8aa262). Pendiente que Daniel vuelva a correr `configurar_telegram.bat` tras actualizar.
- **Alertas por Telegram**: corte hecho (quién/venta/pagos/se saca, ⚠️ si el dueño encontró diferencia ≥ $50), retiro del cajón, cierre sin corte (10 min después), movimiento fuera de horario (apertura supuesta 09:00). Cola `alerta_telegram` que el bot vacía cada vuelta; migración `w6e7f8a9b0c1`. Bot ya configurado y contestando en la PC principal.
- **Venta rápida**: botón "Sin ticket" (registra sin papel), "← Regresar" en la vista del ticket, "Producto sin código" con chips de prendas 4×2.
- **Libreta**: 🧾 Cortes = historial con reimpresión.
- **Calendario del kiosko**: detalle del día al tocar + pago con gafete (empleada el suyo, Daniel/León todos); Naye (por días) sin "descansos" falsos. Ver [[30 - Calendario de Empleadas]].
- Impresión lenta el 2026-09-09 (~10:49–11:17, tickets esperaron hasta 28 min; etiquetas directas se trababan): Windows Update en la principal. Recomendación: horas activas 8:00–19:00.
- Auditoría de Meilisearch (ver [[13 - Servicios - Utilidades]]); decisión pendiente.

## 2026-09-17 → 2026-09-21 — Afinar, nombres, la `.10` perdida y el catálogo (fases 1 y 2)

- **17/09 — rendimiento medido** (perfilador sobre el kiosko y el POS, AST-scan de consultas en bucle; el servidor no contestaba, tiempos de la Mac): flujo guiado del kiosko 0.38 → 0.05 s por cambio de escuela; banner de conteo vencido a un hilo (congelaba la UI cada 10 min por Wi-Fi); tarifarios ~100 → 2 consultas; índice en `movimiento_inventario.referencia` (`ef5a6b7c8d9e`); Conteos ~85 → ~10 consultas (`alcances_en_lote`); **escaneo en venta rápida cache-primero** (cero viajes a Postgres por pieza; un precio nuevo tarda ≤5 min); POS: normalización del buscador con caché, arranque 1.9 → 1.2 s. Afluencia se queda en 4 fps (no es prioridad). Tabla completa en [[19 - Deuda Técnica]].
- **17/09 — celular, básicos por prenda:** al tocar un tipo con varias prendas, "¿todas o una sola?", cada una con su último conteo y quién la cuenta (cache v15). [[36 - Conteos por Jornada]]
- **18/09 — siempre el nombre, nunca `VEND-1`:** `nombres_empleadas_service` (caché + copia local) aplicado en tickets, historiales, Libreta, inventario/bodega, conteos, celular y Telegram; lo guardado no cambia. [[22 - Referencia Rápida]]
- **18/09 — Contar en el celular:** pestañas Escuelas | Básicos, buscador y grupos (en proceso / tocan / nunca / contadas); ⚠ solo en las vencidas de verdad. Y la **hoja de captura salía vacía** desde el 17 (id `cont-prendas` repetido por el selector de básicos) → `cont-prenda-sel` + test de ids únicos (cache v17). Probado desde el celular de Daniel contra el servidor de la Mac. [[36 - Conteos por Jornada]]
- **18/09 — hojas repetidas:** imprimir la hoja de conteo abre la jornada a nombre de quien imprime (`registrar_impresion`, migración `f06b7c8d9e0f`), el selector avisa "hoja impresa 10:32" y pide confirmación fuerte para otra; el banner sin gafete ya no imprime. [[36 - Conteos por Jornada]]
- **18/09 — bodega móvil:** *Llegó mercancía* sin Pants 3pz ni Chamarra (son artificiales: se arman), orden por tipo de pieza y tallas como en la hoja (cache v19).
- **18/09 — navegación de la PWA:** barra superior (Atrás / Actualizar / Menú) con pila de pantallas y botón físico de atrás; jalar para actualizar en todas; *Llegó mercancía* imprime una etiqueta por pieza y el dueño ve *Lo que ha llegado* (cache v22). [[31 - PWA Libreta Móvil]]
- **18/09 — red:** POS y kiosko en modo local a la vez → un celular tomó la `.10` por DHCP y Windows dejó la fija de la principal en `169.254…`. Se recuperó con `netsh` (receta en [[22 - Referencia Rápida]]) y Daniel apartó la `.10` en el ARRIS. Pendiente: apartar `.9` y `.11`, y un cable en vez del dongle Wi-Fi.

- **19/09:** corte con cada pago y retiro desglosado y casilla "no salió del cajón" (`en_cajon`, migración `0b1c2d3e4f5a`); asistencia en el celular con Quitar por marca y "Sí vino", también para el dueño (cache v23).

- **20/09:** **catálogo fase 1** en producción: 398 nombres limpios, Álvaro Obregón (El Carretón) y Vicente Guerrero Preescolar separadas, 3 pares de duplicados fundidos; sin tocar SKUs.
- **20/09:** limpieza en producción: 138 tallas reubicadas a la jornada de su prenda (`reubicar_conteos_por_prenda`); Mandil → Bata Infantil Estampado.
- **20/09:** **Mapa de conteos** (celular y kiosko): qué está contado y qué no, por capas, con semáforo; en el kiosko dentro de la sección Conteos, nativo (sin WebEngine) y a tono con el programa (tarjetas `libretaCard`, `conteo_mapa_widgets.py`), con "En proceso · quién".
- **20/09:** básicos = **todos** los generales de uniforme, menos la ropa normal (casual, temporada, interior): 56 → 196 prendas en producción.
- **20/09:** la captura del kiosko de una jornada de una sola prenda traía todo el tipo → usa `alcance` con prenda.
- **21/09 — catálogo fase 2, base:** Daniel actualizó la principal (producción en `0b1c2d3e4f5a`). Se acordó el modelo del **uniforme como entidad** (Olan = un producto en varios uniformes; "Pants Suelto <escuela>" es otro pants con escudo y hay mezcla con los del estante): `uniforme` + `uniforme_pieza` (`1c2d3e4f5a6b`), `uniforme_service`, `armar_uniformes` (dry-run/`--aplicar`), POS Más → Uniformes por escuela, ligas en espejo mientras tanto; probado sobre una copia de producción del día. Test de marcas del celular ya no depende del día de la semana. Nada en producción. Ver [[38 - Catálogo Fase 2 - Uniformes]]. Fase 3 decidida: 3pz/Chamarra siguen artificiales, la venta descompone (2pz + playera; 2pz → chamarra + suelto), precios sueltos más caros a propósito. **2b** (`47c98bb3`): hoja/mapa en el orden del uniforme, tarifario por grupo con opcional y color de pieza (y sin "Sin color"), guiado con las generales del uniforme; todo con fallback si la escuela no está armada. **Fase 3** (`1e3a53ef`): `conjunto_componente` + `conjunto_service`; `registrar_movimiento` descompone la venta de un 3pz/chamarra en sus piezas y recalcula su stock (`derivado:`); Libreta y Revisar al tanto; `armar_recetas` y Receta… en la pantalla. **22/09**: alternativas en la receta (el 3pz del SABES lleva playera deportiva de hombre o de mujer, stock sumado), `crear_piezas_faltantes` (los 15 `Pants Suelto <escuela>` que faltaban y la `Playera Deportiva Vicente Guerrero`) y desempate por la regla de precios → **114/114 recetas** sobre la copia de producción, 0 pendientes.

### Estado al cerrar (2026-09-21)

```
Rama:  chore/reorganizacion-repo @ cc5baa4d (pusheada)
Tests: completa 2,436 en verde (~35 s con -n 6)
Base:  producción en 0b1c2d3e4f5a · el código pide 2d3e4f5a6b7c (uniformes + recetas; entran solas al actualizar)
Windows: cuando Daniel diga → actualizar_pc_principal.bat + armar_uniformes en la principal
```

## 2026-09-12 → 2026-09-15 — Revisar v2, conteos de las empleadas, bodega móvil, stock vivo y pasos únicos

Resumen; el detalle está en el índice y en las notas enlazadas.

- **12/09:** la ventana negra era "POS Snapshot Casa" → `INFRA_VERSION 4`; `/asistencia` con comandos tocables por empleada (`/falta_Fanny · /descanso_Fanny`). [[34 - Telegram y Resumen Diario]]
- **13/09 (domingo, larga):** contar desde el celular; afluencia con tarea oculta, `INFRA_VERSION 5` y **líneas dibujadas con el ratón** en caliente; **Revisar v2** (cuántas hay / vendidas / ritmo / cuánto pedir a 4 semanas, se guarda lo decidido `bc2d3e4f5a6b`, hoja de pedido, historia de talla y de escuela); conteos como las pidieron las empleadas (una jornada por escuela, seguirla, 14 días fuera del menú, sin pisar capturas, Eliminar/Reasignar); **bodega móvil** (piso vs cajas, Llegó mercancía / Pasar al piso / Corregir caja); nómina por días de menos y descanso movido. [[37 - Revisar y Pedidos]], [[36 - Conteos por Jornada]], [[31 - PWA Libreta Móvil]], [[30 - Calendario de Empleadas]]
- **14/09:** el corte ofrece los pagos de hoy; **la venta descuenta stock** (`cd3e4f5a6b7c`, puede quedar negativo); reimprimir ticket; tablero con todas las escuelas; Revisar rediseñado (tarjetas, 5 columnas, "por qué"); comparativo con el conteo anterior; catálogo: Práxedis partida, Rancho Nuevo y Jaral (51 escuelas), 214/322 prendas sin color; tarjeta "lo que llega" en grande; básicos por prenda (`de4f5a6b7c8d`); ventanas negras del corte (`INFRA_VERSION 6`) y pythonw para bot/PWA. [[33 - Caja, Nómina y Corte Automático]], [[07 - Servicios - Catálogo e Inventario]], [[29 - Updates y Mensajería]]
- **15/09:** iconos originales (M y átomo) en 7 tamaños; **pasos de una sola vez al actualizar** (`--pasos-unicos`: Meilisearch S4U, descontar ventas pasadas —cada vez—, instalar afluencia): ya no queda nada que correr a mano. Revisión de bugs: nómina con descanso movido + falta, aplicar conteo que deja negativo, tablero de Conteos en menos consultas.

### Estado al cerrar (2026-09-15)

```
Rama:  chore/reorganizacion-repo @ 20411854 (pusheada)
Tests: completa 2,334 en verde (~28 s con -n 6)
Base:  producción en ab1c2d3e4f5a · el código pide de4f5a6b7c8d (bc2d… → cd3e… → de4f… entran solas al actualizar)
Windows: PENDIENTE actualizar_pc_principal.bat — trae todo del 13 al 15 y corre solo los pasos únicos;
         lo único de Daniel: dibujar la línea de ENTRADA2.2 en la ventana que se abre al final
```

## 2026-09-10 — Un solo supervisor, cifras oficiales y lenguaje neutral

- **Infraestructura que se aplica sola**: `scripts/postactualizacion.py` (lo llaman `abrir_pos.bat` y `actualizar_pc_principal.bat`) deja tareas y servicios al día según `INFRA_VERSION`; borra las obsoletas, crea las que faltan y reinicia bot + PWA. Regla nueva de la casa: **cambio de infraestructura = editar esas listas y subir `INFRA_VERSION`**, nunca pedirle a Daniel que corra un instalador. Ver [[29 - Updates y Mensajería]].
- **Supervisor único** (`scripts/supervisor.py`): un proceso oculto que revisa bot y PWA cada 60 s, con mutex, calma de 3 min y log propio. Sustituye a 4 tareas de cada 5 min que abrían consola. Ver [[34 - Telegram y Resumen Diario]].
- **Tickets de corte más simples** (v3, pedido de Daniel): reactivo primero, venta, tarjeta con VENTA TOTAL, las restas una por una y SACAR DE LA VENTA. Sin "EN CAJA" ni "Se retira".
- **Cifras oficiales vs reales**: lo oficial (con sus ajustes) se muestra **sin anunciarlo** en Libreta, historial, tickets y PWA; lo real se asoma solo con **Ctrl+Shift+R**. Los ajustes también corrigen el efectivo de la Libreta (`ajustes_en_rango`). Ver [[33 - Caja, Nómina y Corte Automático]].
- **Borrar corte** y **deshacer pago** (ambos solo VEND-1), con el periodo y el reactivo recompuestos.
- **Lenguaje neutral**: ningún texto, comentario ni dato de prueba nombra a la familia; se dice "el encargado".
- **Meilisearch**: puntos 1-5 de la auditoría implementados (SKU corto, nivel/atributo/escudo indexados, talla/color filtrables, ranking por existencia y ventas de 60 días, orden de tallas, sinónimos reales).
- **El corte pregunta por la venta**, no por el total del cajón; debajo se ve en vivo cuánto queda en caja.
- **Historial de cortes con el idioma del ticket**: Reactivo · Venta · Pagos · Gastos (fuera "En caja" y "Se retiró"), con *Venta real* y *Ajuste* tras Ctrl+Shift+R.
- **Corregir cortes**: ✏️ Ajustar la venta (lo que se reporta vs lo real), ↩ Quitar el ajuste, 🗑 Borrar corte.
- **Un solo ticket**: el simple es el default en la Libreta, el encargado, Telegram y las reimpresiones; el completo queda como casilla.
- **La casilla de ocultar tarjeta se recuerda** (migración `y8a9b0c1d2e3`).
- Limpieza en producción: se quitaron 3 cortes duplicados (5, 6 y 7 de septiembre) para dejar uno por día; respaldo previo en JSON.
- Diagnóstico: la impresión lenta del 09 fue **Windows Update**, no el sistema.

### Estado al cerrar (2026-09-10)

```
Rama:  chore/reorganizacion-repo @ 47d9c5fc (pusheada)
Tests: completa 1,989 en verde (~70 s) · --fast 711 (~4 s)
Base:  producción en x7f8a9b0c1d2 · pruebas en y8a9b0c1d2e3 (la nueva entra sola al actualizar)
Windows: PENDIENTE abrir "POS Uniformes" para tomar lo del 10 (la postactualización hace el resto sola)
```
