# Subflujo Caja: Origen de la Venta

## Objetivo

Definir el comportamiento esperado para atribuir de forma discreta el origen comercial de una venta dentro de `Caja`, sin mezclar esta decision con la identidad tecnica del usuario que opera el POS.

## Alcance

Este subflujo cubre:

- origen comercial visible de la venta en Caja
- lectura de QR de equipo comercial
- convivencia entre operador tecnico y origen comercial
- comportamiento por defecto cuando no se identifica a nadie
- reglas de cambio antes de confirmar la venta

No cubre:

- calculo de comisiones
- analitica por empleada
- integracion de kiosko o app movil
- liquidaciones o cortes comerciales

## Vocabulario visible en UI

Para reducir friccion operativa, Caja no debe usar en pantalla palabras como:

- `comision`
- `vendedora acreditada`
- `atribucion`
- `venta de quien`

El lenguaje visible recomendado es:

- etiqueta principal: `Origen`
- estados:
  - `Libre`
  - `Asistido`
  - `Directo`
- acciones:
  - `Identificar`
  - `Tomar directo`
  - `Liberar`

## Mapeo interno

Detras de ese lenguaje discreto, el modelo tecnico propuesto es:

- `usuario_id`
  - operador tecnico del POS
- `seller_employee_id`
  - identidad comercial acreditada para la venta
- `credit_mode`
  - `UNASSIGNED`
  - `EMPLOYEE`
  - `OPERATOR_DIRECT`

Mapeo entre UI e interno:

- `Libre` -> `UNASSIGNED`
- `Asistido` -> `EMPLOYEE`
- `Directo` -> `OPERATOR_DIRECT`

## Regla principal

1. Toda venta debe conservar `usuario_id` como operador tecnico.
2. El origen comercial no debe asumirse como venta del operador por default.
3. Si se escanea un QR del equipo comercial, el origen pasa a `Asistido`.
4. Si el operador decide marcar que la venta fue tomada directamente por el mismo, el origen pasa a `Directo`.
5. Si no ocurre ninguna de las dos cosas, la venta permanece en `Libre`.
6. La venta puede confirmarse en cualquiera de los tres estados durante la primera iteracion.

## Principio operativo

El sistema debe distinguir claramente entre:

- quien opero la caja
- quien atendio comercialmente
- cuando no hubo atribucion comercial explicita

Esto evita mezclar:

- ventas realmente tomadas por el operador
- ventas supervisadas o aceleradas por el operador
- ventas que pertenecen al equipo comercial

## Flujo esperado

### Caso A. Venta libre

- Se abre una venta nueva.
- Caja muestra `Origen: Libre`.
- No se escanea QR del equipo.
- No se usa `Tomar directo`.
- La venta se confirma en `Libre`.

Uso esperado:

- ventas rapidas
- apoyo operativo
- supervision sin atribucion comercial

### Caso B. Venta asistida

- Se abre una venta nueva.
- Caja muestra `Origen: Libre`.
- Se escanea QR del equipo comercial.
- Caja cambia a `Origen: Asistido`.
- La venta queda vinculada a `seller_employee_id`.
- Despues puede escanearse el QR del cliente y seguir el flujo normal.

Uso esperado:

- una integrante del equipo atendio al cliente
- otra persona puede operar o cobrar sin perder la atribucion comercial

### Caso C. Venta directa

- Se abre una venta nueva.
- Caja muestra `Origen: Libre`.
- El operador usa `Tomar directo`.
- Caja cambia a `Origen: Directo`.
- La venta se confirma como atencion directa del operador, sin requerir que el operador exista como `empleada`.

Uso esperado:

- ventas que el operador realmente tomo por cuenta propia

### Caso D. Cambio antes de confirmar

- Mientras la venta siga en borrador:
  - puede escanearse un QR del equipo para pasar a `Asistido`
  - puede usarse `Tomar directo`
  - puede usarse `Liberar` para volver a `Libre`
