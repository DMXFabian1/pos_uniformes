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
- `venta de quien`

El lenguaje visible recomendado es:

- etiqueta principal: `Responsable`
- estados:
  - `Sin asignar`
  - `Asignada`
  - `Directa`
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

- `Sin asignar` -> `UNASSIGNED`
- `Asignada` -> `EMPLOYEE`
- `Directa` -> `OPERATOR_DIRECT`

## Regla principal

1. Toda venta debe conservar `usuario_id` como operador tecnico.
2. El origen comercial no debe asumirse como venta del operador por default.
3. Si se escanea un QR del equipo comercial, el origen pasa a `Asignada`.
4. Si el operador decide marcar que la venta fue tomada directamente por el mismo, el origen pasa a `Directa`.
5. Si no ocurre ninguna de las dos cosas, la venta permanece en `Sin asignar`.
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
- Caja muestra `Responsable: Sin asignar`.
- No se escanea QR del equipo.
- No se usa `Tomar directo`.
- La venta se confirma en `Sin asignar`.

Uso esperado:

- ventas rapidas
- apoyo operativo
- supervision sin atribucion comercial

### Caso B. Venta asistida

- Se abre una venta nueva.
- Caja muestra `Responsable: Sin asignar`.
- Se escanea QR del equipo comercial.
- Caja cambia a `Responsable: Asignada`.
- La venta queda vinculada a `seller_employee_id`.
- Despues puede escanearse el QR del cliente y seguir el flujo normal.

Uso esperado:

- una integrante del equipo atendio al cliente
- otra persona puede operar o cobrar sin perder la atribucion comercial

### Caso C. Venta directa

- Se abre una venta nueva.
- Caja muestra `Responsable: Sin asignar`.
- El operador usa `Tomar directo`.
- Caja cambia a `Responsable: Directa`.
- La venta se confirma como atencion directa del operador, sin requerir que el operador exista como `empleada`.

Uso esperado:

- ventas que el operador realmente tomo por cuenta propia

### Caso D. Cambio antes de confirmar

- Mientras la venta siga en borrador:
  - puede escanearse un QR del equipo para pasar a `Asignada`
  - puede usarse `Tomar directo`
  - puede usarse `Liberar` para volver a `Sin asignar`
- Al confirmar, el origen queda congelado.

## Contrato UX minimo

Caja debe mostrar un bloque pequeno y siempre visible con:

- `Responsable: Sin asignar | Asignada | Directa`
- `Identificar`
- `Tomar directo`
- `Liberar`

No debe mostrar en esa zona:

- porcentajes
- metas
- palabras de comision
- lenguaje sensible para el equipo comercial

Si el origen es `Asignada`, la UI puede mostrar el nombre corto de la persona identificada, por ejemplo:

- `Responsable: Fer`
- `Responsable: Andrea`

sin explicar en pantalla para que se usa despues ese dato.

## Copy exacto del bloque en Caja

El bloque visible debe quedar asi:

- etiqueta fija del bloque:
  - `Responsable`
- valor visible del estado:
  - `Sin asignar`
  - nombre corto de la persona identificada, por ejemplo `Fer` o `Andrea`
  - `Directa`
- botones visibles:
  - `Identificar`
  - `Tomar directo`
  - `Liberar`

Render esperado del bloque:

- estado vacio:
  - `Responsable: Sin asignar`
- estado con QR del equipo:
  - `Responsable: Fer`
- estado tomado por el operador:
  - `Responsable: Directa`

Reglas de copy:

- no mostrar la palabra `Asignada` como estado visible final si ya existe nombre corto
- no mostrar `comision`, `acreditacion`, `origen comercial` o frases similares dentro del bloque
- mantener `Tomar directo` como el unico texto discretamente codificado
- `Liberar` solo aparece habilitado cuando el estado actual no es `Sin asignar`

## Decision cerrada de uso

- `Tomar directo` puede usarse por cualquier operador con acceso a Caja.
- No queda restringido solo a `ADMIN`.
- La restriccion relevante no es el rol administrativo, sino tener permiso operativo para abrir y cobrar una venta.
- Si despues hiciera falta un control adicional, debe resolverse por permisos de Caja, no por el concepto de origen comercial.
- `Sin asignar` se permite de forma permanente, no solo durante la adopcion inicial.
- `Sin asignar` representa una venta valida sin atribucion comercial explicita.
- Esto permite distinguir entre:
  - ventas realmente tomadas por el operador
  - ventas del equipo comercial
  - ventas operadas o supervisadas sin acreditacion comercial
- En fases futuras:
  - `Asignada` podra entrar a comisiones
  - `Directa` podra medirse aparte como atencion propia del operador
  - `Sin asignar` no debera entrar a comisiones

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

## Formato final del QR de equipo para V1

Para la primera iteracion, el QR del equipo debe usar este formato exacto:

- `EMP:{codigo}`

Ejemplos validos:

- `EMP:FER001`
- `EMP:ANDREA02`
- `EMP:VEND-14`

Reglas:

- `EMP:` debe ir en mayusculas
- el valor posterior se trata como `codigo` comercial legible
- no usar JSON, Base64 ni payloads largos en V1
- el scanner debe poder leerlo como texto plano y Caja debe resolverlo con comparacion exacta
- si el codigo no existe, Caja debe mostrar error breve y mantener el estado actual de `Responsable`
- el `codigo` no se muestra al cliente ni al equipo como estado final de la venta
- el `codigo` solo sirve para resolver internamente a la empleada correcta

Ejemplo de resolucion:

- el QR lee `EMP:VEND-1`
- Caja busca `codigo = VEND-1`
- el sistema encuentra a `Lupita`
- el bloque visible queda en `Responsable: Lupita` o en su nombre corto configurado

## Superficies donde debe verse el nombre

Cuando el origen comercial sea `EMPLOYEE`, el nombre visible de la empleada debe mostrarse tambien en:

- `Caja`
- ticket final de venta
- `Presupuestos`
- `Apartados`

Reglas:

- en `Caja`, el bloque visible muestra `Responsable: Lupita`
- en ticket final, debe imprimirse una linea discreta como `Responsable: Lupita`
- en `Presupuestos` y `Apartados`, debe guardarse y mostrarse el mismo dato visible para no perder continuidad operativa
- si el estado es `Sin asignar`, no debe inventarse nombre
- si el estado es `Directa`, no debe mostrarse un nombre de empleada; solo el estado correspondiente
- este dato visible sirve para seguimiento operativo, no para exponer reglas de comision

Razon de esta decision:

- facilita generar e imprimir codigos sin tooling extra
- acelera pruebas manuales con cualquier generador QR
- deja el flujo facil de depurar antes de introducir tokens mas opacos

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
