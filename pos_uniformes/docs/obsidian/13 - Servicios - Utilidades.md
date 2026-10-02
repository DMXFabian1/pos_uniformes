---
tags: [servicios, pos-uniformes]
---

# Servicios — Utilidades y Soporte

---

## Meilisearch — Búsqueda typo-tolerant (agregado 2026-05-20)

### `meilisearch_service.py`
Motor de búsqueda tolerante a errores de escritura. Indexa todas las variantes activas en un índice Meilisearch local.

**Funciones principales:**
- `search(query, limit=40, mode=None)` — búsqueda con typo tolerance, retorna hits con SKU, nombre, talla, color, precio, escuela, etc.
- `search_as_families(query, limit=40, mode=None)` — agrupa hits por `family_key` (tipo_pieza + nombre_base)
- `index_from_db(session)` — re-indexa todas las variantes activas desde la DB
- `configure_index()` — configura searchable/filterable attributes, typo tolerance, ranking rules
- `is_available()` — verifica si Meilisearch responde

**Atributos indexados:** SKU, nombre_base, nombre_producto, talla, color, tipo_pieza, tipo_prenda, categoría, marca, escuela
**Atributos filtrables:** activo, escuela_id, tipo_pieza_id, tipo_prenda_id, modo (school/basics)

**Patrón de uso (consistente en 6 áreas):**
1. Meilisearch pre-filtra por relevancia (`limit=500`)
2. Filtro local refina con términos exactos + combos activos
3. Si Meilisearch no disponible, solo filtro local (fallback transparente)

**Áreas integradas:**
| Área | Archivo |
|------|---------|
| Satélite catálogo | `quote_satellite_window.py` |
| Satélite guiado | `quote_satellite_window.py` |
| Cmd+S búsqueda rápida | `quick_product_search_dialog.py` |
| Inventario POS | `main_window.py` |
| Catálogo POS | `main_window.py` |
| Bodega ingreso | `bodega_ingreso_dialog.py` |

**Infraestructura macOS:**
- Binario: `/Users/danielfabian/bin/meilisearch`
- Data: `/Users/danielfabian/meili_data/`
- LaunchAgent: `com.danielfabian.meilisearch` con `KeepAlive=true`
- URL: `http://127.0.0.1:7700` (sin API key)

**Windows:** `ensure_running()` / `ensure_installed()` descargan y arrancan `C:\Meilisearch\meilisearch.exe` (v1.14.0) por máquina, ligado a `127.0.0.1:7700`; cada satélite/POS tiene su propio índice y reindexa desde la base al arrancar (`autostart_and_reindex`). Desde la Mac no se alcanza el de la principal (solo escucha en localhost).

**Auditoría 2026-09-09 (qué falta, contra los datos reales: 4,795 variantes / 546 productos / 47 escuelas):**
1. **SKU corto**: `SKU000621` es un solo token → teclear `621` no encuentra nada (prefijo). Falta campo `sku_num`.
2. **Popularidad y stock en el ranking**: las ventas de la Libreta (`libreta_venta.detalle`) no influyen; falta `ventas_60d` + `en_stock` como reglas de ranking.
3. **Campos sin indexar**: `nivel_educativo` (317 productos; los sinónimos sec/prepa/kinder apuntan al vacío), `atributo` (415), `escudo` ("Con Escudo", 262). `talla`/`color` no filtrables (sin chips). NO indexar `descripcion` (504 dicen "Importado desde productos.db.").
4. **Sinónimos faltantes**: oscuro↔obscuro, escocés↔escoces, pgallo↔pata de gallo, guinda/tinto/bordo→vino, kaki→caqui, rey→azul rey, tele→telesecundaria, uni↔unitalla.
5. **Orden de tallas**: falta `talla_orden` numérico (2…46, CH, MD, GD, EXG).
6. **Stock viejo en el índice**: solo se reindexa al editar producto, no al vender; el reindex borra todo y recarga (segundos en vacío). Mejor: update parcial id+stock al vender + reindex diario.
7. **Datos sucios**: tallas Uni/Unitalla/Ch/M, tipos Basico/Básico, Blanca 310 vs Blanco 124, nombres con la escuela repetida.
**Hecho el 2026-09-09 (puntos 1-5):** `sku_num` (teclear `621`), `nivel_educativo` / `atributo` / `escudo` indexados (los sinónimos sec/prepa/kinder ya pegan), `talla` / `color` / `nivel_educativo` / `en_stock` filtrables, ranking `en_stock:desc` + `ventas_60d:desc` (piezas vendidas en la Libreta, `ventas_por_sku`, solo Postgres), `talla_orden` sortable, sinónimos nuevos. `documento_variante()` arma cada doc (puro). Se aplica solo: cada app reconfigura e indexa al arrancar (`autostart_and_reindex`). Pendientes: 6 (stock viejo / reindex diario) y 7 (limpiar datos).

