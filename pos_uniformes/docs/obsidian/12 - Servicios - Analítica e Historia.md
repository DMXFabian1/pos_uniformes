---
tags: [servicios, pos-uniformes]
---

# Servicios — Analítica e Historia

**Cobertura de tests:** 100% ✓
**Característica:** Todos los servicios son **puros** — solo leen, nunca modifican la BD.

> [!danger] Los servicios de abajo leen tablas muertas (verificado 2026-09-10)
> `analytics_snapshot_service`, `analytics_layaway_service` y compañía consultan `venta` (8 filas, última del 10 de abril), `venta_detalle`, `apartado` (7 filas, marzo) y `cliente`. **Las ventas reales viven en `libreta_venta`.**
>
> Por eso la pestaña Analítica ahora abre con dos bloques nuevos que sí leen la realidad, y la vista general vieja quedó abajo:
>
> | Bloque | Servicio | Helper de UI |
> |--------|----------|--------------|
> | Ventas reales (Libreta del kiosko) | `analitica_libreta_service.py` | `ui/helpers/analytics_libreta_helper.py` |
> | Lo que se perdió | `demanda_service.py` | `ui/helpers/analytics_demanda_helper.py` |
>
> Ninguno de los dos puede tumbar la Analítica: si la consulta falla, se registra y el bloque se pinta vacío.

### `analitica_libreta_service.py` — la base analítica de verdad (2026-09-10)

Convierte `libreta_venta.detalle` (JSON) en **una fila por línea de producto vendida** y la enriquece con el catálogo (escuela, pieza, categoría, género, nivel). Todo lo que no toca la base es puro.

- `desglosar(rows)` → `FilaVenta`; los abonos no traen prendas, no generan filas.
- `datos_de_catalogo(session, skus)` → una sola consulta con `selectinload`.
- `filas_de_periodo(session, desde, hasta)` → todo junto.
- Agregados puros: `por_producto`, `por_sku`, `por_escuela`, `por_pieza`, `por_talla`, `por_empleada`, `por_dia`, `por_hora`, `por_forma_pago`, `resumen`.

Pensado como la materia prima de la analítica pesada que Daniel quiere para alimentar un algoritmo. Le falta la otra mitad: [[35 - Demanda No Atendida]].

---

## Servicios de Analítica

### `analytics_snapshot_service.py`
Snapshot principal del dashboard de analítica:
- Ventas totales del período
- Ticket promedio
- Comparación vs período anterior

### `analytics_layaway_service.py`
Métricas de apartados:
- Activos, vencidos, liquidados
- Monto pendiente total

### `analytics_stock_service.py`
Top de SKUs con stock crítico (por debajo del mínimo).

### `analytics_top_clients_service.py`
Top clientes por gasto acumulado en el período.

### `analytics_top_products_service.py`
Top productos por cantidad vendida.

---

## Servicios de Historia

### `history_snapshot_service.py`
Snapshot para el historial general de transacciones:
- **Inventario:** movimientos con registro descriptivo `SKU | Producto | Talla` (antes solo SKU)
- **Catálogo:** cambios con `descripcion_entidad` completa
- Soporta filtros por origen, entidad, tipo, rango de fechas y texto libre

---

## Características comunes

Todos los servicios de analítica:
- Reciben parámetros de fecha (inicio / fin del período)
- Devuelven dataclasses (no modelos ORM directos)
- Son seguros para llamar varias veces sin efecto secundario
- No requieren sesión activa de caja

---

## UI relacionada

- `ui/views/analytics_view.py` — tab de Analítica (~299 líneas)
- `ui/views/history_view.py` — tab de Historial (~164 líneas)
- `ui/helpers/analytics_*` — 8 helpers de presentación
- `ui/helpers/history_*` — 6 helpers de presentación

---

## Ver también
- [[02 - Base de Datos]] — tablas que estos servicios consultan
- [[18 - Cobertura de Tests]] — dominio con mejor cobertura del proyecto
