---
tags: [estado, pos-uniformes]
---

# Deuda Técnica

> Hallazgos del mapeo profundo del proyecto.
> Ordenados por impacto y riesgo operativo.

---

## 🔴 Dos fuentes de verdad: el Panel no usa los servicios (2026-09-22)

`scripts/generar_panel_uniformes.py` tiene **2,981 líneas**, escribe **40 consultas SQL crudas** y **no importa un solo servicio** de `services/` (el POS tiene **167**). Cada regla que el Panel muestra —stock, precio, cobertura, qué cuenta como básico— está definida **dos veces**.

Prueba viva: el commit `90ff5912` sacó los conjuntos de los totales con `conjunto_service.filtro_sin_conjuntos`; en el generador la misma regla vive como `NOT IN (SELECT conjunto_id FROM conjunto_componente)`, **duplicada en dos lugares del SQL**. Nadie garantiza que sigan diciendo lo mismo dentro de un mes.

Agravantes:
- El HTML generado **se commitea** (`a9d5ac8f`, "regenerado el 20/09"): la foto viaja en git y se confunde con estar al día.
- El Panel corre con **dos relojes**: Resumen/Piezas/Tarifarios/Disponibilidad son foto; Conteo es vivo por el bridge.
- **Cero tests** del generador. Por eso el desfase no avisa.

Plan: Fase 2 de [[39 - Brújula]] — cambiar 40 consultas por 40 llamadas a servicio, de menos a más riesgo (Resumen → Piezas → Tarifarios → Disponibilidad). Detalle en [[25 - Panel de Uniformes]].

> **Módulos nuevos congelados hasta cerrar esta fase.** Cada módulo que nazca antes se trae su propia copia de la verdad.

---

## 🔴 La deuda más cara hoy: el inventario no se mantiene solo (2026-09-10)

`stock_actual` **no baja al vender**. El único camino que lo descontaba (`venta_service.registrar_salida_venta`) pertenece al POS viejo y está muerto desde marzo. El último movimiento de inventario de cualquier tipo es del **16 de julio**; de ahí en adelante todo lo vendido salió sin registrarse.

Consecuencias en cadena:
- El número del sistema está **inflado** y no sirve para prometerle nada a un cliente.
- La mitad de [[35 - Demanda No Atendida]] que depende del stock queda **corta**, y por eso su parte visible está apagada.
- Contar el catálogo no arregla nada por sí solo: se vuelve a desfasar en días (360 SKUs distintos se movieron en 9 días).

Recomendación, cifras y orden de los pasos en [[07 - Servicios - Catálogo e Inventario]]. **Resuelto el 2026-09-14:** la venta ya descuenta (`118a67f2`) y las ventas viejas se restan solas en la próxima actualización (paso único). Queda contar lo que se mueve y prender `EXISTENCIA_CONFIABLE`.

---

## 🟢 Rendimiento — medido y afinado (2026-09-17)

Perfilado el constructor del kiosko (`cProfile`, Mac, DB local): 1.02 s → 0.84 s. Lo que se arregló:

| Dónde | Antes | Ahora |
|---|---|---|
| `_inject_linked_products` (flujo guiado) | normalizaba cada general × cada escuela con ligas: 0.38 s, en cada cambio de escuela/nivel | generales normalizados una vez: 0.05 s |
| `_refresh_conteo_banner` | consulta Postgres en el hilo de UI cada 10 min (Wi-Fi → pantalla congelada) | hilo `conteo-banner` + señal `_conteo_banner_ready`; una a la vez |
| `list_schools_for_tariff` | 1 + (1–2 por escuela) ≈ 100 consultas al abrir Tarifarios | 2 consultas |
| `movimiento_inventario.referencia` | sin índice: cada venta (`descontar_stock`) y cada borrado recorrían la tabla | índice (`ef5a6b7c8d9e`) |
| `search_filter_service._normalize_search_fragment` (POS) | 285,000 normalizaciones NFKD al arrancar (y en cada refresco de catálogo/inventario): 0.85 s | `lru_cache` + atajo ASCII: 0.16 s. POS 1.9 s → 1.2 s; `refresh_all` con caché caliente 0.65 s |
| `tablero_conteos` | 85 consultas (15/09: 60) | ~10: lo capturado en 1 consulta y el alcance de todas las escuelas en 2 (`alcances_en_lote` → `obtener_variantes_para_conteo_varias`), medido 48 escuelas: 96 → 2 |