---

## Servicios de soporte

### `backup_service.py`
Respaldo y restauración de PostgreSQL.
- Tests: ✓

### `bootstrap_service.py`
Crea datos iniciales: usuario admin, categorías base.
- Usa: `auth_service`, `inventario_service`
- Tests: ✗ (pendiente)

### `search_filter_service.py`
Búsqueda de texto puro compartida entre Catálogo e Inventario.
- Tests: ✓

### `search_suggestion_service.py`
Sugerencias incrementales al escribir en el buscador.
- Tests: ✓

### `active_filter_service.py`
Formatea el estado de filtros activos para mostrar como chips visuales.
- Tests: ✓

### `satellite_startup_service.py` *(satélite)*
Probe TCP para detectar si la PC principal responde antes de arrancar.
- `probe_database_host(timeout_sec=3.0) → bool`
- No usa SQLAlchemy — conexión TCP pura, falla silenciosamente
- Tests: ✓ 5 tests

### `supplier_service.py`
CRUD de proveedores.
- Tests: ✗ (pendiente)

---

## Servicios especializados

### `sports_uniform_pricing_service.py`
Reglas de precio para uniformes deportivos (ej. regla 2pz → 3pz).

### `sports_uniform_size_service.py`
Equivalencias de tallas para uniformes deportivos.

---

## Utils (`utils/`)

| Archivo | Función |
|---------|---------|
| `config.py` | Settings desde variables de entorno (DATABASE_URL, DB_ECHO, etc.) |
| `app_metadata.py` | VERSION, APP_DISPLAY_NAME, rutas de assets |
| `product_name.py` | Sanitización de nombres + `build_ticket_product_name()` (nombre_base + escuela, sin Ad hoc ni tipo pieza) |
| `date_format.py` | Formateo consistente de fechas y horas en todo el POS |
| `product_templates.py` | Plantillas para crear productos nuevos rápidamente |
| `qr_generator.py` | Generación de QR para variantes, clientes y empleadas. `BulkQrWorker` (QThread) genera/regenera QR masivo con progreso y cancelación |
| `label_generator.py` | Generación de etiquetas (standard, split, continuous). Split: QR 160px, gap 2px, texto pegado al QR. `show_price` parameter: override solo puede quitar precio, nunca forzar en uniformes |
| `inventory_label_content_helper.py` | Perfiles de etiqueta (`InventoryLabelProfile`): uniformes show_price=False, ropa_normal show_price=True |
| `headless_browser_helper.py` | Búsqueda de ejecutable de navegador |
| `legacy_paths.py` | Manejo de rutas de versiones anteriores |
| `venv_bootstrap.py` | Inicialización automática del entorno virtual |
| `pyinstaller_data_helper.py` | Soporte para bundle PyInstaller (Windows) |

---

## Scripts (`scripts/`)

| Script | Función |
|--------|---------|
| `check_startup_health.py` | Verifica salud de BD al arrancar — **verificación mínima** |
| `check_operational_flows.py` | Testa flujos operativos críticos |
| `setup_dev_env.py` | Configura entorno de desarrollo desde cero |
| `create_initial_users.py` | Crea usuario admin inicial |
| `backup_database.py` | Respaldo manual de PostgreSQL |
| `restore_database.py` | Restauración manual |
| `run_scheduled_backup.py` | Runner para tarea programada de respaldo automático |
| `import_legacy_products.py` | Migración de datos desde sistema anterior |
| `backfill_legacy_import_trace.py` | Rellena trazabilidad histórica |
| `windows_build_runner.py` | Build del ejecutable para Windows |
| `windows_run_dev.py` | Ejecutar en modo dev en Windows |
| `windows_setup_postgres.py` | Setup de PostgreSQL en Windows |
| `build_presupuestos_satelite_windows.ps1` | Build del bundle satélite para Windows (corre tests + PyInstaller) |
| `setup_satelite.ps1` | Instalación del satélite en un paso (env, conexión, acceso directo, autostart) |
| `windows_launch_presupuestos_satelite.ps1` | Lanzar la app satélite en desarrollo |

---

## Configuración de entorno

El archivo `pos_uniformes.env` (no versionado) configura cada máquina:

```env
DATABASE_URL=postgresql://user:pass@localhost/pos_db
DB_ECHO=false
AUTO_CREATE_SCHEMA=false
```

Usar `pos_uniformes.env.example` como base.

---

## Ver también
- [[01 - Arquitectura General]] — flujo de arranque y setup
- [[18 - Cobertura de Tests]] — servicios sin tests en este dominio
