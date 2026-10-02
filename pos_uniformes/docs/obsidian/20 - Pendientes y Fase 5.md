---
tags: [estado, pos-uniformes]
---

# Pendientes y Fase 5

## Fase actual: Fase 5 — Optimización fina

> Objetivo: Mejorar mantenibilidad y rendimiento con el sistema ya estabilizado.
> No abrir refactors grandes. No mezclar estructura con features nuevas.

---

## Pendientes de validación en Windows

| Pendiente | Estado | Prioridad |
|-----------|--------|-----------|
| Conteo físico V2 (selección múltiple, modo uno-a-uno, Restar 1) | `validated-tests` | Alta |
| "Agregar sin código" en Caja | `validated-tests` | Alta |
| Impresión por lote de etiquetas | `validated-tests` | Alta |
| Conteo por SKU + stock mínimo por presentación | `validated-tests` | Alta |
| Duplicar presentación + filtros de precio | `validated-tests` | Alta |
| Migración `a3c7e9f1b204` — `alembic upgrade heads` | `validated-windows` ✅ 2026-04-22 | Alta |
| Impresión ticket 80mm EC-PM-80320 | `validated-windows` ✅ 2026-04-22 | Alta |
| Build Windows con todos los cambios actuales | `pending-manual` | Alta |
| Satélite en uso de piso (Reanudar/Emitir, offline, crear cliente) | `pending-manual` | Media |

**Comando de verificación en Windows:**
```powershell
py scripts\check_startup_health.py
py -m unittest discover -s tests -p 'test_*.py'
```

---

## Pendientes de consolidación en git

Archivos nuevos sin trackear (rama `codex/etiquetas-windows`):
- `docs/conteo_por_sku_y_recordatorios.md` — decisiones de producto
- `docs/satelite_consulta_y_cache_local.md` — arquitectura del satélite
- `scripts/build_presupuestos_satelite_hoy_windows.bat` — build satélite Windows
- `scripts/windows_launch_presupuestos_satelite.ps1` — launcher Windows

**Decisión pendiente:** ¿Estos docs y scripts ya son el flujo oficial o solo utilidades locales?

Archivo modificado sin commitear:
- `docs/hoja_ruta_mejoras.md` — tiene anotaciones nuevas de producto

---

## Pendientes técnicos de Fase 5

### Tests críticos (bloquean el cierre)
- [x] `loyalty_service` ✅ 32 tests — 2026-04-14
- [x] `auth_service` ✅ 17 tests — 2026-04-14

### Tests importantes (Fase 5)
- [x] `catalog_mutation_service` ✅ ya tenía 4 tests
- [x] `user_service` ✅ 20 tests — 2026-04-14
- [x] `compra_service` ✅ 14 tests — 2026-04-14
- [x] `quote_action_service` ✅ 14 tests — 2026-04-16 — `e3b6b7f`

### Optimizaciones de Fase 5
- [x] Revisar consultas repetidas en `main_window.py` ✅ 2026-04-16 — `da69a03`
- [x] Revisar refrescos de UI costosos ✅ 2026-04-16 — `243115c`
- [ ] Consolidar utilidades compartidas
- [ ] Cerrar política de respaldos automáticos y recuperación

---

## Pendientes de producto/UX abiertos

### Backlog de Caja

| # | Pendiente | Estado |
|---|-----------|--------|
| 1 | Calculadora con teclado físico | ✅ cerrado 2026-04-18 — ya implementado desde `fc5f0bb` |
| 2 | Quitar nombre del cliente del bloque de total | ✅ cerrado 2026-05-02 — `45771d6` |
| 3 | Redondeo de cobro | ✅ cerrado 2026-04-18 — `ResumenCaja` desglosa descuento y ajuste |
| 4 | Cliente en Caja solo por escaneo de QR | ✅ cerrado 2026-04-18 — ya implementado, combo oculto/deshabilitado siempre |
| 5 | Corte cierra y reabre en un solo paso | ✅ cerrado 2026-04-18 — `close_and_reopen_cash_session_action`, `3a9d45b` / `e0ccc9b` |

