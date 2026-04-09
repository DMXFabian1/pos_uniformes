# Hoja de Ruta de Mejoras

## Objetivo

Registrar mejoras propuestas por operacion o producto y ubicarlas dentro del plan tecnico sin asumir que deban implementarse de inmediato.

## Regla de lectura

- Esta hoja no reemplaza `docs/plan_estabilizacion.md`.
- Una mejora puede quedar agendada para una fase futura aunque no sea la siguiente tarea.
- La fase sugerida indica el mejor momento tecnico para implementarla con bajo riesgo.

## Solicitudes abiertas

### 2026-04-07

#### 9. Checkpoint operativo Windows y regla deportivo 3pz

- Idea:
  Cerrar una ronda amplia de pruebas reales en Windows antes de entrar al bloque de kiosko y satelite desacoplada.
- Estado:
  - `2026-04-07`: checkpoint operativo validado en Windows para login, branding visible, QR individual, impresion de etiqueta, carga/salida segura, tablas de Caja/Apartados/Presupuestos, regla `2pz -> 3pz` en Caja, Presupuestos y Apartados, hover reusable en filtros/desplegables de Inventario y respiracion del carrito de Presupuestos principal
  - `2026-04-07`: pendiente solo el cierre de empaquetado final de Windows con validacion del `.ico` y de recursos dentro del bundle
  - `2026-04-07`: la siguiente decision grande ya no es funcional sino de producto/operacion: que hacer con los SKUs legacy `3pz` y cuando desacoplar la satelite para kiosko
  - `2026-04-08`: anotacion operativa para kiosko/presupuesto guiado: la ruta actual no debe mostrar `ropa normal` aunque una prenda este catalogada con escuela; antes de abrir el bloque de `piezas generales`, conviene endurecer el filtro base de `Uniformes por escuela` para aceptar solo lineas escolares reales (`Deportivo` / `Oficial`) y dejar la ropa normal fuera de ese flujo

### 2026-03-26

#### 4. Selector visible de usuarios en login

- Idea:
  En el login, mostrar una lista de usuarios para elegir en lugar de depender solo de captura manual del nombre o usuario.
- Estado:
  resuelto el `2026-03-27`

#### 5. Mejora futura de conteo fisico

- Idea:
  Revisar y mejorar la experiencia de `Conteo fisico` en `Inventario`.
- Estado:
  `2026-03-27`: `V1` construida con flujo rapido por `SKU`, lote y confirmacion final; queda pendiente validacion manual de UI y, despues, una segunda iteracion para `conteo por lote filtrado`

### 2026-03-27

#### 6. Quitar login en la app satelite de presupuestos

- Idea:
  La app satelite debe abrir directo al flujo operativo sin pedir login.
- Estado:
  resuelto el `2026-03-27`

#### 7. Pulido de WhatsApp en presupuestos

- Idea:
  Refinar el flujo y el copy de `WhatsApp` en presupuestos. El ajuste se hara primero en el POS principal y despues se portara al satelite.
- Estado:
  resuelto en POS principal y satelite el `2026-03-27`

#### 8. Pulido de pantalla WhatsApp y mensajes

- Idea:
  Mejorar la experiencia de edicion de plantillas en `Configuracion > WhatsApp y mensajes` para que sea mas clara y comoda de usar.
- Estado:
  resuelto el `2026-03-27` con tarjetas por plantilla, placeholders visibles, chips de insercion rapida y vista previa que se actualiza al escribir

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
  - `2026-03-25`: sugerencias pausadas temporalmente en `Catalogo` e `Inventario` para preservar estabilidad operativa mientras se rediseña un motor reusable, desacoplado del refresh pesado de tablas y con limites claros de costo por tecla
- Alcance recomendado v2:
  - ordenar sugerencias por frecuencia de uso, ventas recientes o coincidencia historica
  - evaluar esta capa despues, idealmente en `Fase 5`, cuando ya tengamos el flujo estable y medible
  - reintroducirla solo cuando exista un flujo reusable con debounce, minimo de caracteres, limite duro de resultados y costo acotado sobre catalogos grandes
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
  - `docs/subflujo_caja_origen_venta.md`
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

### 2026-04-06

#### 9. Empaquetado Windows, QR y branding de build

- Idea:
  Blindar la build de pruebas para Windows, asegurar assets QR y hacer visible que build/version se esta probando.
