# Checklist de Operacion

## Antes de trabajar

- Verifica que PostgreSQL este arriba.
- Genera un respaldo antes de cambios grandes:
  - `./.venv/bin/python scripts/backup_database.py`
- Abre la app e inicia sesion.

## Prueba rapida despues de cambios

- Login con `admin`.
- Abrir `Productos`.
- Abrir `Inventario`.
- Crear una presentacion nueva de prueba o editar una existente.
- Registrar una `entrada`.
- Ejecutar `Corregir stock`.
- Ejecutar `Conteo fisico` con una fila de prueba.
- Generar o regenerar un QR.
- Ir a `Caja` y vender por SKU.
- Revisar `Historial` para confirmar el movimiento.

## Reglas para no romper el sistema

- Haz un cambio funcional por vez.
- Prueba el flujo afectado antes de seguir.
- No borres productos con historial; usa desactivar.
- No edites directo en PostgreSQL salvo emergencia.
- Si un cambio toca inventario o ventas, respalda primero.

## Respaldo recomendado

- Respaldo SQL:
  - `./.venv/bin/python scripts/backup_database.py --format plain`
- Respaldo binario:
  - `./.venv/bin/python scripts/backup_database.py --format custom`
- Rotacion recomendada:
  - el script ya conserva 7 dias por defecto y elimina respaldos mas viejos del mismo formato

## Si algo sale mal

- Cierra la app.
- Genera un respaldo del estado actual antes de intentar corregir.
- Revisa `Historial` para identificar el movimiento.
- Si el problema fue de stock, usa `Corregir stock` o `Conteo fisico`.
- Si el problema fue estructural, vuelve a una version estable del codigo y restaura la base si hace falta.
