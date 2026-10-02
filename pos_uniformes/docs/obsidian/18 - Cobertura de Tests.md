---
tags: [estado, pos-uniformes]
---

# Cobertura de Tests

**Cobertura general:** ~91% (actualizado 2026-04-21)
**Archivos de tests:** ~270 · **2,066 tests** (actualizado 2026-09-10)
**Comandos (desde `Playground 2`):** mientras construyes, solo el archivo que tocas o `… -m pytest pos_uniformes/tests --fast -q` (~4 s, solo puros) · antes de subir, todo en paralelo: `… -m pytest pos_uniformes/tests -q -n 6 --dist load` (**~28 s**; en serie eran 80 s). Necesita `pytest-xdist` (`requirements-dev.txt`).

> [!tip] Por qué `-n 6 --dist load` (medido 2026-09-10)
> Serie 80 s · `-n 4 --dist loadfile` 59 s · `-n 6 --dist load` 27–32 s. El cuello era un solo archivo: `test_main_window_snapshot_cache.py` arma la ventana del POS 81 veces y tarda 41 s él solo; repartido por archivo se quedaba en un proceso. Por prueba se reparte. Cada proceso trae su `QApplication`, así que las pruebas de Qt se estorban menos. Con 8 procesos no mejora (4 núcleos rápidos). **Regla:** la suite completa solo antes de subir, no a cada rato.

> [!success] Suite saneada (2026-09-08)
> `conftest.py` (befff3c3…2bca1f20): fuerza `127.0.0.1/pos_uniformes_test` (aborta si la base no es `*_test`), `--fast` ni siquiera importa archivos Qt/DB, semilla mínima en la base de prueba, ningún test levanta hilos de Postgres ni espera un clic, reloj congelado donde toca. Hay que migrar la base de prueba local tras cada migración (`alembic upgrade head` con `POS_UNIFORMES_DB_HOST=127.0.0.1 POS_UNIFORMES_DB_NAME=pos_uniformes_test`).

> [!info] Tests nuevos del 2026-09-10
> `test_analitica_libreta.py` (15) · `test_analytics_libreta_panel.py` (6) · `test_demanda_service.py` (19) · `test_demanda_no_estorba.py` (7) · `test_analytics_demanda_panel.py` (5) · `test_pestanas_ocultas.py` (10).
>
> Dos patrones que conviene repetir:
> - **Los dos estados de un interruptor.** `EXISTENCIA_CONFIABLE` se prueba apagado (lo de hoy) y encendido (lo de después), para que el día que se mueva no se rompa nada en silencio.
> - **El caso feo explícito.** Anotar con el disco lleno, sin carpeta de datos o con la base caída: la venta debe seguir. Una señal perdida no vale una venta.
> Tests nuevos del 2026-09-08: cámaras (`test_dvr_settings_cache_service`, `test_camera_wall_dialog`, `test_camera_playback_dialog`, `test_libreta_ver_momento`), afluencia (`test_afluencia_conteo`, `test_afluencia_service`, `test_libreta_afluencia`), caja/nómina (`test_corte_caja_service`, `test_nomina_service`, `test_corte_caja_dialog`, `test_historial_pagos`, `test_pendientes_service`, `test_equipo`, `test_empleada_por_dia`, `test_retiros`, `test_horario_tienda`), Telegram (`test_resumen_diario`, `test_telegram_bot`), updater (`test_satellite_update_version`). Lección: `services/caja_service.py` ya existía (caja del POS principal) — el nuevo es `corte_caja_service.py`.

