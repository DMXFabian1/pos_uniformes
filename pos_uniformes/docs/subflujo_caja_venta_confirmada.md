# Subflujo Caja: Venta Confirmada y Nota Final

## Objetivo

Definir el comportamiento esperado al confirmar una venta despues de que el carrito, descuentos y medio de pago ya fueron resueltos.

## Alcance

Este subflujo cubre:

- totales finales
- nota operativa que se guarda en la venta
- registro de promo manual si aplica
- mensaje de transicion de lealtad para siguiente compra

No cubre:

- seleccion del cliente
- autorizacion del codigo de promo
- captura del medio de pago

## Regla principal

1. La venta debe guardar subtotal, porcentaje, monto de descuento y total final.
2. La observacion de la venta debe incluir metodo de pago, beneficio aplicado y notas adicionales del pago.
3. Si hubo promo manual efectiva, debe registrarse auditoria de promo manual.
4. Si el cliente cambia de nivel o descuento despues de confirmar la venta, debe mostrarse aviso para la siguiente compra.
5. Si ocurre error de stock, el mensaje final debe ser claro y no dejar la venta a medias.

## Archivos involucrados

- `ui/main_window.py`
- `services/venta_service.py`
- `services/sale_note_service.py`
- `services/sale_discount_service.py`
- `services/manual_promo_service.py`
- `services/loyalty_service.py`
- `services/sale_loyalty_notice_service.py`

## Nota operativa esperada

Debe incluir, segun el caso:

- metodo de pago
- descuento porcentual
- lealtad si aplica
- promo manual si aplica
- beneficio aplicado
- descuento aplicado si fue mayor a cero
- notas adicionales de pago

## Anomalias a vigilar

- la nota guardada no coincide con el beneficio real aplicado
- se registra promo manual sin que la promo haya sido efectiva
- el mensaje de lealtad no coincide con el nuevo nivel
- el error de stock deja al operador sin contexto claro
- el total mostrado no coincide con el total confirmado

## Checklist manual rapido

- confirmar venta sin descuento
- confirmar venta con lealtad
- confirmar venta con promo manual
- revisar observacion guardada
- revisar historial de promo manual si aplica
- provocar validacion de stock y revisar el mensaje