También perfilado `MainWindow` (POS): lo que queda es construir widgets Qt (~0.2 s) y los dos snapshots de catálogo e inventario (~0.2 s cada uno, CPU en Python); se puede seguir ahí si algún día molesta, pero el POS corre en la principal con Postgres local, no por Wi-Fi.

**Cómo medir otra vez:** `scratchpad/perfil.py` de la sesión (cuenta consultas y tiempo SQL por función con `before_cursor_execute`); el AST-scan de "query dentro de for" encontró los N+1. El servidor de la tienda no respondía ese día (la `.10` era otro aparato), así que los tiempos son de la Mac.

**Propuestas que cambian comportamiento (decide Daniel):**
- ~~Escaneo en venta rápida cache-primero~~ **hecho 2026-09-17** (`QuickSaleWidget._lookup_sku`): en memoria primero, Postgres solo si el SKU no está (producto recién dado de alta); sin conexión, solo cache. Un cambio de precio tarda hasta 5 min en llegar al kiosko (o al instante si se refresca el catálogo). Tests en `test_quick_sale_add_sku`.
- **Afluencia a 2 fps** (`fps_proceso`): 4 cámaras × 4 fps de YOLO en la CPU del servidor, que también corre Postgres, la PWA y el POS. A 2 fps una persona caminando sigue cruzando la línea varias veces; medir CPU antes.
- API `movil.py` vista del dueño: ~3 consultas por empleada (horario + comisiones); son 6 empleadas, tolerable.

## 🟡 Código vivo que ya nadie ve (2026-09-10)

Cuatro pestañas quedaron ocultas ([[03 - Mapa de Módulos UI]]) pero su código sigue completo y se sigue construyendo al arrancar: `cashier_view`, `quotes_view`, `layaway_view`, `products_view` y los servicios detrás.

Es **decisión consciente, no descuido**: fueron la base del sistema y los datos siguen ahí. Lo que conviene recordar es que ese código ya no lo ejercita nadie en producción, así que un cambio que lo rompa no se va a notar hasta que alguien vuelva a prender una pestaña.

---

## ✅ Resuelto en App Satélite (2026-04-15)

| Deuda | Solución |
|-------|----------|
| 9 atributos de estado sueltos (`guided_mode`, `guided_selected_*`) | `GuidedFlowState` dataclass con `reset()` — `self._gfs` |
| 3 métodos `_rebuild_guided_*` idénticos | `_rebuild_guided_hrow()` helper genérico |
| `_refresh_guided_browser` — 110 líneas monolíticas | Split en 4 métodos: orchestrador + `_correct_guided_state` + `_apply_guided_view` + `_apply_guided_section_visibility` + `_apply_guided_product_section_labels` |
| CSS inline de 494 líneas en `_apply_styles` | Extraído a `ui/styles/satellite_styles.py` — `_apply_styles` queda en 2 líneas |

**Resultado:** `quote_satellite_window.py` bajó de 4,064 → 3,607 líneas (−457).

---

## ✅ Deuda resuelta — App Satélite (2026-04-15)

> Estado final: **3,652 líneas** — estructura interna limpia, cero monkey-patches.

| Deuda | Solución |
|-------|----------|
| SAT-3: Lambda con tupla en `_show_cart_popup` | `_on_remove` función nombrada |
| SAT-2: Monkey-patching de `mouseDoubleClickEvent` (2 lugares) | `_DoubleClickButton` + `_DoubleClickFrame` con señal `double_clicked` |
| SAT-1: `_build_guided_page` 275 líneas | Split en `_build_guided_steps_card()` + `_build_guided_detail_card()` |
| SAT-4: `_build_editor_panel` 126 líneas | Split en `_build_editor_form_panel()` + `_build_editor_cart_panel()` + `_make_form_label()` |

---

## 🔴 Prioridad Alta

### 1. ~~`loyalty_service` sin tests~~ ✅ Resuelto 2026-04-14
- 32 tests agregados — coerce_level, visual_spec, default_level_for_client_type, resolve_initial_level, discount_for_level, assign_level, evaluate_auto_level, recalculate_all_clients

