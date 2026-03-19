# Historial de Refactors y Checkpoints

## Checkpoint actual

- Precheck de arranque activo.
- Suite de pruebas activa.
- Base actual validada con `check_startup_health.py`.
- Busqueda textual endurecida para tolerar alias con comillas mal cerradas sin dejar al operador con resultados vacios silenciosos.
- Busqueda textual endurecida para tolerar comparaciones sin acento contra catalogo real con nombres y variantes acentuadas.
- Ticket de venta documentado y con correccion tolerante para descuentos faltantes en ventas antiguas.
- Validacion manual confirmada para `Ventas recientes -> Ver ticket`.
- Ventas recientes delega el listado visible a `services/recent_sale_service.py` y reutiliza una sola lectura de venta seleccionada para ticket y cancelacion.
- Caja delega el armado visible del carrito y del bloque total a `ui/helpers/sale_cashier_view_helper.py`.
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

### Caja

- `services/sale_client_benefit_service.py`
  - Beneficio visible del cliente en Caja a partir de descuento preferente y nivel de lealtad.
- `services/sale_selected_client_service.py`
  - Carga del cliente seleccionado en Caja y resolucion compartida de su beneficio visible.
- `services/sale_discount_service.py`
  - Descuentos, desglose y totales.
- `ui/helpers/sale_cart_table_helper.py`
  - Filas visibles del carrito y conteo total de piezas para Caja.
- `ui/helpers/sale_cashier_summary_helper.py`
  - Resumen visible del bloque total en Caja sin referencia del cliente.
- `services/manual_promo_flow_service.py`
  - Estado, decision y transicion de promo manual fuera de `MainWindow`.
- `services/sale_note_service.py`
  - Notas operativas de la venta.
- `services/sale_checkout_service.py`
  - Snapshot del cliente en checkout y resolucion del aviso de lealtad post-venta.
- `services/sale_loyalty_notice_service.py`
  - Mensajes de transicion de lealtad.
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
- `services/sale_selected_client_service.py`
  - Carga el beneficio del cliente seleccionado y expone el descuento efectivo con fallback a cero para Caja.

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
- `services/sale_payment_note_service.py`
  - Detalles puros de cobro y notas operativas por metodo de pago.
- `services/layaway_payment_service.py`
  - Estado y normalizacion del abono segun metodo de pago para apartados.
- `services/sale_rounding_service.py`
  - Regla pura de redondeo posterior al descuento.
- `ui/dialogs/payment_dialogs.py`
  - Dialogos de efectivo, transferencia y mixto fuera de `MainWindow`.
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
- `ui/helpers/catalog_access_helper.py`
  - Estado visible del tab Catalogo segun rol: mensaje de permiso, acciones habilitadas y visibilidad de caja rapida.
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
  - Resumen visible de marketing por nivel de lealtad, sin cargar clientes completos en `MainWindow`.
- `ui/helpers/marketing_history_helper.py`
  - Shape visible y estado del historial de marketing fuera de `MainWindow`.
- `ui/helpers/settings_suppliers_helper.py`
  - Listado visible y estado del modulo de proveedores en Configuracion.
- `ui/helpers/settings_users_helper.py`
  - Listado visible y estado del modulo de usuarios en Configuracion.
- `ui/helpers/settings_whatsapp_preview_helper.py`
  - Vista previa de WhatsApp: seleccion de plantilla, fallback a defaults y render de datos de ejemplo.

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

### Historial

- `ui/helpers/history_filter_helper.py`
  - Opciones visibles del filtro `Tipo` segun el origen seleccionado, reutilizadas por la vista y `MainWindow`.
- `ui/helpers/history_summary_helper.py`
  - Resumen visible de movimientos y filtros aplicados en la pestana Historial.
- `ui/helpers/history_table_helper.py`
  - Shape visible, orden, limite y tonos de la tabla de historial de inventario/catalogo fuera de `MainWindow`.

## Riesgo residual conocido

- `ui/main_window.py` sigue siendo el coordinador mas grande y sensible.
- Configuracion y algunas acciones de inventario aun dependen mucho de handlers largos.
- Falta documentar por dominio con mas detalle.
- Falta validacion manual visual de caja con redondeo ya conectado al total de cobro.

## Proximo paso recomendado

- Si seguimos buscando recortes grandes y seguros, el siguiente candidato natural es un lote masivo de inventario.
- Registrar aqui cada nuevo checkpoint antes de pasar a otro dominio.
