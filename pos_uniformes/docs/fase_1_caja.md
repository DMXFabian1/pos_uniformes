# Fase 1. Caja

## Objetivo

Blindar el flujo de venta antes de tocar cambios mas complejos.

## Alcance

Esta fase cubre:

- cliente enlazado en caja
- cliente escaneado
- descuento por cliente
- descuento por lealtad
- promo manual
- notas operativas de venta
- resumen visible de beneficios

No cubre todavia:

- rediseño visual de caja
- reestructuracion grande de `ui/main_window.py`
- cambios de BD o flujo de tickets

## Archivos clave

### Coordinacion UI

- `ui/main_window.py`
- `ui/views/cashier_view.py`

### Servicios de caja ya extraidos

- `services/sale_discount_service.py`
- `services/manual_promo_flow_service.py`
- `services/sale_note_service.py`
- `services/sale_loyalty_notice_service.py`
- `services/scanned_client_flow_service.py`
- `services/sale_discount_option_service.py`
- `services/sale_discount_lock_service.py`
- `services/sale_client_discount_service.py`

### Persistencia y dominio

- `services/venta_service.py`
- `services/manual_promo_service.py`
- `services/loyalty_service.py`
- `services/caja_service.py`
- `database/models.py`

## Checklist tecnico antes de tocar caja

1. Correr `./.venv/bin/python scripts/check_startup_health.py`
2. Correr `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
3. Revisar `docs/historial_refactors.md`
4. Confirmar si la regla ya vive en `services/`

## Checklist manual de caja

### Flujo base

- Login con `admin`
- Abrir caja si aplica
- Agregar producto por SKU
- Confirmar subtotal sin descuento
- Completar venta simple

### Cliente

- Seleccionar cliente manualmente
- Confirmar cambio de descuento visible
- Escanear cliente ya enlazado
- Escanear cliente distinto con carrito
- Confirmar que pide confirmacion antes de reemplazar

### Descuentos

- Venta sin cliente y sin promo
- Venta con cliente con descuento preferente
- Venta con cliente por nivel de lealtad
- Confirmar que no se acumulan beneficios

### Promo manual

- Elegir promo manual valida
- Confirmar solicitud de codigo
- Probar codigo invalido
- Probar cancelacion de autorizacion
- Confirmar que la promo no queda aplicada por error

### Cierre de venta

- Confirmar nota operativa generada
- Confirmar beneficio aplicado visible
- Confirmar registro de promo manual en historial si aplica

## Matriz de anomalias

### Anomalia

Descuento acumulado.

### Senal

El total aplica descuento de cliente y promo al mismo tiempo.

### Zona probable

- `services/sale_discount_service.py`
- `services/manual_promo_flow_service.py`
- `ui/main_window.py`

### Anomalia

Cliente escaneado reemplaza al actual sin confirmacion.

### Senal

El cliente cambia con carrito cargado sin preguntar.

### Zona probable

- `services/scanned_client_flow_service.py`
- `ui/main_window.py`

### Anomalia

Promo manual queda activa tras cancelar o fallar autorizacion.

### Senal

La promo sigue afectando total aunque no se autorizo.

### Zona probable

- `services/manual_promo_flow_service.py`
- `ui/main_window.py`

### Anomalia

Descuento visible distinto al realmente aplicado.

### Senal

El resumen de caja muestra un beneficio y la venta confirma otro.

### Zona probable

- `services/sale_discount_service.py`
- `services/sale_note_service.py`
- `ui/main_window.py`

### Anomalia

Mensaje de transicion de lealtad incorrecto.

### Senal

El aviso final no coincide con el nivel actualizado del cliente.

### Zona probable

- `services/loyalty_service.py`
- `services/sale_loyalty_notice_service.py`

## Criterio de salida de la fase

La fase se considera madura cuando:

- la suite sigue en verde
- los flujos de caja pasan checklist manual
- no se agregan reglas nuevas directo en `ui/main_window.py`
- cada cambio nuevo de caja deja prueba o checklist asociado

## Siguiente orden recomendado dentro de caja

1. terminar extracciones puras pequenas
2. cubrir sincronizacion de descuento con cliente
3. aislar handlers grandes de venta
4. documentar flujo completo de venta confirmada

## Solicitudes operativas abiertas

Ver `docs/backlog_caja.md`.

- soporte de teclado fisico para calculadora/captura de cobro
- reducir ruido visual del bloque de total en caja
- definir politica de redondeo en efectivo sin centavos
