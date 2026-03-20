# Historial de Refactors y Checkpoints

## Checkpoint actual

- `2026-03-20`: `Fase 4` queda cerrada con checkpoint `validated-manual`.
- Precheck tecnico validado.
- Bateria operativa validada.
- Validacion manual confirmada para Caja, sesion operativa, Apartados, Catalogo, Inventario y Configuracion.
- El siguiente frente ya no es extraccion estructural, sino `Fase 5. Optimizacion fina`.
- Precheck de arranque activo.
- Suite de pruebas activa.
- Base compartida de Presupuestos preparada para una app satelite: soporte de `BORRADOR`, emision posterior y servicios reutilizables para texto, WhatsApp e impresion sin cambiar la UI principal.
- Existe entrada separada `presupuestos_satelite_main.py`, ventana dedicada `ui/quote_satellite_window.py` y spec de Windows independiente para distribuir el satelite sin mezclarlo con el POS principal.
- La ventana satelite ahora abre priorizando un kiosko de escaneo rapido: consulta SKU, muestra precio/detalles y desde ahi agrega lineas al presupuesto.
- La UI satelite se reorganizo como navegacion lateral con paginas `Kiosko`, `Presupuesto`, `Buscar` y `Compartir`, para evitar mezclar funciones en una sola pantalla.
- La UI satelite suma una pagina `Catalogo` para cotizar por escuela: filtra uniformes por escuela, permite incluir extras generales y agrega variantes directo al presupuesto.
- `Catalogo` del satelite ahora soporta filtro por `nivel educativo`, y `Presupuesto` conserva una sola cotizacion multi-escuela con salto por escuela sin perder lineas ya capturadas.
- Checkpoint `validated-tests` para servicios de Presupuestos orientados a la app satelite; validacion manual de esa UI queda `pending-manual`.
- Base actual validada con `check_startup_health.py`.
- Base de datos catalogada como checkpoint bueno despues del delta legacy del `2026-03-19`, con respaldo en `backups/database/pos_uniformes_20260319_173442.dump`.
- Delta legacy aplicado desde `Gestor_de_Inventarios/data/productos.db`: `656` variantes nuevas, `74` familias nuevas y `0` SKUs `SKU%` pendientes; se omitieron `2` filas de prueba sin prefijo `SKU`.
- Checklist especifica de cierre para `Fase 4` y validacion manual pendiente de `Fase 1` creada en `docs/checklist_cierre_fase_4.md`.
- Busqueda textual endurecida para tolerar alias con comillas mal cerradas sin dejar al operador con resultados vacios silenciosos.
- Busqueda textual endurecida para tolerar comparaciones sin acento contra catalogo real con nombres y variantes acentuadas.
- Ticket de venta documentado y con correccion tolerante para descuentos faltantes en ventas antiguas.
- Validacion manual confirmada para `Ventas recientes -> Ver ticket`.
- Ventas recientes delega el listado visible a `services/recent_sale_service.py` y reutiliza una sola lectura de venta seleccionada para ticket y cancelacion.
- Caja delega el armado visible del carrito y del bloque total a `ui/helpers/sale_cashier_view_helper.py`.
- Caja delega el contexto operativo de cliente, descuento y promo manual a `services/sale_discount_context_service.py`, dejando a `MainWindow` sin mezclar presets, sync con cliente, autorizacion y desglose efectivo.
- Caja delega el panel visible completo del carrito a `ui/helpers/sale_cashier_panel_helper.py`, dejando a `MainWindow` solo aplicar filas, resumen, tooltip y botones.
- Caja delega la confirmacion operativa de venta a `services/sale_checkout_action_service.py` y los mensajes de cierre a `ui/helpers/sale_checkout_feedback_helper.py`, dejando a `MainWindow` sin construir la venta confirmada inline.
- Caja delega la construccion de ticket/comprobante y sus fallbacks de configuracion a `services/sale_document_view_service.py`, dejando a `MainWindow` sin armar textos imprimibles inline para ventas y apartados.
- Caja delega el feedback visible posterior a venta/cancelacion a `ui/helpers/sale_post_action_feedback_helper.py`, dejando a `MainWindow` sin decidir mensajes, tono y aviso de lealtad inline.
- Caja delega la orquestacion de apertura de texto imprimible a `ui/helpers/printable_document_flow_helper.py`, dejando a `MainWindow` sin repetir la secuencia de sesion + documento + dialogo.
- Cobro delega la seleccion del dialogo y la carga del snapshot de transferencia a `services/sale_payment_collection_service.py`, dejando a `sale_payment_helper` sin resolver configuracion inline.
- Cobro delega las notas operativas del pago a `services/sale_payment_context_service.py` y el tooltip visible del metodo a `ui/helpers/sale_payment_summary_helper.py`, dejando a `MainWindow` y al panel de caja sin copy hardcodeado por metodo.
- Cobro delega validaciones de efectivo, transferencia y mixto a `services/sale_payment_validation_service.py`, dejando a `payment_dialogs.py` sin reglas inline de suficiencia, cambio y configuracion.
- Caja delega apertura, movimientos, correccion de apertura y corte a `services/cash_session_action_service.py`, y los mensajes visibles asociados a `ui/helpers/cash_session_feedback_helper.py`, dejando a `MainWindow` sin cargar entidades ni construir feedback operacional inline.
- Existe una bateria operativa reusable en `scripts/check_operational_flows.py` para revisar Caja/Cobro y Apartados/Tickets con una sola corrida enfocada.
- Cliente escaneado en Caja delega su plan visible de confirmacion y feedback a `ui/helpers/sale_scanned_client_helper.py`.
- Cliente seleccionado en Caja delega el reset de promo manual, el bloqueo de descuento y el tooltip visible a `ui/helpers/sale_client_selection_helper.py`.
- El beneficio del cliente seleccionado se resuelve desde `services/sale_selected_client_service.py` y el flujo de cliente escaneado reutiliza la misma sesion activa.
- Inventario delega el resumen visible del listado y los chips de estado a `ui/helpers/inventory_summary_helper.py`.
- Inventario delega la ficha rapida de la seleccion actual a `ui/helpers/inventory_overview_helper.py`.
- Inventario delega el plan visible de acciones contextuales a `ui/helpers/inventory_context_menu_helper.py`.
- Inventario delega el estado visible del panel QR a `ui/helpers/inventory_qr_preview_helper.py`, dejando a `MainWindow` solo cargar la presentacion y aplicar la vista.
- Inventario delega la carga del snapshot de la ficha rapida a `services/inventory_overview_service.py`, dejando a `MainWindow` sin consultas ni fallbacks manuales para ese panel.
- Inventario delega la resolucion de seleccion y sincronizacion de `variant_id` a `ui/helpers/inventory_selection_helper.py`, dejando a `MainWindow` sin deduplicacion ni busquedas manuales de filas.
- Inventario delega el popup del menu contextual a `ui/dialogs/inventory_context_menu_dialog.py` y la resolucion de la accion elegida a `ui/helpers/inventory_context_menu_helper.py`, dejando a `MainWindow` solo despachando por `action_key`.
- Catalogo delega la resolucion de la fila seleccionada y el armado de la ficha visible desde `catalog_rows` a `ui/helpers/catalog_selection_helper.py`, dejando a `MainWindow` sin mapear diccionarios ni recorrer variantes a mano.
- Catalogo delega las guardas de seleccion/permisos para editar, activar/desactivar y eliminar a `ui/helpers/catalog_action_guard_helper.py`, dejando a `MainWindow` sin repetir el mismo copy operativo en cada handler.
- Catalogo delega confirmaciones, titulos de error y mensajes de exito de acciones criticas a `ui/helpers/catalog_action_feedback_helper.py`, dejando a `MainWindow` sin repetir copy de toggle/delete.
- Catalogo delega el mapeo de resultados crudos y las columnas visibles del listado a `ui/helpers/catalog_refresh_helper.py`, dejando a `MainWindow` sin traducir tuplas SQL a mano para la tabla.
- Catalogo delega las mutaciones de toggle/delete con sesion a `services/catalog_mutation_service.py`, dejando a `MainWindow` sin cargar entidades ni llamar `CatalogService` directamente para esos casos.
- Catalogo delega el filtrado visible del listado a `ui/helpers/catalog_filter_helper.py`, dejando a `MainWindow` sin cadenas largas de condiciones inline para filtros macro y estados.
- Catalogo ahora separa `Uniforme escolar` y `Ropa normal` con un filtro visible por contexto de escuela (`General` vs escuela asignada), y deja deshabilitado el filtro de escuela cuando el operador entra a ropa normal para no mezclar criterios.
- Catalogo ahora ofrece un modo de captura `Uniforme escolar / Ropa normal` dentro del formulario de producto, con hints, labels, categoria y campos de contexto adaptados segun el flujo.
- Catalogo delega el nombre visible, el resumen en vivo y la revision final del formulario de producto a `ui/helpers/catalog_product_form_summary_helper.py`, dejando a `MainWindow` sin construir esos HTML inline.
- Inventario delega el filtrado visible del listado a `ui/helpers/inventory_filter_helper.py`, dejando a `MainWindow` sin ramas repetidas por filtro antes de pintar la tabla.
- Catalogo e Inventario comparten predicados de visibilidad en `ui/helpers/listing_visibility_helper.py`, reduciendo duplicacion en filtros de seleccion multiple, estado, origen e incidencias.
- Catalogo delega la carga del query y el snapshot base del listado a `services/catalog_snapshot_service.py`, dejando a `MainWindow` sin construir el query SQL completo de catalogo.
- Inventario delega la carga del query y el snapshot base del listado a `services/inventory_snapshot_service.py`, dejando a `MainWindow` sin construir el query SQL completo ni revisar QR por fila inline.
- Inventario delega el armado visible de filas y tonos de la tabla a `ui/helpers/inventory_table_row_helper.py`, dejando a `MainWindow` solo aplicando items y estilos.
- Analytics delega la carga del snapshot de top productos a `services/analytics_top_products_service.py` y el armado visible de filas a `ui/helpers/analytics_top_products_helper.py`, dejando a `MainWindow` sin query agregado ni limpieza inline de nombres para ese bloque.
- Analytics delega la carga del snapshot de top clientes a `services/analytics_top_clients_service.py` y el armado visible de filas y badges a `ui/helpers/analytics_top_clients_helper.py`, dejando a `MainWindow` sin query agregado ni criterio visual inline para ese bloque.
- Analytics delega las KPI cards de apartados a `services/analytics_layaway_service.py` y `ui/helpers/analytics_layaway_helper.py`, dejando a `MainWindow` sin consultas ni tonos inline para activos, saldo pendiente, vencidos y entregados.
- Analytics delega la tabla de stock critico a `services/analytics_stock_service.py` y `ui/helpers/analytics_stock_helper.py`, dejando a `MainWindow` sin query agregado ni badges inline para stock, apartado y estado.
- Analytics delega el armado exportable de tablas y resumen de apartados a `ui/helpers/analytics_export_helper.py`, dejando a `MainWindow` sin leer cada celda manualmente para top productos, top clientes, metodos de pago y stock critico.
- Analytics delega la resolucion de periodo, el estado manual y el texto visible de exportacion a `ui/helpers/analytics_period_helper.py`, dejando a `MainWindow` sin ramas repetidas para fechas y cliente actual.
- Apartados delega la carga del snapshot base del listado a `services/layaway_snapshot_service.py` y el armado visible de filas a `ui/helpers/layaway_table_row_helper.py`, dejando a `MainWindow` sin construir snapshots ni badges inline en `_refresh_layaways`.
- Apartados delega la carga del detalle seleccionado a `services/layaway_detail_service.py` y `MainWindow` reutiliza `_apply_layaway_detail_view(...)`, dejando `_refresh_layaway_detail` sin mapear manualmente detalles, abonos y permisos inline.
- Apartados delega las metricas de alertas a `services/layaway_alerts_service.py` y el estado contextual de botones a `ui/helpers/layaway_action_helper.py`, dejando a `MainWindow` sin contadores ni guardas repetidas para acciones del tab.
- Ventas recientes delega el armado visible de la tabla a `ui/helpers/recent_sale_table_helper.py`, dejando a `MainWindow` sin iterar filas inline en `_refresh_sales_table`.
- Ventas recientes delega la resolucion de seleccion y el estado visible de acciones a `ui/helpers/recent_sale_selection_helper.py`, y la cancelacion operativa a `services/recent_sale_action_service.py`, dejando a `MainWindow` sin parsear la fila seleccionada ni cancelar ventas inline.
- Ventas recientes delega permisos y mensajes operativos a `ui/helpers/recent_sale_feedback_helper.py`, dejando a `MainWindow` sin repetir copy de seleccion, permisos y resultado para ticket/cancelacion.
- Apartados delega la creacion operativa desde dialogo a `services/layaway_creation_service.py`, dejando a `MainWindow` sin resolver usuario, cliente ni fecha compromiso inline en los flujos de crear y convertir desde Caja.
- Apartados delega el registro operativo de abonos a `services/layaway_payment_action_service.py`, dejando a `MainWindow` sin cargar usuario/apartado ni llamar `registrar_abono(...)` inline.
- Apartados delega entrega y cancelacion operativa a `services/layaway_closure_service.py`, dejando a `MainWindow` sin cargar usuario/apartado ni crear la venta de entrega inline en esos handlers.
- Presupuestos delega la carga del snapshot base del listado a `services/quote_snapshot_service.py` y el armado visible de filas a `ui/helpers/quote_table_row_helper.py`, dejando a `MainWindow` sin construir snapshots ni pintar la tabla inline en `_refresh_quotes`.
- Presupuestos delega la carga del detalle seleccionado a `services/quote_detail_service.py` y `MainWindow` reutiliza `_apply_quote_detail_view(...)`, dejando `_refresh_quote_detail` sin mapear el presupuesto inline.
- Presupuestos delega la resolucion de seleccion y el estado contextual de acciones a `ui/helpers/quote_selection_helper.py`, y la cancelacion operativa a `services/quote_action_service.py`, dejando a `MainWindow` sin resolver la fila seleccionada ni cancelar inline.
- Presupuestos delega permisos y mensajes operativos a `ui/helpers/quote_feedback_helper.py`, dejando a `MainWindow` sin repetir copy de permisos, seleccion, presupuesto vacio y resultados de guardado/cancelacion.
- Configuracion delega la seleccion, guardas, mensajes y acciones operativas de respaldos a `services/settings_backup_action_service.py`, `ui/helpers/settings_backup_selection_helper.py` y `ui/helpers/settings_backup_feedback_helper.py`, dejando a `MainWindow` sin orquestar inline crear/restaurar/abrir carpeta.
- Configuracion delega la seleccion, snapshots de prompt, guardas, mensajes y mutaciones de usuarios a `services/settings_user_action_service.py`, `ui/helpers/settings_user_selection_helper.py` y `ui/helpers/settings_user_feedback_helper.py`, dejando a `MainWindow` sin cargar entidades ni repetir copy operativo para CRUD basico.
- Configuracion delega el snapshot y guardado operativo de negocio/marketing/WhatsApp a `services/settings_business_action_service.py`, centraliza plantillas reutilizables en `services/settings_whatsapp_template_service.py` y mueve permisos/resultados a `ui/helpers/settings_business_feedback_helper.py`.
- Configuracion delega la seleccion, guardas, mensajes y acciones operativas de proveedores, clientes y marketing a `services/settings_supplier_action_service.py`, `services/settings_client_action_service.py`, `services/settings_marketing_action_service.py` y `ui/helpers/settings_crm_feedback_helper.py`, dejando a `MainWindow` sin cargar entidades ni mapear historial de marketing inline.
- Historial delega el estado puro de filtros, rango y acciones secundarias a `ui/helpers/history_filter_state_helper.py`, dejando a `MainWindow` sin recomponer inline fechas, reseteos ni preservacion del tipo seleccionado.
- Historial delega la carga del snapshot consultado a `services/history_snapshot_service.py`, dejando a `MainWindow` sin construir queries inline para inventario y catalogo.
- Historial ya no depende de enums ORM para poblar opciones del filtro de tipos en `ui/helpers/history_filter_helper.py`, lo que mantiene las pruebas puras fuera de Windows/SQLAlchemy.
- Catalogo e Inventario ya ofrecen sugerencias incrementales de busqueda mediante `services/search_suggestion_service.py` y `ui/helpers/search_input_helper.py`, conectadas desde sus vistas y con `MainWindow` solo empujando snapshots.
- La `V2` de sugerencias prioriza lenguaje natural para el operador medio y deja los prefijos como apoyo; ademas, las flechas del teclado ya solo navegan el popup sin reescribir el input en cada highlight.
- Impresion de etiquetas ya delega el dialogo de preview e impresion a `ui/dialogs/inventory_label_dialog.py`, dejando a `MainWindow` solo cargando la presentacion y enlazando render/print.
- Impresion de etiquetas ya delega la carga del contexto visible y el render de etiqueta a `services/inventory_label_service.py`, dejando a `MainWindow` sin logica real de render.
- Impresion de etiquetas ya delega el resumen visible del preview y el mensaje de confirmacion a `ui/helpers/inventory_label_preview_helper.py`, dejando el dialogo mas testeable.
- Windows ya tiene base de empaquetado preparada: `packaging/windows/pos_uniformes_windows.spec`, scripts de build y soporte de configuracion local con `pos_uniformes.env` junto al ejecutable.
- Dialogos de cobro extraidos a `ui/dialogs/payment_dialogs.py`.
- Modal imprimible de ticket y comprobante extraido a `ui/dialogs/printable_text_dialog.py`.
- Cobro mixto ajustado para captura por teclado fisico con confirmacion por `Enter` y cancelacion por `Esc`.

