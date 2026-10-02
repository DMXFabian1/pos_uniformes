---
tags: [feature, pos-uniformes, panel, dashboard, conteo, inventario]
fecha: 2026-09-22
estado: en producción · candidato principal de la Fase 2 de [[39 - Brújula]]
---

# 25 — Panel de Uniformes

> Dashboard por escuela embebido en la app PyQt6 (QWebEngineView). Un script de Python consulta PostgreSQL y **escribe un HTML entero**; la app lo carga. Solo la pestaña Conteo habla con Python en vivo, por QWebChannel.

> [!warning] Lee esto antes de tocar el Panel
> El generador tiene **2,981 líneas**, produce **37,722 líneas de HTML**, hace **40 consultas SQL crudas** y **no importa ni un solo servicio** de `services/` (hay 167). Cada regla de negocio que el Panel muestra está **escrita dos veces**: una en el POS y otra aquí.
> Ejemplo real: el commit `90ff5912` sacó los conjuntos de los totales con `conjunto_service.filtro_sin_conjuntos`; en el Panel la misma regla vive como `NOT IN (SELECT conjunto_id FROM conjunto_componente)`, duplicada en dos lugares del SQL.
> **Antes de agregar una consulta aquí, revisa si el servicio ya existe.** Ver [[39 - Brújula]], Fase 2.

## Los dos relojes

El Panel muestra datos de dos edades distintas en la misma ventana:

| Pestaña | Cómo obtiene los datos | Qué tan fresco |
|---------|------------------------|----------------|
| Resumen | SQL crudo en el generador | **foto** del último `generar_panel_uniformes.py` |
| Piezas | SQL crudo en el generador | **foto** |
| Tarifarios | SQL crudo en el generador | **foto** |
| Disponibilidad | SQL crudo en el generador | **foto** (salvo los toggles, que sí van por bridge) |
| **Conteo** | bridge QWebChannel → `conteo_service` | **vivo** |

El HTML generado **se commitea al repo** (`a9d5ac8f` "panel de uniformes regenerado el 20/09 — 50 escuelas, 560 productos, 15,333 piezas en tienda"; antes `4a1eedfd`, datos del 10/09). O sea: la foto viaja en git y puede tener semanas.

La app intenta taparlo: al abrir la pestaña, si el HTML tiene **más de 5 minutos**, lanza el generador como subprocess en un `QThread` y recarga. Funciona cuando hay base; cuando no, te quedas con la foto del repo sin aviso claro.

## Ubicación

| Archivo | Descripción |
|---------|-------------|
| `scripts/generar_panel_uniformes.py` | Generador — 2,981 líneas, 40 consultas SQL, 0 servicios |
| `panel_uniformes.html` | Salida — 37,722 líneas, versionada en git |
| `ui/views/panel_uniformes_view.py` | Widget PyQt6 (QWebEngineView + QWebChannel + `PanelBridge`) — 608 líneas |
| `services/conteo_service.py` | Conteo de inventario (lo único que el bridge usa) |
| `services/conteo_sheet_service.py` | Hojas de conteo, impresora térmica |
| `services/pedido_sheet_service.py` | Hojas de pedido, impresora térmica |
| `ui/dialogs/conteo_print_dialog.py` | Diálogo de impresión multi-hoja |

Builders del generador: `build_resumen` · `build_pieces` · `build_tariffs` · `build_variants` (Disponibilidad) · `build_conteo`.

