# Empleadas, Atribucion y Comisiones

## Objetivo

Definir una base funcional y tecnica para el futuro modulo de `empleadas`, de forma que sirva como identidad comercial transversal del negocio y no solo como usuario interno del POS.

Este modulo debe nacer pensando desde el inicio en tres frentes:

- POS principal
- kiosko
- app movil futura

## Principio base

- `usuario` = quien opera tecnicamente el sistema
- `empleada` = a quien se acredita la venta o la atencion comercial

No deben tratarse como la misma entidad por defecto.

La trazabilidad tecnica y la atribucion comercial deben poder convivir sin contaminarse.

## Vision del modulo

La entidad `empleada` debe ser una identidad operativa unificada del negocio, reutilizable en:

- ventas del POS
- atencion en kiosko
- seguimiento comercial desde app movil
- analitica y comisiones

## Base del modulo

La ficha inicial de `empleada` debe contemplar:

- nombre completo
- codigo interno
- telefono
- rol operativo
- estado activo/inactivo
- QR unico
- PIN corto
- foto opcional

## Relacion con el sistema

### Usuario del sistema

Debe seguir cubriendo:

- acceso tecnico al POS
- permisos administrativos
- auditoria de acciones sensibles
- apertura/cierre de caja
- cancelaciones, autorizaciones y cambios administrativos

### Empleada

Debe cubrir:

- identidad comercial
- atribucion de venta
- metas y productividad
- relacion con kiosko
- relacion con app movil
- comisiones y liquidacion

## Relacion con el POS

En el POS se debe permitir:

- identificar a la empleada activa
- acreditar ventas
- acreditar apartados
- acreditar entregas
- diferenciar entre operador del sistema y vendedora acreditada

### Decision de modelo recomendada

- conservar `usuario_id` en `venta` como operador real del POS
- introducir despues `employee_id` o `seller_employee_id` como vendedora acreditada

Esto evita perder trazabilidad cuando:

- una cajera cobra pero otra empleada hizo la venta
- una administradora corrige o cancela una operacion
- una venta nace en kiosko y se cierra en POS

## Relacion con kiosko

El kiosko debe poder reutilizar `empleada` como identidad rapida para:

- identificarse con QR
- confirmar identidad con PIN si hace falta
- tomar una atencion o pedido
- vincular una cotizacion, apartado o venta futura
- registrar quien atendio al cliente

La autenticacion del kiosko debe ser ligera, pero no debe sustituir validaciones mas fuertes para acciones sensibles.

## Relacion con app movil

La app movil futura debe poder usar la misma entidad `empleada` para:

- ver ventas atribuidas
- ver metas y avance del dia/periodo
- revisar apartados y entregas
- consultar clientes atendidos
- revisar comisiones y liquidaciones
- ver alertas o tareas comerciales

## Operacion diaria esperada

### Flujo minimo

- iniciar turno
- identificarse rapido con QR
- confirmar identidad con PIN cuando aplique
- tomar ventas o atenciones
- cerrar turno

### Operacion comercial

- registrar quien atendio
- reasignar venta si hizo falta
- medir metas del dia o del periodo
- separar operadora POS de vendedora acreditada cuando no coincidan

## Ventas y atribucion

La analitica futura por empleada debe derivarse de ventas reales confirmadas.

### Indicadores base

- ventas por empleada
- tickets por empleada
- unidades vendidas
- apartados creados
- apartados entregados
- conversion de presupuesto a venta
- clientes atendidos
- clientes recurrentes

## Comisiones y liquidacion

La comision no debe salir de capturas manuales, sino de operaciones reales del sistema.

### Regla general

- la fuente de verdad es la venta confirmada
- cancelaciones y reversos deben ajustar la atribucion
- descuentos, ajustes y promos especiales deben tener politica explicita

### Componentes esperados

- regla de comision por porcentaje
- regla por monto fijo
- regla por categoria o linea
- exclusiones administrativas
- retenciones internas
- liquidacion por periodo
- historial de pagos o cortes comerciales

## Analitica futura

La analitica por empleada debe contemplar:

- top vendedoras
- ingreso generado
- ticket promedio
- productividad por turno
- cumplimiento de meta
- comparacion entre operadora del POS y vendedora acreditada
- conversion por canal
  - kiosko -> POS
  - app movil -> POS

## Control y auditoria

El sistema debe poder responder con claridad:

- quien abrio caja
- quien cobro
- quien atendio la venta
- quien autorizo promo manual
- quien cancelo
- quien entrego apartado
- quien hizo cambios sensibles

## Fases recomendadas

### Etapa 1. Diseno y contrato

- cerrar modelo `usuario` vs `empleada`
- documentar QR y PIN
- definir si `employee_id` vive en venta, apartado y presupuesto

### Etapa 2. Identidad operativa

- ficha de empleada
- QR unico
- PIN corto
- estados y roles

### Etapa 3. Atribucion comercial

- asignacion de empleada en venta
- separacion entre operadora POS y vendedora acreditada
- soporte base en kiosko

### Etapa 4. Analitica operativa

- ventas, tickets, piezas, apartados y conversiones por empleada
- filtros y exportacion por empleada

### Etapa 5. Comisiones y liquidacion

- reglas de comision
- retenciones
- cortes comerciales
- historial de pagos

### Etapa 6. Integracion movil

- consultas de desempeno
- metas
- comisiones
- tareas comerciales y seguimiento

## Alcance recomendado de la primera implementacion futura

Cuando abramos este modulo, el primer corte sano deberia ser:

- ficha de empleada
- QR + PIN
- asignacion de empleada a venta
- trazabilidad basica en POS

No conviene arrancar directamente por:

- comisiones complejas
- analitica avanzada
- comparativos por canal

## Riesgos a evitar

- usar `usuario` y `empleada` como sinonimos
- ligar comisiones a capturas manuales
- perder trazabilidad entre kiosko, POS y app movil
- abrir analitica de empleados antes de cerrar el modelo de atribucion
- meter esta logica nueva dentro de `ui/main_window.py`

## Decision vigente

Por ahora:

- no integrar analitica de empleados dentro del tablero actual
- dejar el modulo documentado como iniciativa futura
- abrirlo despues del cierre de estabilizacion y del pulido general de `Fase 5`