## Extracciones ya realizadas

### Arranque

- `database/preflight.py`
  - Verificacion de conexion y revision de esquema.
- `scripts/check_startup_health.py`
  - Smoke operativo reutilizable.
- `scripts/check_operational_flows.py`
  - Bateria enfocada de regresion para Caja/Cobro y Apartados/Tickets.

### Caja

- `services/sale_client_benefit_service.py`
  - Beneficio visible del cliente en Caja a partir de descuento preferente y nivel de lealtad.
- `services/sale_selected_client_service.py`
  - Carga del cliente seleccionado en Caja y resolucion compartida de su beneficio visible.
- `services/sale_discount_service.py`
  - Descuentos, desglose y totales.
- `services/sale_discount_context_service.py`
  - Presets, sync con cliente, contexto efectivo de descuento y transicion de promo manual fuera de `MainWindow`.
- `ui/helpers/sale_cart_table_helper.py`
  - Filas visibles del carrito y conteo total de piezas para Caja.
- `ui/helpers/sale_cashier_panel_helper.py`
  - Estado visible completo del panel de Caja: vista, tooltip de cobro y habilitacion de acciones.
- `ui/helpers/sale_cashier_summary_helper.py`
  - Resumen visible del bloque total en Caja sin referencia del cliente.
- `services/manual_promo_flow_service.py`
  - Estado, decision y transicion de promo manual fuera de `MainWindow`.
