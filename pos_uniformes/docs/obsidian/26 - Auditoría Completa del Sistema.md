---
tags: [auditoria, bugs, refactor, pos-uniformes, deuda-tecnica]
fecha: 2026-05-25
---

# Auditoría Completa del Sistema — POS Uniformes

> Análisis profundo del codebase generado el 2026-05-25.
> Fuente: 3 agentes paralelos (arquitectura, bugs, código muerto).

## Resumen ejecutivo

| Métrica                     | Valor                   |
| --------------------------- | ----------------------- |
| Archivos Python totales     | 4,638                   |
| Líneas de código            | ~1.8M (incluye .venv)   |
| Servicios                   | 113                     |
| MainWindow líneas           | **12,296** (god object) |
| QuoteSatelliteWindow líneas | 5,692                   |
| Modelos ORM                 | 40 + 15 enums           |
| Bugs CRITICAL               | 3                       |
| Bugs HIGH                   | 4                       |
| Bugs MEDIUM                 | 5                       |
| Espacio recuperable         | ~300 MB                 |

---

## ✅ Verificaciones realizadas (2026-05-25)

| Hallazgo                          | Verificado | Evidencia                                                                          |
| --------------------------------- | ---------- | ---------------------------------------------------------------------------------- |
| C1: anular_ultimo_abono sin admin | ✅          | `_validar_operador` línea 319 vs `_validar_admin` línea 286 en `cancelar_apartado` |
| C2: stock sin lock                | ✅          | 0 usos de `with_for_update` en todo el repo                                        |
| C3: db_sync destructivo           | ✅          | `pg_dump --clean --if-exists` línea 127-128                                        |
| Tests skipped                     | ✅ Negativo | 0 tests con `@skip` o `@xfail`                                                     |
| TODOs en producción               | ✅ Negativo | 0 `# TODO/FIXME/HACK` reales                                                       |
| Total de tests                    | ✅          | 1068 funciones de test (no 228 como decía Obsidian)                                |

## 🔴 PRIORIDAD CRITICAL (atender YA)

### C1. Cajero puede anular abonos sin autorización ni auditoría

**Archivo**: `services/apartado_service.py:319`

```python
# Estado actual (MAL)
anular_ultimo_abono() → valida con _validar_operador (ADMIN o CAJERO)
session.delete(ultimo)  # borra el abono físicamente
```

**Impacto**: Cualquier cajero puede vaciar saldos sin que quede rastro. Desbalancea reportes de caja y empleadas.

**Fix**:
1. Cambiar a `cls._validar_admin(usuario)`
2. Soft-delete: marcar `anulado=true` en vez de borrar
3. Registrar en log/auditoría quién y cuándo

---

### C2. Race condition en stock — sobreventas garantizadas

**Archivo**: `services/inventario_service.py:86-92` (y todo flujo venta/apartado)

```python
# Estado actual (MAL)
stock_anterior = variante.stock_actual  # lee sin lock
# ...validación...
variante.stock_actual = stock_posterior  # escribe sin lock
```

**Impacto**: Con POS + app móvil API + satélite operando sobre la misma DB, dos cajeros vendiendo la última pieza pasan validación y el stock queda negativo. Ya hay constraint `>= -1`, pero el riesgo es real.

**Fix**:
```python
session.execute(
    select(Variante).where(Variante.id == vid).with_for_update()
)
```
O versión optimista con columna `version_id`.

---

### C3. `sync_remote_to_local` destructivo en arranque

**Archivo**: `services/db_sync_service.py:84-176` (llamado desde `main.py:71`)

**Impacto**: En cada arranque en macOS hace `pg_dump --clean --if-exists` + `psql` — borra y reimporta la DB local completa. Si hubo cambios locales (modo offline o desarrollo), se pierden.

**Errores silenciados**: `main.py` envuelve con `except Exception: pass`.

**Fix**:
1. Validar fingerprint/timestamp antes de aplicar
2. Advertir y exigir confirmación
3. O quitar auto-sync y dejarlo manual

---

## 🟠 PRIORIDAD HIGH

### H1. Passwords default hardcoded

