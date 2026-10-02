---
tags: [servicios, pos-uniformes]
---

# Servicios — Configuración y Marketing

**Cobertura de tests:** 87% (7/8) — `marketing_audit_service` sin tests ⚠️

---

## Servicios de Configuración

Todos actúan como **puente entre UI y servicios core** — reciben datos del diálogo y los delegan.

| Servicio | Función |
|---------|---------|
| `settings_business_action_service.py` | Carga y guarda configuración del negocio |
| `settings_user_action_service.py` | CRUD de usuarios del sistema |
| `settings_client_action_service.py` | CRUD de clientes |
| `settings_employee_action_service.py` | CRUD de empleadas |
| `settings_supplier_action_service.py` | CRUD de proveedores |
| `settings_marketing_action_service.py` | Configura descuentos, promociones, niveles |
| `settings_backup_action_service.py` | Respaldo y restauración de la BD |
| `settings_whatsapp_template_service.py` | Gestión de templates de WhatsApp |

---

## Servicios de Negocio (base)

### `business_settings_service.py`
Configuración general del negocio — **usado por 7 servicios distintos**.
- Nombre del negocio, logo, información de contacto
- Descuentos por nivel de lealtad
- Templates de WhatsApp
- Información de transferencias bancarias
- Configuración de impresora

### `business_payment_settings_service.py`
Sub-servicio de métodos de pago habilitados.

### `business_print_settings_service.py`
Sub-servicio de configuración de impresora y formato de ticket.

---

## Servicios de Marketing y Auditoría

### `manual_promo_service.py`
Autenticación de promociones manuales con código hash.
- Usa: `auth_service`
- Guarda en `AutorizacionPromocionManual`

### `marketing_audit_service.py`
Registra cambios en configuración de marketing en `CambioMarketingConfiguracion`.
- Tests: ✗ (pendiente)

---

## Configuración de WhatsApp

El sistema genera mensajes automáticos de WhatsApp para:
- Presupuestos emitidos
- Confirmaciones de apartado
- Mensajes personalizados al cliente

Los templates se editan desde `Configuración > WhatsApp y mensajes`:
- Tarjeta por plantilla
- Placeholders visibles
- Chips de inserción rápida
- Vista previa en tiempo real

---

## Respaldos

El sistema de respaldo maneja:
- Respaldo manual desde Configuración
- Respaldo automático programado (`scripts/run_scheduled_backup.py`)
- Restauración desde archivo

Ver: `docs/estrategia_respaldos_automaticos.md`

---

## Tabla `ConfiguracionNegocio`

Configuración singleton por negocio. Campos principales:
- `nombre_negocio`, `logo_path`, `telefono`, `direccion`
- Descuentos por nivel (BASICO, LEAL, PROFESOR, MAYORISTA)
- Templates de mensajes WhatsApp
- Datos de transferencia bancaria
- Configuración de impresora/ticket

---

## UI relacionada

- `ui/views/settings_view.py` — tab de Configuración
- `ui/dialogs/settings_dialogs.py` — 968 líneas de formularios
- `ui/dialogs/settings_prompt_dialogs.py` — confirmaciones

---

## Ver también
- [[09 - Servicios - Clientes y Lealtad]] — umbrales de lealtad configurados aquí
- [[13 - Servicios - Utilidades]] — `backup_service`
