# Subflujo Caja: Cambio de Cliente con Carrito

## Objetivo

Definir el comportamiento esperado cuando se intenta enlazar o escanear un cliente nuevo mientras ya existe otro cliente activo en la venta.

## Regla principal

1. Si el cliente escaneado ya es el cliente activo, no se reemplaza nada.
2. Si ya existe cliente activo y hay carrito, debe pedirse confirmacion antes de reemplazar.
3. Si no hay cliente activo o no hay carrito, el cliente nuevo puede aplicarse directo.
4. Si el usuario cancela el reemplazo, el cliente actual debe conservarse.
5. Si se aplica el nuevo cliente, el descuento visible debe recalcularse con ese cliente.

## Archivos involucrados

- `services/scanned_client_flow_service.py`
- `services/sale_client_discount_service.py`
- `services/sale_discount_lock_service.py`
- `ui/main_window.py`

## Casos esperados

### Caso A. Cliente ya enlazado

- Se escanea el mismo cliente.
- No cambia el cliente activo.
- Se muestra feedback neutral.

### Caso B. Cliente distinto con carrito

- Existe cliente activo.
- Hay carrito con productos.
- El sistema pide confirmacion.
- Si el usuario cancela, el cliente activo se conserva.

### Caso C. Cliente distinto sin carrito

- Existe o no cliente activo.
- No hay carrito.
- El cliente nuevo puede aplicarse directo.

## Anomalias a vigilar

- reemplazo de cliente sin confirmacion
- se limpia el carrito sin razon
- cambia el cliente pero no cambia el descuento visible
- el feedback mostrado no coincide con la accion real
- cliente ya enlazado dispara recalculo innecesario o reemplazo

## Checklist manual rapido

- escanear el mismo cliente dos veces
- escanear cliente distinto con carrito cargado
- cancelar el reemplazo
- confirmar el reemplazo
- revisar descuento visible antes y despues
