# Plan de Estabilizacion y Optimizacion

## Objetivo

Reducir riesgo operativo, sacar logica critica fuera de `ui/main_window.py`, mejorar trazabilidad y dejar una ruta clara para cambios complejos sin romper ventas, inventario o configuracion.

## Reglas del plan

- Un bloque funcional por vez.
- Cada bloque debe cerrar con checkpoint.
- No mezclar refactor y nuevas funciones en la misma fase.
- Si una fase toca caja, inventario o descuentos: pruebas y verificacion manual obligatorias.
- Todo cambio estructural debe dejar una nota en `docs/historial_refactors.md`.

## Fase 0. Base estable

### Objetivo

Tener una linea base repetible antes de seguir moviendo codigo.

### Trabajo

- Mantener el precheck de arranque.
- Mantener la suite en verde.
- Documentar arquitectura y protocolo.

### Checkpoint

- `./.venv/bin/python scripts/check_startup_health.py`
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`

### Anomalias a vigilar

- Conexion a PostgreSQL.
- Esquema fuera de sincronizacion con Alembic.
- Imports rotos en `main.py` o `ui/main_window.py`.

## Fase 1. Caja

### Objetivo

Blindar descuentos, promociones, cliente enlazado y notas de venta.

### Trabajo

- Extraer reglas puras de descuentos y promociones manuales.
- Separar decisiones de cliente escaneado.
- Separar textos operativos de venta.

### Checkpoint

- Suite verde.
- Venta manual validada con cliente y sin cliente.
- Promo manual validada con y sin autorizacion.

### Anomalias a vigilar

- Descuento acumulado por error.
- Promo manual autorizada con porcentaje incorrecto.
- Cambio de cliente que altera el beneficio sin confirmacion.

## Fase 2. Catalogo e Inventario

### Objetivo

Reducir duplicacion en filtros, busqueda, resumenes y acciones sobre variantes.

### Trabajo

- Consolidar filtros activos.
- Consolidar busqueda textual.
- Separar acciones de QR, etiquetas y ajustes.

### Checkpoint

- Filtros de catalogo e inventario responden igual que antes.
- QR y etiquetas siguen operando.
- No hay regresiones en resumenes visibles.

### Anomalias a vigilar

- Filtros que dejan de aplicar.
- Resultados visibles inconsistentes.
- Acciones contextuales que desaparecen o cambian de permisos.

## Fase 3. Configuracion y Marketing

### Objetivo

Separar carga, validacion, guardado y auditoria de configuracion.

### Trabajo

- Aislar reglas de negocio de dialogs.
- Consolidar validaciones administrativas.
- Ordenar auditoria de cambios.

### Checkpoint

- Configuracion carga y guarda sin perdida.
- Historial de marketing sigue registrando cambios.
- Plantillas y configuracion de impresora siguen disponibles.

### Anomalias a vigilar

- Configuracion que se guarda incompleta.
- Campos sensibles sin auditoria.
- Reglas de descuento alteradas desde configuracion.

## Fase 4. Extraccion estructural

### Objetivo

Reducir el rol de `ui/main_window.py` a coordinador.

### Trabajo

- Crear controladores o coordinadores por dominio.
- Mover handlers grandes fuera de la ventana principal.
- Dejar `main_window.py` orquestando UI y llamadas.

### Checkpoint

- `main_window.py` baja de tamano y responsabilidad.
- Cada dominio tiene entrada clara.
- Los flujos principales conservan pruebas.

### Anomalias a vigilar

- Dependencias circulares.
- Imports cruzados entre controladores y vistas.
- Doble responsabilidad entre UI y servicios.

## Fase 5. Optimizacion fina

### Objetivo

Mejorar mantenibilidad y rendimiento con el sistema ya estabilizado.

### Trabajo

- Limpiar duplicados restantes.
- Revisar consultas repetidas.
- Revisar refrescos de UI costosos.
- Consolidar utilidades compartidas.

### Checkpoint

- Cambios medibles y localizados.
- Ninguna optimizacion sin comparacion antes/despues.

### Anomalias a vigilar

- Refrescos parciales que dejan datos viejos.
- Consultas duplicadas que afectan tiempos de respuesta.
- Servicios nuevos que repiten reglas ya extraidas.

## Cierre por fase

Cada fase se considera cerrada solo si:

- La suite sigue en verde.
- El precheck sigue en verde.
- Se documenta lo movido.
- Se anota riesgo residual.
- Se registra checkpoint en `docs/historial_refactors.md`.