- `services/sale_note_service.py`
  - Notas operativas de la venta.
- `services/sale_checkout_service.py`
  - Snapshot del cliente en checkout y resolucion del aviso de lealtad post-venta.
- `services/sale_checkout_action_service.py`
  - Confirmacion operativa de la venta, logging de promo manual y aviso postventa fuera de `MainWindow`.
- `services/sale_document_view_service.py`
  - Construccion del documento visible de ticket/comprobante con fallback de configuracion de impresion.
- `services/sale_payment_collection_service.py`
  - Seleccion del dialogo de cobro y snapshot operativo de transferencia fuera del helper UI.
- `services/sale_payment_context_service.py`
  - Contexto operativo del pago y notas finales de venta fuera de `MainWindow`.
- `services/sale_loyalty_notice_service.py`
  - Mensajes de transicion de lealtad.
- `services/cash_session_action_service.py`
  - Apertura, movimientos, correccion de apertura y corte de caja fuera de `MainWindow`.
- `services/scanned_client_flow_service.py`
  - Decisiones y copy de cliente escaneado.
- `services/sale_discount_option_service.py`
  - Construccion de opciones del combo de descuento.
- `services/sale_discount_lock_service.py`
  - Estado y tooltip del bloqueo por cliente.
- `services/sale_client_discount_service.py`
  - Resolucion del descuento efectivo del cliente.
