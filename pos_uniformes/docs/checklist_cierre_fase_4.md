# Checklist de Cierre Fase 4

## Objetivo

Cerrar la fase de extraccion estructural con una validacion corta pero suficiente, y al mismo tiempo cubrir la validacion manual pendiente mas importante de `Fase 1. Caja`.

## Estado esperado antes de correrla

- Base actual respaldada y considerada checkpoint bueno.
- Delta legacy ya aplicado.
- Suite puntual verde.
- `ui/main_window.py` funcionando como coordinador y no como propietario de nuevas reglas.

## Precheck tecnico

- Correr:
  - `./.venv/bin/python scripts/check_startup_health.py`
- Verificar:
  - conexion a PostgreSQL
  - esquema sincronizado
  - arranque sin imports rotos

## Suite minima recomendada

- Correr:
  - `PYTHONPATH='/Users/danielfabian/Documents/Playground 2' ./.venv/bin/python scripts/check_operational_flows.py`
- Correr:
  - `PYTHONPATH='/Users/danielfabian/Documents/Playground 2' ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`

## Validacion manual corta

### Caja y Cobro

- Abrir Caja sin cliente y vender un SKU.
- Abrir Caja con cliente enlazado y vender un SKU.
- Cambiar de cliente con carrito ya armado y confirmar que el beneficio visible se actualiza de forma coherente.
- Probar promo manual sin autorizacion valida y confirmar bloqueo.
- Probar promo manual con autorizacion valida y confirmar porcentaje correcto.
- Validar cobro en:
  - efectivo
  - transferencia
  - mixto
- Confirmar que el ticket/comprobante abre despues de la venta.

### Caja y sesion operativa

- Abrir sesion de caja.
- Registrar un movimiento manual.
- Hacer correccion de apertura si aplica.
- Ejecutar corte de caja.
- Confirmar feedback visible correcto en cada paso.

### Apartados y Tickets

- Crear apartado.
- Registrar abono.
- Entregar apartado.
- Cancelar un apartado de prueba si el entorno lo permite.
- Abrir comprobante o ticket asociado.

### Catalogo e Inventario

- Abrir Catalogo y verificar que carga.
- Abrir Inventario y verificar que carga.
- Buscar una escuela del delta importado y confirmar que aparecen sus productos.
- Abrir un producto, revisar su presentacion y confirmar que el QR/etiqueta siguen accesibles.

### Configuracion

- Abrir Configuracion.
- Revisar carga de negocio, usuarios y respaldos.
- Confirmar que el modulo de respaldos lista el dump bueno actual.

## Criterio para declarar Fase 4 cerrada

- El precheck pasa.
- La bateria operativa pasa.
- La app abre y los dominios principales responden.
- No aparece una regresion estructural nueva ligada a extracciones recientes.
- `main_window.py` ya no recibe nuevas reglas densas; solo integracion.

## Cierre formal

- Fecha de cierre: `2026-03-20`
- Estado: `validated-manual`
- Resultado:
  - precheck tecnico validado
  - bateria operativa validada
  - validacion manual confirmada en Caja, sesion operativa, Apartados, Catalogo, Inventario y Configuracion
  - `ui/main_window.py` queda aceptado como coordinador principal, con la mayor parte de la logica operativa ya extraida a servicios, helpers y dialogs
- Riesgo residual aceptado:
  - impresion y validacion Windows siguen como frente separado
  - quedan mejoras de UX y estabilidad operativa para `Fase 5`
- Paso siguiente:
  - entrar a `Fase 5. Optimizacion fina`

## Criterio para considerar Fase 1 suficientemente cerrada

- Venta manual validada con cliente y sin cliente.
- Promo manual validada con y sin autorizacion.
- Cambio de cliente no altera descuento o beneficio de forma incoherente.
- Cobro y ticket cierran sin inconsistencias visibles.

## Si aparece una falla

- No abrir otro refactor grande.
- Registrar el bug exacto.
- Corregir solo el flujo afectado.
- Repetir esta checklist antes de pasar a `Fase 5`.