- Estado:
  - `2026-04-06`: `validated-tests` para inclusion de `migrations` y `assets/qr_icons` en specs de PyInstaller con helper dedicado
  - `2026-04-06`: `validated-tests` para flujo QR mas tolerante a fallos de asset; si falta el icono central el PNG se genera sin cerrar la app
  - `2026-04-06`: `validated-tests` para branding visible en login con logo, nombre y version de la build
  - `2026-04-06`: `pending-manual` en Windows para bundle real, presencia de `_internal/pos_uniformes/migrations`, `_internal/pos_uniformes/assets/qr_icons` y validacion del icono final del ejecutable

#### 10. Arranque con carga visible y cierre seguro

- Idea:
  Hacer mas claro el arranque y las operaciones pesadas para que la app no parezca congelada ni cierre de forma brusca.
- Estado:
  - `2026-04-06`: `validated-tests` para login persistente mientras carga la principal, mensaje `Cargando aplicacion...`, cursor de espera y limpieza correcta del cursor al terminar
  - `2026-04-06`: `validated-tests` para estados de carga reutilizables en operaciones pesadas y bloqueo de cierre durante proceso activo
  - `2026-04-06`: `pending-manual` para confirmar sensacion operativa en Mac y Windows durante recargas, QR y salida segura

#### 11. Coherencia visual en tablas, Caja, Catalogo e Inventario

- Idea:
  Mantener el naranja como identidad, pero quitarlo de la lectura pesada de tablas y superficies donde parecia seleccion permanente.
- Estado:
  - `2026-04-06`: `validated-tests` para nueva paleta compartida en tablas, cards, tabs, KPIs y banners operativos
  - `2026-04-06`: `validated-tests` para reorden de columnas en Caja, Apartados y Presupuestos: `Cantidad` al inicio y `SKU` removido en los flujos acordados
  - `2026-04-06`: `validated-tests` para semantica de tonos mas limpia en Catalogo, Inventario y Analitica; `positive` deja de verse naranja y `reserved` pasa a azul suave
  - `2026-04-06`: `pending-manual` para revisar en Windows contraste, tablas y dialogs operativos con la nueva paleta

#### 12. Flexibilizacion temporal por stock insuficiente

- Idea:
  Quitar temporalmente el bloqueo operativo por stock insuficiente sin borrar la posibilidad de endurecerlo despues.
- Estado:
  - `2026-04-06`: `validated-tests` con politica centralizada en `services/sale_stock_policy.py`; Caja ya no bloquea venta o escaneo por falta de stock
  - `2026-04-06`: riesgo operativo asumido de stock negativo temporal; queda `pending-manual` validar flujo real de venta con bajo stock

#### 13. Maqueta deportivo 2pz -> 3pz

- Idea:
  Probar una composicion guiada `pants 2pz + playera` sin cerrarla aun como regla definitiva.
- Estado:
  - `2026-04-06`: `validated-tests` para pregunta en Caja, validacion de misma escuela, seleccion/escaneo de playera y trazabilidad interna de maqueta
  - `2026-04-06`: `validated-tests` para sugerencia de tallas `Exacta / Sugerida / Atipica` como guia reusable
  - `2026-04-06`: decision tomada de tratarlo como `maqueta operativa`, no como regla final ni SKU unico de `3pz`
  - `2026-04-06`: `pending-manual` en Windows y operacion real antes de expandirlo a otros flujos
  - `2026-04-07`: expandido a `Presupuestos` y `Apartados`, con precio especial de playera, restauracion al quitar el `2pz` y texto visible `Conjunto deportivo 3pz - Escuela`
  - `2026-04-07`: pendiente decision sobre SKUs legacy `3pz` ya catalogados; recomendacion tecnica actual: no borrarlos aun, marcarlos como legado/compatibilidad y planear una migracion operativa hacia el flujo guiado `2pz + playera` si la validacion real confirma que la nueva regla cubre todos los casos

#### 15. Respiro visual de la tabla en Presupuestos

- Idea:
  Hacer que la tabla operativa de `Presupuestos`, especialmente al escanear/agregar productos, respire igual que `Caja` y no se sienta recortada o apretada.
- Estado:
  - `2026-04-07`: detectado en revision manual de Windows; pendiente ajuste visual fino
- Alcance sugerido:
  - revisar anchos de columnas
  - revisar altura de filas
  - revisar margenes/padding alrededor del bloque de tabla
  - empatar sensacion visual con `Caja` sin tocar la logica ya estable
- Prioridad:
  media-alta

#### 14. Comprobante de apartado y cierre de caja

