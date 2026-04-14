# Conteo por SKU y recordatorios futuros

## Contexto

Queda anotada una mejora futura para que el sistema recuerde cuando fue contado cada `SKU` y pueda sugerir reconteos sin saturar la operacion diaria.

La idea nace del flujo real de piso: despues de usar `Conteo fisico` por escaneo uno a uno, conviene que el sistema conserve una huella por presentacion para saber que tan reciente fue el ultimo conteo.

## Decision tomada

- el seguimiento debe ser `por SKU`
- no se implementara por zona como base principal
- los avisos futuros deben ser discretos, no invasivos
- no se quieren popups constantes

## Objetivo funcional

Permitir que `Inventario` responda rapidamente preguntas como:

- que presentaciones nunca se han contado
- que presentaciones se contaron hoy
- cuales llevan varios dias sin reconteo
- cuales deberian revisarse pronto

## Modelo recomendado

Cada presentacion debe conservar una huella minima de conteo:

- `ultimo_conteo_at`
- `ultimo_conteo_referencia`
- `ultimo_conteo_observacion` (opcional en una segunda iteracion)
- `veces_contado` (opcional, no requerida para la primera version)

## Regla operativa

La fecha de ultimo conteo debe actualizarse solo cuando un `Conteo fisico` se aplica realmente.

Esto implica:

- no actualizar solo por abrir el dialogo
- no actualizar por escaneos que no se confirman
- actualizar solo los `SKU` incluidos en el lote confirmado

## UX recomendada

La informacion debe mostrarse de forma visible pero tranquila.

### Inventario

Propuesta inicial:

- columna o badge `Ult. conteo`
- estados legibles:
  - `Contado hoy`
  - `Hace 2 dias`
  - `Hace 9 dias`
  - `Nunca`

### Filtros utiles

- `Sin conteo`
- `Conteo reciente`
- `Conteo vencido`

### Resumen discreto

En lugar de alertas duras:

- badge o contador tipo `Pendientes de reconteo: 18`
- uso de color suave:
  - verde para reciente
  - ambar para por revisar
  - rojo suave para vencido
  - gris para nunca contado

## Regla inicial sugerida

Para una primera version simple:

- `0 a 3 dias`: reciente
- `4 a 7 dias`: por revisar
- `8+ dias`: vencido

Esta regla puede volverse configurable despues si operacion lo necesita.

## Orden recomendado de implementacion

### V1

- guardar `ultimo conteo por SKU`
- mostrar `Ult. conteo` en `Inventario`

### V2

- agregar filtros `Sin conteo` y `Conteo vencido`

### V3

- agregar resumen superior o aviso discreto en `Inventario` o `Dashboard`

## Criterios para no saturar

- evitar popups automaticos por producto
- priorizar resumenes y filtros por encima de alertas modales
- no mezclar esta mejora con el flujo de captura principal del conteo
- mantener el conteo rapido como tarea principal y el recordatorio como soporte secundario

## Estado

- `2026-04-11`: idea aprobada conceptualmente y anotada en hoja de ruta
- implementacion pospuesta para una iteracion futura
