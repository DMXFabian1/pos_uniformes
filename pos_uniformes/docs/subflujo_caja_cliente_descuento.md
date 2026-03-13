# Subflujo Caja: Cliente y Descuento

## Objetivo

Describir el comportamiento esperado cuando caja enlaza un cliente y calcula el beneficio visible y aplicado.

## Alcance

Este subflujo cubre:

- descuento preferente del cliente
- descuento por nivel de lealtad
- bloqueo del descuento ligado al cliente
- promo manual no acumulable
- beneficio final visible en caja

No cubre:

- escritura de la venta en base de datos
- confirmacion final de cobro
- impresion de ticket

## Regla principal

1. Si el cliente tiene `descuento_preferente` mayor a cero, ese descuento gana sobre el descuento por nivel.
2. Si no tiene descuento preferente, se usa el descuento del nivel de lealtad.
3. Ese descuento queda bloqueado como beneficio del cliente.
4. La promo manual no se acumula con el beneficio del cliente.
5. Se aplica el mayor beneficio entre cliente y promo manual.

## Archivos involucrados

- `services/sale_client_discount_service.py`
- `services/sale_discount_lock_service.py`
- `services/manual_promo_flow_service.py`
- `services/sale_discount_service.py`
- `ui/main_window.py`

## Flujo esperado

### Caso A. Cliente con descuento preferente

- Caja enlaza cliente.
- Se resuelve `descuento_preferente`.
- El estado de bloqueo queda activo con ese porcentaje.
- El tooltip de descuento indica el cliente y el porcentaje.

### Caso B. Cliente sin descuento preferente

- Caja enlaza cliente.
- Se resuelve el descuento por lealtad.
- El estado de bloqueo queda activo con ese porcentaje.

### Caso C. Promo manual menor al beneficio del cliente

- La promo puede autorizarse.
- El beneficio final sigue siendo el del cliente.
- El resumen debe indicar que gana lealtad/cliente.

### Caso D. Promo manual mayor al beneficio del cliente

- La promo puede autorizarse.
- El beneficio final pasa a ser promo manual.
- El resumen debe indicar que gana la promo.

## Anomalias a vigilar

- cliente con descuento preferente termina usando descuento por nivel
- tooltip muestra un porcentaje distinto al bloqueado
- promo manual se suma al beneficio del cliente
- promo manual queda activa aunque el descuento seleccionado ya no coincide
- el resumen muestra un ganador distinto al descuento efectivo

## Checklist manual rapido

- enlazar cliente con descuento preferente
- enlazar cliente sin descuento preferente
- comparar descuento visible antes y despues
- autorizar promo manual menor al descuento del cliente
- autorizar promo manual mayor al descuento del cliente
- confirmar que el total aplica solo un beneficio