### 2. ~~`auth_service` sin tests~~ ✅ Resuelto 2026-04-14
- 17 tests agregados — hash_password, verify_password (pbkdf2 + texto plano legacy), authenticate (upgrade automático de hash)

### 3. Lógica de negocio en `ui/main_window.py`
El archivo tiene:
- **45 `raise ValueError`** — validaciones que deberían vivir en servicios
- **34 `select()` directos** — queries que deberían estar en servicios de lectura
- **46 `session.commit()`** — operaciones de BD fuera de la capa de servicio
- **137 métodos de negocio** (`_handle_*`, `_validate_*`, `_apply_*`)

Esto no es urgente de resolver ahora, pero **nunca debe crecer más**.

---

## 🟠 Prioridad Media

### 4. `catalog_product_dialog.py` — 1,852 líneas con lógica interna
- El diálogo de alta/edición de productos tiene demasiada lógica dentro
- Debería extraerse a `catalog_product_action_service.py`
- **Acción:** Identificar qué lógica sacar sin romper el flujo

### 5. ~~`inventory_count_dialog.py` — extracción completada~~ ✅ Resuelto 2026-05-05
- `get_inventory_count_apply_error()` extraído al servicio — valida si el conteo puede aplicarse
- `build_inventory_count_confirm_text()` extraído al view helper — texto del diálogo de confirmación
- `_handle_confirm` en el diálogo simplificado: de 37 → 22 líneas sin lógica inline
- Commit `5141005` — 4 tests nuevos, 16/16 OK

### 6. ~~`catalog_mutation_service` sin tests~~ ✅ Resuelto 2026-04-14
- Ya tenía 4 tests existentes (falso negativo en el mapeo inicial)

### 7. Superposición entre servicios de texto y documentos
- `sale_ticket_totals_service` + `sale_document_service` hacen overlap en cálculo de totales
- `sale_discount_service` + `sale_client_discount_service` podrían consolidarse
- Varios `*_text_service` para generar strings (quote, sale, layaway) con patrón muy similar
- **Acción:** Documentar cuál es el canónico de cada grupo antes de consolidar

---

## ✅ Bug API get_db sin commit cerrado (2026-05-02)

`api/dependencies.py` usaba `with get_session() as session: yield session`. Al salir el context manager llama `session.close()` sin commit — PostgreSQL descartaba silenciosamente todos los cambios (crear/actualizar/cancelar presupuesto desde la app móvil). Corregido con patrón estándar FastAPI: `commit()` en éxito, `rollback()` en excepción, `close()` siempre. Commit `99b2fce`.

---

## ✅ Bug datetime naive/aware cerrado (2026-05-02)

Todos los servicios que escriben a columnas `DateTime(timezone=True)` usaban `datetime.now()` (naive), lo que causa `TypeError` en producción al comparar con fechas PostgreSQL que llevan `tzinfo: America/Mexico_City`.

| Servicio | Puntos corregidos |
|----------|------------------|
| `presupuesto_service` | 6 — vigencias, emitido_at, cancelado_at, convertido_at |
| `venta_service` | 4 — confirmada_at × 2, cancelada_at, reference_time |
| `compra_service` | 1 — confirmada_at |
| `apartado_service` | 3 — liquidado_at, entregado_at, cancelado_at |
| `loyalty_service` | 1 — review_time fallback |

`backup_service` y `customer_card_service` conservan `datetime.now()` (operaciones de sistema de archivos y presentación UI, no escritura a BD). Commits `3132efc` + `b7847a4`. Checkpoint `validated-tests`.

---

## 🟠 Suite de tests desincronizada (descubierto 2026-05-30)

Al correr la suite completa aparecieron **~17 tests fallando** y **1 que colgaba la suite entera**. NO son regresiones nuevas — son tests que no se actualizaron cuando cambió el código. Vale una tanda dedicada.