> [!success] La suite completa corre LIMPIA de punta a punta (2026-07-08)
> **1,175 pasan · 0 fallan · 77 s** (pytest, offscreen, `-p no:cacheprovider`).
> Ese día se reparó TODA la deuda: 2 tests de logout que colgaban (QDialog custom
> de `1db1d12`), 21 de bodega (regexp portable + API de códigos vigente), ~10 de
> timezone aware, 6 del satélite, y ~12 de fixtures/expectativas viejas.
> El único cambio de producto por tests: `.op("~")` → `.regexp_match()` en
> `bodega_service._siguiente_codigo` (idéntico en Postgres, portable a SQLite).
> Además destapó y reparó un bug real: página Buscar del satélite perdida en
> `4d13bea` (ver [[21 - Sesión de Trabajo]]).
> Comando: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest pos_uniformes/tests`
> (desde `Playground 2`).

---

## ✓ Dominios con 100% de cobertura

| Dominio | Servicios |
|---------|-----------|
| Analítica | `analytics_snapshot`, `analytics_layaway`, `analytics_stock`, `analytics_top_clients`, `analytics_top_products` |
| Apartados | Todos los `layaway_*` |
| Caja | `caja_service`, `cash_session_*` |
| Empleadas | Todos los `employee_*` |
| Historia | `history_snapshot_service` |
| Inventario | `inventario_service`, `inventory_count`, `inventory_label`, `inventory_overview`, `inventory_snapshot` |
| Conteo (panel) | `conteo_service` (6 tests, 2026-05-30 — scope tienda, ajuste negativo, filtro por nivel) |
| Bodega | `bodega_service` ⚠️ 4 tests rotos (usan `crear_ubicacion`, API vieja) — ver [[19 - Deuda Técnica]] |
| Ventas recientes | `recent_sale_*` |
| Búsqueda | `search_filter_service`, `search_suggestion_service` |
| Uniformes deportivos | `sports_uniform_pricing`, `sports_uniform_size` |
| Promo manual | `manual_promo_service`, `manual_promo_flow_service` |
| Presupuestos | `presupuesto_service` |
| Venta | `venta_service` |
| Escáner cliente | `scanned_client_flow_service` |
| Backup | `backup_service` |

---

## ⚠️ Dominios con cobertura parcial

| Dominio | Cobertura | Sin tests |
|---------|-----------|-----------|
| Configuración | ✅ 100% | `marketing_audit_service` resuelto 2026-04-14 |
| Presupuestos completo | ✅ 100% (9/9) | resuelto 2026-04-14 |
| Venta completo | 91% | algunos `sale_*` auxiliares |
| Catálogo | ✅ `catalog_mutation_service` ya tenía 4 tests | — |
| Configuración negocio | 66% | parcial en `business_settings_service` |

---

## ✓ Servicios sin tests que ya fueron cubiertos (sesión 2026-04-14)

| Servicio | Tests agregados |
|---------|----------------|
| `loyalty_service` | ✓ 32 tests |
| `auth_service` | ✓ 17 tests |
| `catalog_mutation_service` | ✓ ya tenía 4 tests (falso negativo) |
| `user_service` | ✓ 20 tests |
| `compra_service` | ✓ 14 tests |
| `marketing_audit_service` | ✓ 7 tests |
| `sale_discount_service` | ✓ 22 tests |
| `sale_stock_policy` | ✓ 3 tests |

## ✗ Servicios aún sin tests (baja prioridad — no bloquean cierre legacy)

| Servicio | Motivo para diferir |
|---------|---------------------|
| `customer_card_service` | Genera imágenes — requiere mocks de PIL/Qt |
| `quote_kiosk_lookup_service` | Thin wrapper sobre queries |
| `catalog_service` | CRUD complejo — requeriría BD real o mocks extensos |
| `client_service` | Similar a catalog_service |
| `catalog_audit_service` | Thin audit logger |
| `settings_employee_action_service` | Bridge de UI a servicios ya testeados |
| `supplier_service` | CRUD simple, bajo riesgo |
| `bootstrap_service` | Solo para setup inicial, no toca producción |
| `business_settings_service` | Config singleton — alto acoplamiento con BD |

---

## Tests de UI helpers

Existen ~80+ tests de UI helpers para `main_window.py` y helpers asociados:
- `test_main_window_snapshot_cache.py` — 80 tests (de 46 → 80 en 2026-04-21)
  - Auditoría de bugs de inventario: riesgos 1-11 cubiertos
  - Paginación, selección, duplicar, ajuste masivo, menú contextual
- `test_inventory_filter_helper.py` — filtros incluyendo precio y conteo
- `test_inventory_selection_helper.py` — resolución de variante seleccionada
- `test_catalog_action_feedback_helper.py` — labels de confirmación/resultado

---

## Prioridad para agregar tests

### ✅ Completado (2026-04-14)
1. ~~`loyalty_service`~~ — 32 tests
2. ~~`auth_service`~~ — 17 tests
3. ~~`catalog_mutation_service`~~ — ya tenía 4 tests
4. ~~`user_service`~~ — 20 tests
5. ~~`compra_service`~~ — 14 tests
6. ~~`marketing_audit_service`~~ — 7 tests
7. ~~`sale_discount_service`~~ — 22 tests
8. ~~`sale_stock_policy`~~ — 3 tests

### Completado adicional (2026-04-14)
- `catalog_local_cache_service` ✅ 10 tests
- `satellite_startup_service` ✅ 5 tests
- `quote_document_view_service` ✅ 5 tests

### Completado (2026-04-17)
- `satellite_favorites_service` ✅ 5 tests (load vacío, roundtrip, toggle, JSON corrupto, seed no sobreescribe)

### Completado (2026-06-11) — Venta Rápida satélite
- `test_quick_sale_add_sku.py` ✅ 9 tests — add_sku (4), logout/ESC (2), apartado 2 copias + mínimo 25% (3)

### Completado (2026-06-17, commiteado 2026-07-03 en `b63fcf5`)
- `test_ticket_print_queue.py` ✅ 9 tests — cola inyectable, cierre seguro de diálogo sin RuntimeError; corren en 0.02s sin Qt
- `test_business_info_cache_service.py` ✅ 3 tests — guardar/cargar info negocio, fallback None
- `test_quick_sale_print_tickets.py` ✅ 8 tests — un diálogo unificado para múltiples copias; tickets offline sin pegar a DB

### Completado (2026-07-03) — sesión de estabilización
- `test_satellite_excepthook.py` ✅ 6 tests — formato/append/truncado del log, install satélite y `install_gui_excepthook(log_path)` para el POS principal
- `test_quote_cart_index_guard.py` ✅ 8 tests — `normalize_cart_row_index` rechaza bools (bug `checked`→fila 0) + regresión a nivel ventana
- `test_quote_satellite_offline_guards.py` ✅ 3 tests — filtros y escaneo rápido no tocan DB en offline; ruta online intacta
- `test_satellite_restart_lock.py` ✅ 2 tests — `_release_instance_lock` suelta el candado para la instancia nueva
- `test_school_link_dialog_status.py` ✅ 2 tests — `_clear_status` traga RuntimeError de widget muerto
- `test_conteo_print_dialog.py` ✅ 1 test — delega en `open_tickets_print_dialog` con `unit_label="hoja"`
- `test_quote_guided_catalog_helper.py` ✅ 28 tests — +8 nuevos (`build_search_price_groups`, `favorites_variant_sort_key`) y **5 reparados** (expectativas al `_PIEZA_ORDER` vigente; fallaban desde 2026-05-24)
- `test_quick_sale_add_sku.py` ✅ 11 tests — +2 (log de error DB en gate, cantidad corrupta cae a 1)
- **Corrida completa del área satélite: 86 tests en verde**

### Completado (2026-04-29)
- `inventory_count_service` ✅ +2 tests — modo `add_to_system` en `accumulate_inventory_count_scan`
  - `test_accumulate_inventory_count_scan_add_to_system_starts_from_system_stock`
  - `test_accumulate_inventory_count_scan_add_to_system_continues_accumulating`

### Completado (2026-04-18)
- `inventory_filter_helper` ✅ actualizado con `conteo_filter` y `stock_minimo`
- `inventory_table_row_helper` ✅ actualizado con columna "Ult. conteo" (9º campo)
- `inventory_snapshot_service` ✅ actualizado con `ultimo_conteo_at` y `stock_minimo` (posiciones 19 y 20)

### Completado (2026-04-21)
- `inventory_filter_helper` ✅ actualizado con `precio_filter` y `precio_text_filter`
- `inventory_selection_helper` ✅ 2 nuevos tests para fallback desactivado cuando inventory_variant_id está presente
- `catalog_action_feedback_helper` ✅ 4 nuevos tests para `build_variant_delete_label` / `build_product_delete_label`
- `test_main_window_snapshot_cache` ✅ +34 tests (auditoría riesgos 1-11, duplicar, paginación, set_combo_value, sync_none)

### Puede esperar
- `supplier_service`
- `bootstrap_service`
- `customer_card_service`
- `quote_kiosk_lookup_service`

---

## Ver también
- [[19 - Deuda Técnica]] — contexto completo de mejoras pendientes
- [[20 - Pendientes y Fase 5]] — plan de cierre

## Tests nuevos (2026-09-09 / 10)

| Test | Cubre |
|------|-------|
| `test_historial_cortes` | Historial del dueño: periodo de cortes viejos, filas, totales, reimpresión congruente, borrar corte, columnas ocultas |
| `test_alertas` | Cola `alerta_telegram`, textos, vigilante (cierre sin corte, fuera de horario), enganches de corte y retiro |
| `test_dia_calendario` | Detalle del día del kiosko y pago por gafete |
| `test_telegram_vigia` · `test_servidor_pwa_vigia` | Vigías del bot y de la PWA (latido, decisión, arranque) |
| `test_supervisor` | Supervisor único: decisión con calma, vuelta, bandera de reinicio, servicios reales |
| `test_search_filter_service` | …y la normalización con caché (mismo resultado, un solo cálculo por texto) |
| `test_conteo_jornada_ui` · `ImprimirDejaHuellaTests` | Imprimir anota la jornada, se pega a la abierta, el aviso dice quién/cuándo y no imprime por defecto |
| `test_pwa_index_html` | Ningún id repetido en el HTML estático de la PWA; la hoja y el selector de básicos con su propio div; barra superior y listas de navegación coherentes |
| `test_limpiar_nombres_productos` · `test_separar_escuela_por_nivel` · `test_fundir_productos` | Rediseño fase 1: nombres sin sufijo y con mayúsculas, choques, plantel separado por nivel (SKUs, ligas, jornada partida), fundir con existencia sumada |
| `test_reubicar_conteos_por_prenda` | El plan ve lo ajeno, mover deja la destino como la origen, crea jornada si no hay, no toca lo aplicado |
| `test_conteo_mapa_service` | Cifras por escuela/básicos, detalle con semáforo por talla, HTML con las tres capas; widget nativo del kiosko: una generación a la vez y no antes de un minuto, navegación por capas (`CapaMapa` → `CapaDetalle` → `Prenda.alternar()`, buscador, mosaicos contados), sección con *Ver tabla*, mosaicos con "En proceso · quién" |
| `test_corte_pagos_de_hoy` · `LoQueYaSalioDelCajonTests` | Desglose con fecha; desmarcar regresa el monto al esperado y deja `en_cajon=False`; todo marcado resta como siempre |
| `test_api_movil` | …y marcas recientes por persona + quitar + "sí vino" desde el celular |
| `test_api_bodega_movil` | …y etiquetas al llegar (una por pieza, solo con la casilla) + `llegadas` del dueño (agrupadas, 403 a empleadas) |
| `test_nombres_empleadas_service` | `mostrar` (código solo, entre paréntesis, en frase, corto), caché, copia local, `invalidar` |
| `test_school_tariff_service` | La lista de escuelas del tarifario en 2 consultas; niveles múltiples, sin nivel, sin productos, inactivas |
| `test_postactualizacion` | Tareas esperadas/obsoletas, idempotencia por `INFRA_VERSION`, nunca detiene la actualización; **pasos únicos** (orden, solo se anotan los que salen bien, reintento, `--pasos-unicos` solo desde actualizar) |
| `test_meilisearch_search_flow` (ampliado) | `sku_num`, `talla_orden`, campos nuevos del índice, ranking |
| `test_libreta` (ampliado) | Tarjeta del ciclo, ajustes en el efectivo (oficial vs real), lista de la empleada |
| `test_libreta_privados` | Solo el dueño oculta · el efectivo no se puede ocultar · ocultar/mostrar · todo el periodo · lo que ve el encargado |
| `test_corte_propuesta` | Propuesta del día, recordatorio único, `--hacer`, `/nocorte`, `/corte 5000`, `sintarjeta` |
| `test_corte_remoto` (ampliado) | `TicketConRetiroTests`: el papel cuadra con la cifra pedida y `sintarjeta` oculta los cobros |
| `test_tareas_windows_sin_ventana` | Ninguna tarea invoca un `.bat` directo (todo por `correr_oculto.vbs`) |
| `test_api_movil` (ampliado) | Corte del dueño desde el celular, privados, payloads de encargado y dueño, ciclo y movimientos |
| `test_calendario_empleadas` · `test_dia_calendario` (ampliados) | Las faltas en el calendario compartido |
| `test_revision_service` | `sugerir` (4 semanas, urgente, demanda como venta perdida, sin datos), `revisar` sobre SQLite (ventas por SKU desde el conteo anterior, apartados sí / devoluciones no, pedido anterior), `guardar_pedidos` solo dueño, hoja de pedido, historia de la talla |
| `test_conteo_jornada_ui` (ampliado) | Revisar nuevo (filtro, editar Pedido, hoja, aplicar guarda pedido, historia), selector con `EN PROCESO` y `Ver todas`, `_conteos_ofrecer_seguir` |
| `test_conteo_jornada_service` (ampliado) | Una abierta por escuela, cualquiera la sigue, conflictos al guardar, `quien` en la hoja, `UltimoConteo.reciente` |
| `test_conteo_subir_dialog` (ampliado) | El kiosko pregunta ante un choque y no duplica |
| `test_api_conteos_movil` (ampliado) | `en_proceso`, abrir repetida devuelve la existente, conflictos con `reemplazar`, `reciente` |
| `test_afluencia_dibujar_lineas` | Sombra del lado de la tienda, dos clics hacen la línea, guardar, recarga en caliente del contador |
| `test_bodega_movil_service` · `test_api_bodega_movil` | Llegó mercancía (al piso / parte a caja), pasar al piso, corregir caja, cajas y prendas, solo el dueño |
| `test_nomina_service` (ampliado) | Faltas netas: faltó y vino en su descanso = 0; el extra solo compensa dentro del ciclo |
| `test_calendario_empleadas` (ampliado) | `DescansoMovidoTests`: descanso en otro día mueve el fijo, quitar lo regresa, falta no mueve, por_dia no aplica, Telegram igual |
| `test_conteo_jornada_ui` / `test_conteo_jornada_service` (ampliados) | Eliminar y Reasignar jornadas a medias según quién mira; historia de la escuela |
| `test_corte_pagos_de_hoy` | El corte del dueño ofrece los pagos que tocan hoy, los registra dentro del periodo y los descuenta; desmarcado no se registra |
| `test_libreta_descuenta_stock` | La venta baja el stock por talla, puede quedar negativo, no descuenta dos veces, apartado sí / abono no, sku desconocido se ignora, un fallo no tumba la venta, borrar la regresa |
| `test_libreta` (`ReimprimirDesdeLibretaTests`, ampliado) | Reimprimir desde el detalle para todas, sin on_printed; abonos sin ticket |
| `test_conteo_jornada_service` / `test_conteo_jornada_ui` (ampliados) | `tablero_conteos`: todas las escuelas en orden (en proceso, recientes, nunca) y su pintado con colores |
| `test_revision_service` (`ComparativoTests`) · `test_conteo_jornada_ui` (ampliado) | Comparativo: había / hay / cambio / vendidas / sin explicar (faltan y sobran), primer conteo sin comparación; el diálogo se abre con la jornada aplicada, desde Revisar y con doble clic en el tablero |
| `test_conteo_jornada_ui` (`RevisionDialogTests`, reescrito) | Revisar compacto: tarjetas que filtran, fila de prenda, Qué hacer, Pedido en la columna 4, "por qué" al tocar, Ver todas las columnas |

> [!warning] Segfault "Garbage-collecting … eventFilter" (2026-09-13)
> Un worker de xdist moría en cualquier test: una `QuoteSatelliteWindow` que otro test dejó suelta se recolectaba con Qt aún usándola como filtro de eventos. El `conftest` guarda referencia viva a cada ventana satélite construida y las cierra en `pytest_sessionfinish`. Si vuelve a aparecer un crash de worker sin traceback útil, buscar ventanas Qt sueltas.

Suite completa al 2026-09-10: **1,989 en verde** (~70 s). `pytest --fast`: 711 (~4 s).
