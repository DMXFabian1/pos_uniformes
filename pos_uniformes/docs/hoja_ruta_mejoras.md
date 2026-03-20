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
  Soportar empleadas vendedoras con comisiones y analitica sin permitir reportes manuales de productos vendidos. Toda comision y toda estadistica debe salir del flujo real de venta confirmado dentro del POS. El modelo futuro debe nacer pensando tambien en kiosko y app movil, no solo en la caja principal.
- Dominios:
  `caja`, `venta`, `configuracion`, `analitica`, `kiosko`, `movil`
- Prioridad:
  alta
- Principios no negociables:
  - la fuente de verdad es la venta registrada en el POS
  - la salida de inventario debe seguir naciendo solo de `VentaService` e `InventarioService`
  - no debe existir captura manual de "vendi X piezas" para comisiones
  - cancelaciones y devoluciones futuras deben poder corregir atribucion y metricas
  - el modulo debe contemplar desde el diseno la reutilizacion de identidad en POS, kiosko y app movil
- Observacion de arquitectura actual:
  - `Venta` ya guarda `usuario_id`, lo que cubre al usuario operador actual
  - antes de introducir `employee_id`, hay que definir si `usuario que opera caja` y `empleado vendedor` son siempre la misma persona
  - si pueden ser personas distintas, conviene separar ambos conceptos para no contaminar auditoria, permisos y comisiones
- Decision de modelo a cerrar primero:
  - opcion A: reutilizar `usuario_id` como vendedor si el operador de caja y el vendedor siempre coinciden
  - opcion B: mantener `usuario_id` como operador del POS e introducir `employee_id` o `seller_employee_id` en la venta cuando el vendedor acreditado puede ser distinto
  - recomendacion actual: tratar esta decision como un checkpoint de diseno antes de abrir migraciones o UI
  - decision vigente: modelar `empleada` como identidad comercial transversal y dejar `usuario` como operador tecnico del sistema
- Fases seguras de implementacion:
  - `Despues de Fase 5`
    - documentar el contrato final `usuario` vs `empleada`
    - crear la ficha base de `empleada`
    - introducir QR + PIN
    - agregar atribucion comercial a ventas reales
  - `Iteracion 2`
    - integrar kiosko con identidad rapida por QR
    - permitir tomar atenciones o ventas atribuidas desde kiosko
  - `Iteracion 3`
    - abrir analitica por empleada sobre ventas reales ya atribuidas
    - exportacion y comparativos por operadora POS vs vendedora acreditada
  - `Iteracion 4`
    - abrir comisiones y liquidacion
    - integrar app movil para metas, seguimiento y consulta de desempeno
- Orden de extraccion conservador:
  - 1. documentar el modelo en `docs/empleadas_y_comisiones.md`
  - 2. cerrar contrato `usuario` vs `empleada`
  - 3. crear identidad base de empleada con QR + PIN
  - 4. persistir el identificador comercial en la venta real
  - 5. integrar kiosko como consumidor de esa identidad
  - 6. abrir analitica por empleada
  - 7. abrir comisiones y liquidacion
  - 8. integrar app movil sobre la misma identidad
- Impacto por capa:
  - base de datos
    - tabla `employees` o `empleadas` como identidad comercial
    - extension de `venta` para guardar vendedor acreditado
    - posible relacion o snapshot derivado para comisiones
    - `employee_sales_stats` solo como tabla derivada opcional, nunca como fuente primaria
  - interfaz POS
    - seleccion del empleado al iniciar una venta o abrir ticket
    - visibilidad clara del vendedor activo dentro de Caja
    - administracion de empleados desde configuracion si el modelo lo requiere
    - nuevas vistas o filtros en analitica por empleado
  - kiosko
    - identificacion rapida con QR
    - confirmacion por PIN si aplica
    - toma de atencion o atribucion comercial
  - app movil
    - consulta de ventas, metas y comisiones
    - seguimiento operativo y comercial
  - logica de negocio
    - servicio de atribucion de vendedor por venta
    - servicio de comisiones derivadas desde ventas reales
    - servicio de analitica por empleado
    - servicio futuro de deteccion de patrones sospechosos
- Alcance recomendado por entregas:
  - v1
    - ficha de empleada
    - QR + PIN
    - atribucion confiable de vendedora en la venta
    - trazabilidad de venta y cancelacion
  - v2
    - integracion base con kiosko
    - consulta basica de ventas e ingresos por empleada
  - v3
    - ticket promedio, frecuencia de ventas y desempeno por categoria
    - filtros/exportacion por empleada en analitica
  - v4
    - comisiones calculadas sobre ventas confirmadas y reversadas
    - app movil con lectura operativa y comercial
  - v5
    - patrones sospechosos y alertas operativas
- Donde implementarla:
  - base actual a revisar: `database/models.py`, `services/venta_service.py`, `services/inventario_service.py`
  - capa UI probable: `ui/views/cashier_view.py`, `ui/views/analytics_view.py`, `ui/dialogs/settings_dialogs.py`
  - integracion futura adicional: `ui/quote_satellite_window.py`, kiosko y cliente movil
  - coordinacion existente a adelgazar: `ui/main_window.py`
  - servicios candidatos nuevos:
    - `services/sale_employee_assignment_service.py`
    - `services/employee_commission_service.py`
    - `services/employee_analytics_service.py`
    - `services/employee_identity_service.py`
    - `services/employee_auth_service.py`
    - `services/employee_alert_service.py` solo en fase tardia
- Riesgos a cuidar:
  - mezclar operador de caja con vendedor acreditado sin definir el modelo
  - recalcular comisiones desde datos manuales en lugar de ventas confirmadas
  - olvidar cancelaciones, apartados convertidos, ventas nacidas en kiosko o cierres desde movil
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
  - kiosko y app movil reutilizan la misma identidad comercial
  - la analitica por empleado reutiliza ventas y detalles existentes como fuente de verdad

### 2026-03-20

#### 3. Respaldos automaticos y recuperacion segura

- Idea:
  Fortalecer la proteccion de la base de datos con una estrategia de respaldo automatico y recuperacion segura, sin depender solo del respaldo manual desde la app.
- Dominios:
  `configuracion`, `operacion`, `deploy`
- Prioridad:
  alta
- Aclaracion tecnica:
  - respaldo automatico y proteccion ante apagones no son la misma cosa
  - el `.dump` ayuda a recuperar
  - la resistencia a cortes depende tambien de PostgreSQL, disco y, de preferencia, UPS
- Fase sugerida:
  `Fase 5. Optimizacion fina`
- Alcance recomendado:
  - mantener respaldo manual en la app
  - programar respaldos automaticos con tarea externa del sistema
  - estandarizar `.dump` como formato principal restaurable
  - agregar copia externa de respaldos
  - documentar recuperacion
- Implementacion recomendada:
  - Windows: `Task Scheduler`
  - macOS: `launchd`
  - script base existente: `scripts/backup_database.py`
- Documentacion base:
  - `docs/estrategia_respaldos_automaticos.md`
- Riesgos a cuidar:
  - confiar solo en respaldos manuales
  - dejar todos los respaldos en la misma maquina
  - meter el scheduler dentro de la UI principal
  - asumir que `.dump` evita corrupcion por apagones
- Criterio de cierre esperado:
  - existe politica oficial de frecuencia y retencion
  - existe ruta automatica local
  - existe copia externa
  - existe guia clara de restauracion