**Archivos**:
- `services/bootstrap_service.py:149,156` — "admin123" / "cajero123"
- `scripts/create_initial_users.py:22,25`

**Impacto**: Defaults conocidos quedan en producción si nadie los cambia.

**Fix**: Forzar password vía argumento sin default.

---

### H2. SQL injection en setup Postgres

**Archivo**: `scripts/windows_setup_postgres.py:235`

```python
f"SELECT 1 FROM pg_database WHERE datname = '{args.db_name}';"
```

**Impacto**: Script corre como admin de Postgres. Nombre con comilla rompe query.

**Fix**: Usar placeholders o validar `args.db_name` contra regex `[a-z_][a-z0-9_]*`.

---

### H3. subprocess con `shell=True`

**Archivo**: `services/bodega_label_service.py:321`

```python
subprocess.Popen(["start", "", str(pdf_path)], shell=True)
```

**Fix**: Usar `os.startfile(str(pdf_path))` en Windows (built-in, sin shell).

---

### H4. CORS abierto con credentials en API

**Archivo**: `api/main.py:49-55`

```python
allow_origins=["*"]
allow_credentials=True  # combinación rechazada por navegadores
```

**Fix**: Restringir a IP/host LAN específico.

---

### H5. `VentaService.crear_confirmada_desde_apartado` pierde data

**Archivo**: `services/venta_service.py:211-212`

```python
sku_snapshot=getattr(detalle_apartado.variante, "sku", None)
descripcion_snapshot=getattr(...nombre, "nombre", None)
```

**Impacto**: Si variante fue borrada, se pierde info crítica para trazabilidad histórica.

**Fix**: `if variante is None: raise ValueError(...)`.

---

## 🟡 PRIORIDAD MEDIUM

### M1. `meilisearch_service` estado global sin lock

**Archivo**: `services/meilisearch_service.py:19-20, 349, 392`

`_client/_client_checked_at` mutado desde múltiples threads sin lock.

**Fix**: `threading.Lock()` o `contextvars`.

### M2. Inventario sin validación de tipos

**Archivo**: `services/inventario_service.py:443`

UI puede pasar float desde QDoubleSpinBox. Multiplicar por -1 produce floats negativos.

**Fix**: `int(cantidad)` explícito.

### M3. Pérdida de precisión Decimal→float

**Archivo**: `services/meilisearch_service.py:181`

```python
float(v.precio_venta or 0)  # rompe centavos
```

**Fix**: Serializar como int de centavos o string Decimal.

### M4. `except Exception: pass` swallowing errors

**Archivos múltiples**:
- `main.py:65-83`
- `services/db_sync_service.py:180`
- `services/catalog_service.py:45`
- `services/customer_card_service.py:398`
- `services/employee_card_service.py:83,309`
- `services/meilisearch_service.py:61,312`

**Fix**: Mínimo `logger.exception()` para mantener trazabilidad.

### M5. `_normalize_whatsapp_phone` duplicada

**Archivos**:
- `ui/quote_satellite_window.py:5614`
- `ui/main_window.py:10741`

**Fix**: Mover a `utils/phone_normalization.py`.

### M6. Normalización NFKD reimplementada en 6 lugares

Ya existe `utils/text_normalization.normalize_text_unicode` pero la reimplementan:
- `ui/main_window.py:726`
- `ui/dialogs/catalog_product_dialog.py:467`
- `ui/helpers/catalog_macro_filter_helper.py:11`
- `ui/helpers/catalog_product_form_summary_helper.py:117`
- `services/search_suggestion_service.py:26`
- `services/search_filter_service.py:82`

**Fix**: Reemplazar todos por el import.

---

## 🟢 PRIORIDAD LOW

### L1. Mezcla `datetime.now()` naive vs aware

El resto usa `datetime.now(timezone.utc)`, estos quedaron en local:
- `ui/main_window.py:3118,5442,7105,7109,10607,10709`
- `services/customer_card_service.py:154`
- `services/backup_service.py:208,223`
- `services/bodega_label_service.py:208`

### L2. `session.refresh(...)` costoso tras cada mutación

**Archivo**: `services/apartado_service.py:464`

Recarga colección entera por roundtrip. Notable con apartados grandes.