- `ui/helpers/sale_cashier_view_helper.py`
  - View model visible del carrito y del bloque total de Caja a partir de datos ya calculados.
- `ui/helpers/sale_scanned_client_helper.py`
  - Plan visible del cliente escaneado en Caja: confirmacion, feedback de conservacion y feedback de aplicacion.
- `ui/helpers/sale_client_selection_helper.py`
  - Estado UI del cliente seleccionado en Caja: reset de promo manual, bloqueo de descuento y tooltip resultante.
- `ui/helpers/sale_checkout_feedback_helper.py`
  - Normalizacion de errores de checkout y mensaje de exito visible para el cierre de venta.
- `ui/helpers/sale_post_action_feedback_helper.py`
  - Feedback visible posterior a venta/cancelacion y aviso opcional de lealtad.
- `ui/helpers/sale_payment_summary_helper.py`
  - Tooltip visible del metodo de cobro dentro del panel de Caja.
- `ui/helpers/printable_document_flow_helper.py`
  - Orquestacion reutilizable para abrir documentos imprimibles desde una sesion.
- `ui/helpers/cash_session_feedback_helper.py`
  - Mensajes visibles de caja abierta, movimientos, correccion y corte.
- `services/sale_selected_client_service.py`
  - Carga el beneficio del cliente seleccionado y expone el descuento efectivo con fallback a cero para Caja.

