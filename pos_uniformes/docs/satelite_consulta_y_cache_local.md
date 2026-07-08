# Satelite de Presupuestos — Arquitectura y modo offline

## Contexto

La app satelite de Presupuestos (`presupuestos_satelite_main.py`) opera como terminal de consulta y presupuesto conectada por red local a la base PostgreSQL de la PC principal. Tambien puede operar sin conexion usando un cache local de lectura.

## Alcance operativo

El satelite es una terminal de:

- consulta de precios y productos (catalogo completo con tallas, colores, SKUs)
- armado y guardado de presupuestos
- busqueda guiada por escuela, tipo de prenda, genero y nivel
- consulta rapida por SKU (kiosko)
- busqueda por texto libre (Meilisearch cuando hay conexion)
- favoritos locales por pieza
- **Venta Rapida** (desde 2026-06/07): gate por QR de empleada, escaneo de productos, tickets de venta/apartado con terminos, copia empleada con descuento autorizado, promo 3pz (pants deportivo + playera a $100), impresion de etiquetas desde Ctrl+S. Impresion multi-ticket via `TicketPrintQueue` (`ui/views/quick_sale_view.py`).

No es una terminal de:

- corte de caja
- inventario ni stock
- administracion de catalogo

## Arquitectura de arranque

### Flujo de inicio (`presupuestos_satelite_main.py`)

1. `probe_database_host()` — TCP probe al host:puerto de PostgreSQL (timeout 3s)
2. Si hay conexion:
   - `init_db()` para asegurar schema
   - `assert_database_ready()` preflight check
   - `autostart_and_reindex()` para Meilisearch — arranca el binario si esta instalado y re-indexa en hilo aparte (tolerante a fallos; antes solo `notify_catalog_changed()`)
   - `resolve_satellite_operator_id()` — selecciona usuario CAJERO o ADMIN activo
   - Abre `QuoteSatelliteWindow(user_id=..., offline_mode=False)`
3. Si no hay conexion:
   - `load_catalog_cache()` — carga snapshot JSON local
   - Si no hay cache: mensaje de error y cierre
   - Si hay cache: abre `QuoteSatelliteWindow(user_id=None, offline_mode=True, offline_catalog_cache=...)`

### Servicios de soporte

| Servicio | Archivo | Funcion |
|----------|---------|---------|
| Probe TCP | `satellite_startup_service.py` | Verifica host vivo sin SQLAlchemy |
| Cache catalogo | `catalog_local_cache_service.py` | Snapshot JSON con escritura atomica |
| Presupuestos offline | `offline_quote_storage_service.py` | JSON local, no se sincronizan |
| Favoritos | `satellite_favorites_service.py` | JSON local con escritura atomica, seed desde bundle |
| Cache links escuela | `school_links_cache_service.py` | Asociaciones escuela-producto para guiado |

## Modo conectado

- Fuente de verdad: PostgreSQL en PC principal
- Presupuestos se guardan en DB via `presupuesto_service`
- Catalogo se obtiene via `catalog_snapshot_service` y se indexa en memoria con `_sku_index` (O(1))
- Meilisearch disponible para busqueda de texto libre (limite 100 resultados)
- Al guardar presupuesto se actualiza el cache local para futuro uso offline

## Modo offline

- Banner visible `Sin conexion — usando catalogo guardado localmente`
- Catalogo cargado desde `satellite_data_dir()/data/catalog_cache.json`
- Presupuestos se guardan localmente en `offline_quotes.json` (no se sincronizan)
- Funciones deshabilitadas: reindexar Meilisearch, compartir presupuesto, administracion
- Favoritos funcionan igual (son siempre locales)
- Cantidades del carrito se modifican en memoria sin acceso a DB

## Interfaz de usuario

### Paginas principales (tabs)

1. **Catalogo** — tabla con busqueda por texto, filtro por escuela/genero/nivel
2. **Presupuesto guiado** — flujo paso a paso: escuela > genero > nivel > tipo prenda > producto > tallas
3. **Kiosko** — busqueda rapida por SKU con campo de texto grande
4. **Presupuestos** — lista de presupuestos guardados, detalle, compartir por WhatsApp
5. **Venta Rapida** — escaneo de productos y generacion de nota (gate por QR de empleada)
6. **Administracion** — diagnostico de conexion. Los controles de Meilisearch se movieron al menu admin oculto **Ctrl+Shift+A** (sin botones a la vista de las empleadas; el header del guiado solo muestra indicador pasivo)

### Carrito lateral

- Sidebar fijo con items del presupuesto activo
- Botones +/- para cantidad (online: DB, offline: memoria)
- Eliminar items individuales
- Boton para guardar/compartir presupuesto

### UX tactil

- `QScroller` habilitado en todas las tablas y scroll areas
- Botones de producto en FlowLayout con corazones de favorito como overlay
- Debounce de 300ms en campo de filtro de presupuestos
- Scroll areas con politica `ScrollBarAsNeeded`

## Persistencia local

Todos los archivos locales se guardan en `satellite_data_dir()`:

```
<satellite_data_dir>/
  data/
    catalog_cache.json      — snapshot del catalogo
    favorites.json          — product_keys favoritos
    offline_quotes.json     — presupuestos sin conexion
    school_links_cache.json — asociaciones escuela-producto
```

La escritura de archivos usa el patron atomico `tempfile.mkstemp` + `os.replace` para evitar corrupcion por cortes de energia o cierres abruptos.

## Build y distribucion (Windows)

El satelite se empaqueta con PyInstaller. `seed_favorites_from_bundle()` copia favoritos del bundle al AppData si no existen, permitiendo que favoritos marcados en desarrollo lleguen al build sin sobreescribir los de la empleada.

## Decisiones de diseno

- **TCP probe vs SQLAlchemy**: el probe TCP es mas rapido (~3s) porque no necesita autenticacion ni negociacion de protocolo
- **SKU index O(1)**: `_rebuild_sku_index()` construye un dict `sku -> row` al cargar el catalogo, reemplazando busquedas lineales O(n)
- **Favoritos locales**: cada satelite tiene sus propios favoritos, no se sincronizan a la DB
- **Sin sincronizacion de presupuestos offline**: los presupuestos creados sin conexion son locales y no se envian a la DB al reconectar — esto es intencional para evitar duplicados y conflictos

## Estado

- `2026-04-11`: decision de producto — satelite como terminal de consulta
- `2026-04-20`: modo offline implementado (Fase 2 del plan original)
- `2026-04-20`: presupuestos offline implementados (Fase 3 del plan original)
- `2026-05-21`: fix bugs offline (refresh, cantidades, reindex sin DB, escritura atomica)
- `2026-05-22`: corazones overlay en botones de producto, mejoras de spacing
- `2026-06/07`: Venta Rapida (gate QR empleada, tickets venta/apartado, promo 3pz, etiquetas Ctrl+S)
- `2026-07-03`: `TicketPrintQueue` (cola de impresion segura), excepthook global (`utils/satellite_excepthook.py`, loguea a `satellite_errors.log`), Meilisearch auto-arranque
- `2026-07-05`: version `2026.07.05` lista para bundle (hiddenimports nuevos en el spec)