- Idea:
  Simplificar el comprobante del cliente y alinear cierre/historial de caja con apartados cancelados.
- Estado:
  - `2026-04-06`: `validated-tests` para comprobante de apartado mas limpio, sin campos internos irrelevantes al cliente
  - `2026-04-06`: `validated-tests` para excluir apartados cancelados del esperado en cierre de caja
  - `2026-04-06`: `validated-tests` para historial de cierres recalculado con montos consistentes
  - `2026-04-06`: `pending-manual` para revisar ticket final del cliente e historial de cierres en datos reales

#### 9. Estabilizacion de build Windows, assets QR y branding de la build de pruebas

- Idea:
  Consolidar la build de pruebas para Windows con todos los recursos que el ejecutable realmente necesita en tiempo de ejecucion, corrigiendo faltantes del bundle, crash posterior a `Generar QR` y visibilidad clara de version/logo en la app.
- Dominios:
  `deploy`, `build`, `qr`, `assets`, `startup`
- Prioridad:
  alta
- Fase sugerida:
  `Fase 5. Optimizacion fina`
- Momento recomendado dentro de la fase:
  primero, antes de tocar UX pesada de Caja o reglas nuevas de venta, porque una build inestable invalida la validacion de todo lo demas
- Linea base funcional a tomar:
  - checkpoint local actual: `57c2092` `Limpiar base Mac y retirar sync simple`
  - cambios utiles ya incorporados desde la rama previa:
    - etiquetas Windows
    - tickets 58 mm
    - bundle Windows con driver Brother
    - ajuste de setup real del bundle
  - no usar como baseline:
    - `Solo Referencia`
    - `dist/`, `build/`, `generated/`, `exports/`, `__pycache__/`, `.DS_Store`
    - el experimento de `sync simple`, ya retirado de la base local
- Alcance propuesto:
  - incluir `_internal/pos_uniformes/migrations` en el bundle
  - incluir `_internal/pos_uniformes/assets/qr_icons` en el bundle
  - revisar el crash observado al terminar `Generar QR`, aunque el PNG si se escriba
  - restaurar la imagen central de los QR
  - agregar logo e icono del programa
  - mostrar nombre y version de forma visible en login o pantalla inicial
- Donde implementarla:
  - `packaging/windows/pos_uniformes_windows.spec`
  - `scripts/build_windows_bundle.ps1`
  - `utils/qr_generator.py`
  - `ui/main_window.py`
  - `ui/login_dialog.py`
  - `assets/`
- Riesgos a cuidar:
  - mezclar errores de empaquetado con errores de flujo Qt y no aislar la causa real del crash
  - volver a depender de assets que solo existen en entornos manuales pero no en la build
  - meter branding o deteccion de version directo en muchos widgets en vez de una fuente unica
- Orden de ejecucion recomendado:
  - 1. corregir bundle y carga de assets
  - 2. reproducir y aislar crash de `Generar QR`
  - 3. cerrar branding visible de build
- Criterio de cierre esperado:
  - la build de Windows arranca con recursos completos
  - `Generar QR` no cierra la app
  - el QR vuelve a mostrar imagen central
  - operador identifica build y version sin abrir archivos externos

#### 10. Estados de carga, salida segura y legibilidad del login

- Idea:
  Mejorar la percepcion de estabilidad de la app mostrando estados de carga, evitando cierres bruscos y corrigiendo problemas de legibilidad del selector de usuarios.
- Dominios:
  `startup`, `login`, `ux`, `shell`
- Prioridad:
  alta
- Fase sugerida:
  `Fase 5. Optimizacion fina`
- Momento recomendado dentro de la fase:
  despues de estabilizar la build y antes de un pulido visual mas amplio, porque estos cambios afectan toda la experiencia de entrada y salida
- Alcance propuesto:
  - estado visible de carga en acciones pesadas
  - cursor de espera mientras hay procesos en progreso
  - salida segura al cerrar la app
  - corregir contraste del selector de usuarios
  - evaluar mantener login visible mientras termina de cargar la app principal
- Donde implementarla:
  - `ui/login_dialog.py`
  - `ui/main_window.py`
  - helpers de carga o feedback reutilizable en `ui/helpers/`
- Riesgos a cuidar:
  - duplicar indicadores de carga sin una politica unica
  - dejar la app bloqueada con cursor de espera si ocurre una excepcion
  - mezclar el problema visual del selector con logica de autenticacion
- Dependencias:
  - conviene cerrar primero la estabilidad de startup y empaquetado de la mejora 9