### Historial

- `ui/helpers/history_filter_helper.py`
  - Opciones visibles del filtro de tipos sin depender de enums ORM en tiempo de import.
- `ui/helpers/history_filter_state_helper.py`
  - Estado puro de filtros, rango de fechas y acciones secundarias del tab Historial.
- `ui/helpers/history_summary_helper.py`
  - Resumen visible de filtros y conteo del historial fuera de `MainWindow`.
- `ui/helpers/history_table_helper.py`
  - Tabla visible del historial, incluyendo orden y tonos de origen/tipo.
- `services/history_snapshot_service.py`
  - Carga el snapshot consultado de inventario y catalogo para el tab Historial fuera de `MainWindow`.

### Ticket

- `services/business_print_settings_service.py`
  - Snapshot reutilizable de negocio, impresion y pie de ticket para textos operativos.
- `services/recent_sale_service.py`
  - Consulta y shape visible del listado de ventas recientes fuera de `MainWindow`.
- `services/sale_document_service.py`
  - Carga y validaciones de venta/apartado para abrir ticket o comprobante.
- `services/sale_ticket_totals_service.py`
  - Normalizacion y reconstruccion de descuento para render de ticket.
- `services/sale_ticket_text_service.py`
  - Render textual del ticket, forma de pago y ajuste de cobro visible.
- `services/layaway_receipt_text_service.py`
  - Render textual del comprobante de apartado fuera de `MainWindow`.
- `ui/dialogs/printable_text_dialog.py`
  - Modal reutilizable para mostrar e imprimir ticket o comprobante en texto plano.

### Cobro

- `services/business_payment_settings_service.py`
  - Snapshot reutilizable de datos de transferencia para dialogs de cobro.
- `services/sale_payment_collection_service.py`
  - Seleccion del dialogo de cobro y fallback del snapshot operativo por metodo.
- `services/sale_payment_context_service.py`
  - Contexto reutilizable para notas operativas y metodo normalizado de cobro.
- `services/sale_payment_note_service.py`
  - Detalles puros de cobro y notas operativas por metodo de pago.
- `services/sale_payment_validation_service.py`
  - Validaciones puras de suficiencia, cambio y disponibilidad para efectivo, transferencia y mixto.
- `services/layaway_payment_service.py`
  - Estado y normalizacion del abono segun metodo de pago para apartados.
- `services/sale_rounding_service.py`
  - Regla pura de redondeo posterior al descuento.
- `ui/dialogs/payment_dialogs.py`
  - Dialogos de efectivo, transferencia y mixto fuera de `MainWindow`.
- `ui/helpers/sale_payment_summary_helper.py`
  - Tooltip visible del metodo de cobro para el panel de Caja.
- `ui/dialogs/layaway_payment_dialog.py`
  - Dialogo reutilizable para registrar abonos fuera de `MainWindow`.
- `ui/helpers/sale_payment_helper.py`
  - Enrutamiento UI del cobro por metodo sin dejar prompts ni snapshot en `MainWindow`.

### Catalogo e inventario

- `services/search_filter_service.py`
  - Busqueda textual compartida.
  - Degrada con gracia cuando el operador deja una comilla sin cerrar en un prefijo como `producto:"...`.
  - Normaliza acentos para que `corbatin` siga encontrando `Corbatín` en texto general y por alias.
- `services/search_suggestion_service.py`
  - Sugerencias incrementales compartidas para Catalogo e Inventario con soporte para texto libre y prefijos como `sku:` o `producto:`.
- `services/active_filter_service.py`
  - Etiquetas y resumenes de filtros activos.
- `ui/helpers/search_input_helper.py`
  - Completer reutilizable para inputs de busqueda, reemplazando solo el ultimo termino y sin cargar comportamiento nuevo en `MainWindow`.
- `ui/helpers/inventory_summary_helper.py`
  - Resumen visible del listado filtrado y chips de agotados, bajo stock, sin QR e inactivas.