| Grupo | Causa | Acción |
|-------|-------|--------|
| ~13 tests de timezone (`analytics_period`, `cash_session`, `layaway`, `catalog`, `inventory_overview/snapshot/table_row`, `history_filter`, `main_window_snapshot`…) | Esperan `datetime` **naive**, pero el código ahora devuelve **aware** (efecto del fix naive/aware del 2026-05-02) | Actualizar los `assertEqual` esperados a aware (patrón repetido, arreglable en bloque) |
| `test_bodega_service.py` (4 tests) | Usan `BodegaService.crear_ubicacion`, método **que ya no existe** (API cambió) | Reescribir con la API actual o sembrar ORM directo |
| `test_inventory_label_dialog` / `_batch_dialog` / `_service` | Mocks de `render_label`/`print_label` sin `show_price`/`mode` (agregados el 23-may, commit `cc21062`). El de batch **colgaba la suite** al disparar un `QMessageBox.warning` no mockeado | ✅ **Resuelto 2026-05-30** — mocks alineados a la firma real |

> [!warning] La suite no corre limpia de punta a punta
> El test del batch dialog colgaba el `pytest` completo (esperaba interacción en un `QMessageBox` modal en modo offscreen). Ya está arreglado, pero quedan los ~17 de timezone + 4 de bodega. Mientras tanto, para validar un cambio puntual conviene correr **solo los tests del área tocada**, no la suite entera.

---

## ✅ Bugs de presupuestos cerrados (2026-04-23)

| Bug | Solución |
|---|---|
| Bug 1: emitir con vigencia vencida | `emitir_presupuesto()` + `_apply_quote_payload()` validan `vigencia_hasta < now()` |
| Bug 1b: bypass por `actualizar_presupuesto` | Validación movida a `_apply_quote_payload` — cubre todos los caminos |
| Bug 3: estado CONVERTIDO inalcanzable | `convertir_presupuesto()` + `convert_quote_to_cart()` + botón "Cobrar presupuesto" en UI |

---

## ✅ Consolidaciones completadas (2026-04-23)

| Consolidación | Resultado |
|---|---|
| `_normalize_text` duplicado en 5 archivos | `utils/text_normalization.py` con `normalize_text` y `normalize_text_unicode` |
| 3 funciones idénticas de resolución de ID | `resolve_selected_settings_row_id` genérico en `settings_crm_selection_helper.py` |
| Lógica de semáforo de stock en 4 archivos | `utils/stock_tone_helper.py` con umbral `_LOW_STOCK_THRESHOLD = 3` centralizado |

## ✅ Errores mypy estructurales corregidos (2026-04-23)

6 errores reales (de 687 totales — el resto es ruido de `dict[str, object]`):
- `dashboard_summary_helper` — tuple variable-length
- `product_templates` — `.get()` sobre `object`
- `analytics_payment_helper` — atributos en `object`
- `inventory_table_row_helper` — `tzinfo/replace` en `object`
- `scanned_client_flow_service` — posible `int(None)`
- `config.py` — `getenv` con default `None`

---

## 🟡 Prioridad Baja / Cosmética

### 8. 104 helpers de UI — algunos podrían consolidarse
- El número de helpers es alto pero el patrón es consistente
- No hay duplicados obvios, pero sí helpers pequeños que se podrían agrupar
- **Acción:** Revisar durante Fase 5, solo consolidar si hay duplicación real

### 9. Cadena de dependencias en servicios de documento
```
quote_document_view_service
  → quote_text_service
  → sale_document_view_service
  → sale_ticket_text_service
  → business_print_settings_service
```
No hay ciclos pero la cadena es larga. No rompe nada pero puede ser difícil de seguir.

### 10. ~~`user_service` y `compra_service` sin tests~~ ✅ Resuelto 2026-04-14
- `user_service`: 20 tests — validación admin, create_user, toggle_active, change_role, change_password
- `compra_service`: 14 tests — permisos, validación items, crear_borrador, confirmar_compra

---

## Lo que está bien y NO debe tocarse innecesariamente

| Aspecto | Estado |
|---------|--------|
| Service layer | ✓ Bien estructurado, ~60 servicios con responsabilidades claras |
| Sin dependencias circulares | ✓ Grafo acíclico confirmado |
| Auditoría centralizada | ✓ `*_audit_service`, `*_action_service` pattern consistente |
| Snapshots puros | ✓ Servicios de lectura devuelven dataclasses, no modelos ORM directos |
| Separación ORM/lógica | ✓ Modelos en `models.py`, lógica en servicios |
| Validación temprana | ✓ Validaciones en servicios, no en BD |
| Feature flags | ✓ `sale_stock_guard_enabled()`, `allow_negative_sale_stock()` |