- Criterio de cierre esperado:
  - el operador siempre sabe cuando la app esta procesando
  - cerrar la ventana no provoca terminacion abrupta ni estados intermedios raros
  - el login se lee correctamente desde el primer vistazo

#### 11. Rebalanceo visual de tablas y homologacion operativa entre Caja, Apartados y Presupuestos

- Idea:
  Reducir la saturacion naranja de la UI, mejorar legibilidad de tablas y homologar el orden de columnas entre los flujos comerciales para que la operacion se sienta consistente.
- Dominios:
  `caja`, `apartados`, `presupuestos`, `ui`, `styles`
- Prioridad:
  media-alta
- Fase sugerida:
  `Fase 5. Optimizacion fina`
- Momento recomendado dentro de la fase:
  despues de cerrar carga/login, porque aqui ya cambiaremos estructura visual y jerarquia de informacion en varias tablas
- Alcance propuesto:
  - quitar tono naranja base de tablas en `Catalogo` e `Inventario`
  - dejar colores para estados reales como alertas o poco stock
  - ampliar paleta visual de `Caja`
  - en `Caja`, quitar `SKU`, mover `Cantidad` al inicio y mejorar contraste/tipografia
  - aplicar renglones alternados
  - replicar la misma estructura de columnas en `Apartados` y `Presupuestos`
- Donde implementarla:
  - `ui/views/cashier_view.py`
  - `ui/views/layaway_view.py`
  - `ui/views/quotes_view.py`
  - `ui/views/products_view.py`
  - `ui/views/inventory_view.py`
  - `ui/styles/`
  - helpers de filas/tabla en `ui/helpers/`
- Riesgos a cuidar:
  - cambiar solo los headers y dejar desfasados accesos por indice o formateo de filas
  - romper pruebas o acciones que aun dependan de la columna `SKU` visible
  - tocar estilos globales y afectar dialogs o widgets no relacionados
- Estrategia recomendada:
  - separar en dos cortes:
    - paleta y tablas generales
    - homologacion de columnas de `Caja`, `Apartados` y `Presupuestos`
- Criterio de cierre esperado:
  - tablas con lectura mas limpia
  - columnas consistentes entre flujos de venta diferida y presupuesto
  - el color vuelve a significar estado, no fondo permanente

#### 12. Flexibilizacion temporal del bloqueo por stock insuficiente

- Idea:
  Desactivar temporalmente el bloqueo operativo que impide vender o escanear por stock insuficiente, sin borrar para siempre la politica ni dejarla imposible de restaurar despues.
- Dominios:
  `caja`, `inventario`, `venta`
- Prioridad:
  alta
- Fase sugerida:
  `Fase 5. Optimizacion fina`
- Momento recomendado dentro de la fase:
  despues de estabilizar UI principal de Caja, porque es una regla operativa que conviene aislar con claridad
- Alcance propuesto:
  - localizar el punto exacto donde hoy se bloquea el escaneo o agregado al carrito
  - sustituir el bloqueo por una politica temporal controlada
  - si aplica, dejar aviso visual suave en lugar de error bloqueante
- Donde implementarla:
  - servicios de venta y validacion de inventario
  - coordinacion de Caja en `ui/main_window.py` o helpers ya extraidos
- Riesgos a cuidar:
  - quitar el bloqueo en un punto y dejar otro bloqueo oculto en otra ruta
  - confundir stock comprometido vs stock fisico vs stock visible
  - perder trazabilidad de la decision temporal
- Decision de implementacion recomendada:
  - no borrar la regla; encapsularla para poder restaurarla despues con un solo cambio
- Criterio de cierre esperado:
  - la operacion ya no se interrumpe por el bloqueo actual
  - la app sigue registrando la venta de forma consistente
  - queda claro en codigo que es una excepcion temporal

#### 13. Regla comercial para uniforme deportivo de 2 a 3 piezas

- Idea:
  Cuando se escanee un uniforme deportivo de 2 piezas, abrir un subflujo que pregunte si tambien lleva playera y, en caso afirmativo, convierta la operacion a `pants 3 piezas` validando escuela y permitiendo talla distinta.
- Dominios:
  `caja`, `catalogo`, `venta`, `reglas_comerciales`
- Prioridad:
  alta
- Fase sugerida:
  `Fase 5. Optimizacion fina`
- Momento recomendado dentro de la fase:
  despues de cerrar el ajuste temporal de stock, porque es una regla operativa nueva dentro del flujo de venta y conviene montarla sobre una Caja ya despejada
