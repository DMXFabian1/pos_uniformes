# Arquitectura Actual

## Flujo de arranque

1. `main.py` arranca la aplicacion.
2. Se ejecuta `database/preflight.py` para validar conexion y version de esquema.
3. Se crea `QApplication`.
4. `ui/login_dialog.py` autentica al usuario.
5. `ui/main_window.py` carga la ventana principal y refresca vistas.

## Piezas principales

### Entrada y control general

- `main.py`: punto de entrada.
- `ui/main_window.py`: orquestador principal de la UI.
- `ui/login_dialog.py`: acceso de usuario.

### Persistencia

- `database/connection.py`: engine, sesiones y `Base`.
- `database/models.py`: modelos ORM.
- `database/preflight.py`: chequeos previos de DB y esquema.
- `migrations/`: historial Alembic.

### Servicios de dominio

- `services/`: logica de negocio, auditoria, backup, caja, ventas, inventario, clientes y helpers puros.

### Vistas y dialogs

- `ui/views/`: construccion de tabs.
- `ui/dialogs/`: dialogs auxiliares.

### Utilidades

- `utils/`: QR, etiquetas, plantillas y helpers varios.

### Scripts operativos

- `scripts/backup_database.py`: respaldo.
- `scripts/restore_database.py`: restauracion.
- `scripts/check_startup_health.py`: smoke operativo de arranque.

## Estado actual de acoplamiento

### Fuerte

- `ui/main_window.py` sigue concentrando coordinacion de:
  - caja
  - catalogo
  - inventario
  - configuracion
  - historial
  - clientes

### Medio

- `ui/views/` ya separa construccion visual, pero mucha logica de eventos sigue en `ui/main_window.py`.

### Bajo

- Varios bloques criticos de caja y filtros ya fueron extraidos a servicios puros bajo `services/`.

## Estrategia de evolucion

- Mantener `main_window.py` como coordinador.
- Mover reglas puras a `services/`.
- Mover handlers grandes por dominio en fases posteriores.
- Documentar cada extraccion para no perder trazabilidad.
