---
name: cambio-codigo-pos
description: Flujo para agregar o corregir funcionalidad en el POS (pos_uniformes/) respetando el protocolo de cambios seguros: lógica en services/ con pruebas, main_window.py solo conecta, migración Alembic si cambia el esquema, y verificación con pytest. Usar en cualquier feat/fix de caja, catálogo, inventario, apartados, presupuestos, kiosko o satélite, Libreta, nómina, Telegram, bodega o API.
---

# Cambio de código en el POS

## 1. Ubicar antes de leer de más

- Revisar que la rama salga del tronco vivo y no de `main` (`git log -1 --format=%cs` reciente). Ver `CLAUDE.md`.
- Para entender el dominio, leer primero la nota del vault que lo cubre (está listada en `POS Uniformes/00 - Índice General.md`) en vez de explorar muchos archivos de código.
- Buscar con `grep -rn` el texto de la UI o el nombre del dominio en `pos_uniformes/services/` y `pos_uniformes/ui/`. **No leer `ui/main_window.py` completo**: buscar el método exacto y leer solo ese rango.
- Si ya existe un servicio del dominio, extenderlo en vez de crear otro.
- Si el cambio toca UI **y** base de datos a la vez, avisar y partirlo.

## 2. Implementar

- **Regla de negocio:** función o clase pura en `services/<dominio>_service.py`, sin Qt y sin sesión de base de datos si se puede (recibe datos y regresa un dataclass o un dict).
- **UI nueva:** un dialog, vista o helper propio en `ui/dialogs/`, `ui/views/` o `ui/helpers/`. En `main_window.py` solo se conecta la señal.
- **API:** router en `api/routers/`, schema en `api/schemas/` y lógica en `services/`.
- Usar dinero con `Decimal`, nunca `float`. Mensajes al usuario en español; al personal se le muestran nombres, nunca códigos como `VEND-1`.

## 3. Si cambia el esquema

- Modelo en `pos_uniformes/database/models.py`. Migración en `pos_uniformes/migrations/versions/` con `revision`, `down_revision` = head actual, `upgrade()` y `downgrade()`. Para sacar el head:
  ```bash
  cd pos_uniformes && "$PY" -m alembic heads
  ```
- **No correr `alembic upgrade` contra la caja** sin el OK de Daniel. Al cerrar, recordarle qué migraciones faltan aplicar en la tienda.

## 4. Pruebas

Desde `pos_uniformes/`, no desde la raíz:
```bash
"$PY" -m pytest tests/test_<servicio>.py -q                      # la nueva primero
"$PY" -m pytest tests --fast -q > /tmp/t.log 2>&1; tail -3 /tmp/t.log
```
Mostrar solo el resumen y los nombres de las pruebas que fallan. Las pruebas marcadas `db` necesitan PostgreSQL. Si fallan por conexión, decirlo y no darlas por regresión. La suite completa (`-n 6`) se cuelga hoy en la Mac (ver `CLAUDE.md`). No esperarla: avisar que no corrió.

## 5. Cerrar

- Dar la verificación manual por dominio, según `pos_uniformes/docs/protocolo_cambios.md`.
- Si cambia lo que se ve en el `.exe`, preguntar si hay que subir `pos_uniformes/VERSION`.
- Commit: `feat(<dominio>): …` o `fix(<dominio>): …`, en español, explicando el porqué.
- Documentar con la skill `actualizar-vault`: nota del dominio y `21 - Sesión de Trabajo`. **No** escribir en `pos_uniformes/docs/obsidian/`.
