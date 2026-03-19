# Hoja de Ruta de Mejoras

## Objetivo

Registrar mejoras propuestas por operacion o producto y ubicarlas dentro del plan tecnico sin asumir que deban implementarse de inmediato.

## Regla de lectura

- Esta hoja no reemplaza `docs/plan_estabilizacion.md`.
- Una mejora puede quedar agendada para una fase futura aunque no sea la siguiente tarea.
- La fase sugerida indica el mejor momento tecnico para implementarla con bajo riesgo.

## Solicitudes abiertas

### 2026-03-13

#### 1. Sugerencias de busqueda en Catalogo e Inventario

- Idea:
  Al teclear en la busqueda de `Catalogo` e `Inventario`, mostrar sugerencias de coincidencia en lugar de depender solo del filtrado final. La primera version debe ser de sugerencias/autocompletado, no de prediccion avanzada.
- Dominio:
  `catalogo` e `inventario`
- Fase sugerida:
  `Fase 2. Catalogo e Inventario`
- Momento recomendado dentro de la fase:
  Despues de consolidar la busqueda textual compartida y antes de optimizaciones finas o ranking por historial.
- Prioridad:
  media
- Justificacion tecnica:
  - Ya existe una base compartida en `services/search_filter_service.py`.
  - `Catalogo` y `Inventario` ya conectan sus inputs de texto a handlers de filtros, asi que la mejora puede entrar como capa incremental.
  - Meter "prediccion" real en este momento mezclaria UX, ranking e historiales; eso eleva riesgo sin ser necesario para la primera mejora operativa.
- Alcance recomendado v1:
  - sugerir SKU, producto, color, talla, marca y escuela conforme se escribe
  - permitir seleccionar una sugerencia para llenar el input o insertar un alias como `sku:`, `producto:`, `color:`
  - mantener intacta la busqueda actual si el operador decide seguir escribiendo libre
- Estado:
  - `2026-03-18`: base `V1` implementada con `QCompleter` y logica compartida en `services/search_suggestion_service.py`; validada con pruebas y precheck, con validacion manual de UI aun pendiente
  - `2026-03-18`: ajuste `V2` aplicado para priorizar sugerencias en lenguaje natural cuando el usuario escribe texto normal y dejar los prefijos como capa avanzada
- Alcance recomendado v2:
  - ordenar sugerencias por frecuencia de uso, ventas recientes o coincidencia historica
  - evaluar esta capa despues, idealmente en `Fase 5`, cuando ya tengamos el flujo estable y medible
- Donde implementarla:
  - logica pura de sugerencias en un servicio nuevo, por ejemplo `services/search_suggestion_service.py`
  - integracion visual del input en `ui/views/products_view.py` y `ui/views/inventory_view.py`
  - `ui/main_window.py` debe quedarse solo coordinando eventos y refrescos, no calculando sugerencias complejas
- Riesgos a cuidar:
  - no disparar consultas o refrescos pesados en cada tecla
  - no ocultar resultados validos por una sugerencia mal elegida
  - no duplicar reglas que ya viven en `search_filter_service`
- Criterio de cierre esperado:
  - el operador puede encontrar productos mas rapido con 2 a 4 letras
  - la busqueda libre sigue funcionando igual que hoy
  - catalogo e inventario comparten la misma logica base de sugerencias

#### 2. Empleados, atribucion de ventas y comisiones derivadas del POS

- Idea:
  Soportar empleados vendedores con comisiones y analitica sin permitir reportes manuales de productos vendidos. Toda comision y toda estadistica debe salir del flujo real de venta confirmado dentro del POS.
- Dominios:
  `caja`, `venta`, `configuracion`, `analitica`
- Prioridad:
  alta
- Principios no negociables:
  - la fuente de verdad es la venta registrada en el POS
  - la salida de inventario debe seguir naciendo solo de `VentaService` e `InventarioService`
  - no debe existir captura manual de "vendi X piezas" para comisiones
  - cancelaciones y devoluciones futuras deben poder corregir atribucion y metricas
- Observacion de arquitectura actual:
  - `Venta` ya guarda `usuario_id`, lo que cubre al usuario operador actual
  - antes de introducir `employee_id`, hay que definir si `usuario que opera caja` y `empleado vendedor` son siempre la misma persona
  - si pueden ser personas distintas, conviene separar ambos conceptos para no contaminar auditoria, permisos y comisiones
- Decision de modelo a cerrar primero:
  - opcion A: reutilizar `usuario_id` como vendedor si el operador de caja y el vendedor siempre coinciden
  - opcion B: mantener `usuario_id` como operador del POS e introducir `employee_id` o `seller_employee_id` en la venta cuando el vendedor acreditado puede ser distinto
  - recomendacion actual: tratar esta decision como un checkpoint de diseno antes de abrir migraciones o UI
