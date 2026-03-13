# Mapa de Modulos

## Entrada

- `main.py`
  - Arranque de la app.
  - Ejecuta precheck de DB.
  - Abre login y ventana principal.

## Base de datos

- `database/connection.py`
  - Configura engine y sesiones.
- `database/models.py`
  - Define entidades ORM.
- `database/preflight.py`
  - Verifica conexion y revision Alembic antes de abrir la app.

## UI principal

- `ui/main_window.py`
  - Coordinador central de eventos, refrescos y acciones.
  - Aun es el archivo mas sensible del sistema.
- `ui/login_dialog.py`
  - Autenticacion de entrada.

## Tabs visuales

- `ui/views/dashboard_view.py`
  - Resumen general.
- `ui/views/cashier_view.py`
  - Construccion visual de caja.
- `ui/views/products_view.py`
  - Construccion visual de catalogo.
- `ui/views/inventory_view.py`
  - Construccion visual de inventario.
- `ui/views/history_view.py`
  - Vista de historial.
- `ui/views/quotes_view.py`
  - Vista de presupuestos.
- `ui/views/layaway_view.py`
  - Vista de apartados.
- `ui/views/analytics_view.py`
  - Vista de analitica.
- `ui/views/settings_view.py`
  - Vista de configuracion.

## Dialogs

- `ui/dialogs/settings_dialogs.py`
  - Dialogs de configuracion y ajustes administrativos.

## Servicios de dominio

- `services/auth_service.py`
  - Hash y validacion de password.
- `services/business_settings_service.py`
  - Configuracion general del negocio.
- `services/caja_service.py`
  - Sesiones y movimientos de caja.
- `services/catalog_service.py`
  - Catalogo y SKU.
- `services/catalog_audit_service.py`
  - Auditoria de catalogo.
- `services/client_service.py`
  - Clientes.
- `services/compra_service.py`
  - Compras.
- `services/inventario_service.py`
  - Movimientos y ajustes de inventario.
- `services/loyalty_service.py`
  - Reglas de niveles y beneficios.
- `services/manual_promo_service.py`
  - Verificacion y auditoria de promo manual.
- `services/marketing_audit_service.py`
  - Historial de cambios de marketing.
- `services/presupuesto_service.py`
  - Presupuestos.
- `services/supplier_service.py`
  - Proveedores.
- `services/user_service.py`
  - Usuarios.
- `services/venta_service.py`
  - Ventas.
- `services/apartado_service.py`
  - Apartados.
- `services/backup_service.py`
  - Respaldos de DB.
- `services/bootstrap_service.py`
  - Datos base/demo.
- `services/customer_card_service.py`
  - Credenciales/QR de cliente.

## Servicios puros ya extraidos

- `services/sale_discount_service.py`
  - Reglas de descuentos y totales.
- `services/manual_promo_flow_service.py`
  - Estado y decisiones de promo manual.
- `services/sale_note_service.py`
  - Notas operativas de la venta.
- `services/sale_loyalty_notice_service.py`
  - Mensajes de cambio de nivel.
- `services/scanned_client_flow_service.py`
  - Decision y copy para cliente escaneado.
- `services/sale_discount_option_service.py`
  - Opciones del combo de descuento.
- `services/sale_discount_lock_service.py`
  - Estado de bloqueo de descuento por cliente.
- `services/sale_client_discount_service.py`
  - Resolucion del descuento efectivo del cliente.
- `services/search_filter_service.py`
  - Busqueda textual compartida.
- `services/active_filter_service.py`
  - Formateo de filtros activos.

## Utilidades

- `utils/qr_generator.py`
  - Generacion de QR.
- `utils/label_generator.py`
  - Generacion de etiquetas.
- `utils/product_templates.py`
  - Plantillas y sugerencias de productos.
- `utils/config.py`
  - Variables de entorno y configuracion local.

## Scripts operativos

- `scripts/check_startup_health.py`
  - Precheck rapido para detectar anomalias base.
- `scripts/backup_database.py`
  - Respaldo manual.
- `scripts/restore_database.py`
  - Restauracion.
- `scripts/create_initial_users.py`
  - Usuarios iniciales.
- `scripts/import_legacy_products.py`
  - Importacion legada.

## Pruebas

- `tests/`
  - Smoke de arranque.
  - Reglas puras extraidas de caja.
  - Filtros y busquedas.
  - Textos y decisiones operativas.