### L3. Bug latente: `ImageFont` no importado

**Archivo**: `utils/qr_generator.py:276-289`

Referencia `ImageFont.truetype` sin importar. Envuelto en `try/except`, cae siempre al fallback. **El monograma de empleada nunca se dibuja**.

**Fix**: `from PIL import ImageFont`

### L4. Bug latente: `datetime` en anotaciones

**Archivo**: `ui/helpers/analytics_period_helper.py:28,61-63`

Anota con `datetime` pero solo importa `date, timedelta`. Funciona por `from __future__ import annotations`, rompe `inspect.get_type_hints()`.

---

## 🧹 CÓDIGO MUERTO / ELIMINAR (300+ MB)

### Para eliminar SIN riesgo

```bash
# Espacio en disco
rm -rf .venv-py39-backup/                    # 283 MB

# Del repo (commiteados)
git rm -rf ownership-map-out/                # 6.1 MB
git rm -rf ownership-map-out-loose-2/        # 1.1 MB
git rm pos.db                                # 0 bytes pero ruido
git rm etiqueta_caja_preview.html            # 11 KB
git rm piezas_por_escuela.html               # 27 KB
git rm api/schemas/common.py                 # ErrorDetail/Response sin uso

# Backups y exports commiteados (rotos por .gitignore)
git rm -r exports/
git rm backups/database/pos_uniformes_20260320_154642.sql
git rm backups/database/.automatic_backup_status.json
```

### Servicios huérfanos (decidir borrar o cablear)

| Archivo | Estado |
|---------|--------|
| `services/quote_document_view_service.py` | Solo importado en tests |
| `services/search_suggestion_service.py` | Solo importado en tests |
| `ui/helpers/search_input_helper.py` | Solo importado en tests |

### Scripts one-off para archivar

- `scripts/backfill_legacy_import_trace.py` — backfill ya aplicado
- `scripts/generar_tarifarios.py`, `generar_tarifarios_html.py` — duplicación con panel

### 58 imports muertos detectados por pyflakes

Top hits:
- `ui/main_window.py:135, 401, 429`
- `ui/quote_satellite_window.py:6, 19, 50`
- `services/meilisearch_service.py:11, 285`
- `database/connection.py:46` (`models` sin usar)
- `services/sale_ticket_text_service.py:24`
- `services/employee_ranking_service.py:12`

**Comando completo**:
```bash
python3 -m pyflakes ui/ services/ utils/ database/ api/ importers/ scripts/ \
  main.py api_server.py presupuestos_satelite_main.py | grep "imported but unused"
```

---

## 🏗️ INCONSISTENCIAS ARQUITECTÓNICAS

### 1. Doble naming inglés/español

- `venta_service.py` + 23 archivos `sale_*`
- `apartado_service.py` + 9 archivos `layaway_*`

**Indica**: Migración a medias. Decidir un solo idioma y migrar.

### 2. Clases vs módulos funcionales sin convención

- Clases: `VentaService`, `ApartadoService`, `CajaService`, `CatalogService`
- Funcionales: `sale_checkout_action_service.complete_sale_checkout`, casi todos `layaway_*`, `meilisearch_service`

**Indica**: Patrón mixto sin guía. Documentar cuál usar para qué.

### 3. Extracción de tabs incompleta

`_build_*_tab()` en `main_window.py` solo delega a `ui/views/*` para algunos. Lógica de refresh/handlers sigue dentro de MainWindow → **12,296 líneas**.

**Fix gradual**: Migrar tab por tab a `ui/views/`.

### 4. `api_server.py` referencia config inexistente

`settings.api_host/api_port` no existen en `utils/config.Settings`.

**Fix**: Agregar campos a Settings o quitar referencia.

### 5. Import circular evitado con late imports

`sale_checkout_action_service` y `sale_checkout_service` usan `def _resolve_dependencies()` con imports tardíos. Síntoma de acoplamiento alto.

---

## 📋 PLAN DE ACCIÓN RECOMENDADO

