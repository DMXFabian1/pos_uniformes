# Satelite de consulta y cache local futuro

## Contexto

La app satelite de `Presupuestos` ya puede operar conectandose por red local a la base PostgreSQL que vive en la PC principal.

La decision de producto actual es mantener el satelite como una terminal de consulta y presupuesto:

- consulta precios reales
- consulta catalogo real
- arma presupuestos
- no cobra
- no descuenta inventario
- no sustituye a `Caja`

Esto reduce mucho el riesgo operativo y permite validar el flujo real sin sobrecomplicar la arquitectura.

## Decision actual

### Fuente de verdad

- la PC principal sigue siendo la fuente de verdad
- PostgreSQL vive en la PC principal
- la app satelite actua como cliente conectado a esa base

### Alcance operativo del satelite

Por ahora el satelite se considera una terminal de:

- consulta de precios
- consulta de productos
- armado de presupuestos
- pruebas reales de atencion en piso

No debe considerarse todavia una terminal de:

- cobro
- corte
- inventario
- apartados sensibles
- operacion offline completa

## Ventajas del enfoque actual

- se prueba con productos y precios reales
- no se duplica catalogo
- no hace falta instalar el POS principal en la satelite
- se valida la UX real del kiosko/presupuesto antes de construir mas complejidad

## Limite actual

La PC principal debe permanecer encendida para que la satelite funcione.

Si la principal se apaga o la red local falla:

- la satelite no puede consultar la base
- la satelite no puede traer precios en vivo
- la satelite no puede operar como hoy

## Que NO se quiere hacer todavia

No se recomienda en esta etapa:

- una replica completa de la base en la satelite
- sincronizacion general de toda la operacion
- permitir cobros offline
- mezclar esta mejora con `Caja` o `Inventario`

Eso elevaria demasiado el riesgo para la etapa actual.

## Mejora futura recomendada

La siguiente evolucion razonable del satelite no es una replica completa, sino una `cache local de lectura`.

Tambien conviene que el propio programa haga el chequeo de arranque, en lugar de depender siempre de un script externo.

### Objetivo de esa cache

Permitir continuidad minima si la principal no esta disponible temporalmente.

### Alcance sugerido v1

- al iniciar, intentar validar la configuracion de conexion y regenerar lo minimo necesario para abrir contra la PC principal
- recordar la ultima configuracion valida de conexion usada por la satelite
- guardar localmente un snapshot ligero del catalogo visible
- guardar localmente precios
- permitir consulta de precio y producto aun sin conexion usando el ultimo snapshot local valido
- mostrar claramente que el satelite esta en `modo cache`

### Aclaracion importante

No se propone "usar la ultima base de datos" como si la satelite tuviera una copia completa operativa.

La idea correcta es:

- recordar la ultima configuracion valida
- intentar conectar en cada arranque
- si no conecta, degradar a `modo cache`
- usar solo el ultimo snapshot local de lectura para catalogo y precios

Eso evita prometer una operacion offline mas grande de la que realmente existe.

### Lo que no debe hacer esa cache v1

- no cobrar
- no confirmar ventas
- no alterar inventario
- no empujar cambios automaticos complejos

## Posible evolucion posterior

Solo si el uso real lo justifica, evaluar una segunda iteracion:

- borradores de presupuesto offline
- estado `pendiente de sincronizar`
- envio posterior a la principal cuando regrese la conexion

Esto debe considerarse un subproyecto aparte, no un parche.

## Propuesta tecnica por fases

### Fase 1. Operacion conectada estable

- mantener la principal como host PostgreSQL
- estabilizar `pos_uniformes.env` de la satelite
- validar flujo real de consulta y presupuesto
- observar dependencias reales de red y tiempos de uso

### Fase 2. Cache local de lectura

- integrar el chequeo de arranque dentro de la app satelite
- validar o regenerar automaticamente la configuracion de conexion al abrir
- exportar o sincronizar snapshot de catalogo/precios al iniciar cuando si haya conexion
- permitir modo lectura si no hay conexion usando el ultimo snapshot local
- mostrar banner visible `Sin conexion / usando cache`

### Fase 3. Borradores offline

- guardar borradores localmente
- marcarlos como pendientes
- sincronizarlos al reconectar

## Riesgos a cuidar

- no confundir cache con fuente de verdad
- no mostrar precios stale sin advertencia visible
- no permitir operaciones sensibles en modo degradado
- no duplicar presupuestos si despues se agrega sincronizacion

## Senales para decidir si vale la pena programarlo

Conviene avanzar esta mejora si se observa en piso que:

- el satelite se usa varias horas al dia
- la principal no siempre puede quedar encendida
- la red local se cae de forma perceptible
- el operador necesita seguir consultando precios aunque no pueda emitir nada

## Anotaciones de UX detectadas en prueba real

- el boton `Agregar al presupuesto` debe ganar protagonismo visual dentro del satelite
- en ciertas resoluciones o distribuciones de la ventana, la accion queda demasiado abajo o puede sentirse tapada por la densidad de la pestaña
- antes de mover logica, conviene revisar layout y jerarquia visual para que la accion principal del flujo quede siempre evidente
- si la satelite va a operar como kiosko tactil, conviene evaluar scroll por arrastre mas natural en tablas y listados, para no depender de barras finas o rueda de mouse

## Estado

- `2026-04-11`: decision de producto tomada
- `2026-04-11`: documentado como frente futuro
- implementacion pospuesta hasta terminar la etapa de validacion operativa del satelite conectado
