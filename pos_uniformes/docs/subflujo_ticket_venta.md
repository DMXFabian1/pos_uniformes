# Subflujo. Ticket de venta

## Objetivo

Documentar como se arma el ticket de una venta confirmada, que datos consume y que anomalias deben vigilarse antes de tocar esta zona.

## Punto de entrada

El subflujo arranca desde `Ventas recientes` en `ui/main_window.py`.

Flujo visible:

1. abrir dialogo de ventas recientes
2. seleccionar una venta
3. pulsar `Ver ticket`
4. construir texto de ticket
5. mostrar o imprimir segun el flujo elegido

## Archivos clave

### Coordinacion UI

- `ui/main_window.py`
  - abre el listado de ventas recientes
  - toma la venta seleccionada
  - construye el ticket textual
  - decide impresora y copias

### Servicios puros

- `services/sale_ticket_totals_service.py`
  - normaliza subtotal, descuento y total
  - reconstruye descuento faltante en ventas antiguas si `subtotal > total`

### Persistencia

- `database/models.py`
  - `Venta.subtotal`
  - `Venta.descuento_porcentaje`
  - `Venta.descuento_monto`
  - `Venta.total`
  - `Venta.observacion`
  - relacion con `cliente`, `usuario` y `detalles`

### Configuracion

- `services/business_settings_service.py`
  - nombre del negocio
  - telefono
  - direccion
  - pie de ticket
  - impresora preferida
  - copias

## Datos que consume el ticket

### Encabezado

- negocio
- folio
- fecha

### Cliente

- nombre
- codigo cliente

### Detalle

- producto
- SKU
- cantidad
- precio unitario
- subtotal por linea

### Totales

- subtotal bruto
- descuento porcentaje
- descuento monto
- total final

### Notas

- observacion de la venta
- pie de ticket

## Criterio de claridad actual

El ticket debe priorizar informacion util para el cliente y para rastrear la venta, sin ruido operativo.

Se mantiene:

- negocio
- folio
- fecha
- cliente si existe
- detalle de articulos
- forma de pago si puede inferirse desde `observacion`
- subtotal
- descuento aplicado
- total a pagar
- notas de venta si existen
- pie de ticket

Se oculta del texto final:

- usuario interno
- estado interno
- telefono del cliente
- impresora preferida
- copias configuradas

Limitacion actual:

- la forma de pago no vive todavia en un campo propio de `Venta`
- por ahora el ticket la infiere desde `observacion` cuando existe `Metodo de pago: ...`

## Regla critica de totales

El ticket debe ser tolerante a ventas antiguas o desalineadas.

Regla actual:

- si `descuento_porcentaje` y `descuento_monto` vienen correctos, se usan tal cual
- si ambos vienen en cero pero `subtotal > total`, el ticket reconstruye el descuento faltante
- si `total > subtotal`, no debe inventar descuento negativo

Ejemplo de recuperacion valida:

- subtotal: `199.00`
- descuento almacenado: `0.00`
- total: `169.15`

El ticket debe mostrar:

- descuento monto: `29.85`
- descuento porcentaje: `15.00`

## Anomalias a vigilar

### Anomalia

Ticket muestra descuento `0.00` pero el total es menor al subtotal.

### Senal

`Subtotal` y `Total` no coinciden con la linea de descuento.

### Zona probable

- `services/sale_ticket_totals_service.py`
- `ui/main_window.py`

### Anomalia

Error por atributo faltante al abrir ticket.

### Senal

Mensajes como `Venta object has no attribute descuento_porcentaje`.

### Zona probable

- `database/models.py`
- migraciones de ventas

### Anomalia

Ticket falla cuando la venta no tiene cliente.

### Senal

Error al intentar renderizar nombre, codigo o telefono de cliente nulo.

### Zona probable

- `ui/main_window.py`

### Anomalia

Ticket muestra configuracion vacia del negocio.

### Senal

Faltan nombre del negocio, pie o impresora aunque la venta abre.

### Zona probable

- `services/business_settings_service.py`
- fallback de `ui/main_window.py`

## Cobertura actual

- `tests/test_sale_ticket_totals_service.py`
  - usa descuento almacenado cuando existe
  - reconstruye descuento faltante
  - evita descuento negativo
  - preserva subtotal y total al reconstruir

## Checklist manual puntual

1. abrir `Ventas recientes`
2. seleccionar venta sin cliente
3. abrir ticket y confirmar que no falla
4. seleccionar venta con descuento actual y validar subtotal, descuento y total
5. seleccionar venta antigua con descuento faltante y validar reconstruccion
6. revisar que el folio y la fecha correspondan a la venta seleccionada

## Limites actuales

- el ticket sigue armado desde `ui/main_window.py`
- la reconstruccion actual solo corrige presentacion, no repara datos historicos
- falta cobertura de render completo del texto del ticket

## Siguiente paso recomendado

Antes de refactorizar esta zona:

1. agregar pruebas de render textual del ticket
2. mantener la logica numerica en servicios puros
3. no mezclar cambios de ticket con cambios de cobro o guardado de ventas

## Ideas futuras

- mantener fuera del ticket el `usuario` tecnico del sistema
- evaluar mas adelante un campo mas claro para operacion, por ejemplo `Atendido por` o `Empleado`
- no implementar ese dato hasta definir bien su fuente y su diferencia contra el usuario interno
- tomar como referencia visual futura los tickets de retiro de dinero de `7-Eleven` en Japon: composicion limpia, jerarquia fuerte y lectura muy rapida
