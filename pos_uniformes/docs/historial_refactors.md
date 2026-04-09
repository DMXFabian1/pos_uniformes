# Historial de Refactors y Checkpoints

## Checkpoint actual

- `2026-04-08`: `Conteo fisico` abre su primer bloque de `V2` con checkpoint `validated-tests`: si `Inventario` tiene filas seleccionadas, el dialogo arranca con ese lote base ya sembrado y permite ajustar el `Contado` por fila dentro de la misma tabla; si entra sin lote previo, el `SKU` trabaja en modo de escaneo acumulado y cada lectura suma 1 al `Contado` de la fila. La extension a `todo lo filtrado` queda separada como siguiente paso para no precargar lotes accidentales demasiado grandes. Validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `Inventario` hace mas evidente su seleccion multiple: mantiene `ExtendedSelection` para clic salteado con `Ctrl/Cmd`, muestra una pista visible en la tabla y agrega `Esc` para limpiar la seleccion actual sin dejar el panel derecho pegado a la ultima fila. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `Inventario` suma una `V1` experimental y reversible para impresion por lote de etiquetas: si hay varias filas seleccionadas, el boton `Imprimir etiqueta(s)` abre `ui/dialogs/inventory_label_batch_dialog.py`, donde el operador define cantidad por presentacion y reutiliza el mismo motor de render/print existente. Rollback simple: quitar la rama `_handle_inventory_print_label_batch(...)`, restaurar el texto del boton y eliminar el dialogo nuevo. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: se corrige un crash real al activar/desactivar producto o presentacion desde `Inventario`/`Catalogo`: el handler armaba llaves de resultado en espanol (`activar` / `desactivar`) pero el helper de feedback solo aceptaba `activate` / `deactivate`. El contrato queda unificado y cubierto con prueba. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: los handlers de activar/desactivar producto/presentacion endurecen la restauracion de seleccion despues del refresh. Si la fila ya no sigue visible tras la mutacion, `Catalogo` e `Inventario` limpian seleccion y celda actual en lugar de dejar foco colgado sobre una fila inexistente. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: el dialogo de `Corte de caja` simplifica su bloque informativo cuando no hubo movimientos: conserva `Apertura`, `Reactivo inicial` y `Esperado en caja`, y solo despliega el desglose de reactivos, ingresos, retiros, ventas y abonos cuando existe actividad real. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: el rol `CAJERO` deja de ver el descuento manual en `Caja` y el hero ya no muestra `Reactivo inicial`; en su lugar queda una linea operativa mas discreta (`Caja abierta` / `Corte pendiente`) sin exponer montos sensibles ni controles muertos de `ADMIN`. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `CAJERO` deja de ver la pestaña `Resumen` en el POS principal y, si por alguna razon cae en ese indice, la navegacion lo redirige a `Caja`. El objetivo es mantener el rol en pantallas operativas y evitar exponer contexto global innecesario. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: el hero del POS principal deja de mostrar `Esperado` en la linea publica de sesion de caja y conserva solo `Reactivo inicial` y `Corte pendiente`, reduciendo exposicion innecesaria de montos sensibles sin tocar calculos internos ni pantallas de arqueo. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `Presupuestos` del POS principal recupera contraste legible en las etiquetas del formulario (`Escaneo`, `Folio`, `Vigencia`, `Observacion`) al dejar de reutilizar el estilo frio de `Caja` y usar un `quoteFormLabel` propio, coherente con el bloque beige del editor. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `Inventario` corrige la agrupacion de tallas con guion dentro del selector multiple: los rangos numericos dejan de ir a un bloque aparte y ahora conviven con `Numericas`, reduciendo saltos visuales dentro de la misma familia de talla. El helper compartido deja a `Catalogo` con el mismo criterio. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: la app satelite devuelve solo sus fondos y superficies de apoyo a la familia beige original para bajar la sensacion azul/gris, manteniendo intactos el hero naranja, los bordes y los acentos ya alineados con el POS principal. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: la app satelite recupera un header hero naranja alineado con el POS principal, manteniendo el resto de la paleta mas neutral. El ajuste se limita a `satHeaderCard`, `satTitle`, `satMeta` y `satStatus`. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: la app satelite acerca su paleta base al POS principal: cards, group boxes, estados, summaries, meta cards y cabeceras de tabla pasan a la familia azul/gris neutral, dejando el naranja como acento principal en lugar de color dominante. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `Catalogo` en la app satelite elimina el footer inferior de estado porque duplicaba informacion ya visible en la paginacion superior y podia empalmarse con la ultima fila del listado. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: los chips removibles de `Catalogo` en la app satelite recuperan el mismo tratamiento visual del POS principal (`chipButton` base, hover y estado activo), corrigiendo el texto lavado/blanco que aparecia al no existir reglas locales para ese componente. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `Catalogo` en la app satelite gana separacion real entre la tabla y el estado inferior, dejando el footer sin empalmarse con la ultima fila visible cuando el listado queda justo al borde. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `Catalogo` en la app satelite restaura los encabezados visibles de la tabla despues de confirmar en validacion manual que seguian siendo necesarios para orientar lectura por columna. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `Catalogo` en la app satelite suma chips removibles para `texto`, `nivel`, `escuela` y `ruta`, reutilizando la misma base de tokens/chips del POS principal y tratando `Escuela + extras generales` como estado base sin chip visible. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: la tabla de `Catalogo` en la app satelite oculta su fila de encabezados para quedarse solo con el listado visual, sin tocar columnas, seleccion ni paginacion. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: el `Catalogo` de la app satelite adopta la misma jerarquia visual base del POS principal: el resumen visible baja debajo de la tabla y el tercer selector arranca en `Solo escuela` para mantener el flujo escolar como ruta por defecto. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `Catalogo` ajusta la jerarquia del strip de filtros: la paginacion y los chips removibles quedan arriba, mientras el resumen `resultados | stock | ap. | fallbacks` baja debajo de la tabla para no competir con los controles activos. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-08`: `Catalogo` porta el desmontaje visual de filtros activos con chips removibles, reutilizando la misma base de tokens que `Inventario` y dejando la etiqueta interna `tipo_uniforme` fuera de la UI visible en favor de `Linea`. Checkpoint `validated-tests`; validacion manual en Windows queda `pending-manual`.
- `2026-04-06`: checkpoint general `validated-tests` para la ronda de mejoras de QR/build/login/carga/tablas/cierre. `check_startup_health.py` queda en verde y la suite completa queda en verde con `636` pruebas.
- `2026-04-06`: `build` de Windows queda mejor preparado con `packaging/windows/pos_uniformes_windows.spec`, `packaging/windows/presupuestos_satelite_windows.spec` y `utils/pyinstaller_data_helper.py` para incluir `pos_uniformes/migrations` y `pos_uniformes/assets/qr_icons`. Validacion real del bundle queda `pending-manual` en Windows.
- `2026-04-06`: QR queda endurecido con checkpoint `validated-tests`: el preview ya no depende de relaciones fuera de sesion, y `utils/qr_generator.py` tolera la falta o fallo del icono central sin cerrar la app.
- `2026-04-06`: `login` y arranque entran a checkpoint `validated-tests`: logo, nombre y version visibles, login persistente durante carga, mensaje `Cargando aplicacion...`, cursor de espera controlado y helpers reutilizables para estados de carga y salida segura.
- `2026-04-06`: `Caja`, `Catalogo`, `Inventario`, `Apartados`, `Presupuestos`, `Analitica` y varios dialogs operativos entran a un checkpoint `validated-tests` de coherencia visual: el naranja queda como identidad/acento, mientras tablas, cards, KPIs, banners y badges pasan a una base mas neutra y legible.
- `2026-04-06`: las tablas operativas quedan mas consistentes con checkpoint `validated-tests`: `SKU` se retira de Caja, Apartados y Presupuestos en los puntos acordados, y `Cantidad` pasa al inicio para facilitar el escaneo visual.
- `2026-04-06`: Caja entra a checkpoint `validated-tests` para la politica temporal de stock: el bloqueo por stock insuficiente sale del flujo operativo y queda centralizado en `services/sale_stock_policy.py` para poder endurecerlo despues desde un solo punto.
- `2026-04-06`: la maqueta `deportivo 2pz -> 3pz` entra a checkpoint `validated-tests`: pregunta por playera, valida misma escuela, permite talla distinta, deja trazabilidad interna y agrega sugerencia de tallas reusable como guia `Exacta / Sugerida / Atipica`. La expansion a otros flujos queda `pending-manual`.
- `2026-04-06`: `layaway_receipt_text_service.py`, `caja_service.py` y `cash_session_history_service.py` dejan un checkpoint `validated-tests` para comprobante de apartado simplificado, cierre de caja sin inflar esperado por apartados cancelados e historial recalculado con montos consistentes.
- `2026-04-06`: se corrigen regressions de estabilidad detectadas por la suite: compatibilidad de snapshot de Catalogo con tuplas legacy/nuevas y restauracion del contrato de navegacion/seleccion en `ui/quote_satellite_window.py`. Checkpoint `validated-tests`.
- `2026-03-27`: el pulido de `WhatsApp` queda alineado entre `Presupuestos` del POS principal y la app satelite: mismo servicio de mensaje, copy mas claro, boton `Compartir por WhatsApp` y bloque de salida consistente en ambos flujos. Checkpoint `validated-manual`.
- `2026-03-27`: `WhatsApp y mensajes` en `Configuracion` entra a un checkpoint `validated-tests` de pulido UX: dialogo mas ancho, tarjetas por plantilla, guia visible de placeholders, chips para insertar variables rapido y vista previa que se actualiza al escribir. Se mantiene intacta la logica de guardado actual.
- `2026-03-27`: `Conteo fisico` entra a una `V1` con checkpoint `validated-tests`: flujo rapido por `SKU`, lote acumulado, resumen visible y confirmacion final antes de aplicar. La aplicacion real del ajuste sigue reutilizando `InventarioService.registrar_ajuste_manual(...)`. Validacion manual de UI queda `pending-manual`.
- `2026-03-27`: el `login` del POS principal queda `validated-manual` con selector visible de usuarios activos en `ComboBox`, nombre limpio sin sufijos de marca, ultimo usuario recordado y foco automatico a contrasena al elegir usuario.
- `2026-03-27`: `Presupuestos` del POS principal entra a un checkpoint `validated-manual` de pulido fino: bloque `Presupuesto actual` reordenado y alineado visualmente con la app satelite, `vigencia` por defecto a `+7 dias`, cliente base `Sin cliente asignado`, captura rapida sin cantidad arriba, ajuste por linea con `-1 / +1`, `WhatsApp` integrado en presupuestos recientes y `Detalle seleccionado` con mejor jerarquia visual.
- `2026-03-27`: la app satelite de Presupuestos ya arranca sin `login`, resolviendo automaticamente un operador activo con rol `CAJERO` o `ADMIN` desde base de datos. Checkpoint `validated-manual`.
- `2026-03-27`: la app satelite de Presupuestos queda `validated-manual` para `Kiosko`, `Catalogo`, `Presupuesto guiado`, `Presupuesto`, `Buscar`, `Compartir` e impresion. `WhatsApp` queda funcional, con pulido de UX/copy pendiente a resolver primero en el POS principal y luego portar al satelite.
- `2026-03-26`: validacion manual operativa confirmada para `Catalogo` e `Inventario` despues de la optimizacion de filtros, resumen compacto y paginacion visible de `25` filas. Checkpoint `validated-manual`.
- `2026-03-25`: `Catalogo` e `Inventario` reutilizan el snapshot base entre cambios de filtros y busqueda, evitando reconstruir toda la consulta en cada tecla. La invalidacion ocurre en `refresh_all()` y cuando Inventario regenera QR. Checkpoint `validated-tests`.
- `2026-03-25`: `Inventario` memoiza la presencia de QR por `SKU` durante la sesion y limpia ese cache al generar QR individuales o masivos, reduciendo chequeos repetidos al filesystem. Checkpoint `validated-tests`.
- `2026-03-25`: la busqueda de `Catalogo` e `Inventario` ahora aplica debounce corto solo al tecleo del input, mientras `Enter` y los demas filtros siguen actualizando al momento. Checkpoint `validated-tests`.
- `2026-03-25`: `Catalogo` e `Inventario` reconstruyen sus tablas con updates/senales suspendidos y ya no fuerzan `resizeColumnsToContents()` en cada refresh, reduciendo repintado y recalculo de layout. Checkpoint `validated-tests`.
- `2026-03-25`: el snapshot de `Catalogo` e `Inventario` ahora precalcula blobs normalizados de busqueda general y por alias, evitando volver a normalizar los mismos campos en cada filtro o tecleo. Checkpoint `validated-tests`.
- `2026-03-25`: la busqueda textual ahora compila sus terminos una sola vez por refresh y `Catalogo`/`Inventario` evaluan primero filtros exactos antes del matcher textual, reduciendo trabajo repetido cuando cambian busqueda y filtros. Checkpoint `validated-tests`.
- `2026-03-25`: `Catalogo` ahora pagina el listado visible en bloques de `25` resultados con controles `Anterior/Siguiente`, reduciendo el costo de pintar miles de celdas por refresh sin cambiar el filtrado base. Checkpoint `validated-tests`.
- `2026-03-25`: `Inventario` ahora replica el patron compacto de `Catalogo`: resumen corto, navegacion `Anterior/Siguiente` y tabla paginada en bloques de `25` resultados, manteniendo la lista filtrada completa para acciones masivas. Checkpoint `validated-tests`.
- `2026-03-26`: se elimina la indicacion de doble clic en `Catalogo` para no prometer una accion que hoy no existe en esa tabla. Checkpoint `validated-manual`.
- `2026-03-20`: `Fase 4` queda cerrada con checkpoint `validated-manual`.
- `2026-03-20`: `Resumen` entra a `Fase 5` con mejor jerarquia visual: KPIs arriba, contexto debajo y zona reservada para futuras notificaciones sin construir todavia el sistema completo. El dashboard ahora suma tarjetas con contexto corto, tonos suaves y microalertas operativas legibles sin duplicar reglas de Analytics. Checkpoint `validated-tests`.
- `2026-03-20`: `Historial` entra a `Fase 5` con rangos rapidos (`Hoy`, `7 dias`, `30 dias`, `Mes actual`), tabla mas legible, panel lateral de detalle, busqueda mas guiada y exportacion del filtro actual a CSV/JSON. Checkpoint `validated-tests`.
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

### Fase 5

- `services/backup_service.py`
  - Ahora tambien concentra el estado visible del respaldo automatico, para que la tarea programada y Configuracion lean la misma fuente de verdad.
- `scripts/run_scheduled_backup.py`
  - Runner listo para tarea programada; genera respaldo automatico, aplica rotacion y actualiza el estado visible para Configuracion.
- `ui/helpers/settings_backup_helper.py`
  - Resume si el respaldo automatico esta OK, viejo o si fallo la ultima ejecucion, sin cargar esa logica a `MainWindow`.
- `ui/dialogs/settings_dialogs.py`
  - La vista de respaldos ahora muestra un bloque propio con el estado del respaldo automatico.
- `ui/views/analytics_view.py`
  - Analitica se compacta con rangos rapidos, mejor jerarquia visual y una franja corta de alertas operativas.
- `ui/helpers/analytics_summary_helper.py`
  - Comparativos del periodo actual vs el anterior y alertas pequenas de stock, apartados vencidos y respaldo automatico.
- `ui/helpers/analytics_payment_helper.py`, `ui/helpers/analytics_top_products_helper.py`, `ui/helpers/analytics_top_clients_helper.py`, `ui/helpers/analytics_stock_helper.py`
  - Las tablas de Analitica ahora cargan tonos y jerarquia visual mas claros para resaltar top 1, caidas y stock critico.
- `ui/views/cashier_view.py`, `ui/helpers/sale_cashier_panel_helper.py`, `services/sale_cart_update_service.py`
  - Caja entra a pulido fino: el cliente visible queda fijo en `Mostrador / sin cliente` salvo QR/codigo, el carrito gana ajustes rapidos de cantidad `-1 / +1`, y la tabla/contexto de venta se ordenan para leer mejor cliente, pago y descuento.
- `ui/helpers/sale_cashier_panel_helper.py`, `ui/views/cashier_view.py`, `ui/main_window.py`
  - Caja ahora muestra un estado vivo de cobro (`lista`, `caja cerrada`, `procesando`, `solo lectura`) separado del feedback transitorio, para que el operador vea de un vistazo si la venta ya puede cobrarse y por que.
- `ui/views/inventory_view.py`
  - Se oculto la banda superior de resumen contextual (`SKU | producto | precio | stock | apartado`) dentro de `Acciones rapidas` para desaturar la vista; la logica interna del label sigue viva para poder revertirlo facil si luego hace falta.
- `ui/dialogs/inventory_count_dialog.py`
  - La `Referencia` de `Conteo fisico` ahora se autogenera al abrir el dialogo y queda en solo lectura, para tratarla como folio fijo del lote y evitar ediciones manuales accidentales.
- `ui/dialogs/cash_session_prompt_dialogs.py`, `ui/main_window.py`
  - Caja ahora expone `Corte administrativo` como retiro formal solo para `ADMIN`, protegido con PIN y registrado como movimiento real de caja para que el esperado del cierre siga siendo consistente.
- `database/models.py`, `services/venta_service.py`, `services/sale_checkout_action_service.py`, `ui/views/cashier_view.py`, `ui/main_window.py`
  - Primer corte real de `Origen en Caja`: la venta ya persiste `credit_mode` y campos base de responsable, `Caja` muestra el bloque `Responsable` y permite marcar `Directa` o volver a `Sin asignar`; `Identificar` queda visible como siguiente corte para enlazar QR de equipo sin mezclarlo aun con una tabla de empleadas.
- `database/models.py`, `services/employee_identity_service.py`, `services/settings_employee_action_service.py`, `ui/views/settings_view.py`, `ui/dialogs/settings_dialogs.py`, `ui/main_window.py`
  - Segundo corte de `Origen en Caja`: ya existe la base minima de `Empleadas` en `Configuracion`, `Caja` resuelve escaneos `EMP:{codigo}` contra esa tabla y el bloque `Responsable` cambia a nombre humano corto; tambien se quito el boton visible `Identificar` para dejar el QR como camino principal.
- `services/employee_card_service.py`, `services/settings_employee_action_service.py`, `ui/dialogs/settings_dialogs.py`, `ui/helpers/settings_employees_helper.py`, `ui/main_window.py`
  - `Empleadas` ahora puede generar una credencial visual propia, separada del QR, con layout sobrio tipo lealtad pero ajustado a `Staff`: sin `POS Uniformes`, sin leyenda extra y con acento negro; la tabla de Configuracion muestra `QR` y `Credencial` como estados independientes.
- `assets/employee_card_template/employee-card.html`, `assets/employee_card_template/employee-card.css`, `services/employee_card_service.py`
  - La credencial de `Staff` ya no parte de un render austero en PIL: ahora usa una plantilla HTML/CSS hermana de la credencial de cliente para heredar mejor jerarquia visual, texturas y balance, manteniendo `Staff`, nombre corto, codigo y QR como unico contenido visible.
- `database/models.py`, `services/employee_identity_service.py`, `services/settings_employee_action_service.py`, `ui/dialogs/settings_prompt_dialogs.py`, `ui/dialogs/settings_dialogs.py`, `ui/main_window.py`
  - `Empleadas` ahora incluye `PIN` como parte de su identidad administrable: se guarda hasheado con PBKDF2, se define solo desde `Configuracion`, la tabla muestra `PIN` como `Listo/Pendiente` y el uso operativo del PIN en `Caja` queda separado para un corte posterior.
- `services/employee_activity_service.py`, `ui/dialogs/settings_dialogs.py`, `ui/main_window.py`
  - `Empleadas` gana un panel lateral pensado para `ADMIN`: muestra detalle de la seleccion y un resumen de los ultimos 7 dias con `Piezas`, `Tickets`, `Monto` y `Ultima venta`, sin saturar la tabla principal.

## Riesgo residual conocido

- `ui/main_window.py` sigue siendo el coordinador mas grande y sensible.
- Impresion y validacion Windows siguen como frente separado.
- Configuracion y algunas acciones de inventario aun dependen de handlers largos, pero ya no bloquean el cierre de `Fase 4`.
- Falta documentar por dominio con mas detalle.

## Proximo paso recomendado

- Entrar a `Fase 5. Optimizacion fina`.
- Priorizar polish visual, consistencia de vistas, respaldo automatico y estabilidad operativa antes de abrir modulos grandes nuevos.