- Fases seguras de implementacion:
  - `Fase 1. Caja`
    - documentar el subflujo de asignacion de empleado en venta
    - resolver el modelo base de atribucion `usuario` vs `empleado`
    - capturar el vendedor al inicio de la venta o al abrir un ticket, sin cambiar aun calculos de comision
    - asegurar que la venta confirmada y la cancelacion conservan trazabilidad coherente
  - `Fase 3. Configuracion y Marketing`
    - crear administracion de empleados y, si aplica, reglas administrativas de comision
    - mantener estas reglas fuera de la pantalla principal de Caja
    - documentar permisos y estados activos/inactivos
  - `Fase 4. Extraccion estructural`
    - extraer servicios dedicados para atribucion, comisiones y analitica por empleado
    - mover agregaciones grandes fuera de `ui/main_window.py`
    - dejar la UI solo consumiendo resultados preparados
  - `Fase 5. Optimizacion fina`
    - agregar tablas derivadas o snapshots como `employee_sales_stats` solo si hacen falta por rendimiento
    - evaluar alertas de patrones sospechosos y rankings historicos
    - medir costo real antes de introducir cache o materializaciones
- Orden de extraccion conservador:
  - 1. documentar subflujo de venta con empleado antes de tocar esquema
  - 2. cerrar contrato de atribucion en un servicio puro, separado de la UI
  - 3. persistir el identificador del vendedor en la venta real
  - 4. extraer el calculo de comisiones a un servicio puro derivado de ventas confirmadas y canceladas
  - 5. extraer agregaciones de analitica por empleado a un servicio dedicado
  - 6. integrar selector y visualizacion en UI como capa final
  - 7. dejar alertas de patrones sospechosos para cuando la atribucion y analitica ya sean confiables
- Impacto por capa:
  - base de datos
    - posible tabla `employees` si el vendedor no coincide siempre con `usuario`
    - extension de `venta` para guardar vendedor acreditado
    - posible relacion o snapshot derivado para comisiones
    - `employee_sales_stats` solo como tabla derivada opcional, nunca como fuente primaria
  - interfaz POS
    - seleccion del empleado al iniciar una venta o abrir ticket
    - visibilidad clara del vendedor activo dentro de Caja
    - administracion de empleados desde configuracion si el modelo lo requiere
    - nuevas vistas o filtros en analitica por empleado
  - logica de negocio
    - servicio de atribucion de vendedor por venta
    - servicio de comisiones derivadas desde ventas reales
    - servicio de analitica por empleado
    - servicio futuro de deteccion de patrones sospechosos
- Alcance recomendado por entregas:
  - v1
    - atribucion confiable de vendedor en la venta
    - trazabilidad de venta y cancelacion
    - sin captura manual de productos vendidos
  - v2
    - comisiones calculadas sobre ventas confirmadas y reversadas en cancelaciones
    - consulta basica de ventas e ingresos por empleado
  - v3
    - ticket promedio, frecuencia de ventas y desempeno por categoria
    - filtros/exportacion por empleado en analitica
  - v4
    - patrones sospechosos y alertas operativas
- Donde implementarla:
  - base actual a revisar: `database/models.py`, `services/venta_service.py`, `services/inventario_service.py`
  - capa UI probable: `ui/views/cashier_view.py`, `ui/views/analytics_view.py`, `ui/dialogs/settings_dialogs.py`
  - coordinacion existente a adelgazar: `ui/main_window.py`
  - servicios candidatos nuevos:
    - `services/sale_employee_assignment_service.py`
    - `services/employee_commission_service.py`
    - `services/employee_analytics_service.py`
    - `services/employee_alert_service.py` solo en fase tardia
- Riesgos a cuidar:
  - mezclar operador de caja con vendedor acreditado sin definir el modelo
  - recalcular comisiones desde datos manuales en lugar de ventas confirmadas
  - olvidar cancelaciones, apartados convertidos o flujos especiales de venta
  - meter agregaciones pesadas directamente en `main_window.py`
  - crear una tabla derivada que luego diverja de la venta real
- Documentacion recomendada:
  - `docs/empleados_y_comisiones.md`
  - `docs/subflujo_caja_venta_empleado.md`
  - `docs/subflujo_analitica_empleado.md`
  - `docs/politica_comisiones.md`
- Checkpoints esperados:
  - checkpoint 1: modelo de atribucion cerrado y documentado
  - checkpoint 2: venta confirmada guarda vendedor de forma coherente y sin romper inventario
  - checkpoint 3: comision calculada desde transacciones reales con pruebas de cancelacion
  - checkpoint 4: analitica por empleado visible y validada manualmente
  - checkpoint 5: alertas solo sobre datos historicos ya confiables
- Criterio de cierre esperado:
  - cada venta queda atribuida a un vendedor real desde el flujo del POS
  - las comisiones salen de ventas confirmadas, no de declaraciones manuales
  - inventario y comisiones permanecen sincronizados
  - la analitica por empleado reutiliza ventas y detalles existentes como fuente de verdad