### Satélite
- [x] Botón "Agregar al presupuesto" más prominente ✅ 2026-04-14
- [x] Scroll táctil por arrastre en listas/tablas ✅ 2026-04-14
- [x] Cache local de catálogo (modo offline) ✅ 2026-04-14
- [x] Impresión de etiquetas desde catálogo (online + offline, PIN) ✅ 2026-04-14
- [x] **Commit refactors SAT-1 a SAT-4** ✅ 2026-04-15 — `0f0a0e9`
- [x] Config y cache en AppData (persiste entre updates) ✅ 2026-04-15 — `130f922` / `7109386`
- [x] Niveles ordenados por ciclo escolar ✅ 2026-04-15 — `c23f89c`
- [x] Fix NameError al emitir + fix freeze Refrescar ✅ 2026-04-15 — `4f6f510` / `df3705a`
- [x] Botones Reanudar/Emitir seleccionado robustecidos ✅ 2026-04-15 — `81f46a3`
- [x] **Presupuestos en modo local con emisión por WhatsApp** ✅ 2026-04-15 — `c52ef95`
- [x] Crear cliente: teléfono obligatorio 10 dígitos ✅ 2026-04-15 — `8e21a5d`
- [x] **Nuevo build Windows** ✅ 2026-04-18 — HEAD `0794e8a` — incluye corte+reopen y redondeo en corte
- [ ] Validar en piso: Reanudar/Emitir seleccionado, flujo offline, crear cliente
- [x] **Pantalla de carga al arrancar** ✅ 2026-04-16 — `b2e0798` — splash con mensajes de progreso + QLockFile bloquea segunda instancia
- [x] **Bug: botón Imprimir cierra la app** ✅ 2026-04-16 — `b2e0798` — `setPageMargins` con API Qt5, corregido a `QMarginsF` para PyQt6
- [x] Filtro de uniformes escolares — excluir ropa normal del flujo guiado
- [x] **Favoritos en piezas** ✅ 2026-04-15 — `d54017a` / `bd6f6ac` — corazón en cada tarjeta, favoritos primero; botón ★ Favoritos abre ventana de acceso rápido; seed en build Windows
- [ ] ~~Motor de sugerencias contextual (reglas + stats + scoring, sin ML)~~ — pospuesto; favoritos cubre la necesidad de acceso rápido con mucho menos complejidad
- [x] **Favoritos protegidos con contraseña al agregar** ✅ 2026-04-16 — `b2e0798` — agregar y quitar piden `12345`
- [x] **Kiosko — zona central más grande** ✅ 2026-04-16 — `b2e0798` — SKU 30px, producto 28px, talla·color nuevo label gris, precio 56px rojo
- [x] **Rediseño UI kiosko** ✅ 2026-04-16 — `3a3cc25` — 2 columnas, satScanCard + satProductHeroCard, precio terracota, addToCartButton
- [x] **Botón Agregar más compacto en kiosko** ✅ 2026-04-16 — `14f129f` — 13px / 36px alto (antes 15px / 48px)
- [ ] ~~Rediseño UI presupuesto guiado~~ — revertido (`399393b`); layout 2 columnas no convenció

### Conteo por SKU
- [x] Guardar "ultimo conteo" por SKU para recordatorios discretos ✅ 2026-04-18 — `626b492`
- [x] **Modulo conteo avanzado en Panel Uniformes** ✅ 2026-05-26 — `2f7e1ce` — conteo_service.py + PanelBridge + tab Conteo HTML
- [x] **Conteo por escuela con vigencia configurable** ✅ 2026-05-26 — config_conteo_escuela (dias_vigencia default 90)
- [x] **Ajuste con auditoria** ✅ 2026-05-26 — confirmar_ajustes_lote() crea MovimientoInventario
- [ ] Probar flujo completo de conteo end-to-end en la app
- [x] Seguimiento por SKU (no por zona) ✅ 2026-04-18
- [x] Sin popups invasivos — columna "Ult. conteo" + filtro en tabla ✅ 2026-04-18
- [x] Stock mínimo por presentación con alerta visual y filtro ✅ 2026-04-18
- [x] Scroll area en diálogo de conteo ✅ 2026-04-29 — `46d5199`
- [x] **Modo "Agregar mercancía"** ✅ 2026-04-29 — `2e05925`…`f12da54` — acumula scans sobre stock actual; spinboxes protegidos con mínimo; Restar 1 respeta piso; confirmación muestra modo

### Inventario — Nuevas funcionalidades (2026-04-21)
- [x] Filtro por rango de precio (combo) ✅ 2026-04-21 — `5af40d6`
- [x] Filtro por precio exacto (input en barra) ✅ 2026-04-21 — `e48addf`
- [x] Duplicar presentación con nueva talla ✅ 2026-04-21 — `167ba37`
- [x] SKU autoasignado al duplicar ✅ 2026-04-21 — `7f7e83c`

### Empleadas — Módulo base (2026-05-13 → 2026-05-15)
- [x] Ranking comparativo por periodo (Hoy / 7 días / Este mes) ✅ 2026-05-13 — `7be0720` — tabla con #, nombre, tickets, piezas, monto, última venta; toggle ocultar montos; 10 tests
- [x] Atribución de empleada en apartados ✅ 2026-05-15 — `9f59a54` — creación, cada abono y entrega pueden tener empleadas distintas; QR scan en diálogos; migración `b3c4d5e6f7a8`; 5 tests