---

## Regla para la versión legacy

> El objetivo NO es resolver toda la deuda técnica.
> El objetivo es **documentarla, no empeorarla, y cerrar lo que está abierto**.
>
> - No abrir refactors nuevos en `main_window.py`
> - No mover más de un dominio a la vez
> - ~~Tests para `loyalty_service` y `auth_service` son críticos antes del cierre~~ ✅ Resuelto

---

## Ver también
- [[18 - Cobertura de Tests]] — detalle de qué tiene tests
- [[20 - Pendientes y Fase 5]] — plan de cierre de la versión

## Nunca editar una migración ya aplicada (2026-09-22)

Edité `2d3e4f5a6b7c` para agregarle una columna después de que Daniel ya la había corrido en la PC principal: allá la tabla quedó sin la columna y el POS tronaba al abrir Uniformes por escuela. Lo correcto: **migración nueva** (`3e4f5a6b7c8d`), y otra para reparar los datos que quedaron mal (`4f5a6b7c8d9e`). Antes de tocar una migración, `select version_num from alembic_version` en producción.

## Conteos: de 147 consultas a 30 (2026-09-22)

El refresco pedía el avance jornada por jornada (3 consultas × 35 por revisar = 99) y calculaba dos veces el alcance de las mismas escuelas. Arreglado con `avances_en_lote`, un `cache` compartido entre `tablero_conteos` y `alcances_en_lote`, y `lo_que_toca(filas=...)`. Además la lectura se fue a un hilo. Patrón a repetir: **si una vista pide N veces lo mismo cambiando un id, hay (o debe haber) una versión en lote**.

## Qt en las pruebas: nunca `QTimer.singleShot` suelto ni `QTest.qWait` (2026-09-22)

Dos causas de segfault al azar en la suite paralela, las dos arregladas:
1. `QTimer.singleShot(ms, self._metodo)` en un diálogo dispara aunque el diálogo ya esté borrado → usar `QTimer(self)` (muere con la ventana).
2. `QTest.qWait(...)` en un test bombea el bucle de eventos y deja entrar cosas de otras pruebas → disparar el timer a mano (`timer.stop(); timer.timeout.emit()`).

Cómo se diagnosticó: la suite fallaba con `-n 6 --dist load` y pasaba en serie, con `-n 4` y con `--dist loadfile`. La prueba decisiva fue agregar 4 tests vacíos al commit **anterior**: también se caía, así que no era del cambio nuevo sino del reparto.

## Abierto al 2026-10-02

| Qué | Por qué importa |
|---|---|
| **`main` quedó en el 11 de julio** | Todo vive en `chore/reorganizacion-repo`, 455 commits adelante. Quien clone el repo limpio se lleva el código de julio |
| **La PC principal sirve la base por Wi-Fi** | El Ethernet tiene un cable conectado a nada. Explica la lentitud del kiosko y la fragilidad de la red. Ver [[22 - Referencia Rápida]] |
| **El DNS del Wi-Fi es IPv6 puro** | Sin IPv6 funcionando, nada resuelve: ni GitHub ni Telegram |
| **El cierre del kiosko al imprimir no se confirmó** | Se blindó la causa probable (el aviso sobre un diálogo modal) pero **nunca se vio el log**. Si se repite: `%APPDATA%\PresupuestosSatelite\logs\` |
| **El guard de venta sigue apagado** | Pendiente desde la Fase 2; retomar cuando el catálogo esté contado |
| **El HTML del Panel se commitea como foto** | Deuda de la Fase 2 |

### Patrón que ya salió tres veces: el silencio pasando por éxito

1. **El respaldo** que nadie disparaba: no fallaba, porque no corría.
2. **«Ya estás al día»**: no poder saber se veía igual que estar al día.
3. **El bot sin internet**: horas muerto y nadie se enteró.

Los tres se arreglaron igual: **hacer ruidoso el no-saber**, y poner la
vigilancia en un camino distinto del que puede caerse. Vale la pena mirar con
esos ojos cualquier cosa nueva que «avise cuando algo falle».