- `ui/helpers/inventory_overview_helper.py`
  - Ficha rapida visible de la seleccion actual: badges, textos secundarios y etiquetas de activar/desactivar.
- `services/inventory_overview_service.py`
  - Carga el snapshot de la ficha rapida de Inventario: presentacion, fallbacks desde `catalog_rows` y ultimo movimiento visible fuera de `MainWindow`.
- `ui/helpers/inventory_selection_helper.py`
  - Resuelve la fila/catalogo seleccionado, normaliza `variant_id`, deduplica seleccion multiple y encuentra la fila visible a sincronizar en Inventario.
- `ui/helpers/inventory_context_menu_helper.py`
  - Etiquetas y disponibilidad visible de las acciones contextuales de inventario segun permisos y estado de la presentacion.
- `ui/dialogs/inventory_context_menu_dialog.py`
  - Popup reutilizable para acciones contextuales de Inventario que devuelve un `action_key` en lugar de dejar el armado del menu inline en `MainWindow`.
- `ui/helpers/inventory_qr_preview_helper.py`
  - Estado visible del panel QR en Inventario: boton, texto secundario, badge y placeholder del preview segun seleccion, QR pendiente o QR disponible.
- `ui/helpers/catalog_summary_helper.py`
  - Resumen visible del listado de catalogo y etiqueta de filtros activos fuera de `MainWindow`.
- `ui/helpers/catalog_selection_helper.py`
  - Ficha breve visible de la presentacion seleccionada en catalogo, con estado vacio y variante segun permisos.
  - Ahora tambien resuelve filas validas, arma la vista directamente desde `catalog_rows` y encuentra la fila correcta por `variant_id`.
- `ui/helpers/catalog_action_guard_helper.py`
  - Copy y validacion ligera para acciones de Catalogo que requieren seleccion y permisos de ADMIN antes de editar, activar/desactivar o eliminar.
- `ui/helpers/catalog_action_feedback_helper.py`
  - Confirmaciones, mensajes de exito y titulos de error para acciones criticas de Catalogo como toggle y delete.
- `ui/helpers/catalog_refresh_helper.py`
  - Mapea filas crudas del query de Catalogo a `catalog_rows` y arma las columnas visibles de la tabla fuera de `MainWindow`.
- `ui/helpers/catalog_filter_helper.py`
  - Filtra el listado visible de Catalogo a partir del snapshot, el texto de busqueda y los filtros activos sin dejar la condicion completa inline en `MainWindow`.
  - Ahora tambien separa `Uniforme escolar` y `Ropa normal` segun el contexto visible de escuela, para que el operador pueda aislar prendas generales sin depender de escuelas especificas.
- `ui/helpers/catalog_product_form_mode_helper.py`
  - Decide y describe el modo visible del formulario de producto (`uniform` o `regular`) para adaptar categoria, hints y campos de contexto sin cargar esa logica en `MainWindow`.
- `ui/helpers/catalog_product_form_summary_helper.py`
  - Construye el nombre visible, los ejemplos de presentaciones, el resumen en vivo y la revision final del formulario de producto fuera de `MainWindow`.
- `ui/helpers/catalog_access_helper.py`
  - Estado visible del tab Catalogo segun rol: mensaje de permiso, acciones habilitadas y visibilidad de caja rapida.
- `services/catalog_snapshot_service.py`
  - Ejecuta el query base de Catalogo y devuelve el snapshot visible listo para sugerencias, filtros y resumenes.
- `ui/helpers/inventory_filter_helper.py`
  - Filtra el listado visible de Inventario a partir del snapshot, el estado QR y los filtros activos fuera de `MainWindow`.
- `ui/helpers/inventory_table_row_helper.py`
  - Arma las filas visibles de la tabla de Inventario: textos de stock, estado QR y tonos de badges fuera de `MainWindow`.
- `ui/helpers/listing_visibility_helper.py`
  - Predicados compartidos para filtros visibles: seleccion multiple, estado activo/inactivo, origen legacy/native e incidencias fallback.
- `services/inventory_snapshot_service.py`
  - Ejecuta el query base de Inventario y devuelve el snapshot visible listo para sugerencias, filtros y tabla.
- `services/catalog_mutation_service.py`
  - Ejecuta toggles y eliminaciones de producto/presentacion cargando entidades y delegando a `CatalogService` fuera de `MainWindow`.
- `ui/helpers/catalog_macro_filter_helper.py`
  - Toggle y estado visual de los chips de macro uniforme en Catalogo fuera de `MainWindow`.
- `ui/dialogs/inventory_label_dialog.py`
  - Dialogo reutilizable para vista previa e impresion de etiquetas de inventario, con callbacks de render e impresion y sin UI inline en `MainWindow`.
- `services/inventory_label_service.py`
  - Carga el contexto visible de la presentacion para cabecera de impresion y delega el render real a `LabelGenerator` fuera de `MainWindow`.
- `ui/helpers/inventory_label_preview_helper.py`
  - Estado visible del preview de etiquetas: error de render, resumen de copias/hojas y mensaje de confirmacion de impresion.
  - Ahora tambien resuelve copy visible por modo y resumen multilinea para una vista previa mas clara.