### Auditoría UI — Pestaña Inventario (2026-04-21)
- [x] Riesgo 1 (Alto): `_selected_catalog_row` con selección de inventario activa ✅ — `1ef0ba4`
- [x] Riesgo 2 (Medio): `_set_combo_value` con valor no encontrado ✅ — `ef5f79a`
- [x] Riesgo 3 (Medio): Duplicar sin selección en inventory_table ✅ — `4e8f088`
- [x] Riesgo 4/8 (Medio): Guard initial+prefill, pre-fill desde tabla ✅ — `df773b7`
- [x] Riesgo 6 (Medio): Paginación pierde variante al cambiar filtros ✅ — `92fc151`
- [x] Riesgo 7 (Medio): Ajuste masivo sin advertencia de filtros activos ✅ — `ef66c3b`
- [x] Riesgo 9 (Bajo): `_sync_inventory_table_selection(None)` dispara señales ✅ — `8062bbf`
- [x] Riesgo 10 (Bajo): Confirmación eliminar sin detalles de variante ✅ — `d4d6e19`
- [x] Riesgo 11 (Bajo): Menú contextual no sincroniza combo ✅ — `382350e`

---

## Criterio de cierre de Fase 5

La Fase 5 se considera cerrada cuando:
1. ✅ Suite en verde
2. ✅ Precheck en verde
3. ✅ Tests de `loyalty_service` y `auth_service` escritos y pasando
4. ✅ Docs y scripts de satélite consolidados en git
5. [ ] Validaciones manuales en Windows completadas
6. [ ] Nuevo build Windows con todos los cambios de satélite
7. [ ] Checkpoint documentado en `docs/historial_refactors.md`

---

## Módulo Bodega (mini-WMS) — implementado 2026-05-17/18

> **Estado:** Código completo y mergeado a main. Pendiente validar en producción.

| Pendiente | Estado |
|-----------|--------|
| Desplegar en PC Windows (`git pull` + `alembic upgrade head`) | ✅ hecho 2026-05-18 |
| Probar crear ubicación, caja, ingresar producto | `pending-manual` |
| Probar búsqueda por producto/SKU en bodega | `pending-manual` |
| Probar QR por caja | `pending-manual` |
| Verificar catálogo e inventario siguen funcionando | ✅ hecho 2026-05-18 |

**Archivos nuevos:** `bodega_service.py`, `bodega_view.py`, `bodega_ingreso_dialog.py`, `bodega_ubicaciones_dialog.py`, `bodega_label_service.py`, `a1b3c5d7e9f0_add_bodega_module.py`, `test_bodega_service.py`

**Ingreso mercancía nueva (2026-05-20):** Checkbox "Es mercancía nueva (aumentar stock)" en diálogo de ingreso a caja. Cuando está activo, sube `stock_actual` vía `InventarioService.registrar_ingreso_compra()` antes de asignar a la caja — todo en la misma transacción. Referencia: `BODEGA_CAJA:{id}`.

**Mejoras 2026-05-21:**
- Etiqueta de caja genera PDF nativo (QPrinter + QTextDocument), vertical carta, con QR embebido — se abre en Vista Previa sin popup
- QR usa `QrGenerator.generate_for_caja()` existente (contenido: `BODEGA:CAJA:{codigo}`)
- Tallas ordenadas con `_size_sort_key` (rangos numéricos en orden natural: 3-5, 6-8, 9-12, 13-18)
- Autocomplete con `UnfilteredPopupCompletion` — Meilisearch filtra, QCompleter muestra todos los resultados
- Fix doble-fire Enter (`_completer_just_activated` flag)
- Fix crash satélite búsqueda (`_selected_search_btn` deleteLater)

---

## Siguiente iniciativa grande

> **Módulo: Empleadas / Atribución comercial / Comisiones**

Reglas de entrada ya definidas:
- No abrir dentro de la estabilización estructural
- Diseñar primero la separación `usuario` vs `empleada`
- Pensarlo desde el inicio para POS, kiosko y app móvil
- Los servicios base (`employee_*`) ya existen y tienen tests

---

## Meilisearch — integrado 2026-05-19/20

> **Estado:** Código completo y mergeado a main. Funcionando en Mac.

| Pendiente | Estado |
|-----------|--------|
| Instalar Meilisearch en PC Windows (binario + servicio) | `pending-manual` |
| Verificar fallback local funciona en Windows sin Meilisearch | `pending-manual` |
| Probar búsquedas en Catálogo, Inventario, Cmd+S, Bodega | `pending-manual` |

**Áreas integradas:** Satélite catálogo, satélite guiado, Cmd+S búsqueda rápida, inventario POS, catálogo POS, bodega ingreso a caja.

**Auto-reindex (2026-05-20):** `notify_catalog_changed()` dispara re-indexación en hilo daemon después de crear/actualizar/desactivar producto o variante, y cambio masivo de precios. No requiere intervención manual.

---

## Rama actual

```
Rama:   main
HEAD:   6f3c611 — UX bodega + catálogo: etiqueta PDF nativa, tallas custom, fixes varios
Origin: pushed ✅ 2026-05-22
Windows: git pull parcial (hasta 1ba92b7), falta 6f3c611
```

---

## Ver también
- [[18 - Cobertura de Tests]] — qué tests faltan
- [[19 - Deuda Técnica]] — deuda técnica identificada
- [[17 - App Satélite]] — pendientes del satélite
- [[01 - Arquitectura General]] — protocolo de cambios