- Al confirmar, el origen queda congelado.

## Contrato UX minimo

Caja debe mostrar un bloque pequeno y siempre visible con:

- `Origen: Libre | Asistido | Directo`
- `Identificar`
- `Tomar directo`
- `Liberar`

No debe mostrar en esa zona:

- porcentajes
- metas
- palabras de comision
- lenguaje sensible para el equipo comercial

Si el origen es `Asistido`, la UI puede mostrar el nombre corto de la persona identificada, pero sin explicar en pantalla para que se usa despues ese dato.

## Decision cerrada de uso

- `Directo` puede usarse por cualquier operador con acceso a Caja.
- No queda restringido solo a `ADMIN`.
- La restriccion relevante no es el rol administrativo, sino tener permiso operativo para abrir y cobrar una venta.
- Si despues hiciera falta un control adicional, debe resolverse por permisos de Caja, no por el concepto de origen comercial.

## Contrato de QR

Para evitar ambiguedades entre codigos:

- QR de equipo comercial:
  - prefijo recomendado `EMP:`
- QR de cliente:
  - prefijo recomendado `CLI:`

Reglas:

- si se escanea `EMP:...`, Caja intenta resolver identidad comercial
- si se escanea `CLI:...`, Caja sigue el subflujo actual de cliente
- no se debe adivinar el tipo de QR por formato ambiguo

## Modelo de datos recomendado para V1

### Nueva entidad comercial

- tabla `empleada`
  - `id`
  - `codigo`
  - `nombre_completo`
  - `telefono`
  - `activo`
  - `qr_token`
  - `pin_hash`
  - `created_at`
  - `updated_at`

### Venta

- mantener `usuario_id` como operador tecnico
- agregar `seller_employee_id` nullable
- agregar `credit_mode` con enum:
  - `UNASSIGNED`
  - `EMPLOYEE`
  - `OPERATOR_DIRECT`

## Reglas de persistencia

- `UNASSIGNED`
  - `seller_employee_id = null`
- `EMPLOYEE`
  - `seller_employee_id = id de empleada`
- `OPERATOR_DIRECT`
  - `seller_employee_id = null`

La informacion necesaria para distinguir una venta libre de una venta directa debe vivir en `credit_mode`, no inferirse despues.

## Cancelacion y trazabilidad

- una cancelacion no debe borrar el origen historico
- la venta cancelada conserva:
  - `usuario_id`
  - `seller_employee_id`
  - `credit_mode`
- lo que cambia despues es su impacto analitico, no su trazabilidad

## Archivos candidatos para la futura implementacion

- `database/models.py`
- `services/venta_service.py`
- `ui/views/cashier_view.py`
- `ui/main_window.py`

Servicios candidatos nuevos:

- `services/employee_identity_service.py`
- `services/sale_origin_assignment_service.py`

## Riesgos a vigilar

- asumir por default que toda venta sin QR es del operador
- obligar al operador a existir como `empleada`
- usar lenguaje visible que genere friccion con el equipo
- mezclar origen comercial con permisos del sistema
- congelar mal el origen antes de confirmar la venta
- permitir QRs ambiguos entre cliente y equipo comercial

## Checklist de diseno antes de programar

- decidir si `Libre` sera permitido permanentemente o solo durante la adopcion inicial
- definir copy exacto de la banda visible en Caja
- definir el formato final del QR de equipo
- definir si el nombre de la persona identificada se muestra completo o resumido

## Primer corte recomendado

La primera implementacion futura deberia hacer solo esto:

- crear `empleada` como identidad comercial
- agregar `seller_employee_id` y `credit_mode` a `venta`
- mostrar bloque `Origen` en Caja
- permitir `Identificar`, `Tomar directo` y `Liberar`
- congelar el origen al confirmar

No deberia incluir todavia:

- comisiones
- analitica
- kiosko
- app movil
- reglas administrativas complejas
