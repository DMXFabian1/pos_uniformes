# Protocolo de Cambios Seguros

## Antes de tocar codigo

1. Identificar el dominio afectado.
2. Confirmar si ya existe un servicio puro para esa regla.
3. Revisar `docs/mapa_modulos.md`.
4. Revisar `docs/historial_refactors.md`.
5. Revisar `docs/plan_estabilizacion.md` y `docs/hoja_ruta_mejoras.md` para no abrir una iniciativa fuera de fase o repetir un frente ya documentado.

## Orden obligatorio de trabajo

1. Localizar el bloque exacto.
2. Detectar si es UI, regla de negocio o persistencia.
3. Si es regla pura, extraerla a `services/`.
4. Si es una mejora nueva, crearla fuera de `ui/main_window.py` y conectar desde ahi.
5. Agregar o ampliar pruebas.
6. Dejar a `ui/main_window.py` delegando.
7. Correr verificaciones.
8. Documentar el cambio.

## Verificaciones minimas

Despues de CADA cambio (rapido, ~4s, sin base ni Qt):

```
python -m pytest pos_uniformes/tests --fast -q
```

Antes de subir a produccion (todo, incluye base y Qt) — 1,681 tests, ~74s:

```
python -m pytest pos_uniformes/tests -q
python pos_uniformes/scripts/check_startup_health.py
```

Los grupos `db` y `qt` se marcan solos — no hay que decorar tests a mano. La
clasificacion vive en `tests/conftest.py` y se hace leyendo el fuente, sin
importar el modulo. Para correr un grupo suelto:

```
python -m pytest pos_uniformes/tests -m db -q
python -m pytest pos_uniformes/tests -m "not qt" -q
```

Nota: `--fast` omite los tests que necesitan PostgreSQL real o PyQt6. Son los
lentos y los que fallan fuera de la tienda; no los sustituye, los aplaza.

### Base de datos de pruebas

Los tests NUNCA tocan produccion: `tests/conftest.py` fuerza la conexion a
`127.0.0.1/pos_uniformes_test` y aborta la corrida si detecta que quedaron
apuntando a otra cosa. Antes de esto, correr la suite desde la Mac escribia en
la base real de la tienda.

Preparar esa base una vez por maquina:

```
psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE pos_uniformes_test"
POS_UNIFORMES_DB_HOST=127.0.0.1 POS_UNIFORMES_DB_NAME=pos_uniformes_test \
    ./.venv/bin/python -m alembic upgrade head
```

Y despues de cada migracion nueva, repetir el `alembic upgrade head` sobre
`pos_uniformes_test` para que no se quede atras.

Para diagnosticar contra una base real (en la tienda, con cuidado):

```
python -m pytest pos_uniformes/tests --db-real -q
```

## Verificacion manual sugerida por dominio

### Caja

- Login.
- Abrir caja si aplica.
- Venta con SKU.
- Venta con cliente.
- Promo manual.

### Catalogo e inventario

- Abrir `Productos`.
- Abrir `Inventario`.
- Probar filtros.
- Generar QR o etiqueta si el cambio toca eso.

### Configuracion

- Abrir `Configuracion`.
- Cargar datos.
- Guardar un cambio controlado.

## Senales de anomalia

- La suite pasa pero la UI muestra textos incoherentes.
- Cambia el orden de mensajes operativos.
- Se altera un permiso sin razon.
- Un flujo depende de DB cuando deberia ser puro.
- Se repite logica ya extraida a `services/`.

## Reglas para cambios complejos

- No hacer refactor grande en una sola entrega.
- No mezclar estructura y comportamiento nuevo.
- No mover dos dominios a la vez.
- No agregar mejoras nuevas directamente dentro de `ui/main_window.py`.
- Si una mejora necesita UI nueva, crear dialog, helper, vista o servicio propio y dejar a `main_window.py` solo enlazando.
- Si un cambio toca caja, cerrar con checkpoint documentado.

## Criterio para detenerse

Hay que pausar y revisar si:

- el cambio pide tocar UI y DB al mismo tiempo
- el archivo a mover no tiene comportamiento claro
- una prueba nueva obliga a reescribir demasiadas rutas a la vez
- la herramienta de edicion deja cambios parciales o inestables