- `ui/dialogs/inventory_label_dialog.py`
  - Vista de impresion de etiquetas reorganizada: preview protagonista, controles compactos arriba, resumen inferior, acciones mas limpias y navegacion `Anterior/Siguiente` entre presentaciones sin devolver logica a `MainWindow`.
- `utils/qr_generator.py`
  - Los QR de presentaciones ahora incrustan un icono central desde `assets/qr_icons`, eligiendo por `tipo_prenda` o nombre de producto y usando `default.png` como fallback seguro.

### Empaquetado

- `packaging/windows/pos_uniformes_windows.spec`
  - Build `onedir` para Windows con assets, migraciones, soporte de `alembic.ini` y nombre versionado a partir de `VERSION`.
  - Ahora tambien incluye `setup_windows_local_bundle.ps1/.bat` y un `seed/initial.dump` opcional cuando se prepara una base semilla.
- `scripts/build_windows_bundle.ps1`
  - Build reproducible en Windows: instala dependencias de build, corre pruebas, lee `VERSION`, genera `dist/POSUniformes-<VERSION>/` y produce `POSUniformes-<VERSION>-windows.zip`.
  - Puede incluir una base semilla con `-CreateSeedBackup` o `-SeedBackupPath`.
- `scripts/build_windows_bundle.bat`
  - Wrapper simple para disparar el build desde consola de Windows.
- `scripts/setup_windows_local_bundle.ps1`
  - Setup automatico en la PC destino: crea la base si falta, restaura `seed\initial.dump` cuando existe y escribe `pos_uniformes.env` junto al `.exe`.
- `scripts/setup_windows_local_bundle.bat`
  - Wrapper para correr el setup automatico de base local desde Windows.
- `pos_uniformes.env.example`
  - Plantilla de configuracion local para ejecutar la app empaquetada sin depender de variables de entorno del sistema.
- `VERSION`
  - Fuente unica de version para nombrar el ejecutable y el bundle de Windows.
- `utils/config.py`
  - Lee `pos_uniformes.env` o `.env` en la raiz del proyecto o junto al ejecutable empaquetado.

### Presupuestos

- `ui/helpers/quote_cart_view_helper.py`
  - Tabla visible, total y resumen del presupuesto en armado fuera de `MainWindow`.
- `ui/helpers/quote_history_helper.py`
  - Filtrado visible, shape de filas y tono del estado para el listado reciente de Presupuestos.
- `ui/helpers/quote_summary_helper.py`
  - Resumen visible del filtro en Presupuestos a partir del texto buscado y el estado seleccionado.
- `ui/helpers/quote_detail_helper.py`
  - Estado visible del detalle seleccionado en Presupuestos: vacio, error, meta resumen y filas del detalle.

### Apartados

- `ui/helpers/layaway_alerts_helper.py`
  - Alertas visibles de Apartados: badges enriquecidos y resumen rapido de vencidos, hoy y proximos 7 dias.
- `ui/helpers/layaway_history_helper.py`
  - Filtrado visible, shape de filas y tonos del listado reciente de Apartados.
- `ui/helpers/layaway_summary_helper.py`
  - Resumen visible del filtro en Apartados a partir de texto buscado, estado y vencimiento.
- `ui/helpers/layaway_detail_helper.py`
  - Estado visible del detalle seleccionado en Apartados: vacio, error, resumen, badge de vencimiento y tablas del panel.

### Configuracion

- `ui/dialogs/marketing_history_dialog.py`
  - Dialogo del historial de marketing extraido de `MainWindow`.
- `ui/dialogs/settings_prompt_dialogs.py`
  - Prompts inline de usuarios, proveedores, clientes y WhatsApp extraidos de `MainWindow`.
- `ui/helpers/settings_backup_helper.py`
  - Ubicacion, listado visible y estado del modulo de respaldos fuera de `MainWindow`.
- `ui/helpers/settings_backup_selection_helper.py`
  - Resolucion de la seleccion actual del modulo de respaldos fuera de `MainWindow`.
- `ui/helpers/settings_backup_feedback_helper.py`
  - Guardas, confirmacion y mensajes operativos para crear/restaurar respaldos.
- `services/settings_backup_action_service.py`
  - Crear respaldo, abrir carpeta y restaurar respaldo sin dejar la orquestacion inline en `MainWindow`.
- `ui/helpers/settings_business_feedback_helper.py`
  - Permisos y mensajes de resultado para guardado de negocio, marketing y WhatsApp.
- `ui/helpers/settings_cash_history_helper.py`
  - Shape visible del listado principal de historial de caja, incluyendo tonos de estado y diferencia.
- `ui/helpers/settings_cash_history_detail_helper.py`
  - Estado visible del modal de detalle de corte: apertura, correcciones, flujo, movimientos y cierre.
- `ui/helpers/settings_cash_history_movements_helper.py`
  - Tabla visible y estado del panel de movimientos del corte seleccionado en historial de caja.
- `ui/helpers/settings_cash_history_summary_helper.py`
  - Resumen visible del rango y conteo de sesiones abiertas/cerradas en historial de caja.
- `ui/helpers/settings_clients_helper.py`
  - Listado visible y badges del modulo de clientes en Configuracion.
- `ui/helpers/settings_marketing_helper.py`
  - Resumen visible de marketing por nivel de lealtad, sin cargar clientes completos en `MainWindow` y sin depender del enum SQLAlchemy para pruebas puras.
