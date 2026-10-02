---
tags: [servicios, pos-uniformes]
---

# Servicios — Empleadas

**Cobertura de tests:** 100% ✓
**Estado del módulo:** Servicios implementados, UI de gestión en Configuración — módulo completo de atribución y comisiones pendiente para post-Fase 5


> [!info] 2026-09: `load_employee_activity_snapshots()` (batch)
> Nueva versión batch de la actividad: UNA query de ventas para todas las empleadas (la versión singular ahora delega en ella). Eliminó el N+1 que congelaba la pestaña de Configuración al teclear. La Libreta ([[28 - Libreta Digital]]) es ahora la fuente operativa de comisiones por empleada.

---

## Servicios

### `employee_identity_service.py`
Resolución de empleadas por QR o código, identidad operativa.
- Usa: `auth_service`
- Permite atribuir una venta a una empleada específica

### `employee_card_service.py`
Renderiza la credencial visual de la empleada (similar a la de clientes).

### `employee_activity_service.py`
Snapshot de actividad reciente de la empleada.

### `employee_sales_history_service.py`
Historial de ventas por empleada y por día.

---

## Estado actual

Los servicios de empleadas **ya existen y tienen tests**, pero el módulo completo de:
- Atribución comercial por venta
- Cálculo de comisiones
- Reportes por empleada

Está planeado para después de cerrar la **Fase 5**.

---

## Atribución de venta a empleada

El modelo `Venta` tiene el campo `ModoOrigenVenta` que distingue:
- Venta normal (cajero)
- Venta por empleada (atribuida)
- Venta directa del operador

Esto ya está en el modelo pero el flujo completo de comisiones no está implementado.

---

## Acceso actual

Las empleadas se gestionan desde:
- `ui/views/settings_view.py` → sección de empleadas
- `services/settings_employee_action_service.py` → operaciones CRUD
- `ui/helpers/settings_employee_*` → presentación

---

> [!success] 2026-09-08 — nómina implementada en el kiosko
> `services/nomina_service.py` (1,300 + 2/comisión − faltas; modo por días), `equipo_service.py` (baja/reactivar), `pendientes_service.py`. No está en el POS principal: vive en la Libreta. Ver [[33 - Caja, Nómina y Corte Automático]].

## Próxima iniciativa

> Después de Fase 5: diseñar el módulo completo de **Empleadas / atribución comercial / comisiones**.
> 
> Regla de diseño ya definida: pensarlo desde el inicio para POS, kiosko y app móvil.
> Separar claramente `usuario` (quien opera el sistema) vs `empleada` (quien genera la venta).

---

## Ver también
- [[20 - Pendientes y Fase 5]] — cuándo se abre este módulo
- [[04 - Servicios - Ventas]] — campo `ModoOrigenVenta` en la venta