**Conexión a BD del generador:** prueba `127.0.0.1:5432` primero; si no responde, usa `server_db_host()` (la PC de Windows). Imprime `DB: local (Mac)` o `DB: red (…)`. Ver [[Referencia Rápida#Rutas]] y la nota de la red local.

## Integración en la app

**Pestaña índice 8** (entre Historial inventarios y Analítica).

```
main.py            → early import QtWebEngineWidgets (ANTES de QApplication, except Exception)
main_window.py     → addTab(build_panel_uniformes_tab(), "Panel Uniformes")
panel_uniformes_view.py → QWebEngineView + QWebChannel + PanelBridge
```

**Dependencia:** `PyQt6-WebEngine` debe coincidir en versión con PyQt6 (ej. ambos 6.10.0).

## Pestañas

### 1. Resumen
KPIs (escuelas, productos, piezas en tienda, valor de inventario). Cards: stock por ubicación (tienda/piso/almacén), salud del inventario, valor por nivel educativo, escuelas por nivel.

- **Salud del inventario**: usa `stock_tienda <= 0` (no `stock_actual = 0`) y solo variantes ligadas a escuela (`catalog_school_product_link` o `producto.escuela_id`). Alineado con Disponibilidad.
- Los **conjuntos no se suman** a totales, valor ni stock bajo: un Pants 3pz con receta *es* el 2pz más la playera, ya contados. *(Regla duplicada — ver el aviso de arriba.)*
- Las barras stacked siempre suman 100% (último segmento = `100 - sum(otros)`).

### 2. Piezas
Matriz escuela × tipo de pieza: qué piezas tiene cada escuela.

- Leyenda: ✓ Tiene · — Falta · ✕ No aplica
- **Modo Configurar**: clic en celdas para marcar ✕ No aplica
- **N/A automáticos** por adopción del nivel (<50% → N/A)
- Cobertura: barra porcentual por escuela (excluye piezas N/A)

### 3. Tarifarios
Cards por escuela con productos, variantes, precios y stock.

- Orden por `PIEZA_ORDER`; drill-down con JSON (`window.__tariffData`, keys cortas)
- Comparador de escuelas, copiar/imprimir tarifario individual

### 4. Disponibilidad
Stock por escuela con grillas de tallas por producto.

- Stats globales: agotadas, bajo mínimo, con faltantes, cobertura %
- Filtro por texto y estado (crítico/bajo/completo); escuelas colapsables
- Cada talla muestra stock en tienda, con tooltip de piso/almacén
- **Doble clic desactiva la talla** → deja de contar como agotada
  - Persiste en `variante.disponibilidad_oculta` (sincroniza Mac ↔ Windows)
  - Bridge: `toggleDisponibilidadOculta(variante_id)`; stats se recalculan en JS
- **Carrito de pedido**: clic en talla → al carrito; barra sticky con Limpiar e Imprimir
  - `imprimirPedido(json)` → `pedido_sheet_service.build_pedido_sheets()` (80 mm)
  - `copiarPedido(json)` → `build_pedido_texto()` → portapapeles (formato WhatsApp)

### 5. Conteo
Conteo físico de inventario. **Solo funciona dentro de la app** (necesita el bridge).

- Selector de escuela con semáforo de estado
- **Productos Básicos**: variantes sin escuela directa pero con link activo en `catalog_school_product_link`; segundo dropdown de tipo de pieza. Pendientes/historial/config no aplican (`isBasicos` los salta).
- **Escuelas multinivel** como entradas independientes; el value es `"escuela_id:nivel_id"`, el bridge lo parsea con `_parse_key()`.
- **SCOPE = SOLO TIENDA.** Mide y ajusta únicamente `stock_tienda`; bodega y piso **nunca** se tocan.
  - `stock_tienda` es derivada: `stock_actual - stock_piso - stock_bodega`
  - `registrar_conteo()` mide `diferencia = fisico - stock_tienda` (no contra el total)
  - `confirmar_ajustes_lote()` suma la diferencia a `stock_actual`; como piso/bodega son constantes, mueve exactamente la porción de tienda
  - Cargar bodega con `populate_existing` tras el `with_for_update` (joinedload + FOR UPDATE no conviven en PG)
- Confirmar ajuste registra al **usuario logueado** (`current_full_name`/`current_username`), no "ADMIN". Si el ajuste dejaría el total < 0, ese conteo se **omite** y queda pendiente, en vez de reventar el lote por el CheckConstraint.
- Pendientes e historial **filtran por escuela Y nivel**.
- Vigencia configurable por escuela (default 90 días).
- **Hojas de conteo** térmicas: una por producto, solo tallas existentes, numeradas "HOJA DE CONTEO X/N", excluye virtuales, jobs separados por `QTimer` (1.5 s) para el autocutter.

> La evolución del conteo (jornada, alcances a medias, historial para auditar) vive en [[36 - Conteos por Jornada]] y [[37 - Revisar y Pedidos]]. Esta nota documenta la **superficie del Panel**, no el modelo de conteo.

## Bridge JS↔Python (`PanelBridge`)

13 slots. Los que necesitan escuela+nivel reciben el string `"eid:nid"` (QWebChannel no resuelve `@pyqtSlot(int, int)` de forma confiable).

| Método JS | Param | Acción Python |
|-----------|-------|---------------|
| `getVariantesParaConteo(key)` | str | Variantes ordenadas por urgencia |
| `getVariantesAgrupadas(key)` | str | Variantes agrupadas por producto |
| `guardarConteo(json)` | str | `registrar_conteos_lote()` |
| `confirmarAjuste(ids_json)` | str | `confirmar_ajustes_lote()` + refresca inventario |
| `getConteosPendientes(eid, nid)` | int,int | Pendientes con dif ≠ 0, por escuela+nivel |
| `getEstadoConteo(key)` | str | Vigencia, pendientes, pct vigente |
| `getConfigConteo(key)` | str | Días de vigencia configurados |
| `setConfigConteo(eid, dias)` | int,int | Upsert `config_conteo_escuela` |
| `getHistorialConteos(eid, lim)` | int,int | Últimos N conteos |
| `toggleDisponibilidadOculta(vid)` | int | Toggle en `variante` |
| `imprimirHojasConteo(key, nombre, nivel, num)` | str×4 | Genera y abre el diálogo de impresión |
| `imprimirPedido(json)` | str | Carrito → hojas de pedido por escuela |
| `copiarPedido(json)` | str | Carrito → texto plano al portapapeles |

**El bridge es el único camino sano del Panel.** Es también el molde de la Fase 2: todo lo que hoy es SQL crudo debería terminar entrando por aquí o por el generador llamando a servicios.

## Tablas

### `conteo_inventario`
| Columna | Tipo | Notas |
|---------|------|-------|
| id | serial PK | |
| variante_id | FK → variante | indexed |
| escuela_id | FK → escuela, nullable | denormalizado para queries rápidas |
| stock_sistema | int | snapshot de `stock_tienda` al contar |
| stock_fisico | int | lo contado en tienda |
| diferencia | int | físico − `stock_tienda` |
| ajustado | bool default false | si ya se aplicó al stock |
| contado_por | varchar(100) | |
| contado_at | timestamptz default now() | indexed |
| notas | text nullable | |

### `config_conteo_escuela`
| Columna | Tipo | Notas |
|---------|------|-------|
| id | serial PK | |
| escuela_id | FK → escuela, UNIQUE | |
| dias_vigencia | int default 90 | frecuencia de reconteo |

### `variante` (columna del Panel)
| Columna | Tipo | Notas |
|---------|------|-------|
| disponibilidad_oculta | bool default false | la talla no cuenta como agotada |

## Bugs resueltos

| Bug | Causa | Fix |
|-----|-------|-----|
| **Conteo destruía bodega (CRÍTICO)** | `registrar_conteo` medía contra `stock_actual` (total) pero la UI cuenta tienda → diferencia falsa de −(bodega+piso) | Medir contra `stock_tienda` + `populate_existing`. Regresión del 27-may perdida en el revert `1ba7c33` |
| Conteos pendientes envenenados | Los registrados con el bug anterior | `scripts/revisar_conteos_pendientes.py` (reporta; `--descartar` los saca sin tocar stock) |
| Botón guardar conteo no funciona | `joinedload + with_for_update` en PostgreSQL | Separar la query con lock de la carga de producto |
| Historial N+1 | Faltaba `joinedload(Variante.producto)` | joinedload + `.unique()` |
| Inventario no refresca tras ajuste | El bridge no invalidaba el cache del snapshot | `_invalidate_listing_snapshot_caches` |
| Slots con 2 ints | QWebChannel no resuelve `@pyqtSlot(int, int)` | String `"eid:nid"` + `_parse_key()` |
| WebEngine DLL en Windows | PyQt6 6.11 vs WebEngine 6.10 | Instalar ambos 6.10.0 |
| Early import silenciado | `except ImportError` no atrapa errores de DLL | `except Exception` |
| Crash del botón reset | QTimer dispara tras cerrar el diálogo | `try/except RuntimeError` |
| Ajuste registraba "ADMIN" | Usuario hardcodeado | `current_full_name`/`current_username` |
| Badge y pendientes ignoraban nivel | `getConteosPendientes` solo filtraba escuela | `obtener_conteos_pendientes` acepta `nivel_id` |
| Ajuste negativo reventaba el lote | Un `stock < -1` violaba el CheckConstraint y revertía TODO | Guard: se omite ese conteo y queda pendiente |
| Entrada inválida → conteo de 0 | `parseInt(val) \|\| 0` en `conteoGuardar` | Validar `isNaN`/negativo e ignorar |

## Tests

`tests/test_conteo_service.py` — diferencia vs tienda (no total), diferencia real en tienda, el ajuste no toca bodega, sin bodega tienda == total, ajuste negativo se omite, pendientes filtran por nivel.

> No hay tests del generador. Las 40 consultas SQL no están cubiertas por nada — es parte de por qué el desfase pasa desapercibido.

## Deuda declarada

1. **40 consultas SQL crudas** que duplican servicios existentes → Fase 2 de [[39 - Brújula]].
2. **El HTML versionado en git** como foto: confunde "está en el repo" con "está al día".
3. **Sin tests del generador.**
4. **Nota 25 estuvo 4 meses sin actualizar** (30-may → 22-sep) mientras el módulo crecía. Si vuelve a pasar, es señal de que el Panel está creciendo sin que nadie lo esté mirando.

---

> Creado: 2026-05-25 · Reescrito: 2026-09-22 (mapeo completo del repo)
> Ver: [[39 - Brújula]] · [[36 - Conteos por Jornada]] · [[37 - Revisar y Pedidos]] · [[19 - Deuda Técnica]]