- `ui/helpers/marketing_history_helper.py`
  - Shape visible y estado del historial de marketing fuera de `MainWindow`.
- `ui/helpers/settings_crm_selection_helper.py`
  - Resolucion de seleccion para proveedores y clientes en Configuracion.
- `ui/helpers/settings_crm_feedback_helper.py`
  - Guardas y mensajes operativos compartidos para proveedores, clientes y marketing.
- `ui/helpers/settings_suppliers_helper.py`
  - Listado visible y estado del modulo de proveedores en Configuracion.
- `ui/helpers/settings_users_helper.py`
  - Listado visible y estado del modulo de usuarios en Configuracion.
- `ui/helpers/settings_user_selection_helper.py`
  - Resolucion de la seleccion actual del modulo de usuarios fuera de `MainWindow`.
- `ui/helpers/settings_user_feedback_helper.py`
  - Guardas y mensajes operativos de usuarios en Configuracion.
- `ui/helpers/settings_whatsapp_preview_helper.py`
  - Vista previa de WhatsApp: seleccion de plantilla, fallback a defaults y render de datos de ejemplo.
- `services/settings_business_action_service.py`
  - Snapshot del formulario y guardado operativo de negocio, marketing y WhatsApp fuera de `MainWindow`.
- `services/settings_client_action_service.py`
  - Snapshots de prompt, mutaciones y QR de clientes fuera de `MainWindow`.
- `services/settings_marketing_action_service.py`
  - Recalculo de niveles e historial visible de marketing fuera de `MainWindow`.
- `services/settings_supplier_action_service.py`
  - Snapshots de prompt y mutaciones de proveedores fuera de `MainWindow`.
- `services/settings_user_action_service.py`
  - Snapshots de prompt y mutaciones de usuarios fuera de `MainWindow`.
- `services/settings_whatsapp_template_service.py`
  - Defaults, mapa actual y render reutilizable de plantillas de WhatsApp.

### UI global

- `ui/styles/main_window_styles.py`
  - Stylesheet principal extraido de `MainWindow` para que `_apply_styles()` quede como coordinador.
- `ui/styles/main_window_control_styles.py`
  - Seccion de botones, toolbars, inputs y tablas separada del stylesheet principal para seguir partiendolo por bloques reconocibles.
- `ui/styles/main_window_hero_cashier_styles.py`
  - Seccion visual de hero y cashier separada del stylesheet principal para reducir el bloque shell.
- `ui/styles/main_window_inventory_analytics_styles.py`
  - Seccion visual de inventory y analytics separada del stylesheet principal para dejar el shell en infraestructura base.

### Caja

- `ui/dialogs/cash_session_prompt_dialogs.py`
  - Prompts de apertura, movimientos, correccion y corte de caja extraidos de `MainWindow`.

### Apartados

- `ui/dialogs/create_layaway_dialog.py`
  - Prompt inline de crear apartado extraido de `MainWindow`, reutilizado tanto para alta directa como para convertir carrito.

### Catalogo

- `ui/dialogs/catalog_product_dialog.py`
  - Modal grande de producto extraido de `MainWindow`; la ventana principal ya solo delega la apertura y el payload final.
  - El modo `Ropa normal` ya oculta las plantillas y los campos/opciones escolares en vez de dejarlos visibles pero deshabilitados.
  - El modo `Ropa normal` ya ofrece sugerencias propias de categoria, linea, pieza, detalle y ubicacion para capturar prendas comerciales nuevas.
- `ui/dialogs/catalog_variant_dialog.py`
  - Dialogos de presentacion simple y por lote extraidos de `MainWindow`, manteniendo el guardado en los mismos handlers.
- `ui/helpers/catalog_form_payload_helper.py`
  - Armado y validaciones puras del payload de producto/presentacion fuera de `MainWindow`, reutilizadas por dialogos y handlers.
  - El payload de producto ya acepta categoria regular por nombre para poder resolverla/crearla al guardar.
- `ui/helpers/catalog_filter_helper.py`
  - La separacion `uniforme escolar / ropa normal` ya se basa en categoria uniforme vs no uniforme, no en `escuela = General`.

### Historial

- `ui/helpers/history_filter_helper.py`
  - Opciones visibles del filtro `Tipo` segun el origen seleccionado, reutilizadas por la vista y `MainWindow`.
- `ui/helpers/history_summary_helper.py`
  - Resumen visible de movimientos y filtros aplicados en la pestana Historial.
- `ui/helpers/history_table_helper.py`
  - Shape visible, orden, limite y tonos de la tabla de historial de inventario/catalogo fuera de `MainWindow`.

## Riesgo residual conocido

- `ui/main_window.py` sigue siendo el coordinador mas grande y sensible.
- Impresion y validacion Windows siguen como frente separado.
- Configuracion y algunas acciones de inventario aun dependen de handlers largos, pero ya no bloquean el cierre de `Fase 4`.
- Falta documentar por dominio con mas detalle.

## Proximo paso recomendado

- Entrar a `Fase 5. Optimizacion fina`.
- Priorizar polish visual, consistencia de vistas, respaldo automatico y estabilidad operativa antes de abrir modulos grandes nuevos.