- Alcance propuesto:
  - detectar el caso de uniforme deportivo de 2 piezas
  - preguntar si tambien lleva playera
  - solicitar escaneo o seleccion de la playera
  - permitir talla distinta
  - impedir escuela distinta
  - convertir la operacion al producto o combinacion correcta de `3 piezas`
- Donde implementarla:
  - servicios de seleccion/composicion de venta
  - catalogo o reglas de equivalencia de productos
  - UI de Caja para el prompt
- Riesgos a cuidar:
  - incrustar demasiada regla de negocio nueva en `ui/main_window.py`
  - resolver mal la equivalencia entre SKU compuesto y piezas separadas
  - permitir una playera incompatible y solo detectarlo despues de cobrar
- Estrategia recomendada:
  - primero documentar el subflujo y el modelo de compatibilidad
  - luego cerrar una implementacion minima con validacion de escuela
- Criterio de cierre esperado:
  - el operador puede completar el caso comercial sin atajos manuales
  - la composicion final de la venta queda consistente
  - la validacion de escuela bloquea combinaciones invalidas

#### 14. Simplificacion del comprobante de apartado y correccion del cierre de caja

- Idea:
  Limpiar el comprobante que ve el cliente y corregir la logica para que apartados cancelados no inflen los montos esperados del cierre de caja, incluyendo el historial de cierres.
- Dominios:
  `apartados`, `ticket`, `cierres`, `historial`, `caja`
- Prioridad:
  alta
- Fase sugerida:
  `Fase 5. Optimizacion fina`
- Momento recomendado dentro de la fase:
  al final de esta ronda, porque toca ticket del cliente, logica de cancelacion y cierre contable; conviene entrar con build, UI y Caja ya estabilizadas
- Alcance propuesto:
  - simplificar ticket de apartado para cliente final
  - retirar campos internos o de pruebas que no aportan valor
  - reforzar jerarquia visual de total, abonado y saldo pendiente
  - ajustar cierre de caja para que apartados cancelados no cuenten como venta esperada
  - corregir historial de cierres
- Donde implementarla:
  - servicios de texto de apartado y ticket
  - servicios de cierre de caja e historial
  - dialogs o vistas de cierre
- Riesgos a cuidar:
  - tocar ticket y cierre en la misma pasada sin tests focalizados
  - corregir el monto esperado actual pero romper cierres historicos o lectura retrocompatibles
  - quitar del ticket datos que aun se usen como referencia operativa interna
- Estrategia recomendada:
  - separar en dos cortes:
    - ticket del cliente
    - logica e historial de cierres
- Criterio de cierre esperado:
  - comprobante de apartado entendible para el cliente
  - cancelaciones no inflan el cierre esperado
  - historial de cierres vuelve a ser usable y coherente

## Orden recomendado de esta ronda

- 1. `Estabilizacion de build Windows, assets QR y branding de la build de pruebas`
- 2. `Estados de carga, salida segura y legibilidad del login`
- 3. `Rebalanceo visual de tablas y homologacion operativa entre Caja, Apartados y Presupuestos`
- 4. `Flexibilizacion temporal del bloqueo por stock insuficiente`
- 5. `Regla comercial para uniforme deportivo de 2 a 3 piezas`
- 6. `Simplificacion del comprobante de apartado y correccion del cierre de caja`

## Nota de baseline para esta ronda

- La referencia funcional actual de trabajo es la base local posterior a `57c2092`.
- La base incluye los cambios utiles de etiquetas Windows, tickets 58 mm y bundle Windows.
- La referencia no incluye el experimento de `sync simple`, ya retirado.
- No tomar `Solo Referencia`, `dist/`, `build/`, `generated/`, `exports/`, `__pycache__/` o `.DS_Store` como parte del producto vigente.

## Recordatorio de seguimiento inmediato

- Manana retomar `Conteo fisico`.
- Probar especificamente la apertura `desde el filtro actual de Inventario`.
- Validar si ese flujo realmente se siente natural para operacion antes de implementarlo.
- Manana validar tambien `Empleadas / Staff`:
  - regenerar QR con icono central
  - escanearlo en `Caja`
  - confirmar que `EMP:{codigo}` siga resolviendo normal al `Responsable`
- Si esa validacion sale bien, el siguiente corte natural en ese frente es:
  - reflejar `Responsable` tambien en ticket, `Presupuestos` y `Apartados`
