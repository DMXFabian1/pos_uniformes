# Historial de Refactors y Checkpoints

## Checkpoint actual

- Precheck de arranque activo.
- Suite de pruebas activa.
- Base actual validada con `check_startup_health.py`.
- Ticket de venta documentado y con correccion tolerante para descuentos faltantes en ventas antiguas.
- Validacion manual confirmada para `Ventas recientes -> Ver ticket`.

## Extracciones ya realizadas

### Arranque

- `database/preflight.py`
  - Verificacion de conexion y revision de esquema.
- `scripts/check_startup_health.py`
  - Smoke operativo reutilizable.

### Caja

- `services/sale_discount_service.py`
  - Descuentos, desglose y totales.
- `services/manual_promo_flow_service.py`
  - Estado y decision de promo manual.
- `services/sale_note_service.py`
  - Notas operativas de la venta.
- `services/sale_loyalty_notice_service.py`
  - Mensajes de transicion de lealtad.
- `services/scanned_client_flow_service.py`
  - Decisiones y copy de cliente escaneado.
- `services/sale_discount_option_service.py`
  - Construccion de opciones del combo de descuento.
- `services/sale_discount_lock_service.py`
  - Estado y tooltip del bloqueo por cliente.
- `services/sale_client_discount_service.py`
  - Resolucion del descuento efectivo del cliente.

### Ticket

- `services/sale_ticket_totals_service.py`
  - Normalizacion y reconstruccion de descuento para render de ticket.
- `services/sale_ticket_text_service.py`
  - Render textual del ticket, forma de pago y ajuste de cobro visible.

### Cobro

- `services/sale_rounding_service.py`
  - Regla pura de redondeo posterior al descuento.

### Catalogo e inventario

- `services/search_filter_service.py`
  - Busqueda textual compartida.
- `services/active_filter_service.py`
  - Etiquetas y resumenes de filtros activos.

## Riesgo residual conocido

- `ui/main_window.py` sigue siendo el coordinador mas grande y sensible.
- Configuracion y algunas acciones de inventario aun dependen mucho de handlers largos.
- Falta documentar por dominio con mas detalle.
- El render completo del ticket sigue en `ui/main_window.py` y aun no tiene prueba integrada de texto final.
- Falta validacion manual visual de caja con redondeo ya conectado al total de cobro.

## Proximo paso recomendado

- Blindar el render del ticket con pruebas de texto final.
- Seguir con extracciones pequenas desde caja o catalogo.
- Registrar aqui cada nuevo checkpoint antes de pasar a otro dominio.