### Sprint 1 — Seguridad ✅ COMPLETADO (2026-05-25)
1. ✅ `anular_ultimo_abono` → admin-only + soft-delete (`anulado`, `anulado_por`, `anulado_at`) + 3 tests nuevos
2. ✅ Passwords default eliminados — `secrets.token_urlsafe(16)` fallback, `--required` en script CLI
3. ✅ SQL injection → validación `re.fullmatch(r"[a-z_][a-z0-9_]*", db_name)` antes de query
4. ✅ `shell=True` → `os.startfile()` (Windows built-in, sin shell)
5. ✅ CORS `*` → lista configurable via `POS_CORS_ORIGINS` env var, default localhost

### Sprint 2 — Integridad de datos (2 días)
1. ⏳ Agregar `with_for_update()` en flujo de stock
2. ⏳ Validar fingerprint antes de `sync_remote_to_local`
3. ⏳ Quitar `getattr` de campos críticos en VentaService
4. ⏳ Reemplazar `except Exception: pass` con logging

### Sprint 3 — Limpieza (medio día)
1. ⏳ Eliminar archivos seguros (300 MB)
2. ⏳ Eliminar 58 imports muertos
3. ⏳ Consolidar `_normalize_whatsapp_phone`
4. ⏳ Consolidar normalización NFKD
5. ⏳ Decidir destino de servicios huérfanos

### Sprint 4 — Refactor estructural (continuo)
1. ⏳ Migrar lógica de tabs a `ui/views/` (1 tab por sesión)
2. ⏳ Unificar naming (decidir inglés o español)
3. ⏳ Documentar convención clases vs funciones
4. ⏳ Fix `api_server.py` settings

---

## 📚 ARQUITECTURA DEL SISTEMA

### Puntos de entrada

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `main.py` | 123 | POS principal — Bootstrap → preflight → sync DB → login → MainWindow |
| `presupuestos_satelite_main.py` | 185 | App satélite — QLockFile → probe DB → online/offline |
| `api_server.py` | 53 | FastAPI uvicorn launcher |

### Capas

```
UI (PyQt6)  ─►  Services (lógica de negocio)  ─►  Database (SQLAlchemy ORM)
   │
   ├─ helpers/   (97 archivos)
   ├─ dialogs/   (20 diálogos modales)
   ├─ views/     (10 builders extraídos de main_window)
   └─ styles/    (6 stylesheets)

API REST (FastAPI) ─► Services compartidos ─► mismo ORM
Importers (Excel/legacy) ─► Services ─► DB
Scripts (backups, generadores HTML, instaladores Windows)
```

### Servicios por dominio (113 archivos)

| Dominio | Servicios | Notas |
|---------|-----------|-------|
| Ventas | `venta_service` + 23 `sale_*` | Doble naming |
| Apartados | `apartado_service` + 9 `layaway_*` | Doble naming |
| Presupuestos | `presupuesto_service` + 9 `quote_*` | Más limpio |
| Catálogo | `catalog_service` (890 ln) + 7 `catalog_*` | El más grande |
| Inventario | `inventario_service` + 4 `inventory_*` | Bodega aparte |
| Caja | `caja_service` + 2 `cash_session_*` | OK |
| Clientes | `client_service` + `loyalty_service` + `customer_card_service` | OK |
| Empleadas | 5 `employee_*` | OK |
| Compras | `compra_service` + `supplier_service` | Poco uso |
| Settings | 8 `settings_*_action_service` + 3 base | Excesivo |
| Analytics | 5 `analytics_*` | OK |
| Manuales/escuelas | `manual_promo_*`, `school_*`, `sports_uniform_*` | OK |
| Auth | `auth_service`, `user_service` | OK |

### Archivos críticamente grandes

| Archivo | Líneas | Acción |
|---------|--------|--------|
| `ui/main_window.py` | 12,296 | God object — migrar a views/ |
| `ui/quote_satellite_window.py` | 5,692 | Mismo problema |
| `ui/dialogs/catalog_product_dialog.py` | 1,868 | Considerar dividir |
| `database/models.py` | 1,597 | OK (40 modelos) |
| `ui/dialogs/settings_dialogs.py` | 1,164 | Considerar dividir |
| `services/catalog_service.py` | 890 | OK |

---

> Generado: 2026-05-25 | Próximo paso: priorizar con Daniel qué atacar primero
