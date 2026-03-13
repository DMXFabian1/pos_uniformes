# Historial de Refactors y Checkpoints

## Checkpoint actual

- Precheck de arranque activo.
- Suite de pruebas activa.
- Base actual validada con `check_startup_health.py`.
- Ticket de venta documentado y con correccion tolerante para descuentos faltantes en ventas antiguas.
- Validacion manual confirmada para `Ventas recientes -> Ver ticket`.
- Dialogos de cobro extraidos a `ui/dialogs/payment_dialogs.py`.
- Modal imprimible de ticket y comprobante extraido a `ui/dialogs/printable_text_dialog.py`.
- Cobro mixto ajustado para captura por teclado fisico con confirmacion por `Enter` y cancelacion por `Esc`.

## Extracciones ya realizadas

### Arranque

- `database/preflight.py`
  - Verificacion de conexion y revision de esquema.
- `scripts/check_startup_health.py`
  - Smoke operativo reutilizable.

### Caja

- `services/sale_client_benefit_service.py`
  - Beneficio visible del cliente en Caja a partir de descuento preferente y nivel de lealtad.
- `services/sale_discount_service.py`
  - Descuentos, desglose y totales.
- `ui/helpers/sale_cart_table_helper.py`
  - Filas visibles del carrito y conteo total de piezas para Caja.
- `ui/helpers/sale_cashier_summary_helper.py`
  - Resumen visible del bloque total en Caja sin referencia del cliente.
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

- `services/business_print_settings_service.py`
  - Snapshot reutilizable de negocio, impresion y pie de ticket para textos operativos.
- `services/sale_document_service.py`
  - Carga y validaciones de venta/apartado para abrir ticket o comprobante.
- `services/sale_ticket_totals_service.py`
  - Normalizacion y reconstruccion de descuento para render de ticket.
- `services/sale_ticket_text_service.py`
  - Render textual del ticket, forma de pago y ajuste de cobro visible.
- `services/layaway_receipt_text_service.py`
  - Render textual del comprobante de apartado fuera de `MainWindow`.
- `ui/dialogs/printable_text_dialog.py`
  - Modal reutilizable para mostrar e imprimir ticket o comprobante en texto plano.

### Cobro

- `services/sale_rounding_service.py`
  - Regla pura de redondeo posterior al descuento.
- `ui/dialogs/payment_dialogs.py`
  - Dialogos de efectivo, transferencia y mixto fuera de `MainWindow`.

### Catalogo e inventario

- `services/search_filter_service.py`
  - Busqueda textual compartida.
- `services/active_filter_service.py`
  - Etiquetas y resumenes de filtros activos.

## Riesgo residual conocido

- `ui/main_window.py` sigue siendo el coordinador mas grande y sensible.
- Configuracion y algunas acciones de inventario aun dependen mucho de handlers largos.
- Falta documentar por dominio con mas detalle.
- Falta validacion manual visual de caja con redondeo ya conectado al total de cobro.

## Proximo paso recomendado

- Seguir con extracciones pequenas desde ticket, resumen visual de caja o catalogo.
- Registrar aqui cada nuevo checkpoint antes de pasar a otro dominio.
