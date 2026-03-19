# Protocolo de Cambios Seguros

## Antes de tocar codigo

1. Identificar el dominio afectado.
2. Confirmar si ya existe un servicio puro para esa regla.
3. Revisar `docs/mapa_modulos.md`.
4. Revisar `docs/historial_refactors.md`.

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

- `./.venv/bin/python scripts/check_startup_health.py`
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`

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
