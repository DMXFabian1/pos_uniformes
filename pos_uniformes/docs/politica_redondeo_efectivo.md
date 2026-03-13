# Politica futura. Redondeo de cobro

## Objetivo

Definir una politica de redondeo de cobro antes de tocar calculos, cambio, ticket o cierre de venta.

## Motivo

En operacion se quiere evitar batallar con centavos en cualquier modalidad de cobro. Si el sistema sigue cobrando montos con centavos sin una regla clara, se generan diferencias entre:

- total visible
- efectivo recibido
- cambio entregado
- ticket
- corte de caja

## Regla de trabajo

No implementar redondeo hasta cerrar esta decision documental y validarla con operacion.

## Preguntas que deben resolverse

1. Si la regla debe aplicar igual a `Efectivo`, `Transferencia` y `Mixto`.
2. Si el redondeo puede ser mayormente a favor del negocio sin sentirse abusivo.
3. Cual es la unidad minima permitida:
   - `0.10`
   - `0.50`
   - `1.00`
4. Si el redondeo debe verse como linea explicita en caja y en ticket.
5. Si el total contable y el total cobrado deben seguir siendo el mismo o si se necesita guardar ambos.

## Decision actual propuesta

Se busca coherencia por encima de reglas distintas por metodo de pago.

Propuesta actual:

- aplicar la misma regla al total final de la venta en `Efectivo`, `Transferencia` y `Mixto`
- usar una regla contenida, mayormente a favor del negocio
- redondear al tramo `.00` o `.50`

Tramos propuestos:

- `.00` a `.19` -> queda en `.00`
- `.20` a `.69` -> sube a `.50`
- `.70` a `.99` -> sube al siguiente `.00`

Ejemplos:

- `179.10` -> `179.00`
- `179.26` -> `179.50`
- `179.68` -> `179.50`
- `179.74` -> `180.00`

## Criterio comercial

La regla no pretende esconder cargos raros ni castigar de forma agresiva. La idea es:

- mantener ajustes pequenos
- hacer el cobro mas operativo
- usar la misma regla siempre
- evitar que el cliente vea un total en pantalla y otro al momento de pagar

## Regla contable y de calculo

Los centavos que hoy aparecen suelen venir del descuento aplicado a la venta. Por eso el redondeo no debe mezclarse con el descuento ni reemplazarlo.

Orden correcto del calculo:

1. calcular `subtotal`
2. calcular `descuento`
3. obtener `total despues de descuento`
4. aplicar `ajuste_redondeo` sobre ese total final
5. obtener `total_cobrado`

Esto implica:

- `descuento` y `redondeo` son conceptos distintos
- el ticket no debe disfrazar redondeo como descuento
- el corte de caja debe poder separar cuanto se desconto y cuanto se ajusto por redondeo
- si en el futuro se guarda el ajuste, debe vivir como dato propio

## Recomendacion tecnica inicial

Antes de cualquier cambio de codigo, modelar por separado:

- `total_bruto`
- `descuento`
- `total_despues_descuento`
- `ajuste_redondeo`
- `total_cobrado`

Aunque hoy no existan todos esos campos, esa separacion ayuda a evitar mezclar descuento con redondeo.

## Riesgos si se implementa sin definicion

- cambio incorrecto al cobrar
- ticket que muestra un total distinto al cobrado
- diferencias pequenas acumuladas en caja
- confusion del operador frente al cliente
- reportes que mezclan descuento con redondeo

## Casos que deben probarse cuando llegue el momento

### Modalidades

- efectivo
- transferencia
- mixto

### Totales

- total `179.10` -> `179.00`
- total `179.26` -> `179.50`
- total `179.74` -> `180.00`

### Cobro

- recibido exacto al total redondeado
- recibido mayor al total redondeado
- cambio cero
- cambio positivo

### Ticket

- mostrar subtotal
- mostrar descuento
- mostrar ajuste por redondeo si aplica
- mostrar total final cobrado

## Criterio de salida para implementarlo

Solo avanzar a codigo cuando exista una decision explicita sobre:

- alcance
- unidad de redondeo
- presentacion en caja
- presentacion en ticket
- impacto en corte de caja
